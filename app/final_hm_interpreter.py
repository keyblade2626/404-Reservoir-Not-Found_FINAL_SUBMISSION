import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


DRIVER_CONTEXT_CSV = Path("artifacts/diagnosis/well_property_driver_context.csv")
WATER_DIAGNOSIS_JSON = Path("artifacts/diagnosis/water_driver_diagnosis.json")
PRODUCER_INJECTOR_CONTEXT_JSON = Path("artifacts/integrated_context/producer_injector_water_context.json")
CLUSTER_SNAP_JSON = Path("artifacts/streamlines/cluster_snap/cluster_snap_streamline_connections.json")

OUTPUT_DIR = Path("artifacts/final_diagnosis")


def to_float(value: Any) -> Optional[float]:
    if value in [None, "", "None", "null", "N/A"]:
        return None
    try:
        return float(value)
    except Exception:
        return None


def parse_percentile(value: Any) -> Optional[float]:
    if value in [None, "", "None", "null", "N/A"]:
        return None

    text = str(value).strip()

    match = re.search(r"P?\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    if not match:
        return to_float(value)

    return float(match.group(1))


def load_json(path: Path) -> Any:
    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def get_value(row: Dict[str, Any], candidates: List[str]) -> Any:
    norm_map = {normalize_key(k): v for k, v in row.items()}

    for c in candidates:
        key = normalize_key(c)
        if key in norm_map:
            return norm_map[key]

    return None


def load_water_diagnoses() -> Dict[str, Dict[str, Any]]:
    data = load_json(WATER_DIAGNOSIS_JSON)

    if data is None:
        return {}

    if isinstance(data, list):
        return {x.get("well"): x for x in data if x.get("well")}

    if isinstance(data, dict):
        for key in ["diagnoses", "water_driver_diagnosis", "water_diagnosis"]:
            if key in data and isinstance(data[key], list):
                return {x.get("well"): x for x in data[key] if x.get("well")}

    return {}


def load_integrated_context() -> Dict[str, Dict[str, Any]]:
    data = load_json(PRODUCER_INJECTOR_CONTEXT_JSON)

    if not data:
        return {}

    rows = data.get("integrated_context", [])

    return {
        item.get("producer"): item
        for item in rows
        if item.get("producer")
    }


def load_cluster_connection_summary() -> Dict[str, List[Dict[str, Any]]]:
    data = load_json(CLUSTER_SNAP_JSON)

    if not data:
        return {}

    by_producer: Dict[str, List[Dict[str, Any]]] = {}

    for conn in data.get("connection_changes", []):
        producer = conn.get("producer")
        if not producer:
            continue

        by_producer.setdefault(producer, [])
        by_producer[producer].append(conn)

    for producer in by_producer:
        by_producer[producer] = sorted(
            by_producer[producer],
            key=lambda x: -float(x.get("eoh_connection_strength") or 0.0),
        )

    return by_producer


def infer_local_property_signals(row: Dict[str, Any]) -> Dict[str, Any]:
    # Read actual fields written by driver_diagnosis.py.
    mean_tran_h = to_float(get_value(row, ["mean_tran_h"]))
    max_tran_h = to_float(get_value(row, ["max_tran_h"]))
    weighted_tran_h = to_float(get_value(row, ["wellconn_weighted_tran_h"]))
    kh_weighted_tran_h = to_float(get_value(row, ["kh_weighted_tran_h"]))
    wellconn_total_tran = to_float(get_value(row, ["wellconn_total_transmissibility"]))
    wellconn_mean_tran = to_float(get_value(row, ["wellconn_mean_transmissibility"]))
    wellconn_max_tran = to_float(get_value(row, ["wellconn_max_transmissibility"]))

    tran_h_pct = parse_percentile(get_value(row, [
        "mean_tran_h_percentile",
        "tran_h_percentile",
        "TRAN_H percentile",
        "tran_h_pct",
    ]))

    max_tran_h_pct = parse_percentile(get_value(row, [
        "max_tran_h_percentile",
        "max_tran_h_pct",
    ]))

    weighted_tran_pct = parse_percentile(get_value(row, [
        "wellconn_weighted_tran_h_percentile",
        "weighted_tran_h_percentile",
        "Well-connection weighted TRAN_H percentile",
    ]))

    kh_pct = parse_percentile(get_value(row, [
        "kh_weighted_tran_h_percentile",
        "wellconn_total_kh_percentile",
        "kh_percentile",
        "KH percentile",
    ]))

    wc_total_tran_pct = parse_percentile(get_value(row, [
        "wellconn_total_transmissibility_percentile",
        "total_transmissibility_percentile",
        "Well-connection total transmissibility percentile",
    ]))

    wc_mean_tran_pct = parse_percentile(get_value(row, [
        "wellconn_mean_transmissibility_percentile",
    ]))

    wc_max_tran_pct = parse_percentile(get_value(row, [
        "wellconn_max_transmissibility_percentile",
    ]))

    mean_mult_h = to_float(get_value(row, [
        "mean_mult_h",
        "mean MULT_H",
        "MULT_H",
    ]))

    mean_mult_z = to_float(get_value(row, [
        "mean_mult_z",
        "mean MULT_Z",
        "MULT_Z",
    ]))

    max_mult_h = to_float(get_value(row, ["max_mult_h"]))
    max_mult_z = to_float(get_value(row, ["max_mult_z"]))

    mean_perm_h = to_float(get_value(row, ["mean_perm_h"]))
    mean_perm_z = to_float(get_value(row, ["mean_perm_z"]))

    swat_eoh = to_float(get_value(row, [
        "mean_swat_eoh",
        "mean SWAT_EOH",
        "SWAT_EOH",
    ]))

    delta_swat = to_float(get_value(row, [
        "delta_swat",
        "delta SWAT",
    ]))

    delta_pressure = to_float(get_value(row, [
        "delta_pressure",
        "delta PRESSURE",
    ]))

    swat_eoh_pct = parse_percentile(get_value(row, [
        "mean_swat_eoh_percentile",
    ]))

    delta_swat_pct = parse_percentile(get_value(row, [
        "delta_swat_percentile",
    ]))

    pressure_eoh_pct = parse_percentile(get_value(row, [
        "mean_pressure_eoh_percentile",
    ]))

    delta_pressure_pct = parse_percentile(get_value(row, [
        "delta_pressure_percentile",
    ]))

    # Signals based on percentiles.
    tran_percentiles = [
        tran_h_pct,
        max_tran_h_pct,
        weighted_tran_pct,
        kh_pct,
        wc_total_tran_pct,
        wc_mean_tran_pct,
        wc_max_tran_pct,
    ]

    high_tran = any(x is not None and x >= 75 for x in tran_percentiles)
    low_tran = any(x is not None and x <= 25 for x in tran_percentiles)

    # Multipliers: use actual value, not percentile, because if all multipliers are 1,
    # percentile can be 100 but it does not mean multiplier is high.
    high_multiplier = (
        mean_mult_h is not None and mean_mult_h > 1.05
    ) or (
        mean_mult_z is not None and mean_mult_z > 1.05
    ) or (
        max_mult_h is not None and max_mult_h > 1.05
    ) or (
        max_mult_z is not None and max_mult_z > 1.05
    )

    low_multiplier = (
        mean_mult_h is not None and mean_mult_h < 0.95
    ) or (
        mean_mult_z is not None and mean_mult_z < 0.95
    )

    # SWAT absolute and relative signals.
    high_water_saturation = (
        swat_eoh is not None and swat_eoh >= 0.45
    ) or (
        swat_eoh_pct is not None and swat_eoh_pct >= 75
    )

    increasing_water_saturation = (
        delta_swat is not None and delta_swat >= 0.05
    ) or (
        delta_swat_pct is not None and delta_swat_pct >= 75 and delta_swat is not None and delta_swat > 0
    )

    return {
        "mean_tran_h": mean_tran_h,
        "max_tran_h": max_tran_h,
        "wellconn_weighted_tran_h": weighted_tran_h,
        "kh_weighted_tran_h": kh_weighted_tran_h,
        "wellconn_total_transmissibility": wellconn_total_tran,
        "wellconn_mean_transmissibility": wellconn_mean_tran,
        "wellconn_max_transmissibility": wellconn_max_tran,

        "tran_h_percentile": tran_h_pct,
        "max_tran_h_percentile": max_tran_h_pct,
        "well_connection_total_transmissibility_percentile": wc_total_tran_pct,
        "well_connection_mean_transmissibility_percentile": wc_mean_tran_pct,
        "well_connection_max_transmissibility_percentile": wc_max_tran_pct,
        "weighted_tran_h_percentile": weighted_tran_pct,
        "kh_percentile": kh_pct,

        "mean_mult_h": mean_mult_h,
        "mean_mult_z": mean_mult_z,
        "max_mult_h": max_mult_h,
        "max_mult_z": max_mult_z,
        "mean_perm_h": mean_perm_h,
        "mean_perm_z": mean_perm_z,

        "mean_swat_eoh": swat_eoh,
        "mean_swat_eoh_percentile": swat_eoh_pct,
        "delta_swat": delta_swat,
        "delta_swat_percentile": delta_swat_pct,
        "delta_pressure": delta_pressure,
        "mean_pressure_eoh_percentile": pressure_eoh_pct,
        "delta_pressure_percentile": delta_pressure_pct,

        "high_tran_signal": high_tran,
        "low_tran_signal": low_tran,
        "high_multiplier_signal": high_multiplier,
        "low_multiplier_signal": low_multiplier,
        "high_water_saturation_signal": high_water_saturation,
        "increasing_water_saturation_signal": increasing_water_saturation,
    }


def classify_water_issue(timing: str, direction: str) -> str:
    timing = str(timing or "").lower()
    direction = str(direction or "").lower()

    if timing in ["early_breakthrough", "simulated_breakthrough_only"]:
        return "simulated_water_too_early"

    if timing in ["delayed_breakthrough", "historical_breakthrough_only"]:
        return "simulated_water_too_late"

    if direction in ["simulated_too_high", "simulated_too_high_signal"]:
        return "simulated_water_too_high"

    if direction in ["simulated_too_low", "simulated_too_low_signal"]:
        return "simulated_water_too_low"

    return "water_profile_shape_issue"


def summarize_connected_injectors(integrated: Dict[str, Any]) -> Dict[str, Any]:
    connected = integrated.get("connected_or_nearby_injectors", []) if integrated else []

    overinjecting = [
        x for x in connected
        if x.get("water_injection_direction") == "simulated_over_injection"
    ]

    underinjecting = [
        x for x in connected
        if x.get("water_injection_direction") == "simulated_under_injection"
    ]

    strengthening = [
        x for x in connected
        if to_float(x.get("delta_connection_strength")) is not None
        and to_float(x.get("delta_connection_strength")) > 0
    ]

    strongest = None

    if connected:
        strongest = sorted(
            connected,
            key=lambda x: -float(x.get("eoh_connection_strength") or 0.0),
        )[0]

    return {
        "connected_injector_count": len(connected),
        "connected_injectors": connected,
        "overinjecting_water_injectors": overinjecting,
        "underinjecting_water_injectors": underinjecting,
        "strengthening_connections": strengthening,
        "strongest_connected_injector": strongest,
    }


def decide_primary_driver(
    water_issue: str,
    local: Dict[str, Any],
    injector_summary: Dict[str, Any],
) -> Dict[str, Any]:

    evidence = []
    confidence = "medium"

    overinjecting = injector_summary["overinjecting_water_injectors"]
    underinjecting = injector_summary["underinjecting_water_injectors"]
    strengthening = injector_summary["strengthening_connections"]
    strongest = injector_summary["strongest_connected_injector"]

    if water_issue in ["simulated_water_too_early", "simulated_water_too_high"]:
        if overinjecting:
            names = ", ".join(x["injector"] for x in overinjecting if x.get("injector"))
            evidence.append(f"Connected water injector(s) over-injecting in simulation: {names}.")
            confidence = "high"
            return {
                "primary_driver": "connected_injector_over_injection",
                "driver_family": "injector_connectivity",
                "recommended_action": (
                    "First review water injection HM/allocation for connected injector(s). "
                    "Do not immediately reduce producer-local transmissibility until injector controls are checked."
                ),
                "confidence": confidence,
                "evidence": evidence,
            }

        if strengthening:
            names = ", ".join(x["injector"] for x in strengthening[:3] if x.get("injector"))
            evidence.append(f"Streamline support increases toward EOH for connected injector(s): {names}.")
            confidence = "medium_high"
            return {
                "primary_driver": "increasing_streamline_support",
                "driver_family": "dynamic_connectivity",
                "recommended_action": (
                    "Inspect streamline support evolution and water-front movement. "
                    "Check whether dynamic connectivity or injector support is too strong at EOH."
                ),
                "confidence": confidence,
                "evidence": evidence,
            }

        if local["high_tran_signal"] or local["high_multiplier_signal"]:
            if local["high_tran_signal"]:
                evidence.append("Local/well-connection transmissibility is high relative to the model distribution.")
            if local["high_multiplier_signal"]:
                evidence.append("Horizontal/vertical transmissibility multiplier is above 1.")
            return {
                "primary_driver": "local_high_transmissibility_or_multiplier",
                "driver_family": "local_property",
                "recommended_action": (
                    "Review TRAN/MULT around the producer completions. "
                    "If geologically justified, reduce excessive local communication or multiplier calibration."
                ),
                "confidence": "medium",
                "evidence": evidence,
            }

        if local["high_water_saturation_signal"] or local["increasing_water_saturation_signal"]:
            evidence.append("High or increasing SWAT near producer completions.")
            return {
                "primary_driver": "local_water_saturation_front",
                "driver_family": "dynamic_property",
                "recommended_action": (
                    "Inspect SWAT maps and water-front movement around the producer. "
                    "Check whether water front is too advanced in the model."
                ),
                "confidence": "medium",
                "evidence": evidence,
            }

        return {
            "primary_driver": "unexplained_early_or_high_water",
            "driver_family": "unresolved",
            "recommended_action": (
                "Review relperm/SATNUM, water contact, aquifer support, fault transmissibility, "
                "and non-local connectivity. No strong injector/local TRAN driver was detected."
            ),
            "confidence": "low_medium",
            "evidence": evidence,
        }

    if water_issue in ["simulated_water_too_late", "simulated_water_too_low"]:
        if underinjecting:
            names = ", ".join(x["injector"] for x in underinjecting if x.get("injector"))
            evidence.append(f"Connected water injector(s) under-injecting in simulation: {names}.")
            return {
                "primary_driver": "connected_injector_under_injection",
                "driver_family": "injector_connectivity",
                "recommended_action": (
                    "First review water injection HM/allocation for connected injector(s). "
                    "The producer may receive too little simulated water support."
                ),
                "confidence": "high",
                "evidence": evidence,
            }

        # Important case:
        # The simulated water profile is too low, but SWAT around the producer is already high.
        # This means water exists in the model near the well, but it is not being produced enough.
        # This is not a generic unexplained issue.
        if local["high_water_saturation_signal"]:
            evidence.append(
                f"Mean SWAT at EOH is high ({local.get('mean_swat_eoh'):.3f}), "
                "but simulated produced water is too low."
            )

            if local["low_tran_signal"]:
                evidence.append(
                    "Low local TRAN/KH around completed cells may reduce effective communication between water-bearing cells and the wellbore."
                )

            if local["low_multiplier_signal"]:
                evidence.append(
                    "A transmissibility multiplier below 1 may be reducing effective water communication toward the well."
                )

            return {
                "primary_driver": "high_swat_but_low_simulated_water_production",
                "driver_family": "water_mobility_or_local_connectivity",
                "recommended_action": (
                    "High SWAT is present around the producer, but simulated water production is too low. "
                    "This suggests that water exists in the model near the completed cells, but its effective "
                    "mobility or communication to the well is insufficient. First review the relevant water "
                    "relative permeability behaviour (krw endpoint/shape and water mobility). Then review local "
                    "PERM/TRAN and transmissibility multipliers around the completed cells. If faults are close "
                    "to the well, check fault transmissibility or sealing assumptions. In history-matched models, "
                    "well controls are usually oil- or liquid-controlled, so they should not be treated as the "
                    "main explanation for low simulated water production. Avoid using PI multiplier as a first-line "
                    "correction; consider it only as a last-resort deliverability calibration after the physical "
                    "connectivity and mobility mechanisms have been checked."
                ),
                "confidence": "medium_high",
                "evidence": evidence,
            }

        if local["low_tran_signal"] or local["low_multiplier_signal"]:
            if local["low_tran_signal"]:
                evidence.append("Local/well-connection transmissibility is low relative to the model distribution.")
            if local["low_multiplier_signal"]:
                evidence.append("Horizontal/vertical transmissibility multiplier is below 1.")
            return {
                "primary_driver": "local_low_transmissibility_or_multiplier",
                "driver_family": "local_property",
                "recommended_action": (
                    "Review whether local communication around the producer is too low. "
                    "If geologically justified, increase transmissibility/connectivity or check barriers."
                ),
                "confidence": "medium",
                "evidence": evidence,
            }

        return {
            "primary_driver": "unexplained_late_or_low_water",
            "driver_family": "unresolved",
            "recommended_action": (
                "Review pressure support, injector allocation, relperm/SATNUM and regional connectivity. "
                "No clear under-injection, high-SWAT/low-water inconsistency, or local low-transmissibility driver was detected."
            ),
            "confidence": "low_medium",
            "evidence": evidence,
        }

    if strongest:
        evidence.append(f"Strongest connected injector at EOH: {strongest.get('injector')}.")

    return {
        "primary_driver": "profile_shape_issue",
        "driver_family": "profile_timing",
        "recommended_action": (
            "Inspect water profile shape and breakthrough timing. "
            "Use connected injector context and local dynamic properties as supporting evidence."
        ),
        "confidence": "medium",
        "evidence": evidence,
    }


def build_final_diagnosis() -> Dict[str, Any]:
    driver_rows = read_csv_rows(DRIVER_CONTEXT_CSV)
    water_diagnoses = load_water_diagnoses()
    integrated_context = load_integrated_context()
    cluster_summary = load_cluster_connection_summary()

    results = []

    for row in driver_rows:
        well = row.get("well")

        if not well:
            continue

        diagnosis = water_diagnoses.get(well, {})
        integrated = integrated_context.get(well, {})

        water_score = to_float(row.get("water_hm_score"))
        if water_score is None:
            water_score = to_float(diagnosis.get("water_hm_score"))

        water_class = row.get("water_hm_class") or diagnosis.get("water_hm_class")
        water_timing = row.get("water_timing_issue") or diagnosis.get("water_timing_issue")
        water_direction = row.get("water_direction") or diagnosis.get("water_direction")

        if water_score is None:
            continue

        # Only final-diagnose wells with Fair/Poor water HM.
        if water_score >= 80:
            continue

        local = infer_local_property_signals(row)
        injector_summary = summarize_connected_injectors(integrated)
        water_issue = classify_water_issue(water_timing, water_direction)

        decision = decide_primary_driver(
            water_issue=water_issue,
            local=local,
            injector_summary=injector_summary,
        )

        connected_pairs = cluster_summary.get(well, [])

        results.append({
            "well": well,
            "water_hm_score": water_score,
            "water_hm_class": water_class,
            "water_issue_type": water_issue,
            "water_timing_issue": water_timing,
            "water_direction": water_direction,
            "primary_driver": decision["primary_driver"],
            "driver_family": decision["driver_family"],
            "confidence": decision["confidence"],
            "recommended_action": decision["recommended_action"],
            "decision_evidence": decision["evidence"],
            "local_property_signals": local,
            "connected_injector_count": injector_summary["connected_injector_count"],
            "strongest_connected_injector": injector_summary["strongest_connected_injector"],
            "overinjecting_water_injectors": injector_summary["overinjecting_water_injectors"],
            "underinjecting_water_injectors": injector_summary["underinjecting_water_injectors"],
            "strengthening_connections": injector_summary["strengthening_connections"],
            "cluster_snap_connections": connected_pairs,
        })

    return {
        "method": {
            "description": (
                "Final HM diagnosis combining producer water HM, local property context, "
                "injector injection HM and validated cluster-snap streamline connectivity."
            ),
            "hm_score_role": "Quantifies mismatch.",
            "streamline_role": "Explains likely connected injector support.",
            "property_role": "Checks local static/dynamic driver around producer completions.",
        },
        "diagnosed_well_count": len(results),
        "diagnoses": results,
    }


def write_outputs(payload: Dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = OUTPUT_DIR / "final_hm_diagnosis.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[OK] Saved {json_path}")

    rows = []

    for item in payload["diagnoses"]:
        strongest = item.get("strongest_connected_injector") or {}

        rows.append({
            "well": item["well"],
            "water_hm_score": item["water_hm_score"],
            "water_hm_class": item["water_hm_class"],
            "water_issue_type": item["water_issue_type"],
            "water_timing_issue": item["water_timing_issue"],
            "water_direction": item["water_direction"],
            "primary_driver": item["primary_driver"],
            "driver_family": item["driver_family"],
            "confidence": item["confidence"],
            "connected_injector_count": item["connected_injector_count"],
            "strongest_connected_injector": strongest.get("injector"),
            "strongest_eoh_connection_strength": strongest.get("eoh_connection_strength"),
            "strongest_delta_connection_strength": strongest.get("delta_connection_strength"),
            "recommended_action": item["recommended_action"],
            "evidence": " | ".join(item.get("decision_evidence", [])),
        })

    csv_path = OUTPUT_DIR / "final_hm_diagnosis.csv"

    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        print(f"[OK] Saved {csv_path}")


def main() -> None:
    payload = build_final_diagnosis()
    write_outputs(payload)

    print("")
    print("Final HM diagnosis completed.")
    print(f"Diagnosed wells: {payload['diagnosed_well_count']}")


if __name__ == "__main__":
    main()
