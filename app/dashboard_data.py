import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"

CONTEXT_CSV = ART / "diagnosis" / "well_property_driver_context.csv"
FINAL_WATER_JSON = ART / "final_diagnosis" / "final_hm_diagnosis.json"
FINAL_GAS_JSON = ART / "final_diagnosis" / "final_gas_diagnosis.json"
FINAL_OIL_JSON = ART / "final_diagnosis" / "final_oil_diagnosis.json"
PORO_PRESSURE_JSON = ART / "final_diagnosis" / "porosity_pressure_observations.json"
CORRIDOR_JSON = ART / "final_diagnosis" / "transmissibility_corridors" / "candidate_transmissibility_corridors.json"
CORRIDOR_SUMMARY_CSV = ART / "final_diagnosis" / "transmissibility_corridors" / "candidate_transmissibility_corridor_summary.csv"



ACTIVITY_JSON = ART / "diagnosis" / "well_activity_classification.json"

_ACTIVITY_CACHE = None

def get_activity_lookup() -> Dict[str, Any]:
    global _ACTIVITY_CACHE

    if _ACTIVITY_CACHE is not None:
        return _ACTIVITY_CACHE

    payload = load_json(ACTIVITY_JSON)
    lookup = {}

    for item in payload.get("wells", []):
        well = str(item.get("well") or "").upper()
        if well:
            lookup[well] = item

    _ACTIVITY_CACHE = lookup
    return lookup


VARIABLE_COLUMNS = {
    "overall": "overall_hm_score",
    "oil": "oil_hm_score",
    "water": "water_hm_score",
    "gas": "gas_hm_score",
    "bhp": "bhp_hm_score",
}


def safe_float(value: Any) -> Optional[float]:
    if value in [None, "", "None", "null", "N/A"]:
        return None
    try:
        return float(value)
    except Exception:
        return None


def load_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def score_class(score: Optional[float], inactive: bool = False) -> str:
    if inactive or score is None:
        return "Inactive"
    if score >= 80:
        return "Good"
    if score >= 60:
        return "Fair"
    return "Poor"


def class_color(cls: str) -> str:
    return {
        "Good": "#22c55e",
        "Fair": "#facc15",
        "Poor": "#ef4444",
        "Inactive": "#64748b",
    }.get(cls, "#64748b")


def is_inactive(row: Dict[str, Any]) -> bool:
    well = str(row.get("well") or "").upper()
    activity = get_activity_lookup().get(well, {})

    if activity:
        if activity.get("exclude_from_hm"):
            return True

        if activity.get("inactive_producer_zero_oil_history"):
            return True

        # For producer HM dashboard, a producer with active_producer=False is inactive.
        role = str(activity.get("well_role") or "").lower()
        if role in ["producer", "producer_injector"] and not activity.get("active_producer", False):
            return True

    exclude = str(row.get("exclude_from_hm") or "").strip().lower()
    if exclude in ["true", "1", "yes"]:
        return True

    hm_evaluable = str(row.get("hm_evaluable") or "true").strip().lower()
    if hm_evaluable in ["false", "0", "no"]:
        return True

    producer_status = str(row.get("producer_activity_status") or "").strip().lower()
    if producer_status == "inactive_producer_zero_oil_history":
        return True

    well_activity = str(row.get("well_activity_status") or "").strip().lower()
    if well_activity in [
        "inactive_no_oil_profile",
        "inactive_producer_zero_oil_history",
        "inactive",
        "no_profile",
        "simulated_active_no_observed_oil_profile",
        "inactive_producer_zero_observed_oil_rate",
        "inactive_injector_zero_observed_water_gas_injection",
    ]:
        return True

    return False



def get_context_rows() -> List[Dict[str, Any]]:
    return load_csv(CONTEXT_CSV)


def get_avg(rows: List[Dict[str, Any]], col: str) -> Optional[float]:
    values = []

    for r in rows:
        if is_inactive(r):
            continue
        v = safe_float(r.get(col))
        if v is not None:
            values.append(v)

    if not values:
        return None

    return round(sum(values) / len(values), 2)


def get_summary_cards() -> Dict[str, Any]:
    rows = get_context_rows()

    cards = []

    for label, variable in [
        ("Overall HM", "overall"),
        ("Oil HM", "oil"),
        ("Water HM", "water"),
        ("Gas HM", "gas"),
        ("BHP HM", "bhp"),
    ]:
        col = VARIABLE_COLUMNS[variable]
        avg = get_avg(rows, col)
        cls = score_class(avg)

        cards.append({
            "label": label,
            "variable": variable,
            "score": avg,
            "class": cls,
            "color": class_color(cls),
        })

    counts = {"Good": 0, "Fair": 0, "Poor": 0, "Inactive": 0}

    for r in rows:
        s = safe_float(r.get("overall_hm_score"))
        cls = score_class(s, inactive=is_inactive(r))
        counts[cls] += 1

    corridor_rows = load_csv(CORRIDOR_SUMMARY_CSV)

    cards.append({
        "label": "Inactive Wells",
        "variable": "inactive",
        "score": counts["Inactive"],
        "class": "Inactive",
        "color": class_color("Inactive"),
    })

    cards.append({
        "label": "Candidate Corridors",
        "variable": "corridors",
        "score": len(corridor_rows),
        "class": "Info",
        "color": "#38bdf8",
    })

    return {
        "cards": cards,
        "well_counts": counts,
        "well_count": len(rows),
        "artifact_status": {
            "context_csv": CONTEXT_CSV.exists(),
            "final_water": FINAL_WATER_JSON.exists(),
            "final_gas": FINAL_GAS_JSON.exists(),
            "final_oil": FINAL_OIL_JSON.exists(),
            "corridors": CORRIDOR_JSON.exists(),
        },
    }


def get_well_map(variable: str = "overall") -> Dict[str, Any]:
    rows = get_context_rows()
    col = VARIABLE_COLUMNS.get(variable, "overall_hm_score")

    wells = []

    for r in rows:
        well = r.get("well")
        i = safe_float(r.get("i"))
        j = safe_float(r.get("j"))

        if not well or i is None or j is None:
            continue

        s = safe_float(r.get(col))
        inactive = is_inactive(r)
        cls = score_class(s, inactive=inactive)

        wells.append({
            "well": well,
            "i": i,
            "j": j,
            "score": s,
            "class": cls,
            "color": class_color(cls),
            "variable": variable,
            "oil_score": safe_float(r.get("oil_hm_score")),
            "water_score": safe_float(r.get("water_hm_score")),
            "gas_score": safe_float(r.get("gas_hm_score")),
            "bhp_score": safe_float(r.get("bhp_hm_score")),
            "overall_score": safe_float(r.get("overall_hm_score")),
        })

    return {
        "variable": variable,
        "wells": wells,
    }


def find_diag(path: Path, well: str) -> Optional[Dict[str, Any]]:
    payload = load_json(path)
    for item in payload.get("diagnoses", []):
        if item.get("well") == well:
            return item
    return None


def get_well_detail(well: str) -> Dict[str, Any]:
    rows = get_context_rows()
    row = next((r for r in rows if str(r.get("well")).upper() == well.upper()), None)

    if row is None:
        return {"found": False, "well": well}

    corridor_rows = load_csv(CORRIDOR_SUMMARY_CSV)
    corridor = next((r for r in corridor_rows if str(r.get("well")).upper() == well.upper()), None)

    return {
        "found": True,
        "well": row.get("well"),
        "location": {
            "i": safe_float(row.get("i")),
            "j": safe_float(row.get("j")),
        },
        "scores": {
            "overall": safe_float(row.get("overall_hm_score")),
            "oil": safe_float(row.get("oil_hm_score")),
            "water": safe_float(row.get("water_hm_score")),
            "gas": safe_float(row.get("gas_hm_score")),
            "bhp": safe_float(row.get("bhp_hm_score")),
        },
        "classes": {
            "overall": row.get("overall_hm_class"),
            "oil": row.get("oil_hm_class"),
            "water": row.get("water_hm_class"),
            "gas": row.get("gas_hm_class"),
            "bhp": row.get("bhp_hm_class"),
        },
        "water_diagnosis": find_diag(FINAL_WATER_JSON, row.get("well")),
        "oil_diagnosis": find_diag(FINAL_OIL_JSON, row.get("well")),
        "gas_diagnosis": find_diag(FINAL_GAS_JSON, row.get("well")),
        "corridor": corridor,
        "raw": row,
    }


def get_top_mismatches(variable: str = "water", limit: int = 10) -> Dict[str, Any]:
    rows = get_context_rows()
    col = VARIABLE_COLUMNS.get(variable, "water_hm_score")

    items = []

    for r in rows:
        if is_inactive(r):
            continue

        s = safe_float(r.get(col))
        if s is None:
            continue

        items.append({
            "well": r.get("well"),
            "score": s,
            "class": score_class(s),
            "oil": safe_float(r.get("oil_hm_score")),
            "water": safe_float(r.get("water_hm_score")),
            "gas": safe_float(r.get("gas_hm_score")),
            "bhp": safe_float(r.get("bhp_hm_score")),
            "issue": r.get(f"{variable}_direction") or r.get("water_direction"),
        })

    items = sorted(items, key=lambda x: x["score"])[:limit]

    return {
        "variable": variable,
        "items": items,
    }


def get_area_summary(area: str = "south") -> Dict[str, Any]:
    rows = get_context_rows()
    valid = []

    for r in rows:
        j = safe_float(r.get("j"))
        if j is not None:
            valid.append((j, r))

    if not valid:
        return {"area": area, "wells": [], "summary": {}}

    js = sorted(j for j, _ in valid)
    n = len(js)
    low = js[n // 3]
    high = js[(2 * n) // 3]

    selected = []

    for j, r in valid:
        if area.lower() == "north" and j <= low:
            selected.append(r)
        elif area.lower() == "south" and j >= high:
            selected.append(r)
        elif area.lower() in ["central", "center", "middle"] and low < j < high:
            selected.append(r)

    if not selected:
        selected = [r for _, r in valid]

    def avg(col):
        return get_avg(selected, col)

    return {
        "area": area,
        "well_count": len(selected),
        "wells": [r.get("well") for r in selected],
        "summary": {
            "overall": avg("overall_hm_score"),
            "oil": avg("oil_hm_score"),
            "water": avg("water_hm_score"),
            "gas": avg("gas_hm_score"),
            "bhp": avg("bhp_hm_score"),
        },
        "top_water_mismatches": sorted(
            [
                {"well": r.get("well"), "score": safe_float(r.get("water_hm_score"))}
                for r in selected
                if safe_float(r.get("water_hm_score")) is not None
            ],
            key=lambda x: x["score"],
        )[:5],
        "top_bhp_mismatches": sorted(
            [
                {"well": r.get("well"), "score": safe_float(r.get("bhp_hm_score"))}
                for r in selected
                if safe_float(r.get("bhp_hm_score")) is not None
            ],
            key=lambda x: x["score"],
        )[:5],
    }


def get_corridor_candidates() -> Dict[str, Any]:
    summary = load_csv(CORRIDOR_SUMMARY_CSV)
    payload = load_json(CORRIDOR_JSON)

    return {
        "summary": summary,
        "method": payload.get("method", {}),
        "candidate_cell_count": len(payload.get("candidate_cells", [])),
        "map_url": "/artifacts/final_diagnosis/transmissibility_corridors/candidate_transmissibility_corridors_all.png",
    }



# ==========================================================
# V230 KPI summary override
# Keep only the five main HM KPI cards in the dashboard.
# ==========================================================
def get_summary_cards():
    from app.well_insight import get_kpi_summary
    return get_kpi_summary()
