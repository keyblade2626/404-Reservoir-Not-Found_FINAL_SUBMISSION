import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.streamlines_reader import (
    MODEL_DIR,
    find_streamline_file,
    try_read_binary_sln_arrays,
    normalize_ptr,
    detect_pointer_units,
    ptr_to_point_slice,
)
from app.well_connections import get_well_spatial_summary


OUTPUT_DIR = Path("artifacts/streamlines")
INJECTION_JSON = Path("artifacts/injection_hm/injection_hm_results.json")

ASSIGNMENT_MAX_DISTANCE_CELLS = 8.0
ICP_ITERATIONS = 30
ROTATION_STEP_DEGREES = 15


def to_float(value: Any) -> Optional[float]:
    if value in [None, "", "None", "null", "N/A"]:
        return None
    try:
        return float(value)
    except Exception:
        return None


def read_injection_roles() -> Dict[str, Dict[str, Any]]:
    if not INJECTION_JSON.exists():
        return {}

    payload = json.loads(INJECTION_JSON.read_text(encoding="utf-8"))
    return payload.get("well_results", {})


def is_injector_role(role: Optional[str]) -> bool:
    if role is None:
        return False

    return role in [
        "water_injector",
        "gas_injector",
        "wag_or_dual_injector",
        "mixed_producer_water_injector",
        "mixed_producer_gas_injector",
        "mixed_producer_wag",
    ]


def is_producer_role(role: Optional[str], payload: Optional[Dict[str, Any]] = None) -> bool:
    if role is None:
        return True

    if role == "producer_only":
        return True

    if role in [
        "mixed_producer_water_injector",
        "mixed_producer_gas_injector",
        "mixed_producer_wag",
    ]:
        return True

    if payload and payload.get("has_material_production"):
        return True

    return False


def get_well_points() -> Dict[str, Dict[str, Any]]:
    spatial = get_well_spatial_summary()
    roles = read_injection_roles()

    result = {}

    for well, payload in spatial.get("wells", {}).items():
        i = to_float(payload.get("representative_i"))
        j = to_float(payload.get("representative_j"))

        if i is None or j is None:
            continue

        role_payload = roles.get(well, {})
        role = role_payload.get("role")

        result[well] = {
            "well": well,
            "x": i,
            "y": j,
            "role": role,
            "is_injector": is_injector_role(role),
            "is_producer": is_producer_role(role, role_payload),
        }

    return result


def extract_streamline_endpoints(path: Path, snapshot: str) -> Dict[str, Any]:
    data, endian = try_read_binary_sln_arrays(path)

    geom = data.get("GEOMETRY")
    ptr_raw = data.get("GEOMINDX")

    if geom is None or ptr_raw is None:
        raise ValueError("Missing GEOMETRY or GEOMINDX.")

    if geom.size % 3 != 0:
        raise ValueError("GEOMETRY length is not divisible by 3.")

    xyz = geom.reshape((geom.size // 3, 3))
    n_points_total = xyz.shape[0]

    ptr = normalize_ptr(ptr_raw)
    n_streamlines = ptr.size - 1
    pointer_units = detect_pointer_units(ptr, geom.size, n_points_total)

    endpoints = []
    all_endpoint_points = []

    for sid in range(n_streamlines):
        a = int(ptr[sid])
        b = int(ptr[sid + 1])

        p0, p1 = ptr_to_point_slice(a, b, pointer_units, n_points_total)

        if p1 <= p0:
            continue

        first = xyz[p0]
        last = xyz[p1 - 1]

        endpoint = {
            "streamline_id": sid + 1,
            "first_x": float(first[0]),
            "first_y": float(first[1]),
            "last_x": float(last[0]),
            "last_y": float(last[1]),
            "first_z": float(first[2]),
            "last_z": float(last[2]),
            "point_count": int(p1 - p0),
        }

        endpoints.append(endpoint)
        all_endpoint_points.append([endpoint["first_x"], endpoint["first_y"]])
        all_endpoint_points.append([endpoint["last_x"], endpoint["last_y"]])

    return {
        "snapshot": snapshot,
        "source_file": str(path),
        "endian": endian,
        "n_streamlines": n_streamlines,
        "n_points_total": n_points_total,
        "pointer_units": pointer_units,
        "endpoints": endpoints,
        "endpoint_points": np.asarray(all_endpoint_points, dtype=float),
    }


def nearest_targets(points: np.ndarray, targets: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    matched = []
    distances = []

    for p in points:
        diff = targets - p
        d2 = np.sum(diff * diff, axis=1)
        idx = int(np.argmin(d2))
        matched.append(idx)
        distances.append(math.sqrt(float(d2[idx])))

    return np.asarray(matched, dtype=int), np.asarray(distances, dtype=float)


def apply_transform(points: np.ndarray, scale: float, rotation: np.ndarray, translation: np.ndarray) -> np.ndarray:
    return scale * (points @ rotation.T) + translation


def fit_similarity_transform(source: np.ndarray, target: np.ndarray) -> Tuple[float, np.ndarray, np.ndarray]:
    """
    Fits target ~= scale * source @ R.T + translation.
    """
    if len(source) < 2:
        return 1.0, np.eye(2), np.zeros(2)

    mu_x = np.mean(source, axis=0)
    mu_y = np.mean(target, axis=0)

    x = source - mu_x
    y = target - mu_y

    var_x = np.mean(np.sum(x * x, axis=1))

    if var_x <= 1e-12:
        return 1.0, np.eye(2), mu_y - mu_x

    cov = (y.T @ x) / len(source)
    u, s, vt = np.linalg.svd(cov)

    d = np.eye(2)
    if np.linalg.det(u @ vt) < 0:
        d[-1, -1] = -1

    rotation = u @ d @ vt
    scale = float(np.trace(np.diag(s) @ d) / var_x)
    translation = mu_y - scale * (mu_x @ rotation.T)

    return scale, rotation, translation


def initial_transform(source: np.ndarray, target: np.ndarray, angle_deg: float, reflection: Tuple[int, int]) -> Tuple[float, np.ndarray, np.ndarray]:
    src_center = np.mean(source, axis=0)
    tgt_center = np.mean(target, axis=0)

    src_std = np.std(source, axis=0)
    tgt_std = np.std(target, axis=0)

    src_scale = float(np.mean(src_std[src_std > 1e-12])) if np.any(src_std > 1e-12) else 1.0
    tgt_scale = float(np.mean(tgt_std[tgt_std > 1e-12])) if np.any(tgt_std > 1e-12) else 1.0

    scale = tgt_scale / src_scale

    theta = math.radians(angle_deg)
    rot = np.array(
        [
            [math.cos(theta), -math.sin(theta)],
            [math.sin(theta), math.cos(theta)],
        ],
        dtype=float,
    )

    refl = np.array(
        [
            [reflection[0], 0],
            [0, reflection[1]],
        ],
        dtype=float,
    )

    rotation = rot @ refl
    translation = tgt_center - scale * (src_center @ rotation.T)

    return scale, rotation, translation


def run_icp(source: np.ndarray, target: np.ndarray) -> Dict[str, Any]:
    best = None

    angles = list(range(0, 360, ROTATION_STEP_DEGREES))
    reflections = [(1, 1), (-1, 1), (1, -1), (-1, -1)]

    for angle in angles:
        for reflection in reflections:
            scale, rotation, translation = initial_transform(source, target, angle, reflection)

            last_score = None

            for _ in range(ICP_ITERATIONS):
                aligned = apply_transform(source, scale, rotation, translation)
                nearest_idx, distances = nearest_targets(aligned, target)
                matched_target = target[nearest_idx]

                scale, rotation, translation = fit_similarity_transform(source, matched_target)

                score = float(np.median(distances))

                if last_score is not None and abs(last_score - score) < 1e-6:
                    break

                last_score = score

            aligned = apply_transform(source, scale, rotation, translation)
            nearest_idx, distances = nearest_targets(aligned, target)

            score_median = float(np.median(distances))
            score_p90 = float(np.percentile(distances, 90))
            score_mean = float(np.mean(distances))

            candidate = {
                "scale": scale,
                "rotation": rotation,
                "translation": translation,
                "median_distance": score_median,
                "p90_distance": score_p90,
                "mean_distance": score_mean,
                "angle_init": angle,
                "reflection_init": reflection,
            }

            if best is None:
                best = candidate
            else:
                if (score_median, score_p90, score_mean) < (
                    best["median_distance"],
                    best["p90_distance"],
                    best["mean_distance"],
                ):
                    best = candidate

    return best


def assign_nearest_well(point: np.ndarray, well_names: List[str], well_xy: np.ndarray) -> Dict[str, Any]:
    diff = well_xy - point
    d2 = np.sum(diff * diff, axis=1)
    idx = int(np.argmin(d2))
    distance = math.sqrt(float(d2[idx]))

    return {
        "well": well_names[idx],
        "distance": distance,
    }


def infer_connection(first_well: Dict[str, Any], last_well: Dict[str, Any], well_points: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if first_well["well"] == last_well["well"]:
        return None

    first_payload = well_points[first_well["well"]]
    last_payload = well_points[last_well["well"]]

    first_is_inj = first_payload["is_injector"]
    last_is_inj = last_payload["is_injector"]

    first_is_prod = first_payload["is_producer"]
    last_is_prod = last_payload["is_producer"]

    # Prefer role-based direction.
    if first_is_inj and last_is_prod and not last_is_inj:
        return {
            "injector": first_well["well"],
            "producer": last_well["well"],
            "direction_inference": "role_first_injector_last_producer",
        }

    if last_is_inj and first_is_prod and not first_is_inj:
        return {
            "injector": last_well["well"],
            "producer": first_well["well"],
            "direction_inference": "role_last_injector_first_producer",
        }

    # Mixed wells can be both producer/injector. Keep but mark less certain.
    if first_is_inj and last_is_prod:
        return {
            "injector": first_well["well"],
            "producer": last_well["well"],
            "direction_inference": "mixed_role_first_as_injector",
        }

    if last_is_inj and first_is_prod:
        return {
            "injector": last_well["well"],
            "producer": first_well["well"],
            "direction_inference": "mixed_role_last_as_injector",
        }

    return None


def aggregate_connections(rows: List[Dict[str, Any]], snapshot: str) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for row in rows:
        key = (row["injector"], row["producer"])

        if key not in grouped:
            grouped[key] = {
                "snapshot": snapshot,
                "injector": row["injector"],
                "producer": row["producer"],
                "connection_strength": 0.0,
                "streamline_count": 0.0,
                "mean_first_endpoint_distance": 0.0,
                "mean_last_endpoint_distance": 0.0,
                "raw_count": 0,
                "direction_inference_examples": [],
            }

        g = grouped[key]
        g["connection_strength"] += 1.0
        g["streamline_count"] += 1.0
        g["mean_first_endpoint_distance"] += row["first_endpoint_distance"]
        g["mean_last_endpoint_distance"] += row["last_endpoint_distance"]
        g["raw_count"] += 1

        if row["direction_inference"] not in g["direction_inference_examples"]:
            g["direction_inference_examples"].append(row["direction_inference"])

    producer_totals: Dict[str, float] = {}

    for g in grouped.values():
        producer_totals[g["producer"]] = producer_totals.get(g["producer"], 0.0) + g["connection_strength"]

    output = []

    for g in grouped.values():
        if g["raw_count"] > 0:
            g["mean_first_endpoint_distance"] /= g["raw_count"]
            g["mean_last_endpoint_distance"] /= g["raw_count"]

        total = producer_totals.get(g["producer"], 0.0)
        g["connection_fraction_to_producer"] = g["connection_strength"] / total if total > 0 else None
        output.append(g)

    return sorted(output, key=lambda x: (x["producer"], -x["connection_strength"]))


def build_snapshot_connections(snapshot_payload: Dict[str, Any], well_points: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    source_points = snapshot_payload["endpoint_points"]

    well_names = list(well_points.keys())
    well_xy = np.asarray([[well_points[w]["x"], well_points[w]["y"]] for w in well_names], dtype=float)

    if len(source_points) < 2 or len(well_xy) < 2:
        raise RuntimeError("Not enough points or wells for geometric alignment.")

    transform = run_icp(source_points, well_xy)

    aligned_points = apply_transform(
        source_points,
        transform["scale"],
        transform["rotation"],
        transform["translation"],
    )

    # Rebuild aligned first/last endpoints.
    rows = []
    endpoint_index = 0

    for endpoint in snapshot_payload["endpoints"]:
        first_aligned = aligned_points[endpoint_index]
        last_aligned = aligned_points[endpoint_index + 1]
        endpoint_index += 2

        first_match = assign_nearest_well(first_aligned, well_names, well_xy)
        last_match = assign_nearest_well(last_aligned, well_names, well_xy)

        if first_match["distance"] > ASSIGNMENT_MAX_DISTANCE_CELLS:
            continue

        if last_match["distance"] > ASSIGNMENT_MAX_DISTANCE_CELLS:
            continue

        conn = infer_connection(first_match, last_match, well_points)

        if conn is None:
            continue

        rows.append(
            {
                "snapshot": snapshot_payload["snapshot"],
                "streamline_id": endpoint["streamline_id"],
                "injector": conn["injector"],
                "producer": conn["producer"],
                "direction_inference": conn["direction_inference"],
                "first_endpoint_well": first_match["well"],
                "last_endpoint_well": last_match["well"],
                "first_endpoint_distance": first_match["distance"],
                "last_endpoint_distance": last_match["distance"],
                "first_x_aligned": float(first_aligned[0]),
                "first_y_aligned": float(first_aligned[1]),
                "last_x_aligned": float(last_aligned[0]),
                "last_y_aligned": float(last_aligned[1]),
            }
        )

    aggregated = aggregate_connections(rows, snapshot_payload["snapshot"])

    return {
        "snapshot": snapshot_payload["snapshot"],
        "source_file": snapshot_payload["source_file"],
        "n_streamlines": snapshot_payload["n_streamlines"],
        "raw_mapped_streamline_count": len(rows),
        "aggregated_connection_count": len(aggregated),
        "assignment_max_distance_cells": ASSIGNMENT_MAX_DISTANCE_CELLS,
        "alignment": {
            "scale": transform["scale"],
            "rotation": transform["rotation"].tolist(),
            "translation": transform["translation"].tolist(),
            "median_endpoint_distance": transform["median_distance"],
            "p90_endpoint_distance": transform["p90_distance"],
            "mean_endpoint_distance": transform["mean_distance"],
            "angle_init": transform["angle_init"],
            "reflection_init": list(transform["reflection_init"]),
        },
        "raw_rows": rows,
        "connections": aggregated,
    }


def build_connection_changes(init_connections: List[Dict[str, Any]], eoh_connections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    init_lookup = {(c["injector"], c["producer"]): c for c in init_connections}
    eoh_lookup = {(c["injector"], c["producer"]): c for c in eoh_connections}

    keys = sorted(set(init_lookup) | set(eoh_lookup))

    changes = []

    for injector, producer in keys:
        init = init_lookup.get((injector, producer))
        eoh = eoh_lookup.get((injector, producer))

        init_strength = float(init.get("connection_strength") or 0.0) if init else 0.0
        eoh_strength = float(eoh.get("connection_strength") or 0.0) if eoh else 0.0

        init_fraction = init.get("connection_fraction_to_producer") if init else None
        eoh_fraction = eoh.get("connection_fraction_to_producer") if eoh else None

        changes.append(
            {
                "injector": injector,
                "producer": producer,
                "init_connection_strength": init_strength,
                "eoh_connection_strength": eoh_strength,
                "delta_connection_strength": eoh_strength - init_strength,
                "init_connection_fraction": init_fraction,
                "eoh_connection_fraction": eoh_fraction,
                "delta_connection_fraction": (
                    eoh_fraction - init_fraction
                    if init_fraction is not None and eoh_fraction is not None
                    else None
                ),
                "appeared_by_eoh": init is None and eoh is not None,
                "disappeared_by_eoh": init is not None and eoh is None,
            }
        )

    return sorted(changes, key=lambda x: (x["producer"], -x["eoh_connection_strength"]))


def write_connections_csv(snapshot_result: Dict[str, Any]) -> None:
    path = OUTPUT_DIR / f"geometric_streamline_connections_{snapshot_result['snapshot']}.csv"
    rows = snapshot_result["connections"]

    if not rows:
        return

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Saved {path}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    well_points = get_well_points()

    if not well_points:
        raise SystemExit("No well points found from WELL_CONNECTIONS.")

    print(f"Well points loaded: {len(well_points)}")

    results_by_snapshot = {}
    connections_by_snapshot = {}

    for snapshot in ["init", "eoh"]:
        path = find_streamline_file(snapshot, model_dir=MODEL_DIR)

        if path is None:
            print(f"[MISSING] {snapshot} streamline file.")
            results_by_snapshot[snapshot] = {
                "snapshot": snapshot,
                "source_file": None,
                "connections": [],
                "warning": "missing_file",
            }
            connections_by_snapshot[snapshot] = []
            continue

        print(f"Reading {snapshot}: {path}")

        snapshot_payload = extract_streamline_endpoints(path, snapshot)
        result = build_snapshot_connections(snapshot_payload, well_points)

        results_by_snapshot[snapshot] = result
        connections_by_snapshot[snapshot] = result["connections"]

        print(
            f"  mapped streamlines: {result['raw_mapped_streamline_count']} / {result['n_streamlines']}"
        )
        print(
            f"  aggregated connections: {result['aggregated_connection_count']}"
        )
        print(
            f"  alignment median endpoint distance: {result['alignment']['median_endpoint_distance']:.2f} grid cells"
        )

        write_connections_csv(result)

    changes = build_connection_changes(
        connections_by_snapshot.get("init", []),
        connections_by_snapshot.get("eoh", []),
    )

    payload = {
        "available": any(len(v) > 0 for v in connections_by_snapshot.values()),
        "method": "geometric_alignment_icp",
        "assignment_max_distance_cells": ASSIGNMENT_MAX_DISTANCE_CELLS,
        "well_points": well_points,
        "snapshots": results_by_snapshot,
        "connections_by_snapshot": connections_by_snapshot,
        "connection_changes": changes,
        "limitations": [
            "Geometric alignment infers connections from streamline endpoints and nearest wells.",
            "It does not use exact ID_CELL-to-completion mapping.",
            "Review alignment distance and mapped streamline count before using results for final interpretation.",
        ],
    }

    out_json = OUTPUT_DIR / "geometric_streamline_connections.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[OK] Saved {out_json}")

    if changes:
        out_csv = OUTPUT_DIR / "geometric_streamline_connection_changes.csv"

        with out_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(changes[0].keys()))
            writer.writeheader()
            writer.writerows(changes)

        print(f"[OK] Saved {out_csv}")

    print("")
    print(f"Available: {payload['available']}")
    print("Geometric streamline mapping completed.")


if __name__ == "__main__":
    main()
