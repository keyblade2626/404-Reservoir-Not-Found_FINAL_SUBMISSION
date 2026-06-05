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


OUTPUT_DIR = Path("artifacts/streamlines/cluster_snap")
MAP_DIR = OUTPUT_DIR / "maps"

# Raggio per raggruppare last point delle streamlines.
LASTPOINT_CLUSTER_RADIUS_CELLS = 12.0

# Distanza massima cluster-producer per accettare uno snap.
MAX_CLUSTER_PRODUCER_DISTANCE_CELLS = 45.0

# Dopo lo snap, distanza massima tra last point e producer.
PRODUCER_RADIUS_CELLS = 10.0

# Distanza massima tra streamline snappata e injector.
INJECTOR_RADIUS_CELLS = 10.0

# "XY" = trasla il gruppo in X e Y fino al producer.
# "Y_ONLY" = trasla solo verticalmente.
SNAP_MODE = "XY"


def producer_points(wells: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {well: wp for well, wp in wells.items() if wp.get("is_producer")}


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


def get_reference_transform_from_init(wells: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Fit transform only on INIT.
    EOH must use the same transform because the coordinate system is the same.
    """
    init_path = find_streamline_file("init", model_dir=MODEL_DIR)

    if init_path is None:
        raise FileNotFoundError("Missing INIT streamline file.")

    init_sln = extract_polylines(init_path)
    return choose_best_transform(init_sln["endpoint_points"], wells)


def point_distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def cluster_last_points(rows: List[Dict[str, Any]], radius: float) -> List[Dict[str, Any]]:
    """
    Connected-component clustering on last points.
    This does not assume vertical alignment.
    """
    n = len(rows)

    if n == 0:
        return []

    visited = [False] * n
    clusters = []

    for i in range(n):
        if visited[i]:
            continue

        queue = [i]
        visited[i] = True
        members_idx = []

        while queue:
            idx = queue.pop()
            members_idx.append(idx)

            p = (float(rows[idx]["last_x_global"]), float(rows[idx]["last_y_global"]))

            for j in range(n):
                if visited[j]:
                    continue

                q = (float(rows[j]["last_x_global"]), float(rows[j]["last_y_global"]))

                if point_distance(p, q) <= radius:
                    visited[j] = True
                    queue.append(j)

        members = [rows[idx] for idx in members_idx]
        xs = np.asarray([m["last_x_global"] for m in members], dtype=float)
        ys = np.asarray([m["last_y_global"] for m in members], dtype=float)

        clusters.append({
            "cluster_id": len(clusters),
            "members": members,
            "count": len(members),
            "median_last_x": float(np.median(xs)),
            "median_last_y": float(np.median(ys)),
            "mean_last_x": float(np.mean(xs)),
            "mean_last_y": float(np.mean(ys)),
        })

    # Larger clusters first, then lower clusters first.
    clusters = sorted(clusters, key=lambda c: (-c["count"], -c["median_last_y"]))

    for idx, c in enumerate(clusters):
        c["cluster_id"] = idx

    return clusters


def assign_clusters_to_producers(
    clusters: List[Dict[str, Any]],
    producers: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[int, Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Assign clusters to producers by 2D distance.
    First pass is one-to-one greedy.
    Remaining clusters are assigned to nearest producer if within max distance.
    """
    producer_names = list(producers.keys())

    pairs = []

    for c in clusters:
        cx = float(c["median_last_x"])
        cy = float(c["median_last_y"])

        for producer in producer_names:
            px = float(producers[producer]["x"])
            py = float(producers[producer]["y"])
            d = point_distance((cx, cy), (px, py))

            pairs.append({
                "cluster_id": c["cluster_id"],
                "producer": producer,
                "distance": d,
                "dx": px - cx,
                "dy": py - cy,
            })

    pairs = sorted(pairs, key=lambda r: r["distance"])

    assigned_clusters = set()
    assigned_producers = set()
    assignments: Dict[int, Dict[str, Any]] = {}

    # First pass: one cluster -> one producer.
    for p in pairs:
        cid = p["cluster_id"]
        prod = p["producer"]

        if cid in assigned_clusters:
            continue

        if prod in assigned_producers:
            continue

        if p["distance"] > MAX_CLUSTER_PRODUCER_DISTANCE_CELLS:
            continue

        assignments[cid] = p
        assigned_clusters.add(cid)
        assigned_producers.add(prod)

    # Second pass: leftover clusters can attach to nearest producer.
    for c in clusters:
        cid = c["cluster_id"]

        if cid in assignments:
            continue

        candidates = [p for p in pairs if p["cluster_id"] == cid]

        if not candidates:
            continue

        best = candidates[0]

        if best["distance"] <= MAX_CLUSTER_PRODUCER_DISTANCE_CELLS:
            assignments[cid] = best

    debug_rows = []

    for c in clusters:
        cid = c["cluster_id"]
        a = assignments.get(cid)

        if a is None:
            debug_rows.append({
                "cluster_id": cid,
                "assigned": False,
                "assigned_producer": "",
                "cluster_count": c["count"],
                "cluster_median_last_x": c["median_last_x"],
                "cluster_median_last_y": c["median_last_y"],
                "cluster_producer_distance": "",
                "dx": "",
                "dy": "",
            })
        else:
            debug_rows.append({
                "cluster_id": cid,
                "assigned": True,
                "assigned_producer": a["producer"],
                "cluster_count": c["count"],
                "cluster_median_last_x": c["median_last_x"],
                "cluster_median_last_y": c["median_last_y"],
                "cluster_producer_distance": a["distance"],
                "dx": a["dx"],
                "dy": a["dy"],
            })

    return assignments, debug_rows


def apply_snap(points: np.ndarray, dx: float, dy: float) -> np.ndarray:
    shifted = points.copy()

    if SNAP_MODE.upper() == "Y_ONLY":
        shifted[:, 1] += dy
    else:
        shifted[:, 0] += dx
        shifted[:, 1] += dy

    return shifted


def build_snapshot(
    snapshot: str,
    wells: Dict[str, Dict[str, Any]],
    reference_transform: Dict[str, Any],
) -> Dict[str, Any]:

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

    prepared_rows = []

    for item in sln["polylines"]:
        sid = int(item["streamline_id"])
        aligned = apply_bbox_transform(item["points"], reference_transform)
        last = aligned[-1]

        prepared_rows.append({
            "streamline_id": sid,
            "aligned": aligned,
            "last_x_global": float(last[0]),
            "last_y_global": float(last[1]),
        })

    clusters = cluster_last_points(prepared_rows, LASTPOINT_CLUSTER_RADIUS_CELLS)
    cluster_assignments, cluster_debug_rows = assign_clusters_to_producers(clusters, producers)

    # Map streamline_id -> cluster assignment.
    sid_assignment = {}

    for c in clusters:
        cid = c["cluster_id"]
        assignment = cluster_assignments.get(cid)

        if assignment is None:
            continue

        for member in c["members"]:
            sid_assignment[int(member["streamline_id"])] = {
                "cluster_id": cid,
                "producer": assignment["producer"],
                "dx": float(assignment["dx"]),
                "dy": float(assignment["dy"]),
                "cluster_producer_distance": float(assignment["distance"]),
            }

    raw_rows = []
    assignment_debug_rows = []

    for item in sln["polylines"]:
        sid = int(item["streamline_id"])

        if sid not in sid_assignment:
            continue

        a = sid_assignment[sid]

        aligned = apply_bbox_transform(item["points"], reference_transform)
        snapped = apply_snap(aligned, a["dx"], a["dy"])

        producer = a["producer"]
        px = float(wells[producer]["x"])
        py = float(wells[producer]["y"])

        producer_distance = point_distance(
            (float(snapped[-1, 0]), float(snapped[-1, 1])),
            (px, py),
        )

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
            "cluster_id": a["cluster_id"],
            "assigned_producer": producer,
            "cluster_producer_distance_before_snap": a["cluster_producer_distance"],
            "producer_distance_after_snap": producer_distance,
            "producer_match_accepted": producer_distance <= PRODUCER_RADIUS_CELLS,
            "nearest_injector": nearest_injector_name,
            "injector_distance": injector_distance,
            "injector_match_accepted": (
                injector_distance is not None and injector_distance <= INJECTOR_RADIUS_CELLS
            ),
            "dx_applied": a["dx"] if SNAP_MODE.upper() == "XY" else 0.0,
            "dy_applied": a["dy"],
            "snap_mode": SNAP_MODE,
            "last_x_after_snap": float(snapped[-1, 0]),
            "last_y_after_snap": float(snapped[-1, 1]),
        })

        # Producer debug is saved above.
        # Below we create injector-producer connection only if injector also matches.
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
            "cluster_id": a["cluster_id"],
            "dx_applied": a["dx"] if SNAP_MODE.upper() == "XY" else 0.0,
            "dy_applied": a["dy"],
            "direction_inference": "last_point_cluster_2d_snap_to_producer",
        })

    connections = aggregate_connections(raw_rows, snapshot)

    return {
        "snapshot": snapshot,
        "source_file": str(path),
        "available": bool(connections),
        "method": "last_point_cluster_2d_snap_to_producer",
        "snap_mode": SNAP_MODE,
        "lastpoint_cluster_radius_cells": LASTPOINT_CLUSTER_RADIUS_CELLS,
        "max_cluster_producer_distance_cells": MAX_CLUSTER_PRODUCER_DISTANCE_CELLS,
        "producer_radius_cells": PRODUCER_RADIUS_CELLS,
        "injector_radius_cells": INJECTOR_RADIUS_CELLS,
        "n_streamlines": sln["n_streamlines"],
        "n_polylines": sln["n_polylines"],
        "cluster_count": len(clusters),
        "raw_connection_count": len(raw_rows),
        "aggregated_connection_count": len(connections),
        "global_transform": transform_to_json(reference_transform),
        "cluster_debug_rows": cluster_debug_rows,
        "assignment_debug_rows": assignment_debug_rows,
        "raw_rows": raw_rows,
        "connections": connections,
    }


def plot_snapshot(snapshot_result: Dict[str, Any], wells: Dict[str, Dict[str, Any]], reference_transform: Dict[str, Any]) -> None:
    MAP_DIR.mkdir(parents=True, exist_ok=True)

    if not snapshot_result.get("source_file"):
        return

    path = Path(snapshot_result["source_file"])
    sln = extract_polylines(path)

    assignment_map = {
        int(r["streamline_id"]): r
        for r in snapshot_result.get("assignment_debug_rows", [])
    }

    plt.figure(figsize=(15, 11))

    for item in sln["polylines"]:
        sid = int(item["streamline_id"])
        aligned = apply_bbox_transform(item["points"], reference_transform)

        if sid in assignment_map:
            a = assignment_map[sid]
            dx = float(a["dx_applied"])
            dy = float(a["dy_applied"])
            snapped = apply_snap(aligned, dx, dy)
            color = "cornflowerblue"
            alpha = 0.65
            linewidth = 0.75
        else:
            snapped = aligned
            color = "lightgray"
            alpha = 0.25
            linewidth = 0.50

        plt.plot(snapped[:, 0], snapped[:, 1], linewidth=linewidth, alpha=alpha, color=color)
        plt.scatter(snapped[0, 0], snapped[0, 1], s=9, color="green", alpha=0.70)
        plt.scatter(snapped[-1, 0], snapped[-1, 1], s=13, color="orange", alpha=0.90)

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

    t = snapshot_result["global_transform"]

    title = (
        f"Last-point 2D cluster snap - {snapshot_result['snapshot'].upper()}\n"
        f"connections={snapshot_result['aggregated_connection_count']} | "
        f"clusters={snapshot_result['cluster_count']} | "
        f"SNAP_MODE={SNAP_MODE} | flip_y={t['flip_y']} | swap_xy={t['swap_xy']}"
    )

    plt.title(title)
    plt.xlabel("Grid I / aligned X")
    plt.ylabel("Grid J / aligned Y")
    plt.grid(True, alpha=0.25)
    plt.gca().invert_yaxis()
    plt.gca().set_aspect("equal", adjustable="box")
    plt.legend(loc="best", fontsize=8)
    plt.tight_layout()

    out = MAP_DIR / f"cluster_snap_streamlines_{snapshot_result['snapshot']}.png"
    plt.savefig(out, dpi=220)
    plt.close()

    print(f"[OK] Saved {out}")


def write_debug_csvs(snapshot_result: Dict[str, Any]) -> None:
    snapshot = snapshot_result["snapshot"]

    write_csv(
        OUTPUT_DIR / f"cluster_snap_cluster_debug_{snapshot}.csv",
        snapshot_result.get("cluster_debug_rows", []),
    )

    write_csv(
        OUTPUT_DIR / f"cluster_snap_assignment_debug_{snapshot}.csv",
        snapshot_result.get("assignment_debug_rows", []),
    )

    write_csv(
        OUTPUT_DIR / f"cluster_snap_connections_{snapshot}.csv",
        snapshot_result.get("connections", []),
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MAP_DIR.mkdir(parents=True, exist_ok=True)

    wells = load_well_points()

    print(f"Wells loaded: {len(wells)}")
    print(f"Producers: {sum(1 for w in wells.values() if w['is_producer'])}")
    print(f"Injectors: {sum(1 for w in wells.values() if w['is_injector'])}")
    print(f"SNAP_MODE: {SNAP_MODE}")
    print(f"LASTPOINT_CLUSTER_RADIUS_CELLS: {LASTPOINT_CLUSTER_RADIUS_CELLS}")

    reference_transform = get_reference_transform_from_init(wells)

    print("")
    print("Reference transform fitted on INIT:")
    print(f"  swap_xy={reference_transform['swap_xy']}")
    print(f"  flip_x={reference_transform['flip_x']}")
    print(f"  flip_y={reference_transform['flip_y']}")
    print(f"  median endpoint distance={reference_transform['median_endpoint_distance']:.2f}")

    results = {}
    connections_by_snapshot = {}

    for snapshot in ["init", "eoh"]:
        print("")
        print(f"Processing {snapshot}...")

        result = build_snapshot(snapshot, wells, reference_transform)

        results[snapshot] = result
        connections_by_snapshot[snapshot] = result.get("connections", [])

        print(f"  source: {result.get('source_file')}")
        print(f"  method: {result.get('method')}")
        print(f"  clusters: {result.get('cluster_count')}")
        print(f"  raw connection rows: {result.get('raw_connection_count')}")
        print(f"  aggregated connections: {result.get('aggregated_connection_count')}")

        plot_snapshot(result, wells, reference_transform)
        write_debug_csvs(result)

    changes = build_changes(
        connections_by_snapshot.get("init", []),
        connections_by_snapshot.get("eoh", []),
    )

    payload = {
        "available": bool(connections_by_snapshot.get("init") or connections_by_snapshot.get("eoh")),
        "method": "last_point_cluster_2d_snap_to_producer",
        "snap_mode": SNAP_MODE,
        "lastpoint_cluster_radius_cells": LASTPOINT_CLUSTER_RADIUS_CELLS,
        "max_cluster_producer_distance_cells": MAX_CLUSTER_PRODUCER_DISTANCE_CELLS,
        "producer_radius_cells": PRODUCER_RADIUS_CELLS,
        "injector_radius_cells": INJECTOR_RADIUS_CELLS,
        "reference_transform_from_init": transform_to_json(reference_transform),
        "snapshots": results,
        "connections_by_snapshot": connections_by_snapshot,
        "connection_changes": changes,
        "notes": [
            "This method does not force vertical columns.",
            "It clusters streamline last points in 2D, assigns each cluster to a producer, and snaps the whole cluster to that producer.",
            "EOH uses the same global transform fitted on INIT.",
            "Producer snapping is saved independently from injector matching.",
        ],
    }

    out_json = OUTPUT_DIR / "cluster_snap_streamline_connections.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[OK] Saved {out_json}")

    write_csv(OUTPUT_DIR / "cluster_snap_connection_changes.csv", changes)

    print("")
    print(f"Available: {payload['available']}")
    print(f"Maps saved in: {MAP_DIR}")


if __name__ == "__main__":
    main()
