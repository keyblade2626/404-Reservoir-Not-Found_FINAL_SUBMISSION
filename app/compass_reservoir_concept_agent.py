import re
from typing import Dict, Any, Optional


CONCEPT_KEYWORDS = [
    "transmissibility",
    "transmissibilita",
    "trasmissibilita",
    "trasmissibilità",
    "relative permeability",
    "relperm",
    "water cut",
    "watercut",
    "wct",
    "bhp",
    "bottom hole pressure",
    "bottom-hole pressure",
    "streamline",
    "streamlines",
    "connectivity",
    "porosity",
    "permeability",
    "history matching",
    "swat",
    "oil saturation",
    "gas saturation",
    "pore volume",
    "aquifer",
    "fault transmissibility",
]


CONCEPT_TRIGGERS = [
    "what is",
    "what are",
    "define",
    "explain",
    "meaning of",
    "how does",
    "how do",
    "what does",
    "can you explain",
    "tell me what",
    "cos'è",
    "cosa è",
    "che cos'è",
    "che significa",
]


def is_concept_question(message: str) -> bool:
    q = str(message or "").lower().strip()

    has_trigger = any(t in q for t in CONCEPT_TRIGGERS)
    has_concept = any(k in q for k in CONCEPT_KEYWORDS)

    return has_trigger and has_concept


def detect_well(message: str) -> Optional[str]:
    q = str(message or "").upper()
    m = re.search(r"\bHW[-_\s]?(\d+[A-Z]?)\b", q)

    if m:
        return f"HW-{m.group(1)}"

    return None


def detect_main_concept(message: str) -> str:
    q = str(message or "").lower()

    if "transmiss" in q or "trasmiss" in q:
        return "transmissibility"
    if "relative permeability" in q or "relperm" in q:
        return "relative permeability"
    if "water cut" in q or "watercut" in q or "wct" in q:
        return "water cut / WCT"
    if "bhp" in q or "bottom hole" in q or "bottom-hole" in q:
        return "BHP"
    if "streamline" in q or "connectivity" in q:
        return "streamlines and connectivity"
    if "porosity" in q or "poro" in q:
        return "porosity"
    if "permeability" in q:
        return "permeability"
    if "history matching" in q:
        return "history matching"
    if "swat" in q or "water saturation" in q:
        return "water saturation"
    if "oil saturation" in q:
        return "oil saturation"
    if "gas saturation" in q:
        return "gas saturation"

    return "reservoir engineering concept"


def fallback_answer(message: str, concept: str, well: Optional[str]) -> str:
    if concept == "transmissibility":
        ans = (
            "Transmissibility is the effective ability of the reservoir grid to transmit flow between connected cells "
            "or toward a well. In a simulator it is controlled by permeability, geometry, thickness, cell connection, "
            "and phase mobility. In history matching, it controls how pressure support, water movement, and gas communication "
            "propagate through the model. If transmissibility is too low, support or breakthrough may arrive too late or too weak. "
            "If it is too high, pressure support or water/gas breakthrough may be too strong or too early."
        )
    elif concept == "relative permeability":
        ans = (
            "Relative permeability describes how easily each phase flows when multiple phases share the pore space. "
            "It controls phase mobility, water cut, GOR and breakthrough behavior. In history matching it should usually be treated "
            "as a rock-type or region-level parameter, not as a quick fix for one well."
        )
    elif concept == "water cut / WCT":
        ans = (
            "Water cut is the fraction of produced liquid that is water: WCT = water rate / (oil rate + water rate). "
            "It is often more meaningful than water rate alone, because water rate can look numerically mismatched while remaining immaterial "
            "if the oil rate is large and WCT is very low."
        )
    elif concept == "BHP":
        ans = (
            "BHP is bottom-hole pressure. It is a key diagnostic for pressure support, depletion and connectivity. "
            "A BHP mismatch can reveal model issues that are hidden when rates are constrained by historical controls."
        )
    elif concept == "streamlines and connectivity":
        ans = (
            "Streamlines are dynamic flow paths from the simulation. They help identify which areas or wells are connected through the flow field. "
            "They are useful for diagnosing whether a mismatch is related to communication, barriers, injector support, or a transmissibility corridor."
        )
    else:
        ans = (
            f"{concept} is a reservoir-engineering concept that should be interpreted together with profiles, spatial property maps, "
            "dynamic connectivity and neighboring-well behavior before making a history-matching change."
        )

    if well:
        ans += (
            f"\n\nApplied to {well}, I would not use the concept in isolation. I would first look at the relevant simulated-vs-observed profile, "
            "then inspect the local pressure/saturation/transmissibility maps and compare with similar nearby wells."
        )

    return ans


def answer_compass_concept(message: str) -> Dict[str, Any]:
    concept = detect_main_concept(message)
    well = detect_well(message)

    base = fallback_answer(message, concept, well)

    try:
        from app.compass_client import call_compass_chat

        system = (
            "You are a senior reservoir engineer agent for an international AI contest. "
            "Answer in English only. Explain reservoir-engineering concepts clearly and technically. "
            "Do not turn concept questions into field diagnostics unless the user explicitly asks for a well diagnosis. "
            "If a well is mentioned, explain how the concept would be used to investigate that well. "
            "Be practical: connect the concept to history matching, profiles, maps, streamlines and model-edit decisions. "
            "Avoid generic textbook language."
        )

        user = (
            f"User question: {message}\n\n"
            f"Detected concept: {concept}\n"
            f"Detected well: {well or 'none'}\n\n"
            f"Deterministic base answer:\n{base}\n\n"
            "Rewrite this as a natural expert answer. Keep it concise, technical and useful for a reservoir engineer. "
            "End with 2 or 3 suggested next diagnostic actions."
        )

        answer = call_compass_chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=800,
        )

        if not answer or len(answer.strip()) < 30:
            answer = base

    except Exception as exc:
        answer = base + f"\n\nCompass concept polishing was not available, so I used the deterministic concept explanation."

    suggestions = [
        "Show transmissibility map",
        "Show streamlines and connectivity",
        "Where would you test a transmissibility multiplier?",
        "Explain HW-10 mismatch",
    ]

    if well:
        suggestions = [
            f"Why is {well} not matching?",
            f"Show water profile for {well}",
            f"Show pressure depletion map around {well}",
            f"Show transmissibility map around {well}",
            "Show streamlines and connectivity",
        ]

    return {
        "type": "visual_response",
        "answer": answer.strip(),
        "intent": "compass_reservoir_concept_explanation",
        "ui_blocks": [
            {
                "type": "compact_notes",
                "title": "How this concept is used in HM",
                "items": [
                    "Use the concept to interpret profile mismatch, not as an isolated number.",
                    "Check spatial evidence: pressure/depletion, saturation change, transmissibility and streamlines.",
                    "Only propose a model edit when multiple independent signals support the same mechanism.",
                ],
            },
            {
                "type": "suggestions",
                "title": "Suggested next diagnostic actions",
                "items": suggestions,
            },
        ],
        "data": {
            "concept": concept,
            "well": well,
            "agent": "CompassReservoirConceptAgent",
        },
        "agent_trace": {
            "CompassReservoirConceptAgent": {
                "concept": concept,
                "well": well,
                "mode": "compass_first_concept_answer",
            }
        },
    }
