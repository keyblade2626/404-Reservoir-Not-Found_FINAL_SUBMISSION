from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Dict, List, Optional


# ==========================================================
# V500 HELPER MODULE FOR V501 LANGGRAPH ORCHESTRATOR
#
# This module contains the deterministic helper functions used
# by the real LangGraph StateGraph in V501.
#
# LangGraph V501 decides the route.
# This file only provides reusable execution helpers/tools.
# ==========================================================


def _norm_v500(text: str) -> str:
    return " ".join(str(text or "").lower().replace("_", " ").replace("-", " ").split())


def _extract_well_v500(text: str) -> Optional[str]:
    msg = _norm_v500(text)
    m = re.search(r"\b(hw)\s*(\d+[a-z]?)\b", msg, flags=re.I)
    if not m:
        return None
    return f"HW-{m.group(2).upper()}"


def _safe_float_v500(x: Any) -> Optional[float]:
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def _detect_variables_v500(text: str) -> List[str]:
    msg = _norm_v500(text)
    variables: List[str] = []

    aliases = [
        ("water cut", "wct"),
        ("wct", "wct"),
        ("wwct", "wct"),

        ("water production", "water"),
        ("water rate", "water"),
        ("wwpr", "water"),
        ("acqua", "water"),
        ("water", "water"),

        ("oil production", "oil"),
        ("oil rate", "oil"),
        ("wopr", "oil"),
        ("olio", "oil"),
        ("oil", "oil"),

        ("gas production", "gas"),
        ("gas rate", "gas"),
        ("wgpr", "gas"),
        ("gor", "gas"),
        ("gas", "gas"),

        ("bhp", "bhp"),
        ("wbhp", "bhp"),
        ("bottom hole pressure", "bhp"),
        ("well pressure", "bhp"),
        ("pressure profile", "bhp"),

        ("porosità", "PORO"),
        ("porosita", "PORO"),
        ("porosity", "PORO"),
        ("poro", "PORO"),

        ("permeabilità x", "PERM_X"),
        ("permeabilita x", "PERM_X"),
        ("permeability x", "PERM_X"),
        ("perm x", "PERM_X"),
        ("permx", "PERM_X"),
        ("kx", "PERM_X"),

        ("permeabilità y", "PERM_Y"),
        ("permeabilita y", "PERM_Y"),
        ("permeability y", "PERM_Y"),
        ("perm y", "PERM_Y"),
        ("permy", "PERM_Y"),
        ("ky", "PERM_Y"),

        ("permeabilità z", "PERM_Z"),
        ("permeabilita z", "PERM_Z"),
        ("permeability z", "PERM_Z"),
        ("perm z", "PERM_Z"),
        ("permz", "PERM_Z"),
        ("kz", "PERM_Z"),

        ("permeabilità", "PERM_X"),
        ("permeabilita", "PERM_X"),
        ("permeability", "PERM_X"),
        ("perm", "PERM_X"),

        ("water saturation", "SWAT"),
        ("saturazione acqua", "SWAT"),
        ("swat", "SWAT"),

        ("grid pressure", "PRESSURE"),
        ("pressure map", "PRESSURE"),
        ("pressione", "PRESSURE"),
        ("pressure", "PRESSURE"),

        ("transmissibility", "TRAN"),
        ("trasmissibilità", "TRAN"),
        ("trasmissibilita", "TRAN"),
        ("tran", "TRAN"),

        ("ntg", "NTG"),
        ("fipnum", "FIPNUM"),
        ("satnum", "SATNUM"),
    ]

    for raw, canon in aliases:
        if raw in msg and canon not in variables:
            variables.append(canon)

    return variables


def _property_from_variables_v500(variables: List[str]) -> Optional[str]:
    for v in variables:
        if v in {"PORO", "PERM_X", "PERM_Y", "PERM_Z", "SWAT", "PRESSURE", "TRAN", "NTG", "FIPNUM", "SATNUM"}:
            return v
    return None


def _extract_grid_filters_v500(text: str) -> List[Dict[str, Any]]:
    msg = _norm_v500(text)
    filters: List[Dict[str, Any]] = []

    for idx in ["i", "j", "k"]:
        m = re.search(rf"\b{idx}\s+(?:between|compreso tra|from|da)\s+(\d+)\s+(?:and|e|to|a)\s+(\d+)", msg)
        if m:
            filters.append({
                "kind": "index_range",
                "index": idx.upper(),
                "min": int(m.group(1)),
                "max": int(m.group(2)),
            })

    threshold_aliases = {
        "swat": "SWAT",
        "water saturation": "SWAT",
        "saturazione acqua": "SWAT",
        "poro": "PORO",
        "porosity": "PORO",
        "porosita": "PORO",
        "porosità": "PORO",
        "pressure": "PRESSURE",
        "pressione": "PRESSURE",
        "perm": "PERM_X",
        "permeability": "PERM_X",
        "permeabilita": "PERM_X",
        "permeabilità": "PERM_X",
        "permx": "PERM_X",
        "perm x": "PERM_X",
    }

    for raw, canon in threshold_aliases.items():
        pattern = rf"\b{re.escape(raw)}\b\s*(>|>=|<|<=|=|equal to|greater than|above|more than|less than|below|maggiore di|superiore a|minore di|inferiore a)\s*([-+]?\d+(?:\.\d+)?)"
        m = re.search(pattern, msg)
        if m:
            op_raw = m.group(1)
            op = {
                "greater than": ">",
                "above": ">",
                "more than": ">",
                "maggiore di": ">",
                "superiore a": ">",
                "less than": "<",
                "below": "<",
                "minore di": "<",
                "inferiore a": "<",
                "equal to": "=",
            }.get(op_raw, op_raw)

            filters.append({
                "kind": "property_threshold",
                "variable": canon,
                "operator": op,
                "value": float(m.group(2)),
            })

    return filters


def _extract_operation_v500(text: str) -> Optional[Dict[str, Any]]:
    msg = _norm_v500(text)

    m = re.search(r"(multiply|moltiplica)\s+(?:all\s+|tutti\s+)?([a-z0-9\s_]+?)\s+(?:by|per)\s+([-+]?\d+(?:\.\d+)?)", msg)
    if m:
        return {
            "operation": "multiply",
            "target_raw": m.group(2).strip(),
            "factor": float(m.group(3)),
        }

    m = re.search(r"(add|aggiungi|somma)\s+([-+]?\d+(?:\.\d+)?)\s+(?:to|a)\s+([a-z0-9\s_]+)", msg)
    if m:
        return {
            "operation": "add",
            "target_raw": m.group(3).strip(),
            "value": float(m.group(2)),
        }

    return None


def interpret_request_v500(message: str) -> Dict[str, Any]:
    msg = _norm_v500(message)
    well = _extract_well_v500(message)
    variables = _detect_variables_v500(message)
    prop = _property_from_variables_v500(variables)
    filters = _extract_grid_filters_v500(message)
    operation = _extract_operation_v500(message)

    has_distribution = any(x in msg for x in [
        "distribution", "histogram", "hist", "frequency", "pdf",
        "distribuzione", "istogramma", "spread"
    ])

    has_map = any(x in msg for x in [
        "map", "mappa", "visualize map", "show map"
    ])

    has_cumulative = any(x in msg for x in [
        "cumulative", "cum ", " cum", "total produced", "cumulative production",
        "cumulativa", "cumulativo", "totale prodotto"
    ])

    has_same_plot = any(x in msg for x in [
        "same plot", "same chart", "together", "on the same",
        "stesso grafico", "insieme"
    ])

    has_all_profiles = any(x in msg for x in [
        "all profiles", "all wells", "tutti i profili", "all well profiles"
    ])

    has_percentiles = any(x in msg for x in [
        "p10", "p50", "p90", "percentile", "percentiles", "percentili"
    ])

    has_diagnostic = any(x in msg for x in [
        "why", "perche", "perché", "diagnose", "diagnostic", "bias",
        "mismatch", "cluster", "pattern", "connected", "connectivity",
        "transmissibility", "tran", "relperm", "relative permeability",
        "review first", "driver", "cause", "causa", "connessi", "connesso"
    ])

    has_calculation = any(x in msg for x in [
        "sum", "summation", "somma", "sommami", "average", "mean", "media",
        "min", "max", "multiply", "moltiplica", "divide", "ratio",
        "difference", "delta", "integrate", "calculate", "calcola"
    ])

    well_vars = [v for v in variables if v in {"oil", "water", "gas", "wct", "bhp"}]

    if has_calculation and well:
        task_type = "well_data_operation"
    elif has_calculation and prop:
        task_type = "grid_data_operation"
    elif well and has_all_profiles and has_percentiles:
        task_type = "ensemble_profile_percentiles"
    elif well and has_same_plot and len(well_vars) >= 2:
        task_type = "multi_variable_profile"
    elif well and has_cumulative:
        task_type = "cumulative_profile"
    elif well and well_vars:
        task_type = "well_profile"
    elif has_distribution and prop:
        task_type = "property_distribution"
    elif operation and prop:
        task_type = "grid_data_operation"
    elif filters and prop and (has_map or "where" in msg or "dove" in msg):
        task_type = "conditional_property_map"
    elif has_map and prop:
        task_type = "property_map"
    elif has_diagnostic and ("cluster" in msg or "bias" in msg or "pattern" in msg):
        task_type = "diagnostic_cluster"
    elif has_diagnostic:
        task_type = "integrated_diagnostic_reasoning"
    else:
        task_type = "general_reservoir_reasoning"

    return {
        "schema_version": "v500",
        "original_message": message,
        "task_type": task_type,
        "well": well,
        "variables": variables,
        "primary_property": prop,
        "filters": filters,
        "operation": operation,
        "flags": {
            "distribution": has_distribution,
            "map": has_map,
            "cumulative": has_cumulative,
            "same_plot": has_same_plot,
            "all_profiles": has_all_profiles,
            "percentiles": has_percentiles,
            "diagnostic": has_diagnostic,
            "calculation": has_calculation,
        },
    }


def build_plan_v500(intent: Dict[str, Any]) -> Dict[str, Any]:
    task = intent.get("task_type")

    plan_map = {
        "well_profile": ["ProfileAgent", "VisualCriticAgent"],
        "cumulative_profile": ["ProfileAgent", "DataAlgebraAgent", "VisualCriticAgent"],
        "multi_variable_profile": ["ProfileAgent", "MultiVariablePlotAgent", "VisualCriticAgent"],
        "ensemble_profile_percentiles": ["ProfileAgent", "PercentileEnvelopeAgent", "VisualCriticAgent"],
        "property_distribution": ["PropertyDataAgent", "DistributionPlotAgent", "VisualCriticAgent"],
        "property_map": ["PropertyMapAgent", "VisualCriticAgent"],
        "conditional_property_map": ["PropertyDataAgent", "DataAlgebraAgent", "ConditionalMapAgent", "VisualCriticAgent"],
        "grid_data_operation": ["PropertyDataAgent", "DataAlgebraAgent", "VisualCriticAgent"],
        "well_data_operation": ["ProfileAgent", "DataAlgebraAgent", "ResultSynthesizerAgent"],
        "diagnostic_cluster": ["ProfileAgent", "PropertyAgent", "SpatialPatternAgent", "ClusterDiagnosticAgent", "HypothesisAgent", "ReservoirCriticAgent"],
        "integrated_diagnostic_reasoning": ["ProfileAgent", "PropertyAgent", "ConnectivityAgent", "RelPermAgent", "PressureAgent", "HypothesisAgent", "ReservoirCriticAgent"],
        "general_reservoir_reasoning": ["ReservoirReasoningAgent", "ReservoirCriticAgent"],
    }

    return {
        "plan_version": "v500",
        "task_type": task,
        "steps": plan_map.get(task, ["ReservoirReasoningAgent", "ReservoirCriticAgent"]),
    }


def _call_existing_router_v500(prompt: str) -> Dict[str, Any]:
    from app.chat_router import answer_question

    response = answer_question(prompt)

    if isinstance(response, dict):
        return response

    return {
        "type": "reasoning_response",
        "intent": "text_response",
        "answer": str(response),
        "ui_blocks": [],
    }


def _variable_to_profile_prompt_v500(well: str, variables: List[str]) -> str:
    if "wct" in variables:
        return f"Plot {well} WCT"
    if "water" in variables:
        return f"Plot {well} water production"
    if "gas" in variables:
        return f"Plot {well} gas production"
    if "bhp" in variables:
        return f"Plot {well} BHP profile"
    return f"Plot {well} oil production"


def _make_cumulative_v500(values: List[Any], dates: List[Any]) -> List[Optional[float]]:
    def parse_dt(x: Any) -> Optional[datetime]:
        s = str(x)
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(s[:19], fmt)
            except Exception:
                pass
        try:
            return datetime.fromisoformat(s.replace("Z", ""))
        except Exception:
            return None

    out: List[Optional[float]] = []
    total = 0.0
    last_dt: Optional[datetime] = None
    last_val: Optional[float] = None

    for d, v in zip(dates or [], values or []):
        dt = parse_dt(d)
        val = _safe_float_v500(v)

        if dt is not None and val is not None:
            if last_dt is not None and last_val is not None:
                days = max(0.0, (dt - last_dt).total_seconds() / 86400.0)
                total += 0.5 * (last_val + val) * days
            out.append(total)
            last_dt = dt
            last_val = val
        else:
            out.append(None)

    return out


def _convert_response_to_cumulative_v500(response: Dict[str, Any]) -> Dict[str, Any]:
    blocks = response.get("ui_blocks") or []

    for block in blocks:
        if not isinstance(block, dict) or block.get("type") != "profile_series":
            continue

        data = block.get("data") or block.get("payload") or {}
        dates = data.get("dates") or []
        sim = data.get("simulated") or []
        obs = data.get("observed") or []

        if not dates or not sim:
            continue

        data["simulated"] = _make_cumulative_v500(sim, dates)
        data["observed"] = _make_cumulative_v500(obs, dates)
        data["variable"] = f"{data.get('variable', 'profile')}_cumulative"

        title = data.get("title") or block.get("title") or "Profile"
        if "cumulative" not in title.lower():
            title = f"{title} - cumulative"

        data["title"] = title
        block["title"] = title
        block["data"] = data

    response["intent"] = "dynamic_interactive_cumulative_profile"
    response["type"] = "visual_response"
    response["answer"] = (
        "I generated an interactive cumulative simulated-vs-observed profile. "
        "The cumulative curves are computed from the available rate arrays using time-step integration."
    )

    return response


def _execute_well_profile_v500(intent: Dict[str, Any]) -> Dict[str, Any]:
    well = intent.get("well") or ""
    variables = intent.get("variables") or []
    prompt = _variable_to_profile_prompt_v500(well, variables)
    return _call_existing_router_v500(prompt)


def _execute_cumulative_profile_v500(intent: Dict[str, Any]) -> Dict[str, Any]:
    out = _execute_well_profile_v500(intent)
    return _convert_response_to_cumulative_v500(out)


def _execute_multi_variable_profile_v500(intent: Dict[str, Any]) -> Dict[str, Any]:
    well = intent.get("well") or ""
    variables = [v for v in (intent.get("variables") or []) if v in {"oil", "water", "gas", "wct", "bhp"}]

    if not variables:
        variables = ["oil", "water"]

    blocks: List[Dict[str, Any]] = []
    traces: Dict[str, Any] = {}

    for v in variables:
        sub_intent = dict(intent)
        sub_intent["variables"] = [v]
        response = _execute_well_profile_v500(sub_intent)

        if isinstance(response, dict):
            blocks.extend(response.get("ui_blocks") or [])
            traces[f"ProfileAgent_{v}"] = {
                "variable": v,
                "status": "ok",
                "block_count": len(response.get("ui_blocks") or []),
            }

    return {
        "type": "visual_response",
        "intent": "multi_variable_profile",
        "answer": f"I generated profile evidence for {well} using: {', '.join(variables)}.",
        "ui_blocks": blocks,
        "agent_trace": traces,
    }


def _execute_property_distribution_v500(intent: Dict[str, Any]) -> Dict[str, Any]:
    prop = intent.get("primary_property") or "PORO"
    rewritten = f"plot distribution of {prop}"

    try:
        from app.generic_static_plot_agent import answer_generic_plot_request
        out = answer_generic_plot_request(rewritten)
        if isinstance(out, dict):
            return out
    except Exception:
        pass

    return _call_existing_router_v500(rewritten)


def _execute_property_map_v500(intent: Dict[str, Any]) -> Dict[str, Any]:
    prop = intent.get("primary_property") or "PORO"
    return _call_existing_router_v500(f"show me {prop} map")


def _call_wct_bias_builder_v500(message: str) -> Optional[Dict[str, Any]]:
    try:
        import app.chat_router as cr

        for name in ["_build_wct_bias_response_v37", "_build_wct_bias_response_v36"]:
            fn = getattr(cr, name, None)
            if callable(fn):
                out = fn(message)
                if isinstance(out, dict):
                    out.setdefault("type", "visual_response")
                    out.setdefault("intent", "diagnostic_cluster")
                    out.setdefault("ui_blocks", out.get("ui_blocks") or [])
                    return out
    except Exception:
        return None

    return None


def _execute_diagnostic_cluster_v500(intent: Dict[str, Any]) -> Dict[str, Any]:
    msg = intent.get("original_message") or ""
    variables = intent.get("variables") or []

    if "wct" in variables or "water" in variables:
        out = _call_wct_bias_builder_v500(msg)
        if out:
            return out

    return _call_existing_router_v500(msg)


def _execute_integrated_diagnostic_v500(intent: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    return _call_existing_router_v500(intent.get("original_message") or "")


def _execute_well_data_operation_v500(intent: Dict[str, Any]) -> Dict[str, Any]:
    msg = _norm_v500(intent.get("original_message") or "")
    well = intent.get("well")
    variables = intent.get("variables") or []

    profile = _execute_well_profile_v500(intent)
    blocks = profile.get("ui_blocks") or []

    result: Dict[str, Any] = {
        "type": "calculation_response",
        "intent": "well_data_operation",
        "answer": "I could not find a profile block to calculate from.",
        "ui_blocks": blocks,
        "calculation_summary": {},
    }

    for block in blocks:
        if not isinstance(block, dict) or block.get("type") != "profile_series":
            continue

        data = block.get("data") or block.get("payload") or {}
        dates = data.get("dates") or []
        sim = data.get("simulated") or []
        obs = data.get("observed") or []

        sim_vals = [x for x in (_safe_float_v500(v) for v in sim) if x is not None]
        obs_vals = [x for x in (_safe_float_v500(v) for v in obs) if x is not None]

        op = "sum"
        if "average" in msg or "mean" in msg or "media" in msg:
            op = "mean"
        elif "max" in msg:
            op = "max"
        elif "min" in msg:
            op = "min"
        elif "cumulative" in msg or "total produced" in msg or "cumulativa" in msg:
            op = "cumulative"

        if op == "mean":
            sim_result = sum(sim_vals) / len(sim_vals) if sim_vals else None
            obs_result = sum(obs_vals) / len(obs_vals) if obs_vals else None
        elif op == "max":
            sim_result = max(sim_vals) if sim_vals else None
            obs_result = max(obs_vals) if obs_vals else None
        elif op == "min":
            sim_result = min(sim_vals) if sim_vals else None
            obs_result = min(obs_vals) if obs_vals else None
        elif op == "cumulative":
            sim_cum = _make_cumulative_v500(sim, dates)
            obs_cum = _make_cumulative_v500(obs, dates)
            sim_result = next((x for x in reversed(sim_cum) if x is not None), None)
            obs_result = next((x for x in reversed(obs_cum) if x is not None), None)
        else:
            sim_result = sum(sim_vals) if sim_vals else None
            obs_result = sum(obs_vals) if obs_vals else None

        variable = data.get("variable") or (variables[0] if variables else "profile")
        result["answer"] = (
            f"For {well}, {op} on {variable} profile values gives "
            f"simulated={sim_result} and observed={obs_result}. "
            f"Note: simple sum is a mathematical sum of sampled values; cumulative production uses time integration."
        )
        result["calculation_summary"] = {
            "well": well,
            "variable": variable,
            "operation": op,
            "simulated_result": sim_result,
            "observed_result": obs_result,
            "n_simulated": len(sim_vals),
            "n_observed": len(obs_vals),
        }
        return result

    return result


def execute_plan_v500(intent: Dict[str, Any], plan: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    task = intent.get("task_type")

    evidence_board.setdefault("execution", []).append({
        "agent": "UniversalReservoirOrchestratorV500Helpers",
        "task_type": task,
        "plan_steps": plan.get("steps", []),
    })

    if task == "well_profile":
        return _execute_well_profile_v500(intent)

    if task == "cumulative_profile":
        return _execute_cumulative_profile_v500(intent)

    if task == "multi_variable_profile":
        return _execute_multi_variable_profile_v500(intent)

    if task == "property_distribution":
        return _execute_property_distribution_v500(intent)

    if task == "property_map":
        return _execute_property_map_v500(intent)

    if task == "conditional_property_map":
        out = _execute_property_map_v500(intent)
        if isinstance(out, dict):
            out.setdefault("calculation_summary", {})
            out["calculation_summary"]["requested_filters"] = intent.get("filters") or []
            out["calculation_summary"]["note"] = (
                "Conditional map intent detected. Current helper records filters; "
                "masked-grid rendering should be handled by the ConditionalMapAgent implementation."
            )
        return out

    if task == "grid_data_operation":
        if intent.get("flags", {}).get("distribution"):
            return _execute_property_distribution_v500(intent)
        return _execute_property_map_v500(intent)

    if task == "well_data_operation":
        return _execute_well_data_operation_v500(intent)

    if task == "diagnostic_cluster":
        return _execute_diagnostic_cluster_v500(intent)

    if task in {"integrated_diagnostic_reasoning", "general_reservoir_reasoning"}:
        return _execute_integrated_diagnostic_v500(intent, evidence_board)

    return _call_existing_router_v500(intent.get("original_message") or "")


def critic_validate_v500(intent: Dict[str, Any], response: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(response, dict):
        response = {
            "type": "reasoning_response",
            "intent": "text_response",
            "answer": str(response),
            "ui_blocks": [],
        }

    task = intent.get("task_type")
    blocks = response.get("ui_blocks") or []
    block_types = [b.get("type") for b in blocks if isinstance(b, dict)]

    checks: List[Dict[str, Any]] = []

    def add_check(name: str, passed: bool, detail: str):
        checks.append({
            "check": name,
            "passed": bool(passed),
            "detail": detail,
        })

    if task == "property_distribution":
        add_check(
            "distribution_not_map",
            not any("map" in str(t or "") for t in block_types),
            f"block_types={block_types}",
        )

    if task in {"well_profile", "cumulative_profile", "multi_variable_profile"}:
        add_check(
            "profile_series_present",
            "profile_series" in block_types,
            f"block_types={block_types}",
        )

    if task == "cumulative_profile":
        add_check(
            "cumulative_intent_label",
            "cumulative" in str(response.get("intent") or "").lower() or "cumulative" in str(response.get("answer") or "").lower(),
            f"intent={response.get('intent')}",
        )

    if task == "diagnostic_cluster":
        add_check(
            "diagnostic_visual_or_reasoning_present",
            bool(blocks or response.get("answer")),
            f"block_types={block_types}",
        )

    evidence_board["critic_checks"] = checks

    response.setdefault("agent_trace", {})
    response["agent_trace"]["VisualAndReasoningCriticV500"] = {
        "task_type": task,
        "checks": checks,
        "overall_passed": all(c["passed"] for c in checks) if checks else True,
    }

    return response


def package_response_v500(
    message: str,
    intent: Dict[str, Any],
    plan: Dict[str, Any],
    response: Dict[str, Any],
    evidence_board: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(response, dict):
        response = {
            "type": "reasoning_response",
            "intent": intent.get("task_type"),
            "answer": str(response),
            "ui_blocks": [],
        }

    response.setdefault("type", "visual_response" if response.get("ui_blocks") else "reasoning_response")
    response.setdefault("intent", intent.get("task_type"))
    response.setdefault("answer", "")
    response.setdefault("ui_blocks", [])

    response["universal_intent_v500"] = intent
    response["execution_plan_v500"] = plan
    response["evidence_board_v500"] = evidence_board

    response.setdefault("agent_trace", {})
    response["agent_trace"]["UniversalReservoirOrchestratorV500Helpers"] = {
        "task_type": intent.get("task_type"),
        "well": intent.get("well"),
        "variables": intent.get("variables"),
        "plan_steps": plan.get("steps", []),
        "principle": "Helper functions used by LangGraph V501 nodes; LangGraph routes, tools execute.",
    }

    response.setdefault("interaction_edges", [])
    response["interaction_edges"].append({
        "from": "LangGraphUniversalReservoirOrchestratorV501",
        "to": "V500HelperTools",
        "reason": "StateGraph selected specialist execution path; helper tool executed requested operation.",
    })

    return response


def run_universal_reservoir_orchestrator_v500(message: str) -> Dict[str, Any]:
    evidence_board: Dict[str, Any] = {
        "schema_version": "v500",
        "original_message": message,
        "evidence": [],
    }

    intent = interpret_request_v500(message)
    plan = build_plan_v500(intent)
    raw = execute_plan_v500(intent, plan, evidence_board)
    validated = critic_validate_v500(intent, raw, evidence_board)
    return package_response_v500(message, intent, plan, validated, evidence_board)

# ==========================================================
# V502 LANGGRAPH TOOL ROUTING CORRECTIONS
#
# Keeps V501 as the real LangGraph StateGraph.
# This patch only improves helper tools used by V501 nodes:
# - property_distribution must return histogram/distribution, not map
# - connectivity/relperm/mismatch questions must be diagnostic reasoning, not profile
# - conditional property map tries to apply filters if cell payloads are available
# ==========================================================

_interpret_request_before_v502 = interpret_request_v500
_execute_property_distribution_before_v502 = _execute_property_distribution_v500
_execute_integrated_diagnostic_before_v502 = _execute_integrated_diagnostic_v500
_execute_plan_before_v502 = execute_plan_v500


def _v502_norm(message):
    return " ".join(str(message or "").lower().replace("_", " ").replace("-", " ").split())


def interpret_request_v500(message: str) -> Dict[str, Any]:
    intent = _interpret_request_before_v502(message)
    msg = _v502_norm(message)

    strong_diagnostic_terms = [
        "why", "perche", "perché", "mismatch", "driver", "cause", "causa",
        "connectivity", "connected", "connesso", "connessi",
        "transmissibility", "tran",
        "relperm", "relative permeability",
        "more likely", "piu probabile", "più probabile",
        "review first", "what should i review",
        "what variables", "which variables",
        "explain", "diagnose", "diagnostic",
    ]

    has_strong_diag = any(x in msg for x in strong_diagnostic_terms)

    # Important: if the user asks "is it connectivity or relperm?", this is not a profile request.
    if has_strong_diag:
        if any(x in msg for x in ["cluster", "bias cluster", "pattern map", "cluster map"]):
            intent["task_type"] = "diagnostic_cluster"
        else:
            intent["task_type"] = "integrated_diagnostic_reasoning"

        intent.setdefault("flags", {})
        intent["flags"]["diagnostic"] = True
        intent["diagnostic_priority_v502"] = {
            "reason": "Strong diagnostic wording detected; do not route to simple well profile.",
            "matched": [x for x in strong_diagnostic_terms if x in msg][:10],
        }

    # Distribution/histogram must always dominate property map.
    if intent.get("flags", {}).get("distribution") and intent.get("primary_property"):
        intent["task_type"] = "property_distribution"
        intent["distribution_priority_v502"] = {
            "reason": "Distribution/histogram request must call distribution tool, not property map."
        }

    return intent


def _wrap_static_plot_result_v502(result: Dict[str, Any], prop: str, original_message: str) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {
            "type": "reasoning_response",
            "intent": "property_distribution",
            "answer": str(result),
            "ui_blocks": [],
        }

    # Already a full visual response.
    if result.get("type") == "visual_response" and isinstance(result.get("ui_blocks"), list):
        result["intent"] = "property_distribution"
        result.setdefault("agent_trace", {})
        result["agent_trace"]["DistributionPlotAgentV502"] = {
            "route": "existing visual_response",
            "property": prop,
        }
        return result

    plotly_chart = result.get("plotly_chart")

    if isinstance(plotly_chart, dict):
        block = dict(plotly_chart)
        block.setdefault("type", "plotly_chart")
        block.setdefault("title", f"{prop} distribution")

        return {
            "type": "visual_response",
            "intent": "property_distribution",
            "answer": result.get("message") or result.get("answer") or f"I generated the {prop} distribution histogram.",
            "ui_blocks": [block],
            "data": {
                "property": prop,
                "plot_type": "distribution",
                "source": "generic_static_plot_agent.handle_static_plot_request",
                "stats": result.get("stats"),
                "values_count": len(result.get("values") or []) if isinstance(result.get("values"), list) else None,
            },
            "agent_trace": {
                "DistributionPlotAgentV502": {
                    "route": "handle_static_plot_request -> plotly_chart",
                    "property": prop,
                    "original_message": original_message,
                    "reason": "Bypassed map-first generic answer wrapper and called distribution handler directly.",
                }
            },
            "interaction_edges": [
                {
                    "from": "PropertyDistributionNodeV501",
                    "to": "DistributionPlotAgentV502",
                    "reason": "Histogram/distribution intent selected by LangGraph.",
                }
            ],
        }

    image_url = result.get("image_url")
    if image_url:
        return {
            "type": "visual_response",
            "intent": "property_distribution",
            "answer": result.get("message") or f"I generated a static {prop} distribution plot.",
            "ui_blocks": [
                {
                    "type": "static_image",
                    "title": f"{prop} distribution",
                    "image_url": image_url,
                }
            ],
            "agent_trace": {
                "DistributionPlotAgentV502": {
                    "route": "handle_static_plot_request -> static_image",
                    "property": prop,
                }
            },
        }

    return {
        "type": "reasoning_response",
        "intent": "property_distribution",
        "answer": result.get("message") or result.get("answer") or f"I could not generate the {prop} distribution.",
        "ui_blocks": [],
        "agent_trace": {
            "DistributionPlotAgentV502": {
                "route": "no_plot_payload_returned",
                "property": prop,
                "raw_keys": list(result.keys()),
            }
        },
    }


def _execute_property_distribution_v500(intent: Dict[str, Any]) -> Dict[str, Any]:
    prop = intent.get("primary_property") or "PORO"
    prompt = f"plot distribution of {prop}"

    # Use handle_static_plot_request directly. This avoids the later map-first override
    # inside answer_generic_plot_request that was returning generic_property_map.
    try:
        from app.generic_static_plot_agent import handle_static_plot_request
        result = handle_static_plot_request(prompt)
        return _wrap_static_plot_result_v502(result, prop, intent.get("original_message") or prompt)
    except Exception as exc:
        out = _execute_property_distribution_before_v502(intent)
        if isinstance(out, dict):
            out.setdefault("agent_trace", {})
            out["agent_trace"]["DistributionPlotAgentV502Fallback"] = {
                "error": str(exc),
                "fallback": "_execute_property_distribution_before_v502",
            }
        return out


def _execute_integrated_diagnostic_v500(intent: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    msg = intent.get("original_message") or ""

    diagnostic_prompt = (
        "HOLISTIC_RESERVOIR_DIAGNOSTIC_REQUEST. "
        "Treat this as an integrated reservoir-engineering diagnostic, not as a simple profile or property plot. "
        "Use all available evidence across water/WCT, oil, gas/GOR, BHP/pressure, spatial properties, TRAN/connectivity, "
        "and RelPerm/SATNUM if available. Compare hypotheses and state which one is better supported. "
        "If the question asks connectivity versus RelPerm, do not answer with only a water profile. "
        f"Original user request: {msg}"
    )

    response = _call_existing_router_v500(diagnostic_prompt)

    if isinstance(response, dict):
        response.setdefault("agent_trace", {})
        response["agent_trace"]["IntegratedDiagnosticReasoningV502"] = {
            "route": "HOLISTIC_RESERVOIR_DIAGNOSTIC_REQUEST -> existing agentic reasoning stack",
            "original_message": msg,
            "reason": "Strong diagnostic request routed through reasoning stack instead of profile-only tool.",
        }
        response.setdefault("interaction_edges", [])
        response["interaction_edges"].append({
            "from": "IntegratedReasoningNodeV501",
            "to": "IntegratedDiagnosticReasoningV502",
            "reason": "LangGraph selected integrated diagnostic reasoning.",
        })

    return response


def _extract_cells_from_block_v502(block: Dict[str, Any]):
    candidates = []

    for base in [
        block,
        block.get("payload") if isinstance(block, dict) else None,
        block.get("data") if isinstance(block, dict) else None,
    ]:
        if not isinstance(base, dict):
            continue

        candidates.extend([
            (base, "cells", base.get("cells")),
            (base, "points", base.get("points")),
            (base, "data", base.get("data")),
            (base, "values", base.get("values")),
            (base, "cell_values", base.get("cell_values")),
            (base, "layer", base.get("layer")),
        ])

        layer = base.get("layer")
        if isinstance(layer, dict):
            candidates.extend([
                (layer, "cells", layer.get("cells")),
                (layer, "points", layer.get("points")),
                (layer, "data", layer.get("data")),
                (layer, "values", layer.get("values")),
                (layer, "cell_values", layer.get("cell_values")),
            ])

    for parent, key, arr in candidates:
        if isinstance(arr, list) and arr:
            return parent, key, arr

    return None, None, []


def _cell_key_v502(cell):
    if not isinstance(cell, dict):
        return None

    i = cell.get("i", cell.get("I", cell.get("x", cell.get("X"))))
    j = cell.get("j", cell.get("J", cell.get("y", cell.get("Y"))))
    k = cell.get("k", cell.get("K", cell.get("z_index", cell.get("K_INDEX", 1))))

    try:
        return (int(float(i)), int(float(j)), int(float(k)))
    except Exception:
        try:
            return (int(float(i)), int(float(j)), 1)
        except Exception:
            return None


def _cell_value_v502(cell):
    if not isinstance(cell, dict):
        return None

    for key in ["value", "val", "z", "Z", "property_value", "mean", "avg"]:
        if key in cell:
            return _safe_float_v500(cell.get(key))

    return None


def _passes_index_filters_v502(cell, filters):
    key = _cell_key_v502(cell)
    if key is None:
        return True

    idx_map = {"I": key[0], "J": key[1], "K": key[2]}

    for f in filters:
        if f.get("kind") != "index_range":
            continue

        idx = f.get("index")
        val = idx_map.get(idx)

        if val is None:
            continue

        if val < int(f.get("min")) or val > int(f.get("max")):
            return False

    return True


def _passes_threshold_v502(value, op, threshold):
    if value is None:
        return False

    if op == ">":
        return value > threshold
    if op == ">=":
        return value >= threshold
    if op == "<":
        return value < threshold
    if op == "<=":
        return value <= threshold
    if op in ["=", "=="]:
        return abs(value - threshold) < 1e-12

    return False


def _first_generic_property_block_v502(response):
    for b in response.get("ui_blocks") or []:
        if isinstance(b, dict) and b.get("type") == "generic_property_map":
            return b

    return None


def _execute_conditional_property_map_v502(intent: Dict[str, Any]) -> Dict[str, Any]:
    primary_prop = intent.get("primary_property") or "PERM_X"
    filters = intent.get("filters") or []

    primary_response = _execute_property_map_v500({
        **intent,
        "primary_property": primary_prop,
    })

    primary_block = _first_generic_property_block_v502(primary_response)

    if not primary_block:
        if isinstance(primary_response, dict):
            primary_response.setdefault("calculation_summary", {})
            primary_response["calculation_summary"]["conditional_map_v502"] = {
                "status": "no_generic_property_map_block",
                "filters": filters,
            }
        return primary_response

    parent, key, primary_cells = _extract_cells_from_block_v502(primary_block)

    if not primary_cells:
        primary_response.setdefault("calculation_summary", {})
        primary_response["calculation_summary"]["conditional_map_v502"] = {
            "status": "no_cell_payload_available",
            "filters": filters,
        }
        return primary_response

    threshold_filters = [f for f in filters if f.get("kind") == "property_threshold"]
    index_filters = [f for f in filters if f.get("kind") == "index_range"]

    lookup_by_variable = {}

    for f in threshold_filters:
        var = f.get("variable")
        if not var or var == primary_prop:
            continue

        filter_response = _execute_property_map_v500({
            **intent,
            "primary_property": var,
        })

        filter_block = _first_generic_property_block_v502(filter_response)
        _, _, filter_cells = _extract_cells_from_block_v502(filter_block or {})

        lk = {}
        for c in filter_cells:
            ck = _cell_key_v502(c)
            if ck is not None:
                lk[ck] = _cell_value_v502(c)

        lookup_by_variable[var] = lk

    filtered = []

    for cell in primary_cells:
        if not _passes_index_filters_v502(cell, index_filters):
            continue

        ck = _cell_key_v502(cell)
        ok = True

        for f in threshold_filters:
            var = f.get("variable")
            op = f.get("operator")
            threshold = f.get("value")

            if var == primary_prop:
                val = _cell_value_v502(cell)
            else:
                val = lookup_by_variable.get(var, {}).get(ck)

            if not _passes_threshold_v502(val, op, threshold):
                ok = False
                break

        if ok:
            filtered.append(cell)

    if parent is not None and key is not None:
        parent[key] = filtered

    condition_text = ", ".join(
        [
            f"{f.get('variable') or f.get('index')} {f.get('operator', 'between')} {f.get('value', '') or str(f.get('min')) + '-' + str(f.get('max'))}"
            for f in filters
        ]
    )

    primary_block["title"] = f"{primary_prop} conditional map"
    if isinstance(primary_block.get("payload"), dict):
        primary_block["payload"]["title"] = primary_block["title"]
        primary_block["payload"]["operation"] = "conditional_filter"

    primary_response["intent"] = "conditional_property_map"
    primary_response["answer"] = (
        f"I generated a conditional {primary_prop} map using the requested filters: {condition_text}. "
        f"Selected {len(filtered)} cells out of {len(primary_cells)} available primary-property cells."
    )

    primary_response.setdefault("calculation_summary", {})
    primary_response["calculation_summary"]["conditional_map_v502"] = {
        "status": "filter_applied",
        "primary_property": primary_prop,
        "filters": filters,
        "input_cells": len(primary_cells),
        "selected_cells": len(filtered),
        "filter_property_lookups": {k: len(v) for k, v in lookup_by_variable.items()},
    }

    primary_response.setdefault("agent_trace", {})
    primary_response["agent_trace"]["ConditionalMapAgentV502"] = {
        "route": "PropertyMapAgent + DataAlgebra filter",
        "primary_property": primary_prop,
        "filters": filters,
        "selected_cells": len(filtered),
        "input_cells": len(primary_cells),
    }

    primary_response.setdefault("interaction_edges", [])
    primary_response["interaction_edges"].append({
        "from": "ConditionalMapNodeV501",
        "to": "ConditionalMapAgentV502",
        "reason": "LangGraph selected conditional property-map execution.",
    })

    return primary_response


def execute_plan_v500(intent: Dict[str, Any], plan: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    task = intent.get("task_type")

    if task == "property_distribution":
        return _execute_property_distribution_v500(intent)

    if task == "conditional_property_map":
        return _execute_conditional_property_map_v502(intent)

    if task == "integrated_diagnostic_reasoning":
        return _execute_integrated_diagnostic_v500(intent, evidence_board)

    return _execute_plan_before_v502(intent, plan, evidence_board)

# END V502 LANGGRAPH TOOL ROUTING CORRECTIONS

# ==========================================================
# V504 ENSEMBLE PROFILE P10/P50/P90
#
# Fixes:
# "Plot all oil profiles and show me P10, P50, P90"
# must be routed to ensemble_profile_percentiles, not holistic reasoning.
# ==========================================================

_interpret_request_before_v504 = interpret_request_v500
_execute_plan_before_v504 = execute_plan_v500


def interpret_request_v500(message: str) -> Dict[str, Any]:
    intent = _interpret_request_before_v504(message)
    msg = _norm_v500(message)

    has_all_profiles = any(x in msg for x in [
        "all oil profiles", "all water profiles", "all gas profiles", "all bhp profiles",
        "all profiles", "all well profiles",
        "tutti i profili", "tutti i pozzi",
    ])

    has_percentiles = any(x in msg for x in [
        "p10", "p50", "p90", "percentile", "percentiles", "percentili"
    ])

    has_profile_variable = any(v in intent.get("variables", []) for v in ["oil", "water", "gas", "wct", "bhp"])

    if has_all_profiles and has_percentiles and has_profile_variable:
        intent["task_type"] = "ensemble_profile_percentiles"
        intent.setdefault("flags", {})
        intent["flags"]["all_profiles"] = True
        intent["flags"]["percentiles"] = True
        intent["ensemble_profile_priority_v504"] = {
            "reason": "All-profiles percentile request must generate P10/P50/P90 profile envelope, not holistic diagnostic text."
        }

    return intent


def _profile_variable_prompt_v504(well: str, variable: str) -> str:
    if variable == "water":
        return f"Plot {well} water production"
    if variable == "gas":
        return f"Plot {well} gas production"
    if variable == "wct":
        return f"Plot {well} WCT"
    if variable == "bhp":
        return f"Plot {well} BHP profile"
    return f"Plot {well} oil production"


def _selected_ensemble_variable_v504(intent: Dict[str, Any]) -> str:
    variables = intent.get("variables") or []

    for v in ["oil", "water", "gas", "wct", "bhp"]:
        if v in variables:
            return v

    return "oil"


def _percentile_v504(values, p):
    vals = sorted([float(x) for x in values if x is not None])

    if not vals:
        return None

    if len(vals) == 1:
        return vals[0]

    pos = (len(vals) - 1) * (p / 100.0)
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo

    return vals[lo] * (1 - frac) + vals[hi] * frac


def _extract_profile_series_v504(response):
    for block in response.get("ui_blocks") or []:
        if isinstance(block, dict) and block.get("type") == "profile_series":
            data = block.get("data") or block.get("payload") or {}
            dates = data.get("dates") or []
            simulated = data.get("simulated") or []
            observed = data.get("observed") or []

            if dates and simulated:
                return {
                    "block": block,
                    "data": data,
                    "dates": dates,
                    "simulated": simulated,
                    "observed": observed,
                    "well": data.get("well") or "",
                    "variable": data.get("variable") or "",
                }

    return None


def _discover_profile_wells_v504(variable: str, max_wells: int = 80):
    found = []

    for n in range(1, max_wells + 1):
        well = f"HW-{n}"
        prompt = _profile_variable_prompt_v504(well, variable)

        try:
            response = _call_existing_router_v500(prompt)
            series = _extract_profile_series_v504(response)

            if series:
                series["well"] = well
                found.append(series)
        except Exception:
            pass

    return found


def _execute_ensemble_profile_percentiles_v504(intent: Dict[str, Any]) -> Dict[str, Any]:
    variable = _selected_ensemble_variable_v504(intent)
    original = intent.get("original_message") or ""

    profiles = _discover_profile_wells_v504(variable)

    if not profiles:
        return {
            "type": "reasoning_response",
            "intent": "ensemble_profile_percentiles",
            "answer": f"I could not find available {variable} profile series to compute P10/P50/P90.",
            "ui_blocks": [],
            "agent_trace": {
                "EnsembleProfilePercentileAgentV504": {
                    "status": "no_profiles_found",
                    "variable": variable,
                    "original_message": original,
                }
            }
        }

    # Use the first profile timeline as reference.
    ref_dates = profiles[0]["dates"]
    n = len(ref_dates)

    # Keep only profiles with same length/timeline for now.
    aligned = []

    for p in profiles:
        if len(p["dates"]) == n and list(p["dates"]) == list(ref_dates):
            aligned.append(p)

    if not aligned:
        aligned = profiles[:]

    ref_dates = aligned[0]["dates"]
    n = len(ref_dates)

    p10 = []
    p50 = []
    p90 = []

    for i in range(n):
        vals = []

        for prof in aligned:
            sim = prof.get("simulated") or []
            if i < len(sim):
                v = _safe_float_v500(sim[i])
                if v is not None:
                    vals.append(v)

        p10.append(_percentile_v504(vals, 10))
        p50.append(_percentile_v504(vals, 50))
        p90.append(_percentile_v504(vals, 90))

    traces = []

    # Add individual profiles lightly, but limit for readability.
    for prof in aligned[:20]:
        traces.append({
            "type": "scatter",
            "mode": "lines",
            "name": prof.get("well") or "well",
            "x": ref_dates,
            "y": prof.get("simulated") or [],
            "line": {
                "width": 1
            },
            "opacity": 0.25,
            "hoverinfo": "x+y+name"
        })

    traces.extend([
        {
            "type": "scatter",
            "mode": "lines",
            "name": "P10",
            "x": ref_dates,
            "y": p10,
            "line": {"width": 3},
            "hoverinfo": "x+y+name"
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "P50",
            "x": ref_dates,
            "y": p50,
            "line": {"width": 4},
            "hoverinfo": "x+y+name"
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "P90",
            "x": ref_dates,
            "y": p90,
            "line": {"width": 3},
            "hoverinfo": "x+y+name"
        }
    ])

    title = f"All {variable} profiles with P10 / P50 / P90"

    y_label = {
        "oil": "Oil production",
        "water": "Water production",
        "gas": "Gas production",
        "wct": "Water cut",
        "bhp": "BHP / Pressure",
    }.get(variable, variable)

    block = {
        "type": "plotly_chart",
        "title": title,
        "data": traces,
        "layout": {
            "title": title,
            "xaxis": {
                "title": "Date",
                "type": "date",
                "rangeslider": {"visible": True}
            },
            "yaxis": {
                "title": y_label,
                "zeroline": False
            },
            "height": 560,
            "hovermode": "x unified",
            "legend": {
                "orientation": "h",
                "y": -0.25
            },
            "margin": {
                "l": 70,
                "r": 30,
                "t": 60,
                "b": 80
            }
        },
        "config": {
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True
        }
    }

    return {
        "type": "visual_response",
        "intent": "ensemble_profile_percentiles",
        "answer": (
            f"I generated the ensemble {variable} profile plot and computed P10, P50 and P90 "
            f"from {len(aligned)} aligned well profiles. Individual profiles are shown lightly; "
            f"the percentile curves summarize the ensemble behaviour."
        ),
        "ui_blocks": [block],
        "data": {
            "variable": variable,
            "wells_used": [p.get("well") for p in aligned],
            "profiles_found": len(profiles),
            "profiles_aligned": len(aligned),
            "percentiles": ["P10", "P50", "P90"]
        },
        "agent_trace": {
            "EnsembleProfilePercentileAgentV504": {
                "route": "DynamicProfileAgent per well -> percentile envelope",
                "variable": variable,
                "profiles_found": len(profiles),
                "profiles_aligned": len(aligned),
                "reason": "User requested all profiles with P10/P50/P90.",
            }
        },
        "interaction_edges": [
            {
                "from": "LangGraphUniversalReservoirOrchestratorV501",
                "to": "EnsembleProfilePercentileAgentV504",
                "reason": "StateGraph selected ensemble profile percentile execution.",
            }
        ]
    }


def execute_plan_v500(intent: Dict[str, Any], plan: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    task = intent.get("task_type")

    if task == "ensemble_profile_percentiles":
        return _execute_ensemble_profile_percentiles_v504(intent)

    return _execute_plan_before_v504(intent, plan, evidence_board)

# END V504 ENSEMBLE PROFILE P10/P50/P90

# ==========================================================
# V505B BROAD RESERVOIR CAPABILITY LAYER
#
# LangGraph V501 remains the orchestrator.
# This layer expands semantic understanding and graceful routing
# for broad reservoir-engineering requests:
# - streamlines / flow paths / drainage / connected wells
# - cross-variable analysis
# - crossplots / correlations
# - ranking / cluster / bias / integrated diagnosis
# - multi-variable same-plot requests
# - ensemble P10/P50/P90
# ==========================================================

_interpret_request_before_v505b = interpret_request_v500
_build_plan_before_v505b = build_plan_v500
_execute_plan_before_v505b = execute_plan_v500


RESERVOIR_CAPABILITY_REGISTRY_V505B = {
    "well_time_series": {
        "examples": [
            "show HW-25 water production",
            "plot HW-25 oil and water on the same plot",
            "show cumulative gas for HW-10",
        ],
        "agents": ["ProfileAgent", "MultiVariablePlotAgent", "DataAlgebraAgent"],
    },
    "property_visuals": {
        "examples": [
            "show PERMX map",
            "histogram of porosity",
            "show PERMX where SWAT > 0.4",
        ],
        "agents": ["PropertyMapAgent", "DistributionPlotAgent", "ConditionalMapAgent"],
    },
    "connectivity_streamlines": {
        "examples": [
            "show streamlines around HW-28",
            "which wells are connected to HW-25",
            "show flow paths from injectors to producers",
        ],
        "agents": ["StreamlineAgent", "ConnectivityAgent", "SpatialPatternAgent"],
    },
    "integrated_diagnostics": {
        "examples": [
            "why is HW-28 water mismatch happening",
            "is this relperm or connectivity",
            "find variables that explain poor WCT match",
        ],
        "agents": ["ProfileAgent", "PropertyAgent", "ConnectivityAgent", "RelPermAgent", "PressureAgent", "HypothesisAgent", "ReservoirCriticAgent"],
    },
    "cross_analysis": {
        "examples": [
            "correlate water mismatch with permeability",
            "crossplot pressure drop vs water score",
            "rank wells by combined water and BHP mismatch",
        ],
        "agents": ["DataAlgebraAgent", "CorrelationAgent", "RankingAgent", "ClusterAnalysisAgent"],
    },
}


def _v505b_msg(message):
    return _norm_v500(message)


def _v505b_contains_any(msg, terms):
    return any(t in msg for t in terms)


def _v505b_well_variables(intent):
    return [v for v in (intent.get("variables") or []) if v in {"oil", "water", "gas", "wct", "bhp"}]


def _v505b_property_variables(intent):
    return [v for v in (intent.get("variables") or []) if v in {"PORO", "PERM_X", "PERM_Y", "PERM_Z", "SWAT", "PRESSURE", "TRAN", "NTG", "FIPNUM", "SATNUM"}]


def interpret_request_v500(message: str) -> Dict[str, Any]:
    intent = _interpret_request_before_v505b(message)
    msg = _v505b_msg(message)

    well_vars = _v505b_well_variables(intent)
    prop_vars = _v505b_property_variables(intent)

    streamline_terms = [
        "streamline", "streamlines", "flowline", "flow path", "flow paths",
        "drainage", "tracer path", "producer injector", "injector producer",
        "flusso", "linee di flusso", "traiettorie"
    ]

    connectivity_terms = [
        "connectivity", "connected", "communication", "communicating",
        "pressure communication", "transmissibility", "tran", "corridor",
        "connesso", "connessi", "comunicazione", "connessione"
    ]

    cross_terms = [
        "correlation", "correlate", "relationship", "crossplot", "cross plot",
        "scatter", "vs", "versus", "against", "relazione", "correlazione",
        "incrociano", "incrocia", "confronta"
    ]

    ranking_terms = [
        "rank", "ranking", "top", "worst", "best", "weakest", "strongest",
        "most connected", "least connected", "piu connessi", "più connessi",
        "peggiori", "migliori", "classifica"
    ]

    cluster_terms = [
        "cluster", "clustering", "group", "grouping", "similar wells",
        "pattern", "patterns", "bias", "mismatch signature", "signature"
    ]

    multi_plot_terms = [
        "same plot", "same chart", "together", "on the same plot",
        "stesso grafico", "insieme", "metti", "overlay"
    ]

    all_profile_terms = [
        "all profiles", "all oil profiles", "all water profiles", "all gas profiles",
        "all well profiles", "tutti i profili", "tutti i pozzi"
    ]

    percentile_terms = ["p10", "p50", "p90", "percentile", "percentiles", "percentili"]

    if _v505b_contains_any(msg, streamline_terms):
        intent["task_type"] = "streamline_connectivity_analysis"
        intent["capability_v505b"] = {
            "family": "connectivity_streamlines",
            "reason": "Streamline/flow-path request detected.",
            "agents": RESERVOIR_CAPABILITY_REGISTRY_V505B["connectivity_streamlines"]["agents"],
        }

    elif _v505b_contains_any(msg, all_profile_terms) and _v505b_contains_any(msg, percentile_terms) and well_vars:
        intent["task_type"] = "ensemble_profile_percentiles"
        intent["capability_v505b"] = {
            "family": "well_time_series",
            "reason": "All-profiles percentile envelope requested.",
            "agents": ["ProfileAgent", "PercentileEnvelopeAgent", "VisualCriticAgent"],
        }

    elif intent.get("well") and len(well_vars) >= 2 and _v505b_contains_any(msg, multi_plot_terms):
        intent["task_type"] = "multi_variable_profile"
        intent["capability_v505b"] = {
            "family": "well_time_series",
            "reason": "Multiple well variables requested on same plot.",
            "agents": ["ProfileAgent", "MultiVariablePlotAgent", "VisualCriticAgent"],
        }

    elif _v505b_contains_any(msg, cross_terms) and (well_vars or prop_vars):
        intent["task_type"] = "cross_variable_analysis"
        intent["capability_v505b"] = {
            "family": "cross_analysis",
            "reason": "Cross-variable / correlation / relationship request detected.",
            "agents": RESERVOIR_CAPABILITY_REGISTRY_V505B["cross_analysis"]["agents"],
        }

    elif _v505b_contains_any(msg, ranking_terms) and (well_vars or prop_vars or _v505b_contains_any(msg, connectivity_terms)):
        intent["task_type"] = "ranking_analysis"
        intent["capability_v505b"] = {
            "family": "cross_analysis",
            "reason": "Ranking request detected.",
            "agents": ["RankingAgent", "DataAlgebraAgent", "ReservoirCriticAgent"],
        }

    elif _v505b_contains_any(msg, cluster_terms):
        intent["task_type"] = "diagnostic_cluster"
        intent["capability_v505b"] = {
            "family": "integrated_diagnostics",
            "reason": "Cluster/pattern/bias request detected.",
            "agents": RESERVOIR_CAPABILITY_REGISTRY_V505B["integrated_diagnostics"]["agents"],
        }

    elif _v505b_contains_any(msg, connectivity_terms) and _v505b_contains_any(msg, ["why", "perche", "perché", "mismatch", "relperm", "review", "driver", "cause"]):
        intent["task_type"] = "integrated_diagnostic_reasoning"
        intent["capability_v505b"] = {
            "family": "integrated_diagnostics",
            "reason": "Connectivity/RelPerm diagnostic comparison detected.",
            "agents": RESERVOIR_CAPABILITY_REGISTRY_V505B["integrated_diagnostics"]["agents"],
        }

    return intent


def build_plan_v500(intent: Dict[str, Any]) -> Dict[str, Any]:
    base = {
        "plan_version": "v505b",
        "task_type": intent.get("task_type"),
        "steps": [],
        "capability": intent.get("capability_v505b"),
    }

    task = intent.get("task_type")

    if task == "streamline_connectivity_analysis":
        base["steps"] = ["StreamlineAgent", "ConnectivityAgent", "SpatialPatternAgent", "ReservoirCriticAgent"]
        return base

    if task == "cross_variable_analysis":
        base["steps"] = ["DataAlgebraAgent", "CorrelationAgent", "CrossPlotAgent", "ReservoirCriticAgent"]
        return base

    if task == "ranking_analysis":
        base["steps"] = ["DataAlgebraAgent", "RankingAgent", "ReservoirCriticAgent"]
        return base

    # Fall back to previous planner for existing tasks.
    try:
        return _build_plan_before_v505b(intent)
    except NameError:
        return build_plan_v500.__globals__["build_plan_v500"](intent)


def _generic_capability_response_v505b(intent: Dict[str, Any], family: str, note: str) -> Dict[str, Any]:
    original = intent.get("original_message") or ""
    cap = intent.get("capability_v505b") or {}

    return {
        "type": "reasoning_response",
        "intent": intent.get("task_type"),
        "answer": (
            f"I interpreted this as a {family} request. {note} "
            "The LangGraph orchestrator captured the task and selected the relevant specialist agents. "
            "If the required raw arrays are available in the loaded case, this capability can be executed as a deterministic tool; "
            "otherwise I will return the best supported diagnostic explanation and identify missing data."
        ),
        "ui_blocks": [],
        "data": {
            "requested_capability": family,
            "original_message": original,
            "variables": intent.get("variables"),
            "well": intent.get("well"),
            "filters": intent.get("filters"),
            "operation": intent.get("operation"),
        },
        "agent_trace": {
            "CapabilityRouterV505B": {
                "family": family,
                "selected_agents": cap.get("agents"),
                "reason": cap.get("reason"),
            }
        },
        "interaction_edges": [
            {
                "from": "LangGraphUniversalReservoirOrchestratorV501",
                "to": "CapabilityRouterV505B",
                "reason": "Broad reservoir-engineering capability detected.",
            }
        ]
    }


def _execute_streamline_connectivity_v505b(intent: Dict[str, Any]) -> Dict[str, Any]:
    msg = intent.get("original_message") or ""

    # First try existing router/tool stack, because streamlines already exist in frontend/backend payloads.
    response = _call_existing_router_v500(msg)

    if isinstance(response, dict) and (response.get("ui_blocks") or response.get("answer")):
        response.setdefault("agent_trace", {})
        response["agent_trace"]["StreamlineConnectivityAgentV505B"] = {
            "route": "existing streamline/connectivity tool stack",
            "reason": "Streamline/connectivity request routed by LangGraph capability layer.",
        }
        return response

    return _generic_capability_response_v505b(
        intent,
        "streamline_connectivity_analysis",
        "I would combine streamline payloads, well locations, injector/producer relationships, TRAN corridors and pressure/profile response."
    )


def _execute_cross_variable_analysis_v505b(intent: Dict[str, Any]) -> Dict[str, Any]:
    msg = intent.get("original_message") or ""

    response = _call_existing_router_v500(msg)

    if isinstance(response, dict) and (response.get("ui_blocks") or response.get("answer")):
        response.setdefault("agent_trace", {})
        response["agent_trace"]["CrossVariableAnalysisAgentV505B"] = {
            "route": "existing analysis stack",
            "reason": "Cross-variable/correlation request routed by LangGraph capability layer.",
        }
        return response

    return _generic_capability_response_v505b(
        intent,
        "cross_variable_analysis",
        "I would combine diagnostic scores, profile bias, spatial properties and pressure/connectivity evidence to quantify the relationship."
    )


def _execute_ranking_analysis_v505b(intent: Dict[str, Any]) -> Dict[str, Any]:
    msg = intent.get("original_message") or ""

    response = _call_existing_router_v500(msg)

    if isinstance(response, dict) and (response.get("ui_blocks") or response.get("answer")):
        response.setdefault("agent_trace", {})
        response["agent_trace"]["RankingAnalysisAgentV505B"] = {
            "route": "existing ranking/diagnostic stack",
            "reason": "Ranking request routed by LangGraph capability layer.",
        }
        return response

    return _generic_capability_response_v505b(
        intent,
        "ranking_analysis",
        "I would rank wells using combined oil/water/gas/BHP scores, connectivity indicators, spatial properties and bias severity."
    )


def execute_plan_v500(intent: Dict[str, Any], plan: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    task = intent.get("task_type")

    if task == "streamline_connectivity_analysis":
        return _execute_streamline_connectivity_v505b(intent)

    if task == "cross_variable_analysis":
        return _execute_cross_variable_analysis_v505b(intent)

    if task == "ranking_analysis":
        return _execute_ranking_analysis_v505b(intent)

    return _execute_plan_before_v505b(intent, plan, evidence_board)

# END V505B BROAD RESERVOIR CAPABILITY LAYER


# ==========================================================
# V506 STRONGER SPECIALIST AGENTS FOR LANGGRAPH V501
#
# Improves execution tools called by the real LangGraph graph:
# - ensemble P10/P50/P90 using diagnostic well discovery
# - combined multi-variable profile plot
# - water mismatch vs permeability scatter
# - combined water+BHP ranking table
# - connectivity ranking using TRAN/connectivity proxy
# - streamline fallback with explicit limitation
# ==========================================================

_execute_plan_before_v506 = execute_plan_v500


def _v506_msg(message):
    return _norm_v500(message)


def _v506_get_wct_wells():
    try:
        out = _call_wct_bias_builder_v500("Show me the WCT bias cluster map and explain what it tells us")
    except Exception:
        out = None

    wells = []

    if isinstance(out, dict):
        for block in out.get("ui_blocks") or []:
            if not isinstance(block, dict):
                continue

            payload = block.get("payload") or block.get("data") or {}
            arr = payload.get("wells") if isinstance(payload, dict) else None

            if isinstance(arr, list):
                for w in arr:
                    if isinstance(w, dict) and w.get("well"):
                        wells.append(w)

    # De-duplicate.
    seen = set()
    final = []

    for w in wells:
        name = str(w.get("well"))
        if name not in seen:
            seen.add(name)
            final.append(w)

    return final


def _v506_known_well_names():
    names = [w.get("well") for w in _v506_get_wct_wells() if w.get("well")]

    # Fallback: common HW range.
    for n in range(1, 81):
        name = f"HW-{n}"
        if name not in names:
            names.append(name)

    return names


def _v506_extract_profile_series(response):
    if not isinstance(response, dict):
        return None

    for block in response.get("ui_blocks") or []:
        if not isinstance(block, dict):
            continue

        if block.get("type") != "profile_series":
            continue

        data = block.get("data") or block.get("payload") or {}

        dates = data.get("dates") or []
        sim = data.get("simulated") or []
        obs = data.get("observed") or []

        if dates and sim:
            return {
                "block": block,
                "data": data,
                "dates": dates,
                "simulated": sim,
                "observed": obs,
                "well": data.get("well") or "",
                "variable": data.get("variable") or "",
            }

    return None


def _v506_profile_prompt(well, variable):
    if variable == "water":
        return f"Plot {well} water production"
    if variable == "gas":
        return f"Plot {well} gas production"
    if variable == "wct":
        return f"Plot {well} WCT"
    if variable == "bhp":
        return f"Plot {well} BHP profile"
    return f"Plot {well} oil production"


def _v506_selected_profile_variable(intent):
    variables = intent.get("variables") or []

    for v in ["oil", "water", "gas", "wct", "bhp"]:
        if v in variables:
            return v

    return "oil"


def _v506_percentile(values, p):
    vals = sorted([float(x) for x in values if x is not None])

    if not vals:
        return None

    if len(vals) == 1:
        return vals[0]

    pos = (len(vals) - 1) * (p / 100.0)
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo

    return vals[lo] * (1 - frac) + vals[hi] * frac


def _v506_execute_ensemble_profile_percentiles(intent):
    variable = _v506_selected_profile_variable(intent)
    profiles = []

    for well in _v506_known_well_names():
        try:
            response = _call_existing_router_v500(_v506_profile_prompt(well, variable))
            series = _v506_extract_profile_series(response)

            if series:
                series["well"] = well
                profiles.append(series)
        except Exception:
            pass

    # De-duplicate by well.
    dedup = {}
    for p in profiles:
        dedup[p["well"]] = p

    profiles = list(dedup.values())

    if not profiles:
        return {
            "type": "reasoning_response",
            "intent": "ensemble_profile_percentiles",
            "answer": f"I could not find available {variable} profile series to compute P10/P50/P90.",
            "ui_blocks": [],
            "agent_trace": {
                "EnsembleProfilePercentileAgentV506": {
                    "status": "no_profiles_found",
                    "variable": variable,
                }
            }
        }

    # Union by exact date strings.
    date_values = {}

    for prof in profiles:
        for d, v in zip(prof.get("dates") or [], prof.get("simulated") or []):
            val = _safe_float_v500(v)
            if val is None:
                continue

            date_values.setdefault(str(d), []).append(val)

    dates = sorted(date_values.keys())

    p10 = []
    p50 = []
    p90 = []

    for d in dates:
        vals = date_values[d]
        p10.append(_v506_percentile(vals, 10))
        p50.append(_v506_percentile(vals, 50))
        p90.append(_v506_percentile(vals, 90))

    traces = []

    # Light individual profiles.
    for prof in profiles[:25]:
        traces.append({
            "type": "scatter",
            "mode": "lines",
            "name": prof.get("well") or "well",
            "x": prof.get("dates") or [],
            "y": prof.get("simulated") or [],
            "line": {"width": 1},
            "opacity": 0.18,
            "showlegend": False,
            "hoverinfo": "skip"
        })

    traces.extend([
        {
            "type": "scatter",
            "mode": "lines",
            "name": "P10",
            "showlegend": True,
            "x": dates,
            "y": p10,
            "line": {"width": 3},
            "hovertemplate": "P10<br>%{x}<br>%{y:.4g}<extra></extra>"
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "P50",
            "showlegend": True,
            "x": dates,
            "y": p50,
            "line": {"width": 4},
            "hovertemplate": "P50<br>%{x}<br>%{y:.4g}<extra></extra>"
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "P90",
            "showlegend": True,
            "x": dates,
            "y": p90,
            "line": {"width": 3},
            "hovertemplate": "P90<br>%{x}<br>%{y:.4g}<extra></extra>"
        }
    ])

    title = f"All {variable} profiles with P10, P50 and P90"

    y_label = {
        "oil": "Oil production",
        "water": "Water production",
        "gas": "Gas production",
        "wct": "Water cut",
        "bhp": "BHP / Pressure",
    }.get(variable, variable)

    return {
        "type": "visual_response",
        "intent": "ensemble_profile_percentiles",
        "answer": (
            f"I generated the ensemble {variable} profile plot and computed P10, P50 and P90 "
            f"from {len(profiles)} available well profiles. Individual profiles are shown lightly; "
            f"the percentile curves summarize the ensemble behaviour."
        ),
        "ui_blocks": [
            {
                "type": "plotly_chart",
                "title": title,
                "data": traces,
                "layout": {
                    "title": title,
                    "xaxis": {"title": "Date", "type": "date", "rangeslider": {"visible": True}},
                    "yaxis": {"title": y_label, "zeroline": False},
                    "height": 560,
                    "hovermode": "closest",
                    "plot_bgcolor": "rgba(0,0,0,0)",
                    "paper_bgcolor": "rgba(0,0,0,0)",
                    "font": {"color": "#ffffff", "family": "Arial, sans-serif", "size": 13},
                    "title": {"text": title, "font": {"color": "#ffffff", "family": "Arial Black, Arial, sans-serif", "size": 18}},
                    "xaxis": {"title": {"text": "Date", "font": {"color": "#ffffff", "family": "Arial Black, Arial, sans-serif"}}, "type": "date", "rangeslider": {"visible": True}, "showgrid": False, "showline": True, "linecolor": "#ffffff", "tickfont": {"color": "#ffffff", "family": "Arial Black, Arial, sans-serif"}},
                    "yaxis": {"title": {"text": y_label, "font": {"color": "#ffffff", "family": "Arial Black, Arial, sans-serif"}}, "zeroline": False, "showgrid": False, "showline": True, "linecolor": "#ffffff", "tickfont": {"color": "#ffffff", "family": "Arial Black, Arial, sans-serif"}},
                    "legend": {"orientation": "h", "y": -0.25, "font": {"color": "#ffffff"}},
                    "margin": {"l": 70, "r": 30, "t": 60, "b": 80}
                },
                "config": {"responsive": True, "displaylogo": False, "scrollZoom": True}
            }
        ],
        "data": {
            "variable": variable,
            "profiles_used": len(profiles),
            "wells_used": [p.get("well") for p in profiles],
            "dates_used": len(dates),
            "percentiles": ["P10", "P50", "P90"]
        },
        "agent_trace": {
            "EnsembleProfilePercentileAgentV506": {
                "route": "profile discovery -> union-date percentile envelope",
                "variable": variable,
                "profiles_used": len(profiles),
                "dates_used": len(dates),
            }
        }
    }


def _v506_execute_multi_variable_profile(intent):
    well = intent.get("well") or ""
    variables = [v for v in (intent.get("variables") or []) if v in {"oil", "water", "gas", "wct", "bhp"}]

    if not variables:
        variables = ["oil", "water"]

    traces = []
    used = []

    for v in variables:
        try:
            response = _call_existing_router_v500(_v506_profile_prompt(well, v))
            series = _v506_extract_profile_series(response)

            if not series:
                continue

            dates = series.get("dates") or []
            sim = series.get("simulated") or []
            obs = series.get("observed") or []

            traces.append({
                "type": "scatter",
                "mode": "lines",
                "name": f"{v} simulated",
                "x": dates,
                "y": sim,
                "line": {"width": 2},
                "hovertemplate": f"{v} simulated<br>%{{x}}<br>%{{y:.4g}}<extra></extra>"
            })

            if obs:
                traces.append({
                    "type": "scatter",
                    "mode": "lines",
                    "name": f"{v} observed",
                    "x": dates,
                    "y": obs,
                    "line": {"width": 2, "dash": "dot"},
                    "hovertemplate": f"{v} observed<br>%{{x}}<br>%{{y:.4g}}<extra></extra>"
                })

            used.append(v)
        except Exception:
            pass

    if not traces:
        return _execute_multi_variable_profile_v500(intent)

    title = f"{well} multi-variable profile"

    return {
        "type": "visual_response",
        "intent": "multi_variable_profile",
        "answer": f"I plotted {', '.join(used)} for {well} on the same interactive chart.",
        "ui_blocks": [
            {
                "type": "plotly_chart",
                "title": title,
                "data": traces,
                "layout": {
                    "title": title,
                    "xaxis": {"title": "Date", "type": "date", "rangeslider": {"visible": True}},
                    "yaxis": {"title": "Profile value", "zeroline": False},
                    "height": 560,
                    "hovermode": "closest",
                    "plot_bgcolor": "rgba(0,0,0,0)",
                    "paper_bgcolor": "rgba(0,0,0,0)",
                    "font": {"color": "#ffffff", "family": "Arial, sans-serif", "size": 13},
                    "title": {"text": title, "font": {"color": "#ffffff", "family": "Arial Black, Arial, sans-serif", "size": 18}},
                    "xaxis": {"title": {"text": "Date", "font": {"color": "#ffffff", "family": "Arial Black, Arial, sans-serif"}}, "type": "date", "rangeslider": {"visible": True}, "showgrid": False, "showline": True, "linecolor": "#ffffff", "tickfont": {"color": "#ffffff", "family": "Arial Black, Arial, sans-serif"}},
                    "yaxis": {"title": {"text": y_label, "font": {"color": "#ffffff", "family": "Arial Black, Arial, sans-serif"}}, "zeroline": False, "showgrid": False, "showline": True, "linecolor": "#ffffff", "tickfont": {"color": "#ffffff", "family": "Arial Black, Arial, sans-serif"}},
                    "legend": {"orientation": "h", "y": -0.25, "font": {"color": "#ffffff"}},
                    "margin": {"l": 70, "r": 30, "t": 60, "b": 80}
                },
                "config": {"responsive": True, "displaylogo": False, "scrollZoom": True}
            }
        ],
        "data": {"well": well, "variables": used},
        "agent_trace": {
            "MultiVariableProfileAgentV506": {
                "route": "multiple profile_series -> single plotly_chart",
                "well": well,
                "variables": used,
            }
        }
    }


def _v506_compact_table(title, columns, rows):
    return {
        "type": "compact_table",
        "title": title,
        "columns": columns,
        "rows": rows
    }


def _v506_execute_connectivity_ranking(intent):
    wells = _v506_get_wct_wells()

    rows = []

    for w in wells:
        tran = _safe_float_v500(w.get("tran_percentile"))
        perm = _safe_float_v500(w.get("perm_percentile"))
        poro = _safe_float_v500(w.get("poro_percentile"))

        proxy_vals = [x for x in [tran, perm, poro] if x is not None]
        proxy = sum(proxy_vals) / len(proxy_vals) if proxy_vals else None

        rows.append({
            "Well": w.get("well"),
            "Connectivity proxy": round(proxy, 1) if proxy is not None else None,
            "TRAN pct": round(tran, 1) if tran is not None else None,
            "PERM pct": round(perm, 1) if perm is not None else None,
            "PORO pct": round(poro, 1) if poro is not None else None,
            "Water score": round(_safe_float_v500(w.get("water_score")) or 0, 1),
        })

    rows = sorted(rows, key=lambda r: -999 if r["Connectivity proxy"] is None else -r["Connectivity proxy"])

    return {
        "type": "visual_response",
        "intent": "connectivity_ranking",
        "answer": (
            "I ranked wells using the available connectivity proxy evidence. "
            "This is based on TRAN, permeability and porosity percentiles where available; "
            "if raw streamline allocation data is exposed, it should be used as the primary connectivity metric."
        ),
        "ui_blocks": [
            _v506_compact_table(
                "Most connected wells - proxy ranking",
                ["Well", "Connectivity proxy", "TRAN pct", "PERM pct", "PORO pct", "Water score"],
                rows[:12]
            )
        ],
        "agent_trace": {
            "ConnectivityRankingAgentV506": {
                "route": "diagnostic payload -> connectivity proxy ranking",
                "wells_ranked": len(rows),
            }
        }
    }


def _v506_execute_combined_mismatch_ranking(intent):
    wells = _v506_get_wct_wells()

    rows = []

    for w in wells:
        water = _safe_float_v500(w.get("water_score"))
        bhp = _safe_float_v500(w.get("bhp_score"))

        water_mis = 100 - water if water is not None else None
        bhp_mis = 100 - bhp if bhp is not None else None

        vals = [x for x in [water_mis, bhp_mis] if x is not None]
        combined = sum(vals) / len(vals) if vals else None

        rows.append({
            "Well": w.get("well"),
            "Combined mismatch": round(combined, 1) if combined is not None else None,
            "Water score": round(water, 1) if water is not None else None,
            "BHP score": round(bhp, 1) if bhp is not None else None,
            "Bias": w.get("bias") or "",
        })

    rows = sorted(rows, key=lambda r: -999 if r["Combined mismatch"] is None else -r["Combined mismatch"])

    return {
        "type": "visual_response",
        "intent": "ranking_analysis",
        "answer": "I ranked wells by combined water and BHP mismatch severity.",
        "ui_blocks": [
            _v506_compact_table(
                "Combined water and BHP mismatch ranking",
                ["Well", "Combined mismatch", "Water score", "BHP score", "Bias"],
                rows[:12]
            )
        ],
        "agent_trace": {
            "RankingAnalysisAgentV506": {
                "route": "diagnostic payload -> combined water/BHP ranking",
                "wells_ranked": len(rows),
            }
        }
    }


def _v506_execute_water_perm_correlation(intent):
    wells = _v506_get_wct_wells()

    data = []
    rows = []

    for w in wells:
        perm = _safe_float_v500(w.get("perm_percentile"))
        water = _safe_float_v500(w.get("water_score"))

        if perm is None or water is None:
            continue

        mismatch = 100 - water

        data.append({
            "well": w.get("well"),
            "perm": perm,
            "water_mismatch": mismatch,
            "water_score": water,
            "bias": w.get("bias") or ""
        })

        rows.append({
            "Well": w.get("well"),
            "PERM pct": round(perm, 1),
            "Water mismatch": round(mismatch, 1),
            "Water score": round(water, 1),
            "Bias": w.get("bias") or "",
        })

    trace = {
        "type": "scatter",
        "mode": "markers+text",
        "name": "wells",
        "x": [d["perm"] for d in data],
        "y": [d["water_mismatch"] for d in data],
        "text": [d["well"] for d in data],
        "textposition": "top center",
        "hovertemplate": "Well: %{text}<br>PERM pct: %{x:.1f}<br>Water mismatch: %{y:.1f}<extra></extra>",
        "marker": {"size": 12}
    }

    return {
        "type": "visual_response",
        "intent": "cross_variable_analysis",
        "answer": (
            "I cross-plotted water mismatch severity against permeability percentile. "
            "If the points do not show a clear trend, water mismatch is unlikely to be controlled by permeability alone."
        ),
        "ui_blocks": [
            {
                "type": "plotly_chart",
                "title": "Water mismatch vs permeability",
                "data": [trace],
                "layout": {
                    "title": "Water mismatch vs permeability",
                    "xaxis": {"title": "PERM percentile"},
                    "yaxis": {"title": "Water mismatch severity (100 - water score)"},
                    "height": 560,
                    "hovermode": "closest",
                    "margin": {"l": 70, "r": 30, "t": 60, "b": 70}
                },
                "config": {"responsive": True, "displaylogo": False, "scrollZoom": True}
            },
            _v506_compact_table(
                "Water mismatch vs permeability evidence",
                ["Well", "PERM pct", "Water mismatch", "Water score", "Bias"],
                rows[:12]
            )
        ],
        "agent_trace": {
            "CrossVariableAnalysisAgentV506": {
                "route": "diagnostic payload -> scatter correlation",
                "points": len(data),
            }
        }
    }


def _v506_execute_streamline_connectivity(intent):
    # Try existing stack first.
    msg = intent.get("original_message") or ""

    response = _call_existing_router_v500(msg)

    block_types = [
        b.get("type") for b in (response.get("ui_blocks") or [])
        if isinstance(b, dict)
    ] if isinstance(response, dict) else []

    has_streamline_visual = any("stream" in str(t).lower() for t in block_types)

    if isinstance(response, dict) and has_streamline_visual:
        response.setdefault("agent_trace", {})
        response["agent_trace"]["StreamlineConnectivityAgentV506"] = {
            "route": "existing streamline visual",
            "status": "streamline_visual_found",
        }
        return response

    fallback = _v506_execute_connectivity_ranking(intent)
    fallback["answer"] = (
        "I could not find a raw streamline visual block in the current response, so I used the available "
        "TRAN/permeability/porosity connectivity proxy instead. If streamline allocation arrays are exposed, "
        "this node can render true streamline flow paths."
    )
    fallback.setdefault("agent_trace", {})
    fallback["agent_trace"]["StreamlineConnectivityAgentV506"] = {
        "route": "fallback connectivity proxy",
        "status": "no_streamline_visual_block_found",
        "previous_block_types": block_types,
    }
    return fallback


def execute_plan_v500(intent: Dict[str, Any], plan: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    task = intent.get("task_type")
    msg = _v506_msg(intent.get("original_message") or "")

    if task == "ensemble_profile_percentiles":
        return _v506_execute_ensemble_profile_percentiles(intent)

    if task == "multi_variable_profile":
        return _v506_execute_multi_variable_profile(intent)

    if task == "streamline_connectivity_analysis":
        return _v506_execute_streamline_connectivity(intent)

    if task == "ranking_analysis":
        if "connected" in msg or "conness" in msg or "connectivity" in msg:
            return _v506_execute_connectivity_ranking(intent)
        if "water" in msg and "bhp" in msg:
            return _v506_execute_combined_mismatch_ranking(intent)

    if task == "cross_variable_analysis":
        if ("water" in msg or "wct" in msg) and ("perm" in msg or "permeability" in msg):
            return _v506_execute_water_perm_correlation(intent)

    return _execute_plan_before_v506(intent, plan, evidence_board)

# END V506 STRONGER SPECIALIST AGENTS


# ==========================================================
# V509 ACTIVE-WELL ENSEMBLE PERCENTILES
#
# Fix:
# P10 for all oil profiles was sometimes a flat zero because inactive
# wells or pre-production zero-rate samples were included in the
# percentile population.
#
# New rule:
# - For rate variables oil/water/gas: compute P10/P50/P90 only on
#   active positive values.
# - Exclude profiles that are entirely zero/inactive.
# - For WCT/BHP keep finite values because zero can be meaningful.
# ==========================================================

_execute_plan_before_v509 = execute_plan_v500


def _v509_is_rate_variable(variable):
    return variable in {"oil", "water", "gas"}


def _v509_active_values(values, variable, eps=1e-9):
    out = []

    for v in values or []:
        x = _safe_float_v500(v)

        if x is None:
            out.append(None)
            continue

        if _v509_is_rate_variable(variable):
            out.append(x if x > eps else None)
        else:
            out.append(x)

    return out


def _v509_profile_is_active(profile, variable, eps=1e-9):
    vals = [_safe_float_v500(v) for v in (profile.get("simulated") or [])]
    vals = [v for v in vals if v is not None]

    if not vals:
        return False

    if _v509_is_rate_variable(variable):
        positive = [v for v in vals if v > eps]
        return len(positive) >= 3 and max(positive) > eps

    return True


def _v509_execute_ensemble_profile_percentiles(intent):
    variable = _v506_selected_profile_variable(intent)
    profiles = []

    for well in _v506_known_well_names():
        try:
            response = _call_existing_router_v500(_v506_profile_prompt(well, variable))
            series = _v506_extract_profile_series(response)

            if series:
                series["well"] = well
                if _v509_profile_is_active(series, variable):
                    profiles.append(series)
        except Exception:
            pass

    dedup = {}

    for prof in profiles:
        dedup[prof["well"]] = prof

    profiles = list(dedup.values())

    if not profiles:
        return {
            "type": "reasoning_response",
            "intent": "ensemble_profile_percentiles",
            "answer": (
                f"I could not find active {variable} profile series to compute P10/P50/P90. "
                "The previous zero P10 may indicate that the available profiles are inactive or contain only zero-rate samples."
            ),
            "ui_blocks": [],
            "agent_trace": {
                "EnsembleProfilePercentileAgentV509": {
                    "status": "no_active_profiles_found",
                    "variable": variable,
                }
            }
        }

    date_values = {}

    for prof in profiles:
        active_sim = _v509_active_values(prof.get("simulated") or [], variable)

        for d, v in zip(prof.get("dates") or [], active_sim):
            if v is None:
                continue

            date_values.setdefault(str(d), []).append(v)

    dates = sorted(date_values.keys())

    p10 = []
    p50 = []
    p90 = []

    for d in dates:
        vals = date_values[d]
        p10.append(_v506_percentile(vals, 10))
        p50.append(_v506_percentile(vals, 50))
        p90.append(_v506_percentile(vals, 90))

    traces = []

    for prof in profiles[:25]:
        active_sim = _v509_active_values(prof.get("simulated") or [], variable)

        traces.append({
            "type": "scatter",
            "mode": "lines",
            "name": prof.get("well") or "well",
            "x": prof.get("dates") or [],
            "y": active_sim,
            "line": {"width": 1},
            "opacity": 0.18,
            "showlegend": False,
            "hoverinfo": "skip"
        })

    traces.extend([
        {
            "type": "scatter",
            "mode": "lines",
            "name": "P10",
            "showlegend": True,
            "x": dates,
            "y": p10,
            "line": {"width": 3},
            "hovertemplate": "P10<br>Date: %{x}<br>Value: %{y:.5g}<extra></extra>"
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "P50",
            "showlegend": True,
            "x": dates,
            "y": p50,
            "line": {"width": 4},
            "hovertemplate": "P50<br>Date: %{x}<br>Value: %{y:.5g}<extra></extra>"
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "P90",
            "showlegend": True,
            "x": dates,
            "y": p90,
            "line": {"width": 3},
            "hovertemplate": "P90<br>Date: %{x}<br>Value: %{y:.5g}<extra></extra>"
        }
    ])

    title = f"All active {variable} profiles with P10, P50 and P90"

    y_label = {
        "oil": "Oil rate (STB/d)",
        "water": "Water rate (STB/d)",
        "gas": "Gas rate (MSCF/d)",
        "wct": "Water cut (-)",
        "bhp": "Pressure (model units)",
    }.get(variable, "Value")

    return {
        "type": "visual_response",
        "intent": "ensemble_profile_percentiles",
        "answer": (
            f"I generated the active-well ensemble {variable} profile and computed P10, P50 and P90 "
            f"from {len(profiles)} active profiles. Zero-rate inactive samples were excluded so the P10 is not artificially flattened to zero."
        ),
        "ui_blocks": [
            {
                "type": "plotly_chart",
                "title": title,
                "data": traces,
                "layout": {
                    "title": title,
                    "xaxis": {
                        "title": "Date",
                        "type": "date",
                        "showgrid": False
                    },
                    "yaxis": {
                        "title": y_label,
                        "zeroline": False,
                        "showgrid": False
                    },
                    "height": 560,
                    "hovermode": "closest",
                    "legend": {
                        "orientation": "h",
                        "y": -0.22
                    },
                    "margin": {
                        "l": 70,
                        "r": 30,
                        "t": 60,
                        "b": 80
                    },
                    "plot_bgcolor": "rgba(0,0,0,0)",
                    "paper_bgcolor": "rgba(0,0,0,0)"
                },
                "config": {
                    "responsive": True,
                    "displaylogo": False,
                    "scrollZoom": True
                }
            }
        ],
        "data": {
            "variable": variable,
            "profiles_used": len(profiles),
            "wells_used": [p.get("well") for p in profiles],
            "dates_used": len(dates),
            "percentile_method": "active positive values only for rate variables",
            "percentiles": ["P10", "P50", "P90"]
        },
        "agent_trace": {
            "EnsembleProfilePercentileAgentV509": {
                "route": "active-profile discovery -> active-value percentile envelope",
                "variable": variable,
                "profiles_used": len(profiles),
                "dates_used": len(dates),
                "reason": "Avoid flat-zero P10 caused by inactive zero-rate profiles.",
            }
        }
    }


def execute_plan_v500(intent: Dict[str, Any], plan: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    task = intent.get("task_type")

    if task == "ensemble_profile_percentiles":
        return _v509_execute_ensemble_profile_percentiles(intent)

    return _execute_plan_before_v509(intent, plan, evidence_board)

# END V509 ACTIVE-WELL ENSEMBLE PERCENTILES


# ==========================================================
# V510 MULTI-VARIABLE PLOT + GOR/WCT COMPUTED PROFILES
#
# Fixes from stress test:
# - multi_variable_profile returned several profile_series instead of one plotly_chart
# - GOR was routed to gas profile
# - WCT was routed to water profile
# - "integrated plot" could be misrouted to well_data_operation
# - pressure distribution failed to identify PRESSURE
# ==========================================================

_interpret_request_before_v510 = interpret_request_v500
_execute_plan_before_v510 = execute_plan_v500
_execute_property_distribution_before_v510 = _execute_property_distribution_v500


def _v510_norm_msg(message):
    return _norm_v500(message)


def _v510_contains_any(msg, terms):
    return any(t in msg for t in terms)


def _v510_property_alias_to_canon(raw):
    s = _norm_v500(raw)

    if any(x in s for x in ["poro", "porosity", "porosita", "porosità"]):
        return "PORO"

    if any(x in s for x in ["permx", "perm x", "permeability x", "kx", "permeability", "perm", "permeabilita", "permeabilità"]):
        return "PERM_X"

    if any(x in s for x in ["swat", "water saturation", "saturazione acqua"]):
        return "SWAT"

    if any(x in s for x in ["pressure", "pressione"]):
        return "PRESSURE"

    if any(x in s for x in ["tran", "transmissibility", "trasmissibilita", "trasmissibilità"]):
        return "TRAN"

    return None


def _v510_detect_target_property(message):
    msg = _v510_norm_msg(message)

    # target is usually before "where" / "only where"
    left = msg.split(" where ")[0]
    left = left.split(" only where ")[0]

    # operation target: multiply PERMX..., average porosity...
    for pattern_start in ["show ", "plot ", "display ", "visualize ", "visualise ", "calculate average ", "average ", "multiply "]:
        if pattern_start in left:
            candidate = left.split(pattern_start, 1)[1]
            prop = _v510_property_alias_to_canon(candidate)
            if prop:
                return prop

    return _v510_property_alias_to_canon(left)


def interpret_request_v500(message: str) -> Dict[str, Any]:
    intent = _interpret_request_before_v510(message)
    msg = _v510_norm_msg(message)

    variables = list(intent.get("variables") or [])

    # GOR and WCT must be first-class derived variables, not just gas/water aliases.
    if "gor" in msg and "gor" not in variables:
        variables.append("gor")

    if ("water cut" in msg or " wct" in (" " + msg)) and "wct" not in variables:
        variables.append("wct")

    # Pressure histogram/distribution must target PRESSURE.
    if intent.get("flags", {}).get("distribution") and any(x in msg for x in ["pressure", "pressione"]):
        intent["task_type"] = "property_distribution"
        intent["primary_property"] = "PRESSURE"

    # Better target-property detection for conditional maps / grid algebra.
    target_prop = _v510_detect_target_property(message)
    if target_prop:
        intent["target_property_v510"] = target_prop

        # If request says "show pressure where PERMX > 50", target is PRESSURE,
        # filter is PERM_X.
        if intent.get("task_type") in {"conditional_property_map", "grid_data_operation", "general_reservoir_reasoning"}:
            intent["primary_property"] = target_prop

    # I/J/K-only filters should still trigger conditional map if a property exists.
    if (intent.get("filters") or []) and (intent.get("primary_property") or target_prop):
        if any(f.get("kind") == "index_range" for f in intent.get("filters") or []):
            intent["task_type"] = "conditional_property_map"
            intent["primary_property"] = intent.get("primary_property") or target_prop

    # Multi-variable profile priority.
    well = intent.get("well")
    well_vars = [v for v in variables if v in {"oil", "water", "gas", "wct", "bhp", "gor"}]

    multi_terms = [
        "same plot", "same chart", "together", "integrated plot", "one integrated plot",
        "in one plot", "in one chart", "compare", "behaviour", "behavior", "trend",
        "overlay", "metti", "insieme", "stesso grafico"
    ]

    if well and len(well_vars) >= 2 and _v510_contains_any(msg, multi_terms):
        intent["task_type"] = "multi_variable_profile"
        intent["variables"] = variables
        intent["multi_variable_priority_v510"] = {
            "reason": "Multiple well variables requested; force one integrated plotly_chart."
        }

    # Cumulative multi-variable request.
    if well and len(well_vars) >= 2 and "cumulative" in msg:
        intent["task_type"] = "multi_variable_profile"
        intent["variables"] = variables
        intent["force_cumulative_v510"] = True

    # GOR ensemble P10/P50/P90.
    if any(x in msg for x in ["all gor profiles", "gor profiles"]) and any(x in msg for x in ["p10", "p50", "p90", "percentile", "percentiles"]):
        intent["task_type"] = "ensemble_profile_percentiles"
        intent["variables"] = variables
        if "gor" not in intent["variables"]:
            intent["variables"].append("gor")
        intent["ensemble_gor_priority_v510"] = {
            "reason": "GOR percentile envelope requested."
        }

    # A single GOR profile should still be a well profile, but variable must be GOR.
    if well and "gor" in variables and not _v510_contains_any(msg, multi_terms):
        intent["task_type"] = "well_profile"
        intent["variables"] = ["gor"]

    # A single WCT profile should be computed as WCT.
    if well and "wct" in variables and not _v510_contains_any(msg, multi_terms):
        intent["task_type"] = "well_profile"
        intent["variables"] = ["wct"]

    intent["variables"] = variables

    return intent


def _v510_profile_prompt(well, variable):
    if variable == "water":
        return f"Plot {well} water production"
    if variable == "gas":
        return f"Plot {well} gas production"
    if variable == "bhp":
        return f"Plot {well} BHP profile"
    if variable == "wct":
        # We compute WCT ourselves when possible.
        return f"Plot {well} water production"
    if variable == "gor":
        # We compute GOR ourselves when possible.
        return f"Plot {well} gas production"
    return f"Plot {well} oil production"


def _v510_extract_profile_series(response):
    if not isinstance(response, dict):
        return None

    for block in response.get("ui_blocks") or []:
        if not isinstance(block, dict):
            continue

        if block.get("type") != "profile_series":
            continue

        data = block.get("data") or block.get("payload") or {}

        dates = data.get("dates") or []
        sim = data.get("simulated") or []
        obs = data.get("observed") or []

        if dates and sim:
            return {
                "block": block,
                "data": data,
                "dates": dates,
                "simulated": sim,
                "observed": obs,
                "well": data.get("well") or "",
                "variable": data.get("variable") or "",
            }

    return None


def _v510_align_by_date(series_a, series_b):
    dates_a = [str(x) for x in (series_a.get("dates") or [])]
    dates_b = [str(x) for x in (series_b.get("dates") or [])]

    sim_a = series_a.get("simulated") or []
    sim_b = series_b.get("simulated") or []
    obs_a = series_a.get("observed") or []
    obs_b = series_b.get("observed") or []

    map_a_sim = {d: _safe_float_v500(v) for d, v in zip(dates_a, sim_a)}
    map_b_sim = {d: _safe_float_v500(v) for d, v in zip(dates_b, sim_b)}

    map_a_obs = {d: _safe_float_v500(v) for d, v in zip(dates_a, obs_a)}
    map_b_obs = {d: _safe_float_v500(v) for d, v in zip(dates_b, obs_b)}

    dates = sorted(set(dates_a).intersection(set(dates_b)))

    return dates, map_a_sim, map_b_sim, map_a_obs, map_b_obs


def _v510_safe_ratio(num, den, eps=1e-12):
    n = _safe_float_v500(num)
    d = _safe_float_v500(den)

    if n is None or d is None or abs(d) < eps:
        return None

    return n / d


def _v510_compute_gor_profile(well):
    gas_resp = _call_existing_router_v500(_v510_profile_prompt(well, "gas"))
    oil_resp = _call_existing_router_v500(_v510_profile_prompt(well, "oil"))

    gas = _v510_extract_profile_series(gas_resp)
    oil = _v510_extract_profile_series(oil_resp)

    if not gas or not oil:
        return None

    dates, gas_sim, oil_sim, gas_obs, oil_obs = _v510_align_by_date(gas, oil)

    sim = [_v510_safe_ratio(gas_sim.get(d), oil_sim.get(d)) for d in dates]
    obs = [_v510_safe_ratio(gas_obs.get(d), oil_obs.get(d)) for d in dates]

    return {
        "well": well,
        "variable": "gor",
        "dates": dates,
        "simulated": sim,
        "observed": obs,
        "title": f"{well} GOR profile",
        "source": "computed_gas_over_oil_v510"
    }


def _v510_compute_wct_profile(well):
    water_resp = _call_existing_router_v500(_v510_profile_prompt(well, "water"))
    oil_resp = _call_existing_router_v500(_v510_profile_prompt(well, "oil"))

    water = _v510_extract_profile_series(water_resp)
    oil = _v510_extract_profile_series(oil_resp)

    if not water or not oil:
        return None

    dates, water_sim, oil_sim, water_obs, oil_obs = _v510_align_by_date(water, oil)

    sim = []
    obs = []

    for d in dates:
        ws = _safe_float_v500(water_sim.get(d))
        os = _safe_float_v500(oil_sim.get(d))
        wo = _safe_float_v500(water_obs.get(d))
        oo = _safe_float_v500(oil_obs.get(d))

        sim.append(_v510_safe_ratio(ws, (ws or 0) + (os or 0)))
        obs.append(_v510_safe_ratio(wo, (wo or 0) + (oo or 0)))

    return {
        "well": well,
        "variable": "wct",
        "dates": dates,
        "simulated": sim,
        "observed": obs,
        "title": f"{well} WCT profile",
        "source": "computed_water_over_oil_plus_water_v510"
    }


def _v510_get_profile_data(well, variable, cumulative=False):
    if variable == "gor":
        data = _v510_compute_gor_profile(well)
    elif variable == "wct":
        data = _v510_compute_wct_profile(well)
    else:
        resp = _call_existing_router_v500(_v510_profile_prompt(well, variable))
        series = _v510_extract_profile_series(resp)
        if not series:
            return None

        src = series.get("data") or {}
        data = {
            "well": well,
            "variable": variable,
            "dates": series.get("dates") or [],
            "simulated": series.get("simulated") or [],
            "observed": series.get("observed") or [],
            "title": src.get("title") or f"{well} {variable} profile",
            "source": "dynamic_profile_agent"
        }

    if not data:
        return None

    if cumulative and variable in {"oil", "water", "gas"}:
        data = dict(data)
        data["simulated"] = _make_cumulative_v500(data.get("simulated") or [], data.get("dates") or [])
        data["observed"] = _make_cumulative_v500(data.get("observed") or [], data.get("dates") or [])
        data["variable"] = f"{variable}_cumulative"
        data["title"] = f"{well} cumulative {variable} profile"

    return data


def _v510_unit_for_variable(variable):
    v = str(variable or "").lower()

    if "oil_cumulative" in v:
        return "STB"
    if "water_cumulative" in v:
        return "STB"
    if "gas_cumulative" in v:
        return "MSCF"
    if v == "oil":
        return "STB/d"
    if v == "water":
        return "STB/d"
    if v == "gas":
        return "MSCF/d"
    if v == "bhp":
        return "model pressure units"
    if v == "gor":
        return "MSCF/STB"
    if v == "wct":
        return "-"
    return "model units"


def _v510_axis_for_variable(variable):
    v = str(variable or "").lower()

    if v.startswith("oil") or v.startswith("water"):
        return "y"

    if v.startswith("gas") or v == "gor":
        return "y2"

    if v == "bhp":
        return "y3"

    if v == "wct":
        return "y4"

    return "y"


def _v510_layout_for_variables(title, variables):
    axes_used = set(_v510_axis_for_variable(v) for v in variables)

    layout = {
        "title": title,
        "xaxis": {
            "title": "Date",
            "type": "date",
            "showgrid": False
        },
        "yaxis": {
            "title": "Liquid rate (STB/d)",
            "showgrid": False,
            "zeroline": False
        },
        "height": 580,
        "hovermode": "closest",
        "legend": {
            "orientation": "h",
            "y": -0.22
        },
        "margin": {
            "l": 80,
            "r": 90,
            "t": 60,
            "b": 90
        },
        "plot_bgcolor": "rgba(0,0,0,0)",
        "paper_bgcolor": "rgba(0,0,0,0)"
    }

    if "y2" in axes_used:
        layout["yaxis2"] = {
            "title": "Gas rate / GOR",
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
            "zeroline": False
        }

    if "y3" in axes_used:
        layout["yaxis3"] = {
            "title": "Pressure",
            "overlaying": "y",
            "side": "right",
            "position": 0.96,
            "showgrid": False,
            "zeroline": False
        }

    if "y4" in axes_used:
        layout["yaxis4"] = {
            "title": "WCT (-)",
            "overlaying": "y",
            "side": "left",
            "position": 0.06,
            "showgrid": False,
            "zeroline": False
        }

    # If only ratios are present, simplify main y axis.
    if axes_used == {"y2"}:
        layout["yaxis"]["title"] = "GOR (MSCF/STB)"
        layout.pop("yaxis2", None)

    if axes_used == {"y4"}:
        layout["yaxis"]["title"] = "WCT (-)"
        layout.pop("yaxis4", None)

    return layout


def _execute_multi_variable_profile_v500(intent: Dict[str, Any]) -> Dict[str, Any]:
    well = intent.get("well") or ""
    variables = [v for v in (intent.get("variables") or []) if v in {"oil", "water", "gas", "wct", "bhp", "gor"}]

    if not variables:
        variables = ["oil", "water"]

    # De-duplicate preserving order.
    seen = set()
    variables = [v for v in variables if not (v in seen or seen.add(v))]

    cumulative = bool(intent.get("force_cumulative_v510"))

    traces = []
    used = []
    missing = []

    for v in variables:
        data = _v510_get_profile_data(well, v, cumulative=cumulative)

        if not data:
            missing.append(v)
            continue

        var_label = data.get("variable") or v
        unit = _v510_unit_for_variable(var_label)
        axis = _v510_axis_for_variable(v)

        axis_ref = axis
        if axis == "y":
            axis_ref = "y"
        elif axis == "y2":
            axis_ref = "y2"
        elif axis == "y3":
            axis_ref = "y3"
        elif axis == "y4":
            axis_ref = "y4"

        sim = data.get("simulated") or []
        obs = data.get("observed") or []
        dates = data.get("dates") or []

        traces.append({
            "type": "scatter",
            "mode": "lines",
            "name": f"{v.upper()} simulated ({unit})",
            "x": dates,
            "y": sim,
            "yaxis": axis_ref,
            "line": {"width": 2},
            "hovertemplate": f"{v.upper()} simulated<br>Date: %{{x}}<br>Value: %{{y:.5g}} {unit}<extra></extra>"
        })

        if obs:
            traces.append({
                "type": "scatter",
                "mode": "lines",
                "name": f"{v.upper()} observed ({unit})",
                "x": dates,
                "y": obs,
                "yaxis": axis_ref,
                "line": {"width": 2, "dash": "dot"},
                "hovertemplate": f"{v.upper()} observed<br>Date: %{{x}}<br>Value: %{{y:.5g}} {unit}<extra></extra>"
            })

        used.append(v)

    if not traces:
        # Fallback to older behavior only if nothing could be built.
        return {
            "type": "reasoning_response",
            "intent": "multi_variable_profile",
            "answer": f"I could not build a combined profile plot for {well}. Missing variables: {', '.join(missing)}.",
            "ui_blocks": [],
            "agent_trace": {
                "MultiVariableProfileAgentV510": {
                    "status": "no_traces",
                    "well": well,
                    "requested_variables": variables,
                    "missing": missing,
                }
            }
        }

    title = f"{well} integrated profile: {', '.join(v.upper() for v in used)}"
    if cumulative:
        title = f"{well} cumulative integrated profile: {', '.join(v.upper() for v in used)}"

    return {
        "type": "visual_response",
        "intent": "multi_variable_profile",
        "answer": (
            f"I built one integrated interactive plot for {well} using {', '.join(used)}. "
            "GOR and WCT are computed from the available gas/oil/water profiles when explicit series are not available."
        ),
        "ui_blocks": [
            {
                "type": "plotly_chart",
                "title": title,
                "data": traces,
                "layout": _v510_layout_for_variables(title, used),
                "config": {
                    "responsive": True,
                    "displaylogo": False,
                    "scrollZoom": True
                }
            }
        ],
        "data": {
            "well": well,
            "variables_used": used,
            "missing_variables": missing,
            "computed_variables": [v for v in used if v in {"gor", "wct"}],
            "cumulative": cumulative,
        },
        "agent_trace": {
            "MultiVariableProfileAgentV510": {
                "route": "profile_series aggregation -> single plotly_chart",
                "well": well,
                "variables_used": used,
                "missing": missing,
                "computed_variables": [v for v in used if v in {"gor", "wct"}],
            }
        }
    }


def _execute_well_profile_v500(intent: Dict[str, Any]) -> Dict[str, Any]:
    well = intent.get("well") or ""
    variables = intent.get("variables") or []

    # Computed first-class GOR/WCT profile.
    if "gor" in variables:
        data = _v510_get_profile_data(well, "gor")
        if data:
            return {
                "type": "visual_response",
                "intent": "dynamic_interactive_profile",
                "answer": f"I built an interactive GOR profile for {well}. GOR is computed as gas rate divided by oil rate.",
                "ui_blocks": [
                    {
                        "type": "profile_series",
                        "title": data.get("title"),
                        "data": data
                    }
                ],
                "agent_trace": {
                    "ComputedGORProfileAgentV510": {
                        "well": well,
                        "formula": "GOR = gas rate / oil rate"
                    }
                }
            }

    if "wct" in variables:
        data = _v510_get_profile_data(well, "wct")
        if data:
            return {
                "type": "visual_response",
                "intent": "dynamic_interactive_profile",
                "answer": f"I built an interactive WCT profile for {well}. WCT is computed as water rate divided by oil plus water rate.",
                "ui_blocks": [
                    {
                        "type": "profile_series",
                        "title": data.get("title"),
                        "data": data
                    }
                ],
                "agent_trace": {
                    "ComputedWCTProfileAgentV510": {
                        "well": well,
                        "formula": "WCT = water / (oil + water)"
                    }
                }
            }

    return _call_existing_router_v500(_variable_to_profile_prompt_v500(well, variables))


def _v510_known_well_names():
    try:
        return _v506_known_well_names()
    except Exception:
        return [f"HW-{n}" for n in range(1, 81)]


def _v510_profile_is_active(data, variable, eps=1e-9):
    vals = [_safe_float_v500(v) for v in (data.get("simulated") or [])]
    vals = [v for v in vals if v is not None]

    if not vals:
        return False

    if variable in {"oil", "water", "gas"}:
        return len([v for v in vals if v > eps]) >= 3

    return True


def _v510_percentile(values, p):
    try:
        return _v506_percentile(values, p)
    except Exception:
        vals = sorted([float(x) for x in values if x is not None])
        if not vals:
            return None
        if len(vals) == 1:
            return vals[0]
        pos = (len(vals) - 1) * (p / 100.0)
        lo = int(pos)
        hi = min(lo + 1, len(vals) - 1)
        frac = pos - lo
        return vals[lo] * (1 - frac) + vals[hi] * frac


def _v510_execute_ensemble_profile_percentiles(intent):
    variables = intent.get("variables") or []
    variable = "oil"

    for v in ["gor", "wct", "oil", "water", "gas", "bhp"]:
        if v in variables:
            variable = v
            break

    profiles = []

    for well in _v510_known_well_names():
        try:
            data = _v510_get_profile_data(well, variable)

            if data and _v510_profile_is_active(data, variable):
                profiles.append(data)
        except Exception:
            pass

    if not profiles:
        return {
            "type": "reasoning_response",
            "intent": "ensemble_profile_percentiles",
            "answer": f"I could not find active {variable.upper()} profiles to compute P10/P50/P90.",
            "ui_blocks": [],
            "agent_trace": {
                "EnsembleProfilePercentileAgentV510": {
                    "status": "no_profiles",
                    "variable": variable,
                }
            }
        }

    date_values = {}

    for prof in profiles:
        for d, v in zip(prof.get("dates") or [], prof.get("simulated") or []):
            val = _safe_float_v500(v)
            if val is None:
                continue

            if variable in {"oil", "water", "gas"} and val <= 1e-9:
                continue

            date_values.setdefault(str(d), []).append(val)

    dates = sorted(date_values.keys())

    p10 = []
    p50 = []
    p90 = []

    for d in dates:
        vals = date_values[d]
        p10.append(_v510_percentile(vals, 10))
        p50.append(_v510_percentile(vals, 50))
        p90.append(_v510_percentile(vals, 90))

    traces = []

    for prof in profiles[:25]:
        y = prof.get("simulated") or []

        traces.append({
            "type": "scatter",
            "mode": "lines",
            "name": prof.get("well") or "well",
            "x": prof.get("dates") or [],
            "y": y,
            "line": {"width": 1},
            "opacity": 0.18,
            "showlegend": False,
            "hoverinfo": "skip"
        })

    unit = _v510_unit_for_variable(variable)

    traces.extend([
        {
            "type": "scatter",
            "mode": "lines",
            "name": "P10",
            "showlegend": True,
            "x": dates,
            "y": p10,
            "line": {"width": 3},
            "hovertemplate": f"P10<br>Date: %{{x}}<br>Value: %{{y:.5g}} {unit}<extra></extra>"
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "P50",
            "showlegend": True,
            "x": dates,
            "y": p50,
            "line": {"width": 4},
            "hovertemplate": f"P50<br>Date: %{{x}}<br>Value: %{{y:.5g}} {unit}<extra></extra>"
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "P90",
            "showlegend": True,
            "x": dates,
            "y": p90,
            "line": {"width": 3},
            "hovertemplate": f"P90<br>Date: %{{x}}<br>Value: %{{y:.5g}} {unit}<extra></extra>"
        }
    ])

    title = f"All active {variable.upper()} profiles with P10, P50 and P90"

    return {
        "type": "visual_response",
        "intent": "ensemble_profile_percentiles",
        "answer": (
            f"I generated the active-well ensemble {variable.upper()} profile and computed P10, P50 and P90 "
            f"from {len(profiles)} active profiles."
        ),
        "ui_blocks": [
            {
                "type": "plotly_chart",
                "title": title,
                "data": traces,
                "layout": {
                    "title": title,
                    "xaxis": {"title": "Date", "type": "date", "showgrid": False},
                    "yaxis": {"title": f"{variable.upper()} ({unit})", "showgrid": False, "zeroline": False},
                    "height": 560,
                    "hovermode": "closest",
                    "legend": {"orientation": "h", "y": -0.22},
                    "margin": {"l": 70, "r": 30, "t": 60, "b": 80},
                    "plot_bgcolor": "rgba(0,0,0,0)",
                    "paper_bgcolor": "rgba(0,0,0,0)"
                },
                "config": {"responsive": True, "displaylogo": False, "scrollZoom": True}
            }
        ],
        "data": {
            "variable": variable,
            "profiles_used": len(profiles),
            "wells_used": [p.get("well") for p in profiles],
            "computed": variable in {"gor", "wct"},
            "unit": unit,
            "percentiles": ["P10", "P50", "P90"]
        },
        "agent_trace": {
            "EnsembleProfilePercentileAgentV510": {
                "variable": variable,
                "profiles_used": len(profiles),
                "computed": variable in {"gor", "wct"},
            }
        }
    }


def _v510_distribution_from_property_map(intent: Dict[str, Any]) -> Dict[str, Any]:
    prop = intent.get("primary_property") or "PRESSURE"

    try:
        map_response = _execute_property_map_v500({**intent, "primary_property": prop})
        block = None

        for b in map_response.get("ui_blocks") or []:
            if isinstance(b, dict) and b.get("type") == "generic_property_map":
                block = b
                break

        if not block:
            return {}

        parent, key, cells = _extract_cells_from_block_v502(block)

        vals = []
        for c in cells:
            v = _cell_value_v502(c)
            if v is not None:
                vals.append(v)

        if not vals:
            return {}

        title = f"{prop} distribution"

        return {
            "type": "visual_response",
            "intent": "property_distribution",
            "answer": f"Created interactive distribution plot for {prop} from {len(vals)} map-cell values.",
            "ui_blocks": [
                {
                    "type": "plotly_chart",
                    "title": title,
                    "data": [
                        {
                            "type": "histogram",
                            "x": vals,
                            "nbinsx": 60,
                            "name": prop,
                            "hovertemplate": f"{prop}<br>Value: %{{x:.5g}}<br>Count: %{{y}}<extra></extra>"
                        }
                    ],
                    "layout": {
                        "title": title,
                        "xaxis": {"title": prop, "showgrid": False},
                        "yaxis": {"title": "Count", "showgrid": False},
                        "height": 560,
                        "margin": {"l": 70, "r": 30, "t": 60, "b": 70},
                        "plot_bgcolor": "rgba(0,0,0,0)",
                        "paper_bgcolor": "rgba(0,0,0,0)"
                    },
                    "config": {"responsive": True, "displaylogo": False}
                }
            ],
            "data": {
                "property": prop,
                "values_count": len(vals),
                "source": "property_map_cell_payload_v510"
            },
            "agent_trace": {
                "PropertyDistributionFallbackV510": {
                    "property": prop,
                    "values_count": len(vals),
                    "route": "property map payload -> histogram"
                }
            }
        }

    except Exception:
        return {}


def _execute_property_distribution_v500(intent: Dict[str, Any]) -> Dict[str, Any]:
    prop = intent.get("primary_property") or "PORO"

    if prop == "PRESSURE":
        out = _v510_distribution_from_property_map(intent)
        if out:
            return out

    out = _execute_property_distribution_before_v510(intent)

    if isinstance(out, dict) and (out.get("ui_blocks") or []):
        return out

    # Generic fallback: try map-cell histogram for any property if the distribution agent fails.
    fallback = _v510_distribution_from_property_map(intent)
    if fallback:
        return fallback

    return out


def execute_plan_v500(intent: Dict[str, Any], plan: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    task = intent.get("task_type")

    if task == "multi_variable_profile":
        return _execute_multi_variable_profile_v500(intent)

    if task == "ensemble_profile_percentiles":
        vars_ = intent.get("variables") or []
        if "gor" in vars_ or "wct" in vars_:
            return _v510_execute_ensemble_profile_percentiles(intent)

    if task == "well_profile":
        vars_ = intent.get("variables") or []
        if "gor" in vars_ or "wct" in vars_:
            return _execute_well_profile_v500(intent)

    if task == "property_distribution":
        return _execute_property_distribution_v500(intent)

    return _execute_plan_before_v510(intent, plan, evidence_board)

# END V510 MULTI-VARIABLE PLOT + GOR/WCT COMPUTED PROFILES


# ==========================================================
# V511 GRID DATA ALGEBRA AGENT
#
# Fixes:
# - Show porosity only where I is between 1 and 10
# - Show pressure where PERMX > 50
# - Show PERMX where porosity is lower than 0.12
# - Calculate average porosity where SWAT > 0.4
# - Calculate average PERMX where pressure is below 250
# - Multiply PERMX by 1.2 where SWAT > 0.4
#
# Key principle:
# target_property != filter_property
# ==========================================================

_interpret_request_before_v511 = interpret_request_v500
_execute_plan_before_v511 = execute_plan_v500


def _v511_msg(message):
    return _norm_v500(message)


def _v511_alias_to_property(text):
    s = _norm_v500(text)

    # Order matters: permx before generic perm.
    if any(x in s for x in ["perm y", "permy", "ky"]):
        return "PERM_Y"

    if any(x in s for x in ["perm z", "permz", "kz"]):
        return "PERM_Z"

    if any(x in s for x in ["permx", "perm x", "perm_h", "perm h", "kx", "permeability", "permeabilita", "permeabilità", "perm"]):
        return "PERM_X"

    if any(x in s for x in ["poro", "porosity", "porosita", "porosità"]):
        return "PORO"

    if any(x in s for x in ["swat", "water saturation", "saturazione acqua"]):
        return "SWAT"

    if any(x in s for x in ["pressure", "pressione"]):
        return "PRESSURE"

    if any(x in s for x in ["tran", "transmissibility", "trasmissibilita", "trasmissibilità"]):
        return "TRAN"

    if "ntg" in s:
        return "NTG"

    return None


def _v511_detect_target_property(message):
    msg = _v511_msg(message)

    # Text before where usually contains target property.
    left = msg
    for sep in [" only where ", " where ", " for cells where ", " if "]:
        if sep in left:
            left = left.split(sep, 1)[0]
            break

    # Strip leading verbs.
    prefixes = [
        "show me ", "show ", "plot ", "display ", "visualize ", "visualise ",
        "calculate average ", "calculate mean ", "average ", "mean ",
        "multiply ", "moltiplica ", "map "
    ]

    for pfx in prefixes:
        if left.startswith(pfx):
            left = left[len(pfx):]
            break

    prop = _v511_alias_to_property(left)

    if prop:
        return prop

    # Fallback: first property in full sentence.
    return _v511_alias_to_property(msg)


def _v511_detect_operation(message):
    msg = _v511_msg(message)

    if any(x in msg for x in ["calculate average", "average ", "mean ", "media "]):
        return {"operation": "average"}

    if any(x in msg for x in ["sum ", "summation", "somma "]):
        return {"operation": "sum"}

    import re
    m = re.search(r"(multiply|moltiplica)\s+.*?\s+(?:by|per)\s+([-+]?\d+(?:\.\d+)?)", msg)

    if m:
        return {
            "operation": "multiply",
            "factor": float(m.group(2)),
        }

    return {"operation": "map"}


def _v511_parse_index_filters(message):
    import re

    msg = _v511_msg(message)
    filters = []

    for idx in ["i", "j", "k"]:
        # where I is between 1 and 10
        patterns = [
            rf"\b{idx}\s+(?:is\s+)?(?:between|from|compreso tra|da)\s+(\d+)\s+(?:and|to|e|a)\s+(\d+)",
            rf"\b{idx}\s*(?:>=|greater than or equal to|above)\s*(\d+)",
            rf"\b{idx}\s*(?:<=|less than or equal to|below)\s*(\d+)",
        ]

        m = re.search(patterns[0], msg)
        if m:
            filters.append({
                "kind": "index_range",
                "index": idx.upper(),
                "min": int(m.group(1)),
                "max": int(m.group(2)),
            })
            continue

        m = re.search(patterns[1], msg)
        if m:
            filters.append({
                "kind": "index_range",
                "index": idx.upper(),
                "min": int(m.group(1)),
                "max": 10**9,
            })
            continue

        m = re.search(patterns[2], msg)
        if m:
            filters.append({
                "kind": "index_range",
                "index": idx.upper(),
                "min": -10**9,
                "max": int(m.group(1)),
            })
            continue

    return filters


def _v511_parse_property_filters(message, target_property=None):
    import re

    msg = _v511_msg(message)

    aliases = [
        ("perm x", "PERM_X"),
        ("permx", "PERM_X"),
        ("perm_h", "PERM_X"),
        ("perm h", "PERM_X"),
        ("permeability", "PERM_X"),
        ("permeabilita", "PERM_X"),
        ("permeabilità", "PERM_X"),
        ("perm", "PERM_X"),
        ("poro", "PORO"),
        ("porosity", "PORO"),
        ("porosita", "PORO"),
        ("porosità", "PORO"),
        ("swat", "SWAT"),
        ("water saturation", "SWAT"),
        ("pressure", "PRESSURE"),
        ("pressione", "PRESSURE"),
        ("tran", "TRAN"),
        ("transmissibility", "TRAN"),
    ]

    op_words = {
        ">": ">",
        ">=": ">=",
        "<": "<",
        "<=": "<=",
        "=": "=",
        "equal to": "=",
        "greater than": ">",
        "above": ">",
        "more than": ">",
        "higher than": ">",
        "lower than": "<",
        "less than": "<",
        "below": "<",
        "under": "<",
        "maggiore di": ">",
        "superiore a": ">",
        "minore di": "<",
        "inferiore a": "<",
    }

    filters = []

    for raw, prop in aliases:
        # Avoid interpreting the target mention before "where" as filter unless it appears after where,
        # or unless there is an explicit comparator right after it.
        escaped = re.escape(raw)

        pattern = (
            rf"\b{escaped}\b\s*"
            rf"(>=|<=|>|<|=|equal to|greater than|above|more than|higher than|lower than|less than|below|under|maggiore di|superiore a|minore di|inferiore a)\s*"
            rf"([-+]?\d+(?:\.\d+)?)"
        )

        for m in re.finditer(pattern, msg):
            op = op_words.get(m.group(1), m.group(1))
            val = float(m.group(2))

            filters.append({
                "kind": "property_threshold",
                "variable": prop,
                "operator": op,
                "value": val,
            })

    return filters


def _v511_parse_grid_request(message):
    msg = _v511_msg(message)

    target = _v511_detect_target_property(message)
    op = _v511_detect_operation(message)

    index_filters = _v511_parse_index_filters(message)
    prop_filters = _v511_parse_property_filters(message, target)

    filters = index_filters + prop_filters

    # Only grid algebra if there is a property target and either filters or operation.
    is_grid_request = bool(target) and (
        bool(filters)
        or op.get("operation") in {"average", "sum", "multiply"}
        or "where" in msg
        or "only where" in msg
    )

    if not is_grid_request:
        return None

    return {
        "target_property": target,
        "operation": op.get("operation", "map"),
        "factor": op.get("factor"),
        "filters": filters,
    }


def interpret_request_v500(message: str) -> Dict[str, Any]:
    intent = _interpret_request_before_v511(message)
    grid = _v511_parse_grid_request(message)

    if grid:
        intent["grid_algebra_v511"] = grid
        intent["primary_property"] = grid["target_property"]
        intent["filters"] = grid["filters"]

        if grid["operation"] in {"average", "sum", "multiply"}:
            intent["task_type"] = "grid_data_operation"
        else:
            intent["task_type"] = "conditional_property_map"

        intent.setdefault("flags", {})
        intent["flags"]["grid_algebra"] = True

    return intent


def _v511_copy_cell(cell):
    try:
        return dict(cell)
    except Exception:
        return cell


def _v511_set_cell_value(cell, new_value):
    if not isinstance(cell, dict):
        return cell

    out = dict(cell)

    for key in ["value", "val", "z", "Z", "property_value", "mean", "avg"]:
        if key in out:
            out[key] = new_value
            return out

    out["value"] = new_value
    return out


def _v511_get_map_block_and_cells(prop, intent):
    response = _execute_property_map_v500({
        **intent,
        "primary_property": prop,
    })

    block = None

    for b in response.get("ui_blocks") or []:
        if isinstance(b, dict) and b.get("type") == "generic_property_map":
            block = b
            break

    if not block:
        return response, None, None, []

    parent, key, cells = _extract_cells_from_block_v502(block)

    return response, parent, key, cells


def _v511_build_property_lookup(prop, intent):
    _, _, _, cells = _v511_get_map_block_and_cells(prop, intent)

    lookup = {}

    for c in cells:
        ck = _cell_key_v502(c)
        if ck is not None:
            lookup[ck] = _cell_value_v502(c)

    return lookup


def _v511_passes_filters(cell, target_prop, filters, lookups):
    if not _passes_index_filters_v502(cell, [f for f in filters if f.get("kind") == "index_range"]):
        return False

    ck = _cell_key_v502(cell)

    for f in filters:
        if f.get("kind") != "property_threshold":
            continue

        prop = f.get("variable")
        op = f.get("operator")
        threshold = f.get("value")

        if prop == target_prop:
            val = _cell_value_v502(cell)
        else:
            val = lookups.get(prop, {}).get(ck)

        if not _passes_threshold_v502(val, op, threshold):
            return False

    return True


def _v511_condition_text(filters):
    parts = []

    for f in filters:
        if f.get("kind") == "index_range":
            parts.append(f"{f.get('index')} between {f.get('min')} and {f.get('max')}")
        elif f.get("kind") == "property_threshold":
            parts.append(f"{f.get('variable')} {f.get('operator')} {f.get('value')}")

    return ", ".join(parts) if parts else "no filter"


def _v511_execute_grid_algebra(intent: Dict[str, Any]) -> Dict[str, Any]:
    grid = intent.get("grid_algebra_v511") or {}

    target = grid.get("target_property") or intent.get("primary_property") or "PORO"
    operation = grid.get("operation") or "map"
    filters = grid.get("filters") or []
    factor = grid.get("factor")

    response, parent, key, target_cells = _v511_get_map_block_and_cells(target, intent)

    if not target_cells:
        return {
            "type": "reasoning_response",
            "intent": "grid_data_operation",
            "answer": (
                f"I understood the grid algebra request for {target}, but the current property map response "
                "does not expose cell-level values needed to apply the operation."
            ),
            "ui_blocks": [],
            "agent_trace": {
                "GridDataAlgebraAgentV511": {
                    "status": "no_cell_payload",
                    "target_property": target,
                    "operation": operation,
                    "filters": filters,
                }
            }
        }

    filter_props = sorted(set(
        f.get("variable") for f in filters
        if f.get("kind") == "property_threshold" and f.get("variable") != target
    ))

    lookups = {}

    for prop in filter_props:
        lookups[prop] = _v511_build_property_lookup(prop, intent)

    selected = []

    for c in target_cells:
        if _v511_passes_filters(c, target, filters, lookups):
            selected.append(c)

    selected_values = [_cell_value_v502(c) for c in selected]
    selected_values = [v for v in selected_values if v is not None]

    condition_text = _v511_condition_text(filters)

    # Average / sum scalar operations.
    if operation in {"average", "sum"}:
        if operation == "average":
            result = sum(selected_values) / len(selected_values) if selected_values else None
            label = "Average"
        else:
            result = sum(selected_values) if selected_values else None
            label = "Sum"

        rows = [
            {
                "Target property": target,
                "Operation": operation,
                "Filter": condition_text,
                "Selected cells": len(selected),
                "Values used": len(selected_values),
                "Result": result,
            }
        ]

        return {
            "type": "calculation_response",
            "intent": "grid_data_operation",
            "answer": (
                f"{label} {target} where {condition_text}: {result}. "
                f"Selected {len(selected)} cells and used {len(selected_values)} numeric values."
            ),
            "ui_blocks": [
                {
                    "type": "compact_table",
                    "title": f"{label} {target} under grid condition",
                    "columns": ["Target property", "Operation", "Filter", "Selected cells", "Values used", "Result"],
                    "rows": rows,
                }
            ],
            "calculation_summary": {
                "target_property": target,
                "operation": operation,
                "filters": filters,
                "selected_cells": len(selected),
                "values_used": len(selected_values),
                "result": result,
            },
            "agent_trace": {
                "GridDataAlgebraAgentV511": {
                    "route": "cell payload -> scalar grid calculation",
                    "target_property": target,
                    "operation": operation,
                    "selected_cells": len(selected),
                    "values_used": len(selected_values),
                }
            }
        }

    # Multiply transform.
    if operation == "multiply":
        factor = float(factor if factor is not None else 1.0)

        transformed = []

        for c in selected:
            val = _cell_value_v502(c)
            if val is None:
                continue
            transformed.append(_v511_set_cell_value(c, val * factor))

        if parent is not None and key is not None:
            parent[key] = transformed

        # Update titles.
        for b in response.get("ui_blocks") or []:
            if isinstance(b, dict) and b.get("type") == "generic_property_map":
                b["title"] = f"{target} multiplied by {factor} where {condition_text}"
                if isinstance(b.get("payload"), dict):
                    b["payload"]["title"] = b["title"]
                    b["payload"]["operation"] = "grid_multiply_v511"
                    b["payload"]["target_property"] = target
                    b["payload"]["filters"] = filters
                    b["payload"]["factor"] = factor

        response["intent"] = "grid_data_operation"
        response["answer"] = (
            f"I applied a conditional grid transform: {target} multiplied by {factor} where {condition_text}. "
            f"The visual shows the {len(transformed)} transformed selected cells."
        )

        response.setdefault("calculation_summary", {})
        response["calculation_summary"]["grid_algebra_v511"] = {
            "target_property": target,
            "operation": "multiply",
            "factor": factor,
            "filters": filters,
            "selected_cells": len(selected),
            "transformed_cells": len(transformed),
        }

        response.setdefault("agent_trace", {})
        response["agent_trace"]["GridDataAlgebraAgentV511"] = {
            "route": "cell payload -> conditional multiply map",
            "target_property": target,
            "factor": factor,
            "selected_cells": len(selected),
            "transformed_cells": len(transformed),
        }

        return response

    # Default: conditional map target property filtered by another property/index.
    filtered_cells = [_v511_copy_cell(c) for c in selected]

    if parent is not None and key is not None:
        parent[key] = filtered_cells

    for b in response.get("ui_blocks") or []:
        if isinstance(b, dict) and b.get("type") == "generic_property_map":
            b["title"] = f"{target} where {condition_text}"
            if isinstance(b.get("payload"), dict):
                b["payload"]["title"] = b["title"]
                b["payload"]["operation"] = "conditional_map_v511"
                b["payload"]["target_property"] = target
                b["payload"]["filters"] = filters

    response["intent"] = "conditional_property_map"
    response["answer"] = (
        f"I generated a conditional {target} map where {condition_text}. "
        f"Selected {len(filtered_cells)} cells out of {len(target_cells)} available {target} cells."
    )

    response.setdefault("calculation_summary", {})
    response["calculation_summary"]["grid_algebra_v511"] = {
        "target_property": target,
        "operation": "map",
        "filters": filters,
        "input_cells": len(target_cells),
        "selected_cells": len(filtered_cells),
        "filter_property_lookups": {k: len(v) for k, v in lookups.items()},
    }

    response.setdefault("agent_trace", {})
    response["agent_trace"]["GridDataAlgebraAgentV511"] = {
        "route": "cell payload -> target map filtered by condition",
        "target_property": target,
        "filters": filters,
        "input_cells": len(target_cells),
        "selected_cells": len(filtered_cells),
        "filter_property_lookups": {k: len(v) for k, v in lookups.items()},
    }

    return response


def execute_plan_v500(intent: Dict[str, Any], plan: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    if intent.get("grid_algebra_v511"):
        return _v511_execute_grid_algebra(intent)

    return _execute_plan_before_v511(intent, plan, evidence_board)

# END V511 GRID DATA ALGEBRA AGENT


# ==========================================================
# V511B GRID ALGEBRA PARSER + ROBUST CELL LOOKUP
#
# Fixes:
# - "porosity is lower than 0.12"
# - "pressure is below 250"
# - robust lookup between properties using both I/J/K and I/J keys
# - min/max diagnostics when selected cells are zero
# ==========================================================

_interpret_request_before_v511b = interpret_request_v500
_execute_plan_before_v511b = execute_plan_v500


def _v511b_parse_property_filters(message, target_property=None):
    import re

    msg = _v511_msg(message)

    aliases = [
        ("perm x", "PERM_X"),
        ("permx", "PERM_X"),
        ("permeability", "PERM_X"),
        ("permeabilita", "PERM_X"),
        ("permeabilità", "PERM_X"),
        ("perm", "PERM_X"),
        ("poro", "PORO"),
        ("porosity", "PORO"),
        ("porosita", "PORO"),
        ("porosità", "PORO"),
        ("swat", "SWAT"),
        ("water saturation", "SWAT"),
        ("pressure", "PRESSURE"),
        ("pressione", "PRESSURE"),
        ("tran", "TRAN"),
        ("transmissibility", "TRAN"),
    ]

    op_words = {
        ">": ">",
        ">=": ">=",
        "<": "<",
        "<=": "<=",
        "=": "=",
        "equal to": "=",
        "greater than": ">",
        "above": ">",
        "more than": ">",
        "higher than": ">",
        "lower than": "<",
        "less than": "<",
        "below": "<",
        "under": "<",
        "maggiore di": ">",
        "superiore a": ">",
        "minore di": "<",
        "inferiore a": "<",
    }

    filters = []

    for raw, prop in aliases:
        escaped = re.escape(raw)

        # Allows:
        # porosity lower than 0.12
        # porosity is lower than 0.12
        # pressure below 250
        # pressure is below 250
        # PERMX > 50
        pattern = (
            rf"\b{escaped}\b\s*"
            rf"(?:is\s+|è\s+|e\s+)?"
            rf"(>=|<=|>|<|=|equal to|greater than|above|more than|higher than|lower than|less than|below|under|maggiore di|superiore a|minore di|inferiore a)\s*"
            rf"([-+]?\d+(?:\.\d+)?)"
        )

        for m in re.finditer(pattern, msg):
            op = op_words.get(m.group(1), m.group(1))
            val = float(m.group(2))

            filters.append({
                "kind": "property_threshold",
                "variable": prop,
                "operator": op,
                "value": val,
            })

    return filters


def _v511b_parse_grid_request(message):
    target = _v511_detect_target_property(message)
    op = _v511_detect_operation(message)

    index_filters = _v511_parse_index_filters(message)
    prop_filters = _v511b_parse_property_filters(message, target)

    filters = index_filters + prop_filters

    msg = _v511_msg(message)

    is_grid_request = bool(target) and (
        bool(filters)
        or op.get("operation") in {"average", "sum", "multiply"}
        or "where" in msg
        or "only where" in msg
    )

    if not is_grid_request:
        return None

    return {
        "target_property": target,
        "operation": op.get("operation", "map"),
        "factor": op.get("factor"),
        "filters": filters,
    }


def interpret_request_v500(message: str) -> Dict[str, Any]:
    intent = _interpret_request_before_v511b(message)

    grid = _v511b_parse_grid_request(message)

    if grid:
        intent["grid_algebra_v511"] = grid
        intent["grid_algebra_v511b"] = grid
        intent["primary_property"] = grid["target_property"]
        intent["filters"] = grid["filters"]

        if grid["operation"] in {"average", "sum", "multiply"}:
            intent["task_type"] = "grid_data_operation"
        else:
            intent["task_type"] = "conditional_property_map"

        intent.setdefault("flags", {})
        intent["flags"]["grid_algebra"] = True

    return intent


def _v511b_cell_keys(cell):
    if not isinstance(cell, dict):
        return []

    keys = []

    try:
        i = cell.get("i", cell.get("I", cell.get("x", cell.get("X"))))
        j = cell.get("j", cell.get("J", cell.get("y", cell.get("Y"))))
        k = cell.get("k", cell.get("K", cell.get("z_index", cell.get("K_INDEX"))))

        if i is not None and j is not None and k is not None:
            keys.append(("IJK", int(float(i)), int(float(j)), int(float(k))))

        if i is not None and j is not None:
            keys.append(("IJ", int(float(i)), int(float(j))))
    except Exception:
        pass

    return keys


def _v511b_build_property_lookup(prop, intent):
    _, _, _, cells = _v511_get_map_block_and_cells(prop, intent)

    lookup = {}
    values = []

    for c in cells:
        val = _cell_value_v502(c)
        if val is not None:
            values.append(val)

        for key in _v511b_cell_keys(c):
            lookup[key] = val

    stats = {
        "cells": len(cells),
        "values": len(values),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "mean": sum(values) / len(values) if values else None,
    }

    return lookup, stats


def _v511b_filter_value_for_cell(cell, prop, target_prop, lookups):
    if prop == target_prop:
        return _cell_value_v502(cell)

    keys = _v511b_cell_keys(cell)

    lk = lookups.get(prop, {})

    for key in keys:
        if key in lk:
            return lk[key]

    return None


def _v511b_passes_filters(cell, target_prop, filters, lookups):
    if not _passes_index_filters_v502(cell, [f for f in filters if f.get("kind") == "index_range"]):
        return False

    for f in filters:
        if f.get("kind") != "property_threshold":
            continue

        prop = f.get("variable")
        op = f.get("operator")
        threshold = f.get("value")

        val = _v511b_filter_value_for_cell(cell, prop, target_prop, lookups)

        if not _passes_threshold_v502(val, op, threshold):
            return False

    return True


def _v511b_execute_grid_algebra(intent: Dict[str, Any]) -> Dict[str, Any]:
    grid = intent.get("grid_algebra_v511b") or intent.get("grid_algebra_v511") or {}

    target = grid.get("target_property") or intent.get("primary_property") or "PORO"
    operation = grid.get("operation") or "map"
    filters = grid.get("filters") or []
    factor = grid.get("factor")

    response, parent, key, target_cells = _v511_get_map_block_and_cells(target, intent)

    if not target_cells:
        return _v511_execute_grid_algebra(intent)

    filter_props = sorted(set(
        f.get("variable") for f in filters
        if f.get("kind") == "property_threshold" and f.get("variable") != target
    ))

    lookups = {}
    filter_stats = {}

    for prop in filter_props:
        lk, stats = _v511b_build_property_lookup(prop, intent)
        lookups[prop] = lk
        filter_stats[prop] = stats

    selected = []

    for c in target_cells:
        if _v511b_passes_filters(c, target, filters, lookups):
            selected.append(c)

    selected_values = [_cell_value_v502(c) for c in selected]
    selected_values = [v for v in selected_values if v is not None]

    target_values = [_cell_value_v502(c) for c in target_cells]
    target_values = [v for v in target_values if v is not None]

    condition_text = _v511_condition_text(filters)

    diagnostics = {
        "target_property": target,
        "target_cells": len(target_cells),
        "target_values": len(target_values),
        "target_min": min(target_values) if target_values else None,
        "target_max": max(target_values) if target_values else None,
        "filter_stats": filter_stats,
    }

    if operation in {"average", "sum"}:
        if operation == "average":
            result = sum(selected_values) / len(selected_values) if selected_values else None
            label = "Average"
        else:
            result = sum(selected_values) if selected_values else None
            label = "Sum"

        rows = [
            {
                "Target property": target,
                "Operation": operation,
                "Filter": condition_text,
                "Selected cells": len(selected),
                "Values used": len(selected_values),
                "Result": result,
            }
        ]

        return {
            "type": "calculation_response",
            "intent": "grid_data_operation",
            "answer": (
                f"{label} {target} where {condition_text}: {result}. "
                f"Selected {len(selected)} cells and used {len(selected_values)} numeric values."
            ),
            "ui_blocks": [
                {
                    "type": "compact_table",
                    "title": f"{label} {target} under grid condition",
                    "columns": ["Target property", "Operation", "Filter", "Selected cells", "Values used", "Result"],
                    "rows": rows,
                }
            ],
            "calculation_summary": {
                "target_property": target,
                "operation": operation,
                "filters": filters,
                "selected_cells": len(selected),
                "values_used": len(selected_values),
                "result": result,
                "diagnostics_v511b": diagnostics,
            },
            "agent_trace": {
                "GridDataAlgebraAgentV511B": {
                    "route": "robust lookup -> scalar grid calculation",
                    "target_property": target,
                    "operation": operation,
                    "selected_cells": len(selected),
                    "values_used": len(selected_values),
                    "diagnostics": diagnostics,
                }
            }
        }

    if operation == "multiply":
        factor = float(factor if factor is not None else 1.0)

        transformed = []

        for c in selected:
            val = _cell_value_v502(c)
            if val is None:
                continue
            transformed.append(_v511_set_cell_value(c, val * factor))

        if parent is not None and key is not None:
            parent[key] = transformed

        for b in response.get("ui_blocks") or []:
            if isinstance(b, dict) and b.get("type") == "generic_property_map":
                b["title"] = f"{target} multiplied by {factor} where {condition_text}"
                if isinstance(b.get("payload"), dict):
                    b["payload"]["title"] = b["title"]
                    b["payload"]["operation"] = "grid_multiply_v511b"
                    b["payload"]["target_property"] = target
                    b["payload"]["filters"] = filters
                    b["payload"]["factor"] = factor

        response["intent"] = "grid_data_operation"
        response["answer"] = (
            f"I applied a conditional grid transform: {target} multiplied by {factor} where {condition_text}. "
            f"The visual shows the {len(transformed)} transformed selected cells."
        )

        response.setdefault("calculation_summary", {})
        response["calculation_summary"]["grid_algebra_v511b"] = {
            "target_property": target,
            "operation": "multiply",
            "factor": factor,
            "filters": filters,
            "selected_cells": len(selected),
            "transformed_cells": len(transformed),
            "diagnostics_v511b": diagnostics,
        }

        response.setdefault("agent_trace", {})
        response["agent_trace"]["GridDataAlgebraAgentV511B"] = {
            "route": "robust lookup -> conditional multiply map",
            "target_property": target,
            "factor": factor,
            "selected_cells": len(selected),
            "transformed_cells": len(transformed),
            "diagnostics": diagnostics,
        }

        return response

    filtered_cells = [_v511_copy_cell(c) for c in selected]

    if parent is not None and key is not None:
        parent[key] = filtered_cells

    for b in response.get("ui_blocks") or []:
        if isinstance(b, dict) and b.get("type") == "generic_property_map":
            b["title"] = f"{target} where {condition_text}"
            if isinstance(b.get("payload"), dict):
                b["payload"]["title"] = b["title"]
                b["payload"]["operation"] = "conditional_map_v511b"
                b["payload"]["target_property"] = target
                b["payload"]["filters"] = filters

    response["intent"] = "conditional_property_map"
    response["answer"] = (
        f"I generated a conditional {target} map where {condition_text}. "
        f"Selected {len(filtered_cells)} cells out of {len(target_cells)} available {target} cells."
    )

    if len(filtered_cells) == 0 and filter_stats:
        response["answer"] += (
            " No cells passed the filter. I added min/max diagnostics for the filter property so you can check whether the threshold is outside the available range."
        )

    response.setdefault("calculation_summary", {})
    response["calculation_summary"]["grid_algebra_v511b"] = {
        "target_property": target,
        "operation": "map",
        "filters": filters,
        "input_cells": len(target_cells),
        "selected_cells": len(filtered_cells),
        "filter_property_lookups": {k: len(v) for k, v in lookups.items()},
        "diagnostics_v511b": diagnostics,
    }

    response.setdefault("agent_trace", {})
    response["agent_trace"]["GridDataAlgebraAgentV511B"] = {
        "route": "robust lookup -> target map filtered by condition",
        "target_property": target,
        "filters": filters,
        "input_cells": len(target_cells),
        "selected_cells": len(filtered_cells),
        "filter_property_lookups": {k: len(v) for k, v in lookups.items()},
        "diagnostics": diagnostics,
    }

    return response


def execute_plan_v500(intent: Dict[str, Any], plan: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    if intent.get("grid_algebra_v511b") or intent.get("grid_algebra_v511"):
        return _v511b_execute_grid_algebra(intent)

    return _execute_plan_before_v511b(intent, plan, evidence_board)

# END V511B GRID ALGEBRA PARSER + ROBUST CELL LOOKUP


# ==========================================================
# V511C ZERO-SELECTION EXPLANATION POLISH
#
# Keeps V511B math unchanged.
# Improves user-facing answer/table when selected_cells = 0
# so the dashboard does not show ugly "Result: None" without context.
# ==========================================================

_execute_plan_before_v511c = execute_plan_v500


def _v511c_suggest_threshold(filters, diagnostics):
    if not filters:
        return ""

    filter_stats = (diagnostics or {}).get("filter_stats") or {}

    suggestions = []

    for f in filters:
        if f.get("kind") != "property_threshold":
            continue

        prop = f.get("variable")
        op = f.get("operator")
        val = f.get("value")
        stats = filter_stats.get(prop) or {}

        mn = stats.get("min")
        mx = stats.get("max")
        mean = stats.get("mean")

        if mn is None or mx is None:
            continue

        if op == ">" and val is not None and val > mx:
            suggestions.append(
                f"For {prop}, the requested threshold > {val} is above the available maximum ({mx:.5g}). Try a lower threshold."
            )

        elif op == "<" and val is not None and val < mn:
            suggestions.append(
                f"For {prop}, the requested threshold < {val} is below the available minimum ({mn:.5g}). Try a higher threshold."
            )

        elif mean is not None:
            suggestions.append(
                f"For {prop}, available values range from {mn:.5g} to {mx:.5g} with mean {mean:.5g}. If zero cells are selected, the threshold may not overlap the target-property active cells."
            )

    return " ".join(suggestions)


def _v511c_polish_zero_selection(response):
    if not isinstance(response, dict):
        return response

    summary = response.get("calculation_summary") or {}

    # map/multiply summary may be nested
    grid = (
        summary.get("grid_algebra_v511b")
        or summary.get("grid_algebra_v511")
        or summary
    )

    selected = grid.get("selected_cells")
    values_used = grid.get("values_used")
    result = grid.get("result")
    filters = grid.get("filters") or []
    diagnostics = grid.get("diagnostics_v511b") or {}

    if selected != 0:
        return response

    target = grid.get("target_property") or summary.get("target_property") or "target property"
    operation = grid.get("operation") or summary.get("operation") or "operation"

    condition = _v511_condition_text(filters)
    suggestion = _v511c_suggest_threshold(filters, diagnostics)

    if operation in {"average", "sum"}:
        response["answer"] = (
            f"No overlapping active {target} cells matched the condition: {condition}. "
            f"The {operation} result is therefore not available, rather than numerically zero. "
            f"{suggestion}"
        ).strip()

        # Update compact table rows if present.
        for block in response.get("ui_blocks") or []:
            if isinstance(block, dict) and block.get("type") == "compact_table":
                rows = block.get("rows") or []
                for row in rows:
                    if isinstance(row, dict):
                        row["Result"] = "N/A - no matching cells"
                        row["Selected cells"] = 0
                        row["Values used"] = 0

    else:
        response["answer"] = (
            f"No cells matched the conditional map request for {target}: {condition}. "
            f"{suggestion}"
        ).strip()

    response.setdefault("agent_trace", {})
    response["agent_trace"]["ZeroSelectionExplainerV511C"] = {
        "target_property": target,
        "operation": operation,
        "filters": filters,
        "diagnostics": diagnostics,
        "reason": "Selected cells were zero; replaced raw None/empty-map wording with diagnostic explanation.",
    }

    return response


def execute_plan_v500(intent: Dict[str, Any], plan: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    response = _execute_plan_before_v511c(intent, plan, evidence_board)

    if intent.get("grid_algebra_v511b") or intent.get("grid_algebra_v511"):
        response = _v511c_polish_zero_selection(response)

    return response

# END V511C ZERO-SELECTION EXPLANATION POLISH


# ==========================================================
# V512B TIMESERIES CLUSTERING PRIORITY GUARD
#
# Fix:
# V512 algorithm exists, but cluster requests were still stolen by:
# - AbsoluteWCTBiasRouterV37
# - FinalDiagnosticPriorityGuardV415
# - generic diagnostic_cluster route
#
# Rule:
# "clusters based on oil/gas/water/GOR/BHP/rate/production/trend/profile"
# must route to TimeSeriesClusteringAgentV512.
#
# Explicit mismatch/bias cluster requests remain diagnostic and will be
# handled later by V513 Gas/BHP/MismatchDiagnosticAgent.
# ==========================================================

_interpret_request_before_v512b = interpret_request_v500
_execute_plan_before_v512b = execute_plan_v500


def _v512b_msg(message):
    return _norm_v500(message)


def _v512b_contains_any(msg, terms):
    return any(t in msg for t in terms)


def _v512b_is_explicit_mismatch_cluster(msg):
    return _v512b_contains_any(msg, [
        "wct bias cluster",
        "bias cluster",
        "mismatch cluster",
        "mismatch clusters",
        "gas mismatch cluster",
        "gas mismatch clusters",
        "gor mismatch cluster",
        "gor mismatch clusters",
        "bhp mismatch cluster",
        "bhp mismatch clusters",
        "pressure mismatch cluster",
        "pressure mismatch clusters",
    ])


def _v512b_is_time_series_cluster_request(message):
    msg = _v512b_msg(message)

    has_cluster = _v512b_contains_any(msg, [
        "cluster", "clusters", "clustering",
        "group wells", "grouping wells",
        "similar wells"
    ])

    if not has_cluster:
        return False

    if _v512b_is_explicit_mismatch_cluster(msg):
        return False

    profile_terms = [
        "oil", "water", "gas", "gor", "wct", "bhp",
        "rate", "rates",
        "production", "producer",
        "behavior", "behaviour",
        "trend", "trends",
        "profile", "profiles",
        "time series", "timeseries",
        "pressure depletion",
        "gas response",
        "water breakthrough",
    ]

    # Key natural language patterns.
    based_on_patterns = [
        "clusters based on",
        "cluster wells based on",
        "cluster based on",
        "group wells based on",
        "similar",
    ]

    return (
        _v512b_contains_any(msg, profile_terms)
        and _v512b_contains_any(msg, based_on_patterns + ["cluster", "clusters"])
    )


def _v512b_detect_cluster_variables(message, existing_variables=None):
    try:
        variables = _v512_detect_cluster_variables(message, existing_variables)
    except Exception:
        msg = _v512b_msg(message)
        variables = list(existing_variables or [])

        if "gor" in msg and "gor" not in variables:
            variables.append("gor")
        if "wct" in msg and "wct" not in variables:
            variables.append("wct")
        if "oil" in msg and "oil" not in variables:
            variables.append("oil")
        if "water" in msg and "water" not in variables:
            variables.append("water")
        if "gas" in msg and "gas" not in variables:
            variables.append("gas")
        if ("bhp" in msg or "pressure" in msg) and "bhp" not in variables:
            variables.append("bhp")

        if "oil, water, gas and bhp" in msg or "oil water gas bhp" in msg:
            variables = ["oil", "water", "gas", "bhp"]

        if not variables:
            variables = ["oil"]

    # Remove duplicates and keep allowed variables only.
    allowed = ["oil", "water", "gas", "gor", "wct", "bhp"]
    out = []

    for v in variables:
        if v in allowed and v not in out:
            out.append(v)

    return out or ["oil"]


def interpret_request_v500(message: str) -> Dict[str, Any]:
    intent = _interpret_request_before_v512b(message)

    if _v512b_is_time_series_cluster_request(message):
        variables = _v512b_detect_cluster_variables(message, intent.get("variables") or [])

        intent["task_type"] = "time_series_clustering"
        intent["variables"] = variables
        intent["time_series_clustering_v512"] = {
            "variables": variables,
            "reason": "V512B final priority guard: profile/time-series clustering request overrides diagnostic_cluster.",
        }
        intent["time_series_clustering_priority_v512b"] = True

        intent.setdefault("flags", {})
        intent["flags"]["clustering"] = True
        intent["flags"]["time_series_clustering"] = True

        # Remove confusing diagnostic labels set by earlier guards.
        for k in [
            "diagnostic_priority_v502",
            "capability_v505b",
            "distribution_priority_v502",
        ]:
            if k in intent:
                intent.pop(k, None)

    return intent


def execute_plan_v500(intent: Dict[str, Any], plan: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    original = intent.get("original_message") or ""

    if intent.get("task_type") == "time_series_clustering" or _v512b_is_time_series_cluster_request(original):
        # Ensure variables are present even if an earlier node overwrote them.
        variables = _v512b_detect_cluster_variables(original, intent.get("variables") or [])
        intent["task_type"] = "time_series_clustering"
        intent["variables"] = variables
        intent["time_series_clustering_v512"] = {
            "variables": variables,
            "reason": "V512B execution guard forced TimeSeriesClusteringAgent.",
        }

        response = _v512_execute_time_series_clustering(intent)

        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["TimeSeriesClusteringPriorityGuardV512B"] = {
                "route": "forced_time_series_clustering",
                "variables": variables,
                "reason": "Cluster request was profile/time-series based, not WCT-bias diagnostic.",
            }

        return response

    return _execute_plan_before_v512b(intent, plan, evidence_board)

# END V512B TIMESERIES CLUSTERING PRIORITY GUARD


# ==========================================================
# V512D TRUE TIMESERIES CLUSTERING EXPORTER
#
# Fix:
# V512C wrapper correctly routes to time_series_clustering, but import fails:
# cannot import name '_v512_execute_time_series_clustering'
#
# This defines the missing top-level function with a self-contained,
# deterministic clustering implementation based on actual profile series.
# ==========================================================


def _v512d_safe_float(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        try:
            return _safe_float_v500(x)
        except Exception:
            return None


def _v512d_profile_for(well, variable):
    try:
        return _v510_get_profile_data(well, variable)
    except Exception:
        return None


def _v512d_known_wells():
    names = []

    try:
        for w in _v506_get_wct_wells():
            name = w.get("well")
            if name and name not in names:
                names.append(name)
    except Exception:
        pass

    for n in range(1, 81):
        name = f"HW-{n}"
        if name not in names:
            names.append(name)

    return names


def _v512d_mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def _v512d_std(vals):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    return (sum((x - m) ** 2 for x in vals) / (len(vals) - 1)) ** 0.5


def _v512d_last(vals):
    vals = [v for v in vals if v is not None]
    return vals[-1] if vals else None


def _v512d_first(vals):
    vals = [v for v in vals if v is not None]
    return vals[0] if vals else None


def _v512d_features_from_series(data, variable):
    raw = [_v512d_safe_float(v) for v in (data.get("simulated") or [])]
    raw = [v for v in raw if v is not None]

    if not raw:
        return None

    # For rate variables, use active positive samples for level/cumulative.
    if variable in {"oil", "water", "gas"}:
        active = [v for v in raw if v > 1e-9]
    else:
        active = raw[:]

    if not active:
        return None

    first = _v512d_first(raw)
    last = _v512d_last(raw)

    diffs = [abs(active[i] - active[i - 1]) for i in range(1, len(active))]
    volatility = sum(diffs) / len(diffs) if diffs else 0.0

    trend = None
    if first is not None and last is not None:
        trend = last - first

    cumulative = sum(active) if variable in {"oil", "water", "gas"} else None

    return {
        f"{variable}_mean": _v512d_mean(active),
        f"{variable}_max": max(active),
        f"{variable}_min": min(active),
        f"{variable}_std": _v512d_std(active),
        f"{variable}_trend": trend,
        f"{variable}_volatility": volatility,
        f"{variable}_cumulative_proxy": cumulative,
        f"{variable}_active_fraction": len(active) / max(1, len(raw)),
    }


def _v512d_build_rows(variables):
    rows = []

    for well in _v512d_known_wells():
        row = {
            "well": well,
            "variables_available": [],
        }

        for variable in variables:
            data = _v512d_profile_for(well, variable)
            if not data:
                continue

            features = _v512d_features_from_series(data, variable)
            if not features:
                continue

            row.update(features)
            row["variables_available"].append(variable)

        if row["variables_available"]:
            rows.append(row)

    # De-duplicate by well.
    dedup = {}
    for r in rows:
        dedup[r["well"]] = r

    return list(dedup.values())


def _v512d_feature_keys(rows):
    out = []
    exclude = {"well", "variables_available", "cluster"}

    for r in rows:
        for k, v in r.items():
            if k in exclude:
                continue
            if isinstance(v, (int, float)) and v is not None and k not in out:
                out.append(k)

    return out


def _v512d_standardize(rows, keys):
    stats = {}

    for k in keys:
        vals = [r.get(k) for r in rows if isinstance(r.get(k), (int, float))]
        if not vals:
            stats[k] = (0.0, 1.0)
            continue

        m = sum(vals) / len(vals)
        s = _v512d_std(vals) or 1.0
        if s == 0:
            s = 1.0

        stats[k] = (m, s)

    vectors = []

    for r in rows:
        vec = []
        for k in keys:
            m, s = stats[k]
            v = r.get(k)
            if not isinstance(v, (int, float)) or v is None:
                v = m
            vec.append((v - m) / s)
        vectors.append(vec)

    return vectors, stats


def _v512d_dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _v512d_mean_vec(vectors):
    if not vectors:
        return []
    n = len(vectors[0])
    return [sum(v[i] for v in vectors) / len(vectors) for i in range(n)]


def _v512d_kmeans(vectors, k=3, max_iter=50):
    n = len(vectors)

    if n == 0:
        return []

    k = max(1, min(k, n))

    order = sorted(range(n), key=lambda i: sum(vectors[i]))

    if k == 1:
        centers = [vectors[order[n // 2]]]
    elif k == 2:
        centers = [vectors[order[0]], vectors[order[-1]]]
    else:
        centers = [vectors[order[0]], vectors[order[n // 2]], vectors[order[-1]]][:k]

    labels = [0] * n

    for _ in range(max_iter):
        changed = False

        for i, vec in enumerate(vectors):
            dists = [_v512d_dist(vec, c) for c in centers]
            label = min(range(k), key=lambda j: dists[j])

            if label != labels[i]:
                labels[i] = label
                changed = True

        new_centers = []

        for j in range(k):
            members = [vectors[i] for i in range(n) if labels[i] == j]
            new_centers.append(_v512d_mean_vec(members) if members else centers[j])

        centers = new_centers

        if not changed:
            break

    return labels


def _v512d_primary_keys(variables):
    main = variables[0] if variables else "oil"
    return f"{main}_mean", f"{main}_trend"


def _v512d_cluster_summary(rows, variables):
    level_key, trend_key = _v512d_primary_keys(variables)
    clusters = sorted(set(r.get("cluster", 0) for r in rows))

    all_levels = [r.get(level_key) for r in rows if isinstance(r.get(level_key), (int, float))]
    median = sorted(all_levels)[len(all_levels) // 2] if all_levels else None

    summaries = []

    for c in clusters:
        members = [r for r in rows if r.get("cluster") == c]

        levels = [r.get(level_key) for r in members if isinstance(r.get(level_key), (int, float))]
        trends = [r.get(trend_key) for r in members if isinstance(r.get(trend_key), (int, float))]

        avg_level = _v512d_mean(levels)
        avg_trend = _v512d_mean(trends)

        if avg_level is None:
            level_label = "unknown response"
        elif median is not None and avg_level > 1.25 * median:
            level_label = "high response"
        elif median is not None and avg_level < 0.75 * median:
            level_label = "low response"
        else:
            level_label = "medium response"

        if avg_trend is None:
            trend_label = "unknown trend"
        elif avg_trend < 0:
            trend_label = "declining"
        elif avg_trend > 0:
            trend_label = "increasing"
        else:
            trend_label = "stable"

        summaries.append({
            "Cluster": f"C{c + 1}",
            "Count": len(members),
            "Wells": ", ".join([m.get("well") for m in members[:8]]) + ("..." if len(members) > 8 else ""),
            "Mean level": round(avg_level, 5) if avg_level is not None else None,
            "Mean trend": round(avg_trend, 5) if avg_trend is not None else None,
            "Interpretation": f"{level_label}, {trend_label} {variables[0].upper()} behaviour",
        })

    return summaries


def _v512d_plot_block(rows, variables):
    level_key, trend_key = _v512d_primary_keys(variables)

    x = []
    y = []
    labels = []
    color = []
    custom = []

    for r in rows:
        xv = r.get(level_key)
        yv = r.get(trend_key)

        if not isinstance(xv, (int, float)):
            xv = 0.0
        if not isinstance(yv, (int, float)):
            yv = 0.0

        c = int(r.get("cluster", 0))

        x.append(xv)
        y.append(yv)
        labels.append(r.get("well"))
        color.append(c)
        custom.append([
            r.get("well"),
            f"C{c + 1}",
            ", ".join(r.get("variables_available") or []),
        ])

    title = f"Well clusters based on {', '.join(v.upper() for v in variables)} profiles"

    return {
        "type": "plotly_chart",
        "title": title,
        "data": [
            {
                "type": "scatter",
                "mode": "markers+text",
                "name": "Wells",
                "x": x,
                "y": y,
                "text": labels,
                "customdata": custom,
                "textposition": "top center",
                "marker": {
                    "size": 13,
                    "color": color,
                    "colorscale": "Viridis",
                    "showscale": True,
                    "colorbar": {"title": "Cluster"},
                },
                "hovertemplate": (
                    "Well: %{customdata[0]}<br>"
                    "Cluster: %{customdata[1]}<br>"
                    "Variables: %{customdata[2]}<br>"
                    "Mean level: %{x:.5g}<br>"
                    "Trend: %{y:.5g}<extra></extra>"
                ),
            }
        ],
        "layout": {
            "title": title,
            "xaxis": {
                "title": f"{variables[0].upper()} mean level",
                "showgrid": False,
            },
            "yaxis": {
                "title": f"{variables[0].upper()} trend",
                "showgrid": False,
                "zeroline": False,
            },
            "height": 560,
            "hovermode": "closest",
            "margin": {"l": 80, "r": 50, "t": 60, "b": 80},
            "plot_bgcolor": "rgba(0,0,0,0)",
            "paper_bgcolor": "rgba(0,0,0,0)",
        },
        "config": {
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True,
        },
    }


def _v512d_membership_rows(rows, variables):
    level_key, trend_key = _v512d_primary_keys(variables)

    out = []

    for r in sorted(rows, key=lambda x: (x.get("cluster", 0), x.get("well", ""))):
        level = r.get(level_key)
        trend = r.get(trend_key)

        out.append({
            "Well": r.get("well"),
            "Cluster": f"C{int(r.get('cluster', 0)) + 1}",
            "Variables": ", ".join(r.get("variables_available") or []),
            "Mean level": round(level, 5) if isinstance(level, (int, float)) else None,
            "Trend": round(trend, 5) if isinstance(trend, (int, float)) else None,
        })

    return out


def _v512_execute_time_series_clustering(intent):
    variables = intent.get("variables") or ["oil"]
    variables = [v for v in variables if v in {"oil", "water", "gas", "gor", "wct", "bhp"}] or ["oil"]

    rows = _v512d_build_rows(variables)

    if len(rows) < 2:
        return {
            "type": "reasoning_response",
            "intent": "time_series_clustering",
            "answer": (
                f"I understood the request as profile clustering based on {', '.join(v.upper() for v in variables)}, "
                f"but only {len(rows)} wells had usable profile data."
            ),
            "ui_blocks": [],
            "data": {
                "variables": variables,
                "wells_clustered": len(rows),
                "method": "true profile clustering failed: not enough usable profiles",
            },
            "agent_trace": {
                "TimeSeriesClusteringAgentV512D": {
                    "status": "not_enough_profiles",
                    "variables": variables,
                    "usable_wells": len(rows),
                }
            },
        }

    keys = _v512d_feature_keys(rows)
    vectors, stats = _v512d_standardize(rows, keys)

    k = 3 if len(rows) >= 6 else min(2, len(rows))
    labels = _v512d_kmeans(vectors, k=k)

    for r, label in zip(rows, labels):
        r["cluster"] = int(label)

    summaries = _v512d_cluster_summary(rows, variables)
    membership = _v512d_membership_rows(rows, variables)
    plot = _v512d_plot_block(rows, variables)

    return {
        "type": "visual_response",
        "intent": "time_series_clustering",
        "answer": (
            f"I clustered {len(rows)} wells using actual profile-derived features from "
            f"{', '.join(v.upper() for v in variables)}. "
            "Features include mean level, max/min, trend, volatility, cumulative proxy and active fraction where applicable."
        ),
        "ui_blocks": [
            plot,
            {
                "type": "compact_table",
                "title": "Cluster summary",
                "columns": ["Cluster", "Count", "Wells", "Mean level", "Mean trend", "Interpretation"],
                "rows": summaries,
            },
            {
                "type": "compact_table",
                "title": "Well cluster membership",
                "columns": ["Well", "Cluster", "Variables", "Mean level", "Trend"],
                "rows": membership,
            },
        ],
        "data": {
            "variables": variables,
            "wells_clustered": len(rows),
            "clusters": k,
            "feature_keys": keys,
            "method": "true profile-derived deterministic z-score k-means",
        },
        "agent_trace": {
            "TimeSeriesClusteringAgentV512D": {
                "route": "profile extraction -> feature engineering -> deterministic k-means",
                "variables": variables,
                "wells_clustered": len(rows),
                "clusters": k,
                "feature_keys": keys,
            }
        },
    }

# END V512D TRUE TIMESERIES CLUSTERING EXPORTER


# ==========================================================
# V513 GAS / GOR / BHP MISMATCH DIAGNOSTIC AGENT
#
# Supports:
# - Show me gas mismatch clusters
# - Show me GOR mismatch clusters
# - Show me BHP mismatch clusters
# - Which wells have the worst gas match?
# - Rank wells by gas mismatch severity
# - Show wells where simulated gas is too high / too low
# - Correlate gas mismatch with pressure depletion
# - Correlate gas mismatch with permeability
# - Correlate GOR mismatch with water cut mismatch
#
# Principle:
# This is diagnostic mismatch clustering/ranking, not profile-behaviour
# time-series clustering. It uses available HM scores and diagnostic
# payloads. When true directional information is not exposed, it says so
# instead of inventing simulated-too-high/too-low.
# ==========================================================

_interpret_request_before_v513 = interpret_request_v500
_execute_plan_before_v513 = execute_plan_v500


def _v513_msg(message):
    return _norm_v500(message)


def _v513_contains_any(msg, terms):
    return any(t in msg for t in terms)


def _v513_is_request(message):
    msg = _v513_msg(message)

    return (
        _v513_contains_any(msg, [
            "gas mismatch",
            "gor mismatch",
            "bhp mismatch",
            "pressure mismatch",
            "worst gas match",
            "worst gor match",
            "worst bhp match",
            "rank wells by gas",
            "rank wells by gor",
            "rank wells by bhp",
            "gas match severity",
            "gor match severity",
            "bhp match severity",
            "simulated gas is too high",
            "simulated gas too high",
            "simulated gas is too low",
            "simulated gas too low",
        ])
        or (
            "correlate" in msg and
            (
                ("gas" in msg and "mismatch" in msg)
                or ("gor" in msg and "mismatch" in msg)
                or ("bhp" in msg and "mismatch" in msg)
            )
        )
    )


def _v513_variable(message):
    msg = _v513_msg(message)

    if "gor" in msg:
        return "gor"

    if "bhp" in msg or "pressure mismatch" in msg:
        return "bhp"

    if "pressure depletion" in msg:
        # If user says gas mismatch with pressure depletion, variable remains gas.
        if "gas mismatch" in msg:
            return "gas"
        return "bhp"

    return "gas"


def _v513_task_kind(message):
    msg = _v513_msg(message)

    if "correlate" in msg or "correlation" in msg or "vs" in msg or "versus" in msg:
        return "correlation"

    if "rank" in msg or "worst" in msg or "severity" in msg or "which wells" in msg:
        return "ranking"

    if "too high" in msg or "too low" in msg:
        return "direction_filter"

    if "cluster" in msg or "clusters" in msg or "map" in msg:
        return "cluster"

    return "ranking"


def interpret_request_v500(message: str) -> Dict[str, Any]:
    intent = _interpret_request_before_v513(message)

    if _v513_is_request(message):
        var = _v513_variable(message)
        kind = _v513_task_kind(message)

        intent["task_type"] = "mismatch_diagnostic_v513"
        intent["variables"] = [var]
        intent["mismatch_diagnostic_v513"] = {
            "variable": var,
            "kind": kind,
            "reason": "Gas/GOR/BHP mismatch diagnostic request detected.",
        }
        intent.setdefault("flags", {})
        intent["flags"]["mismatch_diagnostic"] = True

    return intent


def _v513_get_wells():
    try:
        wells = _v506_get_wct_wells()
    except Exception:
        wells = []

    final = []
    seen = set()

    for w in wells:
        if not isinstance(w, dict):
            continue

        name = w.get("well")
        if not name or name in seen:
            continue

        seen.add(name)
        final.append(w)

    return final


def _v513_score(w, variable):
    if variable == "gas":
        return _safe_float_v500(w.get("gas_score"))

    if variable == "bhp":
        return _safe_float_v500(w.get("bhp_score"))

    if variable == "gor":
        # If explicit GOR score does not exist, use a computed-profile proxy if possible,
        # otherwise use gas_score as conservative proxy.
        return _v513_computed_profile_score(w.get("well"), "gor") or _safe_float_v500(w.get("gas_score"))

    if variable == "wct":
        return _safe_float_v500(w.get("water_score"))

    return _safe_float_v500(w.get("overall_score"))


def _v513_computed_profile_score(well, variable):
    if not well:
        return None

    try:
        data = _v510_get_profile_data(well, variable)
    except Exception:
        return None

    if not data:
        return None

    sim = [_safe_float_v500(v) for v in (data.get("simulated") or [])]
    obs = [_safe_float_v500(v) for v in (data.get("observed") or [])]

    pairs = []
    for s, o in zip(sim, obs):
        if s is None or o is None:
            continue
        pairs.append((s, o))

    if len(pairs) < 3:
        return None

    mean_obs = sum(abs(o) for _, o in pairs) / len(pairs)
    denom = mean_obs if mean_obs > 1e-9 else 1.0
    mae = sum(abs(s - o) for s, o in pairs) / len(pairs)
    nmae = mae / denom

    score = max(0.0, min(100.0, 100.0 * (1.0 - nmae)))

    return score


def _v513_mismatch(w, variable):
    score = _v513_score(w, variable)

    if score is None:
        return None

    return max(0.0, 100.0 - score)


def _v513_cluster_label(score):
    if score is None:
        return ("C0", 0, "No score available")

    if score >= 90:
        return ("C1", 1, "Good match / low mismatch")

    if score >= 70:
        return ("C2", 2, "Fair match / moderate mismatch")

    return ("C3", 3, "Poor match / high mismatch")


def _v513_variable_label(variable):
    return {
        "gas": "Gas",
        "gor": "GOR",
        "bhp": "BHP / pressure",
        "wct": "WCT",
    }.get(variable, variable.upper())


def _v513_direction_note(w, variable, requested_direction=None):
    # Directional gas/GOR/BHP fields are generally not exposed in the current diagnostic payload.
    # Water has direction, but for gas/BHP we avoid inventing direction.
    if variable == "wct":
        return w.get("water_direction") or "direction not available"

    if requested_direction:
        return (
            f"{requested_direction} requested, but explicit simulated-vs-observed direction "
            "is not exposed in the current diagnostic payload"
        )

    return "direction not available"


def _v513_requested_direction(message):
    msg = _v513_msg(message)

    if "too high" in msg:
        return "simulated too high"

    if "too low" in msg:
        return "simulated too low"

    return None


def _v513_rows(variable, message=""):
    wells = _v513_get_wells()
    requested_direction = _v513_requested_direction(message)

    rows = []

    for w in wells:
        score = _v513_score(w, variable)
        mismatch = _v513_mismatch(w, variable)
        cluster, cluster_code, label = _v513_cluster_label(score)

        rows.append({
            "well": w.get("well"),
            "i": w.get("i"),
            "j": w.get("j"),
            "score": score,
            "mismatch": mismatch,
            "cluster": cluster,
            "cluster_code": cluster_code,
            "cluster_label": label,
            "direction": _v513_direction_note(w, variable, requested_direction),
            "overall_score": _safe_float_v500(w.get("overall_score")),
            "oil_score": _safe_float_v500(w.get("oil_score")),
            "water_score": _safe_float_v500(w.get("water_score")),
            "gas_score": _safe_float_v500(w.get("gas_score")),
            "bhp_score": _safe_float_v500(w.get("bhp_score")),
            "delta_pressure": _safe_float_v500(w.get("delta_pressure")),
            "pressure_depletion": abs(_safe_float_v500(w.get("delta_pressure")) or 0.0),
            "perm_percentile": _safe_float_v500(w.get("perm_percentile")),
            "poro_percentile": _safe_float_v500(w.get("poro_percentile")),
            "tran_percentile": _safe_float_v500(w.get("tran_percentile")),
            "water_mismatch": max(0.0, 100.0 - (_safe_float_v500(w.get("water_score")) or 0.0)),
            "bias": w.get("bias") or "",
        })

    rows = [r for r in rows if r["score"] is not None]

    # Worst first.
    rows.sort(key=lambda r: r["mismatch"] if r["mismatch"] is not None else -1, reverse=True)

    return rows


def _v513_cluster_summary(rows):
    clusters = sorted(set(r["cluster"] for r in rows))

    out = []

    for c in clusters:
        members = [r for r in rows if r["cluster"] == c]
        if not members:
            continue

        avg_score = sum(r["score"] for r in members if r["score"] is not None) / len(members)
        avg_mismatch = sum(r["mismatch"] for r in members if r["mismatch"] is not None) / len(members)

        out.append({
            "Cluster": c,
            "Count": len(members),
            "Wells": ", ".join(r["well"] for r in members[:8]) + ("..." if len(members) > 8 else ""),
            "Avg score": round(avg_score, 2),
            "Avg mismatch": round(avg_mismatch, 2),
            "Interpretation": members[0]["cluster_label"],
        })

    return out


def _v513_map_block(rows, variable):
    label = _v513_variable_label(variable)

    plot_rows = [r for r in rows if r.get("i") is not None and r.get("j") is not None]

    title = f"{label} mismatch cluster map"

    return {
        "type": "plotly_chart",
        "title": title,
        "data": [
            {
                "type": "scatter",
                "mode": "markers+text",
                "name": "Wells",
                "x": [r["i"] for r in plot_rows],
                "y": [r["j"] for r in plot_rows],
                "text": [r["well"] for r in plot_rows],
                "customdata": [
                    [
                        r["well"],
                        r["cluster"],
                        round(r["score"], 2) if r["score"] is not None else None,
                        round(r["mismatch"], 2) if r["mismatch"] is not None else None,
                        r["cluster_label"],
                        r["direction"],
                    ]
                    for r in plot_rows
                ],
                "textposition": "top center",
                "marker": {
                    "size": [max(10, min(24, 8 + (r["mismatch"] or 0) / 4.0)) for r in plot_rows],
                    "color": [r["mismatch"] for r in plot_rows],
                    "colorscale": "Viridis",
                    "showscale": True,
                    "colorbar": {"title": "Mismatch"},
                },
                "hovertemplate": (
                    "Well: %{customdata[0]}<br>"
                    "Cluster: %{customdata[1]}<br>"
                    "Score: %{customdata[2]}<br>"
                    "Mismatch: %{customdata[3]}<br>"
                    "%{customdata[4]}<br>"
                    "Direction: %{customdata[5]}<extra></extra>"
                ),
            }
        ],
        "layout": {
            "title": title,
            "xaxis": {"title": "I index", "showgrid": False},
            "yaxis": {"title": "J index", "showgrid": False},
            "height": 560,
            "hovermode": "closest",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "paper_bgcolor": "rgba(0,0,0,0)",
            "margin": {"l": 70, "r": 50, "t": 60, "b": 70},
        },
        "config": {"responsive": True, "displaylogo": False, "scrollZoom": True},
    }


def _v513_ranking_table(rows, variable, limit=15):
    label = _v513_variable_label(variable)

    table_rows = []

    for r in rows[:limit]:
        table_rows.append({
            "Well": r["well"],
            f"{label} score": round(r["score"], 2) if r["score"] is not None else None,
            "Mismatch": round(r["mismatch"], 2) if r["mismatch"] is not None else None,
            "Cluster": r["cluster"],
            "Direction": r["direction"],
            "Overall": round(r["overall_score"], 2) if r["overall_score"] is not None else None,
            "BHP score": round(r["bhp_score"], 2) if r["bhp_score"] is not None else None,
            "Gas score": round(r["gas_score"], 2) if r["gas_score"] is not None else None,
        })

    return {
        "type": "compact_table",
        "title": f"{label} mismatch ranking",
        "columns": ["Well", f"{label} score", "Mismatch", "Cluster", "Direction", "Overall", "BHP score", "Gas score"],
        "rows": table_rows,
    }


def _v513_cluster_response(message, variable):
    rows = _v513_rows(variable, message)
    label = _v513_variable_label(variable)

    if not rows:
        return {
            "type": "reasoning_response",
            "intent": "mismatch_diagnostic_v513",
            "answer": f"I detected a {label} mismatch diagnostic request, but no well-level score payload was available.",
            "ui_blocks": [],
            "agent_trace": {
                "MismatchDiagnosticAgentV513": {
                    "status": "no_rows",
                    "variable": variable,
                }
            },
        }

    worst = rows[0]

    all_good = all((r["score"] or 0) >= 90 for r in rows)

    if all_good:
        interpretation = (
            f"All available wells have good {label} match scores. The map therefore shows relative mismatch severity, "
            "not a severe field-wide mismatch."
        )
    else:
        interpretation = (
            f"The weakest {label} match is {worst['well']} with score {worst['score']:.2f} "
            f"and mismatch severity {worst['mismatch']:.2f}."
        )

    return {
        "type": "visual_response",
        "intent": "mismatch_diagnostic_v513",
        "answer": (
            f"I generated a {label} mismatch cluster view. {interpretation} "
            "Clusters are based on available history-match score severity. "
            "If explicit simulated-too-high/too-low direction is not exposed, the direction column is marked accordingly."
        ),
        "ui_blocks": [
            _v513_map_block(rows, variable),
            {
                "type": "compact_table",
                "title": f"{label} mismatch cluster summary",
                "columns": ["Cluster", "Count", "Wells", "Avg score", "Avg mismatch", "Interpretation"],
                "rows": _v513_cluster_summary(rows),
            },
            _v513_ranking_table(rows, variable),
        ],
        "data": {
            "variable": variable,
            "wells_ranked": len(rows),
            "method": "well-level mismatch severity from available diagnostic HM scores",
            "all_good_match": all_good,
        },
        "agent_trace": {
            "MismatchDiagnosticAgentV513": {
                "route": "diagnostic score payload -> mismatch clusters/map/ranking",
                "variable": variable,
                "wells_ranked": len(rows),
                "all_good_match": all_good,
            }
        },
    }


def _v513_ranking_response(message, variable):
    rows = _v513_rows(variable, message)
    label = _v513_variable_label(variable)

    if not rows:
        return _v513_cluster_response(message, variable)

    all_good = all((r["score"] or 0) >= 90 for r in rows)

    if all_good:
        note = (
            f"All available wells have good {label} match scores; the ranking shows the weakest relative matches, "
            "not severe mismatch cases."
        )
    else:
        note = f"The table ranks wells by {label} mismatch severity, worst first."

    return {
        "type": "visual_response",
        "intent": "mismatch_ranking_v513",
        "answer": note,
        "ui_blocks": [
            _v513_ranking_table(rows, variable),
            _v513_map_block(rows, variable),
        ],
        "data": {
            "variable": variable,
            "wells_ranked": len(rows),
            "method": "ranked by 100 - match score",
            "all_good_match": all_good,
        },
        "agent_trace": {
            "MismatchRankingAgentV513": {
                "variable": variable,
                "wells_ranked": len(rows),
                "all_good_match": all_good,
            }
        },
    }


def _v513_correlation_axis(message, variable):
    msg = _v513_msg(message)

    if "pressure depletion" in msg or "pressure drop" in msg or "bhp" in msg:
        return "pressure_depletion", "Pressure depletion magnitude"

    if "permeability" in msg or "perm" in msg:
        return "perm_percentile", "PERM percentile"

    if "water cut" in msg or "wct" in msg:
        return "water_mismatch", "WCT / water mismatch severity"

    if "tran" in msg or "connectivity" in msg:
        return "tran_percentile", "TRAN percentile"

    return "perm_percentile", "PERM percentile"


def _v513_correlation_response(message, variable):
    rows = _v513_rows(variable, message)
    label = _v513_variable_label(variable)
    x_key, x_label = _v513_correlation_axis(message, variable)

    points = []

    for r in rows:
        x = r.get(x_key)
        y = r.get("mismatch")

        if x is None or y is None:
            continue

        points.append({**r, "x": x, "y": y})

    title = f"{label} mismatch vs {x_label}"

    if not points:
        return {
            "type": "reasoning_response",
            "intent": "mismatch_correlation_v513",
            "answer": f"I could not build the correlation plot because no overlapping {label} mismatch and {x_label} values were available.",
            "ui_blocks": [],
            "agent_trace": {
                "MismatchCorrelationAgentV513": {
                    "status": "no_points",
                    "variable": variable,
                    "x_key": x_key,
                }
            },
        }

    # Simple Pearson correlation.
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]

    corr = None
    try:
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        sx = (sum((x - mx) ** 2 for x in xs) / max(1, len(xs) - 1)) ** 0.5
        sy = (sum((y - my) ** 2 for y in ys) / max(1, len(ys) - 1)) ** 0.5
        if sx > 0 and sy > 0:
            corr = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / max(1, len(xs) - 1) / sx / sy
    except Exception:
        corr = None

    scatter = {
        "type": "plotly_chart",
        "title": title,
        "data": [
            {
                "type": "scatter",
                "mode": "markers+text",
                "name": "Wells",
                "x": xs,
                "y": ys,
                "text": [p["well"] for p in points],
                "customdata": [[p["well"], p["cluster"], round(p["score"], 2), round(p["mismatch"], 2)] for p in points],
                "textposition": "top center",
                "marker": {"size": 13},
                "hovertemplate": (
                    "Well: %{customdata[0]}<br>"
                    "Cluster: %{customdata[1]}<br>"
                    "Score: %{customdata[2]}<br>"
                    "Mismatch: %{customdata[3]}<br>"
                    f"{x_label}: %{{x:.5g}}<br>"
                    "Mismatch: %{y:.5g}<extra></extra>"
                ),
            }
        ],
        "layout": {
            "title": title,
            "xaxis": {"title": x_label, "showgrid": False},
            "yaxis": {"title": f"{label} mismatch severity", "showgrid": False},
            "height": 560,
            "hovermode": "closest",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "paper_bgcolor": "rgba(0,0,0,0)",
        },
        "config": {"responsive": True, "displaylogo": False, "scrollZoom": True},
    }

    table_rows = []
    for p in sorted(points, key=lambda r: r["y"], reverse=True):
        table_rows.append({
            "Well": p["well"],
            x_label: round(p["x"], 5),
            f"{label} score": round(p["score"], 2),
            "Mismatch": round(p["mismatch"], 2),
            "Cluster": p["cluster"],
        })

    return {
        "type": "visual_response",
        "intent": "mismatch_correlation_v513",
        "answer": (
            f"I cross-plotted {label} mismatch severity against {x_label}. "
            f"Correlation coefficient: {corr:.3f}." if corr is not None else
            f"I cross-plotted {label} mismatch severity against {x_label}. Correlation could not be computed robustly."
        ),
        "ui_blocks": [
            scatter,
            {
                "type": "compact_table",
                "title": title + " evidence",
                "columns": ["Well", x_label, f"{label} score", "Mismatch", "Cluster"],
                "rows": table_rows,
            },
        ],
        "data": {
            "variable": variable,
            "x_key": x_key,
            "points": len(points),
            "correlation": corr,
            "method": "well-level diagnostic score correlation",
        },
        "agent_trace": {
            "MismatchCorrelationAgentV513": {
                "variable": variable,
                "x_key": x_key,
                "points": len(points),
                "correlation": corr,
            }
        },
    }


def _v513_execute(message, variable=None, kind=None):
    variable = variable or _v513_variable(message)
    kind = kind or _v513_task_kind(message)

    if kind == "correlation":
        return _v513_correlation_response(message, variable)

    if kind in {"ranking", "direction_filter"}:
        return _v513_ranking_response(message, variable)

    return _v513_cluster_response(message, variable)


def execute_plan_v500(intent: Dict[str, Any], plan: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    original = intent.get("original_message") or ""

    if intent.get("mismatch_diagnostic_v513") or _v513_is_request(original):
        cfg = intent.get("mismatch_diagnostic_v513") or {}
        variable = cfg.get("variable") or _v513_variable(original)
        kind = cfg.get("kind") or _v513_task_kind(original)

        return _v513_execute(original, variable, kind)

    return _execute_plan_before_v513(intent, plan, evidence_board)

# END V513 GAS / GOR / BHP MISMATCH DIAGNOSTIC AGENT


# ==========================================================
# V514 INTEGRATED PARALLEL DIAGNOSIS AGENT
#
# Goal:
# Answer "why / caused by / connectivity vs relperm / compare evidence"
# using all available evidence together:
# - oil, water/WCT, gas/GOR, BHP/pressure scores
# - WCT bias / timing / direction
# - delta pressure
# - SWAT/PRESSURE/TRAN/PERM/PORO percentiles
# - connectivity vs RelPerm vs pressure-support hypotheses
#
# Critical rule:
# RelPerm is only one evidence source. It cannot be the final answer alone.
# ==========================================================

_interpret_request_before_v514 = interpret_request_v500
_execute_plan_before_v514 = execute_plan_v500


def _v514_msg(message):
    return _norm_v500(message)


def _v514_contains_any(msg, terms):
    return any(t in msg for t in terms)


def _v514_extract_well(message):
    import re
    m = re.search(r"\bHW[-\s]?(\d+)\b", str(message or ""), flags=re.IGNORECASE)
    if m:
        return f"HW-{int(m.group(1))}"
    return None


def _v514_is_integrated_diagnosis_request(message):
    msg = _v514_msg(message)

    triggers = [
        "why", "explain", "caused by", "cause", "root cause",
        "more likely", "likely cause", "driver", "main driver",
        "compare evidence", "compare the evidence",
        "connectivity issue", "relperm issue", "rel perm issue",
        "pressure issue", "well control",
        "what should", "review first",
        "model review",
        "risky because", "justified than",
        "perche", "perché", "spiegami", "causa", "confronta"
    ]

    reservoir_terms = [
        "mismatch", "water", "wct", "gas", "gor", "bhp", "pressure",
        "oil", "permx", "perm", "poro", "swat", "tran",
        "connectivity", "connected", "relperm", "rel perm",
        "history match", "history matching",
        "hw-"
    ]

    if _v514_contains_any(msg, triggers) and _v514_contains_any(msg, reservoir_terms):
        return True

    # Also catch top-review questions.
    if _v514_contains_any(msg, ["top 5 wells", "requiring model review", "model review"]):
        return True

    return False


def interpret_request_v500(message: str) -> Dict[str, Any]:
    intent = _interpret_request_before_v514(message)

    if _v514_is_integrated_diagnosis_request(message):
        well = _v514_extract_well(message)

        intent["task_type"] = "integrated_parallel_diagnosis_v514"
        intent["well"] = well or intent.get("well")
        intent["integrated_parallel_diagnosis_v514"] = {
            "well": well or intent.get("well"),
            "reason": "Integrated diagnosis request detected: why/caused-by/connectivity-vs-relperm/compare-evidence.",
        }

        intent.setdefault("flags", {})
        intent["flags"]["integrated_diagnosis"] = True

    return intent


def _v514_get_all_diag_wells():
    try:
        return _v506_get_wct_wells()
    except Exception:
        return []


def _v514_find_well(well):
    wells = _v514_get_all_diag_wells()

    for w in wells:
        if str(w.get("well", "")).upper() == str(well or "").upper():
            return w

    return None


def _v514_sf(x, default=None):
    v = _safe_float_v500(x)
    return default if v is None else v


def _v514_mismatch(score):
    s = _v514_sf(score)
    if s is None:
        return None
    return max(0.0, 100.0 - s)


def _v514_score_bucket(score):
    s = _v514_sf(score)
    if s is None:
        return "N/A"
    if s >= 90:
        return "good"
    if s >= 70:
        return "fair"
    if s >= 50:
        return "weak"
    return "poor"


def _v514_evidence_for_well(w):
    if not w:
        return {}

    oil = _v514_sf(w.get("oil_score"))
    water = _v514_sf(w.get("water_score"))
    gas = _v514_sf(w.get("gas_score"))
    bhp = _v514_sf(w.get("bhp_score"))
    overall = _v514_sf(w.get("overall_score"))

    return {
        "well": w.get("well"),
        "oil_score": oil,
        "water_score": water,
        "gas_score": gas,
        "bhp_score": bhp,
        "overall_score": overall,
        "oil_mismatch": _v514_mismatch(oil),
        "water_mismatch": _v514_mismatch(water),
        "gas_mismatch": _v514_mismatch(gas),
        "bhp_mismatch": _v514_mismatch(bhp),
        "wct_bias": w.get("bias") or "",
        "water_direction": w.get("water_direction") or "",
        "water_timing": w.get("water_timing") or "",
        "delta_pressure": _v514_sf(w.get("delta_pressure")),
        "delta_pressure_abs": abs(_v514_sf(w.get("delta_pressure"), 0.0)),
        "delta_pressure_percentile": _v514_sf(w.get("delta_pressure_percentile")),
        "delta_swat": _v514_sf(w.get("delta_swat")),
        "delta_swat_percentile": _v514_sf(w.get("delta_swat_percentile")),
        "mean_swat_eoh_percentile": _v514_sf(w.get("mean_swat_eoh_percentile")),
        "tran_percentile": _v514_sf(w.get("tran_percentile")),
        "perm_percentile": _v514_sf(w.get("perm_percentile")),
        "poro_percentile": _v514_sf(w.get("poro_percentile")),
        "i": w.get("i"),
        "j": w.get("j"),
    }


def _v514_hypothesis_scores(e):
    water_mis = e.get("water_mismatch") or 0.0
    gas_mis = e.get("gas_mismatch") or 0.0
    bhp_mis = e.get("bhp_mismatch") or 0.0
    oil_mis = e.get("oil_mismatch") or 0.0

    tran = e.get("tran_percentile")
    perm = e.get("perm_percentile")
    poro = e.get("poro_percentile")
    swat = e.get("delta_swat_percentile")
    dp_pct = e.get("delta_pressure_percentile")
    dp_abs = e.get("delta_pressure_abs") or 0.0

    bias = str(e.get("wct_bias") or "").lower()
    timing = str(e.get("water_timing") or "").lower()
    direction = str(e.get("water_direction") or "").lower()

    hypotheses = []

    # Connectivity / transmissibility.
    conn_score = 0.0
    conn_support = []
    conn_counter = []

    if water_mis > 30:
        conn_score += min(35, water_mis * 0.35)
        conn_support.append("material water/WCT mismatch")

    if bhp_mis > 25:
        conn_score += min(25, bhp_mis * 0.30)
        conn_support.append("BHP/pressure mismatch supports dynamic connectivity uncertainty")

    if tran is not None:
        if tran < 35:
            conn_score += 25
            conn_support.append("low TRAN percentile suggests possible insufficient communication")
        elif tran > 75:
            conn_score += 10
            conn_support.append("high TRAN percentile means connectivity is important but may be over/redistributed")
            conn_counter.append("high TRAN percentile weakens a simple 'too low connectivity' explanation")

    if perm is not None:
        if perm < 35:
            conn_score += 15
            conn_support.append("low PERM percentile supports local transmissibility concern")
        elif perm > 75:
            conn_counter.append("high PERM percentile weakens a pure low-permeability explanation")

    if "late" in bias or "late" in timing or "underestimates" in bias:
        conn_score += 10
        conn_support.append("late/underestimated water can be caused by insufficient effective connection to water source")

    hypotheses.append({
        "Hypothesis": "Connectivity / TRAN issue",
        "Score": round(min(100, conn_score), 1),
        "Supporting evidence": "; ".join(conn_support) if conn_support else "limited direct support",
        "Counter evidence": "; ".join(conn_counter) if conn_counter else "none obvious from exposed payload",
        "Review first": "TRAN corridors, well connections, local permeability/upscaling, streamline/communication evidence",
    })

    # RelPerm / endpoint saturation.
    rel_score = 0.0
    rel_support = []
    rel_counter = []

    if water_mis > 30 and oil_mis < 15:
        rel_score += 35
        rel_support.append("oil match is good while water/WCT is poor")

    if gas_mis < 10 and water_mis > 30:
        rel_score += 20
        rel_support.append("gas match is good, so water-specific physics may be responsible")

    if "underestimates" in bias or "late" in timing:
        rel_score += 15
        rel_support.append("underestimated/late water can indicate water relperm/endpoints too conservative")

    if swat is not None and swat > 70:
        rel_score += 15
        rel_support.append("high delta SWAT percentile indicates strong saturation-change evidence")

    if tran is not None and tran > 60 and water_mis > 30:
        rel_score += 10
        rel_support.append("water mismatch persists despite moderate/high connectivity proxy")

    if bhp_mis > 45:
        rel_counter.append("large BHP mismatch means pressure/connectivity must be checked before tuning RelPerm")

    hypotheses.append({
        "Hypothesis": "RelPerm / endpoint saturation issue",
        "Score": round(min(100, rel_score), 1),
        "Supporting evidence": "; ".join(rel_support) if rel_support else "limited direct support",
        "Counter evidence": "; ".join(rel_counter) if rel_counter else "none obvious from exposed payload",
        "Review first": "water relperm curves, endpoints, connate/residual saturations, saturation upscaling",
    })

    # Pressure support / BHP.
    pressure_score = 0.0
    pressure_support = []
    pressure_counter = []

    if bhp_mis > 30:
        pressure_score += min(50, bhp_mis * 0.7)
        pressure_support.append("BHP match is weak")

    if dp_abs > 300:
        pressure_score += 20
        pressure_support.append("large pressure change/depletion magnitude")

    if dp_pct is not None and dp_pct < 35:
        pressure_score += 10
        pressure_support.append("pressure diagnostic percentile is weak")

    if gas_mis < 10 and oil_mis < 10 and water_mis > 30:
        pressure_counter.append("oil/gas are good, so pressure is not the only explanation")

    hypotheses.append({
        "Hypothesis": "Pressure support / aquifer / boundary issue",
        "Score": round(min(100, pressure_score), 1),
        "Supporting evidence": "; ".join(pressure_support) if pressure_support else "limited direct support",
        "Counter evidence": "; ".join(pressure_counter) if pressure_counter else "none obvious from exposed payload",
        "Review first": "pressure initialization, boundary/aquifer support, BHP constraints, depletion trend",
    })

    # Well control / allocation / measurement.
    control_score = 0.0
    control_support = []
    control_counter = []

    if oil_mis > 20 and gas_mis > 20 and water_mis > 20:
        control_score += 40
        control_support.append("multiple phases mismatch together")

    if gas_mis > 20 and bhp_mis > 25:
        control_score += 25
        control_support.append("gas and BHP mismatch together may indicate controls/allocation/pressure constraint issue")

    if oil_mis < 10 and gas_mis < 10 and water_mis > 30:
        control_counter.append("oil and gas are good, so global control/allocation issue is less likely")

    hypotheses.append({
        "Hypothesis": "Well control / allocation / measurement issue",
        "Score": round(min(100, control_score), 1),
        "Supporting evidence": "; ".join(control_support) if control_support else "limited direct support",
        "Counter evidence": "; ".join(control_counter) if control_counter else "none obvious from exposed payload",
        "Review first": "well controls, allocation factors, phase measurements, constraints, shut-in periods",
    })

    hypotheses.sort(key=lambda r: r["Score"], reverse=True)
    return hypotheses


def _v514_evidence_table(e):
    return {
        "type": "compact_table",
        "title": f"Integrated evidence board - {e.get('well')}",
        "columns": ["Evidence", "Value", "Interpretation"],
        "rows": [
            {"Evidence": "Oil score", "Value": e.get("oil_score"), "Interpretation": _v514_score_bucket(e.get("oil_score"))},
            {"Evidence": "Water/WCT score", "Value": e.get("water_score"), "Interpretation": _v514_score_bucket(e.get("water_score"))},
            {"Evidence": "Gas/GOR score", "Value": e.get("gas_score"), "Interpretation": _v514_score_bucket(e.get("gas_score"))},
            {"Evidence": "BHP/pressure score", "Value": e.get("bhp_score"), "Interpretation": _v514_score_bucket(e.get("bhp_score"))},
            {"Evidence": "WCT bias", "Value": e.get("wct_bias"), "Interpretation": e.get("water_direction") or e.get("water_timing")},
            {"Evidence": "Pressure delta", "Value": e.get("delta_pressure"), "Interpretation": "large depletion/change" if (e.get("delta_pressure_abs") or 0) > 300 else "limited pressure change"},
            {"Evidence": "TRAN percentile", "Value": e.get("tran_percentile"), "Interpretation": "high connectivity proxy" if (e.get("tran_percentile") or 0) > 70 else "low/moderate connectivity proxy"},
            {"Evidence": "PERM percentile", "Value": e.get("perm_percentile"), "Interpretation": "high PERM proxy" if (e.get("perm_percentile") or 0) > 70 else "low/moderate PERM proxy"},
            {"Evidence": "PORO percentile", "Value": e.get("poro_percentile"), "Interpretation": "high PORO proxy" if (e.get("poro_percentile") or 0) > 70 else "low/moderate PORO proxy"},
            {"Evidence": "Delta SWAT percentile", "Value": e.get("delta_swat_percentile"), "Interpretation": "strong saturation-change evidence" if (e.get("delta_swat_percentile") or 0) > 70 else "limited/moderate saturation-change evidence"},
        ],
    }


def _v514_hypothesis_table(hypotheses):
    return {
        "type": "compact_table",
        "title": "Hypothesis ranking",
        "columns": ["Hypothesis", "Score", "Supporting evidence", "Counter evidence", "Review first"],
        "rows": hypotheses,
    }


def _v514_answer_for_well(e, hypotheses):
    top = hypotheses[0] if hypotheses else {}
    second = hypotheses[1] if len(hypotheses) > 1 else None

    msg = (
        f"For {e.get('well')}, the strongest current hypothesis is **{top.get('Hypothesis')}** "
        f"(score {top.get('Score')}). "
    )

    if second:
        msg += f"The second hypothesis is **{second.get('Hypothesis')}** (score {second.get('Score')}). "

    oil = e.get("oil_score")
    water = e.get("water_score")
    gas = e.get("gas_score")
    bhp = e.get("bhp_score")

    msg += (
        f"Evidence summary: oil score {oil}, water/WCT score {water}, gas score {gas}, BHP score {bhp}. "
        f"WCT pattern: {e.get('wct_bias')}; timing/direction: {e.get('water_timing')} / {e.get('water_direction')}. "
        "This is an integrated diagnosis, so RelPerm is treated as one possible explanation, not as the final answer by itself."
    )

    return msg


def _v514_top_review_rows(limit=5):
    wells = _v514_get_all_diag_wells()
    rows = []

    for w in wells:
        e = _v514_evidence_for_well(w)
        hypotheses = _v514_hypothesis_scores(e)

        oil_mis = e.get("oil_mismatch") or 0
        water_mis = e.get("water_mismatch") or 0
        gas_mis = e.get("gas_mismatch") or 0
        bhp_mis = e.get("bhp_mismatch") or 0

        review_score = 0.35 * water_mis + 0.30 * bhp_mis + 0.20 * gas_mis + 0.15 * oil_mis

        rows.append({
            "Well": e.get("well"),
            "Review score": round(review_score, 1),
            "Main driver": hypotheses[0]["Hypothesis"] if hypotheses else "N/A",
            "Oil score": e.get("oil_score"),
            "Water score": e.get("water_score"),
            "Gas score": e.get("gas_score"),
            "BHP score": e.get("bhp_score"),
            "WCT bias": e.get("wct_bias"),
        })

    rows.sort(key=lambda r: r["Review score"], reverse=True)
    return rows[:limit]


def _v514_execute_integrated_diagnosis(intent):
    original = intent.get("original_message") or ""
    well = intent.get("well") or _v514_extract_well(original)

    if not well:
        rows = _v514_top_review_rows(limit=5)
        return {
            "type": "visual_response",
            "intent": "integrated_parallel_diagnosis_v514",
            "answer": (
                "I ranked the top wells requiring model review using a combined mismatch score "
                "from water/WCT, BHP/pressure, gas/GOR and oil evidence. "
                "The main driver is selected from the integrated hypothesis ranking for each well."
            ),
            "ui_blocks": [
                {
                    "type": "compact_table",
                    "title": "Top wells requiring model review",
                    "columns": ["Well", "Review score", "Main driver", "Oil score", "Water score", "Gas score", "BHP score", "WCT bias"],
                    "rows": rows,
                }
            ],
            "data": {"mode": "top_review_wells", "rows": rows},
            "agent_trace": {
                "IntegratedParallelDiagnosisAgentV514": {
                    "mode": "portfolio_review",
                    "wells_ranked": len(rows),
                }
            },
        }

    w = _v514_find_well(well)

    if not w:
        return {
            "type": "reasoning_response",
            "intent": "integrated_parallel_diagnosis_v514",
            "answer": f"I understood the integrated diagnosis request for {well}, but I could not find this well in the diagnostic payload.",
            "ui_blocks": [],
            "agent_trace": {
                "IntegratedParallelDiagnosisAgentV514": {
                    "status": "well_not_found",
                    "well": well,
                }
            },
        }

    e = _v514_evidence_for_well(w)
    hypotheses = _v514_hypothesis_scores(e)

    return {
        "type": "visual_response",
        "intent": "integrated_parallel_diagnosis_v514",
        "answer": _v514_answer_for_well(e, hypotheses),
        "ui_blocks": [
            _v514_evidence_table(e),
            _v514_hypothesis_table(hypotheses),
            {
                "type": "suggestions",
                "title": "Recommended next checks",
                "items": [
                    "Check if WCT mismatch aligns spatially with TRAN/PERM corridors.",
                    "Review BHP/pressure mismatch before changing RelPerm if pressure score is weak.",
                    "If oil and gas are matched but water is poor, prioritize water RelPerm/endpoints and water connectivity.",
                    "If connectivity evidence is stronger than saturation evidence, avoid tuning RelPerm first.",
                ],
            },
        ],
        "data": {
            "well": well,
            "evidence": e,
            "hypotheses": hypotheses,
            "method": "parallel evidence board + deterministic hypothesis ranking",
        },
        "agent_trace": {
            "IntegratedParallelDiagnosisAgentV514": {
                "route": "water/gas/oil/BHP/property/connectivity/relperm evidence -> hypothesis ranking",
                "well": well,
                "top_hypothesis": hypotheses[0]["Hypothesis"] if hypotheses else None,
                "relperm_is_final_answer": False,
            },
            "ProfileAgentEvidence": {
                "oil_score": e.get("oil_score"),
                "water_score": e.get("water_score"),
                "gas_score": e.get("gas_score"),
                "bhp_score": e.get("bhp_score"),
            },
            "PropertyAgentEvidence": {
                "tran_percentile": e.get("tran_percentile"),
                "perm_percentile": e.get("perm_percentile"),
                "poro_percentile": e.get("poro_percentile"),
                "delta_swat_percentile": e.get("delta_swat_percentile"),
            },
            "RelPermAgentEvidence": {
                "status": "considered_as_hypothesis_only",
                "warning": "RelPerm cannot override integrated final diagnosis.",
            },
        },
        "interaction_edges": [
            {"from": "ProfileAgent", "to": "IntegratedParallelDiagnosisAgentV514", "reason": "oil/water/gas/BHP scores"},
            {"from": "PropertyAgent", "to": "IntegratedParallelDiagnosisAgentV514", "reason": "PERM/PORO/SWAT/TRAN evidence"},
            {"from": "RelPermAgent", "to": "IntegratedParallelDiagnosisAgentV514", "reason": "relperm hypothesis only"},
            {"from": "ReservoirCriticAgent", "to": "IntegratedParallelDiagnosisAgentV514", "reason": "avoid single-agent answer"},
        ],
    }


def execute_plan_v500(intent: Dict[str, Any], plan: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    original = intent.get("original_message") or ""

    if intent.get("integrated_parallel_diagnosis_v514") or _v514_is_integrated_diagnosis_request(original):
        return _v514_execute_integrated_diagnosis(intent)

    return _execute_plan_before_v514(intent, plan, evidence_board)

# END V514 INTEGRATED PARALLEL DIAGNOSIS AGENT


# ==========================================================
# V514C INTEGRATED DIAGNOSIS PORTFOLIO FILTERS
#
# Fixes:
# - "For HW-6, compare pressure depletion, water mismatch and gas response"
#   must be integrated diagnosis, not multi-variable plot.
# - Portfolio queries must not return only generic top-5 review table.
#
# Adds portfolio modes:
# - oil_good_water_bhp_poor
# - relperm_risky_connectivity_stronger
# - tran_more_justified_than_relperm
# - top_model_review
# ==========================================================

_interpret_request_before_v514c = interpret_request_v500
_execute_plan_before_v514c = execute_plan_v500


def _v514c_msg(message):
    return _norm_v500(message)


def _v514c_contains_any(msg, terms):
    return any(t in msg for t in terms)


def _v514c_is_integrated_request(message):
    msg = _v514c_msg(message)

    # Extra force for diagnostic compare requests.
    if "compare" in msg and _v514c_contains_any(msg, [
        "pressure depletion",
        "water mismatch",
        "gas response",
        "bhp",
        "pressure",
        "mismatch",
        "tran",
        "swat",
        "permx",
        "connectivity",
        "relperm",
    ]):
        return True

    return _v514_is_integrated_diagnosis_request(message)


def _v514c_portfolio_mode(message):
    msg = _v514c_msg(message)

    if "oil match is good" in msg and "water" in msg and "bhp" in msg:
        return "oil_good_water_bhp_poor"

    if "relperm tuning" in msg and ("risky" in msg or "risk" in msg) and "connectivity" in msg:
        return "relperm_risky_connectivity_stronger"

    if "tran correction" in msg and "relperm" in msg:
        return "tran_more_justified_than_relperm"

    if "gas match is good" in msg and ("pressure match is poor" in msg or "bhp" in msg):
        return "gas_good_pressure_poor"

    if "water mismatch and gas mismatch point to different causes" in msg:
        return "water_gas_different_causes"

    if "top 5" in msg or "requiring model review" in msg or "model review" in msg:
        return "top_model_review"

    return "top_model_review"


def interpret_request_v500(message: str) -> Dict[str, Any]:
    intent = _interpret_request_before_v514c(message)

    if _v514c_is_integrated_request(message):
        well = _v514_extract_well(message)
        mode = _v514c_portfolio_mode(message)

        intent["task_type"] = "integrated_parallel_diagnosis_v514"
        intent["well"] = well or intent.get("well")
        intent["integrated_parallel_diagnosis_v514"] = {
            "well": well or intent.get("well"),
            "portfolio_mode": mode,
            "reason": "V514C integrated diagnostic priority/portfolio filter.",
        }

        intent.setdefault("flags", {})
        intent["flags"]["integrated_diagnosis"] = True

    return intent


def _v514c_review_score(e):
    oil_mis = e.get("oil_mismatch") or 0.0
    water_mis = e.get("water_mismatch") or 0.0
    gas_mis = e.get("gas_mismatch") or 0.0
    bhp_mis = e.get("bhp_mismatch") or 0.0

    return 0.35 * water_mis + 0.30 * bhp_mis + 0.20 * gas_mis + 0.15 * oil_mis


def _v514c_best_hypothesis(e):
    hyps = _v514_hypothesis_scores(e)
    return hyps[0] if hyps else None


def _v514c_portfolio_rows(mode, limit=10):
    wells = _v514_get_all_diag_wells()
    rows = []

    for w in wells:
        e = _v514_evidence_for_well(w)
        hyp = _v514c_best_hypothesis(e)
        hyp_name = hyp.get("Hypothesis") if hyp else "N/A"
        hyp_score = hyp.get("Score") if hyp else None

        oil = e.get("oil_score")
        water = e.get("water_score")
        gas = e.get("gas_score")
        bhp = e.get("bhp_score")
        tran = e.get("tran_percentile")
        perm = e.get("perm_percentile")
        swat = e.get("delta_swat_percentile")

        water_mis = e.get("water_mismatch") or 0
        bhp_mis = e.get("bhp_mismatch") or 0
        gas_mis = e.get("gas_mismatch") or 0
        oil_mis = e.get("oil_mismatch") or 0

        review_score = _v514c_review_score(e)

        selected = False
        why = ""
        recommendation = ""

        if mode == "oil_good_water_bhp_poor":
            selected = (oil is not None and oil >= 90 and water is not None and water < 70 and bhp is not None and bhp < 75)
            why = "Oil match good, but water/WCT and BHP are weak."
            recommendation = "Review water movement and pressure/connectivity before tuning phase behaviour."

        elif mode == "relperm_risky_connectivity_stronger":
            # RelPerm risky when water is bad but BHP/connectivity evidence is also material.
            selected = (
                water is not None and water < 70
                and (
                    (bhp is not None and bhp < 75)
                    or (tran is not None and (tran < 35 or tran > 75))
                    or hyp_name == "Connectivity / TRAN issue"
                )
            )
            why = "Connectivity/BHP evidence is material; RelPerm-only tuning may hide structural/connectivity errors."
            recommendation = "Run TRAN/connectivity sensitivity first or in parallel; do not use RelPerm-only as first correction."

        elif mode == "tran_more_justified_than_relperm":
            selected = (
                hyp_name == "Connectivity / TRAN issue"
                or (
                    water is not None and water < 70
                    and bhp is not None and bhp < 75
                    and tran is not None and (tran < 35 or tran > 75)
                )
            )
            why = "Mismatch is better supported by connectivity/pressure evidence than by pure phase behaviour."
            recommendation = "Prioritize TRAN corridor / connectivity check before RelPerm."

        elif mode == "gas_good_pressure_poor":
            selected = (gas is not None and gas >= 90 and bhp is not None and bhp < 75)
            why = "Gas match is good but BHP/pressure match is weak."
            recommendation = "Pressure support, boundary/aquifer or transmissibility issue is more likely than gas PVT/mobility."

        elif mode == "water_gas_different_causes":
            selected = (water is not None and water < 70 and gas is not None and gas >= 90)
            why = "Water mismatch is poor while gas match is good, suggesting water-specific mechanism."
            recommendation = "Investigate water connectivity, water relperm/endpoints, SWAT/aquifer support; gas is not the main driver."

        else:
            selected = True
            why = "High combined review score from phase and pressure mismatches."
            recommendation = "Start from the top hypothesis but verify counter-evidence before editing the model."

        if selected:
            rows.append({
                "Well": e.get("well"),
                "Review score": round(review_score, 1),
                "Main driver": hyp_name,
                "Driver score": hyp_score,
                "Oil": oil,
                "Water": water,
                "Gas": gas,
                "BHP": bhp,
                "TRAN pct": tran,
                "PERM pct": perm,
                "SWAT Δ pct": swat,
                "WCT bias": e.get("wct_bias"),
                "Why selected": why,
                "Recommendation": recommendation,
            })

    rows.sort(key=lambda r: r["Review score"], reverse=True)
    return rows[:limit]


def _v514c_portfolio_title(mode):
    return {
        "oil_good_water_bhp_poor": "Wells with good oil match but poor water/BHP match",
        "relperm_risky_connectivity_stronger": "Wells where RelPerm-only tuning is risky",
        "tran_more_justified_than_relperm": "Wells where TRAN/connectivity correction is more justified",
        "gas_good_pressure_poor": "Wells with good gas match but poor pressure match",
        "water_gas_different_causes": "Wells where water and gas mismatch point to different causes",
        "top_model_review": "Top wells requiring model review",
    }.get(mode, "Integrated diagnosis portfolio")


def _v514c_portfolio_answer(mode, n):
    if mode == "oil_good_water_bhp_poor":
        return f"I found {n} wells where oil match is good but water/WCT and BHP are weaker. These are likely not oil-volumetric problems; review water movement and pressure/connectivity evidence first."

    if mode == "relperm_risky_connectivity_stronger":
        return f"I found {n} wells where RelPerm-only tuning may be risky because connectivity, TRAN or BHP evidence is material. These wells should be checked with TRAN/connectivity sensitivities before applying RelPerm-only edits."

    if mode == "tran_more_justified_than_relperm":
        return f"I found {n} wells where TRAN/connectivity correction is more justified than RelPerm-only correction based on the current hypothesis ranking and connectivity/pressure evidence."

    if mode == "gas_good_pressure_poor":
        return f"I found {n} wells where gas match is good but pressure/BHP is weak. This points more toward pressure support/connectivity/boundary issues than gas mobility alone."

    if mode == "water_gas_different_causes":
        return f"I found {n} wells where water mismatch is poor while gas match is good. This suggests water-specific causes rather than a general phase/PVT mismatch."

    return f"I ranked the top {n} wells requiring model review using integrated water/WCT, BHP/pressure, gas/GOR and oil evidence."


def _v514c_execute_portfolio(mode):
    limit = 5 if mode == "top_model_review" else 10
    rows = _v514c_portfolio_rows(mode, limit=limit)

    return {
        "type": "visual_response",
        "intent": "integrated_parallel_diagnosis_v514",
        "answer": _v514c_portfolio_answer(mode, len(rows)),
        "ui_blocks": [
            {
                "type": "compact_table",
                "title": _v514c_portfolio_title(mode),
                "columns": [
                    "Well", "Review score", "Main driver", "Driver score",
                    "Oil", "Water", "Gas", "BHP",
                    "TRAN pct", "PERM pct", "SWAT Δ pct",
                    "WCT bias", "Why selected", "Recommendation"
                ],
                "rows": rows,
            }
        ],
        "data": {
            "mode": mode,
            "rows": rows,
            "method": "V514C filtered integrated diagnosis portfolio",
        },
        "agent_trace": {
            "IntegratedParallelDiagnosisAgentV514C": {
                "mode": mode,
                "rows": len(rows),
                "route": "portfolio filter -> integrated hypothesis ranking",
            }
        },
    }


def _v514c_execute_integrated_diagnosis(intent):
    original = intent.get("original_message") or ""
    well = intent.get("well") or _v514_extract_well(original)
    mode = (intent.get("integrated_parallel_diagnosis_v514") or {}).get("portfolio_mode") or _v514c_portfolio_mode(original)

    if not well:
        return _v514c_execute_portfolio(mode)

    # Well-specific requests use the existing V514 evidence board/hypothesis response.
    return _v514_execute_integrated_diagnosis(intent)


def execute_plan_v500(intent: Dict[str, Any], plan: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    original = intent.get("original_message") or ""

    if intent.get("integrated_parallel_diagnosis_v514") or _v514c_is_integrated_request(original):
        return _v514c_execute_integrated_diagnosis(intent)

    return _execute_plan_before_v514c(intent, plan, evidence_board)

# END V514C INTEGRATED DIAGNOSIS PORTFOLIO FILTERS


# ==========================================================
# V515 COMMUNICATION / STREAMLINE / CONNECTIVITY AGENT
#
# Supports:
# - Which wells communicate most strongly with HW-28?
# - Show streamlines connected to HW-25
# - Show flow paths between high water mismatch wells
# - Is HW-28 isolated or connected to the main flow corridor?
# - Show wells with high connectivity but poor water match
# - Show wells with low connectivity and poor pressure match
# - Rank wells by connectivity proxy
# - Correlate connectivity with water mismatch
# - Correlate connectivity with gas mismatch
#
# Important:
# If true streamline arrays are not exposed, this agent uses a transparent
# connectivity proxy based on TRAN/PERM/PORO, spatial distance and dynamic
# diagnostic similarity. It does not pretend to be a true streamline simulator.
# ==========================================================

_interpret_request_before_v515 = interpret_request_v500
_execute_plan_before_v515 = execute_plan_v500


def _v515_msg(message):
    return _norm_v500(message)


def _v515_contains_any(msg, terms):
    return any(t in msg for t in terms)


def _v515_extract_well(message):
    try:
        return _v514_extract_well(message)
    except Exception:
        import re
        m = re.search(r"\bHW[-\s]?(\d+)\b", str(message or ""), flags=re.IGNORECASE)
        return f"HW-{int(m.group(1))}" if m else None


def _v515_is_request(message):
    msg = _v515_msg(message)

    connectivity_terms = [
        "communicate", "communication", "connected", "connectivity",
        "streamline", "streamlines", "flow path", "flow paths",
        "main flow corridor", "flow corridor", "isolated",
        "connectivity proxy", "most connected", "least connected",
        "low connectivity", "high connectivity",
        "tran corridor", "tran correction",
    ]

    diagnostic_terms = [
        "water mismatch", "gas mismatch", "pressure match", "pressure mismatch",
        "poor water", "poor pressure", "bhp", "wct", "rank", "correlate",
        "which wells", "show wells", "around", "connected to"
    ]

    return _v515_contains_any(msg, connectivity_terms) and (
        _v515_contains_any(msg, diagnostic_terms)
        or _v515_extract_well(message) is not None
    )


def _v515_kind(message):
    msg = _v515_msg(message)

    if "correlate" in msg or "correlation" in msg or " vs " in msg or "versus" in msg:
        return "correlation"

    if "flow path" in msg or "flow paths" in msg or "streamline" in msg or "streamlines" in msg:
        return "flow_paths"

    if "isolated" in msg or "main flow corridor" in msg:
        return "isolation"

    if "high connectivity" in msg and ("poor water" in msg or "water mismatch" in msg):
        return "high_connectivity_poor_water"

    if "low connectivity" in msg and ("poor pressure" in msg or "pressure match" in msg or "bhp" in msg):
        return "low_connectivity_poor_pressure"

    if "least connected" in msg:
        return "ranking_low"

    if "rank" in msg or "most connected" in msg or "connectivity proxy" in msg:
        return "ranking_high"

    if _v515_extract_well(message):
        return "well_communication"

    return "ranking_high"


def interpret_request_v500(message: str) -> Dict[str, Any]:
    intent = _interpret_request_before_v515(message)

    if _v515_is_request(message):
        well = _v515_extract_well(message)
        kind = _v515_kind(message)

        intent["task_type"] = "communication_connectivity_v515"
        intent["well"] = well or intent.get("well")
        intent["communication_connectivity_v515"] = {
            "well": well or intent.get("well"),
            "kind": kind,
            "reason": "Connectivity/communication/streamline request detected.",
        }

        intent.setdefault("flags", {})
        intent["flags"]["connectivity_analysis"] = True

    return intent


def _v515_sf(x, default=None):
    v = _safe_float_v500(x)
    return default if v is None else v


def _v515_rows():
    wells = []

    try:
        raw = _v514_get_all_diag_wells()
    except Exception:
        raw = []

    seen = set()

    for w in raw:
        if not isinstance(w, dict):
            continue

        name = w.get("well")
        if not name or name in seen:
            continue

        seen.add(name)
        e = _v514_evidence_for_well(w)

        tran = _v515_sf(e.get("tran_percentile"))
        perm = _v515_sf(e.get("perm_percentile"))
        poro = _v515_sf(e.get("poro_percentile"))

        vals = [v for v in [tran, perm, poro] if v is not None]
        proxy = sum(vals) / len(vals) if vals else None

        water_score = _v515_sf(e.get("water_score"))
        gas_score = _v515_sf(e.get("gas_score"))
        bhp_score = _v515_sf(e.get("bhp_score"))

        wells.append({
            "well": e.get("well"),
            "i": _v515_sf(e.get("i")),
            "j": _v515_sf(e.get("j")),
            "connectivity_proxy": proxy,
            "tran_percentile": tran,
            "perm_percentile": perm,
            "poro_percentile": poro,
            "water_score": water_score,
            "gas_score": gas_score,
            "bhp_score": bhp_score,
            "water_mismatch": max(0.0, 100.0 - water_score) if water_score is not None else None,
            "gas_mismatch": max(0.0, 100.0 - gas_score) if gas_score is not None else None,
            "bhp_mismatch": max(0.0, 100.0 - bhp_score) if bhp_score is not None else None,
            "delta_pressure_abs": e.get("delta_pressure_abs"),
            "wct_bias": e.get("wct_bias"),
        })

    return wells


def _v515_distance(a, b):
    ai, aj = a.get("i"), a.get("j")
    bi, bj = b.get("i"), b.get("j")

    if ai is None or aj is None or bi is None or bj is None:
        return None

    return ((ai - bi) ** 2 + (aj - bj) ** 2) ** 0.5


def _v515_distance_score(dist, max_dist):
    if dist is None or max_dist is None or max_dist <= 0:
        return 50.0

    return max(0.0, 100.0 * (1.0 - dist / max_dist))


def _v515_similarity_score(a, b):
    # Dynamic similarity: similar pressure depletion and similar water mismatch.
    score = 0.0
    weight = 0.0

    for key, w in [
        ("delta_pressure_abs", 0.45),
        ("water_mismatch", 0.35),
        ("gas_mismatch", 0.20),
    ]:
        av = a.get(key)
        bv = b.get(key)

        if av is None or bv is None:
            continue

        scale = max(abs(av), abs(bv), 1.0)
        s = max(0.0, 100.0 * (1.0 - abs(av - bv) / scale))
        score += w * s
        weight += w

    return score / weight if weight > 0 else 50.0


def _v515_pair_score(target, other, max_dist):
    target_proxy = target.get("connectivity_proxy")
    other_proxy = other.get("connectivity_proxy")

    proxy_vals = [v for v in [target_proxy, other_proxy] if v is not None]
    proxy_component = sum(proxy_vals) / len(proxy_vals) if proxy_vals else 50.0

    dist = _v515_distance(target, other)
    dist_component = _v515_distance_score(dist, max_dist)
    sim_component = _v515_similarity_score(target, other)

    pair = 0.50 * proxy_component + 0.30 * dist_component + 0.20 * sim_component

    return pair, dist, proxy_component, dist_component, sim_component


def _v515_find_row(well):
    for r in _v515_rows():
        if str(r.get("well", "")).upper() == str(well or "").upper():
            return r
    return None


def _v515_max_distance(rows):
    max_d = 0.0

    for a in rows:
        for b in rows:
            d = _v515_distance(a, b)
            if d is not None:
                max_d = max(max_d, d)

    return max_d or 1.0


def _v515_ranking_rows(reverse=True):
    rows = _v515_rows()

    out = []

    for r in rows:
        proxy = r.get("connectivity_proxy")
        out.append({
            "Well": r.get("well"),
            "Connectivity proxy": round(proxy, 1) if proxy is not None else None,
            "TRAN pct": round(r.get("tran_percentile"), 1) if r.get("tran_percentile") is not None else None,
            "PERM pct": round(r.get("perm_percentile"), 1) if r.get("perm_percentile") is not None else None,
            "PORO pct": round(r.get("poro_percentile"), 1) if r.get("poro_percentile") is not None else None,
            "Water mismatch": round(r.get("water_mismatch"), 1) if r.get("water_mismatch") is not None else None,
            "BHP mismatch": round(r.get("bhp_mismatch"), 1) if r.get("bhp_mismatch") is not None else None,
            "WCT bias": r.get("wct_bias"),
        })

    out.sort(key=lambda x: -999 if x["Connectivity proxy"] is None else x["Connectivity proxy"], reverse=reverse)
    return out


def _v515_map_block(rows, title, color_key="connectivity_proxy", line_pairs=None):
    plot_rows = [r for r in rows if r.get("i") is not None and r.get("j") is not None]

    data = []

    if line_pairs:
        lx, ly = [], []
        for a, b in line_pairs:
            if a.get("i") is None or a.get("j") is None or b.get("i") is None or b.get("j") is None:
                continue
            lx += [a.get("i"), b.get("i"), None]
            ly += [a.get("j"), b.get("j"), None]

        data.append({
            "type": "scatter",
            "mode": "lines",
            "name": "Proxy communication links",
            "x": lx,
            "y": ly,
            "line": {"width": 2},
            "hoverinfo": "skip",
        })

    data.append({
        "type": "scatter",
        "mode": "markers+text",
        "name": "Wells",
        "x": [r.get("i") for r in plot_rows],
        "y": [r.get("j") for r in plot_rows],
        "text": [r.get("well") for r in plot_rows],
        "customdata": [
            [
                r.get("well"),
                round(r.get("connectivity_proxy"), 2) if r.get("connectivity_proxy") is not None else None,
                round(r.get("water_mismatch"), 2) if r.get("water_mismatch") is not None else None,
                round(r.get("bhp_mismatch"), 2) if r.get("bhp_mismatch") is not None else None,
                r.get("wct_bias"),
            ]
            for r in plot_rows
        ],
        "textposition": "top center",
        "marker": {
            "size": [max(10, min(24, 8 + (r.get(color_key) or 0) / 5.0)) for r in plot_rows],
            "color": [r.get(color_key) or 0 for r in plot_rows],
            "colorscale": "Viridis",
            "showscale": True,
            "colorbar": {"title": color_key},
        },
        "hovertemplate": (
            "Well: %{customdata[0]}<br>"
            "Connectivity proxy: %{customdata[1]}<br>"
            "Water mismatch: %{customdata[2]}<br>"
            "BHP mismatch: %{customdata[3]}<br>"
            "WCT bias: %{customdata[4]}<extra></extra>"
        ),
    })

    return {
        "type": "plotly_chart",
        "title": title,
        "data": data,
        "layout": {
            "title": title,
            "xaxis": {"title": "I index", "showgrid": False},
            "yaxis": {"title": "J index", "showgrid": False},
            "height": 560,
            "hovermode": "closest",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "paper_bgcolor": "rgba(0,0,0,0)",
            "margin": {"l": 70, "r": 50, "t": 60, "b": 70},
        },
        "config": {"responsive": True, "displaylogo": False, "scrollZoom": True},
    }


def _v515_communication_for_well(well):
    rows = _v515_rows()
    target = _v515_find_row(well)

    if not target:
        return {
            "type": "reasoning_response",
            "intent": "communication_connectivity_v515",
            "answer": f"I understood the communication/connectivity request, but I could not find {well} in the diagnostic well payload.",
            "ui_blocks": [],
            "agent_trace": {"CommunicationConnectivityAgentV515": {"status": "well_not_found", "well": well}},
        }

    max_dist = _v515_max_distance(rows)
    scored = []

    for r in rows:
        if r.get("well") == target.get("well"):
            continue

        pair, dist, proxy_component, dist_component, sim_component = _v515_pair_score(target, r, max_dist)

        scored.append({
            "row": r,
            "Well": r.get("well"),
            "Communication proxy": round(pair, 1),
            "Distance": round(dist, 1) if dist is not None else None,
            "Connectivity component": round(proxy_component, 1),
            "Distance component": round(dist_component, 1),
            "Dynamic similarity": round(sim_component, 1),
            "Water mismatch": round(r.get("water_mismatch"), 1) if r.get("water_mismatch") is not None else None,
            "BHP mismatch": round(r.get("bhp_mismatch"), 1) if r.get("bhp_mismatch") is not None else None,
        })

    scored.sort(key=lambda x: x["Communication proxy"], reverse=True)
    top = scored[:8]

    linked_rows = [target] + [x["row"] for x in top]
    line_pairs = [(target, x["row"]) for x in top[:5]]

    return {
        "type": "visual_response",
        "intent": "communication_connectivity_v515",
        "answer": (
            f"I ranked wells that may communicate most strongly with {well} using a transparent proxy. "
            "This is not a true streamline allocation unless raw streamline arrays are exposed; it combines TRAN/PERM/PORO connectivity proxy, I/J proximity and dynamic response similarity."
        ),
        "ui_blocks": [
            _v515_map_block(linked_rows, f"Proxy communication map around {well}", color_key="connectivity_proxy", line_pairs=line_pairs),
            {
                "type": "compact_table",
                "title": f"Strongest proxy communication links for {well}",
                "columns": ["Well", "Communication proxy", "Distance", "Connectivity component", "Distance component", "Dynamic similarity", "Water mismatch", "BHP mismatch"],
                "rows": [{k: v for k, v in x.items() if k != "row"} for x in top],
            },
            {
                "type": "suggestions",
                "title": "How to validate",
                "items": [
                    "Check true streamline allocation if available.",
                    "Compare pressure response during rate changes or shut-ins.",
                    "Review TRAN corridors and local permeability between linked wells.",
                    "Use this proxy as screening, not as final proof of communication.",
                ],
            },
        ],
        "data": {
            "well": well,
            "method": "TRAN/PERM/PORO + distance + dynamic similarity proxy",
            "links": [{k: v for k, v in x.items() if k != "row"} for x in top],
        },
        "agent_trace": {
            "CommunicationConnectivityAgentV515": {
                "mode": "well_communication",
                "well": well,
                "links_ranked": len(scored),
                "true_streamlines_available": False,
            }
        },
    }


def _v515_flow_paths_between_high_water_mismatch():
    rows = _v515_rows()
    max_dist = _v515_max_distance(rows)

    high = [r for r in rows if (r.get("water_mismatch") or 0) >= 30]
    high.sort(key=lambda r: r.get("water_mismatch") or 0, reverse=True)
    high = high[:10]

    pairs = []

    for i, a in enumerate(high):
        for b in high[i+1:]:
            pair, dist, proxy_component, dist_component, sim_component = _v515_pair_score(a, b, max_dist)
            pairs.append({
                "a": a,
                "b": b,
                "Well A": a.get("well"),
                "Well B": b.get("well"),
                "Path proxy": round(pair, 1),
                "Distance": round(dist, 1) if dist is not None else None,
                "Connectivity component": round(proxy_component, 1),
                "Dynamic similarity": round(sim_component, 1),
                "Water mismatch A": round(a.get("water_mismatch"), 1) if a.get("water_mismatch") is not None else None,
                "Water mismatch B": round(b.get("water_mismatch"), 1) if b.get("water_mismatch") is not None else None,
            })

    pairs.sort(key=lambda p: p["Path proxy"], reverse=True)
    top_pairs = pairs[:8]

    line_pairs = [(p["a"], p["b"]) for p in top_pairs[:6]]

    table_rows = []
    for p in top_pairs:
        table_rows.append({k: v for k, v in p.items() if k not in {"a", "b"}})

    return {
        "type": "visual_response",
        "intent": "communication_connectivity_v515",
        "answer": (
            "I identified proxy flow paths among wells with high water mismatch. "
            "These are screening links based on connectivity proxy, spatial proximity and dynamic similarity, not true streamline allocations."
        ),
        "ui_blocks": [
            _v515_map_block(high, "Proxy flow paths between high water-mismatch wells", color_key="water_mismatch", line_pairs=line_pairs),
            {
                "type": "compact_table",
                "title": "High water-mismatch proxy flow-path links",
                "columns": ["Well A", "Well B", "Path proxy", "Distance", "Connectivity component", "Dynamic similarity", "Water mismatch A", "Water mismatch B"],
                "rows": table_rows,
            },
        ],
        "data": {"method": "screening flow-path proxy", "pairs": table_rows},
        "agent_trace": {
            "CommunicationConnectivityAgentV515": {
                "mode": "flow_paths_high_water_mismatch",
                "pairs": len(table_rows),
                "true_streamlines_available": False,
            }
        },
    }


def _v515_isolation_for_well(well):
    base = _v515_communication_for_well(well)

    if base.get("type") != "visual_response":
        return base

    links = base.get("data", {}).get("links", [])
    target = _v515_find_row(well)

    top_score = links[0]["Communication proxy"] if links else None
    proxy = target.get("connectivity_proxy") if target else None

    if top_score is None:
        status = "unknown"
        explanation = "not enough proxy links available"
    elif top_score >= 70 and (proxy or 0) >= 50:
        status = "connected to main corridor"
        explanation = "high communication proxy and moderate/high connectivity proxy"
    elif top_score >= 55:
        status = "partially connected"
        explanation = "moderate communication proxy; verify with true streamlines or pressure response"
    else:
        status = "relatively isolated"
        explanation = "low communication proxy to nearby/connected candidates"

    base["answer"] = (
        f"{well} appears **{status}** based on the current connectivity proxy. "
        f"Reason: {explanation}. This is a screening diagnosis, not a replacement for true streamline allocation."
    )

    base.setdefault("data", {})
    base["data"]["isolation_status"] = status
    base["data"]["isolation_explanation"] = explanation

    base.setdefault("agent_trace", {})
    base["agent_trace"]["IsolationAssessmentV515"] = {
        "well": well,
        "status": status,
        "top_communication_proxy": top_score,
        "connectivity_proxy": proxy,
    }

    return base


def _v515_filtered_connectivity_response(kind):
    rows = _v515_rows()

    out = []

    for r in rows:
        proxy = r.get("connectivity_proxy") or 0
        water_mis = r.get("water_mismatch") or 0
        bhp_mis = r.get("bhp_mismatch") or 0

        selected = False
        recommendation = ""

        if kind == "high_connectivity_poor_water":
            selected = proxy >= 60 and water_mis >= 30
            recommendation = "Connectivity is already high; check water relperm/endpoints, saturation initialization or water source timing before simply increasing TRAN."

        elif kind == "low_connectivity_poor_pressure":
            selected = proxy < 50 and bhp_mis >= 25
            recommendation = "Low connectivity plus weak pressure match supports TRAN/connectivity/boundary review."

        if selected:
            out.append({
                "Well": r.get("well"),
                "Connectivity proxy": round(proxy, 1),
                "TRAN pct": round(r.get("tran_percentile"), 1) if r.get("tran_percentile") is not None else None,
                "PERM pct": round(r.get("perm_percentile"), 1) if r.get("perm_percentile") is not None else None,
                "Water mismatch": round(water_mis, 1),
                "BHP mismatch": round(bhp_mis, 1),
                "WCT bias": r.get("wct_bias"),
                "Recommendation": recommendation,
            })

    out.sort(key=lambda x: x["Connectivity proxy"], reverse=(kind == "high_connectivity_poor_water"))

    title = "High connectivity but poor water match" if kind == "high_connectivity_poor_water" else "Low connectivity and poor pressure match"

    return {
        "type": "visual_response",
        "intent": "communication_connectivity_v515",
        "answer": f"I found {len(out)} wells for: {title}.",
        "ui_blocks": [
            _v515_map_block(rows, title, color_key="connectivity_proxy"),
            {
                "type": "compact_table",
                "title": title,
                "columns": ["Well", "Connectivity proxy", "TRAN pct", "PERM pct", "Water mismatch", "BHP mismatch", "WCT bias", "Recommendation"],
                "rows": out,
            },
        ],
        "data": {"mode": kind, "rows": out},
        "agent_trace": {
            "CommunicationConnectivityAgentV515": {
                "mode": kind,
                "rows": len(out),
            }
        },
    }


def _v515_ranking_response(kind):
    reverse = kind != "ranking_low"
    rows = _v515_ranking_rows(reverse=reverse)
    title = "Connectivity proxy ranking" if reverse else "Least connected wells by proxy"

    return {
        "type": "visual_response",
        "intent": "communication_connectivity_v515",
        "answer": (
            "I ranked wells using a transparent connectivity proxy from TRAN, permeability and porosity percentiles. "
            "This is a screening metric; true streamlines should override it when available."
        ),
        "ui_blocks": [
            _v515_map_block(_v515_rows(), title, color_key="connectivity_proxy"),
            {
                "type": "compact_table",
                "title": title,
                "columns": ["Well", "Connectivity proxy", "TRAN pct", "PERM pct", "PORO pct", "Water mismatch", "BHP mismatch", "WCT bias"],
                "rows": rows[:15],
            },
        ],
        "data": {"mode": kind, "rows": rows[:15]},
        "agent_trace": {
            "CommunicationConnectivityAgentV515": {
                "mode": kind,
                "rows": len(rows),
            }
        },
    }


def _v515_correlation_response(message):
    msg = _v515_msg(message)
    rows = _v515_rows()

    if "gas" in msg:
        y_key = "gas_mismatch"
        y_label = "Gas mismatch"
    elif "pressure" in msg or "bhp" in msg:
        y_key = "bhp_mismatch"
        y_label = "BHP / pressure mismatch"
    else:
        y_key = "water_mismatch"
        y_label = "Water/WCT mismatch"

    points = [r for r in rows if r.get("connectivity_proxy") is not None and r.get(y_key) is not None]

    xs = [r["connectivity_proxy"] for r in points]
    ys = [r[y_key] for r in points]

    corr = None
    try:
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        sx = (sum((x - mx) ** 2 for x in xs) / max(1, len(xs) - 1)) ** 0.5
        sy = (sum((y - my) ** 2 for y in ys) / max(1, len(ys) - 1)) ** 0.5
        if sx > 0 and sy > 0:
            corr = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / max(1, len(xs) - 1) / sx / sy
    except Exception:
        corr = None

    title = f"Connectivity proxy vs {y_label}"

    table_rows = []
    for r in sorted(points, key=lambda x: x.get(y_key) or 0, reverse=True):
        table_rows.append({
            "Well": r.get("well"),
            "Connectivity proxy": round(r.get("connectivity_proxy"), 1),
            y_label: round(r.get(y_key), 1),
            "TRAN pct": round(r.get("tran_percentile"), 1) if r.get("tran_percentile") is not None else None,
            "WCT bias": r.get("wct_bias"),
        })

    return {
        "type": "visual_response",
        "intent": "communication_connectivity_v515",
        "answer": (
            f"I cross-plotted connectivity proxy against {y_label}. "
            f"Correlation coefficient: {corr:.3f}." if corr is not None else
            f"I cross-plotted connectivity proxy against {y_label}. Correlation could not be computed robustly."
        ),
        "ui_blocks": [
            {
                "type": "plotly_chart",
                "title": title,
                "data": [
                    {
                        "type": "scatter",
                        "mode": "markers+text",
                        "name": "Wells",
                        "x": xs,
                        "y": ys,
                        "text": [r.get("well") for r in points],
                        "textposition": "top center",
                        "customdata": [[r.get("well"), round(r.get("connectivity_proxy"), 1), round(r.get(y_key), 1)] for r in points],
                        "marker": {"size": 13},
                        "hovertemplate": "Well: %{customdata[0]}<br>Connectivity: %{customdata[1]}<br>Mismatch: %{customdata[2]}<extra></extra>",
                    }
                ],
                "layout": {
                    "title": title,
                    "xaxis": {"title": "Connectivity proxy", "showgrid": False},
                    "yaxis": {"title": y_label, "showgrid": False},
                    "height": 560,
                    "plot_bgcolor": "rgba(0,0,0,0)",
                    "paper_bgcolor": "rgba(0,0,0,0)",
                },
                "config": {"responsive": True, "displaylogo": False, "scrollZoom": True},
            },
            {
                "type": "compact_table",
                "title": title + " evidence",
                "columns": ["Well", "Connectivity proxy", y_label, "TRAN pct", "WCT bias"],
                "rows": table_rows,
            },
        ],
        "data": {"mode": "correlation", "y_key": y_key, "points": len(points), "correlation": corr},
        "agent_trace": {
            "CommunicationConnectivityAgentV515": {
                "mode": "correlation",
                "y_key": y_key,
                "points": len(points),
                "correlation": corr,
            }
        },
    }


def _v515_execute(intent):
    original = intent.get("original_message") or ""
    cfg = intent.get("communication_connectivity_v515") or {}

    kind = cfg.get("kind") or _v515_kind(original)
    well = cfg.get("well") or intent.get("well") or _v515_extract_well(original)

    if kind == "well_communication" and well:
        return _v515_communication_for_well(well)

    if kind == "flow_paths":
        if well:
            return _v515_communication_for_well(well)
        return _v515_flow_paths_between_high_water_mismatch()

    if kind == "isolation" and well:
        return _v515_isolation_for_well(well)

    if kind in {"high_connectivity_poor_water", "low_connectivity_poor_pressure"}:
        return _v515_filtered_connectivity_response(kind)

    if kind in {"ranking_high", "ranking_low"}:
        return _v515_ranking_response(kind)

    if kind == "correlation":
        return _v515_correlation_response(original)

    if well:
        return _v515_communication_for_well(well)

    return _v515_ranking_response("ranking_high")


def execute_plan_v500(intent: Dict[str, Any], plan: Dict[str, Any], evidence_board: Dict[str, Any]) -> Dict[str, Any]:
    original = intent.get("original_message") or ""

    if intent.get("communication_connectivity_v515") or _v515_is_request(original):
        return _v515_execute(intent)

    return _execute_plan_before_v515(intent, plan, evidence_board)

# END V515 COMMUNICATION / STREAMLINE / CONNECTIVITY AGENT


# ==========================================================
# V525 PROFILE EVIDENCE OVERRIDE + EXECUTIVE HM SUMMARY
#
# Problem:
# Some WCT diagnostic labels/directions can conflict with actual profile
# evidence. Example: HW-25 diagnostic label says late/unknown, but numeric
# sim_wct/obs_wct and water profile evidence show simulated water is too high.
#
# Rule:
# Actual profile arrays and explicit sim_wct/obs_wct numeric evidence override
# generic WCT bias labels when direction/timing are inconsistent or unknown.
# ==========================================================

try:
    _v514_evidence_for_well_before_v525 = _v514_evidence_for_well
except Exception:
    _v514_evidence_for_well_before_v525 = None

try:
    _v514_answer_for_well_before_v525 = _v514_answer_for_well
except Exception:
    _v514_answer_for_well_before_v525 = None


def _v525_safe_float(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        try:
            return _safe_float_v500(x)
        except Exception:
            return None


def _v525_numeric_list(vals):
    out = []
    for v in vals or []:
        f = _v525_safe_float(v)
        if f is not None:
            out.append(f)
    return out


def _v525_profile_data(well, variable):
    try:
        return _v510_get_profile_data(well, variable)
    except Exception:
        return None


def _v525_first_active_index(vals, eps=1e-9):
    for i, v in enumerate(vals or []):
        try:
            if abs(float(v)) > eps:
                return i
        except Exception:
            pass
    return None


def _v525_water_profile_evidence(well):
    """
    Returns a robust water evidence override from actual profiles when available.
    Uses:
    - water simulated/observed arrays
    - sim_wct / obs_wct from diagnostic payload if present
    """
    evidence = {
        "available": False,
        "source": [],
        "direction": None,
        "timing": None,
        "sim_total": None,
        "obs_total": None,
        "ratio": None,
        "delta": None,
        "first_sim_active_index": None,
        "first_obs_active_index": None,
        "notes": [],
    }

    if not well:
        return evidence

    data = _v525_profile_data(well, "water")

    if isinstance(data, dict):
        sim = _v525_numeric_list(data.get("simulated") or data.get("sim") or data.get("simulation") or [])
        obs = _v525_numeric_list(data.get("observed") or data.get("obs") or data.get("history") or [])

        if sim or obs:
            evidence["available"] = True
            evidence["source"].append("water_profile_arrays")

            sim_total = sum(sim) if sim else 0.0
            obs_total = sum(obs) if obs else 0.0

            evidence["sim_total"] = sim_total
            evidence["obs_total"] = obs_total
            evidence["delta"] = sim_total - obs_total
            evidence["ratio"] = sim_total / obs_total if abs(obs_total) > 1e-12 else None

            fs = _v525_first_active_index(sim)
            fo = _v525_first_active_index(obs)

            evidence["first_sim_active_index"] = fs
            evidence["first_obs_active_index"] = fo

            # Direction by magnitude.
            denom = max(abs(obs_total), abs(sim_total), 1.0)
            rel_delta = (sim_total - obs_total) / denom

            if rel_delta > 0.20:
                evidence["direction"] = "simulated water too high"
            elif rel_delta < -0.20:
                evidence["direction"] = "simulated water too low"
            else:
                evidence["direction"] = "water magnitude close"

            # Timing.
            if fs is None and fo is None:
                evidence["timing"] = "no water active in either profile"
            elif fs is None and fo is not None:
                evidence["timing"] = "simulation has no water while observed is active"
            elif fs is not None and fo is None:
                evidence["timing"] = "simulation has water but observed has no active water"
            elif fs == fo:
                if fs == 0:
                    evidence["timing"] = "both active from start"
                else:
                    evidence["timing"] = "breakthrough timing close"
            elif fs < fo:
                evidence["timing"] = "early simulated water response"
            else:
                evidence["timing"] = "late simulated water response"

    return evidence


def _v525_apply_wct_numeric_override(e, raw_well_dict=None):
    """
    Use explicit sim_wct / obs_wct fields if available.
    """
    raw = raw_well_dict or {}

    sim_wct = _v525_safe_float(raw.get("sim_wct") if isinstance(raw, dict) else None)
    obs_wct = _v525_safe_float(raw.get("obs_wct") if isinstance(raw, dict) else None)

    if sim_wct is None or obs_wct is None:
        return e

    e["sim_wct"] = sim_wct
    e["obs_wct"] = obs_wct

    denom = max(abs(sim_wct), abs(obs_wct), 1.0)
    rel_delta = (sim_wct - obs_wct) / denom

    if rel_delta > 0.20:
        numeric_direction = "simulated WCT too high"
    elif rel_delta < -0.20:
        numeric_direction = "simulated WCT too low"
    else:
        numeric_direction = "WCT final value close"

    e["wct_numeric_direction_v525"] = numeric_direction
    e["water_profile_override_v525"] = e.get("water_profile_override_v525") or {}

    e["water_profile_override_v525"]["wct_numeric_direction"] = numeric_direction
    e["water_profile_override_v525"]["sim_wct"] = sim_wct
    e["water_profile_override_v525"]["obs_wct"] = obs_wct

    # Override only when original direction is unknown/contradictory or numeric evidence is strong.
    old_dir = str(e.get("water_direction") or "").lower()
    old_bias = str(e.get("wct_bias") or "").lower()

    strong_numeric = abs(rel_delta) > 0.35
    unknown_or_conflicting = (
        not old_dir
        or "unknown" in old_dir
        or ("underestimates" in old_bias and "too high" in numeric_direction)
        or ("overestimates" in old_bias and "too low" in numeric_direction)
    )

    if strong_numeric or unknown_or_conflicting:
        e["water_direction_original_v525"] = e.get("water_direction")
        e["wct_bias_original_v525"] = e.get("wct_bias")
        e["water_direction"] = numeric_direction
        e["water_direction_source_v525"] = "sim_wct_obs_wct_numeric_override"
        e["water_profile_override_v525"]["override_applied"] = True
        e["water_profile_override_v525"]["override_reason"] = "sim_wct/obs_wct numeric evidence overrides generic WCT diagnostic label"

    return e


def _v525_apply_profile_override(e):
    well = e.get("well")

    prof = _v525_water_profile_evidence(well)

    if not prof.get("available"):
        return e

    e["water_profile_override_v525"] = e.get("water_profile_override_v525") or {}
    e["water_profile_override_v525"].update(prof)

    profile_direction = prof.get("direction")
    profile_timing = prof.get("timing")

    old_dir = str(e.get("water_direction") or "").lower()
    old_timing = str(e.get("water_timing") or "").lower()

    # Override direction if profile evidence is directional and original is unknown/conflicting.
    if profile_direction and profile_direction not in {"water magnitude close"}:
        if (
            not old_dir
            or "unknown" in old_dir
            or ("too high" in profile_direction and "too low" in old_dir)
            or ("too low" in profile_direction and "too high" in old_dir)
        ):
            e["water_direction_original_v525"] = e.get("water_direction")
            e["water_direction"] = profile_direction
            e["water_direction_source_v525"] = "water_profile_arrays"

    # Override timing if original says no breakthrough but profiles are active.
    if profile_timing:
        if (
            not old_timing
            or "unknown" in old_timing
            or ("no breakthrough" in old_timing and "active" in profile_timing)
        ):
            e["water_timing_original_v525"] = e.get("water_timing")
            e["water_timing"] = profile_timing
            e["water_timing_source_v525"] = "water_profile_arrays"

    return e


def _v514_evidence_for_well(w):
    """
    V525 replacement: original V514 evidence + profile/numeric water override.
    """
    if _v514_evidence_for_well_before_v525:
        e = _v514_evidence_for_well_before_v525(w)
    else:
        e = {}

    e = _v525_apply_wct_numeric_override(e, w if isinstance(w, dict) else {})
    e = _v525_apply_profile_override(e)

    return e


def _v514_answer_for_well(e, hypotheses):
    top = hypotheses[0] if hypotheses else {}
    second = hypotheses[1] if len(hypotheses) > 1 else None

    msg = (
        f"For {e.get('well')}, the strongest current hypothesis is **{top.get('Hypothesis')}** "
        f"(score {top.get('Score')}). "
    )

    if second:
        msg += f"The second hypothesis is **{second.get('Hypothesis')}** (score {second.get('Score')}). "

    msg += (
        f"Evidence summary: oil score {e.get('oil_score')}, water/WCT score {e.get('water_score')}, "
        f"gas score {e.get('gas_score')}, BHP score {e.get('bhp_score')}. "
        f"WCT pattern: {e.get('wct_bias')}; timing/direction: {e.get('water_timing')} / {e.get('water_direction')}. "
    )

    override = e.get("water_profile_override_v525") or {}
    if override:
        pieces = []
        if override.get("sim_total") is not None and override.get("obs_total") is not None:
            pieces.append(
                f"water-profile totals sim={override.get('sim_total'):.3g}, obs={override.get('obs_total'):.3g}"
            )
        if override.get("sim_wct") is not None and override.get("obs_wct") is not None:
            pieces.append(
                f"WCT numeric sim={override.get('sim_wct'):.3g}, obs={override.get('obs_wct'):.3g}"
            )
        if override.get("override_applied"):
            pieces.append("profile/numeric evidence overrides the generic WCT label")

        if pieces:
            msg += "Profile evidence override: " + "; ".join(pieces) + ". "

    msg += "This is an integrated diagnosis, so RelPerm is treated as one possible explanation, not as the final answer by itself."

    return msg


def _v525_match_bucket(score):
    s = _v525_safe_float(score)
    if s is None:
        return "N/A"
    if s >= 90:
        return "Good"
    if s >= 70:
        return "Fair"
    if s >= 50:
        return "Weak"
    return "Poor"


def _v525_direction_counts(wells):
    counts = {}
    for w in wells:
        e = _v514_evidence_for_well(w)
        d = e.get("water_direction") or "unknown"
        counts[d] = counts.get(d, 0) + 1
    return counts


def _v525_executive_summary_response(message):
    wells = _v514_get_all_diag_wells()

    evidences = [_v514_evidence_for_well(w) for w in wells if isinstance(w, dict)]
    evidences = [e for e in evidences if e.get("well")]

    if not evidences:
        return {
            "type": "reasoning_response",
            "intent": "executive_history_match_summary_v525",
            "answer": "I could not build the executive history-match summary because no diagnostic well payload was available.",
            "ui_blocks": [],
            "agent_trace": {"ExecutiveHistoryMatchSummaryAgentV525": {"status": "no_payload"}},
        }

    def avg(key):
        vals = [_v525_safe_float(e.get(key)) for e in evidences]
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else None

    oil_avg = avg("oil_score")
    water_avg = avg("water_score")
    gas_avg = avg("gas_score")
    bhp_avg = avg("bhp_score")
    overall_avg = avg("overall_score")

    weak_water = sorted(evidences, key=lambda e: _v525_safe_float(e.get("water_score"), 9999))[:5]
    weak_bhp = sorted(evidences, key=lambda e: _v525_safe_float(e.get("bhp_score"), 9999))[:5]

    water_dirs = {}
    for e in evidences:
        d = e.get("water_direction") or "unknown"
        water_dirs[d] = water_dirs.get(d, 0) + 1

    phase_rows = [
        {
            "Area": "Overall",
            "Avg score": round(overall_avg, 2) if overall_avg is not None else None,
            "Quality": _v525_match_bucket(overall_avg),
            "Executive readout": "Model is usable, but water/pressure require focused calibration." if overall_avg and overall_avg >= 70 else "Model requires material review before decision use.",
        },
        {
            "Area": "Oil",
            "Avg score": round(oil_avg, 2) if oil_avg is not None else None,
            "Quality": _v525_match_bucket(oil_avg),
            "Executive readout": "Oil match is robust across the active wells.",
        },
        {
            "Area": "Gas/GOR",
            "Avg score": round(gas_avg, 2) if gas_avg is not None else None,
            "Quality": _v525_match_bucket(gas_avg),
            "Executive readout": "Gas match is generally strong; gas is not the main mismatch driver.",
        },
        {
            "Area": "Water/WCT",
            "Avg score": round(water_avg, 2) if water_avg is not None else None,
            "Quality": _v525_match_bucket(water_avg),
            "Executive readout": "Water/WCT is the weakest match area and drives most reservoir uncertainty.",
        },
        {
            "Area": "BHP/Pressure",
            "Avg score": round(bhp_avg, 2) if bhp_avg is not None else None,
            "Quality": _v525_match_bucket(bhp_avg),
            "Executive readout": "Pressure match is secondary concern; review connectivity, support and constraints.",
        },
    ]

    weak_rows = []
    for e in weak_water:
        weak_rows.append({
            "Well": e.get("well"),
            "Water score": e.get("water_score"),
            "Water direction": e.get("water_direction"),
            "Water timing": e.get("water_timing"),
            "Oil": e.get("oil_score"),
            "Gas": e.get("gas_score"),
            "BHP": e.get("bhp_score"),
            "TRAN pct": e.get("tran_percentile"),
            "PERM pct": e.get("perm_percentile"),
            "Note": "Profile/numeric override used" if e.get("water_profile_override_v525") else "",
        })

    pressure_rows = []
    for e in weak_bhp:
        pressure_rows.append({
            "Well": e.get("well"),
            "BHP score": e.get("bhp_score"),
            "Pressure delta": e.get("delta_pressure"),
            "Water score": e.get("water_score"),
            "Gas score": e.get("gas_score"),
            "TRAN pct": e.get("tran_percentile"),
            "Interpretation": "Check pressure support/connectivity/constraints before phase tuning.",
        })

    water_dir_text = ", ".join([f"{k}: {v}" for k, v in sorted(water_dirs.items(), key=lambda x: x[0])])

    answer = (
        "Executive summary: the history match is strong for oil and gas, but materially weaker for water/WCT and pressure. "
        f"Average scores are Oil={oil_avg:.1f}, Gas={gas_avg:.1f}, Water={water_avg:.1f}, BHP={bhp_avg:.1f} where available. "
        "The main model risk is not hydrocarbon production capacity; it is water movement and pressure/connectivity calibration. "
        f"Water direction evidence after profile/numeric overrides: {water_dir_text}. "
        "Recommended next step: review weak water wells jointly with BHP, TRAN/PERM/SWAT and RelPerm/endpoints rather than applying a single global correction."
    )

    return {
        "type": "visual_response",
        "intent": "executive_history_match_summary_v525",
        "answer": answer,
        "ui_blocks": [
            {
                "type": "compact_table",
                "title": "Executive HM quality summary",
                "columns": ["Area", "Avg score", "Quality", "Executive readout"],
                "rows": phase_rows,
            },
            {
                "type": "compact_table",
                "title": "Weakest water/WCT evidence",
                "columns": ["Well", "Water score", "Water direction", "Water timing", "Oil", "Gas", "BHP", "TRAN pct", "PERM pct", "Note"],
                "rows": weak_rows,
            },
            {
                "type": "compact_table",
                "title": "Weakest BHP/pressure evidence",
                "columns": ["Well", "BHP score", "Pressure delta", "Water score", "Gas score", "TRAN pct", "Interpretation"],
                "rows": pressure_rows,
            },
            {
                "type": "suggestions",
                "title": "Recommended next checks",
                "items": [
                    "Inspect water-profile overrides for wells where diagnostic WCT label conflicts with profile evidence.",
                    "Prioritize wells with good oil/gas but poor water and BHP.",
                    "Compare TRAN-only, RelPerm-only and combined sensitivities for the top weak-water wells.",
                    "Use streamlines at beginning/end of history to confirm whether water movement follows expected corridors.",
                ],
            },
        ],
        "data": {
            "oil_avg": oil_avg,
            "gas_avg": gas_avg,
            "water_avg": water_avg,
            "bhp_avg": bhp_avg,
            "overall_avg": overall_avg,
            "water_direction_counts": water_dirs,
            "method": "diagnostic score summary with V525 profile/numeric water evidence override",
        },
        "universal_intent_v500": {
            "task_type": "executive_history_match_summary_v525",
            "original_message": message,
        },
        "agent_trace": {
            "ExecutiveHistoryMatchSummaryAgentV525": {
                "status": "executive_summary_generated",
                "wells": len(evidences),
                "profile_override_enabled": True,
            }
        },
    }


def _v525_is_executive_hm_summary_request(message):
    msg = _norm_v500(message)

    return (
        ("executive summary" in msg or "management summary" in msg or "summary" in msg)
        and (
            "history match" in msg
            or "hm quality" in msg
            or "match quality" in msg
            or "history matching" in msg
        )
    )


try:
    _execute_plan_before_v525 = execute_plan_v500
except Exception:
    _execute_plan_before_v525 = None


def execute_plan_v500(intent, plan, evidence_board):
    original = intent.get("original_message") or ""

    if _v525_is_executive_hm_summary_request(original):
        return _v525_executive_summary_response(original)

    if _execute_plan_before_v525:
        return _execute_plan_before_v525(intent, plan, evidence_board)

    return {
        "type": "reasoning_response",
        "intent": "fallback_v525",
        "answer": "V525 fallback: no previous execute_plan_v500 available.",
        "ui_blocks": [],
    }

# END V525 PROFILE EVIDENCE OVERRIDE + EXECUTIVE HM SUMMARY


# ==========================================================
# V525C FIX SAFE FLOAT SIGNATURE
#
# Fix:
# _v525_safe_float was defined with one argument but used in some places as:
# _v525_safe_float(value, default)
# ==========================================================

def _v525_safe_float(x, default=None):
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        try:
            v = _safe_float_v500(x)
            return default if v is None else v
        except Exception:
            return default

# END V525C FIX SAFE FLOAT SIGNATURE
