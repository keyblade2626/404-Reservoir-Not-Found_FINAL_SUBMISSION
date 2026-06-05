from pathlib import Path
import json
from datetime import date

meta_path = Path("metadata.json")
summary_path = Path("logs/official_examples_interaction_summary.json")

meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))

meta["last_updated"] = str(date.today())
meta["official_examples"] = {
    "description": "Four final official examples regenerated after enabling the LLM final answer writer for cleaner user-facing synthesis.",
    "passed": summary.get("passed"),
    "failed": summary.get("failed"),
    "examples": summary.get("examples", []),
    "input_files": [
        "input_examples/example_1.json",
        "input_examples/example_2.json",
        "input_examples/example_3.json",
        "input_examples/example_4.json"
    ],
    "output_files": [
        "output_examples/example_1_output.json",
        "output_examples/example_2_output.json",
        "output_examples/example_3_output.json",
        "output_examples/example_4_output.json"
    ]
}

meta.setdefault("final_logs", {})
meta["final_logs"]["description"] = "Clean final logs retained for submission after regenerating official examples with the LLM final answer writer enabled."
meta["final_logs"]["files"] = [
    "logs/submission_agent_interaction_summary.md",
    "logs/official_examples_interaction_summary.json",
    "logs/v700_official_examples_summary.json",
    "logs/example_1_agent_trace.json",
    "logs/example_2_agent_trace.json",
    "logs/example_3_agent_trace.json",
    "logs/example_4_agent_trace.json",
    "logs/trace-example-001.jsonl",
    "logs/trace-example-002.jsonl",
    "logs/trace-example-003.jsonl",
    "logs/trace-example-004.jsonl"
]

meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

print("[OK] metadata.json official examples updated from regenerated logs")
