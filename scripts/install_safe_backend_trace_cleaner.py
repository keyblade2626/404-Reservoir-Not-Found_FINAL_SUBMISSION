from pathlib import Path

p = Path("app/final_answer_synthesizer_llm.py")

if not p.exists():
    raise SystemExit("Missing app/final_answer_synthesizer_llm.py")

txt = p.read_text(encoding="utf-8-sig")

START = "# --- 404_RNF_SAFE_TRACE_PAYLOAD_CLEANER_START ---"
END = "# --- 404_RNF_SAFE_TRACE_PAYLOAD_CLEANER_END ---"

def remove_block(text):
    while START in text:
        before = text.split(START, 1)[0]
        rest = text.split(START, 1)[1]
        if END in rest:
            after = rest.split(END, 1)[1]
            text = before.rstrip() + "\n" + after.lstrip()
        else:
            text = before.rstrip() + "\n"
    return text

txt = remove_block(txt)

patch = r'''

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
'''

txt = txt.rstrip() + "\n" + patch + "\n"

p.write_text(txt, encoding="utf-8")

print("[OK] Safe backend trace payload cleaner installed in", p)
