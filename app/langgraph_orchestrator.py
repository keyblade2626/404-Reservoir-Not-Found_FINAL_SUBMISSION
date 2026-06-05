
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END


class ReservoirOrchestratorState(TypedDict, total=False):
    message: str
    decision: Dict[str, Any]
    trace: List[Dict[str, Any]]
    mode: str
    output: Dict[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_well(message: str) -> Optional[str]:
    m = re.search(r"\b(hw[-_\s]?\d+[a-z]?)\b", str(message or ""), re.I)
    if not m:
        return None
    return m.group(1).upper().replace("_", "-").replace(" ", "-")


def _contains_any(q: str, terms: List[str]) -> bool:
    return any(t in q for t in terms)


def deterministic_route_decision(message: str) -> Dict[str, Any]:
    original = str(message or "")
    q = original.lower().replace("-", " ").replace("_", " ")
    well = _extract_well(original)

    pressure_terms = [
        "pressure", "pressione", "bhp", "wbhp",
        "bottom hole pressure", "bottom-hole pressure",
    ]

    profile_terms = [
        "plot", "profile", "profiles", "curve", "trend",
        "time series", "timeseries", "history",
        "grafico", "profilo", "curva", "andamento",
    ]

    map_terms = [
        "map", "mappa", "property map", "heatmap",
        "spatial", "spaziale", "distribution", "distribuzione",
    ]

    tran_terms = [
        "transmissibility", "trasmissibilita", "trasmissibilità",
        "tran", "connectivity", "connection", "corridor", "corridoio",
        "communication",
    ]

    model_edit_terms = [
        "multiplier", "multipliers", "improve", "increase",
        "modify", "change", "adjust", "tune", "calibrate",
        "optimize", "optimise", "candidate", "candidates",
        "where should", "where do i have to", "where i have to",
        "where would you", "where to", "test", "apply",
        "applicare", "modificare", "migliorare", "ottimizzare", "aumentare",
    ]

    relperm_terms = [
        "relperm", "relative permeability", "permeability curve",
        "krw", "kro", "krg", "pcow", "pcgo",
    ]

    concept_terms = [
        "what is", "what are", "define", "explain what",
        "cos'è", "cosa è", "che cos'è", "che significa",
    ]

    diagnostic_terms = [
        "why", "explain", "not matching", "mismatch",
        "weak", "poor", "history match", "hm",
        "perché", "perche", "spiega",
    ]

    # 1) Well pressure/BHP profile: never send to pressure map.
    if well and _contains_any(q, pressure_terms) and _contains_any(q, profile_terms) and not _contains_any(q, map_terms):
        return {
            "intent": "well_profile",
            "route": "dynamic_profile_agent",
            "confidence": "high",
            "well": well,
            "variable": "BHP",
            "normalized_question": f"Show BHP profiles simulated vs observed for {well}",
            "forbidden_routes": ["generic_property_map"],
            "reason": "Detected well + pressure/BHP + profile/plot/trend request.",
        }

    # 2A) Specific TRAN corridor request for one well.
    # Example: "Show proposed TRAN corridor for HW-28"
    if well and _contains_any(q, tran_terms) and _contains_any(q, [
        "corridor", "corridoio", "proposed", "proposal", "candidate",
        "multiplier", "multipliers", "ixf", "edit"
    ]):
        return {
            "intent": "tran_multiplier_candidate",
            "route": "tran_corridor_visual_agent",
            "confidence": "high",
            "well": well,
            "variable": "TRAN",
            "edit_type": "transmissibility_multiplier",
            "normalized_question": f"Show proposed TRAN corridor for {well}",
            "forbidden_routes": ["generic_property_map"],
            "reason": "Detected specific well + TRAN/corridor/proposed-edit request.",
        }

    # 2B) Global TRAN multiplier/model-edit candidate: never send to raw TRAN map.
    if _contains_any(q, tran_terms) and _contains_any(q, model_edit_terms):
        return {
            "intent": "tran_multiplier_candidate",
            "route": "tran_corridor_visual_agent",
            "confidence": "high",
            "well": well,
            "variable": "TRAN",
            "edit_type": "transmissibility_multiplier",
            "normalized_question": (
                "Show proposed transmissibility multiplier corridors and explain where "
                "TRAN multipliers should be tested for history matching."
            ),
            "forbidden_routes": ["generic_property_map"],
            "reason": "Detected transmissibility/connectivity + model-edit/multiplier/candidate language.",
        }

    # 3) RelPerm sensitivity.
    if _contains_any(q, relperm_terms):
        return {
            "intent": "relperm_sensitivity",
            "route": "relperm_sensitivity_agent",
            "confidence": "high" if well else "medium",
            "well": well,
            "variable": "relperm",
            "edit_type": "relative_permeability_curve",
            "normalized_question": original,
            "forbidden_routes": ["generic_property_map"],
            "reason": "Detected relative permeability / Kr terms.",
        }

    # 4) Explicit maps stay maps.
    if _contains_any(q, map_terms):
        return {
            "intent": "property_map",
            "route": "generic_plot_agent",
            "confidence": "medium",
            "well": well,
            "normalized_question": original,
            "forbidden_routes": [],
            "reason": "Explicit map/spatial/property-map language.",
        }

    # 5) Conceptual questions.
    if _contains_any(q, concept_terms):
        return {
            "intent": "concept_question",
            "route": "compass_concept_agent",
            "confidence": "medium",
            "well": well,
            "normalized_question": original,
            "forbidden_routes": [],
            "reason": "Detected concept/explanation question.",
        }

    # 6) Diagnostic explanation.
    if _contains_any(q, diagnostic_terms):
        return {
            "intent": "diagnostic_explanation",
            "route": "reservoir_story_agent",
            "confidence": "medium",
            "well": well,
            "normalized_question": original,
            "forbidden_routes": [],
            "reason": "Detected diagnostic explanation language.",
        }

    return {
        "intent": "passthrough",
        "route": "existing_router",
        "confidence": "low",
        "well": well,
        "normalized_question": original,
        "forbidden_routes": [],
        "reason": "No high-confidence orchestrator intent detected.",
    }


def node_intent_router(state: ReservoirOrchestratorState) -> ReservoirOrchestratorState:
    message = state.get("message", "")
    decision = deterministic_route_decision(message)

    trace = list(state.get("trace", []))
    trace.append({
        "timestamp": _utc_now(),
        "agent": "IntentRouterAgent",
        "model": "deterministic_rules_v001",
        "action": "classified_user_intent",
        "input": message,
        "decision": decision,
        "status": "success",
    })

    state["decision"] = decision
    state["trace"] = trace
    return state


def node_shadow_trace(state: ReservoirOrchestratorState) -> ReservoirOrchestratorState:
    decision = state.get("decision", {})
    message = state.get("message", "")

    trace = list(state.get("trace", []))
    trace.append({
        "timestamp": _utc_now(),
        "agent": "ShadowDispatcherAgent",
        "action": "shadow_route_only",
        "input": message,
        "recommended_route": decision.get("route"),
        "intent": decision.get("intent"),
        "forbidden_routes": decision.get("forbidden_routes", []),
        "status": "success",
    })

    state["trace"] = trace
    state["output"] = {
        "type": "orchestrator_shadow_decision",
        "message": message,
        "decision": decision,
        "trace": trace,
    }
    return state


def build_shadow_graph():
    graph = StateGraph(ReservoirOrchestratorState)
    graph.add_node("intent_router", node_intent_router)
    graph.add_node("shadow_trace", node_shadow_trace)

    graph.set_entry_point("intent_router")
    graph.add_edge("intent_router", "shadow_trace")
    graph.add_edge("shadow_trace", END)

    return graph.compile()


_SHADOW_GRAPH = None


def run_langgraph_shadow_orchestrator(message: str) -> Dict[str, Any]:
    global _SHADOW_GRAPH
    if _SHADOW_GRAPH is None:
        _SHADOW_GRAPH = build_shadow_graph()

    result = _SHADOW_GRAPH.invoke({
        "message": message,
        "mode": "shadow",
        "trace": [],
    })

    return result.get("output", result)


def append_orchestrator_trace_jsonl(result: Dict[str, Any], log_path: str = "logs/langgraph_orchestrator_trace.jsonl") -> None:
    Path("logs").mkdir(exist_ok=True)
    p = Path(log_path)

    record = {
        "timestamp": _utc_now(),
        "component": "LangGraphReservoirOrchestrator",
        "mode": "shadow",
        "result": result,
    }

    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


if __name__ == "__main__":
    tests = [
        "show me pressure plot for HW-28",
        "show me where I have to improve transmissibility by multipliers",
        "show transmissibility map",
        "show pressure map",
        "why is HW-28 not matching water?",
        "show modified relperm curve for HW-28",
    ]

    for t in tests:
        out = run_langgraph_shadow_orchestrator(t)
        append_orchestrator_trace_jsonl(out)
        print("\n==============================")
        print(t)
        print(json.dumps(out["decision"], indent=2, ensure_ascii=False))



# ==========================================================
# LANGGRAPH ACTIVE NODE GRAPH V013
# Real node-based orchestrator:
# IntentRouterNode -> DispatcherNode -> SpecialistExecutorNode
# -> MemoryNode -> CriticNode -> FinalResponseNode
# This is initially exposed via test API only.
# ==========================================================

class ActiveReservoirOrchestratorState(TypedDict, total=False):
    message: str
    decision: Dict[str, Any]
    dispatch: Dict[str, Any]
    response: Dict[str, Any]
    trace: List[Dict[str, Any]]
    mode: str
    output: Dict[str, Any]


def _append_node_trace_v013(
    state: ActiveReservoirOrchestratorState,
    node: str,
    action: str,
    status: str = "success",
    details: Optional[Dict[str, Any]] = None,
) -> ActiveReservoirOrchestratorState:
    trace = list(state.get("trace", []))
    trace.append({
        "timestamp": _utc_now(),
        "node": node,
        "action": action,
        "status": status,
        "details": details or {},
    })
    state["trace"] = trace
    return state


def node_intent_router_v013(state: ActiveReservoirOrchestratorState) -> ActiveReservoirOrchestratorState:
    message = state.get("message", "")
    decision = deterministic_route_decision(message)

    state["decision"] = decision

    return _append_node_trace_v013(
        state,
        node="IntentRouterNode",
        action="classified_user_intent",
        details={
            "message": message,
            "intent": decision.get("intent"),
            "route": decision.get("route"),
            "confidence": decision.get("confidence"),
            "well": decision.get("well"),
            "forbidden_routes": decision.get("forbidden_routes", []),
            "reason": decision.get("reason"),
        },
    )


def node_dispatcher_v013(state: ActiveReservoirOrchestratorState) -> ActiveReservoirOrchestratorState:
    decision = state.get("decision") or {}
    intent = decision.get("intent")
    well = decision.get("well")

    dispatch = {
        "selected_node": "FallbackNode",
        "selected_agent": "existing_router_chain",
        "reason": "No high-confidence V013 dispatch rule matched.",
    }

    if intent == "tran_multiplier_candidate" and not well:
        dispatch = {
            "selected_node": "GlobalTRANCandidateNode",
            "selected_agent": "GlobalTRANMultiplierCandidateAgent",
            "reason": "Global TRAN multiplier request without specific well.",
        }

    elif intent == "tran_multiplier_candidate" and well:
        dispatch = {
            "selected_node": "TRANCorridorNode",
            "selected_agent": "TRANCorridorVisualAgent",
            "reason": "Specific TRAN multiplier/corridor request.",
        }

    elif intent == "relperm_sensitivity":
        dispatch = {
            "selected_node": "RelPermNode",
            "selected_agent": "RelPermSensitivityAgent",
            "reason": "Relative permeability sensitivity request.",
        }

    elif intent == "well_profile":
        dispatch = {
            "selected_node": "WellProfileNode",
            "selected_agent": "DynamicProfileAgent",
            "reason": "Well time-series/profile request.",
        }

    elif intent == "property_map":
        dispatch = {
            "selected_node": "PropertyMapNode",
            "selected_agent": "GenericPlotAgent",
            "reason": "Explicit property map request.",
        }

    elif intent == "diagnostic_explanation":
        dispatch = {
            "selected_node": "DiagnosticExplanationNode",
            "selected_agent": "ExistingDiagnosticRouter",
            "reason": "Diagnostic explanation request; keeping existing diagnostic chain for now.",
        }

    state["dispatch"] = dispatch

    return _append_node_trace_v013(
        state,
        node="DispatcherNode",
        action="selected_specialist_agent",
        details={
            "intent": intent,
            "well": well,
            "dispatch": dispatch,
        },
    )


def node_specialist_executor_v013(state: ActiveReservoirOrchestratorState) -> ActiveReservoirOrchestratorState:
    message = state.get("message", "")
    decision = state.get("decision") or {}
    dispatch = state.get("dispatch") or {}

    normalized = decision.get("normalized_question") or message
    selected_agent = dispatch.get("selected_agent")

    try:
        response = None

        if selected_agent == "GlobalTRANMultiplierCandidateAgent":
            from app.tran_multiplier_candidate_agent import answer_global_tran_multiplier_candidate_question
            response = answer_global_tran_multiplier_candidate_question(message)

        elif selected_agent == "TRANCorridorVisualAgent":
            from app.tran_corridor_export_agent import answer_tran_corridor_visual_question
            response = answer_tran_corridor_visual_question(normalized)

        elif selected_agent == "RelPermSensitivityAgent":
            from app.relperm_sensitivity_agent import answer_relperm_sensitivity_question
            response = answer_relperm_sensitivity_question(normalized)

        elif selected_agent == "DynamicProfileAgent":
            from app.dynamic_profile_agent import answer_dynamic_profile_question
            response = answer_dynamic_profile_question(normalized)

        elif selected_agent == "GenericPlotAgent":
            from app.generic_plot_agent import answer_generic_plot_question
            response = answer_generic_plot_question(normalized)

        else:
            response = {
                "type": "visual_response",
                "intent": "v013_passthrough_required",
                "answer": (
                    "V013 LangGraph classified this request, but this route is still delegated "
                    "to the existing chat router in production mode."
                ),
                "ui_blocks": [
                    {
                        "type": "suggestions",
                        "title": "Suggested next steps",
                        "items": [
                            "Diagnose HW-10 mismatch",
                            "show pressure map",
                            "show me where I have to improve transmissibility by multipliers",
                        ],
                    }
                ],
                "data": {
                    "decision": decision,
                    "dispatch": dispatch,
                },
                "agent_trace": {},
            }

        if response is None:
            response = {
                "type": "visual_response",
                "intent": "v013_specialist_no_response",
                "answer": f"V013 selected {selected_agent}, but the specialist returned no response.",
                "ui_blocks": [],
                "data": {
                    "decision": decision,
                    "dispatch": dispatch,
                },
                "agent_trace": {},
            }

        response.setdefault("agent_trace", {})
        response["agent_trace"]["LangGraphV013SpecialistExecutor"] = {
            "selected_agent": selected_agent,
            "selected_node": dispatch.get("selected_node"),
            "normalized_question": normalized,
            "status": "success",
        }

        state["response"] = response

        return _append_node_trace_v013(
            state,
            node="SpecialistExecutorNode",
            action="executed_specialist_agent",
            details={
                "selected_agent": selected_agent,
                "response_intent": response.get("intent"),
                "ui_block_types": [
                    b.get("type") for b in response.get("ui_blocks", []) if isinstance(b, dict)
                ],
            },
        )

    except Exception as exc:
        response = {
            "type": "visual_response",
            "intent": "v013_specialist_error",
            "answer": f"V013 specialist execution failed for {selected_agent}: {exc}",
            "ui_blocks": [],
            "data": {
                "error": str(exc),
                "decision": decision,
                "dispatch": dispatch,
            },
            "agent_trace": {
                "LangGraphV013SpecialistExecutor": {
                    "selected_agent": selected_agent,
                    "status": "error",
                    "error": str(exc),
                }
            },
        }

        state["response"] = response

        return _append_node_trace_v013(
            state,
            node="SpecialistExecutorNode",
            action="specialist_execution_failed",
            status="error",
            details={
                "selected_agent": selected_agent,
                "error": str(exc),
            },
        )


def node_memory_v013(state: ActiveReservoirOrchestratorState) -> ActiveReservoirOrchestratorState:
    response = state.get("response") or {}
    decision = state.get("decision") or {}
    dispatch = state.get("dispatch") or {}

    try:
        from app.orchestrator_memory import load_memory

        memory_snapshot = load_memory()

        response.setdefault("agent_trace", {})
        response["agent_trace"]["LangGraphV013MemoryNode"] = {
            "status": "memory_snapshot_attached",
            "last_intent": memory_snapshot.get("last_intent"),
            "candidate_wells": memory_snapshot.get("candidate_wells"),
            "last_route": memory_snapshot.get("last_route"),
            "updated_at": memory_snapshot.get("updated_at"),
        }

        state["response"] = response

        return _append_node_trace_v013(
            state,
            node="MemoryNode",
            action="attached_shared_memory_snapshot",
            details={
                "last_intent": memory_snapshot.get("last_intent"),
                "candidate_wells": memory_snapshot.get("candidate_wells"),
                "last_route": memory_snapshot.get("last_route"),
            },
        )

    except Exception as exc:
        response.setdefault("agent_trace", {})
        response["agent_trace"]["LangGraphV013MemoryNode"] = {
            "status": "memory_error",
            "error": str(exc),
        }
        state["response"] = response

        return _append_node_trace_v013(
            state,
            node="MemoryNode",
            action="memory_snapshot_failed",
            status="error",
            details={"error": str(exc)},
        )


def node_critic_v013(state: ActiveReservoirOrchestratorState) -> ActiveReservoirOrchestratorState:
    message = state.get("message", "")
    response = state.get("response") or {}

    try:
        from app.reservoir_critic_agent import review_response_for_model_edit_conflicts

        reviewed = review_response_for_model_edit_conflicts(message, response)
        state["response"] = reviewed

        critic_trace = (reviewed.get("agent_trace") or {}).get("ReservoirCriticAgentV008", {})

        return _append_node_trace_v013(
            state,
            node="CriticNode",
            action="reviewed_specialist_response",
            details={
                "critic_status": critic_trace.get("status"),
                "well": critic_trace.get("well"),
                "warnings": critic_trace.get("warnings"),
                "reason": critic_trace.get("reason"),
            },
        )

    except Exception as exc:
        response.setdefault("agent_trace", {})
        response["agent_trace"]["LangGraphV013CriticNode"] = {
            "status": "critic_error",
            "error": str(exc),
        }
        state["response"] = response

        return _append_node_trace_v013(
            state,
            node="CriticNode",
            action="critic_review_failed",
            status="error",
            details={"error": str(exc)},
        )


def node_final_response_v013(state: ActiveReservoirOrchestratorState) -> ActiveReservoirOrchestratorState:
    response = state.get("response") or {}
    decision = state.get("decision") or {}
    dispatch = state.get("dispatch") or {}

    # Append FinalResponseNode first, then expose the complete node trace.
    state = _append_node_trace_v013(
        state,
        node="FinalResponseNode",
        action="finalized_response",
        details={
            "final_intent": response.get("intent"),
            "trace_nodes_before_final": [x.get("node") for x in state.get("trace", [])],
        },
    )

    trace = state.get("trace") or []

    response.setdefault("agent_trace", {})
    response["agent_trace"]["LangGraphActiveNodesV013"] = {
        "status": "completed",
        "decision": decision,
        "dispatch": dispatch,
        "node_trace": trace,
    }

    state["response"] = response
    state["output"] = response

    return state


_ACTIVE_GRAPH_V013 = None


def build_active_graph_v013():
    graph = StateGraph(ActiveReservoirOrchestratorState)

    graph.add_node("intent_router", node_intent_router_v013)
    graph.add_node("dispatcher", node_dispatcher_v013)
    graph.add_node("specialist_executor", node_specialist_executor_v013)
    graph.add_node("memory", node_memory_v013)
    graph.add_node("critic", node_critic_v013)
    graph.add_node("final_response", node_final_response_v013)

    graph.set_entry_point("intent_router")
    graph.add_edge("intent_router", "dispatcher")
    graph.add_edge("dispatcher", "specialist_executor")
    graph.add_edge("specialist_executor", "memory")
    graph.add_edge("memory", "critic")
    graph.add_edge("critic", "final_response")
    graph.add_edge("final_response", END)

    return graph.compile()


def run_langgraph_active_orchestrator_v013(message: str) -> Dict[str, Any]:
    global _ACTIVE_GRAPH_V013

    if _ACTIVE_GRAPH_V013 is None:
        _ACTIVE_GRAPH_V013 = build_active_graph_v013()

    result = _ACTIVE_GRAPH_V013.invoke({
        "message": message,
        "mode": "active_v013",
        "trace": [],
    })

    return result.get("output", result)



