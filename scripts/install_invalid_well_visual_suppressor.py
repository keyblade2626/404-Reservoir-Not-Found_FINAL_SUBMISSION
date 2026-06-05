from pathlib import Path

p = Path("app/final_answer_synthesizer_llm.py")

if not p.exists():
    raise SystemExit("Missing app/final_answer_synthesizer_llm.py. Install LLM final writer first.")

txt = p.read_text(encoding="utf-8-sig")

START = "# --- 404_RNF_INVALID_WELL_VISUAL_SUPPRESSOR_START ---"
END = "# --- 404_RNF_INVALID_WELL_VISUAL_SUPPRESSOR_END ---"

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

patch = r'''

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
'''

txt = txt.rstrip() + "\n" + patch + "\n"

p.write_text(txt, encoding="utf-8")

print("[OK] Invalid-well visual suppressor installed in", p)
