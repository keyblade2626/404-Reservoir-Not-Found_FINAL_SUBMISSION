from __future__ import annotations

import csv
import json
import importlib
import inspect
from pathlib import Path

ROOT = Path(".").resolve()
REPORT = Path(".\\__relperm_candidate_eligibility_diagnosis_20260604_144541")
REPORT.mkdir(exist_ok=True)

CONTEXT = ROOT / "artifacts" / "diagnosis" / "well_property_driver_context.csv"
WATER_DIAG = ROOT / "artifacts" / "diagnosis" / "water_driver_diagnosis.json"
RELPERM_MAPPING = ROOT / "artifacts" / "diagnosis" / "relperm_region_mapping.json"
RELPERM_CURVES = ROOT / "artifacts" / "diagnosis" / "relperm_curves.json"

mod = importlib.import_module("app.relperm_sensitivity_agent")

def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        return default

def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

def read_context_rows():
    with CONTEXT.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames or []

rows, fields = read_context_rows()
water_diag_raw = load_json(WATER_DIAG, [])
mapping_raw = load_json(RELPERM_MAPPING, {})
curves_raw = load_json(RELPERM_CURVES, {})

water_by_well = {}
if isinstance(water_diag_raw, list):
    for item in water_diag_raw:
        if isinstance(item, dict) and item.get("well"):
            water_by_well[str(item["well"]).upper()] = item

print("[INFO] Context rows:", len(rows))
print("[INFO] Context columns containing relperm/model/region/SATNUM:")
print([c for c in fields if any(x in c.lower() for x in ["relperm", "saturation", "region", "satnum", "model"])])

print("[INFO] Water diagnosis wells:", len(water_by_well))
print("[INFO] RelPerm mapping top-level keys:", list(mapping_raw.keys()) if isinstance(mapping_raw, dict) else type(mapping_raw))
print("[INFO] RelPerm models:", list((curves_raw.get("models") or {}).keys()) if isinstance(curves_raw, dict) else [])

results = []

for row in rows:
    well = str(row.get("well") or row.get("WELL") or row.get("Well") or "").strip().upper()
    if not well:
        continue

    water = water_by_well.get(well, {})

    item = {
        "well": well,
        "context": {
            "well_activity_status": row.get("well_activity_status"),
            "well_role": row.get("well_role"),
            "water_hm_score": row.get("water_hm_score"),
            "water_hm_class": row.get("water_hm_class"),
            "water_direction": row.get("water_direction"),
            "water_timing_issue": row.get("water_timing_issue"),
            "mean_swat_eoh": row.get("mean_swat_eoh"),
            "delta_swat": row.get("delta_swat"),
            "saturation_model": row.get("saturation_model"),
            "relperm_model": row.get("relperm_model"),
            "relperm_region": row.get("relperm_region"),
            "region_property": row.get("region_property"),
            "region_property_value": row.get("region_property_value"),
        },
        "water_driver_diagnosis": {
            "action_category": water.get("action_category"),
            "primary_action": water.get("primary_action"),
            "interpretation": water.get("interpretation"),
            "confidence": water.get("confidence"),
            "water_direction": water.get("water_direction"),
            "water_timing_issue": water.get("water_timing_issue"),
        },
        "backend": {},
    }

    try:
        backend_row = mod.get_row_for_well(well)
        mapping = mod.load_mapping()
        curves = mod.load_curves()
        reg = mod.infer_region_for_well(backend_row, mapping)
        item["backend"]["region_mapping"] = reg
        item["backend"]["model_found"] = reg.get("saturation_model") or reg.get("relperm_model")
        item["backend"]["model_exists_in_curves"] = item["backend"]["model_found"] in (curves.get("models") or {})

        if hasattr(mod, "classify_water_bias"):
            try:
                item["backend"]["target_bias"] = mod.classify_water_bias(backend_row)
            except Exception as exc:
                item["backend"]["target_bias_error"] = repr(exc)

        if hasattr(mod, "determine_relperm_action"):
            try:
                bias = item["backend"].get("target_bias")
                if bias is not None:
                    item["backend"]["determine_relperm_action"] = mod.determine_relperm_action(bias)
            except Exception as exc:
                item["backend"]["determine_relperm_action_error"] = repr(exc)

        # Try common candidate function names.
        candidate = None
        for fn in [
            "evaluate_relperm_candidate",
            "evaluate_relperm_sensitivity_candidate",
            "build_relperm_candidate_for_well",
            "find_relperm_candidate_for_well",
        ]:
            if hasattr(mod, fn):
                try:
                    candidate = getattr(mod, fn)(well)
                    item["backend"]["candidate_function"] = fn
                    item["backend"]["candidate_result"] = candidate
                    break
                except Exception as exc:
                    item["backend"][f"{fn}_error"] = repr(exc)

        if hasattr(mod, "build_relperm_curve_view_for_well"):
            try:
                view = mod.build_relperm_curve_view_for_well(well)
                item["backend"]["curve_view_summary"] = {
                    "ok": view.get("ok"),
                    "well": view.get("well"),
                    "model": view.get("model"),
                    "message": view.get("message"),
                    "keys": list(view.keys()),
                }
            except Exception as exc:
                item["backend"]["curve_view_error"] = repr(exc)

    except Exception as exc:
        item["backend"]["fatal_error"] = repr(exc)

    results.append(item)

write_json(REPORT / "relperm_candidate_eligibility_by_well.json", results)

# Console summary
print("\n=== RELPERM ELIGIBILITY SUMMARY ===")

eligible_count = 0
mapped_count = 0
model_exists_count = 0
review_diag_count = 0

for item in results:
    well = item["well"]
    model = item["backend"].get("model_found")
    exists = item["backend"].get("model_exists_in_curves")
    cand = item["backend"].get("candidate_result") or {}
    eligible = cand.get("eligible") if isinstance(cand, dict) else None
    msg = cand.get("message") if isinstance(cand, dict) else None
    action_cat = item["water_driver_diagnosis"].get("action_category")
    bias = item["backend"].get("target_bias")
    action = item["backend"].get("determine_relperm_action")

    if model:
        mapped_count += 1
    if exists:
        model_exists_count += 1
    if eligible:
        eligible_count += 1
    if action_cat == "review_relperm_or_well_connection":
        review_diag_count += 1

    print(f"\n{well}")
    print(f"  water_driver action_category : {action_cat}")
    print(f"  context water_direction      : {item['context'].get('water_direction')}")
    print(f"  backend model                : {model}")
    print(f"  model exists in curves        : {exists}")
    print(f"  target_bias                  : {bias}")
    print(f"  relperm action               : {action}")
    print(f"  candidate eligible           : {eligible}")
    print(f"  candidate message            : {msg}")

print("\n=== COUNTS ===")
print("wells:", len(results))
print("mapped_count:", mapped_count)
print("model_exists_count:", model_exists_count)
print("water diagnosis review_relperm_or_well_connection:", review_diag_count)
print("eligible_count:", eligible_count)

# Save source snippets for the functions we need.
snippets = []
for fn in [
    "classify_water_bias",
    "determine_relperm_action",
    "evaluate_relperm_candidate",
    "evaluate_relperm_sensitivity_candidate",
    "find_best_relperm_candidate",
    "build_relperm_curve_view_for_well",
]:
    if hasattr(mod, fn):
        try:
            snippets.append(f"\n\n--- FUNCTION {fn} ---\n")
            snippets.append(inspect.getsource(getattr(mod, fn)))
        except Exception as exc:
            snippets.append(f"\n\n--- FUNCTION {fn} source unavailable: {exc} ---\n")

Path(REPORT / "relperm_candidate_function_sources.txt").write_text("".join(snippets), encoding="utf-8")

print("\n[OK] Wrote:")
print(" -", REPORT / "relperm_candidate_eligibility_by_well.json")
print(" -", REPORT / "relperm_candidate_function_sources.txt")

if eligible_count == 0 and review_diag_count > 0 and mapped_count > 0:
    print("\n[DIAGNOSIS] Mapping exists and water diagnosis has RelPerm-review wells, but candidate eligibility is zero.")
    print("[DIAGNOSIS] This means the eligibility/action filter is too strict or disconnected from water_driver_diagnosis.json.")
