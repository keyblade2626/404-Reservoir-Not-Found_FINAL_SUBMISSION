import json
from pathlib import Path

summary = json.load(open("logs/official_examples_interaction_summary.json", encoding="utf-8-sig"))
examples = summary.get("examples", [])

lines = []
lines.append("# Official Strong Examples - Interaction Summary")
lines.append("")
lines.append("These examples are intended to demonstrate multi-agent reservoir reasoning, guard/fallback behaviour and auditable JSONL traces.")
lines.append("")
lines.append(f"- Passed: **{summary.get('passed')}**")
lines.append(f"- Failed / red flags: **{summary.get('failed')}**")
lines.append("")
lines.append("| Example | Purpose | Pass | Task | Tools | Edges | Agents | Visuals |")
lines.append("|---|---|---:|---|---:|---:|---:|---|")

for e in examples:
    visuals = ", ".join(e.get("ui_block_types") or [])
    lines.append(
        f"| `{e.get('example')}` | {e.get('purpose')} | "
        f"{'yes' if e.get('pass') else 'no'} | `{e.get('task_type')}` | "
        f"{e.get('tool_count')} | {e.get('interaction_edge_count')} | "
        f"{e.get('agent_count')} | {visuals} |"
    )

lines.append("")
lines.append("## Required JSONL trace files")
lines.append("")
lines.append("The final logs folder includes one JSONL trace per official run:")
lines.append("")
for i in range(1, 5):
    lines.append(f"- `logs/trace-example-{i:03d}.jsonl`")
lines.append("")
lines.append("Each JSONL line contains the required fields:")
lines.append("")
lines.append("```text")
lines.append("timestamp")
lines.append("run_id")
lines.append("agent_name")
lines.append("action")
lines.append("input_summary")
lines.append("output_summary")
lines.append("target_agent")
lines.append("confidence")
lines.append("retry_count")
lines.append("status")
lines.append("```")
lines.append("")
lines.append("## Details")
lines.append("")

for e in examples:
    lines.append(f"### {e.get('example')} - {e.get('purpose')}")
    lines.append("")
    lines.append("**Runtime evidence:**")
    lines.append("")
    lines.append(f"- Status: `{e.get('status')}`")
    lines.append(f"- Type: `{e.get('type')}`")
    lines.append(f"- Task: `{e.get('task_type')}`")
    lines.append(f"- Tools called: `{', '.join(e.get('tools_called') or [])}`")
    lines.append(f"- Interaction edges: `{e.get('interaction_edge_count')}`")
    lines.append(f"- Agent trace entries: `{e.get('agent_count')}`")
    lines.append(f"- Visual block types: `{', '.join(e.get('ui_block_types') or [])}`")
    lines.append("")
    lines.append("**Strengths:**")
    for s in e.get("strengths", []):
        lines.append(f"- {s}")
    lines.append("")
    lines.append("**Red flags:**")
    if e.get("red_flags"):
        for r in e.get("red_flags"):
            lines.append(f"- {r}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("**Answer preview:**")
    lines.append("")
    lines.append("```text")
    lines.append((e.get("answer_preview") or "")[:1200])
    lines.append("```")
    lines.append("")

Path("logs/submission_agent_interaction_summary.md").write_text("\n".join(lines), encoding="utf-8")
print("[OK] Updated logs/submission_agent_interaction_summary.md for 4 examples")
