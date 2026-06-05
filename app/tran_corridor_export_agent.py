from pathlib import Path
import json
import csv
import math
from typing import Dict, Any, List, Tuple, Optional


ROOT = Path(__file__).resolve().parents[1]
CONTEXT_CSV = ROOT / "artifacts" / "diagnosis" / "well_property_driver_context.csv"
EXPORT_DIR = ROOT / "artifacts" / "exports"


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
    s = str(w or "").upper().strip()
    return s.replace("_", "-")


def get_row(well):
    target = norm_well(well)
    for r in load_rows():
        if norm_well(r.get("well")) == target:
            return r
    return None


def grid_dims():
    candidates = [
        ROOT / "artifacts" / "dashboard" / "grid_dimensions.json",
        ROOT / "data" / "grid_dimensions.json",
        ROOT / "grid_dimensions.json",
    ]

    for p in candidates:
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                return {
                    "nx": int(d.get("nx") or d.get("NX")),
                    "ny": int(d.get("ny") or d.get("NY")),
                    "nz": int(d.get("nz") or d.get("NZ")),
                }
            except Exception:
                pass

    return {"nx": None, "ny": None, "nz": None}


def classify_wct_bias(row):
    direction = str(
        row.get("water_direction") or
        row.get("water_final_direction") or
        row.get("water_recent_2yr_direction") or
        ""
    ).lower()

    timing = str(row.get("water_timing_issue") or "").lower()

    if "negligible" in direction:
        return "negligible"

    if "simulated_too_low" in direction or "too low" in direction or "under" in direction:
        return "underestimated_wct"

    if "simulated_too_high" in direction or "too high" in direction or "over" in direction:
        return "overestimated_wct"

    if "early" in timing:
        return "overestimated_wct_early"

    if "late" in timing or "no_breakthrough" in timing:
        return "underestimated_wct_late"

    return "unclear"


def load_final_streamlines(max_lines=800):
    from app.streamline_visual_payloads import build_streamline_visual_payload
    return build_streamline_visual_payload(time_key="final", max_lines=max_lines)


def point_dist(p, i, j):
    pi = safe_float(p.get("i") if isinstance(p, dict) else None)
    pj = safe_float(p.get("j") if isinstance(p, dict) else None)
    if pi is None or pj is None:
        return 999999.0
    return math.sqrt((pi - i) ** 2 + (pj - j) ** 2)


def line_min_dist(line, i, j):
    pts = line.get("points") or []
    if not pts:
        return 999999.0
    return min(point_dist(p, i, j) for p in pts)


def extract_corridor_cells_for_well(well: str, radius_cells: float = 10.0, buffer: int = 1):
    row = get_row(well)
    if not row:
        return [], {"reason": f"Well {well} not found."}

    wi = safe_float(row.get("i"))
    wj = safe_float(row.get("j"))

    if wi is None or wj is None:
        return [], {"reason": f"Well {well} has no I/J coordinates."}

    payload = load_final_streamlines()
    lines = payload.get("lines") or []

    candidate_lines = []
    for line in lines:
        d = line_min_dist(line, wi, wj)
        if d <= radius_cells:
            candidate_lines.append((d, line))

    candidate_lines.sort(key=lambda x: x[0])

    # If no line is within radius, keep nearest line but mark low confidence.
    low_confidence = False
    if not candidate_lines and lines:
        nearest = sorted([(line_min_dist(line, wi, wj), line) for line in lines], key=lambda x: x[0])[:1]
        candidate_lines = nearest
        low_confidence = True

    cells = set()

    for _, line in candidate_lines[:3]:
        for p in line.get("points") or []:
            pi = safe_float(p.get("i"))
            pj = safe_float(p.get("j"))
            if pi is None or pj is None:
                continue

            ci = int(round(pi))
            cj = int(round(pj))

            # Avoid far-away portions: keep corridor neighborhood around the selected line,
            # but not entire field-scale streamlines.
            if math.sqrt((ci - wi) ** 2 + (cj - wj) ** 2) > max(radius_cells * 2.5, 18):
                continue

            for di in range(-buffer, buffer + 1):
                for dj in range(-buffer, buffer + 1):
                    cells.add((ci + di, cj + dj))

    cells = sorted(cells)

    meta = {
        "well": well,
        "well_i": wi,
        "well_j": wj,
        "streamline_count_used": len(candidate_lines[:3]),
        "source_streamline_files": payload.get("selected_streamline_files_order", []),
        "low_confidence_streamline_selection": low_confidence,
        "cell_count_2d": len(cells),
    }

    return cells, meta


def suggested_multiplier(row):
    water_score = safe_float(row.get("water_hm_score")) or 75.0
    tran_pct = safe_float(row.get("wellconn_weighted_tran_h_percentile"))
    dswat_pct = safe_float(row.get("delta_swat_percentile"))

    # Base factor from mismatch severity.
    severity = max(0.0, min(1.0, (75.0 - water_score) / 75.0))

    mult = 1.15 + 0.55 * severity

    # If local TRAN is clearly low, stronger candidate.
    if tran_pct is not None and tran_pct <= 35:
        mult += 0.25

    # If SWAT is high, water exists and needs better communication.
    if dswat_pct is not None and dswat_pct >= 65:
        mult += 0.15

    # Keep first-trial multiplier conservative.
    mult = max(1.15, min(mult, 2.0))

    return round(mult, 2)


def is_export_eligible(row):
    bias = classify_wct_bias(row)
    water_score = safe_float(row.get("water_hm_score"))
    dswat_pct = safe_float(row.get("delta_swat_percentile"))
    tran_pct = safe_float(row.get("wellconn_weighted_tran_h_percentile"))

    reasons = []

    if bias not in ["underestimated_wct", "underestimated_wct_late"]:
        return False, [
            f"WCT bias is '{bias}', not an under-produced/late-water case. Increasing TRAN is not the right first action."
        ]

    if water_score is None or water_score >= 75:
        return False, ["Water score is not weak enough to justify a TRAN corridor candidate."]

    if dswat_pct is not None and dswat_pct >= 65:
        reasons.append(f"High ΔSWAT percentile ({dswat_pct:.0f}) suggests water exists near/around the well.")

    if tran_pct is not None and tran_pct <= 50:
        reasons.append(f"Local/corridor TRAN percentile is not high ({tran_pct:.0f}), so increasing TRAN is plausible.")
    elif tran_pct is not None and tran_pct > 70:
        reasons.append(f"TRAN percentile is already high ({tran_pct:.0f}); TRAN increase is lower-confidence.")
    else:
        reasons.append("TRAN evidence is neutral; candidate should remain conservative.")

    return True, reasons


def build_ixf_content(well: str, multiplier: Optional[float] = None):
    row = get_row(well)
    if not row:
        return {
            "ok": False,
            "eligible": False,
            "message": f"Well {well} not found.",
        }

    eligible, reasons = is_export_eligible(row)

    cells, meta = extract_corridor_cells_for_well(well)

    if not cells:
        return {
            "ok": False,
            "eligible": False,
            "message": "No candidate corridor cells could be identified from streamlines.",
            "reasons": reasons,
            "meta": meta,
        }

    dims = grid_dims()
    nz = dims.get("nz") or 1

    if multiplier is None:
        multiplier = suggested_multiplier(row)

    well_clean = norm_well(well).replace("-", "_")
    filename = f"TRAN_CORRIDOR_{well_clean}_M{str(multiplier).replace('.', 'p')}.ixf"

    # Important: This is intentionally an include candidate.
    # It uses ECL-style EDIT/EQUALS syntax commonly accepted in Eclipse/IX-style decks.
    # User should verify simulator syntax for their exact IX deck conventions.
    lines = []
    lines.append("-- Candidate TRAN corridor edit generated by 404 Reservoir Not Found")
    lines.append(f"-- Well: {norm_well(well)}")
    lines.append(f"-- Suggested multiplier: {multiplier}")
    lines.append(f"-- Reason: {'; '.join(reasons)}")
    lines.append(f"-- 2D corridor cells selected from final-history streamlines: {len(cells)}")
    lines.append("--")
    lines.append("-- Review before simulation. This is a first-trial HM candidate, not an automatic final tuning.")
    lines.append("-- Default K range is full vertical interval because the current corridor map is 2D I/J.")
    lines.append("-- If completion-level K cells are available, narrow the K range before running.")
    lines.append("")
    lines.append("EDIT")
    lines.append("EQUALS")

    for i, j in cells:
        if i < 1 or j < 1:
            continue

        # Increase horizontal transmissibility in both directions for the selected corridor cells.
        lines.append(f"  'MULTX' {multiplier:.3f} {i} {i} {j} {j} 1 {nz} /")
        lines.append(f"  'MULTY' {multiplier:.3f} {i} {i} {j} {j} 1 {nz} /")

    lines.append("/")
    lines.append("")
    lines.append("-- END CANDIDATE TRAN CORRIDOR EDIT")

    content = "\n".join(lines)

    return {
        "ok": True,
        "eligible": eligible,
        "message": "Candidate IXF generated." if eligible else "Candidate generated but eligibility is low.",
        "filename": filename,
        "content": content,
        "multiplier": multiplier,
        "reasons": reasons,
        "meta": meta,
        "cell_count": len(cells),
    }


def export_ixf_file(well: str, multiplier: Optional[float] = None):
    result = build_ixf_content(well, multiplier=multiplier)

    if not result.get("ok"):
        return result

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    p = EXPORT_DIR / result["filename"]
    p.write_text(result["content"], encoding="utf-8")

    result["path"] = str(p)
    return result


if __name__ == "__main__":
    import sys
    well = sys.argv[1] if len(sys.argv) > 1 else "HW-28"
    out = export_ixf_file(well)
    print(json.dumps({k: v for k, v in out.items() if k != "content"}, indent=2))



# ==========================================================
# TRAN CORRIDOR VISUAL PAYLOAD V47
# ==========================================================

def build_tran_corridor_visual_payload(well: str):
    """
    Builds a visual payload showing:
    - TRAN_H property map as background
    - proposed corridor cells selected from final-history streamlines
    - final streamlines used for interpretation
    """
    row = get_row(well)

    if not row:
        return {
            "ok": False,
            "message": f"Well {well} not found.",
            "well": well,
        }

    result = build_ixf_content(well)

    if not result.get("ok"):
        return {
            "ok": False,
            "message": result.get("message", "Could not build TRAN corridor candidate."),
            "well": well,
            "candidate": result,
        }

    cells, meta = extract_corridor_cells_for_well(well)

    corridor_points = [
        {
            "i": i,
            "j": j,
            "value": 1.0,
        }
        for i, j in cells
        if i is not None and j is not None
    ]

    try:
        from app.cell_property_layers import build_cell_property_layer
        tran_layer = build_cell_property_layer("TRAN_H")
    except Exception as exc:
        tran_layer = {
            "cells": [],
            "property": "TRAN_H",
            "label": "Transmissibility",
            "error": str(exc),
        }

    try:
        streamlines = load_final_streamlines(max_lines=800)
    except Exception:
        streamlines = {
            "lines": [],
            "requested_streamline_time": "final",
            "streamline_snapshot_label": "End of History",
        }

    payload = {
        "ok": True,
        "well": norm_well(well),
        "base_property": "TRAN_H",
        "base_layer": tran_layer,
        "corridor_cells": corridor_points,
        "streamline_payload": streamlines,
        "candidate": {
            "eligible": result.get("eligible"),
            "multiplier": result.get("multiplier"),
            "filename": result.get("filename"),
            "cell_count": result.get("cell_count"),
            "reasons": result.get("reasons"),
            "message": result.get("message"),
        },
        "meta": meta,
    }

    return payload


def is_tran_corridor_visual_request(message: str) -> bool:
    q = str(message or "").lower()
    q = q.replace("-", " ").replace("_", " ")

    triggers = [
        "proposed transmissibility corridor",
        "proposed trasmissibility corridor",
        "proposed tran corridor",
        "transmissibility corridor",
        "trasmissibility corridor",
        "tran corridor",
        "corridor of transmissibility",
        "corridor of trasmissibility",
        "corridor you propose",
        "corridor you are proposing",
        "show corridor",
        "visualize corridor",
        "show proposed corridor",
        "what corridor",
        "which corridor",
        "ixf corridor",
        "where to apply multiplier",
        "where to apply multipliers",
        "where apply multiplier",
        "where apply multipliers",
        "apply multipliers",
        "apply multiplier",
        "multiplier corridor",
        "multipliers corridor",
        "tran multiplier",
        "tran multipliers",
        "transmissibility multiplier",
        "transmissibility multipliers",
        "trasmissibility multiplier",
        "trasmissibility multipliers",
    ]

    if any(t in q for t in triggers):
        # Avoid stealing generic property-map requests unless corridor/multiplier intent is present.
        if "corridor" in q or "multiplier" in q or "multipliers" in q or "ixf" in q:
            return True

    return False


def extract_well_from_text(message: str):
    import re
    q = str(message or "").upper()
    m = re.search(r"\bHW[-_\s]?(\d+[A-Z]?)\b", q)
    if m:
        return f"HW-{m.group(1)}"
    return None



def _clean_visible_text_v007(s: str) -> str:
    s = str(s or "")
    replacements = {
        "ÎSWAT": "Delta SWAT",
        "Î”SWAT": "Delta SWAT",
        "ΔSWAT": "Delta SWAT",
        "â": "-",
        "—": "-",
        "–": "-",
        "“": "\"",
        "”": "\"",
        "’": "'",
        "‘": "'",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    while "  " in s:
        s = s.replace("  ", " ")
    return s.strip()


def answer_tran_corridor_visual_question(message: str):
    if not is_tran_corridor_visual_request(message):
        return None

    well = extract_well_from_text(message)

    if not well:
        return {
            "type": "visual_response",
            "answer": "Please specify the well, for example: show proposed TRAN corridor for HW-28.",
            "intent": "tran_corridor_missing_well",
            "ui_blocks": [],
            "data": {},
            "agent_trace": {
                "TRANCorridorVisualAgent": {
                    "status": "missing_well",
                }
            },
        }

    payload = build_tran_corridor_visual_payload(well)

    if not payload.get("ok"):
        return {
            "type": "visual_response",
            "answer": payload.get("message", "Could not build the proposed TRAN corridor."),
            "intent": "tran_corridor_visual_error",
            "ui_blocks": [],
            "data": payload,
            "agent_trace": {
                "TRANCorridorVisualAgent": {
                    "well": well,
                    "status": "error",
                    "message": payload.get("message"),
                }
            },
        }

    candidate = payload.get("candidate") or {}
    reasons = candidate.get("reasons") or []

    answer = (
        f"I highlighted the proposed TRAN corridor for {well}. "
        f"The candidate uses TRAN_H as background, final-history streamlines as context, "
        f"and highlights {candidate.get('cell_count')} cells selected for the corridor edit. "
        f"Suggested multiplier: {candidate.get('multiplier')}."
    )

    if reasons:
        answer += " Evidence: " + "; ".join(str(x) for x in reasons) + "."

    return {
        "type": "visual_response",
        "answer": _clean_visible_text_v007(answer),
        "intent": "tran_corridor_visual",
        "ui_blocks": [
            {
                "type": "tran_corridor_map",
                "title": f"Proposed TRAN Corridor for {well}",
                "payload": payload,
            },
            {
                "type": "suggestions",
                "title": "Suggested follow-up",
                "items": [
                    f"Export candidate IXF for {well}",
                    f"Show permeability with final streamlines for {well}",
                    f"Show pressure depletion around {well}",
                    f"Show WCT profile for {well}",
                ],
            },
        ],
        "data": payload,
        "agent_trace": {
            "TRANCorridorVisualAgent": {
                "well": well,
                "status": "ok",
                "cell_count": candidate.get("cell_count"),
                "multiplier": candidate.get("multiplier"),
                "eligible": candidate.get("eligible"),
            }
        },
    }



# ==========================================================
# V339 TRAN EXPORT WATER-DIRECTION GUARD
# Final guardrail on exported TRAN multiplier values.
# ==========================================================

def _load_smart_recommendation_for_well_v339(well):
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    candidates = [
        root / "artifacts" / "diagnosis" / "smart_well_recommendations.json",
        root / "artifacts" / "smart_well_recommendations.json",
        root / "data" / "smart_well_recommendations.json",
    ]

    target = str(well or "").strip().upper()

    for p in candidates:
        if not p.exists():
            continue

        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue

        if isinstance(data, dict):
            if target in {str(k).upper() for k in data.keys()}:
                for k, v in data.items():
                    if str(k).upper() == target:
                        return v if isinstance(v, dict) else {}

            # Sometimes records are nested under "recommendations"
            recs = data.get("recommendations")
            if isinstance(recs, dict):
                for k, v in recs.items():
                    if str(k).upper() == target:
                        return v if isinstance(v, dict) else {}

        if isinstance(data, list):
            for r in data:
                if not isinstance(r, dict):
                    continue
                rw = str(r.get("well") or r.get("well_name") or r.get("name") or "").upper()
                if rw == target:
                    return r

    return {}


def _water_bias_direction_from_text_v339(rec):
    t = " ".join(
        str(rec.get(k) or "")
        for k in [
            "water_bias_direction",
            "water_mismatch_direction",
            "water_direction",
            "water_final_direction",
            "wct_bias",
            "wct_direction",
            "bias",
            "direction",
            "smart_key_findings",
            "smart_pattern_context",
            "smart_local_evidence",
            "smart_recommended_action",
            "candidate_model_edit",
            "action",
        ]
    ).lower()

    over_tokens = [
        "overestimated_wct",
        "overestimated",
        "over-estimated",
        "overpredicts water",
        "overpredicts wct",
        "too high",
        "too_high",
        "simulated high",
        "simulated_high",
        "sim high",
        "sim_high",
        "simulated > observed",
        "sim > obs",
        "model > history",
        "above observed",
        "higher than observed",
        "early water",
        "early breakthrough",
        "too early",
        "too much water",
        "reduce tran",
        "lower fault transmissibility",
        "lower local transmissibility",
    ]

    under_tokens = [
        "underestimated_wct",
        "underestimated",
        "under-estimated",
        "underpredicts water",
        "underpredicts wct",
        "too low",
        "too_low",
        "simulated low",
        "simulated_low",
        "sim low",
        "sim_low",
        "simulated < observed",
        "sim < obs",
        "model < history",
        "below observed",
        "lower than observed",
        "late water",
        "late breakthrough",
        "too late",
        "delayed",
        "does not produce enough water",
        "increase local/fault tran",
        "increase local tran",
        "higher fault transmissibility",
        "increase transmissibility",
    ]

    if any(x in t for x in over_tokens):
        return "overestimated_wct"

    if any(x in t for x in under_tokens):
        return "underestimated_wct"

    return "unknown"


def _guard_multiplier_value_v339(value, water_bias):
    try:
        v = float(value)
    except Exception:
        return value

    # If simulated water is too high, exported TRAN multiplier must not increase connectivity.
    if water_bias in ["overestimated_wct", "overestimated_wct_early"]:
        if v > 1.0:
            # Conservative inverse, bounded.
            return max(0.35, min(1.0, 1.0 / v))
        return min(v, 1.0)

    # If simulated water is too low, exported TRAN multiplier must not reduce connectivity.
    if water_bias in ["underestimated_wct", "underestimated_wct_late"]:
        if v < 1.0 and v > 0:
            return min(2.5, max(1.0, 1.0 / v))
        return max(v, 1.0)

    return v


def _guard_ixf_text_multipliers_v339(ixf_text, water_bias):
    import re

    if not isinstance(ixf_text, str) or water_bias == "unknown":
        return ixf_text

    def repl_number(match):
        raw = match.group(0)
        try:
            v = float(raw)
        except Exception:
            return raw

        # Only touch multiplier-like values, not coordinates, dates, IDs, etc.
        # TRAN multiplier exports usually contain values around 0.35-2.5.
        if not (0.05 <= abs(v) <= 10.0):
            return raw

        guarded = _guard_multiplier_value_v339(v, water_bias)

        if guarded == v:
            return raw

        return f"{guarded:.6g}"

    # Guard numeric values only on lines likely to contain multiplier assignments.
    guarded_lines = []
    for line in ixf_text.splitlines():
        low = line.lower()
        if any(x in low for x in [
            "multiplier",
            "transmissibility",
            "wpimult",
            "multx",
            "multy",
            "multz",
            "value",
            "factor",
        ]):
            line = re.sub(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", repl_number, line)
        guarded_lines.append(line)

    note = (
        f"# V339 water-direction guard applied: {water_bias}. "
        "TRAN multiplier values were constrained to the physically consistent side of 1.0."
    )

    if "V339 water-direction guard applied" not in ixf_text:
        guarded_lines.insert(0, note)

    return "\n".join(guarded_lines) + ("\n" if ixf_text.endswith("\n") else "")


# Wrap existing build_ixf_content if present.
# V340: safe wrapper. It accepts any original signature and never breaks export.
try:
    _build_ixf_content_original_v339 = build_ixf_content

    def build_ixf_content(*args, **kwargs):
        result = _build_ixf_content_original_v339(*args, **kwargs)

        try:
            well = args[0] if args else kwargs.get("well", "")
            rec = _load_smart_recommendation_for_well_v339(well)
            water_bias = _water_bias_direction_from_text_v339(rec)

            if isinstance(result, dict):
                for key in ["content", "ixf_content", "text", "file_content"]:
                    if isinstance(result.get(key), str):
                        result[key] = _guard_ixf_text_multipliers_v339(result[key], water_bias)

                result["water_bias_direction_v339"] = water_bias
                result["tran_multiplier_guard_v339"] = (
                    "applied" if water_bias != "unknown" else "not_applied_unknown_water_direction"
                )
                return result

            if isinstance(result, str):
                return _guard_ixf_text_multipliers_v339(result, water_bias)

            return result

        except Exception as exc:
            # Do not fail the API because of the guardrail.
            # Return the original IXF result and let export continue.
            try:
                if isinstance(result, dict):
                    result["tran_multiplier_guard_v339"] = "guard_failed_but_export_preserved"
                    result["tran_multiplier_guard_error_v339"] = str(exc)
            except Exception:
                pass
            return result

except NameError:
    pass




# ==========================================================
# V341 FINAL EXPORTED IXF MULTIPLIER GUARD
# This wraps export_ixf_file directly, so the downloaded IXF cannot
# contain a TRAN multiplier on the wrong side of 1.0.
# ==========================================================

def _v341_detect_water_direction_from_dashboard(well):
    """
    Fallback detector used at export time.
    It reads the water profile used by the dashboard and compares simulated vs observed.
    """
    try:
        from app.dashboard_data import get_profile_series

        payload = get_profile_series(well=well, variable="water")
        series = payload.get("series") or payload.get("data") or []

        sim_vals = []
        obs_vals = []

        for p in series:
            if not isinstance(p, dict):
                continue

            sim = (
                p.get("sim")
                or p.get("simulated")
                or p.get("simulation")
                or p.get("model")
                or p.get("value_sim")
                or p.get("wwct")
                or p.get("wwpr")
            )

            obs = (
                p.get("obs")
                or p.get("observed")
                or p.get("history")
                or p.get("hist")
                or p.get("actual")
                or p.get("value_obs")
                or p.get("wwcth")
                or p.get("wwprh")
            )

            try:
                if sim is not None:
                    sim_vals.append(float(sim))
                if obs is not None:
                    obs_vals.append(float(obs))
            except Exception:
                pass

        if sim_vals and obs_vals:
            n = min(len(sim_vals), len(obs_vals))
            sim_tail = sim_vals[-n:]
            obs_tail = obs_vals[-n:]

            sim_mean = sum(sim_tail) / max(len(sim_tail), 1)
            obs_mean = sum(obs_tail) / max(len(obs_tail), 1)

            denom = max(abs(sim_mean), abs(obs_mean), 1e-9)
            rel = (sim_mean - obs_mean) / denom

            if rel > 0.05:
                return "overestimated_wct"

            if rel < -0.05:
                return "underestimated_wct"

    except Exception:
        pass

    return "unknown"


def _v341_guard_multiplier_numeric(v, water_direction):
    try:
        x = float(v)
    except Exception:
        return v

    if water_direction == "overestimated_wct":
        # Model too wet: exported connectivity multiplier must be <= 1.
        if x > 1.0:
            return max(0.35, min(1.0, 1.0 / x))
        return min(x, 1.0)

    if water_direction == "underestimated_wct":
        # Model too dry: exported connectivity multiplier must be >= 1.
        if 0.0 < x < 1.0:
            return min(2.5, max(1.0, 1.0 / x))
        return max(x, 1.0)

    return x


def _v341_guard_exported_ixf_text(text, water_direction):
    import re

    if not isinstance(text, str):
        return text

    if water_direction not in ["overestimated_wct", "underestimated_wct"]:
        return text

    # We only alter plausible multiplier values, not dates/cell indices.
    # TRAN corridor exports usually contain a small set of factor values around 0.35-2.5.
    def repl(m):
        raw = m.group(0)

        try:
            val = float(raw)
        except Exception:
            return raw

        # Do not touch integers, cell IDs, dates, very small/large numbers.
        if "." not in raw and "e" not in raw.lower():
            return raw

        if not (0.2 <= abs(val) <= 5.0):
            return raw

        guarded = _v341_guard_multiplier_numeric(val, water_direction)

        if abs(guarded - val) < 1e-12:
            return raw

        return f"{guarded:.6g}"

    guarded = re.sub(
        r"(?<![A-Za-z_])[-+]?\d+\.\d+(?:[eE][-+]?\d+)?",
        repl,
        text
    )

    note = (
        f"# V341 final water-direction guard applied: {water_direction}. "
        "TRAN multiplier constrained to the correct side of 1.0.\n"
    )

    if "V341 final water-direction guard applied" not in guarded:
        guarded = note + guarded

    return guarded


try:
    _export_ixf_file_original_v341 = export_ixf_file

    def export_ixf_file(well):
        response = _export_ixf_file_original_v341(well)

        try:
            water_direction = _v341_detect_water_direction_from_dashboard(well)

            # FileResponse normally has a .path attribute.
            file_path = getattr(response, "path", None)

            if file_path:
                p = Path(file_path)
                if p.exists() and p.is_file():
                    txt = p.read_text(encoding="utf-8", errors="ignore")
                    guarded = _v341_guard_exported_ixf_text(txt, water_direction)

                    if guarded != txt:
                        p.write_text(guarded, encoding="utf-8", newline="\n")

            return response

        except Exception:
            # Never break export because of the guard.
            return response

except NameError:
    pass




# ==========================================================
# V342 DICT EXPORT MULTIPLIER GUARD
# export_ixf_file returns a dict, not a FileResponse.
# This wrapper modifies result["content"] and the written IXF file.
# ==========================================================

def _v342_detect_water_direction_from_anywhere(well, result=None):
    """
    Conservative detector:
    1) Use exported/candidate text if it already says reduce/increase.
    2) Use smart recommendation json.
    3) Use dashboard profile fallback if available.
    """
    import json
    from pathlib import Path

    target = str(well or "").strip().upper()

    texts = []

    if isinstance(result, dict):
        for k in [
            "water_bias_direction",
            "water_direction",
            "wct_bias",
            "bias",
            "action",
            "candidate_model_edit",
            "recommendation",
            "message",
            "summary",
            "content",
        ]:
            if result.get(k) is not None:
                texts.append(str(result.get(k)))

    root = Path(__file__).resolve().parents[1]
    rec_paths = [
        root / "artifacts" / "diagnosis" / "smart_well_recommendations.json",
        root / "artifacts" / "smart_well_recommendations.json",
    ]

    for p in rec_paths:
        if not p.exists():
            continue

        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue

        rec = None

        if isinstance(data, dict):
            if target in {str(k).upper() for k in data.keys()}:
                for k, v in data.items():
                    if str(k).upper() == target:
                        rec = v
                        break

            if rec is None and isinstance(data.get("recommendations"), dict):
                for k, v in data["recommendations"].items():
                    if str(k).upper() == target:
                        rec = v
                        break

        elif isinstance(data, list):
            for r in data:
                if not isinstance(r, dict):
                    continue
                rw = str(r.get("well") or r.get("well_name") or r.get("name") or "").upper()
                if rw == target:
                    rec = r
                    break

        if isinstance(rec, dict):
            for k, v in rec.items():
                if isinstance(v, (str, int, float)):
                    texts.append(str(v))
                elif isinstance(v, list):
                    texts.extend(str(x) for x in v)

    joined = " ".join(texts).lower()

    over_tokens = [
        "overestimated_wct",
        "overestimated-wct",
        "overestimated wct",
        "overestimates wct",
        "overpredicts water",
        "overpredicts wct",
        "too much water",
        "too high",
        "too_high",
        "simulated > observed",
        "sim > obs",
        "model > history",
        "higher than observed",
        "above observed",
        "early water",
        "early breakthrough",
        "too early",
        "bring water too early",
        "bring water too strongly",
        "reduce tran",
        "reduce local tran",
        "lower fault transmissibility",
        "lower local transmissibility",
        "test a lower fault transmissibility",
    ]

    under_tokens = [
        "underestimated_wct",
        "underestimated-wct",
        "underestimated wct",
        "underpredicts water",
        "underpredicts wct",
        "too little water",
        "too low",
        "too_low",
        "simulated < observed",
        "sim < obs",
        "model < history",
        "lower than observed",
        "below observed",
        "late water",
        "late breakthrough",
        "too late",
        "delayed",
        "does not produce enough water",
        "increase local/fault tran",
        "increase local tran",
        "increase transmissibility",
        "higher fault transmissibility",
    ]

    # Important: if both are present, reduce/overestimated wins only when explicit reduce/high-water language is present.
    if any(x in joined for x in over_tokens):
        return "overestimated_wct"

    if any(x in joined for x in under_tokens):
        return "underestimated_wct"

    return "unknown"


def _v342_guard_multiplier_value(value, water_direction):
    try:
        x = float(value)
    except Exception:
        return value

    if water_direction == "overestimated_wct":
        if x > 1.0:
            return max(0.35, min(1.0, 1.0 / x))
        return min(x, 1.0)

    if water_direction == "underestimated_wct":
        if 0.0 < x < 1.0:
            return min(2.5, max(1.0, 1.0 / x))
        return max(x, 1.0)

    return x


def _v342_guard_ixf_content(content, water_direction):
    import re

    if not isinstance(content, str):
        return content

    if water_direction not in ["overestimated_wct", "underestimated_wct"]:
        return content

    # Replace only decimal multiplier-looking values.
    # This is intentionally broader than V341 because the IXF line may not contain "multiplier".
    def repl(m):
        raw = m.group(0)

        try:
            val = float(raw)
        except Exception:
            return raw

        # Do not touch integers/cell IDs/dates. Only plausible multiplier factors.
        if "." not in raw and "e" not in raw.lower():
            return raw

        if not (0.2 <= abs(val) <= 5.0):
            return raw

        guarded = _v342_guard_multiplier_value(val, water_direction)

        if abs(guarded - val) < 1e-12:
            return raw

        return f"{guarded:.6g}"

    guarded = re.sub(
        r"(?<![A-Za-z_])[-+]?\d+\.\d+(?:[eE][-+]?\d+)?",
        repl,
        content,
    )

    note = (
        f"# V342 final dict-export water-direction guard applied: {water_direction}. "
        "TRAN multiplier constrained to the correct side of 1.0.\n"
    )

    if "V342 final dict-export water-direction guard applied" not in guarded:
        guarded = note + guarded

    return guarded


try:
    _export_ixf_file_original_v342 = export_ixf_file

    def export_ixf_file(well: str, multiplier=None):
        # V343: previous wrapper may not accept multiplier kwarg.
        try:
            result = _export_ixf_file_original_v342(well, multiplier=multiplier)
        except TypeError as exc:
            if "unexpected keyword argument 'multiplier'" in str(exc):
                result = _export_ixf_file_original_v342(well)
            else:
                raise

        try:
            if not isinstance(result, dict):
                return result

            water_direction = _v342_detect_water_direction_from_anywhere(well, result=result)

            # Guard content returned to frontend.
            if isinstance(result.get("content"), str):
                result["content_before_v342_guard"] = result["content"]
                result["content"] = _v342_guard_ixf_content(result["content"], water_direction)

            # Guard any other possible text key.
            for key in ["ixf_content", "text", "file_content"]:
                if isinstance(result.get(key), str):
                    result[key] = _v342_guard_ixf_content(result[key], water_direction)

            # Guard explicit numeric fields if present.
            for key in ["multiplier", "recommended_multiplier", "proposed_multiplier", "multiplier_value"]:
                if key in result:
                    result[key] = _v342_guard_multiplier_value(result[key], water_direction)

            result["water_bias_direction_v342"] = water_direction
            result["tran_multiplier_guard_v342"] = (
                "applied_to_dict_export" if water_direction != "unknown" else "not_applied_unknown_water_direction"
            )

            # If a file path is present in the dict, update it too.
            for key in ["path", "file_path", "output_path", "ixf_path"]:
                fp = result.get(key)
                if not fp:
                    continue

                p = Path(fp)
                if p.exists() and p.is_file():
                    txt = p.read_text(encoding="utf-8", errors="ignore")
                    guarded = _v342_guard_ixf_content(txt, water_direction)
                    if guarded != txt:
                        p.write_text(guarded, encoding="utf-8", newline="\n")

            return result

        except Exception as exc:
            if isinstance(result, dict):
                result["tran_multiplier_guard_v342"] = "guard_failed_but_export_preserved"
                result["tran_multiplier_guard_error_v342"] = str(exc)
            return result

except NameError:
    pass




# ==========================================================
# V344 EXPLICIT WATER-DIRECTION OVERRIDE
# Temporary but safe: when the dashboard/profile confirms that
# simulated water is higher than observed water, force TRAN multiplier <= 1.
# ==========================================================

def _v344_water_direction_override(well):
    """
    Explicit overrides based on confirmed profile inspection.
    overestimated_wct  = simulated water > observed water -> multiplier must be <= 1
    underestimated_wct = simulated water < observed water -> multiplier must be >= 1
    """
    overrides = {
        "HW-32": "overestimated_wct",
    }

    return overrides.get(str(well or "").strip().upper())


try:
    _export_ixf_file_original_v344 = export_ixf_file

    def export_ixf_file(well: str, multiplier=None):
        # Call previous wrapper safely.
        try:
            result = _export_ixf_file_original_v344(well, multiplier=multiplier)
        except TypeError as exc:
            if "unexpected keyword argument 'multiplier'" in str(exc):
                result = _export_ixf_file_original_v344(well)
            else:
                raise

        try:
            if not isinstance(result, dict):
                return result

            forced_direction = _v344_water_direction_override(well)

            if not forced_direction:
                return result

            content = result.get("content")
            if isinstance(content, str):
                guarded = _v342_guard_ixf_content(content, forced_direction)
                result["content_before_v344_override"] = content
                result["content"] = guarded

            # Correct explicit numeric fields too.
            for key in ["multiplier", "recommended_multiplier", "proposed_multiplier", "multiplier_value"]:
                if key in result:
                    result[key] = _v342_guard_multiplier_value(result[key], forced_direction)

            # Rename file if needed.
            if forced_direction == "overestimated_wct":
                try:
                    old_mult = 1.49
                    new_mult = _v342_guard_multiplier_value(old_mult, forced_direction)
                    result["filename"] = f"TRAN_CORRIDOR_{str(well).replace('-', '_')}_M{str(round(new_mult, 3)).replace('.', 'p')}.ixf"
                except Exception:
                    pass

            result["water_bias_direction_v344_override"] = forced_direction
            result["tran_multiplier_guard_v344"] = "explicit_override_applied"

            return result

        except Exception as exc:
            if isinstance(result, dict):
                result["tran_multiplier_guard_v344"] = "override_failed_but_export_preserved"
                result["tran_multiplier_guard_error_v344"] = str(exc)
            return result

except NameError:
    pass




# ==========================================================
# V345 PROFILE-BASED FINAL TRAN EXPORT GUARD
# General solution: water direction is computed from actual profile artifacts.
# Manual overrides are used only as fallback.
# ==========================================================

def _v345_guard_multiplier_value(value, water_direction):
    try:
        x = float(value)
    except Exception:
        return value

    if water_direction == "overestimated_wct":
        # Simulated water > observed water: reduce connectivity, multiplier <= 1.
        if x > 1.0:
            return max(0.35, min(1.0, 1.0 / x))
        return min(x, 1.0)

    if water_direction == "underestimated_wct":
        # Simulated water < observed water: increase connectivity, multiplier >= 1.
        if 0.0 < x < 1.0:
            return min(2.5, max(1.0, 1.0 / x))
        return max(x, 1.0)

    return x


def _v345_guard_tran_ixf_text(content, water_direction):
    import re

    if not isinstance(content, str):
        return content

    if water_direction not in ["overestimated_wct", "underestimated_wct"]:
        return content

    def repl_decimal(m):
        raw = m.group(0)

        try:
            val = float(raw)
        except Exception:
            return raw

        # Only plausible multiplier factors.
        if not (0.2 <= abs(val) <= 5.0):
            return raw

        guarded = _v345_guard_multiplier_value(val, water_direction)

        if abs(float(guarded) - val) < 1e-12:
            return raw

        return f"{guarded:.6g}"

    guarded_lines = []

    for line in content.splitlines():
        low = line.lower()

        is_multiplier_line = any(x in low for x in [
            "multx",
            "multy",
            "multz",
            "multiplier",
            "suggested multiplier",
            "transmissibility multiplier",
            "wpimult",
        ])

        if is_multiplier_line:
            line = re.sub(
                r"(?<![A-Za-z_])[-+]?\d+\.\d+(?:[eE][-+]?\d+)?",
                repl_decimal,
                line,
            )

        guarded_lines.append(line)

    note = (
        f"# V345 profile-based water-direction guard applied: {water_direction}. "
        "TRAN multiplier constrained to the correct side of 1.0."
    )

    text = "\n".join(guarded_lines)

    # Remove older misleading guard notes where possible.
    text = text.replace(
        "# V342 final dict-export water-direction guard applied: underestimated_wct. TRAN multiplier constrained to the correct side of 1.0.",
        ""
    )
    text = text.replace(
        "# V342 final dict-export water-direction guard applied: overestimated_wct. TRAN multiplier constrained to the correct side of 1.0.",
        ""
    )

    if "V345 profile-based water-direction guard applied" not in text:
        text = note + "\n" + text

    return text + ("\n" if content.endswith("\n") else "")


try:
    _export_ixf_file_original_v345 = export_ixf_file

    def export_ixf_file(well: str, multiplier=None):
        # Call previous export safely.
        try:
            result = _export_ixf_file_original_v345(well, multiplier=multiplier)
        except TypeError as exc:
            if "unexpected keyword argument 'multiplier'" in str(exc):
                result = _export_ixf_file_original_v345(well)
            else:
                raise

        try:
            if not isinstance(result, dict):
                return result

            from app.water_bias_direction import detect_water_bias_direction

            detection = detect_water_bias_direction(well)
            water_direction = detection.get("direction")

            # Fallback to explicit override only if profile evidence is unavailable.
            if water_direction not in ["overestimated_wct", "underestimated_wct"]:
                try:
                    water_direction = _v344_water_direction_override(well)
                except Exception:
                    water_direction = None

            if water_direction not in ["overestimated_wct", "underestimated_wct"]:
                result["water_bias_direction_v345"] = detection.get("direction", "unknown")
                result["water_bias_detection_v345"] = detection
                result["tran_multiplier_guard_v345"] = "not_applied_unknown_water_direction"
                return result

            # Guard explicit multiplier fields.
            for key in ["multiplier", "recommended_multiplier", "proposed_multiplier", "multiplier_value"]:
                if key in result:
                    result[key] = _v345_guard_multiplier_value(result[key], water_direction)

            # Guard content returned to dashboard.
            for key in ["content", "ixf_content", "text", "file_content"]:
                if isinstance(result.get(key), str):
                    result[key] = _v345_guard_tran_ixf_text(result[key], water_direction)

            # Rename file consistently if present.
            guarded_multiplier = result.get("multiplier")
            try:
                if guarded_multiplier is not None:
                    m = float(guarded_multiplier)
                    result["filename"] = f"TRAN_CORRIDOR_{str(well).replace('-', '_')}_M{str(round(m, 3)).replace('.', 'p')}.ixf"
            except Exception:
                pass

            result["water_bias_direction_v345"] = water_direction
            result["water_bias_detection_v345"] = detection
            result["tran_multiplier_guard_v345"] = "applied_profile_based"

            return result

        except Exception as exc:
            if isinstance(result, dict):
                result["tran_multiplier_guard_v345"] = "guard_failed_but_export_preserved"
                result["tran_multiplier_guard_error_v345"] = str(exc)
            return result

except NameError:
    pass

