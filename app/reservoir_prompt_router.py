import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

AGENT_LOG = LOG_DIR / "reservoir_agent_prompt_router.jsonl"


def normalize_text(text: str) -> str:
    return str(text or "").strip()


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def lower(text: str) -> str:
    return compact(text).lower()


def detect_well(message: str) -> Optional[str]:
    q = message.upper()

    # HW-6, HW6, HW 6
    m = re.search(r"\b([A-Z]{1,5})[\s_-]?(\d+[A-Z]?)\b", q)
    if m:
        prefix = m.group(1)
        number = m.group(2)

        # Prefer realistic well prefixes used in your model.
        if prefix in ["HW", "INJ", "PROD", "WELL", "H"]:
            if prefix == "HW":
                return f"HW-{number}"
            return f"{prefix}-{number}"

    # fallback exact HW pattern
    m = re.search(r"\bHW[-_\s]?(\d+[A-Z]?)\b", q)
    if m:
        return f"HW-{m.group(1)}"

    return None


def detect_variable(message: str) -> Optional[str]:
    q = lower(message)

    if any(x in q for x in ["wct", "water cut", "watercut", "acqua", "water", "wwpr", "wwct"]):
        return "water"

    if any(x in q for x in ["olio", "oil", "wopr", "opr"]):
        return "oil"

    if any(x in q for x in ["gas", "gor", "wgpr", "gpr"]):
        return "gas"

    if any(x in q for x in ["bhp", "bottom hole", "bottomhole", "pressione di fondo"]):
        return "bhp"

    if any(x in q for x in ["pressure", "pressione", "depletion", "deplet"]):
        return "pressure"

    if any(x in q for x in ["swat", "water saturation", "saturazione acqua"]):
        return "swat"

    if any(x in q for x in ["soil", "oil saturation", "saturazione olio"]):
        return "soil"

    if any(x in q for x in ["sgas", "gas saturation", "saturazione gas"]):
        return "sgas"

    if any(x in q for x in ["perm", "permeability", "permeabilita", "permeabilità"]):
        return "permeability"

    if any(x in q for x in ["tran", "transmissibility", "trasmissibilita", "trasmissibilità", "moltiplicatore"]):
        return "transmissibility"

    return None


def has_any(q: str, words) -> bool:
    return any(w in q for w in words)


def is_profile_intent(q: str) -> bool:
    return has_any(q, [
        "plot", "profile", "profiles", "curva", "grafico", "trend",
        "vs", "versus", "observed", "simulated", "osservato", "simulato",
        "storico", "history", "andamento", "fammi vedere"
    ])


def is_map_intent(q: str) -> bool:
    return has_any(q, [
        "map", "mappa", "heatmap", "visualizza", "vedere", "show",
        "dove", "area", "zona", "spatial", "spaziale"
    ])


def is_why_intent(q: str) -> bool:
    return has_any(q, [
        "why", "perche", "perché", "cause", "causa", "spiega", "explain",
        "problema", "problem", "non match", "mismatch", "sbagliato", "wrong",
        "criticita", "criticità", "diagnosi", "diagnosis"
    ])


def is_recommendation_intent(q: str) -> bool:
    return has_any(q, [
        "cosa faccio", "cosa posso fare", "recommend", "raccomanda",
        "azione", "action", "improve", "migliorare", "sistemare",
        "aumentare", "increase", "ridurre", "decrease", "apply multiplier"
    ])


def is_connectivity_intent(q: str) -> bool:
    return has_any(q, [
        "streamline", "streamlines", "connectivity", "connession",
        "conness", "comunica", "communication", "support", "supporto",
        "injector", "producer injector", "flusso"
    ])


def is_transmissibility_corridor_intent(q: str) -> bool:
    return has_any(q, [
        "increase transmissibility", "aumentare transmissibility",
        "aumentare trasmiss", "moltiplicatore", "corridor", "corridoio",
        "canale", "channel", "tran multiplier", "transmissibility multiplier"
    ])


def has_time_keyword(q: str) -> bool:
    return has_any(q, [
        "init", "initial", "iniziale", "inizio",
        "eoh", "end", "fine", "history", "final",
        "delta", "difference", "change", "varia", "depletion", "deplet"
    ])


def normalize_property_prompt(message: str, variable: str) -> str:
    q = lower(message)

    if variable == "pressure":
        if has_any(q, ["depletion", "deplet", "delta", "difference", "change", "varia"]):
            return "Show pressure depletion map"
        if has_any(q, ["init", "initial", "iniziale", "inizio"]):
            return "Show initial pressure map"
        if has_any(q, ["eoh", "end", "fine", "history", "final"]):
            return "Show pressure EOH map"
        return "Show pressure map"

    if variable == "swat":
        if has_any(q, ["delta", "difference", "change", "varia"]):
            return "Show delta SWAT map"
        if has_any(q, ["init", "initial", "iniziale", "inizio"]):
            return "Show initial SWAT map"
        if has_any(q, ["eoh", "end", "fine", "history", "final"]):
            return "Show SWAT EOH map"
        return "Show SWAT map"

    if variable == "soil":
        if has_any(q, ["delta", "difference", "change", "varia"]):
            return "Show delta oil saturation map"
        if has_any(q, ["init", "initial", "iniziale", "inizio"]):
            return "Show initial oil saturation map"
        if has_any(q, ["eoh", "end", "fine", "history", "final"]):
            return "Show oil saturation EOH map"
        return "Show oil saturation map"

    if variable == "sgas":
        if has_any(q, ["delta", "difference", "change", "varia"]):
            return "Show delta gas saturation map"
        if has_any(q, ["init", "initial", "iniziale", "inizio"]):
            return "Show initial gas saturation map"
        if has_any(q, ["eoh", "end", "fine", "history", "final"]):
            return "Show gas saturation EOH map"
        return "Show gas saturation map"

    if variable == "permeability":
        return "Show permeability map"

    if variable == "transmissibility":
        return "Show transmissibility map"

    return message


def normalize_reservoir_prompt(message: str) -> Dict[str, str]:
    original = compact(message)
    q = lower(original)
    well = detect_well(original)
    var = detect_variable(original)

    normalized = original
    intent = "passthrough"

    # Connectivity / streamlines
    if is_connectivity_intent(q) and not is_transmissibility_corridor_intent(q):
        normalized = "Show streamlines"
        intent = "connectivity_streamlines"

    # Transmissibility corridors / multiplier recommendation
    elif is_transmissibility_corridor_intent(q):
        if well:
            normalized = f"Where should I increase transmissibility for {well}?"
        else:
            normalized = "Where should I increase transmissibility?"
        intent = "transmissibility_corridor"

    # Why / diagnosis / mismatch
    elif is_why_intent(q):
        if var in ["water", "wct", None] and has_any(q, ["water", "wct", "acqua"]):
            normalized = f"Why is water not matching for {well}?" if well else "Why is water not matching?"
            intent = "water_mismatch_story"

        elif var == "gas":
            normalized = f"Why is gas not matching for {well}?" if well else "Why is gas not matching?"
            intent = "gas_mismatch_story"

        elif var in ["pressure", "bhp"]:
            normalized = f"Why is BHP not matching for {well}?" if well else "Why is BHP not matching?"
            intent = "bhp_mismatch_story"

        elif var == "oil":
            normalized = f"Why is oil not matching for {well}?" if well else "Why is oil not matching?"
            intent = "oil_mismatch_story"

        elif well:
            normalized = f"Show {well}"
            intent = "well_diagnosis"

    # Profile plot intent
    elif is_profile_intent(q) and well:
        if var == "water" or has_any(q, ["wct", "acqua"]):
            normalized = f"Show water profiles simulated vs observed for {well}"
            intent = "water_profile"

        elif var == "oil":
            normalized = f"Show oil profiles simulated vs observed for {well}"
            intent = "oil_profile"

        elif var == "gas":
            normalized = f"Show gas profiles simulated vs observed for {well}"
            intent = "gas_profile"

        elif var in ["bhp", "pressure"]:
            normalized = f"Show BHP profiles simulated vs observed for {well}"
            intent = "bhp_profile"

        else:
            normalized = f"Show water profiles simulated vs observed for {well}"
            intent = "default_profile"

    # Property map intent
    elif is_map_intent(q) and var in [
        "pressure", "swat", "soil", "sgas", "permeability", "transmissibility"
    ]:
        normalized = normalize_property_prompt(original, var)
        intent = "property_map"

    # User asks only about a well
    elif well and has_any(q, ["show", "tell", "dimmi", "vedi", "analizza", "diagnosi", "detail", "dettaglio"]):
        normalized = f"Show {well}"
        intent = "well_diagnosis"

    # Generic quality
    elif has_any(q, ["quality", "qualita", "qualità", "history matching", "hm", "match generale", "overall"]):
        normalized = "Show overall HM quality map"
        intent = "overall_hm"

    log_prompt_route(original, normalized, intent, well, var)

    return {
        "original": original,
        "normalized": normalized,
        "intent": intent,
        "well": well or "",
        "variable": var or "",
    }


def log_prompt_route(original: str, normalized: str, intent: str, well: Optional[str], variable: Optional[str]):
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "agent": "ReservoirEngineerPromptRouter",
        "original_prompt": original,
        "normalized_prompt": normalized,
        "intent": intent,
        "well": well,
        "variable": variable,
    }

    with AGENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


if __name__ == "__main__":
    tests = [
        "plot acqua hw6",
        "fammi vedere perché HW-6 non matcha l'acqua",
        "pressione zona sud",
        "dove aumenteresti la transmissibility?",
        "show me HW6 gas",
        "come sta messo HW-6?",
        "voglio vedere swat",
        "fammi vedere delta pressione",
    ]

    for t in tests:
        print(t, "=>", normalize_reservoir_prompt(t))
