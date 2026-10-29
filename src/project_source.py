"""Capture and independently project the public release without recovering suppressed cells."""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import gzip, hashlib, io, json
from pathlib import Path
import sqlite3

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
STATES = "01 02 04 05 06 08 09 10 11 12 13 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50 51 53 54 55 56".split()


def write_json(path, data):
    path.write_bytes((json.dumps(data, indent=2) + "\n").encode())


def numeric(token):
    if token in ["", "D", "S", "X", "N"]:
        return None
    try:
        value = Decimal(token)
    except InvalidOperation:
        raise AssertionError("Unrecognized source token: " + token)
    assert value.is_finite()
    return value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--private-root", required=True, type=Path)
    args = ap.parse_args()
    assert not args.private_root.resolve().is_relative_to(ROOT.resolve())
    args.private_root.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((ROOT / "protocol.json").read_text(encoding="utf-8"))
    fields = cfg["source"]["fields"]
    response = requests.get(cfg["source"]["csv"], timeout=60)
    response.raise_for_status()
    raw = response.content
    digest = hashlib.sha256(raw).hexdigest()
    target = args.private_root / ("bds2023-state-sector-" + digest[:12] + ".csv")
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    before = cfg["source"]["metadata_before"]
    assert (
        len(raw) == int(before["Content-Length"])
        and response.headers.get("Last-Modified") == before["Last-Modified"]
    )
    if (ROOT / "data/source/manifest.json").exists():
        assert (
            json.loads((ROOT / "data/source/manifest.json").read_text())["raw_sha256"]
            == digest
        ), "New source revision; preserve original and stop"
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    assert set(fields) <= set(reader.fieldnames)
    rows = [{k: r[k].strip() for k in fields} for r in reader]
    assert len({(r["year"], r["st"], r["sector"]) for r in rows}) == len(
        rows
    ), "Duplicate source keys"
    frame = pd.read_csv(
        io.BytesIO(raw), usecols=fields, dtype=str, keep_default_na=False, engine="c"
    )
    assert len(frame) == len(rows)
    checks = 0
    for r, other in zip(rows, frame[fields].itertuples(index=False, name=None)):
        for k, value in zip(fields, other):
            assert r[k] == value.strip(), k
            checks += 1
    tokens = []
    scales = {}
    for field in fields[3:]:
        counts = Counter()
        places = 0
        for row in rows:
            value = numeric(row[field])
            if value is None:
                counts["blank" if row[field] == "" else row[field]] += 1
            else:
                counts["numeric"] += 1
                places = max(places, max(0, -value.as_tuple().exponent))
                if field != "net_job_creation":
                    assert value >= 0, (field, row["year"], row["st"], row["sector"])
        assert places <= 6, "Unexpected source precision; inspect before projection"
        scales[field] = 10**places
        tokens.extend(
            dict(field=field, token=key, rows=count)
            for key, count in sorted(counts.items())
        )
    selected = [
        r
        for r in rows
        if 2010 <= int(r["year"]) <= 2023
        and r["st"] in STATES
        and r["sector"] in cfg["source"]["sectors"]
    ]
    assert {r["st"] for r in selected} == set(STATES) and {
        r["sector"] for r in selected
    } == set(cfg["source"]["sectors"])
    assert {int(r["year"]) for r in selected} == set(range(2010, 2024))
    selected.sort(key=lambda r: (int(r["year"]), r["st"], r["sector"]))
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE counts(y INT,st TEXT,sector TEXT,field TEXT,value INT)")
    expected = defaultdict(lambda: [0, 0])
    inserts = []
    for r in selected:
        for field in fields[3:]:
            value = numeric(r[field])
            scaled = None if value is None else int(value * scales[field])
            assert value is None or Decimal(scaled) / scales[field] == value
            inserts.append((int(r["year"]), r["st"], r["sector"], field, scaled))
            key = (int(r["year"]), field)
            if scaled is not None:
                expected[key][0] += 1
                expected[key][1] += scaled
    assert all(abs(sum_) < 2**62 for count, sum_ in expected.values())
    db.executemany("INSERT INTO counts VALUES(?,?,?,?,?)", inserts)
    controls = []
    sql_checks = 0
    for year, field, count, sum_ in db.execute(
        "SELECT y,field,COUNT(value),COALESCE(SUM(value),0) FROM counts GROUP BY y,field ORDER BY y,field"
    ):
        assert [count, sum_] == expected[year, field]
        sql_checks += 2
        controls.append(
            dict(
                year=year,
                field=field,
                published_numeric_cells=count,
                integer_scale=scales[field],
                sum_scaled=sum_,
            )
        )
    after = requests.get(cfg["source"]["csv"], stream=True, timeout=45)
    after.raise_for_status()
    after_header = next(after.iter_lines()).decode("utf-8-sig")
    after.close()
    assert (
        hashlib.sha256(after_header.encode()).hexdigest()
        == cfg["source"]["header_sha256"]
    )
    assert (
        after.headers.get("Last-Modified") == before["Last-Modified"]
        and after.headers.get("Content-Length") == before["Content-Length"]
    )

    def write_csv(path, items, columns):
        s = io.StringIO(newline="")
        w = csv.DictWriter(s, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        w.writerows(items)
        data = s.getvalue().encode()
        path.write_bytes(gzip.compress(data, mtime=0) if path.suffix == ".gz" else data)
        return data

    projection = write_csv(ROOT / "data/source/state-sector.csv.gz", selected, fields)
    write_csv(
        ROOT / "data/source/token-inventory.csv", tokens, ["field", "token", "rows"]
    )
    write_csv(
        ROOT / "data/source/sql-controls.csv",
        controls,
        ["year", "field", "published_numeric_cells", "integer_scale", "sum_scaled"],
    )
    coverage = [
        dict(
            year=y,
            rows=sum(int(r["year"]) == y for r in selected),
            expected_state_sector_keys=len(STATES) * len(cfg["source"]["sectors"]),
        )
        for y in range(2010, 2024)
    ]
    write_csv(
        ROOT / "data/source/coverage.csv",
        coverage,
        ["year", "rows", "expected_state_sector_keys"],
    )
    manifest = dict(
        retrieved_utc=datetime.now(timezone.utc).isoformat(),
        source_url=cfg["source"]["csv"],
        raw_sha256=digest,
        raw_bytes=len(raw),
        raw_file_name=target.name,
        projection="data/source/state-sector.csv.gz",
        projection_csv_sha256=hashlib.sha256(projection).hexdigest(),
        projection_gzip_sha256=hashlib.sha256(
            (ROOT / "data/source/state-sector.csv.gz").read_bytes()
        ).hexdigest(),
        source_rows=len(rows),
        selected_rows=len(selected),
        fields=fields,
        source_scalar_checks=checks,
        independent_sql_control_scalars=sql_checks,
        source_key="year/st/sector",
        duplicates=0,
        metadata_before_after="Header SHA, Last-Modified and Content-Length unchanged. This is bounded replacement detection, not universal source immutability.",
        source_truth="UNKNOWN; captured disclosure-protected/revised published cells only",
        rights="Public federal factual aggregates with attribution and original work; no full source/manual or source-wide third-party license claim.",
        raw_source_public=False,
        suppression_recovery=False,
    )
    write_json(ROOT / "data/source/manifest.json", manifest)
    print(
        json.dumps(
            dict(
                status="PASS",
                source_rows=len(rows),
                selected_rows=len(selected),
                source_scalar_checks=checks,
                independent_sql_control_scalars=sql_checks,
                source_sha256=digest,
                raw_tokens_preserved=True,
                suppression_recovery=False,
            )
        )
    )


if __name__ == "__main__":
    main()
