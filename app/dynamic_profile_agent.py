import csv
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
SEARCH_DIRS = [
    ROOT / "artifacts",
    ROOT / "data",
    ROOT / "outputs",
]

DATE_KEYS = ["date", "time", "day", "month", "year", "report_date", "datetime"]

VAR_KEYS = {
    "water": {
        "sim": ["WWPR", "WWCT", "WCT", "WATER", "WATER_RATE", "WATER_PROD"],
        "obs": ["WWPRH", "WWCTH", "WCTH", "WATER_OBS", "OBS_WATER", "HIST_WATER"],
        "title": "WATER profile",
    },
    "oil": {
        "sim": ["WOPR", "OIL", "OIL_RATE", "OIL_PROD"],
        "obs": ["WOPRH", "OIL_OBS", "OBS_OIL", "HIST_OIL"],
        "title": "OIL profile",
    },
    "gas": {
        "sim": ["WGPR", "GOR", "GAS", "GAS_RATE", "GAS_PROD"],
        "obs": ["WGPRH", "GORH", "GAS_OBS", "OBS_GAS", "HIST_GAS"],
        "title": "GAS profile",
    },
    "bhp": {
        "sim": ["WBHP", "BHP", "PRESSURE"],
        "obs": ["WBHPH", "BHPH", "OBS_BHP", "HIST_BHP", "OBS_PRESSURE"],
        "title": "BHP profile",
    },
}


def safe_float(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def detect_well(message: str) -> Optional[str]:
    q = str(message or "").upper()
    m = re.search(r"\bHW[-_\s]?(\d+[A-Z]?)\b", q)
    if m:
        return f"HW-{m.group(1)}"
    return None


def detect_variable(message: str) -> Optional[str]:
    q = str(message or "").lower()

    if any(x in q for x in ["water", "wct", "water cut", "watercut"]):
        return "water"
    if any(x in q for x in ["oil", "opr", "wopr"]):
        return "oil"
    if any(x in q for x in ["gas", "gor", "gpr"]):
        return "gas"
    if any(x in q for x in ["bhp", "bottom hole", "pressure profile"]):
        return "bhp"

    return None


def is_profile_request(message: str) -> bool:
    q = str(message or "").lower()
    return (
        any(x in q for x in ["profile", "plot", "curve", "trend", "simulated vs observed", "observed vs simulated"])
        and detect_well(message) is not None
    )


def candidate_files():
    files = []

    for d in SEARCH_DIRS:
        if not d.exists():
            continue

        for p in d.rglob("*"):
            if not p.is_file():
                continue

            if p.suffix.lower() not in [".csv", ".json"]:
                continue

            try:
                if p.stat().st_size > 80_000_000:
                    continue
            except Exception:
                continue

            files.append(p)

    # Prefer files likely to contain profiles/time series.
    files.sort(key=lambda p: (
        0 if re.search(r"profile|series|time|summary|unsmry|production|history", p.name, re.I) else 1,
        len(str(p))
    ))

    return files


def col_score(col: str, well: str, aliases: List[str], observed: bool) -> int:
    c = str(col or "").upper()
    w = well.upper()

    score = 0

    if w in c or w.replace("-", "") in c.replace("-", ""):
        score += 5

    if any(a.upper() in c for a in aliases):
        score += 5

    if observed:
        if any(x in c for x in ["OBS", "HIST", "HISTORY"]) or re.search(r"H[:_\-]?" + re.escape(w), c):
            score += 4
        if c.endswith("H") or ":H" in c:
            score += 2
    else:
        if not any(x in c for x in ["OBS", "HIST", "HISTORY"]):
            score += 1

    return score


def find_date_column(headers: List[str]) -> Optional[str]:
    for h in headers:
        hl = h.lower()
        if any(k in hl for k in DATE_KEYS):
            return h
    return headers[0] if headers else None


def read_wide_csv(path: Path, well: str, variable: str) -> Optional[Dict[str, Any]]:
    aliases = VAR_KEYS[variable]
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            if len(headers) < 3:
                return None

            date_col = find_date_column(headers)

            sim_candidates = sorted(
                headers,
                key=lambda h: col_score(h, well, aliases["sim"], observed=False),
                reverse=True,
            )

            obs_candidates = sorted(
                headers,
                key=lambda h: col_score(h, well, aliases["obs"], observed=True),
                reverse=True,
            )

            sim_col = sim_candidates[0] if sim_candidates and col_score(sim_candidates[0], well, aliases["sim"], False) >= 8 else None
            obs_col = obs_candidates[0] if obs_candidates and col_score(obs_candidates[0], well, aliases["obs"], True) >= 8 else None

            if not sim_col and not obs_col:
                return None

            dates, sim, obs = [], [], []

            for row in reader:
                dates.append(row.get(date_col, len(dates)) if date_col else len(dates))
                sim.append(safe_float(row.get(sim_col)) if sim_col else None)
                obs.append(safe_float(row.get(obs_col)) if obs_col else None)

            if not any(v is not None for v in sim) and not any(v is not None for v in obs):
                return None

            return {
                "dates": dates,
                "simulated": sim,
                "observed": obs,
                "source_file": str(path),
                "sim_col": sim_col,
                "obs_col": obs_col,
                "date_col": date_col,
            }

    except Exception:
        return None


def read_long_csv(path: Path, well: str, variable: str) -> Optional[Dict[str, Any]]:
    aliases = VAR_KEYS[variable]

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            lower = {h.lower(): h for h in headers}

            well_col = next((h for h in headers if h.lower() in ["well", "well_name", "wellname"]), None)
            date_col = find_date_column(headers)

            if not well_col or not date_col:
                return None

            sim_col = None
            obs_col = None

            for h in headers:
                hu = h.upper()
                if any(a.upper() in hu for a in aliases["sim"]) and not any(x in hu for x in ["OBS", "HIST"]):
                    sim_col = h
                if any(a.upper() in hu for a in aliases["obs"]) or any(x in hu for x in ["OBS", "HIST"]):
                    if any(a.upper().replace("H", "") in hu for a in aliases["sim"] + aliases["obs"]):
                        obs_col = h

            if not sim_col and not obs_col:
                return None

            dates, sim, obs = [], [], []

            for row in reader:
                w = str(row.get(well_col) or "").upper()
                if well.upper() not in w and well.upper().replace("-", "") not in w.replace("-", ""):
                    continue

                dates.append(row.get(date_col, len(dates)))
                sim.append(safe_float(row.get(sim_col)) if sim_col else None)
                obs.append(safe_float(row.get(obs_col)) if obs_col else None)

            if not dates:
                return None

            return {
                "dates": dates,
                "simulated": sim,
                "observed": obs,
                "source_file": str(path),
                "sim_col": sim_col,
                "obs_col": obs_col,
                "date_col": date_col,
            }

    except Exception:
        return None





def extract_arrays_from_profile_series_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Very robust extractor for app.profile_series.get_profile_series output.

    It supports:
    - direct keys: dates/time/x + simulated/observed
    - Plotly-style traces: [{"name": "...", "x": [...], "y": [...]}]
    - nested traces under data/series/traces/figure/payload
    - point-style traces: [{"points": [{"x":..., "y":...}, ...]}]
    - table rows: [{"date":..., "simulated":..., "observed":...}]
    """
    if not isinstance(payload, dict):
        return None

    def as_list(v):
        return v if isinstance(v, list) else []

    def numeric_count(values):
        c = 0
        for v in values or []:
            try:
                if v is not None and v != "":
                    float(v)
                    c += 1
            except Exception:
                pass
        return c

    def get_by_keys(obj, keys):
        if not isinstance(obj, dict):
            return None
        for k in keys:
            if k in obj:
                return obj[k]
        # case-insensitive
        lower = {str(k).lower(): k for k in obj.keys()}
        for k in keys:
            lk = k.lower()
            if lk in lower:
                return obj[lower[lk]]
        return None

    def trace_name(tr):
        if not isinstance(tr, dict):
            return ""
        return str(
            tr.get("name") or tr.get("label") or tr.get("legend") or
            tr.get("key") or tr.get("title") or ""
        ).lower()

    def extract_xy_from_trace(tr):
        if not isinstance(tr, dict):
            return [], []

        # Standard x/y
        x = get_by_keys(tr, ["x", "dates", "date", "time", "times", "DATE", "TIME"])
        y = get_by_keys(tr, ["y", "values", "value", "data", "rates", "rate"])

        if isinstance(x, list) and isinstance(y, list):
            return x, y

        # Point list format
        points = get_by_keys(tr, ["points", "rows", "records"])
        if isinstance(points, list) and points and isinstance(points[0], dict):
            xs = []
            ys = []
            for p in points:
                px = get_by_keys(p, ["x", "date", "time", "DATE", "TIME"])
                py = get_by_keys(p, ["y", "value", "rate", "VALUE", "RATE"])
                xs.append(px)
                ys.append(py)
            return xs, ys

        return [], []

    def walk(obj):
        """Yield all nested dict/list objects."""
        yield obj
        if isinstance(obj, dict):
            for v in obj.values():
                yield from walk(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from walk(v)

    # 1. Direct payload format
    direct_dates = get_by_keys(payload, ["dates", "date", "time", "times", "x"])
    direct_sim = get_by_keys(payload, ["simulated", "simulation", "sim", "y_sim", "sim_values"])
    direct_obs = get_by_keys(payload, ["observed", "history", "historical", "obs", "hist", "y_obs", "obs_values"])

    if isinstance(direct_dates, list) and (isinstance(direct_sim, list) or isinstance(direct_obs, list)):
        sim = direct_sim if isinstance(direct_sim, list) else []
        obs = direct_obs if isinstance(direct_obs, list) else []
        if numeric_count(sim) or numeric_count(obs):
            return {
                "dates": direct_dates,
                "simulated": sim,
                "observed": obs,
                "source_file": "app.profile_series.get_profile_series",
                "sim_col": "simulated",
                "obs_col": "observed",
                "date_col": "dates",
                "raw_payload_keys": list(payload.keys()),
            }

    # 2. Find any trace lists recursively
    candidate_trace_lists = []

    for obj in walk(payload):
        if isinstance(obj, dict):
            for key in ["series", "traces", "data", "plot_data", "datasets"]:
                v = obj.get(key)
                if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                    candidate_trace_lists.append(v)

        elif isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj):
            # Could be a trace list or row table
            candidate_trace_lists.append(obj)

    best_result = None
    best_score = -1

    for traces in candidate_trace_lists:
        sim_trace = None
        obs_trace = None

        for tr in traces:
            name = trace_name(tr)

            is_obs = any(x in name for x in [
                "observed", "observation", "history", "historical", "hist", "obs", "actual"
            ])
            is_sim = any(x in name for x in [
                "simulated", "simulation", "sim", "model"
            ])

            if is_obs:
                obs_trace = tr
            elif is_sim:
                sim_trace = tr

        # fallback: if exactly two traces and no clear names
        if sim_trace is None and obs_trace is None and len(traces) >= 2:
            x0, y0 = extract_xy_from_trace(traces[0])
            x1, y1 = extract_xy_from_trace(traces[1])
            if numeric_count(y0) or numeric_count(y1):
                sim_trace = traces[0]
                obs_trace = traces[1]

        # table-like rows fallback
        if sim_trace is None and obs_trace is None and traces and isinstance(traces[0], dict):
            row0 = traces[0]
            cols = list(row0.keys())

            date_col = next((c for c in cols if str(c).lower() in ["date", "time", "dates", "datetime"]), None)
            sim_col = next((c for c in cols if any(k in str(c).lower() for k in ["sim", "model"])), None)
            obs_col = next((c for c in cols if any(k in str(c).lower() for k in ["obs", "hist", "actual"])), None)

            if date_col and (sim_col or obs_col):
                dates = [r.get(date_col) for r in traces]
                sim = [r.get(sim_col) for r in traces] if sim_col else []
                obs = [r.get(obs_col) for r in traces] if obs_col else []
                score = numeric_count(sim) + numeric_count(obs)

                if score > best_score:
                    best_score = score
                    best_result = {
                        "dates": dates,
                        "simulated": sim,
                        "observed": obs,
                        "source_file": "app.profile_series.get_profile_series",
                        "sim_col": sim_col,
                        "obs_col": obs_col,
                        "date_col": date_col,
                        "raw_payload_keys": list(payload.keys()),
                    }

        if sim_trace is not None or obs_trace is not None:
            ref = sim_trace or obs_trace
            dates, _ = extract_xy_from_trace(ref)

            _, sim = extract_xy_from_trace(sim_trace) if sim_trace is not None else ([], [])
            _, obs = extract_xy_from_trace(obs_trace) if obs_trace is not None else ([], [])

            n = max(len(dates), len(sim), len(obs))
            if len(dates) < n:
                dates = list(range(n))

            score = numeric_count(sim) + numeric_count(obs)

            if score > best_score:
                best_score = score
                best_result = {
                    "dates": dates,
                    "simulated": sim,
                    "observed": obs,
                    "source_file": "app.profile_series.get_profile_series",
                    "sim_col": trace_name(sim_trace) if sim_trace else "simulated",
                    "obs_col": trace_name(obs_trace) if obs_trace else "observed",
                    "date_col": "x/dates",
                    "raw_payload_keys": list(payload.keys()),
                }

    if best_result and best_score > 0:
        return best_result

    return None


def find_profile_arrays_from_profile_series(well: str, variable: str) -> Optional[Dict[str, Any]]:
    try:
        from app.profile_series import get_profile_series

        payload = get_profile_series(well=well, variable=variable)
        extracted = extract_arrays_from_profile_series_payload(payload)

        if extracted:
            extracted["raw_profile_status"] = payload.get("status") or payload.get("message") or payload.get("ok")
            return extracted

        return {
            "dates": [],
            "simulated": [],
            "observed": [],
            "source_file": "app.profile_series.get_profile_series",
            "profile_series_payload_keys": list(payload.keys()) if isinstance(payload, dict) else [],
            "profile_series_payload_preview": str(payload)[:3000],
        }

    except Exception as exc:
        return {
            "dates": [],
            "simulated": [],
            "observed": [],
            "source_file": "app.profile_series.get_profile_series",
            "profile_series_error": str(exc),
        }


def find_profile_arrays(well: str, variable: str) -> Optional[Dict[str, Any]]:
    # 1. First use the same source as the existing static PNG plot.
    out = find_profile_arrays_from_profile_series(well, variable)

    if out and (
        any(v is not None for v in out.get("simulated", [])) or
        any(v is not None for v in out.get("observed", []))
    ):
        out["checked_files_count"] = 0
        out["checked_files_sample"] = []
        return out

    # 2. Fallback to CSV/JSON artifacts if profile_series does not expose arrays.
    checked = []

    for p in candidate_files():
        checked.append(str(p))

        csv_out = read_wide_csv(p, well, variable)
        if csv_out:
            csv_out["checked_files_count"] = len(checked)
            return csv_out

        csv_out = read_long_csv(p, well, variable)
        if csv_out:
            csv_out["checked_files_count"] = len(checked)
            return csv_out

    if out:
        out["checked_files_count"] = len(checked)
        out["checked_files_sample"] = checked[:20]
        return out

    return {
        "dates": [],
        "simulated": [],
        "observed": [],
        "checked_files_count": len(checked),
        "checked_files_sample": checked[:20],
    }


def answer_dynamic_profile_question(message: str):
    if not is_profile_request(message):
        return None

    well = detect_well(message)
    variable = detect_variable(message) or "water"

    result = find_profile_arrays(well, variable)

    dates = result.get("dates") or []
    sim = result.get("simulated") or []
    obs = result.get("observed") or []

    has_data = len(dates) >= 2 and (
        any(v is not None for v in sim) or any(v is not None for v in obs)
    )

    if not has_data:
        return {
            "type": "visual_response",
            "answer": (
                f"I tried to build an interactive {variable} profile for {well}, "
                "but I could not find numeric simulated/observed arrays in the current CSV/JSON artifacts. "
                "The existing static PNG can be shown, but Plotly needs the underlying time-series data."
            ),
            "intent": "dynamic_profile_missing_arrays",
            "ui_blocks": [
                {
                    "type": "compact_notes",
                    "title": "Profile data not found",
                    "items": [
                        f"Well requested: {well}",
                        f"Variable requested: {variable}",
                        f"Files checked: {result.get('checked_files_count')}",
                        "Need a CSV/JSON with DATE plus simulated and observed columns, for example WOPR:HW-29 and WOPRH:HW-29.",
                    ],
                }
            ],
            "data": result,
            "agent_trace": {
                "DynamicProfileAgent": {
                    "well": well,
                    "variable": variable,
                    "status": "missing_arrays",
                    "checked_files_count": result.get("checked_files_count"),
                }
            },
        }

    title = f"{well} {VAR_KEYS[variable]['title']}"

    return {
        "type": "visual_response",
        "answer": (
            f"I built an interactive simulated-vs-observed {variable} profile for {well}. "
            "You can zoom, pan, hover values and use the time range slider."
        ),
        "intent": "dynamic_interactive_profile",
        "ui_blocks": [
            {
                "type": "profile_series",
                "title": title,
                "data": {
                    "title": title,
                    "well": well,
                    "variable": variable,
                    "dates": dates,
                    "simulated": sim,
                    "observed": obs,
                    "source_file": result.get("source_file"),
                    "sim_col": result.get("sim_col"),
                    "obs_col": result.get("obs_col"),
                    "date_col": result.get("date_col"),
                },
            }
        ],
        "data": result,
        "agent_trace": {
            "DynamicProfileAgent": {
                "well": well,
                "variable": variable,
                "status": "interactive_arrays_found",
                "source_file": result.get("source_file"),
                "sim_col": result.get("sim_col"),
                "obs_col": result.get("obs_col"),
            }
        },
    }


if __name__ == "__main__":
    for q in [
        "show water profile for HW-29",
        "show oil profile for HW-29",
        "show gas profile for HW-29",
        "show BHP profile for HW-29",
    ]:
        print("=" * 80)
        print(q)
        r = answer_dynamic_profile_question(q)
        print(r["intent"] if r else None)
        print(r["answer"] if r else None)
        print(r.get("agent_trace") if r else None)
