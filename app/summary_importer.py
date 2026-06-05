from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_CASE_ROOT = Path("data/sample_model/CASE")


class SummaryImportError(RuntimeError):
    pass


def _load_resdata_summary(case_root: Path):
    """
    Loads native SMSPEC/UNSMRY summary data using resdata.

    Expected files:
      data/sample_model/CASE.SMSPEC
      data/sample_model/CASE.UNSMRY
    """
    try:
        from resdata.summary import Summary
    except Exception as exc:
        raise SummaryImportError(
            "resdata is not installed or cannot be imported. "
            "Native SMSPEC/UNSMRY ingestion requires resdata. "
            "If this fails on Windows, run inside Docker/Linux."
        ) from exc

    candidates = [
        str(case_root),
        str(case_root.with_suffix(".SMSPEC")),
    ]

    last_error: Optional[Exception] = None

    for candidate in candidates:
        try:
            return Summary(candidate)
        except Exception as exc:
            last_error = exc

    raise SummaryImportError(
        f"Could not load summary case from {case_root}. "
        f"Expected {case_root}.SMSPEC and {case_root}.UNSMRY. "
        f"Last error: {last_error}"
    )


def _get_summary_keys(summary_obj: Any) -> List[str]:
    """
    Tries common resdata/libecl-style APIs to list summary vectors.
    """
    for method_name in ["keys", "get_keys"]:
        if hasattr(summary_obj, method_name):
            method = getattr(summary_obj, method_name)
            try:
                keys = method()
                return sorted([str(k) for k in keys])
            except TypeError:
                try:
                    keys = method("*")
                    return sorted([str(k) for k in keys])
                except Exception:
                    pass
            except Exception:
                pass

    raise SummaryImportError(
        "Could not list summary vectors from resdata Summary object. "
        "The installed resdata API may differ from expected methods."
    )


def _get_dates(summary_obj: Any) -> List[str]:
    """
    Gets report dates using common APIs.
    """
    for attr_name in ["dates", "report_dates"]:
        if hasattr(summary_obj, attr_name):
            attr = getattr(summary_obj, attr_name)
            try:
                dates = attr() if callable(attr) else attr
                return [str(d) for d in dates]
            except Exception:
                pass

    return []


def _get_vector_values(summary_obj: Any, key: str) -> List[float]:
    """
    Gets values for one summary vector using common APIs.
    """
    candidates = [
        "numpy_vector",
        "get_values",
        "values",
    ]

    for method_name in candidates:
        if hasattr(summary_obj, method_name):
            method = getattr(summary_obj, method_name)
            try:
                values = method(key)
                return [float(v) for v in values]
            except Exception:
                pass

    try:
        values = summary_obj[key]
        return [float(v) for v in values]
    except Exception:
        pass

    raise SummaryImportError(f"Could not extract values for summary vector: {key}")


def _detect_well_keys(keys: List[str]) -> Dict[str, List[str]]:
    """
    Groups well summary vectors by well name.

    Common style:
      WOPR:WELL-01
      WWCT:WELL-01
      WGOR:WELL-01
      WBHP:WELL-01
    """
    well_keys: Dict[str, List[str]] = {}

    for key in keys:
        if ":" not in key:
            continue

        vector, well = key.split(":", 1)

        if vector.upper().startswith("W"):
            well_keys.setdefault(well, []).append(key)

    return well_keys


def import_native_summary(case_root: Path = DEFAULT_CASE_ROOT) -> Dict[str, Any]:
    smspec = case_root.with_suffix(".SMSPEC")
    unsmry = case_root.with_suffix(".UNSMRY")

    if not smspec.exists():
        raise FileNotFoundError(f"Missing SMSPEC file: {smspec}")

    if not unsmry.exists():
        raise FileNotFoundError(f"Missing UNSMRY file: {unsmry}")

    summary_obj = _load_resdata_summary(case_root)
    keys = _get_summary_keys(summary_obj)
    dates = _get_dates(summary_obj)
    well_key_map = _detect_well_keys(keys)

    field_keys = [k for k in keys if k.startswith("F")]
    well_keys = [k for k in keys if k.startswith("W")]

    return {
        "case_root": str(case_root),
        "smspec_file": str(smspec),
        "unsmry_file": str(unsmry),
        "summary_vector_count": len(keys),
        "date_count": len(dates),
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "available_vectors_sample": keys[:50],
        "field_vector_count": len(field_keys),
        "well_vector_count": len(well_keys),
        "well_count": len(well_key_map),
        "wells": sorted(well_key_map.keys()),
        "well_key_map": well_key_map,
    }


def extract_key_well_vectors(
    case_root: Path = DEFAULT_CASE_ROOT,
    requested_vectors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Extracts selected well vectors.

    Default vectors:
      WOPR, WWPR, WGPR, WWCT, WGOR, WBHP
    """
    requested_vectors = requested_vectors or ["WOPR", "WWPR", "WGPR", "WWCT", "WGOR", "WBHP"]

    summary_obj = _load_resdata_summary(case_root)
    keys = _get_summary_keys(summary_obj)
    dates = _get_dates(summary_obj)

    well_key_map = _detect_well_keys(keys)

    extracted: Dict[str, Any] = {}

    for well, well_keys in well_key_map.items():
        extracted[well] = {}

        for vector in requested_vectors:
            matching_keys = [
                key for key in well_keys
                if key.upper().startswith(f"{vector.upper()}:")
            ]

            if not matching_keys:
                continue

            key = matching_keys[0]

            try:
                values = _get_vector_values(summary_obj, key)
            except SummaryImportError:
                continue

            if not values:
                continue

            extracted[well][vector] = {
                "summary_key": key,
                "first_value": values[0],
                "last_value": values[-1],
                "min_value": min(values),
                "max_value": max(values),
                "change": values[-1] - values[0],
                "points": len(values),
            }

    return {
        "dates": dates,
        "requested_vectors": requested_vectors,
        "well_results": extracted,
    }


def build_native_summary_kpis(case_root: Path = DEFAULT_CASE_ROOT) -> Dict[str, Any]:
    """
    Builds first-pass KPIs directly from UNSMRY/SMSPEC.
    """
    overview = import_native_summary(case_root)
    vector_data = extract_key_well_vectors(case_root)

    well_kpis: Dict[str, Any] = {}

    for well, vectors in vector_data["well_results"].items():
        kpis: Dict[str, Any] = {}

        if "WOPR" in vectors:
            first = vectors["WOPR"]["first_value"]
            last = vectors["WOPR"]["last_value"]
            if abs(first) > 1e-9:
                kpis["opr_change_pct"] = round(((last - first) / first) * 100, 2)
            else:
                kpis["opr_change_pct"] = None

        if "WWCT" in vectors:
            kpis["wct_change"] = round(vectors["WWCT"]["change"], 4)
            kpis["final_wct"] = round(vectors["WWCT"]["last_value"], 4)

        if "WGOR" in vectors:
            first = vectors["WGOR"]["first_value"]
            last = vectors["WGOR"]["last_value"]
            if abs(first) > 1e-9:
                kpis["gor_change_pct"] = round(((last - first) / first) * 100, 2)
            else:
                kpis["gor_change_pct"] = None

        if "WBHP" in vectors:
            kpis["bhp_change"] = round(vectors["WBHP"]["change"], 2)

        well_kpis[well] = {
            "vectors": vectors,
            "kpis": kpis,
        }

    return {
        "source_type": "native_smspec_unsmry",
        "overview": overview,
        "well_kpis": well_kpis,
    }
