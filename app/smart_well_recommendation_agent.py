import csv
import json
import math
from pathlib import Path
from typing import Dict, Any, List, Optional


ROOT = Path(__file__).resolve().parents[1]
CONTEXT_CSV = ROOT / "artifacts" / "diagnosis" / "well_property_driver_context.csv"
OUTPUT_JSON = ROOT / "artifacts" / "diagnosis" / "smart_well_recommendations.json"
OUTPUT_CSV = ROOT / "artifacts" / "diagnosis" / "smart_well_recommendations.csv"


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


def load_rows():
    if not CONTEXT_CSV.exists():
        return []

    with CONTEXT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm_well(w):
    return str(w or "").strip().upper()


def get_row(rows, well):
    target = norm_well(well)
    for r in rows:
        if norm_well(r.get("well")) == target:
            return r
    return None


def is_excluded(row):
    if str(row.get("exclude_from_hm") or "").lower() in ["true", "1", "yes"]:
        return True
    if str(row.get("inactive_producer_zero_oil_history") or "").lower() in ["true", "1", "yes"]:
        return True
    if str(row.get("well_activity_status") or "").lower().startswith("inactive"):
        return True
    return False


def distance(a, b):
    ai = safe_float(a.get("i"))
    aj = safe_float(a.get("j"))
    bi = safe_float(b.get("i"))
    bj = safe_float(b.get("j"))

    if None in [ai, aj, bi, bj]:
        return None

    return math.sqrt((ai - bi) ** 2 + (aj - bj) ** 2)


def clean_flag(v):
    return str(v or "").strip().replace("_", " ")


def classify_wct_bias(row):
    direction = str(
        row.get("water_direction") or
        row.get("water_final_direction") or
        row.get("water_recent_2yr_direction") or
        ""
    ).lower()

    timing = str(row.get("water_timing_issue") or "").lower()
    water_score = safe_float(row.get("water_hm_score"))

    if "negligible" in direction or str(row.get("water_negligible_match") or "").lower() in ["true", "1", "yes"]:
        return "negligible"

    if "simulated_too_low" in direction or "too low" in direction or "under" in direction:
        return "underestimated_wct"

    if "simulated_too_high" in direction or "too high" in direction or "over" in direction:
        return "overestimated_wct"

    if "early" in timing:
        return "overestimated_wct_early"

    if "late" in timing or "no_breakthrough" in timing:
        return "underestimated_wct_late"

    if water_score is None:
        return "not_evaluated"

    if water_score >= 75:
        return "balanced"

    return "weak_unclear"


def nearby_similar_wells(rows, target, radius=25.0):
    target_bias = classify_wct_bias(target)
    target_timing = str(target.get("water_timing_issue") or "")
    target_dir = str(target.get("water_direction") or target.get("water_final_direction") or "")

    out = []

    for r in rows:
        if norm_well(r.get("well")) == norm_well(target.get("well")):
            continue
        if is_excluded(r):
            continue

        d = distance(target, r)
        if d is None or d > radius:
            continue

        bias = classify_wct_bias(r)
        timing = str(r.get("water_timing_issue") or "")
        direction = str(r.get("water_direction") or r.get("water_final_direction") or "")

        same_bias = bias == target_bias and bias not in ["balanced", "negligible", "not_evaluated"]
        same_timing = target_timing and timing == target_timing
        same_direction = target_dir and direction == target_dir

        water_score = safe_float(r.get("water_hm_score"))
        weak_water = water_score is not None and water_score < 75

        similarity_score = 0
        if same_bias:
            similarity_score += 3
        if same_timing:
            similarity_score += 2
        if same_direction:
            similarity_score += 2
        if weak_water:
            similarity_score += 1

        if similarity_score >= 3:
            out.append({
                "well": r.get("well"),
                "distance": d,
                "similarity_score": similarity_score,
                "water_score": water_score,
                "bias": bias,
                "timing": clean_flag(timing),
                "direction": clean_flag(direction),
                "delta_swat_percentile": safe_float(r.get("delta_swat_percentile")),
                "tran_percentile": safe_float(r.get("wellconn_weighted_tran_h_percentile")),
                "perm_percentile": safe_float(r.get("mean_perm_h_percentile")),
            })

    out.sort(key=lambda x: (-x["similarity_score"], x["distance"]))
    return out




# ==========================================================
# V338 WATER-MISMATCH DIRECTION GUARD
# Purpose:
#   Do not recommend increasing TRAN / water mobility when
#   simulated water is already higher than observed water.
# ==========================================================
def _water_bias_direction_v338(row):
    """
    Returns:
      overestimated_wct   -> simulated water/WCT is too high vs observed
      underestimated_wct  -> simulated water/WCT is too low vs observed
      None                -> direction not safely inferred

    This is intentionally conservative and is used as a guardrail on top of
    classify_wct_bias(row), because recommendation direction must depend on
    the sign of the mismatch, not only on water HM score severity.
    """

    def _txt(v):
        return str(v or "").strip().lower()

    text_fields = [
        "water_bias_direction",
        "water_mismatch_direction",
        "water_direction",
        "water_final_direction",
        "wct_bias",
        "wct_direction",
        "bias",
        "direction",
    ]

    joined = " ".join(_txt(row.get(k)) for k in text_fields)

    over_tokens = [
        "overestimated_wct",
        "overestimated",
        "over-estimated",
        "too high",
        "too_high",
        "simulated high",
        "simulated_high",
        "sim high",
        "sim_high",
        "simulated > observed",
        "sim > obs",
        "model > history",
        "model above history",
        "above observed",
        "higher than observed",
        "higher_than_observed",
        "early water",
        "early breakthrough",
        "too early",
    ]

    under_tokens = [
        "underestimated_wct",
        "underestimated",
        "under-estimated",
        "too low",
        "too_low",
        "simulated low",
        "simulated_low",
        "sim low",
        "sim_low",
        "simulated < observed",
        "sim < obs",
        "model < history",
        "model below history",
        "below observed",
        "lower than observed",
        "lower_than_observed",
        "late water",
        "late breakthrough",
        "too late",
        "delayed",
    ]

    if any(tok in joined for tok in over_tokens):
        return "overestimated_wct"

    if any(tok in joined for tok in under_tokens):
        return "underestimated_wct"

    # Numeric fallback. Look for simulated/history water or WCT values.
    # This tries to be generic because different files may use different column names.
    def _is_waterish(k):
        lk = str(k).lower()
        return any(x in lk for x in ["water", "wct", "wwct", "wwpr", "wwpt"])

    def _is_bad_metric(k):
        lk = str(k).lower()
        return any(x in lk for x in [
            "score", "percentile", "rank", "distance", "issue",
            "timing", "direction", "flag", "class"
        ])

    def _is_sim(k):
        lk = str(k).lower()
        return any(x in lk for x in ["sim", "model", "calc", "pred", "forecast"])

    def _is_obs(k):
        lk = str(k).lower()
        return any(x in lk for x in ["obs", "hist", "history", "meas", "actual"])

    sim_vals = []
    obs_vals = []

    for k, v in dict(row).items():
        if not _is_waterish(k) or _is_bad_metric(k):
            continue

        try:
            val = safe_float(v)
        except Exception:
            val = None

        if val is None:
            continue

        if _is_sim(k):
            sim_vals.append(val)
        elif _is_obs(k):
            obs_vals.append(val)

    if sim_vals and obs_vals:
        # Use the last available values as a pragmatic final/late-history proxy.
        sim = sim_vals[-1]
        obs = obs_vals[-1]
        denom = max(abs(obs), abs(sim), 1e-6)
        rel = (sim - obs) / denom

        # 10% normalized mismatch threshold to avoid flipping on noise.
        if rel > 0.10:
            return "overestimated_wct"

        if rel < -0.10:
            return "underestimated_wct"

    return None


def build_smart_recommendation(row, rows):
    well = row.get("well")
    water_score = safe_float(row.get("water_hm_score"))
    oil_score = safe_float(row.get("oil_hm_score"))
    gas_score = safe_float(row.get("gas_hm_score"))
    bhp_score = safe_float(row.get("bhp_hm_score"))

    timing = clean_flag(row.get("water_timing_issue"))
    direction = clean_flag(row.get("water_direction") or row.get("water_final_direction"))

    # V345 guardrail:
    # First use real profile evidence from artifacts. Text-based recommendation can be stale.
    try:
        from app.water_bias_direction import detect_water_bias_direction
        well_for_v345 = row.get("well") or row.get("well_name") or row.get("name") or ""
        water_bias_profile_v345 = detect_water_bias_direction(well_for_v345)
        bias = (
            water_bias_profile_v345.get("direction")
            if water_bias_profile_v345.get("direction") in ["overestimated_wct", "underestimated_wct"]
            else None
        ) or _water_bias_direction_v338(row) or classify_wct_bias(row)
    except Exception:
        water_bias_profile_v345 = {"direction": "unknown", "method": "failed"}
        bias = _water_bias_direction_v338(row) or classify_wct_bias(row)

    delta_swat_pct = safe_float(row.get("delta_swat_percentile"))
    swat_eoh_pct = safe_float(row.get("mean_swat_eoh_percentile"))
    pressure_depl_pct = safe_float(row.get("delta_pressure_percentile"))
    tran_pct = safe_float(row.get("wellconn_weighted_tran_h_percentile"))
    perm_pct = safe_float(row.get("mean_perm_h_percentile"))

    similar = nearby_similar_wells(rows, row, radius=25.0)
    similar_names = [x["well"] for x in similar[:4]]

    pattern_type = "isolated"
    if len(similar) >= 3:
        pattern_type = "local_cluster"
    elif len(similar) >= 1:
        pattern_type = "weak_local_pattern"

    # Main issue
    key_findings = []

    if water_score is not None and water_score < 75:
        key_findings.append(f"Water match is the main concern ({water_score:.1f}/100).")

    if bhp_score is not None:
        if bhp_score >= 75:
            key_findings.append(f"Pressure/BHP is acceptable ({bhp_score:.1f}/100), so pressure alone is unlikely to explain the issue.")
        elif bhp_score < 60:
            key_findings.append(f"Pressure/BHP is also weak ({bhp_score:.1f}/100), so pressure support may be part of the issue.")
        else:
            key_findings.append(f"Pressure/BHP is moderate ({bhp_score:.1f}/100), so it should be checked but is not the only driver.")

    if bias in ["overestimated_wct", "overestimated_wct_early"]:
        key_findings.append("The model appears to bring water too early or too strongly.")
    elif bias in ["underestimated_wct", "underestimated_wct_late"]:
        key_findings.append("The model appears to bring too little water or delays water breakthrough.")
    elif bias == "negligible":
        key_findings.append("Water is negligible in both observed and simulated profiles; water tuning is not material for this well.")
    elif bias == "weak_unclear":
        key_findings.append("Water match is weak, but the over/under-estimation direction is not clear from the current diagnostics.")

    # Pattern context
    if pattern_type == "local_cluster":
        pattern_context = (
            f"This does not look isolated. Nearby wells {', '.join(similar_names)} show a similar water-mismatch signature."
        )
    elif pattern_type == "weak_local_pattern":
        pattern_context = (
            f"There is partial local support: {', '.join(similar_names)} show a related water-mismatch signature."
        )
    else:
        pattern_context = (
            "This looks more isolated. Nearby wells do not show a strong matching water-mismatch signature."
        )

    # Evidence-based interpretation
    evidence = []

    if delta_swat_pct is not None:
        if delta_swat_pct >= 70:
            evidence.append(f"high ΔSWAT percentile ({delta_swat_pct:.0f})")
        elif delta_swat_pct <= 30:
            evidence.append(f"low ΔSWAT percentile ({delta_swat_pct:.0f})")

    if tran_pct is not None:
        if tran_pct >= 70:
            evidence.append(f"high TRAN percentile ({tran_pct:.0f})")
        elif tran_pct <= 30:
            evidence.append(f"low TRAN percentile ({tran_pct:.0f})")

    if perm_pct is not None:
        if perm_pct >= 70:
            evidence.append(f"high PERM percentile ({perm_pct:.0f})")
        elif perm_pct <= 30:
            evidence.append(f"low PERM percentile ({perm_pct:.0f})")

    if pressure_depl_pct is not None:
        if pressure_depl_pct >= 70:
            evidence.append(f"high pressure-depletion percentile ({pressure_depl_pct:.0f})")
        elif pressure_depl_pct <= 30:
            evidence.append(f"low pressure-depletion percentile ({pressure_depl_pct:.0f})")

    if evidence:
        evidence_text = "Local evidence: " + "; ".join(evidence) + "."
    else:
        evidence_text = "Local evidence does not show a single dominant property signal."

    # Specific recommended action focused on what we can actually tune:
    # - transmissibility around completed cells
    # - transmissibility along preferential corridor / streamlines
    # - fault transmissibility if a nearby fault exists
    # - permeability / multiplier consistency
    # - relperm/SATNUM only when local evidence is weak or the pattern is regional/systemic

    local_tran_high = tran_pct is not None and tran_pct >= 65
    local_tran_low = tran_pct is not None and tran_pct <= 40
    local_perm_high = perm_pct is not None and perm_pct >= 65
    local_perm_low = perm_pct is not None and perm_pct <= 40
    dswat_high = delta_swat_pct is not None and delta_swat_pct >= 65
    dswat_low = delta_swat_pct is not None and delta_swat_pct <= 35

    if bias in ["overestimated_wct", "overestimated_wct_early"]:
        # Simulated water is too high / too early.
        if pattern_type in ["local_cluster", "weak_local_pattern"]:
            if local_tran_high or local_perm_high:
                recommended = (
                    "Treat this as a local high/early-water connectivity problem, not as a single-well issue. "
                    "The first tuning candidate is local transmissibility: reduce TRAN around the completed cells or along the preferential streamline/corridor feeding this group. "
                    "If a fault or barrier is present along the same corridor, test a lower fault transmissibility before changing relperm. "
                    "Use relperm/SATNUM only if the same overestimated-WCT behaviour is repeated across different areas/rock types, because a field-wide relperm change could damage wells that already underpredict water."
                )
            else:
                recommended = (
                    "The model overestimates WCT, but local TRAN/PERM are not clearly high. "
                    "Do not apply a blind TRAN reduction. First inspect the final streamlines and ΔSWAT around the local group: if water is entering through a specific corridor, tune TRAN or fault transmissibility along that corridor; if no corridor is evident, the issue is more likely water mobility/relperm/SATNUM than local connectivity."
                )
        else:
            recommended = (
                "This overestimated-WCT issue looks isolated. Do not change regional relperm or field-wide water mobility from this well alone. "
                "Start with a strictly local test: reduce TRAN around the completed cells or along the nearest preferential streamline corridor only if the map shows a clear water path into the well. "
                "If no clear path exists, the tool has weak local evidence and the safer next hypothesis is relperm/SATNUM rather than transmissibility."
            )

    elif bias in ["underestimated_wct", "underestimated_wct_late"]:
        # Simulated water is too low / too late.
        if dswat_high:
            if local_tran_low or local_perm_low:
                recommended = (
                    "Water is present near the well in the model, but the simulated WCT is too low. "
                    "This points to insufficient effective communication between water-bearing cells and the well. "
                    "The first tuning candidate is to increase local TRAN around the completed cells, or open the preferential corridor indicated by streamlines. "
                    "If a nearby fault cuts the connection, test higher fault transmissibility. "
                    "Do not use PI multiplier as a first-line correction because the issue is phase communication/mobility, not generic deliverability."
                )
            else:
                recommended = (
                    "Water is present near the well, but the model does not produce enough water. "
                    "TRAN/PERM are not clearly low, so a simple local TRAN increase is not strongly supported. "
                    "First inspect whether the connected cells actually communicate with the completion through streamlines. "
                    "If the corridor is weak, increase local/fault TRAN; if the corridor is already connected, the better hypothesis is water relative permeability/SATNUM."
                )
        else:
            recommended = (
                "The model underestimates WCT and ΔSWAT is not high around the well. "
                "This suggests the problem is not just well-to-cell communication: the model may not be bringing enough water into the area. "
                "Check regional water support first: streamline support, fault connectivity between water source and producer, and aquifer/contact representation if available. "
                "If those do not explain the issue, then relperm/SATNUM becomes a more defensible tuning lever than local TRAN."
            )

    elif bias == "negligible":
        recommended = (
            "No water-specific tuning is needed for this well. Do not spend HM effort on water here. "
            "Focus on the weakest non-water variable, and only revisit water if WCT becomes material in the history."
        )

    else:
        recommended = (
            "The WCT direction is not clear enough to choose a tuning parameter. "
            "The tool should not recommend changing TRAN or relperm yet. "
            "The next discriminating check is: compare ΔSWAT, final streamlines and local TRAN around the completed cells. "
            "If a clear corridor exists, tune local/fault TRAN; if no corridor explains the mismatch, escalate to relperm/SATNUM."
        )

    if pattern_type == "local_cluster" and bias not in ["weak_unclear", "not_evaluated"]:
        confidence = "High"
    elif pattern_type == "weak_local_pattern" or dswat_high or local_tran_high or local_tran_low:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "well": well,
        "smart_key_findings": " ".join(key_findings),
        "smart_pattern_context": pattern_context,
        "smart_local_evidence": evidence_text,
        "smart_recommended_action": recommended,
        "smart_pattern_type": pattern_type,
        "smart_wct_bias": bias,
        "smart_confidence": confidence,
        "smart_similar_wells": ", ".join(similar_names),
    }


def build_all_smart_recommendations():
    rows = [r for r in load_rows() if r.get("well")]

    recommendations = {}

    for r in rows:
        recommendations[r.get("well")] = build_smart_recommendation(r, rows)

    return recommendations


def export_smart_recommendations():
    recs = build_all_smart_recommendations()

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(recs, indent=2), encoding="utf-8")

    if recs:
        fields = [
            "well",
            "smart_key_findings",
            "smart_pattern_context",
            "smart_local_evidence",
            "smart_recommended_action",
            "smart_pattern_type",
            "smart_wct_bias",
            "smart_confidence",
            "smart_similar_wells",
        ]

        with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for _, row in sorted(recs.items()):
                writer.writerow({k: row.get(k, "") for k in fields})

    return {
        "count": len(recs),
        "json": str(OUTPUT_JSON),
        "csv": str(OUTPUT_CSV),
    }


if __name__ == "__main__":
    out = export_smart_recommendations()
    print(out)
