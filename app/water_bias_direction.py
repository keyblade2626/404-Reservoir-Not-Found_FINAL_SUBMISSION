from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Optional


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        if isinstance(v, str):
            s = v.strip().replace(",", "")
            if s == "" or s.lower() in {"nan", "none", "null", "n/a"}:
                return None
            return float(s)
        return float(v)
    except Exception:
        return None


def _well_matches(value: Any, well: str) -> bool:
    return str(value or "").strip().upper() == str(well or "").strip().upper()


def _is_water_key(k: str) -> bool:
    lk = str(k).lower()
    return any(x in lk for x in ["water", "wct", "wwct", "wwpr", "wwpt"])


def _is_bad_metric_key(k: str) -> bool:
    lk = str(k).lower()
    return any(x in lk for x in [
        "score", "percentile", "rank", "distance", "class", "flag",
        "direction", "bias", "issue", "quality", "hm",
    ])


def _is_sim_key(k: str) -> bool:
    lk = str(k).lower()
    return any(x in lk for x in ["sim", "simulated", "simulation", "model", "calc", "pred", "forecast"])


def _is_obs_key(k: str) -> bool:
    lk = str(k).lower()
    return any(x in lk for x in ["obs", "observed", "history", "hist", "meas", "actual"])


def _row_well(row: dict[str, Any]) -> str:
    for k in ["well", "well_name", "name", "wellName", "WELL", "WELL_NAME"]:
        if k in row:
            return str(row.get(k) or "")
    return ""


def _extract_pair_from_row(row: dict[str, Any]) -> Optional[tuple[float, float, str]]:
    sim_vals: list[tuple[str, float]] = []
    obs_vals: list[tuple[str, float]] = []

    for k, v in row.items():
        if not _is_water_key(k) or _is_bad_metric_key(k):
            continue

        val = _safe_float(v)
        if val is None:
            continue

        if _is_sim_key(k):
            sim_vals.append((k, val))
        elif _is_obs_key(k):
            obs_vals.append((k, val))

    if sim_vals and obs_vals:
        sk, sv = sim_vals[-1]
        ok, ov = obs_vals[-1]
        return sv, ov, f"{sk} vs {ok}"

    # Generic fallback for rows already scoped to water.
    keys = {str(k).lower(): k for k in row.keys()}
    sim_key = None
    obs_key = None

    for candidate in ["sim", "simulated", "simulation", "model", "forecast", "calculated"]:
        if candidate in keys:
            sim_key = keys[candidate]
            break

    for candidate in ["obs", "observed", "history", "hist", "actual", "measured"]:
        if candidate in keys:
            obs_key = keys[candidate]
            break

    if sim_key and obs_key:
        sv = _safe_float(row.get(sim_key))
        ov = _safe_float(row.get(obs_key))
        if sv is not None and ov is not None:
            return sv, ov, f"{sim_key} vs {obs_key}"

    return None


def _walk_json_records(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_json_records(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_json_records(item)


def _detect_from_json_file(path: Path, well: str) -> list[tuple[float, float, str]]:
    pairs: list[tuple[float, float, str]] = []

    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return pairs

    for row in _walk_json_records(data):
        if not isinstance(row, dict):
            continue

        row_well = _row_well(row)

        # Accept rows with matching well, or rows in clearly well-specific files.
        file_mentions_well = well.upper() in path.name.upper()

        if row_well and not _well_matches(row_well, well):
            continue

        if not row_well and not file_mentions_well:
            continue

        pair = _extract_pair_from_row(row)
        if pair:
            sim, obs, source = pair
            pairs.append((sim, obs, f"{path.name}: {source}"))

    return pairs


def _detect_from_csv_file(path: Path, well: str) -> list[tuple[float, float, str]]:
    pairs: list[tuple[float, float, str]] = []

    try:
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_well = _row_well(row)
                file_mentions_well = well.upper() in path.name.upper()

                if row_well and not _well_matches(row_well, well):
                    continue

                if not row_well and not file_mentions_well:
                    continue

                pair = _extract_pair_from_row(row)
                if pair:
                    sim, obs, source = pair
                    pairs.append((sim, obs, f"{path.name}: {source}"))

    except Exception:
        pass

    return pairs


def detect_water_bias_direction(well: str, root: Optional[Path] = None, threshold: float = 0.05) -> dict[str, Any]:
    """
    Detect water mismatch sign from actual stored dashboard/profile artifacts.

    Returns:
      direction = overestimated_wct  when simulated water > observed water
      direction = underestimated_wct when simulated water < observed water
      direction = unknown            when not enough evidence
    """
    root = root or Path(__file__).resolve().parents[1]
    artifacts = root / "artifacts"

    well_norm = str(well or "").strip().upper()

    if not artifacts.exists():
        return {
            "direction": "unknown",
            "method": "artifacts_missing",
            "well": well_norm,
        }

    pairs: list[tuple[float, float, str]] = []

    candidate_files: list[Path] = []

    for ext in ["*.json", "*.csv"]:
        for p in artifacts.rglob(ext):
            if not p.is_file():
                continue

            # Avoid huge files and unrelated cache dumps.
            try:
                if p.stat().st_size > 40_000_000:
                    continue
            except Exception:
                continue

            name = p.name.lower()
            path_s = str(p).lower()

            # Prefer profile/history/dashboard-like files, but keep enough recall.
            if any(x in name or x in path_s for x in [
                "profile", "water", "wct", "wwct", "wwpr", "summary",
                "well", "diagnosis", "dashboard", "hm", "history",
            ]):
                candidate_files.append(p)

    # Search well-specific files first.
    candidate_files = sorted(
        set(candidate_files),
        key=lambda p: (
            well_norm not in p.name.upper(),
            len(str(p)),
            str(p).lower(),
        ),
    )

    for p in candidate_files:
        if p.suffix.lower() == ".json":
            pairs.extend(_detect_from_json_file(p, well_norm))
        elif p.suffix.lower() == ".csv":
            pairs.extend(_detect_from_csv_file(p, well_norm))

        # Enough evidence; avoid scanning everything forever.
        if len(pairs) >= 200:
            break

    if not pairs:
        return {
            "direction": "unknown",
            "method": "no_profile_pairs_found",
            "well": well_norm,
            "files_scanned": len(candidate_files),
        }

    # Use late-profile behavior: last 30% of available pairs, minimum 3 if possible.
    n = len(pairs)
    tail_n = max(3, int(n * 0.30)) if n >= 3 else n
    tail = pairs[-tail_n:]

    sim_mean = sum(x[0] for x in tail) / len(tail)
    obs_mean = sum(x[1] for x in tail) / len(tail)

    denom = max(abs(sim_mean), abs(obs_mean), 1e-9)
    rel = (sim_mean - obs_mean) / denom

    if rel > threshold:
        direction = "overestimated_wct"
    elif rel < -threshold:
        direction = "underestimated_wct"
    else:
        direction = "balanced_or_timing_issue"

    return {
        "direction": direction,
        "method": "artifact_profile_tail_mean",
        "well": well_norm,
        "sim_mean_tail": sim_mean,
        "obs_mean_tail": obs_mean,
        "relative_bias": rel,
        "pairs_used": len(tail),
        "pairs_found": len(pairs),
        "evidence_sample": tail[-5:],
    }
