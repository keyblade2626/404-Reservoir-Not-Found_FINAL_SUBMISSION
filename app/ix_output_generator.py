from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


FM_OUTPUT_IXF_NAME = "404_RNF_MINIMAL_OUTPUT_REQUEST_FM_EDIT.ixf"
IX_STREAMLINE_IXF_NAME = "404_RNF_STREAMLINE_MGR_IX_EDIT.ixf"
RELPERM_METADATA_JSON = "404_RNF_RELPERM_REGION_MAPPING_USED_BY_GENERATOR.json"

SATURATION_MAPPING_KEYWORDS = {
    "DRAINAGE_SATURATION_FUNCTION",
    "IMBIBITION_SATURATION_FUNCTION",
    "DRAINAGE_SATURATION_FUNCTION_X",
    "DRAINAGE_SATURATION_FUNCTION_Y",
    "DRAINAGE_SATURATION_FUNCTION_Z",
    "IMBIBITION_SATURATION_FUNCTION_X",
    "IMBIBITION_SATURATION_FUNCTION_Y",
    "IMBIBITION_SATURATION_FUNCTION_Z",
}


def read_text_flexible(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="latin-1", errors="ignore")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def safe_name(name: str) -> str:
    name = Path(name).name
    return re.sub(r"[^A-Za-z0-9_.\- ]+", "_", name)


def detect_reservoir_name_from_afi(afi_path: Path) -> Optional[str]:
    text = read_text_flexible(afi_path)
    matches = re.findall(r'reservoir\s*=\s*"([^"]+)"', text, flags=re.I)
    if not matches:
        return None
    return Counter(matches).most_common(1)[0][0]


def ix_include_line(reservoir_name: Optional[str]) -> str:
    if reservoir_name:
        return f'INCLUDE "{IX_STREAMLINE_IXF_NAME}" {{ simulation="ix" type="ixf" reservoir="{reservoir_name}" }}'
    return f'INCLUDE "{IX_STREAMLINE_IXF_NAME}" {{ simulation="ix" type="ixf" }}'


def fm_include_line() -> str:
    return f'INCLUDE "{FM_OUTPUT_IXF_NAME}" {{ simulation="fm" type="ixf" }}'


def parse_date_candidate(value: str) -> Optional[datetime]:
    raw = value.strip().strip('"').strip("'").strip()
    raw = re.sub(r"\s+", " ", raw)

    formats = [
        "%d-%b-%Y", "%d-%B-%Y",
        "%d/%b/%Y", "%d/%B/%Y",
        "%d %b %Y", "%d %B %Y",
        "%Y-%m-%d", "%Y/%m/%d",
        "%d/%m/%Y", "%d-%m-%Y",
        "%m/%d/%Y", "%m-%d-%Y",
        "%d-%b-%y", "%d-%B-%y",
        "%d/%m/%y", "%m/%d/%y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue

    return None


def format_ix_date(dt: datetime) -> str:
    return dt.strftime("%d-%b-%Y")


def _normalize_include_ref(ref: str) -> str:
    ref = (ref or "").strip().strip('"').strip("'").strip()
    ref = ref.replace("\\", "/")
    return ref


def _resolve_referenced_file(ref: str, current_folder: Path, root_folder: Path) -> Optional[Path]:
    """
    Resolve an AFI/IXF referenced file.

    Browser upload caveat:
    if only the .afi is uploaded, sibling files are not available unless they were also
    uploaded/copied to the server workspace or the AFI contains absolute paths accessible
    from this local Python process.
    """
    ref = _normalize_include_ref(ref)
    if not ref:
        return None

    candidates: list[Path] = []

    raw = Path(ref)

    if raw.is_absolute():
        candidates.append(raw)

    candidates.append(current_folder / ref)
    candidates.append(root_folder / ref)
    candidates.append(root_folder / raw.name)

    for c in candidates:
        try:
            if c.exists() and c.is_file():
                return c.resolve()
        except Exception:
            pass

    # Last fallback: search by basename inside workspace.
    try:
        matches = list(root_folder.rglob(raw.name))
        for m in matches:
            if m.is_file():
                return m.resolve()
    except Exception:
        pass

    return None


def _extract_referenced_paths_from_text(text: str) -> list[str]:
    refs: list[str] = []

    # Standard AFI/IX include syntax:
    # INCLUDE "file.ixf" { ... }
    # INCLUDE 'file.ixf'
    for m in re.finditer(r'\bINCLUDE\b\s+["\']([^"\']+)["\']', text, flags=re.I):
        refs.append(m.group(1))

    # More generic quoted file references.
    for m in re.finditer(r'["\']([^"\']+\.(?:afi|ixf|obsh|prt|txt|inc|dat|data|csv))["\']', text, flags=re.I):
        refs.append(m.group(1))

    # Assignment-style paths, e.g. File = something.ixf
    for m in re.finditer(r'\b(?:FILE|FILENAME|PATH)\b\s*=\s*["\']?([^"\'\s;{}]+\.(?:afi|ixf|obsh|prt|txt|inc|dat|data|csv))', text, flags=re.I):
        refs.append(m.group(1))

    # De-duplicate while preserving order.
    seen = set()
    out = []
    for r in refs:
        key = _normalize_include_ref(r).lower()
        if key and key not in seen:
            seen.add(key)
            out.append(r)

    return out


def extract_include_files_from_afi(afi_path: Path) -> list[Path]:
    """
    Recursively discover files referenced by the AFI and nested includes.
    """
    root_folder = afi_path.parent
    discovered: list[Path] = []
    queue: list[Path] = [afi_path.resolve()]
    seen: set[str] = set()

    max_files = 500
    max_size = 50_000_000

    while queue and len(discovered) < max_files:
        current = queue.pop(0)
        key = str(current).lower()

        if key in seen:
            continue

        seen.add(key)

        try:
            if not current.exists() or not current.is_file():
                continue
            if current.stat().st_size > max_size:
                continue
        except Exception:
            continue

        discovered.append(current)

        try:
            current_text = read_text_flexible(current)
        except Exception:
            continue

        for ref in _extract_referenced_paths_from_text(current_text):
            resolved = _resolve_referenced_file(ref, current.parent, root_folder)
            if resolved is not None and str(resolved).lower() not in seen:
                queue.append(resolved)

    return discovered


def extract_dates_from_file(path: Path) -> list[datetime]:
    if path.suffix.lower() in {".gsg", ".unsmry", ".smspec"}:
        return []

    try:
        text = read_text_flexible(path)
    except Exception:
        return []

    candidates: list[str] = []

    for m in re.finditer(
        r'\bDATE\s+"?([0-9]{1,2}[-/ ][A-Za-z]{3,9}[-/ ][0-9]{2,4}|[0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4})"?',
        text,
        flags=re.I,
    ):
        candidates.append(m.group(1))

    patterns = [
        r'\b[0-9]{1,2}[-/ ][A-Za-z]{3,9}[-/ ][0-9]{2,4}\b',
        r'\b[0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}\b',
        r'\b[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4}\b',
    ]

    for pattern in patterns:
        for m in re.finditer(pattern, text):
            candidates.append(m.group(0))

    parsed = []
    for c in candidates:
        dt = parse_date_candidate(c)
        if dt:
            parsed.append(dt)

    return sorted(set(parsed))


def infer_history_dates(folder: Path, afi_path: Path) -> tuple[str, str, list[str]]:
    included_files = extract_include_files_from_afi(afi_path)

    candidate_files: list[Path] = []
    candidate_files.extend([p for p in included_files if p.suffix.lower() == ".obsh"])
    candidate_files.extend([
        p for p in included_files
        if re.search(r"hist|history|historical|obsh", p.name, flags=re.I)
        and p not in candidate_files
    ])
    candidate_files.extend([
        p for p in included_files
        if p.suffix.lower() in {".afi", ".ixf", ".obsh"}
        and p not in candidate_files
    ])

    for ext in ("*.obsh", "*.ixf", "*.afi", "*.txt", "*.csv", "*.prt", "*.inc", "*.dat", "*.data"):
        for p in folder.rglob(ext):
            if p not in candidate_files and p.is_file():
                try:
                    if p.stat().st_size < 50_000_000:
                        candidate_files.append(p)
                except Exception:
                    pass

    all_dates: list[datetime] = []
    sources: list[str] = []

    for p in candidate_files:
        dates = extract_dates_from_file(p)
        if dates:
            all_dates.extend(dates)
            sources.append(f"{p.name}: {format_ix_date(min(dates))} -> {format_ix_date(max(dates))}")

    if not all_dates:
        discovered_names = [p.name for p in candidate_files[:30]]
        raise RuntimeError(
            "Could not infer history start/end dates automatically after inspecting the AFI, "
            "its accessible referenced INCLUDE files, and the current workspace. "
            "This usually means the AFI references files that were not uploaded/copied into the workspace "
            "or uses local paths not accessible to the Python process. "
            f"Files inspected: {discovered_names}"
        )

    start = min(all_dates)
    end = max(all_dates)
    return format_ix_date(start), format_ix_date(end), sources


def strip_comments(text: str) -> str:
    clean_lines = []
    for line in text.splitlines():
        line = re.split(r"\s+#", line, maxsplit=1)[0]
        line = re.split(r"\s+--", line, maxsplit=1)[0]
        clean_lines.append(line)
    return "\n".join(clean_lines)


def tokenize_ixf_line(line: str) -> list[str]:
    lexer = shlex.shlex(line, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def normalize_token(token: str) -> str:
    return token.strip().strip('"').strip("'").strip()


def is_saturation_mapping_type(token: str) -> bool:
    t = normalize_token(token).upper()
    return "SATURATION_FUNCTION" in t or "REL_PERM" in t or "HYSTERESIS" in t


def extract_rock_region_mapping_blocks(text: str) -> list[str]:
    blocks = []
    for m in re.finditer(r"RockRegionMapping\s*\[.*?\]", text, flags=re.I | re.S):
        blocks.append(m.group(0))
    for m in re.finditer(r"RockRegionMapping\s*\{.*?\}", text, flags=re.I | re.S):
        blocks.append(m.group(0))
    return blocks


def parse_table_rock_region_mapping(block: str, source: str) -> list[dict[str, Any]]:
    rows = []

    content_match = re.search(r"RockRegionMapping\s*\[(.*?)\]", block, flags=re.I | re.S)
    if not content_match:
        return rows

    content = content_match.group(1)
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]

    header_idx = None
    headers = []

    for i, line in enumerate(lines):
        toks = [normalize_token(t) for t in tokenize_ixf_line(line)]
        upper = [t.upper() for t in toks]

        if {"REGIONFAMILYNAMES", "REGIONNAMES", "MODELNAMES", "MAPPINGTYPES"}.issubset(set(upper)):
            header_idx = i
            headers = upper
            break

    if header_idx is None:
        return rows

    for line in lines[header_idx + 1:]:
        toks = [normalize_token(t) for t in tokenize_ixf_line(line)]
        if len(toks) < 4:
            continue

        try:
            rf_i = headers.index("REGIONFAMILYNAMES")
            rn_i = headers.index("REGIONNAMES")
            mn_i = headers.index("MODELNAMES")
            mt_i = headers.index("MAPPINGTYPES")
        except ValueError:
            continue

        max_i = max(rf_i, rn_i, mn_i, mt_i)
        if len(toks) <= max_i:
            continue

        row = {
            "source_file": source,
            "region_family": toks[rf_i],
            "region_name": toks[rn_i],
            "model_name": toks[mn_i],
            "mapping_type": toks[mt_i],
            "raw_line": line,
        }

        if is_saturation_mapping_type(row["mapping_type"]):
            rows.append(row)

    return rows


def detect_relperm_region(folder: Path, afi_path: Path) -> dict[str, Any]:
    included = extract_include_files_from_afi(afi_path)

    files = set(folder.glob("*.ixf"))
    for p in included:
        if p.suffix.lower() == ".ixf":
            files.add(p)

    rows: list[dict[str, Any]] = []

    for path in sorted(files):
        try:
            text = strip_comments(read_text_flexible(path))
        except Exception:
            continue

        for block in extract_rock_region_mapping_blocks(text):
            rows.extend(parse_table_rock_region_mapping(block, path.name))

    relevant = [
        r for r in rows
        if r["mapping_type"].upper() in SATURATION_MAPPING_KEYWORDS
        or "SATURATION_FUNCTION" in r["mapping_type"].upper()
    ]

    if not relevant:
        return {
            "detected": False,
            "region_family": None,
            "report_property_name": "FLUID_IN_PLACE_REGION",
            "report_label": "FIPNUM",
            "rows": [],
            "reason": "No RockRegionMapping saturation-function mapping found.",
        }

    by_family = defaultdict(list)
    for row in relevant:
        by_family[row["region_family"]].append(row)

    scored = []
    for family, family_rows in by_family.items():
        fam_upper = family.upper()
        score = len(family_rows)

        if fam_upper == "SATURATION_FUNCTION_DRAINAGE_TABLE_NO":
            score += 20
        elif "DRAINAGE" in fam_upper or "SATURATION" in fam_upper:
            score += 10
        elif fam_upper in {"RFN", "SATNUM"}:
            score += 8
        elif "FACIES" in fam_upper:
            score += 5

        if any(r["mapping_type"].upper() == "DRAINAGE_SATURATION_FUNCTION" for r in family_rows):
            score += 5

        scored.append((score, family, family_rows))

    scored.sort(reverse=True, key=lambda x: x[0])
    score, best_family, best_rows = scored[0]

    if best_family.upper() == "SATURATION_FUNCTION_DRAINAGE_TABLE_NO":
        report_property_name = "SATURATION_FUNCTION_DRAINAGE_TABLE_NO"
        report_label = "SATNUM"
    elif best_family.upper() == "SATURATION_FUNCTION_IMBIBITION_TABLE_NO":
        report_property_name = "SATURATION_FUNCTION_IMBIBITION_TABLE_NO"
        report_label = "IMBNUM"
    elif "FLUID_IN_PLACE" in best_family.upper():
        report_property_name = "FLUID_IN_PLACE_REGION"
        report_label = "FIPNUM"
    elif "FACIES" in best_family.upper():
        report_property_name = best_family
        report_label = "FACIES"
    else:
        report_property_name = best_family
        report_label = re.sub(r"[^A-Z0-9_]", "_", best_family.upper())[:16] or "REGION"

    return {
        "detected": True,
        "region_family": best_family,
        "report_property_name": report_property_name,
        "report_label": report_label,
        "score": score,
        "region_names": sorted(set(r["region_name"] for r in best_rows)),
        "model_names": sorted(set(r["model_name"] for r in best_rows)),
        "mapping_types": sorted(set(r["mapping_type"] for r in best_rows)),
        "source_files": sorted(set(r["source_file"] for r in best_rows)),
        "rows": best_rows,
        "reason": (
            f"Detected saturation-function mapping through RockRegionMapping. "
            f"Exporting IX property '{report_property_name}' as report label '{report_label}'."
        ),
    }


def generate_ix_streamline_mgr_ixf(streamline_seed_density: float = 0.3) -> str:
    return f"""# ==============================================================================
# 404 Reservoir Not Found - IX Streamline Manager Activation
# Include this file as: simulation="ix" type="ixf"
# ==============================================================================
START MODEL_DEFINITION

StreamlineMgr {{
  Active = TRUE
  SeedDensity = {streamline_seed_density}
  SeedMethod = BOTH
  VerbosityLevel = 1
}}

END_INPUT
"""


def controlled_target_block(date_value: str, label: str) -> str:
    return f"""
# ------------------------------------------------------------------------------
# Controlled recurrent 3D output at {label}: {date_value}
# Recurrent3D uses ONE_TARGET_TIME and is limited to this selected date.
# ------------------------------------------------------------------------------
DATE "{date_value}"

Recurrent3DReport "404_RNF_Recurrent3D_{label}" {{
  On = TRUE
  FileName = "404_RNF_{label}_3D"
  FileFormat = BINARY
  Unified = TRUE
  Frequency = ONE_TARGET_TIME
  Period = 1
}}

Recurrent3DReport "404_RNF_Recurrent3D_{label}" [
  SelectedProperties ReportLabels
  PRESSURE "PRESSURE"
  OIL_SATURATION "SOIL"
  WATER_SATURATION "SWAT"
  GAS_SATURATION "SGAS"
]
"""


def generate_fm_output_ixf(
    start_date: str,
    end_date: str,
    streamline_count: int,
    relperm_detection: dict[str, Any],
    include_target_3d_and_streamlines: bool = True,
) -> str:
    relprop = relperm_detection.get("report_property_name", "SATURATION_FUNCTION_DRAINAGE_TABLE_NO")
    rellabel = relperm_detection.get("report_label", "SATNUM")

    header = f"""# ==============================================================================
# 404 Reservoir Not Found - Controlled Output Request for INTERSECT
# Generated automatically.
# ==============================================================================
START MODEL_DEFINITION

FieldManagement {{
  VerbosityLevel = 0
}}

ReportMgr {{
  Output3DReports = TRUE
}}

Initial3DReport "*" [
  SelectedProperties ReportLabels
  POROSITY "PORO"
  PERM_I "PERMX"
  PERM_J "PERMY"
  PERM_K "PERMZ"
  TRANSMISSIBILITY_I "TRANX"
  TRANSMISSIBILITY_J "TRANY"
  TRANSMISSIBILITY_K "TRANZ"
  TRANSMISSIBILITY_MULTIPLIER_I "MULTX"
  TRANSMISSIBILITY_MULTIPLIER_J "MULTY"
  TRANSMISSIBILITY_MULTIPLIER_K "MULTZ"
  POROSITY_MULTIPLIER "PORO_MULT"
  {relprop} "{rellabel}"
  FLUID_IN_PLACE_REGION "FIPNUM"
]

# Streamline report.
# Period = 1 intentionally generates streamlines at each target time.
# The downstream extractor will use the first and last generated SLN files.
StreamlineReport "404_RNF_Streamlines_DEBUG" {{
  Streamlines = {streamline_count}
  Frequency = TARGET_TIMES
  Period = 1
  OutputFlows = TRUE
  OutputAllocations = TRUE
}}

XYPlotSummaryReport "*" {{
  On = TRUE
  FileFormat = BINARY
  Unified = TRUE
  OutputRSM = FALSE

  WellProperties "*" {{
    WellNames = ["*"]

    add_property(BOTTOM_HOLE_PRESSURE WBHP)

    add_property(OIL_PRODUCTION_RATE WOPR)
    add_property(OIL_PRODUCTION_CUML WOPT)
    add_property(WATER_PRODUCTION_RATE WWPR)
    add_property(WATER_PRODUCTION_CUML WWPT)
    add_property(GAS_PRODUCTION_RATE WGPR)
    add_property(GAS_PRODUCTION_CUML WGPT)

    add_property(WATER_CUT WWCT)
    add_property(GAS_OIL_RATIO WGOR)

    add_property(WATER_INJECTION_RATE WWIR)
    add_property(WATER_INJECTION_CUML WWIT)
    add_property(GAS_INJECTION_RATE WGIR)
    add_property(GAS_INJECTION_CUML WGIT)
    add_property(OIL_INJECTION_RATE WOIR)
    add_property(OIL_INJECTION_CUML WOIT)

    add_property(HISTORICAL_BOTTOM_HOLE_PRESSURE WBHPH)

    add_property(HISTORICAL_OIL_PRODUCTION_RATE WOPRH)
    add_property(HISTORICAL_OIL_PRODUCTION_CUML WOPTH)
    add_property(HISTORICAL_WATER_PRODUCTION_RATE WWPRH)
    add_property(HISTORICAL_WATER_PRODUCTION_CUML WWPTH)
    add_property(HISTORICAL_GAS_PRODUCTION_RATE WGPRH)
    add_property(HISTORICAL_GAS_PRODUCTION_CUML WGPTH)

    add_property(HISTORICAL_WATER_CUT WWCTH)
    add_property(HISTORICAL_GAS_OIL_RATIO WGORH)

    add_property(HISTORICAL_WATER_INJECTION_RATE WWIRH)
    add_property(HISTORICAL_WATER_INJECTION_CUML WWITH)
    add_property(HISTORICAL_GAS_INJECTION_RATE WGIRH)
    add_property(HISTORICAL_GAS_INJECTION_CUML WGITH)
  }}

  FieldProperties "*" {{
    add_property(PRESSURE FPR)

    add_property(OIL_PRODUCTION_RATE FOPR)
    add_property(OIL_PRODUCTION_CUML FOPT)
    add_property(WATER_PRODUCTION_RATE FWPR)
    add_property(WATER_PRODUCTION_CUML FWPT)
    add_property(GAS_PRODUCTION_RATE FGPR)
    add_property(GAS_PRODUCTION_CUML FGPT)

    add_property(WATER_CUT FWCT)
    add_property(GAS_OIL_RATIO FGOR)

    add_property(WATER_INJECTION_RATE FWIR)
    add_property(WATER_INJECTION_CUML FWIT)
    add_property(GAS_INJECTION_RATE FGIR)
    add_property(GAS_INJECTION_CUML FGIT)
    add_property(OIL_INJECTION_RATE FOIR)
    add_property(OIL_INJECTION_CUML FOIT)

    add_property(HISTORICAL_OIL_PRODUCTION_RATE FOPRH)
    add_property(HISTORICAL_OIL_PRODUCTION_CUML FOPTH)
    add_property(HISTORICAL_WATER_PRODUCTION_RATE FWPRH)
    add_property(HISTORICAL_WATER_PRODUCTION_CUML FWPTH)
    add_property(HISTORICAL_GAS_PRODUCTION_RATE FGPRH)
    add_property(HISTORICAL_GAS_PRODUCTION_CUML FGPTH)
    add_property(HISTORICAL_WATER_INJECTION_RATE FWIRH)
    add_property(HISTORICAL_WATER_INJECTION_CUML FWITH)
    add_property(HISTORICAL_GAS_INJECTION_RATE FGIRH)
    add_property(HISTORICAL_GAS_INJECTION_CUML FGITH)
  }}
}}

END_INPUT

"""

    if include_target_3d_and_streamlines:
        targets = (
            "START\n"
            + controlled_target_block(start_date, "INIT")
            + (controlled_target_block(end_date, "EOH") if end_date != start_date else "")
            + "\nEND_INPUT\n"
        )
    else:
        targets = "# Target 3D outputs disabled by user option.\n"

    return header + targets


def insert_flat_include_after(lines: list[str], include_line: str, simulation: str, preferred_patterns: list[str]) -> list[str]:
    lower_sim = f'simulation="{simulation}"'

    candidates = [
        i for i, line in enumerate(lines)
        if "include" in line.lower()
        and lower_sim in line.lower()
        and 'type="ixf"' in line.lower()
    ]

    preferred = [
        i for i in candidates
        if any(pat.upper() in lines[i].upper() for pat in preferred_patterns)
    ]

    if preferred:
        insert_after = preferred[-1]
    elif candidates:
        insert_after = candidates[-1]
    else:
        insert_after = len(lines) - 1

    lines.insert(insert_after + 1, include_line)
    return lines


def modify_afi(afi_path: Path, reservoir_name: Optional[str], suffix: str) -> Path:
    text = read_text_flexible(afi_path)
    lines = text.splitlines()

    if IX_STREAMLINE_IXF_NAME.lower() not in text.lower():
        lines = insert_flat_include_after(
            lines,
            ix_include_line(reservoir_name),
            "ix",
            ["RESERVOIR_SIMULATION_SETTINGS", "RESERVOIR_DEFINITION"],
        )

    text = "\n".join(lines) + "\n"
    lines = text.splitlines()

    if FM_OUTPUT_IXF_NAME.lower() not in text.lower():
        lines = insert_flat_include_after(
            lines,
            fm_include_line(),
            "fm",
            ["REPORT_SETTINGS", "SUMMARY", "3D", "FM_EDIT", "REPORT"],
        )

    new_text = "\n".join(lines) + "\n"
    new_afi_path = afi_path.with_name(f"{afi_path.stem}{suffix}{afi_path.suffix}")
    write_text(new_afi_path, new_text)
    return new_afi_path


def generate_package(
    work_dir: Path,
    afi_filename: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    streamlines: int = 300,
    seed_density: float = 0.3,
    suffix: str = "_404_RNF",
) -> dict[str, Any]:
    afi_path = work_dir / afi_filename
    warnings = []
    include_target_3d_and_streamlines = True
    reservoir_name = detect_reservoir_name_from_afi(afi_path)

    if start_date and end_date:
        s_date = start_date
        e_date = end_date
        date_sources = ["Manual date override."]
    else:
        s_date, e_date, date_sources = infer_history_dates(work_dir, afi_path)

    relperm_detection = detect_relperm_region(work_dir, afi_path)

    ix_text = generate_ix_streamline_mgr_ixf(streamline_seed_density=seed_density)
    fm_text = generate_fm_output_ixf(
        start_date=s_date,
        end_date=e_date,
        streamline_count=streamlines,
        relperm_detection=relperm_detection,
        include_target_3d_and_streamlines=True,
    )

    ix_path = work_dir / IX_STREAMLINE_IXF_NAME
    fm_path = work_dir / FM_OUTPUT_IXF_NAME
    metadata_path = work_dir / RELPERM_METADATA_JSON

    write_text(ix_path, ix_text)
    write_text(fm_path, fm_text)
    metadata_path.write_text(json.dumps(relperm_detection, indent=2, ensure_ascii=False), encoding="utf-8")

    new_afi_path = modify_afi(afi_path, reservoir_name, suffix=suffix)

    generated = [new_afi_path.name, IX_STREAMLINE_IXF_NAME, FM_OUTPUT_IXF_NAME, RELPERM_METADATA_JSON]

    package_zip = work_dir / "404_RNF_INTERSECT_OUTPUT_PACKAGE.zip"
    if package_zip.exists():
        package_zip.unlink()

    with zipfile.ZipFile(package_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in generated:
            zf.write(work_dir / name, arcname=name)

    return {
        "status": "success",
        "afi_file": afi_path.name,
        "modified_afi": new_afi_path.name,
        "ix_include": IX_STREAMLINE_IXF_NAME,
        "fm_include": FM_OUTPUT_IXF_NAME,
        "metadata": RELPERM_METADATA_JSON,
        "zip_file": package_zip.name,
        "generated_files": generated,
        "reservoir_name": reservoir_name,
        "history_start": s_date,
        "history_end": e_date,
        "date_sources": date_sources[:10],
        "warnings": warnings,
        "target_3d_outputs_enabled": include_target_3d_and_streamlines,
        "relperm_detection": relperm_detection,
        "message": (
            "Run the modified AFI in INTERSECT. After the simulation finishes, upload the run results for extraction."
            if not warnings else
            "Package generated with warnings. Review the warnings before running the modified AFI in INTERSECT."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--afi", required=True)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--streamlines", type=int, default=300)
    parser.add_argument("--seed-density", type=float, default=0.3)
    args = parser.parse_args()

    result = generate_package(
        work_dir=Path.cwd(),
        afi_filename=args.afi,
        start_date=args.start_date,
        end_date=args.end_date,
        streamlines=args.streamlines,
        seed_density=args.seed_density,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
