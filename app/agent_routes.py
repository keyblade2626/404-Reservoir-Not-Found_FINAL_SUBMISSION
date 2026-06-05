import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter

from app.agent_bus import read_logs
from app.agent_orchestrator import run_agent_orchestration
from app.agent_registry import get_agent_flow


ROOT = Path(__file__).resolve().parents[1]
LAST_RUN = ROOT / "artifacts" / "agent_logs" / "last_agent_run.json"


router = APIRouter()


@router.post("/api/agents/run-full")
def run():
    """
    Competition-compatible root endpoint.
    Starts the full multi-agent reservoir diagnostic workflow.
    """
    return run_agent_orchestration(clear_previous_logs=True)


@router.post("/api/agents/run")
def api_agents_run():
    return run_agent_orchestration(clear_previous_logs=True)


@router.get("/api/agents/flow")
def api_agents_flow():
    return get_agent_flow()


@router.get("/api/agents/logs")
def api_agents_logs(limit: int = 200):
    return {
        "logs": read_logs(limit=limit),
    }


@router.get("/api/agents/last-run")
def api_last_run():
    if not LAST_RUN.exists():
        return {
            "available": False,
            "message": "No agent run report found yet.",
        }

    return {
        "available": True,
        "report": json.loads(LAST_RUN.read_text(encoding="utf-8")),
    }
