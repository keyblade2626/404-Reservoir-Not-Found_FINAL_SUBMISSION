from pathlib import Path
import re

p = Path("app/main.py")
txt = p.read_text(encoding="utf-8-sig")

block = r'''

# ============================================================
# Agentathon required JSONL trace logging + stdout logging
# ============================================================
try:
    from app.agentathon_trace_logger import (
        TraceTimer as _AgentathonTraceTimer,
        new_run_id as _agentathon_new_run_id,
        stdout_error as _agentathon_stdout_error,
        stdout_info as _agentathon_stdout_info,
        summarize_text as _agentathon_summarize_text,
        write_trace_event as _agentathon_write_trace_event,
    )

    def _agentathon_should_trace_path_v1102(path: str) -> bool:
        return (
            path == "/run"
            or path.startswith("/api/agent-chat")
            or path.startswith("/api/chat")
            or path == "/api/completed-run/activate"
            or path.startswith("/api/activate-uploaded-case/")
        )

    def _agentathon_target_for_path_v1102(path: str) -> str:
        if path == "/run":
            return "CopilotOrchestrator"
        if path.startswith("/api/agent-chat") or path.startswith("/api/chat"):
            return "AskReservoirAI"
        if path == "/api/completed-run/activate" or path.startswith("/api/activate-uploaded-case/"):
            return "CaseActivationDiagnosticsPipeline"
        return "Application"

    @app.middleware("http")
    async def _agentathon_jsonl_trace_middleware_v1102(request, call_next):
        path = request.url.path

        if not _agentathon_should_trace_path_v1102(path):
            return await call_next(request)

        run_id = (
            request.headers.get("X-Run-Id")
            or request.query_params.get("run_id")
            or _agentathon_new_run_id("eval")
        )

        timer = _AgentathonTraceTimer()
        target_agent = _agentathon_target_for_path_v1102(path)

        body_summary = ""
        try:
            content_length = int(request.headers.get("content-length") or "0")
        except Exception:
            content_length = 0

        try:
            if content_length and content_length < 250000:
                raw_body = await request.body()
                body_summary = _agentathon_summarize_text(raw_body.decode("utf-8", errors="ignore"), 300)
        except Exception:
            body_summary = ""

        _agentathon_stdout_info(run_id, f"Starting {request.method} {path} request")
        _agentathon_write_trace_event(
            run_id=run_id,
            agent_name="FastAPI",
            action="request_start",
            input_summary=f"{request.method} {path} {body_summary}",
            output_summary="Request received and routed to application.",
            target_agent=target_agent,
            confidence=1.0,
            retry_count=0,
            status="success",
            http_method=request.method,
            path=path,
        )

        _agentathon_stdout_info(run_id, f"FastAPI delegated request to {target_agent}")
        _agentathon_write_trace_event(
            run_id=run_id,
            agent_name="FastAPI",
            action="delegate_task",
            input_summary=f"Route {path}",
            output_summary=f"Delegated request handling to {target_agent}.",
            target_agent=target_agent,
            confidence=0.95,
            retry_count=0,
            status="success",
        )

        try:
            response = await call_next(request)
            duration = timer.elapsed()
            status_code = getattr(response, "status_code", None)
            status = "success" if status_code is not None and status_code < 400 else "error"

            _agentathon_write_trace_event(
                run_id=run_id,
                agent_name=target_agent,
                action="complete_request",
                input_summary=f"Handled {request.method} {path}",
                output_summary=f"Completed with HTTP {status_code} in {duration} seconds.",
                target_agent="ResponseWriter",
                confidence=1.0 if status == "success" else 0.4,
                retry_count=0,
                status=status,
                http_status=status_code,
                duration_seconds=duration,
            )

            _agentathon_stdout_info(run_id, f"{target_agent} completed with HTTP {status_code} in {duration} seconds")

            _agentathon_write_trace_event(
                run_id=run_id,
                agent_name="ResponseWriter",
                action="write_response",
                input_summary=f"HTTP status {status_code}",
                output_summary="Response returned to caller.",
                target_agent=None,
                confidence=1.0 if status == "success" else 0.4,
                retry_count=0,
                status=status,
                duration_seconds=duration,
            )

            if status == "success":
                _agentathon_stdout_info(run_id, f"Completed successfully in {duration} seconds")
            else:
                _agentathon_stdout_info(run_id, f"Completed with errors in {duration} seconds")

            try:
                response.headers["X-Run-Id"] = run_id
            except Exception:
                pass

            return response

        except Exception as exc:
            duration = timer.elapsed()

            _agentathon_write_trace_event(
                run_id=run_id,
                agent_name=target_agent,
                action="request_error",
                input_summary=f"Failed while handling {request.method} {path}",
                output_summary=f"{type(exc).__name__}: {exc}",
                target_agent=None,
                confidence=0.0,
                retry_count=0,
                status="error",
                duration_seconds=duration,
            )

            _agentathon_stdout_error(run_id, f"{target_agent} failed after {duration} seconds: {type(exc).__name__}: {exc}")
            raise

except Exception as _agentathon_logging_patch_error:
    print(f"[WARN] Agentathon JSONL logging middleware was not installed: {_agentathon_logging_patch_error}", flush=True)

'''

if "Agentathon required JSONL trace logging + stdout logging" not in txt:
    txt = txt.rstrip() + "\n\n" + block + "\n"
    p.write_text(txt, encoding="utf-8")
    print("[OK] main.py patched with Agentathon JSONL/stdout middleware")
else:
    print("[OK] main.py already contains Agentathon JSONL/stdout middleware")
