import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from app.streamlines_reader import (
    MODEL_DIR,
    try_read_binary_sln_arrays,
    normalize_ptr,
    detect_pointer_units,
    ptr_to_point_slice,
    find_streamline_file,
)
from app.well_connections import get_well_spatial_summary


GRID_DIMENSIONS_FILE = MODEL_DIR / "grid_dimensions.json"

RADII = [0, 1, 2, 3, 5, 8]


def load_dims():
    data = json.loads(GRID_DIMENSIONS_FILE.read_text(encoding="utf-8-sig"))
    return int(data["nx"]), int(data["ny"]), int(data["nz"])


def id_to_ijk_i_fastest(cell_id: int, nx: int, ny: int, nz: int, base: int):
    idx = cell_id - base

    if idx < 0 or idx >= nx * ny * nz:
        return None

    i = idx % nx + 1
    j = (idx // nx) % ny + 1
    k = idx // (nx * ny) + 1

    return i, j, k


def id_to_ijk_j_fastest(cell_id: int, nx: int, ny: int, nz: int, base: int):
    idx = cell_id - base

    if idx < 0 or idx >= nx * ny * nz:
        return None

    j = idx % ny + 1
    i = (idx // ny) % nx + 1
    k = idx // (nx * ny) + 1

    return i, j, k


def id_to_ijk_k_fastest(cell_id: int, nx: int, ny: int, nz: int, base: int):
    idx = cell_id - base

    if idx < 0 or idx >= nx * ny * nz:
        return None

    k = idx % nz + 1
    j = (idx // nz) % ny + 1
    i = idx // (ny * nz) + 1

    return i, j, k


CONVENTIONS = {
    "I_FASTEST_0_BASED": lambda cid, nx, ny, nz: id_to_ijk_i_fastest(cid, nx, ny, nz, 0),
    "I_FASTEST_1_BASED": lambda cid, nx, ny, nz: id_to_ijk_i_fastest(cid, nx, ny, nz, 1),
    "J_FASTEST_0_BASED": lambda cid, nx, ny, nz: id_to_ijk_j_fastest(cid, nx, ny, nz, 0),
    "J_FASTEST_1_BASED": lambda cid, nx, ny, nz: id_to_ijk_j_fastest(cid, nx, ny, nz, 1),
    "K_FASTEST_0_BASED": lambda cid, nx, ny, nz: id_to_ijk_k_fastest(cid, nx, ny, nz, 0),
    "K_FASTEST_1_BASED": lambda cid, nx, ny, nz: id_to_ijk_k_fastest(cid, nx, ny, nz, 1),
}


def get_completion_cells():
    spatial = get_well_spatial_summary()
    cells = []

    for well, payload in spatial.get("wells", {}).items():
        for c in payload.get("connections", []):
            try:
                cells.append(
                    {
                        "well": well,
                        "i": int(c["i"]),
                        "j": int(c["j"]),
                        "k": int(c["k"]),
                    }
                )
            except Exception:
                continue

    return cells


def chebyshev_distance(a, b):
    return max(
        abs(a[0] - b[0]),
        abs(a[1] - b[1]),
        abs(a[2] - b[2]),
    )


def read_streamline_cells(path: Path):
    data, endian = try_read_binary_sln_arrays(path)

    geom = data["GEOMETRY"]
    ptr = normalize_ptr(data["GEOMINDX"])
    id_cell = data["ID_CELL"]

    n_points_total = geom.size // 3
    pointer_units = detect_pointer_units(ptr, geom.size, n_points_total)
    n_streamlines = ptr.size - 1

    streamlines = []
    cell_cursor = 0

    for sid in range(n_streamlines):
        a = int(ptr[sid])
        b = int(ptr[sid + 1])
        p0, p1 = ptr_to_point_slice(a, b, pointer_units, n_points_total)

        if p1 <= p0:
            continue

        npts = p1 - p0

        if id_cell.size == n_points_total:
            cells = list(id_cell[p0:p1])
        else:
            # Segment-cell style: usually npts - 1 cells for npts points.
            ncell_this = max(0, npts - 1)
            cells = list(id_cell[cell_cursor:cell_cursor + ncell_this])
            cell_cursor += ncell_this

        cells = [int(x) for x in cells if str(x) != ""]

        if cells:
            streamlines.append(
                {
                    "streamline_id": sid + 1,
                    "cells": cells,
                    "first_cells": cells[:max(3, min(10, len(cells)))],
                    "last_cells": cells[-max(3, min(10, len(cells))):],
                }
            )

    return streamlines


def evaluate_snapshot(snapshot: str):
    path = find_streamline_file(snapshot, model_dir=MODEL_DIR)

    if path is None:
        print(f"No file for {snapshot}")
        return

    nx, ny, nz = load_dims()
    completions = get_completion_cells()
    streamlines = read_streamline_cells(path)

    print("")
    print("=" * 100)
    print(f"SNAPSHOT: {snapshot} | {path.name}")
    print("=" * 100)
    print(f"Completions: {len(completions)}")
    print(f"Streamlines: {len(streamlines)}")

    for conv_name, converter in CONVENTIONS.items():
        # Convert all SLN cells to IJK if possible.
        converted_streamlines = []

        for sl in streamlines:
            first_ijk = []
            last_ijk = []
            all_ijk = []

            for cid in sl["first_cells"]:
                ijk = converter(cid, nx, ny, nz)
                if ijk:
                    first_ijk.append(ijk)

            for cid in sl["last_cells"]:
                ijk = converter(cid, nx, ny, nz)
                if ijk:
                    last_ijk.append(ijk)

            for cid in sl["cells"]:
                ijk = converter(cid, nx, ny, nz)
                if ijk:
                    all_ijk.append(ijk)

            converted_streamlines.append(
                {
                    "streamline_id": sl["streamline_id"],
                    "first_ijk": first_ijk,
                    "last_ijk": last_ijk,
                    "all_ijk": all_ijk,
                }
            )

        valid_count = sum(1 for sl in converted_streamlines if sl["all_ijk"])

        print("")
        print(f"Convention: {conv_name}")
        print(f"  streamlines with valid converted cells: {valid_count}/{len(streamlines)}")

        for radius in RADII:
            first_matches = 0
            last_matches = 0
            any_matches = 0
            both_endpoint_matches = 0
            matched_wells = set()

            for sl in converted_streamlines:
                first_wells = set()
                last_wells = set()
                any_wells = set()

                for comp in completions:
                    comp_ijk = (comp["i"], comp["j"], comp["k"])

                    if any(chebyshev_distance(x, comp_ijk) <= radius for x in sl["first_ijk"]):
                        first_wells.add(comp["well"])
                        matched_wells.add(comp["well"])

                    if any(chebyshev_distance(x, comp_ijk) <= radius for x in sl["last_ijk"]):
                        last_wells.add(comp["well"])
                        matched_wells.add(comp["well"])

                    if any(chebyshev_distance(x, comp_ijk) <= radius for x in sl["all_ijk"]):
                        any_wells.add(comp["well"])
                        matched_wells.add(comp["well"])

                if first_wells:
                    first_matches += 1

                if last_wells:
                    last_matches += 1

                if any_wells:
                    any_matches += 1

                if first_wells and last_wells:
                    both_endpoint_matches += 1

            print(
                f"  radius={radius:<2} | "
                f"first={first_matches:<4} "
                f"last={last_matches:<4} "
                f"both_endpoints={both_endpoint_matches:<4} "
                f"anywhere={any_matches:<4} "
                f"matched_wells={len(matched_wells):<3}"
            )


def main():
    evaluate_snapshot("init")
    evaluate_snapshot("eoh")


if __name__ == "__main__":
    main()
