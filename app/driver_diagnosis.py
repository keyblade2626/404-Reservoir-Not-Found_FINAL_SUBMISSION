import csv
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.history_match import build_history_match_kpis
from app.well_connections import get_well_spatial_summary


MODEL_DIR = Path("data/sample_model")
GRID_DIMENSIONS_FILE = MODEL_DIR / "grid_dimensions.json"
OUTPUT_DIR = Path("artifacts/diagnosis")

LIQUID_RATE_NEGLIGIBLE_THRESHOLD = 10.0


PROPERTY_SPECS = {
    "tran_x": {"files": ["TRANX.GRDECL", "TRAN_X.GRDECL"], "keywords": ["TRANX", "TRAN_X"]},
    "tran_y": {"files": ["TRANY.GRDECL", "TRAN_Y.GRDECL"], "keywords": ["TRANY", "TRAN_Y"]},
    "tran_z": {"files": ["TRANZ.GRDECL", "TRAN_Z.GRDECL"], "keywords": ["TRANZ", "TRAN_Z"]},

    "mult_x": {"files": ["MULTX.GRDECL", "MULT_X.GRDECL"], "keywords": ["MULTX", "MULT_X"]},
    "mult_y": {"files": ["MULTY.GRDECL", "MULT_Y.GRDECL"], "keywords": ["MULTY", "MULT_Y"]},
    "mult_z": {"files": ["MULTZ.GRDECL", "MULT_Z.GRDECL"], "keywords": ["MULTZ", "MULT_Z"]},

    "perm_x": {"files": ["PERM_X.GRDECL", "PERMX.GRDECL", "PERM_I.GRDECL"], "keywords": ["PERMX", "PERM_X", "PERM_I"]},
    "perm_y": {"files": ["PERM_Y.GRDECL", "PERMY.GRDECL", "PERM_J.GRDECL"], "keywords": ["PERMY", "PERM_Y", "PERM_J"]},
    "perm_z": {"files": ["PERM_Z.GRDECL", "PERMZ.GRDECL", "PERM_K.GRDECL"], "keywords": ["PERMZ", "PERM_Z", "PERM_K"]},

    "swat_init": {
        "files": ["SWAT_INIT.GRDECL", "SWATER_INIT.GRDECL", "SWAT_INITIAL.GRDECL", "SWATER_INITIAL.GRDECL"],
        "keywords": ["SWAT", "SWATER"],
    },
    "swat_eoh": {
        "files": ["SWAT_EOH.GRDECL", "SWATER_EOH.GRDECL", "SWAT_END.GRDECL", "SWATER_END.GRDECL", "SWAT_FINAL.GRDECL"],
        "keywords": ["SWAT", "SWATER"],
    },

    "soil_init": {"files": ["SOIL_INIT.GRDECL", "SOIL_INITIAL.GRDECL"], "keywords": ["SOIL"]},
    "soil_eoh": {"files": ["SOIL_EOH.GRDECL", "SOIL_END.GRDECL", "SOIL_FINAL.GRDECL"], "keywords": ["SOIL"]},

    "sgas_init": {"files": ["SGAS_INIT.GRDECL", "SGAS_INITIAL.GRDECL"], "keywords": ["SGAS"]},
    "sgas_eoh": {"files": ["SGAS_EOH.GRDECL", "SGAS_END.GRDECL", "SGAS_FINAL.GRDECL"], "keywords": ["SGAS"]},

    "pressure_init": {"files": ["PRESSURE_INIT.GRDECL", "PRESSURE_INITIAL.GRDECL"], "keywords": ["PRESSURE"]},
    "pressure_eoh": {"files": ["PRESSURE_EOH.GRDECL", "PRESSURE_END.GRDECL", "PRESSURE_FINAL.GRDECL"], "keywords": ["PRESSURE"]},

    "poro": {"files": ["PORO.GRDECL", "POROSITY.GRDECL"], "keywords": ["PORO", "POROSITY"]},
    "poro_mult": {"files": ["PORO_MULT.GRDECL", "POROMULT.GRDECL", "MULTPV.GRDECL"], "keywords": ["PORO_MULT", "POROMULT", "MULTPV"]},
}


TOKEN_PATTERN = re.compile(
    r"(?P<repeat>\d+)\*(?P<value>[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?)|"
    r"(?P<number>[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?)|"
    r"(?P<default_repeat>\d+)\*"
)


def strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if "--" in line:
            line = line.split("--", 1)[0]
        lines.append(line)
    return "\n".join(lines)


def find_existing_file(candidates: List[str]) -> Optional[Path]:
    for filename in candidates:
        path = MODEL_DIR / filename
        if path.exists():
            return path
    return None


def expand_grdecl_values(block: str) -> List[float]:
    values: List[float] = []

    for match in TOKEN_PATTERN.finditer(block):
        if match.group("repeat") is not None:
            values.extend([float(match.group("value"))] * int(match.group("repeat")))
        elif match.group("number") is not None:
            values.append(float(match.group("number")))
        elif match.group("default_repeat") is not None:
            values.extend([0.0] * int(match.group("default_repeat")))

    return values


def read_grdecl_property(prop_name: str, expected_count: int) -> Optional[Dict[str, Any]]:
    spec = PROPERTY_SPECS[prop_name]
    path = find_existing_file(spec["files"])

    if path is None:
        return None

    text = strip_comments(path.read_text(encoding="utf-8", errors="ignore"))

    for keyword in spec["keywords"]:
        pattern = re.compile(
            rf"\b{re.escape(keyword)}\b(?P<body>.*?)/",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(text)

        if not match:
            continue

        values = expand_grdecl_values(match.group("body"))

        if len(values) != expected_count:
            raise ValueError(
                f"{path.name} keyword {keyword} has {len(values)} values, "
                f"but grid requires {expected_count}."
            )

        return {
            "name": prop_name,
            "source_file": str(path),
            "keyword": keyword,
            "values": values,
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
        }

    raise ValueError(f"{path} exists, but none of these keywords were found: {spec['keywords']}")


def load_grid_dimensions() -> Dict[str, int]:
    data = json.loads(GRID_DIMENSIONS_FILE.read_text(encoding="utf-8-sig"))
    nx = int(data["nx"])
    ny = int(data["ny"])
    nz = int(data["nz"])

    return {"nx": nx, "ny": ny, "nz": nz, "cell_count": nx * ny * nz}


def cell_to_index(i: int, j: int, k: int, dims: Dict[str, int]) -> int:
    nx = dims["nx"]
    ny = dims["ny"]
    nz = dims["nz"]

    if not (1 <= i <= nx and 1 <= j <= ny and 1 <= k <= nz):
        raise IndexError(f"Cell ({i},{j},{k}) outside grid ({nx},{ny},{nz}).")

    return (k - 1) * nx * ny + (j - 1) * nx + (i - 1)


def get_cell_value(prop: Optional[Dict[str, Any]], i: int, j: int, k: int, dims: Dict[str, int]) -> Optional[float]:
    if prop is None:
        return None

    try:
        return float(prop["values"][cell_to_index(i, j, k, dims)])
    except Exception:
        return None


def average(values: List[Optional[float]]) -> Optional[float]:
    clean = [float(v) for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


def maximum(values: List[Optional[float]]) -> Optional[float]:
    clean = [float(v) for v in values if v is not None]
    return max(clean) if clean else None


def weighted_average(values: List[Optional[float]], weights: List[Optional[float]]) -> Optional[float]:
    pairs = [
        (float(v), max(float(w), 0.0))
        for v, w in zip(values, weights)
        if v is not None and w is not None
    ]

    if not pairs:
        return None

    total_weight = sum(w for _, w in pairs)

    if total_weight <= 1e-12:
        return sum(v for v, _ in pairs) / len(pairs)

    return sum(v * w for v, w in pairs) / total_weight


def percentile(value: Optional[float], population: List[Optional[float]]) -> Optional[float]:
    if value is None:
        return None

    clean = sorted(float(v) for v in population if v is not None)

    if not clean:
        return None

    return round(100.0 * sum(1 for v in clean if v <= float(value)) / len(clean), 2)


def safe_sqrt_product(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return math.sqrt(max(float(a), 0.0) * max(float(b), 0.0))


def parse_event_date(value: Optional[Any]) -> Optional[datetime]:
    if not value:
        return None

    text = str(value).replace("Z", "").strip()

    try:
        return datetime.fromisoformat(text)
    except Exception:
        pass

    match = re.search(r"\d{4}-\d{2}-\d{2}", text)

    if match:
        try:
            return datetime.fromisoformat(match.group(0))
        except Exception:
            return None

    return None


def classify_water_timing(water_result: Dict[str, Any]) -> Dict[str, Any]:
    events = water_result.get("events", {})

    sim_date = parse_event_date(events.get("sim_water_breakthrough_date"))
    hist_date = parse_event_date(events.get("hist_water_breakthrough_date"))

    if sim_date is None and hist_date is None:
        return {
            "water_timing_issue": "no_breakthrough_detected",
            "water_breakthrough_delta_days": None,
            "sim_water_breakthrough_date": None,
            "hist_water_breakthrough_date": None,
        }

    if sim_date is not None and hist_date is None:
        return {
            "water_timing_issue": "simulated_breakthrough_only",
            "water_breakthrough_delta_days": None,
            "sim_water_breakthrough_date": str(sim_date),
            "hist_water_breakthrough_date": None,
        }

    if sim_date is None and hist_date is not None:
        return {
            "water_timing_issue": "historical_breakthrough_only",
            "water_breakthrough_delta_days": None,
            "sim_water_breakthrough_date": None,
            "hist_water_breakthrough_date": str(hist_date),
        }

    delta_days = (sim_date - hist_date).days

    if delta_days <= -365:
        issue = "early_breakthrough"
    elif delta_days >= 365:
        issue = "delayed_breakthrough"
    else:
        issue = "breakthrough_timing_close"

    return {
        "water_timing_issue": issue,
        "water_breakthrough_delta_days": delta_days,
        "sim_water_breakthrough_date": str(sim_date),
        "hist_water_breakthrough_date": str(hist_date),
    }


def classify_water_direction(water_result: Dict[str, Any]) -> str:
    if water_result.get("negligible_match"):
        return "negligible_matched"

    if water_result.get("status") != "evaluated":
        return "not_evaluated"

    sim = water_result.get("last_sim_value")
    hist = water_result.get("last_hist_value")

    if sim is None or hist is None:
        return "unknown"

    sim = float(sim)
    hist = float(hist)

    tolerance = 0.05

    if sim > hist + tolerance:
        return "simulated_too_high"

    if sim < hist - tolerance:
        return "simulated_too_low"

    return "final_value_close"


def is_negligible_variable(result: Dict[str, Any]) -> bool:
    return bool(result.get("negligible_match"))


def variable_has_no_data(result: Dict[str, Any]) -> bool:
    return result.get("status") in ["inactive", "unavailable"] or result.get("score") is None


def classify_well_activity(hm_payload: Dict[str, Any]) -> str:
    """
    Separates true HM problems from wells where there is no meaningful production signal.

    If oil, water and gas are all negligible or unavailable, we do not comment HM.
    """
    variables = hm_payload.get("variables", {})

    oil = variables.get("oil", {})
    water = variables.get("watercut", {})
    gas = variables.get("gor", {})

    core = [oil, water, gas]

    negligible_count = sum(1 for r in core if is_negligible_variable(r))
    no_data_count = sum(1 for r in core if variable_has_no_data(r))

    if negligible_count + no_data_count == len(core):
        return "no_material_flow_or_no_evaluable_simulation"

    return "active_or_partially_active"


def build_row_for_well(
    well: str,
    spatial_payload: Dict[str, Any],
    hm_payload: Dict[str, Any],
    properties: Dict[str, Optional[Dict[str, Any]]],
    dims: Dict[str, int],
) -> Dict[str, Any]:
    connections = [
        c for c in spatial_payload.get("connections", [])
        if str(c.get("status", "")).upper() == "OPEN"
    ]

    if not connections:
        connections = spatial_payload.get("connections", [])

    collected: Dict[str, List[Optional[float]]] = {name: [] for name in properties}

    tran_h_values: List[Optional[float]] = []
    mult_h_values: List[Optional[float]] = []
    perm_h_values: List[Optional[float]] = []

    wellconn_trans_weights: List[Optional[float]] = []
    kh_weights: List[Optional[float]] = []

    for c in connections:
        i = int(c["i"])
        j = int(c["j"])
        k = int(c["k"])

        cell_values: Dict[str, Optional[float]] = {}

        for prop_name, prop in properties.items():
            value = get_cell_value(prop, i, j, k, dims)
            collected[prop_name].append(value)
            cell_values[prop_name] = value

        tran_h_values.append(safe_sqrt_product(cell_values.get("tran_x"), cell_values.get("tran_y")))
        mult_h_values.append(safe_sqrt_product(cell_values.get("mult_x"), cell_values.get("mult_y")))
        perm_h_values.append(safe_sqrt_product(cell_values.get("perm_x"), cell_values.get("perm_y")))

        wellconn_trans_weights.append(float(c.get("transmissibility") or 0.0))
        kh_weights.append(float(c.get("permeability_thickness") or 0.0))

    variables = hm_payload.get("variables", {})

    water = variables.get("watercut", {})
    oil = variables.get("oil", {})
    gas = variables.get("gor", {})
    bhp = variables.get("bhp", {})

    timing = classify_water_timing(water)

    row = {
        "well": well,
        "i": spatial_payload.get("representative_i"),
        "j": spatial_payload.get("representative_j"),
        "open_connection_count": spatial_payload.get("open_connection_count"),
        "used_connection_count": len(connections),

        "well_activity_status": classify_well_activity(hm_payload),

        "overall_hm_score": hm_payload.get("hm_score"),
        "overall_hm_class": hm_payload.get("hm_class"),

        "water_hm_score": water.get("score"),
        "water_hm_class": water.get("class"),
        "water_status": water.get("status"),
        "water_negligible_match": water.get("negligible_match", False),
        "water_direction": classify_water_direction(water),
        "water_timing_issue": timing["water_timing_issue"],
        "water_breakthrough_delta_days": timing["water_breakthrough_delta_days"],
        "sim_water_breakthrough_date": timing["sim_water_breakthrough_date"],
        "hist_water_breakthrough_date": timing["hist_water_breakthrough_date"],
        "water_full_trend_score": water.get("components", {}).get("full_trend_score"),
        "water_recent_2yr_score": water.get("components", {}).get("recent_2yr_trend_score"),
        "water_final_score": water.get("components", {}).get("final_score"),
        "water_max_sim_signal": water.get("max_sim_signal"),
        "water_max_hist_signal": water.get("max_hist_signal"),

        "oil_hm_score": oil.get("score"),
        "oil_hm_class": oil.get("class"),
        "oil_status": oil.get("status"),
        "oil_negligible_match": oil.get("negligible_match", False),
        "oil_max_sim_signal": oil.get("max_sim_signal"),
        "oil_max_hist_signal": oil.get("max_hist_signal"),

        "gas_hm_score": gas.get("score"),
        "gas_hm_class": gas.get("class"),
        "gas_status": gas.get("status"),
        "gas_negligible_match": gas.get("negligible_match", False),
        "gas_max_sim_signal": gas.get("max_sim_signal"),
        "gas_max_hist_signal": gas.get("max_hist_signal"),

        "bhp_hm_score": bhp.get("score"),
        "bhp_hm_class": bhp.get("class"),
        "bhp_status": bhp.get("status"),

        "mean_tran_h": average(tran_h_values),
        "max_tran_h": maximum(tran_h_values),
        "wellconn_weighted_tran_h": weighted_average(tran_h_values, wellconn_trans_weights),
        "kh_weighted_tran_h": weighted_average(tran_h_values, kh_weights),

        "mean_tran_z": average(collected["tran_z"]),
        "max_tran_z": maximum(collected["tran_z"]),

        "mean_mult_h": average(mult_h_values),
        "max_mult_h": maximum(mult_h_values),
        "mean_mult_z": average(collected["mult_z"]),
        "max_mult_z": maximum(collected["mult_z"]),

        "mean_perm_h": average(perm_h_values),
        "max_perm_h": maximum(perm_h_values),
        "mean_perm_z": average(collected["perm_z"]),
        "max_perm_z": maximum(collected["perm_z"]),

        "mean_swat_init": average(collected["swat_init"]),
        "mean_swat_eoh": average(collected["swat_eoh"]),
        "delta_swat": None,

        "mean_soil_init": average(collected["soil_init"]),
        "mean_soil_eoh": average(collected["soil_eoh"]),
        "delta_soil": None,

        "mean_sgas_init": average(collected["sgas_init"]),
        "mean_sgas_eoh": average(collected["sgas_eoh"]),
        "delta_sgas": None,

        "mean_pressure_init": average(collected["pressure_init"]),
        "mean_pressure_eoh": average(collected["pressure_eoh"]),
        "delta_pressure": None,

        "mean_poro": average(collected["poro"]),
        "mean_poro_mult": average(collected["poro_mult"]),

        "wellconn_total_transmissibility": spatial_payload.get("total_transmissibility"),
        "wellconn_mean_transmissibility": spatial_payload.get("mean_transmissibility"),
        "wellconn_max_transmissibility": spatial_payload.get("max_transmissibility"),
        "wellconn_total_kh": spatial_payload.get("total_permeability_thickness"),
        "wellconn_mean_kh": spatial_payload.get("mean_permeability_thickness"),
    }

    if row["mean_swat_init"] is not None and row["mean_swat_eoh"] is not None:
        row["delta_swat"] = row["mean_swat_eoh"] - row["mean_swat_init"]

    if row["mean_soil_init"] is not None and row["mean_soil_eoh"] is not None:
        row["delta_soil"] = row["mean_soil_eoh"] - row["mean_soil_init"]

    if row["mean_sgas_init"] is not None and row["mean_sgas_eoh"] is not None:
        row["delta_sgas"] = row["mean_sgas_eoh"] - row["mean_sgas_init"]

    if row["mean_pressure_init"] is not None and row["mean_pressure_eoh"] is not None:
        row["delta_pressure"] = row["mean_pressure_eoh"] - row["mean_pressure_init"]

    return row


def add_percentiles(rows: List[Dict[str, Any]]) -> None:
    fields = [
        "mean_tran_h",
        "max_tran_h",
        "wellconn_weighted_tran_h",
        "kh_weighted_tran_h",
        "wellconn_total_transmissibility",
        "wellconn_mean_transmissibility",
        "wellconn_max_transmissibility",
        "mean_tran_z",
        "mean_mult_h",
        "max_mult_h",
        "mean_mult_z",
        "max_mult_z",
        "mean_perm_h",
        "mean_perm_z",
        "mean_swat_eoh",
        "delta_swat",
        "mean_pressure_eoh",
        "delta_pressure",
        "wellconn_total_kh",
        "mean_poro",
        "mean_poro_mult",
    ]

    for field in fields:
        population = [row.get(field) for row in rows]

        for row in rows:
            row[f"{field}_percentile"] = percentile(row.get(field), population)


def pct_text(value: Optional[float]) -> str:
    return "N/A" if value is None else f"P{value:.0f}"


def num_text(value: Optional[float], digits: int = 3) -> str:
    return "N/A" if value is None else f"{float(value):.{digits}f}"



def both_sim_and_history_negligible(row: Dict[str, Any], variable_prefix: str) -> bool:
    """
    True only when we have evidence that both simulated and historical signal
    are negligible. This is stronger than 'unavailable'.
    """
    negligible_key = f"{variable_prefix}_negligible_match"

    if row.get(negligible_key) is True:
        return True

    sim_key = f"{variable_prefix}_max_sim_signal"
    hist_key = f"{variable_prefix}_max_hist_signal"

    sim = row.get(sim_key)
    hist = row.get(hist_key)

    if sim is None or hist is None:
        return False

    try:
        return float(sim) <= LIQUID_RATE_NEGLIGIBLE_THRESHOLD and float(hist) <= LIQUID_RATE_NEGLIGIBLE_THRESHOLD
    except Exception:
        return False


def water_is_inactive_in_sim_and_history(row: Dict[str, Any]) -> bool:
    """
    This is used for cases like a well that exists in WELL_CONNECTIONS
    but has no material simulated and historical water signal.

    It should not be used when vectors are simply missing or unreadable.
    """
    return both_sim_and_history_negligible(row, "water")


def well_is_inactive_in_sim_and_history(row: Dict[str, Any]) -> bool:
    """
    Strong inactivity test:
    oil, water and gas are all negligible in both simulation and history.
    If data is missing, we do not claim inactive; we classify as not interpretable.
    """
    return (
        both_sim_and_history_negligible(row, "oil")
        and both_sim_and_history_negligible(row, "water")
        and both_sim_and_history_negligible(row, "gas")
    )



def choose_action_category(row: Dict[str, Any]) -> str:
    """
    Selects the dominant diagnostic category.

    Important:
    - Timing has priority over final value.
    - If early/delayed breakthrough is not supported by local TRAN/MULT evidence,
      we explicitly say that instead of returning a generic profile-timing comment.
    - If water score is zero but no direction/breakthrough is interpretable,
      we do not generate a reservoir-property recommendation.
    """

    water_score = row.get("water_hm_score")
    timing = row.get("water_timing_issue")
    direction = row.get("water_direction")

    # Strong no-comment cases.
    if row.get("well_activity_status") == "no_material_flow_or_no_evaluable_simulation":
        return "no_hm_comment"

    if row.get("water_negligible_match") is True:
        return "inactive_water_in_sim_and_history"

    if water_score is None:
        return "water_signal_not_interpretable"

    # Case like HW-25 in your output:
    # score 0, unknown direction, no breakthrough detected.
    # This should not become a transmissibility recommendation.
    if float(water_score) == 0.0 and direction == "unknown" and timing == "no_breakthrough_detected":
        return "water_signal_not_interpretable"

    if float(water_score) >= 80.0:
        return "no_water_action"

    tran_pct = row.get("mean_tran_h_percentile")
    max_tran_pct = row.get("max_tran_h_percentile")
    weighted_tran_pct = row.get("wellconn_weighted_tran_h_percentile")
    wellconn_pct = row.get("wellconn_total_transmissibility_percentile")
    kh_pct = row.get("wellconn_total_kh_percentile")

    mult_h = row.get("mean_mult_h")
    mult_z = row.get("mean_mult_z")
    swat_eoh = row.get("mean_swat_eoh")
    delta_swat = row.get("delta_swat")

    high_tran = any(
        pct is not None and float(pct) >= 75.0
        for pct in [tran_pct, max_tran_pct, weighted_tran_pct, wellconn_pct, kh_pct]
    )

    low_tran = (
        tran_pct is not None and float(tran_pct) <= 25.0
        and wellconn_pct is not None and float(wellconn_pct) <= 25.0
    )

    high_mult_h = mult_h is not None and float(mult_h) > 1.05
    low_mult_h = mult_h is not None and float(mult_h) < 0.95
    high_mult_z = mult_z is not None and float(mult_z) > 1.05

    high_swat = swat_eoh is not None and float(swat_eoh) >= 0.45
    low_swat = swat_eoh is not None and float(swat_eoh) < 0.25
    increasing_swat = delta_swat is not None and float(delta_swat) > 0.05

    # ------------------------------------------------------------
    # Early / over-water cases.
    # ------------------------------------------------------------
    if timing in ["early_breakthrough", "simulated_breakthrough_only"]:
        if high_mult_h:
            return "review_lateral_trans_multiplier"
        if high_mult_z:
            return "review_vertical_trans_multiplier"
        if high_tran:
            return "review_base_transmissibility"
        if high_swat or increasing_swat:
            return "review_water_front_or_relperm"
        return "early_breakthrough_no_local_driver"

    if direction in ["simulated_too_high", "simulated_too_high_signal"]:
        if high_mult_h:
            return "review_lateral_trans_multiplier"
        if high_mult_z:
            return "review_vertical_trans_multiplier"
        if high_tran:
            return "review_base_transmissibility"
        if high_swat or increasing_swat:
            return "review_water_front_or_relperm"
        return "overpredicted_water_no_local_driver"

    # ------------------------------------------------------------
    # Delayed / under-water cases.
    # ------------------------------------------------------------
    if timing in ["delayed_breakthrough", "historical_breakthrough_only"]:
        if low_mult_h:
            return "review_low_lateral_multiplier"
        if low_tran:
            return "review_under_connectivity"
        if low_swat:
            return "review_water_front_support"
        if high_swat:
            return "review_relperm_or_well_connection"
        return "delayed_breakthrough_no_local_driver"

    if direction in ["simulated_too_low", "simulated_too_low_signal"]:
        if low_mult_h:
            return "review_low_lateral_multiplier"
        if low_tran:
            return "review_under_connectivity"
        if low_swat:
            return "review_water_front_support"
        if high_swat:
            return "review_relperm_or_well_connection"
        return "underpredicted_water_no_local_driver"

    # ------------------------------------------------------------
    # Final close, but score poor/fair: shape/timing issue.
    # ------------------------------------------------------------
    if direction == "final_value_close":
        return "profile_shape_mismatch"

    return "water_signal_not_interpretable"



def make_specific_interpretation(row: Dict[str, Any]) -> Dict[str, Any]:
    action = choose_action_category(row)

    water_score = row.get("water_hm_score")
    water_class = row.get("water_hm_class")
    timing = row.get("water_timing_issue")
    direction = row.get("water_direction")

    tran_pct = row.get("mean_tran_h_percentile")
    max_tran_pct = row.get("max_tran_h_percentile")
    weighted_tran_pct = row.get("wellconn_weighted_tran_h_percentile")
    wellconn_pct = row.get("wellconn_total_transmissibility_percentile")
    kh_pct = row.get("wellconn_total_kh_percentile")

    mult_h = row.get("mean_mult_h")
    mult_z = row.get("mean_mult_z")

    swat_eoh = row.get("mean_swat_eoh")
    delta_swat = row.get("delta_swat")
    pressure_delta = row.get("delta_pressure")

    evidence = [
        f"Water HM score = {num_text(water_score, 2)} ({water_class}).",
        f"Water timing issue = {timing}.",
        f"Water direction based on final value = {direction}.",
        f"Breakthrough delta days = {row.get('water_breakthrough_delta_days')}.",
        f"Sim water breakthrough = {row.get('sim_water_breakthrough_date')}.",
        f"Hist water breakthrough = {row.get('hist_water_breakthrough_date')}.",
        f"TRAN_H percentile = {pct_text(tran_pct)}.",
        f"Max TRAN_H percentile = {pct_text(max_tran_pct)}.",
        f"Well-connection total transmissibility percentile = {pct_text(wellconn_pct)}.",
        f"Well-connection weighted TRAN_H percentile = {pct_text(weighted_tran_pct)}.",
        f"KH percentile = {pct_text(kh_pct)}.",
        f"mean MULT_H = {num_text(mult_h, 3)}.",
        f"mean MULT_Z = {num_text(mult_z, 3)}.",
        f"mean SWAT_EOH = {num_text(swat_eoh, 3)}.",
        f"delta SWAT = {num_text(delta_swat, 3)}.",
        f"delta PRESSURE = {num_text(pressure_delta, 2)}.",
    ]

    confidence = "medium"

    # ------------------------------------------------------------
    # No-comment / inactive cases
    # ------------------------------------------------------------
    if action == "no_hm_comment":
        interpretation = (
            f"{row['well']} is present in the spatial/well-connection data, but there is no material or evaluable "
            "production signal to support a history-match diagnostic. No reservoir-property calibration action is generated."
        )
        primary_action = "Confirm well status, schedule and availability of simulated/observed vectors before using this well for calibration."
        confidence = "high"

    elif action == "inactive_water_in_sim_and_history":
        interpretation = (
            f"{row['well']} is present in the model, but the water signal is negligible in both simulation and historical data. "
            "Therefore this is not treated as a water history-match problem."
        )
        primary_action = "No water-specific calibration action. Do not adjust transmissibility or relperm based on water for this well."
        confidence = "high"

    elif action == "no_water_action":
        interpretation = (
            f"{row['well']} has acceptable or negligible water mismatch. No water-specific diagnostic action is required."
        )
        primary_action = "No water-specific action."
        confidence = "high"

    # ------------------------------------------------------------
    # Specific over-communication cases
    # ------------------------------------------------------------
    elif action == "review_lateral_trans_multiplier":
        interpretation = (
            f"{row['well']} has water mismatch with evidence of lateral transmissibility multiplier influence. "
            f"mean MULT_H={num_text(mult_h, 3)}, TRAN_H={pct_text(tran_pct)}, "
            f"well-connection transmissibility={pct_text(wellconn_pct)}. "
            "The mismatch may be amplified by MULTX/MULTY rather than by base permeability alone."
        )
        primary_action = "Review MULTX/MULTY around completed cells before modifying base PERM/TRAN or relperm."
        confidence = "high"

    elif action == "review_vertical_trans_multiplier":
        interpretation = (
            f"{row['well']} has water mismatch with elevated vertical multiplier. "
            f"mean MULT_Z={num_text(mult_z, 3)}. Vertical communication may contribute to the mismatch."
        )
        primary_action = "Review MULTZ/TRANZ and vertical communication around the completed interval."
        confidence = "high"

    elif action == "review_base_transmissibility":
        interpretation = (
            f"{row['well']} has water mismatch and high local connectivity. "
            f"TRAN_H={pct_text(tran_pct)}, max TRAN_H={pct_text(max_tran_pct)}, "
            f"well-connection transmissibility={pct_text(wellconn_pct)}, KH={pct_text(kh_pct)}, "
            f"mean MULT_H={num_text(mult_h, 3)}. "
            "Because multipliers are not clearly dominant, the base TRAN/PERM corridor or completion KH may be driving the issue."
        )
        primary_action = "Review base TRANX/TRANY, PERM_H corridor and completion KH around the well."
        confidence = "high"

    elif action == "review_water_front_or_relperm":
        interpretation = (
            f"{row['well']} has water mismatch with high or increasing simulated water saturation "
            f"(SWAT_EOH={num_text(swat_eoh, 3)}, delta_SWAT={num_text(delta_swat, 3)}). "
            "This suggests the model already places water near the completion; relperm/mobility or local dynamic support may be relevant."
        )
        primary_action = "Review SWAT movement, water mobility/relperm/SATNUM and local connectivity."
        confidence = "medium"

    # ------------------------------------------------------------
    # Specific under-communication cases
    # ------------------------------------------------------------
    elif action == "review_low_lateral_multiplier":
        interpretation = (
            f"{row['well']} appears to under-communicate water and has low lateral transmissibility multipliers. "
            f"mean MULT_H={num_text(mult_h, 3)}."
        )
        primary_action = "Review whether MULTX/MULTY reductions are too strong near the completed cells."
        confidence = "high"

    elif action == "review_under_connectivity":
        interpretation = (
            f"{row['well']} appears to under-communicate water. "
            f"TRAN_H={pct_text(tran_pct)}, well-connection transmissibility={pct_text(wellconn_pct)}."
        )
        primary_action = "Review whether local TRANX/TRANY, barriers or completion connectivity are too low."
        confidence = "high"

    elif action == "review_water_front_support":
        interpretation = (
            f"{row['well']} appears to under-predict water and SWAT_EOH is low "
            f"({num_text(swat_eoh, 3)}). The simulated water front may not be reaching the well."
        )
        primary_action = "Review aquifer/injector support, pressure depletion and water-front movement."
        confidence = "medium"

    elif action == "review_relperm_or_well_connection":
        interpretation = (
            f"{row['well']} has water mismatch while SWAT_EOH is already significant "
            f"({num_text(swat_eoh, 3)}). Water is present near the completion but not matched properly."
        )
        primary_action = "Review water relperm/SATNUM, mobility and well-connection parameters."
        confidence = "medium"

    # ------------------------------------------------------------
    # Key new cases: timing mismatch but no local-property support
    # ------------------------------------------------------------
    elif action == "early_breakthrough_no_local_driver":
        years = None
        if row.get("water_breakthrough_delta_days") is not None:
            years = abs(float(row.get("water_breakthrough_delta_days"))) / 365.25

        years_text = "N/A" if years is None else f"{years:.1f} years"

        interpretation = (
            f"{row['well']} has Poor/Fair water match mainly because the simulated water breakthrough is too early. "
            f"The model predicts water breakthrough {years_text} earlier than history "
            f"(sim={row.get('sim_water_breakthrough_date')}, hist={row.get('hist_water_breakthrough_date')}). "
            f"However, local completed-cell properties do not strongly support a local transmissibility/multiplier driver: "
            f"TRAN_H={pct_text(tran_pct)}, well-connection transmissibility={pct_text(wellconn_pct)}, "
            f"weighted TRAN_H={pct_text(weighted_tran_pct)}, KH={pct_text(kh_pct)}, "
            f"mean MULT_H={num_text(mult_h, 3)}, mean MULT_Z={num_text(mult_z, 3)}, "
            f"SWAT_EOH={num_text(swat_eoh, 3)}, delta_SWAT={num_text(delta_swat, 3)}. "
            "Therefore, the early water arrival is real, but it is not clearly explained by local TRAN/MULT around the completed cells."
        )
        primary_action = (
            "Do not directly reduce local TRAN/MULT based on this evidence alone. "
            "First inspect water profile plots and then check relperm/SATNUM, water contact or water-front position, "
            "aquifer/injection support, schedule/controls, or non-local connectivity."
        )
        confidence = "medium"

    elif action == "delayed_breakthrough_no_local_driver":
        interpretation = (
            f"{row['well']} has delayed simulated water breakthrough, but local TRAN/MULT indicators are not clearly low. "
            f"TRAN_H={pct_text(tran_pct)}, well-connection transmissibility={pct_text(wellconn_pct)}, "
            f"mean MULT_H={num_text(mult_h, 3)}, SWAT_EOH={num_text(swat_eoh, 3)}. "
            "The delayed water is therefore not clearly explained by local under-connectivity."
        )
        primary_action = (
            "Check water-front movement, aquifer/injection support, schedule/controls, relperm/SATNUM and regional connectivity."
        )
        confidence = "medium"

    elif action == "overpredicted_water_no_local_driver":
        interpretation = (
            f"{row['well']} overpredicts final water behaviour, but local TRAN/MULT indicators are not high enough "
            "to support a clear local over-communication driver. "
            f"TRAN_H={pct_text(tran_pct)}, well-connection transmissibility={pct_text(wellconn_pct)}, "
            f"mean MULT_H={num_text(mult_h, 3)}, SWAT_EOH={num_text(swat_eoh, 3)}."
        )
        primary_action = "Inspect profile and water-front maps; then check relperm/SATNUM, aquifer/injection support, observed data quality and non-local connectivity."
        confidence = "medium"

    elif action == "underpredicted_water_no_local_driver":
        interpretation = (
            f"{row['well']} underpredicts final water behaviour, but local TRAN/MULT indicators are not clearly low. "
            f"TRAN_H={pct_text(tran_pct)}, well-connection transmissibility={pct_text(wellconn_pct)}, "
            f"mean MULT_H={num_text(mult_h, 3)}, SWAT_EOH={num_text(swat_eoh, 3)}."
        )
        primary_action = "Inspect water-front movement, injector/aquifer support and well controls before changing local transmissibility."
        confidence = "medium"

    elif action == "profile_shape_mismatch":
        interpretation = (
            f"{row['well']} has water score below Good while the final water value is close. "
            "This indicates a profile-shape or timing mismatch rather than a final-magnitude mismatch. "
            f"Components: full_trend={row.get('water_full_trend_score')}, "
            f"recent_2yr={row.get('water_recent_2yr_score')}, final={row.get('water_final_score')}."
        )
        primary_action = "Inspect simulated-vs-history water profile and breakthrough timing before changing properties."
        confidence = "medium"

    elif action == "water_signal_not_interpretable":
        interpretation = (
            f"{row['well']} has water score={num_text(water_score, 2)}, but the water signal is not interpretable for property-driver diagnosis "
            f"(direction={direction}, timing={timing}). "
            "This may indicate missing/flat vectors, no simulated activity, no observed activity, or a signal-rule fallback. "
            "It should not be treated as a reservoir-property mismatch until WWPR/WWPRH and WWCT/WWCTH are inspected."
        )
        primary_action = "Do not generate TRAN/PERM/relperm actions. First inspect WWPR/WWPRH and WWCT/WWCTH and confirm whether the well is active in simulation and history."
        confidence = "low"

    else:
        interpretation = (
            f"{row['well']} could not be assigned to a reliable diagnostic category."
        )
        primary_action = "Inspect profiles and vectors manually before applying calibration actions."
        confidence = "low"

    return {
        "well": row["well"],
        "action_category": action,
        "primary_action": primary_action,
        "interpretation": interpretation,
        "confidence": confidence,
        "water_hm_score": water_score,
        "water_hm_class": water_class,
        "water_direction": direction,
        "water_timing_issue": timing,
        "water_breakthrough_delta_days": row.get("water_breakthrough_delta_days"),
        "sim_water_breakthrough_date": row.get("sim_water_breakthrough_date"),
        "hist_water_breakthrough_date": row.get("hist_water_breakthrough_date"),
        "evidence": evidence,
    }


def write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    if not rows:
        raise RuntimeError("No rows to write.")

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_summary(diagnoses: List[Dict[str, Any]]) -> Dict[str, Any]:
    action_counts: Dict[str, int] = {}
    timing_counts: Dict[str, int] = {}

    for d in diagnoses:
        action = d.get("action_category")
        timing = d.get("water_timing_issue")

        action_counts[action] = action_counts.get(action, 0) + 1
        timing_counts[timing] = timing_counts.get(timing, 0) + 1

    return {
        "well_count": len(diagnoses),
        "action_counts": action_counts,
        "water_timing_counts": timing_counts,
        "wells_by_action": {
            action: [d["well"] for d in diagnoses if d.get("action_category") == action]
            for action in sorted(action_counts)
        },
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dims = load_grid_dimensions()
    cell_count = dims["cell_count"]

    properties: Dict[str, Optional[Dict[str, Any]]] = {}
    property_load_report: Dict[str, Any] = {}

    print("Loading properties...")
    for prop_name in PROPERTY_SPECS:
        try:
            prop = read_grdecl_property(prop_name, cell_count)
            properties[prop_name] = prop

            if prop is None:
                print(f"[MISSING] {prop_name}")
                property_load_report[prop_name] = {"status": "missing"}
            else:
                print(f"[OK] {prop_name}: {prop['source_file']} keyword={prop['keyword']}")
                property_load_report[prop_name] = {
                    "status": "loaded",
                    "source_file": prop["source_file"],
                    "keyword": prop["keyword"],
                    "min": prop["min"],
                    "max": prop["max"],
                    "mean": prop["mean"],
                }

        except Exception as exc:
            properties[prop_name] = None
            print(f"[ERROR] {prop_name}: {type(exc).__name__}: {exc}")
            property_load_report[prop_name] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    spatial = get_well_spatial_summary()
    hm = build_history_match_kpis()

    rows = []

    for well, spatial_payload in spatial["wells"].items():
        hm_payload = hm.get("well_results", {}).get(well)

        if hm_payload is None:
            continue

        rows.append(
            build_row_for_well(
                well=well,
                spatial_payload=spatial_payload,
                hm_payload=hm_payload,
                properties=properties,
                dims=dims,
            )
        )

    add_percentiles(rows)

    context_csv = OUTPUT_DIR / "well_property_driver_context.csv"
    write_csv(rows, context_csv)
    print(f"[OK] Saved {context_csv}")

    diagnoses = [make_specific_interpretation(row) for row in rows]

    diagnosis_json = OUTPUT_DIR / "water_driver_diagnosis.json"
    diagnosis_json.write_text(json.dumps(diagnoses, indent=2), encoding="utf-8")
    print(f"[OK] Saved {diagnosis_json}")

    summary_payload = {
        "grid_dimensions": dims,
        "property_load_report": property_load_report,
        "summary": make_summary(diagnoses),
    }

    summary_json = OUTPUT_DIR / "driver_diagnosis_summary.json"
    summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    print(f"[OK] Saved {summary_json}")

    print("")
    print("Completed enhanced driver diagnosis.")
    print(f"Open folder: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
