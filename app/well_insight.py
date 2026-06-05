import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"

CONTEXT_CSV = ART / "diagnosis" / "well_property_driver_context.csv"
ACTIVITY_JSON = ART / "diagnosis" / "well_activity_classification.json"
FINAL_HM_JSON = ART / "final_diagnosis" / "final_hm_diagnosis.json"


VARIABLES = [
    {
        "key": "overall",
        "label": "Overall HM",
        "score_col": "overall_hm_score",
        "class_col": "overall_hm_class",
        "status_col": None,
    },
    {
        "key": "oil",
        "label": "Oil HM",
        "score_col": "oil_hm_score",
        "class_col": "oil_hm_class",
        "status_col": "oil_status",
    },
    {
        "key": "water",
        "label": "Water HM",
        "score_col": "water_hm_score",
        "class_col": "water_hm_class",
        "status_col": "water_status",
    },
    {
        "key": "gas",
        "label": "Gas HM",
        "score_col": "gas_hm_score",
        "class_col": "gas_hm_class",
        "status_col": "gas_status",
    },
    {
        "key": "bhp",
        "label": "BHP HM",
        "score_col": "bhp_hm_score",
        "class_col": "bhp_hm_class",
        "status_col": "bhp_status",
    },
]


def safe_float(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None


def score_class(score: Optional[float]) -> str:
    if score is None:
        return "Not Evaluated"
    if score >= 80:
        return "Good"
    if score >= 60:
        return "Fair"
    return "Poor"


def load_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_activity_lookup() -> Dict[str, Dict[str, Any]]:
    payload = load_json(ACTIVITY_JSON)
    out = {}

    for item in payload.get("wells", []):
        well = str(item.get("well") or "").upper()
        if well:
            out[well] = item

    return out


def row_is_excluded(row: Dict[str, Any], activity: Dict[str, Dict[str, Any]]) -> bool:
    well = str(row.get("well") or "").upper()
    act = activity.get(well, {})

    if act.get("exclude_from_hm"):
        return True

    if act.get("inactive_producer_zero_oil_history"):
        return True

    if str(row.get("exclude_from_hm") or "").lower() in ["true", "1", "yes"]:
        return True

    if str(row.get("hm_evaluable") or "").lower() in ["false", "0", "no"]:
        return True

    if str(row.get("producer_activity_status") or "").lower() == "inactive_producer_zero_oil_history":
        return True

    return False


def status_is_evaluable(status: Any) -> bool:
    s = str(status or "").strip().lower()

    if not s:
        return True

    bad = [
        "inactive",
        "not_evaluated",
        "not evaluated",
        "no_observed",
        "no observed",
        "missing",
        "unavailable",
        "not_applicable",
        "not applicable",
    ]

    return not any(x in s for x in bad)


def get_context_rows() -> List[Dict[str, Any]]:
    return load_csv(CONTEXT_CSV)


def get_final_diagnosis_lookup() -> Dict[str, Dict[str, Any]]:
    payload = load_json(FINAL_HM_JSON)

    items = payload.get("diagnoses", [])
    if not items and isinstance(payload, list):
        items = payload

    out = {}

    for item in items:
        well = str(item.get("well") or "").upper()
        if well:
            out[well] = item

    return out


def get_kpi_summary() -> Dict[str, Any]:
    rows = get_context_rows()
    activity = get_activity_lookup()

    active_rows = [r for r in rows if not row_is_excluded(r, activity)]

    cards = []

    for var in VARIABLES:
        values = []

        for row in active_rows:
            status_col = var["status_col"]

            if status_col and not status_is_evaluable(row.get(status_col)):
                continue

            value = safe_float(row.get(var["score_col"]))

            if value is None:
                continue

            values.append(value)

        avg_score = round(sum(values) / len(values), 2) if values else None

        cards.append({
            "key": var["key"],
            "label": var["label"],
            "score": avg_score,
            "value": avg_score,
            "class": score_class(avg_score),
            "evaluated_count": len(values),
            "active_well_count": len(active_rows),
            "subtext": f"{len(values)} evaluated wells" if values else "Not evaluated",
        })

    return {
        "cards": cards,
        "active_well_count": len(active_rows),
        "excluded_well_count": len(rows) - len(active_rows),
    }


def build_variable_card(row: Dict[str, Any], var: Dict[str, Any]) -> Dict[str, Any]:
    status = row.get(var["status_col"]) if var["status_col"] else "evaluated"
    score = safe_float(row.get(var["score_col"]))

    if var["status_col"] and not status_is_evaluable(status):
        score = None

    cls = row.get(var["class_col"]) or score_class(score)

    if score is None:
        cls = "Not Evaluated"

    return {
        "key": var["key"],
        "label": var["label"],
        "score": score,
        "value": score,
        "class": cls,
        "status": status or "evaluated",
    }


def collect_criticalities(row: Dict[str, Any], diagnosis: Dict[str, Any], activity: Dict[str, Any]) -> List[str]:
    out = []

    if activity.get("exclude_from_hm"):
        reason = activity.get("exclusion_reason") or "inactive or not evaluable"
        out.append(f"This well is excluded from HM scoring because it is classified as {reason}.")
        return out

    for var in VARIABLES[1:]:
        score = safe_float(row.get(var["score_col"]))
        status = row.get(var["status_col"])

        if var["status_col"] and not status_is_evaluable(status):
            continue

        if score is not None and score < 60:
            out.append(f"{var['label']} is Poor ({score:.1f}).")

        elif score is not None and score < 80:
            out.append(f"{var['label']} is Fair ({score:.1f}).")

    water_timing = row.get("water_timing_issue")
    water_direction = row.get("water_direction")

    if water_timing and str(water_timing).lower() not in ["none", "nan", ""]:
        out.append(f"Water timing signal: {water_timing}.")

    if water_direction and str(water_direction).lower() not in ["none", "nan", "", "final_value_close"]:
        out.append(f"Water direction signal: {water_direction}.")

    primary_driver = diagnosis.get("primary_driver") or row.get("primary_driver")
    driver_family = diagnosis.get("driver_family") or row.get("driver_family")

    if primary_driver:
        out.append(f"Likely driver: {primary_driver}.")

    if driver_family:
        out.append(f"Driver family: {driver_family}.")

    high_swat = str(row.get("high_water_saturation_signal") or "").lower() == "true"
    low_tran = str(row.get("low_tran_signal") or "").lower() == "true"

    if high_swat:
        out.append("High local SWAT signal is present near the well.")

    if low_tran:
        out.append("Low local transmissibility signal is present near the well.")

    if not out:
        out.append("No major criticality was detected from the current diagnostic artifacts.")

    return out[:7]


def get_well_insight(well: str) -> Dict[str, Any]:
    target = str(well or "").upper()
    rows = get_context_rows()
    activity_lookup = get_activity_lookup()
    diagnosis_lookup = get_final_diagnosis_lookup()

    row = None

    for r in rows:
        if str(r.get("well") or "").upper() == target:
            row = r
            break

    if row is None:
        return {
            "found": False,
            "well": well,
            "message": f"Well {well} was not found in the diagnostic context.",
        }

    activity = activity_lookup.get(target, {})
    diagnosis = diagnosis_lookup.get(target, {})

    cards = [build_variable_card(row, var) for var in VARIABLES]
    criticalities = collect_criticalities(row, diagnosis, activity)

    recommended_action = (
        diagnosis.get("recommended_action")
        or row.get("recommended_action")
        or "Review the variable-specific profiles, local property map and streamline/corridor context before applying model edits."
    )

    interpretation = (
        diagnosis.get("interpretation")
        or row.get("interpretation")
        or ""
    )

    return {
        "found": True,
        "well": row.get("well") or well,
        "cards": cards,
        "criticalities": criticalities,
        "recommended_action": recommended_action,
        "interpretation": interpretation,
        "activity": {
            "active_producer": activity.get("active_producer"),
            "active_injector": activity.get("active_injector"),
            "exclude_from_hm": activity.get("exclude_from_hm"),
            "exclusion_reason": activity.get("exclusion_reason"),
            "max_observed_oil_rate": activity.get("max_observed_oil_rate"),
            "max_observed_injection_rate": activity.get("max_observed_injection_rate"),
        },
        "raw": {
            "row": row,
            "diagnosis": diagnosis,
        },
    }


if __name__ == "__main__":
    print(json.dumps(get_kpi_summary(), indent=2))
