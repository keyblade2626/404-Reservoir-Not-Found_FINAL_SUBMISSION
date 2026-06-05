import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from app.streamlines_reader import MODEL_DIR, find_streamline_file
from app.streamline_near_well_mapper import (
    extract_polylines,
    load_well_points,
    choose_best_transform,
    apply_bbox_transform,
    nearest_role_well,
    distance_polyline_to_well,
    aggregate_connections,
    build_changes,
    write_csv,
)


OUTPUT_DIR = Path("artifacts/streamlines/near_well_snapped")
MAP_DIR = OUTPUT_DIR / "maps"

PRODUCER_RADIUS_CELLS = 8.0
INJECTOR_RADIUS_CELLS = 8.0

# Se True, la correzione verticale può solo aumentare J, cioè andare "verso il basso".
DOWNSHIFT_ONLY = True

# Se "group_median", tutte le streamlines associate allo stesso producer ricevono la stessa traslazione.
# Se "per_streamline", ogni streamline viene spostata verticalmente per far coincidere il proprio last point col producer.
SNAP_MODE = "group_median"  # "group_median" oppure "per_streamline"


def to_float(value: Any) -> Optional[float]:
    if value in [None, "", "None", "null", "N/A"]:
        return None
    try:
        return float(value)
    except Exception:
        return None


def producer_points(wells: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {
        well: wp
        for well, wp in wells.items()
        if wp.get("is_producer")
    }


def nearest_producer_to_point(point: np.ndarray, producers: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    best = None

    for well, wp in producers.items():
        d = math.sqrt((point[0] - wp["x"]) ** 2 + (point[1] - wp["y"]) ** 2)

        item = {
            "well": well,
            "distance": d,
            "producer_x": wp["x"],
            "producer_y": wp["y"],
        }

        if best is None or d < best["distance"]:
            best = item

    return best


def build_group_vertical_shifts(prepared_rows: List[Dict[str, Any]], wells: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    """
    For each producer group:
    dy = producer_y - median(last_y_of_streamlines_assigned_to_producer)

    If DOWNSHIFT_ONLY=True, negative dy is set to zero.
    """
    grouped: Dict[str, List[float]] = {}

    for row in prepared_rows:
        producer = row["assigned_producer"]
        grouped.setdefault(producer, [])
        grouped[producer].append(float(row["last_y_global"]))

    shifts: Dict[str, float] = {}

    for producer, last_ys in grouped.items():
        producer_y = float(wells[producer]["y"])
        median_last_y = float(np.median(np.asarray(last_ys, dtype=float)))
        dy = producer_y - median_last_y

        if DOWNSHIFT_ONLY and dy < 0:
            dy = 0.0

        shifts[producer] = dy

    return shifts


def apply_vertical_shift(points: np.ndarray, dy: float) -> np.ndarray:
    shifted = points.copy()
    shifted[:, 1] = shifted[:, 1] + dy
    return shifted


def build_snapshot(snapshot: str, wells: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    path = find_streamline_file(snapshot, model_dir=MODEL_DIR)

    if path is None:
        return {
            "snapshot": snapshot,
            "available": False,
            "warning": "missing_streamline_file",
            "connections": [],
            "raw_rows": [],
        }

    sln = extract_polylines(path)

    producers = producer_points(wells)
    if not producers:
        raise RuntimeError("No producer wells available for snapping.")

    best_transform = choose_best_transform(sln["endpoint_points"], wells)

    # Step 1: global transform + assign each streamline to nearest producer using last point.
    prepared_rows = []

    for item in sln["polylines"]:
        sid = item["streamline_id"]
        raw_pts = item["points"]

        global_aligned = apply_bbox_transform(raw_pts, best_transform)
        last_point = global_aligned[-1]

        nearest_prod = nearest_producer_to_point(last_point, producers)

        prepared_rows.append(
            {
                "streamline_id": sid,
                "raw_points": raw_pts,
                "global_aligned": global_aligned,
                "assigned_producer": nearest_prod["well"],
                "producer_assignment_distance_before_snap": nearest_prod["distance"],
                "last_x_global": float(last_point[0]),
                "last_y_global": float(last_point[1]),
            }
        )

    # Step 2: compute vertical shifts by producer group.
    group_shifts = build_group_vertical_shifts(prepared_rows, wells)

    raw_rows = []

    for row in prepared_rows:
        sid = row["streamline_id"]
        producer = row["assigned_producer"]
        global_aligned = row["global_aligned"]

        if SNAP_MODE == "per_streamline":
            producer_y = float(wells[producer]["y"])
            dy = producer_y - float(global_aligned[-1, 1])
            if DOWNSHIFT_ONLY and dy < 0:
                dy = 0.0
        else:
            dy = group_shifts.get(producer, 0.0)

        snapped = apply_vertical_shift(global_aligned, dy)

        producer_payload = wells[producer]
        producer_xy = np.asarray([producer_payload["x"], producer_payload["y"]], dtype=float)

        producer_distance_after = math.sqrt(
            (snapped[-1, 0] - producer_xy[0]) ** 2 + (snapped[-1, 1] - producer_xy[1]) ** 2
        )

        # Cerca injector più vicino all'intera streamline dopo snapping.
        nearest_injector = nearest_role_well(snapped, wells, "is_injector")

        if nearest_injector is None:
            continue

        injector_distance = nearest_injector["distance"]

        if producer_distance_after > PRODUCER_RADIUS_CELLS:
            continue

        if injector_distance > INJECTOR_RADIUS_CELLS:
            continue

        if nearest_injector["well"] == producer:
            continue

        raw_rows.append(
            {
                "snapshot": snapshot,
                "streamline_id": sid,
                "injector": nearest_injector["well"],
                "producer": producer,
                "injector_distance": injector_distance,
                "producer_distance": producer_distance_after,
                "producer_assignment_distance_before_snap": row["producer_assignment_distance_before_snap"],
                "vertical_shift_applied": dy,
                "snap_mode": SNAP_MODE,
                "direction_inference": "last_point_snapped_to_assigned_producer",
            }
        )

    connections = aggregate_connections(raw_rows, snapshot)

    return {
        "snapshot": snapshot,
        "source_file": str(path),
        "available": bool(connections),
        "method": "near_well_y_mirror_then_producer_group_vertical_snap",
        "snap_mode": SNAP_MODE,
        "downshift_only": DOWNSHIFT_ONLY,
        "producer_radius_cells": PRODUCER_RADIUS_CELLS,
        "injector_radius_cells": INJECTOR_RADIUS_CELLS,
        "n_streamlines": sln["n_streamlines"],
        "n_polylines": sln["n_polylines"],
        "raw_connection_count": len(raw_rows),
        "aggregated_connection_count": len(connections),
        "global_transform": transform_to_json(best_transform),
        "producer_vertical_shifts": group_shifts,
        "raw_rows": raw_rows,
        "connections": connections,
    }


def transform_to_json(transform: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "swap_xy": transform["swap_xy"],
        "flip_x": transform["flip_x"],
        "flip_y": transform["flip_y"],
        "src_min": transform["src_min"].tolist(),
        "scale": transform["scale"].tolist(),
        "tgt_min": transform["tgt_min"].tolist(),
        "median_endpoint_distance": transform["median_endpoint_distance"],
        "p75_endpoint_distance": transform["p75_endpoint_distance"],
        "p90_endpoint_distance": transform["p90_endpoint_distance"],
        "mean_endpoint_distance": transform["mean_endpoint_distance"],
        "within_8_cells_fraction": transform["within_8_cells_fraction"],
        "within_12_cells_fraction": transform["within_12_cells_fraction"],
        "all_candidates_summary": transform["all_candidates_summary"],
    }


def plot_snapshot(snapshot_result: Dict[str, Any], wells: Dict[str, Dict[str, Any]]) -> None:
    MAP_DIR.mkdir(parents=True, exist_ok=True)

    if not snapshot_result.get("source_file"):
        return

    path = Path(snapshot_result["source_file"])
    sln = extract_polylines(path)

    t = snapshot_result["global_transform"]

    transform = {
        "swap_xy": t["swap_xy"],
        "flip_x": t["flip_x"],
        "flip_y": t["flip_y"],
        "src_min": np.asarray(t["src_min"], dtype=float),
        "scale": np.asarray(t["scale"], dtype=float),
        "tgt_min": np.asarray(t["tgt_min"], dtype=float),
    }

    producers = producer_points(wells)
    group_shifts = snapshot_result.get("producer_vertical_shifts", {})

    plt.figure(figsize=(15, 11))

    # Plot snapped streamlines.
    for item in sln["polylines"]:
        global_aligned = apply_bbox_transform(item["points"], transform)
        nearest_prod = nearest_producer_to_point(global_aligned[-1], producers)
        producer = nearest_prod["well"]

        if SNAP_MODE == "per_streamline":
            producer_y = float(wells[producer]["y"])
            dy = producer_y - float(global_aligned[-1, 1])
            if DOWNSHIFT_ONLY and dy < 0:
                dy = 0.0
        else:
            dy = group_shifts.get(producer, 0.0)

        snapped = apply_vertical_shift(global_aligned, dy)

        plt.plot(
            snapped[:, 0],
            snapped[:, 1],
            linewidth=0.65,
            alpha=0.55,
            color="cornflowerblue",
        )

        plt.scatter(snapped[0, 0], snapped[0, 1], s=10, color="green", alpha=0.75)
        plt.scatter(snapped[-1, 0], snapped[-1, 1], s=12, color="orange", alpha=0.85)

    # Plot wells.
    used_labels = set()

    for well, wp in wells.items():
        if wp["is_injector"] and wp["is_producer"]:
            marker = "s"
            color = "purple"
            label = "mixed"
            size = 95
        elif wp["is_injector"]:
            marker = "^"
            color = "red"
            label = "injector"
            size = 105
        elif wp["is_producer"]:
            marker = "o"
            color = "black"
            label = "producer"
            size = 75
        else:
            marker = "x"
            color = "gray"
            label = "unknown"
            size = 75

        legend_label = label if label not in used_labels else None
        used_labels.add(label)

        plt.scatter(
            wp["x"],
            wp["y"],
            s=size,
            marker=marker,
            color=color,
            edgecolor="white",
            linewidth=0.8,
            zorder=5,
            label=legend_label,
        )

        plt.text(wp["x"] + 0.8, wp["y"] + 0.8, well, fontsize=8, color=color, zorder=6)

    plt.scatter([], [], s=20, color="green", label="streamline first point")
    plt.scatter([], [], s=20, color="orange", label="streamline last point snapped")

    title = (
        f"Streamlines mirrored/aligned + vertical producer snap - {snapshot_result['snapshot'].upper()}\n"
        f"flip_y={t['flip_y']} | swap_xy={t['swap_xy']} | flip_x={t['flip_x']} | "
        f"snap_mode={SNAP_MODE} | downshift_only={DOWNSHIFT_ONLY} | "
        f"connections={snapshot_result['aggregated_connection_count']}"
    )

    plt.title(title)
    plt.xlabel("Grid I / aligned X")
    plt.ylabel("Grid J / aligned Y")
    plt.grid(True, alpha=0.25)
    plt.gca().invert_yaxis()
    plt.gca().set_aspect("equal", adjustable="box")
    plt.legend(loc="best", fontsize=8)
    plt.tight_layout()

    out = MAP_DIR / f"snapped_streamlines_{snapshot_result['snapshot']}.png"
    plt.savefig(out, dpi=220)
    plt.close()

    print(f"[OK] Saved {out}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MAP_DIR.mkdir(parents=True, exist_ok=True)

    wells = load_well_points()

    print(f"Wells loaded: {len(wells)}")
    print(f"Producers: {sum(1 for w in wells.values() if w['is_producer'])}")
    print(f"Injectors: {sum(1 for w in wells.values() if w['is_injector'])}")
    print(f"SNAP_MODE: {SNAP_MODE}")
    print(f"DOWNSHIFT_ONLY: {DOWNSHIFT_ONLY}")

    results = {}
    connections_by_snapshot = {}

    for snapshot in ["init", "eoh"]:
        print("")
        print(f"Processing {snapshot}...")
        result = build_snapshot(snapshot, wells)

        results[snapshot] = result
        connections_by_snapshot[snapshot] = result.get("connections", [])

        print(f"  source: {result.get('source_file')}")
        print(f"  method: {result.get('method')}")
        print(f"  raw connection rows: {result.get('raw_connection_count')}")
        print(f"  aggregated connections: {result.get('aggregated_connection_count')}")

        if result.get("global_transform"):
            tr = result["global_transform"]
            print(
                f"  global transform: swap_xy={tr['swap_xy']} flip_x={tr['flip_x']} flip_y={tr['flip_y']}"
            )
            print(
                f"  global endpoint distances before snap: median={tr['median_endpoint_distance']:.2f}, "
                f"p75={tr['p75_endpoint_distance']:.2f}, p90={tr['p90_endpoint_distance']:.2f}"
            )

        plot_snapshot(result, wells)
        write_csv(OUTPUT_DIR / f"snapped_connections_{snapshot}.csv", result.get("connections", []))

    changes = build_changes(
        connections_by_snapshot.get("init", []),
        connections_by_snapshot.get("eoh", []),
    )

    payload = {
        "available": bool(connections_by_snapshot.get("init") or connections_by_snapshot.get("eoh")),
        "method": "near_well_y_mirror_then_producer_group_vertical_snap",
        "snap_mode": SNAP_MODE,
        "downshift_only": DOWNSHIFT_ONLY,
        "producer_radius_cells": PRODUCER_RADIUS_CELLS,
        "injector_radius_cells": INJECTOR_RADIUS_CELLS,
        "snapshots": results,
        "connections_by_snapshot": connections_by_snapshot,
        "connection_changes": changes,
        "notes": [
            "Global transform first handles mirror/scale/swap.",
            "Then each streamline group is shifted vertically toward its assigned producer.",
            "Downward means increasing grid J coordinate.",
            "Use snapped_streamlines_eoh.png to visually validate before trusting connections.",
        ],
    }

    out_json = OUTPUT_DIR / "snapped_streamline_connections.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[OK] Saved {out_json}")

    write_csv(OUTPUT_DIR / "snapped_connection_changes.csv", changes)

    print("")
    print(f"Available: {payload['available']}")
    print(f"Maps saved in: {MAP_DIR}")


if __name__ == "__main__":
    main()
