import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"

CONTEXT_CSV = ART / "diagnosis" / "well_property_driver_context.csv"
FINAL_JSON = ART / "final_diagnosis" / "final_hm_diagnosis.json"

WCT_THRESHOLD = 0.01  # 1.0% as fraction


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


def load_csv(path: Path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows):
    if not rows:
        return

    keys = []
    seen = set()

    for r in rows:
        for k in r.keys():
            if k not in seen:
                keys.append(k)
                seen.add(k)

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def flatten_numeric(x):
    out = []

    if x is None:
        return out

    if isinstance(x, list):
        for item in x:
            out.extend(flatten_numeric(item))
        return out

    if isinstance(x, dict):
        for v in x.values():
            out.extend(flatten_numeric(v))
        return out

    v = safe_float(x)
    if v is not None:
        out.append(v)

    return out


def find_array(obj, includes, excludes=None):
    excludes = excludes or []

    if isinstance(obj, dict):
        # First pass: direct key match
        for k, v in obj.items():
            lk = str(k).lower()
            if any(x in lk for x in includes) and not any(x in lk for x in excludes):
                arr = flatten_numeric(v)
                if arr:
                    return arr

        # Recursive pass
        for v in obj.values():
            found = find_array(v, includes, excludes)
            if found:
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = find_array(item, includes, excludes)
            if found:
                return found

    return []


def get_profile(well: str, variable: str):
    try:
        from app.profile_series import get_profile_series
        return get_profile_series(well=well, variable=variable)
    except Exception:
        return None


def extract_sim_obs(payload):
    """
    Extract generic simulated and observed arrays from a profile payload.
    """
    if not payload:
        return [], []

    sim = find_array(payload, ["simulated", "simulation", "sim"], ["observed", "obs", "hist"])
    obs = find_array(payload, ["observed", "historical", "history", "hist", "obs"], ["sim"])

    return sim, obs


def get_direct_wct_arrays(well: str):
    """
    Try direct WCT profiles first.
    """
    for var in ["wct", "water_cut", "watercut"]:
        payload = get_profile(well, var)
        if not payload:
            continue

        sim = find_array(payload, ["sim_wct", "simulated_wct", "simulation_wct", "sim_water_cut", "simulated_water_cut"])
        obs = find_array(payload, ["obs_wct", "observed_wct", "hist_wct", "historical_wct", "obs_water_cut", "observed_water_cut"])

        if not sim:
            sim = find_array(payload, ["simulated", "simulation", "sim"], ["observed", "obs", "hist"])
        if not obs:
            obs = find_array(payload, ["observed", "historical", "history", "hist", "obs"], ["sim"])

        if sim and obs:
            return sim, obs, "direct_wct_profile"

    return [], [], "direct_wct_not_available"


def get_rate_based_wct_arrays(well: str):
    """
    Compute WCT from oil and water rate profiles:
    WCT = water / (oil + water)
    """
    water_payload = get_profile(well, "water")
    oil_payload = get_profile(well, "oil")

    water_sim, water_obs = extract_sim_obs(water_payload)
    oil_sim, oil_obs = extract_sim_obs(oil_payload)

    n_sim = min(len(water_sim), len(oil_sim))
    n_obs = min(len(water_obs), len(oil_obs))

    sim_wct = []
    obs_wct = []

    for i in range(n_sim):
        w = safe_float(water_sim[i])
        o = safe_float(oil_sim[i])

        if w is None or o is None:
            continue

        denom = w + o

        if denom > 0:
            sim_wct.append(w / denom)

    for i in range(n_obs):
        w = safe_float(water_obs[i])
        o = safe_float(oil_obs[i])

        if w is None or o is None:
            continue

        denom = w + o

        if denom > 0:
            obs_wct.append(w / denom)

    return sim_wct, obs_wct, "computed_from_water_and_oil_rates"



def get_context_row_for_well(well: str):
    rows = load_csv(CONTEXT_CSV)
    target = str(well or "").strip().upper()

    for row in rows:
        if str(row.get("well") or "").strip().upper() == target:
            return row

    return None


def get_context_max_signal_wct_arrays(well: str):
    """
    Fallback when full time profiles are not available.

    Uses diagnostic CSV max signals:
      simulated WCT ~= water_max_sim_signal / (max_simulated_oil_rate + water_max_sim_signal)
      observed  WCT ~= water_max_hist_signal / (max_observed_oil_rate + water_max_hist_signal)

    This is not as precise as timestep-aligned WCT, but it is conservative enough
    for the negligible-water override.
    """
    row = get_context_row_for_well(well)

    if not row:
        return [], [], "context_row_not_found"

    sim_water = safe_float(row.get("water_max_sim_signal"))
    obs_water = safe_float(row.get("water_max_hist_signal"))

    sim_oil = safe_float(row.get("max_simulated_oil_rate"))
    obs_oil = safe_float(row.get("max_observed_oil_rate"))

    sim_wct = []
    obs_wct = []

    if sim_water is not None and sim_oil is not None and (sim_water + sim_oil) > 0:
        sim_wct = [sim_water / (sim_water + sim_oil)]

    if obs_water is not None and obs_oil is not None and (obs_water + obs_oil) > 0:
        obs_wct = [obs_water / (obs_water + obs_oil)]

    return sim_wct, obs_wct, "computed_from_context_max_water_and_oil_signals"


def get_best_wct_arrays(well: str):
    sim, obs, source = get_direct_wct_arrays(well)

    if sim and obs:
        # If values look like percent scale, convert to fraction.
        if max([abs(x) for x in sim + obs if x is not None], default=0) > 1.5:
            sim = [x / 100.0 for x in sim]
            obs = [x / 100.0 for x in obs]
            source += "_converted_percent_to_fraction"
        return sim, obs, source

    sim, obs, source = get_rate_based_wct_arrays(well)

    if sim and obs:
        return sim, obs, source

    # Final fallback: use max water/oil signals already stored in diagnostic CSV.
    sim, obs, source = get_context_max_signal_wct_arrays(well)
    return sim, obs, source


def max_abs(values):
    clean = [abs(x) for x in values if x is not None and math.isfinite(x)]
    return max(clean) if clean else None


def is_negligible_wct(well: str):
    sim, obs, source = get_best_wct_arrays(well)

    max_sim = max_abs(sim)
    max_obs = max_abs(obs)

    ok = (
        max_sim is not None
        and max_obs is not None
        and max_sim < WCT_THRESHOLD
        and max_obs < WCT_THRESHOLD
    )

    return ok, {
        "source": source,
        "max_sim_wct": max_sim,
        "max_obs_wct": max_obs,
        "threshold": WCT_THRESHOLD,
        "sim_points": len(sim),
        "obs_points": len(obs),
    }


def recompute_overall(row):
    vals = []

    for key, status_key in [
        ("oil_hm_score", "oil_status"),
        ("water_hm_score", "water_status"),
        ("gas_hm_score", "gas_status"),
        ("bhp_hm_score", "bhp_status"),
    ]:
        status = str(row.get(status_key) or "").lower()

        if any(x in status for x in ["not", "missing", "unavailable", "no_observed"]):
            continue

        v = safe_float(row.get(key))

        if v is not None:
            vals.append(v)

    if not vals:
        return

    overall = sum(vals) / len(vals)
    row["overall_hm_score"] = round(overall, 2)

    if overall >= 80:
        row["overall_hm_class"] = "Good"
    elif overall >= 60:
        row["overall_hm_class"] = "Fair"
    else:
        row["overall_hm_class"] = "Poor"


def apply_to_context():
    rows = load_csv(CONTEXT_CSV)
    changed = 0

    for row in rows:
        well = str(row.get("well") or "").strip()
        if not well:
            continue

        ok, ev = is_negligible_wct(well)

        row["wct_override_source"] = ev["source"]
        row["wct_override_max_sim_wct"] = ev["max_sim_wct"]
        row["wct_override_max_obs_wct"] = ev["max_obs_wct"]
        row["wct_override_threshold"] = ev["threshold"]
        row["wct_override_sim_points"] = ev["sim_points"]
        row["wct_override_obs_points"] = ev["obs_points"]

        if not ok:
            continue

        row["water_hm_score"] = 100.0
        row["water_hm_class"] = "Good"
        row["water_status"] = "evaluated"
        row["water_negligible_match"] = "True"
        row["water_direction"] = "negligible_water_both_sim_and_observed"
        row["water_timing_issue"] = "not_applicable_negligible_water"
        row["water_issue_type"] = "no_material_water_mismatch"
        row["water_full_trend_score"] = 100.0
        row["water_recent_2yr_score"] = 100.0
        row["water_final_score"] = 100.0
        row["water_override_reason"] = (
            "Both observed and simulated WCT are below 1.0%; "
            "water HM set to 100 / Good."
        )

        recompute_overall(row)
        changed += 1

    write_csv(CONTEXT_CSV, rows)
    return changed


def apply_to_final_json():
    payload = load_json(FINAL_JSON)

    if payload is None:
        return 0

    if isinstance(payload, list):
        items = payload
    else:
        items = payload.get("diagnoses") or payload.get("items") or []

    changed = 0

    for item in items:
        well = str(item.get("well") or "").strip()

        if not well:
            continue

        ok, ev = is_negligible_wct(well)

        if not ok:
            continue

        item["water_hm_score"] = 100.0
        item["water_hm_class"] = "Good"
        item["water_issue_type"] = "no_material_water_mismatch"
        item["water_timing_issue"] = "not_applicable_negligible_water"
        item["water_direction"] = "negligible_water_both_sim_and_observed"
        item["primary_driver"] = "no_material_water_mismatch"
        item["driver_family"] = "no_action_required"
        item["confidence"] = "high"
        item["recommended_action"] = (
            "No water-specific HM action is required. "
            "Both observed and simulated WCT are below 1.0%."
        )
        item["decision_evidence"] = [
            f"Maximum observed WCT = {ev['max_obs_wct']:.6g}",
            f"Maximum simulated WCT = {ev['max_sim_wct']:.6g}",
            "Both are below the 0.01 fraction threshold.",
            f"WCT source: {ev['source']}",
        ]

        changed += 1

    write_json(FINAL_JSON, payload)
    return changed


def main():
    n1 = apply_to_context()
    n2 = apply_to_final_json()

    print(f"[OK] Context rows updated: {n1}")
    print(f"[OK] Final diagnosis rows updated: {n2}")
    print("Rule applied: if max simulated WCT < 0.01 and max observed WCT < 0.01, Water HM = 100 / Good.")


if __name__ == "__main__":
    main()
