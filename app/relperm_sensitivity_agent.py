from pathlib import Path
import json
import csv
import math
import re
from collections import Counter, defaultdict


ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / "artifacts" / "relperm"
DIAG = ROOT / "artifacts" / "diagnosis"
EXPORT_DIR = ROOT / "artifacts" / "exports"

CURVES_JSON = REL / "relperm_curves.json"
MAPPING_JSON = REL / "relperm_region_mapping_proposed.json"
CONTEXT_CSV = DIAG / "well_property_driver_context.csv"


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


def norm_well(w):
    s = str(w or "").upper().strip()
    s = s.replace("_", "-").replace(" ", "-")
    m = re.search(r"\bHW[-]?(\d+[A-Z]?)\b", s)
    if m:
        return f"HW-{m.group(1)}"
    return s


def load_json(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_context_rows():
    if not CONTEXT_CSV.exists():
        return []

    with CONTEXT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def get_row_for_well(well):
    target = norm_well(well)

    for r in load_context_rows():
        if norm_well(r.get("well")) == target:
            return r

    return None


def classify_water_bias(row):
    direction = str(
        row.get("water_direction") or
        row.get("water_final_direction") or
        row.get("water_recent_2yr_direction") or
        ""
    ).lower()

    timing = str(row.get("water_timing_issue") or "").lower()

    if "negligible" in direction:
        return "negligible"

    if "too_low" in direction or "too low" in direction or "under" in direction:
        return "underestimated_wct"

    if "too_high" in direction or "too high" in direction or "over" in direction:
        return "overestimated_wct"

    if "early" in timing:
        return "overestimated_wct"

    if "late" in timing:
        return "underestimated_wct"

    return "unclear"


def extract_fipnum_from_row(row):
    """
    First version:
    tries to use existing columns if they exist.
    Later we can compute this from completed cells + FIPNUM.GRDECL.
    """
    candidates = [
        "dominant_fipnum",
        "FIPNUM",
        "fipnum",
        "relperm_region",
        "dominant_relperm_region",
        "satnum",
        "SATNUM",
    ]

    for c in candidates:
        v = row.get(c)
        fv = safe_float(v)
        if fv is not None:
            if abs(fv - round(fv)) < 1e-9:
                return int(round(fv))
            return fv

    # Fallback: if no column is available, assign by nearest mapping sequence later.
    return None


def load_mapping():
    data = load_json(MAPPING_JSON) or {}
    rows = data.get("rows") or []

    by_property_value = {}
    by_model = {}

    for r in rows:
        pv = safe_float(r.get("property_value"))
        if pv is not None and abs(pv - round(pv)) < 1e-9:
            pv = int(round(pv))

        model = r.get("saturation_model")

        if pv is not None:
            by_property_value[pv] = r

        if model:
            by_model[model] = r

    return {
        "raw": data,
        "rows": rows,
        "by_property_value": by_property_value,
        "by_model": by_model,
    }


def load_curves():
    return load_json(CURVES_JSON) or {"models": {}}


def infer_region_for_well(row, mapping):
    """
    First attempt:
    - if context contains FIPNUM/SATNUM, use mapping.
    - otherwise fallback to a simple model assignment by row order is NOT used for actual confidence.
    """
    pv = extract_fipnum_from_row(row)

    if pv is not None and pv in mapping["by_property_value"]:
        m = mapping["by_property_value"][pv]
        return {
            "property_value": pv,
            "saturation_model": m.get("saturation_model"),
            "mapping_source": "well_context_region_property",
            "mapping_confidence": m.get("mapping_confidence", "Medium"),
        }

    return {
        "property_value": None,
        "saturation_model": None,
        "mapping_source": "missing_well_region_property",
        "mapping_confidence": "Low",
    }


def build_well_region_table():
    mapping = load_mapping()
    rows = load_context_rows()

    out = []

    for r in rows:
        well = r.get("well")
        if not well:
            continue

        reg = infer_region_for_well(r, mapping)

        out.append({
            "well": norm_well(well),
            "property_value": reg.get("property_value"),
            "saturation_model": reg.get("saturation_model"),
            "mapping_source": reg.get("mapping_source"),
            "mapping_confidence": reg.get("mapping_confidence"),
            "water_bias": classify_water_bias(r),
            "water_score": safe_float(r.get("water_hm_score")),
            "pressure_score": safe_float(r.get("bhp_hm_score") or r.get("pressure_hm_score")),
            "delta_swat_percentile": safe_float(r.get("delta_swat_percentile")),
            "tran_percentile": safe_float(r.get("wellconn_weighted_tran_h_percentile")),
            "perm_percentile": safe_float(r.get("wellconn_weighted_perm_h_percentile")),
        })

    return out


def get_impacted_wells_for_model(model):
    table = build_well_region_table()
    return [r for r in table if r.get("saturation_model") == model]


def region_consistency(target_well, target_model, target_bias):
    impacted = get_impacted_wells_for_model(target_model)

    counts = Counter([r.get("water_bias") for r in impacted])

    same = [r for r in impacted if r.get("water_bias") == target_bias]
    opposite_bias = (
        "overestimated_wct" if target_bias == "underestimated_wct"
        else "underestimated_wct" if target_bias == "overestimated_wct"
        else None
    )
    opposite = [r for r in impacted if r.get("water_bias") == opposite_bias]

    good_or_neutral = [
        r for r in impacted
        if r.get("water_bias") in ["negligible", "unclear"]
        or (r.get("water_score") is not None and r.get("water_score") >= 75)
    ]

    if len(same) >= 2 and len(opposite) == 0:
        confidence = "High"
    elif len(same) >= 2 and len(opposite) <= 1:
        confidence = "Medium"
    elif len(same) == 1 and len(opposite) == 0:
        confidence = "Low"
    else:
        confidence = "Weak"

    return {
        "target_well": target_well,
        "target_model": target_model,
        "target_bias": target_bias,
        "impacted_wells": impacted,
        "counts": dict(counts),
        "same_direction_wells": same,
        "opposite_direction_wells": opposite,
        "neutral_or_good_wells": good_or_neutral,
        "confidence": confidence,
    }


def determine_relperm_action(target_bias):
    if target_bias == "underestimated_wct":
        return {
            "action": "increase_water_mobility",
            "curve": "Krw_v_Sw",
            "direction": "uplift",
            "description": "Increase Krw slightly in the intermediate Sw range to help the model produce more water.",
        }

    if target_bias == "overestimated_wct":
        return {
            "action": "decrease_water_mobility",
            "curve": "Krw_v_Sw",
            "direction": "reduction",
            "description": "Reduce Krw slightly in the intermediate Sw range to delay/reduce water production.",
        }

    return {
        "action": "no_relperm_change",
        "curve": "Krw_v_Sw",
        "direction": "none",
        "description": "Water mismatch direction is not clear enough for a relperm sensitivity.",
    }


def conservative_change_factor(confidence, opposite_count, water_score):
    """
    Conservative first-trial factors:
    - High consistency: 12-15%
    - Medium: 8-10%
    - Low: 5%
    - Opposite wells present: reduce factor
    """
    if confidence == "High":
        base = 0.14
    elif confidence == "Medium":
        base = 0.10
    elif confidence == "Low":
        base = 0.06
    else:
        base = 0.0

    if water_score is not None:
        severity = max(0.0, min(1.0, (75.0 - water_score) / 75.0))
        base = base * (0.65 + 0.70 * severity)

    if opposite_count > 0:
        base *= 0.45

    return round(max(0.0, min(base, 0.16)), 3)


def bell_weight(x, xmin, xmax):
    """
    Smooth weight:
    0 at endpoints, 1 near middle.
    """
    if xmax <= xmin:
        return 0.0

    t = (x - xmin) / (xmax - xmin)
    t = max(0.0, min(1.0, t))

    # parabola peaked at 0.5
    return max(0.0, 4.0 * t * (1.0 - t))


def enforce_monotonic_increasing(rows):
    out = []
    last = None

    for r in rows:
        v = r["value"]
        if last is not None and v < last:
            v = last
        last = v
        out.append({
            "saturation": r["saturation"],
            "value": v,
        })

    return out


def modify_krw_curve(rows, direction, factor):
    if not rows or factor <= 0:
        return rows

    sats = [r["saturation"] for r in rows]
    vals = [r["value"] for r in rows]

    xmin = min(sats)
    xmax = max(sats)
    endpoint = vals[-1]

    new_rows = []

    for idx, r in enumerate(rows):
        s = r["saturation"]
        v = r["value"]

        # Keep exact zero points and endpoints stable.
        if idx == 0 or idx == len(rows) - 1 or v <= 0:
            nv = v
        else:
            w = bell_weight(s, xmin, xmax)

            if direction == "uplift":
                nv = v * (1.0 + factor * w)
                nv = min(nv, endpoint)
            elif direction == "reduction":
                nv = v * (1.0 - factor * w)
                nv = max(nv, 0.0)
            else:
                nv = v

        new_rows.append({
            "saturation": s,
            "value": round(nv, 10),
        })

    # Krw must be monotonically increasing.
    new_rows = enforce_monotonic_increasing(new_rows)

    # Keep endpoint exactly as original.
    if new_rows:
        new_rows[-1]["value"] = rows[-1]["value"]

    return new_rows


def build_relperm_sensitivity_cached_v96(well):
    target = norm_well(well)
    row = get_row_for_well(target)

    if not row:
        return {
            "ok": False,
            "eligible": False,
            "message": f"Well {target} not found in diagnostic context.",
        }

    mapping = load_mapping()
    curves = load_curves()

    reg = infer_region_for_well(row, mapping)
    model = reg.get("saturation_model")

    if not model:
        return {
            "ok": False,
            "eligible": False,
            "message": (
                f"No relperm model could be assigned to {target}. "
                "Need well-to-region mapping from completed cells or a region property column."
            ),
            "well": target,
            "region_mapping": reg,
        }

    models = curves.get("models") or {}

    if model not in models:
        return {
            "ok": False,
            "eligible": False,
            "message": f"RelPerm model {model} not found in relperm_curves.json.",
            "well": target,
            "model": model,
        }

    target_bias = classify_water_bias(row)
    action = determine_relperm_action(target_bias)

    if action["action"] == "no_relperm_change":
        return {
            "ok": True,
            "eligible": False,
            "message": "Water mismatch direction is not clear enough for a relperm sensitivity.",
            "well": target,
            "model": model,
            "target_bias": target_bias,
        }

    consistency = region_consistency(target, model, target_bias)

    if consistency["confidence"] == "Weak":
        return {
            "ok": True,
            "eligible": False,
            "message": (
                "Relperm sensitivity is not recommended because wells in the same region "
                "do not show a coherent water mismatch direction."
            ),
            "well": target,
            "model": model,
            "target_bias": target_bias,
            "consistency": consistency,
        }

    krw_table = models[model]["tables"].get("Krw_v_Sw")

    if not krw_table:
        return {
            "ok": False,
            "eligible": False,
            "message": f"Krw_v_Sw not found for {model}.",
            "well": target,
            "model": model,
        }

    original = krw_table.get("rows") or []
    water_score = safe_float(row.get("water_hm_score"))
    factor = conservative_change_factor(
        confidence=consistency["confidence"],
        opposite_count=len(consistency["opposite_direction_wells"]),
        water_score=water_score,
    )

    if factor <= 0:
        return {
            "ok": True,
            "eligible": False,
            "message": "Relperm change factor is zero after risk checks.",
            "well": target,
            "model": model,
            "target_bias": target_bias,
            "consistency": consistency,
        }

    proposed = modify_krw_curve(
        rows=original,
        direction=action["direction"],
        factor=factor,
    )

    same_names = [r["well"] for r in consistency["same_direction_wells"]]
    opposite_names = [r["well"] for r in consistency["opposite_direction_wells"]]
    neutral_names = [r["well"] for r in consistency["neutral_or_good_wells"]]

    if target_bias == "underestimated_wct":
        interpretation = (
            f"{target} underpredicts water and is mapped to {model}. "
            f"The same relperm region contains {len(same_names)} well(s) with the same water-underprediction signature. "
            "A conservative Krw uplift is a defensible first mobility sensitivity if TRAN/fault evidence is weak."
        )
    else:
        interpretation = (
            f"{target} overpredicts water and is mapped to {model}. "
            f"The same relperm region contains {len(same_names)} well(s) with the same water-overprediction signature. "
            "A conservative Krw reduction is a defensible first mobility sensitivity if local high-TRAN evidence is weak."
        )

    if opposite_names:
        risk = (
            f"Risk: {', '.join(opposite_names)} show the opposite WCT direction in the same relperm region. "
            "The proposed factor has therefore been reduced and should be tested carefully."
        )
    else:
        risk = (
            "No opposite-direction WCT wells were detected in the same relperm region. "
            "The proposed sensitivity is still conservative and should be tested as a first trial."
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
            f"Proposed {action['direction']} of Krw_v_Sw for {model} with maximum conservative factor {factor:.1%}."
        ),
    }


def format_curve_block(name, rows):
    lines = []
    lines.append(f'    RelPerm "{name}" [')
    lines.append("           Saturation    RelPerm")

    for r in rows:
        lines.append(f"        {r['saturation']:>14.9g}    {r['value']:>14.9g}")

    lines.append("    ]")
    return "\n".join(lines)


def export_relperm_ixf_candidate(well):
    result = build_relperm_sensitivity_cached_v96(well)

    if not result.get("eligible"):
        return result

    model = result["model"]
    curve_name = result["curve_name"]
    proposed = result["proposed_curve"]

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    clean_model = str(model).replace(" ", "_")
    clean_well = norm_well(well).replace("-", "_")
    direction = result["action"]["direction"]
    pct = int(round(result["factor"] * 100))

    filename = f"RELPERM_{clean_model}_{direction}_{pct}pct_for_{clean_well}.ixf"
    path = EXPORT_DIR / filename

    lines = []
    lines.append("######################################")
    lines.append("# Candidate RelPerm sensitivity generated by 404 Reservoir Not Found")
    lines.append("# Review before simulation. This is a conservative first-trial HM candidate.")
    lines.append("######################################")
    lines.append("")
    lines.append("MODEL_DEFINITION")
    lines.append("")
    lines.append(f'SaturationFunction "{model}" {{')
    lines.append(f"    # Modified curve for well {norm_well(well)}")
    lines.append(f"    # Action: {result['action']['description']}")
    lines.append(f"    # Max conservative factor: {result['factor']:.3f}")
    lines.append("")
    lines.append(format_curve_block(curve_name, proposed))
    lines.append("")
    lines.append("}")
    lines.append("")

    content = "\n".join(lines)
    path.write_text(content, encoding="utf-8")

    result = dict(result)
    result["filename"] = filename
    result["path"] = str(path)
    result["content"] = content

    return result


def is_relperm_request(message):
    q = str(message or "").lower()

    triggers = [
        "relperm",
        "relative permeability",
        "permeability curve",
        "krw",
        "kro",
        "water mobility",
        "modify curve",
        "modified curve",
        "proposed curve",
        "export relperm",
    ]

    return any(t in q for t in triggers)


def extract_well(message):
    q = str(message or "").upper()
    m = re.search(r"\bHW[-_\s]?(\d+[A-Z]?)\b", q)
    if m:
        return f"HW-{m.group(1)}"
    return None


def answer_relperm_sensitivity_question(message):
    if not is_relperm_request(message):
        return None

    well = extract_well(message)

    if not well:
        return {
            "type": "visual_response",
            "answer": "Please specify the well, for example: propose a relperm sensitivity for HW-28.",
            "intent": "relperm_sensitivity_missing_well",
            "ui_blocks": [],
            "data": {},
            "agent_trace": {
                "RelPermSensitivityAgent": {
                    "status": "missing_well",
                }
            },
        }

    result = build_relperm_sensitivity_cached_v96(well)

    if not result.get("ok"):
        return {
            "type": "visual_response",
            "answer": result.get("message", "RelPerm sensitivity failed."),
            "intent": "relperm_sensitivity_error",
            "ui_blocks": [],
            "data": result,
            "agent_trace": {
                "RelPermSensitivityAgent": {
                    "well": well,
                    "status": "error",
                    "message": result.get("message"),
                }
            },
        }

    if not result.get("eligible"):
        return {
            "type": "visual_response",
            "answer": result.get("message", "RelPerm sensitivity is not recommended for this well."),
            "intent": "relperm_sensitivity_not_eligible",
            "ui_blocks": [
                {
                    "type": "compact_notes",
                    "title": "RelPerm Sensitivity Check",
                    "items": [
                        result.get("message", ""),
                    ],
                }
            ],
            "data": result,
            "agent_trace": {
                "RelPermSensitivityAgent": {
                    "well": well,
                    "status": "not_eligible",
                }
            },
        }

    answer = (
        f"{result['interpretation']} {result['risk_statement']} "
        f"I propose a conservative {result['action']['direction']} of {result['curve_name']} "
        f"for {result['model']} with a maximum factor of {result['factor']:.1%}."
    )

    return {
        "type": "visual_response",
        "answer": answer,
        "intent": "relperm_sensitivity",
        "ui_blocks": [
            {
                "type": "relperm_curve_sensitivity",
                "title": f"RelPerm Sensitivity - {result['model']} / {result['curve_name']}",
                "payload": result,
            },
            {
                "type": "compact_table",
                "title": "Impacted wells in same RelPerm region",
                "columns": ["group", "wells"],
                "rows": [
                    {
                        "group": "Same WCT direction",
                        "wells": ", ".join(result["impacted_wells_summary"]["same_direction"]),
                    },
                    {
                        "group": "Opposite WCT direction",
                        "wells": ", ".join(result["impacted_wells_summary"]["opposite_direction"]),
                    },
                    {
                        "group": "Neutral / good",
                        "wells": ", ".join(result["impacted_wells_summary"]["neutral_or_good"]),
                    },
                ],
            },
            {
                "type": "suggestions",
                "title": "Suggested follow-up",
                "items": [
                    f"Export relperm IXF for {well}",
                    f"Show proposed transmissibility corridor for {well}",
                    f"Show WCT profile for {well}",
                ],
            },
        ],
        "data": result,
        "agent_trace": {
            "RelPermSensitivityAgent": {
                "well": well,
                "model": result.get("model"),
                "target_bias": result.get("target_bias"),
                "factor": result.get("factor"),
                "status": "eligible",
            }
        },
    }


if __name__ == "__main__":
    import sys
    well = sys.argv[1] if len(sys.argv) > 1 else "HW-28"
    print(json.dumps(build_relperm_sensitivity_cached_v96(well), indent=2, default=str))



# ==========================================================
# WELL TO FIPNUM FALLBACK MAPPING V61
# Uses well I/J + FIPNUM.GRDECL neighborhood to assign dominant relperm model.
# ==========================================================

FIPNUM_GRDECL = ROOT / "data" / "sample_model" / "FIPNUM.GRDECL"


def load_grid_dimensions_v61():
    candidates = [
        ROOT / "artifacts" / "dashboard" / "grid_dimensions.json",
        ROOT / "artifacts" / "grid_dimensions.json",
        ROOT / "data" / "sample_model" / "grid_dimensions.json",
        ROOT / "data" / "grid_dimensions.json",
    ]

    for p in candidates:
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8-sig"))
                nx = int(d.get("nx") or d.get("NX"))
                ny = int(d.get("ny") or d.get("NY"))
                nz = int(d.get("nz") or d.get("NZ"))
                if nx > 0 and ny > 0 and nz > 0:
                    return {"nx": nx, "ny": ny, "nz": nz, "source": str(p)}
            except Exception:
                pass

    # Try importing from streamline payload utilities if available.
    try:
        from app.streamline_visual_payloads import get_grid_dimensions
        dims = get_grid_dimensions()
        if isinstance(dims, dict):
            nx = int(dims.get("nx") or dims.get("NX"))
            ny = int(dims.get("ny") or dims.get("NY"))
            nz = int(dims.get("nz") or dims.get("NZ"))
            return {"nx": nx, "ny": ny, "nz": nz, "source": "streamline_visual_payloads.get_grid_dimensions"}
    except Exception:
        pass

    return {"nx": None, "ny": None, "nz": None, "source": "not_found"}


def expand_grdecl_tokens_v61(tokens):
    values = []

    for tok in tokens:
        t = str(tok or "").strip()

        if not t:
            continue

        if "/" in t:
            t = t.replace("/", "")
            if not t:
                continue

        m = re.match(r"^(\d+)\*(.+)$", t)
        if m:
            n = int(m.group(1))
            val = safe_float(m.group(2))
            if val is not None:
                values.extend([val] * n)
        else:
            val = safe_float(t)
            if val is not None:
                values.append(val)

    return values


def load_fipnum_values_v61():
    if not FIPNUM_GRDECL.exists():
        return {
            "ok": False,
            "message": f"FIPNUM.GRDECL not found at {FIPNUM_GRDECL}",
            "values": [],
        }

    text = FIPNUM_GRDECL.read_text(encoding="utf-8", errors="ignore")

    clean_lines = []
    for line in text.splitlines():
        s = line.split("--")[0].split("#")[0].strip()
        if s:
            clean_lines.append(s)

    clean = "\n".join(clean_lines)
    tokens = re.split(r"\s+", clean)

    if tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", tokens[0]) and "*" not in tokens[0]:
        prop_name = tokens[0].upper()
        data_tokens = tokens[1:]
    else:
        prop_name = "FIPNUM"
        data_tokens = tokens

    values = expand_grdecl_tokens_v61(data_tokens)

    int_values = []
    for v in values:
        if v is None:
            continue
        if abs(v - round(v)) < 1e-9:
            int_values.append(int(round(v)))
        else:
            int_values.append(v)

    return {
        "ok": True,
        "property_name": prop_name,
        "values": int_values,
        "cell_count": len(int_values),
        "unique_values": sorted(set(int_values), key=lambda x: float(x)),
    }


def grid_index_v61(i, j, k, nx, ny, nz):
    """
    ECLIPSE/GRDECL flattening assumption: I fastest, then J, then K.
    i, j, k are 1-based.
    """
    if i < 1 or j < 1 or k < 1 or i > nx or j > ny or k > nz:
        return None

    return (k - 1) * nx * ny + (j - 1) * nx + (i - 1)


def dominant_fipnum_around_well_v61(row, radius=1):
    """
    Uses well I/J from well_property_driver_context.csv and samples FIPNUM column/neighborhood.
    This is a first fallback when completion-level cells are not yet parsed.
    """
    wi = safe_float(row.get("i") or row.get("I") or row.get("well_i") or row.get("x_i"))
    wj = safe_float(row.get("j") or row.get("J") or row.get("well_j") or row.get("y_j"))

    if wi is None or wj is None:
        return {
            "ok": False,
            "message": "Well row has no I/J coordinates.",
        }

    i0 = int(round(wi))
    j0 = int(round(wj))

    dims = load_grid_dimensions_v61()
    nx, ny, nz = dims.get("nx"), dims.get("ny"), dims.get("nz")

    if not nx or not ny or not nz:
        return {
            "ok": False,
            "message": "Grid dimensions not found; cannot map I/J to FIPNUM index.",
            "dims": dims,
        }

    fip = load_fipnum_values_v61()

    if not fip.get("ok"):
        return fip

    values = fip.get("values") or []

    if len(values) < nx * ny * nz:
        return {
            "ok": False,
            "message": f"FIPNUM cell count ({len(values)}) is smaller than NX*NY*NZ ({nx*ny*nz}).",
            "dims": dims,
            "fipnum_cell_count": len(values),
        }

    counts = Counter()

    for di in range(-radius, radius + 1):
        for dj in range(-radius, radius + 1):
            ii = i0 + di
            jj = j0 + dj

            if ii < 1 or jj < 1 or ii > nx or jj > ny:
                continue

            for kk in range(1, nz + 1):
                idx = grid_index_v61(ii, jj, kk, nx, ny, nz)
                if idx is None or idx >= len(values):
                    continue

                val = values[idx]

                # ignore inactive/zero if present
                if val is None:
                    continue

                counts[val] += 1

    if not counts:
        return {
            "ok": False,
            "message": "No FIPNUM values sampled around well.",
            "well_i": i0,
            "well_j": j0,
            "dims": dims,
        }

    dominant_value, dominant_count = counts.most_common(1)[0]
    total = sum(counts.values())

    return {
        "ok": True,
        "property_name": fip.get("property_name", "FIPNUM"),
        "dominant_property_value": dominant_value,
        "dominant_fraction": dominant_count / total if total else None,
        "distribution": {str(k): v for k, v in counts.most_common()},
        "well_i": i0,
        "well_j": j0,
        "sample_radius": radius,
        "sampled_cells": total,
        "dims": dims,
    }


def infer_region_for_well_v61(row, mapping):
    """
    Improved region inference:
    1. existing explicit column in context
    2. fallback to FIPNUM.GRDECL sampled around well I/J
    """
    # First try original logic.
    pv = extract_fipnum_from_row(row)

    if pv is not None and pv in mapping["by_property_value"]:
        m = mapping["by_property_value"][pv]
        return {
            "property_value": pv,
            "saturation_model": m.get("saturation_model"),
            "mapping_source": "well_context_region_property",
            "mapping_confidence": m.get("mapping_confidence", "Medium"),
            "fipnum_sampling": None,
        }

    # Fallback: sample FIPNUM around well location.
    sampled = dominant_fipnum_around_well_v61(row, radius=1)

    if sampled.get("ok"):
        sampled_value = sampled.get("dominant_property_value")

        if sampled_value in mapping["by_property_value"]:
            m = mapping["by_property_value"][sampled_value]
            return {
                "property_value": sampled_value,
                "saturation_model": m.get("saturation_model"),
                "mapping_source": "fipnum_grdecl_neighborhood_sample",
                "mapping_confidence": "Medium" if sampled.get("dominant_fraction", 0) < 0.80 else "High",
                "fipnum_sampling": sampled,
            }

        # Try float/int conversion
        try:
            sv_int = int(round(float(sampled_value)))
            if sv_int in mapping["by_property_value"]:
                m = mapping["by_property_value"][sv_int]
                return {
                    "property_value": sv_int,
                    "saturation_model": m.get("saturation_model"),
                    "mapping_source": "fipnum_grdecl_neighborhood_sample",
                    "mapping_confidence": "Medium" if sampled.get("dominant_fraction", 0) < 0.80 else "High",
                    "fipnum_sampling": sampled,
                }
        except Exception:
            pass

    return {
        "property_value": None,
        "saturation_model": None,
        "mapping_source": "missing_well_region_property",
        "mapping_confidence": "Low",
        "fipnum_sampling": sampled,
    }


# Override original region inference function.
infer_region_for_well = infer_region_for_well_v61


def export_well_relperm_region_context_v61():
    """
    Creates a useful CSV showing which relperm model was assigned to each well.
    """
    mapping = load_mapping()
    rows = load_context_rows()
    out_rows = []

    for r in rows:
        well = r.get("well")
        if not well:
            continue

        reg = infer_region_for_well_v61(r, mapping)
        sampling = reg.get("fipnum_sampling") or {}

        out_rows.append({
            "well": norm_well(well),
            "property_value": reg.get("property_value"),
            "saturation_model": reg.get("saturation_model"),
            "mapping_source": reg.get("mapping_source"),
            "mapping_confidence": reg.get("mapping_confidence"),
            "dominant_fraction": sampling.get("dominant_fraction"),
            "well_i": sampling.get("well_i"),
            "well_j": sampling.get("well_j"),
            "sampled_cells": sampling.get("sampled_cells"),
            "water_bias": classify_water_bias(r),
            "water_score": safe_float(r.get("water_hm_score")),
        })

    out_dir = ROOT / "artifacts" / "relperm"
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "well_relperm_region_context.csv"
    json_path = out_dir / "well_relperm_region_context.json"

    fields = [
        "well",
        "property_value",
        "saturation_model",
        "mapping_source",
        "mapping_confidence",
        "dominant_fraction",
        "well_i",
        "well_j",
        "sampled_cells",
        "water_bias",
        "water_score",
    ]

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in out_rows:
            writer.writerow(row)

    json_path.write_text(json.dumps(out_rows, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "rows": len(out_rows),
        "csv": str(csv_path),
        "json": str(json_path),
    }




# ==========================================================
# GRID DIMENSION DETECTION FROM MODEL FILES V62
# Reads NX/NY/NZ from PRT, DATA, IX, AFI, GRDECL-like files.
# Overrides load_grid_dimensions_v61.
# ==========================================================

def _try_parse_dimens_from_text_v62(text, source=""):
    """
    Tries multiple patterns commonly found in Eclipse/IX/Petrel/PRT files.
    Returns {"nx":..., "ny":..., "nz":..., "source":...} or None.
    """

    if not text:
        return None

    # 1) Eclipse style:
    # DIMENS
    #  200 150 60 /
    m = re.search(
        r'\bDIMENS\b\s*[\r\n]+(?:\s*)?(\d+)\s+(\d+)\s+(\d+)\s*/?',
        text,
        flags=re.IGNORECASE
    )
    if m:
        return {
            "nx": int(m.group(1)),
            "ny": int(m.group(2)),
            "nz": int(m.group(3)),
            "source": f"DIMENS in {source}",
        }

    # 2) Inline DIMENS 200 150 60 /
    m = re.search(
        r'\bDIMENS\b\s+(\d+)\s+(\d+)\s+(\d+)\s*/?',
        text,
        flags=re.IGNORECASE
    )
    if m:
        return {
            "nx": int(m.group(1)),
            "ny": int(m.group(2)),
            "nz": int(m.group(3)),
            "source": f"inline DIMENS in {source}",
        }

    # 3) Petrel / IX style:
    # NX = 200
    # NY = 150
    # NZ = 60
    mx = re.search(r'\bN[ _-]?X\b\s*[=:]\s*(\d+)', text, flags=re.IGNORECASE)
    my = re.search(r'\bN[ _-]?Y\b\s*[=:]\s*(\d+)', text, flags=re.IGNORECASE)
    mz = re.search(r'\bN[ _-]?Z\b\s*[=:]\s*(\d+)', text, flags=re.IGNORECASE)

    if mx and my and mz:
        return {
            "nx": int(mx.group(1)),
            "ny": int(my.group(1)),
            "nz": int(mz.group(1)),
            "source": f"NX/NY/NZ in {source}",
        }

    # 4) Petrel sometimes reports:
    # Grid dimensions: 200 x 150 x 60
    m = re.search(
        r'(?:grid\s+dimensions|cartesian\s+dimensions|dimensions)\D+(\d+)\s*[x, ]\s*(\d+)\s*[x, ]\s*(\d+)',
        text,
        flags=re.IGNORECASE
    )
    if m:
        return {
            "nx": int(m.group(1)),
            "ny": int(m.group(2)),
            "nz": int(m.group(3)),
            "source": f"dimension text in {source}",
        }

    # 5) PRT may report I/J/K extents:
    # I dimension ... 200
    # J dimension ... 150
    # K dimension ... 60
    mi = re.search(r'\bI\s*(?:dimension|cells|size|extent)\D+(\d+)', text, flags=re.IGNORECASE)
    mj = re.search(r'\bJ\s*(?:dimension|cells|size|extent)\D+(\d+)', text, flags=re.IGNORECASE)
    mk = re.search(r'\bK\s*(?:dimension|cells|size|extent)\D+(\d+)', text, flags=re.IGNORECASE)

    if mi and mj and mk:
        return {
            "nx": int(mi.group(1)),
            "ny": int(mj.group(1)),
            "nz": int(mk.group(1)),
            "source": f"I/J/K dimension text in {source}",
        }

    # 6) Alternative compact:
    # CartesianGrid { Nx=... Ny=... Nz=... }
    m = re.search(
        r'(?:Nx|NX)\s*[=:]\s*(\d+).*?(?:Ny|NY)\s*[=:]\s*(\d+).*?(?:Nz|NZ)\s*[=:]\s*(\d+)',
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    if m:
        return {
            "nx": int(m.group(1)),
            "ny": int(m.group(2)),
            "nz": int(m.group(3)),
            "source": f"compact Nx/Ny/Nz in {source}",
        }

    return None


def _candidate_dimension_files_v62():
    model_dir = ROOT / "data" / "sample_model"

    preferred_names = [
        "SIMULATION.PRT",
        "simulation.prt",
        "MODEL.DATA",
        "model.DATA",
        "MODEL.IX",
        "model.IX",
        "MODEL.AFI",
        "model.AFI",
    ]

    files = []

    for name in preferred_names:
        p = model_dir / name
        if p.exists():
            files.append(p)

    # Then scan common text model files.
    for pattern in ["*.PRT", "*.prt", "*.DATA", "*.data", "*.IX", "*.ix", "*.AFI", "*.afi", "*.GRDECL", "*.grdecl", "*.INC", "*.inc"]:
        files.extend(model_dir.glob(pattern))

    # Deduplicate preserving order.
    seen = set()
    out = []
    for p in files:
        key = str(p.resolve()).lower()
        if key not in seen and p.exists() and p.is_file():
            seen.add(key)
            out.append(p)

    return out


def load_grid_dimensions_v62():
    """
    Improved grid dimension loader.
    Priority:
    1. existing JSON artifacts
    2. existing utility functions
    3. PRT/DATA/IX/AFI/GRDECL parsing from data/sample_model
    """
    # 1) JSON artifacts
    candidates = [
        ROOT / "artifacts" / "dashboard" / "grid_dimensions.json",
        ROOT / "artifacts" / "grid_dimensions.json",
        ROOT / "data" / "sample_model" / "grid_dimensions.json",
        ROOT / "data" / "grid_dimensions.json",
    ]

    for p in candidates:
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8-sig"))
                nx = int(d.get("nx") or d.get("NX"))
                ny = int(d.get("ny") or d.get("NY"))
                nz = int(d.get("nz") or d.get("NZ"))
                if nx > 0 and ny > 0 and nz > 0:
                    return {"nx": nx, "ny": ny, "nz": nz, "source": str(p)}
            except Exception:
                pass

    # 2) Existing utility functions
    for module_name, fn_name in [
        ("app.streamline_visual_payloads", "get_grid_dimensions"),
        ("app.hm_map_payload", "get_grid_dimensions"),
        ("app.cell_property_layers", "get_grid_dimensions"),
    ]:
        try:
            mod = __import__(module_name, fromlist=[fn_name])
            fn = getattr(mod, fn_name, None)
            if fn:
                dims = fn()
                if isinstance(dims, dict):
                    nx = int(dims.get("nx") or dims.get("NX"))
                    ny = int(dims.get("ny") or dims.get("NY"))
                    nz = int(dims.get("nz") or dims.get("NZ"))
                    if nx > 0 and ny > 0 and nz > 0:
                        return {
                            "nx": nx,
                            "ny": ny,
                            "nz": nz,
                            "source": f"{module_name}.{fn_name}",
                        }
        except Exception:
            pass

    # 3) Parse text model files
    for p in _candidate_dimension_files_v62():
        try:
            # Avoid reading huge binary-looking files; text only.
            if p.stat().st_size > 250_000_000:
                continue

            text = p.read_text(encoding="utf-8", errors="ignore")
            dims = _try_parse_dimens_from_text_v62(text, source=str(p))
            if dims and dims["nx"] > 0 and dims["ny"] > 0 and dims["nz"] > 0:
                return dims

        except Exception:
            continue

    return {
        "nx": None,
        "ny": None,
        "nz": None,
        "source": "not_found",
    }


# Override previous dimension loader.
load_grid_dimensions_v61 = load_grid_dimensions_v62



# ==========================================================
# ABSOLUTE GRID DIMENSIONS LOADER V65
# Final override: always read data/sample_model/grid_dimensions.json.
# ==========================================================

def _extract_dim_value_v65(d, keys):
    for k in keys:
        if k in d and d[k] is not None:
            return int(float(d[k]))
    return None


def load_grid_dimensions_v65():
    p = ROOT / "data" / "sample_model" / "grid_dimensions.json"

    if not p.exists():
        return {
            "nx": None,
            "ny": None,
            "nz": None,
            "source": str(p),
            "message": "grid_dimensions.json does not exist at expected path.",
            "root": str(ROOT),
        }

    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))

        # Support flat JSON:
        # {"nx":..., "ny":..., "nz":...}
        nx = _extract_dim_value_v65(d, ["nx", "NX", "nX", "Nx", "ni", "NI", "i", "I"])
        ny = _extract_dim_value_v65(d, ["ny", "NY", "nY", "Ny", "nj", "NJ", "j", "J"])
        nz = _extract_dim_value_v65(d, ["nz", "NZ", "nZ", "Nz", "nk", "NK", "k", "K"])

        # Support nested JSON:
        # {"grid": {"nx":..., "ny":..., "nz":...}}
        if (nx is None or ny is None or nz is None):
            for nested_key in ["grid", "dims", "dimensions", "cartesian", "model_grid"]:
                sub = d.get(nested_key)
                if isinstance(sub, dict):
                    nx = nx or _extract_dim_value_v65(sub, ["nx", "NX", "nX", "Nx", "ni", "NI", "i", "I"])
                    ny = ny or _extract_dim_value_v65(sub, ["ny", "NY", "nY", "Ny", "nj", "NJ", "j", "J"])
                    nz = nz or _extract_dim_value_v65(sub, ["nz", "NZ", "nZ", "Nz", "nk", "NK", "k", "K"])

        if not nx or not ny or not nz:
            return {
                "nx": None,
                "ny": None,
                "nz": None,
                "source": str(p),
                "message": "grid_dimensions.json was found but nx/ny/nz keys were not recognized.",
                "available_keys": list(d.keys()) if isinstance(d, dict) else [],
                "raw": d,
            }

        return {
            "nx": nx,
            "ny": ny,
            "nz": nz,
            "source": str(p),
        }

    except Exception as exc:
        return {
            "nx": None,
            "ny": None,
            "nz": None,
            "source": str(p),
            "message": f"Failed to parse grid_dimensions.json: {exc}",
        }


# Final hard override of all previous loaders.
load_grid_dimensions_v61 = load_grid_dimensions_v65
load_grid_dimensions_v62 = load_grid_dimensions_v65
load_grid_dimensions_v64 = load_grid_dimensions_v65




# ==========================================================
# RELPERM CURVE SELECTOR + GROUPED CURVES V67
# Shows all curves for a well/model before modifying one.
# ==========================================================

def _convert_so_curve_to_sw_v67(rows):
    """
    For water-oil comparison:
    Krow_v_So is converted to equivalent Sw = 1 - So for plotting against Krw_v_Sw.
    """
    out = []
    for r in rows or []:
        so = safe_float(r.get("saturation"))
        val = safe_float(r.get("value"))
        if so is None or val is None:
            continue
        out.append({
            "saturation": round(1.0 - so, 10),
            "value": val,
            "original_saturation": so,
        })
    return sorted(out, key=lambda x: x["saturation"])


def _convert_so_curve_to_sg_v67(rows):
    """
    For gas-oil comparison:
    Krog_v_So is converted to equivalent Sg = 1 - So for plotting against Krg_v_Sg.
    """
    out = []
    for r in rows or []:
        so = safe_float(r.get("saturation"))
        val = safe_float(r.get("value"))
        if so is None or val is None:
            continue
        out.append({
            "saturation": round(1.0 - so, 10),
            "value": val,
            "original_saturation": so,
        })
    return sorted(out, key=lambda x: x["saturation"])


def build_relperm_curve_view_for_well(well):
    target = norm_well(well)
    row = get_row_for_well(target)

    if not row:
        return {
            "ok": False,
            "message": f"Well {target} not found in diagnostic context.",
            "well": target,
        }

    mapping = load_mapping()
    reg = infer_region_for_well(row, mapping)
    model = reg.get("saturation_model")

    if not model:
        return {
            "ok": False,
            "message": (
                f"No relperm model could be assigned to {target}. "
                "Need well-to-region mapping from FIPNUM/region property."
            ),
            "well": target,
            "region_mapping": reg,
        }

    curves = load_curves()
    models = curves.get("models") or {}

    if model not in models:
        return {
            "ok": False,
            "message": f"RelPerm model {model} not found in relperm_curves.json.",
            "well": target,
            "model": model,
        }

    tables = models[model].get("tables") or {}

    def rows(name):
        return (tables.get(name) or {}).get("rows") or []

    water_oil = {
        "group": "water_oil",
        "title": "Water-Oil Relative Permeability",
        "x_axis": "Water saturation Sw",
        "y_axis": "Relative permeability",
        "curves": [
            {
                "name": "Krw_v_Sw",
                "label": "Krw vs Sw",
                "x": "Sw",
                "y": "Krw",
                "rows": rows("Krw_v_Sw"),
                "editable": True,
                "edit_type": "water_mobility",
            },
            {
                "name": "Krow_v_So",
                "label": "Krow vs equivalent Sw = 1 - So",
                "x": "Sw_equivalent",
                "y": "Krow",
                "rows": _convert_so_curve_to_sw_v67(rows("Krow_v_So")),
                "original_x": "So",
                "editable": False,
                "edit_type": "oil_water_oil_relperm",
            },
        ],
    }

    gas_oil = {
        "group": "gas_oil",
        "title": "Gas-Oil Relative Permeability",
        "x_axis": "Gas saturation Sg",
        "y_axis": "Relative permeability",
        "curves": [
            {
                "name": "Krg_v_Sg",
                "label": "Krg vs Sg",
                "x": "Sg",
                "y": "Krg",
                "rows": rows("Krg_v_Sg"),
                "editable": True,
                "edit_type": "gas_mobility",
            },
            {
                "name": "Krog_v_So",
                "label": "Krog vs equivalent Sg = 1 - So",
                "x": "Sg_equivalent",
                "y": "Krog",
                "rows": _convert_so_curve_to_sg_v67(rows("Krog_v_So")),
                "original_x": "So",
                "editable": False,
                "edit_type": "gas_oil_oil_relperm",
            },
        ],
    }

    capillary = {
        "group": "capillary",
        "title": "Capillary Pressure",
        "x_axis": "Saturation",
        "y_axis": "Capillary pressure",
        "curves": [
            {
                "name": "Pcow_v_Sw",
                "label": "Pcow vs Sw",
                "x": "Sw",
                "y": "Pcow",
                "rows": rows("Pcow_v_Sw"),
                "editable": False,
                "edit_type": "capillary_pressure_water_oil",
            },
            {
                "name": "Pcgo_v_Sg",
                "label": "Pcgo vs Sg",
                "x": "Sg",
                "y": "Pcgo",
                "rows": rows("Pcgo_v_Sg"),
                "editable": False,
                "edit_type": "capillary_pressure_gas_oil",
            },
        ],
    }

    available_groups = []
    for g in [water_oil, gas_oil, capillary]:
        g["curves"] = [c for c in g["curves"] if c.get("rows")]
        if g["curves"]:
            available_groups.append(g)

    # Check whether Krw sensitivity is eligible, but do not force it.
    sens = build_relperm_sensitivity_cached_v96(target)
    krw_sensitivity_available = bool(sens.get("eligible"))

    return {
        "ok": True,
        "well": target,
        "model": model,
        "property_value": reg.get("property_value"),
        "region_mapping": reg,
        "summary": models[model].get("summary") or {},
        "groups": available_groups,
        "curve_names": list(tables.keys()),
        "krw_sensitivity_available": krw_sensitivity_available,
        "krw_sensitivity": sens if krw_sensitivity_available else None,
        "message": f"Loaded {len(tables)} relperm/capillary tables for {target} in {model}.",
    }


def detect_requested_relperm_curve_v67(message):
    q = str(message or "").lower()

    if "krw" in q or "water mobility" in q:
        return "Krw_v_Sw"

    if "krow" in q or ("oil" in q and "water" in q):
        return "Krow_v_So"

    if "krg" in q or "gas mobility" in q:
        return "Krg_v_Sg"

    if "krog" in q or ("oil" in q and "gas" in q):
        return "Krog_v_So"

    if "pcow" in q or "capillary water" in q or "capillary oil water" in q:
        return "Pcow_v_Sw"

    if "pcgo" in q or "capillary gas" in q:
        return "Pcgo_v_Sg"

    return None


def answer_relperm_curve_selector_question_v67(message):
    q = str(message or "").lower()

    relperm_words = [
        "relperm",
        "relative permeability",
        "permeability curve",
        "permeability curves",
        "capillary",
        "krw",
        "krow",
        "krg",
        "krog",
        "pcow",
        "pcgo",
        "water mobility",
        "gas mobility",
        "modified permeability curve",
    ]

    if not any(x in q for x in relperm_words):
        return None

    well = extract_well(message)

    if not well:
        return {
            "type": "visual_response",
            "answer": "Please specify the well, for example: show relperm curves for HW-28.",
            "intent": "relperm_curve_missing_well",
            "ui_blocks": [],
            "data": {},
            "agent_trace": {
                "RelPermCurveSelectorAgentV67": {
                    "status": "missing_well",
                }
            },
        }

    requested_curve = detect_requested_relperm_curve_v67(message)

    # If the user explicitly requests a Krw modification/evaluation, run sensitivity.
    wants_modification = any(x in q for x in [
        "modify",
        "modified",
        "adjust",
        "change",
        "sensitivity",
        "rifatta",
        "scarica",
        "export",
        "evaluate",
        "valuta",
    ])

    if requested_curve == "Krw_v_Sw" and wants_modification:
        return answer_relperm_sensitivity_question(message)

    view = build_relperm_curve_view_for_well(well)

    if not view.get("ok"):
        return {
            "type": "visual_response",
            "answer": view.get("message", "Could not load relperm curves."),
            "intent": "relperm_curve_error",
            "ui_blocks": [],
            "data": view,
            "agent_trace": {
                "RelPermCurveSelectorAgentV67": {
                    "well": well,
                    "status": "error",
                    "message": view.get("message"),
                }
            },
        }

    answer = (
        f"I loaded the relative permeability and capillary-pressure curves for {view['well']} "
        f"in relperm model {view['model']}. Select the curve group to inspect. "
    )

    if view.get("krw_sensitivity_available"):
        answer += (
            "A Krw water-mobility sensitivity is available for this well; use the Evaluate/Export button "
            "if you want to generate the modified curve candidate."
        )
    else:
        answer += (
            "A Krw modification is not automatically recommended yet; inspect the curves and regional impact first."
        )

    return {
        "type": "visual_response",
        "answer": answer,
        "intent": "relperm_curve_selector",
        "ui_blocks": [
            {
                "type": "relperm_curve_selector",
                "title": f"RelPerm Curves - {view['well']} / {view['model']}",
                "payload": view,
            },
            {
                "type": "suggestions",
                "title": "Suggested follow-up",
                "items": [
                    f"Evaluate Krw sensitivity for {view['well']}",
                    f"Export relperm IXF for {view['well']}",
                    f"Show WCT profile for {view['well']}",
                    f"Show proposed transmissibility corridor for {view['well']}",
                ],
            },
        ],
        "data": view,
        "agent_trace": {
            "RelPermCurveSelectorAgentV67": {
                "well": view.get("well"),
                "model": view.get("model"),
                "groups": [g.get("group") for g in view.get("groups", [])],
                "krw_sensitivity_available": view.get("krw_sensitivity_available"),
            }
        },
    }


# Override relperm answer entrypoint:
# generic relperm requests show selector; explicit Krw modification still uses sensitivity.
answer_relperm_sensitivity_question_v60_original = answer_relperm_sensitivity_question

def answer_relperm_sensitivity_question(message):
    q = str(message or "").lower()
    requested_curve = detect_requested_relperm_curve_v67(message)
    wants_modification = any(x in q for x in [
        "modify", "modified", "adjust", "change", "sensitivity",
        "rifatta", "scarica", "export", "evaluate", "valuta"
    ])

    if requested_curve == "Krw_v_Sw" and wants_modification:
        return answer_relperm_sensitivity_question_v60_original(message)

    return answer_relperm_curve_selector_question_v67(message)



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

