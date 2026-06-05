from __future__ import annotations

import math
import re
import uuid
from pathlib import Path
from typing import Any, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
PLOT_DIR = ROOT / "artifacts" / "chat_plots"
PLOT_DIR.mkdir(parents=True, exist_ok=True)


VARIABLE_ALIASES = {
    "oil": ["oil", "olio", "oil rate", "oil production", "liquid oil", "wopr", "wopt"],
    "water": ["water", "acqua", "wct", "wwct", "wwpr", "wwpt"],
    "gas": ["gas", "wgpr", "wgpt", "gor", "wgor"],
    "pressure": ["pressure", "pressione", "bhp", "wbhp", "fpr"],
}


PROPERTY_ALIASES = {
    "PORO": ["poro", "porosity", "porosità", "porosity distribution"],
    "PERM_X": ["perm_x", "permx", "perm i", "perm_i", "permeability x", "permeabilità x", "permeability"],
    "PERM_Y": ["perm_y", "permy", "perm j", "perm_j", "permeability y", "permeabilità y"],
    "PERM_Z": ["perm_z", "permz", "perm k", "perm_k", "permeability z", "permeabilità z"],
    "SWAT_INIT": ["swat_init", "initial swat", "initial water saturation"],
    "SWAT_EOH": ["swat_eoh", "final swat", "end water saturation"],
    "SOIL_INIT": ["soil_init", "initial soil", "initial oil saturation"],
    "SOIL_EOH": ["soil_eoh", "final soil", "end oil saturation"],
    "SGAS_INIT": ["sgas_init", "initial sgas", "initial gas saturation"],
    "SGAS_EOH": ["sgas_eoh", "final sgas", "end gas saturation"],
    "PRESSURE_INIT": ["pressure_init", "initial pressure"],
    "PRESSURE_EOH": ["pressure_eoh", "final pressure", "end pressure"],
    "TRANX": ["tranx", "transmissibility x"],
    "TRANY": ["trany", "transmissibility y"],
    "TRANZ": ["tranz", "transmissibility z"],
    "FIPNUM": ["fipnum"],
    "SATNUM": ["satnum"],
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9_]+", " ", str(s).lower()).strip()


def _detect_well(message: str) -> Optional[str]:
    m = re.search(r"\b([A-Z]{1,4}-\d+[A-Z]?)\b", message.upper())
    return m.group(1) if m else None


def _detect_variable(message: str) -> Optional[str]:
    msg = _norm(message)
    for variable, aliases in VARIABLE_ALIASES.items():
        if any(_norm(a) in msg for a in aliases):
            return variable
    return None


def _detect_property(message: str) -> Optional[str]:
    msg = _norm(message)

    # Prefer exact property names first.
    for prop in PROPERTY_ALIASES:
        if _norm(prop) in msg:
            return prop

    for prop, aliases in PROPERTY_ALIASES.items():
        if any(_norm(a) in msg for a in aliases):
            return prop

    return None




# ==========================================================
# V412 DIAGNOSTIC INTENT BYPASS
# Do not let deterministic plot/property handlers capture
# reservoir diagnostic questions such as WCT/GOR bias clusters.
# These should continue to the agentic/LangGraph diagnostic path.
# ==========================================================

def _is_holistic_diagnostic_query_v412(message: str) -> bool:
    msg = _norm(message)

    has_reservoir_signal = any(x in msg for x in [
        "wct", "water cut", "water-cut", "water",
        "gas", "gor", "gas oil ratio", "gas-oil ratio",
        "oil", "bhp", "pressure", "rate", "profile",
    ])

    has_diagnostic_intent = any(x in msg for x in [
        "bias", "cluster", "mismatch", "driver", "drivers",
        "weak", "weakest", "diagnostic", "diagnose",
        "history match", "history matching", "hm",
        "pattern", "evidence", "review first",
    ])

    return has_reservoir_signal and has_diagnostic_intent


def _detect_plot_type(message: str) -> Optional[str]:
    msg = _norm(message)

    if any(x in msg for x in ["cumulative", "cumulate", "cumulated", "cumulativo", "cumulata", "cum"]):
        return "cumulative"

    if any(x in msg for x in ["distribution", "distribuzione", "histogram", "istogramma", "hist"]):
        return "distribution"

    if any(x in msg for x in ["plot", "chart", "grafico", "traccia", "profile", "profilo", "rate", "production rate"]):
        return "profile"

    return None


def _is_plot_request(message: str) -> bool:
    if _is_holistic_diagnostic_query_v412(message):
        return False

    msg = _norm(message)
    return any(x in msg for x in [
        "plot", "chart", "grafico", "istogramma", "histogram",
        "distribution", "distribuzione", "profile", "profiles", "profilo",
        "cumulative", "cumulate", "cumulativo", "cumulata",
        "rate", "production rate", "oil rate", "water rate", "gas rate",
        "show me", "fammi vedere", "mostrami"
    ])


def _float_list(values):
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


def _extract_profile_arrays(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    Same spirit as V349: extract Observed/Simulated arrays from profile_series payload.
    """
    if not isinstance(payload, dict):
        return None

    candidates = []

    for key in ["series", "traces", "data"]:
        if isinstance(payload.get(key), list):
            candidates.extend(payload[key])

    inner = payload.get("payload")
    if isinstance(inner, dict):
        for key in ["series", "traces", "data"]:
            if isinstance(inner.get(key), list):
                candidates.extend(inner[key])

    obs = None
    sim = None
    x = None

    for item in candidates:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name") or item.get("label") or "").lower()
        y = _float_list(item.get("y") or item.get("values") or item.get("data"))
        x_raw = item.get("x") or item.get("dates") or item.get("time")

        if not y or sum(v is not None for v in y) < 3:
            continue

        if x is None and isinstance(x_raw, list):
            x = x_raw

        if any(k in name for k in ["obs", "observed", "hist", "history"]):
            obs = y
        elif any(k in name for k in ["sim", "simulated", "model"]):
            sim = y

    if obs is not None and sim is not None:
        n = min(len(obs), len(sim))
        return {
            "x": x[:n] if isinstance(x, list) else list(range(n)),
            "observed": obs[:n],
            "simulated": sim[:n],
        }

    try:
        from app.dynamic_profile_agent import extract_arrays_from_profile_series_payload
        extracted = extract_arrays_from_profile_series_payload(payload)
        if isinstance(extracted, dict):
            sim_arr = _float_list(extracted.get("simulated") or extracted.get("sim") or extracted.get("model"))
            obs_arr = _float_list(extracted.get("observed") or extracted.get("obs") or extracted.get("history") or extracted.get("hist"))
            x_arr = extracted.get("x") or extracted.get("dates") or extracted.get("time")
            n = min(len(sim_arr), len(obs_arr))
            if n >= 3:
                return {
                    "x": x_arr[:n] if isinstance(x_arr, list) else list(range(n)),
                    "observed": obs_arr[:n],
                    "simulated": sim_arr[:n],
                }
    except Exception:
        pass

    return None


def _cumulative(values):
    total = 0.0
    out = []
    for v in values:
        if v is None or not math.isfinite(float(v)):
            out.append(total)
        else:
            total += float(v)
            out.append(total)
    return out


def _plot_profile_or_cumulative(message: str, well: str, variable: str, plot_type: str) -> dict[str, Any]:
    from app.profile_series import get_profile_series

    payload = get_profile_series(well=well, variable=variable)
    arrays = _extract_profile_arrays(payload)

    if not arrays:
        return {
            "ok": False,
            "message": f"I could not extract Observed/Simulated profile arrays for {well} / {variable}.",
        }

    x = arrays["x"]
    sim = arrays["simulated"]
    obs = arrays["observed"]

    n = min(len(x), len(sim), len(obs))
    x = x[:n]
    sim = sim[:n]
    obs = obs[:n]

    if plot_type == "cumulative":
        sim_plot = _cumulative(sim)
        obs_plot = _cumulative(obs)
        title = f"{well} - Cumulative {variable}"
        y_label = f"Cumulative {variable}"
        note = "Cumulative profile is computed from the available profile-series values."
    else:
        sim_plot = sim
        obs_plot = obs
        title = f"{well} - {variable.capitalize()} profile"
        y_label = variable.capitalize()
        note = "Profile uses the same source as the interactive Plotly plots."

    plot_id = uuid.uuid4().hex[:10]
    filename = f"{plot_id}_{well}_{variable}_{plot_type}.png".replace("/", "_")
    path = PLOT_DIR / filename

    plt.figure(figsize=(11, 5.8))
    plt.plot(x, obs_plot, label="Observed")
    plt.plot(x, sim_plot, label="Simulated")
    plt.title(title)
    plt.xlabel("Date / profile index")
    plt.ylabel(y_label)
    plt.xticks(rotation=30, ha="right")
    plt.grid(True, alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()

    return {
        "ok": True,
        "message": f"Created {plot_type} plot for {well} / {variable}. {note}",
        "image_url": f"/artifacts/chat_plots/{filename}",
        "image_path": str(path),
        "well": well,
        "variable": variable,
        "plot_type": plot_type,
        "points": n,
    }


def _parse_grdecl_values(path: Path, max_values: int = 5_000_000) -> list[float]:
    values = []
    started = False

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()

            if not line or line.startswith("--"):
                continue

            # First non-comment line is keyword. Data begins after keyword.
            if not started:
                started = True
                continue

            # Remove inline comments and slash terminator.
            line = line.split("--", 1)[0].replace("/", " ")
            if not line.strip():
                continue

            for token in line.split():
                if "*" in token:
                    try:
                        n_s, v_s = token.split("*", 1)
                        n = int(float(n_s))
                        v = float(v_s)
                        if math.isfinite(v):
                            values.extend([v] * n)
                    except Exception:
                        continue
                else:
                    try:
                        v = float(token)
                        if math.isfinite(v):
                            values.append(v)
                    except Exception:
                        continue

                if len(values) >= max_values:
                    return values[:max_values]

    return values


def _find_property_file(prop: str) -> Optional[Path]:
    candidates = []

    search_roots = [
        ROOT / "artifacts",
        ROOT,
    ]

    names = [
        f"{prop}.GRDECL",
        f"{prop}.grdecl",
    ]

    for base in search_roots:
        if not base.exists():
            continue
        for name in names:
            candidates.extend(base.rglob(name))

    # Prefer completed imported/standardized case or extracted grdecl.
    candidates = [p for p in candidates if p.is_file()]
    candidates = sorted(
        candidates,
        key=lambda p: (
            "completed_run_imports" not in str(p).lower(),
            "404_rnf_extracted_grdecl" not in str(p).lower(),
            len(str(p)),
        ),
    )

    return candidates[0] if candidates else None


def _plot_property_distribution(prop: str) -> dict[str, Any]:
    path = _find_property_file(prop)

    if not path:
        return {
            "ok": False,
            "message": f"I could not find a GRDECL file for property {prop}. Expected something like {prop}.GRDECL.",
        }

    values = _parse_grdecl_values(path)

    if not values:
        return {
            "ok": False,
            "message": f"I found {path.name}, but could not parse numeric values.",
        }

    plot_id = uuid.uuid4().hex[:10]
    filename = f"{plot_id}_{prop}_distribution.png"
    out = PLOT_DIR / filename

    plt.figure(figsize=(9, 5.5))
    plt.hist(values, bins=80)
    plt.title(f"{prop} distribution")
    plt.xlabel(prop)
    plt.ylabel("Cell count")
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()

    sorted_vals = sorted(values)
    n = len(sorted_vals)

    def pct(q):
        if n == 0:
            return None
        idx = min(n - 1, max(0, int(q * (n - 1))))
        return sorted_vals[idx]

    return {
        "ok": True,
        "message": (
            f"Created distribution plot for {prop}. "
            f"Parsed {n:,} values from {path.name}. "
            f"P10={pct(0.10):.4g}, P50={pct(0.50):.4g}, P90={pct(0.90):.4g}."
        ),
        "image_url": f"/artifacts/chat_plots/{filename}",
        "image_path": str(out),
        "property": prop,
        "plot_type": "distribution",
        "values": n,
        "source_file": str(path),
    }


def handle_static_plot_request(message: str) -> Optional[dict[str, Any]]:
    if _is_holistic_diagnostic_query_v412(message):
        return None

    if not _is_plot_request(message):
        return None

    plot_type = _detect_plot_type(message) or "profile"
    well = _detect_well(message)
    variable = _detect_variable(message)
    prop = _detect_property(message)

    # Distribution/histogram of a grid property.
    if plot_type == "distribution" or prop:
        if not prop:
            return {
                "ok": False,
                "message": (
                    "I understood that you want a property distribution plot, but I could not identify the property. "
                    "Try for example: 'plot distribution of PERM_X' or 'histogram of PORO'."
                ),
            }
        return _plot_property_distribution(prop)

    # Profile/cumulative plot.
    if variable:
        if not well:
            return {
                "ok": False,
                "message": (
                    f"I understood that you want a {plot_type} plot for {variable}, "
                    "but I need the well name, for example HW-32."
                ),
            }
        return _plot_profile_or_cumulative(message, well, variable, plot_type)

    return {
        "ok": False,
        "message": (
            "I understood that you want a plot, but I could not identify the variable/property. "
            "Examples: 'plot cumulative water for HW-32', 'plot oil profile for HW-10', "
            "'plot distribution of PERM_X', 'histogram of PORO'."
        ),
    }



# ==========================================================
# V355 INTERACTIVE PLOTLY PAYLOADS
# Adds Plotly-ready payloads to profile/cumulative/property plots.
# Frontend can render result["plotly_chart"] interactively.
# ==========================================================

def _v355_make_profile_plotly(well, variable, plot_type, x, obs_values, sim_values):
    title = f"{well} - {'Cumulative ' if plot_type == 'cumulative' else ''}{str(variable).capitalize()}"

    y_title = f"Cumulative {variable}" if plot_type == "cumulative" else str(variable).capitalize()

    return {
        "type": "plotly_chart",
        "title": title,
        "data": [
            {
                "x": list(x),
                "y": list(obs_values),
                "type": "scatter",
                "mode": "lines",
                "name": "Observed",
            },
            {
                "x": list(x),
                "y": list(sim_values),
                "type": "scatter",
                "mode": "lines",
                "name": "Simulated",
            },
        ],
        "layout": {
            "title": title,
            "xaxis": {"title": "Date / profile index"},
            "yaxis": {"title": y_title},
            "hovermode": "x unified",
            "legend": {"orientation": "h", "y": -0.25},
            "margin": {"l": 70, "r": 25, "t": 60, "b": 90},
            "height": 520,
        },
        "config": {
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True,
        },
    }


def _v355_make_distribution_plotly(prop, values, max_points=250000):
    vals = list(values or [])

    # Plotly can handle many points, but avoid sending millions to the browser.
    if len(vals) > max_points:
        step = max(1, len(vals) // max_points)
        vals = vals[::step]

    title = f"{prop} distribution"

    return {
        "type": "plotly_chart",
        "title": title,
        "data": [
            {
                "x": vals,
                "type": "histogram",
                "name": prop,
                "nbinsx": 80,
            }
        ],
        "layout": {
            "title": title,
            "xaxis": {"title": prop},
            "yaxis": {"title": "Cell count"},
            "bargap": 0.03,
            "margin": {"l": 70, "r": 25, "t": 60, "b": 70},
            "height": 520,
        },
        "config": {
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True,
        },
    }


# Wrap profile/cumulative function.
try:
    _plot_profile_or_cumulative_original_v355 = _plot_profile_or_cumulative

    def _plot_profile_or_cumulative(message: str, well: str, variable: str, plot_type: str) -> dict[str, Any]:
        result = _plot_profile_or_cumulative_original_v355(message, well, variable, plot_type)

        try:
            from app.profile_series import get_profile_series

            payload = get_profile_series(well=well, variable=variable)
            arrays = _extract_profile_arrays(payload)

            if arrays:
                x = arrays["x"]
                sim = arrays["simulated"]
                obs = arrays["observed"]

                n = min(len(x), len(sim), len(obs))
                x = x[:n]
                sim = sim[:n]
                obs = obs[:n]

                if plot_type == "cumulative":
                    sim_plot = _cumulative(sim)
                    obs_plot = _cumulative(obs)
                else:
                    sim_plot = sim
                    obs_plot = obs

                result["plotly_chart"] = _v355_make_profile_plotly(
                    well=well,
                    variable=variable,
                    plot_type=plot_type,
                    x=x,
                    obs_values=obs_plot,
                    sim_values=sim_plot,
                )
                result["interactive"] = True
                result["message"] = (
                    f"Created interactive {plot_type} plot for {well} / {variable}. "
                    "Use zoom, pan, hover and legend controls directly in the chart."
                )
        except Exception as exc:
            result["plotly_error_v355"] = str(exc)

        return result

except NameError:
    pass


# Wrap property distribution function.
try:
    _plot_property_distribution_original_v355 = _plot_property_distribution

    def _plot_property_distribution(prop: str) -> dict[str, Any]:
        result = _plot_property_distribution_original_v355(prop)

        try:
            path = _find_property_file(prop)
            if path:
                values = _parse_grdecl_values(path)
                if values:
                    result["plotly_chart"] = _v355_make_distribution_plotly(prop, values)
                    result["interactive"] = True
                    result["message"] = (
                        f"Created interactive distribution plot for {prop}. "
                        f"Parsed {len(values):,} values. Use zoom, pan and hover directly in the chart."
                    )
        except Exception as exc:
            result["plotly_error_v355"] = str(exc)

        return result

except NameError:
    pass




# ==========================================================
# V359 PROFILE ALIAS PLOTLY FORCE
# Some variables may not resolve with only "oil", "gas", etc.
# Try multiple profile_series variable aliases and always return
# interactive Plotly if a valid Observed/Simulated profile is found.
# ==========================================================

def _v359_profile_variable_candidates(variable: str):
    v = str(variable or "").lower().strip()

    if v == "oil":
        return ["oil", "oil_rate", "wopr", "WOPR", "oil production", "oil_profile"]

    if v == "water":
        return ["water", "water_rate", "wct", "wwct", "wwpr", "WWCT", "WWPR", "water_profile"]

    if v == "gas":
        return ["gas", "gas_rate", "wgpr", "WGPR", "gor", "WGOR", "gas_profile"]

    if v == "pressure":
        return ["pressure", "bhp", "wbhp", "WBHP", "fpr", "pressure_profile"]

    return [v]


def _v359_get_profile_arrays_with_aliases(well: str, variable: str):
    from app.profile_series import get_profile_series

    errors = []

    for candidate in _v359_profile_variable_candidates(variable):
        try:
            payload = get_profile_series(well=well, variable=candidate)
            arrays = _extract_profile_arrays(payload)

            if arrays:
                sim = arrays.get("simulated") or []
                obs = arrays.get("observed") or []
                n = min(len(sim), len(obs))

                valid_pairs = 0
                for i in range(n):
                    if sim[i] is not None and obs[i] is not None:
                        valid_pairs += 1

                if valid_pairs >= 3:
                    arrays["resolved_variable"] = candidate
                    arrays["valid_pairs"] = valid_pairs
                    return arrays

        except Exception as exc:
            errors.append(f"{candidate}: {exc}")

    return None


try:
    _plot_profile_or_cumulative_original_v359 = _plot_profile_or_cumulative

    def _plot_profile_or_cumulative(message: str, well: str, variable: str, plot_type: str) -> dict[str, Any]:
        # Keep the existing static export as fallback, but force interactive chart when possible.
        result = _plot_profile_or_cumulative_original_v359(message, well, variable, plot_type)

        try:
            arrays = _v359_get_profile_arrays_with_aliases(well, variable)

            if arrays:
                x = arrays["x"]
                sim = arrays["simulated"]
                obs = arrays["observed"]

                n = min(len(x), len(sim), len(obs))
                x = x[:n]
                sim = sim[:n]
                obs = obs[:n]

                if plot_type == "cumulative":
                    sim_plot = _cumulative(sim)
                    obs_plot = _cumulative(obs)
                else:
                    sim_plot = sim
                    obs_plot = obs

                result["plotly_chart"] = _v355_make_profile_plotly(
                    well=well,
                    variable=variable,
                    plot_type=plot_type,
                    x=x,
                    obs_values=obs_plot,
                    sim_values=sim_plot,
                )

                result["interactive"] = True
                result["resolved_profile_variable_v359"] = arrays.get("resolved_variable")
                result["valid_pairs_v359"] = arrays.get("valid_pairs")
                result["image_url"] = None

                result["message"] = (
                    f"Created interactive {plot_type} plot for {well} / {variable}. "
                    f"Resolved profile variable: {arrays.get('resolved_variable')}. "
                    "Use zoom, pan, hover and legend controls directly in the chart."
                )

        except Exception as exc:
            result["plotly_error_v359"] = str(exc)

        return result

except NameError:
    pass




# ==========================================================
# V365 TRANSMISSIBILITY GENERIC DISTRIBUTION
# "transmissibility distribution" -> combined TRANX / TRANY / TRANZ
# ==========================================================

try:
    PROPERTY_ALIASES["TRAN_ALL"] = [
        "transmissibility",
        "transmissibilities",
        "transmissibility distribution",
        "tran distribution",
        "trans distribution",
        "trasmissibilità",
        "distribuzione transmissibility",
        "distribuzione trasmissibilità",
    ]
except Exception:
    pass


try:
    _detect_property_original_v365 = _detect_property

    def _detect_property(message: str) -> Optional[str]:
        msg = _norm(message)

        # Generic transmissibility request: no direction specified.
        if any(x in msg for x in [
            "transmissibility",
            "transmissibilities",
            "trasmissibilita",
            "trasmissibilità",
            "tran distribution",
            "trans distribution",
        ]):
            if not any(x in msg for x in ["tranx", "tran x", "x direction", "transmissibility x"]):
                if not any(x in msg for x in ["trany", "tran y", "y direction", "transmissibility y"]):
                    if not any(x in msg for x in ["tranz", "tran z", "z direction", "transmissibility z"]):
                        return "TRAN_ALL"

        return _detect_property_original_v365(message)

except NameError:
    pass


def _plot_transmissibility_all_distribution_v365() -> dict[str, Any]:
    props = ["TRANX", "TRANY", "TRANZ"]
    traces = []
    stats = []
    total_values = 0

    for prop in props:
        path = _find_property_file(prop)
        if not path:
            continue

        values = _parse_grdecl_values(path)

        if not values:
            continue

        total_values += len(values)

        # Avoid sending millions of values to browser.
        max_points = 250000
        vals_for_plot = values
        if len(vals_for_plot) > max_points:
            step = max(1, len(vals_for_plot) // max_points)
            vals_for_plot = vals_for_plot[::step]

        traces.append({
            "x": vals_for_plot,
            "type": "histogram",
            "name": prop,
            "nbinsx": 80,
            "opacity": 0.62,
        })

        sorted_vals = sorted(values)
        n = len(sorted_vals)

        def pct(q):
            idx = min(n - 1, max(0, int(q * (n - 1))))
            return sorted_vals[idx]

        stats.append(f"{prop}: n={n:,}, P50={pct(0.50):.4g}, P90={pct(0.90):.4g}")

    if not traces:
        return {
            "ok": False,
            "message": "I could not find TRANX, TRANY or TRANZ GRDECL files for transmissibility distribution.",
        }

    plotly_chart = {
        "type": "plotly_chart",
        "title": "Transmissibility distribution - TRANX / TRANY / TRANZ",
        "data": traces,
        "layout": {
            "title": "Transmissibility distribution - TRANX / TRANY / TRANZ",
            "xaxis": {"title": "Transmissibility"},
            "yaxis": {"title": "Cell count"},
            "barmode": "overlay",
            "bargap": 0.03,
            "hovermode": "x unified",
            "height": 560,
            "margin": {"l": 78, "r": 34, "t": 72, "b": 86},
        },
        "config": {
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True,
        },
    }

    return {
        "ok": True,
        "message": (
            "Created interactive transmissibility distribution plot using TRANX, TRANY and TRANZ. "
            + " | ".join(stats)
        ),
        "property": "TRAN_ALL",
        "plot_type": "distribution",
        "values": total_values,
        "interactive": True,
        "image_url": None,
        "plotly_chart": plotly_chart,
    }


try:
    _plot_property_distribution_original_v365 = _plot_property_distribution

    def _plot_property_distribution(prop: str) -> dict[str, Any]:
        if str(prop).upper() == "TRAN_ALL":
            return _plot_transmissibility_all_distribution_v365()

        return _plot_property_distribution_original_v365(prop)

except NameError:
    pass




# ==========================================================
# V378 INTERACTIVE GRDECL PROPERTY MAPS
# Handles requests like:
# - show me SWAT map at initial
# - show me pressure map at final
# - show me PERM_X map
# Creates Plotly heatmap payload from GRDECL values.
# ==========================================================



# ==========================================================
# V413 DIAGNOSTIC INTENT BYPASS
# Prevent final V378 property-map override from capturing
# WCT/GOR/water/gas/oil/BHP bias/cluster/HM diagnostic queries.
# ==========================================================

def _is_holistic_diagnostic_query_v413(message: str) -> bool:
    msg = _norm(message)

    has_reservoir_signal = any(x in msg for x in [
        "wct", "water cut", "water-cut", "water",
        "gas", "gor", "gas oil ratio", "gas-oil ratio",
        "oil", "bhp", "pressure", "rate", "profile",
    ])

    has_diagnostic_intent = any(x in msg for x in [
        "bias", "cluster", "mismatch", "driver", "drivers",
        "weak", "weakest", "diagnostic", "diagnose",
        "history match", "history matching", "hm",
        "pattern", "evidence", "review first",
    ])

    return has_reservoir_signal and has_diagnostic_intent


def _v378_norm_msg(message: str) -> str:
    return str(message or "").lower().replace("_", " ").replace("-", " ")


def _v378_is_map_request(message: str) -> bool:
    if _is_holistic_diagnostic_query_v413(message):
        return False

    msg = _v378_norm_msg(message)
    return any(x in msg for x in [
        " map", "map ", "mappa", "heatmap", "property map",
        "show me swat", "show swat", "show me pressure",
    ])


def _v378_detect_map_property(message: str):
    msg = _v378_norm_msg(message)

    is_initial = any(x in msg for x in [
        "initial", "init", "start", "first", "iniziale", "inizio", "at initial"
    ])

    is_final = any(x in msg for x in [
        "final", "eoh", "end", "last", "ultimo", "fine", "at final"
    ])

    def timed(base):
        if is_final:
            return f"{base}_EOH"
        return f"{base}_INIT"

    # Dynamic properties.
    if any(x in msg for x in ["swat", "water saturation", "saturazione acqua"]):
        return timed("SWAT")

    if any(x in msg for x in ["soil", "oil saturation", "saturazione olio"]):
        return timed("SOIL")

    if any(x in msg for x in ["sgas", "gas saturation", "saturazione gas"]):
        return timed("SGAS")

    if any(x in msg for x in ["pressure", "pressione", "press"]):
        return timed("PRESSURE")

    # Static properties.
    if any(x in msg for x in ["perm x", "permx", "perm_x", "permeability x"]):
        return "PERM_X"

    if any(x in msg for x in ["perm y", "permy", "perm_y", "permeability y"]):
        return "PERM_Y"

    if any(x in msg for x in ["perm z", "permz", "perm_z", "permeability z"]):
        return "PERM_Z"

    if any(x in msg for x in ["poro", "porosity", "porosita", "porosità"]):
        return "PORO"

    if any(x in msg for x in ["tran x", "tranx", "transmissibility x"]):
        return "TRANX"

    if any(x in msg for x in ["tran y", "trany", "transmissibility y"]):
        return "TRANY"

    if any(x in msg for x in ["tran z", "tranz", "transmissibility z"]):
        return "TRANZ"

    # Generic transmissibility map defaults to TRANX unless direction is specified.
    if any(x in msg for x in ["transmissibility", "trasmissibilita", "trasmissibilità"]):
        return "TRANX"

    return None


def _v378_load_grid_dimensions():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]

    candidates = list(root.glob("**/grid_dimensions.json"))

    # Prefer active/completed-run standardized case artifacts.
    candidates = sorted(
        candidates,
        key=lambda x: (
            0 if "completed_run_imports" in str(x).lower() or "standardized_case" in str(x).lower() else 1,
            -x.stat().st_mtime
        )
    )

    for path in candidates:
        try:
            d = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            nx = int(d.get("nx") or d.get("NX") or d.get("i") or d.get("I"))
            ny = int(d.get("ny") or d.get("NY") or d.get("j") or d.get("J"))
            nz = int(d.get("nz") or d.get("NZ") or d.get("k") or d.get("K"))
            if nx > 0 and ny > 0 and nz > 0:
                return {"nx": nx, "ny": ny, "nz": nz, "path": str(path)}
        except Exception:
            continue

    return None


def _v378_find_grdecl_property_file(prop: str):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    p = str(prop or "").upper()

    candidates = []

    patterns = [
        f"{p}.GRDECL",
        f"{p}.grdecl",
        f"*{p}*.GRDECL",
        f"*{p}*.grdecl",
    ]

    for pattern in patterns:
        candidates.extend(root.glob(f"**/{pattern}"))

    # Avoid backups if possible, prefer standardized/active artifacts.
    candidates = [
        x for x in candidates
        if "backup" not in str(x).lower()
        and "before_" not in x.name.lower()
    ]

    if not candidates:
        return None

    candidates = sorted(
        candidates,
        key=lambda x: (
            0 if "completed_run_imports" in str(x).lower() or "standardized_case" in str(x).lower() else 1,
            -x.stat().st_mtime
        )
    )

    return candidates[0]


def _v378_values_to_top_map(values, nx: int, ny: int, nz: int):
    import math

    n_expected = nx * ny * nz
    vals = list(values or [])

    if len(vals) < nx * ny:
        return None

    # Trim/pad to grid size.
    vals = vals[:n_expected]

    if len(vals) < n_expected:
        vals = vals + [None] * (n_expected - len(vals))

    # Assume GRDECL flat order is I fastest, then J, then K.
    # Build a vertical-average top-view map: z[j][i] averaged over K.
    z = []

    for j in range(ny):
        row = []
        for i in range(nx):
            col = []
            for k in range(nz):
                idx = k * nx * ny + j * nx + i
                try:
                    v = vals[idx]
                    if v is not None:
                        fv = float(v)
                        if math.isfinite(fv):
                            col.append(fv)
                except Exception:
                    pass

            if col:
                row.append(sum(col) / len(col))
            else:
                row.append(None)

        z.append(row)

    return z


def _v378_make_map_plotly(prop: str, z, grid_info, source_file: str):
    title = f"{prop} map - vertical average"

    return {
        "type": "plotly_chart",
        "title": title,
        "data": [
            {
                "z": z,
                "type": "heatmap",
                "colorscale": [
                    [0.00, "#081427"],
                    [0.20, "#123B63"],
                    [0.40, "#1D74A8"],
                    [0.60, "#22D3EE"],
                    [0.80, "#A78BFA"],
                    [1.00, "#FBBF24"],
                ],
                "colorbar": {
                    "title": prop
                },
                "hovertemplate": "I=%{x}<br>J=%{y}<br>" + prop + "=%{z:.4g}<extra></extra>",
            }
        ],
        "layout": {
            "title": title,
            "xaxis": {"title": "I index"},
            "yaxis": {"title": "J index", "autorange": "reversed"},
            "height": 620,
            "margin": {"l": 70, "r": 70, "t": 72, "b": 76},
        },
        "config": {
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True,
        },
        "meta": {
            "property": prop,
            "grid_dimensions": grid_info,
            "source_file": source_file,
            "map_method": "vertical_average_over_K",
        },
    }


try:
    _generic_static_plot_agent_answer_original_v378 = answer_generic_plot_request

    def answer_generic_plot_request(message: str) -> dict:
        if _is_holistic_diagnostic_query_v413(message):
            return _generic_static_plot_agent_answer_original_v378(message)

        if _v378_is_map_request(message):
            prop = _v378_detect_map_property(message)

            if not prop:
                return {
                    "ok": False,
                    "message": (
                        "I understood that you want a property map, but I could not identify the property. "
                        "Try for example: 'show me SWAT map at initial', 'show me pressure map at final', "
                        "'show me PERM_X map'."
                    ),
                }

            grid = _v378_load_grid_dimensions()

            if not grid:
                return {
                    "ok": False,
                    "message": "I found the property request, but I could not find grid_dimensions.json."
                }

            path = _v378_find_grdecl_property_file(prop)

            if not path:
                return {
                    "ok": False,
                    "message": f"I could not find a GRDECL file for {prop}. Expected something like {prop}.GRDECL."
                }

            values = _parse_grdecl_values(path)

            if not values:
                return {
                    "ok": False,
                    "message": f"I found {path.name}, but could not parse numeric GRDECL values."
                }

            z = _v378_values_to_top_map(values, grid["nx"], grid["ny"], grid["nz"])

            if z is None:
                return {
                    "ok": False,
                    "message": (
                        f"I found {path.name}, but could not reshape it into a map using "
                        f"NX={grid['nx']}, NY={grid['ny']}, NZ={grid['nz']}."
                    )
                }

            chart = _v378_make_map_plotly(prop, z, grid, str(path))

            return {
                "ok": True,
                "message": (
                    f"Created interactive {prop} map using {path.name}. "
                    "The displayed map is a vertical average over K layers."
                ),
                "source": "interactive_grdecl_map_v378",
                "plotly_chart": chart,
                "image_url": None,
                "plot": {
                    "property": prop,
                    "plot_type": "map",
                    "source_file": str(path),
                    "grid_dimensions": grid,
                    "map_method": "vertical_average_over_K",
                    "interactive": True,
                },
            }

        return _generic_static_plot_agent_answer_original_v378(message)

except NameError:
    pass

