import json
import importlib

mod = importlib.import_module("app.relperm_sensitivity_agent")

mapping = mod.load_mapping()
print("[INFO] mapping source:", mapping.get("source"))
print("[INFO] mapped wells:", len(mapping.get("by_well") or {}))

for well in ["HW-28", "HW-32", "HW-10", "HW-25"]:
    row = mod.get_row_for_well(well)
    reg = mod.infer_region_for_well(row, mapping)
    print("\nWELL", well)
    print("REGION:", json.dumps(reg, indent=2, ensure_ascii=False)[:1200])

    if not reg.get("saturation_model"):
        raise SystemExit(f"{well} still has no saturation_model")

    if hasattr(mod, "evaluate_relperm_candidate"):
        result = mod.evaluate_relperm_candidate(well)
    elif hasattr(mod, "evaluate_relperm_sensitivity_candidate"):
        result = mod.evaluate_relperm_sensitivity_candidate(well)
    else:
        result = None

    if result is not None:
        print("CANDIDATE:", json.dumps({
            "ok": result.get("ok"),
            "eligible": result.get("eligible"),
            "well": result.get("well"),
            "model": result.get("model"),
            "message": result.get("message"),
        }, indent=2, ensure_ascii=False))

    if hasattr(mod, "build_relperm_curve_view_for_well"):
        view = mod.build_relperm_curve_view_for_well(well)
        print("CURVE VIEW:", json.dumps({
            "ok": view.get("ok"),
            "well": view.get("well"),
            "model": view.get("model"),
            "message": view.get("message"),
            "curve_groups": len(view.get("curve_groups") or view.get("groups") or []),
        }, indent=2, ensure_ascii=False))

print("\n[OK] RelPerm backend mapping test passed")
