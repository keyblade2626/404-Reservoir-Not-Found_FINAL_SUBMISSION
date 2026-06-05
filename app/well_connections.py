import re
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_WELL_CONNECTIONS_PATH = Path("data/sample_model/WELL_CONNECTIONS.IXF")


def _to_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _weighted_average(values: List[float], weights: List[float]) -> Optional[float]:
    if not values:
        return None

    positive_weights = [max(w, 0.0) for w in weights]
    total_weight = sum(positive_weights)

    if total_weight <= 1e-12:
        return sum(values) / len(values)

    return sum(v * w for v, w in zip(values, positive_weights)) / total_weight


def parse_well_connections_ixf(path: Path = DEFAULT_WELL_CONNECTIONS_PATH) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Well connections file not found: {path}")

    text = path.read_text(encoding="utf-8", errors="ignore")

    well_pattern = re.compile(
        r'WellDef\s+"(?P<well>[^"]+)"\s*\{(?P<body>.*?)\n\}',
        re.DOTALL | re.IGNORECASE,
    )

    table_pattern = re.compile(
        r'WellToCellConnections\s*\[(?P<table>.*?)\]',
        re.DOTALL | re.IGNORECASE,
    )

    cell_pattern = re.compile(
        r'\(\s*(?P<i>\d+)\s+(?P<j>\d+)\s+(?P<k>\d+)\s*\)\s+"(?P<completion>[^"]+)"(?P<rest>.*)$',
        re.IGNORECASE,
    )

    wells: Dict[str, Any] = {}

    for well_match in well_pattern.finditer(text):
        well_name = well_match.group("well")
        body = well_match.group("body")

        table_match = table_pattern.search(body)

        if not table_match:
            wells[well_name] = {
                "connections": [],
                "connection_count": 0,
                "open_connection_count": 0,
                "warning": "No WellToCellConnections table found.",
            }
            continue

        table = table_match.group("table")
        connections: List[Dict[str, Any]] = []

        for raw_line in table.splitlines():
            line = raw_line.strip()

            if not line.startswith("("):
                continue

            cell_match = cell_pattern.search(line)

            if not cell_match:
                continue

            i = int(cell_match.group("i"))
            j = int(cell_match.group("j"))
            k = int(cell_match.group("k"))
            completion = cell_match.group("completion")
            rest = cell_match.group("rest").strip()

            tokens = rest.split()

            segment_node = None
            status = None

            if len(tokens) >= 1:
                try:
                    segment_node = int(tokens[0])
                except Exception:
                    segment_node = None

            if len(tokens) >= 2:
                status = tokens[1].upper()

            numeric_values = []

            # After SegmentNode and Status, the line contains the numeric columns.
            for token in tokens[2:]:
                value = _to_float(token)
                if value is not None:
                    numeric_values.append(value)

            true_vertical_depth = numeric_values[0] if len(numeric_values) > 0 else None
            measured_depth = numeric_values[1] if len(numeric_values) > 1 else None
            wellbore_radius = numeric_values[2] if len(numeric_values) > 2 else None
            skin = numeric_values[3] if len(numeric_values) > 3 else None
            pi_multiplier = numeric_values[4] if len(numeric_values) > 4 else None
            pressure_equivalent_radius = numeric_values[5] if len(numeric_values) > 5 else None
            permeability_thickness = numeric_values[6] if len(numeric_values) > 6 else None
            transmissibility = numeric_values[7] if len(numeric_values) > 7 else None

            penetration_direction = tokens[-1] if tokens else None

            connections.append(
                {
                    "i": i,
                    "j": j,
                    "k": k,
                    "completion": completion,
                    "segment_node": segment_node,
                    "status": status,
                    "true_vertical_depth": true_vertical_depth,
                    "measured_depth": measured_depth,
                    "wellbore_radius": wellbore_radius,
                    "skin": skin,
                    "pi_multiplier": pi_multiplier,
                    "pressure_equivalent_radius": pressure_equivalent_radius,
                    "permeability_thickness": permeability_thickness,
                    "transmissibility": transmissibility,
                    "penetration_direction": penetration_direction,
                }
            )

        wells[well_name] = summarize_well_connections(well_name, connections)

    return {
        "source_file": str(path),
        "well_count": len(wells),
        "wells": wells,
    }


def summarize_well_connections(well_name: str, connections: List[Dict[str, Any]]) -> Dict[str, Any]:
    open_connections = [
        c for c in connections
        if str(c.get("status", "")).upper() == "OPEN"
    ]

    active_connections = open_connections if open_connections else connections

    i_values = [float(c["i"]) for c in active_connections]
    j_values = [float(c["j"]) for c in active_connections]
    k_values = [float(c["k"]) for c in active_connections]

    transmissibilities = [
        float(c.get("transmissibility") or 0.0)
        for c in active_connections
    ]

    perm_thickness_values = [
        float(c.get("permeability_thickness") or 0.0)
        for c in active_connections
    ]

    representative_i = _weighted_average(i_values, transmissibilities)
    representative_j = _weighted_average(j_values, transmissibilities)

    return {
        "well": well_name,
        "connections": connections,
        "connection_count": len(connections),
        "open_connection_count": len(open_connections),
        "representative_i": representative_i,
        "representative_j": representative_j,
        "mean_i": sum(i_values) / len(i_values) if i_values else None,
        "mean_j": sum(j_values) / len(j_values) if j_values else None,
        "min_i": min(i_values) if i_values else None,
        "max_i": max(i_values) if i_values else None,
        "min_j": min(j_values) if j_values else None,
        "max_j": max(j_values) if j_values else None,
        "min_k": min(k_values) if k_values else None,
        "max_k": max(k_values) if k_values else None,
        "total_transmissibility": sum(transmissibilities),
        "max_transmissibility": max(transmissibilities) if transmissibilities else None,
        "mean_transmissibility": (
            sum(transmissibilities) / len(transmissibilities)
            if transmissibilities else None
        ),
        "total_permeability_thickness": sum(perm_thickness_values),
        "mean_permeability_thickness": (
            sum(perm_thickness_values) / len(perm_thickness_values)
            if perm_thickness_values else None
        ),
        "trajectory_ij": [
            [c["i"], c["j"]]
            for c in active_connections
        ],
    }


def get_well_spatial_summary(path: Path = DEFAULT_WELL_CONNECTIONS_PATH) -> Dict[str, Any]:
    return parse_well_connections_ixf(path)
