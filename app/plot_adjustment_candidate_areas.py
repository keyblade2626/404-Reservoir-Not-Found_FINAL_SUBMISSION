import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from app.well_connections import get_well_spatial_summary


FINAL_DIAGNOSIS_JSON = Path("artifacts/final_diagnosis/final_hm_diagnosis.json")
OUTPUT_DIR = Path("artifacts/final_diagnosis/adjustment_maps")

# Raggio in celle intorno alle completions.
# 3 = abbastanza locale; 5 = più largo.
DEFAULT_RADIUS_CELLS = 3


ACTION_STYLES = {
    "candidate_increase_local_tran_mult": {
        "color": "red",
        "label": "Candidate increase local TRAN/MULT",
    },
    "candidate_reduce_local_tran_mult": {
        "color": "blue",
        "label": "Candidate reduce local TRAN/MULT",
    },
    "review_water_relperm_mobility": {
        "color": "orange",
        "label": "Review water relperm / krw mobility",
    },
    "review_fault_or_regional_connectivity": {
        "color": "purple",
        "label": "Review fault / regional connectivity",
    },
    "review_injector_connectivity": {
        "color": "green",
        "label": "Review injector connectivity/allocation",
    },
    "unresolved_review": {
        "color": "gray",
        "label": "Unresolved review area",
    },
}


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def to_float(value: Any) -> Optional[float]:
    if value in [None, "", "None", "null", "N/A"]:
        return None
    try:
        return float(value)
    except Exception:
        return None


def get_well_completion_cells() -> Dict[str, Dict[str, Any]]:
    spatial = get_well_spatial_summary()
    out = {}

    for well, payload in spatial.get("wells", {}).items():
        connections = []

        for c in payload.get("connections", []):
            try:
                connections.append({
                    "i": int(c["i"]),
                    "j": int(c["j"]),
                    "k": int(c["k"]),
                })
            except Exception:
                continue

        out[well] = {
            "well": well,
            "representative_i": to_float(payload.get("representative_i")),
            "representative_j": to_float(payload.get("representative_j")),
            "connections": connections,
        }

    return out


def choose_candidate_action(diagnosis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts final diagnosis into an actionable map category.

    Important:
    This does not prescribe a final model edit. It only highlights areas to review.
    """
    primary_driver = diagnosis.get("primary_driver")
    driver_family = diagnosis.get("driver_family")
    issue_type = diagnosis.get("water_issue_type")
    local = diagnosis.get("local_property_signals", {}) or {}

    high_tran = bool(local.get("high_tran_signal"))
    low_tran = bool(local.get("low_tran_signal"))
    high_swat = bool(local.get("high_water_saturation_signal"))
    increasing_swat = bool(local.get("increasing_water_saturation_signal"))

    if primary_driver in [
        "connected_injector_over_injection",
        "connected_injector_under_injection",
        "increasing_streamline_support",
    ]:
        return {
            "action_category": "review_injector_connectivity",
            "recommended_local_edit": "Do not start with local producer multiplier. First review injector allocation/connectivity.",
            "radius_cells": DEFAULT_RADIUS_CELLS,
        }

    if primary_driver == "local_high_transmissibility_or_multiplier":
        return {
            "action_category": "candidate_reduce_local_tran_mult",
            "recommended_local_edit": "Candidate area to reduce local TRAN/MULT if geologically justified.",
            "radius_cells": DEFAULT_RADIUS_CELLS,
        }

    if primary_driver == "local_low_transmissibility_or_multiplier":
        return {
            "action_category": "candidate_increase_local_tran_mult",
            "recommended_local_edit": "Candidate area to increase local TRAN/MULT if geologically justified.",
            "radius_cells": DEFAULT_RADIUS_CELLS,
        }

    if primary_driver == "high_swat_but_low_simulated_water_production":
        if low_tran:
            return {
                "action_category": "candidate_increase_local_tran_mult",
                "recommended_local_edit": (
                    "High SWAT but low simulated water, with low TRAN/KH signal. "
                    "Candidate to increase local communication via PERM/TRAN/MULT review."
                ),
                "radius_cells": DEFAULT_RADIUS_CELLS,
            }

        return {
            "action_category": "review_water_relperm_mobility",
            "recommended_local_edit": (
                "High SWAT but low simulated water without clear low TRAN signal. "
                "Do not start with multiplier; first review water relperm/krw mobility."
            ),
            "radius_cells": DEFAULT_RADIUS_CELLS,
        }

    if issue_type in ["simulated_water_too_early", "simulated_water_too_high"]:
        if high_tran:
            return {
                "action_category": "candidate_reduce_local_tran_mult",
                "recommended_local_edit": (
                    "Simulated water is too early/high and local TRAN/KH is high. "
                    "Candidate to reduce local communication if supported by geology."
                ),
                "radius_cells": DEFAULT_RADIUS_CELLS,
            }

        if high_swat or increasing_swat:
            return {
                "action_category": "review_fault_or_regional_connectivity",
                "recommended_local_edit": (
                    "Water is too early/high but local TRAN is not clearly high. "
                    "Review regional/fault connectivity and water-front movement."
                ),
                "radius_cells": DEFAULT_RADIUS_CELLS + 2,
            }

    if issue_type in ["simulated_water_too_late", "simulated_water_too_low"]:
        if low_tran:
            return {
                "action_category": "candidate_increase_local_tran_mult",
                "recommended_local_edit": (
                    "Simulated water is too low/late and local TRAN/KH is low. "
                    "Candidate to increase local communication if supported by geology."
                ),
                "radius_cells": DEFAULT_RADIUS_CELLS,
            }

    return {
        "action_category": "unresolved_review",
        "recommended_local_edit": "No direct multiplier recommendation. Review maps, relperm, connectivity and fault context.",
        "radius_cells": DEFAULT_RADIUS_CELLS,
    }


def build_candidate_cells_for_well(
    well: str,
    well_info: Dict[str, Any],
    diagnosis: Dict[str, Any],
    action: Dict[str, Any],
) -> List[Dict[str, Any]]:

    radius = int(action["radius_cells"])
    rows = []
    seen = set()

    connections = well_info.get("connections", [])

    for c in connections:
        ci = int(c["i"])
        cj = int(c["j"])
        ck = int(c["k"])

        for di in range(-radius, radius + 1):
            for dj in range(-radius, radius + 1):
                # circular-ish neighbourhood in I/J
                dist = math.sqrt(di * di + dj * dj)

                if dist > radius:
                    continue

                ii = ci + di
                jj = cj + dj

                key = (well, ii, jj, ck, action["action_category"])

                if key in seen:
                    continue

                seen.add(key)

                rows.append({
                    "well": well,
                    "i": ii,
                    "j": jj,
                    "k": ck,
                    "source_completion_i": ci,
                    "source_completion_j": cj,
                    "source_completion_k": ck,
                    "distance_cells": round(dist, 3),
                    "action_category": action["action_category"],
                    "recommended_local_edit": action["recommended_local_edit"],
                    "water_hm_score": diagnosis.get("water_hm_score"),
                    "water_issue_type": diagnosis.get("water_issue_type"),
                    "primary_driver": diagnosis.get("primary_driver"),
                    "driver_family": diagnosis.get("driver_family"),
                    "confidence": diagnosis.get("confidence"),
                })

    return rows


def build_all_candidate_cells() -> Dict[str, Any]:
    final = load_json(FINAL_DIAGNOSIS_JSON)
    wells = get_well_completion_cells()

    all_rows = []
    well_summaries = []

    for diagnosis in final.get("diagnoses", []):
        well = diagnosis.get("well")

        if not well or well not in wells:
            continue

        action = choose_candidate_action(diagnosis)
        rows = build_candidate_cells_for_well(well, wells[well], diagnosis, action)

        all_rows.extend(rows)

        well_summaries.append({
            "well": well,
            "representative_i": wells[well]["representative_i"],
            "representative_j": wells[well]["representative_j"],
            "completion_count": len(wells[well].get("connections", [])),
            "candidate_cell_count": len(rows),
            "action_category": action["action_category"],
            "recommended_local_edit": action["recommended_local_edit"],
            "water_hm_score": diagnosis.get("water_hm_score"),
            "water_issue_type": diagnosis.get("water_issue_type"),
            "primary_driver": diagnosis.get("primary_driver"),
            "driver_family": diagnosis.get("driver_family"),
            "confidence": diagnosis.get("confidence"),
        })

    return {
        "candidate_cells": all_rows,
        "well_summaries": well_summaries,
    }


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Saved {path}")


def plot_all_candidate_areas(payload: Dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cells = payload["candidate_cells"]
    summaries = payload["well_summaries"]

    if not cells:
        print("No candidate cells to plot.")
        return

    plt.figure(figsize=(16, 12))

    used_labels = set()

    for action_category, style in ACTION_STYLES.items():
        rows = [r for r in cells if r["action_category"] == action_category]

        if not rows:
            continue

        x = [float(r["i"]) for r in rows]
        y = [float(r["j"]) for r in rows]

        label = style["label"]

        plt.scatter(
            x,
            y,
            s=16,
            c=style["color"],
            alpha=0.23,
            marker="s",
            label=label if label not in used_labels else None,
        )

        used_labels.add(label)

    # Plot diagnosed wells
    for s in summaries:
        x = to_float(s["representative_i"])
        y = to_float(s["representative_j"])

        if x is None or y is None:
            continue

        action_category = s["action_category"]
        color = ACTION_STYLES.get(action_category, ACTION_STYLES["unresolved_review"])["color"]

        plt.scatter(
            x,
            y,
            s=110,
            c=color,
            edgecolor="black",
            linewidth=1.0,
            marker="o",
            zorder=5,
        )

        plt.text(
            x + 1.0,
            y + 1.0,
            f"{s['well']}\n{s['primary_driver']}",
            fontsize=8,
            color="black",
            zorder=6,
        )

    plt.title(
        "Candidate Adjustment Areas Around Diagnosed Producers\n"
        "Highlighted cells are investigation areas, not automatic multiplier edits"
    )

    plt.xlabel("Grid I")
    plt.ylabel("Grid J")
    plt.grid(True, alpha=0.25)
    plt.gca().invert_yaxis()
    plt.gca().set_aspect("equal", adjustable="box")
    plt.legend(loc="best", fontsize=8)
    plt.tight_layout()

    out = OUTPUT_DIR / "candidate_adjustment_areas_all.png"
    plt.savefig(out, dpi=220)
    plt.close()

    print(f"[OK] Saved {out}")


def plot_per_well_maps(payload: Dict[str, Any]) -> None:
    cells = payload["candidate_cells"]
    summaries = payload["well_summaries"]

    for s in summaries:
        well = s["well"]
        rows = [r for r in cells if r["well"] == well]

        if not rows:
            continue

        action_category = s["action_category"]
        style = ACTION_STYLES.get(action_category, ACTION_STYLES["unresolved_review"])

        x = [float(r["i"]) for r in rows]
        y = [float(r["j"]) for r in rows]

        plt.figure(figsize=(10, 9))

        plt.scatter(
            x,
            y,
            s=28,
            c=style["color"],
            alpha=0.35,
            marker="s",
            label=style["label"],
        )

        rep_i = to_float(s["representative_i"])
        rep_j = to_float(s["representative_j"])

        if rep_i is not None and rep_j is not None:
            plt.scatter(
                rep_i,
                rep_j,
                s=150,
                c=style["color"],
                edgecolor="black",
                linewidth=1.0,
                marker="o",
                zorder=5,
                label="Producer representative location",
            )

            plt.text(rep_i + 0.5, rep_j + 0.5, well, fontsize=10, color="black")

        plt.title(
            f"{well} - Candidate Adjustment Area\n"
            f"Driver: {s['primary_driver']} | Action: {s['action_category']}\n"
            f"{s['recommended_local_edit']}"
        )

        plt.xlabel("Grid I")
        plt.ylabel("Grid J")
        plt.grid(True, alpha=0.25)
        plt.gca().invert_yaxis()
        plt.gca().set_aspect("equal", adjustable="box")
        plt.legend(loc="best", fontsize=8)
        plt.tight_layout()

        safe_well = well.replace("/", "_").replace("\\", "_")
        out = OUTPUT_DIR / f"candidate_area_{safe_well}.png"
        plt.savefig(out, dpi=220)
        plt.close()

        print(f"[OK] Saved {out}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = build_all_candidate_cells()

    json_path = OUTPUT_DIR / "candidate_adjustment_areas.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[OK] Saved {json_path}")

    write_csv(OUTPUT_DIR / "candidate_adjustment_cells.csv", payload["candidate_cells"])
    write_csv(OUTPUT_DIR / "candidate_adjustment_well_summary.csv", payload["well_summaries"])

    plot_all_candidate_areas(payload)
    plot_per_well_maps(payload)

    print("")
    print("Candidate adjustment maps completed.")
    print(f"Wells mapped: {len(payload['well_summaries'])}")
    print(f"Candidate cells: {len(payload['candidate_cells'])}")
    print(f"Output folder: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
