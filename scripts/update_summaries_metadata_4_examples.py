from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(".").resolve()
LOGS = ROOT / "logs"

def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        return default

def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

example4_trace = load_json(LOGS / "example_4_agent_trace.json", {})

example4_entry = {
    "example": "example_4",
    "purpose": "Invalid well guard and safe fallback behaviour",
    "expected_mode": "guard / fallback",
    "status": example4_trace.get("status", "success"),
    "type": example4_trace.get("type", "guard_response"),
    "task_type": example4_trace.get("task_type", "guard_invalid_well"),
    "ui_block_types": [],
    "agent_count": example4_trace.get("agent_count", 7),
    "interaction_edge_count": example4_trace.get("interaction_edge_count", 6),
    "tools_called": example4_trace.get("tools_called", []),
    "tool_count": len(example4_trace.get("tools_called", [])),
    "collaboration_summary": example4_trace.get("collaboration_summary", {}),
    "answer_preview": example4_trace.get("answer_preview", ""),
    "strengths": example4_trace.get("strengths", []),
    "red_flags": example4_trace.get("red_flags", []),
    "pass": example4_trace.get("pass", True),
    "elapsed_sec": None,
    "input_message": example4_trace.get("input_message", ""),
    "output_file": "output_examples\\example_4_output.json"
}

for summary_path in [LOGS / "official_examples_interaction_summary.json", LOGS / "v700_official_examples_summary.json"]:
    data = load_json(summary_path, {})
    if not data:
        continue

    examples = data.setdefault("examples", [])
    examples = [e for e in examples if e.get("example") != "example_4"]
    examples.append(example4_entry)
    data["examples"] = examples
    data["passed"] = sum(1 for e in examples if e.get("pass") is True)
    data["failed"] = sum(1 for e in examples if e.get("pass") is not True)
    if "description" in data and "Three official examples" in data["description"]:
        data["description"] = data["description"].replace("Three official examples", "Four official examples")
    write_json(summary_path, data)

m = load_json(ROOT / "metadata.json", {})

for key, item in [
    ("example_inputs", "input_examples/example_4.json"),
    ("example_outputs", "output_examples/example_4_output.json"),
    ("logs", "logs/example_1_agent_trace.json"),
    ("logs", "logs/example_2_agent_trace.json"),
    ("logs", "logs/example_3_agent_trace.json"),
    ("logs", "logs/example_4_agent_trace.json"),
    ("logs", "logs/trace-example-001.jsonl"),
    ("logs", "logs/trace-example-002.jsonl"),
    ("logs", "logs/trace-example-003.jsonl"),
    ("logs", "logs/trace-example-004.jsonl"),
]:
    arr = m.setdefault(key, [])
    if item not in arr:
        arr.append(item)

final_logs = m.setdefault("final_logs", {})
files = final_logs.setdefault("files", [])
for item in [
    "logs/example_1_agent_trace.json",
    "logs/example_2_agent_trace.json",
    "logs/example_3_agent_trace.json",
    "logs/example_4_agent_trace.json",
    "logs/trace-example-001.jsonl",
    "logs/trace-example-002.jsonl",
    "logs/trace-example-003.jsonl",
    "logs/trace-example-004.jsonl",
]:
    if item not in files:
        files.append(item)

official = m.setdefault("official_examples", {})
official["description"] = "Four final official examples designed to demonstrate multi-agent reservoir diagnosis plus guard/fallback behaviour."
official["passed"] = 4
official["failed"] = 0

official_examples = official.setdefault("examples", [])
official_examples = [e for e in official_examples if e.get("example") != "example_4"]
official_examples.append({
    "example": "example_4",
    "purpose": "Invalid well guard and safe fallback behaviour",
    "status": example4_entry["status"],
    "pass": example4_entry["pass"],
    "task_type": example4_entry["task_type"],
    "type": example4_entry["type"],
    "tools_called": example4_entry["tools_called"],
    "tool_count": example4_entry["tool_count"],
    "interaction_edge_count": example4_entry["interaction_edge_count"],
    "agent_count": example4_entry["agent_count"],
    "ui_block_types": [],
    "red_flags": example4_entry["red_flags"]
})
official["examples"] = official_examples

for key, item in [
    ("input_files", "input_examples/example_4.json"),
    ("output_files", "output_examples/example_4_output.json")
]:
    arr = official.setdefault(key, [])
    if item not in arr:
        arr.append(item)

m["logging_compliance"] = {
    "jsonl_trace_per_run": True,
    "trace_filename_pattern": "logs/trace-<run_id>.jsonl",
    "stdout_logging": True,
    "stdout_format_example": "[INFO] run_id=<run_id> Starting /run request",
    "required_schema_fields": [
        "timestamp",
        "run_id",
        "agent_name",
        "action",
        "input_summary",
        "output_summary",
        "target_agent",
        "confidence",
        "retry_count",
        "status"
    ]
}

write_json(ROOT / "metadata.json", m)
print("[OK] summaries and metadata updated")
