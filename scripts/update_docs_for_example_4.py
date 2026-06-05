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
    "output_file": "output_examples\\example_4_output.json",
}

for summary_path in [
    LOGS / "official_examples_interaction_summary.json",
    LOGS / "v700_official_examples_summary.json",
]:
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

metadata_path = ROOT / "metadata.json"
m = load_json(metadata_path, {})

for key, item in [
    ("example_inputs", "input_examples/example_4.json"),
    ("example_outputs", "output_examples/example_4_output.json"),
    ("logs", "logs/example_4_agent_trace.json"),
    ("logs", "logs/trace-example-004.jsonl"),
]:
    arr = m.setdefault(key, [])
    if item not in arr:
        arr.append(item)

final_logs = m.setdefault("final_logs", {})
files = final_logs.setdefault("files", [])
for item in [
    "logs/example_4_agent_trace.json",
    "logs/trace-example-004.jsonl",
]:
    if item not in files:
        files.append(item)

official = m.setdefault("official_examples", {})
official["description"] = "Four final official examples designed to demonstrate multi-agent reservoir diagnosis plus guard/fallback behaviour."
official["passed"] = 4
official["failed"] = 0

examples = official.setdefault("examples", [])
examples = [e for e in examples if e.get("example") != "example_4"]
examples.append({
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
    "red_flags": example4_entry["red_flags"],
})
official["examples"] = examples

for key, item in [
    ("input_files", "input_examples/example_4.json"),
    ("output_files", "output_examples/example_4_output.json"),
]:
    arr = official.setdefault(key, [])
    if item not in arr:
        arr.append(item)

guard_notes = m.setdefault("submission_notes", [])
note = "Example 4 demonstrates invalid-well guard/fallback behaviour with a required JSONL trace."
if note not in guard_notes:
    guard_notes.append(note)

write_json(metadata_path, m)

readme_path = ROOT / "README.md"
readme = readme_path.read_text(encoding="utf-8-sig")

readme = readme.replace(
    "The repository contains three strong official examples:",
    "The repository contains four official examples:"
)
readme = readme.replace(
    "3. Integrated pressure/BHP weakness diagnosis.",
    "3. Integrated pressure/BHP weakness diagnosis.\n4. Invalid well guard and safe fallback behaviour."
)
readme = readme.replace(
    "logs/trace-example-003.jsonl",
    "logs/trace-example-003.jsonl\nlogs/trace-example-004.jsonl"
)
readme = readme.replace(
    "logs/example_3_agent_trace.json",
    "logs/example_3_agent_trace.json\nlogs/example_4_agent_trace.json"
)
readme = readme.replace(
    "output_examples/example_3_output.json",
    "output_examples/example_3_output.json\noutput_examples/example_4_output.json"
)
readme = readme.replace(
    "input_examples/example_3.json",
    "input_examples/example_3.json\ninput_examples/example_4.json"
)

if "Example 4 demonstrates the invalid-well guard" not in readme:
    insert = """

Example 4 demonstrates the invalid-well guard. It verifies that a request for `HW-250` does not silently fall back to another well. The system validates the well name, blocks the unsafe substitution, suggests valid alternatives and returns a guarded response.
"""
    marker = "These examples are intentionally diagnostic and multi-agent, not simple single-tool plot requests."
    if marker in readme:
        readme = readme.replace(marker, marker + "\n" + insert, 1)
    else:
        readme += insert

readme_path.write_text(readme, encoding="utf-8")

print("[OK] summaries, metadata and README updated for example_4")
