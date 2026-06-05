import csv
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data" / "sample_model"
ART = ROOT / "artifacts"

OUTPUT_DIR = ART / "dashboard" / "cell_layers"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GRID_DIMENSIONS_JSON = MODEL_DIR / "grid_dimensions.json"

HM_MAP_JSON = ART / "dashboard" / "hm_map_payload.json"


PROPERTY_DEFINITIONS = {
    "PERM_H": {
        "label": "Horizontal Permeability",
        "unit": "mD",
        "type": "derived_sqrt",
        "components": ["PERMX", "PERMY"],
        "aggregation": "log_mean_k",
        "aliases": ["perm", "permeability", "permeabilita", "mean_perm_h"],
    },
    "TRAN_H": {
        "label": "Horizontal Transmissibility",
        "unit": "",
        "type": "derived_sqrt",
        "components": ["TRANX", "TRANY"],
        "aggregation": "log_mean_k",
        "aliases": ["tran", "transmissibility", "trasmissibilita", "transmissibilita", "mean_tran_h"],
    },
    "PORO": {
        "label": "Porosity",
        "unit": "frac",
        "type": "single",
        "components": ["PORO"],
        "aggregation": "mean_k",
        "aliases": ["poro", "porosity", "porosita", "mean_poro"],
    },
    "SWAT_INIT": {
        "label": "Water Saturation Initial",
        "unit": "frac",
        "type": "single",
        "components": ["SWAT_INIT", "SWATER_INIT", "SWAT"],
        "aggregation": "mean_k",
        "aliases": ["swat init", "initial swat", "water saturation initial", "initial water saturation"],
    },
    "DELTA_SWAT": {
        "label": "Delta Water Saturation",
        "unit": "frac",
        "type": "delta",
        "components": ["SWAT_EOH", "SWAT_INIT"],
        "aggregation": "mean_k",
        "aliases": ["delta swat", "swat delta", "change swat", "water saturation change", "delta water", "water change"],
    },
    "SOIL_INIT": {
        "label": "Oil Saturation Initial",
        "unit": "frac",
        "type": "single",
        "components": ["SOIL_INIT", "SOIL"],
        "aggregation": "mean_k",
        "aliases": ["soil init", "initial soil", "oil saturation initial", "initial oil saturation"],
    },
    "DELTA_SOIL": {
        "label": "Delta Oil Saturation",
        "unit": "frac",
        "type": "delta",
        "components": ["SOIL_EOH", "SOIL_INIT"],
        "aggregation": "mean_k",
        "aliases": ["delta soil", "soil delta", "change soil", "oil saturation change", "delta oil", "oil change"],
    },
    "SGAS_INIT": {
        "label": "Gas Saturation Initial",
        "unit": "frac",
        "type": "single",
        "components": ["SGAS_INIT", "SGAS"],
        "aggregation": "mean_k",
        "aliases": ["sgas init", "initial sgas", "gas saturation initial", "initial gas saturation"],
    },
    "DELTA_SGAS": {
        "label": "Delta Gas Saturation",
        "unit": "frac",
        "type": "delta",
        "components": ["SGAS_EOH", "SGAS_INIT"],
        "aggregation": "mean_k",
        "aliases": ["delta sgas", "sgas delta", "change sgas", "gas saturation change", "delta gas", "gas change"],
    },
    "PRESSURE_INIT": {
        "label": "Pressure Initial",
        "unit": "psi",
        "type": "single",
        "components": ["PRESSURE_INIT", "PINIT"],
        "aggregation": "mean_k",
        "aliases": ["pressure init", "initial pressure", "pinit"],
    },
    "SWAT_EOH": {
        "label": "Water Saturation EOH",
        "unit": "frac",
        "type": "single",
        "components": ["SWAT_EOH", "SWATER_EOH", "SWAT", "SWATER"],
        "aggregation": "mean_k",
        "aliases": ["swat", "water saturation", "mean_swat_eoh"],
    },
    "SOIL_EOH": {
        "label": "Oil Saturation EOH",
        "unit": "frac",
        "type": "single",
        "components": ["SOIL_EOH", "SOIL"],
        "aggregation": "mean_k",
        "aliases": ["soil", "oil saturation", "mean_soil_eoh"],
    },
    "SGAS_EOH": {
        "label": "Gas Saturation EOH",
        "unit": "frac",
        "type": "single",
        "components": ["SGAS_EOH", "SGAS"],
        "aggregation": "mean_k",
        "aliases": ["sgas", "gas saturation", "mean_sgas_eoh"],
    },
    "PRESSURE_EOH": {
        "label": "Pressure EOH",
        "unit": "psi",
        "type": "single",
        "components": ["PRESSURE_EOH", "PRESSURE"],
        "aggregation": "mean_k",
        "aliases": ["pressure", "pressione", "mean_pressure_eoh"],
    },
    "DELTA_PRESSURE": {
        "label": "Delta Pressure",
        "unit": "psi",
        "type": "delta",
        "components": ["PRESSURE_EOH", "PRESSURE_INIT"],
        "aggregation": "mean_k",
        "aliases": ["delta pressure", "depletion", "delta_pressure"],
    },
}


def _clean_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if "--" in line:
            line = line.split("--", 1)[0]
        lines.append(line)
    return "\n".join(lines)


def _parse_numeric_token(token: str) -> List[float]:
    token = token.strip().replace("D", "E").replace("d", "e")

    if not token or token == "/":
        return []

    if "*" in token:
        left, right = token.split("*", 1)
        try:
            n = int(float(left))
            v = float(right)
            return [v] * n
        except Exception:
            return []

    try:
        return [float(token)]
    except Exception:
        return []


def parse_grdecl_keyword(path: Path, keyword: Optional[str] = None) -> np.ndarray:
    text = _clean_text(path.read_text(encoding="utf-8", errors="ignore"))
    text = text.replace("/", " / ")
    tokens = text.split()

    start_idx = 0

    if keyword:
        kw = keyword.upper()
        found = False
        for idx, token in enumerate(tokens):
            if token.upper() == kw:
                start_idx = idx + 1
                found = True
                break

        if not found:
            # Fallback: parse numbers from file anyway.
            start_idx = 0
    else:
        # skip first token if it looks like a keyword
        if tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", tokens[0]):
            start_idx = 1

    values = []

    for token in tokens[start_idx:]:
        if token == "/":
            if values:
                break
            continue

        values.extend(_parse_numeric_token(token))

    return np.asarray(values, dtype=float)


def find_property_file(keyword: str) -> Optional[Path]:
    keyword_u = keyword.upper()

    candidates = []

    for ext in ["*.GRDECL", "*.grdecl", "*.INC", "*.inc", "*.DATA", "*.data"]:
        candidates.extend(MODEL_DIR.glob(ext))

    # First: exact stem match.
    for path in candidates:
        if path.stem.upper() == keyword_u:
            return path

    # Second: keyword contained in stem.
    for path in candidates:
        if keyword_u in path.stem.upper():
            return path

    # Third: keyword inside file text.
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:50000].upper()
            if re.search(rf"\b{re.escape(keyword_u)}\b", text):
                return path
        except Exception:
            pass

    return None



def find_grid_dimensions_json() -> Optional[Path]:
    candidates = [
        MODEL_DIR / "grid_dimensions.json",
        ROOT / "grid_dimensions.json",
        ART / "grid_dimensions.json",
        ART / "dashboard" / "grid_dimensions.json",
    ]

    for p in candidates:
        if p.exists():
            return p

    # fallback recursive search, but prefer shortest path
    found = list(ROOT.rglob("grid_dimensions.json"))
    if found:
        return sorted(found, key=lambda x: len(str(x)))[0]

    return None


def get_reference_property_length() -> Optional[int]:
    """
    Returns the length of a representative full-grid property vector.
    This is used only as fallback to infer NZ when NX/NY are available.
    """
    candidates = [
        "PERMX", "PERMY", "PERMZ",
        "TRANX", "TRANY", "TRANZ",
        "PORO", "PRESSURE", "SWAT", "SWATER", "SOIL", "SGAS",
        "ACTNUM",
    ]

    lengths = []

    for key in candidates:
        try:
            arr, _ = load_property_vector(key)
            if arr is not None and arr.size > 0:
                lengths.append(int(arr.size))
        except Exception:
            pass

    if not lengths:
        return None

    # Use the most common length, because some vectors may be ACTNUM or region arrays.
    counts = {}
    for n in lengths:
        counts[n] = counts.get(n, 0) + 1

    return sorted(counts.items(), key=lambda x: (-x[1], -x[0]))[0][0]


def get_max_ij_from_spatial_summary() -> Tuple[Optional[int], Optional[int], str]:
    """
    Fallback only. Uses well/completion I,J to estimate NX/NY.
    This may underestimate the grid if wells do not cover the full model.
    """
    try:
        from app.well_connections import get_well_spatial_summary

        spatial = get_well_spatial_summary()
        max_i = None
        max_j = None

        for _, payload in spatial.get("wells", {}).items():
            for key in ["representative_i", "i", "mean_i", "max_i"]:
                value = payload.get(key)
                if value not in [None, ""]:
                    iv = int(float(value))
                    max_i = iv if max_i is None else max(max_i, iv)

            for key in ["representative_j", "j", "mean_j", "max_j"]:
                value = payload.get(key)
                if value not in [None, ""]:
                    jv = int(float(value))
                    max_j = jv if max_j is None else max(max_j, jv)

        return max_i, max_j, "well_spatial_summary"

    except Exception:
        return None, None, "well_spatial_summary_failed"


def discover_grid_dimensions() -> Tuple[Optional[int], Optional[int], Optional[int], str]:
    # 0) Manual config file has priority.
    # Preferred file:
    # data/sample_model/grid_dimensions.json
    # Example:
    # {"nx": 181, "ny": 190, "nz": 62}
    grid_json = find_grid_dimensions_json()

    if grid_json is not None:
        try:
            payload = json.loads(grid_json.read_text(encoding="utf-8-sig"))
            nx = int(payload.get("nx"))
            ny = int(payload.get("ny"))
            nz = int(payload.get("nz"))

            if nx > 0 and ny > 0 and nz > 0:
                return nx, ny, nz, f"manual config from {grid_json}"
        except Exception as exc:
            return None, None, None, f"invalid grid_dimensions.json at {grid_json}: {exc}"

    # 1) Try SPECGRID / DIMENS in text model files.
    for ext in ["*.DATA", "*.data", "*.GRDECL", "*.grdecl", "*.INC", "*.inc"]:
        for path in MODEL_DIR.glob(ext):
            try:
                text = _clean_text(path.read_text(encoding="utf-8", errors="ignore"))
                m = re.search(r"\b(SPECGRID|DIMENS)\b(.*?)/", text, flags=re.IGNORECASE | re.DOTALL)
                if m:
                    nums = re.findall(r"[-+]?\d+", m.group(2))
                    if len(nums) >= 3:
                        nx, ny, nz = int(nums[0]), int(nums[1]), int(nums[2])
                        if nx > 0 and ny > 0 and nz > 0:
                            return nx, ny, nz, f"{m.group(1).upper()} from {path.name}"
            except Exception:
                pass

    # 2) Try grid_full_table.csv.
    for path in [ROOT / "grid_full_table.csv", MODEL_DIR / "grid_full_table.csv", ART / "grid_full_table.csv"]:
        if path.exists():
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    max_i = max_j = max_k = None

                    for row in reader:
                        keys = {k.lower(): k for k in row.keys()}

                        i_key = keys.get("i")
                        j_key = keys.get("j")
                        k_key = keys.get("k")

                        if not i_key or not j_key or not k_key:
                            continue

                        i = int(float(row[i_key]))
                        j = int(float(row[j_key]))
                        k = int(float(row[k_key]))

                        max_i = i if max_i is None else max(max_i, i)
                        max_j = j if max_j is None else max(max_j, j)
                        max_k = k if max_k is None else max(max_k, k)

                    if max_i and max_j and max_k:
                        return max_i, max_j, max_k, f"grid_full_table.csv from {path}"
            except Exception:
                pass

    # 3) Fallback: infer NZ from property vector length and max well/completion I,J.
    # This is less safe than SPECGRID/DIMENS, but useful for demo if wells reach grid edges.
    ref_len = get_reference_property_length()
    max_i, max_j, ij_source = get_max_ij_from_spatial_summary()

    if ref_len and max_i and max_j:
        denom = max_i * max_j
        if denom > 0 and ref_len % denom == 0:
            nz = ref_len // denom
            if nz > 0:
                return max_i, max_j, int(nz), f"inferred from property length={ref_len} and {ij_source}"

    return None, None, None, "not_found"


def load_property_vector(keyword: str) -> Tuple[Optional[np.ndarray], Optional[str]]:
    path = find_property_file(keyword)

    if path is None:
        return None, None

    arr = parse_grdecl_keyword(path, keyword=keyword)

    if arr.size == 0:
        arr = parse_grdecl_keyword(path, keyword=None)

    return arr, str(path)


def normalize_length(arr: np.ndarray, total: int) -> np.ndarray:
    out = np.full(total, np.nan, dtype=float)

    n = min(total, arr.size)
    out[:n] = arr[:n]

    return out


def load_actnum(total: int) -> Optional[np.ndarray]:
    arr, _ = load_property_vector("ACTNUM")

    if arr is None or arr.size == 0:
        return None

    arr = normalize_length(arr, total)

    return arr > 0.5


def aggregate_k(values: np.ndarray, nx: int, ny: int, nz: int, mode: str, actnum: Optional[np.ndarray]) -> np.ndarray:
    total = nx * ny * nz
    values = normalize_length(values, total)

    if actnum is not None:
        values = np.where(actnum, values, np.nan)

    cube = values.reshape((nz, ny, nx))

    if mode == "log_mean_k":
        positive = np.where(cube > 0, cube, np.nan)

        with np.errstate(invalid="ignore"):
            logv = np.log10(positive)
            mean_log = np.nanmean(logv, axis=0)
            out = np.power(10.0, mean_log)

        return out

    with np.errstate(invalid="ignore"):
        return np.nanmean(cube, axis=0)


def percentile_scale(values: List[float]) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    arr = np.asarray([v for v in values if v is not None and np.isfinite(v)], dtype=float)

    if arr.size == 0:
        return None, None, None, None

    return (
        float(np.nanmin(arr)),
        float(np.nanmax(arr)),
        float(np.nanpercentile(arr, 2)),
        float(np.nanpercentile(arr, 98)),
    )


def resolve_layer_name(name: str) -> str:
    q = str(name or "").strip().lower()

    # Exact layer name.
    for layer, cfg in PROPERTY_DEFINITIONS.items():
        if q == layer.lower():
            return layer

    # Exact alias.
    for layer, cfg in PROPERTY_DEFINITIONS.items():
        aliases = [a.lower() for a in cfg.get("aliases", [])]
        if q in aliases:
            return layer

    # Prioritize time-dependent delta/init/eoh words.
    has_delta = any(x in q for x in ["delta", "difference", "change", "varia", "depletion", "deplet"])
    has_init = any(x in q for x in ["initial", "init", "iniziale", "inizio", "start"])
    has_eoh = any(x in q for x in ["eoh", "end", "fine", "history", "hm", "final"])

    if "swat" in q or "water saturation" in q or "saturazione acqua" in q:
        if has_delta:
            return "DELTA_SWAT"
        if has_init:
            return "SWAT_INIT"
        return "SWAT_EOH"

    if "soil" in q or "oil saturation" in q or "saturazione olio" in q:
        if has_delta:
            return "DELTA_SOIL"
        if has_init:
            return "SOIL_INIT"
        return "SOIL_EOH"

    if "sgas" in q or "gas saturation" in q or "saturazione gas" in q:
        if has_delta:
            return "DELTA_SGAS"
        if has_init:
            return "SGAS_INIT"
        return "SGAS_EOH"

    if "pressure" in q or "pressione" in q or "depletion" in q:
        if has_delta or "depletion" in q or "deplet" in q:
            return "DELTA_PRESSURE"
        if has_init:
            return "PRESSURE_INIT"
        return "PRESSURE_EOH"

    # Partial aliases.
    for layer, cfg in PROPERTY_DEFINITIONS.items():
        aliases = [a.lower() for a in cfg.get("aliases", [])]
        if any(a in q for a in aliases):
            return layer

    return "TRAN_H"


def get_hm_wells() -> List[Dict[str, Any]]:
    try:
        from app.hm_map_payload import build_hm_map_payload
        return build_hm_map_payload().get("wells", [])
    except Exception:
        pass

    if HM_MAP_JSON.exists():
        try:
            return json.loads(HM_MAP_JSON.read_text(encoding="utf-8")).get("wells", [])
        except Exception:
            return []

    return []


def build_cell_property_layer(property_name: str = "TRAN_H") -> Dict[str, Any]:
    layer = resolve_layer_name(property_name)
    cfg = PROPERTY_DEFINITIONS[layer]

    nx, ny, nz, dim_source = discover_grid_dimensions()

    if not nx or not ny or not nz:
        return {
            "ok": False,
            "property": layer,
            "message": "Grid dimensions not found. Export SPECGRID/DIMENS or grid_full_table.csv with I,J,K.",
            "dimension_source": dim_source,
            "cells": [],
            "wells": get_hm_wells(),
        }

    total = nx * ny * nz
    actnum = load_actnum(total)

    source_files = {}

    if cfg["type"] == "derived_sqrt":
        a_key, b_key = cfg["components"]
        a, a_path = load_property_vector(a_key)
        b, b_path = load_property_vector(b_key)

        if a is None or b is None:
            return {
                "ok": False,
                "property": layer,
                "message": f"Missing component files for {layer}: {a_key}, {b_key}.",
                "cells": [],
                "wells": get_hm_wells(),
            }

        a = normalize_length(a, total)
        b = normalize_length(b, total)

        values = np.sqrt(np.maximum(a, 0) * np.maximum(b, 0))
        source_files[a_key] = a_path
        source_files[b_key] = b_path

    elif cfg["type"] == "delta":
        eoh_key, init_key = cfg["components"]

        eoh, eoh_path = load_property_vector(eoh_key)
        init, init_path = load_property_vector(init_key)

        if eoh is None or init is None:
            return {
                "ok": False,
                "property": layer,
                "message": f"Missing component files for {layer}: {eoh_key}, {init_key}.",
                "cells": [],
                "wells": get_hm_wells(),
            }

        eoh = normalize_length(eoh, total)
        init = normalize_length(init, total)

        values = eoh - init
        source_files[eoh_key] = eoh_path
        source_files[init_key] = init_path

    else:
        arr = None
        used_key = None
        used_path = None

        for key in cfg["components"]:
            arr, used_path = load_property_vector(key)
            if arr is not None and arr.size > 0:
                used_key = key
                break

        if arr is None:
            return {
                "ok": False,
                "property": layer,
                "message": f"No GRDECL property file found for {layer}. Tried {cfg['components']}.",
                "cells": [],
                "wells": get_hm_wells(),
            }

        values = normalize_length(arr, total)
        source_files[used_key] = used_path

    grid_2d = aggregate_k(values, nx, ny, nz, cfg["aggregation"], actnum)

    cells = []
    valid_values = []

    for j in range(ny):
        for i in range(nx):
            v = grid_2d[j, i]

            if not np.isfinite(v):
                continue

            vf = float(v)

            cells.append({
                "i": i + 1,
                "j": j + 1,
                "value": vf,
            })

            valid_values.append(vf)

    min_v, max_v, p2, p98 = percentile_scale(valid_values)

    payload = {
        "ok": True,
        "property": layer,
        "label": cfg["label"],
        "unit": cfg["unit"],
        "aggregation": cfg["aggregation"],
        "nx": nx,
        "ny": ny,
        "nz": nz,
        "dimension_source": dim_source,
        "source_files": source_files,
        "min": min_v,
        "max": max_v,
        "p2": p2,
        "p98": p98,
        "cell_count": len(cells),
        "cells": cells,
        "wells": get_hm_wells(),
        "message": f"{cfg['label']} aggregated along K using {cfg['aggregation']}.",
    }

    out = OUTPUT_DIR / f"{layer.lower()}_cell_layer.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return payload


def list_cell_property_layers() -> Dict[str, Any]:
    return {
        "layers": [
            {
                "name": name,
                "label": cfg["label"],
                "unit": cfg["unit"],
                "aggregation": cfg["aggregation"],
                "aliases": cfg["aliases"],
            }
            for name, cfg in PROPERTY_DEFINITIONS.items()
        ]
    }


if __name__ == "__main__":
    for layer in ["PERM_H", "TRAN_H", "PORO", "SWAT_EOH", "PRESSURE_EOH", "DELTA_PRESSURE"]:
        p = build_cell_property_layer(layer)
        print(layer, p.get("ok"), p.get("message"), "cells=", p.get("cell_count"))
