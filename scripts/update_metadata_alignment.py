import json
from pathlib import Path

p = Path("metadata.json")
m = json.loads(p.read_text(encoding="utf-8-sig"))

m["last_updated"] = "2026-06-04"

runtime = m.setdefault("runtime", {})
runtime["recommended_judge_url"] = "http://127.0.0.1:8000/demo-dashboard"
runtime["full_import_workflow_url"] = "http://127.0.0.1:8000"
runtime["requires_manual_data_import_for_demo"] = False
runtime["demo_data_preloaded"] = True

env = m.setdefault("environment", {})
env["python_recommended_version"] = ">=3.13"
env["requirements_install_command"] = "pip install -r requirements.txt"

notes = env.setdefault("notes", [])
extra_notes = [
    "Python 3.13 or higher is recommended.",
    "If using an older Python version, resdata==6.2.9 may require a different compatible version.",
    "For judging, open the ready demo dashboard directly at /demo-dashboard.",
    "The full INTERSECT / IX import workflow is supported from the landing page but is not required for evaluating the bundled demo.",
    "Activating a newly imported completed run triggers the deterministic diagnostics pipeline and may take a few minutes depending on model size."
]

for note in extra_notes:
    if note not in notes:
        notes.append(note)

demo = m.setdefault("demo", {})
demo["preloaded_case"] = True
demo["manual_import_required"] = False
demo["recommended_judge_url"] = "http://127.0.0.1:8000/demo-dashboard"
demo["full_import_workflow_supported"] = True
demo["full_import_workflow_url"] = "http://127.0.0.1:8000"
demo["judge_note"] = "Judges are encouraged to open /demo-dashboard directly because the submitted demo case has already completed import and diagnostic post-processing."

m["diagnostics_pipeline"] = {
    "type": "deterministic_post_processing",
    "trigger": "Activate case after completed-run import",
    "not_llm_generated": True,
    "typical_runtime": "A few minutes; local tests ranged from a few minutes to approximately 5-6 minutes depending on model size.",
    "modules": [
        "app.driver_diagnosis",
        "app.export_oil_profile_diagnostics",
        "app.export_gas_profile_diagnostics",
        "app.export_bhp_profile_diagnostics",
        "app.bhp_observed_filter",
        "app.well_activity_classifier",
        "app.smart_well_recommendation_agent"
    ],
    "outputs": [
        "artifacts/diagnosis/well_property_driver_context.csv",
        "artifacts/diagnosis/water_driver_diagnosis.json",
        "artifacts/diagnosis/driver_diagnosis_summary.json",
        "artifacts/diagnosis/oil_profile_diagnostics.json",
        "artifacts/diagnosis/gas_profile_diagnostics.json",
        "artifacts/diagnosis/bhp_profile_diagnostics.json",
        "artifacts/diagnosis/bhp_observed_filter_report.json",
        "artifacts/diagnosis/well_activity_classification.json",
        "artifacts/diagnosis/well_activity_classification.csv",
        "artifacts/diagnosis/smart_well_recommendations.json",
        "artifacts/diagnosis/smart_well_recommendations.csv"
    ]
}

p.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
print("[OK] metadata.json aligned")
