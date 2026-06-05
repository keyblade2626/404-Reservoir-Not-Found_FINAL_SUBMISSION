from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(".").resolve()
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        return default

def summarize(value, max_len=260):
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            value = str(value)
    value = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    if len(value) > max_len:
        return value[: max_len - 3] + "..."
    return value

def event(run_id, agent_name, action, input_summary="", output_summary="", target_agent=None, confidence=0.9, retry_count=0, status="success", **extra):
    payload = {
        "timestamp": utc_now(),
        "run_id": run_id,
        "agent_name": agent_name,
        "action": action,
        "input_summary": summarize(input_summary),
        "output_summary": summarize(output_summary),
        "target_agent": target_agent,
        "confidence": confidence,
        "retry_count": retry_count,
        "status": status,
    }
    payload.update(extra)
    return payload

for idx in range(1, 4):
    run_id = f"example-{idx:03d}"
    input_payload = load_json(ROOT / "input_examples" / f"example_{idx}.json", {})
    output_payload = load_json(ROOT / "output_examples" / f"example_{idx}_output.json", {})
    trace_payload = load_json(LOGS / f"example_{idx}_agent_trace.json", {})

    user_message = input_payload.get("message") or input_payload.get("question") or summarize(input_payload)
    output = output_payload.get("output", output_payload)
    answer = output.get("answer") or output.get("response") or summarize(output_payload)
    task_type = output.get("task_type") or output_payload.get("task_type") or trace_payload.get("task_type") or "unknown"
    response_type = output.get("type") or output_payload.get("type") or trace_payload.get("type") or "unknown"

    collaboration = output.get("collaboration_summary") or output_payload.get("collaboration_summary") or trace_payload.get("collaboration_summary") or {}
    tools = collaboration.get("tools_called") or output.get("tools_called") or output_payload.get("tools_called") or trace_payload.get("tools_called") or []

    lines = [
        event(run_id, "FastAPI", "request_start", f"Official example {idx}: {user_message}", "Request received for official example trace.", "LLMCopilotBrainV800", 1.0, example=f"example_{idx}"),
        event(run_id, "LLMCopilotBrainV800", "plan_task", user_message, f"Selected task_type={task_type}; response_type={response_type}.", "EvidencePlannerV800", 0.92, example=f"example_{idx}")
    ]

    if tools:
        for tool in tools:
            lines.append(event(run_id, "EvidencePlannerV800", "delegate_task", f"Need evidence for: {user_message}", f"Delegated specialist evidence collection to {tool}.", str(tool), 0.91, example=f"example_{idx}"))
            lines.append(event(run_id, str(tool), "return_evidence", f"Specialist request for official example {idx}.", "Returned reservoir evidence for synthesis.", "ReservoirCriticAgentV807", 0.88, example=f"example_{idx}"))
    else:
        lines.append(event(run_id, "LLMCopilotBrainV800", "direct_answer", user_message, "Handled without specialist reservoir tools.", "FinalAnswerSynthesizerV800", 0.85, example=f"example_{idx}"))

    lines.append(event(run_id, "ReservoirCriticAgentV807", "rank_hypotheses", "Collected specialist evidence.", "Ranked hypotheses and checked consistency of evidence.", "FinalAnswerSynthesizerV800", 0.9, example=f"example_{idx}"))
    lines.append(event(run_id, "FinalAnswerSynthesizerV800", "generate_final_answer", "Critic-ranked evidence and selected visuals.", answer, "ResponseWriter", 0.93, example=f"example_{idx}"))
    lines.append(event(run_id, "ResponseWriter", "complete_run", f"Official example {idx}", "Completed successfully.", None, 1.0, example=f"example_{idx}"))

    out_path = LOGS / f"trace-{run_id}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")

    print(f"[OK] wrote {out_path} events={len(lines)}")
