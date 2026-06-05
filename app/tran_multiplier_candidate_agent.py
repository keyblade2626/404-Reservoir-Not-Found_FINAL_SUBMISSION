
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_smart_recommendations() -> Dict[str, Any]:
    p = _repo_root() / "artifacts" / "diagnosis" / "smart_well_recommendations.json"

    if not p.exists():
        return {}

    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}



def _clean_visible_text(s: str) -> str:
    """Clean mojibake/special symbols for dashboard-visible text."""
    s = str(s or "")

    replacements = {
        "ÎSWAT": "Delta SWAT",
        "Î”SWAT": "Delta SWAT",
        "ΔSWAT": "Delta SWAT",
        "â": "-",
        "—": "-",
        "–": "-",
        "“": "\"",
        "”": "\"",
        "’": "'",
        "‘": "'",
    }

    for old, new in replacements.items():
        s = s.replace(old, new)

    # Clean repeated spaces after replacements.
    while "  " in s:
        s = s.replace("  ", " ")

    return s.strip()





# ==========================================================
# V338 TRAN MULTIPLIER DIRECTION GUARD
# If simulated water is higher than observed water, do not rank
# the well as a candidate for TRAN increase.
# ==========================================================
def _water_bias_direction_from_rec_v338(rec: Dict[str, Any], already_joined_text: str = "") -> str:
    t = (already_joined_text or "").lower()

    # Also inspect common structured fields.
    for key in [
        "water_bias_direction",
        "water_mismatch_direction",
        "water_direction",
        "water_final_direction",
        "wct_bias",
        "wct_direction",
        "bias",
        "smart_key_findings",
        "smart_recommended_action",
        "candidate_model_edit",
        "action",
    ]:
        t += " " + str(rec.get(key) or "").lower()

    over_tokens = [
        "overestimated_wct",
        "overestimated",
        "over-estimated",
        "too high",
        "too_high",
        "simulated high",
        "simulated_high",
        "sim high",
        "sim_high",
        "simulated > observed",
        "sim > obs",
        "model > history",
        "above observed",
        "higher than observed",
        "early water",
        "early breakthrough",
        "too early",
        "bring water too early",
        "bring water too strongly",
        "overestimates wct",
    ]

    under_tokens = [
        "underestimated_wct",
        "underestimated",
        "under-estimated",
        "too low",
        "too_low",
        "simulated low",
        "simulated_low",
        "sim low",
        "sim_low",
        "simulated < observed",
        "sim < obs",
        "model < history",
        "below observed",
        "lower than observed",
        "late water",
        "late breakthrough",
        "too late",
        "delayed",
        "does not produce enough water",
        "bring too little water",
    ]

    if any(x in t for x in over_tokens):
        return "overestimated_wct"

    if any(x in t for x in under_tokens):
        return "underestimated_wct"

    return "unknown"


def _score_candidate(well: str, rec: Dict[str, Any]) -> Dict[str, Any]:
    text = " ".join([
        str(rec.get("smart_key_findings") or ""),
        str(rec.get("smart_pattern_context") or ""),
        str(rec.get("smart_local_evidence") or ""),
        str(rec.get("smart_recommended_action") or ""),
        str(rec.get("candidate_model_edit") or ""),
        str(rec.get("action") or ""),
        str(rec.get("driver_family") or ""),
        str(rec.get("likely_driver") or ""),
    ])

    t = text.lower()

    water_bias_v338 = _water_bias_direction_from_rec_v338(rec, t)

    score = 0
    reasons = []

    if "tran" in t or "transmissibility" in t:
        score += 4
        reasons.append("TRAN/transmissibility mentioned")

    if "corridor" in t:
        score += 3
        reasons.append("corridor mentioned")

    if "connectivity" in t or "communicate" in t or "communication" in t:
        score += 2
        reasons.append("connectivity issue mentioned")

    if "fault" in t:
        score += 2
        reasons.append("fault/corridor check mentioned")

    if "increase local/fault tran" in t or "increase local tran" in t or "increase transmissibility" in t:
        if water_bias_v338 == "overestimated_wct":
            score -= 20
            reasons.append("blocked TRAN increase: simulated water appears higher/earlier than observed")
        else:
            score += 4
            reasons.append("explicit TRAN increase hypothesis")

    if (
        "reduce tran" in t
        or "reduce local tran" in t
        or "lower fault transmissibility" in t
        or "lower local transmissibility" in t
        or "test a lower fault transmissibility" in t
    ):
        if water_bias_v338 == "underestimated_wct":
            score -= 20
            reasons.append("blocked TRAN reduction: simulated water appears lower/later than observed")
        else:
            score += 4
            reasons.append("explicit TRAN reduction hypothesis")

    if "export an ixf only if" in t or "candidate model edit" in t:
        score += 1
        reasons.append("candidate edit present")

    # Reduce score if recommendation clearly prefers relperm/SATNUM instead.
    if "better hypothesis is water relative permeability" in t:
        score -= 2
        reasons.append("relperm/SATNUM may be preferred if corridor is already connected")

    if "simple local tran increase is not strongly supported" in t:
        score -= 2
        reasons.append("simple local TRAN increase not strongly supported")

    # Strong negative signals: these should not appear as TRAN multiplier candidates.
    negative_no_tuning = [
        "no water-specific tuning is needed",
        "no water specific tuning is needed",
        "do not spend hm effort on water here",
        "no action required",
        "no water-specific tuning required",
        "no water specific tuning required",
    ]

    if any(x in t for x in negative_no_tuning):
        score -= 10
        reasons.append("recommendation says no water-specific tuning is needed")

    # Final guardrail: direction must be visible in the candidate object.
    if water_bias_v338 == "overestimated_wct":
        reasons.append("water-direction guard: model too wet, multiplier must be <= 1 if exported")
    elif water_bias_v338 == "underestimated_wct":
        reasons.append("water-direction guard: model too dry, multiplier must be >= 1 if exported")

    action = str(rec.get("smart_recommended_action") or "").strip()
    confidence = str(rec.get("smart_confidence") or rec.get("confidence") or "N/A")

    return {
        "well": well,
        "score": score,
        "confidence": confidence,
        "reasons": reasons,
        "action": action,
        "water_bias_direction": water_bias_v338,
        "raw": rec,
    }


def find_global_tran_multiplier_candidates(limit: int = 8) -> List[Dict[str, Any]]:
    recs = _load_smart_recommendations()

    candidates = []

    for well, rec in recs.items():
        if not isinstance(rec, dict):
            continue

        c = _score_candidate(well, rec)

        # Keep candidates where TRAN/corridor/connectivity is materially present.
        if c["score"] >= 5:
            candidates.append(c)

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:limit]


def answer_global_tran_multiplier_candidate_question(message: str) -> Dict[str, Any]:
    candidates = find_global_tran_multiplier_candidates(limit=8)

    if not candidates:
        return {
            "type": "visual_response",
            "answer": (
                "I understood this as a global TRAN multiplier candidate search. "
                "I did not find a strong global TRAN-corridor candidate list in the current smart recommendations. "
                "Please select a specific well, for example: show proposed TRAN corridor for HW-28."
            ),
            "intent": "global_tran_multiplier_candidates_empty",
            "ui_blocks": [
                {
                    "type": "suggestions",
                    "title": "Suggested follow-up",
                    "items": [
                        "Show proposed TRAN corridor for HW-28",
                        "Show proposed TRAN corridor for HW-10",
                        "Where would you test a transmissibility multiplier for HW-28?",
                    ],
                }
            ],
            "data": {
                "candidates": [],
                "message": message,
            },
            "agent_trace": {
                "GlobalTRANMultiplierCandidateAgent": {
                    "status": "no_candidates",
                    "source": "smart_well_recommendations.json",
                }
            },
        }

    lines = []
    suggestions = []

    for idx, c in enumerate(candidates, start=1):
        well = c["well"]
        reason = _clean_visible_text("; ".join(c["reasons"][:3]) or "TRAN/corridor candidate language detected")
        action = _clean_visible_text(c["action"])

        if len(action) > 220:
            action = action[:220].rstrip() + "..."

        lines.append(
            f"{idx}. {well} - candidate score {c['score']}. "
            f"Evidence: {reason}. "
            f"{('Action: ' + action) if action else ''}"
        )

        suggestions.append(f"Show proposed TRAN corridor for {well}")

    answer = (
        "LangGraph Orchestrator interpreted this as a global TRAN multiplier candidate search, "
        "not as a raw transmissibility map.\n\n"
        "Candidate wells/corridors to review first:\n"
        + "\n".join(lines)
        + "\n\nOpen a specific candidate to evaluate the proposed corridor and export IXF only after review."
    )

    answer = _clean_visible_text(answer)

    # Shared orchestrator memory: store ranked candidates for follow-up questions.
    try:
        from app.orchestrator_memory import update_memory

        update_memory(
            last_intent="global_tran_multiplier_candidates",
            last_route="global_tran_multiplier_candidate_agent",
            candidate_wells=[c["well"] for c in candidates],
            candidate_source="artifacts/diagnosis/smart_well_recommendations.json",
        )
    except Exception:
        pass

    return {
        "type": "visual_response",
        "answer": answer,
        "intent": "global_tran_multiplier_candidates",
        "ui_blocks": [
            {
                "type": "suggestions",
                "title": "Open candidate corridor",
                "items": suggestions[:6],
            }
        ],
        "data": {
            "candidates": [
                {
                    "well": c["well"],
                    "score": c["score"],
                    "confidence": c["confidence"],
                    "reasons": c["reasons"],
                    "action": c["action"],
                }
                for c in candidates
            ],
            "source": "artifacts/diagnosis/smart_well_recommendations.json",
        },
        "agent_trace": {
            "GlobalTRANMultiplierCandidateAgent": {
                "status": "success",
                "candidate_count": len(candidates),
                "source": "smart_well_recommendations.json",
            }
        },
    }
