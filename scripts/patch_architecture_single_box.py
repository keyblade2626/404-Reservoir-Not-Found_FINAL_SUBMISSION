from pathlib import Path
import re

p = Path("ARCHITECTURE.md")
txt = p.read_text(encoding="utf-8-sig")

official_examples_section = """## 13. Official Input / Output Examples

Required folders:

    input_examples/
    output_examples/

The final official examples are:

    input_examples/example_1.json
    input_examples/example_2.json
    input_examples/example_3.json
    input_examples/example_4.json

    output_examples/example_1_output.json
    output_examples/example_2_output.json
    output_examples/example_3_output.json
    output_examples/example_4_output.json

The current official examples are intentionally diagnostic, multi-agent and guard-oriented:

1. Integrated HW-28 water mismatch root-cause diagnosis.
2. Ranked model-update action plan across the demo case.
3. Integrated pressure/BHP weakness diagnosis.
4. Invalid well guard and safe fallback behaviour.

Regenerate examples 1-3:

    python scripts/create_stronger_official_examples.py

Example 4 is the invalid-well guard/fallback validation. It demonstrates that the system blocks `HW-250`, avoids silently substituting another well and suggests valid alternatives.

Expected final official summary:

    Passed: 4
    Failed: 0

---
"""

final_logs_section = """## 14. Final Logs

The final logs folder should remain clean and focused.

Expected final logs:

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

The `example_*_agent_trace.json` files provide rich runtime traces for each official example.

The `trace-example-*.jsonl` files satisfy the required Agentathon JSONL trace format:

    logs/trace-<run_id>.jsonl

Each JSONL line contains:

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

These logs demonstrate:

- which agents were invoked
- what each agent was asked to do
- agent-to-agent handoffs
- delegation decisions
- critic / validation steps
- guard and fallback behaviour
- final output synthesis

Large debug traces, old server stdout/stderr logs and temporary stress-test files are not required in the final submission.

---
"""

txt2 = re.sub(
    r"## 13\. Official Input / Output Examples[\s\S]*?---\s*\n\s*## 14\. Final Logs",
    official_examples_section + "\n## 14. Final Logs",
    txt,
    count=1
)

txt3 = re.sub(
    r"## 14\. Final Logs[\s\S]*?---\s*\n\s*## 15\. Stress-Test Architecture",
    final_logs_section + "\n## 15. Stress-Test Architecture",
    txt2,
    count=1
)

if txt3 == txt:
    raise SystemExit("Could not patch ARCHITECTURE sections 13/14")

p.write_text(txt3, encoding="utf-8")
print("[OK] ARCHITECTURE.md aligned to 4 examples and required JSONL logs")
