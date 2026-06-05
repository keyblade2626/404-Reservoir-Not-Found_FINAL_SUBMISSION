from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]


# ==========================================================
# V380 PLOT INTENT ENGINE
# Smart resolver for property maps, distributions and simple
# operations between GRDECL properties.
# ==========================================================


STATIC_ALIASES = {
    "PORO": [
        "poro", "porosity", "porosita", "porosità",
    ],
    "PERM_X": [
        "perm x", "permx", "perm_x", "kx",
        "permeability x", "permeability along x", "permeability in x",
        "x permeability", "permeability direction x",
    ],
    "PERM_Y": [
        "perm y", "permy", "perm_y", "ky",
        "permeability y", "permeability along y", "permeability in y",
        "y permeability", "permeability direction y",
    ],
    "PERM_Z": [
        "perm z", "permz", "perm_z", "kz",
        "permeability z", "permeability along z", "permeability in z",
        "z permeability", "vertical permeability",
    ],
    "TRANX": [
        "tranx", "tran x", "transmissibility x", "transmissibility along x",
        "transmissibility in x", "x transmissibility",
    ],
    "TRANY": [
        "trany", "tran y", "transmissibility y", "transmissibility along y",
        "transmissibility in y", "y transmissibility",
    ],
    "TRANZ": [
        "tranz", "tran z", "transmissibility z", "transmissibility along z",
        "transmissibility in z", "z transmissibility",
    ],
}


DYNAMIC_ALIASES = {
    "SWAT": [
        "swat", "water saturation", "saturation water", "saturazione acqua",
    ],
    "SOIL": [
        "soil", "oil saturation", "saturation oil", "saturazione olio",
    ],
    "SGAS": [
        "sgas", "gas saturation", "saturation gas", "saturazione gas",
    ],
    "PRESSURE": [
        "pressure", "press", "pressione", "reservoir pressure",
    ],
}


DISPLAY_NAMES = {
    "PORO": "Porosity",
    "PERM_X": "Permeability X",
    "PERM_Y": "Permeability Y",
    "PERM_Z": "Permeability Z",
    "TRANX": "Transmissibility X",
    "TRANY": "Transmissibility Y",
    "TRANZ": "Transmissibility Z",
    "SWAT_INIT": "Initial Water Saturation",
    "SWAT_EOH": "End-of-History Water Saturation",
    "SOIL_INIT": "Initial Oil Saturation",
    "SOIL_EOH": "End-of-History Oil Saturation",
    "SGAS_INIT": "Initial Gas Saturation",
    "SGAS_EOH": "End-of-History Gas Saturation",
    "PRESSURE_INIT": "Initial Pressure",
    "PRESSURE_EOH": "End-of-History Pressure",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower().replace("_", " ").replace("-", " ")).strip()




# ==========================================================
# V412 DIAGNOSTIC INTENT BYPASS
# Prevent physical plot/map intent engine from capturing
# diagnostic bias/cluster/history-match questions.
# ==========================================================

def _is_holistic_diagnostic_query_v412(message: str) -> bool:
    msg = _norm(message)

    has_reservoir_signal = any(x in msg for x in [
        "wct", "water cut", "water-cut", "water",
        "gas", "gor", "gas oil ratio", "gas-oil ratio",
        "oil", "bhp", "pressure", "rate", "profile",
    ])

    has_diagnostic_intent = any(x in msg for x in [
        "bias", "cluster", "mismatch", "driver", "drivers",
        "weak", "weakest", "diagnostic", "diagnose",
        "history match", "history matching", "hm",
        "pattern", "evidence", "review first",
    ])

    return has_reservoir_signal and has_diagnostic_intent


def _is_plot_intent(message: str) -> bool:
    if _is_holistic_diagnostic_query_v412(message):
        return False

    msg = _norm(message)
    return any(x in msg for x in [
        "plot", "map", "mappa", "heatmap", "distribution", "histogram",
        "show me", "display", "draw", "fammi vedere", "mostrami",
        "difference", "change", "delta", "minus", "plus", "sum", "ratio",
    ])


def _is_distribution_intent(message: str) -> bool:
    if _is_holistic_diagnostic_query_v412(message):
        return False

    msg = _norm(message)
    return any(x in msg for x in [
        "distribution", "histogram", "hist", "distribuzione", "istogramma",
    ])


def _is_map_intent(message: str) -> bool:
    if _is_holistic_diagnostic_query_v412(message):
        return False

    msg = _norm(message)
    return any(x in msg for x in [
        "map", "mappa", "heatmap", "property map",
    ]) or not _is_distribution_intent(message)


def _detect_time_suffix(message: str) -> str:
    msg = _norm(message)

    if any(x in msg for x in [
        "final", "eoh", "end of history", "end history", "end", "last",
        "fine", "ultimo", "alla fine", "at final",
    ]):
        return "EOH"

    if any(x in msg for x in [
        "initial", "init", "start", "first", "iniziale", "inizio", "at initial",
    ]):
        return "INIT"

    # Default for dynamic map request is INIT unless the request asks for change/difference.
    return "INIT"


def _contains_any(msg: str, aliases: List[str]) -> bool:
    padded = f" {msg} "
    for alias in aliases:
        a = _norm(alias)
        if f" {a} " in padded or a in msg:
            return True
    return False


def _detect_base_property(message: str) -> Optional[str]:
    msg = _norm(message)

    # Specific static aliases first.
    for prop, aliases in STATIC_ALIASES.items():
        if _contains_any(msg, aliases):
            return prop

    # Generic permeability/transmissibility defaults.
    if "permeability" in msg or "perm" in msg:
        if any(x in msg for x in ["along y", "in y", " y ", "direction y"]):
            return "PERM_Y"
        if any(x in msg for x in ["along z", "in z", " z ", "vertical", "direction z"]):
            return "PERM_Z"
        return "PERM_X"

    if "transmissibility" in msg or "trasmissibil" in msg or "tran" in msg:
        if any(x in msg for x in ["along y", "in y", " y ", "direction y"]):
            return "TRANY"
        if any(x in msg for x in ["along z", "in z", " z ", "direction z"]):
            return "TRANZ"
        return "TRANX"

    for base, aliases in DYNAMIC_ALIASES.items():
        if _contains_any(msg, aliases):
            return base

    return None


def _to_property_name(base: str, message: str) -> str:
    base = str(base or "").upper()

    if base in STATIC_ALIASES:
        return base

    if base in DYNAMIC_ALIASES:
        suffix = _detect_time_suffix(message)
        return f"{base}_{suffix}"

    return base


def _is_difference_intent(message: str) -> bool:
    msg = _norm(message)
    return any(x in msg for x in [
        "difference", "diff", "delta", "change", "variation",
        "minus", "subtract", "subtracted", "meno", "differenza",
    ])


def _detect_binary_operator(message: str) -> Optional[str]:
    msg = _norm(message)

    if any(x in msg for x in [" plus ", " + ", "sum", "add", "somma"]):
        return "+"

    if any(x in msg for x in [" minus ", " - ", "difference", "diff", "delta", "change", "meno"]):
        return "-"

    if any(x in msg for x in [" divided by ", " / ", "ratio"]):
        return "/"

    if any(x in msg for x in [" times ", " * ", "multiply", "product"]):
        return "*"

    return None


def _detect_two_static_or_dynamic_props(message: str) -> List[str]:
    msg = _norm(message)
    found: List[str] = []

    for prop, aliases in STATIC_ALIASES.items():
        if _contains_any(msg, aliases):
            found.append(prop)

    for base, aliases in DYNAMIC_ALIASES.items():
        if _contains_any(msg, aliases):
            if _is_difference_intent(message):
                found.append(f"{base}_EOH")
                found.append(f"{base}_INIT")
            else:
                found.append(_to_property_name(base, message))

    # Deduplicate preserving order.
    out = []
    for x in found:
        if x not in out:
            out.append(x)

    return out


def _resolve_expression(message: str) -> Optional[Dict[str, Any]]:
    if not _is_plot_intent(message):
        return None

    msg = _norm(message)
    operator = _detect_binary_operator(message)

    base = _detect_base_property(message)

    # Dynamic difference/change: EOH - INIT.
    if base in DYNAMIC_ALIASES and _is_difference_intent(message):
        return {
            "kind": "expression",
            "operation": "-",
            "operands": [f"{base}_EOH", f"{base}_INIT"],
            "label": f"{base}_EOH - {base}_INIT",
            "intent": "distribution" if _is_distribution_intent(message) else "map",
        }

    # Explicit binary operation between two detected properties.
    props = _detect_two_static_or_dynamic_props(message)
    if operator and len(props) >= 2:
        return {
            "kind": "expression",
            "operation": operator,
            "operands": props[:2],
            "label": f"{props[0]} {operator} {props[1]}",
            "intent": "distribution" if _is_distribution_intent(message) else "map",
        }

    if base:
        prop = _to_property_name(base, message)
        return {
            "kind": "single",
            "operation": None,
            "operands": [prop],
            "label": prop,
            "intent": "distribution" if _is_distribution_intent(message) else "map",
        }

    return None


def _load_grid_dimensions() -> Optional[Dict[str, Any]]:
    candidates = list(ROOT.glob("**/grid_dimensions.json"))

    candidates = [
        p for p in candidates
        if "backup" not in str(p).lower()
        and "before_" not in str(p).lower()
    ]

    candidates = sorted(
        candidates,
        key=lambda p: (
            0 if "completed_run_imports" in str(p).lower() or "standardized_case" in str(p).lower() else 1,
            -p.stat().st_mtime,
        ),
    )

    for path in candidates:
        try:
            d = json.loads(path.read_text(encoding="utf-8", errors="ignore"))

            nx = int(d.get("nx") or d.get("NX") or d.get("i") or d.get("I"))
            ny = int(d.get("ny") or d.get("NY") or d.get("j") or d.get("J"))
            nz = int(d.get("nz") or d.get("NZ") or d.get("k") or d.get("K"))

            if nx > 0 and ny > 0 and nz > 0:
                return {"nx": nx, "ny": ny, "nz": nz, "path": str(path)}
        except Exception:
            continue

    return None


def _find_grdecl_file(prop: str) -> Optional[Path]:
    prop = str(prop or "").upper()

    exact_patterns = [
        f"{prop}.GRDECL",
        f"{prop}.grdecl",
    ]

    candidates: List[Path] = []

    for pattern in exact_patterns:
        candidates.extend(ROOT.glob(f"**/{pattern}"))

    # Only use fuzzy if exact failed.
    if not candidates:
        candidates.extend(ROOT.glob(f"**/*{prop}*.GRDECL"))
        candidates.extend(ROOT.glob(f"**/*{prop}*.grdecl"))

    candidates = [
        p for p in candidates
        if "backup" not in str(p).lower()
        and "before_" not in p.name.lower()
        and p.is_file()
    ]

    if not candidates:
        return None

    candidates = sorted(
        candidates,
        key=lambda p: (
            0 if "completed_run_imports" in str(p).lower() or "standardized_case" in str(p).lower() else 1,
            0 if p.name.upper() == f"{prop}.GRDECL" else 1,
            -p.stat().st_mtime,
        ),
    )

    return candidates[0]


def _parse_grdecl_values(path: Path) -> List[float]:
    text = path.read_text(encoding="utf-8", errors="ignore")

    # Remove comments.
    text = re.sub(r"--.*?$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"/", " ", text)

    tokens = re.split(r"\s+", text.strip())
    values: List[float] = []

    for token in tokens:
        if not token:
            continue

        # Skip property keyword tokens.
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", token):
            continue

        # GRDECL repeat syntax: 10*1.25
        m = re.match(r"^(\d+)\*([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)$", token)
        if m:
            count = int(m.group(1))
            val = float(m.group(2))
            values.extend([val] * count)
            continue

        # GRDECL repeat null: 10*
        m = re.match(r"^(\d+)\*$", token)
        if m:
            count = int(m.group(1))
            values.extend([0.0] * count)
            continue

        try:
            values.append(float(token))
        except Exception:
            continue

    return values


def _stats(values: List[float]) -> Dict[str, Optional[float]]:
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]

    if not clean:
        return {"min": None, "p50": None, "max": None, "mean": None, "n": 0}

    clean_sorted = sorted(clean)
    n = len(clean_sorted)

    def pct(q: float) -> float:
        idx = min(n - 1, max(0, int(q * (n - 1))))
        return clean_sorted[idx]

    return {
        "min": min(clean_sorted),
        "p50": pct(0.50),
        "max": max(clean_sorted),
        "mean": sum(clean_sorted) / n,
        "n": n,
    }


def _load_property_values(prop: str) -> Tuple[List[float], Dict[str, Any]]:
    path = _find_grdecl_file(prop)

    if not path:
        raise FileNotFoundError(f"Could not find GRDECL file for {prop}")

    values = _parse_grdecl_values(path)

    if not values:
        raise ValueError(f"Could not parse numeric values from {path.name}")

    return values, {"property": prop, "source_file": str(path), "stats": _stats(values)}


def _apply_operation(a: List[float], b: List[float], operation: str) -> List[Optional[float]]:
    n = min(len(a), len(b))
    out: List[Optional[float]] = []

    for x, y in zip(a[:n], b[:n]):
        try:
            x = float(x)
            y = float(y)

            if operation == "+":
                out.append(x + y)
            elif operation == "-":
                out.append(x - y)
            elif operation == "*":
                out.append(x * y)
            elif operation == "/":
                out.append(None if abs(y) < 1e-12 else x / y)
            else:
                out.append(None)
        except Exception:
            out.append(None)

    return out


def _values_to_vertical_average_map(values: List[float], grid: Dict[str, Any]) -> List[List[Optional[float]]]:
    nx = int(grid["nx"])
    ny = int(grid["ny"])
    nz = int(grid["nz"])

    n_expected = nx * ny * nz
    vals: List[Optional[float]] = list(values[:n_expected])

    if len(vals) < n_expected:
        vals.extend([None] * (n_expected - len(vals)))

    z: List[List[Optional[float]]] = []

    for j in range(ny):
        row: List[Optional[float]] = []

        for i in range(nx):
            col = []

            for k in range(nz):
                idx = k * nx * ny + j * nx + i
                v = vals[idx]

                try:
                    if v is not None:
                        fv = float(v)
                        if math.isfinite(fv):
                            col.append(fv)
                except Exception:
                    pass

            row.append(sum(col) / len(col) if col else None)

        z.append(row)

    return z


def _make_heatmap_chart(label: str, z: List[List[Optional[float]]], stats: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "plotly_chart",
        "title": f"{label} map",
        "data": [
            {
                "z": z,
                "type": "heatmap",
                "colorscale": [
                    [0.00, "#08306B"],   # dark blue = minimum
                    [0.15, "#2171B5"],
                    [0.30, "#41B6C4"],
                    [0.45, "#7FCDBB"],
                    [0.60, "#C7E9B4"],
                    [0.72, "#FFFFBF"],
                    [0.84, "#FDBF6F"],
                    [0.94, "#F03B20"],
                    [1.00, "#BD0026"],   # dark red = maximum
                ],
                "colorbar": {"title": label},
                "hovertemplate": "I=%{x}<br>J=%{y}<br>Value=%{z:.4g}<extra></extra>",
            }
        ],
        "layout": {
            "title": f"{label} map",
            "xaxis": {"title": "I index"},
            "yaxis": {"title": "J index", "autorange": "reversed"},
            "height": 620,
            "margin": {"l": 70, "r": 70, "t": 72, "b": 76},
        },
        "config": {
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True,
        },
        "meta": meta | {"stats": stats},
    }


def _make_histogram_chart(label: str, values: List[float], stats: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    max_points = 250000
    vals = [v for v in values if v is not None and math.isfinite(float(v))]

    if len(vals) > max_points:
        step = max(1, len(vals) // max_points)
        vals = vals[::step]

    return {
        "type": "plotly_chart",
        "title": f"{label} distribution",
        "data": [
            {
                "x": vals,
                "type": "histogram",
                "name": label,
                "nbinsx": 90,
                "opacity": 0.72,
            }
        ],
        "layout": {
            "title": f"{label} distribution",
            "xaxis": {"title": label},
            "yaxis": {"title": "Cell count"},
            "height": 560,
            "margin": {"l": 78, "r": 34, "t": 72, "b": 86},
        },
        "config": {
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True,
        },
        "meta": meta | {"stats": stats},
    }




# ==========================================================
# V381 STREAMLINE INTENT SUPPORT
# Handles requests like:
# - show me streamlines
# - plot streamlines
# - show streamlines for HW-28
# Supports CSV/JSON streamline artifacts if available.
# ==========================================================

def _is_streamline_intent(message: str) -> bool:
    msg = _norm(message)
    return any(x in msg for x in [
        "streamline", "streamlines", "stream line", "stream lines",
        "flight path", "flow path", "flow lines", "fluss", "linee di flusso"
    ])


def _extract_requested_well(message: str) -> Optional[str]:
    m = re.search(r"\b([A-Z]{1,6}-\d+[A-Z]?)\b", str(message or "").upper())
    return m.group(1) if m else None


def _find_streamline_files(well: Optional[str] = None) -> List[Path]:
    patterns = [
        "*streamline*.csv", "*streamlines*.csv",
        "*streamline*.json", "*streamlines*.json",
        "*STREAMLINE*.csv", "*STREAMLINES*.csv",
        "*STREAMLINE*.json", "*STREAMLINES*.json",
    ]

    files: List[Path] = []

    for pattern in patterns:
        files.extend(ROOT.glob(f"**/{pattern}"))

    files = [
        f for f in files
        if f.is_file()
        and "backup" not in str(f).lower()
        and "before_" not in f.name.lower()
    ]

    if well:
        w = well.upper()
        preferred = [f for f in files if w in f.name.upper() or w in str(f).upper()]
        if preferred:
            files = preferred

    files = sorted(
        files,
        key=lambda p: (
            0 if "completed_run_imports" in str(p).lower() or "standardized_case" in str(p).lower() else 1,
            -p.stat().st_mtime,
        ),
    )

    return files


def _read_streamline_table(path: Path) -> List[Dict[str, Any]]:
    import csv

    suffix = path.suffix.lower()

    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))

        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]

        if isinstance(data, dict):
            for key in ["streamlines", "lines", "points", "data", "rows"]:
                if isinstance(data.get(key), list):
                    return [x for x in data[key] if isinstance(x, dict)]

        return []

    rows: List[Dict[str, Any]] = []

    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        sample = f.read(4096)
        f.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t ")
        except Exception:
            dialect = csv.excel

        reader = csv.DictReader(f, dialect=dialect)

        for row in reader:
            if isinstance(row, dict):
                rows.append(row)

    return rows


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        s = str(value).strip()
        if not s or s.lower() in {"nan", "none", "null", "n/a"}:
            return None
        return float(s.replace(",", ""))
    except Exception:
        return None


def _pick_col(row: Dict[str, Any], names: List[str]) -> Optional[Any]:
    lower = {str(k).lower().strip(): k for k in row.keys()}

    for name in names:
        n = name.lower().strip()
        if n in lower:
            return row.get(lower[n])

    # fuzzy
    for k in row.keys():
        kl = str(k).lower().strip()
        for name in names:
            if name.lower().strip() in kl:
                return row.get(k)

    return None


def _build_streamline_plotly(rows: List[Dict[str, Any]], source_file: str, well: Optional[str] = None) -> Dict[str, Any]:
    # Try to support common column names:
    # x/y/z, i/j/k, cell_i/cell_j/cell_k, streamline_id, well, tof, flux/rate/weight
    traces_by_line: Dict[str, Dict[str, List[float]]] = {}

    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue

        if well:
            row_well = _pick_col(row, ["well", "well_name", "producer", "injector"])
            if row_well and well.upper() not in str(row_well).upper():
                continue

        x = _as_float(_pick_col(row, ["x", "i", "cell_i", "ix", "coord_x"]))
        y = _as_float(_pick_col(row, ["y", "j", "cell_j", "jy", "coord_y"]))
        z = _as_float(_pick_col(row, ["z", "k", "cell_k", "kz", "coord_z"]))

        if x is None or y is None:
            continue

        sid = _pick_col(row, ["streamline_id", "streamline", "line_id", "id", "sl_id"])
        sid = str(sid if sid is not None else "streamline")

        if sid not in traces_by_line:
            traces_by_line[sid] = {"x": [], "y": [], "z": []}

        traces_by_line[sid]["x"].append(x)
        traces_by_line[sid]["y"].append(y)

        if z is not None:
            traces_by_line[sid]["z"].append(z)

    if not traces_by_line:
        raise ValueError("No usable x/y or i/j streamline coordinates found.")

    use_3d = any(len(v["z"]) == len(v["x"]) and len(v["z"]) > 0 for v in traces_by_line.values())

    traces = []

    max_lines = 200
    for n, (sid, coords) in enumerate(traces_by_line.items()):
        if n >= max_lines:
            break

        if len(coords["x"]) < 2:
            continue

        if use_3d and len(coords["z"]) == len(coords["x"]):
            traces.append({
                "type": "scatter3d",
                "mode": "lines",
                "name": str(sid),
                "x": coords["x"],
                "y": coords["y"],
                "z": coords["z"],
                "line": {
                    "width": 3,
                    "colorscale": "Jet",
                },
                "showlegend": False,
            })
        else:
            traces.append({
                "type": "scatter",
                "mode": "lines",
                "name": str(sid),
                "x": coords["x"],
                "y": coords["y"],
                "line": {
                    "width": 2,
                    "color": "rgba(34,211,238,0.55)",
                },
                "showlegend": False,
            })

    title = f"Streamlines{f' - {well}' if well else ''}"

    if use_3d:
        layout = {
            "title": title,
            "scene": {
                "xaxis": {"title": "X / I"},
                "yaxis": {"title": "Y / J"},
                "zaxis": {"title": "Z / K"},
            },
            "height": 650,
            "margin": {"l": 0, "r": 0, "t": 70, "b": 0},
        }
    else:
        layout = {
            "title": title,
            "xaxis": {"title": "X / I index"},
            "yaxis": {"title": "Y / J index", "autorange": "reversed"},
            "height": 620,
            "margin": {"l": 70, "r": 40, "t": 72, "b": 76},
        }

    return {
        "type": "plotly_chart",
        "title": title,
        "data": traces,
        "layout": layout,
        "config": {
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True,
        },
        "meta": {
            "source_file": source_file,
            "well": well,
            "streamline_count_rendered": len(traces),
            "is_3d": use_3d,
        },
    }


def answer_streamline_intent_v381(message: str) -> Optional[Dict[str, Any]]:
    if not _is_streamline_intent(message):
        return None

    # V383 temporary guard:
    # Do not use the generic V382 parser because it converts the original
    # streamline visual payload into wrong continuous lines.
    # The correct renderer must be restored from app.streamline_visual_payloads.
    answer = (
        "I found the streamline request, but the generic parser is disabled because it renders the original "
        "streamline payload incorrectly. Use the dedicated streamline visual payload renderer instead."
    )
    return {
        "ok": False,
        "answer": answer,
        "message": answer,
        "response": answer,
        "source": "streamline_intent_v383_guard",
    }

    well = _extract_requested_well(message)
    files = _find_streamline_files(well=well)

    if not files:
        answer = (
            "I understood that you want a streamline plot, but I could not find streamline CSV/JSON artifacts. "
            "Expected files with names like streamlines.csv, STREAMLINES.json, or well-specific streamline files."
        )
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "streamline_intent_v381",
        }

    errors = []

    for path in files[:8]:
        try:
            rows = _read_streamline_table(path)
            if not rows:
                errors.append(f"{path.name}: no rows")
                continue

            chart = _build_streamline_plotly(rows, str(path), well=well)

            answer = (
                f"Created interactive streamline plot using {path.name}. "
                f"Rendered {chart.get('meta', {}).get('streamline_count_rendered')} streamline traces."
            )

            return {
                "ok": True,
                "answer": answer,
                "message": answer,
                "response": answer,
                "source": "streamline_intent_v381",
                "plotly_chart": chart,
                "image_url": None,
                "plot": {
                    "plot_type": "streamlines",
                    "source_file": str(path),
                    "well": well,
                    "interactive": True,
                    "meta": chart.get("meta", {}),
                },
            }

        except Exception as exc:
            errors.append(f"{path.name}: {exc}")

    answer = (
        "I found streamline candidate files, but could not build a plot from them. "
        "Details: " + " | ".join(errors[:5])
    )

    return {
        "ok": False,
        "answer": answer,
        "message": answer,
        "response": answer,
        "source": "streamline_intent_v381",
        "errors": errors,
    }



def answer_plot_intent(message: str) -> Optional[Dict[str, Any]]:
    v381_streamlines = answer_streamline_intent_v381(message)
    if v381_streamlines is not None:
        return v381_streamlines

    intent = _resolve_expression(message)

    if intent is None:
        return None

    try:
        grid = _load_grid_dimensions()
        if not grid and intent["intent"] == "map":
            answer = "I understood the plot request, but I could not find grid_dimensions.json for map reshaping."
            return {
                "ok": False,
                "answer": answer,
                "message": answer,
                "response": answer,
                "source": "plot_intent_engine_v380",
            }

        operands = intent["operands"]
        operation = intent.get("operation")

        source_info = []

        if operation is None:
            values, info = _load_property_values(operands[0])
            label = DISPLAY_NAMES.get(operands[0], operands[0])
            source_info.append(info)
        else:
            values_a, info_a = _load_property_values(operands[0])
            values_b, info_b = _load_property_values(operands[1])
            values = _apply_operation(values_a, values_b, operation)
            label = intent["label"]
            source_info.extend([info_a, info_b])

        stats = _stats([v for v in values if v is not None])

        meta = {
            "intent": intent,
            "source_info": source_info,
            "grid_dimensions": grid,
        }

        if intent["intent"] == "distribution":
            chart = _make_histogram_chart(label, values, stats, meta)
            plot_type = "distribution"
        else:
            z = _values_to_vertical_average_map(values, grid)
            chart = _make_heatmap_chart(label, z, stats, meta)
            plot_type = "map"

        quality_note = ""

        if stats.get("n", 0) > 0 and stats.get("min") == stats.get("max"):
            quality_note = (
                f" Warning: all parsed values are constant ({stats.get('min')}). "
                "This may indicate a true constant property or the wrong GRDECL source file."
            )

        answer = (
            f"Created interactive {plot_type} for {label}. "
            f"Min={stats.get('min'):.4g}, P50={stats.get('p50'):.4g}, Max={stats.get('max'):.4g}. "
            f"Source: " + "; ".join(Path(x["source_file"]).name for x in source_info) + "."
            + quality_note
        )

        return {
            "ok": True,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "plot_intent_engine_v380",
            "plotly_chart": chart,
            "image_url": None,
            "plot": {
                "plot_type": plot_type,
                "label": label,
                "intent": intent,
                "stats": stats,
                "source_info": source_info,
                "grid_dimensions": grid,
                "interactive": True,
            },
        }

    except Exception as exc:
        answer = f"I understood the plot request, but could not build it: {exc}"
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "plot_intent_engine_v380",
            "error": str(exc),
        }



# ==========================================================
# V382 ROBUST STREAMLINE JSON PAYLOAD PARSER
# Handles:
# - JSON already containing plotly_chart
# - JSON containing Plotly data/layout
# - nested streamlines / points / segments
# - connection-style JSON with cell coordinates
# ==========================================================

def _v382_dedupe_paths(paths: List[Path]) -> List[Path]:
    out = []
    seen = set()

    for path in paths:
        try:
            key = str(path.resolve()).lower()
        except Exception:
            key = str(path).lower()

        if key not in seen:
            seen.add(key)
            out.append(path)

    return out


def _v382_find_first_plotly_payload(obj: Any) -> Optional[Dict[str, Any]]:
    """
    Recursively find an existing Plotly payload.
    Accepts:
    - {"plotly_chart": {"data": [...], "layout": {...}}}
    - {"data": [...], "layout": {...}}
    - {"type": "plotly_chart", "data": [...]}
    """
    if isinstance(obj, dict):
        pc = obj.get("plotly_chart")
        if isinstance(pc, dict) and isinstance(pc.get("data"), list):
            return pc

        if isinstance(obj.get("data"), list) and (
            "layout" in obj or obj.get("type") == "plotly_chart"
        ):
            return {
                "type": "plotly_chart",
                "title": obj.get("title") or obj.get("layout", {}).get("title") or "Streamlines",
                "data": obj.get("data"),
                "layout": obj.get("layout", {}),
                "config": obj.get("config", {
                    "responsive": True,
                    "displaylogo": False,
                    "scrollZoom": True,
                }),
                "meta": obj.get("meta", {}),
            }

        for v in obj.values():
            found = _v382_find_first_plotly_payload(v)
            if found:
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = _v382_find_first_plotly_payload(item)
            if found:
                return found

    return None


def _v382_collect_candidate_rows(obj: Any) -> List[Dict[str, Any]]:
    """
    Recursively collect dictionaries that may represent points or segments.
    """
    rows: List[Dict[str, Any]] = []

    def walk(x: Any):
        if isinstance(x, dict):
            keys = {str(k).lower() for k in x.keys()}

            coordinate_like = any(k in keys for k in [
                "x", "y", "z", "i", "j", "k",
                "cell_i", "cell_j", "cell_k",
                "from_i", "from_j", "to_i", "to_j",
                "start_i", "start_j", "end_i", "end_j",
            ])

            if coordinate_like:
                rows.append(x)

            for v in x.values():
                walk(v)

        elif isinstance(x, list):
            for item in x:
                walk(item)

    walk(obj)
    return rows


def _v382_try_build_plotly_from_json(path: Path, well: Optional[str] = None) -> Optional[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))

    existing = _v382_find_first_plotly_payload(data)

    if existing:
        chart = dict(existing)
        chart["type"] = "plotly_chart"
        chart["title"] = chart.get("title") or "Streamlines"
        chart["layout"] = chart.get("layout") or {}
        chart["layout"]["title"] = chart["layout"].get("title") or chart["title"]
        chart["layout"]["height"] = chart["layout"].get("height") or 650
        chart["config"] = chart.get("config") or {
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True,
        }
        chart["meta"] = chart.get("meta") or {}
        chart["meta"]["source_file"] = str(path)
        chart["meta"]["parser"] = "existing_plotly_payload_v382"
        return chart

    rows = _v382_collect_candidate_rows(data)

    if not rows:
        return None

    return _v382_build_streamline_plotly_from_rows_or_segments(rows, str(path), well=well)


def _v382_build_streamline_plotly_from_rows_or_segments(
    rows: List[Dict[str, Any]],
    source_file: str,
    well: Optional[str] = None
) -> Dict[str, Any]:
    """
    Supports both point rows and segment rows.

    Point format:
      x,y,z or i,j,k + streamline_id

    Segment format:
      from_i,from_j,from_k,to_i,to_j,to_k
      start_i,start_j,start_k,end_i,end_j,end_k
    """
    traces = []
    grouped: Dict[str, Dict[str, List[float]]] = {}

    def get(row, names):
        return _pick_col(row, names)

    for idx, row in enumerate(rows):
        if well:
            row_well = get(row, ["well", "well_name", "producer", "injector"])
            if row_well and well.upper() not in str(row_well).upper():
                continue

        # Segment style first.
        x1 = _as_float(get(row, ["from_x", "x1", "start_x", "from_i", "i1", "start_i"]))
        y1 = _as_float(get(row, ["from_y", "y1", "start_y", "from_j", "j1", "start_j"]))
        z1 = _as_float(get(row, ["from_z", "z1", "start_z", "from_k", "k1", "start_k"]))

        x2 = _as_float(get(row, ["to_x", "x2", "end_x", "to_i", "i2", "end_i"]))
        y2 = _as_float(get(row, ["to_y", "y2", "end_y", "to_j", "j2", "end_j"]))
        z2 = _as_float(get(row, ["to_z", "z2", "end_z", "to_k", "k2", "end_k"]))

        if x1 is not None and y1 is not None and x2 is not None and y2 is not None:
            sid = get(row, ["streamline_id", "streamline", "line_id", "id", "sl_id"])
            sid = str(sid if sid is not None else f"segment_{idx}")

            if z1 is not None and z2 is not None:
                traces.append({
                    "type": "scatter3d",
                    "mode": "lines",
                    "name": sid,
                    "x": [x1, x2],
                    "y": [y1, y2],
                    "z": [z1, z2],
                    "line": {"width": 3, "color": "rgba(34,211,238,0.65)"},
                    "showlegend": False,
                })
            else:
                traces.append({
                    "type": "scatter",
                    "mode": "lines",
                    "name": sid,
                    "x": [x1, x2],
                    "y": [y1, y2],
                    "line": {"width": 2, "color": "rgba(34,211,238,0.60)"},
                    "showlegend": False,
                })

            continue

        # Point style.
        x = _as_float(get(row, ["x", "i", "cell_i", "ix", "coord_x"]))
        y = _as_float(get(row, ["y", "j", "cell_j", "jy", "coord_y"]))
        z = _as_float(get(row, ["z", "k", "cell_k", "kz", "coord_z"]))

        if x is None or y is None:
            continue

        sid = get(row, ["streamline_id", "streamline", "line_id", "id", "sl_id"])
        sid = str(sid if sid is not None else "streamline")

        if sid not in grouped:
            grouped[sid] = {"x": [], "y": [], "z": []}

        grouped[sid]["x"].append(x)
        grouped[sid]["y"].append(y)

        if z is not None:
            grouped[sid]["z"].append(z)

    # Add grouped point traces.
    max_grouped = 200

    for n, (sid, coords) in enumerate(grouped.items()):
        if n >= max_grouped:
            break

        if len(coords["x"]) < 2:
            continue

        if len(coords["z"]) == len(coords["x"]) and len(coords["z"]) > 0:
            traces.append({
                "type": "scatter3d",
                "mode": "lines",
                "name": str(sid),
                "x": coords["x"],
                "y": coords["y"],
                "z": coords["z"],
                "line": {"width": 3, "color": "rgba(34,211,238,0.65)"},
                "showlegend": False,
            })
        else:
            traces.append({
                "type": "scatter",
                "mode": "lines",
                "name": str(sid),
                "x": coords["x"],
                "y": coords["y"],
                "line": {"width": 2, "color": "rgba(34,211,238,0.60)"},
                "showlegend": False,
            })

    if not traces:
        raise ValueError("No usable point or segment coordinates found in nested JSON payload.")

    use_3d = any(t.get("type") == "scatter3d" for t in traces)

    title = f"Streamlines{f' - {well}' if well else ''}"

    if use_3d:
        layout = {
            "title": title,
            "scene": {
                "xaxis": {"title": "X / I"},
                "yaxis": {"title": "Y / J"},
                "zaxis": {"title": "Z / K"},
            },
            "height": 650,
            "margin": {"l": 0, "r": 0, "t": 70, "b": 0},
        }
    else:
        layout = {
            "title": title,
            "xaxis": {"title": "X / I index"},
            "yaxis": {"title": "Y / J index", "autorange": "reversed"},
            "height": 620,
            "margin": {"l": 70, "r": 40, "t": 72, "b": 76},
        }

    return {
        "type": "plotly_chart",
        "title": title,
        "data": traces[:300],
        "layout": layout,
        "config": {
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True,
        },
        "meta": {
            "source_file": source_file,
            "well": well,
            "streamline_count_rendered": len(traces[:300]),
            "is_3d": use_3d,
            "parser": "nested_json_rows_or_segments_v382",
        },
    }


# Override previous streamline answer function with robust JSON support.
def answer_streamline_intent_v381(message: str) -> Optional[Dict[str, Any]]:
    if not _is_streamline_intent(message):
        return None

    well = _extract_requested_well(message)
    files = _v382_dedupe_paths(_find_streamline_files(well=well))

    if not files:
        answer = (
            "I understood that you want a streamline plot, but I could not find streamline CSV/JSON artifacts. "
            "Expected files with names like streamlines.csv, STREAMLINES.json, or well-specific streamline files."
        )
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "streamline_intent_v382",
        }

    errors = []

    for path in files[:12]:
        try:
            chart = None

            if path.suffix.lower() == ".json":
                chart = _v382_try_build_plotly_from_json(path, well=well)
            else:
                rows = _read_streamline_table(path)
                if rows:
                    chart = _v382_build_streamline_plotly_from_rows_or_segments(rows, str(path), well=well)

            if not chart:
                errors.append(f"{path.name}: no usable Plotly/data/coordinates found")
                continue

            answer = (
                f"Created interactive streamline plot using {path.name}. "
                f"Rendered {chart.get('meta', {}).get('streamline_count_rendered', len(chart.get('data', [])))} streamline traces."
            )

            return {
                "ok": True,
                "answer": answer,
                "message": answer,
                "response": answer,
                "source": "streamline_intent_v382",
                "plotly_chart": chart,
                "image_url": None,
                "plot": {
                    "plot_type": "streamlines",
                    "source_file": str(path),
                    "well": well,
                    "interactive": True,
                    "meta": chart.get("meta", {}),
                },
            }

        except Exception as exc:
            errors.append(f"{path.name}: {exc}")

    answer = (
        "I found streamline candidate files, but could not build a plot from them. "
        "Details: " + " | ".join(errors[:8])
    )

    return {
        "ok": False,
        "answer": answer,
        "message": answer,
        "response": answer,
        "source": "streamline_intent_v382",
        "errors": errors,
    }




# ==========================================================
# V383 DEDICATED STREAMLINE OVERLAY RENDERER
# Uses app.streamline_visual_payloads.build_streamline_visual_payload()
# and renders:
# - background GRDECL property map, default TRANX
# - streamlines from payload["lines"][].points[i,j]
# - well markers from payload["wells"]
# Supports initial/final/compare and "over <property>".
# ==========================================================

def _v383_detect_streamline_time(message: str) -> str:
    msg = _norm(message)

    if any(x in msg for x in [
        "compare", "comparison", "initial vs final", "init vs final",
        "start vs end", "beginning vs end", "inizio vs fine"
    ]):
        return "compare"

    if any(x in msg for x in [
        "initial", "init", "start", "beginning", "boh", "inizio", "iniziale"
    ]):
        return "initial"

    if any(x in msg for x in [
        "final", "eoh", "end", "last", "fine", "finale", "end of history"
    ]):
        return "final"

    return "final"


def _v383_detect_background_property(message: str) -> str:
    """
    Background for streamline overlay.
    Default is TRANX / transmissibility.
    """
    msg = _norm(message)

    # If user says "over X", still the global property detector catches X.
    base = _detect_base_property(message)

    if base:
        if base in DYNAMIC_ALIASES:
            return _to_property_name(base, message)
        return base

    # Default requested by user: transmissibility.
    return "TRANX"


def _v383_property_map_for_background(prop: str):
    """
    Return z map and source info for background property.
    Uses existing V380 GRDECL loader and vertical-average map.
    """
    grid = _load_grid_dimensions()

    if not grid:
        raise ValueError("grid_dimensions.json not found")

    values, info = _load_property_values(prop)
    z = _values_to_vertical_average_map(values, grid)
    stats = _stats([v for v in values if v is not None])

    return z, grid, info, stats


def _v383_line_style(snapshot: str):
    if snapshot == "initial":
        return {
            "color": "rgba(255,255,255,0.74)",
            "width": 1.4,
            "dash": "dot",
        }

    if snapshot == "compare_initial":
        return {
            "color": "rgba(255,255,255,0.68)",
            "width": 1.25,
            "dash": "dot",
        }

    if snapshot == "compare_final":
        return {
            "color": "rgba(0,0,0,0.65)",
            "width": 1.45,
            "dash": "solid",
        }

    return {
        "color": "rgba(0,0,0,0.72)",
        "width": 1.45,
        "dash": "solid",
    }


def _v383_payload_to_streamline_traces(payload: Dict[str, Any], snapshot: str, max_lines: int = 450) -> List[Dict[str, Any]]:
    traces = []

    lines = payload.get("lines") or []

    style = _v383_line_style(snapshot)
    label = payload.get("streamline_snapshot_label") or snapshot

    for idx, line in enumerate(lines[:max_lines]):
        pts = line.get("points") or []

        x = []
        y = []

        for pt in pts:
            try:
                i = pt.get("i")
                j = pt.get("j")

                if i is None or j is None:
                    continue

                x.append(float(i))
                y.append(float(j))
            except Exception:
                continue

        if len(x) < 2:
            continue

        strength = line.get("strength")

        # Keep opacity reasonably visible, but not dominant.
        opacity = 0.45
        try:
            if strength is not None:
                opacity = min(0.85, max(0.25, 0.25 + 0.45 * float(strength)))
        except Exception:
            pass

        traces.append({
            "type": "scatter",
            "mode": "lines",
            "name": label if idx == 0 else label,
            "x": x,
            "y": y,
            "line": {
                "color": style["color"],
                "width": style["width"],
                "dash": style["dash"],
            },
            "opacity": opacity,
            "hoverinfo": "skip",
            "hovertemplate": None,
            "showlegend": idx == 0,
            "legendgroup": label,
        })

    return traces


def _v383_well_marker_traces(payloads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Use wells from the first payload that has wells.
    wells = []

    for payload in payloads:
        wells = payload.get("wells") or []
        if wells:
            break

    if not wells:
        return []

    prod_x, prod_y, prod_text = [], [], []
    inj_x, inj_y, inj_text = [], [], []

    for w in wells:
        try:
            x = float(w.get("i"))
            y = float(w.get("j"))
        except Exception:
            continue

        name = str(w.get("well") or "")

        is_inj = bool(w.get("active_injector")) or bool(w.get("injector_candidate"))
        is_prod = bool(w.get("active_producer")) or bool(w.get("producer_candidate"))

        if is_inj and not is_prod:
            inj_x.append(x)
            inj_y.append(y)
            inj_text.append(name)
        else:
            prod_x.append(x)
            prod_y.append(y)
            prod_text.append(name)

    traces = []

    if prod_x:
        traces.append({
            "type": "scatter",
            "mode": "markers+text",
            "name": "Producers",
            "x": prod_x,
            "y": prod_y,
            "text": prod_text,
            "textposition": "top center",
            "marker": {
                "size": 9,
                "color": "#B91C1C",
                "line": {"color": "white", "width": 1.2},
                "symbol": "circle",
            },
            "textfont": {"color": "#EAF2FF", "size": 10},
            "hovertemplate": "%{text}<extra>Producer</extra>",
        })

    if inj_x:
        traces.append({
            "type": "scatter",
            "mode": "markers+text",
            "name": "Injectors",
            "x": inj_x,
            "y": inj_y,
            "text": inj_text,
            "textposition": "top center",
            "marker": {
                "size": 10,
                "color": "#22D3EE",
                "line": {"color": "white", "width": 1.2},
                "symbol": "diamond",
            },
            "textfont": {"color": "#EAF2FF", "size": 10},
            "hovertemplate": "%{text}<extra>Injector</extra>",
        })

    return traces


def _v383_build_streamline_overlay_chart(
    payloads: List[Dict[str, Any]],
    background_prop: str,
    title_suffix: str,
) -> Dict[str, Any]:
    z, grid, prop_info, stats = _v383_property_map_for_background(background_prop)

    traces = [
        {
            "z": z,
            "type": "heatmap",
            "name": background_prop,
            "colorscale": [
                [0.00, "#08306B"],
                [0.15, "#2171B5"],
                [0.30, "#41B6C4"],
                [0.45, "#7FCDBB"],
                [0.60, "#C7E9B4"],
                [0.72, "#FFFFBF"],
                [0.84, "#FDBF6F"],
                [0.94, "#F03B20"],
                [1.00, "#BD0026"],
            ],
            "colorbar": {"title": background_prop},
            "hovertemplate": "I=%{x}<br>J=%{y}<br>" + background_prop + "=%{z:.4g}<extra></extra>",
        }
    ]

    for pld in payloads:
        snap = str(pld.get("_v383_snapshot_key") or pld.get("requested_streamline_time") or "final")

        if snap == "initial":
            trace_key = "compare_initial" if len(payloads) > 1 else "initial"
        elif snap == "final":
            trace_key = "compare_final" if len(payloads) > 1 else "final"
        else:
            trace_key = snap

        traces.extend(_v383_payload_to_streamline_traces(pld, trace_key))

    traces.extend(_v383_well_marker_traces(payloads))

    title = f"Streamlines over {background_prop} - {title_suffix}"

    return {
        "type": "plotly_chart",
        "title": title,
        "data": traces,
        "layout": {
            "title": title,
            "xaxis": {"title": "I index"},
            "yaxis": {"title": "J index", "autorange": "reversed"},
            "height": 680,
            "margin": {"l": 70, "r": 70, "t": 76, "b": 76},
            "legend": {
                "orientation": "h",
                "y": -0.16,
                "x": 0,
            },
        },
        "config": {
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True,
        },
        "meta": {
            "background_property": background_prop,
            "background_source_file": prop_info.get("source_file"),
            "background_stats": stats,
            "grid_dimensions": grid,
            "streamline_payloads": [
                {
                    "snapshot": p.get("requested_streamline_time"),
                    "label": p.get("streamline_snapshot_label"),
                    "line_count": p.get("line_count"),
                    "used_files": p.get("used_files"),
                }
                for p in payloads
            ],
            "renderer": "v383_streamline_overlay",
        },
    }


def answer_streamline_intent_v381(message: str) -> Optional[Dict[str, Any]]:
    """
    Override bad V382 generic renderer.
    Use dedicated streamline_visual_payloads builder and overlay on GRDECL property.
    """
    if not _is_streamline_intent(message):
        return None

    try:
        from app.streamline_visual_payloads import build_streamline_visual_payload

        time_key = _v383_detect_streamline_time(message)
        background_prop = _v383_detect_background_property(message)

        payloads = []

        if time_key == "compare":
            p_init = build_streamline_visual_payload(max_lines=800, time_key="initial")
            p_init["_v383_snapshot_key"] = "initial"

            p_final = build_streamline_visual_payload(max_lines=800, time_key="final")
            p_final["_v383_snapshot_key"] = "final"

            payloads = [p_init, p_final]
            title_suffix = "Initial vs End of History"

        else:
            pld = build_streamline_visual_payload(max_lines=800, time_key=time_key)
            pld["_v383_snapshot_key"] = time_key
            payloads = [pld]
            title_suffix = pld.get("streamline_snapshot_label") or time_key

        usable_payloads = [
            p for p in payloads
            if p.get("ok") and (p.get("lines") or [])
        ]

        if not usable_payloads:
            msg = " | ".join(str(p.get("message") or "No lines") for p in payloads)
            answer = f"I understood the streamline request, but no usable streamline lines were generated. {msg}"
            return {
                "ok": False,
                "answer": answer,
                "message": answer,
                "response": answer,
                "source": "streamline_intent_v383_overlay",
                "payload_status": payloads,
            }

        chart = _v383_build_streamline_overlay_chart(usable_payloads, background_prop, title_suffix)

        total_lines = sum(int(p.get("line_count") or len(p.get("lines") or [])) for p in usable_payloads)

        answer = (
            f"Created interactive streamline overlay on {background_prop}. "
            f"Snapshot: {title_suffix}. Rendered {total_lines} streamline lines. "
            f"Background source: {Path(chart['meta'].get('background_source_file', '')).name}."
        )

        return {
            "ok": True,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "streamline_intent_v383_overlay",
            "plotly_chart": chart,
            "image_url": None,
            "plot": {
                "plot_type": "streamlines_overlay",
                "background_property": background_prop,
                "snapshot": time_key,
                "streamline_count": total_lines,
                "interactive": True,
                "meta": chart.get("meta", {}),
            },
        }

    except Exception as exc:
        answer = f"I understood the streamline request, but could not build the overlay: {exc}"
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "streamline_intent_v383_overlay",
            "error": str(exc),
        }




# ==========================================================
# V386 CONDITIONAL MAPS + NEAR-WELL SPATIAL FILTERS
# Supports:
# - show cells where SWAT > 0.4
# - show cells where pressure final < 2500
# - show PERM_X only near HW-28
# - show TRANX near HW-32 within 15 cells
# ==========================================================

def _v386_extract_well_name(message: str) -> Optional[str]:
    m = re.search(r"\b([A-Z]{1,8}-\d+[A-Z]?)\b", str(message or "").upper())
    return m.group(1) if m else None


def _v386_extract_radius(message: str, default_radius: float = 12.0) -> float:
    msg = _norm(message)

    patterns = [
        r"within\s+(\d+(?:\.\d+)?)\s*(?:cells|cell|grid|blocks|block)?",
        r"radius\s+(\d+(?:\.\d+)?)",
        r"nearby\s+(\d+(?:\.\d+)?)",
        r"around\s+\w+-\d+\s+(\d+(?:\.\d+)?)",
    ]

    for pat in patterns:
        m = re.search(pat, msg)
        if m:
            try:
                return max(1.0, float(m.group(1)))
            except Exception:
                pass

    return default_radius


def _v386_load_well_locations() -> List[Dict[str, Any]]:
    candidates = [
        ROOT / "artifacts" / "dashboard" / "hm_map_payload.json",
        ROOT / "artifacts" / "dashboard" / "streamline_visual_payload.json",
    ]

    for path in candidates:
        try:
            if path.exists():
                d = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
                wells = d.get("wells") or []
                if wells:
                    return wells
        except Exception:
            pass

    try:
        from app.streamline_visual_payloads import get_hm_wells
        wells = get_hm_wells()
        if wells:
            return wells
    except Exception:
        pass

    return []


def _v386_find_well_location(well: str) -> Optional[Dict[str, Any]]:
    target = str(well or "").upper().strip()

    for w in _v386_load_well_locations():
        name = str(w.get("well") or w.get("name") or "").upper().strip()
        if name == target:
            try:
                return {
                    "well": name,
                    "i": float(w.get("i")),
                    "j": float(w.get("j")),
                    "raw": w,
                }
            except Exception:
                return None

    return None


def _v386_compare_value(x: float, op: str, threshold: float) -> bool:
    if op == ">":
        return x > threshold
    if op == ">=":
        return x >= threshold
    if op == "<":
        return x < threshold
    if op == "<=":
        return x <= threshold
    if op in ["=", "=="]:
        return abs(x - threshold) <= 1e-12
    if op in ["!=", "<>"]:
        return abs(x - threshold) > 1e-12
    return False


def _v386_detect_condition(message: str) -> Optional[Dict[str, Any]]:
    msg = _norm(message)

    if not any(x in msg for x in [" where ", "cells where", "cell where", "greater than", "less than", "above", "below", ">", "<"]):
        return None

    base = _detect_base_property(message)
    if not base:
        return None

    prop = _to_property_name(base, message)

    # Normalize verbal operators.
    verbal_patterns = [
        (r"(?:greater than|above|higher than)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", ">"),
        (r"(?:less than|below|lower than)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", "<"),
        (r"(?:equal to|equals)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", "=="),
    ]

    for pat, op in verbal_patterns:
        m = re.search(pat, msg)
        if m:
            return {
                "kind": "conditional_mask",
                "property": prop,
                "operator": op,
                "threshold": float(m.group(1)),
                "intent": "map",
                "label": f"Cells where {prop} {op} {float(m.group(1)):g}",
            }

    # Symbolic operators.
    m = re.search(r"(?:where\s+)?[a-z0-9_\s]*\s*(>=|<=|>|<|==|=|!=|<>)\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", msg)

    if m:
        return {
            "kind": "conditional_mask",
            "property": prop,
            "operator": m.group(1),
            "threshold": float(m.group(2)),
            "intent": "map",
            "label": f"Cells where {prop} {m.group(1)} {float(m.group(2)):g}",
        }

    return None


def _v386_detect_near_well_filter(message: str) -> Optional[Dict[str, Any]]:
    msg = _norm(message)

    well = _v386_extract_well_name(message)
    if not well:
        return None

    if not any(x in msg for x in [" near ", "around", "close to", "nearby", "only near", "within"]):
        return None

    base = _detect_base_property(message)

    if base:
        prop = _to_property_name(base, message)
    else:
        # Default reservoir-engineering context.
        prop = "TRANX"

    radius = _v386_extract_radius(message)

    return {
        "kind": "near_well_filter",
        "property": prop,
        "well": well,
        "radius": radius,
        "intent": "map",
        "label": f"{prop} near {well} within {radius:g} cells",
    }


def _v386_mask_values_by_condition(values: List[float], grid: Dict[str, Any], op: str, threshold: float) -> List[Optional[float]]:
    """
    Return 3D flat mask values, 1 where condition is true, 0 where false.
    Later vertical averaging gives fraction of K layers satisfying condition.
    """
    out: List[Optional[float]] = []

    for v in values:
        try:
            x = float(v)
            if math.isfinite(x):
                out.append(1.0 if _v386_compare_value(x, op, threshold) else 0.0)
            else:
                out.append(None)
        except Exception:
            out.append(None)

    return out


def _v386_apply_near_well_mask_to_2d_map(
    z: List[List[Optional[float]]],
    well_i: float,
    well_j: float,
    radius: float,
) -> List[List[Optional[float]]]:
    out = []

    r2 = radius * radius

    for j, row in enumerate(z):
        out_row = []

        for i, value in enumerate(row):
            # Plotly heatmap x/y are 0-based indices, while reservoir I/J may be 1-based.
            # The payload wells are usually I/J cell coordinates, so compare against i+1/j+1.
            di = (i + 1) - well_i
            dj = (j + 1) - well_j

            if di * di + dj * dj <= r2:
                out_row.append(value)
            else:
                out_row.append(None)

        out.append(out_row)

    return out


def _v386_make_near_well_marker_trace(well_loc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "scatter",
        "mode": "markers+text",
        "name": well_loc["well"],
        "x": [well_loc["i"]],
        "y": [well_loc["j"]],
        "text": [well_loc["well"]],
        "textposition": "top center",
        "marker": {
            "size": 13,
            "color": "#FFFFFF",
            "line": {"color": "#B91C1C", "width": 2.4},
            "symbol": "circle",
        },
        "textfont": {"color": "#EAF2FF", "size": 12},
        "hovertemplate": "Well=%{text}<br>I=%{x}<br>J=%{y}<extra></extra>",
    }


def _v386_answer_condition_mask(message: str) -> Optional[Dict[str, Any]]:
    cond = _v386_detect_condition(message)
    if not cond:
        return None

    prop = cond["property"]
    op = cond["operator"]
    threshold = cond["threshold"]

    grid = _load_grid_dimensions()

    if not grid:
        answer = "I understood the conditional map request, but grid_dimensions.json was not found."
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "plot_intent_engine_v386_condition",
        }

    values, info = _load_property_values(prop)
    mask_values = _v386_mask_values_by_condition(values, grid, op, threshold)
    z = _values_to_vertical_average_map(mask_values, grid)

    stats = _stats([v for v in mask_values if v is not None])

    label = cond["label"]

    chart = _make_heatmap_chart(label, z, stats, {
        "intent": cond,
        "source_info": [info],
        "grid_dimensions": grid,
        "map_method": "vertical_fraction_of_layers_satisfying_condition",
    })

    # Override colorbar title/hover for conditional mask.
    try:
        chart["data"][0]["colorbar"] = {"title": "Fraction of K layers"}
        chart["data"][0]["hovertemplate"] = (
            "I=%{x}<br>J=%{y}<br>Fraction satisfying condition=%{z:.3f}<extra></extra>"
        )
    except Exception:
        pass

    pct = None
    try:
        pct = 100.0 * (sum(v for v in mask_values if v is not None) / len([v for v in mask_values if v is not None]))
    except Exception:
        pass

    if pct is not None:
        answer = (
            f"Created conditional map for {prop} {op} {threshold:g}. "
            f"Approximately {pct:.1f}% of valid grid cells/layers satisfy the condition. "
            f"Displayed map is the vertical fraction over K layers."
        )
    else:
        answer = (
            f"Created conditional map for {prop} {op} {threshold:g}. "
            "Displayed map is the vertical fraction over K layers."
        )

    return {
        "ok": True,
        "answer": answer,
        "message": answer,
        "response": answer,
        "source": "plot_intent_engine_v386_condition",
        "plotly_chart": chart,
        "image_url": None,
        "plot": {
            "plot_type": "conditional_map",
            "property": prop,
            "operator": op,
            "threshold": threshold,
            "stats": stats,
            "source_info": [info],
            "grid_dimensions": grid,
            "interactive": True,
        },
    }


def _v386_answer_near_well_filter(message: str) -> Optional[Dict[str, Any]]:
    req = _v386_detect_near_well_filter(message)
    if not req:
        return None

    prop = req["property"]
    well = req["well"]
    radius = float(req["radius"])

    well_loc = _v386_find_well_location(well)

    if not well_loc:
        answer = f"I understood the near-well plot request, but I could not find I,J coordinates for {well}."
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "plot_intent_engine_v386_near_well",
        }

    grid = _load_grid_dimensions()

    if not grid:
        answer = "I understood the near-well plot request, but grid_dimensions.json was not found."
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "plot_intent_engine_v386_near_well",
        }

    values, info = _load_property_values(prop)
    z_full = _values_to_vertical_average_map(values, grid)
    z_masked = _v386_apply_near_well_mask_to_2d_map(z_full, well_loc["i"], well_loc["j"], radius)

    # Stats only inside mask.
    inside_values = []
    for row in z_masked:
        for v in row:
            if v is not None:
                inside_values.append(v)

    stats = _stats(inside_values)

    label = req["label"]

    chart = _make_heatmap_chart(label, z_masked, stats, {
        "intent": req,
        "source_info": [info],
        "grid_dimensions": grid,
        "well_location": well_loc,
        "map_method": "vertical_average_over_K_masked_by_radius",
    })

    try:
        chart["data"].append(_v386_make_near_well_marker_trace(well_loc))
    except Exception:
        pass

    answer = (
        f"Created {prop} map near {well} within {radius:g} grid cells. "
        f"Well location: I={well_loc['i']:.0f}, J={well_loc['j']:.0f}. "
        f"Inside-mask stats: Min={stats.get('min'):.4g}, P50={stats.get('p50'):.4g}, Max={stats.get('max'):.4g}."
    )

    return {
        "ok": True,
        "answer": answer,
        "message": answer,
        "response": answer,
        "source": "plot_intent_engine_v386_near_well",
        "plotly_chart": chart,
        "image_url": None,
        "plot": {
            "plot_type": "near_well_property_map",
            "property": prop,
            "well": well,
            "radius_cells": radius,
            "well_location": well_loc,
            "stats": stats,
            "source_info": [info],
            "grid_dimensions": grid,
            "interactive": True,
        },
    }


# Override answer_plot_intent again, intercepting V386 before V380/V385.
_answer_plot_intent_before_v386 = answer_plot_intent

def answer_plot_intent(message: str) -> Optional[Dict[str, Any]]:
    # Keep streamlines first.
    v381_streamlines = answer_streamline_intent_v381(message)
    if v381_streamlines is not None:
        return v381_streamlines

    v386_near = _v386_answer_near_well_filter(message)
    if v386_near is not None:
        return v386_near

    v386_cond = _v386_answer_condition_mask(message)
    if v386_cond is not None:
        return v386_cond

    return _answer_plot_intent_before_v386(message)




# ==========================================================
# V387 TRUE FILTERED CONDITION MAPS
# Fixes V386 behavior:
# - false cells are blank/null, not shown as zero
# - true cells display the original property value
# - vertical map is average of only the values satisfying the condition
# ==========================================================

def _v387_filter_values_by_condition(values: List[float], op: str, threshold: float) -> List[Optional[float]]:
    """
    Keep original property value where condition is true.
    Set everything else to None so Plotly heatmap does not display it.
    """
    out: List[Optional[float]] = []

    for v in values:
        try:
            x = float(v)

            if not math.isfinite(x):
                out.append(None)
                continue

            if _v386_compare_value(x, op, threshold):
                out.append(x)
            else:
                out.append(None)

        except Exception:
            out.append(None)

    return out


def _v387_condition_satisfaction_stats(original_values: List[float], filtered_values: List[Optional[float]]) -> Dict[str, Any]:
    valid = []
    kept = []

    for raw, filtered in zip(original_values or [], filtered_values or []):
        try:
            x = float(raw)
            if math.isfinite(x):
                valid.append(x)
                if filtered is not None:
                    kept.append(float(filtered))
        except Exception:
            pass

    pct = 0.0
    if valid:
        pct = 100.0 * len(kept) / len(valid)

    return {
        "valid_cells_or_layers": len(valid),
        "kept_cells_or_layers": len(kept),
        "kept_percent": pct,
        "kept_stats": _stats(kept),
    }


def _v387_answer_condition_mask(message: str) -> Optional[Dict[str, Any]]:
    cond = _v386_detect_condition(message)
    if not cond:
        return None

    prop = cond["property"]
    op = cond["operator"]
    threshold = cond["threshold"]

    grid = _load_grid_dimensions()

    if not grid:
        answer = "I understood the conditional map request, but grid_dimensions.json was not found."
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "plot_intent_engine_v387_condition",
        }

    values, info = _load_property_values(prop)

    filtered_values = _v387_filter_values_by_condition(values, op, threshold)
    z = _values_to_vertical_average_map(filtered_values, grid)

    condition_stats = _v387_condition_satisfaction_stats(values, filtered_values)
    stats = condition_stats["kept_stats"]

    label = cond["label"]

    chart = _make_heatmap_chart(label, z, stats, {
        "intent": cond,
        "source_info": [info],
        "grid_dimensions": grid,
        "map_method": "vertical_average_of_only_cells_satisfying_condition",
        "condition_stats": condition_stats,
    })

    # Make it explicit that we are showing the original property values,
    # but only where the condition is true.
    try:
        chart["data"][0]["colorbar"] = {"title": prop}
        chart["data"][0]["hovertemplate"] = (
            "I=%{x}<br>J=%{y}<br>" + prop + "=%{z:.4g}<extra></extra>"
        )
        chart["data"][0]["name"] = label
    except Exception:
        pass

    answer = (
        f"Created filtered condition map for {prop} {op} {threshold:g}. "
        f"Only cells/layers satisfying the condition are displayed; all others are blank. "
        f"Kept {condition_stats['kept_cells_or_layers']} of {condition_stats['valid_cells_or_layers']} "
        f"valid cells/layers ({condition_stats['kept_percent']:.1f}%). "
        f"Displayed value is the vertical average over K of the values satisfying the condition."
    )

    return {
        "ok": True,
        "answer": answer,
        "message": answer,
        "response": answer,
        "source": "plot_intent_engine_v387_condition",
        "plotly_chart": chart,
        "image_url": None,
        "plot": {
            "plot_type": "filtered_condition_map",
            "property": prop,
            "operator": op,
            "threshold": threshold,
            "stats": stats,
            "condition_stats": condition_stats,
            "source_info": [info],
            "grid_dimensions": grid,
            "interactive": True,
        },
    }


# Override answer_plot_intent again so V387 condition maps replace V386.
_answer_plot_intent_before_v387 = answer_plot_intent

def answer_plot_intent(message: str) -> Optional[Dict[str, Any]]:
    # Keep streamlines first.
    v381_streamlines = answer_streamline_intent_v381(message)
    if v381_streamlines is not None:
        return v381_streamlines

    # Keep near-well before generic condition.
    v386_near = _v386_answer_near_well_filter(message)
    if v386_near is not None:
        return v386_near

    # New true filtered condition map.
    v387_cond = _v387_answer_condition_mask(message)
    if v387_cond is not None:
        return v387_cond

    return _answer_plot_intent_before_v387(message)




# ==========================================================
# V388 CROSS-PROPERTY CONDITIONAL MAPS
# Supports:
# - show PERM_X where SWAT > 0.4
# - show permeability where water saturation is bigger than 0.4
# - show TRANX where pressure final < 2500
# - show porosity where SWAT final > 0.5
#
# Meaning:
# display property A, filtered by condition on property B.
# ==========================================================

def _v388_split_display_and_condition_text(message: str) -> Optional[Tuple[str, str]]:
    raw = str(message or "")
    msg = _norm(raw)

    # Main pattern: "show/plot/display A where B > threshold"
    if " where " not in msg:
        return None

    left, right = msg.split(" where ", 1)

    # Remove common verbs from left part.
    left = re.sub(r"\b(show me|show|plot|display|map|mappa|heatmap|please|can you|give me)\b", " ", left)
    left = _norm(left)

    right = _norm(right)

    if not left or not right:
        return None

    return left, right


def _v388_detect_property_from_text(text_fragment: str) -> Optional[str]:
    frag = _norm(text_fragment)

    # Static properties first.
    for prop, aliases in STATIC_ALIASES.items():
        if _contains_any(frag, aliases):
            return prop

    # Generic permeability / transmissibility with direction.
    if "permeability" in frag or "perm" in frag:
        if any(x in frag for x in ["along y", "in y", " y ", "direction y"]):
            return "PERM_Y"
        if any(x in frag for x in ["along z", "in z", " z ", "vertical", "direction z"]):
            return "PERM_Z"
        return "PERM_X"

    if "transmissibility" in frag or "trasmissibil" in frag or "tran" in frag:
        if any(x in frag for x in ["along y", "in y", " y ", "direction y"]):
            return "TRANY"
        if any(x in frag for x in ["along z", "in z", " z ", "direction z"]):
            return "TRANZ"
        return "TRANX"

    # Dynamic properties.
    for base, aliases in DYNAMIC_ALIASES.items():
        if _contains_any(frag, aliases):
            # Time suffix should be detected from the same fragment.
            return _to_property_name(base, frag)

    return None


def _v388_detect_condition_from_text(condition_text: str) -> Optional[Dict[str, Any]]:
    cond_text = _norm(condition_text)

    prop = _v388_detect_property_from_text(cond_text)
    if not prop:
        return None

    # Verbal operators.
    verbal_patterns = [
        (r"(?:is\s+)?(?:greater than|bigger than|above|higher than|more than)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", ">"),
        (r"(?:is\s+)?(?:less than|smaller than|below|lower than)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", "<"),
        (r"(?:is\s+)?(?:equal to|equals|equal)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", "=="),
    ]

    for pat, op in verbal_patterns:
        m = re.search(pat, cond_text)
        if m:
            return {
                "property": prop,
                "operator": op,
                "threshold": float(m.group(1)),
            }

    # Symbolic operators.
    m = re.search(r"(>=|<=|>|<|==|=|!=|<>)\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", cond_text)
    if m:
        return {
            "property": prop,
            "operator": m.group(1),
            "threshold": float(m.group(2)),
        }

    return None


def _v388_detect_cross_property_condition(message: str) -> Optional[Dict[str, Any]]:
    split = _v388_split_display_and_condition_text(message)
    if not split:
        return None

    display_text, condition_text = split

    display_prop = _v388_detect_property_from_text(display_text)
    condition = _v388_detect_condition_from_text(condition_text)

    if not display_prop or not condition:
        return None

    # If display and condition are exactly the same, let V387 handle it.
    if display_prop == condition["property"]:
        return None

    return {
        "kind": "cross_property_condition",
        "display_property": display_prop,
        "condition_property": condition["property"],
        "operator": condition["operator"],
        "threshold": condition["threshold"],
        "intent": "map",
        "label": (
            f"{display_prop} where {condition['property']} "
            f"{condition['operator']} {condition['threshold']:g}"
        ),
    }


def _v388_filter_display_values_by_condition(
    display_values: List[float],
    condition_values: List[float],
    op: str,
    threshold: float,
) -> List[Optional[float]]:
    n = min(len(display_values), len(condition_values))
    out: List[Optional[float]] = []

    for dv, cv in zip(display_values[:n], condition_values[:n]):
        try:
            d = float(dv)
            c = float(cv)

            if not math.isfinite(d) or not math.isfinite(c):
                out.append(None)
                continue

            if _v386_compare_value(c, op, threshold):
                out.append(d)
            else:
                out.append(None)

        except Exception:
            out.append(None)

    return out


def _v388_cross_condition_stats(
    display_values: List[float],
    condition_values: List[float],
    filtered_values: List[Optional[float]],
) -> Dict[str, Any]:
    valid_condition = 0
    kept = 0

    for cv, fv in zip(condition_values or [], filtered_values or []):
        try:
            c = float(cv)
            if math.isfinite(c):
                valid_condition += 1
                if fv is not None:
                    kept += 1
        except Exception:
            pass

    pct = 0.0
    if valid_condition:
        pct = 100.0 * kept / valid_condition

    kept_values = []
    for v in filtered_values or []:
        try:
            if v is not None:
                kept_values.append(float(v))
        except Exception:
            pass

    return {
        "valid_condition_cells_or_layers": valid_condition,
        "kept_cells_or_layers": kept,
        "kept_percent": pct,
        "display_property_stats_inside_condition": _stats(kept_values),
    }


def _v388_answer_cross_property_condition(message: str) -> Optional[Dict[str, Any]]:
    req = _v388_detect_cross_property_condition(message)
    if not req:
        return None

    display_prop = req["display_property"]
    condition_prop = req["condition_property"]
    op = req["operator"]
    threshold = req["threshold"]

    grid = _load_grid_dimensions()

    if not grid:
        answer = "I understood the cross-property condition request, but grid_dimensions.json was not found."
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "plot_intent_engine_v388_cross_condition",
        }

    display_values, display_info = _load_property_values(display_prop)
    condition_values, condition_info = _load_property_values(condition_prop)

    filtered_values = _v388_filter_display_values_by_condition(
        display_values,
        condition_values,
        op,
        threshold,
    )

    z = _values_to_vertical_average_map(filtered_values, grid)

    cross_stats = _v388_cross_condition_stats(
        display_values,
        condition_values,
        filtered_values,
    )

    stats = cross_stats["display_property_stats_inside_condition"]

    label = req["label"]

    chart = _make_heatmap_chart(label, z, stats, {
        "intent": req,
        "source_info": [display_info, condition_info],
        "grid_dimensions": grid,
        "map_method": "vertical_average_of_display_property_where_condition_is_true",
        "cross_condition_stats": cross_stats,
    })

    try:
        chart["data"][0]["colorbar"] = {"title": display_prop}
        chart["data"][0]["hovertemplate"] = (
            "I=%{x}<br>J=%{y}<br>"
            + display_prop
            + "=%{z:.4g}<extra></extra>"
        )
        chart["data"][0]["name"] = label
    except Exception:
        pass

    answer = (
        f"Created cross-property filtered map: showing {display_prop} only where "
        f"{condition_prop} {op} {threshold:g}. "
        f"Kept {cross_stats['kept_cells_or_layers']} of "
        f"{cross_stats['valid_condition_cells_or_layers']} valid condition cells/layers "
        f"({cross_stats['kept_percent']:.1f}%). "
        f"Displayed value is the vertical average over K of {display_prop} where the condition is true."
    )

    return {
        "ok": True,
        "answer": answer,
        "message": answer,
        "response": answer,
        "source": "plot_intent_engine_v388_cross_condition",
        "plotly_chart": chart,
        "image_url": None,
        "plot": {
            "plot_type": "cross_property_filtered_map",
            "display_property": display_prop,
            "condition_property": condition_prop,
            "operator": op,
            "threshold": threshold,
            "stats": stats,
            "cross_condition_stats": cross_stats,
            "source_info": [display_info, condition_info],
            "grid_dimensions": grid,
            "interactive": True,
        },
    }


# Override answer_plot_intent again.
_answer_plot_intent_before_v388 = answer_plot_intent

def answer_plot_intent(message: str) -> Optional[Dict[str, Any]]:
    # Keep streamlines first.
    v381_streamlines = answer_streamline_intent_v381(message)
    if v381_streamlines is not None:
        return v381_streamlines

    # Near-well filter.
    v386_near = _v386_answer_near_well_filter(message)
    if v386_near is not None:
        return v386_near

    # Cross-property condition before simple same-property condition.
    v388_cross = _v388_answer_cross_property_condition(message)
    if v388_cross is not None:
        return v388_cross

    # Same-property filtered condition.
    v387_cond = _v387_answer_condition_mask(message)
    if v387_cond is not None:
        return v387_cond

    return _answer_plot_intent_before_v388(message)

