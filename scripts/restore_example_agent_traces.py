from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(".").resolve()
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

summary_path = LOGS / "official_examples_interaction_summary.json"

def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default

def write_json_no_bom(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

def summarize(value, max_len=1200):
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            value = str(value)
    value = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    if len(value) > max_len:
        return value[:max_len - 3] + "..."
    return value

summary = load_json(summary_path, {})
examples = summary.get("examples", [])

if not examples:
    raise SystemExit("official_examples_interaction_summary.json has no examples")

for ex in examples:
    name = ex.get("example")
    if not name:
        continue

    idx = name.replace("example_", "")
    input_path = ROOT / "input_examples" / f"example_{idx}.json"
    output_path = ROOT / "output_examples" / f"example_{idx}_output.json"
    trace_path = LOGS / f"example_{idx}_agent_trace.json"

    input_payload = load_json(input_path, {})
    output_payload = load_json(output_path, {})

    output = output_payload.get("output", output_payload)
    raw_response = output_payload.get("raw_response", output.get("raw_response", {}))

    # Try all known locations used by your run.py outputs.
    agent_trace = (
        output.get("agent_trace")
        or raw_response.get("agent_trace")
        or output_payload.get("agent_trace")
        or {}
    )

    interaction_edges = (
        output.get("interaction_edges")
        or raw_response.get("interaction_edges")
        or output_payload.get("interaction_edges")
        or []
    )

    collaboration_summary = (
        output.get("collaboration_summary")
        or raw_response.get("collaboration_summary")
        or ex.get("collaboration_summary")
        or {}
    )

    answer = (
        output.get("answer")
        or raw_response.get("answer")
        or output_payload.get("answer")
        or ex.get("answer_preview")
        or ""
    )

    # If a previous rich trace exists for example_4, preserve its useful fields but normalize encoding.
    existing = load_json(trace_path, {}) if trace_path.exists() else {}

    trace_doc = {
        "log_type": existing.get("log_type", "official_example_agent_trace"),
        "example": name,
        "purpose": ex.get("purpose"),
        "expected_mode": ex.get("expected_mode"),
        "status": ex.get("status", output_payload.get("status", "success")),
        "pass": ex.get("pass", True),
        "type": ex.get("type", output.get("type")),
        "task_type": ex.get("task_type", output.get("task_type") or output.get("intent")),
        "input_message": ex.get("input_message") or input_payload.get("message") or input_payload.get("question") or summarize(input_payload),
        "agent_count": ex.get("agent_count"),
        "interaction_edge_count": ex.get("interaction_edge_count") or len(interaction_edges),
        "tools_called": ex.get("tools_called", []),
        "tool_count": ex.get("tool_count", len(ex.get("tools_called", []))),
        "ui_block_types": ex.get("ui_block_types", output.get("ui_block_types", [])),
        "collaboration_summary": collaboration_summary,
        "agent_trace": agent_trace,
        "interaction_edges": interaction_edges,
        "answer_preview": ex.get("answer_preview") or summarize(answer),
        "strengths": ex.get("strengths", []),
        "red_flags": ex.get("red_flags", []),
        "output_file": ex.get("output_file") or f"output_examples\\example_{idx}_output.json",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_files": {
            "input": str(input_path).replace("\\", "/"),
            "output": str(output_path).replace("\\", "/"),
            "official_summary": str(summary_path).replace("\\", "/"),
        },
        "raw_output_reference": {
            "status": output_payload.get("status"),
            "output_type": output.get("type"),
            "task_type": output.get("task_type") or output.get("intent"),
        },
    }

    # Preserve explicit guard fields for example_4 if they existed.
    for key in [
        "requested_well",
        "guard_detected",
        "safe_fallback",
        "silent_substitution_avoided",
        "valid_well_suggestions",
        "raw_output",
    ]:
        if key in existing:
            trace_doc[key] = existing[key]

    write_json_no_bom(trace_path, trace_doc)
    print(f"[OK] wrote {trace_path}")

print("[OK] Recreated all example_X_agent_trace.json files from official examples")
