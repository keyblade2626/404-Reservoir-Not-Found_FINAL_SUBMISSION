import csv
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
CONTEXT_CSV = ART / "diagnosis" / "well_property_driver_context.csv"


def safe_float(v):
    try:
        if v is None or v == "":
            return None
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None


def load_context_rows():
    if not CONTEXT_CSV.exists():
        return []

    with CONTEXT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def well_points_from_context():
    wells = []

    for r in load_context_rows():
        i = safe_float(r.get("i"))
        j = safe_float(r.get("j"))

        if i is None or j is None:
            continue

        wells.append({
            "well": r.get("well"),
            "i": i,
            "j": j,
            "producer_candidate": True,
            "injector_candidate": str(r.get("has_injector_evidence") or "").lower() == "true",
            "active_producer": str(r.get("active_producer") or "").lower() == "true",
            "active_injector": str(r.get("active_injector") or "").lower() == "true",
            "overall_score": safe_float(r.get("overall_hm_score")),
            "overall_class": r.get("overall_hm_class"),
            "water_score": safe_float(r.get("water_hm_score")),
            "water_class": r.get("water_hm_class"),
            "oil_score": safe_float(r.get("oil_hm_score")),
            "oil_class": r.get("oil_hm_class"),
            "gas_score": safe_float(r.get("gas_hm_score")),
            "gas_class": r.get("gas_hm_class"),
            "bhp_score": safe_float(r.get("bhp_hm_score")),
            "bhp_class": r.get("bhp_hm_class"),
        })

    return wells


PROPERTY_ALIASES = {
    # Permeability
    "permeability": "PERM_H",
    "perm": "PERM_H",
    "k map": "PERM_H",
    "kh map": "PERM_H",

    # Transmissibility
    "transmissibility": "TRAN_H",
    "transmissibilita": "TRAN_H",
    "trasmissibilita": "TRAN_H",
    "trasmissibilità": "TRAN_H",
    "tran": "TRAN_H",
    "transmissibility multiplier": "TRAN_H",

    # Pressure
    "pressure depletion": "DELTA_PRESSURE",
    "depletion": "DELTA_PRESSURE",
    "delta pressure": "DELTA_PRESSURE",
    "pressure drop": "DELTA_PRESSURE",
    "pressure change": "DELTA_PRESSURE",
    "pressure eoh": "PRESSURE_EOH",
    "end pressure": "PRESSURE_EOH",
    "final pressure": "PRESSURE_EOH",
    "pressure": "PRESSURE_EOH",

    # Water saturation
    "delta swat": "DELTA_SWAT",
    "swat change": "DELTA_SWAT",
    "water saturation change": "DELTA_SWAT",
    "swat eoh": "SWAT_EOH",
    "final swat": "SWAT_EOH",
    "water saturation": "SWAT_EOH",
    "swat": "SWAT_EOH",

    # Oil saturation
    "delta oil saturation": "DELTA_SOIL",
    "oil saturation change": "DELTA_SOIL",
    "soil eoh": "SOIL_EOH",
    "oil saturation": "SOIL_EOH",
    "soil": "SOIL_EOH",

    # Gas saturation
    "delta gas saturation": "DELTA_SGAS",
    "gas saturation change": "DELTA_SGAS",
    "sgas eoh": "SGAS_EOH",
    "gas saturation": "SGAS_EOH",
    "sgas": "SGAS_EOH",

    # Porosity
    "porosity": "PORO",
    "poro": "PORO",
    "pore volume": "PORO",
}


COLUMN_ALIASES = {
    "overall score": "overall_hm_score",
    "overall hm": "overall_hm_score",
    "water score": "water_hm_score",
    "water hm": "water_hm_score",
    "water mismatch": "water_hm_score",
    "oil score": "oil_hm_score",
    "oil hm": "oil_hm_score",
    "gas score": "gas_hm_score",
    "gas hm": "gas_hm_score",
    "bhp score": "bhp_hm_score",
    "bhp hm": "bhp_hm_score",
    "pressure match": "bhp_hm_score",
    "transmissibility": "wellconn_weighted_tran_h",
    "tran": "wellconn_weighted_tran_h",
    "tran percentile": "wellconn_weighted_tran_h_percentile",
    "permeability": "mean_perm_h",
    "perm": "mean_perm_h",
    "swat": "mean_swat_eoh",
    "delta swat": "delta_swat",
    "swat increase": "delta_swat",
    "pressure": "mean_pressure_eoh",
    "delta pressure": "delta_pressure",
    "pressure depletion": "delta_pressure",
    "porosity": "mean_poro",
    "poro": "mean_poro",
}


def detect_property(message: str) -> Optional[str]:
    """
    Detect the requested base property.

    Important rule:
    Streamlines are an overlay only. They must never force TRAN_H.
    If the user says "permeability with streamlines", the base layer is PERM_H.
    """
    q = str(message or "").lower()

    # Explicit priority. Longer/more specific phrases first.
    priority = [
        ("pressure depletion", "DELTA_PRESSURE"),
        ("delta pressure", "DELTA_PRESSURE"),
        ("pressure drop", "DELTA_PRESSURE"),
        ("pressure change", "DELTA_PRESSURE"),

        ("delta swat", "DELTA_SWAT"),
        ("swat change", "DELTA_SWAT"),
        ("water saturation change", "DELTA_SWAT"),

        ("delta oil saturation", "DELTA_SOIL"),
        ("oil saturation change", "DELTA_SOIL"),

        ("delta gas saturation", "DELTA_SGAS"),
        ("gas saturation change", "DELTA_SGAS"),

        ("permeability", "PERM_H"),
        ("perm", "PERM_H"),
        ("porosity", "PORO"),
        ("poro", "PORO"),

        ("transmissibility", "TRAN_H"),
        ("transmissibilita", "TRAN_H"),
        ("trasmissibilita", "TRAN_H"),
        ("trasmissibilità", "TRAN_H"),
        ("tran", "TRAN_H"),

        ("pressure", "PRESSURE_EOH"),
        ("swat", "SWAT_EOH"),
        ("water saturation", "SWAT_EOH"),
        ("soil", "SOIL_EOH"),
        ("oil saturation", "SOIL_EOH"),
        ("sgas", "SGAS_EOH"),
        ("gas saturation", "SGAS_EOH"),
    ]

    for phrase, prop in priority:
        if phrase in q:
            return prop

    return None



def detect_streamline_time(message: str) -> str:
    """
    Detect which streamline snapshot the user wants.
    Returns:
      - initial
      - final
      - compare
      - auto
    """
    q = str(message or "").lower()

    if any(x in q for x in [
        "compare streamlines",
        "compare initial and final",
        "initial vs final",
        "start vs end",
        "beginning vs end",
        "streamline evolution",
        "streamlines evolution",
    ]):
        return "compare"

    if any(x in q for x in [
        "initial streamlines",
        "initial streamline",
        "start streamlines",
        "start of history",
        "beginning of history",
        "boh",
        "initial history",
        "at start",
        "at beginning",
    ]):
        return "initial"

    if any(x in q for x in [
        "final streamlines",
        "final streamline",
        "end streamlines",
        "end of history",
        "eoh",
        "end-history",
        "at end",
        "late history",
        "current streamlines",
        "last streamlines",
    ]):
        return "final"

    return "auto"


def streamline_time_label(time_key: str) -> str:
    return {
        "initial": "Initial History",
        "final": "End of History",
        "compare": "Initial vs End of History",
        "auto": "Available / Default Snapshot",
    }.get(time_key, time_key)


def wants_streamlines(message: str) -> bool:
    q = str(message or "").lower()
    return any(x in q for x in ["streamline", "streamlines", "connectivity", "flow path", "communication"])


def is_property_map_request(message: str) -> bool:
    q = str(message or "").lower()
    return (
        any(x in q for x in ["map", "mappa", "show", "plot", "display", "visualize", "overlay"])
        and detect_property(q) is not None
    )


def load_streamline_payload(time_key: str = "auto"):
    """
    Load streamline payload, trying to respect initial/final/compare if the available
    streamline module supports it. Falls back safely to the default payload.
    """
    try:
        import app.streamline_visual_payloads as svp

        # Try common APIs with time/snapshot arguments.
        for name in [
            "build_streamline_visual_payload",
            "build_streamline_payload",
            "get_streamline_visual_payload",
            "load_streamline_payload",
            "main_payload",
        ]:
            fn = getattr(svp, name, None)
            if not callable(fn):
                continue

            # Try keyword forms first.
            for kwargs in [
                {"time_key": time_key},
                {"snapshot": time_key},
                {"streamline_time": time_key},
                {"mode": time_key},
            ]:
                try:
                    out = fn(**kwargs)
                    if isinstance(out, dict):
                        out["requested_streamline_time"] = time_key
                        return out
                except TypeError:
                    pass
                except Exception:
                    pass

            # Then try no-arg fallback.
            try:
                out = fn()
                if isinstance(out, dict):
                    out["requested_streamline_time"] = time_key
                    out.setdefault(
                        "warning",
                        "The streamline provider did not expose selectable initial/final snapshots; default payload was used."
                    )
                    return out
            except Exception:
                pass

    except Exception:
        pass

    return {
        "ok": False,
        "lines": [],
        "requested_streamline_time": time_key,
        "message": "Streamline payload not available from current artifacts.",
    }


def build_property_map_response(message: str):
    requested_prop = detect_property(message)

    # If the user asks only for streamlines/connectivity, use transmissibility as a reasonable background.
    # But if the user explicitly asks for permeability/pressure/SWAT/etc., keep that requested property.
    if not requested_prop and wants_streamlines(message):
        requested_prop = "TRAN_H"

    if not requested_prop:
        return None

    try:
        from app.cell_property_layers import build_cell_property_layer
        layer = build_cell_property_layer(requested_prop)
    except Exception as exc:
        return {
            "type": "visual_response",
            "answer": (
                f"I understood that you want a map of {requested_prop}, "
                f"but I could not build that raw property layer yet: {exc}"
            ),
            "intent": "dynamic_property_map_error",
            "ui_blocks": [],
            "data": {
                "requested_property": requested_prop,
                "error": str(exc),
            },
            "agent_trace": {
                "DynamicVisualAgent": {
                    "intent": "property_map_error",
                    "requested_property": requested_prop,
                    "error": str(exc),
                }
            },
        }

    if not isinstance(layer, dict):
        layer = {"property": requested_prop, "cells": []}

    # Add explicit metadata so frontend does not guess.
    layer["requested_property"] = requested_prop
    layer["property"] = requested_prop
    layer["label"] = property_label(requested_prop)
    layer["wells"] = well_points_from_context()

    streamline_time = detect_streamline_time(message)
    streamline_payload = load_streamline_payload(streamline_time) if wants_streamlines(message) else None

    answer = (
        f"I generated an interactive {property_label(requested_prop)} map from the raw model-derived property layer. "
        "Wells are overlaid so you can relate the property distribution to the HM diagnostics."
    )

    if streamline_payload:
        answer += (
            f" Streamlines are shown as an overlay only; they do not change the selected base property layer. Streamline snapshot: {streamline_time_label(streamline_time)}."
        )

    return {
        "type": "visual_response",
        "answer": answer,
        "intent": "dynamic_property_map",
        "ui_blocks": [
            {
                "type": "cell_property_map",
                "title": property_label(requested_prop) + (f" + Streamlines ({streamline_time_label(streamline_time)})" if streamline_payload else ""),
                "payload": layer,
                "streamline_payload": streamline_payload,
                "source": "DynamicVisualAgent",
                "requested_property": requested_prop,
                "overlay_streamlines": bool(streamline_payload),
                "streamline_time": streamline_time,
            }
        ],
        "data": {
            "requested_property": requested_prop,
            "property_label": property_label(requested_prop),
            "with_streamlines": bool(streamline_payload),
            "streamline_time": streamline_time,
        },
        "agent_trace": {
            "DynamicVisualAgent": {
                "intent": "property_map",
                "requested_property": requested_prop,
                "property_label": property_label(requested_prop),
                "with_streamlines": bool(streamline_payload),
            "streamline_time": streamline_time,
            }
        },
    }


def normalize_metric(text: str) -> Optional[str]:
    q = str(text or "").lower().strip()

    for alias in sorted(COLUMN_ALIASES.keys(), key=len, reverse=True):
        if alias in q:
            return COLUMN_ALIASES[alias]

    # direct column fallback
    rows = load_context_rows()
    if rows:
        cols = rows[0].keys()
        for c in cols:
            if c.lower() == q:
                return c

    return None


def detect_correlation_metrics(message: str):
    q = str(message or "").lower()

    # pattern: x vs y
    m = re.search(r"(.+?)\s+(?:vs|versus|against)\s+(.+)", q)
    if m:
        left = m.group(1)
        right = m.group(2)

        x = normalize_metric(left)
        y = normalize_metric(right)

        if x and y:
            return x, y

    # Useful defaults from natural language.
    if "water" in q and "transmiss" in q:
        return "wellconn_weighted_tran_h_percentile", "water_hm_score"

    if ("pressure" in q or "bhp" in q) and ("depletion" in q or "delta pressure" in q):
        return "delta_pressure", "bhp_hm_score"

    if "swat" in q and "water" in q:
        return "delta_swat", "water_hm_score"

    if "permeability" in q and ("pressure" in q or "bhp" in q):
        return "mean_perm_h", "bhp_hm_score"

    if "porosity" in q and ("pressure" in q or "bhp" in q):
        return "mean_poro", "bhp_hm_score"

    return None, None


def is_correlation_request(message: str) -> bool:
    q = str(message or "").lower()
    return any(x in q for x in ["correlation", "correlate", "crossplot", "scatter", " vs ", " versus ", " against "])


def build_correlation_response(message: str):
    x_col, y_col = detect_correlation_metrics(message)

    if not x_col or not y_col:
        return None

    rows = load_context_rows()
    points = []

    for r in rows:
        x = safe_float(r.get(x_col))
        y = safe_float(r.get(y_col))

        if x is None or y is None:
            continue

        points.append({
            "well": r.get("well"),
            "x": x,
            "y": y,
            "overall": safe_float(r.get("overall_hm_score")),
            "water": safe_float(r.get("water_hm_score")),
            "oil": safe_float(r.get("oil_hm_score")),
            "gas": safe_float(r.get("gas_hm_score")),
            "bhp": safe_float(r.get("bhp_hm_score")),
            "i": safe_float(r.get("i")),
            "j": safe_float(r.get("j")),
        })

    if not points:
        return {
            "type": "visual_response",
            "answer": f"I understood the crossplot request, but I could not find numeric data for {x_col} and {y_col}.",
            "intent": "dynamic_correlation_empty",
            "ui_blocks": [],
            "data": {"x": x_col, "y": y_col},
        }

    return {
        "type": "visual_response",
        "answer": (
            f"I created a dynamic crossplot of {y_col} versus {x_col}. "
            "Use this to check whether the mismatch is correlated with a local property or dynamic signal."
        ),
        "intent": "dynamic_correlation_plot",
        "ui_blocks": [
            {
                "type": "correlation_scatter",
                "title": f"{y_col} vs {x_col}",
                "x_label": x_col,
                "y_label": y_col,
                "points": points,
            }
        ],
        "data": {
            "x": x_col,
            "y": y_col,
            "points": points,
        },
        "agent_trace": {
            "DynamicVisualAgent": {
                "intent": "correlation_scatter",
                "x": x_col,
                "y": y_col,
                "point_count": len(points),
            }
        },
    }


def answer_dynamic_visual_question(message: str):
    if is_correlation_request(message):
        out = build_correlation_response(message)
        if out is not None:
            return out

    if is_property_map_request(message) or wants_streamlines(message):
        out = build_property_map_response(message)
        if out is not None:
            return out

    return None


if __name__ == "__main__":
    tests = [
        "plot permeability map with streamlines",
        "show pressure depletion with streamlines",
        "correlate water score with transmissibility",
        "crossplot BHP score vs pressure depletion",
        "plot delta SWAT vs water score",
    ]

    for t in tests:
        print("=" * 80)
        print(t)
        r = answer_dynamic_visual_question(t)
        print(r["intent"] if r else None)
        print(r.get("answer") if r else None)



# ==========================================================
# HARD OVERRIDES V16
# These functions intentionally override previous definitions.
# They preserve user-requested raw property and streamline snapshot.
# ==========================================================

def detect_property(message: str) -> Optional[str]:
    q = str(message or "").lower()

    # Explicit property priority. Do not let "streamlines" imply transmissibility.
    if any(x in q for x in ["permeability", "perm", "k map", "kh map"]):
        return "PERM_H"

    if any(x in q for x in ["porosity", "poro", "pore volume"]):
        return "PORO"

    if any(x in q for x in ["pressure depletion", "delta pressure", "pressure drop", "pressure change", "depletion"]):
        return "DELTA_PRESSURE"

    if any(x in q for x in ["pressure eoh", "end pressure", "final pressure"]):
        return "PRESSURE_EOH"

    # Generic pressure only after depletion/final pressure checks.
    if "pressure" in q:
        return "PRESSURE_EOH"

    if any(x in q for x in ["delta swat", "swat change", "water saturation change"]):
        return "DELTA_SWAT"

    if any(x in q for x in ["swat", "water saturation"]):
        return "SWAT_EOH"

    if any(x in q for x in ["delta soil", "delta oil saturation", "oil saturation change"]):
        return "DELTA_SOIL"

    if any(x in q for x in ["soil", "oil saturation"]):
        return "SOIL_EOH"

    if any(x in q for x in ["delta sgas", "delta gas saturation", "gas saturation change"]):
        return "DELTA_SGAS"

    if any(x in q for x in ["sgas", "gas saturation"]):
        return "SGAS_EOH"

    # Transmissibility only if explicitly requested.
    if any(x in q for x in ["transmissibility", "transmissibilita", "trasmissibilita", "trasmissibilità", "tran"]):
        return "TRAN_H"

    return None


def detect_streamline_time(message: str) -> str:
    q = str(message or "").lower()

    if any(x in q for x in [
        "compare streamlines",
        "compare initial and final",
        "initial vs final",
        "start vs end",
        "beginning vs end",
        "streamline evolution",
        "streamlines evolution",
    ]):
        return "compare"

    # Initial must be checked before final.
    if any(x in q for x in [
        "initial streamlines",
        "initial streamline",
        "initial connectivity",
        "start streamlines",
        "start streamline",
        "start of history",
        "beginning of history",
        "beginning streamlines",
        "initial history",
        "at start",
        "at beginning",
        "boh",
    ]):
        return "initial"

    if any(x in q for x in [
        "final streamlines",
        "final streamline",
        "final connectivity",
        "end streamlines",
        "end streamline",
        "end of history",
        "end-history",
        "eoh",
        "at end",
        "late history",
        "current streamlines",
        "last streamlines",
    ]):
        return "final"

    return "auto"


def property_label(prop: str) -> str:
    labels = {
        "PERM_H": "Permeability",
        "TRAN_H": "Transmissibility",
        "PRESSURE_EOH": "Pressure at End of History",
        "DELTA_PRESSURE": "Pressure Depletion / ΔPressure",
        "SWAT_EOH": "Water Saturation at End of History",
        "DELTA_SWAT": "Water Saturation Change / ΔSWAT",
        "SOIL_EOH": "Oil Saturation at End of History",
        "DELTA_SOIL": "Oil Saturation Change / ΔSOIL",
        "SGAS_EOH": "Gas Saturation at End of History",
        "DELTA_SGAS": "Gas Saturation Change / ΔSGAS",
        "PORO": "Porosity",
    }
    return labels.get(prop, prop)


def build_property_map_response(message: str):
    requested_prop = detect_property(message)
    streamlines_requested = wants_streamlines(message)
    streamline_time = detect_streamline_time(message)

    # If user asks ONLY streamlines/connectivity without a base property,
    # choose TRAN_H as background. Otherwise preserve requested property.
    if not requested_prop and streamlines_requested:
        requested_prop = "TRAN_H"

    if not requested_prop:
        return None

    try:
        from app.cell_property_layers import build_cell_property_layer
        layer = build_cell_property_layer(requested_prop)
    except Exception as exc:
        return {
            "type": "visual_response",
            "answer": f"I understood the request for {property_label(requested_prop)}, but could not build the raw layer: {exc}",
            "intent": "dynamic_property_map_error",
            "ui_blocks": [],
            "data": {
                "requested_property": requested_prop,
                "streamline_time": streamline_time,
                "error": str(exc),
            },
            "agent_trace": {
                "DynamicVisualAgent": {
                    "intent": "property_map_error",
                    "requested_property": requested_prop,
                    "streamline_time": streamline_time,
                    "error": str(exc),
                }
            },
        }

    if not isinstance(layer, dict):
        layer = {"cells": []}

    # Force metadata after layer creation, even if builder returns an internal default.
    layer["requested_property"] = requested_prop
    layer["property"] = requested_prop
    layer["label"] = property_label(requested_prop)
    layer["wells"] = well_points_from_context()

    streamline_payload = load_streamline_payload(streamline_time) if streamlines_requested else None

    title = property_label(requested_prop)
    if streamline_payload:
        title += f" + Streamlines ({streamline_time_label(streamline_time)})"

    answer = (
        f"I generated an interactive {property_label(requested_prop)} map. "
        f"The selected base property is {requested_prop}."
    )

    if streamline_payload:
        answer += (
            f" Streamlines are used only as an overlay. "
            f"Requested streamline snapshot: {streamline_time_label(streamline_time)}."
        )

    return {
        "type": "visual_response",
        "answer": answer,
        "intent": "dynamic_property_map",
        "ui_blocks": [
            {
                "type": "cell_property_map",
                "title": title,
                "payload": layer,
                "streamline_payload": streamline_payload,
                "source": "DynamicVisualAgent",
                "requested_property": requested_prop,
                "overlay_streamlines": bool(streamline_payload),
                "streamline_time": streamline_time,
            }
        ],
        "data": {
            "requested_property": requested_prop,
            "property_label": property_label(requested_prop),
            "with_streamlines": bool(streamline_payload),
            "streamline_time": streamline_time,
        },
        "agent_trace": {
            "DynamicVisualAgent": {
                "intent": "property_map",
                "requested_property": requested_prop,
                "property_label": property_label(requested_prop),
                "with_streamlines": bool(streamline_payload),
                "streamline_time": streamline_time,
            }
        },
    }



# ==========================================================
# STRICT STREAMLINE LOADER V22
# Force DynamicVisualAgent to request the exact snapshot.
# Adds a hash so frontend/debug can prove initial/final are different.
# ==========================================================

def _hash_streamline_lines_v22(lines):
    try:
        import hashlib
        import json
        raw = json.dumps((lines or [])[:100], sort_keys=True, default=str)
        return hashlib.md5(raw.encode("utf-8")).hexdigest()
    except Exception:
        return ""


def load_streamline_payload(time_key: str = "auto"):
    """
    Strict loader used by DynamicVisualAgent.

    Important:
    - initial means initial only
    - final means final only
    - auto keeps default behavior
    """
    try:
        from app.streamline_visual_payloads import build_streamline_visual_payload

        payload = build_streamline_visual_payload(
            time_key=time_key,
            max_lines=800,
        )

        if isinstance(payload, dict):
            lines = payload.get("lines", [])
            payload["requested_streamline_time"] = time_key
            payload["line_hash"] = _hash_streamline_lines_v22(lines)
            payload["line_count"] = len(lines) if isinstance(lines, list) else 0
            payload["strict_loader"] = "DynamicVisualAgent.load_streamline_payload.V22"
            return payload

    except Exception as exc:
        return {
            "ok": False,
            "lines": [],
            "requested_streamline_time": time_key,
            "line_hash": "",
            "line_count": 0,
            "strict_loader": "DynamicVisualAgent.load_streamline_payload.V22",
            "message": f"Could not load streamline payload for {time_key}: {exc}",
        }

    return {
        "ok": False,
        "lines": [],
        "requested_streamline_time": time_key,
        "line_hash": "",
        "line_count": 0,
        "strict_loader": "DynamicVisualAgent.load_streamline_payload.V22",
        "message": "Streamline payload not available.",
    }



# ==========================================================
# STREAMLINE TIME LANGUAGE PATCH V23
# Broader natural-language detection for initial/final history.
# ==========================================================

def detect_streamline_time(message: str) -> str:
    q = str(message or "").lower()

    # Normalize small language variants.
    q = q.replace("-", " ").replace("_", " ")

    # Compare / evolution
    if any(x in q for x in [
        "compare streamlines",
        "compare initial and final",
        "compare initial vs final",
        "initial vs final",
        "start vs end",
        "beginning vs end",
        "streamline evolution",
        "streamlines evolution",
        "evolution of streamlines",
    ]):
        return "compare"

    # Initial / beginning of history
    initial_patterns = [
        "initial streamlines",
        "initial streamline",
        "initial connectivity",
        "initial history",
        "initial of history",
        "initial time",
        "initial timestep",
        "initial step",
        "at initial",
        "at the initial",
        "at the initial of history",
        "at the beginning",
        "at beginning",
        "beginning of history",
        "beginning history",
        "beginning streamlines",
        "start of history",
        "start history",
        "start streamlines",
        "starting streamlines",
        "early history",
        "first timestep",
        "first time step",
        "first streamlines",
        "boh",
        "init",
    ]

    if any(x in q for x in initial_patterns):
        return "initial"

    # Also catch flexible wording: "streamlines ... initial ... history"
    if "streamline" in q and "initial" in q:
        return "initial"

    if "history" in q and any(x in q for x in ["initial", "beginning", "start", "first"]):
        return "initial"

    # Final / end of history
    final_patterns = [
        "final streamlines",
        "final streamline",
        "final connectivity",
        "final history",
        "final of history",
        "end of history",
        "end history",
        "end history streamlines",
        "end streamlines",
        "at the end",
        "at end",
        "at the end of history",
        "late history",
        "last timestep",
        "last time step",
        "last streamlines",
        "current streamlines",
        "eoh",
        "final",
    ]

    if any(x in q for x in final_patterns):
        return "final"

    if "streamline" in q and any(x in q for x in ["final", "end", "last", "current", "eoh"]):
        return "final"

    if "history" in q and any(x in q for x in ["final", "end", "last", "current", "eoh"]):
        return "final"

    return "auto"
