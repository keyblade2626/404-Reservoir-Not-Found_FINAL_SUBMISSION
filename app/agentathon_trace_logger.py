from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_run_id(prefix: str = "eval") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short = uuid.uuid4().hex[:8]
    return f"{prefix}-{stamp}-{short}"


def trace_path(run_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in str(run_id))
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR / f"trace-{safe}.jsonl"


def summarize_text(value: Any, max_len: int = 240) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            value = str(value)
    value = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    if len(value) > max_len:
        return value[: max_len - 3] + "..."
    return value


def write_trace_event(
    run_id: str,
    agent_name: str,
    action: str,
    input_summary: str = "",
    output_summary: str = "",
    target_agent: Optional[str] = None,
    confidence: Optional[float] = None,
    retry_count: int = 0,
    status: str = "success",
    **extra: Any,
) -> dict:
    event = {
        "timestamp": utc_now(),
        "run_id": run_id,
        "agent_name": agent_name,
        "action": action,
        "input_summary": summarize_text(input_summary),
        "output_summary": summarize_text(output_summary),
        "target_agent": target_agent,
        "confidence": confidence,
        "retry_count": retry_count,
        "status": status,
    }

    for key, value in extra.items():
        if key not in event:
            event[key] = value

    path = trace_path(run_id)

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

    return event


def stdout_info(run_id: str, message: str) -> None:
    print(f"[INFO] run_id={run_id} {message}", flush=True)


def stdout_warn(run_id: str, message: str) -> None:
    print(f"[WARN] run_id={run_id} {message}", flush=True)


def stdout_error(run_id: str, message: str) -> None:
    print(f"[ERROR] run_id={run_id} {message}", file=sys.stderr, flush=True)


class TraceTimer:
    def __init__(self) -> None:
        self.start = time.perf_counter()

    def elapsed(self) -> float:
        return round(time.perf_counter() - self.start, 3)
