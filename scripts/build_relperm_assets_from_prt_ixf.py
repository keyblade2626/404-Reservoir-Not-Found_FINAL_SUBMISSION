from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(".").resolve()
DATA = ROOT / "data" / "sample_model"
DIAG = ROOT / "artifacts" / "diagnosis"

PRT_PATH = DATA / "SIMULATION.PRT"
RELPERM_IXF = DATA / "RELPERM.ixf"
WELL_CONN = DATA / "WELL_CONNECTIONS.ixf"
SATNUM_PATH = DATA / "SATNUM.GRDECL"
FIPNUM_PATH = DATA / "FIPNUM.GRDECL"
GRID_DIMS = DATA / "grid_dimensions.json"
CONTEXT_CSV = DIAG / "well_property_driver_context.csv"

CURVES_JSON = DIAG / "relperm_curves.json"
MAPPING_JSON = DIAG / "relperm_region_mapping.json"
MAPPING_CSV = DIAG / "relperm_well_region_mapping.csv"

WELL_RE = re.compile(r'WellDef\s+"([^"]+)"', re.IGNORECASE)
CELL_RE = re.compile(r"\((\d+)\s+(\d+)\s+(\d+)\)")


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def read_grid_dims():
    if not GRID_DIMS.exists():
        return None

    try:
        d = json.loads(GRID_DIMS.read_text(encoding="utf-8-sig"))
    except Exception:
        return None

    for keys in [
        ("nx", "ny", "nz"),
        ("NX", "NY", "NZ"),
        ("i", "j", "k"),
        ("I", "J", "K"),
    ]:
        if all(k in d for k in keys):
            return int(d[keys[0]]), int(d[keys[1]]), int(d[keys[2]])

    dims = d.get("dimensions") or d.get("dims") or d.get("grid_dimensions")
    if isinstance(dims, list) and len(dims) >= 3:
        return int(dims[0]), int(dims[1]), int(dims[2])

    return None


def parse_grdecl_values(path: Path):
    txt = read_text(path)
    if not txt:
        return []

    vals = []
    for raw in txt.splitlines():
        line = raw.split("--", 1)[0].replace("/", " ")
        for tok in line.split():
            tok = tok.strip().strip(",")
            if not tok:
                continue

            # skip keywords
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tok):
                continue

            m = re.fullmatch(r"(\d+)\*([-+]?\d+(?:\.\d+)?(?:[Ee][-+]?\d+)?)", tok)
            if m:
                vals.extend([float(m.group(2))] * int(m.group(1)))
                continue

            try:
                vals.append(float(tok))
            except Exception:
                pass

    return vals


def cell_index(i, j, k, nx, ny, nz):
    i = int(i)
    j = int(j)
    k = int(k)

    if not (1 <= i <= nx and 1 <= j <= ny and 1 <= k <= nz):
        return None

    return (k - 1) * nx * ny + (j - 1) * nx + (i - 1)


def parse_prt_region_model_mapping():
    """
    Reads Intersect PRT RockRegionMapping.

    Expected PRT evidence:
    ROCKNUM_1_RRT_01 -> ROCKNUM_1_RRT_01
    ROCKNUM_1_RRT_02 -> ROCKNUM_1_RRT_02
    ...
    """

    txt = read_text(PRT_PATH)
    mapping = {}

    # Most robust: table rows like:
    # | ROCKNUM_1_RRT_01 | ROCKNUM_1_RRT_01 |
    for line in txt.splitlines():
        if "RRT_" not in line.upper():
            continue

        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) >= 2:
            left = cells[0]
            right = cells[1]
            m = re.search(r"RRT[_-]?(\d+)", left, re.IGNORECASE)
            if m:
                n = int(m.group(1))
                # Use right as model if it looks like a model name, otherwise left.
                model = right if "RRT" in right.upper() else left
                mapping[n] = model

    # Fallback from created model names.
    if not mapping:
        names = sorted(set(re.findall(r"ROCKNUM_\d+_RRT_(\d+)", txt, flags=re.IGNORECASE)))
        for n in names:
            mapping[int(n)] = f"ROCKNUM_1_RRT_{int(n):02d}"

    return mapping


def parse_relperm_ixf_curves():
    """
    Parses dashboard-compatible SaturationFunction blocks from RELPERM.ixf.
    Produces models[model]["tables"][curve]["rows"].
    """

    txt = read_text(RELPERM_IXF)
    models = {}

    current_model = None
    current_table = None

    for raw in txt.splitlines():
        line = raw.strip()

        m_model = re.search(r'SaturationFunction\s+"([^"]+)"', line, flags=re.IGNORECASE)
        if m_model:
            current_model = m_model.group(1).strip()
            models.setdefault(current_model, {"tables": {}, "summary": {}})
            current_table = None
            continue

        if current_model:
            m_rel = re.search(r'RelPerm\s+"([^"]+)"\s*\[', line, flags=re.IGNORECASE)
            if m_rel:
                current_table = m_rel.group(1).strip()
                models[current_model]["tables"].setdefault(
                    current_table,
                    {
                        "rows": [],
                        "x_column": "Saturation",
                        "y_column": "RelPerm",
                    },
                )
                continue

            if line.startswith("]"):
                current_table = None
                continue

            if current_table:
                nums = re.findall(r"[-+]?\d+(?:\.\d+)?(?:[Ee][-+]?\d+)?", line)
                if len(nums) >= 2:
                    try:
                        x = float(nums[0])
                        y = float(nums[1])
                        models[current_model]["tables"][current_table]["rows"].append(
                            {"saturation": x, "relperm": y}
                        )
                    except Exception:
                        pass

    # Add summary
    for model, payload in models.items():
        tables = payload.get("tables", {})
        payload["summary"] = {
            "table_count": len(tables),
            "tables": sorted(tables.keys()),
        }

    return {"models": models, "source": str(RELPERM_IXF).replace("\\", "/")}


def parse_well_connections():
    """
    Reads well completion cells from WELL_CONNECTIONS.ixf.

    Example:
    WellDef "HW-28" {
       WellToCellConnections [
          (135 128 1) "OPENHOLE" ... Transmissibility ...
    """

    txt = read_text(WELL_CONN)
    by_well = defaultdict(list)
    current_well = None

    for raw in txt.splitlines():
        line = raw.strip()

        m_well = WELL_RE.search(line)
        if m_well:
            current_well = m_well.group(1).strip().upper()
            continue

        if not current_well:
            continue

        m_cell = CELL_RE.search(line)
        if not m_cell:
            continue

        i, j, k = map(int, m_cell.groups())

        # try to capture transmissibility as the last numeric before direction K/I/J
        nums = re.findall(r"[-+]?\d+(?:\.\d+)?(?:[Ee][-+]?\d+)?", line[m_cell.end():])
        weight = 1.0
        if nums:
            try:
                # In this exported IXF, transmissibility is near the end before penetration direction.
                weight = abs(float(nums[-1]))
                if weight == 0:
                    weight = 1.0
            except Exception:
                weight = 1.0

        by_well[current_well].append(
            {
                "i": i,
                "j": j,
                "k": k,
                "weight": weight,
            }
        )

    return dict(by_well)


def choose_region_property():
    """
    Prefer SATNUM. If missing or unusable, use FIPNUM.
    This avoids generic dominant fallback and uses completed-cell region property.
    """

    sat = parse_grdecl_values(SATNUM_PATH)
    if sat:
        return "SATNUM", sat, SATNUM_PATH

    fip = parse_grdecl_values(FIPNUM_PATH)
    if fip:
        return "FIPNUM", fip, FIPNUM_PATH

    return None, [], None


def model_name_for_region(region_number, prt_models, relperm_models):
    n = int(region_number)

    # 1. PRT mapping first.
    if n in prt_models:
        candidate = prt_models[n]
        if candidate in relperm_models:
            return candidate

        # Sometimes PRT has ROCKNUM_1_RRT_01 but IXF model name differs slightly.
        m = re.search(r"RRT[_-]?(\d+)", candidate, re.IGNORECASE)
        if m:
            nn = int(m.group(1))
            for model in relperm_models:
                mm = re.search(r"(\d+)", model)
                if mm and int(mm.group(1)) == nn:
                    return model

        return candidate

    # 2. Model name containing RRT_NN.
    for model in relperm_models:
        if re.search(rf"RRT[_-]?0*{n}\b", model, re.IGNORECASE):
            return model

    # 3. Numeric model order fallback only when there is a clear model list.
    relperm_models_sorted = sorted(relperm_models)
    if 1 <= n <= len(relperm_models_sorted):
        return relperm_models_sorted[n - 1]

    return None


def update_context_csv(mapping_by_well):
    if not CONTEXT_CSV.exists():
        return

    with CONTEXT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames or [])

    add_fields = [
        "region_property",
        "region_property_value",
        "relperm_region",
        "saturation_model",
        "relperm_model",
        "relperm_mapping_source",
        "relperm_mapping_confidence",
        "relperm_completed_cells_used",
    ]

    for f in add_fields:
        if f not in fields:
            fields.append(f)

    for row in rows:
        well = str(row.get("well", "")).strip().upper()
        m = mapping_by_well.get(well)
        if not m:
            continue

        row["region_property"] = m.get("region_property", "")
        row["region_property_value"] = str(m.get("region_property_value", ""))
        row["relperm_region"] = str(m.get("relperm_region", ""))
        row["saturation_model"] = str(m.get("saturation_model", ""))
        row["relperm_model"] = str(m.get("saturation_model", ""))
        row["relperm_mapping_source"] = str(m.get("mapping_source", ""))
        row["relperm_mapping_confidence"] = str(m.get("mapping_confidence", ""))
        row["relperm_completed_cells_used"] = str(m.get("completed_cells_used", ""))

    with CONTEXT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    DIAG.mkdir(parents=True, exist_ok=True)

    dims = read_grid_dims()
    if not dims:
        raise SystemExit("Cannot read grid_dimensions.json, cannot map completion cells to property regions.")

    nx, ny, nz = dims
    print("[INFO] Grid dimensions:", dims)

    region_property_name, region_values, region_path = choose_region_property()
    if not region_values:
        raise SystemExit("No SATNUM.GRDECL or FIPNUM.GRDECL values found.")

    print("[INFO] Region property used:", region_property_name, region_path)
    print("[INFO] Region values count:", len(region_values))

    expected = nx * ny * nz
    if len(region_values) < expected:
        print("[WARN] Region values fewer than grid cells:", len(region_values), "expected", expected)

    prt_models = parse_prt_region_model_mapping()
    print("[INFO] PRT region->model mapping:", prt_models)

    curves = parse_relperm_ixf_curves()
    relperm_models = sorted((curves.get("models") or {}).keys())
    print("[INFO] RELPERM.ixf models:", relperm_models)

    if not relperm_models:
        raise SystemExit("No SaturationFunction models parsed from RELPERM.ixf")

    well_connections = parse_well_connections()
    print("[INFO] Wells with connections:", len(well_connections))

    mapping_by_well = {}
    table = []

    for well, conns in sorted(well_connections.items()):
        weighted = defaultdict(float)
        used = 0

        for c in conns:
            idx = cell_index(c["i"], c["j"], c["k"], nx, ny, nz)
            if idx is None or idx >= len(region_values):
                continue

            try:
                region_value = int(round(float(region_values[idx])))
            except Exception:
                continue

            if region_value <= 0:
                continue

            weighted[region_value] += float(c.get("weight") or 1.0)
            used += 1

        if not weighted:
            continue

        total_w = sum(weighted.values()) or 1.0
        region_value, region_weight = sorted(weighted.items(), key=lambda x: x[1], reverse=True)[0]
        confidence = round(region_weight / total_w, 4)

        model = model_name_for_region(region_value, prt_models, relperm_models)

        if not model:
            continue

        rec = {
            "well": well,
            "region_property": region_property_name,
            "region_property_value": region_value,
            "relperm_region": f"RRT_{int(region_value):02d}",
            "saturation_model": model,
            "relperm_model": model,
            "mapping_source": f"WELL_CONNECTIONS.ixf + {region_property_name}.GRDECL + SIMULATION.PRT RockRegionMapping",
            "mapping_confidence": confidence,
            "completed_cells_used": used,
            "region_weight_distribution": {str(k): v for k, v in sorted(weighted.items())},
        }

        mapping_by_well[well] = rec
        table.append(rec)

    if not mapping_by_well:
        raise SystemExit("No well-to-relperm mappings could be created.")

    mapping_payload = {
        "source": "generated_from_prt_ixf_completed_cells",
        "grid_dimensions": {"nx": nx, "ny": ny, "nz": nz},
        "region_property": region_property_name,
        "region_property_file": str(region_path).replace("\\", "/"),
        "prt_file": str(PRT_PATH).replace("\\", "/"),
        "relperm_ixf": str(RELPERM_IXF).replace("\\", "/"),
        "well_connections": str(WELL_CONN).replace("\\", "/"),
        "prt_region_model_mapping": {str(k): v for k, v in prt_models.items()},
        "by_well": mapping_by_well,
        "table": table,
    }

    CURVES_JSON.write_text(json.dumps(curves, indent=2, ensure_ascii=False), encoding="utf-8")
    MAPPING_JSON.write_text(json.dumps(mapping_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    with MAPPING_CSV.open("w", encoding="utf-8", newline="") as f:
        fields = [
            "well",
            "region_property",
            "region_property_value",
            "relperm_region",
            "saturation_model",
            "mapping_source",
            "mapping_confidence",
            "completed_cells_used",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for rec in table:
            writer.writerow({k: rec.get(k, "") for k in fields})

    update_context_csv(mapping_by_well)

    print("[OK] Wrote", CURVES_JSON)
    print("[OK] Wrote", MAPPING_JSON)
    print("[OK] Wrote", MAPPING_CSV)
    print("[OK] Updated", CONTEXT_CSV)
    print("[INFO] Wells mapped:", len(mapping_by_well))

    for well in sorted(mapping_by_well)[:20]:
        rec = mapping_by_well[well]
        print(f"  {well}: {rec['region_property']}={rec['region_property_value']} -> {rec['saturation_model']} confidence={rec['mapping_confidence']}")


if __name__ == "__main__":
    main()
