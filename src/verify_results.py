"""Independent SQL data lineage and decimal/rational forecast-loss reconstruction."""

import argparse
from collections import defaultdict
import csv, gzip, hashlib, io, json, sqlite3
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from fractions import Fraction as Q
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_SCALE = 10**6
SCORE_SCALE = 10**12


def read(name):
    data = (ROOT / name).read_bytes()
    if name.endswith(".gz"):
        data = gzip.decompress(data)
    return list(csv.DictReader(io.StringIO(data.decode())))


def number(token):
    if token in ["", "D", "S", "X", "N"]:
        return None
    return Q(Decimal(token))


def decimal(q, places=12):
    q = Q(q)
    with localcontext() as c:
        c.prec = len(str(abs(q.numerator))) + len(str(q.denominator)) + 100
        return format(
            (Decimal(q.numerator) / Decimal(q.denominator)).quantize(
                Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN
            ),
            "f",
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["validation", "held"])
    args = ap.parse_args()
    cfg = json.loads((ROOT / "protocol.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "data/source/manifest.json").read_text(encoding="utf-8")
    )
    assert (
        hashlib.sha256(
            gzip.decompress((ROOT / manifest["projection"]).read_bytes())
        ).hexdigest()
        == manifest["projection_csv_sha256"]
    )
    rows = read(manifest["projection"])
    raw = {(int(r["year"]), r["st"], r["sector"]): r for r in rows}
    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE source(y INT,st TEXT,sector TEXT,jcc INT,denom INT,PRIMARY KEY(y,st,sector))"
    )
    db.execute("CREATE INDEX donor_lookup ON source(y,sector,st)")
    for r in rows:
        vals = []
        for field in ["job_creation_continuers", "denom"]:
            n = number(r[field])
            scaled = None if n is None else n * INPUT_SCALE
            assert scaled is None or scaled.denominator == 1
            vals.append(None if scaled is None else scaled.numerator)
        db.execute(
            "INSERT INTO source VALUES(?,?,?,?,?)",
            (int(r["year"]), r["st"], r["sector"], *vals),
        )
    db.execute(
        "CREATE VIEW valid AS SELECT * FROM source WHERE jcc IS NOT NULL AND jcc>=0 AND denom>0"
    )
    cohort = set(
        db.execute(
            "SELECT st,sector FROM valid WHERE y BETWEEN 2010 AND 2015 GROUP BY st,sector HAVING COUNT(*)=6 AND MIN(denom)>=?",
            (1000 * INPUT_SCALE,),
        ).fetchall()
    )
    assert len(cohort) >= 50
    db.execute("CREATE TABLE cohort(st TEXT,sector TEXT,PRIMARY KEY(st,sector))")
    db.executemany("INSERT INTO cohort VALUES(?,?)", sorted(cohort))
    checks = 0

    def match(actual, expected):
        nonlocal checks
        assert set(actual) == set(expected), (actual, expected)
        for name, value in expected.items():
            assert str(actual[name]) == str(value), (name, actual[name], value)
            checks += 1

    actual_cohort = read("results/cohort.csv")
    assert len(actual_cohort) == 51 * 19
    for r in actual_cohort:
        st, s = r["st"], r["sector"]
        reasons = []
        valid = 0
        for y in range(2010, 2016):
            v = db.execute(
                "SELECT jcc,denom FROM source WHERE y=? AND st=? AND sector=?",
                (y, st, s),
            ).fetchone()
            if v is None or v[0] is None or v[0] < 0 or v[1] is None or v[1] <= 0:
                reasons.append(str(y) + ":absent_or_flagged_target_or_denom")
            elif v[1] < 1000 * INPUT_SCALE:
                reasons.append(str(y) + ":baseline_denom_below1000")
            else:
                valid += 1
        match(
            r,
            dict(
                st=st,
                sector=s,
                eligible=int((st, s) in cohort),
                valid_baseline_years=valid,
                reason="eligible" if (st, s) in cohort else "|".join(reasons),
            ),
        )
    years = (
        [2016, 2017, 2018, 2019]
        if args.stage == "validation"
        else [2020, 2021, 2022, 2023]
    )
    features = {}
    eligibility = {}
    lineage_checks = 0
    for y in years:
        for st, s in sorted(cohort):
            target = db.execute(
                "SELECT jcc,denom FROM valid WHERE y=? AND st=? AND sector=?",
                (y, st, s),
            ).fetchone()
            prior = db.execute(
                "SELECT jcc,denom FROM valid WHERE y=? AND st=? AND sector=?",
                (y - 1, st, s),
            ).fetchone()
            donors = db.execute(
                "SELECT d.st,d.jcc,d.denom FROM valid d JOIN cohort c ON d.st=c.st AND d.sector=c.sector WHERE d.y=? AND d.sector=? AND d.st<>? ORDER BY d.st",
                (y - 1, s, st),
            ).fetchall()
            reasons = []
            if target is None:
                reasons.append("absent_or_flagged_target")
            if prior is None:
                reasons.append("absent_or_flagged_prior_input")
            if len(donors) < 5:
                reasons.append("fewer_than5_other_state_donors")
            eligibility[y, st, s] = dict(
                year=y,
                st=st,
                sector=s,
                eligible=int(not reasons),
                donor_states=len(donors),
                reason="eligible" if not reasons else "|".join(reasons),
            )
            if reasons:
                continue
            assert all(d[0] != st for d in donors)
            lineage_checks += len(donors) + 1
            pool = db.execute(
                "SELECT SUM(d.jcc),SUM(d.denom),COUNT(*) FROM valid d JOIN cohort c ON d.st=c.st AND d.sector=c.sector WHERE d.y=? AND d.sector=? AND d.st<>?",
                (y - 1, s, st),
            ).fetchone()
            assert pool[2] == len(donors) and pool[:2] == (
                sum(d[1] for d in donors),
                sum(d[2] for d in donors),
            )
            lineage_checks += 3
            features[y, st, s] = dict(
                year=y,
                st=st,
                sector=s,
                input_year=y - 1,
                own_count=str(Q(prior[0], INPUT_SCALE)),
                own_denom=str(Q(prior[1], INPUT_SCALE)),
                donor_codes="|".join(d[0] for d in donors),
                donor_states=len(donors),
                pool_count=str(Q(pool[0], INPUT_SCALE)),
                pool_denom=str(Q(pool[1], INPUT_SCALE)),
                target_denom=str(Q(target[1], INPUT_SCALE)),
                target=decimal(Q(100 * target[0], target[1])),
            )
    prefix = "results/" + args.stage + "-"
    actual = read(prefix + "features.csv")
    assert len(actual) == len(features)
    for r in actual:
        match(r, features[int(r["year"]), r["st"], r["sector"]])
    actual = read(prefix + "eligibility.csv")
    assert len(actual) == len(eligibility)
    for r in actual:
        match(r, eligibility[int(r["year"]), r["st"], r["sector"]])
    selection = json.loads((ROOT / "SELECTION.json").read_text(encoding="utf-8"))
    weights = (
        ["0", "1/4", "1/2", "3/4", "1"]
        if args.stage == "validation"
        else sorted({selection["selected_own_weight"], "1"}, key=Q)
    )
    predictions = {}
    metric_inputs = []
    for key, f in features.items():
        y, st, s = key
        for weight in weights:
            w = Q(weight)
            point = 100 * (
                w * Q(f["own_count"]) / Q(f["own_denom"])
                + (1 - w) * Q(f["pool_count"]) / Q(f["pool_denom"])
            )
            predicted = decimal(point)
            error = Q(predicted) - Q(f["target"])
            predictions[y, st, s, weight] = dict(
                year=y,
                st=st,
                sector=s,
                own_weight=weight,
                target=f["target"],
                prediction=predicted,
                error=decimal(error),
                absolute_error=decimal(abs(error)),
                squared_error=decimal(error * error, 24),
            )
            metric_inputs.append(
                dict(
                    year=y,
                    st=st,
                    sector=s,
                    weight=weight,
                    error=error,
                    denom=Q(f["target_denom"]),
                    prior_denom=Q(f["own_denom"]),
                )
            )
    actual = read(prefix + "predictions.csv.gz")
    assert len(actual) == len(predictions)
    seen = set()
    for r in actual:
        key = (int(r["year"]), r["st"], r["sector"], r["own_weight"])
        assert key not in seen
        seen.add(key)
        match(r, predictions[key])
    assert seen == set(predictions)

    def summary(group):
        if not group:
            return dict(n=0, series=0, mae="", mse="", rmse="", weighted_mae="")
        per = defaultdict(list)
        for r in group:
            per[r["st"], r["sector"]].append(r["error"])
        errors = [sum(map(abs, x), Q(0)) / len(x) for x in per.values()]
        squared = [sum((e * e for e in x), Q(0)) / len(x) for x in per.values()]
        mae = sum(errors, Q(0)) / len(errors)
        mse = sum(squared, Q(0)) / len(squared)
        weighted = sum((abs(r["error"]) * r["denom"] for r in group), Q(0)) / sum(
            (r["denom"] for r in group), Q(0)
        )
        with localcontext() as context:
            context.prec = 120
            rmse = (
                (Decimal(mse.numerator) / Decimal(mse.denominator))
                .sqrt()
                .quantize(Decimal("1e-12"), rounding=ROUND_HALF_EVEN)
            )
        return dict(
            n=len(group),
            series=len(per),
            mae=str(mae),
            mse=str(mse),
            rmse=format(rmse, "f"),
            weighted_mae=str(weighted),
        )

    metrics = {}
    for weight in weights:
        policy = [r for r in metric_inputs if r["weight"] == weight]
        groups = {("overall", "all"): policy}
        for y in years:
            groups["year", str(y)] = [r for r in policy if r["year"] == y]
        for s in cfg["source"]["sectors"]:
            groups["sector", s] = [r for r in policy if r["sector"] == s]
        for st, s in sorted({(r["st"], r["sector"]) for r in policy}):
            groups["series", st + "|" + s] = [
                r for r in policy if r["st"] == st and r["sector"] == s
            ]
        for minimum in [1000, 5000, 25000]:
            groups["prior_denom_subset", str(minimum)] = [
                r for r in policy if r["prior_denom"] >= minimum
            ]
        for (scope, unit), group in groups.items():
            metrics[weight, scope, unit] = dict(
                own_weight=weight, scope=scope, unit=unit, **summary(group)
            )
    actual = read(prefix + "metrics.csv")
    assert len(actual) == len(metrics)
    for r in actual:
        match(r, metrics[r["own_weight"], r["scope"], r["unit"]])
    if args.stage == "validation":
        candidates = [metrics[w, "overall", "all"] for w in weights]
        best = min(candidates, key=lambda r: (Q(r["mae"]), Q(r["own_weight"])))
        assert (
            selection["selected_own_weight"] == best["own_weight"]
            and selection["score_exact"] == best["mae"]
        )
        checks += 2
        assert selection["all_candidates"] == [
            dict(
                own_weight=r["own_weight"],
                mae_exact=r["mae"],
                n=r["n"],
                series=r["series"],
            )
            for r in candidates
        ]
        checks += len(candidates) * 4
    else:
        complete = []
        actual_cells = read("results/held-composition-cells.csv")
        assert len(actual_cells) == len(features)
        for r in actual_cells:
            source = raw[int(r["year"]), r["st"], r["sector"]]
            names = [
                "job_creation",
                "job_creation_births",
                "job_creation_continuers",
                "job_destruction",
                "job_destruction_deaths",
                "job_destruction_continuers",
                "net_job_creation",
            ]
            v = {k: number(source[k]) for k in names}
            ok = (
                all(v[k] is not None for k in names[:3])
                and number(source["denom"]) is not None
            )
            expected = dict(
                year=int(r["year"]),
                st=r["st"],
                sector=r["sector"],
                creation_components_complete=int(ok),
                denom=source["denom"],
                job_creation=source["job_creation"],
                births=source["job_creation_births"],
                continuers=source["job_creation_continuers"],
                creation_residual=(
                    str(v[names[0]] - v[names[1]] - v[names[2]]) if ok else ""
                ),
                destruction_residual=(
                    ""
                    if any(v[k] is None for k in names[3:6])
                    else str(v[names[3]] - v[names[4]] - v[names[5]])
                ),
                net_residual=(
                    ""
                    if any(v[k] is None for k in [names[0], names[3], names[6]])
                    else str(v[names[6]] - v[names[0]] + v[names[3]])
                ),
            )
            match(r, expected)
            complete.append(expected)
        actual_summary = read("results/held-composition-sectors.csv")
        assert len(actual_summary) == 19
        for r in actual_summary:
            group = [x for x in complete if x["sector"] == r["sector"]]
            observed = [x for x in group if x["creation_components_complete"]]
            den = sum((number(x["denom"]) for x in observed), Q(0))
            expected = dict(
                sector=r["sector"],
                model_cases=len(group),
                creation_complete_cases=len(observed),
                nonzero_creation_residual_cases=sum(
                    Q(x["creation_residual"]) != 0 for x in observed
                ),
                maximum_absolute_creation_residual=str(
                    max(
                        (abs(Q(x["creation_residual"])) for x in observed), default=Q(0)
                    )
                ),
            )
            for label, col in [
                ("total_rate", "job_creation"),
                ("birth_rate", "births"),
                ("continuer_rate", "continuers"),
            ]:
                expected[label] = (
                    ""
                    if not den
                    else str(100 * sum((number(x[col]) for x in observed), Q(0)) / den)
                )
            match(r, expected)
    stage_summary = json.loads(
        (ROOT / (prefix + "SUMMARY.json")).read_text(encoding="utf-8")
    )
    assert (
        stage_summary["baseline_series"] == len(cohort)
        and stage_summary["cases"] == len(features)
        and stage_summary["prediction_rows"] == len(predictions)
        and stage_summary["metric_rows"] == len(metrics)
    )
    checks += 4
    receipt = dict(
        status="PASS",
        stage=args.stage,
        exact_exported_fields_checked=checks,
        independent_sql_lineage_checks=lineage_checks,
        baseline_series=len(cohort),
        cases=len(features),
        prediction_rows=len(predictions),
        metric_rows=len(metrics),
        scope="Independent source-token interpretation, SQLite cohorts/lag/donor sums and rational/decimal scoring. Exactness is relative to declared12-place score representation; no source-truth, hires, causal or real-time claim.",
    )
    (ROOT / (prefix + "VERIFICATION.json")).write_bytes(
        (json.dumps(receipt, indent=2) + "\n").encode()
    )
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
