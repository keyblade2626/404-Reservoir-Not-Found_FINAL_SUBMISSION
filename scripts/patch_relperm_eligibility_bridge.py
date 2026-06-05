from pathlib import Path

p = Path("app/relperm_sensitivity_agent.py")
txt = p.read_text(encoding="utf-8-sig")

marker = "# --- 404_RNF_RELPERM_ELIGIBILITY_BRIDGE_VFINAL ---"

if marker in txt:
    txt = txt.split(marker)[0].rstrip() + "\n"

bridge = r'''

# --- 404_RNF_RELPERM_ELIGIBILITY_BRIDGE_VFINAL ---
# This bridge keeps the original PRT/IXF/FIPNUM workflow:
#   relperm_mobility_agent.py -> artifacts/relperm/*
# and only relaxes candidate eligibility for wells already flagged by
# water_driver_diagnosis.json as review_relperm_or_well_connection.
#
# It does NOT make every well a candidate.

_build_relperm_sensitivity_cached_v96_original = build_relperm_sensitivity_cached_v96


def _404_load_water_driver_by_well_vfinal():
    path = DIAG / "water_driver_diagnosis.json"

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}

    out = {}

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        # Support either {"wells":[...]} or {"HW-28": {...}}
        if isinstance(data.get("wells"), list):
            items = data.get("wells")
        else:
            items = []
            for k, v in data.items():
                if isinstance(v, dict):
                    vv = dict(v)
                    vv.setdefault("well", k)
                    items.append(vv)
    else:
        items = []

    for item in items:
        if isinstance(item, dict) and item.get("well"):
            out[norm_well(item.get("well"))] = item

    return out


def _404_bias_from_diag_or_row_vfinal(row, diag):
    # First use the existing function.
    bias = classify_water_bias(row)

    if bias in ["underestimated_wct", "overestimated_wct"]:
        return bias

    # Then inspect diagnosis text.
    text = " ".join([
        str(diag.get("water_direction") or ""),
        str(diag.get("direction") or ""),
        str(diag.get("interpretation") or ""),
        str(diag.get("primary_action") or ""),
        str(diag.get("action_category") or ""),
    ]).lower()

    if any(x in text for x in ["simulated_too_low", "too low", "underpredict", "under-predict", "underestimate"]):
        return "underestimated_wct"

    if any(x in text for x in ["simulated_too_high", "too high", "overpredict", "over-predict", "overestimate"]):
        return "overestimated_wct"

    return bias


def _404_is_review_relperm_candidate_vfinal(row, diag, bias):
    action_category = str(diag.get("action_category") or "").lower()
    primary_action = str(diag.get("primary_action") or "").lower()
    interpretation = str(diag.get("interpretation") or "").lower()

    if "review_relperm_or_well_connection" in action_category:
        return True

    if "relperm" in primary_action or "relative permeability" in primary_action:
        return True

    if "relperm" in interpretation or "relative permeability" in interpretation or "water mobility" in interpretation:
        return True

    # Conservative fallback only when water mismatch is clear and poor.
    water_score = safe_float(row.get("water_hm_score"))
    water_class = str(row.get("water_hm_class") or "").lower()

    if bias in ["underestimated_wct", "overestimated_wct"]:
        if water_score is not None and water_score < 60:
            return True
        if any(x in water_class for x in ["poor", "bad", "weak", "critical"]):
            return True

    return False


def build_relperm_sensitivity_cached_v96(well):
    # First use the original strict logic.
    strict = _build_relperm_sensitivity_cached_v96_original(well)

    if strict.get("eligible"):
        return strict

    target = norm_well(well)
    row = get_row_for_well(target)

    if not row:
        return strict

    water_by_well = _404_load_water_driver_by_well_vfinal()
    diag = water_by_well.get(target, {})

    mapping = load_mapping()
    curves = load_curves()

    reg = infer_region_for_well(row, mapping)
    model = reg.get("saturation_model")

    if not model:
        return strict

    models = curves.get("models") or {}

    if model not in models:
        return strict

    target_bias = _404_bias_from_diag_or_row_vfinal(row, diag)

    if target_bias not in ["underestimated_wct", "overestimated_wct"]:
        return strict

    if not _404_is_review_relperm_candidate_vfinal(row, diag, target_bias):
        return strict

    action = determine_relperm_action(target_bias)

    if action.get("action") == "no_relperm_change":
        return strict

    tables = models[model].get("tables") or {}
    krw_table = tables.get("Krw_v_Sw")

    if not krw_table:
        return strict

    original = krw_table.get("rows") or []

    if not original:
        return strict

    # Keep existing consistency calculation, but do not reject solely because it is Weak
    # for wells already flagged by water-driver diagnosis.
    consistency = region_consistency(target, model, target_bias)

    water_score = safe_float(row.get("water_hm_score"))

    if consistency.get("confidence") == "High":
        factor = conservative_change_factor("High", len(consistency.get("opposite_direction_wells") or []), water_score)
        bridge_confidence = "High"
    elif consistency.get("confidence") == "Medium":
        factor = conservative_change_factor("Medium", len(consistency.get("opposite_direction_wells") or []), water_score)
        bridge_confidence = "Medium"
    elif consistency.get("confidence") == "Low":
        factor = conservative_change_factor("Low", len(consistency.get("opposite_direction_wells") or []), water_score)
        bridge_confidence = "Low"
    else:
        # Low-confidence but still useful candidate because the water-driver diagnosis
        # explicitly says this well should be reviewed for RelPerm or well-connection effects.
        factor = 0.04
        if len(consistency.get("opposite_direction_wells") or []) > 0:
            factor = 0.025
        bridge_confidence = "Low / diagnostic-review"

    factor = round(max(0.015, min(float(factor), 0.08)), 3)

    proposed = modify_krw_curve(
        rows=original,
        direction=action["direction"],
        factor=factor,
    )

    same_names = [r.get("well") for r in consistency.get("same_direction_wells", [])]
    opposite_names = [r.get("well") for r in consistency.get("opposite_direction_wells", [])]
    neutral_names = [r.get("well") for r in consistency.get("neutral_or_good_wells", [])]

    if target_bias == "underestimated_wct":
        interpretation = (
            f"{target} underpredicts water and is mapped to {model}. "
            "Water-driver diagnosis flags this well for RelPerm or well-connection review. "
            "A conservative Krw uplift is generated as a first diagnostic sensitivity, not as an automatic final model update."
        )
    else:
        interpretation = (
            f"{target} overpredicts water and is mapped to {model}. "
            "Water-driver diagnosis flags this well for RelPerm or well-connection review. "
            "A conservative Krw reduction is generated as a first diagnostic sensitivity, not as an automatic final model update."
        )

    if opposite_names:
        risk = (
            f"Risk: {', '.join([x for x in opposite_names if x])} show opposite water behaviour in the same RelPerm region. "
            "Therefore the proposed factor is intentionally small and should be tested carefully."
        )
    else:
        risk = (
            "No strong opposite-direction wells were identified by the current regional consistency check. "
            "The factor is still kept conservative."
        )

    return {
        "ok": True,
        "eligible": True,
        "well": target,
        "model": model,
        "property_value": reg.get("property_value"),
        "target_bias": target_bias,
        "action": action,
        "factor": factor,
        "water_score": water_score,
        "consistency": consistency,
        "curve_name": "Krw_v_Sw",
        "original_curve": original,
        "proposed_curve": proposed,
        "interpretation": interpretation,
        "risk_statement": risk,
        "impacted_wells_summary": {
            "same_direction": same_names,
            "opposite_direction": opposite_names,
            "neutral_or_good": neutral_names,
        },
        "message": (
            f"Low-confidence diagnostic RelPerm candidate generated for {target}: "
            f"{action['direction']} of Krw_v_Sw for {model}, max factor {factor:.1%}. "
            "This is recommended as a test sensitivity because the water-driver diagnosis flagged RelPerm/well-connection review."
        ),
        "strict_result_before_bridge": {
            "eligible": strict.get("eligible"),
            "message": strict.get("message"),
            "target_bias": strict.get("target_bias"),
        },
        "water_driver_diagnosis": diag,
        "bridge_confidence": bridge_confidence,
        "eligibility_bridge": "water_driver_diagnosis_review_relperm_or_well_connection",
    }

# --- END 404_RNF_RELPERM_ELIGIBILITY_BRIDGE_VFINAL ---
'''

p.write_text(txt.rstrip() + "\n\n" + bridge + "\n", encoding="utf-8")
print("[OK] Added final RelPerm eligibility bridge")
