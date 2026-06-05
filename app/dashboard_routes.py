from fastapi import APIRouter
from app.well_insight import get_kpi_summary, get_well_insight
from pydantic import BaseModel

from app.agent_orchestrator import run_agent_orchestration
from app.dashboard_data import (
    get_summary_cards,
    get_well_map,
    get_well_detail,
    get_top_mismatches,
    get_area_summary,
    get_corridor_candidates,
)
from app.chat_router import answer_question
from app.profile_plotter import create_profile_plot
from app.profile_series import get_profile_series
from app.visual_payloads import get_visual_hm_map, get_property_visual_map, get_transmissibility_corridor_visual, get_available_property_layers
from app.cell_property_layers import build_cell_property_layer, list_cell_property_layers
from app.streamline_visual_payloads import build_streamline_visual_payload
from app.hm_map_payload import build_hm_map_payload


router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/api/run-diagnostics")
def api_run_diagnostics():
    return run_agent_orchestration(clear_previous_logs=True)


@router.get("/api/dashboard/summary")
def api_summary():
    return get_summary_cards()


@router.get("/api/dashboard/wells")
def api_wells(variable: str = "overall"):
    return get_well_map(variable)


@router.get("/api/dashboard/well/{well}")
def api_well_detail(well: str):
    return get_well_detail(well)


@router.get("/api/dashboard/top-mismatches")
def api_top_mismatches(variable: str = "water", limit: int = 10):
    return get_top_mismatches(variable, limit)


@router.get("/api/dashboard/area/{area}")
def api_area(area: str):
    return get_area_summary(area)


@router.get("/api/dashboard/corridors")
def api_corridors():
    return get_corridor_candidates()


@router.get("/api/dashboard/profile-plot/{well}")
def api_profile_plot(well: str, variable: str = "water"):
    return create_profile_plot(well=well, variable=variable)


@router.get("/api/dashboard/profile-series/{well}")
def api_profile_series(well: str, variable: str = "water"):
    return get_profile_series(well=well, variable=variable)




@router.get("/api/dashboard/hm-map")
def api_hm_map():
    return build_hm_map_payload()



@router.get("/api/visual/hm-map")
def api_visual_hm_map(variable: str = "overall"):
    return get_visual_hm_map(variable=variable)


@router.get("/api/visual/property-map")
def api_visual_property_map(property_name: str = "mean_tran_h", variable: str = "overall"):
    return get_property_visual_map(property_name=property_name, variable=variable)


@router.get("/api/visual/transmissibility-corridors")
def api_visual_transmissibility_corridors(well: str = None):
    return get_transmissibility_corridor_visual(well=well)


@router.get("/api/visual/properties")
def api_visual_properties():
    return get_available_property_layers()



@router.get("/api/visual/cell-property-layer")
def api_cell_property_layer(property_name: str = "TRAN_H"):
    return build_cell_property_layer(property_name)


@router.get("/api/visual/cell-property-layers")
def api_cell_property_layers():
    return list_cell_property_layers()



@router.get("/api/visual/streamlines")
def api_visual_streamlines():
    return build_streamline_visual_payload()



@router.get("/api/dashboard/kpi-summary")
def api_dashboard_kpi_summary():
    return get_kpi_summary()


@router.get("/api/dashboard/well-insight")
def api_dashboard_well_insight(well: str):
    return get_well_insight(well)



# ==========================================================
# V351 CHAT VARIABLE-BIAS INTERCEPT
# Force /api/chat to answer over/under-estimation questions
# using the real profile_series audit, not stale HM diagnostics.
# ==========================================================
def _api_chat_variable_bias_answer_v351(message: str):
    msg = str(message or "").lower()

    variable = None
    if any(x in msg for x in ["water", "acqua", "wct", "wwct", "wwpr"]):
        variable = "water"
    elif any(x in msg for x in ["oil", "olio", "wopr", "wopt"]):
        variable = "oil"
    elif any(x in msg for x in ["gas", "gor", "wgpr", "wgor"]):
        variable = "gas"
    elif any(x in msg for x in ["pressure", "pressione", "bhp", "wbhp", "fpr"]):
        variable = "pressure"

    if variable is None:
        return None

    wants_over = any(x in msg for x in [
        "overestimat", "over-estimat", "over predict", "overpredict",
        "sovrastim", "simulated above", "sim > obs", "simulata sopra",
        "too high", "troppo alta", "troppa acqua"
    ])

    wants_under = any(x in msg for x in [
        "underestimat", "under-estimat", "under predict", "underpredict",
        "sottostim", "simulated below", "sim < obs", "simulata sotto",
        "too low", "troppo bassa", "poca acqua"
    ])

    if not wants_over and not wants_under:
        return None

    try:
        from app.variable_bias_direction import summarize_variable_bias

        rows = summarize_variable_bias(variable)

        if wants_over:
            target_direction = f"overestimated_{variable}"
            selected = [r for r in rows if r.get("direction") == target_direction]
            selected = sorted(selected, key=lambda r: float(r.get("relative_bias") or 0), reverse=True)
            title = f"Wells overestimating {variable}"
        else:
            target_direction = f"underestimated_{variable}"
            selected = [r for r in rows if r.get("direction") == target_direction]
            selected = sorted(selected, key=lambda r: float(r.get("relative_bias") or 0))
            title = f"Wells underestimating {variable}"

        if not selected:
            answer = (
                f"I did not find wells classified as {target_direction.replace('_', ' ')} "
                f"using the real profile-series audit. This result is based on the same "
                f"Observed vs Simulated profile data used by the interactive Plotly charts."
            )
            return {
                "ok": True,
                "answer": answer,
                "message": answer,
                "response": answer,
                "source": "variable_bias_audit_v351",
                "variable": variable,
                "rows": [],
            }

        direction_word = "higher than" if wants_over else "lower than"
        practical_meaning = "over-predicting" if wants_over else "under-predicting"

        variable_label = {
            "water": "water production / WCT response",
            "oil": "oil production",
            "gas": "gas production",
            "pressure": "pressure / BHP",
        }.get(variable, variable)

        lines = [
            f"I found {len(selected)} well(s) where the simulated {variable_label} is {direction_word} the observed profile in the late-history period.",
            "",
            f"In practical terms, these wells are **{practical_meaning} {variable}** in the model compared with history.",
            "",
            "Most relevant wells:",
        ]

        for r in selected[:10]:
            sim_v = float(r["sim_mean_tail"])
            obs_v = float(r["obs_mean_tail"])
            rel_v = float(r["relative_bias"])

            if abs(obs_v) > 1e-12:
                pct_vs_obs = (sim_v - obs_v) / abs(obs_v) * 100.0
                if pct_vs_obs >= 0:
                    bias_txt = f"simulated is {abs(pct_vs_obs):.1f}% higher than observed"
                else:
                    bias_txt = f"simulated is {abs(pct_vs_obs):.1f}% lower than observed"
            else:
                # If observed is zero/near-zero, percentage vs observed is not meaningful.
                # Use the normalized profile bias instead.
                if rel_v >= 0:
                    bias_txt = f"simulated is above observed; normalized bias = {abs(rel_v) * 100.0:.1f}%"
                else:
                    bias_txt = f"simulated is below observed; normalized bias = {abs(rel_v) * 100.0:.1f}%"

            lines.append(
                f"- **{r['well']}**: {bias_txt}. "
                f"Late-history average: simulated = {sim_v:.1f}, observed = {obs_v:.1f} "
                f"({int(float(r['pairs_found']))} profile points)."
            )

        if len(selected) > 10:
            lines.append(f"\nI am showing the first 10 of {len(selected)} wells, ranked by mismatch severity.")

        if variable == "water" and wants_over:
            lines.append(
                "\nReservoir interpretation: the model is bringing too much water, or bringing water too early/too strongly, "
                "compared with the observed profile. First checks should be water-front position, local connectivity/TRAN, "
                "completion intervals and nearby injector/aquifer support. RelPerm/SATNUM should be considered mainly if the same pattern is regional."
            )
        elif variable == "water" and wants_under:
            lines.append(
                "\nReservoir interpretation: the model is not bringing enough water, or water breakthrough is delayed. "
                "First checks should be missing connectivity, low local/fault TRAN, completion connection, water-front position and injector/aquifer support."
            )
        elif variable == "oil" and wants_over:
            lines.append(
                "\nReservoir interpretation: the model is producing too much oil compared with history. Check PI/productivity, pressure support, controls, KH and local depletion."
            )
        elif variable == "oil" and wants_under:
            lines.append(
                "\nReservoir interpretation: the model is producing too little oil compared with history. Check productivity, completion KH, local pressure, constraints and connectivity."
            )
        elif variable == "gas" and wants_over:
            lines.append(
                "\nReservoir interpretation: the model is producing too much gas. Check gas-cap communication, GOR behaviour, vertical connectivity, completions and PVT/relperm assumptions."
            )
        elif variable == "gas" and wants_under:
            lines.append(
                "\nReservoir interpretation: the model is producing too little gas. Check gas mobility, gas-cap connection, completion intervals, constraints and PVT/relperm assumptions."
            )
        elif variable == "pressure" and wants_over:
            lines.append(
                "\nReservoir interpretation: simulated pressure/BHP is too high compared with observed data. The model may have too much pressure support, too weak depletion, or overly strong connectivity/injection support."
            )
        elif variable == "pressure" and wants_under:
            lines.append(
                "\nReservoir interpretation: simulated pressure/BHP is too low compared with observed data. The model may be depleting too fast, lacking pressure support, or missing connectivity/injection/aquifer support."
            )

        lines.append(
            "\nMethod: this answer uses the same Observed vs Simulated profile-series source used by the interactive Plotly plots. "
            "The classification is based on the late-history average profile bias; positive bias means simulated is above observed."
        )

        answer = "\n".join(lines)

        return {
            "ok": True,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "variable_bias_audit_v351",
            "variable": variable,
            "direction": target_direction,
            "rows": selected,
        }

    except Exception as exc:
        answer = f"Variable-bias audit failed: {exc}"
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "variable_bias_audit_v351",
        }




# ==========================================================
# V354 GENERIC STATIC PLOT CHAT INTERCEPT
# Handles requests like cumulative plots and property distributions.
# ==========================================================
def _api_chat_generic_static_plot_v354(message: str):
    try:
        from app.generic_static_plot_agent import handle_static_plot_request

        result = handle_static_plot_request(message)

        if result is None:
            return None

        if not result.get("ok"):
            answer = result.get("message", "I could not create the requested plot.")
            return {
                "ok": False,
                "answer": answer,
                "message": answer,
                "response": answer,
                "source": "generic_static_plot_v354",
            }

        image_url = result.get("image_url")
        plotly_chart = result.get("plotly_chart")
        answer = result.get("message", "Plot created.")

        # V358: if an interactive Plotly payload exists, do not expose the PNG fallback.
        # This prevents the dashboard from rendering both the static image and the interactive chart.
        if plotly_chart:
            image_url = None
            result["image_url"] = None
            answer += "\n\nInteractive plot rendered below."
        elif image_url:
            answer += f"\n\nPlot image: {image_url}"

        return {
            "ok": True,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "generic_interactive_plot_v358",
            "image_url": image_url,
            "plotly_chart": plotly_chart,
            "plot": result,
        }

    except Exception as exc:
        answer = f"Generic plot engine failed: {exc}"
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "generic_static_plot_v354",
        }




# ==========================================================
# V362 UNIVERSAL INTERACTIVE PROFILE PLOT
# Handles oil/water/gas/pressure profile and cumulative plots
# before the old SMSPEC/UNSMRY PNG fallback router.
# ==========================================================
def _api_chat_universal_interactive_plot_v362(message: str):
    import re
    import math

    msg_raw = str(message or "")
    msg = msg_raw.lower()

    is_plot_request = any(x in msg for x in [
        "plot", "chart", "show me", "display", "draw",
        "profile", "profiles", "rate", "cumulative", "cumulate",
        "grafico", "fammi vedere", "mostrami", "profilo", "cumulata"
    ])

    if not is_plot_request:
        return None

    well_match = re.search(r"\b([A-Z]{1,5}-\d+[A-Z]?)\b", msg_raw.upper())
    if not well_match:
        return None

    well = well_match.group(1)

    variable = None

    # V370 precise variable intent.
    # Important: WCT and GOR are ratios, not generic water/gas rate.
    if any(x in msg for x in ["water cut", "wct", "wwct", "watercut", "water-cut"]):
        variable = "water_cut"
    elif any(x in msg for x in ["gor", "gas oil ratio", "gas-oil ratio", "wgor"]):
        variable = "gor"
    elif any(x in msg for x in ["water rate", "wwpr", "water production rate", "acqua rate", "portata acqua"]):
        variable = "water_rate"
    elif any(x in msg for x in ["oil rate", "wopr", "oil production rate", "olio rate", "portata olio"]):
        variable = "oil_rate"
    elif any(x in msg for x in ["gas rate", "wgpr", "gas production rate", "portata gas"]):
        variable = "gas_rate"
    elif any(x in msg for x in ["pressure", "pressione", "bhp", "wbhp", "fpr"]):
        variable = "pressure"
    elif any(x in msg for x in ["water", "acqua", "wwpt"]):
        # Generic "water" defaults to water rate, unless WCT was explicitly requested above.
        variable = "water_rate"
    elif any(x in msg for x in ["oil", "olio", "wopt"]):
        variable = "oil_rate"
    elif any(x in msg for x in ["gas", "wgpt"]):
        variable = "gas_rate"

    if variable is None:
        return None

    plot_type = "cumulative" if any(x in msg for x in [
        "cumulative", "cumulate", "cumulated", "cumulativo", "cumulata", "cum "
    ]) else "profile"

    variable_candidates = {
        "oil_rate": ["oil_rate", "oil", "wopr", "WOPR", "oil production", "oil_profile"],
        "water_rate": ["water_rate", "water", "wwpr", "WWPR", "water production", "water_profile"],
        "gas_rate": ["gas_rate", "gas", "wgpr", "WGPR", "gas production", "gas_profile"],
        "water_cut": ["water_cut", "wct", "WCT", "wwct", "WWCT", "watercut"],
        "gor": ["gor", "GOR", "wgor", "WGOR", "gas_oil_ratio", "gas oil ratio"],
        "pressure": ["pressure", "bhp", "wbhp", "WBHP", "fpr", "pressure_profile"],
    }[variable]

    def as_float_list(values):
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

    def cumulative(values):
        total = 0.0
        out = []
        for v in values:
            if v is None:
                out.append(total)
            else:
                try:
                    fv = float(v)
                    if math.isfinite(fv):
                        total += fv
                except Exception:
                    pass
                out.append(total)
        return out

    def extract_arrays(payload):
        if not isinstance(payload, dict):
            return None

        # Prefer existing robust extractor if available.
        try:
            from app.dynamic_profile_agent import extract_arrays_from_profile_series_payload
            ex = extract_arrays_from_profile_series_payload(payload)
            if isinstance(ex, dict):
                sim = as_float_list(ex.get("simulated") or ex.get("sim") or ex.get("model"))
                obs = as_float_list(ex.get("observed") or ex.get("obs") or ex.get("history") or ex.get("hist"))
                x = ex.get("x") or ex.get("dates") or ex.get("time")
                n = min(len(sim), len(obs), len(x) if isinstance(x, list) else 10**9)
                if n >= 3:
                    return {
                        "x": x[:n] if isinstance(x, list) else list(range(n)),
                        "simulated": sim[:n],
                        "observed": obs[:n],
                    }
        except Exception:
            pass

        # Fallback to series/traces/data.
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
            y = as_float_list(item.get("y") or item.get("values") or item.get("data"))
            x_raw = item.get("x") or item.get("dates") or item.get("time")

            if not y or sum(v is not None for v in y) < 3:
                continue

            if x is None and isinstance(x_raw, list):
                x = x_raw

            if any(k in name for k in ["obs", "observed", "hist", "history", "measured"]):
                obs = y
            elif any(k in name for k in ["sim", "simulated", "model"]):
                sim = y

        if obs is not None and sim is not None:
            n = min(len(obs), len(sim), len(x) if isinstance(x, list) else 10**9)
            if n >= 3:
                return {
                    "x": x[:n] if isinstance(x, list) else list(range(n)),
                    "simulated": sim[:n],
                    "observed": obs[:n],
                }

        return None

    arrays = None
    resolved_variable = None

    try:
        from app.profile_series import get_profile_series

        def get_arrays_for_candidates(candidates):
            for candidate in candidates:
                try:
                    payload = get_profile_series(well=well, variable=candidate)
                    candidate_arrays = extract_arrays(payload)

                    if candidate_arrays:
                        valid = sum(
                            1 for s, o in zip(candidate_arrays["simulated"], candidate_arrays["observed"])
                            if s is not None and o is not None
                        )
                        if valid >= 3:
                            candidate_arrays["resolved_variable"] = candidate
                            return candidate_arrays
                except Exception:
                    continue
            return None

        def safe_div(num, den, scale=1.0):
            out = []
            for a, b in zip(num, den):
                try:
                    if a is None or b is None or abs(float(b)) < 1e-12:
                        out.append(None)
                    else:
                        out.append(float(a) / float(b) * scale)
                except Exception:
                    out.append(None)
            return out

        def align_two_profiles_by_x(a, b):
            """
            Align two profile arrays by x/date instead of assuming same index.
            This avoids wrong WCT/GOR if oil/water/gas profiles have missing points
            or slightly different date vectors.
            """
            if not a or not b:
                return None

            ax = [str(v) for v in a.get("x", [])]
            bx = [str(v) for v in b.get("x", [])]

            if not ax or not bx:
                return None

            a_map = {}
            for i, xval in enumerate(ax):
                if i < len(a.get("simulated", [])) and i < len(a.get("observed", [])):
                    a_map[xval] = {
                        "sim": a["simulated"][i],
                        "obs": a["observed"][i],
                    }

            b_map = {}
            for i, xval in enumerate(bx):
                if i < len(b.get("simulated", [])) and i < len(b.get("observed", [])):
                    b_map[xval] = {
                        "sim": b["simulated"][i],
                        "obs": b["observed"][i],
                    }

            common_x = [x for x in ax if x in b_map and x in a_map]

            if len(common_x) < 3:
                return None

            return {
                "x": common_x,
                "a_sim": [a_map[x]["sim"] for x in common_x],
                "a_obs": [a_map[x]["obs"] for x in common_x],
                "b_sim": [b_map[x]["sim"] for x in common_x],
                "b_obs": [b_map[x]["obs"] for x in common_x],
            }

        def numeric_min_max(values):
            clean = []
            for v in values or []:
                try:
                    if v is not None:
                        clean.append(float(v))
                except Exception:
                    pass
            if not clean:
                return None, None
            return min(clean), max(clean)

        def arrays_too_similar(a_values, b_values, tolerance=1e-9):
            """
            Guard against a bad fallback where oil and water, or gas and oil,
            resolve to the same time series. This was causing WCT = 50% flat.
            """
            pairs = []
            for a, b in zip(a_values or [], b_values or []):
                try:
                    if a is not None and b is not None:
                        pairs.append((float(a), float(b)))
                except Exception:
                    pass

            if len(pairs) < 10:
                return False

            same = 0
            for a, b in pairs:
                scale = max(abs(a), abs(b), 1.0)
                if abs(a - b) <= tolerance * scale:
                    same += 1

            return same / len(pairs) > 0.95

        def ratio_profile_debug(arrays):
            if not arrays:
                return {}
            return {
                "points": len(arrays.get("x", [])),
                "sim_min": numeric_min_max(arrays.get("simulated", []))[0],
                "sim_max": numeric_min_max(arrays.get("simulated", []))[1],
                "obs_min": numeric_min_max(arrays.get("observed", []))[0],
                "obs_max": numeric_min_max(arrays.get("observed", []))[1],
                "resolved_variable": arrays.get("resolved_variable"),
            }

        # V371: WCT and GOR must not fall back to water/gas rate.
        # If direct WCT/GOR is unavailable, compute from oil/water/gas rates.
        if variable == "water_cut":
            # V373: use strict rate series for WCT. Do not accept generic fallback
            # that can return the same profile for oil and water.
            oil_arrays = get_arrays_for_candidates(["WOPR", "wopr", "oil_rate", "oil"])
            water_arrays = get_arrays_for_candidates(["WWPR", "wwpr", "water_rate", "water"])

            ratio_source_debug = {
                "oil": ratio_profile_debug(oil_arrays),
                "water": ratio_profile_debug(water_arrays),
            }

            aligned = align_two_profiles_by_x(oil_arrays, water_arrays)

            if aligned and (
                arrays_too_similar(aligned["a_sim"], aligned["b_sim"]) or
                arrays_too_similar(aligned["a_obs"], aligned["b_obs"])
            ):
                aligned = None
                ratio_source_debug["rejected_reason"] = "oil and water resolved to nearly identical time series; refusing flat 50% WCT fallback"

            if aligned:
                oil_sim = aligned["a_sim"]
                oil_obs = aligned["a_obs"]
                water_sim = aligned["b_sim"]
                water_obs = aligned["b_obs"]

                sim_total_liq = []
                obs_total_liq = []

                for o, w in zip(oil_sim, water_sim):
                    try:
                        sim_total_liq.append((float(o) if o is not None else 0.0) + (float(w) if w is not None else 0.0))
                    except Exception:
                        sim_total_liq.append(None)

                for o, w in zip(oil_obs, water_obs):
                    try:
                        obs_total_liq.append((float(o) if o is not None else 0.0) + (float(w) if w is not None else 0.0))
                    except Exception:
                        obs_total_liq.append(None)

                # V372: plot WCT in percent for readability.
                sim_wct_pct = safe_div(water_sim, sim_total_liq, scale=100.0)
                obs_wct_pct = safe_div(water_obs, obs_total_liq, scale=100.0)

                arrays = {
                    "x": aligned["x"],
                    "simulated": sim_wct_pct,
                    "observed": obs_wct_pct,
                }
                resolved_variable = "computed_WCT_percent_from_WWPR_over_WOPR_plus_WWPR_aligned_by_date"

            # Only if computed WCT fails, try direct WCT. Do not accept generic water fallback.
            if not arrays:
                direct = get_arrays_for_candidates(["water_cut", "wct", "WCT", "wwct", "WWCT", "watercut"])
                if direct and str(direct.get("resolved_variable", "")).lower() in {"water_cut", "wct", "wwct", "watercut"}:
                    arrays = direct
                    resolved_variable = direct.get("resolved_variable")

            plot_type = "profile"

        elif variable == "gor":
            # V373: use strict rate series for GOR. Do not accept generic fallback.
            oil_arrays = get_arrays_for_candidates(["WOPR", "wopr", "oil_rate", "oil"])
            gas_arrays = get_arrays_for_candidates(["WGPR", "wgpr", "gas_rate", "gas"])

            ratio_source_debug = {
                "oil": ratio_profile_debug(oil_arrays),
                "gas": ratio_profile_debug(gas_arrays),
            }

            aligned = align_two_profiles_by_x(oil_arrays, gas_arrays)

            if aligned and (
                arrays_too_similar(aligned["a_sim"], aligned["b_sim"]) or
                arrays_too_similar(aligned["a_obs"], aligned["b_obs"])
            ):
                aligned = None
                ratio_source_debug["rejected_reason"] = "oil and gas resolved to nearly identical time series; refusing invalid GOR fallback"

            if aligned:
                oil_sim = aligned["a_sim"]
                oil_obs = aligned["a_obs"]
                gas_sim = aligned["b_sim"]
                gas_obs = aligned["b_obs"]

                arrays = {
                    "x": aligned["x"],
                    "simulated": safe_div(gas_sim, oil_sim),
                    "observed": safe_div(gas_obs, oil_obs),
                }
                resolved_variable = "computed_GOR_from_WGPR_over_WOPR_aligned_by_date"

            # Only if computed GOR fails, try direct GOR. Do not accept generic gas fallback.
            if not arrays:
                direct = get_arrays_for_candidates(["gor", "GOR", "wgor", "WGOR", "gas_oil_ratio"])
                if direct and str(direct.get("resolved_variable", "")).lower() in {"gor", "wgor", "gas_oil_ratio"}:
                    arrays = direct
                    resolved_variable = direct.get("resolved_variable")

            plot_type = "profile"

        else:
            arrays = get_arrays_for_candidates(variable_candidates)
            if arrays:
                resolved_variable = arrays.get("resolved_variable")

    except Exception as exc:
        answer = f"I could not load profile-series data: {exc}"
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "universal_interactive_plot_v362",
        }

    if not arrays:
        answer = f"I could not find valid Observed vs Simulated profile data for {well} / {variable}."
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "universal_interactive_plot_v362",
        }

    x = arrays["x"]
    sim = arrays["simulated"]
    obs = arrays["observed"]
    n = min(len(x), len(sim), len(obs))

    x = x[:n]
    sim = sim[:n]
    obs = obs[:n]

    variable_display = {
        "oil_rate": "Oil Rate",
        "water_rate": "Water Rate",
        "gas_rate": "Gas Rate",
        "water_cut": "Water Cut",
        "gor": "Gas-Oil Ratio",
        "pressure": "Pressure / BHP",
    }

    unit_by_variable = {
        "oil_rate": {
            "profile": "Oil Rate (STB/d)",
            "cumulative": "Cumulative Oil (STB)",
        },
        "water_rate": {
            "profile": "Water Rate (STB/d)",
            "cumulative": "Cumulative Water (STB)",
        },
        "gas_rate": {
            "profile": "Gas Rate (MSCF/d)",
            "cumulative": "Cumulative Gas (MSCF)",
        },
        "water_cut": {
            "profile": "Water Cut (%)",
            "cumulative": "Cumulative Water Cut (%·step)",
        },
        "gor": {
            "profile": "Gas-Oil Ratio (MSCF/STB)",
            "cumulative": "Cumulative GOR (MSCF/STB·step)",
        },
        "pressure": {
            "profile": "Pressure / BHP (psi)",
            "cumulative": "Cumulative Pressure (psi·step)",
        },
    }

    display_name = variable_display.get(variable, variable)

    if plot_type == "cumulative":
        sim_y = cumulative(sim)
        obs_y = cumulative(obs)
        title = f"{well} - Cumulative {display_name}"
        y_title = unit_by_variable.get(variable, {}).get("cumulative", f"Cumulative {display_name}")
    else:
        sim_y = sim
        obs_y = obs
        title = f"{well} - {display_name}"
        y_title = unit_by_variable.get(variable, {}).get("profile", display_name)

    plotly_chart = {
        "type": "plotly_chart",
        "title": title,
        "data": [
            {
                "x": x,
                "y": obs_y,
                "type": "scatter",
                "mode": "lines",
                "name": "Observed",
            },
            {
                "x": x,
                "y": sim_y,
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
            "height": 560,
            "margin": {"l": 78, "r": 34, "t": 72, "b": 86},
        },
        "config": {
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True,
        },
    }

    answer = (
        f"Created interactive {plot_type} plot for {well} / {display_name}. "
        f"Resolved profile variable: {resolved_variable}. "
        "Interactive plot rendered below."
    )

    return {
        "ok": True,
        "answer": answer,
        "message": answer,
        "response": answer,
        "source": "universal_interactive_plot_v362",
        "plotly_chart": plotly_chart,
        "image_url": None,
        "plot": {
            "well": well,
            "variable": variable,
            "resolved_profile_variable": resolved_variable,
            "plot_type": plot_type,
            "points": n,
            "interactive": True,
            "sim_min": numeric_min_max(sim_y)[0],
            "sim_max": numeric_min_max(sim_y)[1],
            "obs_min": numeric_min_max(obs_y)[0],
            "obs_max": numeric_min_max(obs_y)[1],
            "ratio_source_debug": locals().get("ratio_source_debug", None),
        },
    }




# ==========================================================
# V379 DIRECT CHAT ROUTER FOR GRDECL PROPERTY MAPS
# Intercepts map requests before old generic plot fallback.
# Examples:
# - show me SWAT map at initial
# - show me SWAT map at final
# - show me pressure map at initial
# - show me PERM_X map
# ==========================================================
def _api_chat_direct_grdecl_map_v379(message: str):
    msg = str(message or "").lower().replace("_", " ").replace("-", " ")

    is_map = any(x in msg for x in [
        " map", "map ", "mappa", "heatmap", "property map",
        "show me swat", "show swat", "show me pressure",
        "show me perm", "show me poro", "show me tran",
    ])

    if not is_map:
        return None

    try:
        from app import generic_static_plot_agent as g
    except Exception as exc:
        answer = f"I understood that you want a map, but the map engine could not be imported: {exc}"
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "direct_grdecl_map_v379",
        }

    # Use V378 map functions if present.
    required = [
        "_v378_detect_map_property",
        "_v378_load_grid_dimensions",
        "_v378_find_grdecl_property_file",
        "_v378_values_to_top_map",
        "_v378_make_map_plotly",
    ]

    missing = [name for name in required if not hasattr(g, name)]

    if missing:
        answer = (
            "I understood that you want a GRDECL property map, but the V378 map functions "
            f"are not loaded in generic_static_plot_agent.py. Missing: {', '.join(missing)}"
        )
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "direct_grdecl_map_v379",
        }

    prop = g._v378_detect_map_property(message)

    if not prop:
        answer = (
            "I understood that you want a property map, but I could not identify the property. "
            "Try: 'show me SWAT map at initial', 'show me SWAT map at final', "
            "'show me pressure map at initial', 'show me PERM_X map', or 'show me PORO map'."
        )
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "direct_grdecl_map_v379",
        }

    grid = g._v378_load_grid_dimensions()

    if not grid:
        answer = "I identified the requested map, but I could not find grid_dimensions.json."
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "direct_grdecl_map_v379",
            "property": prop,
        }

    path = g._v378_find_grdecl_property_file(prop)

    if not path:
        answer = f"I identified the property as {prop}, but I could not find {prop}.GRDECL."
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "direct_grdecl_map_v379",
            "property": prop,
            "grid_dimensions": grid,
        }

    values = g._parse_grdecl_values(path)

    if not values:
        answer = f"I found {path.name}, but I could not parse numeric GRDECL values."
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "direct_grdecl_map_v379",
            "property": prop,
            "source_file": str(path),
        }

    z = g._v378_values_to_top_map(values, grid["nx"], grid["ny"], grid["nz"])

    if z is None:
        answer = (
            f"I found {path.name}, but could not reshape it using "
            f"NX={grid['nx']}, NY={grid['ny']}, NZ={grid['nz']}."
        )
        return {
            "ok": False,
            "answer": answer,
            "message": answer,
            "response": answer,
            "source": "direct_grdecl_map_v379",
            "property": prop,
            "source_file": str(path),
            "grid_dimensions": grid,
        }

    chart = g._v378_make_map_plotly(prop, z, grid, str(path))

    answer = (
        f"Created interactive {prop} map using {path.name}. "
        "The displayed map is a vertical average over K layers."
    )

    return {
        "ok": True,
        "answer": answer,
        "message": answer,
        "response": answer,
        "source": "direct_grdecl_map_v379",
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


@router.post("/api/chat")
def api_chat(req: ChatRequest):
    try:
        from app.plot_intent_engine import answer_plot_intent
        v380_plot = answer_plot_intent(req.message)
        if v380_plot is not None:
            return v380_plot
    except Exception as exc:
        # Do not break chat if the plot intent engine fails unexpectedly.
        pass
    v379_map = _api_chat_direct_grdecl_map_v379(req.message)
    if v379_map is not None:
        return v379_map
    v362_plot = _api_chat_universal_interactive_plot_v362(req.message)
    if v362_plot is not None:
        return v362_plot
    v354_plot_answer = _api_chat_generic_static_plot_v354(req.message)
    if v354_plot_answer is not None:
        return v354_plot_answer

    v351_answer = _api_chat_variable_bias_answer_v351(req.message)
    if v351_answer is not None:
        return v351_answer

    return answer_question(req.message)



# ==========================================================
# SMART WELL RECOMMENDATIONS API V41
# ==========================================================
@router.get("/api/smart-well-recommendations")
def api_smart_well_recommendations():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    p = root / "artifacts" / "diagnosis" / "smart_well_recommendations.json"

    if not p.exists():
        return {
            "ok": False,
            "message": "smart_well_recommendations.json not found. Run: python -m app.smart_well_recommendation_agent",
            "recommendations": {},
        }

    return {
        "ok": True,
        "recommendations": json.loads(p.read_text(encoding="utf-8")),
    }



# ==========================================================
# TRAN CORRIDOR IXF EXPORT API V44
# ==========================================================
@router.get("/api/tran-corridor-candidate/{well}")
def api_tran_corridor_candidate(well: str):
    from app.tran_corridor_export_agent import build_ixf_content

    result = build_ixf_content(well)
    # Do not return full content in candidate preview.
    result.pop("content", None)
    return result


@router.get("/api/export-tran-corridor-ixf/{well}")
def api_export_tran_corridor_ixf(well: str):
    from app.tran_corridor_export_agent import export_ixf_file

    return export_ixf_file(well)



# ==========================================================
# RELPERM MOBILITY API V59
# ==========================================================

@router.get("/api/relperm/intake-summary")
def api_relperm_intake_summary():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    p = root / "artifacts" / "relperm" / "relperm_intake_summary.json"

    if not p.exists():
        return {
            "ok": False,
            "message": "RelPerm artifacts not found. Run: python -m app.relperm_mobility_agent",
        }

    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/api/relperm/mapping")
def api_relperm_mapping():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    p = root / "artifacts" / "relperm" / "relperm_region_mapping_proposed.json"

    if not p.exists():
        return {
            "ok": False,
            "message": "RelPerm mapping not found. Run: python -m app.relperm_mobility_agent",
            "rows": [],
        }

    d = json.loads(p.read_text(encoding="utf-8"))
    d["ok"] = True
    return d


@router.get("/api/relperm/curves")
def api_relperm_curves():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    p = root / "artifacts" / "relperm" / "relperm_curves.json"

    if not p.exists():
        return {
            "ok": False,
            "message": "RelPerm curves not found. Run: python -m app.relperm_mobility_agent",
            "models": {},
        }

    d = json.loads(p.read_text(encoding="utf-8"))
    d["ok"] = True
    return d



# ==========================================================
# RELPERM SENSITIVITY EXPORT API V60
# ==========================================================

@router.get("/api/relperm/sensitivity/{well}")
def api_relperm_sensitivity(well: str):
    from app.relperm_sensitivity_agent import build_relperm_sensitivity_cached_v96

    return build_relperm_sensitivity_cached_v96(well)


@router.get("/api/relperm/export-ixf/{well}")
def api_relperm_export_ixf(well: str):
    from app.relperm_sensitivity_agent import export_relperm_ixf_candidate

    return export_relperm_ixf_candidate(well)



# ==========================================================
# AGENT COLLABORATION LOG API V010
# Returns recent multi-agent collaboration trace records for dashboard/demo.
# ==========================================================
@router.get("/api/agent-collaboration-log")
def api_agent_collaboration_log(limit: int = 8):
    import json
    from pathlib import Path

    p = Path("logs/agent_collaboration_trace.jsonl")

    if not p.exists():
        return {
            "ok": True,
            "records": [],
            "message": "No agent collaboration logs found yet. Ask a question first.",
        }

    try:
        lines = p.read_text(encoding="utf-8").splitlines()
        records = []

        for line in lines[-max(1, min(limit, 50)):]:
            try:
                records.append(json.loads(line))
            except Exception:
                continue

        return {
            "ok": True,
            "records": records,
            "count": len(records),
            "source": "logs/agent_collaboration_trace.jsonl",
        }

    except Exception as exc:
        return {
            "ok": False,
            "records": [],
            "message": str(exc),
        }



# ==========================================================
# LANGGRAPH ACTIVE NODE GRAPH TEST API V013
# Test endpoint for the real node-based LangGraph orchestrator.
# Does not replace /api/chat yet.
# ==========================================================
@router.post("/api/langgraph-v013/run")
def api_langgraph_v013_run(req: ChatRequest):
    from app.langgraph_orchestrator import run_langgraph_active_orchestrator_v013
    return run_langgraph_active_orchestrator_v013(req.message)


