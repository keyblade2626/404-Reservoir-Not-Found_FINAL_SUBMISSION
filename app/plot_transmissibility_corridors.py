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
from app.streamline_near_well_mapper import (
    extract_polylines,
    apply_bbox_transform,
)


FINAL_DIAGNOSIS_JSON = Path("artifacts/final_diagnosis/final_hm_diagnosis.json")
CLUSTER_SNAP_JSON = Path("artifacts/streamlines/cluster_snap/cluster_snap_streamline_connections.json")

OUTPUT_DIR = Path("artifacts/final_diagnosis/transmissibility_corridors")

# Use EOH because it represents end-of-history connectivity.
SNAPSHOT = "eoh"

# Corridor mode:
# "full" = whole snapped streamline corridor
# "producer_side" = only final portion close to producer
CORRIDOR_MODE = "full"

# If CORRIDOR_MODE = "producer_side", keep only last fraction of streamline points.
PRODUCER_SIDE_FRACTION = 0.45

# Buffer around each rasterized streamline point, in grid cells.
# 1 = thin corridor, 2/3 = wider operational area.
CORRIDOR_BUFFER_CELLS = 2

# Densification step along streamline segments in grid-cell units.
SEGMENT_SAMPLE_STEP_CELLS = 0.5

# K handling:
# "producer_completed_k" = export corridor cells only on K layers completed by that producer.
# This is practical for a first MULT candidate list.
K_MODE = "producer_completed_k"

# Which final diagnosis drivers should produce a transmissibility corridor.
INCREASE_TRAN_DRIVERS = {
    "high_swat_but_low_simulated_water_production",
    "local_low_transmissibility_or_multiplier",
}

DECREASE_TRAN_DRIVERS = {
    "local_high_transmissibility_or_multiplier",
}


ACTION_STYLE = {
    "increase_transmissibility_corridor": {
        "color": "red",
        "label": "Candidate increase TRAN/MULT corridor",
    },
    "decrease_transmissibility_corridor": {
        "color": "blue",
        "label": "Candidate reduce TRAN/MULT corridor",
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


def transform_from_json(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "swap_xy": payload["swap_xy"],
        "flip_x": payload["flip_x"],
        "flip_y": payload["flip_y"],
        "src_min": np.asarray(payload["src_min"], dtype=float),
        "scale": np.asarray(payload["scale"], dtype=float),
        "tgt_min": np.asarray(payload["tgt_min"], dtype=float),
    }


def load_final_diagnoses() -> Dict[str, Dict[str, Any]]:
    data = load_json(FINAL_DIAGNOSIS_JSON)

    return {
        item["well"]: item
        for item in data.get("diagnoses", [])
        if item.get("well")
    }


def load_cluster_snap() -> Dict[str, Any]:
    return load_json(CLUSTER_SNAP_JSON)


def load_well_connections_summary() -> Dict[str, Dict[str, Any]]:
    spatial = get_well_spatial_summary()
    output = {}

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

        k_values = sorted(set(c["k"] for c in connections))

        output[well] = {
            "well": well,
            "representative_i": to_float(payload.get("representative_i")),
            "representative_j": to_float(payload.get("representative_j")),
            "connections": connections,
            "completed_k_values": k_values,
        }

    return output


def choose_corridor_action(diagnosis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    primary_driver = diagnosis.get("primary_driver")
    issue_type = diagnosis.get("water_issue_type")

    if primary_driver in INCREASE_TRAN_DRIVERS:
        return {
            "action_category": "increase_transmissibility_corridor",
            "multiplier_direction": "increase",
            "reason": (
                "Water is under-produced or delayed and the diagnosis indicates insufficient local "
                "communication/mobility through the model corridor. This corridor is a candidate area "
                "where increasing transmissibility multipliers may be tested, if geologically justified."
            ),
        }

    if primary_driver in DECREASE_TRAN_DRIVERS:
        return {
            "action_category": "decrease_transmissibility_corridor",
            "multiplier_direction": "decrease",
            "reason": (
                "Water is over-produced or too early and the diagnosis indicates excessive local "
                "communication. This corridor is a candidate area where reducing transmissibility "
                "multipliers may be tested, if geologically justified."
            ),
        }

    # Additional fallback:
    # If water is too low/late and final diagnosis is unresolved but low TRAN signal exists,
    # still create a candidate increase corridor.
    local = diagnosis.get("local_property_signals", {}) or {}

    if issue_type in ["simulated_water_too_low", "simulated_water_too_late"] and local.get("low_tran_signal"):
        return {
            "action_category": "increase_transmissibility_corridor",
            "multiplier_direction": "increase",
            "reason": (
                "Water is too low/late and local low-TRAN signal is present. Corridor can be reviewed "
                "as a possible area for increasing transmissibility."
            ),
        }

    if issue_type in ["simulated_water_too_high", "simulated_water_too_early"] and local.get("high_tran_signal"):
        return {
            "action_category": "decrease_transmissibility_corridor",
            "multiplier_direction": "decrease",
            "reason": (
                "Water is too high/early and local high-TRAN signal is present. Corridor can be reviewed "
                "as a possible area for reducing transmissibility."
            ),
        }

    return None


def densify_polyline(points: np.ndarray, step: float) -> np.ndarray:
    if len(points) < 2:
        return points

    samples = []

    for idx in range(len(points) - 1):
        p0 = points[idx]
        p1 = points[idx + 1]

        dx = float(p1[0] - p0[0])
        dy = float(p1[1] - p0[1])
        dist = math.sqrt(dx * dx + dy * dy)

        n = max(1, int(math.ceil(dist / max(step, 1e-9))))

        for t in np.linspace(0.0, 1.0, n, endpoint=False):
            samples.append(p0 + t * (p1 - p0))

    samples.append(points[-1])

    return np.asarray(samples, dtype=float)


def select_corridor_portion(points: np.ndarray) -> np.ndarray:
    if CORRIDOR_MODE.lower() == "producer_side":
        n = len(points)
        start = int(max(0, math.floor(n * (1.0 - PRODUCER_SIDE_FRACTION))))
        return points[start:]

    return points


def buffer_cell_indices(i: int, j: int, radius: int) -> List[Tuple[int, int, float]]:
    rows = []

    for di in range(-radius, radius + 1):
        for dj in range(-radius, radius + 1):
            d = math.sqrt(di * di + dj * dj)

            if d <= radius:
                rows.append((i + di, j + dj, d))

    return rows


def rasterize_corridor(
    well: str,
    streamline_id: int,
    snapped_points: np.ndarray,
    completed_k_values: List[int],
    action: Dict[str, Any],
    diagnosis: Dict[str, Any],
) -> List[Dict[str, Any]]:

    selected = select_corridor_portion(snapped_points)
    dense = densify_polyline(selected, SEGMENT_SAMPLE_STEP_CELLS)

    rows = []
    seen = set()

    if K_MODE == "producer_completed_k":
        k_values = completed_k_values or [None]
    else:
        k_values = [None]

    for p in dense:
        i0 = int(round(float(p[0])))
        j0 = int(round(float(p[1])))

        for ii, jj, d in buffer_cell_indices(i0, j0, CORRIDOR_BUFFER_CELLS):
            for kk in k_values:
                key = (well, streamline_id, ii, jj, kk, action["action_category"])

                if key in seen:
                    continue

                seen.add(key)

                rows.append({
                    "well": well,
                    "streamline_id": streamline_id,
                    "i": ii,
                    "j": jj,
                    "k": kk,
                    "corridor_mode": CORRIDOR_MODE,
                    "buffer_radius_cells": CORRIDOR_BUFFER_CELLS,
                    "distance_from_streamline_point_cells": round(d, 3),
                    "action_category": action["action_category"],
                    "multiplier_direction": action["multiplier_direction"],
                    "reason": action["reason"],
                    "water_hm_score": diagnosis.get("water_hm_score"),
                    "water_issue_type": diagnosis.get("water_issue_type"),
                    "primary_driver": diagnosis.get("primary_driver"),
                    "driver_family": diagnosis.get("driver_family"),
                    "confidence": diagnosis.get("confidence"),
                })

    return rows


def aggregate_candidate_cells(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[Any, ...], Dict[str, Any]] = {}

    for r in rows:
        key = (
            r["well"],
            r["i"],
            r["j"],
            r["k"],
            r["action_category"],
            r["multiplier_direction"],
        )

        if key not in grouped:
            grouped[key] = {
                "well": r["well"],
                "i": r["i"],
                "j": r["j"],
                "k": r["k"],
                "action_category": r["action_category"],
                "multiplier_direction": r["multiplier_direction"],
                "corridor_mode": r["corridor_mode"],
                "buffer_radius_cells": r["buffer_radius_cells"],
                "streamline_count_support": 0,
                "supporting_streamlines": set(),
                "min_distance_from_streamline_cells": r["distance_from_streamline_point_cells"],
                "water_hm_score": r["water_hm_score"],
                "water_issue_type": r["water_issue_type"],
                "primary_driver": r["primary_driver"],
                "driver_family": r["driver_family"],
                "confidence": r["confidence"],
                "reason": r["reason"],
            }

        g = grouped[key]
        g["supporting_streamlines"].add(str(r["streamline_id"]))
        g["streamline_count_support"] = len(g["supporting_streamlines"])
        g["min_distance_from_streamline_cells"] = min(
            g["min_distance_from_streamline_cells"],
            r["distance_from_streamline_point_cells"],
        )

    output = []

    for g in grouped.values():
        g["supporting_streamlines"] = ";".join(sorted(g["supporting_streamlines"], key=lambda x: int(x)))
        output.append(g)

    return sorted(
        output,
        key=lambda x: (
            x["well"],
            -x["streamline_count_support"],
            x["i"],
            x["j"],
            -1 if x["k"] is None else x["k"],
        ),
    )


def build_corridors() -> Dict[str, Any]:
    diagnoses = load_final_diagnoses()
    cluster = load_cluster_snap()
    wells = load_well_connections_summary()

    snapshot_payload = cluster.get("snapshots", {}).get(SNAPSHOT, {})

    if not snapshot_payload:
        raise RuntimeError(f"Snapshot {SNAPSHOT} not found in cluster snap JSON.")

    source_file = Path(snapshot_payload["source_file"])

    if "reference_transform_from_init" in cluster:
        transform = transform_from_json(cluster["reference_transform_from_init"])
    else:
        transform = transform_from_json(snapshot_payload["global_transform"])

    assignment_rows = snapshot_payload.get("assignment_debug_rows", [])

    assignment_by_sid = {
        int(r["streamline_id"]): r
        for r in assignment_rows
        if r.get("assigned_producer")
    }

    sln = extract_polylines(source_file)

    raw_candidate_rows = []
    well_summaries = {}

    for item in sln["polylines"]:
        sid = int(item["streamline_id"])

        if sid not in assignment_by_sid:
            continue

        assignment = assignment_by_sid[sid]
        producer = assignment.get("assigned_producer")

        if producer not in diagnoses:
            continue

        diagnosis = diagnoses[producer]
        action = choose_corridor_action(diagnosis)

        if action is None:
            continue

        aligned = apply_bbox_transform(item["points"], transform)

        dx = to_float(assignment.get("dx_applied")) or 0.0
        dy = to_float(assignment.get("dy_applied")) or 0.0

        snapped = aligned.copy()
        snapped[:, 0] += dx
        snapped[:, 1] += dy

        well_info = wells.get(producer, {})
        completed_k_values = well_info.get("completed_k_values", [])

        rows = rasterize_corridor(
            well=producer,
            streamline_id=sid,
            snapped_points=snapped,
            completed_k_values=completed_k_values,
            action=action,
            diagnosis=diagnosis,
        )

        raw_candidate_rows.extend(rows)

        if producer not in well_summaries:
            well_summaries[producer] = {
                "well": producer,
                "representative_i": well_info.get("representative_i"),
                "representative_j": well_info.get("representative_j"),
                "completed_k_values": completed_k_values,
                "action_category": action["action_category"],
                "multiplier_direction": action["multiplier_direction"],
                "reason": action["reason"],
                "water_hm_score": diagnosis.get("water_hm_score"),
                "water_issue_type": diagnosis.get("water_issue_type"),
                "primary_driver": diagnosis.get("primary_driver"),
                "driver_family": diagnosis.get("driver_family"),
                "confidence": diagnosis.get("confidence"),
                "supporting_streamlines": set(),
            }

        well_summaries[producer]["supporting_streamlines"].add(str(sid))

    aggregated_cells = aggregate_candidate_cells(raw_candidate_rows)

    summary_rows = []

    for well, s in well_summaries.items():
        cell_count = sum(1 for r in aggregated_cells if r["well"] == well)

        item = dict(s)
        item["supporting_streamlines"] = ";".join(sorted(s["supporting_streamlines"], key=lambda x: int(x)))
        item["supporting_streamline_count"] = len(s["supporting_streamlines"])
        item["candidate_cell_count"] = cell_count
        item["completed_k_values"] = ";".join(str(k) for k in s["completed_k_values"])
        summary_rows.append(item)

    summary_rows = sorted(summary_rows, key=lambda x: x["well"])

    return {
        "method": {
            "description": (
                "Builds corridor-style candidate areas for transmissibility multiplier testing. "
                "Corridors are derived from validated cluster-snapped EOH streamlines assigned to diagnosed producers."
            ),
            "snapshot": SNAPSHOT,
            "corridor_mode": CORRIDOR_MODE,
            "producer_side_fraction": PRODUCER_SIDE_FRACTION,
            "corridor_buffer_cells": CORRIDOR_BUFFER_CELLS,
            "segment_sample_step_cells": SEGMENT_SAMPLE_STEP_CELLS,
            "k_mode": K_MODE,
            "important_note": (
                "These are candidate investigation cells for transmissibility multiplier testing, "
                "not automatic model edits."
            ),
        },
        "candidate_cells": aggregated_cells,
        "well_summaries": summary_rows,
    }


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert sets if any remain.
    clean_rows = []

    for r in rows:
        rr = {}

        for k, v in r.items():
            if isinstance(v, set):
                rr[k] = ";".join(sorted(v))
            elif isinstance(v, list):
                rr[k] = ";".join(str(x) for x in v)
            else:
                rr[k] = v

        clean_rows.append(rr)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(clean_rows[0].keys()))
        writer.writeheader()
        writer.writerows(clean_rows)

    print(f"[OK] Saved {path}")


def plot_all_corridors(payload: Dict[str, Any]) -> None:
    rows = payload["candidate_cells"]
    summaries = payload["well_summaries"]

    if not rows:
        print("No transmissibility corridor candidate cells to plot.")
        return

    plt.figure(figsize=(17, 13))

    used_labels = set()

    for action_category, style in ACTION_STYLE.items():
        sub = [r for r in rows if r["action_category"] == action_category]

        if not sub:
            continue

        x = [float(r["i"]) for r in sub]
        y = [float(r["j"]) for r in sub]

        label = style["label"]

        plt.scatter(
            x,
            y,
            s=15,
            c=style["color"],
            alpha=0.22,
            marker="s",
            label=label if label not in used_labels else None,
        )

        used_labels.add(label)

    for s in summaries:
        x = to_float(s.get("representative_i"))
        y = to_float(s.get("representative_j"))

        if x is None or y is None:
            continue

        style = ACTION_STYLE.get(s["action_category"], {"color": "gray"})

        plt.scatter(
            x,
            y,
            s=135,
            c=style["color"],
            edgecolor="black",
            linewidth=1.0,
            marker="o",
            zorder=5,
        )

        plt.text(
            x + 1.0,
            y + 1.0,
            f"{s['well']}\n{s['multiplier_direction']} TRAN",
            fontsize=8,
            color="black",
            zorder=6,
        )

    plt.title(
        "Candidate Transmissibility Multiplier Corridors\n"
        "Cells are derived from snapped EOH streamlines assigned to problematic producers"
    )

    plt.xlabel("Grid I")
    plt.ylabel("Grid J")
    plt.grid(True, alpha=0.25)
    plt.gca().invert_yaxis()
    plt.gca().set_aspect("equal", adjustable="box")
    plt.legend(loc="best", fontsize=8)
    plt.tight_layout()

    out = OUTPUT_DIR / "candidate_transmissibility_corridors_all.png"
    plt.savefig(out, dpi=220)
    plt.close()

    print(f"[OK] Saved {out}")


def plot_per_well_corridors(payload: Dict[str, Any]) -> None:
    rows = payload["candidate_cells"]
    summaries = payload["well_summaries"]

    for s in summaries:
        well = s["well"]
        sub = [r for r in rows if r["well"] == well]

        if not sub:
            continue

        style = ACTION_STYLE.get(s["action_category"], {"color": "gray", "label": s["action_category"]})

        x = [float(r["i"]) for r in sub]
        y = [float(r["j"]) for r in sub]
        support = [float(r["streamline_count_support"]) for r in sub]

        plt.figure(figsize=(12, 10))

        plt.scatter(
            x,
            y,
            s=[max(14, min(60, 10 + 8 * v)) for v in support],
            c=style["color"],
            alpha=0.30,
            marker="s",
            label=style["label"],
        )

        rep_i = to_float(s.get("representative_i"))
        rep_j = to_float(s.get("representative_j"))

        if rep_i is not None and rep_j is not None:
            plt.scatter(
                rep_i,
                rep_j,
                s=170,
                c=style["color"],
                edgecolor="black",
                linewidth=1.0,
                marker="o",
                zorder=5,
                label="Producer",
            )

            plt.text(rep_i + 0.8, rep_j + 0.8, well, fontsize=10, color="black", zorder=6)

        plt.title(
            f"{well} - Candidate Transmissibility Corridor\n"
            f"Direction: {s['multiplier_direction']} | Driver: {s['primary_driver']}\n"
            f"Supporting streamlines: {s['supporting_streamline_count']} | Candidate cells: {s['candidate_cell_count']}"
        )

        plt.xlabel("Grid I")
        plt.ylabel("Grid J")
        plt.grid(True, alpha=0.25)
        plt.gca().invert_yaxis()
        plt.gca().set_aspect("equal", adjustable="box")
        plt.legend(loc="best", fontsize=8)
        plt.tight_layout()

        safe = well.replace("/", "_").replace("\\", "_")
        out = OUTPUT_DIR / f"candidate_transmissibility_corridor_{safe}.png"
        plt.savefig(out, dpi=220)
        plt.close()

        print(f"[OK] Saved {out}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = build_corridors()

    json_path = OUTPUT_DIR / "candidate_transmissibility_corridors.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[OK] Saved {json_path}")

    write_csv(
        OUTPUT_DIR / "candidate_transmissibility_corridor_cells.csv",
        payload["candidate_cells"],
    )

    write_csv(
        OUTPUT_DIR / "candidate_transmissibility_corridor_summary.csv",
        payload["well_summaries"],
    )

    plot_all_corridors(payload)
    plot_per_well_corridors(payload)

    print("")
    print("Candidate transmissibility corridor mapping completed.")
    print(f"Wells with corridors: {len(payload['well_summaries'])}")
    print(f"Candidate cells: {len(payload['candidate_cells'])}")
    print(f"Output folder: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
