import csv
import math
from pathlib import Path
from typing import Dict, List, Any, Optional

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt


INPUT_CSV = Path("artifacts/diagnosis/well_property_driver_context.csv")
INPUT_JSON = Path("artifacts/diagnosis/water_driver_diagnosis.json")
OUTPUT_DIR = Path("artifacts/diagnosis/maps")


ACTION_COLORS = {
    "review_lateral_trans_multiplier": "red",
    "review_vertical_trans_multiplier": "purple",
    "review_base_transmissibility": "orange",
    "review_low_lateral_multiplier": "blue",
    "review_under_connectivity": "navy",
    "review_water_front_support": "cyan",
    "review_relperm_or_well_connection": "magenta",
    "review_water_front_or_relperm": "brown",
    "review_profile_timing": "gold",
    "inactive_in_sim_and_history": "lightgray",
    "inactive_water_in_sim_and_history": "silver",
    "no_water_action": "green",
    "no_hm_comment": "lightgray",
}

TIMING_COLORS = {
    "early_breakthrough": "red",
    "delayed_breakthrough": "blue",
    "simulated_breakthrough_only": "darkred",
    "historical_breakthrough_only": "darkblue",
    "breakthrough_timing_close": "gold",
    "no_breakthrough_detected": "lightgray",
    None: "lightgray",
}


def read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input CSV: {path}. Run python -m app.driver_diagnosis first.")

    rows = []

    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            rows.append(row)

    return rows


def read_diagnoses_by_well(path: Path) -> Dict[str, Dict[str, Any]]:
    import json

    if not path.exists():
        raise FileNotFoundError(f"Missing input JSON: {path}. Run python -m app.driver_diagnosis first.")

    items = json.loads(path.read_text(encoding="utf-8"))

    return {item["well"]: item for item in items}


def to_float(value: Any) -> Optional[float]:
    if value in [None, "", "None", "null", "N/A"]:
        return None

    try:
        return float(value)
    except Exception:
        return None


def marker_size(row: Dict[str, Any]) -> float:
    score = to_float(row.get("water_hm_score"))

    if score is None:
        return 120.0

    severity = max(0.0, 100.0 - score)
    return 100.0 + severity * 4.0


def plot_action_map(rows: List[Dict[str, Any]], diagnoses: Dict[str, Dict[str, Any]]) -> None:
    plt.figure(figsize=(12, 9))

    for row in rows:
        x = to_float(row.get("i"))
        y = to_float(row.get("j"))

        if x is None or y is None:
            continue

        diagnosis = diagnoses.get(row["well"], {})
        action = diagnosis.get("action_category", "no_hm_comment")
        color = ACTION_COLORS.get(action, "lightgray")

        plt.scatter(
            x,
            y,
            s=marker_size(row),
            color=color,
            edgecolor="black",
            linewidth=0.8,
            alpha=0.9,
        )

        score = to_float(row.get("water_hm_score"))
        score_text = "NA" if score is None else f"{score:.0f}"

        plt.text(x + 0.7, y + 0.7, f"{row['well']}\nW {score_text}", fontsize=8)

    plt.gca().invert_yaxis()
    plt.title("Recommended Water-Mismatch Action Map")
    plt.xlabel("Grid I")
    plt.ylabel("Grid J")
    plt.grid(True, alpha=0.25)

    for action, color in ACTION_COLORS.items():
        plt.scatter([], [], color=color, edgecolor="black", label=action)

    plt.legend(fontsize=7, loc="best")
    plt.tight_layout()

    out = OUTPUT_DIR / "water_action_map.png"
    plt.savefig(out, dpi=180)
    plt.close()
    print(f"[OK] Saved {out}")


def plot_timing_map(rows: List[Dict[str, Any]]) -> None:
    plt.figure(figsize=(12, 9))

    for row in rows:
        x = to_float(row.get("i"))
        y = to_float(row.get("j"))

        if x is None or y is None:
            continue

        timing = row.get("water_timing_issue")
        color = TIMING_COLORS.get(timing, "lightgray")

        delta_days = to_float(row.get("water_breakthrough_delta_days"))
        if delta_days is None:
            delta_text = "NA"
        else:
            delta_text = f"{delta_days / 365.25:.1f}y"

        plt.scatter(
            x,
            y,
            s=marker_size(row),
            color=color,
            edgecolor="black",
            linewidth=0.8,
            alpha=0.9,
        )

        plt.text(x + 0.7, y + 0.7, f"{row['well']}\n{delta_text}", fontsize=8)

    plt.gca().invert_yaxis()
    plt.title("Water Breakthrough Timing Map")
    plt.xlabel("Grid I")
    plt.ylabel("Grid J")
    plt.grid(True, alpha=0.25)

    for timing, color in TIMING_COLORS.items():
        plt.scatter([], [], color=color, edgecolor="black", label=str(timing))

    plt.legend(fontsize=8, loc="best")
    plt.tight_layout()

    out = OUTPUT_DIR / "water_breakthrough_timing_map.png"
    plt.savefig(out, dpi=180)
    plt.close()
    print(f"[OK] Saved {out}")


def plot_property_bubble_map(
    rows: List[Dict[str, Any]],
    property_field: str,
    title: str,
    filename: str,
) -> None:
    plt.figure(figsize=(12, 9))

    values = [to_float(row.get(property_field)) for row in rows]
    values = [v for v in values if v is not None]

    if not values:
        print(f"[SKIP] {property_field}: no values")
        return

    min_v = min(values)
    max_v = max(values)

    for row in rows:
        x = to_float(row.get("i"))
        y = to_float(row.get("j"))
        v = to_float(row.get(property_field))

        if x is None or y is None or v is None:
            continue

        if max_v > min_v:
            norm = (v - min_v) / (max_v - min_v)
        else:
            norm = 0.5

        size = 80 + 420 * norm

        score = to_float(row.get("water_hm_score"))
        if score is None:
            edge = "gray"
        elif score < 60:
            edge = "red"
        elif score < 80:
            edge = "gold"
        else:
            edge = "green"

        plt.scatter(
            x,
            y,
            s=size,
            alpha=0.65,
            edgecolor=edge,
            linewidth=2,
        )

        plt.text(x + 0.7, y + 0.7, f"{row['well']}\n{v:.2g}", fontsize=8)

    plt.gca().invert_yaxis()
    plt.title(title)
    plt.xlabel("Grid I")
    plt.ylabel("Grid J")
    plt.grid(True, alpha=0.25)
    plt.tight_layout()

    out = OUTPUT_DIR / filename
    plt.savefig(out, dpi=180)
    plt.close()
    print(f"[OK] Saved {out}")


def plot_scatter(
    rows: List[Dict[str, Any]],
    x_field: str,
    y_field: str,
    title: str,
    filename: str,
) -> None:
    plt.figure(figsize=(9, 6))

    for row in rows:
        x = to_float(row.get(x_field))
        y = to_float(row.get(y_field))

        if x is None or y is None:
            continue

        timing = row.get("water_timing_issue")
        color = TIMING_COLORS.get(timing, "lightgray")

        plt.scatter(x, y, s=110, color=color, edgecolor="black", alpha=0.85)
        plt.text(x, y, row["well"], fontsize=8, ha="left", va="bottom")

    plt.title(title)
    plt.xlabel(x_field)
    plt.ylabel(y_field)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    out = OUTPUT_DIR / filename
    plt.savefig(out, dpi=180)
    plt.close()
    print(f"[OK] Saved {out}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = read_csv_rows(INPUT_CSV)
    diagnoses = read_diagnoses_by_well(INPUT_JSON)

    plot_action_map(rows, diagnoses)
    plot_timing_map(rows)

    plot_property_bubble_map(
        rows,
        property_field="mean_tran_h_percentile",
        title="Local TRAN_H Percentile Around Completed Cells",
        filename="tran_h_percentile_map.png",
    )

    plot_property_bubble_map(
        rows,
        property_field="mean_mult_h",
        title="Mean MULT_H Around Completed Cells",
        filename="mult_h_map.png",
    )

    plot_property_bubble_map(
        rows,
        property_field="mean_swat_eoh",
        title="Mean SWAT_EOH Around Completed Cells",
        filename="swat_eoh_map.png",
    )

    plot_scatter(
        rows,
        x_field="mean_tran_h_percentile",
        y_field="water_hm_score",
        title="Water HM Score vs TRAN_H Percentile",
        filename="scatter_water_score_vs_tran_h_percentile.png",
    )

    plot_scatter(
        rows,
        x_field="mean_mult_h",
        y_field="water_hm_score",
        title="Water HM Score vs MULT_H",
        filename="scatter_water_score_vs_mult_h.png",
    )

    print("")
    print(f"Maps saved in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
