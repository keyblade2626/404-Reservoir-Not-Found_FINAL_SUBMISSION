import re
from typing import Any, Dict, Optional

from app.dashboard_data import (
    get_summary_cards,
    get_top_mismatches,
    get_well_detail,
    get_area_summary,
)
from app.profile_series import get_profile_series
from app.profile_plotter import create_profile_plot
from app.agent_bus import log_event, new_run_id
from app.cell_property_layers import build_cell_property_layer
from app.streamline_visual_payloads import build_streamline_visual_payload
from app.visual_payloads import (
    get_visual_hm_map,
    get_property_visual_map,
    get_transmissibility_corridor_visual,
    resolve_property_name,
)


def log_chat_interaction(message: str, intent: str, artifacts_used=None):
    run_id = new_run_id()

    log_event(
        run_id=run_id,
        agent="Chat Copilot Agent",
        role="Route user questions to reservoir artifacts and visual evidence.",
        event="user_question_routed",
        status="success",
        message=f"User question routed with intent={intent}: {message}",
        inputs=["user question"],
        outputs=["chat answer", "visual evidence"],
        tools=["intent router", "artifact lookup", "visual payload builder"],
        handoff_to=None,
        metadata={
            "intent": intent,
            "artifacts_used": artifacts_used or [],
        },
    )


def detect_well(text: str) -> Optional[str]:
    m = re.search(r"\b([A-Z]{1,6}-?\d+[A-Z]?)\b", text.upper())
    if m:
        return m.group(1)
    return None


def detect_variable(q: str) -> str:
    q = q.lower()

    if any(x in q for x in ["wct", "water cut", "water", "wwpr", "acqua"]):
        return "water"

    if any(x in q for x in ["oil", "opr", "wopr", "olio"]):
        return "oil"

    if any(x in q for x in ["gas", "gor", "gpr", "wgpr"]):
        return "gas"

    if any(x in q for x in ["bhp", "pressure", "pressione", "pressur"]):
        return "bhp"

    if any(x in q for x in ["overall", "global", "totale", "general"]):
        return "overall"

    return "overall"



def needs_time_choice_for_property(q: str) -> bool:
    ql = q.lower()

    is_time_property = any(x in ql for x in [
        "swat", "water saturation", "saturazione acqua",
        "soil", "oil saturation", "saturazione olio",
        "sgas", "gas saturation", "saturazione gas",
        "pressure", "pressione"
    ])

    has_time = any(x in ql for x in [
        "init", "initial", "iniziale", "inizio",
        "eoh", "end", "fine", "final", "history",
        "delta", "difference", "change", "varia", "depletion", "deplet"
    ])

    return is_time_property and not has_time


def is_profile_question(q: str) -> bool:
    return any(x in q for x in [
        "profile", "profiles", "plot", "curve", "trend",
        "simulated vs observed", "observed vs simulated",
        "grafico", "fammi vedere"
    ])


def is_corridor_question(q: str) -> bool:
    q = q.lower()

    has_tran = any(x in q for x in [
        "transmiss", "trasmiss", "tran", "multiplier", "moltiplicatore", "corridor", "corridoio"
    ])

    has_action = any(x in q for x in [
        "increase", "decrease", "aumentare", "ridurre", "where", "dove",
        "suggest", "recommend", "candidate", "candidato", "canale", "channel"
    ])

    return has_tran and has_action


def is_property_map_question(q: str) -> bool:
    return any(x in q for x in [
        "property", "properties", "proprieta", "mappa proprieta",
        "swat", "soil", "sgas", "poro", "porosity", "pressure",
        "perm", "permeability", "transmissibility", "trasmissibilita",
        "tran", "kh"
    ])


def is_hm_map_question(q: str) -> bool:
    return any(x in q for x in [
        "map", "mappa", "show", "visualize", "visualizza",
        "hm map", "quality map", "mismatch map"
    ]) and any(x in q for x in [
        "hm", "match", "mismatch", "quality", "oil", "water", "gas", "bhp", "wct"
    ])


def is_ranking_question(q: str) -> bool:
    return any(x in q for x in [
        "ranking", "rank", "worst", "best", "poor", "bad", "weak",
        "highest mismatch", "largest mismatch", "top mismatch",
        "which wells", "quali pozzi", "peggiori", "migliori",
        "alto mismatch", "basso score"
    ])


def is_summary_question(q: str) -> bool:
    return any(x in q for x in [
        "quality", "history matching quality", "hm quality", "model quality",
        "overall quality", "summary", "overview", "qualità", "riassunto",
        "sintesi", "come siamo messi"
    ])




def is_streamline_question(q: str) -> bool:
    return any(x in q for x in [
        "streamline", "streamlines", "communication", "connectivity",
        "communicate", "comunic", "connession", "conness", "support"
    ])


def is_water_story_question(q: str) -> bool:
    return (
        any(x in q for x in ["why", "perche", "perché", "explain", "story", "storytelling", "cause", "causes"])
        and any(x in q for x in ["water", "wct", "acqua"])
    ) or any(x in q for x in [
        "why is water not matching",
        "water mismatch story",
        "explain water mismatch",
        "perche non matcha acqua",
        "perché non matcha acqua",
    ])


def detect_area(q: str) -> Optional[str]:
    if any(x in q for x in ["south", "southern", "area sud", "sud"]):
        return "south"
    if any(x in q for x in ["north", "northern", "area nord", "nord"]):
        return "north"
    if any(x in q for x in ["central", "center", "middle", "centro", "centrale"]):
        return "central"
    return None


def visual_response(answer: str, intent: str, ui_blocks: list, data: Optional[Dict[str, Any]] = None):
    log_chat_interaction(
        answer,
        intent,
        [b.get("source") for b in ui_blocks if isinstance(b, dict) and b.get("source")],
    )

    return {
        "type": "visual_response",
        "intent": intent,
        "answer": answer,
        "ui_blocks": ui_blocks,
        "data": data or {},
    }






# ==========================================================

def _v307_is_well_pressure_plot_request(q: str) -> bool:
    import re

    low = (q or "").lower()

    has_well = re.search(r"\b(hw[-_\s]?\d+[a-z]?)\b", low, re.I) is not None

    asks_plot = any(k in low for k in [
        "plot", "profile", "curve", "trend", "time series", "timeseries",
        "history", "evolution", "grafico", "profilo", "curva", "andamento"
    ])

    pressure_terms = any(k in low for k in [
        "pressure", "pressione", "bhp", "wbhp", "bottom hole", "bottom-hole"
    ])

    asks_map = any(k in low for k in [
        "map", "mappa", "property map", "grid map", "spatial", "spaziale"
    ])

    # If the user explicitly says map/mappa, don't override.
    if asks_map:
        return False

    return has_well and asks_plot and pressure_terms


def _v307_build_well_pressure_plot_response(q: str):
    """
    Reuses the existing well/profile mechanism by returning a clear chat instruction.
    If a dedicated ui_block builder exists later, it can be plugged here.
    """
    well = detect_well(q)

    # Try to use existing profile logic by forcing variable to pressure/BHP.
    # The frontend/chat router already supports profile blocks for well variables in most builds.
    return {
        "answer": (
            f"Showing the pressure time-series/profile for {well}. "
            "This is a well plot over time, not a reservoir pressure map."
        ),
        "intent": "well_pressure_profile_v307",
        "ui_blocks": [
            {
                "type": "well_profile_request",
                "well": well,
                "variable": "pressure",
                "title": f"Pressure profile - {well}",
                "y_label": "Pressure / BHP",
                "note": "Well pressure time-series requested by chat intent guard V307."
            }
        ],
        "trace": {
            "V307IntentGuard": {
                "routed_to": "well_pressure_profile",
                "reason": "well + pressure + plot/profile/trend request"
            }
        }
    }



def answer_question(message:
 str) -> Dict[str, Any]:
    q = message.lower().strip()
    well = detect_well(message)
    variable = detect_variable(q)

    # 0A. Streamline/connectivity scene.
    if is_streamline_question(q):
        base_layer = build_cell_property_layer("TRAN_H")
        streamline_payload = build_streamline_visual_payload()

        return visual_response(
            answer=(
                "I overlaid the available streamline/connectivity information on top of the TRAN_H heatmap. "
                "The lines are simplified to show dynamic communication trends rather than exact simulator geometry."
            ),
            intent="streamline_connectivity",
            ui_blocks=[
                {
                    "type": "cell_property_map",
                    "title": "TRAN_H with streamline connectivity overlay",
                    "payload": base_layer,
                    "streamline_payload": streamline_payload,
                    "source": "streamline visual artifacts + TRAN_H",
                },
                {
                    "type": "compact_notes",
                    "items": [
                        "Streamline lines are simplified for interpretation.",
                        "Use them to understand likely communication paths and support direction.",
                        "Combine this with mismatch WCT timing/trend behavior before deciding model edits.",
                    ],
                },
            ],
            data={"cell_layer": base_layer, "streamlines": streamline_payload},
        )

    # 0B. Water mismatch storytelling scene.
    if is_water_story_question(q):
        base_layer = build_cell_property_layer("SWAT_EOH")
        streamlines = build_streamline_visual_payload()

        return visual_response(
            answer=(
                "I prepared a water-mismatch investigation scene. "
                "The base layer is SWAT at end of history; active wells and available streamline/connectivity paths are overlaid. "
                "Use this view to check whether water is present near the wells and whether dynamic connectivity supports the observed water response."
            ),
            intent="water_mismatch_story",
            ui_blocks=[
                {
                    "type": "cell_property_map",
                    "title": "Water mismatch story: SWAT_EOH + wells + streamlines",
                    "payload": base_layer,
                    "streamline_payload": streamlines,
                    "source": "SWAT_EOH + streamline visual artifacts",
                },
                {
                    "type": "compact_notes",
                    "items": [
                        "If SWAT is high near a producer but simulated water is low, review effective connectivity or transmissibility corridors.",
                        "If simulated breakthrough is too early, review high-transmissibility channels or excessive injector support.",
                        "Inactive producers are excluded from HM interpretation.",
                    ],
                },
            ],
            data={"cell_layer": base_layer, "streamlines": streamlines},
        )

    # 1. Profile request.
    if well and is_profile_question(q):
        if variable == "overall":
            variable = "water"

        series = get_profile_series(well=well, variable=variable)
        fallback_plot = create_profile_plot(well=well, variable=variable)

        if isinstance(series, dict):
            series["fallback_plot"] = fallback_plot

        return visual_response(
            answer=(
                f"I prepared the {variable} simulated-vs-observed profile for {well}. "
                "Use this to check timing, magnitude and profile shape."
            ),
            intent="profile_series",
            ui_blocks=[
                {
                    "type": "profile_series",
                    "title": f"{well} {variable.upper()} profile",
                    "data": series,
                    "source": "SMSPEC/UNSMRY",
                }
            ],
            data={"well": well, "variable": variable},
        )

    # 2. Transmissibility corridor request.
    if is_corridor_question(q):
        corridor_payload = get_transmissibility_corridor_visual(well=well)
        tran_layer = build_cell_property_layer("TRAN_H")

        short = (
            "I highlighted the candidate transmissibility corridors over a cell-based TRAN_H heatmap. "
            "These are screening areas where a TRAN/MULT test may be meaningful if the mismatch direction supports it."
        )

        if well:
            short = (
                f"I highlighted candidate transmissibility corridors associated with {well} over the TRAN_H heatmap. "
                "Use this to inspect whether the suggested channel is geologically and dynamically plausible."
            )

        return visual_response(
            answer=short,
            intent="transmissibility_corridors",
            ui_blocks=[
                {
                    "type": "cell_property_map",
                    "title": "TRAN_H with candidate transmissibility corridors",
                    "payload": tran_layer,
                    "corridor_payload": corridor_payload,
                    "source": "GRDECL TRANX/TRANY + candidate corridor cells",
                },
                {
                    "type": "compact_notes",
                    "items": [
                        "The base heatmap is TRAN_H averaged along K.",
                        "Highlighted cells are candidate corridors, not automatic model edits.",
                        "Use this together with mismatch direction, streamlines and geological consistency.",
                    ],
                },
            ],
            data={"cell_layer": tran_layer, "corridors": corridor_payload},
        )

    # 3. Property visualization.
    if is_property_map_question(q):
        if needs_time_choice_for_property(q):
            return visual_response(
                answer=(
                    "This property changes with time. Which map do you want to inspect: initial, end of history, or delta/change?"
                ),
                intent="property_time_choice",
                ui_blocks=[
                    {
                        "type": "suggestions",
                        "items": [
                            f"Show initial {message}",
                            f"Show end of history {message}",
                            f"Show delta {message}",
                        ],
                    },
                    {
                        "type": "compact_notes",
                        "items": [
                            "Initial map shows the starting condition.",
                            "End-of-history map shows the current/history-matched condition.",
                            "Delta map shows end-of-history minus initial; useful for depletion or saturation change.",
                        ],
                    },
                ],
                data={},
            )

        prop = resolve_property_name(q)
        cell_layer = build_cell_property_layer(prop)

        return visual_response(
            answer=(
                f"I prepared a cell-based 2D heatmap for {cell_layer.get('label', prop)}. "
                "The map is averaged along K and wells are overlaid on top."
            ),
            intent="cell_property_map",
            ui_blocks=[
                {
                    "type": "cell_property_map",
                    "title": cell_layer.get("label", prop),
                    "payload": cell_layer,
                    "source": "GRDECL cell properties",
                }
            ],
            data=cell_layer,
        )

    # 4. HM map request.
    if is_hm_map_question(q):
        payload = get_visual_hm_map(variable=variable)

        return visual_response(
            answer=(
                f"I prepared the {variable.upper()} history-match map. "
                "Active producers are shown by default; inactive wells remain excluded unless explicitly enabled."
            ),
            intent="hm_map",
            ui_blocks=[
                {
                    "type": "interactive_map",
                    "map_kind": "hm_map",
                    "title": f"{variable.upper()} HM map",
                    "payload": payload,
                    "source": "hm_map_payload.json",
                }
            ],
            data=payload,
        )

    # 5. Area summary.
    area = detect_area(q)
    if area:
        area_data = get_area_summary(area)
        map_payload = get_visual_hm_map(variable=variable)

        return visual_response(
            answer=(
                f"I filtered the {area} area using map coordinates and summarized the weakest wells. "
                "Use the map to visually inspect where the issue is concentrated."
            ),
            intent="area_summary",
            ui_blocks=[
                {
                    "type": "compact_table",
                    "title": f"{area.upper()} area summary",
                    "rows": [
                        {"metric": "Well count", "value": area_data.get("well_count")},
                        {"metric": "Overall HM", "value": area_data.get("summary", {}).get("overall")},
                        {"metric": "Water HM", "value": area_data.get("summary", {}).get("water")},
                        {"metric": "BHP HM", "value": area_data.get("summary", {}).get("bhp")},
                    ],
                },
                {
                    "type": "interactive_map",
                    "map_kind": "hm_map",
                    "title": f"{area.upper()} area HM map",
                    "payload": map_payload,
                    "source": "hm_map_payload.json",
                },
            ],
            data=area_data,
        )

    # 6. Ranking request.
    if is_ranking_question(q):
        ranking = get_top_mismatches(variable, limit=8)
        map_payload = get_visual_hm_map(variable=variable)

        return visual_response(
            answer=(
                f"I ranked the weakest wells for {variable.upper()} HM and prepared the corresponding map. "
                "Focus first on active producers with the lowest score."
            ),
            intent="ranking",
            ui_blocks=[
                {
                    "type": "compact_table",
                    "title": f"Weakest {variable.upper()} wells",
                    "rows": ranking.get("items", [])[:8],
                },
                {
                    "type": "interactive_map",
                    "map_kind": "hm_map",
                    "title": f"{variable.upper()} HM map",
                    "payload": map_payload,
                    "source": "well_property_driver_context.csv",
                },
            ],
            data=ranking,
        )

    # 7. Well detail.
    if well:
        detail = get_well_detail(well)
        if detail.get("found"):
            map_payload = get_visual_hm_map(variable=variable)

            return visual_response(
                answer=(
                    f"I loaded the diagnostic detail for {detail['well']}. "
                    "Use the score cards and map location to inspect the well context."
                ),
                intent="well_detail",
                ui_blocks=[
                    {
                        "type": "well_cards",
                        "title": f"{detail['well']} diagnostic cards",
                        "data": detail,
                        "source": "well_property_driver_context.csv",
                    },
                    {
                        "type": "interactive_map",
                        "map_kind": "hm_map",
                        "title": f"{detail['well']} on HM map",
                        "payload": map_payload,
                        "focus_well": detail["well"],
                    },
                ],
                data=detail,
            )

    # 8. Summary.
    if is_summary_question(q):
        summary = get_summary_cards()
        map_payload = get_visual_hm_map(variable="overall")

        return visual_response(
            answer=(
                "I summarized the field-level HM quality. "
                "The overview separates inactive/non-evaluable wells from the active producer HM score."
            ),
            intent="summary",
            ui_blocks=[
                {
                    "type": "metric_cards",
                    "title": "HM summary",
                    "items": summary.get("cards", []),
                    "source": "well_property_driver_context.csv",
                },
                {
                    "type": "interactive_map",
                    "map_kind": "hm_map",
                    "title": "Overall HM map",
                    "payload": map_payload,
                    "source": "hm_map_payload.json",
                },
            ],
            data=summary,
        )

    # 9. Guided fallback.
    return visual_response(
        answer=(
            "I can help you inspect HM quality, profile plots, property maps, transmissibility corridors, "
            "well diagnosis and area-level issues. Use one of the suggested actions below."
        ),
        intent="guided_help",
        ui_blocks=[
            {
                "type": "suggestions",
                "items": [
                    "Show overall HM quality map",
                    "Show water mismatch map",
                    "Show BHP mismatch map",
                    "Show SWAT property map",
                    "Show pressure property map",
                    "Where should I increase transmissibility?",
                    "Show water profiles simulated vs observed for HW-6",
                ],
            }
        ],
        data={},
    )



# ==========================================================
# Reservoir Engineer Agent prompt router
# Allows natural language questions to be translated into the
# precise internal commands already supported by the dashboard.
# ==========================================================
try:
    from app.reservoir_prompt_router import normalize_reservoir_prompt

    _base_answer_question = answer_question

    def answer_question(message: str):
        route = normalize_reservoir_prompt(message)
        normalized = route.get("normalized") or message

        response = _base_answer_question(normalized)

        # Attach lightweight agent routing metadata for contest traceability.
        try:
            if isinstance(response, dict):
                response.setdefault("agent_trace", {})
                response["agent_trace"]["prompt_router"] = {
                    "agent": "ReservoirEngineerPromptRouter",
                    "original_prompt": route.get("original"),
                    "normalized_prompt": normalized,
                    "intent": route.get("intent"),
                    "well": route.get("well"),
                    "variable": route.get("variable"),
                }

                if route.get("intent") != "passthrough":
                    prefix = (
                        f"I interpreted your question as: "
                        f"`{normalized}`. "
                    )
                    response["answer"] = prefix + str(response.get("answer", ""))

            return response

        except Exception:
            return response

except Exception as _router_exc:
    pass



# ==========================================================
# Senior Reservoir Engineer Agent
# This agent goes beyond command routing: it correlates HM scores,
# local properties, saturation/pressure signals and similar wells.
# ==========================================================
try:
    from app.reservoir_engineer_agent import answer_reservoir_engineer_question

    _previous_answer_question_for_re_agent = answer_question

    def answer_question(message: str):
        try:
            agent_response = answer_reservoir_engineer_question(message)
            if agent_response is not None:
                return agent_response
        except Exception:
            pass

        return _previous_answer_question_for_re_agent(message)

except Exception:
    pass



# ==========================================================
# Conversational memory layer - English-only contest mode
# Keeps the technical thread across follow-up questions.
# ==========================================================
try:
    from app.conversation_memory import (
        enrich_question_with_context,
        update_memory,
        force_english_response,
    )

    _answer_question_before_memory = answer_question

    def answer_question(message: str):
        session_id = "default"

        enriched = enrich_question_with_context(message, session_id=session_id)
        enriched_question = enriched.get("enriched") or message

        response = _answer_question_before_memory(enriched_question)

        if isinstance(response, dict):
            response = force_english_response(response)

            response.setdefault("agent_trace", {})
            response["agent_trace"]["ConversationMemoryAgent"] = {
                "original_question": enriched.get("original"),
                "enriched_question": enriched_question,
                "used_context": enriched.get("used_context"),
                "last_well_before": enriched.get("memory_before", {}).get("last_well"),
                "last_variable_before": enriched.get("memory_before", {}).get("last_variable"),
                "detected_well": enriched.get("well"),
                "detected_variable": enriched.get("variable"),
            }

            # Make context use visible but not annoying.
            if enriched.get("used_context"):
                answer = str(response.get("answer") or "")
                if answer and not answer.lower().startswith("continuing from the previous context"):
                    response["answer"] = (
                        f"Continuing from the previous context "
                        f"({enriched.get('well') or 'same well'}, "
                        f"{enriched.get('variable') or 'same variable'}):\n\n"
                        + answer
                    )

        update_memory(
            question=message,
            response=response if isinstance(response, dict) else {},
            session_id=session_id,
            detected_well=enriched.get("well"),
            detected_variable=enriched.get("variable"),
            detected_intent=enriched.get("intent"),
        )

        return response

except Exception:
    pass



# ==========================================================
# Suppress Compass configuration messages in contest demo
# If Compass is not configured, never show technical API errors
# to the user; use deterministic reservoir diagnostics instead.
# ==========================================================
try:
    from app.reservoir_engineer_agent import answer_reservoir_engineer_question as _deterministic_re_answer

    _answer_question_before_compass_suppress = answer_question

    def answer_question(message: str):
        response = _answer_question_before_compass_suppress(message)

        try:
            answer_text = ""
            if isinstance(response, dict):
                answer_text = str(response.get("answer") or "")
            else:
                answer_text = str(response or "")

            bad_phrases = [
                "Compass API is not configured",
                "COMPASS_API_BASE_URL",
                "COMPASS_API_KEY",
                "LLM-based Compass reasoning is disabled",
            ]

            if any(x.lower() in answer_text.lower() for x in bad_phrases):
                fallback = _deterministic_re_answer(message)

                if fallback is not None:
                    fallback.setdefault("agent_trace", {})
                    fallback["agent_trace"]["CompassFallbackGuard"] = {
                        "reason": "Compass not configured message suppressed",
                        "used": "deterministic_reservoir_engineer_agent",
                    }
                    return fallback

                return {
                    "type": "visual_response",
                    "answer": (
                        "I will use the deterministic reservoir diagnostic workflow for this local demo. "
                        "Please specify a well or a mismatch variable, for example: "
                        "'Why is HW-10 not matching water?' or 'What is the weakest variable for HW-10?'."
                    ),
                    "intent": "deterministic_fallback",
                    "ui_blocks": [
                        {
                            "type": "suggestions",
                            "items": [
                                "Why is HW-10 not matching?",
                                "What is the weakest variable for HW-10?",
                                "Show water profile for HW-10",
                                "Show pressure depletion map",
                            ],
                        }
                    ],
                    "data": {},
                }

        except Exception:
            pass

        return response

except Exception:
    pass



# ==========================================================
# Reservoir Story Agent
# Converts raw diagnostic tables/flags into a technical
# reservoir-engineering investigation narrative.
# ==========================================================
try:
    from app.reservoir_story_agent import upgrade_reservoir_response

    _answer_question_before_story_agent = answer_question

    def answer_question(message: str):
        response = _answer_question_before_story_agent(message)

        try:
            response = upgrade_reservoir_response(message, response)
        except Exception:
            pass

        return response

except Exception:
    pass



# ==========================================================
# Conversation reset command
# ==========================================================
try:
    from app.conversation_memory import reset_session

    _answer_question_before_reset_command = answer_question

    def answer_question(message: str):
        q = str(message or "").strip().lower()

        if q in ["reset", "reset conversation", "clear context", "new topic", "start over"]:
            reset_session("default")
            return {
                "type": "visual_response",
                "answer": "Conversation context cleared. We can start a new reservoir investigation.",
                "intent": "reset_conversation",
                "ui_blocks": [
                    {
                        "type": "suggestions",
                        "items": [
                            "Why is HW-10 not matching?",
                            "Show pressure depletion map",
                            "Where would you test a transmissibility multiplier?",
                            "Which wells have the weakest water match?",
                        ],
                    }
                ],
                "data": {},
            }

        return _answer_question_before_reset_command(message)

except Exception:
    pass



# ==========================================================
# Contextual profile follow-up guard
# Handles "show the profile", "plot it", "show me the plot"
# using the current conversation memory before generic diagnosis.
# ==========================================================
try:
    from app.conversation_memory import get_session

    _answer_question_before_profile_followup_guard = answer_question

    def answer_question(message: str):
        q = str(message or "").strip().lower()

        profile_followups = [
            "show the profile",
            "show profile",
            "plot it",
            "show me the plot",
            "show me profile",
            "show the plot",
            "plot the profile",
            "profile",
        ]

        if q in profile_followups or any(x in q for x in ["show the profile", "plot it", "show me the plot"]):
            mem = get_session("default")
            well = mem.get("last_well")
            variable = mem.get("last_variable") or "water"

            if well:
                if variable in ["pressure"]:
                    variable = "BHP"
                elif variable in ["swat", "transmissibility", "permeability"]:
                    variable = "water"

                return _answer_question_before_profile_followup_guard(
                    f"Show {variable} profiles simulated vs observed for {well}"
                )

        return _answer_question_before_profile_followup_guard(message)

except Exception:
    pass



# ==========================================================
# FINAL PRIORITY ROUTER
# Concept questions must be answered as reservoir engineering
# explanations before any diagnostic/field-level agent runs.
# ==========================================================
try:
    from app.reservoir_concept_agent import answer_concept_with_case

    _answer_question_before_final_priority_router = answer_question

    def answer_question(message: str):
        q = str(message or "").strip().lower()

        concept_triggers = [
            "what is",
            "what are",
            "define",
            "explain",
            "meaning of",
            "how does",
            "how do",
            "what does",
            "cos'è",
            "cosa è",
            "che cos'è",
            "che significa",
        ]

        reservoir_concepts = [
            "transmissibility",
            "transmissibilita",
            "trasmissibilita",
            "trasmissibilità",
            "relative permeability",
            "relperm",
            "water cut",
            "wct",
            "bhp",
            "bottom hole pressure",
            "streamline",
            "streamlines",
            "connectivity",
            "porosity",
            "permeability",
            "history matching",
            "swat",
            "oil saturation",
            "gas saturation",
        ]

        is_concept_question = (
            any(t in q for t in concept_triggers)
            and any(c in q for c in reservoir_concepts)
        )

        if is_concept_question:
            concept_response = answer_concept_with_case(message)
            if concept_response is not None:
                concept_response.setdefault("agent_trace", {})
                concept_response["agent_trace"]["FinalPriorityRouter"] = {
                    "route": "concept_agent_first",
                    "reason": "concept question detected before diagnostic routing",
                }
                return concept_response

        return _answer_question_before_final_priority_router(message)

except Exception:
    pass



# ==========================================================
# ABSOLUTE FINAL ROUTER - Compass-first concept routing
# This must remain the last answer_question definition in this file.
# ==========================================================
try:
    from app.compass_reservoir_concept_agent import (
        is_concept_question as _final_is_concept_question,
        answer_compass_concept as _final_answer_compass_concept,
    )

    _answer_question_before_absolute_final_router = answer_question

    def answer_question(message: str):
        q = str(message or "").strip().lower()

        # 1. Reset must remain available.
        if q in ["reset", "reset conversation", "clear context", "new topic", "start over"]:
            try:
                from app.conversation_memory import reset_session
                reset_session("default")
            except Exception:
                pass

            return {
                "type": "visual_response",
                "answer": "Conversation context cleared. We can start a new reservoir investigation.",
                "intent": "reset_conversation",
                "ui_blocks": [
                    {
                        "type": "suggestions",
                        "items": [
                            "What is transmissibility?",
                            "Why is HW-10 not matching?",
                            "Show pressure depletion map",
                            "Where would you test a transmissibility multiplier?",
                        ],
                    }
                ],
                "data": {},
                "agent_trace": {
                    "AbsoluteFinalRouter": {
                        "route": "reset_conversation"
                    }
                },
            }

        # 2. Conceptual reservoir-engineering questions must go to Compass first.
        if _final_is_concept_question(message):
            response = _final_answer_compass_concept(message)
            response.setdefault("agent_trace", {})
            response["agent_trace"]["AbsoluteFinalRouter"] = {
                "route": "compass_concept_agent",
                "reason": "concept question detected before diagnostic routing",
            }
            return response

        # 3. Everything else goes to the existing visual/diagnostic pipeline.
        response = _answer_question_before_absolute_final_router(message)

        # 4. Safety override: if a concept question somehow leaked into diagnostics, fix it.
        try:
            answer_text = str(response.get("answer", "")) if isinstance(response, dict) else str(response)
            if _final_is_concept_question(message) and "field-level transmissibility diagnostic" in answer_text.lower():
                fixed = _final_answer_compass_concept(message)
                fixed.setdefault("agent_trace", {})
                fixed["agent_trace"]["AbsoluteFinalRouter"] = {
                    "route": "safety_override_to_compass_concept_agent",
                    "reason": "diagnostic answer detected for concept question",
                }
                return fixed
        except Exception:
            pass

        return response

except Exception as _absolute_final_router_error:
    pass



# ==========================================================


# ==========================================================
# V414 DIAGNOSTIC PRIORITY GUARD
# WCT/GOR/water/gas/oil/BHP + bias/cluster/mismatch questions
# must not be captured by deterministic property-map shortcuts.
# They should reach Compass/LangGraph-style diagnostic reasoning first.
# ==========================================================

def _is_holistic_diagnostic_query_v414(message: str) -> bool:
    msg = str(message or "").lower().replace("_", " ").replace("-", " ")
    msg = re.sub(r"\s+", " ", msg).strip()

    has_reservoir_signal = any(x in msg for x in [
        "wct", "water cut", "water",
        "gas", "gor", "gas oil ratio",
        "oil", "bhp", "pressure", "rate", "profile",
    ])

    has_diagnostic_intent = any(x in msg for x in [
        "bias", "cluster", "mismatch", "driver", "drivers",
        "weak", "weakest", "diagnostic", "diagnose",
        "history match", "history matching", "hm",
        "pattern", "evidence", "review first",
    ])

    return bool(has_reservoir_signal and has_diagnostic_intent)


# TRUE FINAL ROUTER - Compass Reservoir Brain
# Compass decides whether to answer directly or call a visual tool.
# This must remain the last answer_question definition.
# ==========================================================
try:
    from app.compass_reservoir_brain import (
        compass_brain_answer as _crb_answer,
        build_visual_response_from_plan as _crb_build_response,
    )

    _answer_question_before_compass_brain = answer_question

    def answer_question(message: str):
        q = str(message or "").strip().lower()

        if q in ["reset", "reset conversation", "clear context", "new topic", "start over"]:
            try:
                from app.conversation_memory import reset_session
                reset_session("default")
            except Exception:
                pass

            return {
                "type": "visual_response",
                "answer": "Conversation context cleared. We can start a new reservoir investigation.",
                "intent": "reset_conversation",
                "ui_blocks": [
                    {
                        "type": "suggestions",
                        "items": [
                            "What is transmissibility?",
                            "Why is HW-10 not matching?",
                            "Show water profile for HW-10",
                            "Show pressure depletion map",
                        ],
                    }
                ],
                "data": {},
                "agent_trace": {
                    "CompassReservoirBrain": {
                        "mode": "reset"
                    }
                },
            }

        try:
            plan = _crb_answer(message)

            mode = str(plan.get("mode") or "").lower()
            tool_command = str(plan.get("tool_command") or "").strip()

            if mode == "tool_command" and tool_command:
                tool_response = _answer_question_before_compass_brain(tool_command)

                if isinstance(tool_response, dict):
                    prefix = str(plan.get("answer") or "").strip()

                    if prefix:
                        old_answer = str(tool_response.get("answer") or "")
                        tool_response["answer"] = prefix + "\n\n" + old_answer

                    tool_response.setdefault("agent_trace", {})
                    tool_response["agent_trace"]["CompassReservoirBrain"] = {
                        "mode": "tool_command",
                        "original_question": message,
                        "tool_command": tool_command,
                        "intent": plan.get("intent"),
                        "well": plan.get("well"),
                        "variable": plan.get("variable"),
                    }

                    return tool_response

            return _crb_build_response(plan)

        except Exception as exc:
            # If Compass fails, fall back to the previous deterministic pipeline.
            response = _answer_question_before_compass_brain(message)

            if isinstance(response, dict):
                response.setdefault("agent_trace", {})
                response["agent_trace"]["CompassReservoirBrain"] = {
                    "mode": "fallback",
                    "error": str(exc),
                }

            return response

except Exception:
    pass



# ==========================================================
# ULTIMATE PROFILE ROUTER - Dynamic Profile Agent
# Explicit profile requests return numeric arrays for Plotly,
# not static PNG fallback.
# ==========================================================
try:
    from app.dynamic_profile_agent import answer_dynamic_profile_question as _dynamic_profile_answer

    _answer_question_before_dynamic_profile_router = answer_question

    def answer_question(message: str):
        try:
            profile_response = _dynamic_profile_answer(message)
            if profile_response is not None:
                return profile_response
        except Exception:
            pass

        return _answer_question_before_dynamic_profile_router(message)

except Exception:
    pass



# ==========================================================
# ABSOLUTE MAP ROUTER - preserve explicit raw property requests
# This must remain the last answer_question definition.

# Explicit map requests bypass Compass planning to avoid property/time drift.
# ==========================================================
try:
    from app.dynamic_visual_agent import answer_dynamic_visual_question as _absolute_dynamic_visual_answer

    _answer_question_before_absolute_map_router = answer_question

    def answer_question(message: str):
        q = str(message or "").lower()

        # V414: diagnostic bias/cluster questions must not bypass Compass/LangGraph.
        if _is_holistic_diagnostic_query_v414(message):
            try:
                response = _crb_answer(message)
                if isinstance(response, dict):
                    response.setdefault("agent_trace", {})["DiagnosticPriorityGuardV414"] = {
                        "route": "CompassReservoirBrain",
                        "reason": "Diagnostic WCT/GOR/water/gas/oil/BHP bias/cluster request routed before explicit property-map bypass.",
                        "bypassed": "explicit_map_property_shortcut",
                    }
                    response.setdefault("interaction_edges", []).append({
                        "from": "DiagnosticPriorityGuardV414",
                        "to": "CompassReservoirBrain",
                        "reason": "Holistic diagnostic intent has priority over property-map keyword shortcut.",
                    })
                    return response
            except Exception as exc:
                fallback = _answer_question_before_absolute_map_router(message)
                if isinstance(fallback, dict):
                    fallback.setdefault("agent_trace", {})["DiagnosticPriorityGuardV414"] = {
                        "route": "previous_agentic_pipeline",
                        "reason": "CompassReservoirBrain failed; diagnostic query still bypassed explicit property-map shortcut.",
                        "error": str(exc),
                    }
                return fallback


        explicit_map_words = [
            "map", "mappa", "heatmap", "plot", "show", "display", "visualize", "overlay"
        ]

        explicit_properties = [
            "permeability", "perm", "porosity", "poro",
            "transmissibility", "tran",
            "pressure", "depletion",
            "swat", "water saturation",
            "soil", "oil saturation",
            "sgas", "gas saturation",
            "streamline", "streamlines", "connectivity"
        ]

        is_explicit_visual = (
            any(w in q for w in explicit_map_words)
            and any(p in q for p in explicit_properties)
        )

        if is_explicit_visual:
            visual = _absolute_dynamic_visual_answer(message)
            if visual is not None:
                visual.setdefault("agent_trace", {})
                visual["agent_trace"]["AbsoluteMapRouter"] = {
                    "route": "dynamic_visual_agent",
                    "reason": "explicit map/property/streamline request bypassed Compass"
                }
                return visual

        return _answer_question_before_absolute_map_router(message)

except Exception:
    pass



# ==========================================================
# SPATIAL PATTERN ROUTER V29
# Handles systemic/regional/neighborhood mismatch questions.
# ==========================================================
try:
    from app.spatial_pattern_agent import answer_spatial_pattern_question as _spatial_pattern_answer

    _answer_question_before_spatial_pattern_router = answer_question

    def answer_question(message: str):
        try:
            spatial_response = _spatial_pattern_answer(message)
            if spatial_response is not None:
                return spatial_response
        except Exception:
            pass

        return _answer_question_before_spatial_pattern_router(message)

except Exception:
    pass



# ==========================================================
# CLUSTER MAP ROUTER V30
# Handles interactive mismatch cluster maps.
# ==========================================================
try:
    from app.cluster_map_agent import answer_cluster_map_question as _cluster_map_answer

    _answer_question_before_cluster_map_router = answer_question

    def answer_question(message: str):
        try:
            cluster_response = _cluster_map_answer(message)
            if cluster_response is not None:
                return cluster_response
        except Exception:
            pass

        return _answer_question_before_cluster_map_router(message)

except Exception:
    pass



# ==========================================================
# ABSOLUTE WCT BIAS MAP ROUTER V35
# This must remain the LAST answer_question definition.
# It forces WCT / water-cut bias map requests to the WCTBiasClusterAgent
# before any generic reservoir diagnosis router.
# ==========================================================
try:
    from app.cluster_map_agent import (
        answer_wct_bias_cluster_question as _absolute_wct_bias_answer,
    )

    _answer_question_before_absolute_wct_bias_router = answer_question

    def answer_question(message: str):
        q = str(message or "").lower()

        wct_bias_triggers = [
            "wct bias",
            "water cut bias",
            "watercut bias",
            "wct map",
            "water cut map",
            "wct direction",
            "water cut direction",
            "underestimate wct",
            "underestimated wct",
            "underestimates wct",
            "overestimate wct",
            "overestimated wct",
            "overestimates wct",
            "underestimate water cut",
            "underestimated water cut",
            "underestimates water cut",
            "overestimate water cut",
            "overestimated water cut",
            "overestimates water cut",
            "model underestimates water",
            "model overestimates water",
            "simulated too low water",
            "simulated too high water",
            "sottostima water",
            "sovrastima water",
            "sottostima acqua",
            "sovrastima acqua",
        ]

        if any(t in q for t in wct_bias_triggers):
            forced = _absolute_wct_bias_answer(message)
            if forced is not None:
                forced.setdefault("agent_trace", {})
                forced["agent_trace"]["AbsoluteWCTBiasRouterV35"] = {
                    "route": "answer_wct_bias_cluster_question",
                    "reason": "explicit WCT / water-cut bias map request",
                }
                return forced

        return _answer_question_before_absolute_wct_bias_router(message)

except Exception:
    pass



# ==========================================================
# ABSOLUTE WCT BIAS MAP ROUTER V36
# Last-resort hard router. It directly builds the WCT bias map
# and bypasses Compass/tool-command/field-diagnosis routing.
# ==========================================================
try:
    from app.cluster_map_agent import build_wct_bias_cluster_payload

    _answer_question_before_absolute_wct_bias_router_v36 = answer_question

    def _is_wct_bias_map_request_v36(message: str) -> bool:
        q = str(message or "").lower()

        triggers = [
            "wct bias",
            "water cut bias",
            "watercut bias",
            "wct map",
            "water cut map",
            "wct direction",
            "water cut direction",
            "underestimate wct",
            "underestimated wct",
            "underestimates wct",
            "overestimate wct",
            "overestimated wct",
            "overestimates wct",
            "underestimate water cut",
            "underestimated water cut",
            "underestimates water cut",
            "overestimate water cut",
            "overestimated water cut",
            "overestimates water cut",
            "model underestimates water cut",
            "model overestimates water cut",
            "model underestimates water",
            "model overestimates water",
            "simulated too low water",
            "simulated too high water",
            "sottostima water",
            "sovrastima water",
            "sottostima acqua",
            "sovrastima acqua",
        ]

        return any(t in q for t in triggers)

    def _build_wct_bias_response_v36(message: str):
        payload = build_wct_bias_cluster_payload()
        summary = payload.get("summary") or {}
        groups = payload.get("bias_groups") or []

        answer = payload.get("interpretation") or "I built the WCT bias pattern map."

        if groups:
            strongest = groups[0]
            weakest = ", ".join(str(x) for x in strongest.get("weakest_wells", [])[:6])
            answer += (
                f" Largest group: '{strongest.get('bias')}' with {strongest.get('count')} wells."
            )
            if weakest:
                answer += f" Weakest examples: {weakest}."

        return {
            "type": "visual_response",
            "answer": answer,
            "intent": "wct_bias_cluster_map",
            "ui_blocks": [
                {
                    "type": "wct_bias_cluster_map",
                    "title": "WCT Bias Pattern Map",
                    "payload": payload,
                },
                {
                    "type": "compact_table",
                    "title": "WCT bias groups",
                    "columns": [
                        "bias",
                        "count",
                        "avg_water_score",
                        "avg_delta_swat_percentile",
                        "avg_tran_percentile",
                        "weakest_wells",
                    ],
                    "rows": groups,
                },
                {
                    "type": "suggestions",
                    "title": "Suggested follow-up",
                    "items": [
                        "Show WCT underestimated areas over delta SWAT",
                        "Show WCT overestimated areas over permeability",
                        "Analyze neighborhood around the weakest underestimated WCT well",
                        "Compare underestimating and overestimating WCT clusters",
                    ],
                },
            ],
            "data": payload,
            "agent_trace": {
                "AbsoluteWCTBiasRouterV36": {
                    "route": "direct_build_wct_bias_cluster_payload",
                    "reason": "explicit WCT / water-cut bias request",
                    "summary": summary,
                }
            },
        }

    def answer_question(message: str):
        if _is_wct_bias_map_request_v36(message):
            return _build_wct_bias_response_v36(message)

        return _answer_question_before_absolute_wct_bias_router_v36(message)

except Exception as _wct_bias_router_v36_error:
    pass



# ==========================================================
# ABSOLUTE WCT BIAS MAP ROUTER V37
# Hard final router. No silent import failure at module load.
# This must remain the LAST answer_question definition.
# ==========================================================

_answer_question_before_absolute_wct_bias_router_v37 = answer_question

def _is_wct_bias_map_request_v37(message: str) -> bool:
    q = str(message or "").lower()

    triggers = [
        "wct bias",
        "water cut bias",
        "watercut bias",
        "wct map",
        "water cut map",
        "watercut map",
        "wct direction",
        "water cut direction",
        "underestimate wct",
        "underestimated wct",
        "underestimates wct",
        "overestimate wct",
        "overestimated wct",
        "overestimates wct",
        "underestimate water cut",
        "underestimated water cut",
        "underestimates water cut",
        "overestimate water cut",
        "overestimated water cut",
        "overestimates water cut",
        "model underestimates water cut",
        "model overestimates water cut",
        "model underestimates water",
        "model overestimates water",
        "simulated too low water",
        "simulated too high water",
        "sottostima water",
        "sovrastima water",
        "sottostima acqua",
        "sovrastima acqua",
    ]

    return any(t in q for t in triggers)


def _build_wct_bias_response_v37(message: str):
    from app.cluster_map_agent import build_wct_bias_cluster_payload

    payload = build_wct_bias_cluster_payload()
    summary = payload.get("summary") or {}
    groups = payload.get("bias_groups") or []

    answer = payload.get("interpretation") or "I built the WCT bias pattern map."

    if groups:
        strongest = groups[0]
        weakest = ", ".join(str(x) for x in strongest.get("weakest_wells", [])[:6])
        answer += f" Largest group: '{strongest.get('bias')}' with {strongest.get('count')} wells."
        if weakest:
            answer += f" Weakest examples: {weakest}."

    return {
        "type": "visual_response",
        "answer": answer,
        "intent": "wct_bias_cluster_map",
        "ui_blocks": [
            {
                "type": "wct_bias_cluster_map",
                "title": "WCT Bias Pattern Map",
                "payload": payload,
            },
            {
                "type": "compact_table",
                "title": "WCT bias groups",
                "columns": [
                    "bias",
                    "count",
                    "avg_water_score",
                    "avg_delta_swat_percentile",
                    "avg_tran_percentile",
                    "weakest_wells",
                ],
                "rows": groups,
            },
            {
                "type": "suggestions",
                "title": "Suggested follow-up",
                "items": [
                    "Show WCT underestimated areas over delta SWAT",
                    "Show WCT overestimated areas over permeability",
                    "Analyze neighborhood around the weakest underestimated WCT well",
                    "Compare underestimating and overestimating WCT clusters",
                ],
            },
        ],
        "data": payload,
        "agent_trace": {
            "AbsoluteWCTBiasRouterV37": {
                "route": "direct_build_wct_bias_cluster_payload",
                "reason": "explicit WCT / water-cut bias request",
                "summary": summary,
            }
        },
    }


def answer_question(message: str):
    if _is_wct_bias_map_request_v37(message):
        try:
            return _build_wct_bias_response_v37(message)
        except Exception as exc:
            return {
                "type": "visual_response",
                "answer": f"WCT Bias Router was triggered, but failed while building the map: {exc}",
                "intent": "wct_bias_cluster_map_error",
                "ui_blocks": [],
                "data": {"error": str(exc)},
                "agent_trace": {
                    "AbsoluteWCTBiasRouterV37": {
                        "route": "error",
                        "error": str(exc),
                    }
                },
            }

    return _answer_question_before_absolute_wct_bias_router_v37(message)



# ==========================================================
# TRAN CORRIDOR VISUAL ROUTER V47
# Must remain near the end: handles proposed TRAN corridor visualization.
# ==========================================================
try:
    from app.tran_corridor_export_agent import answer_tran_corridor_visual_question as _tran_corridor_visual_answer

    _answer_question_before_tran_corridor_visual_router_v47 = answer_question

    def answer_question(message: str):
        try:
            corridor_response = _tran_corridor_visual_answer(message)
            if corridor_response is not None:
                return corridor_response
        except Exception as exc:
            return {
                "type": "visual_response",
                "answer": f"TRAN corridor visual agent failed: {exc}",
                "intent": "tran_corridor_visual_error",
                "ui_blocks": [],
                "data": {"error": str(exc)},
                "agent_trace": {
                    "TRANCorridorVisualRouterV47": {
                        "error": str(exc),
                    }
                },
            }

        return _answer_question_before_tran_corridor_visual_router_v47(message)

except Exception:
    pass



# ==========================================================
# ABSOLUTE TRAN CORRIDOR VISUAL ROUTER V48
# Forces corridor/multiplier requests to the corridor visual agent
# before generic transmissibility map routing.
# ==========================================================

_answer_question_before_absolute_tran_corridor_v48 = answer_question

def _is_absolute_tran_corridor_request_v48(message: str) -> bool:
    q = str(message or "").lower()
    q = q.replace("-", " ").replace("_", " ")

    has_tran_word = any(x in q for x in [
        "tran",
        "transmissibility",
        "trasmissibility",
        "transmissibil",
        "trasmissibil",
    ])

    has_corridor_or_multiplier = any(x in q for x in [
        "corridor",
        "multiplier",
        "multipliers",
        "apply multiplier",
        "apply multipliers",
        "where to apply",
        "ixf",
    ])

    return has_tran_word and has_corridor_or_multiplier

def answer_question(message: str):
    if _is_absolute_tran_corridor_request_v48(message):
        try:
            from app.tran_corridor_export_agent import answer_tran_corridor_visual_question
            response = answer_tran_corridor_visual_question(message)
            if response is not None:
                response.setdefault("agent_trace", {})
                response["agent_trace"]["AbsoluteTRANCorridorRouterV48"] = {
                    "route": "answer_tran_corridor_visual_question",
                    "reason": "explicit TRAN corridor / multiplier request",
                }
                return response
        except Exception as exc:
            return {
                "type": "visual_response",
                "answer": f"TRAN corridor visual router failed: {exc}",
                "intent": "tran_corridor_visual_error",
                "ui_blocks": [],
                "data": {"error": str(exc)},
                "agent_trace": {
                    "AbsoluteTRANCorridorRouterV48": {
                        "error": str(exc),
                    }
                },
            }

    return _answer_question_before_absolute_tran_corridor_v48(message)



# ==========================================================
# GENERIC PLOT ROUTER V49
# Handles delta maps, generic property maps and profile ensembles.
# Must be near the end but before generic diagnosis fallback.
# ==========================================================

_answer_question_before_generic_plot_router_v49 = answer_question

def answer_question(message: str):
    try:
        from app.generic_plot_agent import answer_generic_plot_question
        generic_response = answer_generic_plot_question(message)
        if generic_response is not None:
            return generic_response
    except Exception as exc:
        return {
            "type": "visual_response",
            "answer": f"Generic plot agent failed: {exc}",
            "intent": "generic_plot_error",
            "ui_blocks": [],
            "data": {"error": str(exc)},
            "agent_trace": {
                "GenericPlotRouterV49": {
                    "error": str(exc),
                }
            },
        }

    return _answer_question_before_generic_plot_router_v49(message)



# ==========================================================
# PROFILE ENSEMBLE ROUTER V58
# Routes all-well profile ensemble requests to ProfileEnsembleAgent.
# ==========================================================

_answer_question_before_profile_ensemble_router_v58 = answer_question

def answer_question(message: str):
    try:
        from app.profile_ensemble_agent import answer_profile_ensemble_question
        response = answer_profile_ensemble_question(message)
        if response is not None:
            return response
    except Exception as exc:
        return {
            "type": "visual_response",
            "answer": f"Profile Ensemble Agent failed: {exc}",
            "intent": "profile_ensemble_error",
            "ui_blocks": [],
            "data": {"error": str(exc)},
            "agent_trace": {
                "ProfileEnsembleRouterV58": {
                    "error": str(exc),
                }
            },
        }

    return _answer_question_before_profile_ensemble_router_v58(message)



# ==========================================================
# RELPERM SENSITIVITY ROUTER V60
# Routes relperm / Krw / permeability-curve requests.
# ==========================================================

_answer_question_before_relperm_sensitivity_router_v60 = answer_question

def answer_question(message: str):
    try:
        from app.relperm_sensitivity_agent import answer_relperm_sensitivity_question
        response = answer_relperm_sensitivity_question(message)
        if response is not None:
            return response
    except Exception as exc:
        return {
            "type": "visual_response",
            "answer": f"RelPerm Sensitivity Agent failed: {exc}",
            "intent": "relperm_sensitivity_error",
            "ui_blocks": [],
            "data": {"error": str(exc)},
            "agent_trace": {
                "RelPermSensitivityRouterV60": {
                    "error": str(exc),
                }
            },
        }

    return _answer_question_before_relperm_sensitivity_router_v60(message)



# ==========================================================
# WELL PRESSURE PROFILE GUARD V307 SAFE FINAL
# Must stay at the very end of chat_router.py.
# Prevents "pressure plot/profile for HW-xx" from being routed as a pressure map.
# ==========================================================

_answer_question_before_well_pressure_profile_guard_v307 = answer_question

def _is_well_pressure_profile_request_v307(message: str) -> bool:
    import re

    q = str(message or "").lower()

    has_well = re.search(r"\b(hw[-_\s]?\d+[a-z]?)\b", q, re.I) is not None

    pressure_terms = [
        "pressure",
        "pressione",
        "bhp",
        "wbhp",
        "bottom hole pressure",
        "bottom-hole pressure",
    ]

    profile_terms = [
        "plot",
        "profile",
        "profiles",
        "curve",
        "trend",
        "time series",
        "timeseries",
        "history",
        "andamento",
        "grafico",
        "profilo",
        "curva",
    ]

    explicit_map_terms = [
        "map",
        "mappa",
        "property map",
        "heatmap",
        "spatial",
        "spaziale",
        "distribution",
        "distribuzione",
    ]

    has_pressure = any(x in q for x in pressure_terms)
    asks_profile = any(x in q for x in profile_terms)
    asks_map = any(x in q for x in explicit_map_terms)

    # If the user explicitly asks for a map, keep map routing.
    if asks_map:
        return False

    return has_well and has_pressure and asks_profile


def _extract_well_for_pressure_profile_v307(message: str):
    import re

    m = re.search(r"\b(hw[-_\s]?\d+[a-z]?)\b", str(message or ""), re.I)
    if not m:
        return None

    well = m.group(1).upper().replace("_", "-").replace(" ", "-")
    return well


def answer_question(message: str):
    if _is_well_pressure_profile_request_v307(message):
        well = _extract_well_for_pressure_profile_v307(message)

        if well:
            normalized = f"Show BHP profiles simulated vs observed for {well}"
            response = _answer_question_before_well_pressure_profile_guard_v307(normalized)

            if isinstance(response, dict):
                response.setdefault("agent_trace", {})
                response["agent_trace"]["WellPressureProfileGuardV307"] = {
                    "route": "well_profile_timeseries",
                    "original_question": message,
                    "normalized_question": normalized,
                    "reason": "well + pressure + plot/profile request should render a profile_series, not a pressure map",
                }

                answer = str(response.get("answer") or "")
                prefix = (
                    f"I interpreted your request as a well pressure time-series/profile for {well}, "
                    "not as a reservoir pressure map. "
                )

                if prefix not in answer:
                    response["answer"] = prefix + answer

            return response

    return _answer_question_before_well_pressure_profile_guard_v307(message)



# ==========================================================
# WELL PRESSURE PROFILE GUARD V309 DIRECT
# Must stay at the very end of chat_router.py.
# Bypasses GenericPlotAgent for "pressure plot/profile for HW-xx".
# ==========================================================

_answer_question_before_well_pressure_profile_guard_v309 = answer_question

def _is_well_pressure_profile_request_v309(message: str) -> bool:
    import re

    q = str(message or "").lower()

    has_well = re.search(r"\b(hw[-_\s]?\d+[a-z]?)\b", q, re.I) is not None

    has_pressure = any(x in q for x in [
        "pressure",
        "pressione",
        "bhp",
        "wbhp",
        "bottom hole pressure",
        "bottom-hole pressure",
    ])

    asks_profile = any(x in q for x in [
        "plot",
        "profile",
        "profiles",
        "curve",
        "trend",
        "time series",
        "timeseries",
        "history",
        "andamento",
        "grafico",
        "profilo",
        "curva",
    ])

    asks_map = any(x in q for x in [
        "map",
        "mappa",
        "property map",
        "heatmap",
        "spatial",
        "spaziale",
        "distribution",
        "distribuzione",
    ])

    # Explicit map requests must remain maps.
    if asks_map:
        return False

    return has_well and has_pressure and asks_profile


def _extract_well_for_pressure_profile_v309(message: str):
    import re

    m = re.search(r"\b(hw[-_\s]?\d+[a-z]?)\b", str(message or ""), re.I)
    if not m:
        return None

    return m.group(1).upper().replace("_", "-").replace(" ", "-")


def _response_contains_property_map_v309(response) -> bool:
    if not isinstance(response, dict):
        return False

    for block in response.get("ui_blocks") or []:
        if isinstance(block, dict) and block.get("type") == "generic_property_map":
            return True

    return False


def _response_contains_profile_series_v309(response) -> bool:
    if not isinstance(response, dict):
        return False

    for block in response.get("ui_blocks") or []:
        if isinstance(block, dict) and block.get("type") == "profile_series":
            return True

    return False


def answer_question(message: str):
    if _is_well_pressure_profile_request_v309(message):
        well = _extract_well_for_pressure_profile_v309(message)

        if well:
            normalized = f"Show BHP profiles simulated vs observed for {well}"

            profile_response = None
            profile_error = None

            # Call the dynamic profile agent directly, bypassing GenericPlotAgent.
            try:
                from app.dynamic_profile_agent import answer_dynamic_profile_question
                profile_response = answer_dynamic_profile_question(normalized)
            except Exception as exc:
                profile_error = str(exc)

            if profile_response is not None and not _response_contains_property_map_v309(profile_response):
                if isinstance(profile_response, dict):
                    profile_response.setdefault("agent_trace", {})
                    profile_response["agent_trace"]["WellPressureProfileGuardV309"] = {
                        "route": "direct_dynamic_profile_agent",
                        "original_question": message,
                        "normalized_question": normalized,
                        "reason": "pressure plot/profile for a well must be rendered as profile_series, not generic_property_map",
                    }

                    answer = str(profile_response.get("answer") or "")
                    prefix = (
                        f"I interpreted your request as a well pressure time-series/profile for {well}, "
                        "not as a reservoir pressure map. "
                    )

                    if prefix not in answer:
                        profile_response["answer"] = prefix + answer

                return profile_response

            # If direct profile agent failed or returned nothing, do NOT fall back to generic map.
            return {
                "type": "visual_response",
                "answer": (
                    f"I understood this as a pressure profile request for {well}, not a pressure map. "
                    "However, I could not find a valid BHP/pressure profile payload for this well. "
                    "Please check that the observed/simulated BHP profile data are available."
                ),
                "intent": "well_pressure_profile_unavailable",
                "ui_blocks": [],
                "data": {
                    "well": well,
                    "normalized_question": normalized,
                    "profile_error": profile_error,
                },
                "agent_trace": {
                    "WellPressureProfileGuardV309": {
                        "route": "direct_dynamic_profile_agent_failed",
                        "original_question": message,
                        "normalized_question": normalized,
                        "error": profile_error,
                    }
                },
            }

    return _answer_question_before_well_pressure_profile_guard_v309(message)



# ==========================================================
# LANGGRAPH ORCHESTRATOR SHADOW HOOK V001
# Must stay at the very end of chat_router.py.
# It does NOT change routing. It only logs/attaches the LangGraph decision.
# ==========================================================

_answer_question_before_langgraph_shadow_hook_v001 = answer_question

def answer_question(message: str):
    response = _answer_question_before_langgraph_shadow_hook_v001(message)

    try:
        from app.langgraph_orchestrator import (
            run_langgraph_shadow_orchestrator,
            append_orchestrator_trace_jsonl,
        )

        shadow = run_langgraph_shadow_orchestrator(message)
        append_orchestrator_trace_jsonl(shadow)

        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["LangGraphOrchestratorShadowV001"] = {
                "mode": "shadow",
                "decision": shadow.get("decision"),
                "trace": shadow.get("trace"),
                "changed_response": False,
            }

    except Exception as exc:
        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["LangGraphOrchestratorShadowV001"] = {
                "mode": "shadow_error",
                "error": str(exc),
                "changed_response": False,
            }

    return response



# ==========================================================
# LANGGRAPH ORCHESTRATOR ACTIVE HOOK V002
# Must stay at the very end of chat_router.py.
# Active only for high-confidence safe routes:
# - tran_multiplier_candidate
# - well_profile
# - relperm_sensitivity
# Everything else falls back to the current working router chain.
# ==========================================================

_answer_question_before_langgraph_active_hook_v002 = answer_question


def _lg_v002_add_trace(response, shadow, routed, active_route=None, error=None):
    if not isinstance(response, dict):
        return response

    response.setdefault("agent_trace", {})
    response["agent_trace"]["LangGraphOrchestratorActiveV002"] = {
        "mode": "active_high_confidence_only",
        "decision": shadow.get("decision") if isinstance(shadow, dict) else None,
        "trace": shadow.get("trace") if isinstance(shadow, dict) else None,
        "routed": routed,
        "active_route": active_route,
        "error": error,
    }
    return response


def answer_question(message: str):
    shadow = None

    try:
        from app.langgraph_orchestrator import (
            run_langgraph_shadow_orchestrator,
            append_orchestrator_trace_jsonl,
        )

        shadow = run_langgraph_shadow_orchestrator(message)
        append_orchestrator_trace_jsonl(shadow)

        decision = shadow.get("decision") or {}
        intent = decision.get("intent")
        confidence = decision.get("confidence")
        normalized = decision.get("normalized_question") or message

        # --------------------------------------------------
        # 1) TRAN multiplier / corridor candidates
        # --------------------------------------------------
        if confidence == "high" and intent == "tran_multiplier_candidate":
            try:
                from app.tran_corridor_export_agent import answer_tran_corridor_visual_question

                response = answer_tran_corridor_visual_question(normalized)

                if response is None:
                    response = {
                        "type": "visual_response",
                        "answer": (
                            "LangGraph correctly classified this as a TRAN multiplier candidate request, "
                            "but the TRAN corridor agent did not return a visual response. "
                            "I did not fall back to a raw transmissibility map because that would be the wrong intent."
                        ),
                        "intent": "tran_multiplier_candidate_unavailable",
                        "ui_blocks": [],
                        "data": {"decision": decision},
                    }

                if isinstance(response, dict):
                    answer = str(response.get("answer") or "")
                    prefix = (
                        "LangGraph Orchestrator routed this as a TRAN multiplier candidate search, "
                        "not as a raw transmissibility map. "
                    )
                    if prefix not in answer:
                        response["answer"] = prefix + answer

                return _lg_v002_add_trace(
                    response=response,
                    shadow=shadow,
                    routed=True,
                    active_route="tran_corridor_visual_agent",
                )

            except Exception as exc:
                response = {
                    "type": "visual_response",
                    "answer": (
                        "LangGraph selected TRAN corridor routing, but the TRAN corridor agent failed. "
                        f"Error: {exc}"
                    ),
                    "intent": "tran_multiplier_candidate_error",
                    "ui_blocks": [],
                    "data": {"error": str(exc), "decision": decision},
                }
                return _lg_v002_add_trace(
                    response=response,
                    shadow=shadow,
                    routed=False,
                    active_route="tran_corridor_visual_agent",
                    error=str(exc),
                )

        # --------------------------------------------------
        # 2) Well profile / time-series
        # --------------------------------------------------
        if confidence == "high" and intent == "well_profile":
            try:
                from app.dynamic_profile_agent import answer_dynamic_profile_question

                response = answer_dynamic_profile_question(normalized)

                if response is None:
                    response = {
                        "type": "visual_response",
                        "answer": (
                            "LangGraph correctly classified this as a well profile/time-series request, "
                            "but the profile agent did not return profile data. "
                            "I did not fall back to a property map because that would be the wrong intent."
                        ),
                        "intent": "well_profile_unavailable",
                        "ui_blocks": [],
                        "data": {"decision": decision},
                    }

                if isinstance(response, dict):
                    answer = str(response.get("answer") or "")
                    prefix = (
                        "LangGraph Orchestrator routed this as a well profile/time-series request, "
                        "not as a property map. "
                    )
                    if prefix not in answer:
                        response["answer"] = prefix + answer

                return _lg_v002_add_trace(
                    response=response,
                    shadow=shadow,
                    routed=True,
                    active_route="dynamic_profile_agent",
                )

            except Exception as exc:
                response = {
                    "type": "visual_response",
                    "answer": (
                        "LangGraph selected well profile routing, but the profile agent failed. "
                        f"Error: {exc}"
                    ),
                    "intent": "well_profile_error",
                    "ui_blocks": [],
                    "data": {"error": str(exc), "decision": decision},
                }
                return _lg_v002_add_trace(
                    response=response,
                    shadow=shadow,
                    routed=False,
                    active_route="dynamic_profile_agent",
                    error=str(exc),
                )

        # --------------------------------------------------
        # 3) RelPerm sensitivity
        # --------------------------------------------------
        if confidence == "high" and intent == "relperm_sensitivity":
            try:
                from app.relperm_sensitivity_agent import answer_relperm_sensitivity_question

                response = answer_relperm_sensitivity_question(normalized)

                if response is None:
                    response = {
                        "type": "visual_response",
                        "answer": (
                            "LangGraph classified this as a relative-permeability sensitivity request, "
                            "but the RelPerm agent did not return a response."
                        ),
                        "intent": "relperm_sensitivity_unavailable",
                        "ui_blocks": [],
                        "data": {"decision": decision},
                    }

                return _lg_v002_add_trace(
                    response=response,
                    shadow=shadow,
                    routed=True,
                    active_route="relperm_sensitivity_agent",
                )

            except Exception as exc:
                response = {
                    "type": "visual_response",
                    "answer": (
                        "LangGraph selected RelPerm sensitivity routing, but the RelPerm agent failed. "
                        f"Error: {exc}"
                    ),
                    "intent": "relperm_sensitivity_error",
                    "ui_blocks": [],
                    "data": {"error": str(exc), "decision": decision},
                }
                return _lg_v002_add_trace(
                    response=response,
                    shadow=shadow,
                    routed=False,
                    active_route="relperm_sensitivity_agent",
                    error=str(exc),
                )

        # --------------------------------------------------
        # 4) Everything else: current working router chain
        # --------------------------------------------------
        response = _answer_question_before_langgraph_active_hook_v002(message)
        return _lg_v002_add_trace(
            response=response,
            shadow=shadow,
            routed=False,
            active_route="existing_router_chain",
        )

    except Exception as exc:
        # Safety fallback: never break the current working chat.
        response = _answer_question_before_langgraph_active_hook_v002(message)
        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["LangGraphOrchestratorActiveV002"] = {
                "mode": "active_error_fallback",
                "routed": False,
                "error": str(exc),
            }
        return response



# ==========================================================
# LANGGRAPH GLOBAL TRAN CANDIDATE HOOK V003
# Must stay at the very end of chat_router.py.
# Handles global TRAN multiplier candidate questions without a specific well.
# ==========================================================

_answer_question_before_langgraph_global_tran_v003 = answer_question


def answer_question(message: str):
    try:
        from app.langgraph_orchestrator import (
            run_langgraph_shadow_orchestrator,
            append_orchestrator_trace_jsonl,
        )

        shadow = run_langgraph_shadow_orchestrator(message)
        append_orchestrator_trace_jsonl(shadow)

        decision = shadow.get("decision") or {}
        intent = decision.get("intent")
        confidence = decision.get("confidence")
        well = decision.get("well")

        if confidence == "high" and intent == "tran_multiplier_candidate" and not well:
            from app.tran_multiplier_candidate_agent import answer_global_tran_multiplier_candidate_question

            response = answer_global_tran_multiplier_candidate_question(message)

            if isinstance(response, dict):
                response.setdefault("agent_trace", {})
                response["agent_trace"]["LangGraphGlobalTRANHookV003"] = {
                    "mode": "active_global_tran_candidates",
                    "decision": decision,
                    "trace": shadow.get("trace"),
                    "routed": True,
                    "active_route": "global_tran_multiplier_candidate_agent",
                    "reason": "Global TRAN multiplier request has no specific well; using candidate ranking instead of asking for a well or showing raw TRAN map.",
                }

            return response

        response = _answer_question_before_langgraph_global_tran_v003(message)

        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["LangGraphGlobalTRANHookV003"] = {
                "mode": "pass_through",
                "decision": decision,
                "routed": False,
            }

        return response

    except Exception as exc:
        response = _answer_question_before_langgraph_global_tran_v003(message)

        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["LangGraphGlobalTRANHookV003"] = {
                "mode": "error_fallback",
                "routed": False,
                "error": str(exc),
            }

        return response



# ==========================================================
# LANGGRAPH ORCHESTRATOR MEMORY FOLLOW-UP V006
# Resolves follow-ups like "show the first one" after a ranked candidate list.
# ==========================================================

_answer_question_before_memory_followup_v006 = answer_question


def _is_candidate_followup_v006(message: str) -> bool:
    q = str(message or "").lower()
    triggers = [
        "show the first", "show first", "open the first", "open first",
        "show the second", "show second", "open the second", "open second",
        "show the third", "show third", "open the third", "open third",
        "show the fourth", "show fourth", "open the fourth", "open fourth",
        "show the fifth", "show fifth", "open the fifth", "open fifth",
        "mostrami il primo", "apri il primo",
        "mostrami il secondo", "apri il secondo",
        "mostrami il terzo", "apri il terzo",
    ]
    return any(t in q for t in triggers)


def answer_question(message: str):
    try:
        if _is_candidate_followup_v006(message):
            from app.orchestrator_memory import load_memory, resolve_ordinal_candidate

            mem = load_memory()
            well = resolve_ordinal_candidate(message)

            if well and mem.get("last_intent") == "global_tran_multiplier_candidates":
                from app.tran_corridor_export_agent import answer_tran_corridor_visual_question

                normalized = f"Show proposed TRAN corridor for {well}"
                response = answer_tran_corridor_visual_question(normalized)

                if isinstance(response, dict):
                    response.setdefault("agent_trace", {})
                    response["agent_trace"]["OrchestratorMemoryFollowUpV006"] = {
                        "mode": "resolved_ranked_candidate_followup",
                        "original_question": message,
                        "resolved_well": well,
                        "normalized_question": normalized,
                        "memory": mem,
                    }

                    answer = str(response.get("answer") or "")
                    prefix = (
                        f"Continuing from the previous ranked TRAN candidate list, "
                        f"I interpreted your follow-up as: {normalized}. "
                    )
                    if prefix not in answer:
                        response["answer"] = prefix + answer

                return response

        return _answer_question_before_memory_followup_v006(message)

    except Exception as exc:
        response = _answer_question_before_memory_followup_v006(message)

        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["OrchestratorMemoryFollowUpV006"] = {
                "mode": "error_fallback",
                "error": str(exc),
            }

        return response



# ==========================================================
# RESERVOIR CRITIC POST-PROCESSOR V008
# Reviews TRAN/RelPerm model-edit responses and adds warnings for conflicting hypotheses.
# It does not change visual blocks or routing.
# ==========================================================

_answer_question_before_reservoir_critic_v008 = answer_question


def answer_question(message: str):
    response = _answer_question_before_reservoir_critic_v008(message)

    try:
        from app.reservoir_critic_agent import review_response_for_model_edit_conflicts

        if isinstance(response, dict):
            response = review_response_for_model_edit_conflicts(message, response)

    except Exception as exc:
        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["ReservoirCriticAgentV008"] = {
                "status": "error_fallback",
                "error": str(exc),
            }

    return response



# ==========================================================
# AGENT COLLABORATION LOGGER V009
# Writes contest-ready multi-agent trace records to logs/agent_collaboration_trace.jsonl.
# Does not change routing, answers, or visual blocks.
# ==========================================================

_answer_question_before_collaboration_logger_v009 = answer_question


def answer_question(message: str):
    response = _answer_question_before_collaboration_logger_v009(message)

    try:
        from app.agent_collaboration_logger import append_collaboration_record

        if isinstance(response, dict):
            append_collaboration_record(message, response)

            response.setdefault("agent_trace", {})
            response["agent_trace"]["AgentCollaborationLoggerV009"] = {
                "status": "logged",
                "log_path": "logs/agent_collaboration_trace.jsonl",
            }

    except Exception as exc:
        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["AgentCollaborationLoggerV009"] = {
                "status": "error_fallback",
                "error": str(exc),
            }

    return response



# ==========================================================
# LANGGRAPH V013 MAIN CHAT INTEGRATION V014
# Uses the real node-based LangGraph orchestrator as the main /api/chat entry
# for safe, validated routes. Falls back to the existing working chain for
# unsupported/diagnostic/passthrough cases.
# ==========================================================

_answer_question_before_langgraph_main_v014 = answer_question


def _lg_v014_is_safe_response(response):
    if not isinstance(response, dict):
        return False

    intent = str(response.get("intent") or "").lower()

    # V013 explicitly says it is not ready for this route.
    if intent in [
        "v013_passthrough_required",
        "v013_specialist_error",
        "v013_specialist_no_response",
    ]:
        return False

    if intent.startswith("v013_"):
        return False

    trace = response.get("agent_trace") or {}
    v013 = trace.get("LangGraphActiveNodesV013") or {}

    if not v013:
        return False

    dispatch = v013.get("dispatch") or {}
    selected_agent = str(dispatch.get("selected_agent") or "")

    # Safe routes already validated.
    safe_agents = {
        "GlobalTRANMultiplierCandidateAgent",
        "TRANCorridorVisualAgent",
        "RelPermSensitivityAgent",
        "DynamicProfileAgent",
        "GenericPlotAgent",
    }

    if selected_agent in safe_agents:
        return True

    return False


def answer_question(message: str):
    try:
        from app.langgraph_orchestrator import run_langgraph_active_orchestrator_v013

        v013_response = run_langgraph_active_orchestrator_v013(message)

        if _lg_v014_is_safe_response(v013_response):
            if isinstance(v013_response, dict):
                v013_response.setdefault("agent_trace", {})
                v013_response["agent_trace"]["LangGraphMainIntegrationV014"] = {
                    "status": "used_v013_response",
                    "reason": "V013 returned a safe validated route.",
                    "decision": (
                        v013_response.get("agent_trace", {})
                        .get("LangGraphActiveNodesV013", {})
                        .get("decision")
                    ),
                    "dispatch": (
                        v013_response.get("agent_trace", {})
                        .get("LangGraphActiveNodesV013", {})
                        .get("dispatch")
                    ),
                }

                # Write contest-ready collaboration log because this wrapper bypasses
                # older logger hooks in the fallback chain.
                try:
                    from app.agent_collaboration_logger import append_collaboration_record
                    append_collaboration_record(message, v013_response)
                    v013_response["agent_trace"]["AgentCollaborationLoggerV009"] = {
                        "status": "logged",
                        "log_path": "logs/agent_collaboration_trace.jsonl",
                        "source": "LangGraphMainIntegrationV014",
                    }
                except Exception as log_exc:
                    v013_response["agent_trace"]["AgentCollaborationLoggerV009"] = {
                        "status": "error_fallback",
                        "error": str(log_exc),
                    }

            return v013_response

        # Fallback for routes not yet migrated to the node graph.
        response = _answer_question_before_langgraph_main_v014(message)

        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["LangGraphMainIntegrationV014"] = {
                "status": "fallback_to_existing_chain",
                "reason": "V013 did not return a safe migrated route.",
                "v013_intent": v013_response.get("intent") if isinstance(v013_response, dict) else None,
                "v013_trace": (
                    v013_response.get("agent_trace", {}).get("LangGraphActiveNodesV013")
                    if isinstance(v013_response, dict)
                    else None
                ),
            }

        return response

    except Exception as exc:
        response = _answer_question_before_langgraph_main_v014(message)

        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["LangGraphMainIntegrationV014"] = {
                "status": "error_fallback_to_existing_chain",
                "error": str(exc),
            }

        return response




# === AGENT COLLABORATION VISIBILITY WRAPPER V001 ===
# Final non-invasive wrapper.
# It preserves the existing answer_question() behaviour and only enriches
# the returned JSON with common agent_trace, interaction_edges and
# collaboration_summary fields for evaluation and auditability.

_answer_question_before_agent_visibility_v001 = answer_question

def answer_question(message: str):
    response = _answer_question_before_agent_visibility_v001(message)
    try:
        from app.agent_visibility import enhance_agent_visibility
        response = enhance_agent_visibility(message, response)
    except Exception as _agent_visibility_exc:
        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["AgentVisibilityWrapperV001"] = {
                "status": "error_fallback",
                "error": str(_agent_visibility_exc),
            }
        return response
    return response

# ==========================================================
# V415 FINAL DIAGNOSTIC PRIORITY WRAPPER
# This must remain the last answer_question definition.
#
# Purpose:
# All WCT/GOR/water/gas/oil/BHP + bias/cluster/mismatch/HM
# diagnostic questions must reach the agentic reasoning path
# before deterministic property-map/property-distribution shortcuts.
# ==========================================================



def _is_profile_or_production_plot_request_v424(message: str) -> bool:
    """Protect legacy interactive well profile/production plot routing.

    Examples that should bypass the final diagnostic cluster guard:
    - plot HW-25 water production
    - show HW-25 water rate
    - HW-25 gas production profile
    - show BHP profile for HW-25
    """
    msg = str(message or "").lower().replace("_", " ").replace("-", " ")
    msg = " ".join(msg.split())

    has_well = bool(re.search(r"\bhw\s*\d+\b", msg))

    has_profile_or_production = any(x in msg for x in [
        "production", "prod", "rate", "profile", "plot",
        "water production", "gas production", "oil production",
        "water rate", "gas rate", "oil rate",
        "bhp profile", "pressure profile",
        "simulated vs observed", "observed vs simulated",
    ])

    # Keep true cluster/bias diagnostic requests in the diagnostic path.
    has_cluster_diagnostic = any(x in msg for x in [
        "bias cluster", "cluster map", "diagnostic cluster",
        "mismatch cluster", "pattern map",
    ])

    return bool(has_well and has_profile_or_production and not has_cluster_diagnostic)


_answer_question_before_final_diagnostic_priority_v415 = answer_question

def _is_holistic_diagnostic_query_v415(message: str) -> bool:
    msg = str(message or "").lower().replace("_", " ").replace("-", " ")
    msg = " ".join(msg.split())

    has_reservoir_signal = any(x in msg for x in [
        "wct", "water cut", "water",
        "gas", "gor", "gas oil ratio",
        "oil", "bhp", "pressure", "rate", "profile",
    ])

    has_diagnostic_intent = any(x in msg for x in [
        "bias", "cluster", "mismatch", "driver", "drivers",
        "weak", "weakest", "diagnostic", "diagnose",
        "history match", "history matching", "hm",
        "pattern", "evidence", "review first",
    ])

    return bool(has_reservoir_signal and has_diagnostic_intent)


def _answer_holistic_diagnostic_v415(message: str):
    response = None
    route_used = None
    error_text = None

    # V420: if the diagnostic request explicitly asks for a WCT / water-cut
    # bias cluster map, use the existing visual map builder first.
    # This keeps the LangGraph/diagnostic priority guard, but still returns
    # dashboard-renderable ui_blocks instead of text only.
    try:
        q_v420 = str(message or "").lower().replace("_", " ").replace("-", " ")
        wants_wct_signal_v420 = ("wct" in q_v420) or ("water cut" in q_v420) or ("watercut" in q_v420)
        wants_bias_cluster_v420 = ("bias" in q_v420) or ("cluster" in q_v420) or ("mismatch" in q_v420)
        wants_visual_v420 = ("map" in q_v420) or ("view" in q_v420) or ("show" in q_v420) or ("visual" in q_v420)

        if wants_wct_signal_v420 and wants_bias_cluster_v420 and wants_visual_v420:
            for builder_name_v420 in ["_build_wct_bias_response_v37", "_build_wct_bias_response_v36"]:
                builder_v420 = globals().get(builder_name_v420)
                if callable(builder_v420):
                    try:
                        visual_response_v420 = builder_v420(message)

                        if isinstance(visual_response_v420, dict):
                            visual_response_v420.setdefault("type", "visual_response")
                            visual_response_v420["intent"] = "wct_bias_cluster_map"
                            visual_response_v420.setdefault("agent_trace", {})
                            visual_response_v420["agent_trace"]["WCTBiasVisualRouterV420"] = {
                                "route": builder_name_v420,
                                "reason": "WCT/water-cut bias cluster diagnostic request requires a dashboard visual map, not text-only reasoning.",
                                "called_from": "FinalDiagnosticPriorityGuardV415",
                            }
                            visual_response_v420.setdefault("interaction_edges", [])
                            visual_response_v420["interaction_edges"].append({
                                "from": "FinalDiagnosticPriorityGuardV415",
                                "to": "WCTBiasVisualRouterV420",
                                "reason": "Diagnostic request included WCT bias cluster map visualization.",
                            })
                            return visual_response_v420

                    except Exception as exc_v420:
                        error_text = str(exc_v420)

    except Exception as exc_v420_outer:
        error_text = str(exc_v420_outer)


    # Preferred: Compass Reservoir Brain direct path if available.
    try:
        crb = globals().get("_crb_answer")
        if callable(crb):
            response = crb(message)
            route_used = "CompassReservoirBrain"
    except Exception as exc:
        error_text = str(exc)

    # Fallback: active LangGraph orchestrator.
    if response is None:
        try:
            from app.langgraph_orchestrator import run_langgraph_active_orchestrator_v013
            response = run_langgraph_active_orchestrator_v013(message)
            route_used = "LangGraphActiveOrchestratorV013"
        except Exception as exc:
            error_text = str(exc)

    # Last fallback: deterministic safe diagnostic answer, but never property-map fallback.
    if response is None:
        response = {
            "type": "visual_response",
            "intent": "holistic_reservoir_diagnostic",
            "answer": (
                "This is a reservoir history-match diagnostic request, not a physical property-map request. "
                "The question should be evaluated across water/WCT, gas/GOR/gas rate, oil rate and BHP behaviour. "
                "The next engineering review should identify the weakest wells, compare mismatch drivers, and check whether "
                "the pattern points first to connectivity/transmissibility, relative permeability, or pressure-support issues."
            ),
            "ui_blocks": [],
        }
        route_used = "DeterministicDiagnosticFallbackV415"

    if not isinstance(response, dict):
        response = {
            "type": "visual_response",
            "intent": "holistic_reservoir_diagnostic",
            "answer": str(response),
            "ui_blocks": [],
        }

    response.setdefault("intent", "holistic_reservoir_diagnostic")
    response.setdefault("agent_trace", {})
    response["agent_trace"]["FinalDiagnosticPriorityGuardV415"] = {
        "route": route_used,
        "reason": (
            "WCT/GOR/water/gas/oil/BHP bias/cluster/history-match diagnostic query "
            "has priority over deterministic property-map/property-distribution shortcuts."
        ),
        "bypassed": [
            "property_map_shortcut",
            "property_distribution_shortcut",
            "generic_plot_shortcut",
        ],
        "error": error_text,
    }

    response.setdefault("interaction_edges", [])
    response["interaction_edges"].append({
        "from": "FinalDiagnosticPriorityGuardV415",
        "to": route_used,
        "reason": "Diagnostic intent routed before deterministic property visual shortcuts.",
    })

    return response


def answer_question(message: str):
    # V424: do not steal existing interactive profile/production plot requests.
    if _is_profile_or_production_plot_request_v424(message):
        return _answer_question_before_final_diagnostic_priority_v415(message)

    if _is_holistic_diagnostic_query_v415(message):
        try:
            q_v421 = str(message or "").lower().replace("_", " ").replace("-", " ")
            wants_wct_v421 = ("wct" in q_v421) or ("water cut" in q_v421) or ("watercut" in q_v421)
            wants_bias_cluster_v421 = ("bias" in q_v421) or ("cluster" in q_v421) or ("mismatch" in q_v421)
            wants_map_v421 = ("map" in q_v421) or ("view" in q_v421) or ("show" in q_v421) or ("visual" in q_v421)

            if wants_wct_v421 and wants_bias_cluster_v421 and wants_map_v421:
                for builder_name_v421 in ["_build_wct_bias_response_v37", "_build_wct_bias_response_v36"]:
                    builder_v421 = globals().get(builder_name_v421)
                    if callable(builder_v421):
                        response_v421 = builder_v421(message)
                        if isinstance(response_v421, dict):
                            response_v421.setdefault("type", "visual_response")
                            response_v421["intent"] = "wct_bias_cluster_map"
                            response_v421.setdefault("ui_blocks", response_v421.get("ui_blocks") or [])
                            response_v421.setdefault("agent_trace", {})
                            response_v421["agent_trace"]["WCTBiasVisualRouterV421"] = {
                                "route": builder_name_v421,
                                "reason": "Explicit WCT bias cluster map request routed to the visual WCT builder."
                            }
                            response_v421.setdefault("interaction_edges", [])
                            response_v421["interaction_edges"].append({
                                "from": "FinalDiagnosticPriorityGuardV415",
                                "to": "WCTBiasVisualRouterV421",
                                "reason": "User explicitly asked for WCT bias cluster map visualization."
                            })
                            return response_v421
        except Exception:
            pass

        return _answer_holistic_diagnostic_v415(message)

    return _answer_question_before_final_diagnostic_priority_v415(message)

# END V415 FINAL DIAGNOSTIC PRIORITY WRAPPER

# ==========================================================
# V427 SHOW PROFILE NORMALIZER
# This must stay after the final diagnostic wrappers.
#
# Problem fixed:
# "plot HW-25 water production" correctly reaches DynamicProfileAgent,
# but "show me HW-25 water production" may be captured by a static visual path.
#
# Rule:
# If the user asks to show/display a specific well profile or production/rate
# curve, rewrite the intent as "plot ..." and reuse the existing dynamic
# profile route. Do not affect cluster maps or physical property maps.
# ==========================================================

_answer_question_before_show_profile_normalizer_v427 = answer_question

def _is_show_profile_request_v427(message: str) -> bool:
    msg = str(message or "").lower().replace("_", " ").replace("-", " ")
    msg = " ".join(msg.split())

    has_show_word = any(x in msg for x in [
        "show me", "show", "display", "open", "visualize", "visualise"
    ])

    has_well = bool(re.search(r"\bhw\s*\d+[a-z]?\b", msg))

    has_profile_variable = any(x in msg for x in [
        "oil production", "oil rate", "wopr", "oil profile",
        "gas production", "gas rate", "wgpr", "gor", "gas profile",
        "water production", "water rate", "wwpr", "water cut", "wct", "wwct", "water profile",
        "bhp", "pressure profile", "well pressure", "wbhp",
        "production profile", "rate profile", "simulated vs observed", "observed vs simulated",
    ])

    # Do not steal diagnostic maps or property maps.
    has_cluster_or_map_diagnostic = any(x in msg for x in [
        "bias cluster", "cluster map", "diagnostic cluster", "mismatch cluster",
        "pattern map", "wct bias", "gas bias", "pressure bias",
    ])

    has_physical_property_map = any(x in msg for x in [
        "poro map", "porosity map", "perm map", "permeability map",
        "swat map", "pressure map", "property map", "fipnum map", "satnum map",
    ])

    return bool(
        has_show_word
        and has_well
        and has_profile_variable
        and not has_cluster_or_map_diagnostic
        and not has_physical_property_map
    )


def _rewrite_show_profile_to_plot_v427(message: str) -> str:
    raw = str(message or "").strip()

    # Keep the rest of the wording, but force the known working dynamic-profile verb.
    cleaned = re.sub(r"^\s*show\s+me\s+", "", raw, flags=re.I)
    cleaned = re.sub(r"^\s*show\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^\s*display\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^\s*open\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^\s*visuali[sz]e\s+", "", cleaned, flags=re.I)

    return "Plot " + cleaned


def answer_question(message: str):
    if _is_show_profile_request_v427(message):
        rewritten = _rewrite_show_profile_to_plot_v427(message)

        response = _answer_question_before_show_profile_normalizer_v427(rewritten)

        if isinstance(response, dict):
            response.setdefault("agent_trace", {})
            response["agent_trace"]["ShowProfileNormalizerV427"] = {
                "route": "DynamicProfileAgent via rewritten plot request",
                "original_message": str(message or ""),
                "rewritten_message": rewritten,
                "reason": "Show/display well profile requests should use the same dynamic profile path as plot requests.",
            }

            response.setdefault("interaction_edges", [])
            response["interaction_edges"].append({
                "from": "ShowProfileNormalizerV427",
                "to": "DynamicProfileAgent",
                "reason": "Normalized show/display profile wording to plot wording.",
            })

        return response

    return _answer_question_before_show_profile_normalizer_v427(message)

# END V427 SHOW PROFILE NORMALIZER

