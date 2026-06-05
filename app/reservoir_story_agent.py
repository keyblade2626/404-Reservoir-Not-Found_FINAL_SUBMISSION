import csv
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
CONTEXT_CSV = ART / "diagnosis" / "well_property_driver_context.csv"


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


def fmt(v, nd=1):
    x = safe_float(v)
    if x is None:
        return "N/A"
    return f"{x:.{nd}f}"


def load_rows():
    if not CONTEXT_CSV.exists():
        return []
    with CONTEXT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm_well(w):
    s = str(w or "").upper().strip()
    m = re.search(r"HW[-_\s]?(\d+[A-Z]?)", s)
    if m:
        return f"HW-{m.group(1)}"
    return s


def find_row(well):
    target = norm_well(well)
    for r in load_rows():
        if norm_well(r.get("well")) == target:
            return r
    return None


def clean_flag(value):
    s = str(value or "").strip()
    if not s:
        return ""
    s = s.replace("_", " ")
    s = s.replace("simulated too low", "the model is underpredicting")
    s = s.replace("simulated too high", "the model is overpredicting")
    s = s.replace("breakthrough timing close", "breakthrough timing is reasonably close")
    s = s.replace("no breakthrough detected", "no clear water breakthrough event is detected")
    s = s.replace("profile shape issue", "the simulated WCT profile does not reproduce the observed WCT trend or shape")
    s = s.replace("profile timing", "WCT profile-shape / trend mismatch")

    s = s.replace("high swat but low simulated water production", "water is present in the grid but is not effectively produced")
    s = s.replace("water mobility or local connectivity", "water mobility or local connectivity")
    return s


def score_and_class(row, variable):
    if variable == "pressure":
        variable = "bhp"

    score = safe_float(row.get(f"{variable}_hm_score"))
    klass = row.get(f"{variable}_hm_class")

    if klass:
        return score, klass

    if score is None:
        return None, "Not evaluated"
    if score >= 80:
        return score, "Good"
    if score >= 60:
        return score, "Fair"
    return score, "Poor"


def weakest_variable(row):
    candidates = []
    for v in ["water", "oil", "gas", "bhp"]:
        s = safe_float(row.get(f"{v}_hm_score"))
        if s is not None:
            candidates.append((s, v))
    if not candidates:
        return "overall"
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def infer_variable(question, row):
    q = str(question or "").lower()

    if any(x in q for x in ["water", "wct", "water cut"]):
        return "water"
    if any(x in q for x in ["oil", "opr"]):
        return "oil"
    if any(x in q for x in ["gas", "gor"]):
        return "gas"
    if any(x in q for x in ["bhp", "pressure", "depletion"]):
        return "bhp"

    return weakest_variable(row)


def property_sentence(row, variable):
    tran_p = safe_float(row.get("wellconn_weighted_tran_h_percentile"))
    swat_p = safe_float(row.get("mean_swat_eoh_percentile"))
    dswat_p = safe_float(row.get("delta_swat_percentile"))
    pressure_p = safe_float(row.get("mean_pressure_eoh_percentile"))
    dpressure_p = safe_float(row.get("delta_pressure_percentile"))
    poro_p = safe_float(row.get("mean_poro_percentile"))

    pieces = []

    if variable == "water":
        pieces.append(
            f"Around the well, end-of-history SWAT is at P{fmt(swat_p,0)} and the SWAT increase is at P{fmt(dswat_p,0)}."
        )
        pieces.append(
            f"The well-connection transmissibility is at P{fmt(tran_p,0)}."
        )

        if dswat_p is not None and dswat_p >= 70 and tran_p is not None and tran_p < 60:
            pieces.append(
                "That combination is important: water seems to be present or increasing near the well, but the effective path into the well may not be strong enough."
            )
        elif dswat_p is not None and dswat_p >= 70:
            pieces.append(
                "The increasing SWAT suggests that water is reaching the area, so I would not start by assuming that the model has no water support."
            )

    elif variable in ["bhp", "pressure"]:
        pieces.append(
            f"EOH pressure is at P{fmt(pressure_p,0)} and pressure depletion is at P{fmt(dpressure_p,0)}."
        )
        pieces.append(
            f"Transmissibility is at P{fmt(tran_p,0)} and porosity is at P{fmt(poro_p,0)}."
        )
        pieces.append(
            "For pressure mismatch, I would first think in terms of regional support/connectivity rather than immediately tuning the well PI."
        )

    elif variable == "oil":
        pieces.append(
            f"Transmissibility is at P{fmt(tran_p,0)}, pressure is at P{fmt(pressure_p,0)}, and the connected flow capacity should be checked against the oil profile."
        )

    elif variable == "gas":
        pieces.append(
            f"Pressure is at P{fmt(pressure_p,0)} and transmissibility is at P{fmt(tran_p,0)}. For gas, I would check whether the mismatch is a GOR behavior, gas-cap communication, or pressure-depletion effect."
        )

    return " ".join([p for p in pieces if p])


def wct_sentence(row):
    sim = safe_float(row.get("wct_override_max_sim_wct"))
    obs = safe_float(row.get("wct_override_max_obs_wct"))
    threshold = safe_float(row.get("wct_override_threshold")) or 0.01

    if sim is None or obs is None:
        return ""

    return (
        f"The maximum simulated WCT is approximately {sim*100:.2f}%, while the maximum observed WCT is approximately {obs*100:.2f}%. "
        f"With the current negligible-water threshold of {threshold*100:.1f}%, this tells me whether water is a material mismatch or just numerical/low-rate noise."
    )


def similar_wells_text(response_data):
    similar = response_data.get("similar_wells") or []
    if not similar:
        return "I do not see a very strong similar-well pattern from the current diagnostic table, so I would treat this as local or data-limited until the maps confirm otherwise."

    names = []
    for s in similar[:4]:
        well = s.get("well")
        score = s.get("score")
        if well:
            names.append(f"{well} ({fmt(score,1)})")

    if not names:
        return ""

    return (
        "This is not isolated: a similar signature appears on "
        + ", ".join(names)
        + ". I would compare these wells spatially before applying a local edit only on one well."
    )


def recommendation_story(row, variable):
    direction = clean_flag(row.get("water_direction"))
    driver = clean_flag(row.get("primary_driver"))
    family = clean_flag(row.get("driver_family"))

    if variable == "water":
        score, klass = score_and_class(row, "water")

        if score is not None and score >= 80:
            return (
                "I would not tune the model on water for this well. Water is not the main problem after the negligible-WCT check. "
                "The next useful investigation is the weakest remaining variable, especially BHP if it is poor."
            )

        if "underpredicting" in direction or "too low" in str(row.get("water_direction")).lower():
            return (
                "My working hypothesis is that the model has water in the area but does not connect or mobilize it effectively into the well. "
                "The first test I would run is a local transmissibility/corridor multiplier along the plausible dynamic path, then re-check the water profile and make sure nearby wells do not deteriorate. "
                "I would not start with global relative permeability unless the same pattern is repeated regionally in wells sharing the same rock type."
            )

        return (
            "I would use the water profile together with delta SWAT, local transmissibility and streamlines. "
            "If the profile shows a material WCT mismatch and the map shows a coherent corridor, a local transmissibility multiplier is a more controlled test than changing relperm globally."
        )

    if variable in ["bhp", "pressure"]:
        return (
            "For BHP, I would first test the pressure-support story. If the well is too depleted in the model, look for missing support or barriers that are too sealing. "
            "If the model pressure is too high, look for excessive support or overly open communication. Porosity can influence pressure through pore volume, but it is a high-impact parameter, so I would use it as supporting evidence rather than the first tuning knob."
        )

    if variable == "oil":
        return (
            "For oil, I would check whether the mismatch is really reservoir-driven or mostly imposed by history controls. If the well is under oil/liquid control, controls are not the tuning target. "
            "Then I would check pressure, KH/transmissibility and local connection quality before considering a PI multiplier."
        )

    if variable == "gas":
        return (
            "For gas, I would separate gas-rate mismatch from GOR mismatch. The key checks are pressure depletion, gas saturation, vertical communication and possible gas-cap support. "
            "PVT or relperm changes are possible but should only be considered if the issue is regional and consistent."
        )

    return (
        "The next step is to combine profile evidence, local property maps and similar-well behavior. The strongest model edit is the one supported by multiple independent signals."
    )


def build_followup_suggestions(well, variable):
    items = []

    if variable == "water":
        items += [
            f"Show water profile for {well}",
            f"Show delta SWAT map around {well}",
            f"Show transmissibility map around {well}",
            f"Compare {well} with similar water mismatch wells",
        ]
    elif variable in ["bhp", "pressure"]:
        items += [
            f"Show BHP profile for {well}",
            f"Show pressure depletion map around {well}",
            f"Compare {well} with similar pressure mismatch wells",
            f"Where would you test transmissibility near {well}?",
        ]
    else:
        items += [
            f"Show {variable} profile for {well}",
            f"Show pressure depletion map around {well}",
            f"Show transmissibility map around {well}",
            f"Compare {well} with similar wells",
        ]

    items.append("Show streamlines and connectivity")
    return items[:5]


def upgrade_reservoir_response(question: str, response: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(response, dict):
        return response

    if response.get("intent") not in [
        "reservoir_engineer_well_diagnosis",
        "reservoir_engineer_field_diagnosis",
        "water_mismatch_story",
        "gas_mismatch_story",
        "bhp_mismatch_story",
        "oil_mismatch_story",
    ]:
        return response

    data = response.get("data") or {}
    well = data.get("well") or data.get("target", {}).get("well")

    if not well:
        # Field-level response: just clean underscores and keep it readable.
        ans = str(response.get("answer") or "")
        response["answer"] = clean_flag(ans)
        return response

    row = find_row(well)
    if row is None:
        response["answer"] = clean_flag(str(response.get("answer") or ""))
        return response

    variable = data.get("variable") or infer_variable(question, row)
    if variable == "pressure":
        variable = "bhp"

    score, klass = score_and_class(row, variable)

    profile_word = {
        "water": "water/WCT",
        "oil": "oil-rate",
        "gas": "gas/GOR",
        "bhp": "BHP",
    }.get(variable, variable)

    p1 = (
        f"For {well}, I would investigate the {profile_word} mismatch first because its current match score is "
        f"{fmt(score,1)} ({klass}). I would not treat the score alone as the conclusion; I would use it as the entry point for a reservoir diagnosis."
    )

    if variable == "water":
        p2 = (
            "The first thing I would check is the simulated-vs-observed water profile. "
            "If the model underpredicts water while SWAT increases around the well, that usually means the model has water in the neighborhood but is not moving it into the well effectively."
        )
    elif variable == "bhp":
        p2 = (
            "The first thing I would check is the BHP profile. A pressure mismatch is often a support/connectivity issue, not simply a single-well problem."
        )
    else:
        p2 = (
            f"The first thing I would check is the {profile_word} profile to understand whether the mismatch is timing-driven, trend-driven or only a late-time deviation."
        )

    prop = property_sentence(row, variable)
    wct = wct_sentence(row) if variable == "water" else ""
    similar = similar_wells_text(data)
    reco = recommendation_story(row, variable)

    paragraphs = [p1, p2]
    if wct:
        paragraphs.append(wct)
    if prop:
        paragraphs.append("From the local property evidence, " + prop)
    paragraphs.append(similar)
    paragraphs.append("My current interpretation is: " + reco)

    response["answer"] = "\n\n".join(paragraphs)

    response["ui_blocks"] = [
        {
            "type": "compact_notes",
            "title": "Investigation workflow",
            "items": [
                f"1. Plot the {profile_word} simulated vs observed profile for {well}.",
                "2. Check whether the mismatch is material or only low-rate/noise-driven.",
                "3. Inspect the local property maps: pressure/depletion, SWAT change and transmissibility.",
                "4. Compare the same signature with nearby or similar wells before proposing a model edit.",
                "5. Test a controlled local change first; avoid global relperm/PVT edits unless the evidence is regional.",
            ],
        },
        {
            "type": "compact_notes",
            "title": "Key evidence",
            "items": [
                f"{profile_word} score: {fmt(score,1)} ({klass}).",
                property_sentence(row, variable) or "No strong local property evidence was extracted.",
                wct_sentence(row) if variable == "water" else "WCT check is not the primary evidence for this variable.",
                similar_wells_text(data),
            ],
        },
        {
            "type": "suggestions",
            "title": "Recommended next plots",
            "items": build_followup_suggestions(well, variable),
        },
    ]

    response.setdefault("agent_trace", {})
    response["agent_trace"]["ReservoirStoryAgent"] = {
        "well": well,
        "variable": variable,
        "mode": "technical_story_upgrade",
    }

    return response
