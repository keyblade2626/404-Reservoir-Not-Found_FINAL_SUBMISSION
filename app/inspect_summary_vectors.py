import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.summary_importer import (
    DEFAULT_CASE_ROOT,
    _get_summary_keys,
    _get_vector_values,
    _load_resdata_summary,
)


def get_key(keys_upper_map: Dict[str, str], vector: str, well: str) -> Optional[str]:
    return keys_upper_map.get(f"{vector}:{well}".upper())


def describe_vector(summary_obj: Any, keys_upper_map: Dict[str, str], vector: str, well: str) -> None:
    key = get_key(keys_upper_map, vector, well)

    if not key:
        print(f"{vector:<8} MISSING")
        return

    try:
        values = _get_vector_values(summary_obj, key)
    except Exception as exc:
        print(f"{vector:<8} ERROR reading {key}: {exc}")
        return

    if not values:
        print(f"{vector:<8} EMPTY")
        return

    non_zero = [v for v in values if abs(v) > 1e-12]

    print(
        f"{vector:<8} key={key:<25} "
        f"points={len(values):<5} "
        f"min={min(values):<14.6g} "
        f"max={max(values):<14.6g} "
        f"first={values[0]:<14.6g} "
        f"last={values[-1]:<14.6g} "
        f"non_zero={len(non_zero)}"
    )


def inspect_well(well: str) -> None:
    summary_obj = _load_resdata_summary(DEFAULT_CASE_ROOT)
    keys = _get_summary_keys(summary_obj)
    keys_upper_map = {key.upper(): key for key in keys}

    print("")
    print("=" * 100)
    print(f"WELL: {well}")
    print("=" * 100)

    vectors = [
        "WOPR", "WOPRH", "WOPT", "WOPTH",
        "WWPR", "WWPRH", "WWPT", "WWPTH",
        "WGPR", "WGPRH", "WGPT", "WGPTH",
        "WWCT", "WWCTH",
        "WGOR", "WGORH",
        "WBHP", "WBHPH",
        "WWIR", "WWIRH",
        "WGIR", "WGIRH"
    ]

    for vector in vectors:
        describe_vector(summary_obj, keys_upper_map, vector, well)

    print("")
    print("All keys containing this well:")
    well_keys = [k for k in keys if f":{well}".upper() in k.upper()]
    for k in sorted(well_keys):
        print("  " + k)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wells", nargs="+", required=True)
    args = parser.parse_args()

    for well in args.wells:
        inspect_well(well)


if __name__ == "__main__":
    main()
