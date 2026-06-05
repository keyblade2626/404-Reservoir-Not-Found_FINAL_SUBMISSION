import json
from pathlib import Path

p = Path("metadata.json")
m = json.loads(p.read_text(encoding="utf-8-sig"))

m["last_updated"] = "2026-06-04"

Fix stale note

notes = m.setdefault("notes", {})
notes["official_examples"] = "Four official examples are included: three diagnostic multi-agent runs and one invalid-well guard/fallback run."

Ensure examples/logs arrays are complete

for key, items in {
"example_inputs": [
"input_examples/example_1.json",
"input_examples/example_2.json",
"input_examples/example_3.json",
"input_examples/example_4.json"
],
"example_outputs": [
"output_examples/example_1_output.json",
"output_examples/example_2_output.json",
"output_examples/example_3_output.json",
"output_examples/example_4_output.json"
],
"logs": [
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
}.items():
m[key] = items

Align official_examples block

m["official_examples"] = {
"description": "Four final official examples designed to demonstrate multi-agent reservoir diagnosis plus guard/fallback behaviour.",
"passed": 4,
"failed": 0,
"examples": [
{
"example": "example_1",
"purpose": "Integrated HW-28 water mismatch root-cause diagnosis",
"status": "success",
"pass": True,
"task_type": "v800_llm_planned_reservoir_multi_agent",
"type": "visual_response",
"tools_called": [
"IntegratedReservoirDiagnosisToolV800",
"DynamicProfileAgentToolV800",
"WCTBiasDiagnosticAgentToolV800",
"TRANCorridorVisualAgentToolV800",
"ReservoirRuntimeToolV501"
],
"tool_count": 5,
"interaction_edge_count": 27,
"agent_count": 12,
"ui_block_types": ["compact_table", "compact_table"],
"red_flags": []
},
{
"example": "example_2",
"purpose": "Ranked model-update action plan across the demo case",
"status": "success",
"pass": True,
"task_type": "v804_model_update_action_plan",
"type": "visual_response",
"tools_called": [
"ExecutiveHMSummaryAgentToolV800",
"IntegratedReservoirDiagnosisToolV800",
"WCTBiasDiagnosticAgentToolV800",
"IntegratedReservoirDiagnosisToolV800",
"TRANCorridorVisualAgentToolV800"
],
"tool_count": 5,
"interaction_edge_count": 27,
"agent_count": 13,
"ui_block_types": [
"wct_bias_cluster_map",
"compact_table",
"compact_table",
"compact_table",
"compact_table"
],
"red_flags": []
},
{
"example": "example_3",
"purpose": "Integrated pressure/BHP weakness diagnosis",
"status": "success",
"pass": True,
"task_type": "v800_llm_planned_reservoir_multi_agent",
"type": "visual_response",
"tools_called": [
"ExecutiveHMSummaryAgentToolV800",
"WCTBiasDiagnosticAgentToolV800",
"TRANCorridorVisualAgentToolV800",
"IntegratedReservoirDiagnosisToolV800"
],
"tool_count": 4,
"interaction_edge_count": 22,
"agent_count": 11,
"ui_block_types": ["compact_table", "compact_table", "suggestions"],
"red_flags": []
},
{
"example": "example_4",
"purpose": "Invalid well guard and safe fallback behaviour",
"status": "success",
"pass": True,
"task_type": "invalid_well_name_final_v601",
"type": "reasoning_response",
"tools_called": [
"LLMCopilotBrainV800",
"WellValidationGuardAgent",
"ClosestWellSuggestionAgent",
"ReservoirGuardResponseAgent",
"FinalAnswerSynthesizerV800"
],
"tool_count": 5,
"interaction_edge_count": 6,
"agent_count": 7,
"ui_block_types": [],
"red_flags": []
}
],
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

m["final_logs"] = {
"description": "Clean final logs retained for submission.",
"files": [
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
}

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

p.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
print("[OK] metadata.json aligned to 4 examples and JSONL logging")
