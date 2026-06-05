import json
from pathlib import Path

p = Path("metadata.json")
m = json.loads(p.read_text(encoding="utf-8-sig"))

trace_files = [
    "logs/trace-example-001.jsonl",
    "logs/trace-example-002.jsonl",
    "logs/trace-example-003.jsonl",
]

existing_logs = m.get("logs", [])
for item in trace_files:
    if item not in existing_logs:
        existing_logs.append(item)
m["logs"] = existing_logs

final_logs = m.setdefault("final_logs", {})
files = final_logs.setdefault("files", [])
for item in trace_files:
    if item not in files:
        files.append(item)

m["logging_compliance"] = {
    "jsonl_trace_per_run": True,
    "trace_filename_pattern": "logs/trace-<run_id>.jsonl",
    "stdout_logging": True,
    "stdout_format_example": "[INFO] run_id=example-001 Planner delegated task to Specialist",
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
    ],
    "runtime_middleware": "app.agentathon_trace_logger + FastAPI HTTP middleware in app.main"
}

p.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
print("[OK] metadata.json updated with JSONL logging compliance")
