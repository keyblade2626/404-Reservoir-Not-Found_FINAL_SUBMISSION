import csv
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

CONTEXT_CSV = ART / "diagnosis" / "well_property_driver_context.csv"
FINAL_JSON = ART / "final_diagnosis" / "final_hm_diagnosis.json"
AGENT_LOG = LOG_DIR / "reservoir_engineer_agent.jsonl"


CORE_PROPS = [
    "overall_hm_score",
    "oil_hm_score",
    "water_hm_score",
    "gas_hm_score",
    "bhp_hm_score",
    "mean_perm_h",
    "wellconn_weighted_tran_h",
    "wellconn_total_transmissibility",
    "mean_swat_eoh",
    "delta_swat",
    "mean_pressure_eoh",
    "delta_pressure",
    "mean_poro",
    "mean_tran_h_percentile",
    "wellconn_weighted_tran_h_percentile",
    "mean_swat_eoh_percentile",
    "delta_swat_percentile",
    "mean_pressure_eoh_percentile",
    "delta_pressure_percentile",
]


def safe_float(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None


def fmt(v: Any, nd: int = 2) -> str:
    x = safe_float(v)
    if x is None:
        return "N/A"
    return f"{x:.{nd}f}"


def load_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_context_rows() -> List[Dict[str, Any]]:
    return load_csv(CONTEXT_CSV)


def load_final_lookup() -> Dict[str, Dict[str, Any]]:
    payload = load_json(FINAL_JSON)
    if payload is None:
        return {}

    if isinstance(payload, list):
        items = payload
    else:
        items = payload.get("diagnoses") or payload.get("items") or []

    out = {}
    for item in items:
        w = str(item.get("well") or "").upper()
        if w:
            out[w] = item
    return out


def normalize_well_name(raw: str) -> str:
    s = str(raw or "").strip().upper()
    s = s.replace("_", "-").replace(" ", "-")
    m = re.match(r"HW-?(\d+[A-Z]?)", s)
    if m:
        return f"HW-{m.group(1)}"
    return s


def detect_well(question: str, rows: List[Dict[str, Any]]) -> Optional[str]:
    q = question.upper()

    known = [str(r.get("well") or "").upper() for r in rows if r.get("well")]
    known_sorted = sorted(known, key=len, reverse=True)

    for w in known_sorted:
        if w and w in q:
            return w

    m = re.search(r"\bHW[-_\s]?(\d+[A-Z]?)\b", q)
    if m:
        return f"HW-{m.group(1)}"

    return None


def detect_variable(question: str) -> str:
    q = question.lower()

    if any(x in q for x in ["water", "wct", "acqua", "water cut", "watercut"]):
        return "water"
    if any(x in q for x in ["oil", "olio", "opr", "wopr"]):
        return "oil"
    if any(x in q for x in ["gas", "gor", "gpr", "wgpr"]):
        return "gas"
    if any(x in q for x in ["bhp", "bottom", "pressione di fondo"]):
        return "bhp"
    if any(x in q for x in ["pressure", "pressione", "depletion", "deplet"]):
        return "pressure"
    if any(x in q for x in ["transmiss", "trasmiss", "tran", "moltiplicatore", "multiplier", "corridor", "corridoio"]):
        return "transmissibility"
    if any(x in q for x in ["swat", "saturazione acqua"]):
        return "swat"
    if any(x in q for x in ["perm", "permeability", "permeabil"]):
        return "permeability"

    return "overall"


def is_engineering_question(question: str) -> bool:
    q = question.lower()

    # Explicit visual commands should be handled by the visual/profile/map router,
    # not by the narrative diagnosis agent.
    explicit_visual = [
        "show water profile", "show oil profile", "show gas profile", "show bhp profile",
        "show water profiles", "show oil profiles", "show gas profiles", "show bhp profiles",
        "plot water", "plot oil", "plot gas", "plot bhp",
        "simulated vs observed",
        "show pressure depletion map", "show swat map", "show delta swat map",
        "show transmissibility map", "show permeability map",
        "show streamlines", "show connectivity",
    ]

    if any(x in q for x in explicit_visual):
        return False

    terms = [
        "why", "perche", "perché", "explain", "spiega", "causa", "cause",
        "mismatch", "match", "non torna", "problema", "critical", "critic",
        "cosa faccio", "recommend", "raccomanda", "azione", "transmiss",
        "pressure", "bhp", "water", "wct", "oil", "gas", "well", "pozzo",
        "permeability", "swat", "streamline", "connectivity", "conness",
        "simile", "similar", "compare", "confronta", "area"
    ]
    return any(t in q for t in terms)


def get_row(rows: List[Dict[str, Any]], well: str) -> Optional[Dict[str, Any]]:
    target = normalize_well_name(well)
    for r in rows:
        if normalize_well_name(r.get("well")) == target:
            return r
    return None


def score_col(variable: str) -> str:
    if variable == "pressure":
        return "bhp_hm_score"
    if variable in ["water", "oil", "gas", "bhp"]:
        return f"{variable}_hm_score"
    return "overall_hm_score"


def class_col(variable: str) -> str:
    if variable == "pressure":
        return "bhp_hm_class"
    if variable in ["water", "oil", "gas", "bhp"]:
        return f"{variable}_hm_class"
    return "overall_hm_class"


def variable_label(variable: str) -> str:
    return {
        "water": "water / WCT",
        "oil": "oil",
        "gas": "gas / GOR",
        "bhp": "BHP",
        "pressure": "BHP / pressure",
        "transmissibility": "transmissibility",
        "swat": "water saturation",
        "permeability": "permeability",
        "overall": "overall HM",
    }.get(variable, variable)


def classify_score(score: Optional[float]) -> str:
    if score is None:
        return "Not Evaluated"
    if score >= 80:
        return "Good"
    if score >= 60:
        return "Fair"
    return "Poor"


def active_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        excl = str(r.get("exclude_from_hm") or "").lower() in ["true", "1", "yes"]
        inactive = str(r.get("inactive_producer_zero_oil_history") or "").lower() in ["true", "1", "yes"]
        if not excl and not inactive:
            out.append(r)
    return out


def percentile_statement(name: str, value: Any) -> Optional[str]:
    v = safe_float(value)
    if v is None:
        return None
    if v >= 80:
        return f"{name} is high relative to the active wells (P{v:.0f})."
    if v <= 20:
        return f"{name} is low relative to the active wells (P{v:.0f})."
    return f"{name} is around the middle range of the active wells (P{v:.0f})."


def get_wct_override_text(row: Dict[str, Any]) -> Optional[str]:
    sim = safe_float(row.get("wct_override_max_sim_wct"))
    obs = safe_float(row.get("wct_override_max_obs_wct"))
    threshold = safe_float(row.get("wct_override_threshold"))

    if sim is not None and obs is not None:
        return (
            f"The maximum simulated WCT is about {sim*100:.2f}% and the maximum observed WCT is about {obs*100:.2f}%. "
            f"The negligible-water threshold is {((threshold or 0.01)*100):.2f}%."
        )

    return None


def similarity_distance(a: Dict[str, Any], b: Dict[str, Any], variable: str) -> float:
    props = [
        "mean_perm_h_percentile",
        "wellconn_weighted_tran_h_percentile",
        "mean_swat_eoh_percentile",
        "delta_swat_percentile",
        "mean_pressure_eoh_percentile",
        "delta_pressure_percentile",
        "mean_poro_percentile",
    ]

    d = 0.0
    n = 0

    for p in props:
        va = safe_float(a.get(p))
        vb = safe_float(b.get(p))
        if va is None or vb is None:
            continue
        d += abs(va - vb) / 100.0
        n += 1

    ia = safe_float(a.get("i"))
    ja = safe_float(a.get("j"))
    ib = safe_float(b.get("i"))
    jb = safe_float(b.get("j"))

    if ia is not None and ja is not None and ib is not None and jb is not None:
        # Spatial term, normalized loosely.
        d += min((((ia - ib) ** 2 + (ja - jb) ** 2) ** 0.5) / 150.0, 1.0)
        n += 1

    # Same direction / issue type should make them closer.
    if variable == "water":
        if a.get("water_direction") and a.get("water_direction") == b.get("water_direction"):
            d -= 0.25
        if a.get("water_timing_issue") and a.get("water_timing_issue") == b.get("water_timing_issue"):
            d -= 0.15

    return d / max(n, 1)


def find_similar_problem_wells(
    rows: List[Dict[str, Any]],
    target: Dict[str, Any],
    variable: str,
    max_items: int = 4
) -> List[Dict[str, Any]]:
    scol = score_col(variable)
    target_well = normalize_well_name(target.get("well"))
    target_score = safe_float(target.get(scol))

    candidates = []

    for r in active_rows(rows):
        if normalize_well_name(r.get("well")) == target_well:
            continue

        s = safe_float(r.get(scol))
        if s is None:
            continue

        # Prefer wells with same weak variable, but allow Fair as similar issue.
        same_problem = False
        if target_score is not None and target_score < 60 and s < 70:
            same_problem = True
        elif target_score is not None and target_score < 80 and s < 80:
            same_problem = True
        elif variable == "water" and r.get("water_direction") == target.get("water_direction"):
            same_problem = True
        elif variable in ["bhp", "pressure"] and s < 70:
            same_problem = True

        if not same_problem:
            continue

        dist = similarity_distance(target, r, variable)
        candidates.append((dist, r))

    candidates.sort(key=lambda x: x[0])
    return [r for _, r in candidates[:max_items]]


def top_problem_wells(rows: List[Dict[str, Any]], variable: str, limit: int = 5) -> List[Dict[str, Any]]:
    scol = score_col(variable)
    ranked = []

    for r in active_rows(rows):
        s = safe_float(r.get(scol))
        if s is None:
            continue
        ranked.append((s, r))

    ranked.sort(key=lambda x: x[0])
    return [r for _, r in ranked[:limit]]


def build_technical_evidence(row: Dict[str, Any], diagnosis: Dict[str, Any], variable: str) -> List[str]:
    evidence = []

    s = safe_float(row.get(score_col(variable)))
    c = row.get(class_col(variable)) or classify_score(s)

    evidence.append(f"{variable_label(variable).capitalize()} HM score is {fmt(s, 1)} ({c}).")

    if variable == "water":
        wct_text = get_wct_override_text(row)
        if wct_text:
            evidence.append(wct_text)

        direction = row.get("water_direction")
        timing = row.get("water_timing_issue")
        if direction:
            evidence.append(f"Water direction flag: {direction}.")
        if timing:
            evidence.append(f"Water timing flag: {timing}.")

        swat = percentile_statement("EOH water saturation around the well", row.get("mean_swat_eoh_percentile"))
        dswat = percentile_statement("Water saturation increase", row.get("delta_swat_percentile"))
        tran = percentile_statement("well-connection transmissibility", row.get("wellconn_weighted_tran_h_percentile"))

        for x in [swat, dswat, tran]:
            if x:
                evidence.append(x)

    elif variable in ["bhp", "pressure"]:
        peoh = percentile_statement("EOH pressure around the well", row.get("mean_pressure_eoh_percentile"))
        dp = percentile_statement("pressure depletion", row.get("delta_pressure_percentile"))
        tran = percentile_statement("well-connection transmissibility", row.get("wellconn_weighted_tran_h_percentile"))
        poro = percentile_statement("porosity", row.get("mean_poro_percentile"))

        for x in [peoh, dp, tran, poro]:
            if x:
                evidence.append(x)

        evidence.append(
            f"Mean pressure changed from {fmt(row.get('mean_pressure_init'), 1)} to {fmt(row.get('mean_pressure_eoh'), 1)} "
            f"(delta {fmt(row.get('delta_pressure'), 1)})."
        )

    elif variable == "oil":
        tran = percentile_statement("well-connection transmissibility", row.get("wellconn_weighted_tran_h_percentile"))
        kh = percentile_statement("connected KH", row.get("wellconn_total_kh_percentile"))
        pressure = percentile_statement("EOH pressure", row.get("mean_pressure_eoh_percentile"))

        for x in [tran, kh, pressure]:
            if x:
                evidence.append(x)

    elif variable == "gas":
        sgas = percentile_statement("EOH gas saturation", row.get("mean_sgas_eoh_percentile"))
        pressure = percentile_statement("EOH pressure", row.get("mean_pressure_eoh_percentile"))
        tran = percentile_statement("well-connection transmissibility", row.get("wellconn_weighted_tran_h_percentile"))

        for x in [sgas, pressure, tran]:
            if x:
                evidence.append(x)

    primary_driver = diagnosis.get("primary_driver") or row.get("primary_driver")
    driver_family = diagnosis.get("driver_family") or row.get("driver_family")

    if primary_driver:
        evidence.append(f"Existing diagnosis driver: {primary_driver}.")
    if driver_family:
        evidence.append(f"Driver family: {driver_family}.")

    return evidence


def build_recommendation(row: Dict[str, Any], variable: str) -> str:
    if variable == "water":
        wscore = safe_float(row.get("water_hm_score"))

        wct_text = get_wct_override_text(row)
        if wct_text and wscore is not None and wscore >= 80:
            return (
                "I would not spend HM effort on water for this well. The WCT is negligible in both simulated and observed profiles, "
                "so water is not a material mismatch. Focus instead on the weaker variables, especially BHP/pressure if it is Poor."
            )

        direction = str(row.get("water_direction") or "").lower()
        swat_p = safe_float(row.get("mean_swat_eoh_percentile"))
        tran_p = safe_float(row.get("wellconn_weighted_tran_h_percentile"))

        if "too_low" in direction:
            if swat_p is not None and swat_p > 60 and tran_p is not None and tran_p < 50:
                return (
                    "The model has water saturation near the producer but the effective connection seems weak. "
                    "I would first test a local transmissibility / MULT corridor along the plausible flow path, rather than changing relperm globally."
                )
            return (
                "Simulated water appears too low. I would inspect local connectivity, transmissibility corridors and streamline support before touching relperm. "
                "Relperm should be considered only if the same water mobility issue appears regionally across the same rock type."
            )

        if "too_high" in direction:
            return (
                "Simulated water appears too high. I would check whether there is an excessive high-transmissibility path or too-strong injector/edge-water support. "
                "A local transmissibility reduction or fault transmissibility review is more defensible than a global relperm change."
            )

        return (
            "For water, first decide if the mismatch is material in WCT terms. If it is material, use SWAT, delta SWAT, transmissibility and streamlines together "
            "to decide whether this is a connectivity/corridor issue or a regional mobility issue."
        )

    if variable in ["bhp", "pressure"]:
        return (
            "For BHP/pressure mismatch, I would first check regional pressure support and transmissibility connectivity. "
            "If pressure is too low, the model may be over-depleting or under-supported; review aquifer/injection support, barriers and transmissibility. "
            "Porosity can influence pore volume and pressure response, but it is a delicate edit because it changes volumes in place, so I would treat it as supporting evidence rather than the first tuning knob."
        )

    if variable == "oil":
        return (
            "For oil-rate mismatch, first check whether the well is under oil/liquid control in history. If controls are imposed, do not tune well controls. "
            "Then inspect pressure support, local transmissibility/KH and completion connection behavior. PI multiplier can be tested, but I would keep it as a last-resort local adjustment."
        )

    if variable == "gas":
        return (
            "For gas mismatch, distinguish GOR behavior from absolute gas rate. Check gas saturation, pressure depletion, gas-cap communication and vertical transmissibility. "
            "PVT or relperm changes are possible but should be treated as regional/high-impact edits, not a quick local fix."
        )

    if variable == "transmissibility":
        return (
            "For transmissibility edits, I would avoid isolated cell tweaking. Use a corridor-based MULT/TRAN test following the dynamic evidence: streamlines, pressure depletion, saturation change and neighboring wells with the same mismatch signature."
        )

    return (
        "I would combine HM scores, profiles, property maps and neighboring-well behavior before proposing edits. The strongest recommendations come when multiple independent signals point to the same mechanism."
    )


def row_summary(row: Dict[str, Any], variable: str) -> Dict[str, Any]:
    return {
        "well": row.get("well"),
        "score": safe_float(row.get(score_col(variable))),
        "class": row.get(class_col(variable)) or classify_score(safe_float(row.get(score_col(variable)))),
        "i": safe_float(row.get("i")),
        "j": safe_float(row.get("j")),
        "water_direction": row.get("water_direction"),
        "water_timing_issue": row.get("water_timing_issue"),
        "mean_perm_h": safe_float(row.get("mean_perm_h")),
        "tran_percentile": safe_float(row.get("wellconn_weighted_tran_h_percentile")),
        "swat_percentile": safe_float(row.get("mean_swat_eoh_percentile")),
        "delta_pressure_percentile": safe_float(row.get("delta_pressure_percentile")),
        "pressure_eoh_percentile": safe_float(row.get("mean_pressure_eoh_percentile")),
    }


def make_table(rows: List[Dict[str, Any]], variable: str) -> Dict[str, Any]:
    return {
        "type": "compact_table",
        "title": "Similar wells / same issue signature",
        "columns": [
            "well",
            "score",
            "class",
            "tran_percentile",
            "swat_percentile",
            "delta_pressure_percentile",
            "water_direction",
        ],
        "rows": [row_summary(r, variable) for r in rows],
    }


def optional_llm_polish(question: str, draft_answer: str, context: Dict[str, Any]) -> str:
    """
    Optional: if the project already has a Compass/OpenAI client, use it to make the
    answer more conversational. If not available, the deterministic answer is used.
    """
    try:
        from app.compass_client import call_compass_chat

        system = (
            "You are a senior reservoir engineer for an international contest demo. Always answer in English. Rewrite the draft answer to be clear, technical, "
            "action-oriented, and concise. Do not invent facts. Use only the provided context. "
            "Mention uncertainty when evidence is limited."
        )

        user = {
            "question": question,
            "draft_answer": draft_answer,
            "context": context,
        }

        polished = call_compass_chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, indent=2)},
            ],
            temperature=0.2,
        )

        if isinstance(polished, str) and len(polished.strip()) > 20:
            bad_phrases = [
                "Compass API is not configured",
                "COMPASS_API_BASE_URL",
                "COMPASS_API_KEY",
                "LLM-based Compass reasoning is disabled",
            ]

            if any(x.lower() in polished.lower() for x in bad_phrases):
                return draft_answer

            return polished.strip()

    except Exception:
        pass

    return draft_answer


def answer_reservoir_engineer_question(question: str) -> Optional[Dict[str, Any]]:
    rows = load_context_rows()

    if not rows:
        return None

    if not is_engineering_question(question):
        return None

    final_lookup = load_final_lookup()
    well = detect_well(question, rows)
    variable = detect_variable(question)

    # If no explicit well, answer at field/problem level.
    if not well:
        if variable == "overall":
            variable = "water" if "water" in question.lower() or "acqua" in question.lower() else "bhp"

        worst = top_problem_wells(rows, variable, limit=5)

        if not worst:
            return None

        lines = [
            f"I interpreted this as a field-level {variable_label(variable)} diagnostic. I will answer in English for the international demo.",
            f"The weakest active wells for {variable_label(variable)} are: "
            + ", ".join([f"{r.get('well')} ({fmt(r.get(score_col(variable)),1)})" for r in worst]) + ".",
        ]

        if variable in ["water", "transmissibility"]:
            lines.append(
                "To explain water mismatch, I would compare WCT materiality, SWAT/ΔSWAT, transmissibility percentiles and streamline/corridor support. "
                "A transmissibility edit is most defensible when several neighboring wells show the same mismatch direction and similar local property signals."
            )
        elif variable in ["bhp", "pressure"]:
            lines.append(
                "For pressure/BHP issues, check whether the weak wells cluster spatially and share depletion or support signatures. "
                "If several wells show similar pressure behavior, the cause is more likely regional support/connectivity than a single-well PI issue."
            )

        answer = "\n\n".join(lines)

        blocks = [
            make_table(worst, variable),
            {
                "type": "suggestions",
                "items": [
                    f"Show {variable_label(variable)} profiles simulated vs observed for {worst[0].get('well')}",
                    "Show pressure depletion map",
                    "Show transmissibility map",
                    "Show streamlines",
                ],
            },
        ]

        log_agent(question, answer, {"mode": "field_level", "variable": variable, "wells": [r.get("well") for r in worst]})

        return {
            "type": "visual_response",
            "answer": answer,
            "intent": "reservoir_engineer_field_diagnosis",
            "ui_blocks": blocks,
            "data": {
                "variable": variable,
                "worst_wells": [row_summary(r, variable) for r in worst],
            },
        }

    row = get_row(rows, well)

    if row is None:
        return None

    diagnosis = final_lookup.get(normalize_well_name(well), {})

    # If user asks generic "how is this well", use weakest variable.
    if variable == "overall":
        candidates = []
        for v in ["water", "oil", "gas", "bhp"]:
            s = safe_float(row.get(score_col(v)))
            if s is not None:
                candidates.append((s, v))
        if candidates:
            candidates.sort(key=lambda x: x[0])
            variable = candidates[0][1]

    evidence = build_technical_evidence(row, diagnosis, variable)
    similar = find_similar_problem_wells(rows, row, variable, max_items=4)
    recommendation = build_recommendation(row, variable)

    score = safe_float(row.get(score_col(variable)))
    klass = row.get(class_col(variable)) or classify_score(score)

    similar_text = ""
    if similar:
        similar_text = (
            "A similar issue signature appears on "
            + ", ".join([f"{r.get('well')} ({fmt(r.get(score_col(variable)),1)})" for r in similar])
            + ". I would compare these wells together before applying isolated tuning."
        )
    else:
        similar_text = "I did not find a strong neighboring/similar-well pattern from the available diagnostic table, so this may be more local or data-limited."

    draft = (
        f"For {well}, the main variable I focused on is {variable_label(variable)}. "
        f"The score is {fmt(score,1)} ({klass}).\n\n"
        f"Technical evidence:\n- " + "\n- ".join(evidence[:8]) + "\n\n"
        f"{similar_text}\n\n"
        f"Recommended interpretation/action: {recommendation}"
    )

    context = {
        "well": well,
        "variable": variable,
        "target": row_summary(row, variable),
        "evidence": evidence,
        "similar_wells": [row_summary(r, variable) for r in similar],
        "recommendation": recommendation,
    }

    answer = optional_llm_polish(question, draft, context)

    suggestions = [
        f"Show {variable_label(variable)} profiles simulated vs observed for {well}",
        f"Show pressure depletion map",
        f"Show transmissibility map around {well}",
        f"Show streamlines",
    ]

    if variable == "water":
        suggestions.insert(1, f"Show delta SWAT map")
    elif variable in ["bhp", "pressure"]:
        suggestions.insert(1, f"Show pressure depletion map")

    blocks = [
        make_table(similar, variable) if similar else {
            "type": "compact_notes",
            "items": ["No strong similar-well pattern was found from the current diagnostic table."]
        },
        {
            "type": "compact_notes",
            "items": evidence[:6],
        },
        {
            "type": "suggestions",
            "items": suggestions[:5],
        },
    ]

    log_agent(question, answer, context)

    return {
        "type": "visual_response",
        "answer": answer,
        "intent": "reservoir_engineer_well_diagnosis",
        "ui_blocks": blocks,
        "data": context,
        "agent_trace": {
            "ReservoirEngineerAgent": {
                "well": well,
                "variable": variable,
                "similar_well_count": len(similar),
            }
        }
    }


def log_agent(question: str, answer: str, context: Dict[str, Any]):
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "agent": "ReservoirEngineerAgent",
        "question": question,
        "answer_preview": answer[:500],
        "context": context,
    }

    with AGENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, default=str) + "\n")


if __name__ == "__main__":
    tests = [
        "HW-6 non mi convince, mi fai capire?",
        "perché HW-6 non matcha acqua?",
        "dove aumenteresti la transmissibility?",
        "fammi vedere i pozzi peggiori per pressione",
        "il problema di HW-6 si vede anche altrove?",
    ]

    for t in tests:
        print("=" * 80)
        print("Q:", t)
        out = answer_reservoir_engineer_question(t)
        print(json.dumps(out, indent=2, default=str)[:4000])
