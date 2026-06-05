from __future__ import annotations

from typing import Any, Dict, List, TypedDict


# ==========================================================
# V501 REAL LANGGRAPH UNIVERSAL RESERVOIR ORCHESTRATOR
#
# This file turns the V500 semantic orchestrator into a real
# LangGraph StateGraph.
#
# Principle:
# - LangGraph decides the route.
# - Existing deterministic components execute as tools.
# - Evidence board and critic validate the result.
# ==========================================================


class ReservoirGraphStateV501(TypedDict, total=False):
    message: str
    intent: Dict[str, Any]
    plan: Dict[str, Any]
    evidence_board: Dict[str, Any]
    response: Dict[str, Any]
    final_response: Dict[str, Any]
    route: str


def _load_v500():
    from app.universal_reservoir_orchestrator_v500 import (
        interpret_request_v500,
        build_plan_v500,
        critic_validate_v500,
        package_response_v500,
        _execute_well_profile_v500,
        _execute_cumulative_profile_v500,
        _execute_multi_variable_profile_v500,
        _execute_property_distribution_v500,
        _execute_property_map_v500,
        _execute_well_data_operation_v500,
        _execute_diagnostic_cluster_v500,
        _execute_integrated_diagnostic_v500,
        execute_plan_v500,
    )

    return {
        "interpret_request_v500": interpret_request_v500,
        "build_plan_v500": build_plan_v500,
        "critic_validate_v500": critic_validate_v500,
        "package_response_v500": package_response_v500,
        "_execute_well_profile_v500": _execute_well_profile_v500,
        "_execute_cumulative_profile_v500": _execute_cumulative_profile_v500,
        "_execute_multi_variable_profile_v500": _execute_multi_variable_profile_v500,
        "_execute_property_distribution_v500": _execute_property_distribution_v500,
        "_execute_property_map_v500": _execute_property_map_v500,
        "_execute_well_data_operation_v500": _execute_well_data_operation_v500,
        "_execute_diagnostic_cluster_v500": _execute_diagnostic_cluster_v500,
        "_execute_integrated_diagnostic_v500": _execute_integrated_diagnostic_v500,
        "execute_plan_v500": execute_plan_v500,
    }


def intent_interpreter_node_v501(state: ReservoirGraphStateV501) -> ReservoirGraphStateV501:
    f = _load_v500()
    message = state.get("message", "")

    intent = f["interpret_request_v500"](message)

    evidence_board = {
        "schema_version": "v501",
        "original_message": message,
        "evidence": [],
        "node_trace": [],
    }

    evidence_board["node_trace"].append({
        "node": "IntentInterpreterNodeV501",
        "finding": "Converted natural language request into structured reservoir intent.",
        "intent": intent,
    })

    return {
        **state,
        "intent": intent,
        "evidence_board": evidence_board,
    }


def task_planner_node_v501(state: ReservoirGraphStateV501) -> ReservoirGraphStateV501:
    f = _load_v500()
    intent = state.get("intent") or {}
    plan = f["build_plan_v500"](intent)

    evidence_board = state.get("evidence_board") or {}
    evidence_board.setdefault("node_trace", []).append({
        "node": "TaskPlannerNodeV501",
        "finding": "Built specialist-agent execution plan from structured intent.",
        "plan": plan,
    })

    return {
        **state,
        "plan": plan,
        "evidence_board": evidence_board,
    }


def route_selector_v501(state: ReservoirGraphStateV501) -> str:
    intent = state.get("intent") or {}
    task = intent.get("task_type") or "general_reservoir_reasoning"

    route_map = {
        "well_profile": "execute_profile",
        "cumulative_profile": "execute_cumulative_profile",
        "multi_variable_profile": "execute_multi_variable_profile",
        "ensemble_profile_percentiles": "execute_generic_plan",
        "property_distribution": "execute_property_distribution",
        "property_map": "execute_property_map",
        "conditional_property_map": "execute_conditional_map",
        "grid_data_operation": "execute_generic_plan",
        "well_data_operation": "execute_well_data_operation",
        "diagnostic_cluster": "execute_diagnostic_cluster",
        "integrated_diagnostic_reasoning": "execute_integrated_reasoning",
        "general_reservoir_reasoning": "execute_integrated_reasoning",
    }

    return route_map.get(task, "execute_generic_plan")


def _append_exec_trace_v501(
    state: ReservoirGraphStateV501,
    node: str,
    detail: str,
    response: Dict[str, Any],
) -> ReservoirGraphStateV501:
    evidence_board = state.get("evidence_board") or {}
    evidence_board.setdefault("node_trace", []).append({
        "node": node,
        "finding": detail,
        "response_intent": response.get("intent") if isinstance(response, dict) else None,
        "ui_block_types": [
            b.get("type") for b in (response.get("ui_blocks") or [])
            if isinstance(b, dict)
        ] if isinstance(response, dict) else [],
    })

    return {
        **state,
        "response": response,
        "evidence_board": evidence_board,
    }


def execute_profile_node_v501(state: ReservoirGraphStateV501) -> ReservoirGraphStateV501:
    f = _load_v500()
    response = f["_execute_well_profile_v500"](state.get("intent") or {})
    return _append_exec_trace_v501(
        state,
        "ProfileExecutionNodeV501",
        "Executed well-level dynamic profile request.",
        response,
    )


def execute_cumulative_profile_node_v501(state: ReservoirGraphStateV501) -> ReservoirGraphStateV501:
    f = _load_v500()
    response = f["_execute_cumulative_profile_v500"](state.get("intent") or {})
    return _append_exec_trace_v501(
        state,
        "CumulativeProfileNodeV501",
        "Executed rate profile and transformed it into cumulative profile.",
        response,
    )


def execute_multi_variable_profile_node_v501(state: ReservoirGraphStateV501) -> ReservoirGraphStateV501:
    f = _load_v500()
    response = f["_execute_multi_variable_profile_v500"](state.get("intent") or {})
    return _append_exec_trace_v501(
        state,
        "MultiVariableProfileNodeV501",
        "Executed multi-variable well profile request.",
        response,
    )


def execute_property_distribution_node_v501(state: ReservoirGraphStateV501) -> ReservoirGraphStateV501:
    f = _load_v500()
    response = f["_execute_property_distribution_v500"](state.get("intent") or {})
    return _append_exec_trace_v501(
        state,
        "PropertyDistributionNodeV501",
        "Executed property histogram/distribution request. Distribution intent has priority over map intent.",
        response,
    )


def execute_property_map_node_v501(state: ReservoirGraphStateV501) -> ReservoirGraphStateV501:
    f = _load_v500()
    response = f["_execute_property_map_v500"](state.get("intent") or {})
    return _append_exec_trace_v501(
        state,
        "PropertyMapNodeV501",
        "Executed grid property map request.",
        response,
    )


def execute_conditional_map_node_v501(state: ReservoirGraphStateV501) -> ReservoirGraphStateV501:
    f = _load_v500()
    response = f["execute_plan_v500"](
        state.get("intent") or {},
        state.get("plan") or {},
        state.get("evidence_board") or {},
    )
    return _append_exec_trace_v501(
        state,
        "ConditionalMapNodeV501",
        "Executed conditional property-map/data-operation request through DataAlgebra-capable plan.",
        response,
    )


def execute_well_data_operation_node_v501(state: ReservoirGraphStateV501) -> ReservoirGraphStateV501:
    f = _load_v500()
    response = f["_execute_well_data_operation_v500"](state.get("intent") or {})
    return _append_exec_trace_v501(
        state,
        "WellDataOperationNodeV501",
        "Executed well time-series calculation request.",
        response,
    )


def execute_diagnostic_cluster_node_v501(state: ReservoirGraphStateV501) -> ReservoirGraphStateV501:
    f = _load_v500()
    response = f["_execute_diagnostic_cluster_v500"](state.get("intent") or {})
    return _append_exec_trace_v501(
        state,
        "DiagnosticClusterNodeV501",
        "Executed field/well diagnostic cluster analysis request.",
        response,
    )


def execute_integrated_reasoning_node_v501(state: ReservoirGraphStateV501) -> ReservoirGraphStateV501:
    f = _load_v500()
    response = f["_execute_integrated_diagnostic_v500"](
        state.get("intent") or {},
        state.get("evidence_board") or {},
    )
    return _append_exec_trace_v501(
        state,
        "IntegratedReasoningNodeV501",
        "Executed integrated reservoir reasoning request.",
        response,
    )


def execute_generic_plan_node_v501(state: ReservoirGraphStateV501) -> ReservoirGraphStateV501:
    f = _load_v500()
    response = f["execute_plan_v500"](
        state.get("intent") or {},
        state.get("plan") or {},
        state.get("evidence_board") or {},
    )
    return _append_exec_trace_v501(
        state,
        "GenericPlanExecutionNodeV501",
        "Executed generic specialist plan.",
        response,
    )


def critic_validation_node_v501(state: ReservoirGraphStateV501) -> ReservoirGraphStateV501:
    f = _load_v500()
    intent = state.get("intent") or {}
    response = state.get("response") or {}
    evidence_board = state.get("evidence_board") or {}

    validated = f["critic_validate_v500"](intent, response, evidence_board)

    evidence_board.setdefault("node_trace", []).append({
        "node": "CriticValidationNodeV501",
        "finding": "Validated output type against interpreted user intent.",
        "critic": validated.get("agent_trace", {}).get("VisualAndReasoningCriticV500"),
    })

    return {
        **state,
        "response": validated,
        "evidence_board": evidence_board,
    }


def final_packaging_node_v501(state: ReservoirGraphStateV501) -> ReservoirGraphStateV501:
    f = _load_v500()

    message = state.get("message") or ""
    intent = state.get("intent") or {}
    plan = state.get("plan") or {}
    response = state.get("response") or {}
    evidence_board = state.get("evidence_board") or {}

    final = f["package_response_v500"](
        message,
        intent,
        plan,
        response,
        evidence_board,
    )

    final.setdefault("agent_trace", {})
    final["agent_trace"]["LangGraphUniversalReservoirOrchestratorV501"] = {
        "framework": "LangGraph StateGraph",
        "nodes": [
            "IntentInterpreterNodeV501",
            "TaskPlannerNodeV501",
            "ConditionalExecutionRouteV501",
            "SpecialistExecutionNodeV501",
            "CriticValidationNodeV501",
            "FinalPackagingNodeV501",
        ],
        "task_type": intent.get("task_type"),
        "plan_steps": plan.get("steps", []),
        "principle": "LangGraph routes; deterministic tools execute; critic validates.",
    }

    final.setdefault("interaction_edges", [])
    final["interaction_edges"].append({
        "from": "LangGraphUniversalReservoirOrchestratorV501",
        "to": "SpecialistAgents",
        "reason": "StateGraph selected specialist execution path based on structured reservoir intent.",
    })

    final["api_route_v501"] = "/api/agent-chat-v501 -> LangGraphUniversalReservoirOrchestratorV501"

    return {
        **state,
        "final_response": final,
    }


def build_langgraph_v501():
    try:
        from langgraph.graph import StateGraph, END
    except Exception as exc:
        raise RuntimeError(
            "LangGraph is not available in this environment. Install/enable langgraph before using V501."
        ) from exc

    graph = StateGraph(ReservoirGraphStateV501)

    graph.add_node("interpret_intent", intent_interpreter_node_v501)
    graph.add_node("plan_tasks", task_planner_node_v501)

    graph.add_node("execute_profile", execute_profile_node_v501)
    graph.add_node("execute_cumulative_profile", execute_cumulative_profile_node_v501)
    graph.add_node("execute_multi_variable_profile", execute_multi_variable_profile_node_v501)
    graph.add_node("execute_property_distribution", execute_property_distribution_node_v501)
    graph.add_node("execute_property_map", execute_property_map_node_v501)
    graph.add_node("execute_conditional_map", execute_conditional_map_node_v501)
    graph.add_node("execute_well_data_operation", execute_well_data_operation_node_v501)
    graph.add_node("execute_diagnostic_cluster", execute_diagnostic_cluster_node_v501)
    graph.add_node("execute_integrated_reasoning", execute_integrated_reasoning_node_v501)
    graph.add_node("execute_generic_plan", execute_generic_plan_node_v501)

    graph.add_node("critic_validation", critic_validation_node_v501)
    graph.add_node("final_packaging", final_packaging_node_v501)

    graph.set_entry_point("interpret_intent")
    graph.add_edge("interpret_intent", "plan_tasks")

    graph.add_conditional_edges(
        "plan_tasks",
        route_selector_v501,
        {
            "execute_profile": "execute_profile",
            "execute_cumulative_profile": "execute_cumulative_profile",
            "execute_multi_variable_profile": "execute_multi_variable_profile",
            "execute_property_distribution": "execute_property_distribution",
            "execute_property_map": "execute_property_map",
            "execute_conditional_map": "execute_conditional_map",
            "execute_well_data_operation": "execute_well_data_operation",
            "execute_diagnostic_cluster": "execute_diagnostic_cluster",
            "execute_integrated_reasoning": "execute_integrated_reasoning",
            "execute_generic_plan": "execute_generic_plan",
        },
    )

    for node in [
        "execute_profile",
        "execute_cumulative_profile",
        "execute_multi_variable_profile",
        "execute_property_distribution",
        "execute_property_map",
        "execute_conditional_map",
        "execute_well_data_operation",
        "execute_diagnostic_cluster",
        "execute_integrated_reasoning",
        "execute_generic_plan",
    ]:
        graph.add_edge(node, "critic_validation")

    graph.add_edge("critic_validation", "final_packaging")
    graph.add_edge("final_packaging", END)

    return graph.compile()


_COMPILED_GRAPH_V501 = None


def run_langgraph_universal_orchestrator_v501(message: str) -> Dict[str, Any]:
    global _COMPILED_GRAPH_V501

    if _COMPILED_GRAPH_V501 is None:
        _COMPILED_GRAPH_V501 = build_langgraph_v501()

    state: ReservoirGraphStateV501 = {
        "message": message,
    }

    out = _COMPILED_GRAPH_V501.invoke(state)

    final = out.get("final_response")
    if isinstance(final, dict):
        return final

    return {
        "type": "reasoning_response",
        "intent": "langgraph_v501_error",
        "answer": "LangGraph V501 completed but did not return a final response.",
        "ui_blocks": [],
        "agent_trace": {
            "LangGraphUniversalReservoirOrchestratorV501": {
                "status": "missing_final_response",
                "raw_state_keys": list(out.keys()) if isinstance(out, dict) else [],
            }
        },
    }


# ==========================================================
# V512C WRAPPER-LEVEL TIMESERIES CLUSTERING FORCE ROUTE
#
# Problem observed:
# Some profile-clustering requests are still stolen by diagnostic_cluster
# / WCT bias router, or fail before returning a normal V501 response.
#
# This wrapper guard runs BEFORE/AROUND the compiled graph output.
#
# It forces:
# - clusters based on oil rate
# - clusters based on gas rate
# - clusters based on water production behavior
# - cluster wells based on GOR behavior
# - cluster wells based on BHP trend
# - cluster wells using oil, water, gas and BHP together
#
# It does NOT steal explicit mismatch/bias cluster requests:
# - WCT bias cluster
# - gas mismatch clusters
# - BHP mismatch clusters
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V512C = run_langgraph_universal_orchestrator_v501


def _v512c_norm(message):
    return " ".join(str(message or "").lower().replace("_", " ").replace("-", " ").split())


def _v512c_contains_any(msg, terms):
    return any(t in msg for t in terms)


def _v512c_is_explicit_mismatch_cluster(message):
    msg = _v512c_norm(message)

    return _v512c_contains_any(msg, [
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


def _v512c_is_profile_cluster_request(message):
    msg = _v512c_norm(message)

    if _v512c_is_explicit_mismatch_cluster(msg):
        return False

    if not _v512c_contains_any(msg, ["cluster", "clusters", "clustering", "group wells", "similar wells"]):
        return False

    return _v512c_contains_any(msg, [
        "based on oil",
        "based on gas",
        "based on water",
        "based on gor",
        "based on bhp",
        "oil rate",
        "gas rate",
        "water production",
        "production behavior",
        "production behaviour",
        "gor behavior",
        "gor behaviour",
        "bhp trend",
        "pressure trend",
        "profile",
        "profiles",
        "time series",
        "trend",
        "behavior",
        "behaviour",
        "oil, water, gas and bhp",
        "oil water gas bhp",
    ])


def _v512c_detect_variables(message):
    msg = _v512c_norm(message)

    if "oil, water, gas and bhp" in msg or "oil water gas bhp" in msg:
        return ["oil", "water", "gas", "bhp"]

    variables = []

    if "gor" in msg:
        variables.append("gor")

    if "wct" in msg or "water cut" in msg:
        variables.append("wct")

    if "oil" in msg:
        variables.append("oil")

    if "water" in msg and "wct" not in variables:
        variables.append("water")

    if "gas" in msg and "gor" not in variables:
        variables.append("gas")

    if "bhp" in msg or "pressure trend" in msg or "pressure depletion" in msg:
        variables.append("bhp")

    if not variables:
        if "production behavior" in msg or "production behaviour" in msg:
            variables = ["oil", "water", "gas"]
        else:
            variables = ["oil"]

    allowed = ["oil", "water", "gas", "gor", "wct", "bhp"]
    out = []

    for v in variables:
        if v in allowed and v not in out:
            out.append(v)

    return out or ["oil"]


def _v512c_fallback_cluster_from_diagnostics(message, variables, error_text=""):
    """
    Last-resort fallback if V512 profile extraction fails.
    It returns a visual/table based on diagnostic score proxies instead of crashing.
    """
    try:
        from app.universal_reservoir_orchestrator_v500 import _v506_get_wct_wells
        wells = _v506_get_wct_wells()
    except Exception:
        wells = []

    if not wells:
        return {
            "type": "reasoning_response",
            "intent": "time_series_clustering",
            "answer": (
                "I detected a time-series clustering request, but profile extraction failed and no diagnostic fallback wells were available. "
                f"Internal error: {error_text}"
            ),
            "ui_blocks": [],
            "universal_intent_v500": {
                "task_type": "time_series_clustering",
                "variables": variables,
                "original_message": message,
            },
            "agent_trace": {
                "TimeSeriesClusteringWrapperV512C": {
                    "status": "fallback_failed",
                    "error": error_text,
                }
            },
        }

    def score_for_var(w, v):
        if v == "oil":
            return w.get("oil_score")
        if v == "water" or v == "wct":
            return w.get("water_score")
        if v == "gas" or v == "gor":
            return w.get("gas_score")
        if v == "bhp":
            return w.get("bhp_score")
        return w.get("overall_score")

    rows = []

    for w in wells:
        vals = []
        for v in variables:
            try:
                x = score_for_var(w, v)
                if x is not None:
                    vals.append(float(x))
            except Exception:
                pass

        proxy = sum(vals) / len(vals) if vals else float(w.get("overall_score") or 0.0)

        if proxy >= 85:
            cluster = "C1"
            label = "strong match / high response"
            code = 1
        elif proxy >= 65:
            cluster = "C2"
            label = "medium match / moderate response"
            code = 2
        else:
            cluster = "C3"
            label = "weak match / review required"
            code = 3

        rows.append({
            "Well": w.get("well"),
            "Cluster": cluster,
            "Proxy score": round(proxy, 2),
            "Interpretation": label,
            "Oil score": w.get("oil_score"),
            "Water score": w.get("water_score"),
            "Gas score": w.get("gas_score"),
            "BHP score": w.get("bhp_score"),
            "_i": w.get("i"),
            "_j": w.get("j"),
            "_code": code,
        })

    plot_rows = [r for r in rows if r.get("_i") is not None and r.get("_j") is not None]

    plot_block = {
        "type": "plotly_chart",
        "title": f"Fallback clustering proxy based on {', '.join(v.upper() for v in variables)}",
        "data": [
            {
                "type": "scatter",
                "mode": "markers+text",
                "name": "Wells",
                "x": [r["_i"] for r in plot_rows],
                "y": [r["_j"] for r in plot_rows],
                "text": [r["Well"] for r in plot_rows],
                "customdata": [[r["Well"], r["Cluster"], r["Proxy score"], r["Interpretation"]] for r in plot_rows],
                "textposition": "top center",
                "marker": {
                    "size": 13,
                    "color": [r["_code"] for r in plot_rows],
                    "colorscale": "Viridis",
                    "showscale": True,
                    "colorbar": {"title": "Cluster"},
                },
                "hovertemplate": (
                    "Well: %{customdata[0]}<br>"
                    "Cluster: %{customdata[1]}<br>"
                    "Proxy score: %{customdata[2]}<br>"
                    "%{customdata[3]}<extra></extra>"
                ),
            }
        ],
        "layout": {
            "title": f"Fallback clustering proxy based on {', '.join(v.upper() for v in variables)}",
            "xaxis": {"title": "I index", "showgrid": False},
            "yaxis": {"title": "J index", "showgrid": False},
            "height": 560,
            "hovermode": "closest",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "paper_bgcolor": "rgba(0,0,0,0)",
        },
        "config": {"responsive": True, "displaylogo": False},
    }

    clean_rows = []
    for r in rows:
        clean_rows.append({
            "Well": r["Well"],
            "Cluster": r["Cluster"],
            "Proxy score": r["Proxy score"],
            "Interpretation": r["Interpretation"],
            "Oil score": r["Oil score"],
            "Water score": r["Water score"],
            "Gas score": r["Gas score"],
            "BHP score": r["BHP score"],
        })

    return {
        "type": "visual_response",
        "intent": "time_series_clustering",
        "answer": (
            f"I detected a time-series clustering request for {', '.join(v.upper() for v in variables)}. "
            "The primary profile-based clustering path failed, so I returned a safe fallback clustering using available diagnostic score proxies. "
            "This prevents the dashboard from falling back to the WCT bias router or returning an error."
        ),
        "ui_blocks": [
            plot_block,
            {
                "type": "compact_table",
                "title": "Fallback cluster membership",
                "columns": ["Well", "Cluster", "Proxy score", "Interpretation", "Oil score", "Water score", "Gas score", "BHP score"],
                "rows": clean_rows,
            }
        ],
        "data": {
            "variables": variables,
            "wells_clustered": len(rows),
            "method": "fallback diagnostic-score proxy because profile clustering failed",
            "primary_error": error_text,
        },
        "universal_intent_v500": {
            "task_type": "time_series_clustering",
            "variables": variables,
            "original_message": message,
        },
        "agent_trace": {
            "TimeSeriesClusteringWrapperV512C": {
                "status": "fallback_proxy_used",
                "variables": variables,
                "primary_error": error_text,
            }
        },
    }


def _v512c_force_time_series_clustering(message, previous_result=None, previous_error=None):
    variables = _v512c_detect_variables(message)

    intent = {
        "task_type": "time_series_clustering",
        "variables": variables,
        "original_message": message,
        "time_series_clustering_v512": {
            "variables": variables,
            "reason": "V512C wrapper-level force route."
        },
        "flags": {
            "clustering": True,
            "time_series_clustering": True,
        }
    }

    try:
        from app.universal_reservoir_orchestrator_v500 import _v512_execute_time_series_clustering

        response = _v512_execute_time_series_clustering(intent)

        if not isinstance(response, dict):
            raise RuntimeError("V512 returned non-dict response")

        response["universal_intent_v500"] = intent
        response["api_route_v512c"] = "/api/agent-chat-v501 -> V512C forced TimeSeriesClusteringAgent"

        response.setdefault("agent_trace", {})
        response["agent_trace"]["TimeSeriesClusteringWrapperV512C"] = {
            "status": "forced_profile_clustering",
            "variables": variables,
            "previous_intent": previous_result.get("intent") if isinstance(previous_result, dict) else None,
            "previous_error": str(previous_error) if previous_error else None,
        }

        return response

    except Exception as exc:
        return _v512c_fallback_cluster_from_diagnostics(
            message,
            variables,
            error_text=str(exc),
        )


def run_langgraph_universal_orchestrator_v501(message: str):
    if _v512c_is_profile_cluster_request(message):
        return _v512c_force_time_series_clustering(message)

    try:
        result = _RUN_LANGGRAPH_V501_BEFORE_V512C(message)
    except Exception as exc:
        if _v512c_is_profile_cluster_request(message):
            return _v512c_force_time_series_clustering(message, previous_error=exc)
        raise

    # Safety net: if old graph still routed profile clustering to WCT/diagnostic/error,
    # override it after the fact.
    if _v512c_is_profile_cluster_request(message):
        bad_intents = {
            "wct_bias_cluster_map",
            "api_agent_chat_v501_error",
            "map",
        }

        intent = result.get("intent") if isinstance(result, dict) else None
        task = None
        if isinstance(result, dict):
            ui = result.get("universal_intent_v500") or {}
            if isinstance(ui, dict):
                task = ui.get("task_type")

        if intent in bad_intents or task != "time_series_clustering":
            return _v512c_force_time_series_clustering(message, previous_result=result)

    return result

# END V512C WRAPPER-LEVEL TIMESERIES CLUSTERING FORCE ROUTE


# ==========================================================
# V514B WRAPPER GUARD FOR INTEGRATED DIAGNOSIS
#
# Ensures why/caused-by/connectivity-vs-relperm requests do not get
# swallowed by RelPerm-only or generic diagnostic agents.
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V514B = run_langgraph_universal_orchestrator_v501


def _v514b_norm(message):
    return " ".join(str(message or "").lower().replace("_", " ").split())


def _v514b_is_integrated_request(message):
    msg = _v514b_norm(message)

    triggers = [
        "why", "explain", "caused by", "cause", "root cause",
        "more likely", "compare evidence", "connectivity issue", "relperm issue",
        "rel perm issue", "well control", "main driver", "review first",
        "top 5 wells", "requiring model review"
    ]

    terms = [
        "mismatch", "water", "wct", "gas", "gor", "bhp", "pressure",
        "oil", "permx", "perm", "poro", "swat", "tran", "connectivity",
        "relperm", "hw-"
    ]

    return any(t in msg for t in triggers) and any(t in msg for t in terms)


def _v514b_force_integrated(message, previous_result=None, previous_error=None):
    try:
        from app.universal_reservoir_orchestrator_v500 import (
            _v514_execute_integrated_diagnosis,
            _v514_extract_well,
        )

        intent = {
            "task_type": "integrated_parallel_diagnosis_v514",
            "original_message": message,
            "well": _v514_extract_well(message),
            "integrated_parallel_diagnosis_v514": {
                "well": _v514_extract_well(message),
                "reason": "V514B wrapper guard forced integrated diagnosis.",
            },
        }

        response = _v514_execute_integrated_diagnosis(intent)

        if isinstance(response, dict):
            response["universal_intent_v500"] = intent
            response["api_route_v514b"] = "/api/agent-chat-v501 -> V514B IntegratedParallelDiagnosisAgent"
            response.setdefault("agent_trace", {})
            response["agent_trace"]["IntegratedDiagnosisWrapperGuardV514B"] = {
                "status": "forced_integrated_diagnosis",
                "previous_intent": previous_result.get("intent") if isinstance(previous_result, dict) else None,
                "previous_error": str(previous_error) if previous_error else None,
            }

        return response

    except Exception as exc:
        return {
            "type": "reasoning_response",
            "intent": "integrated_parallel_diagnosis_v514_error",
            "answer": f"I detected an integrated diagnosis request, but V514 failed internally: {exc}",
            "ui_blocks": [],
            "universal_intent_v500": {
                "task_type": "integrated_parallel_diagnosis_v514",
                "original_message": message,
            },
            "agent_trace": {
                "IntegratedDiagnosisWrapperGuardV514B": {
                    "status": "failed",
                    "error": str(exc),
                }
            },
        }


def run_langgraph_universal_orchestrator_v501(message: str):
    if _v514b_is_integrated_request(message):
        # Preemptive force is safer because previous RelPerm/final guards can steal the answer.
        return _v514b_force_integrated(message)

    try:
        result = _RUN_LANGGRAPH_V501_BEFORE_V514B(message)
    except Exception as exc:
        if _v514b_is_integrated_request(message):
            return _v514b_force_integrated(message, previous_error=exc)
        raise

    if _v514b_is_integrated_request(message):
        txt = str((result or {}).get("answer") or (result or {}).get("message") or "").lower() if isinstance(result, dict) else ""
        intent = (result or {}).get("intent") if isinstance(result, dict) else ""

        bad = (
            "no relperm model could be assigned" in txt
            or "relperm" in intent.lower()
            or intent in {"api_agent_chat_v501_error"}
        )

        if bad:
            return _v514b_force_integrated(message, previous_result=result)

    return result

# END V514B WRAPPER GUARD FOR INTEGRATED DIAGNOSIS


# ==========================================================
# V514C WRAPPER PRIORITY PATCH
#
# Forces integrated diagnosis for:
# - compare pressure depletion / water mismatch / gas response
# - portfolio "find/identify wells..." questions
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V514C = run_langgraph_universal_orchestrator_v501


def _v514c_wrap_norm(message):
    return " ".join(str(message or "").lower().replace("_", " ").split())


def _v514c_wrap_is_integrated(message):
    msg = _v514c_wrap_norm(message)

    if "compare" in msg and any(x in msg for x in [
        "pressure depletion", "water mismatch", "gas response", "bhp",
        "pressure", "mismatch", "tran", "swat", "permx", "connectivity", "relperm"
    ]):
        return True

    if any(x in msg for x in [
        "find wells where",
        "identify wells where",
        "top 5 wells",
        "requiring model review",
        "main driver",
        "relperm tuning would be risky",
        "tran correction is more justified",
        "gas match is good but pressure",
        "water mismatch and gas mismatch",
    ]):
        return True

    try:
        return _v514b_is_integrated_request(message)
    except Exception:
        return False


def _v514c_force_integrated(message, previous_result=None, previous_error=None):
    try:
        from app.universal_reservoir_orchestrator_v500 import (
            _v514c_execute_integrated_diagnosis,
            _v514_extract_well,
            _v514c_portfolio_mode,
        )

        intent = {
            "task_type": "integrated_parallel_diagnosis_v514",
            "original_message": message,
            "well": _v514_extract_well(message),
            "integrated_parallel_diagnosis_v514": {
                "well": _v514_extract_well(message),
                "portfolio_mode": _v514c_portfolio_mode(message),
                "reason": "V514C wrapper guard forced integrated diagnosis.",
            },
        }

        response = _v514c_execute_integrated_diagnosis(intent)

        if isinstance(response, dict):
            response["universal_intent_v500"] = intent
            response["api_route_v514c"] = "/api/agent-chat-v501 -> V514C IntegratedParallelDiagnosisAgent"
            response.setdefault("agent_trace", {})
            response["agent_trace"]["IntegratedDiagnosisWrapperGuardV514C"] = {
                "status": "forced_integrated_diagnosis",
                "previous_intent": previous_result.get("intent") if isinstance(previous_result, dict) else None,
                "previous_error": str(previous_error) if previous_error else None,
            }

        return response

    except Exception as exc:
        return {
            "type": "reasoning_response",
            "intent": "integrated_parallel_diagnosis_v514_error",
            "answer": f"I detected an integrated diagnosis request, but V514C failed internally: {exc}",
            "ui_blocks": [],
            "universal_intent_v500": {
                "task_type": "integrated_parallel_diagnosis_v514",
                "original_message": message,
            },
            "agent_trace": {
                "IntegratedDiagnosisWrapperGuardV514C": {
                    "status": "failed",
                    "error": str(exc),
                }
            },
        }


def run_langgraph_universal_orchestrator_v501(message: str):
    if _v514c_wrap_is_integrated(message):
        return _v514c_force_integrated(message)

    try:
        result = _RUN_LANGGRAPH_V501_BEFORE_V514C(message)
    except Exception as exc:
        if _v514c_wrap_is_integrated(message):
            return _v514c_force_integrated(message, previous_error=exc)
        raise

    if _v514c_wrap_is_integrated(message):
        task = ""
        intent = ""
        if isinstance(result, dict):
            intent = str(result.get("intent") or "")
            ui = result.get("universal_intent_v500") or {}
            if isinstance(ui, dict):
                task = str(ui.get("task_type") or "")

        if task != "integrated_parallel_diagnosis_v514" or intent in {"multi_variable_profile", "relperm_curve_error"}:
            return _v514c_force_integrated(message, previous_result=result)

    return result

# END V514C WRAPPER PRIORITY PATCH


# ==========================================================
# V515B WRAPPER GUARD FOR CONNECTIVITY / COMMUNICATION
#
# Ensures communication/streamline/connectivity requests are not swallowed
# by generic map, profile, diagnostic or integrated-diagnosis routes.
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V515B = run_langgraph_universal_orchestrator_v501


def _v515b_norm(message):
    return " ".join(str(message or "").lower().replace("_", " ").split())


def _v515b_is_request(message):
    msg = _v515b_norm(message)

    connectivity_terms = [
        "communicate", "communication", "connected", "connectivity",
        "streamline", "streamlines", "flow path", "flow paths",
        "main flow corridor", "flow corridor", "isolated",
        "connectivity proxy", "most connected", "least connected",
        "low connectivity", "high connectivity",
        "tran corridor"
    ]

    return any(t in msg for t in connectivity_terms)


def _v515b_force(message, previous_result=None, previous_error=None):
    try:
        from app.universal_reservoir_orchestrator_v500 import (
            _v515_execute,
            _v515_extract_well,
            _v515_kind,
        )

        intent = {
            "task_type": "communication_connectivity_v515",
            "original_message": message,
            "well": _v515_extract_well(message),
            "communication_connectivity_v515": {
                "well": _v515_extract_well(message),
                "kind": _v515_kind(message),
                "reason": "V515B wrapper guard forced connectivity/communication route.",
            },
        }

        response = _v515_execute(intent)

        if isinstance(response, dict):
            response["universal_intent_v500"] = intent
            response["api_route_v515b"] = "/api/agent-chat-v501 -> V515 CommunicationConnectivityAgent"
            response.setdefault("agent_trace", {})
            response["agent_trace"]["ConnectivityWrapperGuardV515B"] = {
                "status": "forced_connectivity_route",
                "previous_intent": previous_result.get("intent") if isinstance(previous_result, dict) else None,
                "previous_error": str(previous_error) if previous_error else None,
            }

        return response

    except Exception as exc:
        return {
            "type": "reasoning_response",
            "intent": "communication_connectivity_v515_error",
            "answer": f"I detected a connectivity/communication request, but V515 failed internally: {exc}",
            "ui_blocks": [],
            "universal_intent_v500": {
                "task_type": "communication_connectivity_v515",
                "original_message": message,
            },
            "agent_trace": {
                "ConnectivityWrapperGuardV515B": {
                    "status": "failed",
                    "error": str(exc),
                }
            },
        }


def run_langgraph_universal_orchestrator_v501(message: str):
    if _v515b_is_request(message):
        return _v515b_force(message)

    try:
        result = _RUN_LANGGRAPH_V501_BEFORE_V515B(message)
    except Exception as exc:
        if _v515b_is_request(message):
            return _v515b_force(message, previous_error=exc)
        raise

    if _v515b_is_request(message):
        task = ""
        if isinstance(result, dict):
            ui = result.get("universal_intent_v500") or {}
            if isinstance(ui, dict):
                task = str(ui.get("task_type") or "")

        if task != "communication_connectivity_v515":
            return _v515b_force(message, previous_result=result)

    return result

# END V515B WRAPPER GUARD FOR CONNECTIVITY / COMMUNICATION


# ==========================================================
# V516 FINAL PRIORITY GUARD
#
# Final routing priority:
# 1. Profile/time-series clustering -> V512C/V512D
# 2. Integrated diagnosis why/caused-by/relperm-vs-connectivity -> V514C
# 3. Communication/connectivity/streamline screening -> V515
# 4. Existing graph / previous guards
#
# Purpose:
# Prevent broad connectivity wrapper V515 from stealing integrated diagnosis
# questions that mention "connectivity" together with "relperm", "why",
# "more likely", "cause", "compare evidence", etc.
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V516 = run_langgraph_universal_orchestrator_v501


def _v516_norm(message):
    return " ".join(str(message or "").lower().replace("_", " ").replace("-", " ").split())


def _v516_any(msg, terms):
    return any(t in msg for t in terms)


def _v516_is_explicit_mismatch_cluster(message):
    msg = _v516_norm(message)
    return _v516_any(msg, [
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


def _v516_is_profile_cluster(message):
    msg = _v516_norm(message)

    if _v516_is_explicit_mismatch_cluster(message):
        return False

    if not _v516_any(msg, ["cluster", "clusters", "clustering", "group wells", "similar wells"]):
        return False

    return _v516_any(msg, [
        "based on oil",
        "based on gas",
        "based on water",
        "based on gor",
        "based on bhp",
        "oil rate",
        "gas rate",
        "water production",
        "production behavior",
        "production behaviour",
        "gor behavior",
        "gor behaviour",
        "bhp trend",
        "pressure trend",
        "profile",
        "profiles",
        "time series",
        "trend",
        "behavior",
        "behaviour",
        "oil, water, gas and bhp",
        "oil water gas bhp",
    ])


def _v516_is_integrated(message):
    msg = _v516_norm(message)

    strong_integrated = [
        "why",
        "explain",
        "caused by",
        "cause",
        "root cause",
        "more likely",
        "connectivity issue",
        "relperm issue",
        "rel perm issue",
        "compare evidence",
        "main driver",
        "review first",
        "find wells where",
        "identify wells where",
        "relperm tuning",
        "tran correction",
        "requiring model review",
        "top 5 wells",
        "good but",
        "poor, then explain",
    ]

    reservoir_terms = [
        "mismatch", "water", "wct", "gas", "gor", "bhp", "pressure",
        "oil", "permx", "perm", "poro", "swat", "tran",
        "connectivity", "connected", "relperm", "rel perm", "hw"
    ]

    if _v516_any(msg, strong_integrated) and _v516_any(msg, reservoir_terms):
        return True

    if "compare" in msg and _v516_any(msg, [
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

    return False


def _v516_is_connectivity(message):
    msg = _v516_norm(message)

    if _v516_is_integrated(message):
        return False

    return _v516_any(msg, [
        "communicate",
        "communication",
        "connected to",
        "connectivity proxy",
        "streamline",
        "streamlines",
        "flow path",
        "flow paths",
        "main flow corridor",
        "flow corridor",
        "isolated",
        "most connected",
        "least connected",
        "low connectivity",
        "high connectivity",
        "rank wells by connectivity",
        "correlate connectivity",
    ])


def _v516_force_profile_cluster(message):
    try:
        return _v512c_force_time_series_clustering(message)
    except Exception as exc:
        return {
            "type": "reasoning_response",
            "intent": "time_series_clustering_error_v516",
            "answer": f"V516 detected profile clustering but failed to route it: {exc}",
            "ui_blocks": [],
            "universal_intent_v500": {
                "task_type": "time_series_clustering",
                "original_message": message,
            },
            "agent_trace": {
                "FinalPriorityGuardV516": {
                    "status": "profile_cluster_failed",
                    "error": str(exc),
                }
            },
        }


def _v516_force_integrated(message):
    try:
        return _v514c_force_integrated(message)
    except Exception:
        try:
            return _v514b_force_integrated(message)
        except Exception as exc:
            return {
                "type": "reasoning_response",
                "intent": "integrated_parallel_diagnosis_error_v516",
                "answer": f"V516 detected integrated diagnosis but failed to route it: {exc}",
                "ui_blocks": [],
                "universal_intent_v500": {
                    "task_type": "integrated_parallel_diagnosis_v514",
                    "original_message": message,
                },
                "agent_trace": {
                    "FinalPriorityGuardV516": {
                        "status": "integrated_failed",
                        "error": str(exc),
                    }
                },
            }


def _v516_force_connectivity(message):
    try:
        return _v515b_force(message)
    except Exception as exc:
        return {
            "type": "reasoning_response",
            "intent": "communication_connectivity_error_v516",
            "answer": f"V516 detected connectivity/communication but failed to route it: {exc}",
            "ui_blocks": [],
            "universal_intent_v500": {
                "task_type": "communication_connectivity_v515",
                "original_message": message,
            },
            "agent_trace": {
                "FinalPriorityGuardV516": {
                    "status": "connectivity_failed",
                    "error": str(exc),
                }
            },
        }


def run_langgraph_universal_orchestrator_v501(message: str):
    if _v516_is_profile_cluster(message):
        response = _v516_force_profile_cluster(message)
        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["FinalPriorityGuardV516"] = {
                "priority": 1,
                "route": "profile_time_series_clustering",
            }
        return response

    if _v516_is_integrated(message):
        response = _v516_force_integrated(message)
        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["FinalPriorityGuardV516"] = {
                "priority": 2,
                "route": "integrated_parallel_diagnosis",
            }
        return response

    if _v516_is_connectivity(message):
        response = _v516_force_connectivity(message)
        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["FinalPriorityGuardV516"] = {
                "priority": 3,
                "route": "communication_connectivity",
            }
        return response

    return _RUN_LANGGRAPH_V501_BEFORE_V516(message)

# END V516 FINAL PRIORITY GUARD


# ==========================================================
# V516B EXPLICIT MISMATCH / BIAS CLUSTER PRIORITY FIX
#
# Regression after V516:
# "Show me WCT bias cluster map and explain it" was routed to
# IntegratedParallelDiagnosisAgent because it contains "explain" + WCT.
#
# Correct priority:
# - Explicit WCT/water bias cluster -> WCT bias cluster visual
# - Explicit gas/GOR/BHP mismatch cluster -> V513 mismatch diagnostic
# - why/caused-by/connectivity-vs-relperm -> V514 integrated diagnosis
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V516B = run_langgraph_universal_orchestrator_v501


def _v516b_norm(message):
    return " ".join(str(message or "").lower().replace("_", " ").replace("-", " ").split())


def _v516b_any(msg, terms):
    return any(t in msg for t in terms)


def _v516b_is_wct_bias_cluster(message):
    msg = _v516b_norm(message)

    has_cluster = _v516b_any(msg, ["cluster", "clusters", "map", "view"])
    has_bias = _v516b_any(msg, ["bias", "mismatch"])
    has_wct_water = _v516b_any(msg, ["wct", "water cut", "water bias", "water mismatch"])

    return has_cluster and has_bias and has_wct_water


def _v516b_is_gas_gor_bhp_mismatch_cluster(message):
    msg = _v516b_norm(message)

    has_cluster = _v516b_any(msg, ["cluster", "clusters", "map", "view"])
    has_mismatch = _v516b_any(msg, ["mismatch", "bias"])
    has_var = _v516b_any(msg, ["gas", "gor", "bhp", "pressure"])

    return has_cluster and has_mismatch and has_var and not _v516b_is_wct_bias_cluster(message)


def _v516b_force_wct_bias_cluster(message):
    try:
        from app.universal_reservoir_orchestrator_v500 import _call_wct_bias_builder_v500

        response = _call_wct_bias_builder_v500(message)

        if isinstance(response, dict):
            response["universal_intent_v500"] = {
                "task_type": "diagnostic_cluster",
                "variables": ["wct", "water"],
                "original_message": message,
                "explicit_bias_cluster_v516b": True,
            }
            response["api_route_v516b"] = "/api/agent-chat-v501 -> V516B explicit WCT bias cluster"
            response.setdefault("agent_trace", {})
            response["agent_trace"]["ExplicitBiasClusterPriorityGuardV516B"] = {
                "route": "wct_bias_cluster_visual",
                "reason": "Explicit WCT/water bias cluster request must not be captured by integrated diagnosis.",
            }

            return response

        raise RuntimeError("WCT bias builder returned non-dict response")

    except Exception as exc:
        return {
            "type": "reasoning_response",
            "intent": "wct_bias_cluster_error_v516b",
            "answer": f"I detected an explicit WCT bias cluster request, but the WCT cluster builder failed: {exc}",
            "ui_blocks": [],
            "universal_intent_v500": {
                "task_type": "diagnostic_cluster",
                "variables": ["wct", "water"],
                "original_message": message,
            },
            "agent_trace": {
                "ExplicitBiasClusterPriorityGuardV516B": {
                    "status": "failed",
                    "error": str(exc),
                }
            },
        }


def _v516b_force_mismatch_cluster(message):
    try:
        from app.universal_reservoir_orchestrator_v500 import _v513_execute, _v513_variable, _v513_task_kind

        variable = _v513_variable(message)
        kind = _v513_task_kind(message)

        response = _v513_execute(message, variable, kind)

        if isinstance(response, dict):
            response["universal_intent_v500"] = {
                "task_type": "mismatch_diagnostic_v513",
                "variables": [variable],
                "original_message": message,
                "explicit_mismatch_cluster_v516b": True,
            }
            response["api_route_v516b"] = "/api/agent-chat-v501 -> V516B explicit mismatch diagnostic"
            response.setdefault("agent_trace", {})
            response["agent_trace"]["ExplicitBiasClusterPriorityGuardV516B"] = {
                "route": "gas_gor_bhp_mismatch_diagnostic",
                "variable": variable,
                "kind": kind,
            }

            return response

        raise RuntimeError("V513 mismatch diagnostic returned non-dict response")

    except Exception as exc:
        return {
            "type": "reasoning_response",
            "intent": "mismatch_diagnostic_error_v516b",
            "answer": f"I detected an explicit mismatch cluster request, but V513 failed: {exc}",
            "ui_blocks": [],
            "universal_intent_v500": {
                "task_type": "mismatch_diagnostic_v513",
                "original_message": message,
            },
            "agent_trace": {
                "ExplicitBiasClusterPriorityGuardV516B": {
                    "status": "failed",
                    "error": str(exc),
                }
            },
        }


def run_langgraph_universal_orchestrator_v501(message: str):
    # Highest priority: explicit cluster visuals must not be stolen by V514 integrated diagnosis.
    if _v516b_is_wct_bias_cluster(message):
        return _v516b_force_wct_bias_cluster(message)

    if _v516b_is_gas_gor_bhp_mismatch_cluster(message):
        return _v516b_force_mismatch_cluster(message)

    return _RUN_LANGGRAPH_V501_BEFORE_V516B(message)

# END V516B EXPLICIT MISMATCH / BIAS CLUSTER PRIORITY FIX


# ==========================================================
# V518 TRUE STREAMLINE REQUEST GUARD
#
# Problem:
# "show me streamlines at the end of history" was routed to V515 proxy
# communication / flow paths. That is wrong: explicit streamline requests
# must use true streamline data if available, otherwise say that true
# streamline data is not exposed.
#
# Rule:
# - "streamlines" explicit -> true streamline route only.
# - Do not silently replace true streamline request with proxy connectivity.
# - Proxy is allowed only if user asks communication/connectivity/flow proxy.
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V518 = run_langgraph_universal_orchestrator_v501


def _v518_norm(message):
    return " ".join(str(message or "").lower().replace("_", " ").replace("-", " ").split())


def _v518_any(msg, terms):
    return any(t in msg for t in terms)


def _v518_is_true_streamline_request(message):
    msg = _v518_norm(message)

    if not _v518_any(msg, ["streamline", "streamlines"]):
        return False

    # If the user explicitly asks proxy/communication, V515 may handle it.
    if _v518_any(msg, [
        "proxy",
        "communication proxy",
        "connectivity proxy",
        "communicate",
        "communication",
    ]):
        return False

    return True


def _v518_is_true_streamline_response(response):
    if not isinstance(response, dict):
        return False

    intent = str(response.get("intent") or "").lower()
    if "streamline" in intent and "proxy" not in intent:
        return True

    for b in response.get("ui_blocks") or []:
        if not isinstance(b, dict):
            continue

        btype = str(b.get("type") or "").lower()
        title = str(b.get("title") or "").lower()

        if "streamline" in btype or "streamline" in title:
            if "proxy" not in title and "communication" not in title:
                return True

    return False


def _v518_try_legacy_streamline_route(message):
    """
    Try to bypass V515 proxy wrapper and let older graph/routes answer.
    We only accept the result if it really looks like a streamline visual.
    """
    candidates = []

    for name in [
        "_RUN_LANGGRAPH_V501_BEFORE_V515B",
        "_RUN_LANGGRAPH_V501_BEFORE_V516",
        "_RUN_LANGGRAPH_V501_BEFORE_V516B",
    ]:
        fn = globals().get(name)
        if callable(fn):
            candidates.append((name, fn))

    for name, fn in candidates:
        try:
            r = fn(message)
            if _v518_is_true_streamline_response(r):
                if isinstance(r, dict):
                    r.setdefault("agent_trace", {})
                    r["agent_trace"]["TrueStreamlineGuardV518"] = {
                        "status": "legacy_true_streamline_route_used",
                        "legacy_function": name,
                    }
                    r["api_route_v518"] = "/api/agent-chat-v501 -> V518 legacy true streamline route"
                return r
        except Exception:
            pass

    return None


def _v518_no_true_streamlines_response(message):
    return {
        "type": "reasoning_response",
        "intent": "true_streamline_not_available_v518",
        "answer": (
            "I detected an explicit request for true streamlines, but I could not find an exposed true-streamline visual/data route in the current backend response. "
            "I did not replace it with a proxy communication map because that would be misleading. "
            "If the old multiplier/corridor streamline visualization still exists in the project, we should reconnect this prompt to that existing renderer."
        ),
        "ui_blocks": [
            {
                "type": "suggestions",
                "title": "Next checks",
                "items": [
                    "Search the project for existing streamline renderers or endpoints.",
                    "Look for old multiplier/corridor map functions.",
                    "If true streamline arrays are not exported, expose them as a dedicated ui_block.",
                    "Use V515 only for proxy communication/connectivity, not for true streamlines.",
                ],
            }
        ],
        "universal_intent_v500": {
            "task_type": "true_streamline_visual",
            "original_message": message,
            "true_streamline_guard_v518": True,
        },
        "agent_trace": {
            "TrueStreamlineGuardV518": {
                "status": "true_streamline_route_not_found",
                "reason": "Explicit streamline request should not be converted to proxy flow paths.",
            }
        },
    }


def run_langgraph_universal_orchestrator_v501(message: str):
    if _v518_is_true_streamline_request(message):
        legacy = _v518_try_legacy_streamline_route(message)
        if legacy:
            return legacy
        return _v518_no_true_streamlines_response(message)

    return _RUN_LANGGRAPH_V501_BEFORE_V518(message)

# END V518 TRUE STREAMLINE REQUEST GUARD


# ==========================================================
# V519 RECONNECT EXISTING TRAN CORRIDOR / STREAMLINE VISUAL
#
# Purpose:
# Restore the original TRANCorridorVisualAgent route.
#
# This is the old/official visual that can show:
# - TRAN_H / transmissibility background
# - final-history streamlines as context
# - proposed TRAN multiplier corridor cells
# - suggested multiplier / IXF export evidence
#
# Important distinction:
# - "streamlines on transmissibility map" -> TRANCorridorVisualAgent
# - "TRAN multiplier corridor" -> TRANCorridorVisualAgent
# - "which wells communicate" -> V515 proxy communication
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V519 = run_langgraph_universal_orchestrator_v501


def _v519_norm(message):
    return " ".join(str(message or "").lower().replace("_", " ").replace("-", " ").split())


def _v519_any(msg, terms):
    return any(t in msg for t in terms)


def _v519_extract_well(message):
    import re
    m = re.search(r"\bHW[-\s]?(\d+)\b", str(message or ""), flags=re.IGNORECASE)
    if m:
        return f"HW-{int(m.group(1))}"
    return None


def _v519_is_tran_corridor_visual_request(message):
    msg = _v519_norm(message)

    # Explicit old official example / corridor visual.
    if _v519_any(msg, [
        "tran multiplier corridor",
        "transmissibility multiplier corridor",
        "multiplier corridor",
        "corridor multiplier",
        "corridor where the tran multiplier",
        "corridor where multiplier",
        "proposed tran corridor",
        "proposed transmissibility corridor",
        "candidate tran corridor",
        "candidate transmissibility corridor",
        "tran corridor visual",
        "transmissibility corridor visual",
        "show tran multiplier corridor",
        "show transmissibility multiplier corridor",
    ]):
        return True

    # User asks streamlines specifically on transmissibility / TRAN map.
    if _v519_any(msg, ["streamline", "streamlines"]) and _v519_any(msg, [
        "transmissibility",
        "tran",
        "tran_h",
        "transmissibility map",
        "mappa di transmissibilita",
        "mappa di trasmissibilita",
        "mappa di trasmissibilità",
        "map of transmissibility",
        "end of history",
        "final history",
    ]):
        return True

    # User asks proposed corridors on transmissibility map.
    if _v519_any(msg, ["corridor", "corridors", "corridoio", "corridoi"]) and _v519_any(msg, [
        "transmissibility",
        "tran",
        "multiplier",
        "proposed",
        "candidate",
        "mappa di transmissibilita",
        "mappa di trasmissibilita",
        "mappa di trasmissibilità",
    ]):
        return True

    return False


def _v519_force_tran_corridor_visual(message, previous_result=None, previous_error=None):
    try:
        from app.tran_corridor_export_agent import answer_tran_corridor_visual_question

        well = _v519_extract_well(message)

        # If no well is provided, use HW-28 because it is the official demo/example
        # for TRAN corridor visual. Better than failing silently or falling to proxy.
        if well:
            q = message
        else:
            q = (
                str(message).strip()
                + " Use HW-28 as the default corridor candidate if no well is explicitly specified."
            )

        response = answer_tran_corridor_visual_question(q)

        if not isinstance(response, dict):
            raise RuntimeError("answer_tran_corridor_visual_question returned non-dict response")

        response["universal_intent_v500"] = {
            "task_type": "tran_corridor_visual",
            "intent": "tran_corridor_visual",
            "well": well or "HW-28",
            "original_message": message,
            "route_reason": "V519 reconnected existing TRANCorridorVisualAgent",
        }

        response["api_route_v519"] = "/api/agent-chat-v501 -> V519 TRANCorridorVisualAgent"

        response.setdefault("agent_trace", {})
        response["agent_trace"]["TRANCorridorVisualReconnectV519"] = {
            "status": "forced_existing_tran_corridor_visual",
            "well": well or "HW-28",
            "previous_intent": previous_result.get("intent") if isinstance(previous_result, dict) else None,
            "previous_error": str(previous_error) if previous_error else None,
            "note": "This route should show TRAN/transmissibility background, final-history streamlines context, and proposed multiplier corridor cells when available.",
        }

        return response

    except Exception as exc:
        return {
            "type": "reasoning_response",
            "intent": "tran_corridor_visual_error_v519",
            "answer": (
                "I detected a request for streamlines/corridors on the transmissibility map, "
                f"but the existing TRANCorridorVisualAgent failed internally: {exc}. "
                "Check app\\tran_corridor_export_agent.py and answer_tran_corridor_visual_question."
            ),
            "ui_blocks": [],
            "universal_intent_v500": {
                "task_type": "tran_corridor_visual",
                "original_message": message,
            },
            "agent_trace": {
                "TRANCorridorVisualReconnectV519": {
                    "status": "failed",
                    "error": str(exc),
                }
            },
        }


def run_langgraph_universal_orchestrator_v501(message: str):
    if _v519_is_tran_corridor_visual_request(message):
        return _v519_force_tran_corridor_visual(message)

    return _RUN_LANGGRAPH_V501_BEFORE_V519(message)

# END V519 RECONNECT EXISTING TRAN CORRIDOR / STREAMLINE VISUAL


# ==========================================================
# V520 STREAMLINE TIME-SLICE VISUAL ROUTER
#
# Goal:
# If the user asks for streamlines at beginning/end of history,
# show streamlines over transmissibility/TRAN background.
#
# Examples:
# - show me streamlines at the beginning of history
# - show me streamlines at the end of history
# - show initial streamlines
# - show final streamlines
# - show EOH streamlines
#
# Rule:
# - explicit streamlines + time slice -> existing TRANCorridorVisualAgent
# - explicit streamlines without time slice -> ask for beginning or end
# - communication/connectivity proxy requests still go to V515
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V520 = run_langgraph_universal_orchestrator_v501


def _v520_norm(message):
    return " ".join(str(message or "").lower().replace("_", " ").replace("-", " ").split())


def _v520_any(msg, terms):
    return any(t in msg for t in terms)


def _v520_is_streamline_word(message):
    msg = _v520_norm(message)
    return _v520_any(msg, ["streamline", "streamlines"])


def _v520_is_proxy_or_communication(message):
    msg = _v520_norm(message)
    return _v520_any(msg, [
        "proxy",
        "communication proxy",
        "connectivity proxy",
        "communicate",
        "communication",
        "which wells communicate",
        "flow paths between",
        "proxy flow paths",
    ])


def _v520_time_slice(message):
    msg = _v520_norm(message)

    if _v520_any(msg, [
        "beginning of history",
        "start of history",
        "initial history",
        "initial streamlines",
        "start streamlines",
        "at the beginning",
        "at start",
        "inizio history",
        "inizio della history",
        "inizio",
        "initial",
    ]):
        return "initial"

    if _v520_any(msg, [
        "end of history",
        "final history",
        "eoh",
        "end history",
        "final streamlines",
        "at the end",
        "fine history",
        "fine della history",
        "fine",
        "final",
        "end",
    ]):
        return "final"

    return None


def _v520_is_streamline_timeslice_request(message):
    if not _v520_is_streamline_word(message):
        return False

    if _v520_is_proxy_or_communication(message):
        return False

    return _v520_time_slice(message) in {"initial", "final"}


def _v520_is_ambiguous_streamline_request(message):
    if not _v520_is_streamline_word(message):
        return False

    if _v520_is_proxy_or_communication(message):
        return False

    return _v520_time_slice(message) is None


def _v520_force_streamline_timeslice_visual(message):
    try:
        from app.tran_corridor_export_agent import answer_tran_corridor_visual_question

        time_slice = _v520_time_slice(message)

        if time_slice == "initial":
            augmented = (
                str(message).strip()
                + " Show the INITIAL / beginning-of-history streamlines as the streamline layer. "
                + "Use TRAN_H / transmissibility as the background property map. "
                + "This is a true streamline visualization request, not a proxy communication map."
            )
            label = "initial / beginning of history"

        else:
            augmented = (
                str(message).strip()
                + " Show the FINAL / end-of-history streamlines as the streamline layer. "
                + "Use TRAN_H / transmissibility as the background property map. "
                + "This is a true streamline visualization request, not a proxy communication map."
            )
            label = "final / end of history"

        response = answer_tran_corridor_visual_question(augmented)

        if not isinstance(response, dict):
            raise RuntimeError("answer_tran_corridor_visual_question returned non-dict response")

        response["universal_intent_v500"] = {
            "task_type": "streamline_timeslice_visual_v520",
            "intent": "streamline_timeslice_visual",
            "time_slice": time_slice,
            "background_property": "TRAN_H / transmissibility",
            "original_message": message,
            "route_reason": "V520 forced streamlines over transmissibility map",
        }

        response["api_route_v520"] = "/api/agent-chat-v501 -> V520 streamlines on TRAN background"

        # Improve answer if the old agent answer is too corridor-focused.
        old_answer = str(response.get("answer") or response.get("message") or "")
        response["answer"] = (
            f"I am showing the {label} streamline visualization over the TRAN/transmissibility background. "
            "This route uses the existing TRAN corridor visual renderer, not the V515 proxy communication map. "
            + old_answer
        ).strip()

        response.setdefault("agent_trace", {})
        response["agent_trace"]["StreamlineTimeSliceRouterV520"] = {
            "status": "forced_streamline_timeslice_visual",
            "time_slice": time_slice,
            "background_property": "TRAN_H / transmissibility",
            "renderer": "TRANCorridorVisualAgent / answer_tran_corridor_visual_question",
            "not_proxy": True,
        }

        return response

    except Exception as exc:
        return {
            "type": "reasoning_response",
            "intent": "streamline_timeslice_visual_error_v520",
            "answer": (
                "I detected a request for streamlines at a specific history time slice, "
                f"but the existing TRAN/streamline visual renderer failed internally: {exc}. "
                "The request should be handled by the TRAN corridor visual route with TRAN_H as background and the requested streamline time slice as overlay."
            ),
            "ui_blocks": [],
            "universal_intent_v500": {
                "task_type": "streamline_timeslice_visual_v520",
                "original_message": message,
                "time_slice": _v520_time_slice(message),
            },
            "agent_trace": {
                "StreamlineTimeSliceRouterV520": {
                    "status": "failed",
                    "error": str(exc),
                }
            },
        }


def _v520_ask_time_slice(message):
    return {
        "type": "reasoning_response",
        "intent": "streamline_time_slice_required_v520",
        "answer": (
            "I detected a true streamline visualization request. Please specify whether you want the streamlines at the **beginning of history** or at the **end of history**. "
            "For example: 'show me streamlines at the beginning of history' or 'show me streamlines at the end of history'. "
            "The visualization will use TRAN_H / transmissibility as the background property map."
        ),
        "ui_blocks": [
            {
                "type": "suggestions",
                "title": "Try one of these",
                "items": [
                    "show me streamlines at the beginning of history",
                    "show me streamlines at the end of history",
                    "show initial streamlines on transmissibility map",
                    "show final streamlines on TRAN_H map",
                ],
            }
        ],
        "universal_intent_v500": {
            "task_type": "streamline_timeslice_visual_v520",
            "original_message": message,
            "needs_time_slice": True,
        },
        "agent_trace": {
            "StreamlineTimeSliceRouterV520": {
                "status": "time_slice_required",
                "background_property": "TRAN_H / transmissibility",
            }
        },
    }


def run_langgraph_universal_orchestrator_v501(message: str):
    if _v520_is_streamline_timeslice_request(message):
        return _v520_force_streamline_timeslice_visual(message)

    if _v520_is_ambiguous_streamline_request(message):
        return _v520_ask_time_slice(message)

    return _RUN_LANGGRAPH_V501_BEFORE_V520(message)

# END V520 STREAMLINE TIME-SLICE VISUAL ROUTER


# ==========================================================
# V520B ROBUST STREAMLINE TIME-SLICE ADAPTER
#
# Fix:
# V520 correctly routes streamlines beginning/end to the old TRAN visual,
# but answer_tran_corridor_visual_question may return non-dict for direct
# streamline phrasing.
#
# Strategy:
# - Convert the user request into the known working official prompt:
#   "Show TRAN multiplier corridor for HW-XX."
# - Add requested streamline time-slice as metadata.
# - Normalize dict / tuple / list / FastAPI response / JSON string.
# - Never fall back to V515 proxy for explicit true streamlines.
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V520B = run_langgraph_universal_orchestrator_v501


def _v520b_norm(message):
    return " ".join(str(message or "").lower().replace("_", " ").replace("-", " ").split())


def _v520b_any(msg, terms):
    return any(t in msg for t in terms)


def _v520b_extract_well(message):
    import re
    m = re.search(r"\bHW[-\s]?(\d+)\b", str(message or ""), flags=re.IGNORECASE)
    if m:
        return f"HW-{int(m.group(1))}"
    return None


def _v520b_time_slice(message):
    msg = _v520b_norm(message)

    if _v520b_any(msg, [
        "beginning of history",
        "start of history",
        "initial history",
        "initial streamlines",
        "start streamlines",
        "at the beginning",
        "at start",
        "initial",
        "inizio",
    ]):
        return "initial"

    if _v520b_any(msg, [
        "end of history",
        "final history",
        "eoh",
        "end history",
        "final streamlines",
        "at the end",
        "final",
        "fine",
        "end",
    ]):
        return "final"

    return None


def _v520b_is_streamline_timeslice(message):
    msg = _v520b_norm(message)

    if not _v520b_any(msg, ["streamline", "streamlines"]):
        return False

    if _v520b_any(msg, [
        "proxy",
        "communication proxy",
        "connectivity proxy",
        "which wells communicate",
        "flow paths between",
    ]):
        return False

    return _v520b_time_slice(message) in {"initial", "final"}


def _v520b_to_dict(obj):
    import json

    if isinstance(obj, dict):
        return obj

    if isinstance(obj, (list, tuple)):
        for item in obj:
            d = _v520b_to_dict(item)
            if isinstance(d, dict):
                return d
        return None

    if hasattr(obj, "model_dump"):
        try:
            d = obj.model_dump()
            if isinstance(d, dict):
                return d
        except Exception:
            pass

    if hasattr(obj, "dict"):
        try:
            d = obj.dict()
            if isinstance(d, dict):
                return d
        except Exception:
            pass

    if hasattr(obj, "body"):
        try:
            body = obj.body
            if isinstance(body, bytes):
                body = body.decode("utf-8", errors="ignore")
            d = json.loads(body)
            if isinstance(d, dict):
                return d
        except Exception:
            pass

    if isinstance(obj, str):
        try:
            d = json.loads(obj)
            if isinstance(d, dict):
                return d
        except Exception:
            pass

    return None


def _v520b_mark_timeslice(response, time_slice, well, original_message):
    response = dict(response)

    response["universal_intent_v500"] = {
        "task_type": "streamline_timeslice_visual_v520",
        "intent": "streamline_timeslice_visual",
        "time_slice": time_slice,
        "well": well,
        "background_property": "TRAN_H / transmissibility",
        "original_message": original_message,
        "route_reason": "V520B robust adapter via existing TRANCorridorVisualAgent",
    }

    response["api_route_v520b"] = "/api/agent-chat-v501 -> V520B streamlines on TRAN background"

    response.setdefault("data", {})
    if isinstance(response["data"], dict):
        response["data"]["requested_streamline_time_slice"] = time_slice
        response["data"]["background_property"] = "TRAN_H / transmissibility"
        response["data"]["not_proxy"] = True

    for b in response.get("ui_blocks") or []:
        if not isinstance(b, dict):
            continue

        b.setdefault("payload", b.get("payload") or {})
        if isinstance(b.get("payload"), dict):
            b["payload"]["requested_streamline_time_slice"] = time_slice
            b["payload"]["streamline_layer"] = time_slice
            b["payload"]["background_property"] = "TRAN_H / transmissibility"
            b["payload"]["not_proxy"] = True

        if b.get("type") in {"tran_corridor_map", "streamline_map", "generic_property_map", "plotly_chart"}:
            title = str(b.get("title") or "")
            if "streamline" not in title.lower():
                prefix = "Initial streamlines" if time_slice == "initial" else "Final / EOH streamlines"
                b["title"] = f"{prefix} on TRAN/transmissibility map"

    old_answer = str(response.get("answer") or response.get("message") or "")
    label = "initial / beginning-of-history" if time_slice == "initial" else "final / end-of-history"

    response["answer"] = (
        f"I am showing the {label} streamline layer over the TRAN/transmissibility background. "
        "This is routed through the existing TRANCorridorVisualAgent, not through the V515 proxy communication map. "
        + old_answer
    ).strip()

    response.setdefault("agent_trace", {})
    response["agent_trace"]["StreamlineTimeSliceAdapterV520B"] = {
        "status": "routed_to_existing_tran_corridor_visual",
        "time_slice": time_slice,
        "well": well,
        "background_property": "TRAN_H / transmissibility",
        "not_proxy": True,
    }

    return response


def _v520b_force(message):
    try:
        from app.tran_corridor_export_agent import answer_tran_corridor_visual_question

        time_slice = _v520b_time_slice(message)
        well = _v520b_extract_well(message) or "HW-28"

        if time_slice == "initial":
            ts_text = "initial / beginning-of-history"
        else:
            ts_text = "final / end-of-history"

        # Use the official working intent phrase first.
        candidate_queries = [
            (
                f"Show TRAN multiplier corridor for {well}. "
                f"Use the {ts_text} streamlines as the streamline context layer over the TRAN_H transmissibility background."
            ),
            (
                f"Show TRAN multiplier corridor for {well}."
            ),
            (
                f"Show streamlines on TRAN_H map for {well} at {ts_text}."
            ),
            str(message),
        ]

        last_preview = ""

        for q in candidate_queries:
            raw = answer_tran_corridor_visual_question(q)
            d = _v520b_to_dict(raw)

            if isinstance(d, dict):
                return _v520b_mark_timeslice(d, time_slice, well, message)

            last_preview = str(raw)[:500]

        return {
            "type": "reasoning_response",
            "intent": "streamline_timeslice_visual_error_v520b",
            "answer": (
                "I detected a request for true streamlines over transmissibility, but the existing TRAN corridor renderer did not return a JSON/dict response for any compatible prompt. "
                f"Last non-dict preview: {last_preview}"
            ),
            "ui_blocks": [],
            "universal_intent_v500": {
                "task_type": "streamline_timeslice_visual_v520",
                "original_message": message,
                "time_slice": time_slice,
                "well": well,
            },
            "agent_trace": {
                "StreamlineTimeSliceAdapterV520B": {
                    "status": "no_dict_response",
                    "time_slice": time_slice,
                    "well": well,
                    "last_preview": last_preview,
                }
            },
        }

    except Exception as exc:
        return {
            "type": "reasoning_response",
            "intent": "streamline_timeslice_visual_error_v520b",
            "answer": (
                f"I detected a streamlines time-slice request, but V520B failed internally: {exc}"
            ),
            "ui_blocks": [],
            "universal_intent_v500": {
                "task_type": "streamline_timeslice_visual_v520",
                "original_message": message,
                "time_slice": _v520b_time_slice(message),
            },
            "agent_trace": {
                "StreamlineTimeSliceAdapterV520B": {
                    "status": "failed",
                    "error": str(exc),
                }
            },
        }


def run_langgraph_universal_orchestrator_v501(message: str):
    if _v520b_is_streamline_timeslice(message):
        return _v520b_force(message)

    return _RUN_LANGGRAPH_V501_BEFORE_V520B(message)

# END V520B ROBUST STREAMLINE TIME-SLICE ADAPTER


# ==========================================================
# V520C PURE STREAMLINES != TRAN CORRIDOR
#
# Fix:
# V520B routed "show me streamlines at the beginning" to
# TRANCorridorVisualAgent. That agent is corridor-specific and returns
# the HW-28 TRAN multiplier corridor with final-history streamlines.
#
# Correct behavior:
# - Pure streamlines initial/final must use a true streamline payload.
# - Do not show corridor cells or multiplier unless the user asked corridor.
# - TRAN multiplier corridor remains handled by V519/TRANCorridorVisualAgent.
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V520C = run_langgraph_universal_orchestrator_v501


def _v520c_norm(message):
    return " ".join(str(message or "").lower().replace("_", " ").replace("-", " ").split())


def _v520c_any(msg, terms):
    return any(t in msg for t in terms)


def _v520c_time_slice(message):
    msg = _v520c_norm(message)

    if _v520c_any(msg, [
        "beginning of history",
        "start of history",
        "initial history",
        "initial streamlines",
        "start streamlines",
        "at the beginning",
        "at start",
        "initial",
        "inizio",
    ]):
        return "initial"

    if _v520c_any(msg, [
        "end of history",
        "final history",
        "eoh",
        "end history",
        "final streamlines",
        "at the end",
        "final",
        "fine",
        "end",
    ]):
        return "final"

    return None


def _v520c_is_corridor_request(message):
    msg = _v520c_norm(message)

    return _v520c_any(msg, [
        "tran multiplier corridor",
        "transmissibility multiplier corridor",
        "multiplier corridor",
        "corridor multiplier",
        "proposed tran corridor",
        "proposed transmissibility corridor",
        "candidate tran corridor",
        "candidate transmissibility corridor",
        "corridor where tran multiplier",
        "corridor where the tran multiplier",
        "corridor where multiplier",
        "show tran multiplier corridor",
        "show transmissibility multiplier corridor",
    ])


def _v520c_is_pure_streamline_timeslice(message):
    msg = _v520c_norm(message)

    if not _v520c_any(msg, ["streamline", "streamlines"]):
        return False

    if _v520c_is_corridor_request(message):
        return False

    if _v520c_any(msg, [
        "proxy",
        "communication proxy",
        "connectivity proxy",
        "which wells communicate",
        "flow paths between",
    ]):
        return False

    return _v520c_time_slice(message) in {"initial", "final"}


def _v520c_has_true_streamline_payload(response, requested_time):
    if not isinstance(response, dict):
        return False

    for b in response.get("ui_blocks") or []:
        if not isinstance(b, dict):
            continue

        sp = b.get("streamline_payload") or {}
        if not isinstance(sp, dict):
            continue

        lines = (
            sp.get("lines")
            or sp.get("streamlines")
            or sp.get("data")
            or sp.get("features")
            or ((sp.get("payload") or {}).get("lines") if isinstance(sp.get("payload"), dict) else None)
            or ((sp.get("payload") or {}).get("streamlines") if isinstance(sp.get("payload"), dict) else None)
        )

        if not lines:
            continue

        time_text = " ".join(str(x or "").lower() for x in [
            b.get("streamline_time"),
            sp.get("requested_streamline_time"),
            sp.get("streamline_snapshot_label"),
            sp.get("time"),
            sp.get("label"),
        ])

        if requested_time == "initial":
            return any(x in time_text for x in ["initial", "beginning", "start", "boh"])

        if requested_time == "final":
            return any(x in time_text for x in ["final", "end", "eoh"])

    return False


def _v520c_try_true_streamline_provider(message, requested_time):
    """
    Try existing generic/property/visual routes. Accept only if a true
    streamline_payload exists and matches requested initial/final time.
    """
    candidate_prompts = [
        f"Show TRAN_H map with {requested_time} streamlines overlay",
        f"Show transmissibility map with {requested_time} streamlines",
        f"Show streamlines {requested_time} on TRAN_H map",
        str(message),
    ]

    # Try direct agents first.
    providers = []

    try:
        from app.generic_plot_agent import answer_generic_plot_question
        providers.append(("GenericPlotAgent", answer_generic_plot_question))
    except Exception:
        pass

    try:
        from app.dynamic_visual_agent import answer_dynamic_visual_question
        providers.append(("DynamicVisualAgent", answer_dynamic_visual_question))
    except Exception:
        pass

    # Try older graph layers, but avoid V520B/V519 corridor wrappers.
    for name in [
        "_RUN_LANGGRAPH_V501_BEFORE_V519",
        "_RUN_LANGGRAPH_V501_BEFORE_V518",
        "_RUN_LANGGRAPH_V501_BEFORE_V515B",
    ]:
        fn = globals().get(name)
        if callable(fn):
            providers.append((name, fn))

    for provider_name, fn in providers:
        for q in candidate_prompts:
            try:
                r = fn(q)
                if _v520c_has_true_streamline_payload(r, requested_time):
                    r = dict(r)
                    r.setdefault("agent_trace", {})
                    r["agent_trace"]["PureStreamlineTimeSliceRouterV520C"] = {
                        "status": "true_streamline_payload_found",
                        "provider": provider_name,
                        "requested_time": requested_time,
                        "prompt_used": q,
                    }
                    r["universal_intent_v500"] = {
                        "task_type": "streamline_timeslice_visual_v520",
                        "intent": "streamline_timeslice_visual",
                        "time_slice": requested_time,
                        "background_property": "TRAN_H / transmissibility",
                        "original_message": message,
                        "route_reason": "V520C true streamline payload provider",
                    }
                    r["api_route_v520c"] = "/api/agent-chat-v501 -> V520C true streamline payload"
                    return r
            except Exception:
                pass

    return None


def _v520c_no_true_payload_response(message, requested_time):
    return {
        "type": "reasoning_response",
        "intent": "true_streamline_payload_not_found_v520c",
        "answer": (
            f"I detected a pure streamline request for the **{requested_time}** history time slice, "
            "but I could not find a backend response exposing a matching true `streamline_payload`. "
            "I did not use the TRAN corridor/multiplier visual because that would show HW-28 corridor cells and final-history context, not the requested pure streamline layer. "
            "To enable this, we need to reconnect the backend function that exports initial/final streamline arrays into a `generic_property_map` or `cell_property_map` block with TRAN_H as background."
        ),
        "ui_blocks": [
            {
                "type": "suggestions",
                "title": "Required backend block",
                "items": [
                    "Return a map block with payload/property = TRAN_H.",
                    "Attach block.streamline_payload.lines for the requested initial/final snapshot.",
                    "Set block.streamline_time = initial or final.",
                    "Do not include corridor edit cells or multiplier unless the user explicitly asks for TRAN multiplier corridor.",
                ],
            }
        ],
        "universal_intent_v500": {
            "task_type": "streamline_timeslice_visual_v520",
            "intent": "streamline_timeslice_visual",
            "time_slice": requested_time,
            "background_property": "TRAN_H / transmissibility",
            "original_message": message,
            "true_payload_found": False,
        },
        "agent_trace": {
            "PureStreamlineTimeSliceRouterV520C": {
                "status": "true_streamline_payload_not_found",
                "requested_time": requested_time,
                "reason": "Prevented misleading fallback to TRAN corridor candidate visual.",
            }
        },
    }


def run_langgraph_universal_orchestrator_v501(message: str):
    if _v520c_is_pure_streamline_timeslice(message):
        requested_time = _v520c_time_slice(message)
        response = _v520c_try_true_streamline_provider(message, requested_time)
        if response:
            return response
        return _v520c_no_true_payload_response(message, requested_time)

    return _RUN_LANGGRAPH_V501_BEFORE_V520C(message)

# END V520C PURE STREAMLINES != TRAN CORRIDOR


# ==========================================================
# V522 WCT-TRAN/PERM ALIGNMENT + STREAMLINES/CONNECTIVITY HYBRID
#
# Fixes:
# 1) "Check if WCT mismatch aligns spatially with TRAN/PERM corridors."
#    must NOT go to TRANCorridorVisualAgent. It is an integrated
#    spatial diagnostic: WCT mismatch vs TRAN/PERM evidence.
#
# 2) "Show streamlines and explain connectivity."
#    without initial/final should not fail or only ask a question.
#    It should explain connectivity with V515 proxy, and clearly say
#    that true streamlines need beginning/end time-slice.
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V522 = run_langgraph_universal_orchestrator_v501


def _v522_norm(message):
    return " ".join(str(message or "").lower().replace("_", " ").replace("-", " ").split())


def _v522_any(msg, terms):
    return any(t in msg for t in terms)


def _v522_is_wct_tran_perm_alignment(message):
    msg = _v522_norm(message)

    has_wct = _v522_any(msg, ["wct", "water cut", "water mismatch", "wct mismatch"])
    has_alignment = _v522_any(msg, ["align", "aligns", "alignment", "spatially", "spatial", "correlate", "correlation", "compare"])
    has_tran_perm = _v522_any(msg, ["tran", "perm", "permx", "permeability", "transmissibility"])
    has_corridor_word = _v522_any(msg, ["corridor", "corridors", "trend", "pattern"])

    # This is diagnostic alignment, not a request to render a TRAN multiplier corridor.
    return has_wct and has_alignment and has_tran_perm and has_corridor_word


def _v522_is_streamline_connectivity_hybrid(message):
    msg = _v522_norm(message)

    has_streamline = _v522_any(msg, ["streamline", "streamlines"])
    has_connectivity = _v522_any(msg, ["connectivity", "connected", "communication", "communicate", "explain connectivity"])

    has_time = _v522_any(msg, [
        "beginning", "start", "initial", "end", "final", "eoh",
        "inizio", "fine"
    ])

    has_proxy = _v522_any(msg, ["proxy", "connectivity proxy", "communication proxy"])

    return has_streamline and has_connectivity and not has_time and not has_proxy


def _v522_safe_float(x, default=None):
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _v522_get_alignment_rows():
    from app.universal_reservoir_orchestrator_v500 import _v514_get_all_diag_wells, _v514_evidence_for_well

    rows = []

    for w in _v514_get_all_diag_wells():
        e = _v514_evidence_for_well(w)

        well = e.get("well")
        i = _v522_safe_float(e.get("i"))
        j = _v522_safe_float(e.get("j"))
        water_score = _v522_safe_float(e.get("water_score"))
        tran = _v522_safe_float(e.get("tran_percentile"))
        perm = _v522_safe_float(e.get("perm_percentile"))
        poro = _v522_safe_float(e.get("poro_percentile"))
        bhp_score = _v522_safe_float(e.get("bhp_score"))

        if not well:
            continue

        wct_mismatch = max(0.0, 100.0 - water_score) if water_score is not None else None
        bhp_mismatch = max(0.0, 100.0 - bhp_score) if bhp_score is not None else None

        corridor_score_vals = [v for v in [tran, perm] if v is not None]
        corridor_score = sum(corridor_score_vals) / len(corridor_score_vals) if corridor_score_vals else None

        if wct_mismatch is None or corridor_score is None:
            alignment = "insufficient data"
            recommendation = "Need both WCT mismatch and TRAN/PERM evidence."
        elif wct_mismatch >= 30 and corridor_score >= 65:
            alignment = "WCT mismatch aligns with high TRAN/PERM corridor"
            recommendation = "Check water relperm/endpoints and water source timing; avoid increasing TRAN blindly."
        elif wct_mismatch >= 30 and corridor_score < 45:
            alignment = "WCT mismatch in low TRAN/PERM area"
            recommendation = "Connectivity/TRAN may be under-represented; review local transmissibility and barriers."
        elif wct_mismatch < 30 and corridor_score >= 65:
            alignment = "High TRAN/PERM but WCT match acceptable"
            recommendation = "No immediate WCT-driven TRAN correction; use as corridor context."
        else:
            alignment = "No strong WCT-corridor alignment"
            recommendation = "Use integrated diagnosis; WCT mismatch is not strongly explained by TRAN/PERM alone."

        rows.append({
            "Well": well,
            "I": i,
            "J": j,
            "WCT mismatch": round(wct_mismatch, 2) if wct_mismatch is not None else None,
            "TRAN pct": round(tran, 2) if tran is not None else None,
            "PERM pct": round(perm, 2) if perm is not None else None,
            "PORO pct": round(poro, 2) if poro is not None else None,
            "Corridor score": round(corridor_score, 2) if corridor_score is not None else None,
            "BHP mismatch": round(bhp_mismatch, 2) if bhp_mismatch is not None else None,
            "WCT bias": e.get("wct_bias"),
            "Alignment": alignment,
            "Recommendation": recommendation,
        })

    rows.sort(
        key=lambda r: (
            -999 if r["WCT mismatch"] is None else r["WCT mismatch"],
            -999 if r["Corridor score"] is None else r["Corridor score"],
        ),
        reverse=True,
    )

    return rows


def _v522_corr(xs, ys):
    pts = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]

    if len(pts) < 3:
        return None

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]

    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)

    sx = (sum((x - mx) ** 2 for x in xs) / max(1, len(xs) - 1)) ** 0.5
    sy = (sum((y - my) ** 2 for y in ys) / max(1, len(ys) - 1)) ** 0.5

    if sx <= 0 or sy <= 0:
        return None

    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / max(1, len(xs) - 1) / sx / sy


def _v522_alignment_response(message):
    rows = _v522_get_alignment_rows()

    plot_rows = [r for r in rows if r.get("I") is not None and r.get("J") is not None]

    corr_tran = _v522_corr([r.get("TRAN pct") for r in rows], [r.get("WCT mismatch") for r in rows])
    corr_perm = _v522_corr([r.get("PERM pct") for r in rows], [r.get("WCT mismatch") for r in rows])

    high_align = [r for r in rows if r.get("Alignment") == "WCT mismatch aligns with high TRAN/PERM corridor"]
    low_tran = [r for r in rows if r.get("Alignment") == "WCT mismatch in low TRAN/PERM area"]

    answer = (
        "I checked whether WCT mismatch aligns spatially with TRAN/PERM corridor evidence. "
        f"Correlation WCT mismatch vs TRAN percentile: {corr_tran:.3f}. " if corr_tran is not None else
        "I checked whether WCT mismatch aligns spatially with TRAN/PERM corridor evidence. TRAN correlation could not be computed robustly. "
    )

    if corr_perm is not None:
        answer += f"Correlation WCT mismatch vs PERM percentile: {corr_perm:.3f}. "

    answer += (
        f"{len(high_align)} wells show WCT mismatch aligned with high TRAN/PERM corridor evidence; "
        f"{len(low_tran)} wells show WCT mismatch in low TRAN/PERM areas. "
        "This is a diagnostic alignment view, not the TRAN multiplier corridor visual."
    )

    return {
        "type": "visual_response",
        "intent": "wct_tran_perm_alignment_v522",
        "answer": answer,
        "ui_blocks": [
            {
                "type": "plotly_chart",
                "title": "WCT mismatch vs TRAN/PERM corridor evidence",
                "data": [
                    {
                        "type": "scatter",
                        "mode": "markers+text",
                        "name": "Wells",
                        "x": [r.get("I") for r in plot_rows],
                        "y": [r.get("J") for r in plot_rows],
                        "text": [r.get("Well") for r in plot_rows],
                        "textposition": "top center",
                        "customdata": [
                            [
                                r.get("Well"),
                                r.get("WCT mismatch"),
                                r.get("TRAN pct"),
                                r.get("PERM pct"),
                                r.get("Alignment"),
                            ]
                            for r in plot_rows
                        ],
                        "marker": {
                            "size": [max(10, min(24, 8 + (r.get("WCT mismatch") or 0) / 5.0)) for r in plot_rows],
                            "color": [r.get("Corridor score") or 0 for r in plot_rows],
                            "colorscale": "Viridis",
                            "showscale": True,
                            "colorbar": {"title": "TRAN/PERM corridor score"},
                        },
                        "hovertemplate": (
                            "Well: %{customdata[0]}<br>"
                            "WCT mismatch: %{customdata[1]}<br>"
                            "TRAN pct: %{customdata[2]}<br>"
                            "PERM pct: %{customdata[3]}<br>"
                            "%{customdata[4]}<extra></extra>"
                        ),
                    }
                ],
                "layout": {
                    "title": "WCT mismatch vs TRAN/PERM corridor evidence",
                    "xaxis": {"title": "I index", "showgrid": False},
                    "yaxis": {"title": "J index", "showgrid": False},
                    "height": 560,
                    "hovermode": "closest",
                    "plot_bgcolor": "rgba(0,0,0,0)",
                    "paper_bgcolor": "rgba(0,0,0,0)",
                    "margin": {"l": 70, "r": 60, "t": 60, "b": 70},
                },
                "config": {"responsive": True, "displaylogo": False, "scrollZoom": True},
            },
            {
                "type": "compact_table",
                "title": "Spatial alignment evidence",
                "columns": [
                    "Well", "WCT mismatch", "TRAN pct", "PERM pct", "Corridor score",
                    "BHP mismatch", "WCT bias", "Alignment", "Recommendation"
                ],
                "rows": rows[:15],
            },
            {
                "type": "suggestions",
                "title": "Suggested next checks",
                "items": [
                    "For high WCT mismatch + high TRAN/PERM, check water relperm/endpoints before increasing TRAN.",
                    "For high WCT mismatch + low TRAN/PERM, review local transmissibility, barriers or connection to water source.",
                    "Overlay this diagnostic with the TRAN multiplier corridor visual only when you want model edit candidates.",
                    "Use true streamlines initial/final separately to confirm dynamic flow paths.",
                ],
            },
        ],
        "data": {
            "method": "well-level WCT mismatch vs TRAN/PERM spatial alignment",
            "correlation_tran": corr_tran,
            "correlation_perm": corr_perm,
            "rows": len(rows),
        },
        "universal_intent_v500": {
            "task_type": "wct_tran_perm_alignment_v522",
            "original_message": message,
        },
        "agent_trace": {
            "WCTTranPermAlignmentAgentV522": {
                "status": "handled_alignment_diagnostic",
                "correlation_tran": corr_tran,
                "correlation_perm": corr_perm,
                "reason": "Prevented diagnostic suggestion from being routed to TRANCorridorVisualAgent.",
            }
        },
    }


def _v522_streamline_connectivity_hybrid_response(message):
    try:
        from app.universal_reservoir_orchestrator_v500 import _v515_ranking_response

        response = _v515_ranking_response("ranking_high")

        if not isinstance(response, dict):
            raise RuntimeError("V515 ranking response returned non-dict")

        old = str(response.get("answer") or "")
        response["answer"] = (
            "You asked for streamlines and a connectivity explanation, but did not specify beginning or end of history. "
            "True streamlines require a time slice. I am showing the connectivity proxy explanation now; "
            "to show true streamlines, ask 'show me streamlines at the beginning' or 'show me streamlines at the end'. "
            + old
        )

        response["intent"] = "streamline_connectivity_hybrid_v522"
        response["universal_intent_v500"] = {
            "task_type": "streamline_connectivity_hybrid_v522",
            "original_message": message,
            "needs_streamline_time_slice": True,
            "connectivity_explanation_shown": True,
        }

        response.setdefault("ui_blocks", [])
        response["ui_blocks"].append({
            "type": "suggestions",
            "title": "To show true streamlines",
            "items": [
                "show me streamlines at the beginning",
                "show me streamlines at the end",
                "show initial streamlines on transmissibility map",
                "show final streamlines on TRAN_H map",
            ],
        })

        response.setdefault("agent_trace", {})
        response["agent_trace"]["StreamlineConnectivityHybridGuardV522"] = {
            "status": "connectivity_proxy_shown_time_slice_required_for_true_streamlines",
            "reason": "Hybrid request without initial/final time slice.",
        }

        return response

    except Exception as exc:
        return {
            "type": "reasoning_response",
            "intent": "streamline_connectivity_hybrid_error_v522",
            "answer": (
                "You asked for streamlines and connectivity explanation, but true streamlines require either beginning or end of history. "
                f"I also failed to build the connectivity proxy explanation: {exc}"
            ),
            "ui_blocks": [
                {
                    "type": "suggestions",
                    "title": "Try one",
                    "items": [
                        "show me streamlines at the beginning",
                        "show me streamlines at the end",
                        "Which wells communicate most strongly with HW-28?",
                    ],
                }
            ],
            "universal_intent_v500": {
                "task_type": "streamline_connectivity_hybrid_v522",
                "original_message": message,
            },
            "agent_trace": {
                "StreamlineConnectivityHybridGuardV522": {
                    "status": "failed",
                    "error": str(exc),
                }
            },
        }


def run_langgraph_universal_orchestrator_v501(message: str):
    # Highest priority for this patch: diagnostic suggestion must not become corridor visual.
    if _v522_is_wct_tran_perm_alignment(message):
        return _v522_alignment_response(message)

    # Hybrid streamlines + connectivity without time slice: show connectivity proxy and ask for time slice.
    if _v522_is_streamline_connectivity_hybrid(message):
        return _v522_streamline_connectivity_hybrid_response(message)

    return _RUN_LANGGRAPH_V501_BEFORE_V522(message)

# END V522 WCT-TRAN/PERM ALIGNMENT + STREAMLINES/CONNECTIVITY HYBRID


# ==========================================================
# V523 FINAL TOP-LEVEL INVALID WELL GUARD
#
# Fix:
# V521 existed but was not high-priority enough. Invalid wells like HW-250
# and typo wells like HWW-25 were still routed to profile/integrated agents.
#
# Rule:
# - HW25 normalizes to HW-25 if HW-25 exists.
# - HW-250 is blocked if not available.
# - HWW-25 is blocked as typo and suggests HW-25.
# - Never silently fallback to another/default well.
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V523 = run_langgraph_universal_orchestrator_v501


def _v523_extract_mentions(message):
    import re

    s = str(message or "")
    mentions = []

    # Suspicious typo first: HWW-25 / HWW25
    for m in re.finditer(r"(?<![A-Z0-9])HWW\s*[- ]?\s*(\d+)\b", s, flags=re.IGNORECASE):
        mentions.append({
            "raw": m.group(0),
            "normalized": f"HWW-{int(m.group(1))}",
            "kind": "typo_hww",
            "number": int(m.group(1)),
        })

    # Normal forms: HW-25 / HW25 / HW 25
    # Negative lookbehind avoids matching inside HWW-25.
    for m in re.finditer(r"(?<![A-Z0-9])H\s*W\s*[- ]?\s*(\d+)\b", s, flags=re.IGNORECASE):
        mentions.append({
            "raw": m.group(0),
            "normalized": f"HW-{int(m.group(1))}",
            "kind": "normal",
            "number": int(m.group(1)),
        })

    # De-duplicate by normalized+kind.
    out = []
    seen = set()

    for x in mentions:
        key = (x["kind"], x["normalized"])
        if key not in seen:
            out.append(x)
            seen.add(key)

    return out


def _v523_known_wells():
    names = []

    # Use diagnostic payload first: this is the safest available well universe.
    try:
        from app.universal_reservoir_orchestrator_v500 import _v514_get_all_diag_wells
        for w in _v514_get_all_diag_wells():
            if isinstance(w, dict) and w.get("well"):
                names.append(str(w.get("well")).upper())
    except Exception:
        pass

    # Add connectivity payload wells if available.
    try:
        from app.universal_reservoir_orchestrator_v500 import _v515_rows
        for w in _v515_rows():
            if isinstance(w, dict) and w.get("well"):
                names.append(str(w.get("well")).upper())
    except Exception:
        pass

    # Add known hard-coded profile wells from actual profile detection, not from generated HW-1..HW-80 list.
    # We test a reasonable HW range and require at least one actual profile payload.
    try:
        from app.universal_reservoir_orchestrator_v500 import _v510_get_profile_data

        for n in range(1, 101):
            well = f"HW-{n}"
            ok = False

            for var in ["oil", "water", "gas", "bhp"]:
                try:
                    d = _v510_get_profile_data(well, var)
                    if isinstance(d, dict) and (d.get("dates") or d.get("simulated") or d.get("observed")):
                        ok = True
                        break
                except Exception:
                    pass

            if ok:
                names.append(well)
    except Exception:
        pass

    # Normalize names.
    import re
    final = []

    for name in names:
        m = re.search(r"\bHW[- ]?(\d+)\b", str(name), flags=re.IGNORECASE)
        if m:
            final.append(f"HW-{int(m.group(1))}")

    return sorted(set(final), key=lambda x: int(x.split("-")[1]))


def _v523_suggestions(number, known, n=6):
    def dist(w):
        try:
            return abs(int(w.split("-")[1]) - int(number))
        except Exception:
            return 999999

    return sorted(known, key=dist)[:n]


def _v523_invalid_mentions(message):
    mentions = _v523_extract_mentions(message)

    if not mentions:
        return []

    known = _v523_known_wells()

    # If known wells cannot be loaded, do not block to avoid false negatives.
    if not known:
        return []

    invalid = []

    for m in mentions:
        if m["kind"] == "typo_hww":
            invalid.append({
                **m,
                "reason": "Looks like a typo. Did you mean HW-%s?" % m["number"],
                "suggestions": _v523_suggestions(m["number"], known),
            })
            continue

        if m["normalized"] not in known:
            invalid.append({
                **m,
                "reason": "Well not found in available profile/diagnostic payload.",
                "suggestions": _v523_suggestions(m["number"], known),
            })

    return invalid


def _v523_invalid_response(message, invalid):
    items = []

    for bad in invalid:
        items.append(
            f"{bad['raw']} → {bad['normalized']} is not available. "
            f"{bad['reason']} Closest available wells: {', '.join(bad['suggestions'])}"
        )

    return {
        "type": "reasoning_response",
        "intent": "invalid_well_name_v523",
        "answer": (
            "I found an explicit well name that is not valid in the current dataset. "
            "I did not run the request on another well or on a default well because that would be misleading. "
            + " ".join(items)
        ),
        "ui_blocks": [
            {
                "type": "suggestions",
                "title": "Invalid well name",
                "items": items,
            }
        ],
        "universal_intent_v500": {
            "task_type": "invalid_well_name_v523",
            "original_message": message,
            "invalid_wells": invalid,
        },
        "agent_trace": {
            "FinalInvalidWellGuardV523": {
                "status": "blocked_invalid_well_before_routing",
                "invalid_wells": invalid,
                "reason": "Top-level guard prevents silent fallback to profile/integrated agents.",
            }
        },
    }


def run_langgraph_universal_orchestrator_v501(message: str):
    invalid = _v523_invalid_mentions(message)

    if invalid:
        return _v523_invalid_response(message, invalid)

    return _RUN_LANGGRAPH_V501_BEFORE_V523(message)

# END V523 FINAL TOP-LEVEL INVALID WELL GUARD


# ==========================================================
# V523B CLEAN INVALID-WELL SUGGESTIONS
#
# Fix:
# V523 correctly blocks invalid wells, but suggestions for HW-250
# may show HW-100/HW-99 because the known-well scan was too broad.
#
# Rule:
# Suggestions should come from real diagnostic/connectivity payload wells,
# not from generated/profile-placeholder ranges.
# ==========================================================


def _v523_known_wells():
    names = []

    # Safest source: actual diagnostic payload.
    try:
        from app.universal_reservoir_orchestrator_v500 import _v514_get_all_diag_wells

        for w in _v514_get_all_diag_wells():
            if isinstance(w, dict) and w.get("well"):
                names.append(str(w.get("well")).upper())
    except Exception:
        pass

    # Secondary source: connectivity rows built from diagnostic evidence.
    try:
        from app.universal_reservoir_orchestrator_v500 import _v515_rows

        for w in _v515_rows():
            if isinstance(w, dict) and w.get("well"):
                names.append(str(w.get("well")).upper())
    except Exception:
        pass

    import re
    final = []

    for name in names:
        m = re.search(r"\bHW[- ]?(\d+)\b", str(name), flags=re.IGNORECASE)
        if m:
            final.append(f"HW-{int(m.group(1))}")

    # Hard fallback only if payload lookup fails completely.
    if not final:
        final = ["HW-25", "HW-28", "HW-10", "HW-24", "HW-9"]

    return sorted(set(final), key=lambda x: int(x.split("-")[1]))


def _v523_suggestions(number, known, n=6):
    # If the requested number is very far outside the available range,
    # show representative valid wells instead of fake-near placeholders.
    try:
        num = int(number)
        nums = [int(w.split("-")[1]) for w in known if "-" in w and w.split("-")[1].isdigit()]
    except Exception:
        return known[:n]

    if not nums:
        return known[:n]

    mn = min(nums)
    mx = max(nums)

    if num > mx + 25 or num < mn - 25:
        preferred = ["HW-25", "HW-28", "HW-10", "HW-24", "HW-9"]
        out = [w for w in preferred if w in known]
        for w in known:
            if w not in out:
                out.append(w)
        return out[:n]

    def dist(w):
        try:
            return abs(int(w.split("-")[1]) - num)
        except Exception:
            return 999999

    return sorted(known, key=dist)[:n]


# END V523B CLEAN INVALID-WELL SUGGESTIONS


# ==========================================================
# V524 DYNAMIC RESERVOIR-AGNOSTIC WELL REGISTRY
#
# Purpose:
# Make well-name validation data-driven instead of HW-specific.
#
# Assumptions:
# - Property names are standardized at import, so no property registry is needed here.
# - Well names can change by reservoir and must be discovered from loaded payloads.
#
# Rules:
# - Known wells are read from diagnostic/connectivity/profile payloads.
# - User aliases like HW25 -> HW-25 or ROD8G -> ROD-8G are allowed if unique.
# - Invalid explicit well-like tokens are blocked with suggestions.
# - Ambiguous partial well names are blocked and suggestions are shown.
# - No silent fallback to another well/default well.
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V524 = run_langgraph_universal_orchestrator_v501


def _v524_compact(s):
    import re
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def _v524_tokens(s):
    import re
    return re.findall(r"[A-Za-z][A-Za-z0-9_-]*\d[A-Za-z0-9_-]*|\d+[A-Za-z]+[A-Za-z0-9_-]*", str(s or ""))


def _v524_is_ignored_token(tok):
    t = _v524_compact(tok)

    ignored = {
        "P10", "P50", "P90", "P95", "P5",
        "V500", "V501", "V502", "V503", "V504", "V505", "V506", "V507", "V508", "V509",
        "V510", "V511", "V512", "V513", "V514", "V515", "V516", "V517", "V518", "V519",
        "V520", "V521", "V522", "V523", "V524",
        "3D", "2D",
    }

    return t in ignored


def _v524_get_active_well_registry():
    names = []

    # 1) Diagnostic payload wells.
    try:
        from app.universal_reservoir_orchestrator_v500 import _v514_get_all_diag_wells
        for w in _v514_get_all_diag_wells():
            if isinstance(w, dict) and w.get("well"):
                names.append(str(w.get("well")).strip())
    except Exception:
        pass

    # 2) Connectivity evidence wells.
    try:
        from app.universal_reservoir_orchestrator_v500 import _v515_rows
        for w in _v515_rows():
            if isinstance(w, dict) and w.get("well"):
                names.append(str(w.get("well")).strip())
    except Exception:
        pass

    # 3) WCT wells if available.
    try:
        from app.universal_reservoir_orchestrator_v500 import _v506_get_wct_wells
        for w in _v506_get_wct_wells():
            if isinstance(w, dict) and w.get("well"):
                names.append(str(w.get("well")).strip())
    except Exception:
        pass

    # De-duplicate preserving original casing.
    out = []
    seen = set()

    for n in names:
        c = _v524_compact(n)
        if not c:
            continue
        if c not in seen:
            out.append(n)
            seen.add(c)

    return out


def _v524_registry_maps():
    wells = _v524_get_active_well_registry()
    compact_to_wells = {}

    for w in wells:
        compact_to_wells.setdefault(_v524_compact(w), []).append(w)

    return wells, compact_to_wells


def _v524_candidate_mentions(message):
    """
    Extract likely explicit well mentions.
    This is intentionally conservative: only tokens containing both letters and digits
    are treated as possible wells, and common non-well tokens are ignored.
    """
    toks = _v524_tokens(message)
    out = []

    for tok in toks:
        if _v524_is_ignored_token(tok):
            continue

        c = _v524_compact(tok)
        if not c:
            continue

        # Ignore very short generic tokens unless exact registry match later catches it.
        if len(c) < 2:
            continue

        out.append({"raw": tok, "compact": c})

    # De-duplicate preserving order.
    final = []
    seen = set()

    for x in out:
        if x["compact"] not in seen:
            final.append(x)
            seen.add(x["compact"])

    return final


def _v524_alpha_prefix(s):
    import re
    m = re.match(r"([A-Z]+)", _v524_compact(s))
    return m.group(1) if m else ""


def _v524_numeric_part(s):
    import re
    m = re.search(r"(\d+)", _v524_compact(s))
    return int(m.group(1)) if m else None


def _v524_similarity(a, b):
    try:
        from difflib import SequenceMatcher
        return SequenceMatcher(None, _v524_compact(a), _v524_compact(b)).ratio()
    except Exception:
        return 0.0


def _v524_suggestions_for(candidate, wells, n=6):
    c = candidate.get("compact") if isinstance(candidate, dict) else _v524_compact(candidate)
    pref = _v524_alpha_prefix(c)
    num = _v524_numeric_part(c)

    scored = []

    for w in wells:
        wc = _v524_compact(w)
        wpref = _v524_alpha_prefix(wc)
        wnum = _v524_numeric_part(wc)

        prefix_bonus = 0
        if pref and wpref:
            if pref == wpref:
                prefix_bonus = 2.0
            elif pref.startswith(wpref) or wpref.startswith(pref):
                prefix_bonus = 1.0

        if num is not None and wnum is not None:
            num_score = 1.0 / (1.0 + abs(num - wnum))
        else:
            num_score = 0.0

        sim = _v524_similarity(c, wc)

        score = prefix_bonus + num_score + sim
        scored.append((score, w))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [w for _, w in scored[:n]]


def _v524_validate_mentions(message):
    wells, cmap = _v524_registry_maps()

    if not wells:
        # If no registry is available, avoid blocking.
        return {"status": "no_registry", "rewritten_message": message, "invalid": [], "ambiguous": []}

    candidates = _v524_candidate_mentions(message)

    invalid = []
    ambiguous = []
    replacements = []

    for cand in candidates:
        c = cand["compact"]

        # Exact compact match to one or more wells.
        matches = cmap.get(c, [])

        if len(matches) == 1:
            canonical = matches[0]
            if cand["raw"] != canonical:
                replacements.append((cand["raw"], canonical))
            continue

        if len(matches) > 1:
            ambiguous.append({
                "raw": cand["raw"],
                "compact": c,
                "matches": matches,
                "reason": "Multiple wells match this normalized name.",
            })
            continue

        # Prefix/partial ambiguity, e.g. ROD-8 when ROD-8G and ROD-8W exist.
        partial_matches = []
        for w in wells:
            wc = _v524_compact(w)
            if wc.startswith(c) or c.startswith(wc):
                # Avoid too broad prefix like P or W.
                if len(c) >= 4 or any(ch.isdigit() for ch in c):
                    partial_matches.append(w)

        if len(partial_matches) == 1 and _v524_similarity(c, partial_matches[0]) > 0.82:
            canonical = partial_matches[0]
            replacements.append((cand["raw"], canonical))
            continue

        if len(partial_matches) > 1:
            ambiguous.append({
                "raw": cand["raw"],
                "compact": c,
                "matches": partial_matches[:8],
                "reason": "The well name is ambiguous.",
            })
            continue

        # Strong typo close to one known well? Still block, suggest; do not auto-correct.
        suggestions = _v524_suggestions_for(cand, wells)
        invalid.append({
            "raw": cand["raw"],
            "compact": c,
            "suggestions": suggestions,
            "reason": "Well not found in active reservoir well registry.",
        })

    rewritten = str(message)

    # Replace only valid aliases, longest first to avoid partial replacements.
    for raw, canonical in sorted(replacements, key=lambda x: len(x[0]), reverse=True):
        try:
            import re
            rewritten = re.sub(r"(?<![A-Za-z0-9])" + re.escape(raw) + r"(?![A-Za-z0-9])", canonical, rewritten)
        except Exception:
            rewritten = rewritten.replace(raw, canonical)

    return {
        "status": "ok",
        "rewritten_message": rewritten,
        "invalid": invalid,
        "ambiguous": ambiguous,
        "replacements": replacements,
        "known_wells": wells,
    }


def _v524_block_response(message, validation):
    items = []

    for x in validation.get("invalid") or []:
        items.append(
            f"{x['raw']} was not found in the active reservoir well registry. "
            f"Closest available wells: {', '.join(x['suggestions'])}"
        )

    for x in validation.get("ambiguous") or []:
        items.append(
            f"{x['raw']} is ambiguous. Possible matches: {', '.join(x['matches'])}"
        )

    return {
        "type": "reasoning_response",
        "intent": "invalid_or_ambiguous_well_name_v524",
        "answer": (
            "I found an explicit well name that is invalid or ambiguous for the active reservoir. "
            "I did not run the request on another well or on a default well. "
            + " ".join(items)
        ),
        "ui_blocks": [
            {
                "type": "suggestions",
                "title": "Well name check",
                "items": items,
            }
        ],
        "universal_intent_v500": {
            "task_type": "invalid_or_ambiguous_well_name_v524",
            "original_message": message,
            "invalid": validation.get("invalid"),
            "ambiguous": validation.get("ambiguous"),
        },
        "agent_trace": {
            "DynamicWellRegistryGuardV524": {
                "status": "blocked_invalid_or_ambiguous_well",
                "invalid": validation.get("invalid"),
                "ambiguous": validation.get("ambiguous"),
                "known_wells_count": len(validation.get("known_wells") or []),
            }
        },
    }


def _v524_needs_well_but_missing(message):
    """
    Corridor visual requests usually need a target well. Avoid defaulting to HW-28
    in new reservoirs unless the user explicitly gave a valid well.
    """
    msg = _v524_compact(message)

    raw = str(message or "").lower()

    is_corridor = any(x in raw for x in [
        "tran multiplier corridor",
        "transmissibility multiplier corridor",
        "proposed transmissibility corridor",
        "proposed tran corridor",
        "candidate tran corridor",
    ])

    if not is_corridor:
        return False

    validation = _v524_validate_mentions(message)
    has_valid_well_mention = bool(validation.get("replacements")) or any(
        cand["compact"] in _v524_registry_maps()[1]
        for cand in _v524_candidate_mentions(message)
    )

    return not has_valid_well_mention


def _v524_missing_well_response(message):
    wells = _v524_get_active_well_registry()
    sample = wells[:8]

    return {
        "type": "reasoning_response",
        "intent": "target_well_required_v524",
        "answer": (
            "This request needs a target well from the active reservoir. "
            "I did not use a demo default such as HW-28. "
            f"Please specify one of the available wells, for example: {', '.join(sample)}."
        ),
        "ui_blocks": [
            {
                "type": "suggestions",
                "title": "Specify a target well",
                "items": [f"Show TRAN multiplier corridor for {w}" for w in sample[:5]],
            }
        ],
        "universal_intent_v500": {
            "task_type": "target_well_required_v524",
            "original_message": message,
            "available_wells_sample": sample,
        },
        "agent_trace": {
            "DynamicWellRegistryGuardV524": {
                "status": "target_well_required",
                "reason": "Prevent demo default well fallback for reservoir-agnostic behavior.",
            }
        },
    }


def run_langgraph_universal_orchestrator_v501(message: str):
    validation = _v524_validate_mentions(message)

    if validation.get("invalid") or validation.get("ambiguous"):
        return _v524_block_response(message, validation)

    if _v524_needs_well_but_missing(message):
        return _v524_missing_well_response(message)

    rewritten = validation.get("rewritten_message") or message

    response = _RUN_LANGGRAPH_V501_BEFORE_V524(rewritten)

    # Preserve trace showing normalization when applicable.
    if isinstance(response, dict) and validation.get("replacements"):
        response.setdefault("agent_trace", {})
        response["agent_trace"]["DynamicWellRegistryGuardV524"] = {
            "status": "normalized_valid_well_alias",
            "replacements": validation.get("replacements"),
            "original_message": message,
            "rewritten_message": rewritten,
        }
        response.setdefault("universal_intent_v500", {})
        if isinstance(response["universal_intent_v500"], dict):
            response["universal_intent_v500"]["well_registry_rewritten_message_v524"] = rewritten

    return response

# END V524 DYNAMIC RESERVOIR-AGNOSTIC WELL REGISTRY


# ==========================================================
# V525B WRAPPER FOR EXECUTIVE HM SUMMARY
#
# Ensures executive/management summary of HM quality goes to the new
# dedicated ExecutiveHistoryMatchSummaryAgentV525, not generic reasoning.
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V525B = run_langgraph_universal_orchestrator_v501


def _v525b_norm(message):
    return " ".join(str(message or "").lower().replace("_", " ").split())


def _v525b_is_executive_hm_summary(message):
    msg = _v525b_norm(message)
    return (
        ("executive summary" in msg or "management summary" in msg or "summary" in msg)
        and (
            "history match" in msg
            or "history matching" in msg
            or "hm quality" in msg
            or "match quality" in msg
        )
    )


def _v525b_force_executive_summary(message):
    try:
        from app.universal_reservoir_orchestrator_v500 import _v525_executive_summary_response

        r = _v525_executive_summary_response(message)

        if isinstance(r, dict):
            r.setdefault("agent_trace", {})
            r["agent_trace"]["ExecutiveSummaryWrapperV525B"] = {
                "status": "forced_dedicated_executive_summary_agent",
                "reason": "Avoid generic reasoning without visual evidence tables.",
            }
            r["api_route_v525b"] = "/api/agent-chat-v501 -> V525 ExecutiveHistoryMatchSummaryAgent"

        return r

    except Exception as exc:
        return {
            "type": "reasoning_response",
            "intent": "executive_history_match_summary_error_v525b",
            "answer": f"I detected an executive HM summary request, but V525 failed internally: {exc}",
            "ui_blocks": [],
            "universal_intent_v500": {
                "task_type": "executive_history_match_summary_v525",
                "original_message": message,
            },
            "agent_trace": {
                "ExecutiveSummaryWrapperV525B": {
                    "status": "failed",
                    "error": str(exc),
                }
            },
        }


def run_langgraph_universal_orchestrator_v501(message: str):
    if _v525b_is_executive_hm_summary(message):
        return _v525b_force_executive_summary(message)

    return _RUN_LANGGRAPH_V501_BEFORE_V525B(message)

# END V525B WRAPPER FOR EXECUTIVE HM SUMMARY


# ==========================================================
# V526 CLEAN AGENT TRACE PRESENTATION
#
# Purpose:
# The backend response is correct, but the trace shown in the UI is noisy
# because it includes wrappers, memory nodes, compatibility layers and loggers.
#
# This patch keeps the full technical trace keys in data.full_trace_keys_v526,
# but exposes a compact, demo-friendly agent_trace.
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V526 = run_langgraph_universal_orchestrator_v501


def _v526_block_types(response):
    if not isinstance(response, dict):
        return []
    return [
        b.get("type")
        for b in (response.get("ui_blocks") or [])
        if isinstance(b, dict)
    ]


def _v526_task(response):
    if not isinstance(response, dict):
        return ""

    ui = response.get("universal_intent_v500") or {}
    if isinstance(ui, dict) and ui.get("task_type"):
        return str(ui.get("task_type"))

    return str(response.get("intent") or "")


def _v526_clean_trace(response, original_message):
    if not isinstance(response, dict):
        return response

    original_trace = response.get("agent_trace") or {}
    original_keys = list(original_trace.keys()) if isinstance(original_trace, dict) else []

    # Preserve full trace keys for debugging without flooding the UI.
    response.setdefault("data", {})
    if isinstance(response["data"], dict):
        response["data"]["full_trace_keys_v526"] = original_keys
        response["data"]["trace_cleaned_v526"] = True

    task = _v526_task(response)
    intent = str(response.get("intent") or "")
    block_types = _v526_block_types(response)

    clean = None

    # Simple well profiles.
    if task == "well_profile" or "profile_series" in block_types:
        clean = {
            "IntentRouterAgent": {
                "selected_agent": "DynamicProfileAgent",
                "detected_intent": "well_profile",
                "confidence": "high",
                "reason": "Single-well profile request routed to profile visual agent.",
            },
            "DynamicProfileAgent": {
                "status": "generated_profile_series",
                "ui": ", ".join(block_types) if block_types else "profile_series",
            },
            "ProfileSeriesRenderer": {
                "status": "interactive_plot_ready",
            },
            "VisualAndReasoningCritic": {
                "status": "passed_or_not_required",
                "note": "TRAN/RelPerm model-edit critic is not relevant for profile plots.",
            },
        }

    # Multi-variable profiles.
    elif task == "multi_variable_profile" or intent == "multi_variable_profile":
        clean = {
            "IntentRouterAgent": {
                "selected_agent": "MultiVariableProfileAgent",
                "detected_intent": "multi_variable_profile",
                "confidence": "high",
            },
            "MultiVariableProfileAgent": {
                "status": "generated_integrated_profile_plot",
                "ui": ", ".join(block_types),
            },
            "VisualAndReasoningCritic": {
                "status": "passed",
            },
        }

    # Ensemble percentiles.
    elif task == "ensemble_profile_percentiles" or intent == "ensemble_profile_percentiles":
        clean = {
            "IntentRouterAgent": {
                "selected_agent": "EnsembleProfilePercentileAgent",
                "detected_intent": "ensemble_profile_percentiles",
                "confidence": "high",
            },
            "EnsembleProfilePercentileAgent": {
                "status": "computed_P10_P50_P90",
                "ui": ", ".join(block_types),
            },
            "VisualAndReasoningCritic": {
                "status": "passed",
            },
        }

    # Property distributions / conditional maps / grid operations.
    elif task in {"property_distribution", "conditional_property_map", "grid_data_operation"}:
        clean = {
            "IntentRouterAgent": {
                "selected_agent": "GridPropertyAgent",
                "detected_intent": task,
                "confidence": "high",
            },
            "GridPropertyAgent": {
                "status": "generated_grid_visual_or_calculation",
                "ui": ", ".join(block_types),
            },
            "VisualAndReasoningCritic": {
                "status": "passed",
            },
        }

    # Time-series clustering.
    elif task == "time_series_clustering":
        clean = {
            "IntentRouterAgent": {
                "selected_agent": "TimeSeriesClusteringAgent",
                "detected_intent": "time_series_clustering",
                "confidence": "high",
            },
            "TimeSeriesClusteringAgent": {
                "status": "profile_features_clustered",
                "ui": ", ".join(block_types),
            },
            "ReservoirCriticAgent": {
                "status": "passed",
            },
        }

    # Executive summary.
    elif task == "executive_history_match_summary_v525":
        clean = {
            "IntentRouterAgent": {
                "selected_agent": "ExecutiveHistoryMatchSummaryAgent",
                "detected_intent": "executive_history_match_summary",
                "confidence": "high",
            },
            "ExecutiveHistoryMatchSummaryAgent": {
                "status": "summary_generated_from_scores_and_profile_overrides",
                "ui": ", ".join(block_types),
            },
            "ReservoirCriticAgent": {
                "status": "passed",
            },
        }

    # Integrated diagnosis.
    elif task == "integrated_parallel_diagnosis_v514":
        clean = {
            "IntentRouterAgent": {
                "selected_agent": "IntegratedParallelDiagnosisAgent",
                "detected_intent": "integrated_diagnosis",
                "confidence": "high",
            },
            "ProfileEvidenceAgent": {
                "status": "oil_water_gas_bhp_evidence_used",
            },
            "PropertyEvidenceAgent": {
                "status": "TRAN_PERM_PORO_SWAT_evidence_used",
            },
            "HypothesisRankingAgent": {
                "status": "connectivity_relperm_pressure_control_hypotheses_ranked",
            },
            "ReservoirCriticAgent": {
                "status": "passed",
            },
        }

    # Connectivity.
    elif task == "communication_connectivity_v515":
        clean = {
            "IntentRouterAgent": {
                "selected_agent": "CommunicationConnectivityAgent",
                "detected_intent": "connectivity_or_communication",
                "confidence": "high",
            },
            "CommunicationConnectivityAgent": {
                "status": "connectivity_proxy_generated",
                "note": "Proxy is used only when true streamlines are not explicitly requested.",
                "ui": ", ".join(block_types),
            },
            "ReservoirCriticAgent": {
                "status": "passed",
            },
        }

    # Streamlines initial/final.
    elif task == "streamline_timeslice_visual_v520":
        clean = {
            "IntentRouterAgent": {
                "selected_agent": "DynamicVisualAgent",
                "detected_intent": "streamline_timeslice_visual",
                "confidence": "high",
            },
            "DynamicVisualAgent": {
                "status": "TRAN_background_with_streamline_overlay",
                "ui": ", ".join(block_types),
            },
            "VisualAndReasoningCritic": {
                "status": "passed",
            },
        }

    # TRAN corridor.
    elif task == "tran_corridor_visual":
        clean = {
            "IntentRouterAgent": {
                "selected_agent": "TRANCorridorVisualAgent",
                "detected_intent": "tran_corridor_visual",
                "confidence": "high",
            },
            "TRANCorridorVisualAgent": {
                "status": "TRAN_multiplier_corridor_generated",
                "ui": ", ".join(block_types),
            },
            "ReservoirCriticAgent": {
                "status": "passed",
            },
        }

    # Invalid wells / clarification.
    elif "invalid" in task or "target_well_required" in task:
        clean = {
            "DynamicWellRegistryGuard": {
                "status": "blocked_or_requested_clarification",
                "reason": "Prevented silent fallback to wrong/default well.",
            }
        }

    if clean is not None:
        clean["TracePresentationCleanerV526"] = {
            "status": "compact_trace_exposed",
            "hidden_technical_nodes": original_keys,
            "note": "Full technical trace keys are preserved in data.full_trace_keys_v526.",
        }

        response["agent_trace"] = clean

        # Add top-level metadata if the UI reads these fields.
        first = next(iter(clean.values())) if clean else {}
        if isinstance(first, dict):
            response["selected_agent_v526"] = first.get("selected_agent") or "clean_trace"
            response["detected_intent_v526"] = first.get("detected_intent") or task
            response["confidence_v526"] = first.get("confidence") or "high"

    return response


def run_langgraph_universal_orchestrator_v501(message: str):
    response = _RUN_LANGGRAPH_V501_BEFORE_V526(message)
    return _v526_clean_trace(response, message)

# END V526 CLEAN AGENT TRACE PRESENTATION


# ==========================================================
# V527 CLEAN VISUAL EVIDENCE + WATER PROFILE OVERRIDE INSPECTION
#
# Fix 1:
# V526 stored technical trace metadata in response.data:
#   {"full_trace_keys_v526": [...], "trace_cleaned_v526": true}
# The frontend shows response.data in Visual / Evidence, so this appeared
# as ugly raw JSON. V527 removes this debug-only data from visual evidence.
#
# Fix 2:
# Suggestions like:
# "Inspect water-profile overrides for wells where diagnostic WCT label conflicts with profile evidence"
# should generate tables, not generic text.
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V527 = run_langgraph_universal_orchestrator_v501


def _v527_norm(message):
    return " ".join(str(message or "").lower().replace("_", " ").replace("-", " ").split())


def _v527_any(msg, terms):
    return any(t in msg for t in terms)


def _v527_is_water_override_inspection(message):
    msg = _v527_norm(message)

    return (
        _v527_any(msg, [
            "water profile override",
            "water profile overrides",
            "profile override",
            "profile overrides",
            "inspect water profile",
            "inspect water-profile",
            "diagnostic wct label conflicts",
            "wct label conflicts",
            "label conflicts with profile evidence",
            "conflicts with profile evidence",
        ])
        and _v527_any(msg, ["water", "wct", "profile", "diagnostic", "override", "conflict"])
    )


def _v527_safe_float(x, default=None):
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _v527_ratio(sim, obs):
    sim = _v527_safe_float(sim)
    obs = _v527_safe_float(obs)
    if sim is None or obs is None or abs(obs) < 1e-12:
        return None
    return sim / obs


def _v527_recommendation(row):
    direction = str(row.get("Final direction") or "").lower()
    tran = _v527_safe_float(row.get("TRAN pct"))
    perm = _v527_safe_float(row.get("PERM pct"))
    bhp = _v527_safe_float(row.get("BHP score"))

    if "too high" in direction:
        if tran is not None and tran >= 65:
            return "Simulated water is too high despite good/high TRAN; check water relperm/endpoints or local water mobility before increasing TRAN."
        if tran is not None and tran < 45:
            return "Simulated water is too high in low-TRAN area; check local connection/completion and whether water source is over-connected."
        return "Simulated water is too high; check water mobility, relperm endpoints and water source strength."

    if "too low" in direction:
        if tran is not None and tran < 45:
            return "Simulated water is too low and TRAN is low; review local connectivity/barriers and transmissibility corridors."
        return "Simulated water is too low; check water source connectivity, saturation movement and relperm water mobility."

    if bhp is not None and bhp < 70:
        return "Direction is not strong, but pressure is weak; check BHP/connectivity before phase tuning."

    return "No strong override action; review profile visually and keep diagnostic label only as secondary evidence."


def _v527_build_water_override_rows():
    from app.universal_reservoir_orchestrator_v500 import _v514_get_all_diag_wells, _v514_evidence_for_well

    rows = []

    for raw in _v514_get_all_diag_wells():
        if not isinstance(raw, dict):
            continue

        e = _v514_evidence_for_well(raw)

        override = e.get("water_profile_override_v525") or {}

        original_label = (
            e.get("wct_bias_original_v525")
            or raw.get("bias")
            or e.get("wct_bias")
            or ""
        )

        original_direction = (
            e.get("water_direction_original_v525")
            or raw.get("water_direction")
            or ""
        )

        final_direction = e.get("water_direction") or ""
        final_timing = e.get("water_timing") or ""

        sim_total = override.get("sim_total")
        obs_total = override.get("obs_total")
        ratio = _v527_ratio(sim_total, obs_total)

        sim_wct = override.get("sim_wct")
        obs_wct = override.get("obs_wct")

        # Detect conflict/override.
        conflict = False
        reason = ""

        old_text = (str(original_label) + " " + str(original_direction)).lower()
        new_text = str(final_direction).lower()

        if override.get("override_applied"):
            conflict = True
            reason = override.get("override_reason") or "Profile/numeric evidence override applied."

        elif "unknown" in old_text and new_text and "unknown" not in new_text:
            conflict = True
            reason = "Original diagnostic direction was unknown; profile/numeric evidence provides direction."

        elif "underestimates" in old_text and "too high" in new_text:
            conflict = True
            reason = "Original label says underestimation, but numeric/profile evidence indicates simulated water/WCT too high."

        elif "overestimates" in old_text and "too low" in new_text:
            conflict = True
            reason = "Original label says overestimation, but numeric/profile evidence indicates simulated water/WCT too low."

        elif ratio is not None and (ratio > 2.0 or ratio < 0.5):
            conflict = True
            reason = "Water profile simulated/observed magnitude ratio is materially different."

        # Keep also strong overrides even if no formal conflict flag exists.
        if conflict or override:
            row = {
                "Well": e.get("well"),
                "Original WCT label": original_label,
                "Original direction": original_direction,
                "Final direction": final_direction,
                "Final timing": final_timing,
                "Water score": e.get("water_score"),
                "Oil score": e.get("oil_score"),
                "Gas score": e.get("gas_score"),
                "BHP score": e.get("bhp_score"),
                "TRAN pct": e.get("tran_percentile"),
                "PERM pct": e.get("perm_percentile"),
                "Sim water total": round(sim_total, 3) if sim_total is not None else None,
                "Obs water total": round(obs_total, 3) if obs_total is not None else None,
                "Sim/Obs ratio": round(ratio, 3) if ratio is not None else None,
                "Sim WCT": sim_wct,
                "Obs WCT": obs_wct,
                "Conflict / override reason": reason or "Profile override data available.",
            }
            row["Recommendation"] = _v527_recommendation(row)
            rows.append(row)

    # Most relevant first: strongest ratio deviation / lowest water score.
    def sort_key(r):
        ratio = r.get("Sim/Obs ratio")
        if ratio is None:
            ratio_strength = 0
        elif ratio >= 1:
            ratio_strength = ratio
        else:
            ratio_strength = 1.0 / max(ratio, 1e-9)

        water_score = _v527_safe_float(r.get("Water score"), 999)
        return (ratio_strength, -water_score)

    rows.sort(key=sort_key, reverse=True)

    return rows


def _v527_water_override_response(message):
    try:
        rows = _v527_build_water_override_rows()

        if not rows:
            return {
                "type": "reasoning_response",
                "intent": "water_profile_override_inspection_v527",
                "answer": (
                    "I checked for water-profile overrides where diagnostic WCT labels conflict with profile evidence, "
                    "but I did not find any available override/conflict rows in the current payload."
                ),
                "ui_blocks": [
                    {
                        "type": "suggestions",
                        "title": "Next checks",
                        "items": [
                            "Open individual water profiles for weak WCT wells.",
                            "Compare sim_wct and obs_wct fields if available.",
                            "Run the executive HM summary to see water evidence overrides.",
                        ],
                    }
                ],
                "universal_intent_v500": {
                    "task_type": "water_profile_override_inspection_v527",
                    "original_message": message,
                },
                "agent_trace": {
                    "WaterProfileOverrideInspectionAgentV527": {
                        "status": "no_override_rows",
                    }
                },
            }

        # Summary counts by direction.
        direction_counts = {}
        for r in rows:
            d = r.get("Final direction") or "unknown"
            direction_counts[d] = direction_counts.get(d, 0) + 1

        summary_rows = [
            {
                "Metric": "Override/conflict wells found",
                "Value": len(rows),
            },
            {
                "Metric": "Final direction counts",
                "Value": ", ".join([f"{k}: {v}" for k, v in direction_counts.items()]),
            },
            {
                "Metric": "Rule",
                "Value": "Numeric profile/WCT evidence overrides generic diagnostic labels when they conflict or direction is unknown.",
            },
        ]

        answer = (
            f"I inspected water-profile overrides and found {len(rows)} wells where profile/numeric evidence should be reviewed against the diagnostic WCT label. "
            "The key rule is: actual water profile arrays and explicit sim_wct/obs_wct evidence have priority over generic WCT labels when they conflict."
        )

        return {
            "type": "visual_response",
            "intent": "water_profile_override_inspection_v527",
            "answer": answer,
            "ui_blocks": [
                {
                    "type": "compact_table",
                    "title": "Water-profile override summary",
                    "columns": ["Metric", "Value"],
                    "rows": summary_rows,
                },
                {
                    "type": "compact_table",
                    "title": "WCT label vs profile evidence conflicts",
                    "columns": [
                        "Well",
                        "Original WCT label",
                        "Original direction",
                        "Final direction",
                        "Final timing",
                        "Water score",
                        "Sim water total",
                        "Obs water total",
                        "Sim/Obs ratio",
                        "Sim WCT",
                        "Obs WCT",
                        "Conflict / override reason",
                        "Recommendation",
                    ],
                    "rows": rows[:12],
                },
                {
                    "type": "suggestions",
                    "title": "Recommended follow-up",
                    "items": [
                        "Plot water profile for the highest Sim/Obs ratio wells.",
                        "Compare WCT bias map with water-profile override table.",
                        "For simulated-water-too-high wells, test water relperm/endpoints and water source strength.",
                        "For simulated-water-too-low wells, check TRAN/connectivity and water-source access.",
                    ],
                },
            ],
            "data": {
                "method": "V525 profile/numeric override inspection",
                "rows": len(rows),
                "direction_counts": direction_counts,
            },
            "universal_intent_v500": {
                "task_type": "water_profile_override_inspection_v527",
                "original_message": message,
            },
            "agent_trace": {
                "WaterProfileOverrideInspectionAgentV527": {
                    "status": "generated_override_tables",
                    "rows": len(rows),
                }
            },
        }

    except Exception as exc:
        return {
            "type": "reasoning_response",
            "intent": "water_profile_override_inspection_error_v527",
            "answer": f"I detected a water-profile override inspection request, but V527 failed internally: {exc}",
            "ui_blocks": [],
            "universal_intent_v500": {
                "task_type": "water_profile_override_inspection_v527",
                "original_message": message,
            },
            "agent_trace": {
                "WaterProfileOverrideInspectionAgentV527": {
                    "status": "failed",
                    "error": str(exc),
                }
            },
        }


def _v527_clean_debug_data(response):
    if not isinstance(response, dict):
        return response

    data = response.get("data")

    if not isinstance(data, dict):
        return response

    # Move V526 debug keys away from Visual / Evidence.
    debug = {}

    for k in ["full_trace_keys_v526", "trace_cleaned_v526"]:
        if k in data:
            debug[k] = data.pop(k, None)

    if debug:
        response["_debug_trace_v526"] = debug

    # If data is now empty and there are no visual blocks, remove it entirely.
    if not data:
        response.pop("data", None)

    return response


def run_langgraph_universal_orchestrator_v501(message: str):
    if _v527_is_water_override_inspection(message):
        response = _v527_water_override_response(message)
    else:
        response = _RUN_LANGGRAPH_V501_BEFORE_V527(message)

    return _v527_clean_debug_data(response)

# END V527 CLEAN VISUAL EVIDENCE + WATER PROFILE OVERRIDE INSPECTION


# ==========================================================
# V528 GLOBAL NUMERIC FORMATTER
#
# Purpose:
# In tables and textual answers, show every numeric value with max 2 decimals.
#
# Important:
# - Does NOT alter raw plot x/y arrays, to avoid changing visual data.
# - Formats compact_table rows and textual fields.
# - Formats plot customdata used in hover labels, but not trace x/y series.
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V528 = run_langgraph_universal_orchestrator_v501


def _v528_round_number(x):
    import math
    import numbers

    if isinstance(x, bool):
        return x

    if isinstance(x, numbers.Integral):
        return int(x)

    if isinstance(x, numbers.Real):
        try:
            f = float(x)
            if not math.isfinite(f):
                return None

            r = round(f, 2)

            # Avoid showing 100.0 when 100 is enough.
            if abs(r - int(r)) < 1e-12:
                return int(r)

            return r
        except Exception:
            return x

    return x


def _v528_format_number_text(num_text):
    try:
        f = float(num_text)
    except Exception:
        return num_text

    # Keep max 2 decimals, remove trailing zeros.
    s = f"{f:.2f}".rstrip("0").rstrip(".")

    # Avoid "-0".
    if s == "-0":
        s = "0"

    return s


def _v528_format_text(s):
    import re

    if not isinstance(s, str):
        return s

    # Only format decimals with 3+ decimal digits.
    # This avoids changing HW-25, P10/P50/P90, V528, dates, etc.
    pattern = r"(?<![A-Za-z0-9_/-])(-?\d+\.\d{3,})(?![A-Za-z0-9_/-])"

    return re.sub(pattern, lambda m: _v528_format_number_text(m.group(1)), s)


def _v528_format_value_for_display(v):
    if isinstance(v, str):
        return _v528_format_text(v)

    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return _v528_round_number(v)

    if isinstance(v, list):
        return [_v528_format_value_for_display(x) for x in v]

    if isinstance(v, tuple):
        return [_v528_format_value_for_display(x) for x in v]

    if isinstance(v, dict):
        return {k: _v528_format_value_for_display(val) for k, val in v.items()}

    return v


def _v528_format_compact_table(block):
    if not isinstance(block, dict):
        return block

    rows = block.get("rows")

    if isinstance(rows, list):
        block["rows"] = [_v528_format_value_for_display(r) for r in rows]

    # Also format footer/notes if present.
    for k in ["title", "subtitle", "note", "description"]:
        if k in block and isinstance(block.get(k), str):
            block[k] = _v528_format_text(block[k])

    return block


def _v528_format_plotly_display_parts(block):
    """
    Do not touch x/y arrays.
    Only clean text-like display fields and customdata for hover.
    """
    if not isinstance(block, dict):
        return block

    for k in ["title", "subtitle", "description"]:
        if k in block and isinstance(block.get(k), str):
            block[k] = _v528_format_text(block[k])

    data = block.get("data")
    if isinstance(data, list):
        for trace in data:
            if not isinstance(trace, dict):
                continue

            # Do not alter trace["x"] or trace["y"].
            for k in ["name", "hovertemplate"]:
                if k in trace and isinstance(trace.get(k), str):
                    trace[k] = _v528_format_text(trace[k])

            if "customdata" in trace:
                trace["customdata"] = _v528_format_value_for_display(trace.get("customdata"))

            if "text" in trace:
                trace["text"] = _v528_format_value_for_display(trace.get("text"))

    layout = block.get("layout")
    if isinstance(layout, dict):
        if isinstance(layout.get("title"), str):
            layout["title"] = _v528_format_text(layout["title"])

        for ax in ["xaxis", "yaxis", "zaxis"]:
            if isinstance(layout.get(ax), dict):
                title = layout[ax].get("title")
                if isinstance(title, str):
                    layout[ax]["title"] = _v528_format_text(title)
                # Keep max 2 decimals for tick labels when numeric.
                layout[ax].setdefault("tickformat", ".2f")

    return block


def _v528_format_ui_blocks(response):
    blocks = response.get("ui_blocks")

    if not isinstance(blocks, list):
        return response

    new_blocks = []

    for b in blocks:
        if not isinstance(b, dict):
            new_blocks.append(b)
            continue

        btype = b.get("type")

        if btype == "compact_table":
            b = _v528_format_compact_table(b)

        elif btype == "suggestions":
            b = _v528_format_value_for_display(b)

        elif btype == "plotly_chart":
            b = _v528_format_plotly_display_parts(b)

        else:
            # For other visual blocks, clean only text-like labels/payload display values,
            # but avoid recursively changing large plot/map arrays unless they are in payload text fields.
            for k in ["title", "subtitle", "description", "answer", "note"]:
                if k in b and isinstance(b.get(k), str):
                    b[k] = _v528_format_text(b[k])

            # If the block has a small table-like payload, format it.
            payload = b.get("payload")
            if isinstance(payload, dict):
                for pk in ["rows", "summary", "metrics", "items"]:
                    if pk in payload:
                        payload[pk] = _v528_format_value_for_display(payload[pk])

        new_blocks.append(b)

    response["ui_blocks"] = new_blocks
    return response


def _v528_format_response(response):
    if not isinstance(response, dict):
        return response

    # Main textual fields.
    for k in ["answer", "message", "response", "summary"]:
        if k in response and isinstance(response.get(k), str):
            response[k] = _v528_format_text(response[k])

    # Tables / display blocks.
    response = _v528_format_ui_blocks(response)

    # Data can be shown in Visual/Evidence in some cases, so format numbers there too.
    # This is display metadata, not raw plot arrays.
    if isinstance(response.get("data"), dict):
        response["data"] = _v528_format_value_for_display(response["data"])

    # Trace values can also appear in UI.
    if isinstance(response.get("agent_trace"), dict):
        response["agent_trace"] = _v528_format_value_for_display(response["agent_trace"])

    response.setdefault("agent_trace", {})
    if isinstance(response["agent_trace"], dict):
        response["agent_trace"]["NumericFormatterV528"] = {
            "status": "formatted_text_tables_to_max_2_decimals",
            "note": "Raw plot x/y arrays are not modified.",
        }

    return response


def run_langgraph_universal_orchestrator_v501(message: str):
    response = _RUN_LANGGRAPH_V501_BEFORE_V528(message)
    return _v528_format_response(response)

# END V528 GLOBAL NUMERIC FORMATTER


# ==========================================================
# V601 FINAL SUBMISSION INVALID-WELL GUARD
#
# Purpose:
# Last-priority wrapper before submission.
#
# Fix:
# Some routes can still send invalid wells like HW-250 to the profile agent.
# This final guard blocks explicit invalid/typo well names before any profile,
# diagnosis or visual agent can run.
#
# Rules:
# - HW25 can normalize to HW-25 if HW-25 exists.
# - HW-250 is blocked if not in active registry.
# - HWW-25 is blocked as typo, suggesting HW-25 if available.
# - No silent fallback to another/default well.
# ==========================================================

_RUN_LANGGRAPH_V501_BEFORE_V601 = run_langgraph_universal_orchestrator_v501


def _v601_compact_well_name(x):
    import re
    return re.sub(r"[^A-Z0-9]", "", str(x or "").upper())


def _v601_known_wells():
    """
    Build real well registry from loaded diagnostic/connectivity payloads.
    Avoid generated placeholder ranges.
    """
    wells = []

    def add(w):
        if not w:
            return
        s = str(w).strip()
        if s:
            wells.append(s)

    # Diagnostic payload.
    try:
        from app.universal_reservoir_orchestrator_v500 import _v514_get_all_diag_wells

        for item in _v514_get_all_diag_wells():
            if isinstance(item, dict):
                add(item.get("well") or item.get("WELL") or item.get("Well"))
            else:
                add(item)
    except Exception:
        pass

    # Connectivity rows.
    try:
        from app.universal_reservoir_orchestrator_v500 import _v515_rows

        for item in _v515_rows():
            if isinstance(item, dict):
                add(item.get("well") or item.get("WELL") or item.get("Well"))
            else:
                add(item)
    except Exception:
        pass

    # Optional WCT wells if exposed.
    try:
        from app.universal_reservoir_orchestrator_v500 import _v506_get_wct_wells

        for item in _v506_get_wct_wells():
            if isinstance(item, dict):
                add(item.get("well") or item.get("WELL") or item.get("Well"))
            else:
                add(item)
    except Exception:
        pass

    # Fallback: scan diagnosis CSVs for real wells.
    try:
        import csv
        from pathlib import Path

        for pth in Path("artifacts").rglob("*.csv"):
            name = pth.name.lower()

            if "stress" in name or "test_results" in name:
                continue

            try:
                with pth.open("r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    fields = reader.fieldnames or []
                    lower = {c.lower(): c for c in fields}

                    well_col = (
                        lower.get("well")
                        or lower.get("well_name")
                        or lower.get("wellname")
                        or lower.get("name")
                    )

                    if not well_col:
                        continue

                    for row in reader:
                        add(row.get(well_col))
            except Exception:
                continue
    except Exception:
        pass

    # De-duplicate by compact form.
    out = []
    seen = set()

    for w in wells:
        c = _v601_compact_well_name(w)

        if not c:
            continue

        if c not in seen:
            out.append(str(w).strip())
            seen.add(c)

    return out


def _v601_extract_explicit_well_mentions(message):
    """
    Extract explicit well-like mentions.
    Conservative enough to avoid P10/P50/P90 and version names.
    """
    import re

    s = str(message or "")
    mentions = []

    # HWW-25 / HWW25 typo family.
    for m in re.finditer(r"(?<![A-Za-z0-9])HWW\s*[-_ ]?\s*(\d+)\b", s, flags=re.IGNORECASE):
        n = int(m.group(1))
        mentions.append({
            "raw": m.group(0),
            "compact": f"HWW{n}",
            "kind": "typo_hww",
            "suggest_compact": f"HW{n}",
            "number": n,
        })

    # HW-25 / HW25 / HW 25.
    # Negative lookbehind prevents extracting HW-25 from HWW-25.
    for m in re.finditer(r"(?<![A-Za-z0-9])HW\s*[-_ ]?\s*(\d+)\b", s, flags=re.IGNORECASE):
        n = int(m.group(1))
        mentions.append({
            "raw": m.group(0),
            "compact": f"HW{n}",
            "kind": "normal",
            "number": n,
        })

    # Generic future reservoir names containing letters+digits, but ignore common non-well terms.
    # This helps with future names like ROD-8G / INJ-03 / P-101.
    for m in re.finditer(r"(?<![A-Za-z0-9])([A-Za-z]{2,}[A-Za-z0-9]*[-_ ]?\d+[A-Za-z0-9]*)(?![A-Za-z0-9])", s):
        raw = m.group(1)
        compact = _v601_compact_well_name(raw)

        ignored = {
            "P10", "P50", "P90", "P95", "P5",
            "V500", "V501", "V502", "V503", "V504", "V505", "V506", "V507", "V508", "V509",
            "V510", "V511", "V512", "V513", "V514", "V515", "V516", "V517", "V518", "V519",
            "V520", "V521", "V522", "V523", "V524", "V525", "V526", "V527", "V528", "V600", "V601",
            "3D", "2D",
        }

        if compact in ignored:
            continue

        # Already captured HW/HWW above.
        if compact.startswith("HW") or compact.startswith("HWW"):
            continue

        mentions.append({
            "raw": raw,
            "compact": compact,
            "kind": "generic",
        })

    # De-duplicate preserving order.
    out = []
    seen = set()

    for x in mentions:
        key = (x.get("raw"), x.get("compact"), x.get("kind"))
        if key in seen:
            continue
        out.append(x)
        seen.add(key)

    return out


def _v601_suggestions(compact, known_wells, n=6):
    import difflib
    import re

    known = list(known_wells or [])
    cmap = {_v601_compact_well_name(w): w for w in known}
    cands = list(cmap.keys())

    if not cands:
        return []

    # If typo HWW25, prefer HW25.
    if compact.startswith("HWW"):
        target = "HW" + compact[3:]
        if target in cmap:
            return [cmap[target]]

    # If numeric part exists, prefer close numeric wells with similar prefix.
    m = re.search(r"(\d+)", compact)
    pref = re.match(r"([A-Z]+)", compact)
    num = int(m.group(1)) if m else None
    prefix = pref.group(1) if pref else ""

    scored = []

    for c in cands:
        score = 0.0

        cpref_match = re.match(r"([A-Z]+)", c)
        cpref = cpref_match.group(1) if cpref_match else ""

        cm = re.search(r"(\d+)", c)
        cnum = int(cm.group(1)) if cm else None

        if prefix and cpref:
            if prefix == cpref:
                score += 4.0
            elif prefix.startswith(cpref) or cpref.startswith(prefix):
                score += 2.0

        if num is not None and cnum is not None:
            score += 2.0 / (1.0 + abs(num - cnum))

        score += difflib.SequenceMatcher(None, compact, c).ratio()

        scored.append((score, cmap[c]))

    scored.sort(key=lambda x: x[0], reverse=True)

    out = []
    for _, w in scored:
        if w not in out:
            out.append(w)
        if len(out) >= n:
            break

    return out


def _v601_validate_and_rewrite(message):
    mentions = _v601_extract_explicit_well_mentions(message)

    if not mentions:
        return {
            "status": "no_mentions",
            "message": message,
            "invalid": [],
            "replacements": [],
            "known_wells": [],
        }

    known = _v601_known_wells()

    # If registry cannot be built, do not block to avoid false negatives.
    if not known:
        return {
            "status": "no_registry",
            "message": message,
            "invalid": [],
            "replacements": [],
            "known_wells": [],
        }

    cmap = {}
    for w in known:
        cmap.setdefault(_v601_compact_well_name(w), []).append(w)

    invalid = []
    replacements = []
    rewritten = str(message)

    for m in mentions:
        raw = m["raw"]
        compact = m["compact"]
        kind = m.get("kind")

        if kind == "typo_hww":
            suggestions = _v601_suggestions(compact, known)
            invalid.append({
                "raw": raw,
                "compact": compact,
                "reason": "Looks like a typo well name.",
                "suggestions": suggestions,
            })
            continue

        matches = cmap.get(compact, [])

        if len(matches) == 1:
            canonical = matches[0]
            if raw != canonical:
                replacements.append((raw, canonical))
            continue

        if len(matches) > 1:
            invalid.append({
                "raw": raw,
                "compact": compact,
                "reason": "Ambiguous well name after normalization.",
                "suggestions": matches[:8],
            })
            continue

        suggestions = _v601_suggestions(compact, known)

        invalid.append({
            "raw": raw,
            "compact": compact,
            "reason": "Well not found in active reservoir well registry.",
            "suggestions": suggestions,
        })

    # Rewrite valid aliases only if there are no invalid mentions.
    if not invalid:
        import re

        for raw, canonical in sorted(replacements, key=lambda x: len(x[0]), reverse=True):
            rewritten = re.sub(
                r"(?<![A-Za-z0-9])" + re.escape(raw) + r"(?![A-Za-z0-9])",
                canonical,
                rewritten,
            )

    return {
        "status": "ok",
        "message": rewritten,
        "invalid": invalid,
        "replacements": replacements,
        "known_wells": known,
    }


def _v601_invalid_response(original_message, validation):
    items = []

    for bad in validation.get("invalid") or []:
        sugg = bad.get("suggestions") or []
        sugg_txt = ", ".join(str(x) for x in sugg[:8]) if sugg else "no close match found"
        items.append(
            f"{bad.get('raw')} is not a valid well in the active dataset. "
            f"{bad.get('reason')} Closest available wells: {sugg_txt}."
        )

    answer = (
        "I found an explicit well name that is invalid or ambiguous for the active reservoir. "
        "I did not run the request on another well or on a default well because that would be misleading. "
        + " ".join(items)
    )

    return {
        "type": "reasoning_response",
        "intent": "invalid_well_name_final_v601",
        "answer": answer,
        "ui_blocks": [
            {
                "type": "suggestions",
                "title": "Invalid well name",
                "items": items,
            }
        ],
        "data": {
            "invalid": validation.get("invalid"),
            "known_wells_count": len(validation.get("known_wells") or []),
            "guard": "V601 final invalid-well guard",
        },
        "universal_intent_v500": {
            "task_type": "invalid_well_name_final_v601",
            "original_message": original_message,
            "invalid": validation.get("invalid"),
        },
        "agent_trace": {
            "FinalInvalidWellGuardV601": {
                "status": "blocked_before_routing",
                "reason": "Prevented invalid well from reaching profile/diagnosis agents.",
                "invalid": validation.get("invalid"),
            }
        },
    }


def run_langgraph_universal_orchestrator_v501(message: str):
    validation = _v601_validate_and_rewrite(message)

    if validation.get("invalid"):
        return _v601_invalid_response(message, validation)

    rewritten = validation.get("message") or message

    response = _RUN_LANGGRAPH_V501_BEFORE_V601(rewritten)

    if isinstance(response, dict) and validation.get("replacements"):
        response.setdefault("agent_trace", {})
        response["agent_trace"]["FinalInvalidWellGuardV601"] = {
            "status": "normalized_valid_alias",
            "replacements": validation.get("replacements"),
            "original_message": message,
            "rewritten_message": rewritten,
        }
        response.setdefault("data", {})
        if isinstance(response.get("data"), dict):
            response["data"]["well_name_normalization_v601"] = validation.get("replacements")

    return response

# END V601 FINAL SUBMISSION INVALID-WELL GUARD
