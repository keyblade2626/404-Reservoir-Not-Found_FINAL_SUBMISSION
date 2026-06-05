from pathlib import Path
import json
import subprocess
import sys
import time

ROOT = Path(".")
INPUT_DIR = ROOT / "input_examples"
OUTPUT_DIR = ROOT / "output_examples"
LOG_DIR = ROOT / "logs"

OUTPUT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

EXAMPLES = [
    {
        "id": "example_1",
        "purpose": "Integrated HW-28 water mismatch root-cause diagnosis",
        "expected_mode": "multi-agent diagnosis",
        "min_edges": 12,
        "min_agents": 6,
        "min_tools": 3,
        "required_terms": ["HW-28", "water", "WCT", "connectivity"],
        "preferred_visuals": ["compact_table", "tran_corridor_map", "wct_bias_cluster_map", "profile_series"]
    },
    {
        "id": "example_2",
        "purpose": "Ranked model-update action plan across the demo case",
        "expected_mode": "multi-agent model update prioritization",
        "min_edges": 8,
        "min_agents": 5,
        "min_tools": 2,
        "required_terms": ["priorit", "history match", "water"],
        "preferred_visuals": ["compact_table", "wct_bias_cluster_map", "tran_corridor_map", "profile_series"]
    },
    {
        "id": "example_3",
        "purpose": "Integrated pressure/BHP weakness diagnosis",
        "expected_mode": "multi-agent pressure/connectivity diagnosis",
        "min_edges": 8,
        "min_agents": 5,
        "min_tools": 2,
        "required_terms": ["pressure", "BHP", "connectivity"],
        "preferred_visuals": ["compact_table", "tran_corridor_map", "wct_bias_cluster_map", "profile_series"]
    }
]

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def compact(text, n=700):
    s = str(text or "").replace("\r", " ").replace("\n", " ").strip()
    while "  " in s:
        s = s.replace("  ", " ")
    return s[:n] + ("..." if len(s) > n else "")

def extract_output_payload(response):
    output = response.get("output") or {}
    raw = response.get("raw_response") or {}
    collab = output.get("collaboration_summary") or raw.get("collaboration_summary") or {}
    if not isinstance(collab, dict):
        collab = {}
    trace = output.get("agent_trace") or {}
    if not isinstance(trace, dict):
        trace = {}
    edges = output.get("interaction_edges") or []
    if not isinstance(edges, list):
        edges = []
    ui_types = output.get("ui_block_types") or []
    if not isinstance(ui_types, list):
        ui_types = []
    tools = collab.get("tools_called") or []
    if not isinstance(tools, list):
        tools = []
    return output, raw, collab, trace, edges, ui_types, tools

def evaluate_example(ex, response):
    output, raw, collab, trace, edges, ui_types, tools = extract_output_payload(response)
    answer = output.get("answer") or ""
    task = output.get("task_type") or ""
    response_type = output.get("type") or ""
    status = response.get("status")

    red_flags = []
    strengths = []

    edge_count = len(edges)
    agent_count = len(trace)
    tool_count = len(tools)

    if status != "success":
        red_flags.append(f"status is not success: {status}")

    if response_type != "visual_response":
        red_flags.append(f"expected visual_response, got {response_type}")

    if "direct" in str(task).lower():
        red_flags.append(f"expected multi-agent reservoir behaviour, got direct task: {task}")

    if edge_count < ex["min_edges"]:
        red_flags.append(f"too few interaction edges: {edge_count} < {ex['min_edges']}")
    else:
        strengths.append(f"{edge_count} interaction edges")

    if agent_count < ex["min_agents"]:
        red_flags.append(f"too few agent trace entries: {agent_count} < {ex['min_agents']}")
    else:
        strengths.append(f"{agent_count} agent trace entries")

    if tool_count < ex["min_tools"]:
        red_flags.append(f"too few specialist tools called: {tool_count} < {ex['min_tools']}")
    else:
        strengths.append(f"{tool_count} specialist tools called")

    low_answer = answer.lower()
    for term in ex["required_terms"]:
        if term.lower() not in low_answer:
            red_flags.append(f"answer missing expected term: {term}")

    bad_generic = [
        "what can you do",
        "i can answer simple general questions",
        "try for example",
        "capabilities"
    ]
    if any(x in low_answer for x in bad_generic):
        red_flags.append("appears to be generic capability answer")

    if not ui_types:
        red_flags.append("no visual evidence blocks")
    else:
        strengths.append("visual evidence returned: " + ", ".join(ui_types))

    if not any(v in ui_types for v in ex["preferred_visuals"]):
        red_flags.append("visual evidence does not include preferred diagnostic visual types")

    mode = collab.get("mode")
    mode_text = str(mode or "").lower()

    multi_like_modes = [
        "multi",
        "action_plan",
        "model_update",
        "diagnosis",
        "v804_model_update_action_plan",
        "v800_reservoir_multi_agent",
    ]

    if mode and any(x in mode_text for x in multi_like_modes):
        strengths.append(f"collaboration mode: {mode}")
    elif ex["min_tools"] >= 2 and tool_count >= ex["min_tools"] and edge_count >= ex["min_edges"]:
        strengths.append(
            f"multi-agent behaviour inferred from tools/edges even though collaboration mode label is: {mode}"
        )
    elif ex["min_tools"] >= 2:
        red_flags.append(f"collaboration mode is not clearly multi-agent: {mode}")

    if collab.get("real_edges") is True:
        strengths.append("real runtime edges confirmed")

    return {
        "example": ex["id"],
        "purpose": ex["purpose"],
        "expected_mode": ex["expected_mode"],
        "status": status,
        "type": response_type,
        "task_type": task,
        "ui_block_types": ui_types,
        "agent_count": agent_count,
        "interaction_edge_count": edge_count,
        "tools_called": tools,
        "tool_count": tool_count,
        "collaboration_summary": collab,
        "answer_preview": compact(answer, 900),
        "strengths": strengths,
        "red_flags": red_flags,
        "pass": len(red_flags) == 0
    }

results = []

for ex in EXAMPLES:
    in_path = INPUT_DIR / f"{ex['id']}.json"
    out_path = OUTPUT_DIR / f"{ex['id']}_output.json"

    print("\n====================================================")
    print(f"Running {ex['id']} - {ex['purpose']}")
    print("====================================================")

    start = time.time()

    proc = subprocess.run(
        [sys.executable, "run.py", "--input", str(in_path), "--output", str(out_path)],
        text=True,
        capture_output=True
    )

    elapsed = round(time.time() - start, 2)

    if proc.returncode != 0:
        print("STDOUT:")
        print(proc.stdout)
        print("STDERR:")
        print(proc.stderr)
        raise SystemExit(f"{ex['id']} failed with exit code {proc.returncode}")

    if not out_path.exists():
        raise SystemExit(f"Missing output file: {out_path}")

    response = load_json(out_path)
    result = evaluate_example(ex, response)
    result["elapsed_sec"] = elapsed
    result["input_message"] = load_json(in_path).get("message")
    result["output_file"] = str(out_path)

    results.append(result)

    print("status:", result["status"])
    print("type:", result["type"])
    print("task:", result["task_type"])
    print("tools:", result["tools_called"])
    print("edges:", result["interaction_edge_count"])
    print("agents:", result["agent_count"])
    print("ui:", result["ui_block_types"])
    print("pass:", result["pass"])
    if result["red_flags"]:
        print("RED FLAGS:")
        for flag in result["red_flags"]:
            print(" -", flag)
    print("answer preview:", result["answer_preview"][:600])

summary = {
    "log_type": "strong_official_examples_summary",
    "description": "Three official examples designed to demonstrate strong multi-agent reservoir diagnosis. These are generated by real runtime calls through run.py.",
    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "examples": results,
    "passed": sum(1 for r in results if r["pass"]),
    "failed": sum(1 for r in results if not r["pass"])
}

write_json(LOG_DIR / "official_examples_interaction_summary.json", summary)
write_json(LOG_DIR / "v700_official_examples_summary.json", summary)

md = []
md.append("# Official Strong Examples - Interaction Summary")
md.append("")
md.append("These examples are intended to demonstrate multi-agent reservoir reasoning rather than simple plotting.")
md.append("")
md.append(f"- Passed: **{summary['passed']}**")
md.append(f"- Failed / red flags: **{summary['failed']}**")
md.append("")
md.append("| Example | Purpose | Pass | Task | Tools | Edges | Agents | Visuals |")
md.append("|---|---|---:|---|---:|---:|---:|---|")

for r in results:
    md.append(
        f"| `{r['example']}` | {r['purpose']} | {'yes' if r['pass'] else 'no'} | "
        f"`{r['task_type']}` | {r['tool_count']} | {r['interaction_edge_count']} | {r['agent_count']} | "
        f"{', '.join(r['ui_block_types']) if r['ui_block_types'] else 'none'} |"
    )

md.append("")
md.append("## Details")
md.append("")

for r in results:
    md.append(f"### {r['example']} - {r['purpose']}")
    md.append("")
    md.append("**Input:**")
    md.append("")
    md.append("```text")
    md.append(r["input_message"])
    md.append("```")
    md.append("")
    md.append("**Runtime evidence:**")
    md.append("")
    md.append(f"- Status: `{r['status']}`")
    md.append(f"- Type: `{r['type']}`")
    md.append(f"- Task: `{r['task_type']}`")
    md.append(f"- Tools called: `{', '.join(r['tools_called']) if r['tools_called'] else 'none'}`")
    md.append(f"- Interaction edges: `{r['interaction_edge_count']}`")
    md.append(f"- Agent trace entries: `{r['agent_count']}`")
    md.append(f"- Visual block types: `{', '.join(r['ui_block_types']) if r['ui_block_types'] else 'none'}`")
    md.append("")
    md.append("**Strengths:**")
    if r["strengths"]:
        for s in r["strengths"]:
            md.append(f"- {s}")
    else:
        md.append("- none")
    md.append("")
    md.append("**Red flags:**")
    if r["red_flags"]:
        for flag in r["red_flags"]:
            md.append(f"- {flag}")
    else:
        md.append("- none")
    md.append("")
    md.append("**Answer preview:**")
    md.append("")
    md.append("```text")
    md.append(r["answer_preview"])
    md.append("```")
    md.append("")

(LOG_DIR / "submission_agent_interaction_summary.md").write_text("\n".join(md), encoding="utf-8")

print("\n====================================================")
print("STRONG OFFICIAL EXAMPLES GENERATED")
print("====================================================")
print("Passed:", summary["passed"])
print("Failed:", summary["failed"])
print("Summary JSON:", LOG_DIR / "official_examples_interaction_summary.json")
print("V700 summary JSON:", LOG_DIR / "v700_official_examples_summary.json")
print("Summary MD:", LOG_DIR / "submission_agent_interaction_summary.md")

# Hard fail only if any example failed status or became direct/generic.
critical = []
for r in results:
    if r["status"] != "success":
        critical.append((r["example"], "status failed"))
    if "direct" in str(r["task_type"]).lower():
        critical.append((r["example"], "routed as direct"))
    if any("generic capability" in f for f in r["red_flags"]):
        critical.append((r["example"], "generic answer"))

if critical:
    print("CRITICAL FAILURES:", critical)
    raise SystemExit(1)

if summary["failed"] > 0:
    print("")
    print("WARNING: Some examples have non-critical red flags. Review the summary before final submission.")
