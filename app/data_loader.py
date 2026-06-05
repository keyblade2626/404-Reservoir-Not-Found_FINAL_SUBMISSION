import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


DATA_PATH = Path("data/sample_well_kpis.csv")


def _to_float(value: str) -> float:
    return float(value)


def load_well_kpis() -> List[Dict[str, Any]]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Sample data file not found: {DATA_PATH}")

    rows: List[Dict[str, Any]] = []

    with DATA_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        required_columns = {"well", "date", "opr", "wwpr", "wct", "gor", "bhp", "status"}
        missing = required_columns - set(reader.fieldnames or [])

        if missing:
            raise ValueError(f"Missing required columns in sample data: {sorted(missing)}")

        for row in reader:
            rows.append(
                {
                    "well": row["well"],
                    "date": datetime.strptime(row["date"], "%Y-%m-%d"),
                    "opr": _to_float(row["opr"]),
                    "wwpr": _to_float(row["wwpr"]),
                    "wct": _to_float(row["wct"]),
                    "gor": _to_float(row["gor"]),
                    "bhp": _to_float(row["bhp"]),
                    "status": row["status"],
                }
            )

    return rows


def summarize_well_kpis(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for row in rows:
        grouped.setdefault(row["well"], []).append(row)

    well_summaries: Dict[str, Any] = {}

    for well, group in grouped.items():
        group = sorted(group, key=lambda item: item["date"])

        first = group[0]
        last = group[-1]

        opr_change_pct = ((last["opr"] - first["opr"]) / first["opr"]) * 100 if first["opr"] else 0
        wct_change = last["wct"] - first["wct"]
        gor_change_pct = ((last["gor"] - first["gor"]) / first["gor"]) * 100 if first["gor"] else 0
        bhp_change = last["bhp"] - first["bhp"]

        well_summaries[well] = {
            "first_date": str(first["date"].date()),
            "last_date": str(last["date"].date()),
            "initial_opr": float(first["opr"]),
            "final_opr": float(last["opr"]),
            "opr_change_pct": round(float(opr_change_pct), 2),
            "initial_wct": float(first["wct"]),
            "final_wct": float(last["wct"]),
            "wct_change": round(float(wct_change), 3),
            "initial_gor": float(first["gor"]),
            "final_gor": float(last["gor"]),
            "gor_change_pct": round(float(gor_change_pct), 2),
            "initial_bhp": float(first["bhp"]),
            "final_bhp": float(last["bhp"]),
            "bhp_change": round(float(bhp_change), 2),
            "status": str(last["status"]),
        }

    return {
        "well_count": len(well_summaries),
        "wells": well_summaries,
    }
