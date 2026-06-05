import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt


PRODUCER_CSV = Path("artifacts/diagnosis/well_property_driver_context.csv")
PRODUCER_DIAGNOSIS_JSON = Path("artifacts/diagnosis/water_driver_diagnosis.json")
INJECTION_JSON = Path("artifacts/injection_hm/injection_hm_results.json")
OUTPUT_DIR = Path("artifacts/integrated_context/maps")


PRODUCER_COLORS = {
    "early_breakthrough": "red",
    "delayed_breakthrough": "blue",
    "simulated_breakthrough_only": "darkred",
    "historical_breakthrough_only": "darkblue",
    "breakthrough_timing_close": "gold",
    "no_breakthrough_detected": "lightgray",
    None: "lightgray",
}

INJECTOR_COLORS = {
    "simulated_over_injection": "red",
    "simulated_under_injection": "blue",
    "final_injection_close": "green",
    "negligible_injection": "lightgray",
    "unknown": "black",
    None: "black",
}


def to_float(value: Any) -> Optional[float]:
    if value in [None, "", "None", "null", "N/A"]:
        return None

    try:
        return float(value)
    except Exception:
        return None


def read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")

    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def injection_direction(payload: Dict[str, Any]) -> str:
    water = payload.get("variables", {}).get("water_injection", {})
    gas = payload.get("variables", {}).get("gas_injection", {})

    water_direction = water.get("direction")
    gas_direction = gas.get("direction")

    if water_direction in ["simulated_over_injection", "simulated_under_injection"]:
        return water_direction

    if gas_direction in ["simulated_over_injection", "simulated_under_injection"]:
        return gas_direction

    if water_direction == "final_injection_close" or gas_direction == "final_injection_close":
        return "final_injection_close"

    return water_direction or gas_direction or "unknown"


def is_injector(payload: Dict[str, Any]) -> bool:
    return payload.get("role") in [
        "water_injector",
        "gas_injector",
        "wag_or_dual_injector",
        "mixed_producer_water_injector",
        "mixed_producer_gas_injector",
        "mixed_producer_wag",
    ]


def producer_marker_size(row: Dict[str, Any]) -> float:
    score = to_float(row.get("water_hm_score"))

    if score is None:
        return 90.0

    return 90.0 + max(0.0, 100.0 - score) * 4.0


def injector_marker_size(payload: Dict[str, Any]) -> float:
    score = payload.get("injection_hm_score")

    if score is None:
        return 130.0

    return 130.0 + max(0.0, 100.0 - float(score)) * 3.5


def plot_integrated_map() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    producers = read_csv_rows(PRODUCER_CSV)
    diagnoses = {d["well"]: d for d in load_json(PRODUCER_DIAGNOSIS_JSON)}
    injection_payload = load_json(INJECTION_JSON)
    injectors = injection_payload.get("well_results", {})

    plt.figure(figsize=(13, 10))

    # Producers
    for row in producers:
        x = to_float(row.get("i"))
        y = to_float(row.get("j"))

        if x is None or y is None:
            continue

        diagnosis = diagnoses.get(row["well"], {})
        action = diagnosis.get("action_category")

        if action in ["no_hm_comment", "inactive_water_in_sim_and_history", "no_water_action"]:
            alpha = 0.35
        else:
            alpha = 0.9

        timing = row.get("water_timing_issue")
        color = PRODUCER_COLORS.get(timing, "lightgray")

        plt.scatter(
            x,
            y,
            s=producer_marker_size(row),
            color=color,
            edgecolor="black",
            linewidth=0.8,
            marker="o",
            alpha=alpha,
        )

        score = to_float(row.get("water_hm_score"))
        score_text = "NA" if score is None else f"{score:.0f}"

        plt.text(x + 0.7, y + 0.7, f"{row['well']}\nW{score_text}", fontsize=8)

    # Injectors
    for well, payload in injectors.items():
        if not is_injector(payload):
            continue

        x = to_float(payload.get("i"))
        y = to_float(payload.get("j"))

        if x is None or y is None:
            continue

        direction = injection_direction(payload)
        color = INJECTOR_COLORS.get(direction, "black")

        plt.scatter(
            x,
            y,
            s=injector_marker_size(payload),
            color=color,
            edgecolor="black",
            linewidth=1.2,
            marker="^",
            alpha=0.95,
        )

        score = payload.get("injection_hm_score")
        score_text = "NA" if score is None else f"{float(score):.0f}"

        plt.text(x + 0.7, y - 1.4, f"{well}\nI{score_text}", fontsize=8)

    plt.gca().invert_yaxis()
    plt.title("Integrated Producer Water HM and Injector Injection HM Map")
    plt.xlabel("Grid I")
    plt.ylabel("Grid J")
    plt.grid(True, alpha=0.25)

    # Legend proxies
    for label, color in PRODUCER_COLORS.items():
        plt.scatter([], [], color=color, edgecolor="black", marker="o", label=f"Producer {label}")

    for label, color in INJECTOR_COLORS.items():
        plt.scatter([], [], color=color, edgecolor="black", marker="^", label=f"Injector {label}")

    plt.legend(fontsize=7, loc="best")
    plt.tight_layout()

    out = OUTPUT_DIR / "producer_injector_integrated_map.png"
    plt.savefig(out, dpi=180)
    plt.close()

    print(f"[OK] Saved {out}")


def main() -> None:
    plot_integrated_map()


if __name__ == "__main__":
    main()
