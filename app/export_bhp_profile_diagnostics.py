import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


MODEL_DIR = Path("data/sample_model")
CONTEXT_CSV = Path("artifacts/diagnosis/well_property_driver_context.csv")
OUTPUT_JSON = Path("artifacts/diagnosis/bhp_profile_diagnostics.json")

FINAL_CLOSE_RATIO = 0.05      # 5% final pressure difference = close
MEAN_CLOSE_RATIO = 0.05       # 5% mean bias = close
RECENT_DAYS = 730             # last 2 years


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


def recent_mask_from_dates(dates: List[Any], n: int) -> np.ndarray:
    if n <= 0:
        return np.asarray([], dtype=bool)

    if not dates or len(dates) < n:
        # fallback: last 24 points
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

    # fallback: last 24 points
    mask = np.zeros(n, dtype=bool)
    mask[max(0, n - 24):] = True
    return mask


def classify_delta(delta: Optional[float], scale: Optional[float], close_ratio: float) -> str:
    if delta is None or scale is None or scale <= 0:
        return "unavailable"

    if abs(delta) / scale <= close_ratio:
        return "final_value_close"

    if delta > 0:
        # sim - hist > 0
        return "simulated_pressure_too_high"

    return "simulated_pressure_too_low"


def compute_bias(sim: np.ndarray, hist: np.ndarray) -> Dict[str, Any]:
    if sim.size == 0 or hist.size == 0:
        return {
            "mean_delta": None,
            "mean_abs_delta": None,
            "mean_bias_pct": None,
            "direction": "unavailable",
        }

    delta = sim - hist
    scale = max(float(np.nanmean(np.abs(hist))), 1e-9)

    mean_delta = float(np.nanmean(delta))
    mean_abs_delta = float(np.nanmean(np.abs(delta)))
    mean_bias_pct = float(mean_delta / scale * 100.0)

    if abs(mean_delta) / scale <= MEAN_CLOSE_RATIO:
        direction = "profile_bias_close"
    elif mean_delta > 0:
        direction = "simulated_pressure_too_high"
    else:
        direction = "simulated_pressure_too_low"

    return {
        "mean_delta": mean_delta,
        "mean_abs_delta": mean_abs_delta,
        "mean_bias_pct": mean_bias_pct,
        "direction": direction,
    }


def diagnose_well(summary, keys: List[str], dates: List[Any], well: str) -> Dict[str, Any]:
    # Main expected keywords.
    sim_key = find_key(keys, "WBHP", well)
    hist_key = find_key(keys, "WBHPH", well)

    # Fallbacks sometimes used in exported summary cases.
    if hist_key is None:
        hist_key = find_key(keys, "WBHPA", well)

    sim_bhp = get_vector(summary, sim_key)
    hist_bhp = get_vector(summary, hist_key)

    sim_pair, hist_pair = finite_pair(sim_bhp, hist_bhp)

    has_sim = sim_bhp is not None and np.asarray(sim_bhp).size > 0 and np.any(np.isfinite(sim_bhp))
    has_hist = hist_bhp is not None and np.asarray(hist_bhp).size > 0 and np.any(np.isfinite(hist_bhp))

    if not has_sim and not has_hist:
        status = "unavailable"
    elif has_sim and not has_hist:
        status = "simulated_only_no_observed_bhp"
    elif has_hist and not has_sim:
        status = "observed_only_no_simulated_bhp"
    else:
        status = "evaluated"

    if sim_pair.size == 0 or hist_pair.size == 0:
        sim_final = None
        hist_final = None
        final_delta = None
        final_delta_pct = None
        final_direction = "unavailable"
        full_bias = compute_bias(sim_pair, hist_pair)
        recent_bias = full_bias
    else:
        sim_final = float(sim_pair[-1])
        hist_final = float(hist_pair[-1])
        final_delta = sim_final - hist_final
        scale = max(abs(hist_final), abs(sim_final), 1e-9)
        final_delta_pct = final_delta / scale * 100.0
        final_direction = classify_delta(final_delta, scale, FINAL_CLOSE_RATIO)

        full_bias = compute_bias(sim_pair, hist_pair)

        n = min(len(sim_bhp), len(hist_bhp)) if sim_bhp is not None and hist_bhp is not None else sim_pair.size
        raw_sim = np.asarray(sim_bhp[:n], dtype=float)
        raw_hist = np.asarray(hist_bhp[:n], dtype=float)
        valid = np.isfinite(raw_sim) & np.isfinite(raw_hist)
        recent_mask = recent_mask_from_dates(dates, n) & valid

        if np.any(recent_mask):
            recent_bias = compute_bias(raw_sim[recent_mask], raw_hist[recent_mask])
        else:
            recent_bias = full_bias

    # Exported main direction:
    # use final direction first because pressure HM decisions often care about end-history pressure,
    # but keep full/recent bias as supporting fields.
    if final_direction != "final_value_close" and final_direction != "unavailable":
        bhp_direction = final_direction
    elif recent_bias["direction"] not in ["profile_bias_close", "unavailable"]:
        bhp_direction = recent_bias["direction"]
    else:
        bhp_direction = final_direction

    return {
        "well": well,
        "bhp_profile_status": status,
        "bhp_sim_key": sim_key,
        "bhp_hist_key": hist_key,

        "bhp_direction": bhp_direction,
        "bhp_final_direction": final_direction,
        "bhp_full_profile_direction": full_bias["direction"],
        "bhp_recent_2yr_direction": recent_bias["direction"],

        "sim_bhp_final": sim_final,
        "hist_bhp_final": hist_final,
        "bhp_final_delta": final_delta,
        "bhp_final_delta_pct": final_delta_pct,

        "bhp_mean_delta_full": full_bias["mean_delta"],
        "bhp_mean_abs_delta_full": full_bias["mean_abs_delta"],
        "bhp_mean_bias_pct_full": full_bias["mean_bias_pct"],

        "bhp_mean_delta_recent_2yr": recent_bias["mean_delta"],
        "bhp_mean_abs_delta_recent_2yr": recent_bias["mean_abs_delta"],
        "bhp_mean_bias_pct_recent_2yr": recent_bias["mean_bias_pct"],
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
    print("BHP profile diagnostics exported to well_property_driver_context.csv")


if __name__ == "__main__":
    main()
