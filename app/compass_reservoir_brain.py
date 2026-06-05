import csv
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

CONTEXT_CSV = ART / "diagnosis" / "well_property_driver_context.csv"
BRAIN_LOG = LOG_DIR / "compass_reservoir_brain.jsonl"


def safe_float(v):
    try:
        if v is None or v == "":
            return None
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None


def load_rows():
    if not CONTEXT_CSV.exists():
        return []
    with CONTEXT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm_well(w):
    s = str(w or "").upper().strip()
    m = re.search(r"\bHW[-_\s]?(\d+[A-Z]?)\b", s)
    if m:
        return f"HW-{m.group(1)}"
    return s


def detect_well(text):
    q = str(text or "").upper()
    m = re.search(r"\bHW[-_\s]?(\d+[A-Z]?)\b", q)
    if m:
        return f"HW-{m.group(1)}"
    return None


def detect_variable(text):
    q = str(text or "").lower()

    if any(x in q for x in ["water", "wct", "water cut", "watercut"]):
        return "water"
    if any(x in q for x in ["oil", "opr", "wopr"]):
        return "oil"
    if any(x in q for x in ["gas", "gor", "gpr"]):
        return "gas"
    if any(x in q for x in ["bhp", "bottom hole"]):
        return "bhp"
    if any(x in q for x in ["pressure", "depletion"]):
        return "pressure"
    if any(x in q for x in ["transmissibility", "transmiss", "tran", "multiplier", "corridor"]):
        return "transmissibility"
    if any(x in q for x in ["swat", "water saturation"]):
        return "swat"
    if any(x in q for x in ["permeability", "perm"]):
        return "permeability"

    return None


def get_row(rows, well):
    if not well:
        return None

    target = norm_well(well)

    for r in rows:
        if norm_well(r.get("well")) == target:
            return r

    return None


def compact_row(row):
    if not row:
        return {}

    keys = [
        "well", "i", "j",
        "overall_hm_score", "overall_hm_class",
        "oil_hm_score", "oil_hm_class",
        "water_hm_score", "water_hm_class",
        "gas_hm_score", "gas_hm_class",
        "bhp_hm_score", "bhp_hm_class",
        "water_direction", "water_timing_issue",
        "water_max_sim_signal", "water_max_hist_signal",
        "wct_override_max_sim_wct", "wct_override_max_obs_wct",
        "mean_perm_h", "mean_swat_init", "mean_swat_eoh", "delta_swat",
        "mean_pressure_init", "mean_pressure_eoh", "delta_pressure",
        "mean_poro",
        "wellconn_weighted_tran_h",
        "wellconn_weighted_tran_h_percentile",
        "mean_swat_eoh_percentile",
        "delta_swat_percentile",
        "mean_pressure_eoh_percentile",
        "delta_pressure_percentile",
        "mean_poro_percentile",
    ]

    out = {}
    for k in keys:
        if k in row:
            out[k] = row.get(k)

    return out


def weakest_wells(rows, variable, limit=5):
    key = {
        "water": "water_hm_score",
        "oil": "oil_hm_score",
        "gas": "gas_hm_score",
        "bhp": "bhp_hm_score",
        "pressure": "bhp_hm_score",
        "overall": "overall_hm_score",
    }.get(variable or "overall", "overall_hm_score")

    ranked = []

    for r in rows:
        excluded = str(r.get("exclude_from_hm") or "").lower() in ["true", "1", "yes"]
        inactive = str(r.get("inactive_producer_zero_oil_history") or "").lower() in ["true", "1", "yes"]

        if excluded or inactive:
            continue

        s = safe_float(r.get(key))
        if s is not None:
            ranked.append((s, r))

    ranked.sort(key=lambda x: x[0])
    return [compact_row(r) for _, r in ranked[:limit]]


def get_memory():
    try:
        from app.conversation_memory import get_session
        return get_session("default")
    except Exception:
        return {
            "last_well": None,
            "last_variable": None,
            "last_intent": None,
            "history": [],
        }


def update_memory_from_brain(plan):
    try:
        from app.conversation_memory import update_memory

        fake_response = {
            "intent": plan.get("intent"),
            "agent_trace": {
                "CompassReservoirBrain": {
                    "well": plan.get("well"),
                    "variable": plan.get("variable"),
                }
            }
        }

        update_memory(
            question=plan.get("original_question", ""),
            response=fake_response,
            session_id="default",
            detected_well=plan.get("well"),
            detected_variable=plan.get("variable"),
            detected_intent=plan.get("intent"),
        )
    except Exception:
        pass


def extract_json(text):
    raw = str(text or "").strip()

    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()

    try:
        return json.loads(raw)
    except Exception:
        pass

    m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass

    return None


def build_compass_context(question):
    rows = load_rows()
    memory = get_memory()

    explicit_well = detect_well(question)
    explicit_variable = detect_variable(question)

    well = explicit_well or memory.get("last_well")
    variable = explicit_variable or memory.get("last_variable") or "overall"

    row = get_row(rows, well)

    return {
        "question": question,
        "detected_well": explicit_well,
        "detected_variable": explicit_variable,
        "memory": {
            "last_well": memory.get("last_well"),
            "last_variable": memory.get("last_variable"),
            "last_intent": memory.get("last_intent"),
            "recent_history": memory.get("history", [])[-5:],
        },
        "active_context": {
            "well": well,
            "variable": variable,
            "well_data": compact_row(row),
            "weakest_wells_for_variable": weakest_wells(rows, variable, limit=5),
        },
        "available_visual_tools": [
            {
                "name": "profile_plot",
                "use_when": "User asks to see simulated vs observed profile, plot, curve, trend, profile.",
                "command_examples": [
                    "Show water profiles simulated vs observed for HW-10",
                    "Show oil profiles simulated vs observed for HW-10",
                    "Show gas profiles simulated vs observed for HW-10",
                    "Show BHP profiles simulated vs observed for HW-10"
                ]
            },
            {
                "name": "property_map",
                "use_when": "User asks for maps: pressure, depletion, SWAT, delta SWAT, permeability, porosity, transmissibility, or property overlays.",
                "important_rule": "Preserve the property requested by the user. If the user asks for permeability plus streamlines, the command must be 'Show permeability map with streamlines', not transmissibility.",
                "command_examples": [
                    "Show permeability map with final streamlines",
                    "Show permeability map with initial streamlines",
                    "Show pressure depletion map with streamlines",
                    "Show delta SWAT map with wells",
                    "Show porosity map",
                    "Show transmissibility map"
                ]
            },
            {
                "name": "streamlines",
                "use_when": "User asks connectivity, streamlines, communication, flow paths.",
                "command_examples": [
                    "Show streamlines",
                    "Show final streamlines and connectivity",
                    "Show initial streamlines and connectivity",
                    "Compare initial and final streamlines"
                ]
            },
            {
                "name": "diagnosis",
                "use_when": "User asks why a well is not matching or what is the likely cause."
            }
        ],
    }


def compass_brain_answer(question: str) -> Dict[str, Any]:
    from app.compass_client import call_compass_chat

    context = build_compass_context(question)

    system = """
You are a senior Reservoir Engineer Agent inside an interactive history-matching application.

You are NOT a static FAQ bot.
You are NOT allowed to answer by copying internal flags.
You must behave like an expert reservoir engineer having a technical conversation with another reservoir engineer.

You can:
1. Answer open reservoir-engineering questions naturally.
2. Explain concepts such as transmissibility, WCT, BHP, relperm, streamlines, porosity, permeability.
3. Use the provided well diagnostics and context when the question is about a well.
4. Decide when a visual tool should be called.
5. Continue the conversation using memory, but do not repeat the previous answer.
6. Always answer in English.

Important behavior:
- If the user asks "what is transmissibility?", explain the concept. Do NOT turn it into a field ranking.
- If the user asks "why is HW-10 not matching?", diagnose HW-10 using the data.
- If the user asks "show the profile", infer the well and variable from memory and request a profile tool.
- If the user asks a concept plus a well, explain the concept and how to apply it to that well.
- If the user asks for a plot/map/streamlines, return a tool command. Preserve the requested property exactly: permeability plus streamlines means permeability as base layer and streamlines as overlay, not transmissibility. Streamlines are dynamic snapshots: if the user asks for beginning/start/initial history, request initial streamlines; if the user asks for end/current/final/end of history, request final streamlines; if the user asks compare/evolution, request initial vs final streamlines.
- Be technical, practical and conversational.
- Mention uncertainty if the evidence is insufficient.
- Do not invent numeric values not present in the context.

Return ONLY valid JSON with this schema:
{
  "mode": "direct_answer" | "tool_command",
  "intent": "concept" | "diagnosis" | "profile" | "map" | "connectivity" | "recommendation" | "comparison",
  "well": "HW-10 or null",
  "variable": "water/oil/gas/bhp/pressure/transmissibility/swat/permeability/overall/null",
  "answer": "natural expert answer in English",
  "tool_command": "exact command to execute if mode is tool_command, otherwise empty",
  "suggestions": ["2 to 5 useful follow-up actions"]
}
"""

    user = {
        "user_question": question,
        "reservoir_context": context,
    }

    raw = call_compass_chat(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, indent=2)},
        ],
        temperature=0.15,
        max_tokens=1100,
    )

    plan = extract_json(raw)

    if not plan:
        plan = {
            "mode": "direct_answer",
            "intent": "unknown",
            "well": context["active_context"].get("well"),
            "variable": context["active_context"].get("variable"),
            "answer": raw,
            "tool_command": "",
            "suggestions": [],
        }

    plan["original_question"] = question

    with BRAIN_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "question": question,
            "context": context,
            "raw_compass": raw,
            "plan": plan,
        }, default=str) + "\n")

    update_memory_from_brain(plan)

    return plan


def build_visual_response_from_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    suggestions = plan.get("suggestions") or []

    return {
        "type": "visual_response",
        "answer": plan.get("answer") or "",
        "intent": "compass_reservoir_brain_direct",
        "ui_blocks": [
            {
                "type": "suggestions",
                "title": "Suggested next steps",
                "items": suggestions[:5],
            }
        ] if suggestions else [],
        "data": {
            "plan": plan,
            "agent": "CompassReservoirBrain",
        },
        "agent_trace": {
            "CompassReservoirBrain": {
                "mode": plan.get("mode"),
                "intent": plan.get("intent"),
                "well": plan.get("well"),
                "variable": plan.get("variable"),
                "tool_command": plan.get("tool_command"),
            }
        },
    }
