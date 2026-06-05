from __future__ import annotations

import ast
import json
import math
import os
import re
import traceback
from fastapi import Body
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# IMPORTANT:
# This imports the existing reservoir runtime as a specialist tool.
# The Copilot does not replace specialist agents; it decides when and how to call them.
from app.langgraph_universal_orchestrator_v501 import (
    run_langgraph_universal_orchestrator_v501 as _run_reservoir_runtime_v501,
)


_ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.FloorDiv,
    ast.USub,
    ast.UAdd,
    ast.Constant,
    ast.Load,
    ast.Call,
    ast.Name,
)

_ALLOWED_MATH_NAMES = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "pi": math.pi,
    "e": math.e,
    "abs": abs,
    "round": round,
}


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _compact_text(x: Any, n: int = 500) -> str:
    s = str(x or "").replace("\r", " ").replace("\n", " ").strip()
    while "  " in s:
        s = s.replace("  ", " ")
    return s[:n] + ("..." if len(s) > n else "")


def _extract_message(payload: Dict[str, Any]) -> str:
    for key in ["message", "query", "question", "input", "prompt"]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    if isinstance(payload.get("messages"), list):
        for item in reversed(payload["messages"]):
            if isinstance(item, dict):
                content = item.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()

    raise ValueError("Missing message/query/question/input/prompt in request JSON.")


def _safe_calc(expr: str) -> Optional[float]:
    expr = expr.strip()
    expr = expr.replace("^", "**")

    tree = ast.parse(expr, mode="eval")

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST_NODES):
            raise ValueError(f"Unsupported expression element: {type(node).__name__}")

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_MATH_NAMES:
                raise ValueError("Only basic math functions are allowed.")

        if isinstance(node, ast.Name):
            if node.id not in _ALLOWED_MATH_NAMES:
                raise ValueError(f"Unknown name: {node.id}")

    return eval(compile(tree, "<safe_math>", "eval"), {"__builtins__": {}}, _ALLOWED_MATH_NAMES)


def _extract_simple_math(message: str) -> Optional[str]:
    s = message.strip()

    # Exact arithmetic expression.
    if re.fullmatch(r"[0-9\.\s\+\-\*\/\^\(\)%]+", s):
        return s

    # Natural language wrappers like "what is 5+7?"
    m = re.search(r"(-?\d+(?:\.\d+)?\s*[\+\-\*\/\^]\s*-?\d+(?:\.\d+)?(?:\s*[\+\-\*\/\^]\s*-?\d+(?:\.\d+)?)*)", s)
    if m and len(s) <= 80:
        return m.group(1)

    return None


def _format_number(x: Any) -> str:
    try:
        f = float(x)
        if abs(f - round(f)) < 1e-12:
            return str(int(round(f)))
        return f"{f:.6g}"
    except Exception:
        return str(x)


def _is_greeting_or_capability_question(message: str) -> bool:
    s = message.lower().strip()

    greetings = [
        "hi",
        "hello",
        "hey",
        "ciao",
        "buongiorno",
        "buonasera",
        "test",
        "what can you do",
        "what can u do",
        "cosa puoi fare",
        "help",
        "aiuto",
        "who are you",
        "chi sei",
    ]

    return any(g in s for g in greetings) and len(s) < 180


def _well_mentions(message: str) -> List[str]:
    out = []
    for m in re.finditer(r"\b[A-Za-z]{1,5}[-_ ]?\d+[A-Za-z]?\b", message):
        raw = m.group(0)
        compact = raw.upper().replace(" ", "-").replace("_", "-")
        if compact.startswith("P10") or compact.startswith("P50") or compact.startswith("P90"):
            continue
        out.append(compact)
    return out


def _reservoir_relevance_score(message: str) -> Tuple[int, List[str]]:
    s = message.lower()
    reasons: List[str] = []
    score = 0

    domain_terms = {
        "reservoir": 3,
        "well": 3,
        "wells": 3,
        "history match": 5,
        "history-match": 5,
        "hm": 2,
        "oil": 3,
        "gas": 3,
        "water": 3,
        "wct": 5,
        "gor": 4,
        "bhp": 4,
        "pressure": 3,
        "production": 3,
        "profile": 3,
        "mismatch": 4,
        "simulated": 3,
        "observed": 3,
        "tran": 5,
        "transmissibility": 5,
        "corridor": 4,
        "streamline": 5,
        "streamlines": 5,
        "perm": 3,
        "permx": 4,
        "poro": 3,
        "swat": 4,
        "relperm": 5,
        "relative permeability": 5,
        "connectivity": 4,
        "cluster": 3,
        "map": 2,
        "p10": 2,
        "p50": 2,
        "p90": 2,
        "aquifer": 3,
        "breakthrough": 4,
        "forecast": 2,
    }

    for term, weight in domain_terms.items():
        if term in s:
            score += weight
            reasons.append(term)

    wells = _well_mentions(message)
    if wells:
        score += 5
        reasons.append("well_name_detected:" + ",".join(wells[:4]))

    return score, reasons


def _looks_reservoir_question(message: str) -> bool:
    score, _ = _reservoir_relevance_score(message)

    if score >= 5:
        return True

    # Imperative visual words with model/well-ish context.
    s = message.lower()
    if any(x in s for x in ["show", "plot", "map", "display", "visualize"]) and _well_mentions(message):
        return True

    return False


def _is_complex_reservoir_diagnosis(message: str) -> bool:
    s = message.lower()

    complexity_terms = [
        "why",
        "explain",
        "diagnosis",
        "happening",
        "cause",
        "driver",
        "root cause",
        "mismatch",
        "compare",
        "align",
        "connectivity",
        "relperm",
        "water issue",
        "water mismatch",
        "wct mismatch",
        "more likely",
        "evidence",
    ]

    if any(t in s for t in complexity_terms) and (
        "water" in s or "wct" in s or "mismatch" in s or "connect" in s or "tran" in s
    ):
        return True

    return False


def _infer_primary_well(message: str) -> Optional[str]:
    wells = _well_mentions(message)
    if not wells:
        return None

    # Convert HW-28 style to HW-28 consistently.
    w = wells[0].upper()
    m = re.match(r"([A-Z]+)-?(\d+[A-Z]?)$", w)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    return w


def _response_task(response: Dict[str, Any]) -> str:
    ui = response.get("universal_intent_v500") or {}
    if isinstance(ui, dict):
        return str(ui.get("task_type") or "")
    return ""


def _response_agent_keys(response: Dict[str, Any]) -> List[str]:
    trace = response.get("agent_trace") or {}
    if isinstance(trace, dict):
        return list(trace.keys())
    return []


def _response_ui_blocks(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks = response.get("ui_blocks") or []
    return [b for b in blocks if isinstance(b, dict)]


def _ui_block_types(blocks: List[Dict[str, Any]]) -> List[str]:
    return [str(b.get("type") or "") for b in blocks if isinstance(b, dict)]


def _specialist_name_from_response(response: Dict[str, Any], fallback: str) -> str:
    keys = _response_agent_keys(response)
    for k in keys:
        kl = k.lower()
        if "router" in kl or "orchestrator" in kl or "trace" in kl or "formatter" in kl:
            continue
        return k
    return fallback


def _call_reservoir_tool(
    subquery: str,
    tool_label: str,
    edges: List[Dict[str, Any]],
    trace: Dict[str, Any],
    tool_outputs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    edges.append({
        "source": "ReservoirCopilotBrainV700",
        "target": tool_label,
        "relation": "tool_call_requested",
        "reason": subquery,
        "timestamp": _now_iso(),
    })

    try:
        response = _run_reservoir_runtime_v501(subquery)

        if not isinstance(response, dict):
            response = {
                "type": "reasoning_response",
                "answer": str(response),
                "ui_blocks": [],
                "agent_trace": {},
            }

        specialist = _specialist_name_from_response(response, tool_label)

        edges.append({
            "source": tool_label,
            "target": specialist,
            "relation": "runtime_exposed_specialist",
            "reason": "Specialist observed in returned agent_trace.",
            "timestamp": _now_iso(),
        })

        edges.append({
            "source": specialist,
            "target": "ReservoirCopilotBrainV700",
            "relation": "returned_evidence",
            "evidence_preview": _compact_text(response.get("answer") or response.get("message"), 350),
            "ui_block_types": _ui_block_types(_response_ui_blocks(response)),
            "timestamp": _now_iso(),
        })

        trace[tool_label] = {
            "status": "completed",
            "subquery": subquery,
            "response_type": response.get("type"),
            "intent": response.get("intent"),
            "task_type": _response_task(response),
            "ui_block_types": _ui_block_types(_response_ui_blocks(response)),
            "exposed_runtime_trace_keys": _response_agent_keys(response),
        }

        tool_outputs.append({
            "tool_label": tool_label,
            "subquery": subquery,
            "response": response,
        })

        return response

    except Exception as exc:
        err = "".join(traceback.format_exception_only(type(exc), exc)).strip()

        edges.append({
            "source": tool_label,
            "target": "ReservoirCopilotBrainV700",
            "relation": "tool_call_failed",
            "error": err,
            "timestamp": _now_iso(),
        })

        trace[tool_label] = {
            "status": "failed",
            "subquery": subquery,
            "error": err,
        }

        response = {
            "type": "reasoning_response",
            "intent": "tool_error",
            "answer": f"{tool_label} failed: {err}",
            "ui_blocks": [],
            "agent_trace": {},
        }

        tool_outputs.append({
            "tool_label": tool_label,
            "subquery": subquery,
            "response": response,
        })

        return response


def _merge_visual_blocks(tool_outputs: List[Dict[str, Any]], max_blocks: int = 6) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []

    seen = set()

    for item in tool_outputs:
        response = item.get("response") or {}
        for block in _response_ui_blocks(response):
            btype = str(block.get("type") or "")
            key = (item.get("tool_label"), btype, str(block.get("title") or "")[:80])
            if key in seen:
                continue
            seen.add(key)
            blocks.append(block)
            if len(blocks) >= max_blocks:
                return blocks

    return blocks


def _critic_rank_hypotheses(message: str, tool_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    evidence_text = " ".join(
        _compact_text((item.get("response") or {}).get("answer") or (item.get("response") or {}).get("message"), 800)
        for item in tool_outputs
    ).lower()

    score_connectivity = 0
    score_relperm = 0
    score_profile = 0
    score_pressure = 0

    for term in ["tran", "transmissibility", "corridor", "connectivity", "communicate", "communication"]:
        if term in evidence_text:
            score_connectivity += 2

    for term in ["relperm", "relative permeability", "mobility", "endpoint", "water mobility"]:
        if term in evidence_text:
            score_relperm += 2

    for term in ["profile", "simulated", "observed", "wct", "water"]:
        if term in evidence_text:
            score_profile += 1

    for term in ["pressure", "bhp", "depletion"]:
        if term in evidence_text:
            score_pressure += 1

    hypotheses = [
        {
            "hypothesis": "local_connectivity_or_TRAN",
            "score": score_connectivity,
            "interpretation": "Supported when TRAN/connectivity/corridor evidence is present.",
        },
        {
            "hypothesis": "relative_permeability_or_water_mobility",
            "score": score_relperm,
            "interpretation": "Supported when timing/shape suggest mobility/endpoints rather than only connectivity.",
        },
        {
            "hypothesis": "profile_level_or_timing_mismatch",
            "score": score_profile,
            "interpretation": "Supported by direct simulated-vs-observed water/WCT profile evidence.",
        },
        {
            "hypothesis": "pressure_support_or_BHP_connectivity",
            "score": score_pressure,
            "interpretation": "Supported when BHP/pressure evidence is part of the mismatch.",
        },
    ]

    hypotheses.sort(key=lambda x: x["score"], reverse=True)

    leading = hypotheses[0] if hypotheses else None

    return {
        "critic": "ReservoirCriticAgentV700",
        "method": "evidence_weighting_from_real_tool_outputs",
        "leading_hypothesis": leading,
        "ranked_hypotheses": hypotheses,
        "note": "Scores are computed from evidence returned by real specialist calls, not from a hard-coded final answer.",
    }


def _build_direct_response(message: str, answer: str, intent: str, task: str = "direct_answer") -> Dict[str, Any]:
    edges = [
        {
            "source": "ReservoirCopilotBrainV700",
            "target": "DirectAnswerAgentV700",
            "relation": "direct_response_selected",
            "reason": intent,
            "timestamp": _now_iso(),
        },
        {
            "source": "DirectAnswerAgentV700",
            "target": "FinalAnswerSynthesizerV700",
            "relation": "final_answer_prepared",
            "timestamp": _now_iso(),
        },
    ]

    return {
        "type": "reasoning_response",
        "intent": intent,
        "answer": answer,
        "ui_blocks": [],
        "agent_trace": {
            "ReservoirCopilotBrainV700": {
                "status": "completed",
                "decision": "direct_answer",
                "input": message,
            },
            "DirectAnswerAgentV700": {
                "status": "completed",
                "answer_preview": _compact_text(answer, 200),
            },
            "FinalAnswerSynthesizerV700": {
                "status": "completed",
            },
        },
        "interaction_edges": edges,
        "collaboration_summary": {
            "mode": "direct_general_chat",
            "agent_count": 3,
            "edge_count": len(edges),
            "real_edges": True,
        },
        "universal_intent_v500": {
            "task_type": task,
            "v700_copilot_mode": "direct_answer",
        },
    }


def _general_capability_answer() -> str:
    return (
        "I can answer simple general questions, do basic calculations, and act as a reservoir copilot for the imported demo model. "
        "For reservoir questions I can call specialist tools for well profiles, WCT bias, gas/oil/BHP diagnostics, TRAN corridors, "
        "streamlines, clustering, property maps and integrated history-match diagnosis. "
        "Try for example: 'Why is HW-28 water mismatch happening?', 'Show me WCT bias cluster map', "
        "'Show TRAN multiplier corridor for HW-28', or 'show me streamlines at the beginning'."
    )


def _build_single_reservoir_response(message: str) -> Dict[str, Any]:
    edges: List[Dict[str, Any]] = []
    trace: Dict[str, Any] = {
        "ReservoirCopilotBrainV700": {
            "status": "completed",
            "decision": "single_reservoir_tool_call",
            "input": message,
            "reservoir_relevance": _reservoir_relevance_score(message),
        }
    }
    tool_outputs: List[Dict[str, Any]] = []

    response = _call_reservoir_tool(
        message,
        "ReservoirRuntimeToolV501",
        edges,
        trace,
        tool_outputs,
    )

    critic = {
        "critic": "ReservoirCriticAgentV700",
        "status": "completed",
        "review": "Single specialist route returned by existing reservoir runtime. No additional evidence requested by planner.",
        "response_type": response.get("type"),
        "task_type": _response_task(response),
    }

    trace["ReservoirCriticAgentV700"] = critic

    edges.append({
        "source": "ReservoirRuntimeToolV501",
        "target": "ReservoirCriticAgentV700",
        "relation": "specialist_output_reviewed",
        "timestamp": _now_iso(),
    })
    edges.append({
        "source": "ReservoirCriticAgentV700",
        "target": "FinalAnswerSynthesizerV700",
        "relation": "reviewed_output_sent_to_final_synthesizer",
        "timestamp": _now_iso(),
    })

    trace["FinalAnswerSynthesizerV700"] = {
        "status": "completed",
        "mode": "single_tool_passthrough_with_edges",
    }

    # Preserve specialist output but add real V700 interaction edges and copilot trace.
    out = dict(response)
    out.setdefault("ui_blocks", response.get("ui_blocks") or [])
    out["agent_trace"] = {
        **trace,
        "SpecialistRuntimeTraceV501": {
            "status": "completed",
            "trace_keys": _response_agent_keys(response),
            "trace": response.get("agent_trace") or {},
        },
    }
    out["interaction_edges"] = edges
    out["collaboration_summary"] = {
        "mode": "single_reservoir_tool_call",
        "agent_count": len(out["agent_trace"]),
        "edge_count": len(edges),
        "real_edges": True,
        "note": "Edges were recorded by V700 at the time it called the real reservoir runtime tool.",
    }

    ui = out.get("universal_intent_v500") or {}
    if isinstance(ui, dict):
        ui["v700_copilot_mode"] = "single_reservoir_tool_call"
        out["universal_intent_v500"] = ui
    else:
        out["universal_intent_v500"] = {
            "task_type": _response_task(response),
            "v700_copilot_mode": "single_reservoir_tool_call",
        }

    return out


def _build_complex_reservoir_response(message: str) -> Dict[str, Any]:
    well = _infer_primary_well(message) or "HW-28"

    edges: List[Dict[str, Any]] = []
    trace: Dict[str, Any] = {
        "ReservoirCopilotBrainV700": {
            "status": "completed",
            "decision": "multi_agent_reservoir_diagnosis",
            "input": message,
            "primary_well": well,
            "reservoir_relevance": _reservoir_relevance_score(message),
        },
        "EvidencePlannerV700": {
            "status": "completed",
            "plan": [
                "collect_direct_water_or_profile_evidence",
                "collect_WCT_bias_spatial_cluster_evidence",
                "collect_TRAN_or_connectivity_evidence",
                "review_competing_hypotheses_with_critic",
            ],
        },
    }

    edges.append({
        "source": "ReservoirCopilotBrainV700",
        "target": "EvidencePlannerV700",
        "relation": "requested_dynamic_evidence_plan",
        "reason": "Question requires more than one evidence source.",
        "timestamp": _now_iso(),
    })

    tool_outputs: List[Dict[str, Any]] = []

    subqueries = [
        (
            f"Show me {well} water production",
            "DynamicProfileAgentToolV700",
        ),
        (
            "Show me WCT bias cluster map and explain it.",
            "WCTBiasDiagnosticAgentToolV700",
        ),
        (
            f"Show TRAN multiplier corridor for {well}.",
            "TRANCorridorVisualAgentToolV700",
        ),
    ]

    for subquery, tool_label in subqueries:
        edges.append({
            "source": "EvidencePlannerV700",
            "target": tool_label,
            "relation": "selected_specialist_for_parallel_evidence",
            "reason": subquery,
            "timestamp": _now_iso(),
        })
        _call_reservoir_tool(subquery, tool_label, edges, trace, tool_outputs)

    critic = _critic_rank_hypotheses(message, tool_outputs)

    trace["ReservoirCriticAgentV700"] = {
        "status": "completed",
        **critic,
    }

    for item in tool_outputs:
        edges.append({
            "source": item["tool_label"],
            "target": "ReservoirCriticAgentV700",
            "relation": "submitted_evidence_for_hypothesis_review",
            "subquery": item["subquery"],
            "timestamp": _now_iso(),
        })

    edges.append({
        "source": "ReservoirCriticAgentV700",
        "target": "FinalAnswerSynthesizerV700",
        "relation": "ranked_hypotheses_sent_to_synthesizer",
        "leading_hypothesis": (critic.get("leading_hypothesis") or {}).get("hypothesis"),
        "timestamp": _now_iso(),
    })

    trace["FinalAnswerSynthesizerV700"] = {
        "status": "completed",
        "mode": "multi_agent_evidence_synthesis",
    }

    evidence_lines = []
    for item in tool_outputs:
        resp = item.get("response") or {}
        evidence_lines.append(
            f"- {item['tool_label']}: {_compact_text(resp.get('answer') or resp.get('message'), 450)}"
        )

    leading = critic.get("leading_hypothesis") or {}
    ranked = critic.get("ranked_hypotheses") or []

    answer = (
        f"I treated this as a multi-agent reservoir diagnosis for {well}. "
        "I collected separate evidence from profile, WCT-bias/spatial clustering and TRAN/connectivity tools, then passed the evidence to a critic for hypothesis ranking.\n\n"
        "Evidence gathered:\n"
        + "\n".join(evidence_lines)
        + "\n\nCritic ranking:\n"
        + "\n".join(
            f"- {h['hypothesis']}: score={h['score']} — {h['interpretation']}"
            for h in ranked
        )
        + "\n\n"
        + f"Leading hypothesis from the critic: {leading.get('hypothesis', 'not available')}. "
        "Use the visual blocks below as supporting evidence rather than as independent final conclusions."
    )

    ui_blocks = _merge_visual_blocks(tool_outputs, max_blocks=6)

    return {
        "type": "visual_response" if ui_blocks else "reasoning_response",
        "intent": "v700_multi_agent_reservoir_diagnosis",
        "answer": answer,
        "ui_blocks": ui_blocks,
        "agent_trace": trace,
        "interaction_edges": edges,
        "collaboration_summary": {
            "mode": "multi_agent_reservoir_diagnosis",
            "agent_count": len(trace),
            "edge_count": len(edges),
            "real_edges": True,
            "tools_called": [x["tool_label"] for x in tool_outputs],
            "leading_hypothesis": leading,
            "note": "Edges were recorded at runtime when V700 requested evidence from real specialist tools.",
        },
        "universal_intent_v500": {
            "task_type": "v700_multi_agent_reservoir_diagnosis",
            "primary_well": well,
            "v700_copilot_mode": "multi_agent_reservoir_diagnosis",
        },
        "data": {
            "tool_outputs_summary": [
                {
                    "tool_label": x["tool_label"],
                    "subquery": x["subquery"],
                    "response_type": (x.get("response") or {}).get("type"),
                    "task_type": _response_task(x.get("response") or {}),
                    "ui_block_types": _ui_block_types(_response_ui_blocks(x.get("response") or {})),
                }
                for x in tool_outputs
            ],
            "critic": critic,
        },
    }


def run_copilot_orchestrator_v700(message: str) -> Dict[str, Any]:
    message = str(message or "").strip()

    if not message:
        return _build_direct_response(
            message,
            "Please ask a question. I can answer general questions or run reservoir diagnostics on the imported demo model.",
            "empty_input",
            "direct_answer",
        )

    math_expr = _extract_simple_math(message)

    if math_expr:
        try:
            val = _safe_calc(math_expr)
            return _build_direct_response(
                message,
                f"{math_expr} = {_format_number(val)}",
                "simple_math",
                "direct_answer_simple_math",
            )
        except Exception:
            pass

    if _is_greeting_or_capability_question(message):
        return _build_direct_response(
            message,
            _general_capability_answer(),
            "general_chat_capabilities",
            "direct_answer_general_chat",
        )

    if not _looks_reservoir_question(message):
        return _build_direct_response(
            message,
            (
                "I can answer simple general questions and I am especially useful as a reservoir copilot for the imported demo model. "
                "This message does not look like a reservoir-model request, so I did not force it into a reservoir workflow. "
                "Ask me for profiles, WCT bias, TRAN corridors, streamlines, clustering, property maps, or history-match diagnosis when you want model-specific analysis."
            ),
            "general_or_out_of_scope",
            "direct_answer_out_of_scope",
        )

    if _is_complex_reservoir_diagnosis(message):
        return _build_complex_reservoir_response(message)

    return _build_single_reservoir_response(message)


def submission_payload_from_response(message: str, response: Dict[str, Any]) -> Dict[str, Any]:
    ui = response.get("universal_intent_v500") or {}
    task = ""

    if isinstance(ui, dict):
        task = str(ui.get("task_type") or "")

    ui_blocks = response.get("ui_blocks") or []
    ui_block_types = [
        b.get("type")
        for b in ui_blocks
        if isinstance(b, dict)
    ]

    return {
        "status": "success",
        "input": {
            "message": message,
        },
        "output": {
            "answer": response.get("answer") or response.get("message") or "",
            "type": response.get("type"),
            "intent": response.get("intent"),
            "task_type": task,
            "ui_blocks_count": len(ui_blocks),
            "ui_block_types": ui_block_types,
            "agent_trace": response.get("agent_trace") or {},
            "interaction_edges": response.get("interaction_edges") or [],
            "collaboration_summary": response.get("collaboration_summary") or {},
        },
        "raw_response": response,
    }


def run_submission_message_v700(message: str) -> Dict[str, Any]:
    response = run_copilot_orchestrator_v700(message)
    return submission_payload_from_response(message, response)


# V700_BODY_ROUTE_FIX
# Use Body(...) instead of Request to avoid FastAPI interpreting "request"
# as a required query parameter under postponed annotations.
def install_v700_routes(app) -> None:
    paths_to_replace = {
        "/run",
        "/api/agent-chat-v501",
        "/api/agent-chat",
        "/api/chat",
    }

    app.router.routes = [
        route for route in app.router.routes
        if not (
            getattr(route, "path", None) in paths_to_replace
            and "POST" in getattr(route, "methods", set())
        )
    ]

    @app.post("/run")
    async def run_endpoint_v700(payload: Dict[str, Any] = Body(...)):
        try:
            message = _extract_message(payload)
            return JSONResponse(run_submission_message_v700(message))
        except Exception as exc:
            return JSONResponse(
                {
                    "status": "error",
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
                status_code=500,
            )

    @app.post("/api/agent-chat-v501")
    async def agent_chat_v501_v700(payload: Dict[str, Any] = Body(...)):
        try:
            message = _extract_message(payload)
            response = run_copilot_orchestrator_v700(message)
            return JSONResponse(response)
        except Exception as exc:
            return JSONResponse(
                {
                    "type": "reasoning_response",
                    "intent": "v700_error",
                    "answer": f"Copilot error: {exc}",
                    "ui_blocks": [],
                    "agent_trace": {
                        "ReservoirCopilotBrainV700": {
                            "status": "failed",
                            "error": str(exc),
                        }
                    },
                    "interaction_edges": [],
                },
                status_code=500,
            )

    @app.post("/api/agent-chat")
    async def agent_chat_v700_alias(payload: Dict[str, Any] = Body(...)):
        try:
            message = _extract_message(payload)
            response = run_copilot_orchestrator_v700(message)
            return JSONResponse(response)
        except Exception as exc:
            return JSONResponse(
                {
                    "type": "reasoning_response",
                    "intent": "v700_error",
                    "answer": f"Copilot error: {exc}",
                    "ui_blocks": [],
                    "agent_trace": {
                        "ReservoirCopilotBrainV700": {
                            "status": "failed",
                            "error": str(exc),
                        }
                    },
                    "interaction_edges": [],
                },
                status_code=500,
            )

    @app.post("/api/chat")
    async def chat_v700_alias(payload: Dict[str, Any] = Body(...)):
        try:
            message = _extract_message(payload)
            response = run_copilot_orchestrator_v700(message)
            return JSONResponse(response)
        except Exception as exc:
            return JSONResponse(
                {
                    "type": "reasoning_response",
                    "intent": "v700_error",
                    "answer": f"Copilot error: {exc}",
                    "ui_blocks": [],
                    "agent_trace": {
                        "ReservoirCopilotBrainV700": {
                            "status": "failed",
                            "error": str(exc),
                        }
                    },
                    "interaction_edges": [],
                },
                status_code=500,
            )

    print("[OK] V700 Body-based routes installed: /run, /api/agent-chat-v501, /api/agent-chat, /api/chat")


# ==========================================================
# V800 LLM COPILOT PLANNER
#
# Purpose:
# - Use an LLM as the general conversational brain when available.
# - Answer general questions directly.
# - Use reservoir runtime as tools only for imported-model questions.
# - Record real interaction_edges when tools are actually called.
# - Fall back to V700 deterministic behaviour when no LLM key is available.
# ==========================================================

def _v800_llm_available() -> bool:
    if os.environ.get("V800_DISABLE_LLM", "").strip().lower() in {"1", "true", "yes"}:
        return False

    if os.environ.get("OPENAI_API_KEY"):
        return True

    if os.environ.get("COMPASS_API_KEY") and (os.environ.get("COMPASS_BASE_URL") or os.environ.get("COMPASS_API_BASE_URL")):
        return True

    return False


def _v800_openai_client():
    try:
        from openai import OpenAI
    except Exception:
        return None

    if os.environ.get("OPENAI_API_KEY"):
        return OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
        )

    if os.environ.get("COMPASS_API_KEY") and (os.environ.get("COMPASS_BASE_URL") or os.environ.get("COMPASS_API_BASE_URL")):
        return OpenAI(
            api_key=os.environ.get("COMPASS_API_KEY"),
            base_url=os.environ.get("COMPASS_BASE_URL"),
        )

    return None


def _v800_extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    raw = str(text).strip()

    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw.strip(), flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw.strip()).strip()

    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    m = re.search(r"\{[\s\S]*\}", raw)

    if not m:
        return None

    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _v800_planner_prompt(message: str) -> str:
    return f"""
You are the V800 Reservoir Copilot Brain.

You are a general conversational assistant AND a reservoir-engineering copilot.

Your job is to classify the user message semantically, not by simple keywords.

You have two kinds of abilities:

1. Direct general answer:
   Use this for normal questions, arithmetic, geography, definitions, general technical explanations, small talk, and conceptual reservoir engineering questions.
   Examples:
   - "5+7" -> direct_answer, answer "5 + 7 = 12"
   - "where is Abu Dhabi?" -> direct_answer, answer that Abu Dhabi is in the United Arab Emirates and is its capital
   - "what is a reservoir?" -> direct_answer, explain oil and gas reservoir concept
   - "what is WCT?" -> direct_answer, explain water cut concept

2. Reservoir model tools:
   Use these only when the user asks about the imported/demo reservoir model, wells, maps, profiles, history match quality, WCT mismatch, TRAN corridors, streamlines, clustering, or model-specific diagnosis.
   Available reservoir tool labels:
   - ExecutiveHMSummaryAgentToolV800
   - DynamicProfileAgentToolV800
   - WCTBiasDiagnosticAgentToolV800
   - TRANCorridorVisualAgentToolV800
   - StreamlineTimesliceVisualAgentToolV800
   - IntegratedReservoirDiagnosisToolV800
   - ReservoirRuntimeToolV501

Important:
- Do not answer model-specific reservoir questions from general knowledge. Use tools.
- Do not force general questions into reservoir tools.
- A question like "Give me an executive summary of the history match quality" is model-specific and should use reservoir tools.
- A question like "Why is HW-28 water mismatch happening?" is model-specific and should use multiple tools.
- A question like "Show TRAN multiplier corridor for HW-28" is model-specific and should use the TRAN corridor tool.
- A question like "what is a reservoir?" is conceptual and should be answered directly.

Return JSON only, with this schema:
{{
  "mode": "direct_answer" | "clarification_needed" | "reservoir_single_tool" | "reservoir_multi_agent",
  "reason": "brief reason",
  "answer": "direct answer only for direct_answer or clarification_needed",
  "primary_well": "HW-28 or null",
  "tool_plan": [
    {{
      "tool_label": "one of the available tool labels",
      "subquery": "exact natural-language subquery to send to the reservoir runtime"
    }}
  ]
}}

User message:
{message}
""".strip()


def _v800_call_llm_planner(message: str) -> Optional[Dict[str, Any]]:
    if not _v800_llm_available():
        return None

    client = _v800_openai_client()

    if client is None:
        return None

    model = (
        os.environ.get("V800_LLM_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or os.environ.get("COMPASS_MODEL")
        or "gpt-4o-mini"
    )

    prompt = _v800_planner_prompt(message)

    try:
        # Prefer Responses API when available.
        if hasattr(client, "responses"):
            resp = client.responses.create(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": "You are a precise JSON-only planning model for a reservoir copilot."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0,
            )

            txt = getattr(resp, "output_text", None)

            if not txt:
                txt = str(resp)

            plan = _v800_extract_json(txt)

            if plan:
                return plan

        # Fallback to Chat Completions for older SDK / compatible gateways.
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise JSON-only planning model for a reservoir copilot."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
        )

        txt = resp.choices[0].message.content
        return _v800_extract_json(txt)

    except Exception as exc:
        print("[WARN] V800 LLM planner failed:", exc)
        return None


def _v800_tool_label_for_subquery(label: str, subquery: str) -> str:
    label = (label or "").strip()

    if label:
        return label

    s = subquery.lower()

    if "executive" in s or "summary" in s or "history match quality" in s:
        return "ExecutiveHMSummaryAgentToolV800"

    if "wct" in s or "water cut" in s:
        return "WCTBiasDiagnosticAgentToolV800"

    if "tran" in s or "corridor" in s or "transmissibility" in s:
        return "TRANCorridorVisualAgentToolV800"

    if "streamline" in s:
        return "StreamlineTimesliceVisualAgentToolV800"

    if "profile" in s or "production" in s or "bhp" in s:
        return "DynamicProfileAgentToolV800"

    return "ReservoirRuntimeToolV501"


def _v800_direct_response(message: str, plan: Dict[str, Any]) -> Dict[str, Any]:
    answer = str(plan.get("answer") or "").strip()

    if not answer:
        answer = "I can answer that directly, but the planner did not provide an answer."

    resp = _build_direct_response(
        message,
        answer,
        "v800_direct_answer",
        "v800_direct_answer",
    )

    resp["agent_trace"] = {
        "LLMCopilotBrainV800": {
            "status": "completed",
            "decision": "direct_answer",
            "reason": plan.get("reason"),
            "llm_planner_used": True,
        },
        **(resp.get("agent_trace") or {}),
    }

    resp["interaction_edges"] = [
        {
            "source": "LLMCopilotBrainV800",
            "target": "DirectAnswerAgentV700",
            "relation": "selected_direct_answer",
            "reason": plan.get("reason"),
            "timestamp": _now_iso(),
        },
        *list(resp.get("interaction_edges") or []),
    ]

    resp["collaboration_summary"] = {
        "mode": "v800_direct_answer",
        "llm_planner_used": True,
        "agent_count": len(resp["agent_trace"]),
        "edge_count": len(resp["interaction_edges"]),
        "real_edges": True,
    }

    resp["universal_intent_v500"] = {
        "task_type": "v800_direct_answer",
        "v800_mode": "direct_answer",
        "llm_planner_used": True,
    }

    return resp


def _v800_reservoir_response(message: str, plan: Dict[str, Any]) -> Dict[str, Any]:
    mode = str(plan.get("mode") or "").strip()
    tool_plan = plan.get("tool_plan") or []

    if not isinstance(tool_plan, list) or not tool_plan:
        tool_plan = [
            {
                "tool_label": "ReservoirRuntimeToolV501",
                "subquery": message,
            }
        ]

    edges: List[Dict[str, Any]] = []
    trace: Dict[str, Any] = {
        "LLMCopilotBrainV800": {
            "status": "completed",
            "decision": mode,
            "reason": plan.get("reason"),
            "primary_well": plan.get("primary_well"),
            "llm_planner_used": True,
        },
        "EvidencePlannerV800": {
            "status": "completed",
            "tool_plan": tool_plan,
        },
    }

    edges.append({
        "source": "LLMCopilotBrainV800",
        "target": "EvidencePlannerV800",
        "relation": "semantic_plan_created",
        "reason": plan.get("reason"),
        "timestamp": _now_iso(),
    })

    tool_outputs: List[Dict[str, Any]] = []

    for item in tool_plan:
        if not isinstance(item, dict):
            continue

        subquery = str(item.get("subquery") or message).strip()
        label = _v800_tool_label_for_subquery(str(item.get("tool_label") or ""), subquery)

        edges.append({
            "source": "EvidencePlannerV800",
            "target": label,
            "relation": "selected_tool_from_llm_plan",
            "reason": subquery,
            "timestamp": _now_iso(),
        })

        _call_reservoir_tool(
            subquery,
            label,
            edges,
            trace,
            tool_outputs,
        )

    if not tool_outputs:
        return _build_single_reservoir_response(message)

    if mode == "reservoir_single_tool" and len(tool_outputs) == 1:
        base = dict(tool_outputs[0]["response"])

        edges.append({
            "source": tool_outputs[0]["tool_label"],
            "target": "ReservoirCriticAgentV800",
            "relation": "single_tool_output_reviewed",
            "timestamp": _now_iso(),
        })

        edges.append({
            "source": "ReservoirCriticAgentV800",
            "target": "FinalAnswerSynthesizerV800",
            "relation": "reviewed_answer_sent_to_user",
            "timestamp": _now_iso(),
        })

        trace["ReservoirCriticAgentV800"] = {
            "status": "completed",
            "review": "Single reservoir tool selected by LLM planner and returned evidence.",
        }

        trace["FinalAnswerSynthesizerV800"] = {
            "status": "completed",
            "mode": "single_tool_synthesis",
        }

        base["agent_trace"] = {
            **trace,
            "SpecialistRuntimeTraceV501": {
                "status": "completed",
                "trace": base.get("agent_trace") or {},
            }
        }

        base["interaction_edges"] = edges
        base["collaboration_summary"] = {
            "mode": "v800_reservoir_single_tool",
            "llm_planner_used": True,
            "tools_called": [tool_outputs[0]["tool_label"]],
            "agent_count": len(base["agent_trace"]),
            "edge_count": len(edges),
            "real_edges": True,
        }

        ui = base.get("universal_intent_v500") or {}

        if isinstance(ui, dict):
            ui["v800_mode"] = "reservoir_single_tool"
            ui["llm_planner_used"] = True
            base["universal_intent_v500"] = ui
        else:
            base["universal_intent_v500"] = {
                "task_type": _response_task(base),
                "v800_mode": "reservoir_single_tool",
                "llm_planner_used": True,
            }

        return base

    critic = _critic_rank_hypotheses(message, tool_outputs)

    trace["ReservoirCriticAgentV800"] = {
        "status": "completed",
        **critic,
    }

    for item in tool_outputs:
        edges.append({
            "source": item["tool_label"],
            "target": "ReservoirCriticAgentV800",
            "relation": "submitted_evidence_for_hypothesis_review",
            "subquery": item["subquery"],
            "timestamp": _now_iso(),
        })

    edges.append({
        "source": "ReservoirCriticAgentV800",
        "target": "FinalAnswerSynthesizerV800",
        "relation": "ranked_hypotheses_sent_to_synthesizer",
        "timestamp": _now_iso(),
    })

    trace["FinalAnswerSynthesizerV800"] = {
        "status": "completed",
        "mode": "multi_tool_synthesis",
    }

    evidence_lines = []

    for item in tool_outputs:
        response = item.get("response") or {}
        evidence_lines.append(
            f"- {item['tool_label']}: {_compact_text(response.get('answer') or response.get('message'), 450)}"
        )

    ranked = critic.get("ranked_hypotheses") or []
    leading = critic.get("leading_hypothesis") or {}

    answer = (
        "I treated this as a model-specific reservoir question and used the LLM planner to select reservoir tools. "
        "Then I collected evidence from the selected specialist outputs and passed it to the critic for synthesis.\n\n"
        "Evidence gathered:\n"
        + "\n".join(evidence_lines)
        + "\n\nCritic ranking:\n"
        + "\n".join(
            f"- {h['hypothesis']}: score={h['score']} — {h['interpretation']}"
            for h in ranked
        )
        + "\n\n"
        + f"Leading hypothesis: {leading.get('hypothesis', 'not available')}."
    )

    ui_blocks = _merge_visual_blocks(tool_outputs, max_blocks=8)

    return {
        "type": "visual_response" if ui_blocks else "reasoning_response",
        "intent": "v800_llm_planned_reservoir_multi_agent",
        "answer": answer,
        "ui_blocks": ui_blocks,
        "agent_trace": trace,
        "interaction_edges": edges,
        "collaboration_summary": {
            "mode": "v800_reservoir_multi_agent",
            "llm_planner_used": True,
            "tools_called": [x["tool_label"] for x in tool_outputs],
            "agent_count": len(trace),
            "edge_count": len(edges),
            "real_edges": True,
            "leading_hypothesis": leading,
        },
        "universal_intent_v500": {
            "task_type": "v800_llm_planned_reservoir_multi_agent",
            "v800_mode": "reservoir_multi_agent",
            "llm_planner_used": True,
            "primary_well": plan.get("primary_well"),
        },
        "data": {
            "llm_plan": plan,
            "critic": critic,
            "tool_outputs_summary": [
                {
                    "tool_label": x["tool_label"],
                    "subquery": x["subquery"],
                    "response_type": (x.get("response") or {}).get("type"),
                    "task_type": _response_task(x.get("response") or {}),
                    "ui_block_types": _ui_block_types(_response_ui_blocks(x.get("response") or {})),
                }
                for x in tool_outputs
            ],
        },
    }


def _v800_try_llm_response(message: str) -> Optional[Dict[str, Any]]:
    plan = _v800_call_llm_planner(message)

    if not plan:
        return None

    mode = str(plan.get("mode") or "").strip().lower()

    if mode in {"direct_answer", "general_answer", "general_technical_explanation", "clarification_needed"}:
        return _v800_direct_response(message, plan)

    if mode in {"reservoir_single_tool", "reservoir_multi_agent", "reservoir_multi_agent_diagnosis"}:
        return _v800_reservoir_response(message, plan)

    return None


# Override weak greeting detector with word-boundary version.
def _is_greeting_or_capability_question(message: str) -> bool:
    s = message.lower().strip()

    if len(s) > 180:
        return False

    greeting_patterns = [
        r"\bhi\b",
        r"\bhello\b",
        r"\bhey\b",
        r"\bciao\b",
        r"\bbuongiorno\b",
        r"\bbuonasera\b",
        r"\btest\b",
        r"\bhelp\b",
        r"\baiuto\b",
        r"\bwhat can you do\b",
        r"\bcosa puoi fare\b",
        r"\bwho are you\b",
        r"\bchi sei\b",
    ]

    return any(re.search(p, s) for p in greeting_patterns)


# Override main V700 function with V800-first behaviour.
def run_copilot_orchestrator_v700(message: str) -> Dict[str, Any]:
    message = str(message or "").strip()

    if not message:
        return _build_direct_response(
            message,
            "Please ask a question. I can answer general questions or run reservoir diagnostics on the imported demo model.",
            "empty_input",
            "direct_answer",
        )

    # Keep local arithmetic fast and deterministic.
    math_expr = _extract_simple_math(message)

    if math_expr:
        try:
            val = _safe_calc(math_expr)
            return _build_direct_response(
                message,
                f"{math_expr} = {_format_number(val)}",
                "simple_math",
                "direct_answer_simple_math",
            )
        except Exception:
            pass

    # True ChatGPT-like behaviour when an LLM is configured.
    v800_response = _v800_try_llm_response(message)

    if v800_response is not None:
        return v800_response

    # Fallback when no LLM key is available.
    # This fallback is not intended to be a general ChatGPT replacement.
    if _is_greeting_or_capability_question(message):
        return _build_direct_response(
            message,
            _general_capability_answer(),
            "general_chat_capabilities",
            "direct_answer_general_chat",
        )

    conceptual_answer = _conceptual_knowledge_answer(message) if "_conceptual_knowledge_answer" in globals() else None

    if conceptual_answer:
        return _build_direct_response(
            message,
            conceptual_answer,
            "general_conceptual_knowledge",
            "direct_answer_conceptual_knowledge",
        )

    if not _looks_reservoir_question(message):
        return _build_direct_response(
            message,
            (
                "I can answer simple local calculations, but a general ChatGPT-like answer requires an LLM key. "
                "Set OPENAI_API_KEY, or COMPASS_API_KEY plus COMPASS_BASE_URL, to enable the V800 general copilot brain. "
                "For model-specific reservoir questions I can still use the available reservoir agents."
            ),
            "general_or_out_of_scope_llm_not_configured",
            "direct_answer_out_of_scope",
        )

    if _is_complex_reservoir_diagnosis(message):
        return _build_complex_reservoir_response(message)

    return _build_single_reservoir_response(message)

# END V800 LLM COPILOT PLANNER


# ==========================================================
# V801 COMPASS / OPENAI-COMPATIBLE LLM CLIENT FIX
#
# Core42 / Compass gateways are usually OpenAI-compatible
# through chat.completions. Some gateways do not support the
# newer Responses API. V801 therefore tries chat.completions
# first and only then falls back to responses.
# ==========================================================

def _v801_env(name: str, default: str = "") -> str:
    return str(os.environ.get(name) or default).strip()


def _v800_llm_available() -> bool:
    if _v801_env("V800_DISABLE_LLM").lower() in {"1", "true", "yes"}:
        return False

    compass_key = _v801_env("COMPASS_API_KEY")
    compass_base = _v801_env("COMPASS_BASE_URL") or _v801_env("COMPASS_API_BASE_URL") or _v801_env("OPENAI_BASE_URL")

    openai_key = _v801_env("OPENAI_API_KEY")

    if compass_key and compass_base:
        return True

    if openai_key:
        return True

    return False


def _v800_openai_client():
    try:
        from openai import OpenAI
    except Exception as exc:
        print("[WARN] OpenAI SDK not installed or unavailable:", exc)
        return None

    compass_key = _v801_env("COMPASS_API_KEY")
    compass_base = _v801_env("COMPASS_BASE_URL") or _v801_env("COMPASS_API_BASE_URL") or _v801_env("OPENAI_BASE_URL")

    openai_key = _v801_env("OPENAI_API_KEY")
    openai_base = _v801_env("OPENAI_BASE_URL")

    if compass_key and compass_base:
        return OpenAI(
            api_key=compass_key,
            base_url=compass_base,
        )

    if openai_key:
        kwargs = {"api_key": openai_key}
        if openai_base:
            kwargs["base_url"] = openai_base
        return OpenAI(**kwargs)

    return None


def _v801_model_name() -> str:
    return (
        _v801_env("V800_LLM_MODEL")
        or _v801_env("COMPASS_MODEL")
        or _v801_env("CHAT_MODEL")
        or _v801_env("OPENAI_MODEL")
        or "gpt-4.1"
    )


def _v800_call_llm_planner(message: str) -> Optional[Dict[str, Any]]:
    if not _v800_llm_available():
        return None

    client = _v800_openai_client()

    if client is None:
        return None

    model = _v801_model_name()
    prompt = _v800_planner_prompt(message)

    # First try OpenAI-compatible Chat Completions.
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise JSON-only planning model for a reservoir copilot."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
        )

        txt = resp.choices[0].message.content
        plan = _v800_extract_json(txt)

        if plan:
            return plan

        print("[WARN] V801 chat.completions returned non-JSON planner output:", str(txt)[:300])

    except Exception as exc:
        print("[WARN] V801 chat.completions planner failed:", exc)

    # Then try Responses API as fallback for native OpenAI environments.
    try:
        if hasattr(client, "responses"):
            resp = client.responses.create(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": "You are a precise JSON-only planning model for a reservoir copilot."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0,
            )

            txt = getattr(resp, "output_text", None) or str(resp)
            plan = _v800_extract_json(txt)

            if plan:
                return plan

            print("[WARN] V801 responses returned non-JSON planner output:", str(txt)[:300])

    except Exception as exc:
        print("[WARN] V801 responses planner failed:", exc)

    return None

# END V801 COMPASS / OPENAI-COMPATIBLE LLM CLIENT FIX


# ==========================================================
# V802 RESERVOIR FALLBACK PATCH
#
# If the LLM planner is unavailable because of API/network issues,
# model-specific reservoir questions must still route to reservoir tools.
# This is not a general-chat replacement; it only protects reservoir demo behaviour.
# ==========================================================

def _v802_is_executive_hm_summary(message: str) -> bool:
    s = message.lower()
    return (
        ("executive" in s or "summary" in s or "summarize" in s)
        and ("history match" in s or "history-match" in s or "hm" in s or "match quality" in s)
    )


def _v802_is_reservoir_model_question(message: str) -> bool:
    s = message.lower()

    strong_phrases = [
        "history match",
        "history-match",
        "match quality",
        "wct bias",
        "water mismatch",
        "oil production",
        "gas production",
        "bhp",
        "tran",
        "transmissibility",
        "streamline",
        "streamlines",
        "corridor",
        "cluster map",
        "well profile",
        "hw-",
    ]

    if any(x in s for x in strong_phrases):
        return True

    if _well_mentions(message):
        return True

    return False


def _v802_local_reservoir_fallback(message: str) -> Optional[Dict[str, Any]]:
    s = message.lower()

    if _v802_is_executive_hm_summary(message):
        resp = _build_single_reservoir_response("Give me an executive summary of the history match quality.")
        resp["universal_intent_v500"] = {
            **(resp.get("universal_intent_v500") or {}),
            "task_type": (resp.get("universal_intent_v500") or {}).get("task_type") or "executive_hm_summary",
            "v802_fallback": "executive_hm_summary_without_llm",
        }
        resp["collaboration_summary"] = {
            **(resp.get("collaboration_summary") or {}),
            "v802_note": "LLM planner unavailable; routed executive HM summary to reservoir runtime fallback.",
        }
        return resp

    if _v802_is_reservoir_model_question(message):
        if "why" in s or "mismatch" in s or "compare" in s or "diagnos" in s:
            return _build_complex_reservoir_response(message)

        return _build_single_reservoir_response(message)

    return None


# Override V800 main function with safer reservoir fallback.
def run_copilot_orchestrator_v700(message: str) -> Dict[str, Any]:
    message = str(message or "").strip()

    if not message:
        return _build_direct_response(
            message,
            "Please ask a question. I can answer general questions when the LLM is configured, or run reservoir diagnostics on the imported demo model.",
            "empty_input",
            "direct_answer",
        )

    math_expr = _extract_simple_math(message)

    if math_expr:
        try:
            val = _safe_calc(math_expr)
            return _build_direct_response(
                message,
                f"{math_expr} = {_format_number(val)}",
                "simple_math",
                "direct_answer_simple_math",
            )
        except Exception:
            pass

    # Try real LLM planner first.
    v800_response = _v800_try_llm_response(message)

    if v800_response is not None:
        return v800_response

    # If LLM is down/unreachable, protect reservoir-model behaviour.
    reservoir_fallback = _v802_local_reservoir_fallback(message)

    if reservoir_fallback is not None:
        return reservoir_fallback

    # Conceptual fallback remains available for known reservoir concepts.
    conceptual_answer = _conceptual_knowledge_answer(message) if "_conceptual_knowledge_answer" in globals() else None

    if conceptual_answer:
        return _build_direct_response(
            message,
            conceptual_answer,
            "general_conceptual_knowledge",
            "direct_answer_conceptual_knowledge",
        )

    if _is_greeting_or_capability_question(message):
        return _build_direct_response(
            message,
            _general_capability_answer(),
            "general_chat_capabilities",
            "direct_answer_general_chat",
        )

    return _build_direct_response(
        message,
        (
            "I can answer simple local calculations and model-specific reservoir questions. "
            "For arbitrary general questions, the V800 LLM planner must be reachable. "
            "Right now the LLM connection appears unavailable, so I did not fabricate a general answer."
        ),
        "general_or_out_of_scope_llm_unavailable",
        "direct_answer_out_of_scope",
    )

# END V802 RESERVOIR FALLBACK PATCH


# ==========================================================
# V803 USER-FACING ANSWER POLISH
#
# Purpose:
# - Keep real agent_trace and interaction_edges untouched.
# - Remove internal tool/agent names from the main user-facing answer.
# - Leave technical evidence visible, but in reservoir-engineering language.
# ==========================================================

def _v803_polish_answer_text(answer: str) -> str:
    text = str(answer or "")

    if not text.strip():
        return text

    replacements = {
        "I treated this as a model-specific reservoir question and used the LLM planner to select reservoir tools. Then I collected evidence from the selected specialist outputs and passed it to the critic for synthesis.": (
            "This is a model-specific reservoir diagnosis. I compared the available profile, WCT-bias, TRAN/connectivity and property evidence before ranking the most likely causes."
        ),
        "I treated this as a multi-agent reservoir diagnosis": "This is an integrated reservoir diagnosis",
        "Evidence gathered:": "Main evidence:",
        "Critic ranking:": "Hypothesis ranking:",
        "Leading hypothesis:": "Most likely explanation:",
        "Leading hypothesis from the critic:": "Most likely explanation:",
        "LLM planner": "copilot",
        "critic": "technical review",
        "Critic": "Technical review",
        "IntegratedReservoirDiagnosisToolV800:": "Integrated diagnosis:",
        "WCTBiasDiagnosticAgentToolV800:": "Water-cut / spatial bias evidence:",
        "TRANCorridorVisualAgentToolV800:": "TRAN / connectivity evidence:",
        "DynamicProfileAgentToolV800:": "Profile evidence:",
        "StreamlineTimesliceVisualAgentToolV800:": "Streamline evidence:",
        "ExecutiveHMSummaryAgentToolV800:": "History-match summary evidence:",
        "ReservoirRuntimeToolV501:": "Model evidence:",
        "local_connectivity_or_TRAN": "local connectivity / TRAN",
        "relative_permeability_or_water_mobility": "relative permeability / water mobility",
        "profile_level_or_timing_mismatch": "profile level / timing mismatch",
        "pressure_support_or_BHP_connectivity": "pressure / BHP support or connectivity",
        "score=": "support score ",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove remaining internal V800/V700 tool labels if any slipped through.
    import re

    text = re.sub(r"\b[A-Za-z0-9_]*(AgentTool|ToolV800|ToolV700|RuntimeToolV501)\b:?", "model evidence", text)
    text = re.sub(r"\b[A-Za-z0-9_]*AgentV\d+\b:?", "specialist", text)

    # Clean awkward duplicated phrases.
    text = text.replace("technical review ranking", "hypothesis ranking")
    text = text.replace("Technical review ranking", "Hypothesis ranking")
    text = text.replace("passed it to the technical review", "reviewed the combined evidence")
    text = text.replace("selected specialist outputs", "available model evidence")

    # Keep paragraphs readable.
    text = text.replace(" Main evidence:", "\n\nMain evidence:")
    text = text.replace(" Hypothesis ranking:", "\n\nHypothesis ranking:")
    text = text.replace(" Most likely explanation:", "\n\nMost likely explanation:")

    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")

    while "  " in text:
        text = text.replace("  ", " ")

    return text.strip()


def _v803_polish_response(response: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(response, dict):
        return response

    answer = response.get("answer")

    if isinstance(answer, str):
        polished = _v803_polish_answer_text(answer)

        if polished != answer:
            response = dict(response)
            response["answer"] = polished

            trace = response.get("agent_trace") or {}

            if isinstance(trace, dict):
                trace = dict(trace)
                trace["UserFacingAnswerPolisherV803"] = {
                    "status": "completed",
                    "action": "removed_internal_agent_names_from_main_answer",
                    "note": "agent_trace and interaction_edges remain available for debug/audit.",
                }
                response["agent_trace"] = trace

            collab = response.get("collaboration_summary") or {}

            if isinstance(collab, dict):
                collab = dict(collab)
                collab["user_facing_answer_polished"] = True
                response["collaboration_summary"] = collab

    return response


_v803_previous_run_copilot_orchestrator_v700 = run_copilot_orchestrator_v700


def run_copilot_orchestrator_v700(message: str) -> Dict[str, Any]:
    response = _v803_previous_run_copilot_orchestrator_v700(message)
    return _v803_polish_response(response)

# END V803 USER-FACING ANSWER POLISH


# ==========================================================
# V804 STRATEGIC ACTION-PLAN MULTI-AGENT PATCH
#
# Purpose:
# Questions about model update priorities / action plans should not
# collapse to a thin single-tool answer. They require multiple evidence
# sources and a final synthesis.
# ==========================================================

def _v804_is_model_update_action_plan(message: str) -> bool:
    s = message.lower()

    action_terms = [
        "model updates",
        "model update",
        "prioritize",
        "prioritise",
        "priority",
        "improve the history match",
        "improve history match",
        "improve hm",
        "model review",
        "action plan",
        "recommend",
        "recommendation",
        "what should we update",
        "what would you update",
        "calibration priorities",
    ]

    hm_terms = [
        "history match",
        "history-match",
        "hm",
        "model",
        "match quality",
        "water",
        "wct",
        "pressure",
        "bhp",
        "tran",
        "relperm",
    ]

    return any(t in s for t in action_terms) and any(t in s for t in hm_terms)


def _v804_action_plan_response(message: str) -> Dict[str, Any]:
    plan = {
        "mode": "reservoir_multi_agent",
        "reason": "The user asks for model-update priorities, which requires integrated evidence across HM summary, water/WCT, pressure/BHP, TRAN/connectivity and relperm/water mobility.",
        "primary_well": None,
        "tool_plan": [
            {
                "tool_label": "ExecutiveHMSummaryAgentToolV800",
                "subquery": "Give me an executive summary of the history match quality."
            },
            {
                "tool_label": "IntegratedReservoirDiagnosisToolV800",
                "subquery": "Give me the top 5 wells requiring model review and explain the main driver for each."
            },
            {
                "tool_label": "WCTBiasDiagnosticAgentToolV800",
                "subquery": "Show me WCT bias cluster map and explain it."
            },
            {
                "tool_label": "IntegratedReservoirDiagnosisToolV800",
                "subquery": "Identify wells where RelPerm tuning would be risky because connectivity evidence is stronger."
            },
            {
                "tool_label": "TRANCorridorVisualAgentToolV800",
                "subquery": "Check if WCT mismatch aligns spatially with TRAN/PERM corridors."
            }
        ]
    }

    response = _v800_reservoir_response(message, plan)

    # Replace the generic synthesis intro with a more action-oriented answer.
    answer = response.get("answer") or ""

    action_intro = (
        "Recommended model-update priorities based on the integrated evidence:\n\n"
        "1. **Start with water/WCT behaviour**, because oil and gas matches are generally strong while water/WCT is the weakest dimension. This points to water movement, breakthrough timing, water mobility or local connectivity rather than a field-wide hydrocarbon volumetric issue.\n\n"
        "2. **Separate connectivity/TRAN candidates from RelPerm/water-mobility candidates.** Wells where TRAN/PERM/corridor evidence is material should be tested with transmissibility or connectivity sensitivities before applying RelPerm-only tuning.\n\n"
        "3. **Use pressure/BHP as a consistency check.** If water mismatch and BHP mismatch appear together, connectivity, pressure support or boundary/aquifer representation should be reviewed before changing only saturation functions.\n\n"
        "4. **Prioritize local, evidence-backed edits.** Avoid broad global multipliers unless the mismatch is clearly systematic across the field. The safest workflow is to test targeted TRAN/corridor edits and RelPerm sensitivities separately, then compare impact on water, BHP, oil and gas.\n\n"
        "5. **Preserve the good oil/gas match.** Any update that improves water but degrades oil or gas should be rejected or constrained.\n\n"
        "Supporting integrated evidence is summarized below.\n\n"
    )

    response["answer"] = action_intro + answer

    trace = response.get("agent_trace") or {}

    if isinstance(trace, dict):
        trace = dict(trace)
        trace["StrategicActionPlanPlannerV804"] = {
            "status": "completed",
            "action": "expanded_model_update_priority_question_into_multi_agent_plan",
            "tools_requested": [x["tool_label"] for x in plan["tool_plan"]],
        }
        response["agent_trace"] = trace

    collab = response.get("collaboration_summary") or {}

    if isinstance(collab, dict):
        collab = dict(collab)
        collab["v804_action_plan_expanded"] = True
        collab["mode"] = "v804_model_update_action_plan"
        response["collaboration_summary"] = collab

    ui = response.get("universal_intent_v500") or {}

    if isinstance(ui, dict):
        ui["task_type"] = "v804_model_update_action_plan"
        ui["v804_action_plan_expanded"] = True
        response["universal_intent_v500"] = ui
    else:
        response["universal_intent_v500"] = {
            "task_type": "v804_model_update_action_plan",
            "v804_action_plan_expanded": True,
        }

    return response


_v804_previous_run_copilot_orchestrator_v700 = run_copilot_orchestrator_v700


def run_copilot_orchestrator_v700(message: str) -> Dict[str, Any]:
    message = str(message or "").strip()

    if _v804_is_model_update_action_plan(message):
        return _v803_polish_response(_v804_action_plan_response(message)) if "_v803_polish_response" in globals() else _v804_action_plan_response(message)

    return _v804_previous_run_copilot_orchestrator_v700(message)

# END V804 STRATEGIC ACTION-PLAN MULTI-AGENT PATCH


# ==========================================================
# V805 USER-FACING ANSWER FORMATTER
#
# Purpose:
# - Keep technical content unchanged.
# - Keep agent_trace / interaction_edges untouched.
# - Improve readability of the main answer with line breaks,
#   headings and bullet/numbered sections.
# ==========================================================

def _v805_sentence_split(text: str) -> List[str]:
    import re

    raw = str(text or "").strip()

    if not raw:
        return []

    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", raw)

    return [p.strip() for p in parts if p.strip()]


def _v805_cleanup_spacing(text: str) -> str:
    import re

    s = str(text or "").replace("\r\n", "\n").replace("\r", "\n")

    # New line before common headings if they are embedded in a paragraph.
    headings = [
        "Main evidence:",
        "Hypothesis ranking:",
        "Most likely explanation:",
        "Recommended model-update priorities",
        "Recommended next steps:",
        "Supporting integrated evidence",
        "Evidence summary:",
        "Interpretation:",
        "Conclusion:",
    ]

    for h in headings:
        s = s.replace(" " + h, "\n\n" + h)

    # Put numbered items on separate lines.
    s = re.sub(r"\s+(\d+)\.\s+", r"\n\1. ", s)

    # Put dash bullets on separate lines when embedded.
    s = re.sub(r"\s+-\s+", r"\n- ", s)

    # Avoid too many blank lines.
    while "\n\n\n" in s:
        s = s.replace("\n\n\n", "\n\n")

    # Remove excessive spaces.
    s = re.sub(r"[ \t]+", " ", s)

    return s.strip()


def _v805_format_action_plan(answer: str) -> str:
    s = _v805_cleanup_spacing(answer)

    # If already starts with a clean recommendation section, keep but normalize.
    if "Recommended model-update priorities" in s:
        s = s.replace(
            "Recommended model-update priorities based on the integrated evidence:",
            "Recommended model-update priorities:"
        )

    return s


def _v805_format_diagnosis(answer: str) -> str:
    s = _v805_cleanup_spacing(answer)

    # Replace very long initial sentence with a clean section.
    long_intro = (
        "This is a model-specific reservoir diagnosis. I compared the available profile, "
        "WCT-bias, TRAN/connectivity and property evidence before ranking the most likely causes."
    )

    if long_intro in s:
        s = s.replace(
            long_intro,
            "Summary:\n"
            "- This is a model-specific reservoir diagnosis.\n"
            "- I compared profile, WCT-bias, TRAN/connectivity and property evidence.\n"
            "- The conclusion below is based on combined evidence, not on a single plot."
        )

    # If the answer contains evidence and ranking but no clear Summary heading, add one.
    if (
        "Main evidence:" in s
        and "Hypothesis ranking:" in s
        and not s.startswith("Summary:")
    ):
        s = "Summary:\n- Integrated model evidence was reviewed before ranking the most likely causes.\n\n" + s

    return s


def _v805_format_executive_summary(answer: str) -> str:
    s = _v805_cleanup_spacing(answer)

    lower = s.lower()

    if "executive summary" not in lower and "history match" not in lower:
        return s

    # Convert first sentence to Summary section if the text is one dense paragraph.
    if "\n" not in s and len(s) > 450:
        sentences = _v805_sentence_split(s)

        if len(sentences) >= 4:
            summary = sentences[0]
            rest = sentences[1:]

            bullets = []
            for sent in rest[:6]:
                bullets.append("- " + sent)

            remaining = " ".join(rest[6:]).strip()

            s = "Summary:\n- " + summary + "\n\nKey points:\n" + "\n".join(bullets)

            if remaining:
                s += "\n\nAdditional interpretation:\n" + remaining

    return s


def _v805_format_generic_long_answer(answer: str) -> str:
    s = _v805_cleanup_spacing(answer)

    if len(s) < 650:
        return s

    # If already structured, avoid over-formatting.
    if "\n- " in s or "\n1. " in s or "Summary:" in s:
        return s

    sentences = _v805_sentence_split(s)

    if len(sentences) < 5:
        return s

    intro = sentences[0]
    bullets = sentences[1:7]
    remaining = sentences[7:]

    formatted = "Summary:\n- " + intro

    formatted += "\n\nKey points:\n"
    formatted += "\n".join("- " + b for b in bullets)

    if remaining:
        formatted += "\n\nAdditional notes:\n"
        formatted += " ".join(remaining)

    return formatted.strip()


def _v805_format_user_answer_text(answer: str, response: Dict[str, Any]) -> str:
    text = str(answer or "").strip()

    if not text:
        return text

    task = ""
    ui = response.get("universal_intent_v500") or {}

    if isinstance(ui, dict):
        task = str(ui.get("task_type") or "").lower()

    intent = str(response.get("intent") or "").lower()

    # Keep very short direct answers untouched, e.g. "5+7 = 12".
    if len(text) < 180 and ("direct_answer_simple_math" in task or "simple_math" in intent):
        return text

    # Action-plan questions.
    if "action_plan" in task or "model_update" in task or "priorit" in text.lower():
        return _v805_format_action_plan(text)

    # Diagnostic multi-agent answers.
    if (
        "diagnosis" in task
        or "multi_agent" in task
        or "hypothesis ranking" in text.lower()
        or "main evidence:" in text.lower()
    ):
        return _v805_format_diagnosis(text)

    # Executive summary.
    if "executive" in task or "history_match_summary" in task:
        return _v805_format_executive_summary(text)

    # General long text.
    return _v805_format_generic_long_answer(text)


def _v805_format_response(response: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(response, dict):
        return response

    answer = response.get("answer")

    if not isinstance(answer, str):
        return response

    formatted = _v805_format_user_answer_text(answer, response)

    if formatted == answer:
        return response

    response = dict(response)
    response["answer"] = formatted

    trace = response.get("agent_trace") or {}

    if isinstance(trace, dict):
        trace = dict(trace)
        trace["UserFacingMarkdownFormatterV805"] = {
            "status": "completed",
            "action": "formatted_main_answer_for_readability",
            "note": "No technical evidence, agent_trace or interaction_edges were changed.",
        }
        response["agent_trace"] = trace

    collab = response.get("collaboration_summary") or {}

    if isinstance(collab, dict):
        collab = dict(collab)
        collab["user_facing_answer_formatted_v805"] = True
        response["collaboration_summary"] = collab

    return response


_v805_previous_run_copilot_orchestrator_v700 = run_copilot_orchestrator_v700


def run_copilot_orchestrator_v700(message: str) -> Dict[str, Any]:
    response = _v805_previous_run_copilot_orchestrator_v700(message)
    return _v805_format_response(response)

# END V805 USER-FACING ANSWER FORMATTER


# ==========================================================
# V806 STABILIZE USER ANSWER + VISUAL BLOCKS
#
# Purpose:
# - Disable V805 backend formatting side effects.
# - Keep previous V803 user-facing text cleanup.
# - Deduplicate UI blocks.
# - For diagnosis questions, avoid unstable proxy/profile visual switching
#   unless the user explicitly asked to show/plot/map.
# ==========================================================

def _v806_block_text(block: Dict[str, Any]) -> str:
    try:
        return json.dumps(block, sort_keys=True, default=str)[:2500]
    except Exception:
        return str(block)[:2500]


def _v806_block_title(block: Dict[str, Any]) -> str:
    if not isinstance(block, dict):
        return ""

    candidates = [
        block.get("title"),
        block.get("name"),
        block.get("label"),
        (block.get("meta") or {}).get("title") if isinstance(block.get("meta"), dict) else None,
        (block.get("props") or {}).get("title") if isinstance(block.get("props"), dict) else None,
    ]

    for c in candidates:
        if c:
            return str(c)

    txt = _v806_block_text(block)
    if "Integrated evidence board" in txt:
        return "Integrated evidence board"
    if "Hypothesis ranking" in txt:
        return "Hypothesis ranking"

    return ""


def _v806_dedupe_ui_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()

    for block in blocks or []:
        if not isinstance(block, dict):
            continue

        btype = str(block.get("type") or "")
        title = _v806_block_title(block)
        text = _v806_block_text(block)

        # Prefer stable semantic signature over full payload.
        if "Integrated evidence board" in text:
            sig = ("integrated_evidence_board", title)
        elif "Hypothesis ranking" in text and btype == "compact_table":
            sig = ("hypothesis_ranking_table", title)
        else:
            sig = (btype, title, text[:500])

        if sig in seen:
            continue

        seen.add(sig)
        out.append(block)

    return out


def _v806_is_diagnostic_question(message: str) -> bool:
    s = str(message or "").lower()

    diagnostic_terms = [
        "why",
        "more likely",
        "caused by",
        "diagnosis",
        "mismatch",
        "connectivity",
        "relative permeability",
        "relperm",
        "water issue",
        "history match",
        "improve the history match",
        "prioritize",
        "prioritise",
        "model updates",
    ]

    return any(t in s for t in diagnostic_terms)


def _v806_explicit_visual_request(message: str) -> bool:
    s = str(message or "").lower()

    explicit_terms = [
        "show",
        "plot",
        "map",
        "display",
        "visualize",
        "visualise",
        "chart",
        "graph",
    ]

    return any(t in s for t in explicit_terms)


def _v806_rank_ui_block(block: Dict[str, Any], message: str) -> int:
    btype = str(block.get("type") or "")
    txt = _v806_block_text(block).lower()
    msg = str(message or "").lower()

    if "integrated evidence board" in txt:
        return 0

    if "hypothesis ranking" in txt and btype == "compact_table":
        return 1

    if btype == "tran_corridor_map" and ("tran" in msg or "connect" in msg or "corridor" in msg):
        return 2

    if btype == "wct_bias_cluster_map" and ("wct" in msg or "water" in msg):
        return 3

    if btype == "compact_table":
        return 4

    if btype == "suggestions":
        return 9

    if btype == "profile_series":
        return 6

    if btype == "plotly_chart":
        return 7

    return 8


def _v806_stabilize_ui_blocks(message: str, response: Dict[str, Any]) -> Dict[str, Any]:
    blocks = response.get("ui_blocks") or []

    if not isinstance(blocks, list) or not blocks:
        return response

    blocks = _v806_dedupe_ui_blocks(blocks)

    # For diagnostic questions without explicit show/plot/map intent, avoid
    # unstable chart/profile switching in the main evidence panel.
    if _v806_is_diagnostic_question(message) and not _v806_explicit_visual_request(message):
        preferred = []

        for block in blocks:
            btype = str(block.get("type") or "")
            txt = _v806_block_text(block).lower()

            if btype in {"profile_series", "plotly_chart"}:
                continue

            # Keep evidence boards/tables and targeted maps only.
            preferred.append(block)

        if preferred:
            blocks = preferred

    blocks = sorted(blocks, key=lambda b: _v806_rank_ui_block(b, message))

    # Do not overload the UI panel.
    blocks = blocks[:5]

    response = dict(response)
    response["ui_blocks"] = blocks

    trace = response.get("agent_trace") or {}

    if isinstance(trace, dict):
        trace = dict(trace)
        trace["VisualEvidenceStabilizerV806"] = {
            "status": "completed",
            "action": "deduplicated_and_ranked_ui_blocks",
            "ui_block_count": len(blocks),
            "note": "No reservoir evidence was invented; duplicate/unstable blocks were removed from display payload.",
        }
        response["agent_trace"] = trace

    collab = response.get("collaboration_summary") or {}

    if isinstance(collab, dict):
        collab = dict(collab)
        collab["visual_blocks_stabilized_v806"] = True
        collab["ui_block_count_after_v806"] = len(blocks)
        response["collaboration_summary"] = collab

    return response


def _v806_light_text_layout(answer: str) -> str:
    text = str(answer or "").strip()

    if not text:
        return text

    # Do not over-format short direct answers.
    if len(text) < 180:
        return text

    import re

    # Keep basic headings readable. The frontend CSS will preserve newlines.
    headings = [
        "Summary:",
        "Main evidence:",
        "Hypothesis ranking:",
        "Most likely explanation:",
        "Recommended model-update priorities:",
        "Recommended next checks:",
        "Supporting integrated evidence",
    ]

    for h in headings:
        text = text.replace(" " + h, "\n\n" + h)

    # Make bullets visible only where they already exist semantically.
    text = re.sub(r"(?<!\n)\s+-\s+", "\n- ", text)

    # Numbered list spacing.
    text = re.sub(r"(?<!\n)\s+(\d+)\.\s+", r"\n\1. ", text)

    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")

    return text.strip()


def _v806_stabilize_answer_text(response: Dict[str, Any]) -> Dict[str, Any]:
    answer = response.get("answer")

    if not isinstance(answer, str):
        return response

    formatted = _v806_light_text_layout(answer)

    if formatted == answer:
        return response

    response = dict(response)
    response["answer"] = formatted

    trace = response.get("agent_trace") or {}

    if isinstance(trace, dict):
        trace = dict(trace)
        trace["LightAnswerLayoutV806"] = {
            "status": "completed",
            "action": "light_linebreak_layout_only",
            "note": "V805 heavy formatter is bypassed; this only adds safe line breaks.",
        }
        response["agent_trace"] = trace

    return response


# IMPORTANT:
# If V805 exists, bypass it by returning to the function that V805 wrapped.
# This avoids the heavy formatter that caused visual/text side effects.
_v806_base_runner = globals().get("_v805_previous_run_copilot_orchestrator_v700", run_copilot_orchestrator_v700)


def run_copilot_orchestrator_v700(message: str) -> Dict[str, Any]:
    response = _v806_base_runner(message)
    response = _v806_stabilize_ui_blocks(message, response)
    response = _v806_stabilize_answer_text(response)
    return response

# END V806 STABILIZE USER ANSWER + VISUAL BLOCKS


# ==========================================================
# V807 STRUCTURED HYPOTHESIS CRITIC
#
# Purpose:
# - Generic, not well-specific.
# - If specialist outputs expose structured hypothesis scores,
#   the final critic must use the highest numeric score.
# - Fallback to the old keyword/evidence heuristic only when no
#   structured ranking is available.
# ==========================================================

def _v807_safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        s = str(value).strip()
        s = s.replace("%", "").replace(",", "")

        if not s:
            return None

        return float(s)

    except Exception:
        return None


def _v807_norm_key(s: Any) -> str:
    return str(s or "").strip().lower().replace("_", " ")


def _v807_get_case_insensitive(d: Dict[str, Any], names: List[str]) -> Any:
    if not isinstance(d, dict):
        return None

    normalized = {_v807_norm_key(k): v for k, v in d.items()}

    for name in names:
        key = _v807_norm_key(name)

        if key in normalized:
            return normalized[key]

    return None


def _v807_normalize_hypothesis_name(name: str) -> str:
    s = str(name or "").strip()

    low = s.lower()

    if "relperm" in low or "relative permeability" in low or "endpoint" in low or "water mobility" in low:
        return "Relative permeability / water mobility"

    if "connect" in low or "tran" in low or "transmissibility" in low:
        return "Connectivity / TRAN"

    if "pressure" in low or "bhp" in low or "aquifer" in low or "boundary" in low:
        return "Pressure support / BHP / boundary"

    if "control" in low or "allocation" in low or "measurement" in low:
        return "Well control / allocation / measurement"

    if "profile" in low or "timing" in low or "level" in low:
        return "Profile level / timing mismatch"

    return s


def _v807_collect_hypotheses(obj: Any, source: str = "unknown") -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []

    if isinstance(obj, dict):
        hypothesis = _v807_get_case_insensitive(
            obj,
            ["hypothesis", "Hypothesis", "name", "Name", "driver", "Driver"]
        )

        score = _v807_get_case_insensitive(
            obj,
            ["score", "Score", "support score", "Support score", "probability", "Probability"]
        )

        numeric_score = _v807_safe_float(score)

        if hypothesis and numeric_score is not None:
            found.append({
                "hypothesis": _v807_normalize_hypothesis_name(str(hypothesis)),
                "raw_hypothesis": str(hypothesis),
                "score": numeric_score,
                "source": source,
                "supporting_evidence": _v807_get_case_insensitive(
                    obj,
                    ["supporting evidence", "Supporting evidence", "evidence", "Evidence", "interpretation", "Interpretation"]
                ),
                "counter_evidence": _v807_get_case_insensitive(
                    obj,
                    ["counter evidence", "Counter evidence"]
                ),
                "review_first": _v807_get_case_insensitive(
                    obj,
                    ["review first", "Review first", "next checks", "Next checks"]
                ),
            })

        for k, v in obj.items():
            next_source = source

            if isinstance(k, str) and k:
                next_source = k

            found.extend(_v807_collect_hypotheses(v, next_source))

    elif isinstance(obj, list):
        for item in obj:
            found.extend(_v807_collect_hypotheses(item, source))

    return found


def _v807_collect_structured_ranking(tool_outputs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    all_rows: List[Dict[str, Any]] = []

    for item in tool_outputs or []:
        label = str(item.get("tool_label") or "unknown_tool")
        response = item.get("response") or {}

        all_rows.extend(_v807_collect_hypotheses(response, label))

    if not all_rows:
        return []

    grouped: Dict[str, Dict[str, Any]] = {}

    for row in all_rows:
        h = row["hypothesis"]

        if h not in grouped:
            grouped[h] = {
                "hypothesis": h,
                "score": row["score"],
                "sources": [row["source"]],
                "raw_hypotheses": [row.get("raw_hypothesis")],
                "supporting_evidence": [],
                "counter_evidence": [],
                "review_first": [],
            }
        else:
            # Conservative generic rule:
            # If several tools expose the same hypothesis, keep the strongest
            # explicit numeric support but retain all sources.
            grouped[h]["score"] = max(grouped[h]["score"], row["score"])
            grouped[h]["sources"].append(row["source"])
            grouped[h]["raw_hypotheses"].append(row.get("raw_hypothesis"))

        for key in ["supporting_evidence", "counter_evidence", "review_first"]:
            val = row.get(key)

            if val and str(val) not in grouped[h][key]:
                grouped[h][key].append(str(val))

    ranked = list(grouped.values())
    ranked.sort(key=lambda x: x["score"], reverse=True)

    for r in ranked:
        r["sources"] = sorted(set(r["sources"]))
        r["raw_hypotheses"] = sorted(set(str(x) for x in r["raw_hypotheses"] if x))

    return ranked


_v807_previous_critic_rank_hypotheses = _critic_rank_hypotheses


def _critic_rank_hypotheses(message: str, tool_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    structured = _v807_collect_structured_ranking(tool_outputs)

    if structured:
        hypotheses = []

        for row in structured:
            support = "; ".join(row.get("supporting_evidence") or [])
            counter = "; ".join(row.get("counter_evidence") or [])
            review = "; ".join(row.get("review_first") or [])

            hypotheses.append({
                "hypothesis": row["hypothesis"],
                "score": row["score"],
                "interpretation": (
                    support
                    if support
                    else "Supported by structured specialist hypothesis ranking."
                ),
                "counter_evidence": counter,
                "review_first": review,
                "sources": row.get("sources") or [],
            })

        return {
            "critic": "ReservoirCriticAgentV807",
            "method": "structured_numeric_hypothesis_ranking",
            "leading_hypothesis": hypotheses[0],
            "ranked_hypotheses": hypotheses,
            "note": (
                "Leading hypothesis selected from structured numeric hypothesis scores exposed by specialist outputs. "
                "Keyword fallback was not used."
            ),
        }

    # Fallback only when there is no structured ranking.
    fallback = _v807_previous_critic_rank_hypotheses(message, tool_outputs)

    if isinstance(fallback, dict):
        fallback["method"] = str(fallback.get("method") or "fallback_keyword_evidence_weighting")
        fallback["note"] = str(fallback.get("note") or "") + " Structured hypothesis scores were not available."

    return fallback

# END V807 STRUCTURED HYPOTHESIS CRITIC


# ==========================================================
# V810 FINAL VISUAL SELECTOR
#
# Purpose:
# - Generic, not HW-28-specific.
# - Do not aggressively remove all maps.
# - Select the final visual evidence that best matches the user's intent:
#   * diagnostic comparison -> evidence/hypothesis tables
#   * explicit TRAN/corridor request -> TRAN map
#   * explicit WCT/map request -> WCT map
#   * explicit profile/production request -> profile plot
#   * otherwise keep original final payload
# ==========================================================

def _v810_message_lower(message: str) -> str:
    return str(message or "").lower()


def _v810_block_type(block: Dict[str, Any]) -> str:
    if not isinstance(block, dict):
        return ""
    return str(block.get("type") or "").lower()


def _v810_block_title(block: Dict[str, Any]) -> str:
    if not isinstance(block, dict):
        return ""

    title = block.get("title") or block.get("name") or ""

    if not title and isinstance(block.get("meta"), dict):
        title = block["meta"].get("title") or ""

    return str(title or "")


def _v810_block_text(block: Dict[str, Any]) -> str:
    try:
        return json.dumps(block, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return str(block)


def _v810_dedupe_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    seen = set()

    for block in blocks or []:
        if not isinstance(block, dict):
            continue

        btype = _v810_block_type(block)
        title = _v810_block_title(block)
        preview = _v810_block_text(block)[:700]

        sig = (btype, title, preview)

        if sig in seen:
            continue

        seen.add(sig)
        out.append(block)

    return out


def _v810_is_diagnostic_decision_question(message: str) -> bool:
    s = _v810_message_lower(message)

    decision_terms = [
        "more likely",
        "caused by",
        "cause",
        "why",
        "diagnosis",
        "diagnose",
        "root cause",
        "hypothesis",
        "connectivity or",
        "relperm or",
        "relative permeability or",
        "compare",
        "explain",
    ]

    reservoir_terms = [
        "water",
        "wct",
        "mismatch",
        "history match",
        "connectivity",
        "tran",
        "transmissibility",
        "relperm",
        "relative permeability",
        "pressure",
        "bhp",
        "well",
        "hw-",
    ]

    return any(x in s for x in decision_terms) and any(x in s for x in reservoir_terms)


def _v810_explicit_visual_family(message: str) -> str:
    s = _v810_message_lower(message)

    explicit_visual_words = [
        "show",
        "plot",
        "map",
        "display",
        "visualize",
        "visualise",
        "draw",
        "graph",
        "chart",
    ]

    has_visual_word = any(x in s for x in explicit_visual_words)

    if not has_visual_word:
        return ""

    if "tran" in s or "transmissibility" in s or "corridor" in s:
        return "tran_map"

    if "wct" in s or "water cut" in s or "bias" in s or "cluster map" in s:
        return "wct_map"

    if "streamline" in s:
        return "streamline_map"

    if "profile" in s or "production" in s or "oil" in s or "gas" in s or "water" in s or "bhp" in s or "pressure" in s:
        return "profile"

    return "visual_generic"


def _v810_is_evidence_table(block: Dict[str, Any]) -> bool:
    btype = _v810_block_type(block)
    title = _v810_block_title(block).lower()
    txt = _v810_block_text(block).lower()

    if btype != "compact_table":
        return False

    if "integrated evidence board" in title or "integrated evidence board" in txt:
        return True

    if "hypothesis ranking" in title or "hypothesis ranking" in txt:
        return True

    return False


def _v810_select_final_blocks(message: str, blocks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], str]:
    blocks = _v810_dedupe_blocks(blocks)

    if not blocks:
        return blocks, "no_blocks"

    family = _v810_explicit_visual_family(message)

    # Explicit visual requests: preserve the visual family requested.
    if family == "tran_map":
        selected = [b for b in blocks if _v810_block_type(b) == "tran_corridor_map" or "tran" in _v810_block_type(b)]
        return (selected or blocks[:1], "explicit_tran_visual")

    if family == "wct_map":
        selected = [b for b in blocks if _v810_block_type(b) == "wct_bias_cluster_map" or "wct" in _v810_block_type(b)]
        return (selected or blocks[:1], "explicit_wct_visual")

    if family == "streamline_map":
        selected = [b for b in blocks if "streamline" in _v810_block_type(b) or "streamline" in _v810_block_title(b).lower()]
        return (selected or blocks[:1], "explicit_streamline_visual")

    if family == "profile":
        selected = [b for b in blocks if _v810_block_type(b) in {"profile_series", "plotly_chart"}]
        return (selected or blocks[:1], "explicit_profile_visual")

    # Diagnostic decision questions: show the decision evidence, not a supporting map.
    if _v810_is_diagnostic_decision_question(message):
        tables = [b for b in blocks if _v810_is_evidence_table(b)]

        if tables:
            # Keep up to two: evidence board + hypothesis ranking.
            return tables[:2], "diagnostic_decision_tables"

    # Default: keep original final blocks but deduped.
    return blocks[:5], "default_keep_final_blocks"


def _v810_apply_final_visual_selector(message: str, response: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(response, dict):
        return response

    blocks = response.get("ui_blocks") or []

    if not isinstance(blocks, list) or not blocks:
        return response

    selected, decision = _v810_select_final_blocks(message, blocks)

    response = dict(response)
    response["ui_blocks"] = selected

    trace = response.get("agent_trace") or {}

    if isinstance(trace, dict):
        trace = dict(trace)
        trace["FinalVisualSelectorV810"] = {
            "status": "completed",
            "decision": decision,
            "original_ui_block_types": [_v810_block_type(b) for b in blocks if isinstance(b, dict)],
            "selected_ui_block_types": [_v810_block_type(b) for b in selected if isinstance(b, dict)],
            "policy": "show_final_decision_visual_not_all_supporting_visuals",
        }
        response["agent_trace"] = trace

    collab = response.get("collaboration_summary") or {}

    if isinstance(collab, dict):
        collab = dict(collab)
        collab["final_visual_selector_v810"] = {
            "decision": decision,
            "selected_ui_block_count": len(selected),
        }
        response["collaboration_summary"] = collab

    return response


_v810_previous_run_copilot_orchestrator_v700 = run_copilot_orchestrator_v700


def run_copilot_orchestrator_v700(message: str) -> Dict[str, Any]:
    response = _v810_previous_run_copilot_orchestrator_v700(message)
    return _v810_apply_final_visual_selector(message, response)

# END V810 FINAL VISUAL SELECTOR
