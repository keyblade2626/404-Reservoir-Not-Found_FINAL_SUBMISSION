import csv
import json
import math
import re
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.well_connections import get_well_spatial_summary


MODEL_DIR = Path("data/sample_model")
OUTPUT_DIR = Path("artifacts/streamlines")
GRID_DIMENSIONS_FILE = MODEL_DIR / "grid_dimensions.json"


STREAMLINE_FILE_PATTERNS = {
    "init": [
        "STREAMLINES_INIT*.csv",
        "STREAMLINES_INIT*.txt",
        "STREAMLINE_INIT*.csv",
        "STREAMLINE_INIT*.txt",
        "*STREAMLINES*INIT*.csv",
        "*STREAMLINES*INIT*.txt",
        "STREAMLINES_INIT*.SLN*",
        "STREAMLINE_INIT*.SLN*",
        "*STREAMLINES*INIT*.SLN*",
    ],
    "eoh": [
        "STREAMLINES_EOH*.csv",
        "STREAMLINES_EOH*.txt",
        "STREAMLINE_EOH*.csv",
        "STREAMLINE_EOH*.txt",
        "*STREAMLINES*EOH*.csv",
        "*STREAMLINES*EOH*.txt",
        "*STREAMLINES*END*.csv",
        "*STREAMLINES*END*.txt",
        "STREAMLINES_EOH*.SLN*",
        "STREAMLINE_EOH*.SLN*",
        "*STREAMLINES*EOH*.SLN*",
        "*STREAMLINES*END*.SLN*",
    ],
}


# =========================
# Generic helpers
# =========================

def looks_binary(raw: bytes) -> bool:
    if not raw:
        return False

    sample = raw[:4096]
    null_ratio = sample.count(b"\x00") / max(len(sample), 1)

    non_text = sum(
        1 for b in sample
        if b not in b"\r\n\t" and (b < 32 or b > 126)
    )
    non_text_ratio = non_text / max(len(sample), 1)

    return null_ratio > 0.01 or non_text_ratio > 0.20


def find_streamline_file(kind: str, model_dir: Path = MODEL_DIR) -> Optional[Path]:
    candidates: List[Path] = []

    for pattern in STREAMLINE_FILE_PATTERNS[kind]:
        candidates.extend(model_dir.glob(pattern))

    candidates = sorted(set(candidates), key=lambda p: p.name.upper())

    if not candidates:
        return None

    # Prefer readable CSV/TXT over binary SLN if both are present.
    text_candidates = [
        p for p in candidates
        if p.suffix.lower() in [".csv", ".txt"]
    ]

    if text_candidates:
        return sorted(text_candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]

    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def load_grid_dimensions() -> Dict[str, int]:
    data = json.loads(GRID_DIMENSIONS_FILE.read_text(encoding="utf-8-sig"))

    nx = int(data["nx"])
    ny = int(data["ny"])
    nz = int(data["nz"])

    return {
        "nx": nx,
        "ny": ny,
        "nz": nz,
        "cell_count": nx * ny * nz,
    }


def cell_id_zero_based(i: int, j: int, k: int, dims: Dict[str, int]) -> int:
    return (k - 1) * dims["nx"] * dims["ny"] + (j - 1) * dims["nx"] + (i - 1)


def cell_id_one_based(i: int, j: int, k: int, dims: Dict[str, int]) -> int:
    return cell_id_zero_based(i, j, k, dims) + 1


def build_completion_cell_lookup() -> Dict[int, List[str]]:
    """
    Maps both 0-based and 1-based flattened cell ids to wells.

    This is intentional because SLN ID_CELL may be 0-based or 1-based depending on export.
    """
    dims = load_grid_dimensions()
    spatial = get_well_spatial_summary()

    lookup: Dict[int, List[str]] = {}

    for well, payload in spatial.get("wells", {}).items():
        for c in payload.get("connections", []):
            try:
                i = int(c["i"])
                j = int(c["j"])
                k = int(c["k"])
            except Exception:
                continue

            for cid in [
                cell_id_zero_based(i, j, k, dims),
                cell_id_one_based(i, j, k, dims),
            ]:
                lookup.setdefault(cid, [])

                if well not in lookup[cid]:
                    lookup[cid].append(well)

    return lookup


def map_cells_to_wells(cell_values: List[Any], cell_to_wells: Dict[int, List[str]]) -> List[str]:
    wells: List[str] = []

    for value in cell_values:
        if value in [None, ""]:
            continue

        try:
            cid = int(value)
        except Exception:
            continue

        for well in cell_to_wells.get(cid, []):
            if well not in wells:
                wells.append(well)

    return wells


# =========================
# Text/CSV parser
# =========================

INJECTOR_ALIASES = ["injector", "inj", "source", "source_well", "from", "from_well", "iw"]
PRODUCER_ALIASES = ["producer", "prod", "target", "target_well", "to", "to_well", "pw"]
STRENGTH_ALIASES = ["connection_fraction", "fraction", "flow_fraction", "allocation_fraction", "strength", "weight", "streamline_fraction"]
COUNT_ALIASES = ["streamline_count", "count", "nstreamlines", "n_streamlines", "num_streamlines"]
RATE_ALIASES = ["allocated_rate", "allocated_water_rate", "water_rate", "rate", "flow"]


def normalize_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def find_column(fieldnames: List[str], aliases: List[str]) -> Optional[str]:
    normalized = {normalize_header(f): f for f in fieldnames}

    for alias in aliases:
        alias_norm = normalize_header(alias)
        if alias_norm in normalized:
            return normalized[alias_norm]

    for norm, original in normalized.items():
        for alias in aliases:
            alias_norm = normalize_header(alias)
            if alias_norm in norm or norm in alias_norm:
                return original

    return None


def to_float(value: Any) -> Optional[float]:
    if value in [None, "", "None", "null", "N/A"]:
        return None

    try:
        return float(str(value).strip())
    except Exception:
        return None


def sniff_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:20])

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t ")
        return dialect.delimiter
    except Exception:
        if ";" in sample:
            return ";"
        if "," in sample:
            return ","
        if "\t" in sample:
            return "\t"
        return " "


def parse_delimited_text(text: str, source_file: Path, snapshot: str) -> List[Dict[str, Any]]:
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("--")
    ]

    if not lines:
        return []

    delimiter = sniff_delimiter("\n".join(lines[:50]))

    if delimiter == " ":
        normalized_lines = [re.sub(r"\s+", " ", line) for line in lines]
        reader = csv.DictReader(normalized_lines, delimiter=" ")
    else:
        reader = csv.DictReader(lines, delimiter=delimiter)

    if reader.fieldnames is None:
        return []

    fieldnames = [f for f in reader.fieldnames if f is not None]

    injector_col = find_column(fieldnames, INJECTOR_ALIASES)
    producer_col = find_column(fieldnames, PRODUCER_ALIASES)
    strength_col = find_column(fieldnames, STRENGTH_ALIASES)
    count_col = find_column(fieldnames, COUNT_ALIASES)
    rate_col = find_column(fieldnames, RATE_ALIASES)

    if injector_col is None or producer_col is None:
        return []

    rows = []

    for raw in reader:
        injector = str(raw.get(injector_col, "")).strip()
        producer = str(raw.get(producer_col, "")).strip()

        if not injector or not producer:
            continue

        strength = to_float(raw.get(strength_col)) if strength_col else None
        count = to_float(raw.get(count_col)) if count_col else None
        rate = to_float(raw.get(rate_col)) if rate_col else None

        if strength is None:
            if count is not None:
                strength = count
            elif rate is not None:
                strength = rate
            else:
                strength = 1.0

        rows.append(
            {
                "snapshot": snapshot,
                "source_file": str(source_file),
                "injector": injector,
                "producer": producer,
                "connection_strength": strength,
                "streamline_count": count,
                "allocated_rate": rate,
                "raw_count": 1,
                "parser_source": "text_delimited",
            }
        )

    return rows


# =========================
# Fortran binary SLN parser
# =========================

def read_fortran_record(f, endian: str = ">") -> Optional[bytes]:
    hdr = f.read(4)

    if len(hdr) == 0:
        return None

    if len(hdr) != 4:
        raise EOFError("Unexpected EOF while reading record header.")

    (reclen,) = struct.unpack(endian + "I", hdr)

    # Basic sanity check to detect wrong endian.
    if reclen <= 0 or reclen > 500_000_000:
        raise ValueError(f"Unrealistic Fortran record length {reclen}; wrong endian or invalid file.")

    payload = f.read(reclen)
    tail = f.read(4)

    if len(payload) != reclen:
        raise EOFError("Unexpected EOF while reading record payload.")

    if len(tail) != 4:
        raise EOFError("Unexpected EOF while reading record trailer.")

    (reclen2,) = struct.unpack(endian + "I", tail)

    if reclen2 != reclen:
        raise ValueError(f"Record length mismatch: {reclen} != {reclen2}")

    return payload


def parse_header16(payload: Optional[bytes], endian: str = ">") -> Optional[Tuple[str, int, str]]:
    if payload is None or len(payload) != 16:
        return None

    key = payload[0:8].decode("ascii", errors="ignore").strip()
    n = struct.unpack(endian + "i", payload[8:12])[0]
    typ = payload[12:16].decode("ascii", errors="ignore").strip().upper()

    if not key:
        return None

    return key, n, typ


def dtype_np(typ: str, endian: str = ">") -> Tuple[Optional[np.dtype], Optional[int]]:
    if typ == "DOUB":
        return np.dtype(endian + "f8"), 8

    if typ == "REAL":
        return np.dtype(endian + "f4"), 4

    if typ == "INTE":
        return np.dtype(endian + "i4"), 4

    return None, None


def read_numeric(f, n: int, typ: str, endian: str = ">") -> np.ndarray:
    npdt, bpe = dtype_np(typ, endian=endian)

    if npdt is None or bpe is None:
        raise ValueError(f"Unsupported type {typ}")

    needed = n * bpe
    chunks = []
    got = 0

    while got < needed:
        rec = read_fortran_record(f, endian=endian)

        if rec is None:
            raise EOFError("Unexpected EOF while reading numeric payload.")

        chunks.append(rec)
        got += len(rec)

    blob = b"".join(chunks)[:needed]

    return np.frombuffer(blob, dtype=npdt)


def skip_typed(f, n: int, typ: str, endian: str = ">") -> None:
    npdt, bpe = dtype_np(typ, endian=endian)

    if npdt is None or bpe is None:
        _ = read_fortran_record(f, endian=endian)
        return

    needed = n * bpe
    got = 0

    while got < needed:
        rec = read_fortran_record(f, endian=endian)

        if rec is None:
            raise EOFError("Unexpected EOF while skipping typed payload.")

        got += len(rec)


def normalize_ptr(ptr: np.ndarray) -> np.ndarray:
    ptr = np.asarray(ptr).astype(np.int64)

    if ptr.size == 0:
        return ptr

    mn = int(ptr.min())

    if mn == 0:
        return ptr

    if mn == 1:
        return ptr - 1

    return ptr - mn


def detect_pointer_units(ptr: np.ndarray, geom_size: int, n_points_total: int) -> str:
    last = int(ptr[-1])

    if last == geom_size:
        return "doubles"

    if last == n_points_total:
        return "points"

    if last == n_points_total - 1:
        return "points_inclusive"

    return "points"


def ptr_to_point_slice(a: int, b: int, pointer_units: str, n_points_total: int) -> Tuple[int, int]:
    if pointer_units == "doubles":
        p0 = a // 3
        p1 = b // 3
    elif pointer_units == "points_inclusive":
        p0 = a
        p1 = b + 1
    else:
        p0 = a
        p1 = b

    p0 = max(0, min(int(p0), n_points_total))
    p1 = max(0, min(int(p1), n_points_total))

    return p0, p1


def read_binary_sln_arrays(path: Path, endian: str = ">") -> Dict[str, np.ndarray]:
    wanted = [
        "GEOMETRY",
        "GEOMINDX",
        "ID_CELL",
        "ID_BEG",
        "ID_END",
        "TIME_BEG",
        "PRESSURE",
    ]

    data: Dict[str, np.ndarray] = {}

    with path.open("rb") as f:
        while True:
            rec = read_fortran_record(f, endian=endian)

            if rec is None:
                break

            hdr = parse_header16(rec, endian=endian)

            if hdr is None:
                continue

            key, n, typ = hdr

            if key in wanted:
                data[key] = read_numeric(f, n, typ, endian=endian)
            else:
                skip_typed(f, n, typ, endian=endian)

    return data


def try_read_binary_sln_arrays(path: Path) -> Tuple[Dict[str, np.ndarray], str]:
    errors = []

    for endian in [">", "<"]:
        try:
            data = read_binary_sln_arrays(path, endian=endian)

            if "GEOMETRY" in data and "GEOMINDX" in data:
                return data, endian

            errors.append(f"endian {endian}: missing GEOMETRY/GEOMINDX")
        except Exception as exc:
            errors.append(f"endian {endian}: {type(exc).__name__}: {exc}")

    raise RuntimeError("Could not parse binary SLN file. " + " | ".join(errors))


def extract_cells_for_streamline(
    sid: int,
    p0: int,
    p1: int,
    n_points_total: int,
    id_cell: Optional[np.ndarray],
    cell_cursor_state: Dict[str, int],
) -> List[Any]:
    if id_cell is None:
        return []

    npts = max(0, p1 - p0)

    if id_cell.size == n_points_total:
        return list(id_cell[p0:p1])

    # Some SLN exports store cell ids per segment, not per point.
    ncell_this = max(0, npts - 1)
    cursor = cell_cursor_state.get("cursor", 0)

    values = [""] + list(id_cell[cursor:cursor + ncell_this])
    cell_cursor_state["cursor"] = cursor + ncell_this

    return values


def parse_binary_sln(path: Path, snapshot: str) -> Dict[str, Any]:
    data, endian = try_read_binary_sln_arrays(path)

    geom = data.get("GEOMETRY")
    ptr_raw = data.get("GEOMINDX")
    id_cell = data.get("ID_CELL")
    id_beg = data.get("ID_BEG")
    id_end = data.get("ID_END")
    tof = data.get("TIME_BEG")
    pressure = data.get("PRESSURE")

    if geom is None or ptr_raw is None:
        raise ValueError("Missing GEOMETRY or GEOMINDX in SLN file.")

    if geom.size % 3 != 0:
        raise ValueError("GEOMETRY length is not divisible by 3.")

    n_points_total = geom.size // 3
    ptr = normalize_ptr(ptr_raw)
    n_streamlines = max(0, ptr.size - 1)
    pointer_units = detect_pointer_units(ptr, geom.size, n_points_total)

    cell_to_wells = build_completion_cell_lookup()

    rows = []
    unmatched = 0
    matched = 0
    cell_cursor_state = {"cursor": 0}

    for sid in range(n_streamlines):
        a = int(ptr[sid])
        b = int(ptr[sid + 1])
        p0, p1 = ptr_to_point_slice(a, b, pointer_units, n_points_total)

        if p1 <= p0:
            continue

        cells_this = extract_cells_for_streamline(
            sid=sid,
            p0=p0,
            p1=p1,
            n_points_total=n_points_total,
            id_cell=id_cell,
            cell_cursor_state=cell_cursor_state,
        )

        beg_candidates: List[Any] = []
        end_candidates: List[Any] = []

        if id_beg is not None and sid < id_beg.size:
            beg_candidates.append(int(id_beg[sid]))

        if id_end is not None and sid < id_end.size:
            end_candidates.append(int(id_end[sid]))

        non_empty_cells = [c for c in cells_this if c != ""]

        if non_empty_cells:
            beg_candidates.append(int(non_empty_cells[0]))
            end_candidates.append(int(non_empty_cells[-1]))

        beg_wells = map_cells_to_wells(beg_candidates, cell_to_wells)
        end_wells = map_cells_to_wells(end_candidates, cell_to_wells)

        if not beg_wells or not end_wells:
            unmatched += 1
            continue

        for beg_well in beg_wells:
            for end_well in end_wells:
                if beg_well == end_well:
                    continue

                matched += 1

                rows.append(
                    {
                        "snapshot": snapshot,
                        "source_file": str(path),
                        "injector": beg_well,
                        "producer": end_well,
                        "connection_strength": 1.0,
                        "streamline_count": 1.0,
                        "allocated_rate": None,
                        "streamline_id": sid + 1,
                        "id_beg": int(id_beg[sid]) if id_beg is not None and sid < id_beg.size else None,
                        "id_end": int(id_end[sid]) if id_end is not None and sid < id_end.size else None,
                        "first_cell": int(non_empty_cells[0]) if non_empty_cells else None,
                        "last_cell": int(non_empty_cells[-1]) if non_empty_cells else None,
                        "time_beg": float(tof[sid]) if tof is not None and sid < tof.size else None,
                        "pressure": float(pressure[sid]) if pressure is not None and sid < pressure.size else None,
                        "raw_count": 1,
                        "parser_source": "fortran_binary_sln",
                    }
                )

    return {
        "rows": rows,
        "metadata": {
            "endian": endian,
            "keys_found": sorted(data.keys()),
            "n_points_total": int(n_points_total),
            "n_streamlines": int(n_streamlines),
            "pointer_units": pointer_units,
            "id_cell_size": int(id_cell.size) if id_cell is not None else None,
            "id_beg_size": int(id_beg.size) if id_beg is not None else None,
            "id_end_size": int(id_end.size) if id_end is not None else None,
            "matched_streamline_links": matched,
            "unmatched_streamlines": unmatched,
            "completion_cell_lookup_size": len(cell_to_wells),
        },
    }


# =========================
# Aggregation
# =========================

def aggregate_connections(rows: List[Dict[str, Any]], snapshot: str) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for row in rows:
        injector = row["injector"]
        producer = row["producer"]
        key = (injector, producer)

        if key not in grouped:
            grouped[key] = {
                "snapshot": snapshot,
                "injector": injector,
                "producer": producer,
                "connection_strength": 0.0,
                "streamline_count": 0.0,
                "allocated_rate": 0.0,
                "source_file": row.get("source_file"),
                "raw_count": 0,
                "parser_source": row.get("parser_source"),
            }

        grouped[key]["connection_strength"] += float(row.get("connection_strength") or 0.0)
        grouped[key]["streamline_count"] += float(row.get("streamline_count") or 0.0)
        grouped[key]["allocated_rate"] += float(row.get("allocated_rate") or 0.0)
        grouped[key]["raw_count"] += int(row.get("raw_count") or 1)

    producer_totals: Dict[str, float] = {}

    for item in grouped.values():
        producer = item["producer"]
        producer_totals[producer] = producer_totals.get(producer, 0.0) + item["connection_strength"]

    result = []

    for item in grouped.values():
        total = producer_totals.get(item["producer"], 0.0)

        if total > 0:
            item["connection_fraction_to_producer"] = item["connection_strength"] / total
        else:
            item["connection_fraction_to_producer"] = None

        result.append(item)

    return sorted(
        result,
        key=lambda x: (x["producer"], -float(x.get("connection_strength") or 0.0)),
    )


def parse_streamline_file(path: Path, snapshot: str) -> Dict[str, Any]:
    raw = path.read_bytes()
    is_binary = looks_binary(raw)

    report = {
        "snapshot": snapshot,
        "source_file": str(path),
        "file_size_bytes": path.stat().st_size,
        "looks_binary": is_binary,
        "parsed_connection_count": 0,
        "aggregated_connection_count": 0,
        "parser_used": None,
        "warning": None,
        "sample_preview": None,
        "metadata": {},
        "connections": [],
    }

    try:
        if is_binary:
            parsed = parse_binary_sln(path, snapshot)
            rows = parsed["rows"]
            report["metadata"] = parsed["metadata"]
            report["parser_used"] = "fortran_binary_sln"
            report["sample_preview"] = str(raw[:128])
        else:
            text = raw.decode("utf-8", errors="ignore")
            report["sample_preview"] = "\n".join(text.splitlines()[:20])
            rows = parse_delimited_text(text, path, snapshot)
            report["parser_used"] = "text_delimited" if rows else None

        aggregated = aggregate_connections(rows, snapshot) if rows else []

        report["parsed_connection_count"] = len(rows)
        report["aggregated_connection_count"] = len(aggregated)
        report["connections"] = aggregated

        if not aggregated:
            report["warning"] = (
                "File was parsed, but no injector-producer well connection could be mapped. "
                "This usually means endpoint cell ids do not match completion cell ids, "
                "or streamline endpoints are not located exactly on well completion cells."
            )

    except Exception as exc:
        report["warning"] = f"Failed to parse streamline file: {type(exc).__name__}: {exc}"
        report["sample_preview"] = str(raw[:128])

    return report


def load_streamline_connections(model_dir: Path = MODEL_DIR) -> Dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload: Dict[str, Any] = {
        "files": {},
        "snapshots": {},
        "connections_by_snapshot": {},
        "connection_changes": [],
        "available": False,
    }

    for snapshot in ["init", "eoh"]:
        path = find_streamline_file(snapshot, model_dir=model_dir)
        payload["files"][snapshot] = str(path) if path else None

        if path is None:
            payload["snapshots"][snapshot] = {
                "snapshot": snapshot,
                "source_file": None,
                "warning": f"No file found for {snapshot} using patterns {STREAMLINE_FILE_PATTERNS[snapshot]}",
                "connections": [],
            }
            payload["connections_by_snapshot"][snapshot] = []
            continue

        report = parse_streamline_file(path, snapshot)
        payload["snapshots"][snapshot] = report
        payload["connections_by_snapshot"][snapshot] = report["connections"]

    init_connections = {
        (c["injector"], c["producer"]): c
        for c in payload["connections_by_snapshot"].get("init", [])
    }

    eoh_connections = {
        (c["injector"], c["producer"]): c
        for c in payload["connections_by_snapshot"].get("eoh", [])
    }

    all_keys = sorted(set(init_connections) | set(eoh_connections))

    changes = []

    for key in all_keys:
        injector, producer = key
        init = init_connections.get(key)
        eoh = eoh_connections.get(key)

        init_strength = float(init.get("connection_strength") or 0.0) if init else 0.0
        eoh_strength = float(eoh.get("connection_strength") or 0.0) if eoh else 0.0

        init_fraction = init.get("connection_fraction_to_producer") if init else None
        eoh_fraction = eoh.get("connection_fraction_to_producer") if eoh else None

        changes.append(
            {
                "injector": injector,
                "producer": producer,
                "init_connection_strength": init_strength,
                "eoh_connection_strength": eoh_strength,
                "delta_connection_strength": eoh_strength - init_strength,
                "init_connection_fraction": init_fraction,
                "eoh_connection_fraction": eoh_fraction,
                "delta_connection_fraction": (
                    eoh_fraction - init_fraction
                    if eoh_fraction is not None and init_fraction is not None
                    else None
                ),
                "appeared_by_eoh": init is None and eoh is not None,
                "disappeared_by_eoh": init is not None and eoh is None,
            }
        )

    payload["connection_changes"] = sorted(
        changes,
        key=lambda x: (x["producer"], -float(x.get("eoh_connection_strength") or 0.0)),
    )

    payload["available"] = any(
        len(payload["connections_by_snapshot"].get(snapshot, [])) > 0
        for snapshot in ["init", "eoh"]
    )

    report_path = OUTPUT_DIR / "streamline_parse_report.json"
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return payload


def main() -> None:
    payload = load_streamline_connections()

    print("")
    print("Streamline file discovery:")
    for snapshot, path in payload["files"].items():
        print(f"  {snapshot}: {path}")

    print("")

    for snapshot, report in payload["snapshots"].items():
        print(f"{snapshot}:")
        print(f"  source_file: {report.get('source_file')}")
        print(f"  looks_binary: {report.get('looks_binary')}")
        print(f"  parser_used: {report.get('parser_used')}")
        print(f"  parsed_connection_count: {report.get('parsed_connection_count')}")
        print(f"  aggregated_connection_count: {report.get('aggregated_connection_count')}")
        print(f"  metadata: {report.get('metadata')}")
        if report.get("warning"):
            print(f"  warning: {report.get('warning')}")

    print("")
    print(f"available: {payload['available']}")
    print("Report saved to artifacts/streamlines/streamline_parse_report.json")


if __name__ == "__main__":
    main()
