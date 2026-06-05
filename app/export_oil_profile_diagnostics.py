import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


MODEL_DIR = Path("data/sample_model")
CONTEXT_CSV = Path("artifacts/diagnosis/well_property_driver_context.csv")
OUTPUT_JSON = Path("artifacts/diagnosis/oil_profile_diagnostics.json")

ACTIVE_OIL_THRESHOLD = 1e-6
TIMING_CLOSE_DAYS = 365
FINAL_CLOSE_RATIO = 0.10
MEAN_CLOSE_RATIO = 0.10
RECENT_DAYS = 730


def to_float(value: Any) -> Optional[float]:
    if value in [None, "", "None", "null", "N/A"]:
        return None
    try:
        return float(value)
    except Exception:
        return None


def read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")

    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv_rows(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return

    fieldnames = []
    seen = set()

    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Updated {path}")


def discover_summary_case() -> Path:
    smspec_files = sorted(MODEL_DIR.glob("*.SMSPEC")) + sorted(MODEL_DIR.glob("*.smspec"))
    unsmry_files = sorted(MODEL_DIR.glob("*.UNSMRY")) + sorted(MODEL_DIR.glob("*.unsmry"))

    if smspec_files:
        return smspec_files[0]

    if unsmry_files:
        return unsmry_files[0]

    raise FileNotFoundError(f"No SMSPEC/UNSMRY found in {MODEL_DIR}")


def load_summary(path: Path):
    try:
        from resdata.summary import Summary
    except Exception as exc:
        raise ImportError(
            "Cannot import resdata.summary.Summary. Install/activate resdata first."
        ) from exc

    candidates = [path, path.with_suffix("")]
    last_error = None

    for candidate in candidates:
        try:
            return Summary(str(candidate))
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"Could not open summary case from {path}. Last error: {last_error}")


def get_summary_keys(summary) -> List[str]:
    for expr in ["*", None]:
        try:
            keys = summary.keys(expr) if expr is not None else summary.keys()
            return [str(k) for k in keys]
        except Exception:
            pass

    raise RuntimeError("Could not retrieve summary keys.")


def get_dates(summary) -> List[Any]:
    for attr in ["dates", "report_dates"]:
        try:
            obj = getattr(summary, attr)
            dates = obj() if callable(obj) else obj
            return list(dates)
        except Exception:
            pass

    try:
        n = len(summary.numpy_vector(get_summary_keys(summary)[0]))
    except Exception:
        n = 0

    return list(range(n))


def get_vector(summary, key: Optional[str]) -> Optional[np.ndarray]:
    if not key:
        return None

    for method in ["numpy_vector", "get_values", "get_vector"]:
        try:
            fn = getattr(summary, method)
            values = fn(key)
            return np.asarray(values, dtype=float)
        except Exception:
            pass

    try:
        return np.asarray(summary[key], dtype=float)
    except Exception:
        return None


def find_key(keys: List[str], keyword: str, well: str) -> Optional[str]:
    key_set = {k.upper(): k for k in keys}

    candidates = [
        f"{keyword}:{well}",
        f"{keyword}:{well.upper()}",
        f"{keyword}:{well.lower()}",
    ]

    for c in candidates:
        if c.upper() in key_set:
            return key_set[c.upper()]

    target_prefix = f"{keyword}:".upper()
    target_well = well.upper()

    for k in keys:
        ku = k.upper()
        if ku.startswith(target_prefix) and ku.split(":", 1)[-1].upper() == target_well:
            return k

    return None


def finite_array(values: Optional[np.ndarray]) -> np.ndarray:
    if values is None:
        return np.asarray([], dtype=float)

    arr = np.asarray(values, dtype=float)
    return arr[np.isfinite(arr)]


def finite_pair(sim: Optional[np.ndarray], hist: Optional[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    if sim is None or hist is None:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)

    s = np.asarray(sim, dtype=float)
    h = np.asarray(hist, dtype=float)

    n = min(len(s), len(h))
    s = s[:n]
    h = h[:n]

    mask = np.isfinite(s) & np.isfinite(h)
    return s[mask], h[mask]


def has_signal(values: Optional[np.ndarray], threshold: float = ACTIVE_OIL_THRESHOLD) -> bool:
    arr = finite_array(values)

    if arr.size == 0:
        return False

    return bool(np.nanmax(np.abs(arr)) > threshold)


def first_active_date(values: Optional[np.ndarray], dates: List[Any], threshold: float = ACTIVE_OIL_THRESHOLD) -> Optional[Any]:
    arr = finite_array(values)

    if arr.size == 0:
        return None

    n = min(len(arr), len(dates))

    for idx in range(n):
        if abs(arr[idx]) > threshold:
            return dates[idx]

    return None


def days_between(a: Any, b: Any) -> Optional[int]:
    if a is None or b is None:
        return None

    try:
        return int((a - b).days)
    except Exception:
        pass

    try:
        return int(a - b)
    except Exception:
        return None


def classify_active_timing(sim: Optional[np.ndarray], hist: Optional[np.ndarray], dates: List[Any]) -> Dict[str, Any]:
    sim_start = first_active_date(sim, dates)
    hist_start = first_active_date(hist, dates)

    if sim_start is None and hist_start is None:
        issue = "no_active_oil_profile"
        delta = None
    elif sim_start is not None and hist_start is None:
        issue = "simulated_oil_profile_only"
        delta = None
    elif sim_start is None and hist_start is not None:
        issue = "historical_oil_profile_only"
        delta = None
    else:
        delta = days_between(sim_start, hist_start)

        if delta is None:
            issue = "oil_start_timing_unknown"
        elif delta < -TIMING_CLOSE_DAYS:
            issue = "simulated_oil_starts_early"
        elif delta > TIMING_CLOSE_DAYS:
            issue = "simulated_oil_starts_late"
        else:
            issue = "oil_start_timing_close"

    return {
        "sim_oil_active_start_date": str(sim_start) if sim_start is not None else None,
        "hist_oil_active_start_date": str(hist_start) if hist_start is not None else None,
        "oil_active_start_delta_days": delta,
        "oil_timing_issue": issue,
    }


def final_direction(sim: Optional[np.ndarray], hist: Optional[np.ndarray], close_ratio: float = FINAL_CLOSE_RATIO) -> Dict[str, Any]:
    sim_arr = finite_array(sim)
    hist_arr = finite_array(hist)

    if sim_arr.size == 0 and hist_arr.size == 0:
        return {
            "direction": "unavailable",
            "sim_final": None,
            "hist_final": None,
            "final_delta": None,
            "final_delta_pct": None,
        }

    sim_signal = has_signal(sim_arr)
    hist_signal = has_signal(hist_arr)

    if not sim_signal and not hist_signal:
        return {
            "direction": "inactive_no_signal",
            "sim_final": float(sim_arr[-1]) if sim_arr.size else None,
            "hist_final": float(hist_arr[-1]) if hist_arr.size else None,
            "final_delta": None,
            "final_delta_pct": None,
        }

    if sim_signal and not hist_signal:
        return {
            "direction": "simulated_signal_only",
            "sim_final": float(sim_arr[-1]) if sim_arr.size else None,
            "hist_final": float(hist_arr[-1]) if hist_arr.size else None,
            "final_delta": None,
            "final_delta_pct": None,
        }

    if hist_signal and not sim_signal:
        return {
            "direction": "historical_signal_only",
            "sim_final": float(sim_arr[-1]) if sim_arr.size else None,
            "hist_final": float(hist_arr[-1]) if hist_arr.size else None,
            "final_delta": None,
            "final_delta_pct": None,
        }

    s = float(sim_arr[-1])
    h = float(hist_arr[-1])
    delta = s - h
    scale = max(abs(s), abs(h), 1e-9)
    delta_pct = delta / scale * 100.0

    if abs(delta) / scale <= close_ratio:
        direction = "final_value_close"
    elif delta > 0:
        direction = "simulated_oil_too_high"
    else:
        direction = "simulated_oil_too_low"

    return {
        "direction": direction,
        "sim_final": s,
        "hist_final": h,
        "final_delta": delta,
        "final_delta_pct": delta_pct,
    }


def recent_mask_from_dates(dates: List[Any], n: int) -> np.ndarray:
    if n <= 0:
        return np.asarray([], dtype=bool)

    if not dates or len(dates) < n:
        mask = np.zeros(n, dtype=bool)
        mask[max(0, n - 24):] = True
        return mask

    dd = dates[:n]

    try:
        end = dd[-1]
        mask = np.asarray([(end - d).days <= RECENT_DAYS for d in dd], dtype=bool)

        if np.any(mask):
            return mask
    except Exception:
        pass

    mask = np.zeros(n, dtype=bool)
    mask[max(0, n - 24):] = True
    return mask


def compute_bias(sim: Optional[np.ndarray], hist: Optional[np.ndarray], dates: List[Any]) -> Dict[str, Any]:
    if sim is None or hist is None:
        return {
            "oil_rate_mean_delta_full": None,
            "oil_rate_mean_bias_pct_full": None,
            "oil_rate_mean_delta_recent_2yr": None,
            "oil_rate_mean_bias_pct_recent_2yr": None,
            "oil_rate_recent_direction": "unavailable",
        }

    n = min(len(sim), len(hist))
    s = np.asarray(sim[:n], dtype=float)
    h = np.asarray(hist[:n], dtype=float)

    valid = np.isfinite(s) & np.isfinite(h)
    s_valid = s[valid]
    h_valid = h[valid]

    if s_valid.size == 0:
        return {
            "oil_rate_mean_delta_full": None,
            "oil_rate_mean_bias_pct_full": None,
            "oil_rate_mean_delta_recent_2yr": None,
            "oil_rate_mean_bias_pct_recent_2yr": None,
            "oil_rate_recent_direction": "unavailable",
        }

    delta = s_valid - h_valid
    scale = max(float(np.nanmean(np.abs(h_valid))), float(np.nanmean(np.abs(s_valid))), 1e-9)

    mean_delta_full = float(np.nanmean(delta))
    mean_bias_pct_full = mean_delta_full / scale * 100.0

    mask_recent_raw = recent_mask_from_dates(dates, n)
    valid_recent = mask_recent_raw & valid

    if np.any(valid_recent):
        sr = s[valid_recent]
        hr = h[valid_recent]
        dr = sr - hr
        scale_r = max(float(np.nanmean(np.abs(hr))), float(np.nanmean(np.abs(sr))), 1e-9)
        mean_delta_recent = float(np.nanmean(dr))
        mean_bias_pct_recent = mean_delta_recent / scale_r * 100.0
    else:
        mean_delta_recent = mean_delta_full
        mean_bias_pct_recent = mean_bias_pct_full

    if abs(mean_bias_pct_recent) <= MEAN_CLOSE_RATIO * 100.0:
        recent_direction = "profile_bias_close"
    elif mean_bias_pct_recent > 0:
        recent_direction = "simulated_oil_too_high"
    else:
        recent_direction = "simulated_oil_too_low"

    return {
        "oil_rate_mean_delta_full": mean_delta_full,
        "oil_rate_mean_bias_pct_full": mean_bias_pct_full,
        "oil_rate_mean_delta_recent_2yr": mean_delta_recent,
        "oil_rate_mean_bias_pct_recent_2yr": mean_bias_pct_recent,
        "oil_rate_recent_direction": recent_direction,
    }


def diagnose_well(summary, keys: List[str], dates: List[Any], well: str) -> Dict[str, Any]:
    wopr_key = find_key(keys, "WOPR", well)
    woprh_key = find_key(keys, "WOPRH", well)

    wopt_key = find_key(keys, "WOPT", well)
    wopth_key = find_key(keys, "WOPTH", well)

    sim_oil_rate = get_vector(summary, wopr_key)
    hist_oil_rate = get_vector(summary, woprh_key)

    sim_oil_cum = get_vector(summary, wopt_key)
    hist_oil_cum = get_vector(summary, wopth_key)

    rate_dir = final_direction(sim_oil_rate, hist_oil_rate)
    cum_dir = final_direction(sim_oil_cum, hist_oil_cum)
    timing = classify_active_timing(sim_oil_rate, hist_oil_rate, dates)
    bias = compute_bias(sim_oil_rate, hist_oil_rate, dates)

    has_sim_oil = has_signal(sim_oil_rate) or has_signal(sim_oil_cum)
    has_hist_oil = has_signal(hist_oil_rate) or has_signal(hist_oil_cum)

    if not has_sim_oil and not has_hist_oil:
        activity_status = "inactive_no_oil_profile"
        hm_evaluable = False
    elif has_hist_oil and not has_sim_oil:
        activity_status = "observed_active_simulated_inactive"
        hm_evaluable = True
    elif has_sim_oil and not has_hist_oil:
        activity_status = "simulated_active_no_observed_oil_profile"
        hm_evaluable = False
    else:
        activity_status = "active_oil_profile"
        hm_evaluable = True

    # Main exported direction:
    # recent bias is usually more useful than final rate if rates are noisy.
    if bias["oil_rate_recent_direction"] not in ["profile_bias_close", "unavailable"]:
        oil_direction = bias["oil_rate_recent_direction"]
        oil_profile_basis = "recent_2yr_rate_bias"
    elif rate_dir["direction"] not in ["final_value_close", "unavailable", "inactive_no_signal"]:
        oil_direction = rate_dir["direction"]
        oil_profile_basis = "final_rate"
    elif cum_dir["direction"] not in ["final_value_close", "unavailable", "inactive_no_signal"]:
        oil_direction = cum_dir["direction"]
        oil_profile_basis = "final_cumulative"
    else:
        oil_direction = rate_dir["direction"]
        oil_profile_basis = "final_rate"

    return {
        "well": well,
        "oil_profile_basis": oil_profile_basis,
        "producer_activity_status": activity_status,
        "hm_evaluable": hm_evaluable,

        "oil_direction": oil_direction,
        "oil_rate_direction": rate_dir["direction"],
        "oil_cum_direction": cum_dir["direction"],
        "oil_rate_recent_direction": bias["oil_rate_recent_direction"],
        "oil_timing_issue": timing["oil_timing_issue"],

        "sim_oil_active_start_date": timing["sim_oil_active_start_date"],
        "hist_oil_active_start_date": timing["hist_oil_active_start_date"],
        "oil_active_start_delta_days": timing["oil_active_start_delta_days"],

        "sim_oil_final_rate": rate_dir["sim_final"],
        "hist_oil_final_rate": rate_dir["hist_final"],
        "oil_rate_final_delta": rate_dir["final_delta"],
        "oil_rate_final_delta_pct": rate_dir["final_delta_pct"],

        "sim_oil_final_cum": cum_dir["sim_final"],
        "hist_oil_final_cum": cum_dir["hist_final"],
        "oil_cum_final_delta": cum_dir["final_delta"],
        "oil_cum_final_delta_pct": cum_dir["final_delta_pct"],

        **bias,

        "wopr_key": wopr_key,
        "woprh_key": woprh_key,
        "wopt_key": wopt_key,
        "wopth_key": wopth_key,
    }


def main() -> None:
    rows = read_csv_rows(CONTEXT_CSV)
    wells = [r["well"] for r in rows if r.get("well")]

    case_path = discover_summary_case()
    print(f"Reading summary case: {case_path}")

    summary = load_summary(case_path)
    keys = get_summary_keys(summary)
    dates = get_dates(summary)

    diagnostics_by_well = {}

    for well in wells:
        diagnostics_by_well[well] = diagnose_well(summary, keys, dates, well)

    for row in rows:
        well = row.get("well")
        diag = diagnostics_by_well.get(well, {})

        for key, value in diag.items():
            if key == "well":
                continue
            row[key] = value

    write_csv_rows(CONTEXT_CSV, rows)

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps({
        "source_summary_case": str(case_path),
        "well_count": len(diagnostics_by_well),
        "diagnostics": list(diagnostics_by_well.values()),
    }, indent=2), encoding="utf-8")

    print(f"[OK] Saved {OUTPUT_JSON}")
    print("Oil profile diagnostics exported to well_property_driver_context.csv")


if __name__ == "__main__":
    main()
