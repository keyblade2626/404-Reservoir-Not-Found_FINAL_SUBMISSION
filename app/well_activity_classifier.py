import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data" / "sample_model"

CONTEXT_CSV = ROOT / "artifacts" / "diagnosis" / "well_property_driver_context.csv"
OUTPUT_JSON = ROOT / "artifacts" / "diagnosis" / "well_activity_classification.json"
OUTPUT_CSV = ROOT / "artifacts" / "diagnosis" / "well_activity_classification.csv"

# Global business rule requested by user.
ACTIVE_OIL_RATE_THRESHOLD = 5.0
ACTIVE_INJECTION_RATE_THRESHOLD = 5.0


PRODUCER_KEYWORDS = [
    "WOPR", "WOPRH", "WOPT", "WOPTH",
    "WWPR", "WWPRH", "WGPR", "WGPRH",
    "WBHP", "WBHPH", "WBHPA",
]

INJECTOR_KEYWORDS = [
    "WWIR", "WWIRH", "WWIT", "WWITH",
    "WGIR", "WGIRH", "WGIT", "WGITH",
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


def discover_summary_case() -> Path:
    smspec = sorted(MODEL_DIR.glob("*.SMSPEC")) + sorted(MODEL_DIR.glob("*.smspec"))
    unsmry = sorted(MODEL_DIR.glob("*.UNSMRY")) + sorted(MODEL_DIR.glob("*.unsmry"))

    if smspec:
        return smspec[0]

    if unsmry:
        return unsmry[0]

    raise FileNotFoundError(f"No SMSPEC/UNSMRY found in {MODEL_DIR}")


def load_summary(path: Path):
    try:
        from resdata.summary import Summary
    except Exception as exc:
        raise ImportError("Cannot import resdata.summary.Summary") from exc

    for candidate in [path, path.with_suffix("")]:
        try:
            return Summary(str(candidate))
        except Exception:
            pass

    raise RuntimeError(f"Could not open summary case from {path}")


def get_keys(summary) -> List[str]:
    try:
        return [str(k) for k in summary.keys("*")]
    except Exception:
        return [str(k) for k in summary.keys()]


def get_vector(summary, key: Optional[str]) -> Optional[np.ndarray]:
    if not key:
        return None

    for method in ["numpy_vector", "get_values", "get_vector"]:
        try:
            values = getattr(summary, method)(key)
            return np.asarray(values, dtype=float)
        except Exception:
            pass

    try:
        return np.asarray(summary[key], dtype=float)
    except Exception:
        return None


def parse_key(key: str):
    if ":" not in key:
        return None, None

    keyword, well = key.split(":", 1)

    return keyword.strip().upper(), well.strip().upper()


def collect_wells(keys: List[str]) -> List[str]:
    wells = set()

    for key in keys:
        keyword, well = parse_key(key)
        if not keyword or not well:
            continue

        if keyword in set(PRODUCER_KEYWORDS + INJECTOR_KEYWORDS):
            wells.add(well)

    return sorted(wells)


def find_key(keys: List[str], keyword: str, well: str) -> Optional[str]:
    key_map = {k.upper(): k for k in keys}
    target = f"{keyword}:{well}".upper()

    if target in key_map:
        return key_map[target]

    prefix = f"{keyword}:".upper()
    well_u = well.upper()

    for k in keys:
        ku = k.upper()
        if ku.startswith(prefix) and ku.split(":", 1)[-1].upper() == well_u:
            return k

    return None


def max_positive(values: Optional[np.ndarray]) -> float:
    if values is None:
        return 0.0

    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]

    if arr.size == 0:
        return 0.0

    return float(np.nanmax(np.maximum(arr, 0.0)))


def has_any_key(keys: List[str], keywords: List[str], well: str) -> bool:
    for kw in keywords:
        if find_key(keys, kw, well):
            return True
    return False


def classify_well(summary, keys: List[str], well: str) -> Dict[str, Any]:
    # Observed / historical production basis.
    woprh_key = find_key(keys, "WOPRH", well)
    wopr_key = find_key(keys, "WOPR", well)

    # Use historical oil rate for active producer classification.
    woprh = get_vector(summary, woprh_key)
    max_observed_oil_rate = max_positive(woprh)

    # Simulated oil is reported only for evidence, not for active HM classification.
    wopr = get_vector(summary, wopr_key)
    max_simulated_oil_rate = max_positive(wopr)

    # Observed / historical injection basis.
    wwirh_key = find_key(keys, "WWIRH", well)
    wgirh_key = find_key(keys, "WGIRH", well)

    # Fallback: some models may not export H injection keys.
    # These are reported, but active HM should remain conservative if H is missing.
    wwir_key = find_key(keys, "WWIR", well)
    wgir_key = find_key(keys, "WGIR", well)

    wwirh = get_vector(summary, wwirh_key)
    wgirh = get_vector(summary, wgirh_key)

    max_observed_water_inj = max_positive(wwirh)
    max_observed_gas_inj = max_positive(wgirh)
    max_observed_total_inj = max(max_observed_water_inj, max_observed_gas_inj)

    max_sim_water_inj = max_positive(get_vector(summary, wwir_key))
    max_sim_gas_inj = max_positive(get_vector(summary, wgir_key))
    max_sim_total_inj = max(max_sim_water_inj, max_sim_gas_inj)

    has_producer_evidence = has_any_key(keys, PRODUCER_KEYWORDS, well)
    has_injector_evidence = has_any_key(keys, INJECTOR_KEYWORDS, well)

    active_producer = (
        has_producer_evidence
        and woprh_key is not None
        and max_observed_oil_rate >= ACTIVE_OIL_RATE_THRESHOLD
    )

    inactive_producer_zero_oil_history = (
        has_producer_evidence
        and not active_producer
    )

    active_injector = (
        has_injector_evidence
        and (
            (wwirh_key is not None or wgirh_key is not None)
            and max_observed_total_inj >= ACTIVE_INJECTION_RATE_THRESHOLD
        )
    )

    inactive_injector_zero_injection_history = (
        has_injector_evidence
        and not active_injector
    )

    if has_producer_evidence and has_injector_evidence:
        well_role = "producer_injector"
    elif has_injector_evidence:
        well_role = "injector"
    elif has_producer_evidence:
        well_role = "producer"
    else:
        well_role = "unknown"

    # Main HM rule:
    # - inactive producers are excluded from producer HM
    # - inactive injectors are excluded from injection HM
    # - active converted/mixed wells can be evaluated depending on active phase
    exclude_from_hm = False
    exclusion_reason = None

    if well_role == "producer" and inactive_producer_zero_oil_history:
        exclude_from_hm = True
        exclusion_reason = "inactive_producer_zero_observed_oil_rate"

    elif well_role == "injector" and inactive_injector_zero_injection_history:
        exclude_from_hm = True
        exclusion_reason = "inactive_injector_zero_observed_water_gas_injection"

    elif well_role == "producer_injector" and not active_producer and not active_injector:
        exclude_from_hm = True
        exclusion_reason = "inactive_converted_well_no_observed_oil_or_injection"

    if well_role == "producer" or well_role == "producer_injector":
        if active_producer:
            producer_activity_status = "active_producer_observed_oil"
        else:
            producer_activity_status = "inactive_producer_zero_oil_history"
    else:
        producer_activity_status = "not_a_producer"

    if well_role == "injector" or well_role == "producer_injector":
        if active_injector:
            injector_activity_status = "active_injector_observed_injection"
        else:
            injector_activity_status = "inactive_injector_zero_injection_history"
    else:
        injector_activity_status = "not_an_injector"

    return {
        "well": well,
        "well_role": well_role,

        "has_producer_evidence": has_producer_evidence,
        "has_injector_evidence": has_injector_evidence,

        "active_producer": active_producer,
        "inactive_producer_zero_oil_history": inactive_producer_zero_oil_history,
        "producer_activity_status": producer_activity_status,

        "active_injector": active_injector,
        "inactive_injector_zero_injection_history": inactive_injector_zero_injection_history,
        "injector_activity_status": injector_activity_status,

        "exclude_from_hm": exclude_from_hm,
        "exclusion_reason": exclusion_reason,

        "max_observed_oil_rate": max_observed_oil_rate,
        "max_simulated_oil_rate": max_simulated_oil_rate,

        "max_observed_water_inj_rate": max_observed_water_inj,
        "max_observed_gas_inj_rate": max_observed_gas_inj,
        "max_observed_injection_rate": max_observed_total_inj,

        "max_simulated_water_inj_rate": max_sim_water_inj,
        "max_simulated_gas_inj_rate": max_sim_gas_inj,
        "max_simulated_injection_rate": max_sim_total_inj,

        "woprh_key": woprh_key,
        "wopr_key": wopr_key,
        "wwirh_key": wwirh_key,
        "wgirh_key": wgirh_key,
        "wwir_key": wwir_key,
        "wgir_key": wgir_key,

        "active_oil_rate_threshold": ACTIVE_OIL_RATE_THRESHOLD,
        "active_injection_rate_threshold": ACTIVE_INJECTION_RATE_THRESHOLD,
    }


def read_context_rows() -> List[Dict[str, Any]]:
    if not CONTEXT_CSV.exists():
        return []

    with CONTEXT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_context_rows(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return

    fieldnames = []
    seen = set()

    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with CONTEXT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def update_context_csv(classification_by_well: Dict[str, Dict[str, Any]]) -> None:
    rows = read_context_rows()

    if not rows:
        return

    for row in rows:
        well = str(row.get("well") or "").upper()
        cls = classification_by_well.get(well)

        if not cls:
            continue

        # Add globally consistent activity fields.
        for key, value in cls.items():
            if key == "well":
                continue
            row[key] = value

        # Force inactive producers out of HM analysis.
        if cls.get("exclude_from_hm"):
            row["hm_evaluable"] = "False"
            row["well_activity_status"] = cls.get("exclusion_reason")
            row["producer_activity_status"] = cls.get("producer_activity_status")
            row["injector_activity_status"] = cls.get("injector_activity_status")

            # Keep original scores for audit, but mark status fields as inactive.
            if cls.get("inactive_producer_zero_oil_history"):
                row["oil_status"] = "inactive"
                row["water_status"] = "inactive"
                row["gas_status"] = "inactive"
                # BHP may exist, but if no active oil production, we exclude from producer HM.
                row["bhp_status"] = row.get("bhp_status") or "inactive"

    write_context_rows(rows)


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return

    fieldnames = []
    seen = set()

    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_well_activity_classification() -> Dict[str, Any]:
    case_path = discover_summary_case()
    summary = load_summary(case_path)
    keys = get_keys(summary)
    wells = collect_wells(keys)

    classifications = []

    for well in wells:
        classifications.append(classify_well(summary, keys, well))

    by_well = {row["well"].upper(): row for row in classifications}

    update_context_csv(by_well)

    payload = {
        "ok": True,
        "source_summary_case": str(case_path),
        "active_oil_rate_threshold": ACTIVE_OIL_RATE_THRESHOLD,
        "active_injection_rate_threshold": ACTIVE_INJECTION_RATE_THRESHOLD,
        "well_count": len(classifications),
        "active_producer_count": sum(1 for x in classifications if x["active_producer"]),
        "inactive_producer_count": sum(1 for x in classifications if x["inactive_producer_zero_oil_history"]),
        "active_injector_count": sum(1 for x in classifications if x["active_injector"]),
        "inactive_injector_count": sum(1 for x in classifications if x["inactive_injector_zero_injection_history"]),
        "excluded_from_hm_count": sum(1 for x in classifications if x["exclude_from_hm"]),
        "wells": classifications,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    write_csv(OUTPUT_CSV, classifications)

    return payload


def main() -> None:
    payload = build_well_activity_classification()

    print(f"[OK] Saved {OUTPUT_JSON}")
    print(f"[OK] Saved {OUTPUT_CSV}")
    print(f"Total wells classified: {payload['well_count']}")
    print(f"Active producers: {payload['active_producer_count']}")
    print(f"Inactive producers: {payload['inactive_producer_count']}")
    print(f"Active injectors: {payload['active_injector_count']}")
    print(f"Inactive injectors: {payload['inactive_injector_count']}")
    print(f"Excluded from HM: {payload['excluded_from_hm_count']}")


if __name__ == "__main__":
    main()
