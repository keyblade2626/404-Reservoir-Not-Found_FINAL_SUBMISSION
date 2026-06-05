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
    aggregate_connections,
    build_changes,
    write_csv,
)


OUTPUT_DIR = Path("artifacts/streamlines/group_snap")
MAP_DIR = OUTPUT_DIR / "maps"

# Producer sulla stessa verticale se X/I è entro questa tolleranza.
COLUMN_X_TOLERANCE_CELLS = 10.0

# Dopo lo snap, accetto il producer solo se il last point resta entro questa distanza.
PRODUCER_RADIUS_CELLS = 10.0

# Accetto l'injector se la streamline passa entro questa distanza.
INJECTOR_RADIUS_CELLS = 10.0

# IMPORTANTE:
# False = il gruppo viene traslato esattamente al producer, anche se serve muoversi leggermente su.
# True  = permette solo shift verso il basso, cioè J aumenta.
# Lo metto False perché ora vogliamo far coincidere il gruppo col producer assegnato.
DOWNSHIFT_ONLY = False


def producer_points(wells: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {well: wp for well, wp in wells.items() if wp.get("is_producer")}


def build_producer_columns(producers: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Raggruppa i producer per verticale.
    J/Y più grande = più in basso nella mappa.
    """
    items = []

    for well, wp in producers.items():
        items.append({
            "well": well,
            "x": float(wp["x"]),
            "y": float(wp["y"]),
        })

    items = sorted(items, key=lambda r: r["x"])

    columns = []
    current = []

    def close_column(rows: List[Dict[str, Any]], col_id: int) -> Dict[str, Any]:
        xs = np.asarray([r["x"] for r in rows], dtype=float)

        return {
            "column_id": col_id,
            "x_center": float(np.median(xs)),
            "x_min": float(np.min(xs)),
            "x_max": float(np.max(xs)),
            "producer_count": len(rows),
            # bottom to top = J/Y decrescente
            "producers_bottom_to_top": sorted(rows, key=lambda r: r["y"], reverse=True),
        }

    for item in items:
        if not current:
            current.append(item)
            continue

        current_x = float(np.median(np.asarray([r["x"] for r in current], dtype=float)))

        if abs(item["x"] - current_x) <= COLUMN_X_TOLERANCE_CELLS:
            current.append(item)
        else:
            columns.append(close_column(current, len(columns)))
            current = [item]

    if current:
        columns.append(close_column(current, len(columns)))

    return columns


def nearest_column(x: float, columns: List[Dict[str, Any]]) -> Dict[str, Any]:
    best = None

    for col in columns:
        d = abs(x - float(col["x_center"]))
        item = {"column_id": col["column_id"], "distance": d}

        if best is None or d < best["distance"]:
            best = item

    return best


def split_rows_by_largest_y_gaps(rows: List[Dict[str, Any]], n_groups: int) -> List[Dict[str, Any]]:
    """
    Crea gruppi di last point nella stessa verticale.

    Esempio:
    - ordino dal basso verso l'alto: J grande -> J piccolo
    - cerco i gap verticali più grandi
    - divido in n gruppi
    """
    if not rows:
        return []

    rows_sorted = sorted(rows, key=lambda r: float(r["last_y_global"]), reverse=True)

    if n_groups <= 1 or len(rows_sorted) <= 1:
        ys = np.asarray([r["last_y_global"] for r in rows_sorted], dtype=float)
        xs = np.asarray([r["last_x_global"] for r in rows_sorted], dtype=float)

        return [{
            "group_rank_bottom_to_top": 0,
            "rows": rows_sorted,
            "median_last_x": float(np.median(xs)),
            "median_last_y": float(np.median(ys)),
            "count": len(rows_sorted),
        }]

    n_groups = min(n_groups, len(rows_sorted))

    # Gaps tra punti consecutivi ordinati bottom -> top.
    # Se y_i è più basso e y_next è più alto, gap = y_i - y_next.
    gaps = []

    for idx in range(len(rows_sorted) - 1):
        y_current = float(rows_sorted[idx]["last_y_global"])
        y_next = float(rows_sorted[idx + 1]["last_y_global"])
        gap = y_current - y_next
        gaps.append((gap, idx))

    # scelgo i n_groups-1 gap più grandi
    split_indices = sorted(idx for _, idx in sorted(gaps, reverse=True)[:n_groups - 1])

    groups = []
    start = 0

    for split_idx in split_indices:
        group_rows = rows_sorted[start:split_idx + 1]
        groups.append(group_rows)
        start = split_idx + 1

    groups.append(rows_sorted[start:])

    output = []

    for rank, group_rows in enumerate(groups):
        ys = np.asarray([r["last_y_global"] for r in group_rows], dtype=float)
        xs = np.asarray([r["last_x_global"] for r in group_rows], dtype=float)

        output.append({
            "group_rank_bottom_to_top": rank,
            "rows": group_rows,
            "median_last_x": float(np.median(xs)),
            "median_last_y": float(np.median(ys)),
            "count": len(group_rows),
        })

    # Assicura ancora bottom -> top.
    output = sorted(output, key=lambda g: g["median_last_y"], reverse=True)

    for rank, g in enumerate(output):
        g["group_rank_bottom_to_top"] = rank

    return output


def build_group_assignments(
    prepared_rows: List[Dict[str, Any]],
    columns: List[Dict[str, Any]],
    wells: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[int, Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Cuore dell'algoritmo:
    per ogni verticale:
      gruppo streamline più basso -> producer più basso
      gruppo successivo -> producer successivo
    """
    rows_by_column: Dict[int, List[Dict[str, Any]]] = {}

    for row in prepared_rows:
        rows_by_column.setdefault(row["column_id"], [])
        rows_by_column[row["column_id"]].append(row)

    assignments: Dict[int, Dict[str, Any]] = {}
    group_debug_rows = []

    for col in columns:
        column_id = int(col["column_id"])
        col_rows = rows_by_column.get(column_id, [])

        if not col_rows:
            continue

        producers_bottom_to_top = col["producers_bottom_to_top"]
        n_producers = len(producers_bottom_to_top)

        groups = split_rows_by_largest_y_gaps(col_rows, n_producers)

        for rank, group in enumerate(groups):
            if rank >= len(producers_bottom_to_top):
                producer = producers_bottom_to_top[-1]
            else:
                producer = producers_bottom_to_top[rank]

            producer_name = producer["well"]
            producer_y = float(producer["y"])

            dy = producer_y - float(group["median_last_y"])

            if DOWNSHIFT_ONLY and dy < 0:
                dy = 0.0

            group_debug_rows.append({
                "column_id": column_id,
                "column_x_center": col["x_center"],
                "group_rank_bottom_to_top": rank,
                "assigned_producer": producer_name,
                "producer_x": producer["x"],
                "producer_y": producer["y"],
                "group_median_last_x": group["median_last_x"],
                "group_median_last_y": group["median_last_y"],
                "streamline_count_in_group": group["count"],
                "vertical_shift_applied": dy,
            })

            for r in group["rows"]:
                sid = int(r["streamline_id"])
                assignments[sid] = {
                    "streamline_id": sid,
                    "column_id": column_id,
                    "group_rank_bottom_to_top": rank,
                    "assigned_producer": producer_name,
                    "assigned_producer_x": float(producer["x"]),
                    "assigned_producer_y": float(producer["y"]),
                    "vertical_shift_applied": dy,
                    "last_x_global": float(r["last_x_global"]),
                    "last_y_global": float(r["last_y_global"]),
                    "group_median_last_y": float(group["median_last_y"]),
                }

    return assignments, group_debug_rows


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
        raise RuntimeError("No producers found.")

    columns = build_producer_columns(producers)
    best_transform = choose_best_transform(sln["endpoint_points"], wells)

    # Step 1: allineamento globale + last point.
    prepared_rows = []

    for item in sln["polylines"]:
        sid = int(item["streamline_id"])
        global_aligned = apply_bbox_transform(item["points"], best_transform)
        last_point = global_aligned[-1]

        col = nearest_column(float(last_point[0]), columns)

        prepared_rows.append({
            "streamline_id": sid,
            "global_aligned": global_aligned,
            "last_x_global": float(last_point[0]),
            "last_y_global": float(last_point[1]),
            "column_id": int(col["column_id"]),
            "distance_to_column": float(col["distance"]),
        })

    # Step 2: gruppi di last point -> producer per ordine J.
    assignments, group_debug_rows = build_group_assignments(prepared_rows, columns, wells)

    raw_rows = []
    assignment_debug_rows = []

    for item in sln["polylines"]:
        sid = int(item["streamline_id"])

        if sid not in assignments:
            continue

        assignment = assignments[sid]
        global_aligned = apply_bbox_transform(item["points"], best_transform)
        dy = float(assignment["vertical_shift_applied"])
        snapped = apply_vertical_shift(global_aligned, dy)

        producer = assignment["assigned_producer"]
        producer_x = float(wells[producer]["x"])
        producer_y = float(wells[producer]["y"])

        producer_distance = math.sqrt(
            (snapped[-1, 0] - producer_x) ** 2 +
            (snapped[-1, 1] - producer_y) ** 2
        )

        # IMPORTANT:
        # Producer snapping must be saved regardless of injector matching.
        # Otherwise, if no injector is found nearby, the plot/debug wrongly looks like
        # no producer was matched either.
        nearest_injector = nearest_role_well(snapped, wells, "is_injector")

        if nearest_injector is None:
            nearest_injector_name = ""
            injector_distance = None
        else:
            nearest_injector_name = nearest_injector["well"]
            injector_distance = float(nearest_injector["distance"])

        assignment_debug_rows.append({
            "snapshot": snapshot,
            "streamline_id": sid,
            "column_id": assignment["column_id"],
            "group_rank_bottom_to_top": assignment["group_rank_bottom_to_top"],
            "assigned_producer": producer,
            "producer_distance_after_snap": producer_distance,
            "producer_match_accepted": producer_distance <= PRODUCER_RADIUS_CELLS,
            "nearest_injector": nearest_injector_name,
            "injector_distance": injector_distance,
            "injector_match_accepted": (
                injector_distance is not None and injector_distance <= INJECTOR_RADIUS_CELLS
            ),
            "vertical_shift_applied": dy,
            "last_x_before_snap": assignment["last_x_global"],
            "last_y_before_snap": assignment["last_y_global"],
            "last_x_after_snap": float(snapped[-1, 0]),
            "last_y_after_snap": float(snapped[-1, 1]),
        })

        # From here onward we are creating injector-producer connections.
        # These filters must NOT affect producer snapping/debug.
        if producer_distance > PRODUCER_RADIUS_CELLS:
            continue

        if nearest_injector is None:
            continue

        if injector_distance is None or injector_distance > INJECTOR_RADIUS_CELLS:
            continue

        if nearest_injector["well"] == producer:
            continue

        raw_rows.append({
            "snapshot": snapshot,
            "streamline_id": sid,
            "injector": nearest_injector["well"],
            "producer": producer,
            "injector_distance": injector_distance,
            "producer_distance": producer_distance,
            "vertical_shift_applied": dy,
            "column_id": assignment["column_id"],
            "group_rank_bottom_to_top": assignment["group_rank_bottom_to_top"],
            "direction_inference": "last_point_group_ranked_by_J_then_vertical_snap",
        })

    connections = aggregate_connections(raw_rows, snapshot)

    return {
        "snapshot": snapshot,
        "source_file": str(path),
        "available": bool(connections),
        "method": "last_point_group_ranked_by_J_then_vertical_snap",
        "downshift_only": DOWNSHIFT_ONLY,
        "column_x_tolerance_cells": COLUMN_X_TOLERANCE_CELLS,
        "producer_radius_cells": PRODUCER_RADIUS_CELLS,
        "injector_radius_cells": INJECTOR_RADIUS_CELLS,
        "n_streamlines": sln["n_streamlines"],
        "n_polylines": sln["n_polylines"],
        "producer_columns": columns,
        "raw_connection_count": len(raw_rows),
        "aggregated_connection_count": len(connections),
        "global_transform": transform_to_json(best_transform),
        "group_debug_rows": group_debug_rows,
        "assignment_debug_rows": assignment_debug_rows,
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

    assignment_map = {
        int(r["streamline_id"]): r
        for r in snapshot_result.get("assignment_debug_rows", [])
    }

    plt.figure(figsize=(15, 11))

    for item in sln["polylines"]:
        sid = int(item["streamline_id"])
        global_aligned = apply_bbox_transform(item["points"], transform)

        if sid in assignment_map:
            dy = float(assignment_map[sid]["vertical_shift_applied"])
            snapped = apply_vertical_shift(global_aligned, dy)
            color = "cornflowerblue"
            alpha = 0.65
            linewidth = 0.75
        else:
            snapped = global_aligned
            color = "lightgray"
            alpha = 0.25
            linewidth = 0.50

        plt.plot(snapped[:, 0], snapped[:, 1], linewidth=linewidth, alpha=alpha, color=color)
        plt.scatter(snapped[0, 0], snapped[0, 1], s=9, color="green", alpha=0.70)
        plt.scatter(snapped[-1, 0], snapped[-1, 1], s=13, color="orange", alpha=0.90)

    # Vertical columns
    for col in snapshot_result.get("producer_columns", []):
        plt.axvline(float(col["x_center"]), color="gray", linestyle="--", linewidth=0.6, alpha=0.35)

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
    plt.plot([], [], color="cornflowerblue", label="assigned/snapped streamline")
    plt.plot([], [], color="lightgray", label="unassigned streamline")

    title = (
        f"Last-point group snap by J rank - {snapshot_result['snapshot'].upper()}\n"
        f"connections={snapshot_result['aggregated_connection_count']} | "
        f"flip_y={t['flip_y']} | swap_xy={t['swap_xy']} | flip_x={t['flip_x']} | "
        f"DOWNSHIFT_ONLY={DOWNSHIFT_ONLY} | COLUMN_X_TOL={COLUMN_X_TOLERANCE_CELLS}"
    )

    plt.title(title)
    plt.xlabel("Grid I / aligned X")
    plt.ylabel("Grid J / aligned Y")
    plt.grid(True, alpha=0.25)
    plt.gca().invert_yaxis()
    plt.gca().set_aspect("equal", adjustable="box")
    plt.legend(loc="best", fontsize=8)
    plt.tight_layout()

    out = MAP_DIR / f"group_snap_streamlines_{snapshot_result['snapshot']}.png"
    plt.savefig(out, dpi=220)
    plt.close()

    print(f"[OK] Saved {out}")


def write_debug_csvs(snapshot_result: Dict[str, Any]) -> None:
    snapshot = snapshot_result["snapshot"]

    write_csv(
        OUTPUT_DIR / f"group_snap_group_debug_{snapshot}.csv",
        snapshot_result.get("group_debug_rows", []),
    )

    write_csv(
        OUTPUT_DIR / f"group_snap_assignment_debug_{snapshot}.csv",
        snapshot_result.get("assignment_debug_rows", []),
    )

    write_csv(
        OUTPUT_DIR / f"group_snap_connections_{snapshot}.csv",
        snapshot_result.get("connections", []),
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MAP_DIR.mkdir(parents=True, exist_ok=True)

    wells = load_well_points()

    print(f"Wells loaded: {len(wells)}")
    print(f"Producers: {sum(1 for w in wells.values() if w['is_producer'])}")
    print(f"Injectors: {sum(1 for w in wells.values() if w['is_injector'])}")
    print(f"COLUMN_X_TOLERANCE_CELLS: {COLUMN_X_TOLERANCE_CELLS}")
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
                f"  endpoint distances before snap: median={tr['median_endpoint_distance']:.2f}, "
                f"p75={tr['p75_endpoint_distance']:.2f}, p90={tr['p90_endpoint_distance']:.2f}"
            )

        plot_snapshot(result, wells)
        write_debug_csvs(result)

    changes = build_changes(
        connections_by_snapshot.get("init", []),
        connections_by_snapshot.get("eoh", []),
    )

    payload = {
        "available": bool(connections_by_snapshot.get("init") or connections_by_snapshot.get("eoh")),
        "method": "last_point_group_ranked_by_J_then_vertical_snap",
        "column_x_tolerance_cells": COLUMN_X_TOLERANCE_CELLS,
        "producer_radius_cells": PRODUCER_RADIUS_CELLS,
        "injector_radius_cells": INJECTOR_RADIUS_CELLS,
        "downshift_only": DOWNSHIFT_ONLY,
        "snapshots": results,
        "connections_by_snapshot": connections_by_snapshot,
        "connection_changes": changes,
        "notes": [
            "This mapper does not use nearest producer as final assignment.",
            "It first groups streamline last points by vertical column.",
            "Within each vertical, last-point groups are sorted by J from bottom to top.",
            "Producer wells in the same vertical are also sorted by J from bottom to top.",
            "Group rank is matched to producer rank, then the whole group is vertically snapped to that producer.",
        ],
    }

    out_json = OUTPUT_DIR / "group_snap_streamline_connections.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[OK] Saved {out_json}")

    write_csv(OUTPUT_DIR / "group_snap_connection_changes.csv", changes)

    print("")
    print(f"Available: {payload['available']}")
    print(f"Maps saved in: {MAP_DIR}")


if __name__ == "__main__":
    main()
