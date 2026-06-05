import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

MEMORY_LOG = LOG_DIR / "conversation_memory.jsonl"

SESSION_MEMORY: Dict[str, Dict[str, Any]] = {}


def normalize_well(raw: str) -> Optional[str]:
    if not raw:
        return None

    q = str(raw).upper()

    m = re.search(r"\bHW[-_\s]?(\d+[A-Z]?)\b", q)
    if m:
        return f"HW-{m.group(1)}"

    return None


def detect_well(text: str) -> Optional[str]:
    return normalize_well(text)


def detect_variable(text: str) -> Optional[str]:
    q = str(text or "").lower()

    if any(x in q for x in ["water", "wct", "water cut", "watercut"]):
        return "water"

    if any(x in q for x in ["oil", "opr", "wopr"]):
        return "oil"

    if any(x in q for x in ["gas", "gor", "gpr", "wgpr"]):
        return "gas"

    if any(x in q for x in ["bhp", "bottom hole", "bottomhole"]):
        return "bhp"

    if any(x in q for x in ["pressure", "depletion"]):
        return "pressure"

    if any(x in q for x in ["swat", "water saturation"]):
        return "swat"

    if any(x in q for x in ["soil", "oil saturation"]):
        return "soil"

    if any(x in q for x in ["sgas", "gas saturation"]):
        return "sgas"

    if any(x in q for x in ["transmissibility", "transmiss", "tran", "multiplier", "corridor"]):
        return "transmissibility"

    if any(x in q for x in ["permeability", "perm"]):
        return "permeability"

    return None


def detect_intent(text: str) -> Optional[str]:
    q = str(text or "").lower()

    if any(x in q for x in ["profile", "plot", "curve", "simulated", "observed"]):
        return "profile"

    if any(x in q for x in ["map", "heatmap", "spatial", "depletion", "swat", "pressure map"]):
        return "map"

    if any(x in q for x in ["streamline", "connectivity", "connection", "connected"]):
        return "connectivity"

    if any(x in q for x in ["why", "explain", "mismatch", "not matching", "problem", "issue"]):
        return "diagnosis"

    if any(x in q for x in ["compare", "similar", "nearby", "same issue"]):
        return "comparison"

    if any(x in q for x in ["transmissibility", "multiplier", "corridor", "where would you test"]):
        return "recommendation"

    return None


def is_contextual_follow_up(text: str) -> bool:
    """
    True only for genuinely ambiguous follow-ups.

    Examples where context should be used:
      - what about pressure?
      - show the profile
      - and for gas?
      - compare with similar wells
      - why?
      - show it
      - same for HW-10

    Examples where context should NOT be forced:
      - show pressure depletion map
      - show streamlines
      - why HW-10 is not matching?
      - show SWAT map
      - where should I increase transmissibility?
    """
    q = str(text or "").lower().strip()

    explicit_well = detect_well(q) is not None
    explicit_variable = detect_variable(q) is not None

    contextual_phrases = [
        "what about",
        "and for",
        "same for",
        "same analysis",
        "same issue",
        "show the profile",
        "show it",
        "plot it",
        "explain better",
        "more detail",
        "why?",
        "why",
        "compare with similar",
        "compare it",
        "nearby wells",
        "this well",
        "that well",
        "for the same well",
        "do we see the same",
    ]

    strong_standalone_phrases = [
        "show pressure depletion map",
        "show pressure map",
        "show swat map",
        "show delta swat",
        "show streamlines",
        "show connectivity",
        "where should i increase transmissibility",
        "where would you test",
        "executive summary",
        "overall history match",
        "history match quality",
    ]

    if any(x in q for x in strong_standalone_phrases):
        return False

    # If a new well is explicit, it is not ambiguous.
    if explicit_well:
        return False

    # If it has an explicit variable and is clearly a map request, don't inherit old well/variable.
    if explicit_variable and any(x in q for x in ["map", "heatmap", "depletion", "delta"]):
        return False

    # Very short "why?" or "show it" type questions can inherit.
    if q in ["why", "why?", "show it", "plot it", "same", "compare", "profile"]:
        return True

    return any(x in q for x in contextual_phrases)


def get_session(session_id: str = "default") -> Dict[str, Any]:
    if session_id not in SESSION_MEMORY:
        SESSION_MEMORY[session_id] = {
            "session_id": session_id,
            "last_well": None,
            "last_variable": None,
            "last_intent": None,
            "last_normalized_prompt": None,
            "history": [],
        }

    return SESSION_MEMORY[session_id]


def enrich_question_with_context(question: str, session_id: str = "default") -> Dict[str, Any]:
    memory = get_session(session_id)

    original = str(question or "").strip()
    well = detect_well(original)
    variable = detect_variable(original)
    intent = detect_intent(original)

    used_context = False
    enriched = original

    should_use_context = is_contextual_follow_up(original)

    if should_use_context:
        if not well and memory.get("last_well"):
            well = memory.get("last_well")
            used_context = True

        if not variable and memory.get("last_variable"):
            variable = memory.get("last_variable")
            used_context = True

        if not intent and memory.get("last_intent"):
            intent = memory.get("last_intent")
            used_context = True

    if used_context:
        context_bits = []

        if well:
            context_bits.append(f"well {well}")

        if variable:
            context_bits.append(f"variable {variable}")

        if intent:
            context_bits.append(f"intent {intent}")

        enriched = (
            f"{original}\n\n"
            f"Conversation context: the user is referring to "
            f"{', '.join(context_bits)}. "
            f"Answer in English only and continue the technical thread, but do not repeat the previous answer. "
            f"Focus on the new aspect requested in the latest message."
        )

    return {
        "original": original,
        "enriched": enriched,
        "well": well,
        "variable": variable,
        "intent": intent,
        "used_context": used_context,
        "memory_before": dict(memory),
    }


def update_memory(
    question: str,
    response: Dict[str, Any],
    session_id: str = "default",
    detected_well: Optional[str] = None,
    detected_variable: Optional[str] = None,
    detected_intent: Optional[str] = None,
):
    memory = get_session(session_id)

    agent_trace = response.get("agent_trace", {}) if isinstance(response, dict) else {}
    re_trace = agent_trace.get("ReservoirEngineerAgent", {}) if isinstance(agent_trace, dict) else {}
    router_trace = agent_trace.get("prompt_router", {}) if isinstance(agent_trace, dict) else {}

    well = detected_well or re_trace.get("well") or router_trace.get("well") or detect_well(question)
    variable = detected_variable or re_trace.get("variable") or router_trace.get("variable") or detect_variable(question)
    intent = detected_intent or (response.get("intent") if isinstance(response, dict) else None) or detect_intent(question)

    normalized = None
    if isinstance(response, dict):
        normalized = router_trace.get("normalized_prompt") or memory.get("last_normalized_prompt")

    if well:
        memory["last_well"] = well

    if variable:
        memory["last_variable"] = variable

    if intent:
        memory["last_intent"] = intent

    if normalized:
        memory["last_normalized_prompt"] = normalized

    memory["history"].append({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "question": question,
        "well": well,
        "variable": variable,
        "intent": intent,
    })

    memory["history"] = memory["history"][-12:]

    with MEMORY_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(memory, default=str) + "\n")


def force_english_response(response: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(response, dict):
        return response

    response.setdefault("language", "en")
    response["language_policy"] = "English only for international contest demo"

    return response



def reset_session(session_id: str = "default"):
    SESSION_MEMORY[session_id] = {
        "session_id": session_id,
        "last_well": None,
        "last_variable": None,
        "last_intent": None,
        "last_normalized_prompt": None,
        "history": [],
    }
    return SESSION_MEMORY[session_id]
