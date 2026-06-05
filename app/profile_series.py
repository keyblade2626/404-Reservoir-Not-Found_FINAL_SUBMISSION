import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data" / "sample_model"


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


def get_dates(summary, n: int) -> List[str]:
    for attr in ["dates", "report_dates"]:
        try:
            obj = getattr(summary, attr)
            dates = obj() if callable(obj) else obj
            dates = list(dates)
            if len(dates) >= n:
                return [str(d) for d in dates[:n]]
        except Exception:
            pass

    return [str(i) for i in range(n)]


def find_key(keys: List[str], keyword: str, well: str) -> Optional[str]:
    key_map = {k.upper(): k for k in keys}

    candidates = [
        f"{keyword}:{well}",
        f"{keyword}:{well.upper()}",
        f"{keyword}:{well.lower()}",
    ]

    for c in candidates:
        if c.upper() in key_map:
            return key_map[c.upper()]

    prefix = f"{keyword}:".upper()
    target = well.upper()

    for k in keys:
        ku = k.upper()
        if ku.startswith(prefix) and ku.split(":", 1)[-1].upper() == target:
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


def clean_series(values: Optional[np.ndarray], n: int) -> List[Optional[float]]:
    if values is None:
        return []

    arr = np.asarray(values[:n], dtype=float)
    out = []

    for v in arr:
        if np.isfinite(v):
            out.append(float(v))
        else:
            out.append(None)

    return out


def compute_wct(oil, water) -> Optional[np.ndarray]:
    if oil is None or water is None:
        return None

    n = min(len(oil), len(water))

    if n == 0:
        return None

    oil = np.asarray(oil[:n], dtype=float)
    water = np.asarray(water[:n], dtype=float)
    liquid = oil + water

    wct = np.full(n, np.nan)
    mask = np.isfinite(liquid) & (np.abs(liquid) > 1e-9)
    wct[mask] = water[mask] / liquid[mask]

    return wct


def variable_config(variable: str) -> Dict[str, Any]:
    v = str(variable or "").lower().strip()

    # V377: strict and explicit variable mapping.
    # Do not let oil_rate / gas_rate fall back to water by mistake.

    if v in ["oil", "oil_rate", "opr", "wopr", "wopt", "oil production", "oil_profile"]:
        return {
            "variable": "oil_rate",
            "title": "Oil Match",
            "sim_key": "WOPR",
            "hist_key": "WOPRH",
            "unit": "STB/d",
            "label": "Oil Rate",
        }

    if v in ["water", "water_rate", "wwpr", "wwpt", "water production", "water_profile"]:
        return {
            "variable": "water_rate",
            "title": "Water Match",
            "sim_key": "WWPR",
            "hist_key": "WWPRH",
            "unit": "STB/d",
            "label": "Water Rate",
        }

    if v in ["gas", "gas_rate", "wgpr", "wgpt", "gas production", "gas_profile"]:
        return {
            "variable": "gas_rate",
            "title": "Gas Match",
            "sim_key": "WGPR",
            "hist_key": "WGPRH",
            "unit": "MSCF/d",
            "label": "Gas Rate",
        }

    if v in ["water_cut", "watercut", "wct", "wwct"]:
        return {
            "variable": "water_cut",
            "title": "Water Cut Match",
            "sim_key": "WWCT",
            "hist_key": "WWCTH",
            "unit": "fraction",
            "label": "Water Cut",
        }

    if v in ["gor", "wgor", "gas_oil_ratio", "gas oil ratio", "gas-oil ratio"]:
        return {
            "variable": "gor",
            "title": "GOR Match",
            "sim_key": "WGOR",
            "hist_key": "WGORH",
            "unit": "MSCF/STB",
            "label": "Gas-Oil Ratio",
        }

    if v in ["bhp", "pressure", "wbhp", "fpr", "pressure_profile"]:
        return {
            "variable": "bhp",
            "title": "BHP Match",
            "sim_key": "WBHP",
            "hist_key": "WBHPH",
            "unit": "psia",
            "label": "BHP",
        }

    # Safer than silently returning water and creating wrong plots.
    raise ValueError(f"Unsupported profile variable: {variable}")


def get_profile_series(well: str, variable: str = "water") -> Dict[str, Any]:
    well = well.upper()
    cfg = variable_config(variable)

    try:
        case_path = discover_summary_case()
        summary = load_summary(case_path)
        keys = get_keys(summary)

        sim_key = find_key(keys, cfg["sim_key"], well)
        hist_key = find_key(keys, cfg["hist_key"], well)

        if cfg["variable"] == "bhp" and hist_key is None:
            hist_key = find_key(keys, "WBHPA", well)

        sim = get_vector(summary, sim_key)
        hist = get_vector(summary, hist_key)

        if sim is None or hist is None:
            return {
                "ok": False,
                "well": well,
                "variable": cfg["variable"],
                "message": "Missing simulated or observed vector.",
                "sim_key": sim_key,
                "hist_key": hist_key,
                "panels": [],
            }

        n = min(len(sim), len(hist))
        x = get_dates(summary, n)

        panels = [
            {
                "title": cfg["label"],
                "y_title": f"{cfg['label']} ({cfg['unit']})",
                "traces": [
                    {
                        "name": "Observed",
                        "x": x,
                        "y": clean_series(hist, n),
                        "mode": "lines",
                        "dash": "solid",
                    },
                    {
                        "name": "Simulated",
                        "x": x,
                        "y": clean_series(sim, n),
                        "mode": "lines",
                        "dash": "dash",
                    },
                ],
            }
        ]

        if cfg["variable"] == "water":
            wopr = get_vector(summary, find_key(keys, "WOPR", well))
            woprh = get_vector(summary, find_key(keys, "WOPRH", well))

            sim_wct = compute_wct(wopr, sim)
            hist_wct = compute_wct(woprh, hist)

            if sim_wct is not None and hist_wct is not None:
                n2 = min(len(sim_wct), len(hist_wct), len(x))
                panels.append({
                    "title": "Water Cut",
                    "y_title": "Water cut fraction",
                    "traces": [
                        {
                            "name": "Observed WCT",
                            "x": x[:n2],
                            "y": clean_series(hist_wct, n2),
                            "mode": "lines",
                            "dash": "solid",
                        },
                        {
                            "name": "Simulated WCT",
                            "x": x[:n2],
                            "y": clean_series(sim_wct, n2),
                            "mode": "lines",
                            "dash": "dash",
                        },
                    ],
                })

        return {
            "ok": True,
            "well": well,
            "variable": cfg["variable"],
            "title": f"{well} - {cfg['title']}",
            "sim_key": sim_key,
            "hist_key": hist_key,
            "panels": panels,
        }

    except Exception as exc:
        return {
            "ok": False,
            "well": well,
            "variable": cfg["variable"],
            "message": str(exc),
            "panels": [],
        }


if __name__ == "__main__":
    print(get_profile_series("HW-6", "water"))
