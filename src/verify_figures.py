"""Check actual plotted values, labels, failure counts and original export hashes."""

from pathlib import Path
from fractions import Fraction as F
import csv, hashlib, json

ROOT = Path(__file__).resolve().parents[1]


def main():
    rows = list(
        csv.DictReader(
            (ROOT / "results/held-metrics.csv").open(encoding="utf-8", newline="")
        )
    )
    values = {(r["own_weight"], r["scope"], r["unit"]): r for r in rows}
    artist = json.loads(
        (ROOT / "figures/ARTIST_VALUES.json").read_text(encoding="utf-8")
    )
    checks = 0
    geometry = 0

    def scalar(got, want):
        nonlocal checks
        assert abs(float(got) - float(want)) < 1e-9, (got, want)
        checks += 1

    a = artist["year_errors"]
    assert a["years"] == ["2020", "2021", "2022", "2023"]
    for weight, name in [("1/4", "selected_heights"), ("1", "baseline_heights")]:
        for year, got in zip(a["years"], a[name]):
            scalar(got, F(values[weight, "year", year]["mae"]))
    assert a["annotations"] == [
        f'{float(F(values[w,"year",y]["mae"])):.3f}'
        for w in ["1/4", "1"]
        for y in a["years"]
    ]
    s = artist["sector_errors"]
    assert len(s["sectors"]) == 19 and len(set(s["sectors"])) == 19
    for i, sector in enumerate(s["sectors"]):
        x = F(values["1/4", "sector", sector]["mae"])
        y = F(values["1", "sector", sector]["mae"])
        scalar(s["selected_offsets"][i][0], x)
        scalar(s["baseline_offsets"][i][0], y)
        assert s["selected_offsets"][i][1] == s["baseline_offsets"][i][1] == i
        geometry += 2
        for pair, want in zip(s["segments"][i], [(min(x, y), i), (max(x, y), i)]):
            assert abs(pair[0] - float(want[0])) < 1e-9 and pair[1] == want[1]
            geometry += 2
        assert s["worse"][i] == (x > y) and s["labels"][i].startswith(sector + "  ")
    assert sum(s["worse"]) == 4
    by_series = {
        w: {
            r["unit"]: F(r["mae"])
            for r in rows
            if r["scope"] == "series" and r["own_weight"] == w
        }
        for w in ["1/4", "1"]
    }
    assert (
        len(by_series["1"]) == 934
        and sum(by_series["1/4"][k] > v for k, v in by_series["1"].items()) == 428
    )
    c = artist["creation_components"]
    assert c["sectors"] == s["sectors"]
    composition = {
        r["sector"]: r
        for r in csv.DictReader(
            (ROOT / "results/held-composition-sectors.csv").open(
                encoding="utf-8", newline=""
            )
        )
    }
    for i, sector in enumerate(c["sectors"]):
        row = composition[sector]
        scalar(c["continuing_widths"][i], F(row["continuer_rate"]))
        scalar(c["birth_widths"][i], F(row["birth_rate"]))
        assert c["model_cases"][i] == int(row["model_cases"]) and c["complete_cases"][
            i
        ] == int(row["creation_complete_cases"])
    assert sum(c["model_cases"]) == 3736 and sum(c["complete_cases"]) == 3715
    assert (
        sum(int(r["nonzero_creation_residual_cases"]) for r in composition.values())
        == 1
    )
    assert (
        max(F(r["maximum_absolute_creation_residual"]) for r in composition.values())
        == 1
    )
    hashes = json.loads((ROOT / "figures/MANIFEST.json").read_text(encoding="utf-8"))
    assert len(hashes) == 9
    for name, digest in hashes.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    result = dict(
        status="PASS",
        plotted_numeric_values=checks,
        coordinate_segment_checks=geometry,
        year_annotations=8,
        sector_labels=19,
        failure_and_composition_counts="PASS",
        export_hashes=9,
        scope="Finite source/result-to-artist checks plus separate rendered review; no accessibility-conformance claim.",
    )
    (ROOT / "figures/VERIFICATION.json").write_bytes(
        (json.dumps(result, indent=2) + "\n").encode()
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
