
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


LOG_PATH = Path("logs/agent_collaboration_trace.jsonl")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _summarize_ui_blocks(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks = []

    for b in response.get("ui_blocks") or []:
        if not isinstance(b, dict):
            continue

        blocks.append({
            "type": b.get("type"),
            "title": b.get("title"),
        })

    return blocks


def _detect_collaboration_path(response: Dict[str, Any]) -> List[str]:
    trace = _safe_dict(response.get("agent_trace"))
    keys = list(trace.keys())

    path = []

    # Prefer real LangGraph V013 node trace if available.
    v013 = _safe_dict(trace.get("LangGraphActiveNodesV013"))
    node_trace = v013.get("node_trace") or []
    if node_trace:
        for item in node_trace:
            if isinstance(item, dict) and item.get("node"):
                path.append(item.get("node"))

    if "LangGraphGlobalTRANHookV003" in keys:
        path.append("LangGraphGlobalTRANHookV003")

    if "LangGraphOrchestratorActiveV002" in keys:
        path.append("LangGraphOrchestratorActiveV002")

    if "GlobalTRANMultiplierCandidateAgent" in keys:
        path.append("GlobalTRANMultiplierCandidateAgent")

    if "OrchestratorMemoryFollowUpV006" in keys:
        path.append("OrchestratorMemoryFollowUpV006")

    if "TRANCorridorVisualAgent" in keys:
        path.append("TRANCorridorVisualAgent")

    if "RelPermCurveSelectorAgentV67" in keys:
        path.append("RelPermCurveSelectorAgentV67")

    if "DynamicProfileAgent" in keys:
        path.append("DynamicProfileAgent")

    if "GenericPlotAgent" in keys:
        path.append("GenericPlotAgent")

    if "CompassReservoirBrain" in keys:
        path.append("CompassReservoirBrain")

    if "ReservoirCriticAgentV008" in keys:
        path.append("ReservoirCriticAgentV008")

    # Keep unknown traces too, but after known path.
    for k in keys:
        if k not in path:
            path.append(k)

    return path


def build_collaboration_record(message: str, response: Dict[str, Any]) -> Dict[str, Any]:
    trace = _safe_dict(response.get("agent_trace"))

    langgraph_decision = None

    for key in [
        "LangGraphActiveNodesV013",
        "LangGraphMainIntegrationV014",
        "LangGraphGlobalTRANHookV003",
        "LangGraphOrchestratorActiveV002",
        "LangGraphOrchestratorShadowV001",
    ]:
        if key in trace:
            langgraph_decision = _safe_dict(trace.get(key)).get("decision")
            if langgraph_decision:
                break

    critic = _safe_dict(trace.get("ReservoirCriticAgentV008"))
    memory_followup = _safe_dict(trace.get("OrchestratorMemoryFollowUpV006"))
    global_tran = _safe_dict(trace.get("GlobalTRANMultiplierCandidateAgent"))

    return {
        "timestamp": _now(),
        "user_message": message,
        "final_intent": response.get("intent"),
        "final_answer_preview": str(response.get("answer") or "")[:700],
        "ui_blocks": _summarize_ui_blocks(response),
        "interaction_edges": response.get("interaction_edges", []),
        "collaboration_path": _detect_collaboration_path(response),
        "langgraph_decision": langgraph_decision,
        "global_candidate_agent": global_tran or None,
        "memory_followup": memory_followup or None,
        "critic_review": critic or None,
        "trace_keys": list(trace.keys()),
    }


def append_collaboration_record(message: str, response: Dict[str, Any]) -> None:
    if not isinstance(response, dict):
        return

    LOG_PATH.parent.mkdir(exist_ok=True)
    record = build_collaboration_record(message, response)

    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def tail_collaboration_records(n: int = 10) -> List[Dict[str, Any]]:
    if not LOG_PATH.exists():
        return []

    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()[-n:]
    out = []

    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception:
            pass

    return out
