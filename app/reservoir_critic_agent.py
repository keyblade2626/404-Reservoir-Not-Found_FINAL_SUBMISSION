
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _clean_text(s: str) -> str:
    s = str(s or "")
    replacements = {
        "ÎSWAT": "Delta SWAT",
        "Î”SWAT": "Delta SWAT",
        "ΔSWAT": "Delta SWAT",
        "â": "-",
        "—": "-",
        "–": "-",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    while "  " in s:
        s = s.replace("  ", " ")
    return s.strip()


def _extract_well_from_text(text: str) -> Optional[str]:
    m = re.search(r"\b(HW[-_\s]?\d+[A-Z]?)\b", str(text or ""), re.I)
    if not m:
        return None
    return m.group(1).upper().replace("_", "-").replace(" ", "-")


def _extract_well_from_response(response: Dict[str, Any], original_message: str = "") -> Optional[str]:
    # 1) Message first.
    well = _extract_well_from_text(original_message)
    if well:
        return well

    # 2) Answer.
    well = _extract_well_from_text(str(response.get("answer") or ""))
    if well:
        return well

    # 3) Data.
    data = response.get("data") or {}
    if isinstance(data, dict):
        for key in ["well", "target_well", "selected_well"]:
            well = _extract_well_from_text(str(data.get(key) or ""))
            if well:
                return well

    # 4) UI blocks titles.
    for block in response.get("ui_blocks") or []:
        if isinstance(block, dict):
            well = _extract_well_from_text(str(block.get("title") or ""))
            if well:
                return well

    return None


def _load_smart_recommendations() -> Dict[str, Any]:
    p = _repo_root() / "artifacts" / "diagnosis" / "smart_well_recommendations.json"
    if not p.exists():
        return {}

    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _has_relperm_signal_for_well(well: str) -> Dict[str, Any]:
    """
    Uses available RelPerm endpoint logic if possible; otherwise falls back to text evidence.
    """
    out = {
        "available": False,
        "eligible": False,
        "source": None,
        "message": None,
    }

    if not well:
        return out

    try:
        from app.relperm_sensitivity_agent import build_relperm_sensitivity_cached_v96

        payload = build_relperm_sensitivity_cached_v96(well)
        out["available"] = True
        out["eligible"] = bool(payload and payload.get("eligible"))
        out["source"] = "relperm_sensitivity_agent"
        out["message"] = payload.get("message") if isinstance(payload, dict) else None
        return out

    except Exception as exc:
        out["source"] = "relperm_sensitivity_agent_error"
        out["message"] = str(exc)

    # Fallback: search smart recommendation text.
    recs = _load_smart_recommendations()
    rec = recs.get(well) or recs.get(well.upper()) or {}

    text = " ".join([
        str(rec.get("smart_key_findings") or ""),
        str(rec.get("smart_pattern_context") or ""),
        str(rec.get("smart_local_evidence") or ""),
        str(rec.get("smart_recommended_action") or ""),
    ]).lower()

    if any(x in text for x in ["relperm", "relative permeability", "satnum", "water mobility", "krw"]):
        out["available"] = True
        out["eligible"] = True
        out["source"] = "smart_recommendation_text"
        out["message"] = "RelPerm/SATNUM/water-mobility language detected in smart recommendation."

    return out


def _has_tran_signal_for_well(well: str) -> Dict[str, Any]:
    out = {
        "available": False,
        "source": None,
        "message": None,
    }

    if not well:
        return out

    recs = _load_smart_recommendations()
    rec = recs.get(well) or recs.get(well.upper()) or {}

    text = " ".join([
        str(rec.get("smart_key_findings") or ""),
        str(rec.get("smart_pattern_context") or ""),
        str(rec.get("smart_local_evidence") or ""),
        str(rec.get("smart_recommended_action") or ""),
        str(rec.get("candidate_model_edit") or ""),
    ]).lower()

    if any(x in text for x in ["tran", "transmissibility", "corridor", "connectivity", "communication"]):
        out["available"] = True
        out["source"] = "smart_recommendation_text"
        out["message"] = "TRAN/transmissibility/corridor/connectivity language detected."

    return out


def _response_is_tran_or_relperm(response: Dict[str, Any]) -> Dict[str, bool]:
    intent = str(response.get("intent") or "").lower()
    answer = str(response.get("answer") or "").lower()

    block_types = " ".join([
        str(b.get("type") or "") for b in response.get("ui_blocks") or [] if isinstance(b, dict)
    ]).lower()

    trace_keys = " ".join((response.get("agent_trace") or {}).keys()).lower()

    is_tran = any(x in " ".join([intent, answer, block_types, trace_keys]) for x in [
        "tran_corridor",
        "tran multiplier",
        "transmissibility multiplier",
        "transmissibility",
        "corridor",
    ])

    is_relperm = any(x in " ".join([intent, answer, block_types, trace_keys]) for x in [
        "relperm",
        "relative permeability",
        "krw",
        "permeability curve",
    ])

    return {
        "is_tran": is_tran,
        "is_relperm": is_relperm,
    }


def review_response_for_model_edit_conflicts(
    message: str,
    response: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Conservative post-processor.
    It does not change ui_blocks. It only appends a warning when a model-edit conflict is plausible.
    """
    if not isinstance(response, dict):
        return response

    # Do not critic global ranked candidate lists or general diagnostic answers
    # as if they were specific model-edit recommendations.
    # The Critic should validate specific TRAN corridor or RelPerm candidate responses only.
    intent = str(response.get("intent") or "").lower()

    skip_intents = [
        "global_tran_multiplier_candidates",
        "global_tran_multiplier_candidates_empty",
        "compass_reservoir_brain_direct",
        "diagnostic_explanation",
        "reservoir_story",
        "executive_summary",
        "generic_diagnosis",
    ]

    if intent in skip_intents:
        response.setdefault("agent_trace", {})
        response["agent_trace"]["ReservoirCriticAgentV008"] = {
            "status": "skipped",
            "reason": "general diagnostic/global response; critic review applies only to specific TRAN/RelPerm model-edit responses",
        }
        return response

    route_type = _response_is_tran_or_relperm(response)

    if not (route_type["is_tran"] or route_type["is_relperm"]):
        response.setdefault("agent_trace", {})
        response["agent_trace"]["ReservoirCriticAgentV008"] = {
            "status": "skipped",
            "reason": "response is not a TRAN/RelPerm model-edit response",
        }
        return response

    well = _extract_well_from_response(response, original_message=message)

    if not well:
        response.setdefault("agent_trace", {})
        response["agent_trace"]["ReservoirCriticAgentV008"] = {
            "status": "skipped",
            "reason": "no well detected for model-edit conflict review",
        }
        return response

    relperm = _has_relperm_signal_for_well(well)
    tran = _has_tran_signal_for_well(well)

    warnings = []

    if route_type["is_tran"] and relperm.get("eligible"):
        warnings.append(
            f"{well} also has a RelPerm / water-mobility sensitivity signal. "
            "Treat the TRAN corridor and RelPerm edit as alternative history-matching hypotheses, "
            "not as automatic combined edits. Test TRAN-only and RelPerm-only cases first, then combine only if both are still justified."
        )

    if route_type["is_relperm"] and tran.get("available"):
        warnings.append(
            f"{well} also has TRAN / connectivity evidence in the smart recommendation. "
            "Do not apply a RelPerm curve change blindly if the main issue may be corridor connectivity. "
            "Compare the RelPerm-only case against a TRAN-only corridor case before combining edits."
        )

    if not warnings:
        response.setdefault("agent_trace", {})
        response["agent_trace"]["ReservoirCriticAgentV008"] = {
            "status": "reviewed_no_warning",
            "well": well,
            "route_type": route_type,
            "relperm_signal": relperm,
            "tran_signal": tran,
        }
        return response

    critic_text = (
        "\n\nReservoir Critic review: "
        + " ".join(warnings)
    )

    answer = str(response.get("answer") or "")
    if "Reservoir Critic review:" not in answer:
        response["answer"] = _clean_text(answer + critic_text)

    response.setdefault("agent_trace", {})
    response["agent_trace"]["ReservoirCriticAgentV008"] = {
        "status": "warning_added",
        "well": well,
        "route_type": route_type,
        "warnings": warnings,
        "relperm_signal": relperm,
        "tran_signal": tran,
    }

    return response
