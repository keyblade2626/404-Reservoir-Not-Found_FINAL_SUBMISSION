import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agent_bus import clear_logs, log_event, new_run_id
from app.agent_registry import get_agent_by_name
from app.compass_client import get_compass_client


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
RUN_REPORT = ARTIFACTS / "agent_logs" / "last_agent_run.json"


AGENT_STEPS = [
    {
        "agent": "Data Ingestion Agent",
        "kind": "internal_validation",
        "required": True,
    },
    {
        "agent": "HM Scoring Agent",
        "kind": "module",
        "module": "app.driver_diagnosis",
        "required": True,
    },
    {
        "agent": "Profile Diagnostics Agent",
        "kind": "multi_module",
        "modules": [
            "app.export_oil_profile_diagnostics",
            "app.export_bhp_profile_diagnostics",
            "app.export_gas_profile_diagnostics",
        ],
        "required": False,
    },
    {
        "agent": "BHP Observed Data Filter Agent",
        "kind": "module",
        "module": "app.bhp_observed_filter",
        "required": True,
    },
    {
        "agent": "Injection HM Agent",
        "kind": "module",
        "module": "app.injection_history_match",
        "required": False,
    },
    {
        "agent": "Streamline Alignment Agent",
        "kind": "module",
        "module": "app.streamline_cluster_snap_mapper",
        "required": False,
    },
    {
        "agent": "Injector-Producer Context Agent",
        "kind": "module",
        "module": "app.producer_injector_context",
        "required": False,
    },
    {
        "agent": "Well Activity Classification Agent",
        "kind": "module",
        "module": "app.well_activity_classifier",
        "required": True,
    },
    {
        "agent": "Reservoir Diagnosis Agent",
        "kind": "multi_module",
        "modules": [
            "app.final_hm_interpreter",
            "app.final_gas_interpreter",
            "app.final_oil_interpreter",
            "app.porosity_pressure_observations",
        ],
        "required": True,
    },
    {
        "agent": "Recommendation Agent",
        "kind": "module",
        "module": "app.plot_transmissibility_corridors",
        "required": False,
    },
    {
        "agent": "SmartWellRecommendationAgent",
        "kind": "module",
        "module": "app.smart_well_recommendation_agent",
        "required": True,
    },
    {
        "agent": "Visualization Agent",
        "kind": "multi_module",
        "modules": [
            "app.hm_map_payload",
        ],
        "required": False,
    },
    {
        "agent": "Chat Copilot Agent",
        "kind": "chat_ready",
        "required": False,
    },
]


def module_exists(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _tail(text: str, n: int = 2500) -> str:
    if not text:
        return ""
    return text[-n:]


def validate_input_artifacts(run_id: str) -> Dict[str, Any]:
    model_dir = ROOT / "data" / "sample_model"

    checks = {
        "model_dir": model_dir.exists(),
        "smspec": bool(list(model_dir.glob("*.SMSPEC")) + list(model_dir.glob("*.smspec"))),
        "unsmry": bool(list(model_dir.glob("*.UNSMRY")) + list(model_dir.glob("*.unsmry"))),
        "grdecl": bool(list(model_dir.glob("*.GRDECL")) + list(model_dir.glob("*.grdecl"))),
        "streamlines": bool(list(model_dir.glob("STREAMLINES*.SLN*"))),
        "well_connections_or_ixf": bool(list(model_dir.glob("*.IXF")) + list(model_dir.glob("*WELL*"))),
    }

    log_event(
        run_id=run_id,
        agent="Data Ingestion Agent",
        role=get_agent_by_name("Data Ingestion Agent")["role"],
        event="input_validation_completed",
        status="success" if checks["model_dir"] else "warning",
        message=(
            "Validated available reservoir input files. "
            f"SMSPEC={checks['smspec']}, UNSMRY={checks['unsmry']}, "
            f"GRDECL={checks['grdecl']}, streamlines={checks['streamlines']}."
        ),
        inputs=["data/sample_model"],
        outputs=["artifact availability report"],
        tools=["filesystem"],
        handoff_to="HM Scoring Agent",
        metadata=checks,
    )

    return checks


def run_module(run_id: str, agent_name: str, module_name: str, required: bool) -> Dict[str, Any]:
    agent = get_agent_by_name(agent_name) or {}
    role = agent.get("role")

    if not module_exists(module_name):
        status = "failed" if required else "skipped"

        log_event(
            run_id=run_id,
            agent=agent_name,
            role=role,
            event="module_missing",
            status=status,
            message=f"Module {module_name} was not found.",
            tools=[module_name],
            handoff_to=agent.get("handoff_to"),
        )

        return {
            "module": module_name,
            "status": status,
            "required": required,
            "returncode": None,
            "stdout_tail": "",
            "stderr_tail": "Module not found.",
        }

    log_event(
        run_id=run_id,
        agent=agent_name,
        role=role,
        event="agent_started",
        status="running",
        message=f"Running {module_name}.",
        inputs=agent.get("inputs", []),
        tools=[module_name],
        handoff_to=None,
    )

    t0 = time.time()

    proc = subprocess.run(
        [sys.executable, "-m", module_name],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )

    elapsed = round(time.time() - t0, 2)
    ok = proc.returncode == 0

    log_event(
        run_id=run_id,
        agent=agent_name,
        role=role,
        event="agent_completed" if ok else "agent_failed",
        status="success" if ok else "failed",
        message=f"{module_name} completed." if ok else f"{module_name} failed.",
        inputs=agent.get("inputs", []),
        outputs=agent.get("outputs", []),
        tools=[module_name],
        handoff_to=agent.get("handoff_to") if ok else None,
        duration_seconds=elapsed,
        metadata={
            "returncode": proc.returncode,
            "stdout_tail": _tail(proc.stdout),
            "stderr_tail": _tail(proc.stderr),
        },
    )

    return {
        "module": module_name,
        "status": "success" if ok else "failed",
        "required": required,
        "returncode": proc.returncode,
        "seconds": elapsed,
        "stdout_tail": _tail(proc.stdout),
        "stderr_tail": _tail(proc.stderr),
    }


def run_chat_ready_step(run_id: str) -> Dict[str, Any]:
    """
    Mark the chat copilot as ready without making the diagnostics pipeline depend
    on a specific Compass/OpenAI wrapper implementation.

    Some environments return a custom Compass wrapper with is_configured()/status().
    Other environments return a raw OpenAI-compatible client. Both are valid for
    the submission runtime, so this step must not crash the whole diagnostic run.
    """
    agent = get_agent_by_name("Chat Copilot Agent") or {}

    compass_status = {
        "configured": False,
        "available": False,
        "client_type": None,
    }
    compass_model = None
    log_status = "success"
    message = (
        "Chat Copilot Agent is ready to route user questions to shared artifacts. "
        "Compass/OpenAI client status was checked in a safe compatibility mode."
    )

    try:
        compass = get_compass_client()
        compass_status["client_type"] = type(compass).__name__

        # Case 1: custom Compass wrapper.
        if hasattr(compass, "is_configured") and callable(getattr(compass, "is_configured")):
            configured = bool(compass.is_configured())
            compass_status["configured"] = configured
            compass_status["available"] = configured

            if hasattr(compass, "status") and callable(getattr(compass, "status")):
                wrapper_status = compass.status()
                if isinstance(wrapper_status, dict):
                    compass_status.update(wrapper_status)

            compass_model = getattr(compass, "model", None) if configured else None

        # Case 2: raw OpenAI-compatible client.
        else:
            import os

            configured = bool(
                os.getenv("COMPASS_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or getattr(compass, "api_key", None)
            )

            compass_status.update({
                "configured": configured,
                "available": configured,
                "base_url_configured": bool(
                    os.getenv("COMPASS_BASE_URL")
                    or os.getenv("OPENAI_BASE_URL")
                    or getattr(compass, "base_url", None)
                ),
                "compatibility_mode": "raw_openai_client",
                "note": (
                    "get_compass_client returned a raw OpenAI-compatible client. "
                    "Wrapper methods such as is_configured() were not available."
                ),
            })

            compass_model = (
                os.getenv("COMPASS_MODEL")
                or os.getenv("OPENAI_MODEL")
                or getattr(compass, "model", None)
            )

    except Exception as exc:
        log_status = "warning"
        message = (
            "Chat Copilot Agent is available in artifact-only mode, but Compass/OpenAI "
            "client status could not be checked safely."
        )
        compass_status.update({
            "configured": False,
            "available": False,
            "error": str(exc),
            "compatibility_mode": "safe_fallback",
        })

    log_event(
        run_id=run_id,
        agent="Chat Copilot Agent",
        role=agent.get("role"),
        event="chat_agent_ready",
        status=log_status,
        message=message,
        inputs=agent.get("inputs", []),
        outputs=agent.get("outputs", []),
        tools=["intent router", "artifact lookup", "Compass API wrapper"],
        model=compass_model,
        handoff_to=None,
        metadata={
            "compass": compass_status,
        },
    )

    return {
        "status": log_status,
        "compass": compass_status,
    }


def run_agent_orchestration(clear_previous_logs: bool = True) -> Dict[str, Any]:
    if clear_previous_logs:
        clear_logs()

    run_id = new_run_id()
    start = time.time()

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    RUN_REPORT.parent.mkdir(parents=True, exist_ok=True)

    log_event(
        run_id=run_id,
        agent="Agent Orchestrator",
        event="run_started",
        status="running",
        message="Starting multi-agent reservoir HM diagnostic orchestration.",
        inputs=["user run request"],
        outputs=["agent run report"],
        tools=["agent_orchestrator"],
        handoff_to="Data Ingestion Agent",
    )

    steps: List[Dict[str, Any]] = []

    for step in AGENT_STEPS:
        agent_name = step["agent"]
        kind = step["kind"]
        required = bool(step.get("required"))

        if kind == "internal_validation":
            checks = validate_input_artifacts(run_id)
            steps.append({
                "agent": agent_name,
                "kind": kind,
                "status": "success",
                "checks": checks,
            })

        elif kind == "module":
            result = run_module(
                run_id=run_id,
                agent_name=agent_name,
                module_name=step["module"],
                required=required,
            )

            steps.append({
                "agent": agent_name,
                "kind": kind,
                **result,
            })

            if required and result["status"] == "failed":
                break

        elif kind == "multi_module":
            module_results = []
            failed_required = False

            for module_name in step["modules"]:
                result = run_module(
                    run_id=run_id,
                    agent_name=agent_name,
                    module_name=module_name,
                    required=False,
                )

                module_results.append(result)

                # For multi-module required agent, at least one core final module must succeed.
                if required and module_name == "app.final_hm_interpreter" and result["status"] == "failed":
                    failed_required = True

            status = "failed" if failed_required else "success"

            steps.append({
                "agent": agent_name,
                "kind": kind,
                "status": status,
                "modules": module_results,
            })

            if failed_required:
                break

        elif kind == "chat_ready":
            result = run_chat_ready_step(run_id)
            steps.append({
                "agent": agent_name,
                "kind": kind,
                **result,
            })

    overall_status = "success"

    for s in steps:
        if s.get("status") == "failed":
            overall_status = "failed"
            break

    elapsed = round(time.time() - start, 2)

    log_event(
        run_id=run_id,
        agent="Agent Orchestrator",
        event="run_completed",
        status=overall_status,
        message=f"Multi-agent orchestration completed with status={overall_status}.",
        inputs=[],
        outputs=["last_agent_run.json", "agent_interactions.jsonl"],
        tools=["agent_orchestrator"],
        duration_seconds=elapsed,
    )

    report = {
        "run_id": run_id,
        "status": overall_status,
        "seconds": elapsed,
        "steps": steps,
        "log_files": [
            "logs/agent_interactions.jsonl",
            "artifacts/agent_logs/agent_interactions.jsonl",
        ],
    }

    RUN_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report


if __name__ == "__main__":
    payload = run_agent_orchestration(clear_previous_logs=True)
    print(json.dumps(payload, indent=2))
