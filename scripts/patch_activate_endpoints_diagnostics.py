from pathlib import Path
import re

p = Path("app/main.py")
txt = p.read_text(encoding="utf-8-sig")

helper = r'''

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

'''

if "_run_diagnostics_pipeline_after_activate_v901" not in txt:
    anchor = '@app.post("/api/activate-uploaded-case/{upload_id}")'
    idx = txt.find(anchor)
    if idx == -1:
        anchor = 'class _CompletedRunActivateRequestV320'
        idx = txt.find(anchor)

    if idx == -1:
        txt = txt + "\n" + helper
    else:
        txt = txt[:idx] + helper + "\n" + txt[idx:]

def insert_before_success_return(text: str, marker: str, call_code: str) -> str:
    if call_code.strip() in text:
        return text

    marker_pos = text.find(marker)
    if marker_pos == -1:
        print(f"[WARN] Marker not found: {marker}")
        return text

    # Find nearest previous return line before the success marker.
    return_pos = text.rfind("\n    return ", 0, marker_pos)
    if return_pos == -1:
        print(f"[WARN] Could not find return before marker: {marker}")
        return text

    return text[:return_pos + 1] + call_code + "\n" + text[return_pos + 1:]

completed_run_call = '''    diagnostics_pipeline_report_v901 = _run_diagnostics_pipeline_after_activate_v901(
        reason="completed_run_activate_button"
    )
'''

uploaded_case_call = '''    diagnostics_pipeline_report_v901 = _run_diagnostics_pipeline_after_activate_v901(
        reason="uploaded_case_activate_button"
    )
'''

# Completed-run landing-page Activate button success response.
txt = insert_before_success_return(
    txt,
    '"message": "Completed run case activated. Open the dashboard."',
    completed_run_call,
)

# Uploaded-case activation success response.
txt = insert_before_success_return(
    txt,
    '"activated_case_dir"',
    uploaded_case_call,
)

p.write_text(txt, encoding="utf-8")

print("[OK] main.py patched")
print("completed_run_activate_button:", "completed_run_activate_button" in txt)
print("uploaded_case_activate_button:", "uploaded_case_activate_button" in txt)
print("helper:", "_run_diagnostics_pipeline_after_activate_v901" in txt)
