import csv
import json
import math
import re
from pathlib import Path
from typing import Dict, Any, List, Optional


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
DASH = ART / "dashboard"
DIAG = ART / "diagnosis"


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


def norm_text(s: str) -> str:
    return str(s or "").lower().replace("-", " ").replace("_", " ")


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_csv(path: Path):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def get_wells_payload():
    candidates = [
        DASH / "hm_map_payload.json",
        DIAG / "well_property_driver_context.csv",
    ]

    # Prefer dashboard map payload if available.
    hm = load_json(candidates[0])
    wells = []

    if isinstance(hm, dict):
        for key in ["wells", "well_points", "points"]:
            arr = hm.get(key)
            if isinstance(arr, list):
                for w in arr:
                    i = safe_float(w.get("i") or w.get("I") or w.get("x") or w.get("X"))
                    j = safe_float(w.get("j") or w.get("J") or w.get("y") or w.get("Y"))
                    name = w.get("well") or w.get("name") or w.get("WELL")
                    if name and i is not None and j is not None:
                        wells.append({
                            "well": name,
                            "i": i,
                            "j": j,
                            "overall_score": safe_float(w.get("overall_score") or w.get("overall_hm_score")),
                            "water_score": safe_float(w.get("water_score") or w.get("water_hm_score")),
                            "oil_score": safe_float(w.get("oil_score") or w.get("oil_hm_score")),
                            "gas_score": safe_float(w.get("gas_score") or w.get("gas_hm_score")),
                            "bhp_score": safe_float(w.get("bhp_score") or w.get("bhp_hm_score")),
                        })
                if wells:
                    return wells

    rows = load_csv(candidates[1])
    for r in rows:
        i = safe_float(r.get("i"))
        j = safe_float(r.get("j"))
        name = r.get("well")
        if name and i is not None and j is not None:
            wells.append({
                "well": name,
                "i": i,
                "j": j,
                "overall_score": safe_float(r.get("overall_hm_score")),
                "water_score": safe_float(r.get("water_hm_score")),
                "oil_score": safe_float(r.get("oil_hm_score")),
                "gas_score": safe_float(r.get("gas_hm_score")),
                "bhp_score": safe_float(r.get("bhp_hm_score")),
            })

    return wells


def property_alias(message: str) -> Optional[str]:
    q = norm_text(message)

    aliases = [
        ("swat", "SWAT"),
        ("water saturation", "SWAT"),
        ("water sat", "SWAT"),
        ("soil", "SOIL"),
        ("oil saturation", "SOIL"),
        ("oil sat", "SOIL"),
        ("sgas", "SGAS"),
        ("gas saturation", "SGAS"),
        ("pressure", "PRESSURE"),
        ("bhp", "PRESSURE"),
        ("poro", "PORO"),
        ("porosity", "PORO"),
        ("perm", "PERM_H"),
        ("permeability", "PERM_H"),
        ("transmissibility", "TRAN_H"),
        ("trasmissibility", "TRAN_H"),
        ("tran", "TRAN_H"),
        ("mult", "MULT_H"),
        ("multiplier", "MULT_H"),
    ]

    for key, val in aliases:
        if key in q:
            return val

    return None


def detect_map_operation(message: str) -> str:
    q = norm_text(message)

    diff_words = [
        "difference",
        "delta",
        "change",
        "variation",
        "vary",
        "between end",
        "between eoh",
        "end of history and initial",
        "eoh and initial",
        "initial and end",
        "initial vs end",
        "end vs initial",
        "depletion",
    ]

    if any(x in q for x in diff_words):
        return "difference"

    if any(x in q for x in ["initial", "init", "beginning", "start of history", "boh"]):
        return "initial"

    if any(x in q for x in ["end of history", "eoh", "final", "last"]):
        return "eoh"

    return "auto"


def detect_streamline_time(message: str) -> Optional[str]:
    q = norm_text(message)

    if "streamline" not in q:
        return None

    if any(x in q for x in ["initial", "init", "beginning", "start", "boh"]):
        return "initial"

    if any(x in q for x in ["final", "eoh", "end of history", "last"]):
        return "final"

    return "final"


def is_generic_map_request(message: str) -> bool:
    q = norm_text(message)

    if "map" not in q and "show" not in q and "plot" not in q and "display" not in q:
        return False

    prop = property_alias(message)
    if not prop:
        return False

    # Do not steal TRAN corridor requests.
    if ("corridor" in q or "multiplier" in q or "ixf" in q) and prop in ["TRAN_H", "PERM_H"]:
        return False

    return True


def extract_cells_from_layer(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    candidates = [
        payload.get("cells"),
        payload.get("points"),
        payload.get("data"),
        payload.get("values"),
        payload.get("cell_values"),
        payload.get("layer"),
    ]

    for arr in candidates:
        if not isinstance(arr, list) or not arr:
            continue

        pts = []
        for item in arr:
            if not isinstance(item, dict):
                continue
            i = safe_float(item.get("i") or item.get("I") or item.get("x") or item.get("X"))
            j = safe_float(item.get("j") or item.get("J") or item.get("y") or item.get("Y"))
            v = safe_float(
                item.get("value")
                if "value" in item else
                item.get("val")
                if "val" in item else
                item.get("z")
                if "z" in item else
                item.get("Z")
                if "Z" in item else
                item.get("property_value")
                if "property_value" in item else
                item.get("mean")
                if "mean" in item else
                item.get("avg")
            )

            if i is not None and j is not None and v is not None:
                pts.append({"i": i, "j": j, "value": v})

        if pts:
            return pts

    return []


def build_single_property_layer(prop: str, operation: str = "auto"):
    from app.cell_property_layers import build_cell_property_layer

    if operation == "initial":
        candidate_names = [f"{prop}_INIT", f"{prop}_INITIAL", prop]
    elif operation == "eoh":
        candidate_names = [f"{prop}_EOH", f"{prop}_END", f"{prop}_FINAL", prop]
    else:
        candidate_names = [prop]

    last_error = None

    for name in candidate_names:
        try:
            p = build_cell_property_layer(name)
            cells = extract_cells_from_layer(p)
            if cells:
                p["requested_property"] = name
                return p
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"Could not build property layer for {prop} ({operation}). Last error: {last_error}")


def build_difference_property_layer(prop: str):
    from app.cell_property_layers import build_cell_property_layer

    init_names = [f"{prop}_INIT", f"{prop}_INITIAL"]
    eoh_names = [f"{prop}_EOH", f"{prop}_END", f"{prop}_FINAL"]

    init_layer = None
    eoh_layer = None
    init_name_used = None
    eoh_name_used = None

    for name in init_names:
        try:
            p = build_cell_property_layer(name)
            if extract_cells_from_layer(p):
                init_layer = p
                init_name_used = name
                break
        except Exception:
            pass

    for name in eoh_names:
        try:
            p = build_cell_property_layer(name)
            if extract_cells_from_layer(p):
                eoh_layer = p
                eoh_name_used = name
                break
        except Exception:
            pass

    if init_layer is None or eoh_layer is None:
        raise RuntimeError(
            f"Could not find both initial and EOH layers for {prop}. "
            f"Tried initial={init_names}, eoh={eoh_names}."
        )

    init_cells = extract_cells_from_layer(init_layer)
    eoh_cells = extract_cells_from_layer(eoh_layer)

    init_map = {(int(round(c["i"])), int(round(c["j"]))): c["value"] for c in init_cells}
    eoh_map = {(int(round(c["i"])), int(round(c["j"]))): c["value"] for c in eoh_cells}

    keys = sorted(set(init_map) & set(eoh_map))

    diff_cells = []
    for i, j in keys:
        diff_cells.append({
            "i": i,
            "j": j,
            "value": eoh_map[(i, j)] - init_map[(i, j)],
            "initial": init_map[(i, j)],
            "eoh": eoh_map[(i, j)],
        })

    return {
        "property": f"DELTA_{prop}",
        "requested_property": f"DELTA_{prop}",
        "label": f"Δ{prop} (EOH - Initial)",
        "operation": "difference",
        "source_initial": init_name_used,
        "source_eoh": eoh_name_used,
        "cells": diff_cells,
        "wells": get_wells_payload(),
    }


def build_generic_map_response(message: str):
    prop = property_alias(message)
    op = detect_map_operation(message)

    if not prop:
        return None

    if op == "difference":
        layer = build_difference_property_layer(prop)
        title = f"{prop} Difference Map (EOH - Initial)"
    else:
        layer = build_single_property_layer(prop, operation=op)
        layer["wells"] = get_wells_payload()
        if op == "initial":
            title = f"{prop} Initial Map"
        elif op == "eoh":
            title = f"{prop} End-of-History Map"
        else:
            title = f"{prop} Map"

    streamline_time = detect_streamline_time(message)
    streamline_payload = None

    if streamline_time:
        try:
            from app.streamline_visual_payloads import build_streamline_visual_payload
            streamline_payload = build_streamline_visual_payload(time_key=streamline_time, max_lines=800)
        except Exception:
            streamline_payload = None

    block = {
        "type": "generic_property_map",
        "title": title,
        "payload": {
            "layer": layer,
            "operation": op,
            "property": prop,
            "streamline_payload": streamline_payload,
            "streamline_time": streamline_time,
        },
    }

    answer = f"I prepared the {title}."

    if op == "difference":
        answer += " Values are computed as End of History minus Initial."

    if streamline_time:
        answer += f" I also overlaid {streamline_time} streamlines."

    return {
        "type": "visual_response",
        "answer": answer,
        "intent": "generic_property_map",
        "ui_blocks": [
            block,
            {
                "type": "suggestions",
                "title": "Suggested follow-up",
                "items": [
                    f"Overlay final streamlines on this {prop} map",
                    f"Show pressure depletion map",
                    f"Show WCT bias map",
                    f"Show proposed transmissibility corridor for HW-28",
                ],
            },
        ],
        "data": block["payload"],
        "agent_trace": {
            "GenericPlotAgent": {
                "mode": "property_map",
                "property": prop,
                "operation": op,
                "streamline_time": streamline_time,
            }
        },
    }


# ==========================================================
# PROFILE ENSEMBLE ENGINE
# ==========================================================

def detect_profile_variable(message: str) -> Optional[str]:
    q = norm_text(message)

    if any(x in q for x in ["water", "wct", "water cut"]):
        return "water"
    if any(x in q for x in ["oil", "opr"]):
        return "oil"
    if any(x in q for x in ["gas", "gor"]):
        return "gas"
    if any(x in q for x in ["pressure", "bhp"]):
        return "bhp"

    return None


def is_profile_ensemble_request(message: str) -> bool:
    q = norm_text(message)

    if not any(x in q for x in ["profile", "profiles", "curve", "curves", "trend", "plot"]):
        return False

    if not any(x in q for x in ["all", "every", "ensemble", "p10", "p50", "p90", "percentile", "percentiles"]):
        return False

    return detect_profile_variable(message) is not None


def percentile(values, p):
    xs = sorted([x for x in values if x is not None])
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * p / 100.0
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return xs[int(k)]
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def get_all_profile_series(variable: str):
    from app.profile_series import get_profile_series

    rows = load_csv(DIAG / "well_property_driver_context.csv")
    wells = [r.get("well") for r in rows if r.get("well")]

    out = []

    for w in sorted(set(wells)):
        try:
            p = get_profile_series(well=w, variable=variable)
            dates = p.get("dates") or p.get("x") or []
            sim = p.get("simulated") or []
            obs = p.get("observed") or []

            if dates and (sim or obs):
                out.append({
                    "well": w,
                    "dates": dates,
                    "simulated": sim,
                    "observed": obs,
                })
        except Exception:
            pass

    return out


def build_profile_ensemble(variable: str):
    series = get_all_profile_series(variable)

    # Build common x-axis by index to avoid date alignment issues.
    max_len = 0
    for s in series:
        max_len = max(max_len, len(s.get("simulated") or []), len(s.get("observed") or []))

    index = list(range(max_len))

    sim_percentiles = []
    obs_percentiles = []

    for idx in index:
        sim_values = []
        obs_values = []

        for s in series:
            sim = s.get("simulated") or []
            obs = s.get("observed") or []

            if idx < len(sim):
                sim_values.append(safe_float(sim[idx]))
            if idx < len(obs):
                obs_values.append(safe_float(obs[idx]))

        sim_percentiles.append({
            "x": idx,
            "p10": percentile(sim_values, 10),
            "p50": percentile(sim_values, 50),
            "p90": percentile(sim_values, 90),
        })

        obs_percentiles.append({
            "x": idx,
            "p10": percentile(obs_values, 10),
            "p50": percentile(obs_values, 50),
            "p90": percentile(obs_values, 90),
        })

    return {
        "variable": variable,
        "series": series,
        "x_index": index,
        "sim_percentiles": sim_percentiles,
        "obs_percentiles": obs_percentiles,
        "well_count": len(series),
    }


def build_profile_ensemble_response(message: str):
    variable = detect_profile_variable(message)

    payload = build_profile_ensemble(variable)

    return {
        "type": "visual_response",
        "answer": (
            f"I prepared an ensemble plot for all available {variable} profiles. "
            "The plot includes individual well profiles and P10/P50/P90 envelopes."
        ),
        "intent": "profile_ensemble",
        "ui_blocks": [
            {
                "type": "profile_ensemble",
                "title": f"All {variable.title()} Profiles with P10/P50/P90",
                "payload": payload,
            },
            {
                "type": "suggestions",
                "title": "Suggested follow-up",
                "items": [
                    f"Show only poor {variable} match wells",
                    f"Compare profile ensemble by WCT bias cluster",
                    f"Show {variable} profile for HW-28",
                    f"Crossplot {variable} score vs delta SWAT",
                ],
            },
        ],
        "data": payload,
        "agent_trace": {
            "GenericPlotAgent": {
                "mode": "profile_ensemble",
                "variable": variable,
                "well_count": payload.get("well_count"),
            }
        },
    }


def answer_generic_plot_question(message: str):
    # Priority: profile ensemble before simple map.
    if is_profile_ensemble_request(message):
        return build_profile_ensemble_response(message)

    if is_generic_map_request(message):
        return build_generic_map_response(message)

    return None


if __name__ == "__main__":
    for q in [
        "show me the SWAT map difference between end of history and initial",
        "show pressure depletion map",
        "show me a plot with all water profiles and highlight P10 P50 P90",
    ]:
        print("=" * 100)
        print(q)
        r = answer_generic_plot_question(q)
        print(r["intent"] if r else None)
        print(r["answer"] if r else None)
        print([b["type"] for b in r["ui_blocks"]] if r else None)



# ==========================================================
# ROBUST PROFILE ENSEMBLE EXTRACTION V56
# Extracts simulated/observed arrays from flexible profile payloads.
# Supports simulated-only ensemble requests.
# ==========================================================

def _is_number_list_v56(x):
    if not isinstance(x, list) or not x:
        return False
    good = 0
    for v in x[:20]:
        if safe_float(v) is not None:
            good += 1
    return good > 0


def _is_date_like_list_v56(x):
    if not isinstance(x, list) or not x:
        return False
    s = str(x[0])
    return any(ch in s for ch in ["-", "/", ":"]) or "T" in s


def _walk_dicts_v56(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_dicts_v56(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_dicts_v56(item)


def _find_profile_arrays_v56(payload):
    """
    Flexible extractor for profile payloads. It handles:
    - top-level dates/simulated/observed
    - nested data dictionaries
    - plotly-like traces
    - keys like sim, simulation, y_sim, observed, history, hist
    """
    if not isinstance(payload, dict):
        return {"dates": [], "simulated": [], "observed": []}

    date_keys = [
        "dates", "date", "time", "times", "x", "timeline", "timesteps", "steps"
    ]

    sim_keys = [
        "simulated", "simulation", "sim", "y_sim", "sim_values", "simulated_values",
        "simulated_rate", "sim_series", "model", "modelled", "modeled"
    ]

    obs_keys = [
        "observed", "observation", "obs", "historical", "history", "hist",
        "y_obs", "obs_values", "observed_values", "history_values"
    ]

    dates = []
    simulated = []
    observed = []

    # 1) Try obvious dictionaries first.
    for d in _walk_dicts_v56(payload):
        if not dates:
            for k in date_keys:
                if k in d and isinstance(d[k], list):
                    dates = d[k]
                    break

        if not simulated:
            for k in sim_keys:
                if k in d and _is_number_list_v56(d[k]):
                    simulated = [safe_float(v) for v in d[k]]
                    break

        if not observed:
            for k in obs_keys:
                if k in d and _is_number_list_v56(d[k]):
                    observed = [safe_float(v) for v in d[k]]
                    break

        if dates and (simulated or observed):
            break

    # 2) Try Plotly-style traces if present.
    if not simulated or not observed:
        traces = []
        for d in _walk_dicts_v56(payload):
            for key in ["traces", "data", "series"]:
                if key in d and isinstance(d[key], list):
                    traces.extend([x for x in d[key] if isinstance(x, dict)])

        for tr in traces:
            name = str(tr.get("name") or tr.get("label") or "").lower()
            y = tr.get("y") or tr.get("values")
            x = tr.get("x") or tr.get("dates") or tr.get("time")

            if not dates and isinstance(x, list):
                dates = x

            if _is_number_list_v56(y):
                vals = [safe_float(v) for v in y]

                if not simulated and any(s in name for s in ["sim", "model"]):
                    simulated = vals

                if not observed and any(s in name for s in ["obs", "hist", "history", "observed"]):
                    observed = vals

    # 3) If no dates, use profile index.
    n = max(len(simulated), len(observed))
    if not dates and n:
        dates = list(range(n))

    return {
        "dates": dates,
        "simulated": simulated,
        "observed": observed,
    }


def detect_profile_source_v56(message: str) -> str:
    q = norm_text(message)

    if "simulated" in q and not any(x in q for x in ["observed", "history", "historical", "obs"]):
        return "simulated_only"

    if any(x in q for x in ["observed", "history", "historical", "obs"]) and "simulated" not in q:
        return "observed_only"

    return "both"


def get_all_profile_series(variable: str):
    """
    V56 override.
    Build ensemble series using get_profile_series() but with flexible payload extraction.
    Accepts simulated-only or observed-only profiles.
    """
    from app.profile_series import get_profile_series

    rows = load_csv(DIAG / "well_property_driver_context.csv")
    wells = [r.get("well") for r in rows if r.get("well")]

    out = []
    checked = 0
    missing = []

    for w in sorted(set(wells)):
        checked += 1
        try:
            p = get_profile_series(well=w, variable=variable)
            arrays = _find_profile_arrays_v56(p)

            dates = arrays.get("dates") or []
            sim = arrays.get("simulated") or []
            obs = arrays.get("observed") or []

            if sim or obs:
                n = max(len(sim), len(obs), len(dates))
                if not dates:
                    dates = list(range(n))

                out.append({
                    "well": w,
                    "dates": dates,
                    "simulated": sim,
                    "observed": obs,
                    "source_status": p.get("status") or p.get("intent") or "profile_series",
                })
            else:
                missing.append(w)

        except Exception:
            missing.append(w)

    # Attach debug metadata as attribute-like hidden row is not possible, so return list only.
    return out


def build_profile_ensemble(variable: str, source_mode: str = "both"):
    """
    V56 override.
    Computes P10/P50/P90 on simulated, observed, or both depending on request.
    """
    series_all = get_all_profile_series(variable)

    series = []
    for s in series_all:
        sim = s.get("simulated") or []
        obs = s.get("observed") or []

        if source_mode == "simulated_only" and not sim:
            continue
        if source_mode == "observed_only" and not obs:
            continue
        if source_mode == "both" and not (sim or obs):
            continue

        series.append(s)

    max_len = 0
    for s in series:
        if source_mode in ["both", "simulated_only"]:
            max_len = max(max_len, len(s.get("simulated") or []))
        if source_mode in ["both", "observed_only"]:
            max_len = max(max_len, len(s.get("observed") or []))

    index = list(range(max_len))

    sim_percentiles = []
    obs_percentiles = []

    for idx in index:
        sim_values = []
        obs_values = []

        for s in series:
            sim = s.get("simulated") or []
            obs = s.get("observed") or []

            if idx < len(sim):
                v = safe_float(sim[idx])
                if v is not None:
                    sim_values.append(v)

            if idx < len(obs):
                v = safe_float(obs[idx])
                if v is not None:
                    obs_values.append(v)

        sim_percentiles.append({
            "x": idx,
            "p10": percentile(sim_values, 10),
            "p50": percentile(sim_values, 50),
            "p90": percentile(sim_values, 90),
        })

        obs_percentiles.append({
            "x": idx,
            "p10": percentile(obs_values, 10),
            "p50": percentile(obs_values, 50),
            "p90": percentile(obs_values, 90),
        })

    return {
        "variable": variable,
        "source_mode": source_mode,
        "series": series,
        "x_index": index,
        "sim_percentiles": sim_percentiles,
        "obs_percentiles": obs_percentiles,
        "well_count": len(series),
        "available_series_before_filter": len(series_all),
    }


def build_profile_ensemble_response(message: str):
    """
    V56 override.
    """
    variable = detect_profile_variable(message)
    source_mode = detect_profile_source_v56(message)

    payload = build_profile_ensemble(variable, source_mode=source_mode)

    label = "simulated" if source_mode == "simulated_only" else "observed" if source_mode == "observed_only" else "simulated/observed"

    return {
        "type": "visual_response",
        "answer": (
            f"I prepared an ensemble plot for all available {label} {variable} profiles. "
            "The plot includes individual well profiles and P10/P50/P90 percentiles."
        ),
        "intent": "profile_ensemble",
        "ui_blocks": [
            {
                "type": "profile_ensemble",
                "title": f"All {variable.title()} Profiles with P10/P50/P90",
                "payload": payload,
            },
            {
                "type": "suggestions",
                "title": "Suggested follow-up",
                "items": [
                    f"Show only poor {variable} match wells",
                    f"Compare profile ensemble by WCT bias cluster",
                    f"Show {variable} profile for HW-28",
                    f"Crossplot {variable} score vs delta SWAT",
                ],
            },
        ],
        "data": payload,
        "agent_trace": {
            "GenericPlotAgentV56": {
                "mode": "profile_ensemble",
                "variable": variable,
                "source_mode": source_mode,
                "well_count": payload.get("well_count"),
                "available_series_before_filter": payload.get("available_series_before_filter"),
            }
        },
    }
