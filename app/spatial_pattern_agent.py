import csv
import math
import re
from pathlib import Path
from typing import Dict, Any, List, Optional


ROOT = Path(__file__).resolve().parents[1]
CONTEXT_CSV = ROOT / "artifacts" / "diagnosis" / "well_property_driver_context.csv"


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


def load_rows() -> List[Dict[str, Any]]:
    if not CONTEXT_CSV.exists():
        return []

    with CONTEXT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def detect_well(text: str) -> Optional[str]:
    q = str(text or "").upper()
    m = re.search(r"\bHW[-_\s]?(\d+[A-Z]?)\b", q)
    if m:
        return f"HW-{m.group(1)}"
    return None


def norm_well(w):
    s = str(w or "").upper().strip()
    m = re.search(r"\bHW[-_\s]?(\d+[A-Z]?)\b", s)
    if m:
        return f"HW-{m.group(1)}"
    return s


def detect_variable(text: str) -> str:
    q = str(text or "").lower()

    if any(x in q for x in ["water", "wct", "water cut"]):
        return "water"

    if any(x in q for x in ["oil", "opr"]):
        return "oil"

    if any(x in q for x in ["gas", "gor"]):
        return "gas"

    if any(x in q for x in ["bhp", "pressure"]):
        return "bhp"

    return "water"


def row_well(row):
    return norm_well(row.get("well"))


def get_row(rows, well):
    target = norm_well(well)
    for r in rows:
        if row_well(r) == target:
            return r
    return None


def distance_cells(a, b):
    ai = safe_float(a.get("i"))
    aj = safe_float(a.get("j"))
    bi = safe_float(b.get("i"))
    bj = safe_float(b.get("j"))

    if None in [ai, aj, bi, bj]:
        return None

    return math.sqrt((ai - bi) ** 2 + (aj - bj) ** 2)


def variable_score(row, variable):
    key = {
        "water": "water_hm_score",
        "oil": "oil_hm_score",
        "gas": "gas_hm_score",
        "bhp": "bhp_hm_score",
    }.get(variable, "water_hm_score")

    return safe_float(row.get(key))


def variable_class(row, variable):
    key = {
        "water": "water_hm_class",
        "oil": "oil_hm_class",
        "gas": "gas_hm_class",
        "bhp": "bhp_hm_class",
    }.get(variable, "water_hm_class")

    return row.get(key) or ""


def mismatch_direction(row, variable):
    if variable == "water":
        return row.get("water_direction") or row.get("water_final_direction") or ""
    if variable == "bhp":
        return row.get("bhp_direction") or row.get("bhp_final_direction") or ""
    if variable == "oil":
        return row.get("oil_direction") or row.get("oil_final_direction") or ""
    if variable == "gas":
        return row.get("gas_direction") or row.get("gas_final_direction") or ""

    return ""


def is_active_evaluable(row):
    if str(row.get("exclude_from_hm") or "").lower() in ["true", "1", "yes"]:
        return False

    if str(row.get("inactive_producer_zero_oil_history") or "").lower() in ["true", "1", "yes"]:
        return False

    return True


def compact_well(row, variable, dist=None):
    return {
        "well": row.get("well"),
        "i": safe_float(row.get("i")),
        "j": safe_float(row.get("j")),
        "distance_cells": dist,
        "overall_hm_score": safe_float(row.get("overall_hm_score")),
        "variable_score": variable_score(row, variable),
        "variable_class": variable_class(row, variable),
        "direction": mismatch_direction(row, variable),
        "water_timing_issue": row.get("water_timing_issue"),
        "delta_swat": safe_float(row.get("delta_swat")),
        "delta_swat_percentile": safe_float(row.get("delta_swat_percentile")),
        "mean_swat_eoh": safe_float(row.get("mean_swat_eoh")),
        "mean_swat_eoh_percentile": safe_float(row.get("mean_swat_eoh_percentile")),
        "delta_pressure": safe_float(row.get("delta_pressure")),
        "delta_pressure_percentile": safe_float(row.get("delta_pressure_percentile")),
        "mean_pressure_eoh": safe_float(row.get("mean_pressure_eoh")),
        "mean_pressure_eoh_percentile": safe_float(row.get("mean_pressure_eoh_percentile")),
        "tran_percentile": safe_float(row.get("wellconn_weighted_tran_h_percentile")),
        "perm_percentile": safe_float(row.get("mean_perm_h_percentile")),
        "poro_percentile": safe_float(row.get("mean_poro_percentile")),
    }


def neighborhood_analysis(well: str, variable: str = "water", radius_cells: float = 25.0) -> Dict[str, Any]:
    rows = [r for r in load_rows() if is_active_evaluable(r)]
    target = get_row(rows, well)

    if not target:
        return {
            "ok": False,
            "message": f"Well {well} was not found in the active/evaluable context.",
            "well": well,
            "variable": variable,
        }

    target_score = variable_score(target, variable)
    target_direction = mismatch_direction(target, variable)
    target_timing = target.get("water_timing_issue") if variable == "water" else ""

    neighbors = []

    for r in rows:
        if row_well(r) == row_well(target):
            continue

        d = distance_cells(target, r)
        if d is None or d > radius_cells:
            continue

        neighbors.append(compact_well(r, variable, dist=d))

    neighbors.sort(key=lambda x: x["distance_cells"] if x["distance_cells"] is not None else 999999)

    similar = []
    for n in neighbors:
        same_direction = target_direction and n.get("direction") == target_direction
        same_timing = target_timing and n.get("water_timing_issue") == target_timing
        poor_or_fair = n.get("variable_score") is not None and n.get("variable_score") < 75

        if poor_or_fair and (same_direction or same_timing):
            similar.append(n)

    local_issue = len(similar) == 0
    clustered_issue = len(similar) >= 2

    target_compact = compact_well(target, variable, dist=0)

    interpretation = ""
    recommended_next = ""

    if variable == "water":
        if clustered_issue:
            interpretation = (
                f"{well} does not look isolated. {len(similar)} nearby wells show a similar water-mismatch signature. "
                "This suggests a local/regional water-movement pattern rather than a single-well correction."
            )

            recommended_next = (
                "First compare the water profiles and ΔSWAT map for this local group. "
                "If the same early/high-water signature is consistent across the cluster, investigate local water mobility/connectivity controls before changing field-wide relperm."
            )
        elif local_issue:
            interpretation = (
                f"{well} looks more isolated. Nearby wells do not show the same water-mismatch signature strongly enough."
            )

            recommended_next = (
                "Do not tune regional parameters from this well alone. First check the well profile, completion/schedule/control status, and local data quality before changing TRAN or relperm."
            )
        else:
            interpretation = (
                f"{well} has some nearby wells with partial similarity, but the pattern is not strong enough to call it systemic."
            )

            recommended_next = (
                "Use the profile and ΔSWAT map to decide whether this is becoming a local water-front pattern or remains a well-specific issue."
            )

    elif variable == "bhp":
        if clustered_issue:
            interpretation = (
                f"{well} is part of a local pressure-match pattern. Nearby wells show similar BHP mismatch behaviour."
            )

            recommended_next = (
                "Inspect pressure depletion and connected pore-volume indicators in the local area before applying single-well tuning."
            )
        else:
            interpretation = (
                f"{well} does not show a strong local pressure-mismatch cluster."
            )

            recommended_next = (
                "Check whether the pressure mismatch is related to well controls, measurement availability, or isolated local connectivity before regional tuning."
            )

    else:
        if clustered_issue:
            interpretation = (
                f"{well} is part of a local {variable}-match pattern. Nearby wells show similar mismatch behaviour."
            )

            recommended_next = (
                f"Compare {variable} profiles for the local group before deciding whether the driver is local or regional."
            )
        else:
            interpretation = (
                f"{well} currently looks more like an isolated {variable}-match issue than a strong spatial pattern."
            )

            recommended_next = (
                "Avoid tuning a regional parameter from this well alone. First confirm the profile and local well data."
            )

    return {
        "ok": True,
        "well": well,
        "variable": variable,
        "radius_cells": radius_cells,
        "target": target_compact,
        "neighbors_count": len(neighbors),
        "similar_neighbors_count": len(similar),
        "nearest_neighbors": neighbors[:8],
        "similar_neighbors": similar[:8],
        "pattern_type": "clustered" if clustered_issue else "isolated" if local_issue else "weak_partial_pattern",
        "interpretation": interpretation,
        "recommended_next": recommended_next,
    }


def field_pattern_analysis(variable: str = "water") -> Dict[str, Any]:
    rows = [r for r in load_rows() if is_active_evaluable(r)]

    points = []
    for r in rows:
        score = variable_score(r, variable)
        if score is None:
            continue

        item = compact_well(r, variable)
        points.append(item)

    poor = [p for p in points if p["variable_score"] is not None and p["variable_score"] < 60]
    fair = [p for p in points if p["variable_score"] is not None and 60 <= p["variable_score"] < 75]
    good = [p for p in points if p["variable_score"] is not None and p["variable_score"] >= 75]

    # Simple quadrant/systemic area grouping by median I/J.
    valid_i = [p["i"] for p in points if p["i"] is not None]
    valid_j = [p["j"] for p in points if p["j"] is not None]

    if not valid_i or not valid_j:
        return {
            "ok": False,
            "message": "No valid I/J coordinates found for field pattern analysis.",
            "variable": variable,
        }

    med_i = sorted(valid_i)[len(valid_i) // 2]
    med_j = sorted(valid_j)[len(valid_j) // 2]

    def area_name(p):
        if p["i"] is None or p["j"] is None:
            return "unknown"
        ew = "East" if p["i"] >= med_i else "West"
        ns = "North" if p["j"] <= med_j else "South"
        return f"{ns}-{ew}"

    areas = {}
    for p in points:
        a = area_name(p)
        areas.setdefault(a, []).append(p)

    area_summary = []
    for a, items in areas.items():
        scores = [x["variable_score"] for x in items if x["variable_score"] is not None]
        poor_items = [x for x in items if x["variable_score"] is not None and x["variable_score"] < 60]
        fair_items = [x for x in items if x["variable_score"] is not None and 60 <= x["variable_score"] < 75]

        if not scores:
            continue

        area_summary.append({
            "area": a,
            "well_count": len(items),
            "avg_score": sum(scores) / len(scores),
            "poor_count": len(poor_items),
            "fair_count": len(fair_items),
            "weak_wells": [x["well"] for x in sorted(poor_items + fair_items, key=lambda z: z["variable_score"])[:6]],
            "avg_delta_swat": avg([x["delta_swat"] for x in items]),
            "avg_delta_pressure": avg([x["delta_pressure"] for x in items]),
            "avg_tran_percentile": avg([x["tran_percentile"] for x in items]),
            "avg_perm_percentile": avg([x["perm_percentile"] for x in items]),
        })

    area_summary.sort(key=lambda x: x["avg_score"])

    weakest_area = area_summary[0] if area_summary else None

    interpretation = ""
    if weakest_area:
        interpretation = (
            f"The weakest {variable} pattern is concentrated in the {weakest_area['area']} area, "
            f"with average score {weakest_area['avg_score']:.1f}/100 and "
            f"{weakest_area['poor_count']} poor wells."
        )

    return {
        "ok": True,
        "variable": variable,
        "total_wells": len(points),
        "poor_count": len(poor),
        "fair_count": len(fair),
        "good_count": len(good),
        "weakest_wells": sorted(points, key=lambda x: x["variable_score"])[:10],
        "area_summary": area_summary,
        "interpretation": interpretation,
    }


def avg(values):
    xs = [v for v in values if v is not None]
    if not xs:
        return None
    return sum(xs) / len(xs)


def is_spatial_pattern_request(message: str) -> bool:
    q = str(message or "").lower()

    triggers = [
        "pattern",
        "cluster",
        "systemic",
        "systematic",
        "area",
        "regional",
        "neighborhood",
        "nearby",
        "around",
        "similar wells",
        "same issue",
        "underestimate",
        "overestimate",
        "sottostima",
        "sovrastima",
    ]

    return any(t in q for t in triggers)


def answer_spatial_pattern_question(message: str) -> Optional[Dict[str, Any]]:
    if not is_spatial_pattern_request(message):
        return None

    variable = detect_variable(message)
    well = detect_well(message)

    if well:
        analysis = neighborhood_analysis(well=well, variable=variable)

        if not analysis.get("ok"):
            return {
                "type": "visual_response",
                "answer": analysis.get("message"),
                "intent": "spatial_pattern_error",
                "ui_blocks": [],
                "data": analysis,
                "agent_trace": {"SpatialPatternAgent": analysis},
            }

        answer = (
            f"{analysis['interpretation']}\n\n"
            f"Recommended next step: {analysis['recommended_next']}"
        )

        return {
            "type": "visual_response",
            "answer": answer,
            "intent": "well_neighborhood_pattern",
            "ui_blocks": [
                {
                    "type": "compact_table",
                    "title": f"Similar nearby wells for {well}",
                    "columns": ["well", "distance_cells", "variable_score", "direction", "water_timing_issue", "delta_swat", "delta_pressure", "tran_percentile"],
                    "rows": analysis.get("similar_neighbors") or analysis.get("nearest_neighbors") or [],
                },
                {
                    "type": "suggestions",
                    "title": "Suggested follow-up",
                    "items": [
                        f"Show water profile for {well}",
                        f"Show delta SWAT map around {well}",
                        f"Show {variable} mismatch patterns",
                        f"Compare similar wells around {well}",
                    ],
                },
            ],
            "data": analysis,
            "agent_trace": {
                "SpatialPatternAgent": {
                    "mode": "well_neighborhood",
                    "well": well,
                    "variable": variable,
                    "pattern_type": analysis.get("pattern_type"),
                    "similar_neighbors_count": analysis.get("similar_neighbors_count"),
                }
            },
        }

    analysis = field_pattern_analysis(variable=variable)

    if not analysis.get("ok"):
        return {
            "type": "visual_response",
            "answer": analysis.get("message"),
            "intent": "spatial_pattern_error",
            "ui_blocks": [],
            "data": analysis,
            "agent_trace": {"SpatialPatternAgent": analysis},
        }

    answer = (
        f"{analysis['interpretation']}\n\n"
        f"Across the field: {analysis['poor_count']} wells are Poor and "
        f"{analysis['fair_count']} wells are Fair for {variable} match."
    )

    return {
        "type": "visual_response",
        "answer": answer,
        "intent": "field_spatial_pattern",
        "ui_blocks": [
            {
                "type": "compact_table",
                "title": f"Area-level {variable} match pattern",
                "columns": ["area", "well_count", "avg_score", "poor_count", "fair_count", "weak_wells", "avg_delta_swat", "avg_delta_pressure", "avg_tran_percentile"],
                "rows": analysis.get("area_summary") or [],
            },
            {
                "type": "compact_table",
                "title": f"Weakest {variable} wells",
                "columns": ["well", "variable_score", "direction", "water_timing_issue", "delta_swat", "delta_pressure", "tran_percentile"],
                "rows": analysis.get("weakest_wells") or [],
            },
            {
                "type": "suggestions",
                "title": "Suggested follow-up",
                "items": [
                    f"Show {variable} mismatch map",
                    f"Show delta SWAT map",
                    f"Analyze neighborhood around {analysis.get('weakest_wells', [{}])[0].get('well', 'HW-10')}",
                    f"Show similar wells with weak {variable} match",
                ],
            },
        ],
        "data": analysis,
        "agent_trace": {
            "SpatialPatternAgent": {
                "mode": "field_pattern",
                "variable": variable,
                "poor_count": analysis.get("poor_count"),
                "fair_count": analysis.get("fair_count"),
            }
        },
    }


if __name__ == "__main__":
    tests = [
        "show water mismatch patterns",
        "is HW-24 issue local or regional?",
        "analyze neighborhood around HW-24",
        "are there areas that underestimate water?",
    ]

    for q in tests:
        print("=" * 80)
        print(q)
        r = answer_spatial_pattern_question(q)
        print(r["intent"] if r else None)
        print(r["answer"] if r else None)
