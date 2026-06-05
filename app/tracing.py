import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

TRACE_PATH = LOG_DIR / "agent_trace.jsonl"


def log_agent_event(
    run_id: str,
    agent_name: str,
    action: str,
    input_summary: str,
    output_summary: str,
    target_agent: Optional[str] = None,
    confidence: Optional[float] = None,
    retry_count: int = 0,
    status: str = "success",
) -> None:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "agent_name": agent_name,
        "action": action,
        "input_summary": input_summary[:500],
        "output_summary": output_summary[:500],
        "target_agent": target_agent,
        "confidence": confidence,
        "retry_count": retry_count,
        "status": status,
        "sample_mode": os.getenv("SAMPLE_MODE", "false").lower() == "true",
    }

    line = json.dumps(event, ensure_ascii=False)

    print(line, flush=True)

    with TRACE_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
