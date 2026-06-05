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


INJECTION_JSON = Path("artifacts/injection_hm/injection_hm_results.json")


def to_float(value: Any) -> Optional[float]:
    if value in [None, "", "None", "null", "N/A"]:
        return None
    try:
        return float(value)
    except Exception:
        return None


def load_roles() -> Dict[str, Dict[str, Any]]:
    if not INJECTION_JSON.exists():
        return {}

    payload = json.loads(INJECTION_JSON.read_text(encoding="utf-8"))
    return payload.get("well_results", {})


def is_injector_role(role: Optional[str]) -> bool:
    return role in [
        "water_injector",
        "gas_injector",
        "wag_or_dual_injector",
        "mixed_producer_water_injector",
        "mixed_producer_gas_injector",
        "mixed_producer_wag",
    ]


def is_producer_role(role: Optional[str], payload: Optional[Dict[str, Any]] = None) -> bool:
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

    if role is None:
        return True

    return False


def load_well_points() -> Dict[str, Dict[str, Any]]:
    spatial = get_well_spatial_summary()
    roles = load_roles()

    wells = {}

    for well, payload in spatial.get("wells", {}).items():
        i = to_float(payload.get("representative_i"))
        j = to_float(payload.get("representative_j"))

        if i is None or j is None:
            continue

        role_payload = roles.get(well, {})
        role = role_payload.get("role")

        wells[well] = {
            "well": well,
            "x": i,
            "y": j,
            "role": role,
            "is_injector": is_injector_role(role),
            "is_producer": is_producer_role(role, role_payload),
        }

    return wells


def extract_polylines(path: Path) -> Dict[str, Any]:
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
    pointer_units = detect_pointer_units(ptr, geom.size, n_points_total)
    n_streamlines = ptr.size - 1

    polylines = []
    endpoints = []

    for sid in range(n_streamlines):
        a = int(ptr[sid])
        b = int(ptr[sid + 1])

        p0, p1 = ptr_to_point_slice(a, b, pointer_units, n_points_total)

        if p1 <= p0:
            continue

        pts = xyz[p0:p1, 0:2].astype(float)

        if len(pts) < 2:
            continue

        polylines.append({
            "streamline_id": sid + 1,
            "points": pts,
        })

        endpoints.append(pts[0])
        endpoints.append(pts[-1])

    return {
        "source_file": str(path),
        "endian": endian,
        "n_streamlines": int(n_streamlines),
        "n_polylines": len(polylines),
        "polylines": polylines,
        "endpoint_points": np.asarray(endpoints, dtype=float),
    }


def prepare_points(points: np.ndarray, swap_xy: bool, flip_x: bool, flip_y: bool) -> np.ndarray:
    q = points.copy().astype(float)

    if swap_xy:
        q = q[:, [1, 0]]

    if flip_x:
        q[:, 0] = -q[:, 0]

    if flip_y:
        q[:, 1] = -q[:, 1]

    return q


def fit_bbox_transform(
    source_points: np.ndarray,
    target_points: np.ndarray,
    swap_xy: bool,
    flip_x: bool,
    flip_y: bool,
) -> Dict[str, Any]:

    prepared = prepare_points(source_points, swap_xy, flip_x, flip_y)

    src_min = np.min(prepared, axis=0)
    src_max = np.max(prepared, axis=0)
    src_range = np.maximum(src_max - src_min, 1e-12)

    tgt_min = np.min(target_points, axis=0)
    tgt_max = np.max(target_points, axis=0)
    tgt_range = np.maximum(tgt_max - tgt_min, 1e-12)

    scale = tgt_range / src_range
    transformed = (prepared - src_min) * scale + tgt_min

    return {
        "swap_xy": swap_xy,
        "flip_x": flip_x,
        "flip_y": flip_y,
        "src_min": src_min,
        "scale": scale,
        "tgt_min": tgt_min,
        "transformed_sample": transformed,
    }


def apply_bbox_transform(points: np.ndarray, transform: Dict[str, Any]) -> np.ndarray:
    prepared = prepare_points(
        points,
        transform["swap_xy"],
        transform["flip_x"],
        transform["flip_y"],
    )

    return (prepared - transform["src_min"]) * transform["scale"] + transform["tgt_min"]


def nearest_distances(points: np.ndarray, targets: np.ndarray) -> np.ndarray:
    distances = []

    for p in points:
        diff = targets - p
        d2 = np.sum(diff * diff, axis=1)
        distances.append(math.sqrt(float(np.min(d2))))

    return np.asarray(distances, dtype=float)


def choose_best_transform(endpoint_points: np.ndarray, well_points: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    target = np.asarray(
        [[w["x"], w["y"]] for w in well_points.values()],
        dtype=float,
    )

    candidates = []

    for swap_xy in [False, True]:
        for flip_x in [False, True]:
            for flip_y in [False, True]:
                transform = fit_bbox_transform(
                    endpoint_points,
                    target,
                    swap_xy=swap_xy,
                    flip_x=flip_x,
                    flip_y=flip_y,
                )

                transformed = transform["transformed_sample"]
                d = nearest_distances(transformed, target)

                candidate = {
                    **transform,
                    "median_endpoint_distance": float(np.median(d)),
                    "p75_endpoint_distance": float(np.percentile(d, 75)),
                    "p90_endpoint_distance": float(np.percentile(d, 90)),
                    "mean_endpoint_distance": float(np.mean(d)),
                    "within_8_cells_fraction": float(np.mean(d <= 8.0)),
                    "within_12_cells_fraction": float(np.mean(d <= 12.0)),
                }

                candidates.append(candidate)

    candidates = sorted(
        candidates,
        key=lambda c: (
            c["median_endpoint_distance"],
            c["p75_endpoint_distance"],
            c["p90_endpoint_distance"],
            -c["within_8_cells_fraction"],
        ),
    )

    best = candidates[0]

    best["all_candidates_summary"] = [
        {
            "swap_xy": c["swap_xy"],
            "flip_x": c["flip_x"],
            "flip_y": c["flip_y"],
            "median_endpoint_distance": c["median_endpoint_distance"],
            "p75_endpoint_distance": c["p75_endpoint_distance"],
            "p90_endpoint_distance": c["p90_endpoint_distance"],
            "within_8_cells_fraction": c["within_8_cells_fraction"],
        }
        for c in candidates
    ]

    return best


def distance_polyline_to_well(polyline: np.ndarray, well_xy: np.ndarray) -> float:
    diff = polyline - well_xy.reshape(1, 2)
    d2 = np.sum(diff * diff, axis=1)
    return math.sqrt(float(np.min(d2)))


def nearest_role_well(
    aligned_polyline: np.ndarray,
    wells: Dict[str, Dict[str, Any]],
    role_key: str,
) -> Optional[Dict[str, Any]]:

    best = None

    for well, wp in wells.items():
        if not wp.get(role_key):
            continue

        d = distance_polyline_to_well(
            aligned_polyline,
            np.asarray([wp["x"], wp["y"]], dtype=float),
        )

        item = {
            "well": well,
            "distance": d,
            "role": wp.get("role"),
        }

        if best is None or d < best["distance"]:
            best = item

    return best


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
                "streamline_count": 0,
                "mean_injector_distance": 0.0,
                "mean_producer_distance": 0.0,
                "raw_count": 0,
            }

        g = grouped[key]
        g["connection_strength"] += 1.0
        g["streamline_count"] += 1
        g["mean_injector_distance"] += float(row.get("injector_distance") or 0.0)
        g["mean_producer_distance"] += float(row.get("producer_distance") or 0.0)
        g["raw_count"] += 1

    producer_totals: Dict[str, float] = {}

    for g in grouped.values():
        producer_totals[g["producer"]] = producer_totals.get(g["producer"], 0.0) + g["connection_strength"]

    output = []

    for g in grouped.values():
        if g["raw_count"] > 0:
            g["mean_injector_distance"] /= g["raw_count"]
            g["mean_producer_distance"] /= g["raw_count"]

        total = producer_totals.get(g["producer"], 0.0)
        g["connection_fraction_to_producer"] = g["connection_strength"] / total if total > 0 else None
        output.append(g)

    return sorted(output, key=lambda x: (x["producer"], -x["connection_strength"]))


def build_changes(init_connections: List[Dict[str, Any]], eoh_connections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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

        changes.append({
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
        })

    return sorted(changes, key=lambda x: (x["producer"], -x["eoh_connection_strength"]))


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Saved {path}")
