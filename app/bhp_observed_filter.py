import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data" / "sample_model"

CONTEXT_CSV = ROOT / "artifacts" / "diagnosis" / "well_property_driver_context.csv"
OUTPUT_JSON = ROOT / "artifacts" / "diagnosis" / "bhp_observed_filter_report.json"

OBSERVED_BHP_MIN_VALID_PRESSURE = 1.0


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


def max_valid(values: Optional[np.ndarray]) -> float:
    if values is None:
        return 0.0

    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]

    if arr.size == 0:
        return 0.0

    return float(np.nanmax(np.abs(arr)))


def read_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return

    fieldnames = []
    seen = set()

    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def score_class(score: Optional[float]) -> str:
    if score is None:
        return "Not Evaluated"
    if score >= 80:
        return "Good"
    if score >= 60:
        return "Fair"
    return "Poor"


def status_is_evaluable(status: str) -> bool:
    s = str(status or "").strip().lower()

    if not s:
        return True

    bad_tokens = [
        "inactive",
        "unavailable",
        "not_evaluated",
        "not evaluated",
        "no_observed",
        "no observed",
        "missing",
        "not_applicable",
        "not applicable",
    ]

    return not any(tok in s for tok in bad_tokens)


def recompute_overall(row: Dict[str, Any]) -> Dict[str, Any]:
    variables = [
        ("oil", "oil_hm_score", "oil_status"),
        ("water", "water_hm_score", "water_status"),
        ("gas", "gas_hm_score", "gas_status"),
        ("bhp", "bhp_hm_score", "bhp_status"),
    ]

    used = []
    skipped = []

    for name, score_col, status_col in variables:
        score = safe_float(row.get(score_col))
        status = row.get(status_col)

        if score is None:
            skipped.append(name)
            continue

        if not status_is_evaluable(status):
            skipped.append(name)
            continue

        used.append((name, score))

    if used:
        overall = round(sum(x[1] for x in used) / len(used), 2)
        row["overall_hm_score"] = overall
        row["overall_hm_class"] = score_class(overall)
    else:
        row["overall_hm_score"] = ""
        row["overall_hm_class"] = "Not Evaluated"

    row["overall_score_variables_used"] = ",".join(x[0] for x in used)
    row["overall_score_variables_skipped"] = ",".join(skipped)

    return row


def observed_bhp_available(summary, keys: List[str], well: str) -> Dict[str, Any]:
    # Standard historical BHP key.
    hist_key = find_key(keys, "WBHPH", well)

    # Common fallback used by some workflows / exports.
    fallback_key = None
    if hist_key is None:
        fallback_key = find_key(keys, "WBHPA", well)

    selected_key = hist_key or fallback_key
    vec = get_vector(summary, selected_key)

    max_bhp = max_valid(vec)
    available = selected_key is not None and max_bhp >= OBSERVED_BHP_MIN_VALID_PRESSURE

    return {
        "available": available,
        "selected_observed_bhp_key": selected_key,
        "wbhph_key": hist_key,
        "wbhpa_key": fallback_key,
        "max_observed_bhp": max_bhp,
    }


def apply_bhp_observed_filter() -> Dict[str, Any]:
    rows = read_rows(CONTEXT_CSV)

    if not rows:
        raise FileNotFoundError(f"No rows found in {CONTEXT_CSV}")

    case_path = discover_summary_case()
    summary = load_summary(case_path)
    keys = get_keys(summary)

    filtered_wells = []
    evaluated_wells = []

    for row in rows:
        well = str(row.get("well") or "").upper()

        if not well:
            continue

        bhp_info = observed_bhp_available(summary, keys, well)

        row["bhp_observed_available"] = str(bool(bhp_info["available"]))
        row["bhp_observed_key"] = bhp_info["selected_observed_bhp_key"] or ""
        row["max_observed_bhp"] = bhp_info["max_observed_bhp"]

        if not bhp_info["available"]:
            # Preserve audit.
            if row.get("bhp_hm_score") not in [None, ""]:
                row["bhp_hm_score_raw_before_observed_filter"] = row.get("bhp_hm_score")

            row["bhp_hm_score"] = ""
            row["bhp_hm_class"] = "Not Evaluated"
            row["bhp_status"] = "not_evaluated_no_observed_bhp"
            row["bhp_profile_status"] = "not_evaluated_no_observed_bhp"
            row["bhp_direction"] = "unavailable_no_observed_bhp"
            row["bhp_final_direction"] = "unavailable_no_observed_bhp"
            row["bhp_recent_2yr_direction"] = "unavailable_no_observed_bhp"

            filtered_wells.append({
                "well": well,
                **bhp_info,
            })
        else:
            # If BHP observed exists and there is a numeric score, keep it.
            if row.get("bhp_status") in [None, "", "not_evaluated_no_observed_bhp"]:
                row["bhp_status"] = "evaluated"

            evaluated_wells.append({
                "well": well,
                **bhp_info,
            })

        recompute_overall(row)

    write_rows(CONTEXT_CSV, rows)

    payload = {
        "ok": True,
        "source_summary_case": str(case_path),
        "observed_bhp_min_valid_pressure": OBSERVED_BHP_MIN_VALID_PRESSURE,
        "context_csv_updated": str(CONTEXT_CSV),
        "filtered_no_observed_bhp_count": len(filtered_wells),
        "evaluated_bhp_count": len(evaluated_wells),
        "filtered_no_observed_bhp_wells": filtered_wells,
        "evaluated_bhp_wells": evaluated_wells,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return payload


def main() -> None:
    payload = apply_bhp_observed_filter()

    print(f"[OK] Saved {OUTPUT_JSON}")
    print(f"[OK] Updated {CONTEXT_CSV}")
    print(f"BHP not evaluated due to missing observed data: {payload['filtered_no_observed_bhp_count']}")
    print(f"BHP evaluated wells: {payload['evaluated_bhp_count']}")


if __name__ == "__main__":
    main()
