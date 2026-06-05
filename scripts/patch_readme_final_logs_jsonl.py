from pathlib import Path
import re

p = Path("README.md")
txt = p.read_text(encoding="utf-8-sig")

final_logs_section = r"""## 17. Final Logs

The final `logs/` folder should remain clean and focused.

Expected final logs:

```text
logs/submission_agent_interaction_summary.md
logs/official_examples_interaction_summary.json
logs/v700_official_examples_summary.json
logs/example_1_agent_trace.json
logs/example_2_agent_trace.json
logs/example_3_agent_trace.json
logs/example_4_agent_trace.json
logs/trace-example-001.jsonl
logs/trace-example-002.jsonl
logs/trace-example-003.jsonl
logs/trace-example-004.jsonl

The example_*_agent_trace.json files provide rich runtime traces for each official example.

The trace-example-*.jsonl files satisfy the required Agentathon trace format:

logs/trace-<run_id>.jsonl

Each JSONL line contains the required fields:

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

The logs demonstrate:

routing mode;
selected tools;
agent trace;
interaction edges;
delegation decisions;
critic / validation steps;
guard and fallback behaviour;
visual block types;
collaboration summary;
answer preview.

Large debug traces and temporary server logs are not required in the final submission.

"""

txt = re.sub(
r"## 17. Final Logs[\s\S]?---\s\n\s*## 18. Required File Checklist",
final_logs_section + "\n## 18. Required File Checklist",
txt,
count=1
)

p.write_text(txt, encoding="utf-8")
print("[OK] README.md final logs section updated with required JSONL traces")
