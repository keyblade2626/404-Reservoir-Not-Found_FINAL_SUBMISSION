import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


MODEL_DIR = Path("data/sample_model")
CONTEXT_CSV = Path("artifacts/diagnosis/well_property_driver_context.csv")
OUTPUT_JSON = Path("artifacts/diagnosis/gas_profile_diagnostics.json")

# Breakthrough threshold:
# use max(relative threshold, absolute threshold)
GAS_BREAKTHROUGH_REL_THRESHOLD = 0.05
GAS_BREAKTHROUGH_ABS_THRESHOLD = 1e-6

GOR_BREAKTHROUGH_REL_THRESHOLD = 0.05
GOR_BREAKTHROUGH_ABS_THRESHOLD = 1e-6

TIMING_CLOSE_DAYS = 365
FINAL_CLOSE_RATIO = 0.25  # +/-25% final mismatch tolerance


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

    candidates = [
        path,
        path.with_suffix(""),
    ]

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
            if expr is None:
                keys = summary.keys()
            else:
                keys = summary.keys(expr)
            return [str(k) for k in keys]
        except Exception:
            pass

    # Fallbacks
    for attr in ["smspec_keys", "keys"]:
        try:
            obj = getattr(summary, attr)
            if callable(obj):
                keys = obj()
            else:
                keys = obj
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

    # Fallback: integer index if dates are not available
    try:
        n = len(summary.numpy_vector(get_summary_keys(summary)[0]))
    except Exception:
        n = 0

    return list(range(n))


def get_vector(summary, key: str) -> Optional[np.ndarray]:
    if key is None:
        return None

    methods = [
        "numpy_vector",
        "get_values",
        "get_vector",
    ]

    for method in methods:
        try:
            fn = getattr(summary, method)
            values = fn(key)
            arr = np.asarray(values, dtype=float)
            return arr
        except Exception:
            pass

    try:
        values = summary[key]
        arr = np.asarray(values, dtype=float)
        return arr
    except Exception:
        pass

    return None


def find_key(keys: List[str], keyword: str, well: str) -> Optional[str]:
    candidates = [
        f"{keyword}:{well}",
        f"{keyword}:{well.upper()}",
        f"{keyword}:{well.lower()}",
    ]

    key_set = {k.upper(): k for k in keys}

    for c in candidates:
        if c.upper() in key_set:
            return key_set[c.upper()]

    # More flexible fallback
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
    arr = arr[np.isfinite(arr)]
    return arr


def max_abs(values: Optional[np.ndarray]) -> float:
    arr = finite_array(values)

    if arr.size == 0:
        return 0.0

    return float(np.nanmax(np.abs(arr)))


def has_signal(values: Optional[np.ndarray], threshold: float = 1e-6) -> bool:
    return max_abs(values) > threshold


def first_breakthrough_date(
    values: Optional[np.ndarray],
    dates: List[Any],
    threshold: float,
) -> Optional[Any]:

    arr = finite_array(values)

    if arr.size == 0:
        return None

    n = min(len(arr), len(dates))

    for idx in range(n):
        if arr[idx] >= threshold:
            return dates[idx]

    return None


def days_between(a: Any, b: Any) -> Optional[int]:
    if a is None or b is None:
        return None

    try:
        return int((a - b).days)
    except Exception:
        pass

    # fallback for non-datetime numeric indices
    try:
        return int(a - b)
    except Exception:
        return None


def final_direction(
    sim: Optional[np.ndarray],
    hist: Optional[np.ndarray],
    close_ratio: float = FINAL_CLOSE_RATIO,
) -> str:

    sim_arr = finite_array(sim)
    hist_arr = finite_array(hist)

    if sim_arr.size == 0 and hist_arr.size == 0:
        return "unavailable"

    sim_signal = has_signal(sim_arr)
    hist_signal = has_signal(hist_arr)

    if not sim_signal and not hist_signal:
        return "inactive_no_signal"

    if sim_signal and not hist_signal:
        return "simulated_signal_only"

    if hist_signal and not sim_signal:
        return "historical_signal_only"

    s = float(sim_arr[-1])
    h = float(hist_arr[-1])

    scale = max(abs(s), abs(h), 1e-9)

    if abs(s - h) / scale <= close_ratio:
        return "final_value_close"

    if s > h:
        return "simulated_too_high"

    return "simulated_too_low"


def timing_issue(
    sim: Optional[np.ndarray],
    hist: Optional[np.ndarray],
    dates: List[Any],
    rel_threshold: float,
    abs_threshold: float,
) -> Dict[str, Any]:

    max_signal = max(max_abs(sim), max_abs(hist))
    threshold = max(abs_threshold, rel_threshold * max_signal)

    sim_bt = first_breakthrough_date(sim, dates, threshold)
    hist_bt = first_breakthrough_date(hist, dates, threshold)

    if sim_bt is None and hist_bt is None:
        issue = "no_breakthrough_detected"
        delta = None
    elif sim_bt is not None and hist_bt is None:
        issue = "simulated_breakthrough_only"
        delta = None
    elif sim_bt is None and hist_bt is not None:
        issue = "historical_breakthrough_only"
        delta = None
    else:
        delta = days_between(sim_bt, hist_bt)

        if delta is None:
            issue = "breakthrough_timing_unknown"
        elif delta < -TIMING_CLOSE_DAYS:
            issue = "early_breakthrough"
        elif delta > TIMING_CLOSE_DAYS:
            issue = "delayed_breakthrough"
        else:
            issue = "breakthrough_timing_close"

    return {
        "threshold": threshold,
        "sim_breakthrough_date": str(sim_bt) if sim_bt is not None else None,
        "hist_breakthrough_date": str(hist_bt) if hist_bt is not None else None,
        "breakthrough_delta_days": delta,
        "timing_issue": issue,
    }


def build_gor(sim_gas, hist_gas, sim_oil, hist_oil) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    sim_gas_arr = finite_array(sim_gas)
    hist_gas_arr = finite_array(hist_gas)
    sim_oil_arr = finite_array(sim_oil)
    hist_oil_arr = finite_array(hist_oil)

    if sim_gas_arr.size == 0 or sim_oil_arr.size == 0:
        sim_gor = None
    else:
        n = min(sim_gas_arr.size, sim_oil_arr.size)
        sim_gor = np.full(n, np.nan)
        mask = np.abs(sim_oil_arr[:n]) > 1e-9
        sim_gor[mask] = sim_gas_arr[:n][mask] / sim_oil_arr[:n][mask]

    if hist_gas_arr.size == 0 or hist_oil_arr.size == 0:
        hist_gor = None
    else:
        n = min(hist_gas_arr.size, hist_oil_arr.size)
        hist_gor = np.full(n, np.nan)
        mask = np.abs(hist_oil_arr[:n]) > 1e-9
        hist_gor[mask] = hist_gas_arr[:n][mask] / hist_oil_arr[:n][mask]

    return sim_gor, hist_gor


def diagnose_well(summary, keys: List[str], dates: List[Any], well: str) -> Dict[str, Any]:
    # Gas rate keys
    wgpr_key = find_key(keys, "WGPR", well)
    wgprh_key = find_key(keys, "WGPRH", well)

    # GOR direct keys, if present
    wgor_key = find_key(keys, "WGOR", well)
    wgorh_key = find_key(keys, "WGORH", well)

    # Oil keys for GOR fallback
    wopr_key = find_key(keys, "WOPR", well)
    woprh_key = find_key(keys, "WOPRH", well)

    sim_gas = get_vector(summary, wgpr_key) if wgpr_key else None
    hist_gas = get_vector(summary, wgprh_key) if wgprh_key else None

    sim_gor = get_vector(summary, wgor_key) if wgor_key else None
    hist_gor = get_vector(summary, wgorh_key) if wgorh_key else None

    if sim_gor is None or hist_gor is None:
        sim_oil = get_vector(summary, wopr_key) if wopr_key else None
        hist_oil = get_vector(summary, woprh_key) if woprh_key else None
        sim_gor_fb, hist_gor_fb = build_gor(sim_gas, hist_gas, sim_oil, hist_oil)

        if sim_gor is None:
            sim_gor = sim_gor_fb

        if hist_gor is None:
            hist_gor = hist_gor_fb

    gas_timing = timing_issue(
        sim=sim_gas,
        hist=hist_gas,
        dates=dates,
        rel_threshold=GAS_BREAKTHROUGH_REL_THRESHOLD,
        abs_threshold=GAS_BREAKTHROUGH_ABS_THRESHOLD,
    )

    gor_timing = timing_issue(
        sim=sim_gor,
        hist=hist_gor,
        dates=dates,
        rel_threshold=GOR_BREAKTHROUGH_REL_THRESHOLD,
        abs_threshold=GOR_BREAKTHROUGH_ABS_THRESHOLD,
    )

    gas_dir = final_direction(sim_gas, hist_gas)
    gor_dir = final_direction(sim_gor, hist_gor)

    # Prefer GOR direction if GOR has signal, otherwise gas-rate direction.
    if gor_dir not in ["unavailable", "inactive_no_signal"]:
        exported_direction = gor_dir
        exported_timing = gor_timing["timing_issue"]
        exported_sim_bt = gor_timing["sim_breakthrough_date"]
        exported_hist_bt = gor_timing["hist_breakthrough_date"]
        exported_delta = gor_timing["breakthrough_delta_days"]
        exported_basis = "GOR"
    else:
        exported_direction = gas_dir
        exported_timing = gas_timing["timing_issue"]
        exported_sim_bt = gas_timing["sim_breakthrough_date"]
        exported_hist_bt = gas_timing["hist_breakthrough_date"]
        exported_delta = gas_timing["breakthrough_delta_days"]
        exported_basis = "WGPR"

    return {
        "well": well,

        "gas_profile_basis": exported_basis,
        "gas_direction": exported_direction,
        "gas_timing_issue": exported_timing,
        "gas_breakthrough_delta_days": exported_delta,
        "sim_gas_breakthrough_date": exported_sim_bt,
        "hist_gas_breakthrough_date": exported_hist_bt,

        "wgpr_key": wgpr_key,
        "wgprh_key": wgprh_key,
        "wgor_key": wgor_key,
        "wgorh_key": wgorh_key,

        "gas_rate_direction": gas_dir,
        "gas_rate_timing_issue": gas_timing["timing_issue"],
        "gas_rate_breakthrough_delta_days": gas_timing["breakthrough_delta_days"],
        "sim_gas_rate_breakthrough_date": gas_timing["sim_breakthrough_date"],
        "hist_gas_rate_breakthrough_date": gas_timing["hist_breakthrough_date"],

        "gor_direction": gor_dir,
        "gor_timing_issue": gor_timing["timing_issue"],
        "gor_breakthrough_delta_days": gor_timing["breakthrough_delta_days"],
        "sim_gor_breakthrough_date": gor_timing["sim_breakthrough_date"],
        "hist_gor_breakthrough_date": gor_timing["hist_breakthrough_date"],

        "gas_max_sim_signal": max_abs(sim_gas),
        "gas_max_hist_signal": max_abs(hist_gas),
        "gor_max_sim_signal": max_abs(sim_gor),
        "gor_max_hist_signal": max_abs(hist_gor),
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

    # Update context CSV in place.
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
    print("Gas/GOR profile diagnostics exported to well_property_driver_context.csv")


if __name__ == "__main__":
    main()
