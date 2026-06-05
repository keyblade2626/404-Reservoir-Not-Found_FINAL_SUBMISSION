from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional


VARIABLE_DEFINITIONS = {
    "oil": {
        "tokens": ["oil", "wopr", "wopt", "fopr", "fopt"],
        "bad_tokens": ["score", "percentile", "rank", "class", "flag", "direction", "bias", "hm"],
    },
    "water": {
        "tokens": ["water", "wct", "wwct", "wwpr", "wwpt", "fwct", "fwpr", "fwpt"],
        "bad_tokens": ["score", "percentile", "rank", "class", "flag", "direction", "bias", "hm"],
    },
    "gas": {
        "tokens": ["gas", "gor", "wgor", "wgpr", "wgpt", "fgor", "fgpr", "fgpt"],
        "bad_tokens": ["score", "percentile", "rank", "class", "flag", "direction", "bias", "hm"],
    },
    "pressure": {
        "tokens": ["pressure", "bhp", "wbhp", "fpr"],
        "bad_tokens": ["score", "percentile", "rank", "class", "flag", "direction", "bias", "hm"],
    },
}


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        if isinstance(v, str):
            s = v.strip().replace(",", "")
            if s == "" or s.lower() in {"nan", "none", "null", "n/a"}:
                return None
            return float(s)
        return float(v)
    except Exception:
        return None


def _row_well(row: dict[str, Any]) -> str:
    for k in ["well", "well_name", "name", "wellName", "WELL", "WELL_NAME"]:
        if k in row and str(row.get(k) or "").strip():
            return str(row.get(k)).strip().upper()
    return ""


def _is_sim_key(k: str) -> bool:
    lk = str(k).lower()
    return any(x in lk for x in ["sim", "simulated", "simulation", "model", "calc", "pred", "forecast"])


def _is_obs_key(k: str) -> bool:
    lk = str(k).lower()
    return any(x in lk for x in ["obs", "observed", "history", "hist", "actual", "measured"])


def _is_variable_key(k: str, variable: str) -> bool:
    lk = str(k).lower()
    cfg = VARIABLE_DEFINITIONS[variable]
    if any(x in lk for x in cfg["bad_tokens"]):
        return False
    return any(x in lk for x in cfg["tokens"])


def _extract_pair(row: dict[str, Any], variable: str):
    sim_vals = []
    obs_vals = []

    for k, v in row.items():
        if not _is_variable_key(k, variable):
            continue

        val = _safe_float(v)
        if val is None:
            continue

        if _is_sim_key(k):
            sim_vals.append((k, val))
        elif _is_obs_key(k):
            obs_vals.append((k, val))

    if sim_vals and obs_vals:
        sk, sv = sim_vals[-1]
        ok, ov = obs_vals[-1]
        return sv, ov, f"{sk} vs {ok}"

    # Fallback for files already scoped to a variable profile.
    keys = {str(k).lower(): k for k in row.keys()}

    sim_key = None
    obs_key = None

    for c in ["sim", "simulated", "simulation", "model", "forecast", "calculated"]:
        if c in keys:
            sim_key = keys[c]
            break

    for c in ["obs", "observed", "history", "hist", "actual", "measured"]:
        if c in keys:
            obs_key = keys[c]
            break

    if sim_key and obs_key:
        sv = _safe_float(row.get(sim_key))
        ov = _safe_float(row.get(obs_key))
        if sv is not None and ov is not None:
            return sv, ov, f"{sim_key} vs {obs_key}"

    return None


def _walk_json(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_json(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from _walk_json(x)


def collect_variable_pairs(variable: str, root: Optional[Path] = None) -> list[dict[str, Any]]:
    variable = variable.lower().strip()
    if variable not in VARIABLE_DEFINITIONS:
        raise ValueError(f"Unsupported variable: {variable}")

    root = root or Path(__file__).resolve().parents[1]
    artifacts = root / "artifacts"

    records = []

    if not artifacts.exists():
        return records

    file_tokens = VARIABLE_DEFINITIONS[variable]["tokens"] + [
        "profile", "summary", "well", "dashboard", "diagnosis", "hm", "history"
    ]

    for ext in ["*.json", "*.csv"]:
        for p in artifacts.rglob(ext):
            if not p.is_file():
                continue

            try:
                if p.stat().st_size > 50_000_000:
                    continue
            except Exception:
                continue

            ps = str(p).lower()

            # V347: exclude diagnostic/flag summaries that are not actual profile time-series.
            # These files can contain columns such as water_max_sim_signal vs water_max_hist_signal,
            # which are not the plotted sim-vs-observed production profiles.
            excluded_summary_sources = [
                "injection_hm_summary",
                "summary_signal",
                "max_sim_signal",
                "max_hist_signal",
                "diagnostic_summary",
            ]

            if any(x in ps for x in excluded_summary_sources):
                continue

            if not any(x in ps for x in file_tokens):
                continue

            if p.suffix.lower() == ".json":
                try:
                    data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
                except Exception:
                    continue

                for row in _walk_json(data):
                    if not isinstance(row, dict):
                        continue

                    well = _row_well(row)
                    pair = _extract_pair(row, variable)

                    if well and pair:
                        sim, obs, source = pair
                        records.append({
                            "well": well,
                            "variable": variable,
                            "sim": sim,
                            "obs": obs,
                            "diff": sim - obs,
                            "source_file": str(p.relative_to(root)),
                            "source_keys": source,
                        })

            elif p.suffix.lower() == ".csv":
                try:
                    with p.open("r", encoding="utf-8", errors="ignore", newline="") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            well = _row_well(row)
                            pair = _extract_pair(row, variable)

                            if well and pair:
                                sim, obs, source = pair
                                records.append({
                                    "well": well,
                                    "variable": variable,
                                    "sim": sim,
                                    "obs": obs,
                                    "diff": sim - obs,
                                    "source_file": str(p.relative_to(root)),
                                    "source_keys": source,
                                })
                except Exception:
                    continue

    return records


def summarize_variable_bias(variable: str, root: Optional[Path] = None, threshold: float = 0.05) -> list[dict[str, Any]]:
    records = collect_variable_pairs(variable, root=root)

    by_well = defaultdict(list)
    for r in records:
        by_well[r["well"]].append(r)

    summary = []

    for well, rows in sorted(by_well.items()):
        n = len(rows)
        tail_n = max(3, int(n * 0.30)) if n >= 3 else n
        tail = rows[-tail_n:]

        sim_mean = sum(r["sim"] for r in tail) / len(tail)
        obs_mean = sum(r["obs"] for r in tail) / len(tail)
        diff_mean = sim_mean - obs_mean

        denom = max(abs(sim_mean), abs(obs_mean), 1e-9)
        rel_bias = diff_mean / denom

        # V347: require enough real profile points before assigning over/under-estimation.
        # A true profile should have several time points. If we only have a few summary records,
        # return unknown rather than a misleading "balanced" or "no wells".
        if n < 6:
            direction = "unknown_insufficient_profile_points"
        elif rel_bias > threshold:
            direction = f"overestimated_{variable}"
        elif rel_bias < -threshold:
            direction = f"underestimated_{variable}"
        else:
            direction = "balanced_or_timing_issue"

        summary.append({
            "well": well,
            "variable": variable,
            "direction": direction,
            "sim_mean_tail": sim_mean,
            "obs_mean_tail": obs_mean,
            "diff_mean_tail": diff_mean,
            "relative_bias": rel_bias,
            "pairs_found": n,
            "pairs_used_tail": len(tail),
            "main_source_file": tail[-1]["source_file"] if tail else "",
            "source_keys": tail[-1]["source_keys"] if tail else "",
        })

    return sorted(summary, key=lambda x: x["relative_bias"], reverse=True)


def detect_variable_bias_direction(well: str, variable: str, root: Optional[Path] = None, threshold: float = 0.05) -> dict[str, Any]:
    well_norm = str(well or "").strip().upper()
    summary = summarize_variable_bias(variable, root=root, threshold=threshold)

    for row in summary:
        if row["well"].upper() == well_norm:
            return row

    return {
        "well": well_norm,
        "variable": variable,
        "direction": "unknown",
        "method": "well_not_found",
    }


def write_variable_bias_audit(root: Optional[Path] = None) -> dict[str, str]:
    root = root or Path(__file__).resolve().parents[1]
    out = root / "artifacts" / "diagnosis"
    out.mkdir(parents=True, exist_ok=True)

    written = {}

    all_rows = []

    for variable in VARIABLE_DEFINITIONS:
        rows = summarize_variable_bias(variable, root=root)
        all_rows.extend(rows)

        json_path = out / f"{variable}_bias_direction_audit.json"
        csv_path = out / f"{variable}_bias_direction_audit.csv"

        json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

        with csv_path.open("w", encoding="utf-8", newline="") as f:
            fieldnames = [
                "well", "variable", "direction", "sim_mean_tail", "obs_mean_tail",
                "diff_mean_tail", "relative_bias", "pairs_found", "pairs_used_tail",
                "main_source_file", "source_keys",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        written[variable] = str(csv_path)

    all_json = out / "all_variable_bias_direction_audit.json"
    all_csv = out / "all_variable_bias_direction_audit.csv"

    all_json.write_text(json.dumps(all_rows, indent=2), encoding="utf-8")

    with all_csv.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "well", "variable", "direction", "sim_mean_tail", "obs_mean_tail",
            "diff_mean_tail", "relative_bias", "pairs_found", "pairs_used_tail",
            "main_source_file", "source_keys",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    written["all"] = str(all_csv)

    return written


# V350 disabled earlier __main__ block because V349 override must load first.
# if __name__ == "__main__":
#     paths = write_variable_bias_audit()
#     print("Variable bias audit written:")
#     for k, v in paths.items():
#         print(f"- {k}: {v}")



# ==========================================================
# V349 PROFILE_SERIES SOURCE OVERRIDE
# Use the same source as interactive Plotly profiles:
# app.profile_series.get_profile_series(well, variable)
# ==========================================================

def _v349_float_list(values):
    out = []
    for v in values or []:
        try:
            if v is None:
                out.append(None)
            elif isinstance(v, str) and v.strip().lower() in {"", "nan", "none", "null", "n/a"}:
                out.append(None)
            else:
                out.append(float(str(v).replace(",", "")))
        except Exception:
            out.append(None)
    return out


def _v349_extract_profile_arrays(payload):
    """
    Robust extraction from get_profile_series() output.
    Expected Plotly traces are Observed and Simulated, but backend payload may expose them
    as series/traces/data or direct arrays.
    """
    if not isinstance(payload, dict):
        return None

    # 1) Direct common structures.
    candidates = []

    for key in ["series", "traces", "data"]:
        obj = payload.get(key)
        if isinstance(obj, list):
            candidates.extend(obj)

    # Sometimes nested under payload.
    inner = payload.get("payload")
    if isinstance(inner, dict):
        for key in ["series", "traces", "data"]:
            obj = inner.get(key)
            if isinstance(obj, list):
                candidates.extend(obj)

    obs = None
    sim = None
    x = None

    for item in candidates:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name") or item.get("label") or item.get("legend") or "").lower()

        y_raw = (
            item.get("y")
            or item.get("values")
            or item.get("data")
            or item.get("value")
        )

        x_raw = (
            item.get("x")
            or item.get("dates")
            or item.get("date")
            or item.get("time")
            or item.get("times")
        )

        y = _v349_float_list(y_raw)

        if not y or sum(v is not None for v in y) < 3:
            continue

        if x is None and isinstance(x_raw, list):
            x = x_raw

        if "obs" in name or "hist" in name or "history" in name or "observed" in name:
            obs = y
        elif "sim" in name or "model" in name or "calculated" in name:
            sim = y

    if obs is not None and sim is not None:
        n = min(len(obs), len(sim))
        if n >= 3:
            return {
                "x": x[:n] if isinstance(x, list) else list(range(n)),
                "observed": obs[:n],
                "simulated": sim[:n],
                "source": "profile_series.series_or_traces",
            }

    # 2) Direct array keys.
    sim_keys = [
        "simulated", "simulation", "sim", "model", "modelled", "calculated",
        "sim_values", "sim_y", "simulated_values"
    ]
    obs_keys = [
        "observed", "history", "hist", "obs", "measured", "actual",
        "obs_values", "obs_y", "observed_values", "history_values"
    ]
    x_keys = ["x", "dates", "date", "time", "times"]

    sim_arr = None
    obs_arr = None
    x_arr = None

    search_spaces = [payload]
    if isinstance(payload.get("payload"), dict):
        search_spaces.append(payload["payload"])

    for space in search_spaces:
        if not isinstance(space, dict):
            continue

        for k in sim_keys:
            if isinstance(space.get(k), list):
                sim_arr = _v349_float_list(space.get(k))
                break

        for k in obs_keys:
            if isinstance(space.get(k), list):
                obs_arr = _v349_float_list(space.get(k))
                break

        for k in x_keys:
            if isinstance(space.get(k), list):
                x_arr = space.get(k)
                break

        if sim_arr is not None and obs_arr is not None:
            break

    if sim_arr is not None and obs_arr is not None:
        n = min(len(sim_arr), len(obs_arr))
        if n >= 3:
            return {
                "x": x_arr[:n] if isinstance(x_arr, list) else list(range(n)),
                "observed": obs_arr[:n],
                "simulated": sim_arr[:n],
                "source": "profile_series.direct_arrays",
            }

    # 3) Fallback: use dynamic_profile_agent extractor if available.
    try:
        from app.dynamic_profile_agent import extract_arrays_from_profile_series_payload
        extracted = extract_arrays_from_profile_series_payload(payload)
        if isinstance(extracted, dict):
            sim_arr = (
                extracted.get("simulated")
                or extracted.get("sim")
                or extracted.get("model")
            )
            obs_arr = (
                extracted.get("observed")
                or extracted.get("obs")
                or extracted.get("history")
                or extracted.get("hist")
            )
            x_arr = extracted.get("x") or extracted.get("dates") or extracted.get("time")

            sim_arr = _v349_float_list(sim_arr)
            obs_arr = _v349_float_list(obs_arr)

            n = min(len(sim_arr), len(obs_arr))
            if n >= 3:
                return {
                    "x": x_arr[:n] if isinstance(x_arr, list) else list(range(n)),
                    "observed": obs_arr[:n],
                    "simulated": sim_arr[:n],
                    "source": "dynamic_profile_agent.extract_arrays_from_profile_series_payload",
                }
    except Exception:
        pass

    return None


def _v349_known_wells_from_profile_sources(root=None):
    """
    Get wells from dashboard diagnosis/context files, then use get_profile_series per variable.
    """
    root = root or Path(__file__).resolve().parents[1]
    wells = set()

    # Preferred: diagnosis/context files usually contain all wells.
    for rel in [
        "artifacts/diagnosis/well_property_driver_context.csv",
        "artifacts/diagnosis/hm_summary.csv",
        "artifacts/injection_hm/injection_hm_summary.csv",
    ]:
        fp = root / rel
        if not fp.exists():
            continue
        try:
            import csv
            with fp.open("r", encoding="utf-8", errors="ignore", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    w = (
                        row.get("well")
                        or row.get("well_name")
                        or row.get("WELL")
                        or row.get("WELL_NAME")
                    )
                    if w:
                        wells.add(str(w).strip().upper())
        except Exception:
            pass

    return sorted(wells)


def collect_variable_pairs(variable: str, root: Optional[Path] = None) -> list[dict[str, Any]]:
    """
    V349 override:
    Build sim/obs records from app.profile_series.get_profile_series,
    which is the same source used by the interactive Plotly profile renderer.
    """
    variable = variable.lower().strip()

    # Keep accepted naming consistent.
    if variable == "bhp":
        variable = "pressure"

    if variable not in {"oil", "water", "gas", "pressure"}:
        raise ValueError(f"Unsupported variable: {variable}")

    root = root or Path(__file__).resolve().parents[1]

    records = []

    try:
        from app.profile_series import get_profile_series
    except Exception:
        get_profile_series = None

    if get_profile_series is not None:
        for well in _v349_known_wells_from_profile_sources(root):
            try:
                payload = get_profile_series(well=well, variable=variable)
                arrays = _v349_extract_profile_arrays(payload)
            except Exception:
                arrays = None

            if not arrays:
                continue

            sim = arrays["simulated"]
            obs = arrays["observed"]
            x = arrays.get("x") or list(range(min(len(sim), len(obs))))
            n = min(len(sim), len(obs), len(x))

            for i in range(n):
                sv = sim[i]
                ov = obs[i]

                if sv is None or ov is None:
                    continue

                records.append({
                    "well": well,
                    "variable": variable,
                    "sim": float(sv),
                    "obs": float(ov),
                    "diff": float(sv) - float(ov),
                    "x": x[i],
                    "source_file": f"app.profile_series.get_profile_series:{arrays.get('source')}",
                    "source_keys": "Observed vs Simulated",
                })

    return records


# ==========================================================
# V350 FINAL MAIN AFTER V349 OVERRIDE
# Ensures profile_series override is loaded before writing audits.
# ==========================================================
if __name__ == "__main__":
    paths = write_variable_bias_audit()
    print("Variable bias audit written with V349/V350 profile_series source:")
    for k, v in paths.items():
        print(f"- {k}: {v}")
