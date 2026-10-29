"""Recreate the complete finite comparison in an isolated checkout."""

import csv, gzip, io, json, hashlib
from pathlib import Path
import shutil, subprocess, sys, tempfile
from verify_freeze import verify

ROOT = Path(__file__).resolve().parents[1]


def main():
    protected = verify()
    names = ["SELECTION.json", "results/cohort.csv"]
    for stage in ["validation", "held"]:
        names += [
            "results/" + stage + "-" + suffix
            for suffix in [
                "features.csv",
                "eligibility.csv",
                "predictions.csv.gz",
                "metrics.csv",
                "SUMMARY.json",
                "VERIFICATION.json",
            ]
        ]
    names += [
        "results/held-composition-cells.csv",
        "results/held-composition-sectors.csv",
    ]
    expected = {name: (ROOT / name).read_bytes() for name in names}
    fields = 0
    documents = 0
    with tempfile.TemporaryDirectory(prefix="employment10-replay-") as directory:
        temp = Path(directory) / "study"
        shutil.copytree(
            ROOT, temp, ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv")
        )
        for name in names:
            (temp / name).unlink()
        for stage in ["validation", "held"]:
            for script in ["run_analysis.py", "verify_results.py"]:
                result = subprocess.run(
                    [sys.executable, str(temp / "src" / script), stage],
                    cwd=temp,
                    capture_output=True,
                    text=True,
                )
                assert result.returncode == 0, result.stdout + result.stderr
        for name, old in expected.items():
            new = (temp / name).read_bytes()
            if name.endswith(".gz"):
                new = gzip.decompress(new)
                old = gzip.decompress(old)
            assert new == old, name
            if ".csv" in name:
                rows = list(csv.reader(io.StringIO(old.decode())))
                fields += (len(rows) - 1) * len(rows[0])
            else:
                documents += 1
        for name, digest in json.loads(
            (ROOT / "FREEZE.json").read_text(encoding="utf-8")
        )["sha256"].items():
            assert (
                hashlib.sha256((temp / name).read_bytes()).hexdigest() == digest
            ), name
    result = dict(
        status="PASS",
        exact_csv_fields=fields,
        selection_summary_and_verification_documents=documents,
        protected_dependencies=protected["dependencies"],
        scope="Exact isolated replay relative to declared12-place scoring representation and captured source cells, not original information vintages or source truth.",
    )
    (ROOT / "REPROCHECK.json").write_bytes(
        (json.dumps(result, indent=2) + "\n").encode()
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
