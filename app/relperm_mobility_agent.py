from pathlib import Path
import re
import json
import csv
from collections import Counter, defaultdict


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data" / "sample_model"
OUT_DIR = ROOT / "artifacts" / "relperm"

IXF_PATH = MODEL_DIR / "RELPERM.ixf"
PRT_PATH = MODEL_DIR / "SIMULATION.PRT"
FIPNUM_PATH = MODEL_DIR / "FIPNUM.GRDECL"


def safe_float(v):
    try:
        return float(str(v).strip())
    except Exception:
        return None


def safe_int(v):
    try:
        x = float(str(v).strip())
        if abs(x - round(x)) < 1e-9:
            return int(round(x))
        return None
    except Exception:
        return None


def read_text(path: Path):
    if not path.exists():
        raise FileNotFoundError(str(path))
    return path.read_text(encoding="utf-8", errors="ignore")


# ==========================================================
# IXF PARSER
# ==========================================================

def parse_table_block(block_text: str):
    """
    Parses lines inside:
    RelPerm "Krw_v_Sw" [
        Saturation RelPerm
        0.1 0.0
        ...
    ]
    """
    rows = []
    lines = block_text.splitlines()

    for line in lines:
        s = line.strip()
        if not s:
            continue

        if s.startswith("#"):
            continue

        if any(x in s.lower() for x in ["saturation", "relperm", "cappressure"]):
            continue

        nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
        if len(nums) >= 2:
            rows.append({
                "saturation": float(nums[0]),
                "value": float(nums[1]),
            })

    return rows


def extract_named_blocks(text: str, keyword: str):
    """
    Extracts blocks like:
    SaturationFunction "Model_01" { ... }
    or:
    RelPerm "Krw_v_Sw" [ ... ]
    """
    out = []

    if keyword == "SaturationFunction":
        pattern = re.compile(r'SaturationFunction\s+"([^"]+)"\s*\{', re.IGNORECASE)
        open_char = "{"
        close_char = "}"
    else:
        pattern = re.compile(rf'{keyword}\s+"([^"]+)"\s*\[', re.IGNORECASE)
        open_char = "["
        close_char = "]"

    for m in pattern.finditer(text):
        name = m.group(1)
        start = m.end()
        depth = 1
        i = start

        while i < len(text) and depth > 0:
            if text[i] == open_char:
                depth += 1
            elif text[i] == close_char:
                depth -= 1
            i += 1

        block = text[start:i - 1]
        out.append((name, block))

    return out


def summarize_curve(rows):
    if not rows:
        return {}

    sats = [r["saturation"] for r in rows]
    vals = [r["value"] for r in rows]

    first_nonzero_sat = None
    for r in rows:
        if r["value"] > 0:
            first_nonzero_sat = r["saturation"]
            break

    return {
        "points": len(rows),
        "sat_min": min(sats),
        "sat_max": max(sats),
        "value_min": min(vals),
        "value_max": max(vals),
        "first_nonzero_saturation": first_nonzero_sat,
        "endpoint_value": vals[-1] if vals else None,
    }


def parse_relperm_ixf(path: Path = IXF_PATH):
    text = read_text(path)

    models = {}

    sat_blocks = extract_named_blocks(text, "SaturationFunction")

    for model_name, model_block in sat_blocks:
        model = {
            "model_name": model_name,
            "tables": {},
            "summary": {},
        }

        for keyword in ["RelPerm", "CapPressure"]:
            for table_name, table_block in extract_named_blocks(model_block, keyword):
                rows = parse_table_block(table_block)
                model["tables"][table_name] = {
                    "type": keyword,
                    "rows": rows,
                    "summary": summarize_curve(rows),
                }

        # Higher-level indicators.
        krw = model["tables"].get("Krw_v_Sw", {}).get("rows", [])
        krow = model["tables"].get("Krow_v_So", {}).get("rows", [])
        krg = model["tables"].get("Krg_v_Sg", {}).get("rows", [])
        krog = model["tables"].get("Krog_v_So", {}).get("rows", [])

        model["summary"] = {
            "table_count": len(model["tables"]),
            "has_oil_water": bool(krw and krow),
            "has_gas_oil": bool(krg and krog),
            "swc_estimate": krw[0]["saturation"] if krw else None,
            "krw_first_nonzero_sw": summarize_curve(krw).get("first_nonzero_saturation") if krw else None,
            "krw_endpoint": krw[-1]["value"] if krw else None,
            "krow_endpoint": krow[-1]["value"] if krow else None,
            "sgc_estimate": krg[0]["saturation"] if krg else None,
            "krg_endpoint": krg[-1]["value"] if krg else None,
            "krog_endpoint": krog[-1]["value"] if krog else None,
        }

        models[model_name] = model

    return {
        "source_file": str(path),
        "model_count": len(models),
        "models": models,
    }


# ==========================================================
# PRT PARSER
# ==========================================================

def parse_prt_region_mapping(path: Path = PRT_PATH):
    text = read_text(path)

    created_regions = []
    mapping_rows = []

    # Extract rows like:
    # |     0 | ROCKNUM_1_RRT_01 | ROCK_COMPACTION_REGION.ROCKNUM_1 |
    # next line includes SATURATION_FUNCTION_DRAINAGE_TABLE_NO.RRT_01
    lines = text.splitlines()

    for idx, line in enumerate(lines):
        if "|" not in line:
            continue

        parts = [p.strip() for p in line.split("|")[1:-1]]

        if len(parts) >= 3:
            index = safe_int(parts[0])
            region_name = parts[1] if len(parts) > 1 else ""

            if index is not None and region_name and "RRT_" in region_name.upper():
                combined = parts[2] if len(parts) > 2 else ""

                # Look at following lines for RRT_xx.
                lookahead = "\n".join(lines[idx:idx+4])
                rrt = None
                m_rrt = re.search(r'RRT[_\s-]?(\d+)', lookahead, re.IGNORECASE)
                if m_rrt:
                    rrt = f"RRT_{int(m_rrt.group(1)):02d}"

                rocknum = None
                m_rock = re.search(r'ROCKNUM[_\s-]?(\d+)', lookahead, re.IGNORECASE)
                if m_rock:
                    rocknum = int(m_rock.group(1))

                created_regions.append({
                    "index": index,
                    "region_name": region_name,
                    "rrt": rrt,
                    "rocknum": rocknum,
                    "combined_region_text": combined,
                })

        # Extract mapping rows:
        # | ROCKNUM_1_RRT_01 | ROCKNUM_1_RRT_01 |
        if len(parts) >= 2:
            a, b = parts[0], parts[1]
            if "RRT_" in a.upper() and "RRT_" in b.upper() and not re.match(r"^\d+$", a):
                mapping_rows.append({
                    "region_name": a,
                    "model_name_from_prt": b,
                })

    # Deduplicate
    seen = set()
    unique_regions = []
    for r in created_regions:
        key = (r["index"], r["region_name"])
        if key in seen:
            continue
        seen.add(key)
        unique_regions.append(r)

    seen = set()
    unique_mapping = []
    for r in mapping_rows:
        key = (r["region_name"], r["model_name_from_prt"])
        if key in seen:
            continue
        seen.add(key)
        unique_mapping.append(r)

    return {
        "source_file": str(path),
        "created_region_count": len(unique_regions),
        "created_regions": unique_regions,
        "region_model_mapping_count": len(unique_mapping),
        "region_model_mapping": unique_mapping,
    }


# ==========================================================
# FIPNUM / REGION PROPERTY PARSER
# ==========================================================

def expand_grdecl_tokens(tokens):
    """
    Supports ECLIPSE compressed syntax:
    10*1 3*2 4.0 /
    """
    values = []

    for tok in tokens:
        t = tok.strip()
        if not t or t == "/":
            continue

        if "/" in t:
            t = t.replace("/", "")
            if not t:
                continue

        m = re.match(r"^(\d+)\*(.+)$", t)
        if m:
            n = int(m.group(1))
            val = safe_float(m.group(2))
            if val is not None:
                values.extend([val] * n)
        else:
            val = safe_float(t)
            if val is not None:
                values.append(val)

    return values


def parse_grdecl_property(path: Path = FIPNUM_PATH):
    text = read_text(path)

    # Remove comments
    clean_lines = []
    for line in text.splitlines():
        s = line.split("--")[0].split("#")[0].strip()
        if s:
            clean_lines.append(s)

    clean = "\n".join(clean_lines)

    # Drop first keyword if present
    tokens = re.split(r"\s+", clean)
    if tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", tokens[0]) and "*" not in tokens[0]:
        prop_name = tokens[0].upper()
        data_tokens = tokens[1:]
    else:
        prop_name = path.stem.upper()
        data_tokens = tokens

    values = expand_grdecl_tokens(data_tokens)

    int_values = []
    for v in values:
        if v is not None:
            if abs(v - round(v)) < 1e-9:
                int_values.append(int(round(v)))
            else:
                int_values.append(v)

    counts = Counter(int_values)

    unique_values = sorted(counts.keys(), key=lambda x: float(x))

    return {
        "source_file": str(path),
        "property_name": prop_name,
        "cell_count": len(int_values),
        "unique_value_count": len(unique_values),
        "unique_values": unique_values,
        "value_counts": {str(k): v for k, v in counts.items()},
        "min_value": min(unique_values) if unique_values else None,
        "max_value": max(unique_values) if unique_values else None,
    }


# ==========================================================
# AUTO-MAPPING
# ==========================================================

def model_number(model_name):
    m = re.search(r"(\d+)", str(model_name))
    return int(m.group(1)) if m else None


def rrt_number(rrt_or_name):
    m = re.search(r"RRT[_\s-]?(\d+)", str(rrt_or_name), re.IGNORECASE)
    return int(m.group(1)) if m else None


def propose_mapping(ixf_data, prt_data, prop_data):
    models = sorted(ixf_data["models"].keys(), key=lambda x: model_number(x) or 999999)
    regions = sorted(prt_data["created_regions"], key=lambda r: r.get("index", 999999))
    prop_values = prop_data.get("unique_values") or []

    rows = []

    model_by_number = {}
    for m in models:
        n = model_number(m)
        if n is not None:
            model_by_number[n] = m

    # Decide if property values are 0-based or 1-based
    # If prop values match PRT index exactly, use index.
    prt_indices = [r["index"] for r in regions]
    prop_set = set(int(v) for v in prop_values if isinstance(v, int))

    zero_based_match = prop_set and set(prt_indices).issubset(prop_set)
    one_based_match = prop_set and set([i + 1 for i in prt_indices]).issubset(prop_set)

    if zero_based_match:
        value_mode = "property_value_equals_prt_index"
    elif one_based_match:
        value_mode = "property_value_equals_prt_index_plus_1"
    else:
        value_mode = "sequential_order"

    for pos, region in enumerate(regions):
        idx = region.get("index")
        rrt = region.get("rrt")
        rrt_no = rrt_number(rrt or region.get("region_name"))

        # Most likely model number follows RRT number:
        # RRT_01 -> Model_01
        model = model_by_number.get(rrt_no)

        # fallback by sequence
        if model is None and pos < len(models):
            model = models[pos]

        if value_mode == "property_value_equals_prt_index":
            prop_value = idx
        elif value_mode == "property_value_equals_prt_index_plus_1":
            prop_value = idx + 1
        else:
            prop_value = prop_values[pos] if pos < len(prop_values) else idx

        confidence = "High"
        reasons = []

        if model is not None and rrt_no is not None and model_number(model) == rrt_no:
            reasons.append(f"RRT_{rrt_no:02d} matches {model}.")
        else:
            confidence = "Medium"
            reasons.append("Model assigned by sequence fallback.")

        if len(models) == len(regions):
            reasons.append("IXF model count matches PRT region count.")
        else:
            confidence = "Medium"
            reasons.append(f"IXF model count ({len(models)}) differs from PRT region count ({len(regions)}).")

        if prop_data.get("unique_value_count") == len(regions):
            reasons.append("Property unique values count matches PRT region count.")
        else:
            confidence = "Medium"
            reasons.append(
                f"Property unique values count ({prop_data.get('unique_value_count')}) differs from PRT region count ({len(regions)})."
            )

        rows.append({
            "property_name": prop_data.get("property_name"),
            "property_value": prop_value,
            "prt_index": idx,
            "prt_region_name": region.get("region_name"),
            "rrt": rrt,
            "rocknum": region.get("rocknum"),
            "saturation_model": model,
            "mapping_confidence": confidence,
            "mapping_reason": " ".join(reasons),
        })

    return {
        "mapping_strategy": value_mode,
        "mapping_count": len(rows),
        "rows": rows,
    }


# ==========================================================
# EXPORT
# ==========================================================

def export_relperm_artifacts():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ixf = parse_relperm_ixf()
    prt = parse_prt_region_mapping()
    prop = parse_grdecl_property()
    mapping = propose_mapping(ixf, prt, prop)

    (OUT_DIR / "relperm_curves.json").write_text(json.dumps(ixf, indent=2), encoding="utf-8")
    (OUT_DIR / "prt_region_mapping.json").write_text(json.dumps(prt, indent=2), encoding="utf-8")
    (OUT_DIR / "fipnum_property_summary.json").write_text(json.dumps(prop, indent=2), encoding="utf-8")
    (OUT_DIR / "relperm_region_mapping_proposed.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")

    csv_path = OUT_DIR / "relperm_region_mapping_proposed.csv"
    fields = [
        "property_name",
        "property_value",
        "prt_index",
        "prt_region_name",
        "rrt",
        "rocknum",
        "saturation_model",
        "mapping_confidence",
        "mapping_reason",
    ]

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in mapping["rows"]:
            writer.writerow({k: r.get(k, "") for k in fields})

    summary = {
        "ok": True,
        "ixf_models": ixf["model_count"],
        "prt_regions": prt["created_region_count"],
        "property_name": prop["property_name"],
        "property_unique_values": prop["unique_value_count"],
        "mapping_count": mapping["mapping_count"],
        "mapping_strategy": mapping["mapping_strategy"],
        "outputs": {
            "relperm_curves": str(OUT_DIR / "relperm_curves.json"),
            "prt_region_mapping": str(OUT_DIR / "prt_region_mapping.json"),
            "fipnum_summary": str(OUT_DIR / "fipnum_property_summary.json"),
            "mapping_json": str(OUT_DIR / "relperm_region_mapping_proposed.json"),
            "mapping_csv": str(csv_path),
        }
    }

    (OUT_DIR / "relperm_intake_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return summary


if __name__ == "__main__":
    summary = export_relperm_artifacts()
    print(json.dumps(summary, indent=2))
