
import csv
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT / "artifacts" / "diagnosis"


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


def load_csv(path: Path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def detect_variable(message: str) -> Optional[str]:
    q = norm_text(message)

    if any(x in q for x in ["water", "wct", "water cut", "wwpr"]):
        return "water"

    if any(x in q for x in ["oil", "opr", "wopr"]):
        return "oil"

    if any(x in q for x in ["gas", "gor", "wgpr"]):
        return "gas"

    if any(x in q for x in ["pressure", "bhp", "wbp"]):
        return "bhp"

    return None


def detect_source_mode(message: str) -> str:
    q = norm_text(message)

    has_sim = any(x in q for x in ["simulated", "simulation", "sim", "model"])
    has_obs = any(x in q for x in ["observed", "history", "historical", "obs", "measured"])

    if has_sim and not has_obs:
        return "simulated_only"

    if has_obs and not has_sim:
        return "observed_only"

    return "both"


def is_profile_ensemble_request(message: str) -> bool:
    q = norm_text(message)

    if not detect_variable(message):
        return False

    profile_words = ["profile", "profiles", "curve", "curves", "trend", "trends", "plot"]
    ensemble_words = ["all", "every", "ensemble", "p10", "p50", "p90", "percentile", "percentiles"]

    return any(x in q for x in profile_words) and any(x in q for x in ensemble_words)


def percentile(values: List[float], p: float):
    xs = sorted([safe_float(v) for v in values if safe_float(v) is not None])
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


def walk_objects(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk_objects(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk_objects(item)


def is_numeric_array(x):
    if not isinstance(x, list) or not x:
        return False

    valid = 0
    for v in x[:30]:
        if safe_float(v) is not None:
            valid += 1

    return valid > 0


def clean_numeric_array(x):
    if not isinstance(x, list):
        return []

    out = []
    for v in x:
        fv = safe_float(v)
        if fv is not None:
            out.append(fv)
        else:
            out.append(None)

    # Trim trailing None
    while out and out[-1] is None:
        out.pop()

    return out


def extract_profile_arrays(payload: Dict[str, Any]) -> Dict[str, List[Any]]:
    """
    Flexible profile extractor.
    Supports:
    - top-level dates/simulated/observed
    - nested payloads
    - Plotly traces
    - list of series objects
    """
    if not isinstance(payload, dict):
        return {"dates": [], "simulated": [], "observed": []}

    date_keys = [
        "dates", "date", "time", "times", "x", "timeline", "timesteps", "steps"
    ]

    sim_keys = [
        "simulated", "simulation", "sim", "model", "modeled", "modelled",
        "y_sim", "sim_values", "simulated_values", "simulated_rate",
        "sim_series", "simulation_values"
    ]

    obs_keys = [
        "observed", "observation", "obs", "history", "historical", "hist",
        "measured", "y_obs", "obs_values", "observed_values",
        "history_values", "historical_values"
    ]

    dates = []
    simulated = []
    observed = []

    # Direct / nested dictionaries
    for d in walk_objects(payload):
        if not isinstance(d, dict):
            continue

        if not dates:
            for k in date_keys:
                if isinstance(d.get(k), list):
                    dates = d.get(k)
                    break

        if not simulated:
            for k in sim_keys:
                if is_numeric_array(d.get(k)):
                    simulated = clean_numeric_array(d.get(k))
                    break

        if not observed:
            for k in obs_keys:
                if is_numeric_array(d.get(k)):
                    observed = clean_numeric_array(d.get(k))
                    break

        if dates and (simulated or observed):
            break

    # Plotly-like traces
    traces = []

    for d in walk_objects(payload):
        if not isinstance(d, dict):
            continue

        for key in ["traces", "data", "series", "plot_data"]:
            arr = d.get(key)
            if isinstance(arr, list):
                traces.extend([x for x in arr if isinstance(x, dict)])

    for tr in traces:
        name = str(tr.get("name") or tr.get("label") or "").lower()
        y = tr.get("y") or tr.get("values") or tr.get("data")
        x = tr.get("x") or tr.get("dates") or tr.get("time")

        if not dates and isinstance(x, list):
            dates = x

        if is_numeric_array(y):
            vals = clean_numeric_array(y)

            if not simulated and any(s in name for s in ["sim", "model"]):
                simulated = vals

            if not observed and any(s in name for s in ["obs", "hist", "history", "measured"]):
                observed = vals

    n = max(len(simulated), len(observed), len(dates))

    if not dates and n:
        dates = list(range(n))

    return {
        "dates": dates,
        "simulated": simulated,
        "observed": observed,
    }


def get_well_list():
    rows = load_csv(DIAG / "well_property_driver_context.csv")

    wells = []
    for r in rows:
        w = r.get("well")
        if not w:
            continue

        excluded = str(r.get("exclude_from_hm") or "").lower() in ["true", "1", "yes"]

        if not excluded:
            wells.append(w)

    return sorted(set(wells))


def get_all_profile_series(variable: str, source_mode: str = "both"):
    from app.profile_series import get_profile_series

    wells = get_well_list()
    out = []
    missing = []

    for w in wells:
        try:
            payload = get_profile_series(well=w, variable=variable)
            arrays = extract_profile_arrays(payload)

            sim = arrays.get("simulated") or []
            obs = arrays.get("observed") or []
            dates = arrays.get("dates") or []

            if source_mode == "simulated_only" and not sim:
                missing.append(w)
                continue

            if source_mode == "observed_only" and not obs:
                missing.append(w)
                continue

            if source_mode == "both" and not (sim or obs):
                missing.append(w)
                continue

            n = max(len(sim), len(obs), len(dates))
            if not dates and n:
                dates = list(range(n))

            out.append({
                "well": w,
                "dates": dates,
                "simulated": sim,
                "observed": obs,
            })

        except Exception:
            missing.append(w)

    return out, missing


def compute_percentiles(series: List[Dict[str, Any]], source_mode: str):
    max_len = 0

    for s in series:
        if source_mode != "observed_only":
            max_len = max(max_len, len(s.get("simulated") or []))

        if source_mode != "simulated_only":
            max_len = max(max_len, len(s.get("observed") or []))

    sim_pct = []
    obs_pct = []

    for idx in range(max_len):
        sim_vals = []
        obs_vals = []

        for s in series:
            sim = s.get("simulated") or []
            obs = s.get("observed") or []

            if idx < len(sim):
                v = safe_float(sim[idx])
                if v is not None:
                    sim_vals.append(v)

            if idx < len(obs):
                v = safe_float(obs[idx])
                if v is not None:
                    obs_vals.append(v)

        sim_pct.append({
            "x": idx,
            "p10": percentile(sim_vals, 10),
            "p50": percentile(sim_vals, 50),
            "p90": percentile(sim_vals, 90),
        })

        obs_pct.append({
            "x": idx,
            "p10": percentile(obs_vals, 10),
            "p50": percentile(obs_vals, 50),
            "p90": percentile(obs_vals, 90),
        })

    return sim_pct, obs_pct


def build_profile_ensemble_payload(variable: str, source_mode: str):
    series, missing = get_all_profile_series(variable, source_mode=source_mode)
    sim_pct, obs_pct = compute_percentiles(series, source_mode)

    return {
        "variable": variable,
        "source_mode": source_mode,
        "series": series,
        "sim_percentiles": sim_pct,
        "obs_percentiles": obs_pct,
        "well_count": len(series),
        "missing_well_count": len(missing),
        "missing_wells": missing[:30],
    }


def answer_profile_ensemble_question(message: str):
    if not is_profile_ensemble_request(message):
        return None

    variable = detect_variable(message)
    source_mode = detect_source_mode(message)

    payload = build_profile_ensemble_payload(variable, source_mode)

    source_label = (
        "simulated" if source_mode == "simulated_only"
        else "observed" if source_mode == "observed_only"
        else "simulated/observed"
    )

    return {
        "type": "visual_response",
        "answer": (
            f"I prepared an ensemble plot for all available {source_label} {variable} profiles. "
            f"The plot highlights P10, P50 and P90 across {payload.get('well_count')} wells."
        ),
        "intent": "profile_ensemble",
        "ui_blocks": [
            {
                "type": "profile_ensemble",
                "title": f"All {variable.title()} Profiles - P10 / P50 / P90",
                "payload": payload,
            },
            {
                "type": "suggestions",
                "title": "Suggested follow-up",
                "items": [
                    f"Show only poor {variable} match wells",
                    f"Show observed {variable} profiles with P10 P50 P90",
                    f"Compare {variable} profiles for HW-24 and HW-28",
                    f"Crossplot {variable} score vs delta SWAT",
                ],
            },
        ],
        "data": payload,
        "agent_trace": {
            "ProfileEnsembleAgent": {
                "variable": variable,
                "source_mode": source_mode,
                "well_count": payload.get("well_count"),
                "missing_well_count": payload.get("missing_well_count"),
            }
        },
    }


if __name__ == "__main__":
    q = "show me all water profiles simulated for all wells and highlight p10, p50, p90"
    r = answer_profile_ensemble_question(q)
    print(json.dumps({
        "intent": r.get("intent") if r else None,
        "answer": r.get("answer") if r else None,
        "well_count": r.get("data", {}).get("well_count") if r else None,
        "missing": r.get("data", {}).get("missing_well_count") if r else None,
        "blocks": [b.get("type") for b in r.get("ui_blocks", [])] if r else None,
    }, indent=2))
