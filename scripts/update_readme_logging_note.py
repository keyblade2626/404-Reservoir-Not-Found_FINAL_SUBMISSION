from pathlib import Path

p = Path("README.md")
txt = p.read_text(encoding="utf-8-sig")

insert = """
In addition, the project includes one JSONL trace file per official example run, following the required pattern:

```text
logs/trace-example-001.jsonl
logs/trace-example-002.jsonl
logs/trace-example-003.jsonl

Each line is a valid JSON object with the required fields:

timestamp
run_id
agent_name
action
input_summary
output_summary
target_agent
confidence
retry_count
status

At runtime, the FastAPI application also prints meaningful stdout logs using the format:

[INFO] run_id=<run_id> Starting /run request
[INFO] run_id=<run_id> FastAPI delegated request to CopilotOrchestrator
[INFO] run_id=<run_id> Completed successfully in <seconds> seconds

This allows reviewers to inspect execution logs using docker logs <container_id> when running in a containerized environment.
"""

if "logs/trace-example-001.jsonl" not in txt:
marker = "Large debug traces and temporary server logs are not required in the final submission."
if marker in txt:
txt = txt.replace(marker, marker + "\n" + insert, 1)
else:
txt += "\n\n## JSONL Trace Logging\n\n" + insert

p.write_text(txt, encoding="utf-8")
print("[OK] README.md updated with JSONL/stdout logging note")
