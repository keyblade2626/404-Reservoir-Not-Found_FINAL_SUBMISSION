from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(".").resolve()
REPORT = Path(".\\__relperm_prt_logic_diagnosis_20260604_142853")
REPORT.mkdir(exist_ok=True)

candidates = [
    ROOT / "data" / "sample_model" / "SIMULATION.PRT",
    ROOT / "data" / "sample_model" / "RELPERM.ixf",
    ROOT / "data" / "sample_model" / "SATNUM.GRDECL",
    ROOT / "data" / "sample_model" / "WELL_CONNECTIONS.ixf",
    ROOT / "artifacts" / "diagnosis" / "well_property_driver_context.csv",
    ROOT / "artifacts" / "diagnosis" / "smart_well_recommendations.json",
    ROOT / "artifacts" / "diagnosis" / "smart_well_recommendations.csv",
    ROOT / "artifacts" / "diagnosis" / "water_driver_diagnosis.json",
    ROOT / "artifacts" / "diagnosis" / "driver_diagnosis_summary.json",
]

keywords = [
    "RELPERM",
    "RELATIVE",
    "PERMEABILITY",
    "SATNUM",
    "SCAL",
    "SWOF",
    "SGOF",
    "SOF",
    "SGFN",
    "SWFN",
    "SCALE",
    "REGION",
    "REGIONS",
    "TABDIMS",
    "EQLNUM",
    "PVTNUM",
    "ENDPOINT",
    "KRW",
    "KRO",
    "KRG",
]

def safe_read(path: Path, max_chars: int | None = None):
    if not path.exists():
        return ""
    data = path.read_text(encoding="utf-8-sig", errors="ignore")
    if max_chars:
        return data[:max_chars]
    return data

def write(path: Path, text: str):
    path.write_text(text, encoding="utf-8")

def extract_keyword_context(path: Path, before=4, after=8, max_hits=300):
    if not path.exists():
        return f"MISSING: {path}\n"

    lines = path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    out = []
    hit_count = 0

    for i, line in enumerate(lines):
        up = line.upper()
        if any(k in up for k in keywords):
            hit_count += 1
            if hit_count > max_hits:
                out.append(f"\n--- STOPPED AFTER {max_hits} HITS ---\n")
                break
            out.append(f"\n--- HIT {hit_count} | {path} | line {i+1} ---")
            s = max(0, i - before)
            e = min(len(lines), i + after + 1)
            for j in range(s, e):
                out.append(f"{j+1}: {lines[j]}")

    if not out:
        return f"No keyword hits found in {path}\n"

    return "\n".join(out)

def inspect_csv(path: Path):
    if not path.exists():
        return f"MISSING: {path}\n"

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = reader.fieldnames or []

    interesting = [
        c for c in fields
        if any(x in c.lower() for x in [
            "well", "satnum", "region", "relperm", "scal", "curve", "model",
            "driver", "recommend", "property", "completion", "cell"
        ])
    ]

    out = []
    out.append(f"CSV: {path}")
    out.append(f"Rows: {len(rows)}")
    out.append(f"Columns: {fields}")
    out.append(f"Interesting columns: {interesting}")
    out.append("")
    out.append("First 10 rows interesting fields:")

    for row in rows[:10]:
        out.append(json.dumps({c: row.get(c) for c in interesting}, ensure_ascii=False))

    return "\n".join(out)

def inspect_json(path: Path):
    if not path.exists():
        return f"MISSING: {path}\n"

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return f"JSON READ ERROR {path}: {exc}\n"

    out = []
    out.append(f"JSON: {path}")
    if isinstance(data, dict):
        out.append(f"Top-level keys: {list(data.keys())}")
        for key in list(data.keys())[:20]:
            val = data[key]
            if isinstance(val, (dict, list)):
                out.append(f"- {key}: {type(val).__name__}, len={len(val)}")
            else:
                out.append(f"- {key}: {repr(val)[:200]}")
    elif isinstance(data, list):
        out.append(f"List length: {len(data)}")
        for item in data[:5]:
            out.append(json.dumps(item, ensure_ascii=False)[:1000])
    return "\n".join(out)

# 1. Keyword context from PRT and RELPERM
for path in [
    ROOT / "data" / "sample_model" / "SIMULATION.PRT",
    ROOT / "data" / "sample_model" / "RELPERM.ixf",
    ROOT / "data" / "sample_model" / "WELL_CONNECTIONS.ixf",
]:
    report_name = path.name.replace(".", "_") + "_keyword_context.txt"
    write(REPORT / report_name, extract_keyword_context(path))

# 2. Inspect diagnosis artifacts
csv_reports = []
for path in [
    ROOT / "artifacts" / "diagnosis" / "well_property_driver_context.csv",
    ROOT / "artifacts" / "diagnosis" / "smart_well_recommendations.csv",
]:
    csv_reports.append(inspect_csv(path))

write(REPORT / "diagnosis_csv_inspection.txt", "\n\n" + ("\n\n" + "="*100 + "\n\n").join(csv_reports))

json_reports = []
for path in [
    ROOT / "artifacts" / "diagnosis" / "smart_well_recommendations.json",
    ROOT / "artifacts" / "diagnosis" / "water_driver_diagnosis.json",
    ROOT / "artifacts" / "diagnosis" / "driver_diagnosis_summary.json",
    ROOT / "metadata.json",
]:
    json_reports.append(inspect_json(path))

write(REPORT / "diagnosis_json_inspection.txt", "\n\n" + ("\n\n" + "="*100 + "\n\n").join(json_reports))

# 3. Try to locate exact backend route/function that emits the message.
target_phrases = [
    "No relperm model could be assigned",
    "RelPerm sensitivity not recommended",
    "Need well-to-region mapping",
]
hits = []
for path in list((ROOT / "app").glob("**/*.py")) + list((ROOT / "web").glob("**/*.js")):
    if "__pycache__" in str(path):
        continue
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    for phrase in target_phrases:
        if phrase in text:
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if phrase in line:
                    s = max(0, i - 20)
                    e = min(len(lines), i + 30)
                    hits.append(f"\n--- {path} | phrase={phrase} | line {i+1} ---")
                    for j in range(s, e):
                        hits.append(f"{j+1}: {lines[j]}")

write(REPORT / "exact_error_source_context.txt", "\n".join(hits) if hits else "Exact error phrase not found in app/web source.\n")

print("[OK] Wrote reports in", REPORT)
print("[OK] Key files to open:")
for name in [
    "exact_error_source_context.txt",
    "SIMULATION_PRT_keyword_context.txt",
    "RELPERM_ixf_keyword_context.txt",
    "diagnosis_csv_inspection.txt",
    "diagnosis_json_inspection.txt",
]:
    print(" -", REPORT / name)
