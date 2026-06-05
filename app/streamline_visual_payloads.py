import csv
import json
import math
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data" / "sample_model"
ART = ROOT / "artifacts"

OUTPUT_JSON = ART / "dashboard" / "streamline_visual_payload.json"




def normalize_streamline_time_key(time_key: str = "auto", snapshot: str = None, streamline_time: str = None, mode: str = None) -> str:
    raw = (streamline_time or snapshot or mode or time_key or "auto")
    q = str(raw).strip().lower()

    if q in ["initial", "init", "boh", "begin", "beginning", "start", "time_beg"]:
        return "initial"

    if q in ["final", "eoh", "end", "last", "current", "late"]:
        return "final"

    if q in ["compare", "comparison", "initial_vs_final", "start_vs_end"]:
        return "compare"

    return "auto"


def streamline_file_time_score(path: Path, time_key: str) -> tuple:
    """
    Rank streamline files according to requested snapshot.
    Lower score is better.
    """
    name = path.name.upper()

    initial_tokens = ["INITIAL", "INIT", "BOH", "BEG", "BEGIN", "START", "TIME_BEG"]
    final_tokens = ["EOH", "FINAL", "END", "LAST", "CURRENT", "TIME_END"]

    has_initial = any(tok in name for tok in initial_tokens)
    has_final = any(tok in name for tok in final_tokens)

    if time_key == "initial":
        if has_initial:
            return (0, name)
        if not has_final:
            return (1, name)
        return (3, name)

    if time_key == "final":
        if has_final:
            return (0, name)
        if not has_initial:
            return (1, name)
        return (3, name)

    # auto: keep old behavior, prefer EOH/final if present.
    if has_final:
        return (0, name)
    return (1, name)


def selected_streamline_snapshot_label(time_key: str) -> str:
    return {
        "initial": "Initial History",
        "final": "End of History",
        "compare": "Initial vs End of History",
        "auto": "Default / Available Snapshot",
    }.get(time_key, time_key)


def safe_float(v):
    try:
        if v is None or v == "":
            return None
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None


def load_json(path: Path):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def get_grid_dims():
    try:
        from app.cell_property_layers import discover_grid_dimensions
        nx, ny, nz, source = discover_grid_dimensions()
        return nx, ny, nz, source
    except Exception:
        return None, None, None, "grid_dims_failed"


def get_hm_wells() -> List[Dict[str, Any]]:
    try:
        from app.hm_map_payload import build_hm_map_payload
        return build_hm_map_payload().get("wells", [])
    except Exception:
        pass

    p = ART / "dashboard" / "hm_map_payload.json"
    data = load_json(p) or {}
    return data.get("wells", [])


def cell_id_to_ij(cell_id, nx, ny, nz, base):
    """
    Converts ECL-style linear cell id to I,J.
    Assumes I fastest, then J, then K.
    base=0 for 0-based cell ids, base=1 for 1-based cell ids.
    """
    try:
        cid = int(float(cell_id)) - base

        if cid < 0:
            return None

        cells_per_layer = nx * ny

        if cid >= cells_per_layer * nz:
            return None

        i = cid % nx + 1
        j = (cid // nx) % ny + 1

        if i < 1 or i > nx or j < 1 or j > ny:
            return None

        return {"i": float(i), "j": float(j)}
    except Exception:
        return None


def choose_cell_id_base(cell_ids, nx, ny, nz):
    sample = [x for x in cell_ids[: min(len(cell_ids), 2000)] if x is not None]

    if not sample:
        return 0

    score0 = 0
    score1 = 0

    for cid in sample:
        if cell_id_to_ij(cid, nx, ny, nz, 0) is not None:
            score0 += 1
        if cell_id_to_ij(cid, nx, ny, nz, 1) is not None:
            score1 += 1

    return 1 if score1 > score0 else 0


# ==========================================================
# Fortran binary SLN reader
# ==========================================================

def read_fortran_record(f, endian=">"):
    hdr = f.read(4)

    if len(hdr) == 0:
        return None

    if len(hdr) != 4:
        return None

    (reclen,) = struct.unpack(endian + "I", hdr)

    if reclen <= 0 or reclen > 500_000_000:
        return None

    payload = f.read(reclen)
    tail = f.read(4)

    if len(tail) != 4:
        return None

    (reclen2,) = struct.unpack(endian + "I", tail)

    if reclen2 != reclen:
        return None

    return payload


def parse_header16(payload, endian=">"):
    if payload is None or len(payload) != 16:
        return None

    key = payload[0:8].decode("ascii", errors="ignore").strip()
    n = struct.unpack(endian + "i", payload[8:12])[0]
    typ = payload[12:16].decode("ascii", errors="ignore").strip().upper()

    if not key:
        return None

    return key, n, typ


def dtype_np(typ):
    if typ == "DOUB":
        return np.dtype(">f8"), 8
    if typ == "INTE":
        return np.dtype(">i4"), 4
    return None, None


def read_numeric(f, n, typ, endian=">"):
    npdt, bpe = dtype_np(typ)

    if npdt is None:
        return None

    needed = n * bpe
    chunks = []
    got = 0

    while got < needed:
        rec = read_fortran_record(f, endian=endian)

        if rec is None:
            break

        chunks.append(rec)
        got += len(rec)

    if got <= 0:
        return None

    blob = b"".join(chunks)[:needed]

    return np.frombuffer(blob, dtype=npdt)


def skip_typed(f, n, typ, endian=">"):
    npdt, bpe = dtype_np(typ)

    if npdt is None:
        _ = read_fortran_record(f, endian=endian)
        return

    needed = n * bpe
    got = 0

    while got < needed:
        rec = read_fortran_record(f, endian=endian)

        if rec is None:
            break

        got += len(rec)


def normalize_ptr(ptr):
    ptr = np.asarray(ptr).astype(np.int64)

    if ptr.size == 0:
        return ptr

    mn = int(ptr.min())

    if mn == 0:
        return ptr

    if mn == 1:
        return ptr - 1

    return ptr - mn


def parse_binary_sln(path: Path, nx: int, ny: int, nz: int, max_lines: int = 600) -> List[Dict[str, Any]]:
    wanted = [
        "GEOMETRY",
        "GEOMINDX",
        "ID_CELL",
        "ID_BEG",
        "ID_END",
        "TIME_BEG",
        "PRESSURE",
    ]

    data = {}
    endian = ">"

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
                arr = read_numeric(f, n, typ, endian=endian)

                if arr is not None:
                    data[key] = arr
            else:
                skip_typed(f, n, typ, endian=endian)

    if "GEOMETRY" not in data or "GEOMINDX" not in data or "ID_CELL" not in data:
        return []

    geom = data["GEOMETRY"]
    ptr = normalize_ptr(data["GEOMINDX"])
    id_cell = np.asarray(data["ID_CELL"]).astype(np.int64)

    if geom.size % 3 != 0:
        return []

    n_points_total = geom.size // 3

    if ptr.size < 2:
        return []

    n_streamlines = ptr.size - 1

    last = int(ptr[-1])

    if last == geom.size:
        pointer_units = "doubles"
    elif last == n_points_total:
        pointer_units = "points"
    elif last == n_points_total - 1:
        pointer_units = "points_inclusive"
    else:
        pointer_units = "points"

    def ptr_to_point_slice(a, b):
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

    base = choose_cell_id_base(id_cell.tolist(), nx, ny, nz)

    lines = []
    cell_cursor = 0

    for sid in range(n_streamlines):
        if len(lines) >= max_lines:
            break

        a = int(ptr[sid])
        b = int(ptr[sid + 1])
        p0, p1 = ptr_to_point_slice(a, b)

        if p1 <= p0:
            continue

        npts = p1 - p0

        # ID_CELL convention 1: one cell id per geometry point.
        if id_cell.size == n_points_total:
            cells_this = id_cell[p0:p1]

        # ID_CELL convention 2: one cell id per segment.
        else:
            ncell_this = max(0, npts - 1)
            seg = id_cell[cell_cursor:cell_cursor + ncell_this]
            cell_cursor += ncell_this

            if seg.size == 0:
                continue

            # Repeat first segment cell as first point.
            cells_this = np.concatenate([seg[:1], seg])

        pts = []

        # Downsample points for browser readability.
        if len(cells_this) > 80:
            idxs = np.linspace(0, len(cells_this) - 1, 80).astype(int)
            sample_cells = cells_this[idxs]
        else:
            sample_cells = cells_this

        last_ij = None

        for cid in sample_cells:
            ij = cell_id_to_ij(cid, nx, ny, nz, base)

            if ij is None:
                continue

            # avoid duplicate consecutive points
            if last_ij and abs(last_ij["i"] - ij["i"]) < 0.01 and abs(last_ij["j"] - ij["j"]) < 0.01:
                continue

            pts.append(ij)
            last_ij = ij

        if len(pts) >= 2:
            id_beg = int(data["ID_BEG"][sid]) if "ID_BEG" in data and sid < data["ID_BEG"].size else None
            id_end = int(data["ID_END"][sid]) if "ID_END" in data and sid < data["ID_END"].size else None

            lines.append({
                "id": sid + 1,
                "producer": None,
                "injector": None,
                "source_id": id_beg,
                "target_id": id_end,
                "strength": 1.0,
                "points": pts,
                "source": "binary_sln_id_cell",
                "source_file": str(path.relative_to(ROOT)),
            })

    return lines


# ==========================================================
# CSV fallback
# ==========================================================

def parse_csv_streamline_points(path: Path, nx: int, ny: int, nz: int, max_lines: int = 600) -> List[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    except Exception:
        return []

    if not rows:
        return []

    keys = {k.lower(): k for k in rows[0].keys()}

    sid_key = keys.get("streamline_id") or keys.get("sid") or keys.get("line_id")
    i_key = keys.get("i") or keys.get("cell_i") or keys.get("grid_i")
    j_key = keys.get("j") or keys.get("cell_j") or keys.get("grid_j")
    cell_key = keys.get("cell_id") or keys.get("cell_id_raw") or keys.get("id_cell")

    if not sid_key:
        return []

    grouped = {}

    # Determine cell id base if needed.
    base = 0
    if cell_key:
        sample_cids = []
        for r in rows[:2000]:
            v = safe_float(r.get(cell_key))
            if v is not None:
                sample_cids.append(v)
        base = choose_cell_id_base(sample_cids, nx, ny, nz)

    for r in rows:
        sid = str(r.get(sid_key))

        if sid not in grouped:
            grouped[sid] = []

        if i_key and j_key:
            i = safe_float(r.get(i_key))
            j = safe_float(r.get(j_key))

            if i is not None and j is not None:
                grouped[sid].append({"i": i, "j": j})

        elif cell_key:
            cid = safe_float(r.get(cell_key))
            ij = cell_id_to_ij(cid, nx, ny, nz, base)

            if ij is not None:
                grouped[sid].append(ij)

    lines = []

    for sid, pts in grouped.items():
        if len(lines) >= max_lines:
            break

        if len(pts) < 2:
            continue

        if len(pts) > 80:
            idxs = np.linspace(0, len(pts) - 1, 80).astype(int)
            pts = [pts[i] for i in idxs]

        clean = []
        last = None

        for p in pts:
            if last and abs(last["i"] - p["i"]) < 0.01 and abs(last["j"] - p["j"]) < 0.01:
                continue
            clean.append(p)
            last = p

        if len(clean) >= 2:
            lines.append({
                "id": sid,
                "producer": None,
                "injector": None,
                "strength": 1.0,
                "points": clean,
                "source": "csv_streamline_points",
                "source_file": str(path.relative_to(ROOT)),
            })

    return lines


def build_streamline_visual_payload(max_lines: int = 800, time_key: str = 'auto', snapshot: str = None, streamline_time: str = None, mode: str = None) -> Dict[str, Any]:
    time_key = normalize_streamline_time_key(time_key, snapshot=snapshot, streamline_time=streamline_time, mode=mode)
    nx, ny, nz, dim_source = get_grid_dims()

    if not nx or not ny or not nz:
        payload = {
            "ok": False,
            "line_count": 0,
            "used_files": [],
            "lines": [],
            "wells": get_hm_wells(),
            "message": "Grid dimensions unavailable, cannot convert streamline CELL_ID to I,J.",
            "dimension_source": dim_source,
        }

        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    lines = []
    used_files = []

    # 1) Strongest path: binary SLN files.
    all_sln_files = sorted(MODEL_DIR.glob("STREAMLINES*.SLN*"))
    sln_files = filter_streamline_files_by_time(all_sln_files, time_key)

    # Strict behavior: if user explicitly asks initial/final and no matching files exist,
    # do not silently fall back to another snapshot.
    if time_key in ["initial", "final"] and not sln_files:
        payload = snapshot_unavailable_payload(time_key, all_sln_files)
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    for path in sln_files:
        parsed = parse_binary_sln(path, nx, ny, nz, max_lines=max_lines - len(lines))

        if parsed:
            lines.extend(parsed)
            used_files.append(str(path.relative_to(ROOT)))

        if len(lines) >= max_lines:
            break

    # 2) CSV fallback if no binary lines.
    if not lines:
        csv_files = []

        for folder in [ART, MODEL_DIR, ROOT]:
            if folder.exists():
                csv_files.extend(folder.rglob("*streamline*.csv"))
                csv_files.extend(folder.rglob("*streamlines*.csv"))

        for path in sorted(set(csv_files)):
            parsed = parse_csv_streamline_points(path, nx, ny, nz, max_lines=max_lines - len(lines))

            if parsed:
                lines.extend(parsed)
                used_files.append(str(path.relative_to(ROOT)))

            if len(lines) >= max_lines:
                break

    payload = {
        "ok": bool(lines),
        "line_count": len(lines),
        "used_files": used_files,
        "lines": lines,
        "wells": get_hm_wells(),
        "dimension_source": dim_source,
        "message": (
            "Streamline overlay generated from SLN ID_CELL / CSV point artifacts. "
            "Lines are simplified for visual interpretation."
            if lines else
            "No streamlines could be converted to I,J. Check SLN files, ID_CELL, or CSV point exports."
        ),
    }

    payload["requested_streamline_time"] = time_key
    payload["streamline_snapshot_label"] = selected_streamline_snapshot_label(time_key)
    payload["selected_streamline_files_order"] = [str(p) for p in sln_files[:10]] if "sln_files" in locals() else []
    payload["all_streamline_files_seen"] = [str(p) for p in all_sln_files[:20]] if "all_sln_files" in locals() else []
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return payload


if __name__ == "__main__":
    p = build_streamline_visual_payload()
    print(f"ok={p['ok']} lines={p['line_count']}")
    print("dimension_source:", p.get("dimension_source"))
    print("used_files:")
    for f in p["used_files"]:
        print(" -", f)
    print("saved:", OUTPUT_JSON)



# ==========================================================
# STRICT STREAMLINE SNAPSHOT SELECTION V19
# This overrides file selection so initial requests never fall
# back to EOH/final files.
# ==========================================================

def streamline_snapshot_kind(path: Path) -> str:
    name = path.name.upper()

    initial_tokens = [
        "INITIAL", "INIT", "BOH", "BEG", "BEGIN", "START", "TIME_BEG", "TIMEBEG"
    ]

    final_tokens = [
        "EOH", "FINAL", "END", "LAST", "CURRENT", "TIME_END", "TIMEEND"
    ]

    if any(tok in name for tok in initial_tokens):
        return "initial"

    if any(tok in name for tok in final_tokens):
        return "final"

    return "unknown"


def filter_streamline_files_by_time(files, time_key: str):
    files = list(files or [])
    time_key = normalize_streamline_time_key(time_key)

    if time_key == "initial":
        selected = [p for p in files if streamline_snapshot_kind(p) == "initial"]
        return sorted(selected, key=lambda p: p.name)

    if time_key == "final":
        selected = [p for p in files if streamline_snapshot_kind(p) == "final"]
        return sorted(selected, key=lambda p: p.name)

    # auto keeps old preference: final first, then unknown, then initial
    return sorted(
        files,
        key=lambda p: (
            0 if streamline_snapshot_kind(p) == "final" else
            1 if streamline_snapshot_kind(p) == "unknown" else
            2,
            p.name
        )
    )


def snapshot_unavailable_payload(time_key: str, all_files):
    return {
        "ok": False,
        "lines": [],
        "requested_streamline_time": time_key,
        "streamline_snapshot_label": selected_streamline_snapshot_label(time_key),
        "selected_streamline_files_order": [],
        "available_streamline_files": [str(p) for p in all_files],
        "message": (
            f"No readable {selected_streamline_snapshot_label(time_key)} streamline files were found. "
            "I will not fall back to EOH/final streamlines because that would misrepresent the requested snapshot."
        ),
    }
