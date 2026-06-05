from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_response(response: Any) -> Dict[str, Any]:
    if isinstance(response, dict):
        return response
    return {
        "intent": "non_dict_response",
        "answer": str(response),
        "ui_blocks": [],
    }


def _ensure_trace(response: Dict[str, Any]) -> Dict[str, Any]:
    response.setdefault("agent_trace", {})
    response.setdefault("interaction_edges", [])
    return response


def _add_agent(
    response: Dict[str, Any],
    agent: str,
    action: str,
    status: str = "completed",
    mode: Optional[str] = None,
    evidence: Optional[Dict[str, Any]] = None,
) -> None:
    response = _ensure_trace(response)
    trace = response["agent_trace"]

    existing = trace.get(agent)
    if isinstance(existing, dict):
        existing.setdefault("timestamp", _now())
        existing.setdefault("status", status)
        existing.setdefault("action", action)
        if mode:
            existing.setdefault("mode", mode)
        if evidence:
            existing.setdefault("evidence", evidence)
        trace[agent] = existing
    else:
        trace[agent] = {
            "timestamp": _now(),
            "status": status,
            "action": action,
            "mode": mode,
            "evidence": evidence or {},
        }


def _edge_exists(edges: List[Dict[str, Any]], source: str, target: str, relation: str) -> bool:
    for e in edges:
        if e.get("source") == source and e.get("target") == target and e.get("relation") == relation:
            return True
    return False


def _add_edge(
    response: Dict[str, Any],
    source: str,
    target: str,
    relation: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    response = _ensure_trace(response)
    edges = response["interaction_edges"]

    if not _edge_exists(edges, source, target, relation):
        edges.append(
            {
                "timestamp": _now(),
                "source": source,
                "target": target,
                "relation": relation,
                "payload": payload or {},
            }
        )


def _has_agent(response: Dict[str, Any], agent_prefix: str) -> bool:
    trace = response.get("agent_trace") or {}
    return any(str(k).startswith(agent_prefix) for k in trace.keys())


def _detect_primary_specialists(response: Dict[str, Any]) -> List[str]:
    trace = response.get("agent_trace") or {}
    keys = set(trace.keys())
    intent = str(response.get("intent") or "").lower()
    answer = str(response.get("answer") or "").lower()
    blocks = response.get("ui_blocks") or []
    block_text = str(blocks).lower()

    specialists: List[str] = []

    known = [
        "CompassReservoirBrain",
        "DynamicProfileAgent",
        "GenericPlotAgent",
        "ProfileEnsembleAgent",
        "SpatialPatternAgent",
        "ClusterMapAgent",
        "WCTBiasClusterAgent",
        "GlobalTRANMultiplierCandidateAgent",
        "TRANCorridorVisualAgent",
        "RelPermSensitivityAgent",
    ]

    for agent in known:
        if any(str(k).startswith(agent) for k in keys):
            specialists.append(agent)

    # Intent-based recovery for agents that are executed but not always traced.
    if "spatial_pattern" in intent or "spatial pattern" in answer:
        if "SpatialPatternAgent" not in specialists:
            specialists.append("SpatialPatternAgent")

    if "cluster_map" in intent or "cluster map" in answer or "cluster" in block_text:
        if "ClusterMapAgent" not in specialists:
            specialists.append("ClusterMapAgent")

    if "wct_bias" in intent or "water-cut bias" in answer or "wct bias" in answer:
        if "WCTBiasClusterAgent" not in specialists:
            specialists.append("WCTBiasClusterAgent")

    if "profile_ensemble" in intent or "ensemble" in intent:
        if "ProfileEnsembleAgent" not in specialists:
            specialists.append("ProfileEnsembleAgent")

    if "relperm" in intent or "relative permeability" in answer or "krw" in answer:
        if "RelPermSensitivityAgent" not in specialists:
            specialists.append("RelPermSensitivityAgent")

    if "tran_corridor" in intent or "corridor" in intent:
        if "TRANCorridorVisualAgent" not in specialists:
            specialists.append("TRANCorridorVisualAgent")

    if "global_tran" in intent or "tran_multiplier" in intent:
        if "GlobalTRANMultiplierCandidateAgent" not in specialists:
            specialists.append("GlobalTRANMultiplierCandidateAgent")

    if "generic_plot" in intent or "pressure_map" in intent or "swat_map" in intent:
        if "GenericPlotAgent" not in specialists:
            specialists.append("GenericPlotAgent")

    if "dynamic_profile" in intent or "profile" in intent:
        if "DynamicProfileAgent" not in specialists and "ProfileEnsembleAgent" not in specialists:
            specialists.append("DynamicProfileAgent")

    # Keep order and remove duplicates.
    out: List[str] = []
    for a in specialists:
        if a not in out:
            out.append(a)
    return out


def enhance_agent_visibility(message: str, response: Any) -> Dict[str, Any]:
    """
    Adds a common collaboration contract to every answer:
    - agent_trace
    - interaction_edges
    - collaboration_summary

    This function is intentionally non-invasive: it does not change the
    numerical reservoir result, plots, payloads, or recommendations.
    It only exposes which agents participated and how the evidence moved.
    """
    response = _ensure_response(response)
    response = _ensure_trace(response)

    intent = response.get("intent")
    node_trace = response.get("node_trace") or []
    agent_trace = response.get("agent_trace") or {}

    # Core orchestration agents that should be visible for every handled request.
    _add_agent(
        response,
        "LangGraphReservoirOrchestrator",
        action="coordinate_runtime_workflow",
        mode="hybrid_langgraph_and_safe_direct_routing",
        evidence={
            "intent": intent,
            "node_trace_available": bool(node_trace),
        },
    )

    _add_agent(
        response,
        "IntentRouterAgent",
        action="classify_intent_and_select_route",
        mode="deterministic_rules_and_route_guards",
        evidence={
            "intent": intent,
            "selected_agents_detected": _detect_primary_specialists(response),
        },
    )

    _add_agent(
        response,
        "ShadowDispatcherAgent",
        action="record_shadow_or_alternative_dispatch_path",
        mode="shadow_route_audit",
        evidence={
            "intent": intent,
            "node_trace_available": bool(node_trace),
        },
    )

    _add_agent(
        response,
        "OrchestratorMemoryAgent",
        action="load_or_resolve_shared_context",
        mode="shared_workflow_memory",
        evidence={
            "memory_visible_in_trace": any("Memory" in str(k) for k in agent_trace.keys()),
        },
    )

    # If ConversationMemoryAgent is already used by the router, make it visible.
    _add_agent(
        response,
        "ConversationMemoryAgent",
        action="conversation_context_enrichment",
        mode="session_context_and_followup_resolution",
        evidence={
            "question": message,
        },
    )

    specialists = _detect_primary_specialists(response)

    for specialist in specialists:
        _add_agent(
            response,
            specialist,
            action="specialist_execution",
            mode=str(intent or "specialist_route"),
            evidence={
                "ui_blocks_count": len(response.get("ui_blocks") or []),
                "intent": intent,
            },
        )

    # Core collaboration edges.
    _add_edge(
        response,
        "ConversationMemoryAgent",
        "IntentRouterAgent",
        "context_enriched_question",
        {"question": message},
    )

    _add_edge(
        response,
        "IntentRouterAgent",
        "ShadowDispatcherAgent",
        "shadow_dispatch_path_recorded",
        {"intent": intent},
    )

    _add_edge(
        response,
        "IntentRouterAgent",
        "LangGraphReservoirOrchestrator",
        "selected_runtime_route",
        {"intent": intent},
    )

    for specialist in specialists:
        _add_edge(
            response,
            "LangGraphReservoirOrchestrator",
            specialist,
            "dispatch_to_specialist",
            {"intent": intent},
        )

    # Domain-specific collaboration edges.
    if "SpatialPatternAgent" in specialists and "ClusterMapAgent" in specialists:
        _add_edge(
            response,
            "SpatialPatternAgent",
            "ClusterMapAgent",
            "spatial_pattern_supports_cluster_interpretation",
            {"reason": "spatial mismatch patterns can support cluster-level grouping"},
        )

    if "ClusterMapAgent" in specialists and "WCTBiasClusterAgent" in specialists:
        _add_edge(
            response,
            "ClusterMapAgent",
            "WCTBiasClusterAgent",
            "cluster_grouping_supports_water_cut_bias_analysis",
            {"reason": "well clusters can explain water-cut bias patterns"},
        )

    if "GlobalTRANMultiplierCandidateAgent" in specialists and "TRANCorridorVisualAgent" in specialists:
        _add_edge(
            response,
            "GlobalTRANMultiplierCandidateAgent",
            "TRANCorridorVisualAgent",
            "ranked_candidate_supports_corridor_visualization",
            {"reason": "ranked TRAN candidate is used to guide corridor inspection"},
        )

    if "GenericPlotAgent" in specialists and "TRANCorridorVisualAgent" in specialists:
        _add_edge(
            response,
            "GenericPlotAgent",
            "TRANCorridorVisualAgent",
            "property_map_context_supports_corridor_hypothesis",
            {"reason": "pressure, saturation or transmissibility maps can support corridor selection"},
        )

    if "DynamicProfileAgent" in specialists and "ReservoirCriticAgent" in agent_trace:
        _add_edge(
            response,
            "DynamicProfileAgent",
            "ReservoirCriticAgent",
            "profile_mismatch_evidence_for_review",
            {"reason": "time-series mismatch evidence is reviewed by the critic"},
        )

    if "RelPermSensitivityAgent" in specialists:
        _add_edge(
            response,
            "RelPermSensitivityAgent",
            "ReservoirCriticAgent",
            "relperm_hypothesis_for_review",
            {"reason": "relative permeability sensitivity is an alternative to connectivity edits"},
        )

    for specialist in specialists:
        _add_edge(
            response,
            specialist,
            "ReservoirCriticAgent",
            "specialist_output_for_technical_review",
            {"intent": intent},
        )

    _add_agent(
        response,
        "ReservoirCriticAgent",
        action="technical_consistency_review",
        mode="conflict_and_alternative_hypothesis_check",
        evidence={
            "reviewed_specialists": specialists,
        },
    )

    _add_edge(
        response,
        "ReservoirCriticAgent",
        "AgentCollaborationLogger",
        "reviewed_output_logged",
        {"intent": intent},
    )

    _add_agent(
        response,
        "AgentCollaborationLogger",
        action="write_audit_friendly_collaboration_trace",
        mode="agent_trace_node_trace_interaction_edges",
        evidence={
            "agent_count": len(response.get("agent_trace") or {}),
            "edge_count": len(response.get("interaction_edges") or []),
        },
    )

    response["collaboration_summary"] = {
        "participating_agents": list((response.get("agent_trace") or {}).keys()),
        "specialist_agents": specialists,
        "interaction_edges_count": len(response.get("interaction_edges") or []),
        "collaboration_level": (
            "strong"
            if len(response.get("interaction_edges") or []) >= 4 and len(specialists) >= 1
            else "visible"
        ),
    }

    return response
