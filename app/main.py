import math
from fastapi.encoders import jsonable_encoder
import time
import uuid
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from app.agents import (
    EvaluatorAgent,
    PlannerAgent,
    ReportWriterAgent,
    ReservoirDiagnosticAgent,
    SummaryImportAgent,
)
from app.tracing import log_agent_event
import json


load_dotenv()

app = FastAPI(title="404 Reservoir Not Found", version="0.2.0")


class RunRequest(BaseModel):
    request_id: Optional[str] = Field(default=None)
    question: Optional[str] = Field(default=None)
    message: Optional[str] = Field(default=None)
    user_query: str = Field(default="Analyze the reservoir history-match quality.")
    mode: str = Field(default="demo")
    context: Dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health() -> Dict[str, Any]:
    import os
    from pathlib import Path

    case_root = Path("data/sample_model/CASE")

    return {
        "status": "ok",
        "service": "404 Reservoir Not Found",
        "api_port": int(os.getenv("PORT", "8000")),
        "compass_configured": bool(os.getenv("OPENAI_API_KEY")),
        "openai_base_url": os.getenv("OPENAI_BASE_URL"),
        "sample_mode": os.getenv("SAMPLE_MODE", "false").lower() == "true",
        "native_summary_mode": True,
        "smspec_exists": case_root.with_suffix(".SMSPEC").exists(),
        "unsmry_exists": case_root.with_suffix(".UNSMRY").exists(),
    }


@app.post("/run")
def run(request: RunRequest) -> Dict[str, Any]:
    """
    Competition-compatible root endpoint.

    Modern behavior:
    - Accepts question/message/user_query.
    - Routes through the current /api/chat logic.
    - Uses LangGraph V013/V014 for safe migrated routes.
    - Falls back to the existing diagnostic chain when needed.
    - Returns a compact, contest-ready JSON response.
    """
    start = time.time()
    run_id = request.request_id or f"run-{uuid.uuid4().hex[:10]}"
    question = (
        request.question
        or request.message
        or request.user_query
        or "Analyze the reservoir history-match quality."
    )

    try:
        from app.chat_router import answer_question

        response = answer_question(question)

        if not isinstance(response, dict):
            response = {
                "type": "text_response",
                "intent": "text_response",
                "answer": str(response),
                "ui_blocks": [],
                "data": {},
                "agent_trace": {},
            }

        agent_trace = response.get("agent_trace") or {}
        v013 = agent_trace.get("LangGraphActiveNodesV013") or {}
        node_trace = v013.get("node_trace") or []
        critic = agent_trace.get("ReservoirCriticAgentV008") or {}

        nodes = [
            item.get("node")
            for item in node_trace
            if isinstance(item, dict) and item.get("node")
        ]

        selected_agent = None
        dispatch = v013.get("dispatch") or {}
        if dispatch:
            selected_agent = dispatch.get("selected_agent")

        collaboration_summary = {
            "orchestrator": "LangGraph V013/V014 safe-route orchestrator",
            "used_langgraph_nodes": bool(nodes),
            "nodes": nodes,
            "selected_agent": selected_agent,
            "critic_status": critic.get("status"),
            "critic_well": critic.get("well"),
            "fallback_used": (
                (agent_trace.get("LangGraphMainIntegrationV014") or {}).get("status")
                in ["fallback_to_existing_chain", "error_fallback_to_existing_chain"]
            ),
        }

        # Contest-compatible trace line.
        try:
            import json
            from datetime import datetime, timezone
            from pathlib import Path

            log_path = Path("logs/agent_trace.jsonl")
            log_path.parent.mkdir(exist_ok=True)

            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": run_id,
                "agent_name": "LangGraphMainOrchestrator",
                "action": "run_question",
                "input_summary": question[:500],
                "output_summary": str(response.get("answer") or "")[:700],
                "target_agent": selected_agent,
                "confidence": None,
                "retry_count": 0,
                "status": "success",
                "latency_ms": int((time.time() - start) * 1000),
                "model": None,
                "tool_name": "answer_question",
                "intent": response.get("intent"),
                "nodes": nodes,
                "critic_status": critic.get("status"),
            }

            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\\n")

        except Exception:
            pass

        return {
            "run_id": run_id,
            "status": "success",
            "mode": request.mode,
            "question": question,
            "intent": response.get("intent"),
            "answer": response.get("answer"),
            "ui_blocks": response.get("ui_blocks", []),
            "data": response.get("data", {}),
            "agent_collaboration_summary": collaboration_summary,
            "agent_trace": agent_trace,
            "log_path": "logs/agent_trace.jsonl",
            "execution_time_seconds": round(time.time() - start, 3),
        }

    except Exception as exc:
        execution_time = round(time.time() - start, 3)

        try:
            log_agent_event(
                run_id=run_id,
                agent_name="System",
                action="modern_run_error",
                input_summary=question,
                output_summary=f"{type(exc).__name__}: {str(exc)}",
                target_agent=None,
                confidence=0.0,
                status="error",
            )
        except Exception:
            pass

        return {
            "run_id": run_id,
            "status": "error",
            "question": question,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
                "recoverable": True,
            },
            "execution_time_seconds": execution_time,
            "log_path": "logs/agent_trace.jsonl",
        }

    

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.dashboard_routes import router as dashboard_router

app.include_router(dashboard_router)

ROOT_DIR = Path(__file__).resolve().parents[1]

app.mount("/web", StaticFiles(directory=str(ROOT_DIR / "web")), name="web")
app.mount("/artifacts", StaticFiles(directory=str(ROOT_DIR / "artifacts")), name="artifacts")




# ==========================================================
# DEMO DASHBOARD ROUTE FOR CONTEST REVIEWERS
# Serves the bundled demo dashboard directly, using the included
# data/sample_model and artifacts/diagnosis outputs.
# This bypasses the INTERSECT import landing workflow.
# ==========================================================
@app.get("/demo-dashboard")
def demo_dashboard_page():
    from pathlib import Path
    from fastapi.responses import FileResponse

    root = Path(__file__).resolve().parents[1]
    dashboard_html = root / "web" / "index.html"

    return FileResponse(str(dashboard_html))


@app.get("/dashboard")
def dashboard_page():
    active_case_marker = ROOT_DIR / "artifacts" / "uploads" / "active_case.json"

    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    if not active_case_marker.exists():
        return FileResponse(str(ROOT_DIR / "web" / "landing.html"), headers=headers)

    return FileResponse(str(ROOT_DIR / "web" / "index.html"), headers=headers)

# V037 RESTORE LANDING ROOT ROUTE
@app.get("/")
def landing_root_page():
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return FileResponse(str(ROOT_DIR / "web" / "landing.html"), headers=headers)


# V037 LANDING ALIAS ROUTE
@app.get("/landing")
def landing_alias_page():
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return FileResponse(str(ROOT_DIR / "web" / "landing.html"), headers=headers)


# V041 RESTORE RESERVOIR CASE IMPORT ROUTES
from fastapi import Request as _RequestV041
from fastapi.responses import JSONResponse as _JSONResponseV041, FileResponse as _FileResponseV041
from pathlib import Path as _PathV041
import re as _re_v041
import json as _json_v041
import uuid as _uuid_v041
import shutil as _shutil_v041
import time as _time_v041

_CASE_UPLOAD_ROOT_V041 = _PathV041(__file__).resolve().parents[1] / "artifacts" / "uploads"
_CASE_UPLOAD_ROOT_V041.mkdir(parents=True, exist_ok=True)

_CASE_ROOT_V041 = _PathV041(__file__).resolve().parents[1] / "data" / "sample_model"

_CASE_FILE_SLOTS_V041 = {
    "case_smspec": {"standard": "CASE.SMSPEC", "required": True, "keyword": None},
    "case_unsmry": {"standard": "CASE.UNSMRY", "required": True, "keyword": None},

    "tranx": {"standard": "TRANX.GRDECL", "required": True, "keyword": "TRANX"},
    "trany": {"standard": "TRANY.GRDECL", "required": True, "keyword": "TRANY"},
    "tranz": {"standard": "TRANZ.GRDECL", "required": True, "keyword": "TRANZ"},

    "permx": {"standard": "PERM_X.GRDECL", "required": True, "keyword": "PERMX"},
    "permy": {"standard": "PERM_Y.GRDECL", "required": True, "keyword": "PERMY"},
    "permz": {"standard": "PERM_Z.GRDECL", "required": True, "keyword": "PERMZ"},

    "poro": {"standard": "PORO.GRDECL", "required": True, "keyword": "PORO"},
    "poro_mult": {"standard": "PORO_MULT.GRDECL", "required": True, "keyword": "PORO_MULT"},

    "multx": {"standard": "MULTX.GRDECL", "required": True, "keyword": "MULTX"},
    "multy": {"standard": "MULTY.GRDECL", "required": True, "keyword": "MULTY"},
    "multz": {"standard": "MULTZ.GRDECL", "required": True, "keyword": "MULTZ"},

    "pressure_init": {"standard": "PRESSURE_INIT.GRDECL", "required": True, "keyword": "PRESSURE"},
    "pressure_eoh": {"standard": "PRESSURE_EOH.GRDECL", "required": True, "keyword": "PRESSURE"},

    "swat_init": {"standard": "SWAT_INIT.GRDECL", "required": True, "keyword": "SWAT"},
    "swat_eoh": {"standard": "SWAT_EOH.GRDECL", "required": True, "keyword": "SWAT"},

    "soil_init": {"standard": "SOIL_INIT.GRDECL", "required": True, "keyword": "SOIL"},
    "soil_eoh": {"standard": "SOIL_EOH.GRDECL", "required": True, "keyword": "SOIL"},

    "sgas_init": {"standard": "SGAS_INIT.GRDECL", "required": True, "keyword": "SGAS"},
    "sgas_eoh": {"standard": "SGAS_EOH.GRDECL", "required": True, "keyword": "SGAS"},

    "relperm_region": {"standard": "FIPNUM.GRDECL", "required": True, "keyword": "FIPNUM"},

    "well_connections": {"standard": "WELL_CONNECTIONS.ixf", "required": True, "keyword": None},
    "relperm": {"standard": "RELPERM.ixf", "required": True, "keyword": None},
    "prt": {"standard": "SIMULATION.PRT", "required": True, "keyword": None},
    "streamlines_init": {"standard": "STREAMLINES_INIT.SLN0001", "required": True, "keyword": None},
    "streamlines_eoh": {"standard": "STREAMLINES_EOH.SLN0359", "required": True, "keyword": None},
}

_EXAMPLE_FILES_V041 = {
    "relperm": "RELPERM.ixf",
    "well_connections": "WELL_CONNECTIONS.ixf",
    "smspec": "CASE.SMSPEC",
    "unsmry": "CASE.UNSMRY",
    "grdecl": "PORO.GRDECL",
}

def _read_text_flexible_v041(path):
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return path.read_text(encoding=enc), enc
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="latin-1", errors="ignore"), "latin-1-ignore"

def _standardize_grdecl_keyword_v041(path, expected_keyword):
    if not expected_keyword or not path.name.lower().endswith(".grdecl"):
        return "not_applicable"

    text, enc = _read_text_flexible_v041(path)
    lines = text.splitlines(keepends=True)

    for idx, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            continue
        if stripped.startswith("--"):
            continue
        if stripped.startswith("/") or stripped == "/":
            continue

        match = _re_v041.match(r"^([A-Za-z_][A-Za-z0-9_]*)\b(.*)$", line)
        if not match:
            continue

        old_keyword = match.group(1)
        rest = match.group(2)

        if old_keyword.upper() == expected_keyword.upper():
            return f"keyword_ok:{old_keyword}"

        newline = ""
        if line.endswith("\r\n"):
            newline = "\r\n"
            rest = rest[:-2] if rest.endswith("\r\n") else rest
        elif line.endswith("\n"):
            newline = "\n"
            rest = rest[:-1] if rest.endswith("\n") else rest

        lines[idx] = expected_keyword + rest + newline
        path.write_text("".join(lines), encoding="utf-8")
        return f"keyword_changed:{old_keyword}->{expected_keyword}"

    return "keyword_not_found"

@app.post("/api/import-case")
async def import_case(request: _RequestV041):
    form = await request.form()

    upload_id = f"case-{_uuid_v041.uuid4().hex[:10]}"
    upload_dir = _CASE_UPLOAD_ROOT_V041 / upload_id
    standardized_dir = upload_dir / "standardized_sample_model"
    standardized_dir.mkdir(parents=True, exist_ok=True)

    def _int_field(name, default):
        try:
            return int(form.get(name, default))
        except Exception:
            return default

    nx = _int_field("nx", 181)
    ny = _int_field("ny", 190)
    nz = _int_field("nz", 62)

    grid_payload = {"nx": nx, "ny": ny, "nz": nz}
    (standardized_dir / "grid_dimensions.json").write_text(
        _json_v041.dumps(grid_payload, indent=2),
        encoding="utf-8"
    )

    files_summary = []
    missing_required = []
    received_count = 0

    for slot, spec in _CASE_FILE_SLOTS_V041.items():
        upload = form.get(slot)

        row = {
            "slot": slot,
            "standard_name": spec["standard"],
            "required": spec["required"],
            "received": False,
            "original_filename": None,
            "keyword_action": "",
            "relative_path": None,
        }

        if upload is None or not getattr(upload, "filename", None):
            missing_required.append(spec["standard"])
            files_summary.append(row)
            continue

        target = standardized_dir / spec["standard"]

        with target.open("wb") as buffer:
            _shutil_v041.copyfileobj(upload.file, buffer)

        keyword_action = _standardize_grdecl_keyword_v041(target, spec.get("keyword"))

        row.update({
            "received": True,
            "original_filename": _PathV041(upload.filename).name,
            "keyword_action": keyword_action,
            "relative_path": str(target.relative_to(_PathV041(__file__).resolve().parents[1])).replace("\\", "/"),
            "size_bytes": target.stat().st_size,
        })

        received_count += 1
        files_summary.append(row)

    manifest = {
        "upload_id": upload_id,
        "status": "success",
        "created_at_unix": _time_v041.time(),
        "standardized_relative_path": str(standardized_dir.relative_to(_PathV041(__file__).resolve().parents[1])).replace("\\", "/"),
        "grid_dimensions": grid_payload,
        "received_count": received_count,
        "missing_required": missing_required,
        "files": files_summary,
        "note": "Files were mapped to standard filenames expected by the current reservoir demo scripts."
    }

    (upload_dir / "manifest.json").write_text(_json_v041.dumps(manifest, indent=2), encoding="utf-8")

    return manifest

@app.get("/api/import-case-status/{upload_id}")
def import_case_status(upload_id: str):
    manifest = _CASE_UPLOAD_ROOT_V041 / upload_id / "manifest.json"

    if not manifest.exists():
        return _JSONResponseV041(
            status_code=404,
            content={
                "status": "not_found",
                "upload_id": upload_id,
                "message": "Import case ID not found."
            }
        )

    return _json_v041.loads(manifest.read_text(encoding="utf-8"))



# ============================================================
# V901 - Activate-case deterministic diagnostics hook
# ============================================================
def _run_diagnostics_pipeline_after_activate_v901(reason: str):
    """
    Runs existing deterministic diagnosis exporters after the user activates
    a case from the landing page. This rebuilds artifacts/diagnosis from
    data/sample_model and does not use the LLM to generate KPIs.
    """
    try:
        from app.diagnostics_pipeline import run_diagnostics_pipeline
        return run_diagnostics_pipeline(reason=reason, strict=False)
    except Exception as exc:
        return {
            "ok": False,
            "reason": reason,
            "error": f"{type(exc).__name__}: {exc}",
        }


@app.post("/api/activate-uploaded-case/{upload_id}")
def activate_uploaded_case(upload_id: str):
    upload_dir = _CASE_UPLOAD_ROOT_V041 / upload_id / "standardized_sample_model"

    if not upload_dir.exists():
        return _JSONResponseV041(
            status_code=404,
            content={
                "status": "not_found",
                "upload_id": upload_id,
                "message": "Standardized uploaded case not found."
            }
        )

    _CASE_ROOT_V041.mkdir(parents=True, exist_ok=True)

    copied = []

    for src in upload_dir.iterdir():
        if not src.is_file():
            continue

        dst = _CASE_ROOT_V041 / src.name
        _shutil_v041.copy2(src, dst)
        copied.append(src.name)

    active_case_marker = _CASE_UPLOAD_ROOT_V041 / "active_case.json"
    active_case_marker.write_text(
        _json_v041.dumps(
            {
                "status": "active",
                "upload_id": upload_id,
                "activated_at_unix": _time_v041.time(),
                "active_case_dir": str(_CASE_ROOT_V041).replace("\\", "/"),
                "copied_file_count": len(copied),
                "copied_files": copied,
            },
            indent=2
        ),
        encoding="utf-8"
    )

    diagnostics_pipeline_report_v901 = _run_diagnostics_pipeline_after_activate_v901(
        reason="uploaded_case_activate_button"
    )

    return {
        "status": "success",
        "upload_id": upload_id,
        "activated_case_dir": str(_CASE_ROOT_V041).replace("\\", "/"),
        "copied_file_count": len(copied),
        "copied_files": copied,
        "note": "Uploaded standardized files have been copied into data/sample_model and will be used by the current scripts."
    }

@app.get("/api/example-file/{file_key}")
def download_example_file(file_key: str):
    standard = _EXAMPLE_FILES_V041.get(file_key.lower())

    if not standard:
        return _JSONResponseV041(
            status_code=404,
            content={
                "status": "not_found",
                "file_key": file_key,
                "available_keys": sorted(_EXAMPLE_FILES_V041.keys())
            }
        )

    path = _CASE_ROOT_V041 / standard

    if not path.exists():
        return _JSONResponseV041(
            status_code=404,
            content={
                "status": "not_found",
                "file_key": file_key,
                "expected_file": standard
            }
        )

    return _FileResponseV041(str(path), filename=standard)


# V050 INTERSECT automatic output package generator
from fastapi import UploadFile as _UploadFileV050, File as _FileV050, Form as _FormV050
from fastapi.responses import FileResponse as _FileResponseV050, JSONResponse as _JSONResponseV050
from typing import Optional as _OptionalV050, List as _ListV050
import uuid as _uuid_v050
import shutil as _shutil_v050

from app.ix_output_generator import generate_package as _generate_ix_package_v050, safe_name as _safe_name_v050

_IX_PACKAGE_ROOT_V050 = Path(__file__).resolve().parents[1] / "artifacts" / "ix_output_packages"
_IX_PACKAGE_ROOT_V050.mkdir(parents=True, exist_ok=True)


@app.post("/api/generate-ix-output-package")
async def generate_ix_output_package(
    afi_file: _UploadFileV050 = _FileV050(...),
    support_files: _ListV050[_UploadFileV050] = _FileV050(default=[]),
    start_date: _OptionalV050[str] = _FormV050(default=None),
    end_date: _OptionalV050[str] = _FormV050(default=None),
):
    package_id = f"ixpkg-{_uuid_v050.uuid4().hex[:10]}"
    work_dir = _IX_PACKAGE_ROOT_V050 / package_id
    work_dir.mkdir(parents=True, exist_ok=True)

    afi_name = _safe_name_v050(afi_file.filename or "case.afi")
    if not afi_name.lower().endswith(".afi"):
        return _JSONResponseV050(
            status_code=400,
            content={
                "status": "error",
                "message": "Please upload a valid .afi file as the main AFI input."
            }
        )

    afi_path = work_dir / afi_name
    with afi_path.open("wb") as buffer:
        _shutil_v050.copyfileobj(afi_file.file, buffer)

    saved_support = []
    for upload in support_files or []:
        if not upload or not upload.filename:
            continue

        name = _safe_name_v050(upload.filename)
        target = work_dir / name

        with target.open("wb") as buffer:
            _shutil_v050.copyfileobj(upload.file, buffer)

        saved_support.append(name)

    try:
        result = _generate_ix_package_v050(
            work_dir=work_dir,
            afi_filename=afi_name,
            start_date=start_date or None,
            end_date=end_date or None,
        )
    except Exception as exc:
        return _JSONResponseV050(
            status_code=500,
            content={
                "status": "error",
                "package_id": package_id,
                "message": f"IX package generation failed: {type(exc).__name__}: {exc}",
                "saved_support_files": saved_support,
            }
        )

    result["package_id"] = package_id
    result["saved_support_files"] = saved_support
    result["download_base"] = f"/api/download-generated-package/{package_id}"

    return result


@app.get("/api/download-generated-package/{package_id}/{filename}")
def download_generated_package(package_id: str, filename: str):
    safe_package = _safe_name_v050(package_id)
    safe_file = _safe_name_v050(filename)

    path = _IX_PACKAGE_ROOT_V050 / safe_package / safe_file

    if not path.exists() or not path.is_file():
        return _JSONResponseV050(
            status_code=404,
            content={
                "status": "not_found",
                "package_id": package_id,
                "filename": filename,
            }
        )

    return _FileResponseV050(str(path), filename=safe_file)



# ==========================================================
# V315 COMPLETE CASE FOLDER IMPORT ROUTE
# Receives full folder upload: main AFI + all include/support files.
# ==========================================================
from fastapi import UploadFile as _UploadFileV315, File as _FileV315, Form as _FormV315
from typing import List as _ListV315, Optional as _OptionalV315
from fastapi.responses import JSONResponse as _JSONResponseV315
import time as _time_v315
import shutil as _shutil_v315
import zipfile as _zipfile_v315
import re as _re_v315

@app.post("/api/intersect/import-case-folder-v315-disabled")
async def import_case_folder_v315(
    files: _ListV315[_UploadFileV315] = _FileV315(...),
    main_afi_path: _OptionalV315[str] = _FormV315(None),
):
    root = Path(__file__).resolve().parents[1]
    session_id = f"case_folder_v315_{int(_time_v315.time())}"

    upload_root = root / "artifacts" / "case_folder_uploads" / session_id
    output_root = root / "artifacts" / "ix_output_packages" / session_id

    upload_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    saved = []

    for f in files:
        rel_name = (f.filename or f"uploaded_{len(saved)}").replace("\\", "/")
        parts = [p for p in Path(rel_name).parts if p not in ("..", "/", "\\") and ":" not in p]
        safe_rel = Path(*parts) if parts else Path(f"uploaded_{len(saved)}")

        dst = upload_root / safe_rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        with dst.open("wb") as out:
            _shutil_v315.copyfileobj(f.file, out)

        saved.append(dst)

    afi_files = [p for p in saved if p.suffix.lower() == ".afi"]

    if not afi_files:
        return _JSONResponseV315(
            status_code=400,
            content={
                "ok": False,
                "message": "No .AFI file detected in the uploaded folder.",
                "saved_files": len(saved),
            },
        )

    selected_afi = None

    if main_afi_path:
        normalized = main_afi_path.replace("\\", "/")
        for p in afi_files:
            try:
                rel = str(p.relative_to(upload_root)).replace("\\", "/")
            except Exception:
                rel = p.name

            if rel == normalized:
                selected_afi = p
                break

    selected_afi = selected_afi or afi_files[0]

    try:
        afi_text = selected_afi.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        afi_text = selected_afi.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        afi_text = ""

    refs = []
    pattern = r"""['"]([^'"]+\.(?:ixf|inc|grdecl|obsh|prt|txt|init|egrid|grid|unrst|smspec|unsmry|afi))['"]"""
    for m in _re_v315.finditer(pattern, afi_text, _re_v315.I):
        refs.append(m.group(1))

    generated_include_1 = output_root / "AR360_MODEL_EDITS.ixf"
    generated_include_2 = output_root / "AR360_OUTPUT_CONTROLS.ixf"
    updated_afi = output_root / selected_afi.name

    generated_include_1.write_text(
        "-- AR360 generated model edits include\n"
        "-- TRAN / RelPerm generated edits will be inserted here.\n",
        encoding="utf-8",
    )

    generated_include_2.write_text(
        "-- AR360 generated output controls include\n"
        "-- Required exports / controls will be inserted here.\n",
        encoding="utf-8",
    )

    include_block = (
        "\n\n-- AR360 generated includes\n"
        f"INCLUDE '{generated_include_1.name}' /\n"
        f"INCLUDE '{generated_include_2.name}' /\n"
    )

    updated_afi.write_text(afi_text + include_block, encoding="utf-8")

    zip_path = output_root / "intersect_output_package.zip"
    with _zipfile_v315.ZipFile(zip_path, "w", _zipfile_v315.ZIP_DEFLATED) as z:
        z.write(updated_afi, updated_afi.name)
        z.write(generated_include_1, generated_include_1.name)
        z.write(generated_include_2, generated_include_2.name)

    return {
        "ok": True,
        "session_id": session_id,
        "saved_files": len(saved),
        "afi_files_detected": [str(p.relative_to(upload_root)).replace("\\", "/") for p in afi_files],
        "main_afi": str(selected_afi.relative_to(upload_root)).replace("\\", "/"),
        "include_references_detected": refs,
        "updated_afi": updated_afi.name,
        "generated_include_count": 2,
        "generated_includes": [generated_include_1.name, generated_include_2.name],
        "download_url": f"/artifacts/ix_output_packages/{session_id}/intersect_output_package.zip",
    }



# ==========================================================
# V316B COMPLETE CASE FOLDER IMPORT ROUTE - REAL IX GENERATOR
# Uses app.ix_output_generator.generate_package(work_dir, afi_filename).
# ==========================================================
from fastapi import UploadFile as _UploadFileV316B, File as _FileV316B, Form as _FormV316B
from typing import List as _ListV316B, Optional as _OptionalV316B
from fastapi.responses import JSONResponse as _JSONResponseV316B
import time as _time_v316b
import shutil as _shutil_v316b
import zipfile as _zipfile_v316b

@app.post("/api/intersect/import-case-folder-v316")
async def import_case_folder_v316b(
    files: _ListV316B[_UploadFileV316B] = _FileV316B(...),
    main_afi_path: _OptionalV316B[str] = _FormV316B(None),
):
    root = Path(__file__).resolve().parents[1]
    session_id = f"case_folder_v316_{int(_time_v316b.time())}"

    upload_root = root / "artifacts" / "case_folder_uploads" / session_id
    output_root = root / "artifacts" / "ix_output_packages" / session_id

    upload_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    saved = []

    for f in files:
        rel_name = (f.filename or f"uploaded_{len(saved)}").replace("\\", "/")
        parts = [p for p in Path(rel_name).parts if p not in ("..", "/", "\\") and ":" not in p]
        safe_rel = Path(*parts) if parts else Path(f"uploaded_{len(saved)}")

        dst = upload_root / safe_rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        with dst.open("wb") as out:
            _shutil_v316b.copyfileobj(f.file, out)

        saved.append(dst)

    afi_files = [p for p in saved if p.suffix.lower() == ".afi"]

    if not afi_files:
        return _JSONResponseV316B(
            status_code=400,
            content={
                "ok": False,
                "message": "No .AFI file detected in the uploaded folder.",
                "saved_files": len(saved),
            },
        )

    selected_afi = None

    if main_afi_path:
        normalized = main_afi_path.replace("\\", "/")
        for p in afi_files:
            rel = str(p.relative_to(upload_root)).replace("\\", "/")
            if rel == normalized:
                selected_afi = p
                break

    if selected_afi is None:
        if len(afi_files) > 1:
            return _JSONResponseV316B(
                status_code=400,
                content={
                    "ok": False,
                    "message": "Multiple .AFI files detected. Please select which AFI to use.",
                    "afi_files_detected": [str(p.relative_to(upload_root)).replace("\\", "/") for p in afi_files],
                },
            )
        selected_afi = afi_files[0]

    try:
        from app.ix_output_generator import generate_package

        result = generate_package(
            work_dir=selected_afi.parent,
            afi_filename=selected_afi.name,
            suffix="_404_RNF",
        )

    except Exception as exc:
        return _JSONResponseV316B(
            status_code=500,
            content={
                "ok": False,
                "message": f"IX output generator failed: {exc}",
                "selected_afi": str(selected_afi.relative_to(upload_root)).replace("\\", "/"),
            },
        )

    generated_files = result.get("generated_files") or []
    zip_file = result.get("zip_file")

    if not zip_file:
        return _JSONResponseV316B(
            status_code=500,
            content={
                "ok": False,
                "message": "Generator completed but did not return zip_file.",
                "generator_result": result,
            },
        )

    source_zip = selected_afi.parent / zip_file

    if not source_zip.exists():
        return _JSONResponseV316B(
            status_code=500,
            content={
                "ok": False,
                "message": f"Generator returned zip_file={zip_file}, but the file was not found.",
                "expected_path": str(source_zip),
                "generator_result": result,
            },
        )

    final_zip = output_root / zip_file
    _shutil_v316b.copy2(source_zip, final_zip)

    return {
        "ok": True,
        "session_id": session_id,
        "saved_files": len(saved),
        "afi_files_detected": [str(p.relative_to(upload_root)).replace("\\", "/") for p in afi_files],
        "original_afi": result.get("afi_file") or selected_afi.name,
        "modified_afi": result.get("modified_afi"),
        "generated_include_count": 2,
        "generated_includes": [
            result.get("ix_include"),
            result.get("fm_include"),
        ],
        "relperm_metadata": result.get("metadata"),
        "packaged_files": generated_files,
        "reservoir_name": result.get("reservoir_name"),
        "history_start": result.get("history_start"),
        "history_end": result.get("history_end"),
        "warnings": result.get("warnings", []),
        "download_url": f"/artifacts/ix_output_packages/{session_id}/{zip_file}",
        "generator_result": result,
    }



# ==========================================================
# V317 COMPLETE CASE FOLDER IMPORT ROUTE
# Robust AFI selection from dropdown + real ix_output_generator.
# ==========================================================
from fastapi import UploadFile as _UploadFileV317, File as _FileV317, Form as _FormV317
from typing import List as _ListV317, Optional as _OptionalV317
from fastapi.responses import JSONResponse as _JSONResponseV317
import time as _time_v317
import shutil as _shutil_v317

@app.post("/api/intersect/import-case-folder-v317")
async def import_case_folder_v317(
    files: _ListV317[_UploadFileV317] = _FileV317(...),
    main_afi_path: _OptionalV317[str] = _FormV317(None),
):
    root = Path(__file__).resolve().parents[1]
    session_id = f"case_folder_v317_{int(_time_v317.time())}"

    upload_root = root / "artifacts" / "case_folder_uploads" / session_id
    output_root = root / "artifacts" / "ix_output_packages" / session_id

    upload_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    saved = []

    for f in files:
        rel_name = (f.filename or f"uploaded_{len(saved)}").replace("\\", "/")
        parts = [p for p in Path(rel_name).parts if p not in ("..", "/", "\\") and ":" not in p]
        safe_rel = Path(*parts) if parts else Path(f"uploaded_{len(saved)}")

        dst = upload_root / safe_rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        with dst.open("wb") as out:
            _shutil_v317.copyfileobj(f.file, out)

        saved.append(dst)

    afi_files = [p for p in saved if p.suffix.lower() == ".afi"]

    if not afi_files:
        return _JSONResponseV317(
            status_code=400,
            content={
                "ok": False,
                "message": "No .AFI file detected in the uploaded folder.",
                "saved_files": len(saved),
            },
        )

    def rel(p: Path) -> str:
        return str(p.relative_to(upload_root)).replace("\\", "/")

    selected_afi = None
    selected_matches = []

    if main_afi_path:
        normalized = main_afi_path.replace("\\", "/").strip()

        # 1. Exact relative path match.
        selected_matches = [p for p in afi_files if rel(p) == normalized]

        # 2. Browser sometimes strips the top folder; allow suffix match.
        if not selected_matches:
            selected_matches = [p for p in afi_files if rel(p).endswith("/" + normalized) or rel(p).endswith(normalized)]

        # 3. Last fallback: filename match only.
        if not selected_matches:
            selected_matches = [p for p in afi_files if p.name == Path(normalized).name]

        if len(selected_matches) == 1:
            selected_afi = selected_matches[0]
        elif len(selected_matches) > 1:
            return _JSONResponseV317(
                status_code=400,
                content={
                    "ok": False,
                    "message": "The selected AFI name matched multiple files. Please select a more specific AFI path.",
                    "selected": normalized,
                    "matches": [rel(p) for p in selected_matches],
                    "afi_files_detected": [rel(p) for p in afi_files],
                },
            )

    if selected_afi is None:
        if len(afi_files) > 1:
            return _JSONResponseV317(
                status_code=400,
                content={
                    "ok": False,
                    "message": "Multiple .AFI files detected. Please select which AFI to use.",
                    "afi_files_detected": [rel(p) for p in afi_files],
                },
            )
        selected_afi = afi_files[0]

    try:
        from app.ix_output_generator import generate_package

        result = generate_package(
            work_dir=selected_afi.parent,
            afi_filename=selected_afi.name,
            suffix="_404_RNF",
        )

    except Exception as exc:
        return _JSONResponseV317(
            status_code=500,
            content={
                "ok": False,
                "message": f"IX output generator failed: {exc}",
                "selected_afi": rel(selected_afi),
                "afi_files_detected": [rel(p) for p in afi_files],
            },
        )

    zip_file = result.get("zip_file")
    if not zip_file:
        return _JSONResponseV317(
            status_code=500,
            content={
                "ok": False,
                "message": "Generator completed but did not return zip_file.",
                "generator_result": result,
            },
        )

    source_zip = selected_afi.parent / zip_file
    if not source_zip.exists():
        return _JSONResponseV317(
            status_code=500,
            content={
                "ok": False,
                "message": f"Generator returned zip_file={zip_file}, but it was not found.",
                "expected_path": str(source_zip),
                "generator_result": result,
            },
        )

    final_zip = output_root / zip_file
    _shutil_v317.copy2(source_zip, final_zip)

    return {
        "ok": True,
        "session_id": session_id,
        "saved_files": len(saved),
        "afi_files_detected": [rel(p) for p in afi_files],
        "selected_afi": rel(selected_afi),
        "original_afi": result.get("afi_file") or selected_afi.name,
        "modified_afi": result.get("modified_afi"),
        "generated_include_count": 2,
        "generated_includes": [
            result.get("ix_include"),
            result.get("fm_include"),
        ],
        "relperm_metadata": result.get("metadata"),
        "packaged_files": result.get("generated_files"),
        "reservoir_name": result.get("reservoir_name"),
        "history_start": result.get("history_start"),
        "history_end": result.get("history_end"),
        "warnings": result.get("warnings", []),
        "download_url": f"/artifacts/ix_output_packages/{session_id}/{zip_file}",
        "generator_result": result,
    }





# ==========================================================
# V320 COMPLETED INTERSECT RUN IMPORT WORKFLOW
# Imports a completed run folder, extracts dashboard-ready files
# using completed_run_extractor_v4.py, and allows activation.
# ==========================================================
from pydantic import BaseModel as _BaseModelV320
from fastapi.responses import JSONResponse as _JSONResponseV320
import subprocess as _subprocess_v320
import sys as _sys_v320
import uuid as _uuid_v320
import shutil as _shutil_v320
import json as _json_v320
from pathlib import Path as _PathV320


class _CompletedRunImportRequestV320(_BaseModelV320):
    folder_path: str
    case_name: str | None = None


class _CompletedRunActivateRequestV320(_BaseModelV320):
    import_id: str


_COMPLETED_RUN_IMPORT_ROOT_V320 = ROOT_DIR / "artifacts" / "completed_run_imports"
_COMPLETED_RUN_IMPORT_ROOT_V320.mkdir(parents=True, exist_ok=True)

_COMPLETED_RUN_ACTIVE_MARKER_V320 = ROOT_DIR / "artifacts" / "uploads" / "active_case.json"
_SAMPLE_MODEL_DIR_V320 = ROOT_DIR / "data" / "sample_model"


def _safe_import_id_v320(raw: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9_\-]", "_", str(raw or ""))[:80]


def _copy_tree_flat_v320(src_dir: _PathV320, dst_dir: _PathV320) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)

    for p in src_dir.iterdir():
        if not p.is_file():
            continue
        _shutil_v320.copy2(p, dst_dir / p.name)


def _completed_run_manifest_v320(import_id: str, extracted_dir: _PathV320, source_folder: _PathV320) -> dict:
    files = []

    for p in sorted(extracted_dir.iterdir()):
        if p.is_file():
            files.append({
                "name": p.name,
                "bytes": int(p.stat().st_size),
            })

    required_core = [
        "grid_dimensions.json",
        "CASE.SMSPEC",
        "CASE.UNSMRY",
        "TRANX.GRDECL",
        "TRANY.GRDECL",
        "TRANZ.GRDECL",
        "PERM_X.GRDECL",
        "PERM_Y.GRDECL",
        "PERM_Z.GRDECL",
        "PORO.GRDECL",
        "PRESSURE_INIT.GRDECL",
        "PRESSURE_EOH.GRDECL",
        "SWAT_INIT.GRDECL",
        "SWAT_EOH.GRDECL",
        "SOIL_INIT.GRDECL",
        "SOIL_EOH.GRDECL",
        "SGAS_INIT.GRDECL",
        "SGAS_EOH.GRDECL",
        "WELL_CONNECTIONS.ixf",
        "RELPERM.ixf",
        "SIMULATION.PRT",
    ]

    present = {f["name"] for f in files}
    missing = [x for x in required_core if x not in present]

    has_streamlines = any(x.startswith("STREAMLINES_INIT") for x in present) and any(x.startswith("STREAMLINES_EOH") for x in present)

    return {
        "ok": len(missing) == 0 and has_streamlines,
        "import_id": import_id,
        "source_folder": str(source_folder),
        "extracted_dir": str(extracted_dir),
        "files": files,
        "missing_core_files": missing,
        "has_streamlines": has_streamlines,
        "message": (
            "Completed run imported successfully. You can activate the case."
            if len(missing) == 0 and has_streamlines
            else "Completed run imported with warnings. Review missing files before activation."
        ),
    }


@app.post("/api/completed-run/import")
def api_completed_run_import_v320(req: _CompletedRunImportRequestV320):
    source_folder = _PathV320(req.folder_path).expanduser().resolve()

    if not source_folder.exists() or not source_folder.is_dir():
        return _JSONResponseV320(
            status_code=400,
            content={
                "ok": False,
                "message": f"Completed run folder not found or not a directory: {source_folder}",
            },
        )

    extractor = ROOT_DIR / "app" / "completed_run_extractor_v4.py"

    if not extractor.exists():
        return _JSONResponseV320(
            status_code=500,
            content={
                "ok": False,
                "message": "completed_run_extractor_v4.py not found in app folder.",
            },
        )

    import_id = _safe_import_id_v320(
        (req.case_name or source_folder.name) + "_" + _uuid_v320.uuid4().hex[:8]
    )

    import_dir = _COMPLETED_RUN_IMPORT_ROOT_V320 / import_id
    extracted_dir = import_dir / "standardized_case"
    import_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        _sys_v320.executable,
        str(extractor),
        "--folder",
        str(source_folder),
        "--out",
        str(extracted_dir),
    ]

    proc = _subprocess_v320.run(
        cmd,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=1800,
    )

    if proc.returncode != 0:
        return _JSONResponseV320(
            status_code=500,
            content={
                "ok": False,
                "message": "Completed run extraction failed.",
                "stdout": proc.stdout[-8000:],
                "stderr": proc.stderr[-8000:],
                "command": cmd,
            },
        )

    # Copy SMSPEC/UNSMRY if extractor did not already standardize them.
    smspec = sorted(source_folder.rglob("*.SMSPEC")) + sorted(source_folder.rglob("*.smspec"))
    unsmry = sorted(source_folder.rglob("*.UNSMRY")) + sorted(source_folder.rglob("*.unsmry"))

    if smspec and not (extracted_dir / "CASE.SMSPEC").exists():
        _shutil_v320.copy2(smspec[0], extracted_dir / "CASE.SMSPEC")

    if unsmry and not (extracted_dir / "CASE.UNSMRY").exists():
        _shutil_v320.copy2(unsmry[0], extracted_dir / "CASE.UNSMRY")

    manifest = _completed_run_manifest_v320(import_id, extracted_dir, source_folder)
    manifest["stdout"] = proc.stdout[-8000:]
    manifest["stderr"] = proc.stderr[-8000:]

    (import_dir / "manifest.json").write_text(
        _json_v320.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return manifest


@app.post("/api/completed-run/activate")
def api_completed_run_activate_v320(req: _CompletedRunActivateRequestV320):
    import_id = _safe_import_id_v320(req.import_id)
    import_dir = _COMPLETED_RUN_IMPORT_ROOT_V320 / import_id
    extracted_dir = import_dir / "standardized_case"
    manifest_path = import_dir / "manifest.json"

    if not extracted_dir.exists():
        return _JSONResponseV320(
            status_code=404,
            content={
                "ok": False,
                "message": f"Imported completed run not found: {import_id}",
            },
        )

    _SAMPLE_MODEL_DIR_V320.mkdir(parents=True, exist_ok=True)

    # Remove old standardized files to avoid mixed cases.
    for p in _SAMPLE_MODEL_DIR_V320.iterdir():
        if p.is_file():
            p.unlink()

    _copy_tree_flat_v320(extracted_dir, _SAMPLE_MODEL_DIR_V320)

    active_payload = {
        "ok": True,
        "active_case_type": "completed_run_import_v320",
        "import_id": import_id,
        "standardized_case_dir": str(extracted_dir),
        "sample_model_dir": str(_SAMPLE_MODEL_DIR_V320),
    }

    if manifest_path.exists():
        try:
            active_payload["manifest"] = _json_v320.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    _COMPLETED_RUN_ACTIVE_MARKER_V320.parent.mkdir(parents=True, exist_ok=True)
    _COMPLETED_RUN_ACTIVE_MARKER_V320.write_text(
        _json_v320.dumps(active_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    diagnostics_pipeline_report_v901 = _run_diagnostics_pipeline_after_activate_v901(
        reason="completed_run_activate_button"
    )

    return {
        "ok": True,
        "message": "Completed run case activated. Open the dashboard.",
        "import_id": import_id,
        "copied_to": str(_SAMPLE_MODEL_DIR_V320),
    }


@app.post("/api/completed-run/reset-active")
def api_completed_run_reset_active_v320():
    if _COMPLETED_RUN_ACTIVE_MARKER_V320.exists():
        _COMPLETED_RUN_ACTIVE_MARKER_V320.unlink()

    return {
        "ok": True,
        "message": "Active case marker removed. Landing page will be shown until a case is activated again.",
    }


@app.get("/api/completed-run/status")
def api_completed_run_status_v320():
    if not _COMPLETED_RUN_ACTIVE_MARKER_V320.exists():
        return {
            "ok": True,
            "active": False,
            "message": "No active completed-run case.",
        }

    try:
        payload = _json_v320.loads(_COMPLETED_RUN_ACTIVE_MARKER_V320.read_text(encoding="utf-8"))
    except Exception:
        payload = {}

    return {
        "ok": True,
        "active": True,
        "active_case": payload,
    }




# ==========================================================
# V331 LOCAL FOLDER PICKER
# Opens a native folder-selection dialog on the local machine.
# Used by the local landing workflow to select completed run folders.
# ==========================================================
from fastapi.responses import JSONResponse as _JSONResponseV331
from pydantic import BaseModel as _BaseModelV331


class _FolderPickerRequestV331(_BaseModelV331):
    title: str | None = None


@app.post("/api/local-folder-picker")
def api_local_folder_picker_v331(req: _FolderPickerRequestV331):
    try:
        import tkinter as _tk_v331
        from tkinter import filedialog as _filedialog_v331

        root = _tk_v331.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        selected = _filedialog_v331.askdirectory(
            title=req.title or "Select folder"
        )

        root.destroy()

        if not selected:
            return {
                "ok": False,
                "cancelled": True,
                "message": "Folder selection cancelled.",
                "folder_path": None,
            }

        return {
            "ok": True,
            "cancelled": False,
            "folder_path": selected,
        }

    except Exception as exc:
        return _JSONResponseV331(
            status_code=500,
            content={
                "ok": False,
                "message": f"Could not open local folder picker: {exc}",
            },
        )




# ==========================================================
# V334 ACTIVE CASE STATUS COMPAT
# Prevents landing 404 on /api/active-case-status.
# ==========================================================
@app.get("/api/active-case-status")
def api_active_case_status_v334():
    marker = ROOT_DIR / "artifacts" / "uploads" / "active_case.json"
    if not marker.exists():
        return {
            "ok": True,
            "active": False,
            "message": "No active case."
        }

    try:
        import json
        return {
            "ok": True,
            "active": True,
            "active_case": json.loads(marker.read_text(encoding="utf-8"))
        }
    except Exception:
        return {
            "ok": True,
            "active": True,
            "message": "Active case marker exists but could not be read."
        }




# ==========================================================
# V337 LOCAL CASE FOLDER WORKFLOW
# Clean local workflow:
# - scan selected INTERSECT case folder for AFI files
# - generate modified AFI + output include package from selected AFI
# ==========================================================
from pydantic import BaseModel as _BaseModelV337
from fastapi.responses import JSONResponse as _JSONResponseV337
import shutil as _shutil_v337
import uuid as _uuid_v337
import json as _json_v337
from pathlib import Path as _PathV337


class _ScanCaseFolderRequestV337(_BaseModelV337):
    folder_path: str


class _GenerateCasePackageRequestV337(_BaseModelV337):
    folder_path: str
    afi_relative_path: str


def _copy_case_text_files_v337(source_root: _PathV337, target_root: _PathV337) -> None:
    allowed_ext = {
        ".afi", ".ixf", ".inc", ".include", ".obsh", ".txt", ".csv",
        ".grdecl", ".dat", ".data", ".sch", ".rft", ".prn"
    }

    skip_dirs = {
        "404_RNF_EXTRACTED_GRDECL",
        "404_RNF_EXTRACTED",
        "__pycache__",
        ".git",
    }

    target_root.mkdir(parents=True, exist_ok=True)

    for p in source_root.rglob("*"):
        if not p.is_file():
            continue

        parts_upper = {part.upper() for part in p.parts}
        if any(skip.upper() in parts_upper for skip in skip_dirs):
            continue

        if p.suffix.lower() not in allowed_ext:
            continue

        try:
            if p.stat().st_size > 200_000_000:
                continue
        except Exception:
            continue

        rel = p.relative_to(source_root)
        dst = target_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        _shutil_v337.copy2(p, dst)


@app.post("/api/local-case-folder/scan")
def api_local_case_folder_scan_v337(req: _ScanCaseFolderRequestV337):
    folder = _PathV337(req.folder_path).expanduser().resolve()

    if not folder.exists() or not folder.is_dir():
        return _JSONResponseV337(
            status_code=400,
            content={
                "ok": False,
                "message": f"Folder not found or not a directory: {folder}",
            },
        )

    afi_files = []
    for p in sorted(folder.rglob("*.afi")):
        if "404_RNF_EXTRACTED_GRDECL" in str(p):
            continue
        try:
            rel = p.relative_to(folder).as_posix()
        except Exception:
            rel = p.name

        afi_files.append({
            "name": p.name,
            "relative_path": rel,
            "full_path": str(p),
            "size": p.stat().st_size,
        })

    return {
        "ok": True,
        "folder_path": str(folder),
        "afi_files": afi_files,
        "afi_count": len(afi_files),
        "message": (
            f"Found {len(afi_files)} AFI file(s)."
            if afi_files else
            "No AFI files found in selected folder."
        ),
    }


@app.post("/api/local-case-folder/generate-package")
def api_local_case_folder_generate_package_v337(req: _GenerateCasePackageRequestV337):
    try:
        from app.ix_output_generator import generate_package as _generate_package_v337

        source_root = _PathV337(req.folder_path).expanduser().resolve()

        if not source_root.exists() or not source_root.is_dir():
            return _JSONResponseV337(
                status_code=400,
                content={
                    "ok": False,
                    "message": f"Folder not found or not a directory: {source_root}",
                },
            )

        afi_rel = _PathV337(req.afi_relative_path)
        if afi_rel.is_absolute():
            try:
                afi_rel = afi_rel.resolve().relative_to(source_root)
            except Exception:
                afi_rel = _PathV337(afi_rel.name)

        source_afi = source_root / afi_rel

        if not source_afi.exists():
            return _JSONResponseV337(
                status_code=400,
                content={
                    "ok": False,
                    "message": f"Selected AFI not found: {source_afi}",
                },
            )

        package_id = f"local_case_{_uuid_v337.uuid4().hex[:8]}"
        package_root = ROOT_DIR / "artifacts" / "ix_output_packages" / package_id
        work_root = package_root / "case"

        _copy_case_text_files_v337(source_root, work_root)

        work_afi = work_root / afi_rel

        if not work_afi.exists():
            return _JSONResponseV337(
                status_code=500,
                content={
                    "ok": False,
                    "message": "AFI was not copied into the working package folder.",
                    "expected_afi": str(work_afi),
                },
            )

        result = _generate_package_v337(
            work_dir=work_afi.parent,
            afi_filename=work_afi.name,
        )

        generated_files = result.get("generated_files", [])
        zip_file = result.get("zip_file")

        download_base_path = work_afi.parent.relative_to(ROOT_DIR).as_posix()
        download_base = f"/{download_base_path}"

        result.update({
            "ok": True,
            "status": "success",
            "package_id": package_id,
            "source_folder": str(source_root),
            "selected_afi": afi_rel.as_posix(),
            "working_folder": str(work_afi.parent),
            "download_base": download_base,
            "generated_files": generated_files,
            "zip_file": zip_file,
            "message": "INTERSECT output package generated successfully.",
        })

        (package_root / "v337_manifest.json").write_text(
            _json_v337.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return result

    except Exception as exc:
        return _JSONResponseV337(
            status_code=500,
            content={
                "ok": False,
                "status": "error",
                "message": f"Package generation failed: {exc}",
            },
        )

# ==========================================================
# V419 DASHBOARD CHAT FINAL ENDPOINT
# Dedicated endpoint for dashboard Ask button.
# It bypasses legacy /api/chat shortcuts and always calls the
# final app.chat_router.answer_question stack.
# ==========================================================

def _safe_json_v419(obj):
    try:
        import math
        from pathlib import Path
    except Exception:
        math = None
        Path = None

    if obj is None:
        return None

    if isinstance(obj, (str, bool, int)):
        return obj

    if isinstance(obj, float):
        if math and (math.isnan(obj) or math.isinf(obj)):
            return None
        return obj

    if Path is not None and isinstance(obj, Path):
        return str(obj)

    if isinstance(obj, dict):
        return {str(k): _safe_json_v419(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [_safe_json_v419(x) for x in obj]

    try:
        if hasattr(obj, "item"):
            return _safe_json_v419(obj.item())
    except Exception:
        pass

    try:
        return str(obj)
    except Exception:
        return "<unserializable>"


@app.post("/api/chat-final")
async def api_chat_final_v419(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    message = (
        payload.get("message")
        or payload.get("question")
        or payload.get("prompt")
        or payload.get("input")
        or ""
    )

    try:
        from app.chat_router import answer_question

        response = answer_question(message)

        if not isinstance(response, dict):
            response = {
                "type": "visual_response",
                "intent": "chat_router_text_response",
                "answer": str(response),
                "ui_blocks": [],
            }

        response.setdefault("api_route_v419", "/api/chat-final -> app.chat_router.answer_question")
        return _safe_json_v419(response)

    except Exception as exc:
        return {
            "type": "visual_response",
            "intent": "api_chat_final_v419_error",
            "answer": "Dashboard chat-final endpoint failed before returning a normal agentic response.",
            "message": str(exc),
            "ui_blocks": [],
            "api_route_v419": "/api/chat-final -> app.chat_router.answer_question",
            "agent_trace": {
                "ApiChatFinalV419": {
                    "status": "error",
                    "error": str(exc),
                }
            },
            "interaction_edges": [
                {
                    "from": "DashboardAsk",
                    "to": "ApiChatFinalV419",
                    "reason": "Dashboard Ask routed to dedicated final chat endpoint.",
                }
            ],
        }

# END V419 DASHBOARD CHAT FINAL ENDPOINT

# ==========================================================
# V501 LANGGRAPH UNIVERSAL RESERVOIR ORCHESTRATOR ENDPOINT
# Real LangGraph StateGraph endpoint.
# ==========================================================

@app.post("/api/agent-chat-v501")
async def api_agent_chat_v501(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    message = (
        payload.get("message")
        or payload.get("question")
        or payload.get("prompt")
        or payload.get("input")
        or ""
    )

    try:
        from app.langgraph_universal_orchestrator_v501 import run_langgraph_universal_orchestrator_v501

        response = run_langgraph_universal_orchestrator_v501(message)

        if isinstance(response, dict):
            response.setdefault("api_route_v501", "/api/agent-chat-v501 -> LangGraphUniversalReservoirOrchestratorV501")
            return response

        return {
            "type": "reasoning_response",
            "intent": "text_response",
            "answer": str(response),
            "ui_blocks": [],
            "api_route_v501": "/api/agent-chat-v501 -> LangGraphUniversalReservoirOrchestratorV501",
        }

    except Exception as exc:
        return {
            "type": "reasoning_response",
            "intent": "api_agent_chat_v501_error",
            "answer": "LangGraph Universal Reservoir Orchestrator V501 failed before returning a normal response.",
            "message": str(exc),
            "ui_blocks": [],
            "api_route_v501": "/api/agent-chat-v501 -> LangGraphUniversalReservoirOrchestratorV501",
            "agent_trace": {
                "LangGraphUniversalReservoirOrchestratorV501": {
                    "status": "error",
                    "error": str(exc),
                }
            }
        }

# END V501 LANGGRAPH UNIVERSAL RESERVOIR ORCHESTRATOR ENDPOINT



# ==========================================================
# V600 HM SUMMARY HTML/PDF REPORT ROUTES
# ==========================================================
try:
    from app.hm_report_v600 import router as hm_report_router_v600
    app.include_router(hm_report_router_v600)
except Exception as _hm_report_v600_exc:
    print("[WARN] V600 HM report routes not loaded:", _hm_report_v600_exc)
# END V600 HM SUMMARY HTML/PDF REPORT ROUTES


# ==========================================================
# V602 SUBMISSION /RUN ENDPOINT
#
# Required by submission checklist:
# POST /run on port 8000
#
# Accepts JSON:
#   {"message": "..."}
#   {"query": "..."}
#   {"input": "..."}
#   {"prompt": "..."}
#
# Returns:
#   status, answer, type, intent, task_type, ui block metadata,
#   agent_trace and raw_response.
# ==========================================================

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse

    def _v602_extract_message_from_payload(payload):
        if not isinstance(payload, dict):
            raise ValueError("Request JSON body must be an object.")

        for key in ["message", "query", "question", "input", "prompt"]:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        if isinstance(payload.get("messages"), list):
            for item in reversed(payload["messages"]):
                if isinstance(item, dict):
                    content = item.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()

        raise ValueError("Missing message/query/question/input/prompt in request JSON.")

    @app.post("/run")
    async def run_submission_endpoint_v602(request: Request):
        try:
            payload = await request.json()
            message = _v602_extract_message_from_payload(payload)

            from app.langgraph_universal_orchestrator_v501 import (
                run_langgraph_universal_orchestrator_v501,
            )

            response = run_langgraph_universal_orchestrator_v501(message)

            if not isinstance(response, dict):
                response = {
                    "type": "reasoning_response",
                    "answer": str(response),
                    "ui_blocks": [],
                }

            task = ""
            ui = response.get("universal_intent_v500") or {}
            if isinstance(ui, dict):
                task = str(ui.get("task_type") or "")

            return JSONResponse(
                {
                    "status": "success",
                    "input": {
                        "message": message,
                    },
                    "output": {
                        "answer": response.get("answer") or response.get("message") or "",
                        "type": response.get("type"),
                        "intent": response.get("intent"),
                        "task_type": task,
                        "ui_blocks_count": len(response.get("ui_blocks") or []),
                        "ui_block_types": [
                            b.get("type")
                            for b in (response.get("ui_blocks") or [])
                            if isinstance(b, dict)
                        ],
                        "agent_trace": response.get("agent_trace") or {},
                    },
                    "raw_response": response,
                }
            )

        except Exception as exc:
            return JSONResponse(
                {
                    "status": "error",
                    "error": str(exc),
                },
                status_code=500,
            )

except Exception as _v602_run_endpoint_error:
    print("[WARN] V602 /run endpoint could not be registered:", _v602_run_endpoint_error)

# END V602 SUBMISSION /RUN ENDPOINT


# ==========================================================
# V605 FINAL SUBMISSION /RUN ROUTE OVERRIDE
#
# Purpose:
# Ensure POST /run returns the correct submission schema even if
# an older /run route was previously registered.
#
# It removes existing POST /run routes and registers the final one.
# ==========================================================

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse

    # Remove older POST /run routes if present.
    try:
        app.router.routes = [
            route for route in app.router.routes
            if not (
                getattr(route, "path", None) == "/run"
                and "POST" in getattr(route, "methods", set())
            )
        ]
    except Exception as _v605_route_cleanup_exc:
        print("[WARN] Could not clean old /run routes:", _v605_route_cleanup_exc)

    def _v605_extract_message_from_payload(payload):
        if not isinstance(payload, dict):
            raise ValueError("Request JSON body must be an object.")

        for key in ["message", "query", "question", "input", "prompt"]:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        if isinstance(payload.get("messages"), list):
            for item in reversed(payload["messages"]):
                if isinstance(item, dict):
                    content = item.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()

        raise ValueError("Missing message/query/question/input/prompt in request JSON.")

    @app.post("/run")
    async def run_submission_endpoint_v605(request: Request):
        try:
            payload = await request.json()
            message = _v605_extract_message_from_payload(payload)

            from app.langgraph_universal_orchestrator_v501 import (
                run_langgraph_universal_orchestrator_v501,
            )

            response = run_langgraph_universal_orchestrator_v501(message)

            if not isinstance(response, dict):
                response = {
                    "type": "reasoning_response",
                    "answer": str(response),
                    "ui_blocks": [],
                    "agent_trace": {},
                }

            task = ""
            ui = response.get("universal_intent_v500") or {}

            if isinstance(ui, dict):
                task = str(ui.get("task_type") or "")

            ui_blocks = response.get("ui_blocks") or []
            ui_block_types = [
                b.get("type")
                for b in ui_blocks
                if isinstance(b, dict)
            ]

            return JSONResponse(
                {
                    "status": "success",
                    "input": {
                        "message": message,
                    },
                    "output": {
                        "answer": response.get("answer") or response.get("message") or "",
                        "type": response.get("type"),
                        "intent": response.get("intent"),
                        "task_type": task,
                        "ui_blocks_count": len(ui_blocks),
                        "ui_block_types": ui_block_types,
                        "agent_trace": response.get("agent_trace") or {},
                    },
                    "raw_response": response,
                }
            )

        except Exception as exc:
            return JSONResponse(
                {
                    "status": "error",
                    "error": str(exc),
                },
                status_code=500,
            )

    print("[OK] V605 final /run route registered")

except Exception as _v605_run_endpoint_error:
    print("[WARN] V605 /run endpoint could not be registered:", _v605_run_endpoint_error)

# END V605 FINAL SUBMISSION /RUN ROUTE OVERRIDE



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


# --- 404_RNF_LLM_FINAL_WRITER_MIDDLEWARE_START ---
# True LLM final writer middleware.
# It rewrites only final JSON answer/response fields from chat endpoints.
# Frontend/dashboard DOM is not touched.

try:
    import json as _404_llm_json
    from fastapi.responses import JSONResponse as _404_llm_JSONResponse
    from app.final_answer_synthesizer_llm import synthesize_final_answer_payload as _404_synthesize_final_answer_payload

    @app.middleware("http")
    async def _404_llm_final_writer_middleware(request, call_next):
        response = await call_next(request)

        path = str(request.url.path or "")

        if path not in {
            "/run",
            "/api/agent-chat-v501",
            "/api/agent-chat",
            "/api/chat",
        }:
            return response

        content_type = str(response.headers.get("content-type", "")).lower()

        if "application/json" not in content_type:
            return response

        body = b""

        async for chunk in response.body_iterator:
            body += chunk

        try:
            payload = _404_llm_json.loads(body.decode("utf-8"))
        except Exception:
            return response

        new_payload = _404_synthesize_final_answer_payload(payload)

        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers.pop("content-type", None)

        return _404_llm_JSONResponse(
            content=new_payload,
            status_code=response.status_code,
            headers=headers,
        )

    print("[OK] LLM final writer middleware installed")

except Exception as _404_llm_final_writer_exc:
    print("[WARN] LLM final writer middleware not installed:", repr(_404_llm_final_writer_exc))

# --- 404_RNF_LLM_FINAL_WRITER_MIDDLEWARE_END ---

