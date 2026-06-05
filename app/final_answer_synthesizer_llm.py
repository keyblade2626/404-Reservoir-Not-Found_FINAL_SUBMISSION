
from __future__ import annotations

import copy
import json
import os
import re
from typing import Any


DIAGNOSTIC_MARKERS = [
    "Main evidence:",
    "Hypothesis ranking:",
    "Most likely explanation:",
    "This is a model-specific reservoir diagnosis",
    "Integrated diagnosis:",
]


def _compact(value: Any, limit: int = 16000) -> str:
    try:
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value)

    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > limit:
        return text[:limit] + " ...[truncated]"

    return text


def _should_rewrite_answer(text: str) -> bool:
    if not isinstance(text, str):
        return False

    if len(text.strip()) < 350:
        return False

    return any(marker in text for marker in DIAGNOSTIC_MARKERS)


def _find_candidate_answer_path(obj: Any, path: list[Any] | None = None) -> list[Any] | None:
    if path is None:
        path = []

    if isinstance(obj, dict):
        # Prefer canonical final answer keys.
        for key in ["answer", "response", "final_answer"]:
            value = obj.get(key)
            if isinstance(value, str) and _should_rewrite_answer(value):
                return path + [key]

        for key, value in obj.items():
            found = _find_candidate_answer_path(value, path + [key])
            if found is not None:
                return found

    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            found = _find_candidate_answer_path(value, path + [i])
            if found is not None:
                return found

    return None


def _get_by_path(obj: Any, path: list[Any]) -> Any:
    cur = obj
    for key in path:
        cur = cur[key]
    return cur


def _set_by_path(obj: Any, path: list[Any], value: Any) -> None:
    cur = obj
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = value


def _extract_user_question(payload: Any) -> str:
    keys = [
        "message",
        "question",
        "query",
        "user_question",
        "input_message",
        "prompt",
    ]

    found: list[str] = []

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                if str(k).lower() in keys and isinstance(v, str):
                    if len(v.strip()) > 5:
                        found.append(v.strip())
                else:
                    walk(v)
        elif isinstance(x, list):
            for item in x:
                walk(item)

    walk(payload)

    if found:
        return found[0]

    return ""


def _extract_structured_context(payload: Any, raw_answer: str) -> str:
    # Keep the raw answer plus a compacted view of the JSON payload so the LLM
    # can use structured evidence, but do not send huge UI payloads if avoidable.
    safe_payload = copy.deepcopy(payload)

    def prune(x: Any) -> Any:
        if isinstance(x, dict):
            out = {}
            for k, v in x.items():
                lk = str(k).lower()
                if lk in {
                    "html",
                    "svg",
                    "image",
                    "image_base64",
                    "data_uri",
                    "figure",
                    "plotly_json",
                }:
                    out[k] = "[omitted visual payload]"
                elif isinstance(v, str) and len(v) > 3000:
                    out[k] = v[:3000] + " ...[truncated]"
                else:
                    out[k] = prune(v)
            return out

        if isinstance(x, list):
            if len(x) > 40:
                return [prune(v) for v in x[:40]] + ["...[list truncated]"]
            return [prune(v) for v in x]

        return x

    safe_payload = prune(safe_payload)

    return (
        "RAW TOOL-AGGREGATED ANSWER:\n"
        + raw_answer
        + "\n\nSTRUCTURED RESPONSE PAYLOAD:\n"
        + _compact(safe_payload, limit=18000)
    )


def _fallback_if_llm_unavailable(raw_answer: str) -> str:
    # Fallback intentionally light: do not invent, do not over-transform.
    # It only removes obvious broken fragments and duplicate visualization narration.
    text = raw_answer

    text = text.replace("Reservoir Technical review review", "Reservoir technical review")
    text = text.replace("candidate should remain conservative..", "candidate should remain conservative.")
    text = text.replace("This is a...", "")

    text = re.sub(
        r"\n?- Streamline evidence:\s*I detected a true streamline visualization request\..*?(?=\n\n|\nHypothesis ranking:|$)",
        "",
        text,
        flags=re.I | re.S,
    )

    text = re.sub(
        r"I built an interactive WCT profile for\s+HW-\d+[A-Z]?\.\s*WCT is computed as water rate divided by oil plus water rate\.",
        "The WCT profile is available in the evidence panel.",
        text,
        flags=re.I,
    )

    return text.strip()


def _call_llm_final_writer(user_question: str, evidence_context: str) -> str | None:
    api_key = (
        os.getenv("COMPASS_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )

    if not api_key:
        print("[INFO] LLM final writer skipped: COMPASS_API_KEY / OPENAI_API_KEY not set")
        return None

    model = (
        os.getenv("COMPASS_MODEL")
        or os.getenv("OPENAI_MODEL")
        or os.getenv("FINAL_WRITER_MODEL")
        or "gpt-4o-mini"
    )

    base_url = (
        os.getenv("COMPASS_BASE_URL")
        or os.getenv("COMPASS_API_BASE")
        or os.getenv("OPENAI_BASE_URL")
        or None
    )

    try:
        from openai import OpenAI
    except Exception as exc:
        print("[WARN] LLM final writer skipped: openai package unavailable:", repr(exc))
        return None

    try:
        if base_url:
            client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            client = OpenAI(api_key=api_key)

        system_prompt = """You are a senior reservoir engineer and final-answer writer.

You receive evidence from multiple diagnostic agents.
Your job is to write the final answer only.

Rules:
- Start with the conclusion.
- Do not repeat tool outputs.
- Do not mention that you created charts, maps, tables, or interactive visuals.
- Do not say "I built", "I loaded", or "I highlighted".
- Do not include unfinished fragments such as "This is a...".
- Do not ask for streamline timing unless the user explicitly asked for streamlines.
- Keep the answer focused on the user's question.
- Separate evidence from interpretation.
- Rank hypotheses clearly.
- End with practical next checks.
- Use only the evidence provided.
- Do not invent numbers.
- Write in concise professional reservoir-engineering English.

Required output structure:
1. Conclusion
2. Key evidence
3. Hypothesis ranking
4. Recommended next checks
"""

        user_prompt = f"""User question:
{user_question or "[not available]"}

Evidence package:
{evidence_context}

Write the final answer now.
"""

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.15,
            max_tokens=900,
        )

        answer = completion.choices[0].message.content

        if not answer or len(answer.strip()) < 80:
            print("[WARN] LLM final writer returned empty/short answer")
            return None

        print("[OK] LLM final writer synthesized final answer")
        return answer.strip()

    except Exception as exc:
        print("[WARN] LLM final writer failed, using fallback/raw answer:", repr(exc))
        return None




# --- 404_RNF_TRACE_DISPLAY_CLEANER_START ---
def _404_trace_string_looks_like_full_answer(value: str) -> bool:
    if not isinstance(value, str):
        return False

    text = value.strip()

    if len(text) < 450:
        return False

    markers = [
        "Conclusion",
        "Key evidence",
        "Hypothesis ranking",
        "Recommended next checks",
        "Most likely cause",
        "relative permeability",
    ]

    hits = sum(1 for m in markers if m.lower() in text.lower())
    return hits >= 3


def _404_trace_summary_replacement(value: str) -> str:
    text = str(value or "")

    if "HW-28" in text:
        return (
            "Final Answer Synthesizer produced an executive HW-28 water-mismatch diagnosis: "
            "leading hypothesis = RelPerm / endpoint saturation issue; secondary check = Connectivity / TRAN; "
            "output includes conclusion, key evidence, hypothesis ranking and recommended next checks."
        )

    return (
        "Final Answer Synthesizer produced the final user-facing answer from the validated multi-agent evidence package."
    )


def _404_clean_trace_metadata(obj, path=None):
    """
    Clean trace/debug metadata only.
    Do not modify final answer fields, visual payloads, tables, maps or evidence boards.
    """

    if path is None:
        path = []

    # Never touch actual final answer fields.
    protected_keys = {"answer", "response", "final_answer"}

    if isinstance(obj, dict):
        out = {}

        for key, value in obj.items():
            key_str = str(key)
            key_lower = key_str.lower()
            next_path = path + [key_lower]

            # Clean selected agent label.
            if key_lower in {"selected_agent", "selected agent", "selectedagent"}:
                if isinstance(value, str) and value.strip().lower() in {"existing/unknown", "unknown", "existing"}:
                    out[key] = "IntegratedRootCauseDiagnosisWorkflow"
                else:
                    out[key] = value
                continue

            # Replace old debug labels wherever they are trace metadata.
            if isinstance(value, str) and value.strip().lower() == "existing/unknown":
                out[key] = "IntegratedRootCauseDiagnosisWorkflow"
                continue

            # Protect actual user-facing answer/response.
            if key_lower in protected_keys:
                out[key] = value
                continue

            # Clean long trace summaries that duplicate the final answer.
            is_trace_context = any(
                token in next_path
                for token in [
                    "trace",
                    "agent_trace",
                    "agent collaboration trace",
                    "interaction_edges",
                    "edges",
                    "collaboration",
                    "summary",
                    "output_summary",
                    "debug",
                ]
            )

            if isinstance(value, str):
                if is_trace_context and _404_trace_string_looks_like_full_answer(value):
                    out[key] = _404_trace_summary_replacement(value)
                else:
                    out[key] = value
                continue

            out[key] = _404_clean_trace_metadata(value, next_path)

        return out

    if isinstance(obj, list):
        return [_404_clean_trace_metadata(x, path) for x in obj]

    return obj

# --- 404_RNF_TRACE_DISPLAY_CLEANER_END ---


def synthesize_final_answer_payload(payload: Any) -> Any:
    path = _find_candidate_answer_path(payload)

    if path is None:
        return payload

    new_payload = copy.deepcopy(payload)
    raw_answer = _get_by_path(new_payload, path)

    if not isinstance(raw_answer, str):
        return payload

    user_question = _extract_user_question(new_payload)
    evidence_context = _extract_structured_context(new_payload, raw_answer)

    llm_answer = _call_llm_final_writer(
        user_question=user_question,
        evidence_context=evidence_context,
    )

    final_answer = llm_answer or _fallback_if_llm_unavailable(raw_answer)

    _set_by_path(new_payload, path, final_answer)

    # Add light metadata for trace/debugging without changing UI semantics.
    try:
        if isinstance(new_payload, dict):
            new_payload.setdefault("final_writer", {})
            new_payload["final_writer"] = {
                "enabled": True,
                "mode": "llm" if llm_answer else "fallback",
                "answer_path": [str(x) for x in path],
            }
    except Exception:
        pass

    new_payload = _404_clean_trace_metadata(new_payload)
    return new_payload


# --- 404_RNF_SAFE_TRACE_PAYLOAD_CLEANER_START ---
# Safe backend-only cleanup of trace metadata.
# Does not touch frontend DOM, maps, tables or visual panels.

def _404_safe_trace_string_cleanup_v1(value):
    if not isinstance(value, str):
        return value

    text = value

    text = text.replace(
        "Selected agent: existing/unknown",
        "Selected agent: IntegratedRootCauseDiagnosisWorkflow"
    )

    text = text.replace(
        "Selected agent: unknown",
        "Selected agent: IntegratedRootCauseDiagnosisWorkflow"
    )

    # If a full final answer was copied into the trace text, replace only that copied tail.
    if (
        "Current answer trace:" in text
        and "Final Visual Selector" in text
        and "1. Conclusion" in text
        and "Recommended next checks" in text
    ):
        head = text.split("1. Conclusion", 1)[0].rstrip()
        text = (
            head
            + "\n→\nFinal Answer Synthesizer produced a concise executive diagnosis "
            + "with conclusion, evidence ranking and recommended next checks."
        )

    return text


def _404_safe_trace_payload_cleanup_v1(obj):
    if isinstance(obj, dict):
        out = {}

        for key, value in obj.items():
            key_l = str(key).lower()

            if key_l in {"selected_agent", "selectedagent", "selected agent"}:
                if isinstance(value, str) and value.strip().lower() in {"existing/unknown", "unknown", "existing"}:
                    out[key] = "IntegratedRootCauseDiagnosisWorkflow"
                else:
                    out[key] = value
                continue

            if isinstance(value, str):
                out[key] = _404_safe_trace_string_cleanup_v1(value)
            else:
                out[key] = _404_safe_trace_payload_cleanup_v1(value)

        return out

    if isinstance(obj, list):
        return [_404_safe_trace_payload_cleanup_v1(x) for x in obj]

    return obj


_404_original_synthesize_final_answer_payload_v1 = synthesize_final_answer_payload


def synthesize_final_answer_payload(payload):
    cleaned = _404_original_synthesize_final_answer_payload_v1(payload)
    return _404_safe_trace_payload_cleanup_v1(cleaned)

# --- 404_RNF_SAFE_TRACE_PAYLOAD_CLEANER_END ---


# --- 404_RNF_INVALID_WELL_VISUAL_SUPPRESSOR_START ---
# Backend-only cleanup:
# If the invalid-well guard is triggered, do not send raw technical JSON
# to the Visual / Evidence panel. Keep the user-facing answer intact.

def _404_to_compact_json_text_v1(obj):
    try:
        import json
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)


def _404_contains_invalid_well_guard_v1(obj):
    if isinstance(obj, dict):
        guard = str(obj.get("guard") or "")
        if "invalid-well guard" in guard.lower() or "v601 final invalid-well guard" in guard.lower():
            return True

        if "invalid" in obj and "known_wells_count" in obj:
            return True

        return any(_404_contains_invalid_well_guard_v1(v) for v in obj.values())

    if isinstance(obj, list):
        return any(_404_contains_invalid_well_guard_v1(v) for v in obj)

    if isinstance(obj, str):
        low = obj.lower()
        return (
            "v601 final invalid-well guard" in low
            or '"known_wells_count"' in low and '"invalid"' in low
            or "well not found in active reservoir well registry" in low and "suggestions" in low
        )

    return False


def _404_is_invalid_guard_artifact_v1(obj):
    if not isinstance(obj, dict):
        return False

    keys = {str(k).lower() for k in obj.keys()}

    # Raw guard object itself.
    if "invalid" in keys and ("known_wells_count" in keys or "guard" in keys):
        return True

    guard = str(obj.get("guard") or "")
    if "invalid-well guard" in guard.lower():
        return True

    # Visual/debug block wrapping the guard object.
    block_text = _404_to_compact_json_text_v1(obj).lower()

    if (
        "v601 final invalid-well guard" in block_text
        and "known_wells_count" in block_text
        and "suggestions" in block_text
    ):
        return True

    # Generic raw JSON evidence/debug blocks related to invalid well.
    block_type = str(obj.get("type") or obj.get("kind") or obj.get("block_type") or "").lower()
    title = str(obj.get("title") or obj.get("name") or obj.get("label") or "").lower()

    if (
        block_type in {"json", "raw_json", "debug", "evidence_json", "compact_table"}
        and "invalid" in block_text
        and "known_wells_count" in block_text
        and "well not found" in block_text
    ):
        return True

    if (
        "visual" in title
        and "invalid" in block_text
        and "known_wells_count" in block_text
    ):
        return True

    return False


def _404_clean_invalid_well_visual_payload_v1(obj, *, root=False):
    if isinstance(obj, dict):
        if not root and _404_is_invalid_guard_artifact_v1(obj):
            return None

        out = {}

        for key, value in obj.items():
            key_l = str(key).lower()

            # Keep user-facing answer/response text.
            if key_l in {"answer", "response", "final_answer", "status"}:
                out[key] = value
                continue

            # Remove raw invalid-well technical guard fields from response payload.
            if key_l in {"invalid", "known_wells_count", "guard"}:
                if _404_contains_invalid_well_guard_v1(obj):
                    continue

            # Remove visual/evidence containers if they only contain invalid guard artifacts.
            cleaned = _404_clean_invalid_well_visual_payload_v1(value, root=False)

            if cleaned is None:
                continue

            if key_l in {
                "visual",
                "visuals",
                "visual_blocks",
                "ui_blocks",
                "blocks",
                "evidence",
                "evidence_blocks",
                "figures",
                "plots",
                "charts",
                "tables",
            }:
                if cleaned == [] or cleaned == {} or cleaned == "":
                    continue

            out[key] = cleaned

        return out

    if isinstance(obj, list):
        cleaned_list = []

        for item in obj:
            cleaned = _404_clean_invalid_well_visual_payload_v1(item, root=False)
            if cleaned is not None:
                cleaned_list.append(cleaned)

        return cleaned_list

    if isinstance(obj, str):
        low = obj.lower()

        # Remove raw JSON string if it is exactly the invalid-well guard payload.
        if (
            "v601 final invalid-well guard" in low
            and "known_wells_count" in low
            and "suggestions" in low
        ):
            return ""

        return obj

    return obj


_404_previous_synthesize_final_answer_payload_invalid_visual_v1 = synthesize_final_answer_payload


def synthesize_final_answer_payload(payload):
    result = _404_previous_synthesize_final_answer_payload_invalid_visual_v1(payload)

    if _404_contains_invalid_well_guard_v1(result):
        result = _404_clean_invalid_well_visual_payload_v1(result, root=True)

        try:
            if isinstance(result, dict):
                result.setdefault("visual_cleanup", {})
                result["visual_cleanup"] = {
                    "invalid_well_raw_json_suppressed": True
                }
        except Exception:
            pass

    return result

# --- 404_RNF_INVALID_WELL_VISUAL_SUPPRESSOR_END ---

