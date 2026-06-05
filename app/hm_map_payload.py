from pathlib import Path
import json
import math
import csv


ROOT = Path(__file__).resolve().parents[1]

WELL_CONTEXT_CSV = ROOT / "artifacts" / "diagnosis" / "well_property_driver_context.csv"
ACTIVITY_JSON = ROOT / "artifacts" / "diagnosis" / "well_activity_classification.json"
INJECTION_JSON = ROOT / "artifacts" / "injection_hm" / "injection_hm_results.json"
OUTPUT_JSON = ROOT / "artifacts" / "dashboard" / "hm_map_payload.json"


def _safe_float(v):
    try:
        if v is None or v == "":
            return None
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None


def _load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_context_rows():
    rows = {}

    if not WELL_CONTEXT_CSV.exists():
        return rows

    with WELL_CONTEXT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            well = str(row.get("well") or "").upper()
            if well:
                rows[well] = row

    return rows


def _load_activity():
    data = _load_json(ACTIVITY_JSON)
    out = {}

    for item in data.get("wells", []):
        well = str(item.get("well") or "").upper()
        if well:
            out[well] = item

    return out


def _load_injection_results():
    data = _load_json(INJECTION_JSON)
    out = {}

    for well, payload in data.get("well_results", {}).items():
        out[str(well).upper()] = payload

    return out


def _load_spatial_summary():
    out = {}

    try:
        from app.well_connections import get_well_spatial_summary

        spatial = get_well_spatial_summary()

        for well, payload in spatial.get("wells", {}).items():
            w = str(well).upper()

            i = (
                payload.get("representative_i")
                or payload.get("i")
                or payload.get("mean_i")
            )

            j = (
                payload.get("representative_j")
                or payload.get("j")
                or payload.get("mean_j")
            )

            out[w] = {
                "well": well,
                "i": _safe_float(i),
                "j": _safe_float(j),
            }

    except Exception:
        pass

    return out


def _hm_class(score, raw_class=None, inactive=False):
    if inactive:
        return "Inactive"

    if raw_class and str(raw_class).strip():
        return str(raw_class).strip()

    if score is None:
        return "Not Evaluated"

    if score >= 80:
        return "Good"
    if score >= 60:
        return "Fair"
    return "Poor"


def _injection_class(score, raw_class=None, inactive=False):
    if inactive:
        return "Inactive"

    if raw_class and str(raw_class).strip():
        return str(raw_class).strip()

    if score is None:
        return "Not Evaluated"

    if score >= 80:
        return "Good"
    if score >= 60:
        return "Fair"
    return "Poor"


def build_hm_map_payload():
    ctx = _load_context_rows()
    activity = _load_activity()
    injection = _load_injection_results()
    spatial = _load_spatial_summary()

    all_wells = sorted(set(ctx.keys()) | set(activity.keys()) | set(injection.keys()) | set(spatial.keys()))

    payload_wells = []

    for well_upper in all_wells:
        row = ctx.get(well_upper, {})
        act = activity.get(well_upper, {})
        inj = injection.get(well_upper, {})
        sp = spatial.get(well_upper, {})

        well_name = row.get("well") or act.get("well") or sp.get("well") or well_upper

        i = _safe_float(row.get("i"))
        j = _safe_float(row.get("j"))

        if i is None:
            i = sp.get("i")
        if j is None:
            j = sp.get("j")

        if i is None or j is None:
            continue

        raw_role = str(act.get("well_role") or row.get("well_role") or "").lower()

        has_producer_evidence = bool(act.get("has_producer_evidence", False))
        has_injector_evidence = bool(act.get("has_injector_evidence", False))

        # Fallbacks if activity JSON is incomplete.
        if not raw_role:
            if has_producer_evidence and has_injector_evidence:
                raw_role = "producer_injector"
            elif has_injector_evidence:
                raw_role = "injector"
            else:
                raw_role = "producer"

        active_producer = bool(act.get("active_producer", False))
        active_injector = bool(act.get("active_injector", False))
        exclude_from_hm = bool(act.get("exclude_from_hm", False))

        producer_candidate = raw_role in ["producer", "producer_injector"] or has_producer_evidence
        injector_candidate = raw_role in ["injector", "producer_injector"] or has_injector_evidence or bool(inj)

        inactive_producer = producer_candidate and not active_producer
        inactive_injector = injector_candidate and not active_injector

        # Producer HM values: force inactive producers to grey/inactive for map.
        producer_inactive_for_map = inactive_producer or exclude_from_hm

        overall_score = _safe_float(row.get("overall_hm_score"))
        oil_score = _safe_float(row.get("oil_hm_score"))
        water_score = _safe_float(row.get("water_hm_score"))
        gas_score = _safe_float(row.get("gas_hm_score"))
        bhp_score = _safe_float(row.get("bhp_hm_score"))

        overall_class = _hm_class(overall_score, row.get("overall_hm_class"), producer_inactive_for_map)
        oil_class = _hm_class(oil_score, row.get("oil_hm_class"), producer_inactive_for_map)
        water_class = _hm_class(water_score, row.get("water_hm_class"), producer_inactive_for_map)
        gas_class = _hm_class(gas_score, row.get("gas_hm_class"), producer_inactive_for_map)
        bhp_class = _hm_class(bhp_score, row.get("bhp_hm_class"), producer_inactive_for_map)

        # Injector HM values.
        injection_score = (
            _safe_float(inj.get("injection_hm_score"))
            or _safe_float(inj.get("hm_score"))
            or _safe_float(inj.get("overall_hm_score"))
        )

        injection_class_raw = (
            inj.get("injection_hm_class")
            or inj.get("hm_class")
            or inj.get("overall_hm_class")
        )

        injection_class = _injection_class(
            injection_score,
            injection_class_raw,
            inactive=inactive_injector,
        )

        payload_wells.append({
            "well": well_name,
            "i": i,
            "j": j,

            "raw_well_role": raw_role,
            "producer_candidate": producer_candidate,
            "injector_candidate": injector_candidate,

            "active_producer": active_producer,
            "inactive_producer": inactive_producer,

            "active_injector": active_injector,
            "inactive_injector": inactive_injector,

            "exclude_from_hm": exclude_from_hm,
            "exclusion_reason": act.get("exclusion_reason"),

            "max_observed_oil_rate": act.get("max_observed_oil_rate"),
            "max_observed_injection_rate": act.get("max_observed_injection_rate"),

            "overall_score": None if producer_inactive_for_map else overall_score,
            "overall_class": overall_class,

            "oil_score": None if producer_inactive_for_map else oil_score,
            "oil_class": oil_class,

            "water_score": None if producer_inactive_for_map else water_score,
            "water_class": water_class,

            "gas_score": None if producer_inactive_for_map else gas_score,
            "gas_class": gas_class,

            "bhp_score": None if producer_inactive_for_map else bhp_score,
            "bhp_class": bhp_class,

            "injection_score": None if inactive_injector else injection_score,
            "injection_class": injection_class,
        })

    payload = {
        "ok": True,
        "well_count": len(payload_wells),

        "producer_candidate_count": sum(1 for w in payload_wells if w["producer_candidate"]),
        "active_producer_count": sum(1 for w in payload_wells if w["producer_candidate"] and w["active_producer"]),
        "inactive_producer_count": sum(1 for w in payload_wells if w["producer_candidate"] and not w["active_producer"]),

        "injector_candidate_count": sum(1 for w in payload_wells if w["injector_candidate"]),
        "active_injector_count": sum(1 for w in payload_wells if w["injector_candidate"] and w["active_injector"]),
        "inactive_injector_count": sum(1 for w in payload_wells if w["injector_candidate"] and not w["active_injector"]),

        "wells": payload_wells,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return payload


if __name__ == "__main__":
    payload = build_hm_map_payload()
    print(f"[OK] Saved {OUTPUT_JSON}")
    print(f"Total wells: {payload['well_count']}")
    print(f"Producer candidates: {payload['producer_candidate_count']}")
    print(f"Active producers: {payload['active_producer_count']}")
    print(f"Inactive producers: {payload['inactive_producer_count']}")
    print(f"Injector candidates: {payload['injector_candidate_count']}")
    print(f"Active injectors: {payload['active_injector_count']}")
    print(f"Inactive injectors: {payload['inactive_injector_count']}")
