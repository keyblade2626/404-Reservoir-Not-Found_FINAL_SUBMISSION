import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"

CONTEXT_CSV = ART / "diagnosis" / "well_property_driver_context.csv"
HM_MAP_JSON = ART / "dashboard" / "hm_map_payload.json"

CORRIDOR_DIR = ART / "final_diagnosis" / "transmissibility_corridors"
CORRIDOR_CELLS_CSV = CORRIDOR_DIR / "candidate_transmissibility_corridor_cells.csv"
CORRIDOR_SUMMARY_CSV = CORRIDOR_DIR / "candidate_transmissibility_corridor_summary.csv"
CORRIDOR_JSON = CORRIDOR_DIR / "candidate_transmissibility_corridors.json"


PROPERTY_ALIASES = {
    "tran": "mean_tran_h",
    "transmissibility": "mean_tran_h",
    "transmissibilita": "mean_tran_h",
    "trasmissibilita": "mean_tran_h",
    "tran_h": "mean_tran_h",
    "kh": "wellconn_total_kh",
    "perm": "mean_perm_h",
    "permeability": "mean_perm_h",
    "permeabilita": "mean_perm_h",
    "poro": "mean_poro",
    "porosity": "mean_poro",
    "porosita": "mean_poro",
    "swat": "mean_swat_eoh",
    "water saturation": "mean_swat_eoh",
    "soil": "mean_soil_eoh",
    "sgas": "mean_sgas_eoh",
    "gas saturation": "mean_sgas_eoh",
    "pressure": "mean_pressure_eoh",
    "pressione": "mean_pressure_eoh",
    "delta pressure": "delta_pressure",
    "depletion": "delta_pressure",
}


PROPERTY_LABELS = {
    "mean_tran_h": "Mean Horizontal Transmissibility",
    "wellconn_weighted_tran_h": "Weighted Well-Connection TRAN_H",
    "wellconn_total_transmissibility": "Total Well-Connection Transmissibility",
    "wellconn_total_kh": "Total KH",
    "mean_perm_h": "Mean Horizontal Permeability",
    "mean_poro": "Mean Porosity",
    "mean_swat_eoh": "SWAT End of History",
    "delta_swat": "Delta SWAT",
    "mean_soil_eoh": "SOIL End of History",
    "mean_sgas_eoh": "SGAS End of History",
    "mean_pressure_eoh": "Pressure End of History",
    "delta_pressure": "Delta Pressure",
}


def safe_float(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalize_well(well: str) -> str:
    return str(well or "").strip().upper()


def resolve_property_name(text_or_property: str) -> str:
    t = str(text_or_property or "").strip().lower()

    if t in PROPERTY_LABELS:
        return t

    for key, value in PROPERTY_ALIASES.items():
        if key in t:
            return value

    return "mean_tran_h"


def get_context_lookup() -> Dict[str, Dict[str, Any]]:
    rows = load_csv(CONTEXT_CSV)
    return {normalize_well(r.get("well")): r for r in rows if r.get("well")}


def get_hm_map_payload() -> Dict[str, Any]:
    try:
        from app.hm_map_payload import build_hm_map_payload
        return build_hm_map_payload()
    except Exception:
        payload = load_json(HM_MAP_JSON)
        if payload:
            return payload
    return {"ok": False, "wells": [], "message": "HM map payload not available."}


def get_visual_hm_map(variable: str = "overall") -> Dict[str, Any]:
    payload = get_hm_map_payload()

    return {
        "kind": "hm_map",
        "title": f"{variable.upper()} History Match Map",
        "variable": variable,
        "wells": payload.get("wells", []),
        "meta": {
            "active_producer_count": payload.get("active_producer_count"),
            "inactive_producer_count": payload.get("inactive_producer_count"),
            "active_injector_count": payload.get("active_injector_count"),
            "inactive_injector_count": payload.get("inactive_injector_count"),
        },
    }


def get_property_visual_map(property_name: str = "mean_tran_h", variable: str = "overall") -> Dict[str, Any]:
    prop = resolve_property_name(property_name)
    ctx = get_context_lookup()
    hm = get_hm_map_payload()

    wells = []
    values = []

    for w in hm.get("wells", []):
        well = normalize_well(w.get("well"))
        row = ctx.get(well, {})

        value = safe_float(row.get(prop))

        item = dict(w)
        item["property_name"] = prop
        item["property_label"] = PROPERTY_LABELS.get(prop, prop)
        item["property_value"] = value

        if value is not None:
            values.append(value)

        wells.append(item)

    return {
        "kind": "property_map",
        "title": PROPERTY_LABELS.get(prop, prop),
        "property_name": prop,
        "property_label": PROPERTY_LABELS.get(prop, prop),
        "variable": variable,
        "min_value": min(values) if values else None,
        "max_value": max(values) if values else None,
        "wells": wells,
    }


def first_existing(paths: List[Path]) -> Optional[Path]:
    for p in paths:
        if p.exists():
            return p
    return None


def pick(row: Dict[str, Any], candidates: List[str]):
    lower = {str(k).lower(): v for k, v in row.items()}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None


def get_corridor_cells(well: Optional[str] = None) -> List[Dict[str, Any]]:
    path = first_existing([
        CORRIDOR_CELLS_CSV,
        CORRIDOR_DIR / "candidate_transmissibility_corridors_cells.csv",
        CORRIDOR_DIR / "candidate_cells.csv",
    ])

    if path is None:
        return []

    rows = load_csv(path)
    target = normalize_well(well) if well else None
    cells = []

    for r in rows:
        row_well = normalize_well(pick(r, ["well", "producer", "producer_well", "target_well"]))
        if target and row_well and row_well != target:
            continue

        i = safe_float(pick(r, ["i", "I", "cell_i", "grid_i"]))
        j = safe_float(pick(r, ["j", "J", "cell_j", "grid_j"]))

        if i is None or j is None:
            continue

        intensity = safe_float(pick(r, [
            "intensity", "score", "weight", "candidate_score",
            "multiplier_factor", "recommended_multiplier", "cell_score"
        ]))

        if intensity is None:
            intensity = 1.0

        cells.append({
            "well": row_well or target,
            "i": i,
            "j": j,
            "intensity": intensity,
            "direction": pick(r, ["direction", "multiplier_direction", "action"]) or "increase",
        })

    return cells


def get_transmissibility_corridor_visual(well: Optional[str] = None) -> Dict[str, Any]:
    hm = get_hm_map_payload()
    cells = get_corridor_cells(well=well)
    summary = load_csv(CORRIDOR_SUMMARY_CSV)

    target = normalize_well(well) if well else None

    if target:
        summary = [
            r for r in summary
            if normalize_well(r.get("well") or r.get("producer") or r.get("producer_well")) == target
        ]

    intensities = [safe_float(c.get("intensity")) for c in cells if safe_float(c.get("intensity")) is not None]

    return {
        "kind": "transmissibility_corridors",
        "title": "Candidate Transmissibility Corridors",
        "well": target,
        "wells": hm.get("wells", []),
        "cells": cells,
        "summary": summary[:8],
        "min_intensity": min(intensities) if intensities else None,
        "max_intensity": max(intensities) if intensities else None,
        "message": (
            "Highlighted cells represent candidate corridors for transmissibility multiplier testing. "
            "They are screening recommendations, not automatic model edits."
        ),
    }


def get_available_property_layers() -> Dict[str, Any]:
    return {
        "properties": [
            {"name": k, "label": v}
            for k, v in PROPERTY_LABELS.items()
        ]
    }
