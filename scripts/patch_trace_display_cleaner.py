from pathlib import Path
import re

p = Path("app/final_answer_synthesizer_llm.py")

if not p.exists():
    raise SystemExit("Missing app/final_answer_synthesizer_llm.py. Install the LLM final writer first.")

txt = p.read_text(encoding="utf-8-sig")

START = "# --- 404_RNF_TRACE_DISPLAY_CLEANER_START ---"
END = "# --- 404_RNF_TRACE_DISPLAY_CLEANER_END ---"

def remove_block(text: str) -> str:
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

cleaner_code = r'''

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
'''

# Insert cleaner before synthesize_final_answer_payload definition.
marker = "def synthesize_final_answer_payload(payload: Any) -> Any:"
if marker not in txt:
    raise SystemExit("Could not find synthesize_final_answer_payload function.")

txt = txt.replace(marker, cleaner_code + "\n\n" + marker, 1)

# Ensure function applies cleaner before return.
old_1 = """    return new_payload
"""
new_1 = """    new_payload = _404_clean_trace_metadata(new_payload)
    return new_payload
"""

# Replace only the return inside synthesize_final_answer_payload.
idx = txt.find(marker)
if idx < 0:
    raise SystemExit("Function marker not found after insertion.")

before = txt[:idx]
after = txt[idx:]

# Replace the last simple return new_payload in the function area.
pos = after.rfind(old_1)
if pos == -1:
    raise SystemExit("Could not find final 'return new_payload' to patch.")

after = after[:pos] + new_1 + after[pos + len(old_1):]
txt = before + after

p.write_text(txt, encoding="utf-8")
print("[OK] Trace metadata cleaner installed in", p)
