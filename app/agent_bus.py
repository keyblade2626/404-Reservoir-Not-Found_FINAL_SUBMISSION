import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
ARTIFACT_LOG_DIR = ROOT / "artifacts" / "agent_logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_LOG_DIR.mkdir(parents=True, exist_ok=True)

MAIN_LOG = LOG_DIR / "agent_interactions.jsonl"
ARTIFACT_LOG = ARTIFACT_LOG_DIR / "agent_interactions.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return str(uuid.uuid4())


def _json_default(obj: Any):
    try:
        return str(obj)
    except Exception:
        return None


def log_event(
    *,
    run_id: str,
    agent: str,
    event: str,
    message: str,
    status: str = "info",
    role: Optional[str] = None,
    inputs: Optional[List[str]] = None,
    outputs: Optional[List[str]] = None,
    tools: Optional[List[str]] = None,
    model: Optional[str] = None,
    handoff_to: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    payload = {
        "timestamp": now_iso(),
        "run_id": run_id,
        "agent": agent,
        "role": role,
        "event": event,
        "status": status,
        "message": message,
        "inputs": inputs or [],
        "outputs": outputs or [],
        "tools": tools or [],
        "model": model,
        "handoff_to": handoff_to,
        "duration_seconds": duration_seconds,
        "metadata": metadata or {},
    }

    line = json.dumps(payload, ensure_ascii=False, default=_json_default)

    for path in [MAIN_LOG, ARTIFACT_LOG]:
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    print(f"[AGENT][{status.upper()}][{agent}] {event}: {message}", flush=True)

    return payload


def clear_logs() -> None:
    for path in [MAIN_LOG, ARTIFACT_LOG]:
        if path.exists():
            path.unlink()


def read_logs(limit: int = 200) -> List[Dict[str, Any]]:
    if not ARTIFACT_LOG.exists():
        return []

    lines = ARTIFACT_LOG.read_text(encoding="utf-8").splitlines()
    lines = lines[-limit:]

    out = []

    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception:
            continue

    return out
