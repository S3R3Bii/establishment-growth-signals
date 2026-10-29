"""Execute the fixed annual state-sector comparison; no suppressed values are inferred."""

import argparse
from collections import defaultdict
import csv, gzip, hashlib, io, json
from fractions import Fraction as F
from pathlib import Path
from model import (
    source_number,
    valid_target,
    quantize,
    fixed,
    predict,
    summarize,
    ratio_text,
    SCALE,
)

ROOT = Path(__file__).resolve().parents[1]


def write_csv(name, rows, fields):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    data = stream.getvalue().encode()
    (ROOT / name).write_bytes(
        gzip.compress(data, mtime=0) if name.endswith(".gz") else data
    )


def load():
    cfg = json.loads((ROOT / "protocol.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "data/source/manifest.json").read_text(encoding="utf-8")
    )
    data = gzip.decompress((ROOT / manifest["projection"]).read_bytes())
    assert hashlib.sha256(data).hexdigest() == manifest["projection_csv_sha256"]
    rows = {
        (int(r["year"]), r["st"], r["sector"]): r
        for r in csv.DictReader(io.StringIO(data.decode()))
    }
    cohort = []
    eligible = set()
    for st in sorted({key[1] for key in rows}):
        for sector in cfg["source"]["sectors"]:
            valid = []
            reasons = []
            for year in cfg["baseline_years"]:
                row = rows.get((year, st, sector))
                if not valid_target(row):
                    reasons.append(str(year) + ":absent_or_flagged_target_or_denom")
                elif source_number(row["denom"]) < 1000:
                    reasons.append(str(year) + ":baseline_denom_below1000")
                else:
                    valid.append(year)
            ok = len(valid) == 6
            if ok:
                eligible.add((st, sector))
            cohort.append(
                dict(
                    st=st,
                    sector=sector,
                    eligible=int(ok),
                    valid_baseline_years=len(valid),
                    reason="eligible" if ok else "|".join(reasons),
                )
            )
    assert len(eligible) >= 50
    return cfg, rows, cohort, eligible


def features_for(cfg, source, eligible, years):
    features = []
    exclusions = []
    for year in years:
        for st, sector in sorted(eligible):
            target = source.get((year, st, sector))
            prior = source.get((year - 1, st, sector))
            reasons = []
            if not valid_target(target):
                reasons.append("absent_or_flagged_target")
            if not valid_target(prior):
                reasons.append("absent_or_flagged_prior_input")
            donors = [
                other
                for other, s in sorted(eligible)
                if s == sector
                and other != st
                and valid_target(source.get((year - 1, other, sector)))
            ]
            if len(donors) < 5:
                reasons.append("fewer_than5_other_state_donors")
            exclusions.append(
                dict(
                    year=year,
                    st=st,
                    sector=sector,
                    eligible=int(not reasons),
                    donor_states=len(donors),
                    reason="eligible" if not reasons else "|".join(reasons),
                )
            )
            if reasons:
                continue
            own = source_number(prior["job_creation_continuers"])
            own_denom = source_number(prior["denom"])
            pool = sum(
                (
                    source_number(
                        source[year - 1, d, sector]["job_creation_continuers"]
                    )
                    for d in donors
                ),
                F(0),
            )
            pool_denom = sum(
                (source_number(source[year - 1, d, sector]["denom"]) for d in donors),
                F(0),
            )
            label = quantize(
                100
                * source_number(target["job_creation_continuers"])
                / source_number(target["denom"])
            )
            features.append(
                dict(
                    year=year,
                    st=st,
                    sector=sector,
                    input_year=year - 1,
                    own_count=str(own),
                    own_denom=str(own_denom),
                    donor_codes="|".join(donors),
                    donor_states=len(donors),
                    pool_count=str(pool),
                    pool_denom=str(pool_denom),
                    target_denom=str(source_number(target["denom"])),
                    target=fixed(label),
                )
            )
    assert features
    return features, exclusions


def prediction_rows(features, weights):
    output = []
    internal = []
    for f in features:
        for weight in weights:
            prediction = predict(
                F(f["own_count"]),
                F(f["own_denom"]),
                F(f["pool_count"]),
                F(f["pool_denom"]),
                F(weight),
            )
            target = quantize(F(f["target"]))
            error = prediction - target
            output.append(
                dict(
                    year=f["year"],
                    st=f["st"],
                    sector=f["sector"],
                    own_weight=weight,
                    target=f["target"],
                    prediction=fixed(prediction),
                    error=fixed(error),
                    absolute_error=fixed(abs(error)),
                    squared_error=fixed(error**2, 24),
                )
            )
            internal.append(
                dict(
                    year=f["year"],
                    st=f["st"],
                    sector=f["sector"],
                    weight=weight,
                    error_scaled=error,
                    target_denom=F(f["target_denom"]),
                    prior_denom=F(f["own_denom"]),
                )
            )
    return output, internal


def metric_rows(cfg, values, weights, years):
    output = []
    scopes = (
        [("overall", "all")]
        + [("year", str(y)) for y in years]
        + [("sector", s) for s in cfg["source"]["sectors"]]
        + [
            ("series", st + "|" + s)
            for st, s in sorted({(r["st"], r["sector"]) for r in values})
        ]
        + [
            ("prior_denom_subset", str(n))
            for n in cfg["small_cell_checks"]["minimum_prior_denominator_subsets"]
        ]
    )
    for weight in weights:
        policy = [r for r in values if r["weight"] == weight]
        for scope, unit in scopes:
            chosen = (
                policy
                if scope == "overall"
                else (
                    [r for r in policy if str(r["year"]) == unit]
                    if scope == "year"
                    else (
                        [r for r in policy if r["sector"] == unit]
                        if scope == "sector"
                        else (
                            [r for r in policy if r["st"] + "|" + r["sector"] == unit]
                            if scope == "series"
                            else [r for r in policy if r["prior_denom"] >= int(unit)]
                        )
                    )
                )
            )
            got = summarize(chosen)
            output.append(dict(own_weight=weight, scope=scope, unit=unit, **got))
    return output


def composition(source, features):
    rows = []
    for f in features:
        raw = source[f["year"], f["st"], f["sector"]]
        vals = {
            k: source_number(raw[k])
            for k in [
                "denom",
                "job_creation",
                "job_creation_births",
                "job_creation_continuers",
                "job_destruction",
                "job_destruction_deaths",
                "job_destruction_continuers",
                "net_job_creation",
            ]
        }
        complete = all(
            vals[k] is not None
            for k in [
                "denom",
                "job_creation",
                "job_creation_births",
                "job_creation_continuers",
            ]
        )
        row = dict(
            year=f["year"],
            st=f["st"],
            sector=f["sector"],
            creation_components_complete=int(complete),
            denom=raw["denom"],
            job_creation=raw["job_creation"],
            births=raw["job_creation_births"],
            continuers=raw["job_creation_continuers"],
        )
        row["creation_residual"] = (
            ""
            if not complete
            else str(
                vals["job_creation"]
                - vals["job_creation_births"]
                - vals["job_creation_continuers"]
            )
        )
        row["destruction_residual"] = (
            ""
            if any(
                vals[k] is None
                for k in [
                    "job_destruction",
                    "job_destruction_deaths",
                    "job_destruction_continuers",
                ]
            )
            else str(
                vals["job_destruction"]
                - vals["job_destruction_deaths"]
                - vals["job_destruction_continuers"]
            )
        )
        row["net_residual"] = (
            ""
            if any(
                vals[k] is None
                for k in ["job_creation", "job_destruction", "net_job_creation"]
            )
            else str(
                vals["net_job_creation"]
                - vals["job_creation"]
                + vals["job_destruction"]
            )
        )
        rows.append(row)
    summary = []
    for sector in sorted({r["sector"] for r in rows}):
        group = [r for r in rows if r["sector"] == sector]
        complete = [r for r in group if r["creation_components_complete"]]
        denom = sum((F(r["denom"]) for r in complete), F(0))
        got = dict(
            sector=sector,
            model_cases=len(group),
            creation_complete_cases=len(complete),
            nonzero_creation_residual_cases=sum(
                F(r["creation_residual"]) != 0 for r in complete
            ),
            maximum_absolute_creation_residual=str(
                max((abs(F(r["creation_residual"])) for r in complete), default=F(0))
            ),
        )
        for label, column in [
            ("total_rate", "job_creation"),
            ("birth_rate", "births"),
            ("continuer_rate", "continuers"),
        ]:
            got[label] = (
                ""
                if not denom
                else str(100 * sum((F(r[column]) for r in complete), F(0)) / denom)
            )
        summary.append(got)
    return rows, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["validation", "held"])
    args = ap.parse_args()
    cfg, source, cohort, eligible = load()
    if args.stage == "held":
        from verify_freeze import verify

        verify()
        selection = json.loads((ROOT / "SELECTION.json").read_text(encoding="utf-8"))
        weights = sorted({selection["selected_own_weight"], "1"}, key=F)
        years = cfg["held_years"]
    else:
        weights = cfg["own_weights"]
        years = cfg["validation_years"]
        write_csv(
            "results/cohort.csv",
            cohort,
            ["st", "sector", "eligible", "valid_baseline_years", "reason"],
        )
    features, exclusions = features_for(cfg, source, eligible, years)
    predictions, internal = prediction_rows(features, weights)
    metrics = metric_rows(cfg, internal, weights, years)
    prefix = "results/" + args.stage + "-"
    write_csv(
        prefix + "features.csv",
        features,
        [
            "year",
            "st",
            "sector",
            "input_year",
            "own_count",
            "own_denom",
            "donor_codes",
            "donor_states",
            "pool_count",
            "pool_denom",
            "target_denom",
            "target",
        ],
    )
    write_csv(
        prefix + "eligibility.csv",
        exclusions,
        ["year", "st", "sector", "eligible", "donor_states", "reason"],
    )
    write_csv(
        prefix + "predictions.csv.gz",
        predictions,
        [
            "year",
            "st",
            "sector",
            "own_weight",
            "target",
            "prediction",
            "error",
            "absolute_error",
            "squared_error",
        ],
    )
    write_csv(
        prefix + "metrics.csv",
        metrics,
        [
            "own_weight",
            "scope",
            "unit",
            "n",
            "series",
            "mae",
            "mse",
            "rmse",
            "weighted_mae",
        ],
    )
    if args.stage == "validation":
        candidates = [r for r in metrics if r["scope"] == "overall"]
        choice = min(candidates, key=lambda r: (F(r["mae"]), F(r["own_weight"])))
        selection = dict(
            selected_own_weight=choice["own_weight"],
            baseline_own_weight="1",
            objective="Equal-state-sector MAE on exported12-place target/prediction values",
            score_exact=choice["mae"],
            tie_rule="Smaller own-history weight",
            all_candidates=[
                dict(
                    own_weight=r["own_weight"],
                    mae_exact=r["mae"],
                    n=r["n"],
                    series=r["series"],
                )
                for r in candidates
            ],
            held_analytical_outcomes_inspected=False,
        )
        (ROOT / "SELECTION.json").write_bytes(
            (json.dumps(selection, indent=2) + "\n").encode()
        )
    else:
        cells, summary = composition(source, features)
        write_csv(
            "results/held-composition-cells.csv",
            cells,
            [
                "year",
                "st",
                "sector",
                "creation_components_complete",
                "denom",
                "job_creation",
                "births",
                "continuers",
                "creation_residual",
                "destruction_residual",
                "net_residual",
            ],
        )
        write_csv(
            "results/held-composition-sectors.csv",
            summary,
            [
                "sector",
                "model_cases",
                "creation_complete_cases",
                "nonzero_creation_residual_cases",
                "maximum_absolute_creation_residual",
                "total_rate",
                "birth_rate",
                "continuer_rate",
            ],
        )
    summary = dict(
        stage=args.stage,
        baseline_series=len(eligible),
        years=years,
        cases=len(features),
        candidate_weights=weights,
        prediction_rows=len(predictions),
        metric_rows=len(metrics),
        excluded_cases=sum(not r["eligible"] for r in exclusions),
        score_decimal_places=12,
    )
    (ROOT / (prefix + "SUMMARY.json")).write_bytes(
        (json.dumps(summary, indent=2) + "\n").encode()
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
