"""Original figures show all held years/sectors and incomplete source components."""

import csv, hashlib, json
from fractions import Fraction as F
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LABELS = {
    "11": "Agriculture & forestry",
    "21": "Mining & extraction",
    "22": "Utilities",
    "23": "Construction",
    "31-33": "Manufacturing",
    "42": "Wholesale trade",
    "44-45": "Retail trade",
    "48-49": "Transport & warehousing",
    "51": "Information",
    "52": "Finance & insurance",
    "53": "Real estate & leasing",
    "54": "Professional & technical",
    "55": "Company management",
    "56": "Admin & support services",
    "61": "Educational services",
    "62": "Health care & social aid",
    "71": "Arts & recreation",
    "72": "Accommodation & food",
    "81": "Other services",
}
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.facecolor": "white",
    }
)


def main():
    rows = list(
        csv.DictReader(
            (ROOT / "results/held-metrics.csv").open(encoding="utf-8", newline="")
        )
    )
    lookup = {(r["own_weight"], r["scope"], r["unit"]): r for r in rows}
    chosen = json.loads((ROOT / "SELECTION.json").read_text())["selected_own_weight"]
    assert chosen == "1/4"
    artists = {}
    hashes = {}

    def save(fig, name):
        for extension in ["pdf", "svg", "png"]:
            path = ROOT / "figures" / (name + "." + extension)
            fig.savefig(
                path,
                dpi=180,
                metadata={"Creator": "Original independent research figure"},
            )
            if extension == "svg":
                path.write_bytes(
                    (
                        "\n".join(
                            line.rstrip()
                            for line in path.read_text(encoding="utf-8").splitlines()
                        )
                        + "\n"
                    ).encode()
                )
            hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
        plt.close(fig)

    years = ["2020", "2021", "2022", "2023"]
    x = np.arange(4)
    selected = [float(F(lookup[chosen, "year", y]["mae"])) for y in years]
    baseline = [float(F(lookup["1", "year", y]["mae"])) for y in years]
    fig, ax = plt.subplots(figsize=(8.6, 4.9))
    fig.subplots_adjust(left=0.12, right=0.96, top=0.78, bottom=0.20)
    a = ax.bar(
        x - 0.18,
        selected,
        width=0.34,
        color="#006d77",
        label="25% own history / 75% other-state pool",
    )
    b = ax.bar(
        x + 0.18, baseline, width=0.34, color="#59677c", label="Own prior-year baseline"
    )
    for bars in [a, b]:
        for bar in bars:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.08,
                f"{bar.get_height():.3f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )
    ax.set_xticks(x, years)
    ax.set_ylim(0, max(baseline + selected) * 1.22)
    ax.set_ylabel("Mean absolute error (percentage points)")
    ax.set_xlabel("Held target year · March-to-March published job flows")
    ax.grid(axis="y", alpha=0.18)
    ax.set_axisbelow(True)
    ax.legend(
        loc="lower left", bbox_to_anchor=(0, 1.02), ncol=2, frameon=False, fontsize=8.5
    )
    fig.suptitle(
        "Pooling lowers overall error, with a small 2023 reversal",
        x=0.08,
        ha="left",
        y=0.97,
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.08,
        0.89,
        "All four held years · 934 fixed state-sector series · 3,736 forecast cases",
        fontsize=10,
        color="#354c5c",
    )
    fig.text(
        0.08,
        0.035,
        "Target: published expanding-continuer job gains per 100 DHS-average employees; not hires or vacancies.\nComplete prior-year inputs are idealized; original release vintages and live forecasting remain unverified.",
        fontsize=8.4,
        color="#354c5c",
    )
    artists["year_errors"] = dict(
        years=years,
        selected_heights=[r.get_height() for r in a],
        baseline_heights=[r.get_height() for r in b],
        annotations=[t.get_text() for t in ax.texts],
    )
    save(fig, "year_errors")

    sectors = list(LABELS)
    y = np.arange(19)
    selected = np.array([float(F(lookup[chosen, "sector", s]["mae"])) for s in sectors])
    baseline = np.array([float(F(lookup["1", "sector", s]["mae"])) for s in sectors])
    worse = selected > baseline
    fig, ax = plt.subplots(figsize=(8.6, 8.2))
    fig.subplots_adjust(left=0.36, right=0.96, top=0.82, bottom=0.13)
    segment = ax.hlines(
        y,
        np.minimum(selected, baseline),
        np.maximum(selected, baseline),
        color=["#c3462d" if w else "#b9c9d5" for w in worse],
        linewidth=3,
    )
    a = ax.scatter(selected, y, s=32, color="#006d77", label="Validated pool", zorder=3)
    b = ax.scatter(
        baseline, y, s=32, color="#59677c", marker="D", label="Own prior year", zorder=3
    )
    ax.set_yticks(y, [s + "  " + LABELS[s] for s in sectors], fontsize=8.8)
    ax.invert_yaxis()
    ax.set_xlim(0, max(max(selected), max(baseline)) * 1.16)
    ax.set_xlabel("Held equal-series MAE (percentage points)")
    ax.grid(axis="x", alpha=0.18)
    ax.set_axisbelow(True)
    ax.legend(
        loc="lower left", bbox_to_anchor=(0, 1.015), ncol=2, frameon=False, fontsize=9
    )
    fig.suptitle(
        "Four of nineteen sectors have higher pooled-model error",
        x=0.08,
        ha="left",
        y=0.97,
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.08,
        0.91,
        "All sectors retained; red segments mark a higher selected-model MAE",
        fontsize=10,
        color="#354c5c",
    )
    fig.text(
        0.08,
        0.035,
        "The fixed model has higher error in 428 of 934 state-sector series; the overall reduction is not universal.\nNineteen 2017-NAICS sectors; baseline eligibility excludes 35 small/flagged series before scoring.",
        fontsize=8.4,
        color="#354c5c",
    )
    artists["sector_errors"] = dict(
        sectors=sectors,
        labels=[t.get_text() for t in ax.get_yticklabels()],
        selected_offsets=a.get_offsets().tolist(),
        baseline_offsets=b.get_offsets().tolist(),
        segments=[r.tolist() for r in segment.get_segments()],
        worse=worse.tolist(),
    )
    save(fig, "sector_errors")

    composition = {
        r["sector"]: r
        for r in csv.DictReader(
            (ROOT / "results/held-composition-sectors.csv").open(
                encoding="utf-8", newline=""
            )
        )
    }
    birth = [float(F(composition[s]["birth_rate"])) for s in sectors]
    continuing = [float(F(composition[s]["continuer_rate"])) for s in sectors]
    fig, ax = plt.subplots(figsize=(8.6, 8.2))
    fig.subplots_adjust(left=0.36, right=0.96, top=0.82, bottom=0.13)
    a = ax.barh(
        y - 0.17, continuing, height=0.30, color="#006d77", label="Expanding continuers"
    )
    b = ax.barh(
        y + 0.17, birth, height=0.30, color="#c47a24", label="Opening establishments"
    )
    ax.set_yticks(y, [s + "  " + LABELS[s] for s in sectors], fontsize=8.8)
    ax.invert_yaxis()
    ax.set_xlim(0, max(birth + continuing) * 1.13)
    ax.set_xlabel("Published job gains per 100 DHS-average employees")
    ax.grid(axis="x", alpha=0.18)
    ax.set_axisbelow(True)
    ax.legend(
        loc="lower left", bbox_to_anchor=(0, 1.015), ncol=2, frameon=False, fontsize=8.8
    )
    fig.suptitle(
        "Separate establishment openings from continuing expansion",
        x=0.08,
        ha="left",
        y=0.97,
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.08,
        0.91,
        "Pooled 2020–2023 annual components on the same complete-component cases",
        fontsize=10,
        color="#354c5c",
    )
    fig.text(
        0.08,
        0.035,
        "Composition covers 3,715 of 3,736 model cases; 21 missing-component cases stay missing.\nOne creation decomposition differs by one published job. Components are unaltered and are not worker hires.",
        fontsize=8.4,
        color="#354c5c",
    )
    artists["creation_components"] = dict(
        sectors=sectors,
        continuing_widths=[r.get_width() for r in a],
        birth_widths=[r.get_width() for r in b],
        model_cases=[int(composition[s]["model_cases"]) for s in sectors],
        complete_cases=[
            int(composition[s]["creation_complete_cases"]) for s in sectors
        ],
    )
    save(fig, "creation_components")
    (ROOT / "figures/ARTIST_VALUES.json").write_bytes(
        (json.dumps(artists, indent=2) + "\n").encode()
    )
    (ROOT / "figures/MANIFEST.json").write_bytes(
        (json.dumps(hashes, indent=2) + "\n").encode()
    )
    print(json.dumps(dict(figures=3, exports=len(hashes))))


if __name__ == "__main__":
    main()
