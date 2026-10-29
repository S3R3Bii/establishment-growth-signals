"""Independent display, source-component, headline and bounded PDF checks."""

import csv, gzip, hashlib, io, json, re, unicodedata
from collections import defaultdict
from fractions import Fraction as F
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    data = (ROOT / name).read_bytes()
    if name.endswith(".gz"):
        data = gzip.decompress(data)
    return list(csv.DictReader(io.StringIO(data.decode())))


def show(q, places=6):
    q = F(q)
    with localcontext() as c:
        c.prec = len(str(abs(q.numerator))) + len(str(q.denominator)) + 100
        return format(
            (Decimal(q.numerator) / Decimal(q.denominator)).quantize(
                Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN
            ),
            ",." + str(places) + "f",
        )


def main():
    val = read("results/validation-metrics.csv")
    held = read("results/held-metrics.csv")
    v = {(r["own_weight"], r["scope"], r["unit"]): r for r in val}
    h = {(r["own_weight"], r["scope"], r["unit"]): r for r in held}
    chosen = json.loads((ROOT / "SELECTION.json").read_text())["selected_own_weight"]
    assert chosen == "1/4"
    labels = {
        "11": "Agriculture/forestry",
        "21": "Mining/extraction",
        "22": "Utilities",
        "23": "Construction",
        "31-33": "Manufacturing",
        "42": "Wholesale",
        "44-45": "Retail",
        "48-49": "Transport/warehousing",
        "51": "Information",
        "52": "Finance/insurance",
        "53": "Real estate/leasing",
        "54": "Professional/technical",
        "55": "Company management",
        "56": "Admin/support",
        "61": "Education",
        "62": "Health/social assistance",
        "71": "Arts/recreation",
        "72": "Accommodation/food",
        "81": "Other services",
    }
    expected = dict(
        validation=[
            [
                w,
                *[
                    show(v[w, "overall", "all"][m])
                    for m in ["mae", "mse", "rmse", "weighted_mae"]
                ],
            ]
            for w in ["0", "1/4", "1/2", "3/4", "1"]
        ],
        primary=[
            [
                name,
                *[
                    show(h[w, "overall", "all"][m])
                    for m in ["mae", "mse", "rmse", "weighted_mae"]
                ],
            ]
            for w, name in [(chosen, "Selected 1/4"), ("1", "Own lag 1")]
        ],
        years=[],
        size=[],
        sectors=[],
        worst=[],
        composition=[],
    )
    for y in ["2020", "2021", "2022", "2023"]:
        a, b = h[chosen, "year", y], h["1", "year", y]
        expected["years"].append(
            [y, a["n"], show(a["mae"]), show(b["mae"]), show(F(a["mae"]) - F(b["mae"]))]
        )
    for minimum in ["1000", "5000", "25000"]:
        a, b = (
            h[chosen, "prior_denom_subset", minimum],
            h["1", "prior_denom_subset", minimum],
        )
        expected["size"].append(
            [
                minimum,
                a["n"],
                a["series"],
                show(a["mae"]),
                show(b["mae"]),
                show(F(a["mae"]) - F(b["mae"])),
            ]
        )
    for sector, label in labels.items():
        a, b = h[chosen, "sector", sector], h["1", "sector", sector]
        expected["sectors"].append(
            [
                sector,
                label,
                a["series"],
                show(a["mae"]),
                show(b["mae"]),
                show(F(a["mae"]) - F(b["mae"])),
            ]
        )
    byseries = {
        w: {
            r["unit"]: F(r["mae"])
            for r in held
            if r["own_weight"] == w and r["scope"] == "series"
        }
        for w in [chosen, "1"]
    }
    differences = {
        key: byseries[chosen][key] - byseries["1"][key] for key in byseries["1"]
    }
    for key, diff in sorted(differences.items(), key=lambda x: (-x[1], x[0]))[:5]:
        expected["worst"].append(
            [key, show(byseries[chosen][key]), show(byseries["1"][key]), show(diff)]
        )
    original = {
        (int(r["year"]), r["st"], r["sector"]): r
        for r in read("data/source/state-sector.csv.gz")
    }
    features = read("results/held-features.csv")
    groups = defaultdict(list)
    num = lambda token: None if token in ["", "D", "S", "X", "N"] else F(token)
    for feature in features:
        groups[feature["sector"]].append(
            original[int(feature["year"]), feature["st"], feature["sector"]]
        )
    complete_count = 0
    residual_count = 0
    for sector in labels:
        cases = groups[sector]
        complete = [
            r
            for r in cases
            if all(
                num(r[k]) is not None
                for k in [
                    "denom",
                    "job_creation",
                    "job_creation_births",
                    "job_creation_continuers",
                ]
            )
        ]
        den = sum((num(r["denom"]) for r in complete), F(0))
        birth = 100 * sum((num(r["job_creation_births"]) for r in complete), F(0)) / den
        continuing = (
            100 * sum((num(r["job_creation_continuers"]) for r in complete), F(0)) / den
        )
        residuals = [
            num(r["job_creation"])
            - num(r["job_creation_births"])
            - num(r["job_creation_continuers"])
            for r in complete
        ]
        nonzero = sum(q != 0 for q in residuals)
        maximum = max(map(abs, residuals), default=F(0))
        complete_count += len(complete)
        residual_count += nonzero
        expected["composition"].append(
            [
                sector,
                str(len(cases)),
                str(len(complete)),
                show(birth),
                show(continuing),
                str(nonzero),
                show(maximum, 0),
            ]
        )
    assert complete_count == 3715 and residual_count == 1 and len(features) == 3736
    checks = 4
    # Recompute the primary MAE directly from distinct exported forecast losses.
    preds = read("results/held-predictions.csv.gz")
    for w in [chosen, "1"]:
        errors = defaultdict(list)
        for r in preds:
            if r["own_weight"] == w:
                errors[r["st"], r["sector"]].append(
                    abs(F(r["prediction"]) - F(r["target"]))
                )
        assert len(errors) == 934 and all(len(e) == 4 for e in errors.values())
        loss = sum((sum(e, F(0)) / len(e) for e in errors.values()), F(0)) / len(errors)
        assert loss == F(h[w, "overall", "all"]["mae"])
        checks += 3
    tex = (ROOT / "paper/main.tex").read_text(encoding="utf-8")
    assert (
        "\\iffalse" not in tex and "\\input" not in tex and "\\includeonly" not in tex
    )
    doc = PdfReader(ROOT / "paper/manuscript.pdf")
    assert not doc.is_encrypted and len(doc.pages) == 8
    checks += 3
    pdftext = " ".join(page.extract_text() for page in doc.pages)
    actual = json.loads((ROOT / "paper/TABLE_VALUES.json").read_text(encoding="utf-8"))
    for name, table in expected.items():
        assert actual[name] == table, name
        checks += 1
        for row in table:
            line = (
                " & ".join(
                    str(x).replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")
                    for x in row
                )
                + " "
                + chr(92) * 2
            )
            assert line in tex, (name, line)
            checks += 1
            for token in row:
                if re.fullmatch("-?[0-9][0-9,.]*", str(token)):
                    assert str(token) in pdftext, (name, token)
                    checks += 1
    selected = F(h[chosen, "overall", "all"]["mae"])
    baseline = F(h["1", "overall", "all"]["mae"])
    reduction = 100 * (baseline - selected) / baseline
    assert show(selected, 3) + " percentage points versus " + show(baseline, 3) in tex
    assert show(reduction, 1) + r"\% reduction" in tex
    checks += 2
    assert (
        sum(q > 0 for q in differences.values()) == 428
        and sum(q < 0 for q in differences.values()) == 506
    )
    checks += 2
    assert (
        sum(
            F(h[chosen, "sector", s]["mae"]) > F(h["1", "sector", s]["mae"])
            for s in labels
        )
        == 4
    )
    checks += 1
    assert F(h[chosen, "year", "2023"]["mae"]) > F(h["1", "year", "2023"]["mae"])
    checks += 1
    source = json.loads(
        (ROOT / "data/source/manifest.json").read_text(encoding="utf-8")
    )
    for count in [
        source["source_rows"],
        source["selected_rows"],
        source["source_scalar_checks"],
        source["independent_sql_control_scalars"],
    ]:
        assert format(count, ",") in tex and format(count, ",") in pdftext
        checks += 2
    for name in ["validation-VERIFICATION.json", "held-VERIFICATION.json"]:
        r = json.loads((ROOT / "results" / name).read_text())
        for key in ["exact_exported_fields_checked", "independent_sql_lineage_checks"]:
            assert format(r[key], ",") in tex and format(r[key], ",") in pdftext
            checks += 2
    replay = json.loads((ROOT / "REPROCHECK.json").read_text())
    assert (
        format(replay["exact_csv_fields"], ",") in tex
        and format(replay["exact_csv_fields"], ",") in pdftext
    )
    checks += 2
    compact = lambda s: re.sub(
        "[^a-z0-9]", "", unicodedata.normalize("NFKC", s).lower()
    )
    for phrase in [
        "not worker hires, job vacancies or a demonstrated labor shortage",
        "original information vintages remain unverified",
        "No suppressed continuer count is reconstructed",
        "Source inputs/quality were visible without blinding",
        "MSE uses squared percentage points",
        "the same frozen model",
        "No current-year target enters the predictor",
        "no R execution",
        "No hidden birth count is inferred",
        "source measurement precision",
        "one complete published creation decomposition differs by one job",
    ]:
        assert compact(phrase) in compact(tex), phrase
        assert compact(phrase) in compact(pdftext), phrase
        checks += 2
    scope = json.loads(
        (ROOT / "paper/PUBLICATION_SCOPE.json").read_text(encoding="utf-8")
    )
    assert (
        scope["scope"] == "independent-program-study"
        and scope["formal_submission_target"] is False
        and len(scope["public_files"]) == 5
    )
    checks += 1
    for name, digest in scope["public_files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
        checks += 1
    for name in ["year_errors", "sector_errors", "creation_components"]:
        assert (ROOT / "paper/images" / (name + ".pdf")).read_bytes() == (
            ROOT / "figures" / (name + ".pdf")
        ).read_bytes()
        checks += 1
    pdf_checks = 0
    for path in [ROOT / "paper/manuscript.pdf", *(ROOT / "paper/images").glob("*.pdf")]:
        reader = PdfReader(path)
        catalog = reader.trailer["/Root"]
        assert not any(k in catalog for k in ["/AA", "/AcroForm"])
        opening = catalog.get("/OpenAction")
        if opening is not None:
            assert (
                isinstance(opening, list)
                and len(opening) == 2
                and str(opening[1]) == "/Fit"
                and opening[0].get_object().get("/Type") == "/Page"
            )
        names = catalog.get("/Names", {})
        if hasattr(names, "get_object"):
            names = names.get_object()
        assert "/JavaScript" not in names and "/EmbeddedFiles" not in names
        for page in reader.pages:
            assert "/AA" not in page
            for ref in page.get("/Annots", []):
                annotation = ref.get_object()
                assert annotation.get("/Subtype") == "/Link" and "/AA" not in annotation
                if "/A" in annotation:
                    assert annotation["/A"].get("/S") == "/URI"
                if "/Rect" in annotation:
                    x0, y0, x1, y1 = map(float, annotation["/Rect"])
                    assert (
                        0 <= x0 <= x1 <= float(page.mediabox.right) + 0.5
                        and 0 <= y0 <= y1 <= float(page.mediabox.top) + 0.5
                    )
        pdf_checks += 1
    assert not re.search(
        r"[Cc]:\\[Uu]sers\\|/[Uu]sers/|/[Hh]ome/", pdftext + str(doc.metadata)
    )
    checks += 1
    result = dict(
        status="PASS",
        independent_paper_checks=checks,
        validation_rows=5,
        primary_rows=2,
        held_year_rows=4,
        size_subset_rows=3,
        sector_rows=19,
        local_failure_rows=5,
        composition_rows=19,
        pdf_pages=8,
        pdf_active_content_checks=pdf_checks,
        scope="Independent displayed-table reconstruction, raw source component sums, direct primary error recomputation, qualifications, exact paper hashes and bounded PDF actions. Source rights and rendered layout reviewed separately.",
    )
    (ROOT / "paper/VERIFICATION.json").write_bytes(
        (json.dumps(result, indent=2) + "\n").encode()
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
