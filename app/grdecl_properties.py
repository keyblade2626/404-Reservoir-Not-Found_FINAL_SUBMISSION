import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.well_connections import get_well_spatial_summary


DEFAULT_MODEL_DIR = Path("data/sample_model")
DEFAULT_DIMENSIONS_FILE = DEFAULT_MODEL_DIR / "grid_dimensions.json"

PROPERTY_FILES = {
    "perm_x": ["PERM_X.GRDECL", "PERM_X.GREDECL"],
    "perm_y": ["PERM_Y.GRDECL", "PERM_Y.GREDECL"],
    "perm_z": ["PERM_Z.GRDECL", "PERM_Z.GREDECL"],
}

PROPERTY_KEYWORDS = {
    "perm_x": ["PERMX", "PERM_X"],
    "perm_y": ["PERMY", "PERM_Y"],
    "perm_z": ["PERMZ", "PERM_Z"],
}


TOKEN_PATTERN = re.compile(
    r"(?P<repeat>\d+)\*(?P<value>[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?)|"
    r"(?P<number>[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?)|"
    r"(?P<default_repeat>\d+)\*"
)


def strip_comments(text: str) -> str:
    cleaned_lines = []

    for line in text.splitlines():
        if "--" in line:
            line = line.split("--", 1)[0]
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def find_property_file(property_name: str, model_dir: Path = DEFAULT_MODEL_DIR) -> Path:
    candidates = PROPERTY_FILES[property_name]

    for filename in candidates:
        path = model_dir / filename
        if path.exists():
            return path

    raise FileNotFoundError(
        f"Could not find GRDECL file for {property_name}. Tried: {candidates}"
    )


def find_keyword_block(text: str, keywords: List[str]) -> str:
    """
    Extracts values after the property keyword until '/'.

    Example:
      PERMY
        10*0 1.2 1.3
      /
    """
    text_no_comments = strip_comments(text)

    for keyword in keywords:
        pattern = re.compile(
            rf"\b{re.escape(keyword)}\b(?P<body>.*?)/",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(text_no_comments)

        if match:
            return match.group("body")

    raise ValueError(f"Could not find property keyword. Tried: {keywords}")


def expand_grdecl_values(block: str) -> List[float]:
    values: List[float] = []

    for match in TOKEN_PATTERN.finditer(block):
        if match.group("repeat") is not None:
            repeat = int(match.group("repeat"))
            value = float(match.group("value"))
            values.extend([value] * repeat)

        elif match.group("number") is not None:
            values.append(float(match.group("number")))

        elif match.group("default_repeat") is not None:
            # In ECLIPSE syntax, n* means n default values.
            # For this workflow we treat default property values as 0.0.
            repeat = int(match.group("default_repeat"))
            values.extend([0.0] * repeat)

    return values


def read_grdecl_property(
    property_name: str,
    model_dir: Path = DEFAULT_MODEL_DIR,
) -> Dict[str, Any]:
    path = find_property_file(property_name, model_dir)
    text = path.read_text(encoding="utf-8", errors="ignore")

    block = find_keyword_block(text, PROPERTY_KEYWORDS[property_name])
    values = expand_grdecl_values(block)

    if not values:
        raise ValueError(f"No values found in {path}")

    return {
        "property_name": property_name,
        "source_file": str(path),
        "value_count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
        "values": values,
    }


def load_grid_dimensions(path: Path = DEFAULT_DIMENSIONS_FILE) -> Dict[str, int]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing grid dimensions file: {path}. "
            "Create data/sample_model/grid_dimensions.json with nx, ny, nz."
        )

    data = json.loads(path.read_text(encoding="utf-8-sig"))

    nx = int(data["nx"])
    ny = int(data["ny"])
    nz = int(data["nz"])

    if nx <= 0 or ny <= 0 or nz <= 0:
        raise ValueError("Grid dimensions must be positive.")

    return {
        "nx": nx,
        "ny": ny,
        "nz": nz,
        "cell_count": nx * ny * nz,
    }


def cell_to_index(i: int, j: int, k: int, nx: int, ny: int, nz: int) -> int:
    """
    Converts 1-based Eclipse cell indices (I,J,K) to 0-based Python list index.

    ECLIPSE order:
      I fastest, then J, then K.
    """
    if not (1 <= i <= nx and 1 <= j <= ny and 1 <= k <= nz):
        raise IndexError(
            f"Cell ({i},{j},{k}) is outside grid dimensions ({nx},{ny},{nz})."
        )

    return (k - 1) * nx * ny + (j - 1) * nx + (i - 1)


def get_property_at_cell(
    values: List[float],
    i: int,
    j: int,
    k: int,
    dims: Dict[str, int],
) -> float:
    idx = cell_to_index(i, j, k, dims["nx"], dims["ny"], dims["nz"])

    if idx >= len(values):
        raise IndexError(
            f"Property index {idx} is outside property array length {len(values)}. "
            "Check NX, NY, NZ."
        )

    return values[idx]


def weighted_average(values: List[float], weights: Optional[List[float]] = None) -> Optional[float]:
    if not values:
        return None

    if not weights:
        return sum(values) / len(values)

    clean_weights = [max(float(w), 0.0) for w in weights]
    total_weight = sum(clean_weights)

    if total_weight <= 1e-12:
        return sum(values) / len(values)

    return sum(v * w for v, w in zip(values, clean_weights)) / total_weight


def percentile_rank(value: Optional[float], population: List[float]) -> Optional[float]:
    if value is None or not population:
        return None

    sorted_pop = sorted(population)
    below_or_equal = sum(1 for v in sorted_pop if v <= value)

    return round(100.0 * below_or_equal / len(sorted_pop), 2)


def build_property_context_by_well(
    model_dir: Path = DEFAULT_MODEL_DIR,
) -> Dict[str, Any]:
    dims = load_grid_dimensions()
    spatial = get_well_spatial_summary()

    properties = {
        "perm_x": read_grdecl_property("perm_x", model_dir),
        "perm_y": read_grdecl_property("perm_y", model_dir),
        "perm_z": read_grdecl_property("perm_z", model_dir),
    }

    for name, prop in properties.items():
        if prop["value_count"] != dims["cell_count"]:
            raise ValueError(
                f"{name} has {prop['value_count']} values, but grid_dimensions gives "
                f"{dims['cell_count']} cells. Check nx, ny, nz or export format."
            )

    well_context: Dict[str, Any] = {}

    all_well_perm_x = []
    all_well_perm_y = []
    all_well_perm_z = []

    for well, payload in spatial["wells"].items():
        connections = [
            c for c in payload.get("connections", [])
            if str(c.get("status", "")).upper() == "OPEN"
        ]

        if not connections:
            connections = payload.get("connections", [])

        perm_x_values = []
        perm_y_values = []
        perm_z_values = []
        transmissibility_weights = []
        kh_weights = []

        skipped_cells = []

        for c in connections:
            i = int(c["i"])
            j = int(c["j"])
            k = int(c["k"])

            try:
                px = get_property_at_cell(properties["perm_x"]["values"], i, j, k, dims)
                py = get_property_at_cell(properties["perm_y"]["values"], i, j, k, dims)
                pz = get_property_at_cell(properties["perm_z"]["values"], i, j, k, dims)
            except Exception as exc:
                skipped_cells.append(
                    {
                        "cell": [i, j, k],
                        "error": str(exc),
                    }
                )
                continue

            perm_x_values.append(px)
            perm_y_values.append(py)
            perm_z_values.append(pz)
            transmissibility_weights.append(float(c.get("transmissibility") or 0.0))
            kh_weights.append(float(c.get("permeability_thickness") or 0.0))

        mean_perm_x = weighted_average(perm_x_values)
        mean_perm_y = weighted_average(perm_y_values)
        mean_perm_z = weighted_average(perm_z_values)

        trans_weighted_perm_x = weighted_average(perm_x_values, transmissibility_weights)
        trans_weighted_perm_y = weighted_average(perm_y_values, transmissibility_weights)
        trans_weighted_perm_z = weighted_average(perm_z_values, transmissibility_weights)

        context = {
            "well": well,
            "connection_count": len(connections),
            "used_cell_count": len(perm_x_values),
            "skipped_cell_count": len(skipped_cells),
            "skipped_cells": skipped_cells[:10],
            "representative_i": payload.get("representative_i"),
            "representative_j": payload.get("representative_j"),
            "mean_perm_x": mean_perm_x,
            "mean_perm_y": mean_perm_y,
            "mean_perm_z": mean_perm_z,
            "transmissibility_weighted_perm_x": trans_weighted_perm_x,
            "transmissibility_weighted_perm_y": trans_weighted_perm_y,
            "transmissibility_weighted_perm_z": trans_weighted_perm_z,
            "max_perm_x": max(perm_x_values) if perm_x_values else None,
            "max_perm_y": max(perm_y_values) if perm_y_values else None,
            "max_perm_z": max(perm_z_values) if perm_z_values else None,
            "total_transmissibility": payload.get("total_transmissibility"),
            "max_transmissibility": payload.get("max_transmissibility"),
            "mean_transmissibility": payload.get("mean_transmissibility"),
            "total_permeability_thickness": payload.get("total_permeability_thickness"),
            "mean_permeability_thickness": payload.get("mean_permeability_thickness"),
        }

        well_context[well] = context

        if mean_perm_x is not None:
            all_well_perm_x.append(mean_perm_x)
        if mean_perm_y is not None:
            all_well_perm_y.append(mean_perm_y)
        if mean_perm_z is not None:
            all_well_perm_z.append(mean_perm_z)

    # Add percentile ranks across wells.
    for well, context in well_context.items():
        context["mean_perm_x_percentile_across_wells"] = percentile_rank(
            context.get("mean_perm_x"),
            all_well_perm_x,
        )
        context["mean_perm_y_percentile_across_wells"] = percentile_rank(
            context.get("mean_perm_y"),
            all_well_perm_y,
        )
        context["mean_perm_z_percentile_across_wells"] = percentile_rank(
            context.get("mean_perm_z"),
            all_well_perm_z,
        )

    return {
        "grid_dimensions": dims,
        "property_files": {
            name: {
                "source_file": prop["source_file"],
                "value_count": prop["value_count"],
                "min": prop["min"],
                "max": prop["max"],
                "mean": prop["mean"],
            }
            for name, prop in properties.items()
        },
        "well_count": len(well_context),
        "well_property_context": well_context,
    }


def inspect_grdecl_files(model_dir: Path = DEFAULT_MODEL_DIR) -> Dict[str, Any]:
    result = {}

    for property_name in ["perm_x", "perm_y", "perm_z"]:
        prop = read_grdecl_property(property_name, model_dir)
        result[property_name] = {
            "source_file": prop["source_file"],
            "value_count": prop["value_count"],
            "min": prop["min"],
            "max": prop["max"],
            "mean": prop["mean"],
        }

    return result

