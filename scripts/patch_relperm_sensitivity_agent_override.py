from pathlib import Path

p = Path("app/relperm_sensitivity_agent.py")
txt = p.read_text(encoding="utf-8-sig")

marker = "# --- 404_RNF_FINAL_RELPERM_PRT_IXF_MAPPING_OVERRIDE ---"

if marker in txt:
    print("[OK] RelPerm override already present, not appending twice.")
else:
    patch = r'''

# --- 404_RNF_FINAL_RELPERM_PRT_IXF_MAPPING_OVERRIDE ---
# This compatibility layer reconnects the RelPerm dashboard action to the
# PRT/IXF/completed-cell mapping generated in artifacts/diagnosis.
# It intentionally does NOT assign a generic dominant model to all wells.

def _404_rnf_load_json_safe(path):
    try:
        from pathlib import Path as _Path
        import json as _json
        p = _Path(path)
        if not p.exists():
            return None
        return _json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _404_rnf_relperm_mapping_path():
    try:
        return ROOT / "artifacts" / "diagnosis" / "relperm_region_mapping.json"
    except Exception:
        from pathlib import Path as _Path
        return _Path(".") / "artifacts" / "diagnosis" / "relperm_region_mapping.json"


def _404_rnf_relperm_curves_path():
    try:
        return ROOT / "artifacts" / "diagnosis" / "relperm_curves.json"
    except Exception:
        from pathlib import Path as _Path
        return _Path(".") / "artifacts" / "diagnosis" / "relperm_curves.json"


def _404_rnf_norm_well_local(value):
    try:
        return norm_well(value)
    except Exception:
        return str(value or "").strip().upper()


# Override load_curves so the dashboard always reads the generated IXF curves.
def load_curves():
    data = _404_rnf_load_json_safe(_404_rnf_relperm_curves_path())
    if isinstance(data, dict) and isinstance(data.get("models"), dict):
        return data
    return {"models": {}}


# Override mapping loader in the exact shape used by the existing agent.
def load_mapping():
    data = _404_rnf_load_json_safe(_404_rnf_relperm_mapping_path()) or {}

    table = data.get("table") or []
    by_well = data.get("by_well") or {}

    # Normalize by_well keys.
    normalized_by_well = {}
    for k, v in by_well.items():
        if isinstance(v, dict):
            normalized_by_well[_404_rnf_norm_well_local(k)] = v

    by_model = {}
    for row in table:
        if not isinstance(row, dict):
            continue
        model = row.get("saturation_model") or row.get("relperm_model") or row.get("model")
        if model:
            by_model.setdefault(model, []).append(row)

    return {
        "source": data.get("source", "generated_from_prt_ixf_completed_cells"),
        "table": table,
        "by_well": normalized_by_well,
        "by_model": by_model,
        "raw": data,
    }


def load_region_table():
    mapping = load_mapping()
    return mapping.get("table") or []


def infer_region_for_well(row, mapping=None):
    mapping = mapping or load_mapping()

    well = None
    if isinstance(row, dict):
        well = (
            row.get("well")
            or row.get("WELL")
            or row.get("Well")
            or row.get("well_name")
            or row.get("WELL_NAME")
        )

    target = _404_rnf_norm_well_local(well)

    # 1) Direct well mapping generated from PRT/IXF/completed cells.
    rec = (mapping.get("by_well") or {}).get(target)
    if isinstance(rec, dict) and (rec.get("saturation_model") or rec.get("relperm_model")):
        model = rec.get("saturation_model") or rec.get("relperm_model")
        out = dict(rec)
        out["well"] = target
        out["saturation_model"] = model
        out["relperm_model"] = model
        out.setdefault("mapping_source", "generated_from_prt_ixf_completed_cells")
        return out

    # 2) Direct row columns, if CSV already has them.
    if isinstance(row, dict):
        for key in [
            "saturation_model",
            "relperm_model",
            "model",
            "relperm_region_model",
        ]:
            value = row.get(key)
            if value:
                return {
                    "well": target,
                    "saturation_model": str(value),
                    "relperm_model": str(value),
                    "mapping_source": f"diagnostic_context_column:{key}",
                }

    # 3) No generic fallback.
    return {
        "well": target,
        "saturation_model": None,
        "relperm_model": None,
        "mapping_source": "not_mapped",
        "reason": "No PRT/IXF completed-cell mapping found for this well.",
    }

# --- END 404_RNF_FINAL_RELPERM_PRT_IXF_MAPPING_OVERRIDE ---
'''
    p.write_text(txt.rstrip() + "\n\n" + patch + "\n", encoding="utf-8")
    print("[OK] Appended RelPerm PRT/IXF mapping compatibility override.")
