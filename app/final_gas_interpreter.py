import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


DRIVER_CONTEXT_CSV = Path("artifacts/diagnosis/well_property_driver_context.csv")
INJECTION_JSON = Path("artifacts/injection_hm/injection_hm_results.json")
CLUSTER_SNAP_JSON = Path("artifacts/streamlines/cluster_snap/cluster_snap_streamline_connections.json")

OUTPUT_DIR = Path("artifacts/final_diagnosis")


GOOD_SCORE_LIMIT = 80.0


def to_float(value: Any) -> Optional[float]:
    if value in [None, "", "None", "null", "N/A"]:
        return None
    try:
        return float(value)
    except Exception:
        return None


def normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def get_value(row: Dict[str, Any], candidates: List[str]) -> Any:
    norm_map = {normalize_key(k): v for k, v in row.items()}

    for c in candidates:
        key = normalize_key(c)
        if key in norm_map:
            return norm_map[key]

    return None


def parse_percentile(value: Any) -> Optional[float]:
    if value in [None, "", "None", "null", "N/A"]:
        return None

    text = str(value)
    match = re.search(r"P?\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)

    if match:
        return float(match.group(1))

    return to_float(value)


def read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> Any:
    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def load_injection_results() -> Dict[str, Dict[str, Any]]:
    data = load_json(INJECTION_JSON)

    if not data:
        return {}

    return data.get("well_results", {})


def load_cluster_connections_by_producer() -> Dict[str, List[Dict[str, Any]]]:
    data = load_json(CLUSTER_SNAP_JSON)

    if not data:
        return {}

    out: Dict[str, List[Dict[str, Any]]] = {}

    for conn in data.get("connection_changes", []):
        producer = conn.get("producer")

        if not producer:
            continue

        out.setdefault(producer, [])
        out[producer].append(conn)

    for producer in out:
        out[producer] = sorted(
            out[producer],
            key=lambda x: -float(x.get("eoh_connection_strength") or 0.0),
        )

    return out


def get_gas_injection_direction(inj_payload: Dict[str, Any]) -> str:
    return (
        inj_payload
        .get("variables", {})
        .get("gas_injection", {})
        .get("direction", "unknown")
    )


def get_gas_injection_score(inj_payload: Dict[str, Any]) -> Optional[float]:
    return (
        inj_payload
        .get("variables", {})
        .get("gas_injection", {})
        .get("score")
    )


def get_water_injection_direction(inj_payload: Dict[str, Any]) -> str:
    return (
        inj_payload
        .get("variables", {})
        .get("water_injection", {})
        .get("direction", "unknown")
    )


def connected_injector_context(
    producer: str,
    connections_by_producer: Dict[str, List[Dict[str, Any]]],
    injection_results: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:

    out = []

    for conn in connections_by_producer.get(producer, []):
        injector = conn.get("injector")
        inj_payload = injection_results.get(injector, {})

        out.append({
            "injector": injector,
            "role": inj_payload.get("role"),
            "injection_hm_score": inj_payload.get("injection_hm_score"),
            "injection_hm_class": inj_payload.get("injection_hm_class"),
            "gas_injection_score": get_gas_injection_score(inj_payload),
            "gas_injection_direction": get_gas_injection_direction(inj_payload),
            "water_injection_direction": get_water_injection_direction(inj_payload),
            "init_connection_strength": conn.get("init_connection_strength"),
            "eoh_connection_strength": conn.get("eoh_connection_strength"),
            "delta_connection_strength": conn.get("delta_connection_strength"),
            "init_connection_fraction": conn.get("init_connection_fraction"),
            "eoh_connection_fraction": conn.get("eoh_connection_fraction"),
            "delta_connection_fraction": conn.get("delta_connection_fraction"),
            "appeared_by_eoh": conn.get("appeared_by_eoh"),
            "disappeared_by_eoh": conn.get("disappeared_by_eoh"),
        })

    return out


def local_gas_signals(row: Dict[str, Any]) -> Dict[str, Any]:
    mean_sgas_eoh = to_float(get_value(row, ["mean_sgas_eoh"]))
    delta_sgas = to_float(get_value(row, ["delta_sgas"]))
    mean_pressure_eoh = to_float(get_value(row, ["mean_pressure_eoh"]))
    delta_pressure = to_float(get_value(row, ["delta_pressure"]))

    mean_tran_h_pct = parse_percentile(get_value(row, ["mean_tran_h_percentile"]))
    weighted_tran_h_pct = parse_percentile(get_value(row, ["wellconn_weighted_tran_h_percentile"]))
    total_tran_pct = parse_percentile(get_value(row, ["wellconn_total_transmissibility_percentile"]))

    mean_tran_z_pct = parse_percentile(get_value(row, ["mean_tran_z_percentile"]))

    mean_mult_h = to_float(get_value(row, ["mean_mult_h"]))
    mean_mult_z = to_float(get_value(row, ["mean_mult_z"]))
    max_mult_h = to_float(get_value(row, ["max_mult_h"]))
    max_mult_z = to_float(get_value(row, ["max_mult_z"]))

    mean_perm_h = to_float(get_value(row, ["mean_perm_h"]))
    mean_perm_z = to_float(get_value(row, ["mean_perm_z"]))

    tran_h_percentiles = [
        mean_tran_h_pct,
        weighted_tran_h_pct,
        total_tran_pct,
    ]

    high_horizontal_tran = any(x is not None and x >= 75 for x in tran_h_percentiles)
    low_horizontal_tran = any(x is not None and x <= 25 for x in tran_h_percentiles)

    high_vertical_tran = mean_tran_z_pct is not None and mean_tran_z_pct >= 75
    low_vertical_tran = mean_tran_z_pct is not None and mean_tran_z_pct <= 25

    high_mult_h = (
        mean_mult_h is not None and mean_mult_h > 1.05
    ) or (
        max_mult_h is not None and max_mult_h > 1.05
    )

    low_mult_h = mean_mult_h is not None and mean_mult_h < 0.95

    high_mult_z = (
        mean_mult_z is not None and mean_mult_z > 1.05
    ) or (
        max_mult_z is not None and max_mult_z > 1.05
    )

    low_mult_z = mean_mult_z is not None and mean_mult_z < 0.95

    high_sgas = mean_sgas_eoh is not None and mean_sgas_eoh >= 0.05
    increasing_sgas = delta_sgas is not None and delta_sgas >= 0.02

    strong_depletion = delta_pressure is not None and delta_pressure <= -500.0
    weak_depletion = delta_pressure is not None and delta_pressure > -100.0

    return {
        "mean_sgas_eoh": mean_sgas_eoh,
        "delta_sgas": delta_sgas,
        "mean_pressure_eoh": mean_pressure_eoh,
        "delta_pressure": delta_pressure,

        "mean_tran_h_percentile": mean_tran_h_pct,
        "weighted_tran_h_percentile": weighted_tran_h_pct,
        "wellconn_total_transmissibility_percentile": total_tran_pct,
        "mean_tran_z_percentile": mean_tran_z_pct,

        "mean_mult_h": mean_mult_h,
        "mean_mult_z": mean_mult_z,
        "max_mult_h": max_mult_h,
        "max_mult_z": max_mult_z,

        "mean_perm_h": mean_perm_h,
        "mean_perm_z": mean_perm_z,

        "high_horizontal_tran_signal": high_horizontal_tran,
        "low_horizontal_tran_signal": low_horizontal_tran,
        "high_vertical_tran_signal": high_vertical_tran,
        "low_vertical_tran_signal": low_vertical_tran,
        "high_mult_h_signal": high_mult_h,
        "low_mult_h_signal": low_mult_h,
        "high_mult_z_signal": high_mult_z,
        "low_mult_z_signal": low_mult_z,
        "high_sgas_signal": high_sgas,
        "increasing_sgas_signal": increasing_sgas,
        "strong_depletion_signal": strong_depletion,
        "weak_depletion_signal": weak_depletion,
    }


def classify_gas_issue(row: Dict[str, Any]) -> str:
    """
    Best effort. If driver_diagnosis/historymatch later exports gas_direction or gas_timing_issue,
    this function will use them. If not available, it will mark the issue as direction_unknown.
    """

    direction = str(get_value(row, [
        "gas_direction",
        "gor_direction",
        "gas_final_direction",
        "gor_final_direction",
    ]) or "").lower()

    timing = str(get_value(row, [
        "gas_timing_issue",
        "gor_timing_issue",
        "gas_breakthrough_timing_issue",
        "gor_breakthrough_timing_issue",
    ]) or "").lower()

    if timing in ["early_breakthrough", "simulated_breakthrough_only", "gas_too_early", "gor_too_early"]:
        return "simulated_gas_too_early"

    if timing in ["delayed_breakthrough", "historical_breakthrough_only", "gas_too_late", "gor_too_late"]:
        return "simulated_gas_too_late"

    if direction in ["simulated_too_high", "simulated_too_high_signal", "gas_too_high", "gor_too_high"]:
        return "simulated_gas_too_high"

    if direction in ["simulated_too_low", "simulated_too_low_signal", "gas_too_low", "gor_too_low"]:
        return "simulated_gas_too_low"

    return "gas_profile_mismatch_direction_unknown"


def summarize_injectors(connected: List[Dict[str, Any]]) -> Dict[str, Any]:
    gas_over = [
        x for x in connected
        if x.get("gas_injection_direction") == "simulated_over_injection"
    ]

    gas_under = [
        x for x in connected
        if x.get("gas_injection_direction") == "simulated_under_injection"
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
        "gas_overinjecting_injectors": gas_over,
        "gas_underinjecting_injectors": gas_under,
        "strengthening_connections": strengthening,
        "strongest_connected_injector": strongest,
    }


def decide_gas_driver(
    gas_issue: str,
    local: Dict[str, Any],
    injector_summary: Dict[str, Any],
) -> Dict[str, Any]:

    evidence = []

    gas_over = injector_summary["gas_overinjecting_injectors"]
    gas_under = injector_summary["gas_underinjecting_injectors"]
    strengthening = injector_summary["strengthening_connections"]
    strongest = injector_summary["strongest_connected_injector"]

    gas_too_high = gas_issue in [
        "simulated_gas_too_high",
        "simulated_gas_too_early",
    ]

    gas_too_low = gas_issue in [
        "simulated_gas_too_low",
        "simulated_gas_too_late",
    ]

    if gas_issue == "gas_profile_mismatch_direction_unknown":
        if strongest:
            evidence.append(f"Strongest connected injector at EOH: {strongest.get('injector')}.")

        return {
            "primary_driver": "gas_mismatch_direction_not_classified",
            "driver_family": "needs_profile_direction",
            "confidence": "medium",
            "recommended_action": (
                "Gas/GOR HM score is below Good, but the mismatch direction was not exported. "
                "First inspect gas-rate/GOR plots to classify whether simulated gas is too high/early "
                "or too low/late. After direction is known, evaluate gas cap communication, gas injection, "
                "SGAS, pressure depletion, TRAN/MULT and fault transmissibility."
            ),
            "evidence": evidence,
        }

    if gas_too_high:
        if gas_over:
            names = ", ".join(x["injector"] for x in gas_over if x.get("injector"))
            evidence.append(f"Connected gas injector(s) simulated over-injecting: {names}.")
            return {
                "primary_driver": "connected_gas_injector_over_injection",
                "driver_family": "gas_injection_connectivity",
                "confidence": "high",
                "recommended_action": (
                    "Review gas injection HM/allocation for connected injector(s) before changing local producer multipliers. "
                    "If the injector match is confirmed, check whether the injector-producer gas communication is too strong."
                ),
                "evidence": evidence,
            }

        if local["high_sgas_signal"] and (local["high_vertical_tran_signal"] or local["high_mult_z_signal"]):
            evidence.append("High SGAS near the producer with high vertical TRAN/MULTZ signal.")
            return {
                "primary_driver": "excessive_vertical_gas_communication",
                "driver_family": "gas_cap_or_vertical_connectivity",
                "confidence": "medium_high",
                "recommended_action": (
                    "Gas is simulated too high/early and the local signals suggest strong vertical gas communication. "
                    "Review TRANZ/MULTZ around the producer and check whether communication with gas-bearing layers or gas cap is too strong. "
                    "If faults are nearby, review fault transmissibility or sealing assumptions."
                ),
                "evidence": evidence,
            }

        if local["high_sgas_signal"] and (local["high_horizontal_tran_signal"] or local["high_mult_h_signal"]):
            evidence.append("High SGAS near the producer with high horizontal TRAN/MULT signal.")
            return {
                "primary_driver": "excessive_horizontal_gas_corridor_transmissibility",
                "driver_family": "local_or_corridor_transmissibility",
                "confidence": "medium",
                "recommended_action": (
                    "Gas is simulated too high/early and the local/corridor transmissibility appears high. "
                    "Review horizontal PERM/TRAN/MULT along the gas corridor. A local or corridor transmissibility reduction may be tested if geologically justified."
                ),
                "evidence": evidence,
            }

        if local["strong_depletion_signal"]:
            evidence.append("Strong simulated pressure depletion may be liberating excessive solution gas.")
            return {
                "primary_driver": "pressure_depletion_solution_gas_review",
                "driver_family": "pressure_pvt_depletion",
                "confidence": "medium",
                "recommended_action": (
                    "Gas overprediction may be linked to excessive simulated depletion and solution gas liberation. "
                    "Review pressure HM, voidage balance, aquifer/injection support and depletion pattern before changing gas transmissibility."
                ),
                "evidence": evidence,
            }

        return {
            "primary_driver": "unresolved_high_or_early_gas",
            "driver_family": "unresolved",
            "confidence": "low_medium",
            "recommended_action": (
                "Review SGAS distribution, gas cap communication, gas injection allocation, pressure depletion, "
                "vertical communication, fault transmissibility and gas relperm/krg if the issue is systematic."
            ),
            "evidence": evidence,
        }

    if gas_too_low:
        if gas_under:
            names = ", ".join(x["injector"] for x in gas_under if x.get("injector"))
            evidence.append(f"Connected gas injector(s) simulated under-injecting: {names}.")
            return {
                "primary_driver": "connected_gas_injector_under_injection",
                "driver_family": "gas_injection_connectivity",
                "confidence": "high",
                "recommended_action": (
                    "Review gas injection HM/allocation for connected injector(s). "
                    "The producer may be receiving insufficient simulated gas support."
                ),
                "evidence": evidence,
            }

        if local["high_sgas_signal"] and (local["low_vertical_tran_signal"] or local["low_mult_z_signal"]):
            evidence.append("High SGAS near the producer but low vertical TRAN/MULTZ signal.")
            return {
                "primary_driver": "high_sgas_but_low_vertical_gas_communication",
                "driver_family": "gas_cap_or_vertical_connectivity",
                "confidence": "medium_high",
                "recommended_action": (
                    "Gas exists near the producer, but simulated gas production is too low. "
                    "Review vertical communication through TRANZ/MULTZ and possible barriers between gas-bearing cells and completed intervals. "
                    "If faults are close, check fault transmissibility/sealing."
                ),
                "evidence": evidence,
            }

        if local["high_sgas_signal"] and (local["low_horizontal_tran_signal"] or local["low_mult_h_signal"]):
            evidence.append("High SGAS near the producer but low horizontal TRAN/MULT signal.")
            return {
                "primary_driver": "high_sgas_but_low_horizontal_gas_corridor_transmissibility",
                "driver_family": "local_or_corridor_transmissibility",
                "confidence": "medium_high",
                "recommended_action": (
                    "Gas exists near the producer, but simulated gas production is too low. "
                    "Review horizontal PERM/TRAN/MULT along the gas corridor. A transmissibility increase may be tested if geologically justified."
                ),
                "evidence": evidence,
            }

        if not local["high_sgas_signal"] and local["weak_depletion_signal"]:
            evidence.append("SGAS is not high and pressure depletion appears weak.")
            return {
                "primary_driver": "insufficient_depletion_or_gas_source",
                "driver_family": "pressure_pvt_depletion",
                "confidence": "medium",
                "recommended_action": (
                    "Gas underprediction may be due to insufficient gas source or insufficient pressure depletion. "
                    "Review pressure HM, gas cap support, bubble point/Rs consistency and voidage balance before changing local transmissibility."
                ),
                "evidence": evidence,
            }

        if strengthening:
            names = ", ".join(x["injector"] for x in strengthening[:3] if x.get("injector"))
            evidence.append(f"Connected streamline support exists or strengthens toward EOH: {names}.")
            return {
                "primary_driver": "gas_corridor_connectivity_review",
                "driver_family": "dynamic_connectivity",
                "confidence": "medium",
                "recommended_action": (
                    "Review the gas corridor highlighted by EOH streamlines. "
                    "If SGAS or gas source exists along the corridor, a transmissibility increase may be tested."
                ),
                "evidence": evidence,
            }

        return {
            "primary_driver": "unresolved_low_or_late_gas",
            "driver_family": "unresolved",
            "confidence": "low_medium",
            "recommended_action": (
                "Review SGAS, pressure depletion, gas cap communication, gas injection allocation, "
                "vertical communication, fault transmissibility and gas relperm/krg if the issue is systematic."
            ),
            "evidence": evidence,
        }

    return {
        "primary_driver": "gas_profile_shape_issue",
        "driver_family": "profile_shape",
        "confidence": "medium",
        "recommended_action": (
            "Inspect gas-rate/GOR profile shape and timing. Use SGAS, pressure, gas injection and streamline corridor context as supporting evidence."
        ),
        "evidence": evidence,
    }


def should_skip_gas_row(row: Dict[str, Any]) -> bool:
    gas_score = to_float(get_value(row, ["gas_hm_score", "gor_hm_score"]))

    if gas_score is None:
        return True

    if gas_score >= GOOD_SCORE_LIMIT:
        return True

    gas_status = str(get_value(row, ["gas_status", "gor_status"]) or "").lower()

    if gas_status in ["unavailable", "inactive", "inactive_no_profile", "not_evaluable", "not evaluated"]:
        return True

    gas_negligible = str(get_value(row, ["gas_negligible_match", "gor_negligible_match"]) or "").lower()

    if gas_negligible == "true":
        return True

    producer_activity_status = str(get_value(row, [
        "producer_activity_status",
        "well_activity_status",
        "activity_status",
    ]) or "").lower()

    if producer_activity_status in [
        "inactive_no_oil_profile",
        "inactive",
        "no_profile",
    ]:
        return True

    # GOR/gas should not be interpreted if there is no material oil profile.
    oil_status = str(get_value(row, ["oil_status"]) or "").lower()
    oil_score = to_float(get_value(row, ["oil_hm_score"]))

    if oil_status in ["unavailable", "inactive", "not_evaluable", "not evaluated"]:
        return True

    if oil_score is None:
        return True

    return False


def build_gas_diagnosis() -> Dict[str, Any]:
    rows = read_csv_rows(DRIVER_CONTEXT_CSV)
    injection_results = load_injection_results()
    connections_by_producer = load_cluster_connections_by_producer()

    diagnoses = []

    for row in rows:
        well = row.get("well")

        if not well:
            continue

        if should_skip_gas_row(row):
            continue

        gas_score = to_float(get_value(row, ["gas_hm_score", "gor_hm_score"]))
        gas_class = get_value(row, ["gas_hm_class", "gor_hm_class"])

        gas_issue = classify_gas_issue(row)
        local = local_gas_signals(row)

        connected = connected_injector_context(
            producer=well,
            connections_by_producer=connections_by_producer,
            injection_results=injection_results,
        )

        injector_summary = summarize_injectors(connected)

        decision = decide_gas_driver(
            gas_issue=gas_issue,
            local=local,
            injector_summary=injector_summary,
        )

        diagnoses.append({
            "well": well,
            "gas_hm_score": gas_score,
            "gas_hm_class": gas_class,
            "gas_issue_type": gas_issue,
            "primary_driver": decision["primary_driver"],
            "driver_family": decision["driver_family"],
            "confidence": decision["confidence"],
            "recommended_action": decision["recommended_action"],
            "decision_evidence": decision["evidence"],
            "local_gas_signals": local,
            "connected_injector_count": injector_summary["connected_injector_count"],
            "strongest_connected_injector": injector_summary["strongest_connected_injector"],
            "gas_overinjecting_injectors": injector_summary["gas_overinjecting_injectors"],
            "gas_underinjecting_injectors": injector_summary["gas_underinjecting_injectors"],
            "strengthening_connections": injector_summary["strengthening_connections"],
            "connected_injectors": connected,
        })

    return {
        "method": {
            "description": (
                "Gas/GOR HM diagnosis combining gas HM score, SGAS, pressure depletion, "
                "TRAN/MULT, gas injection HM and cluster-snap streamline connectivity."
            ),
            "important_note": (
                "Gas recommendations are mechanism-based. Area-based maps should focus on TRAN/MULT corridors, "
                "MULTZ/vertical communication and fault transmissibility. Gas relperm/PVT are engineering review items, "
                "not cell-by-cell map edits."
            ),
        },
        "diagnosed_well_count": len(diagnoses),
        "diagnoses": diagnoses,
    }


def write_outputs(payload: Dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = OUTPUT_DIR / "final_gas_diagnosis.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[OK] Saved {json_path}")

    rows = []

    for item in payload["diagnoses"]:
        strongest = item.get("strongest_connected_injector") or {}

        rows.append({
            "well": item["well"],
            "gas_hm_score": item["gas_hm_score"],
            "gas_hm_class": item["gas_hm_class"],
            "gas_issue_type": item["gas_issue_type"],
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

    csv_path = OUTPUT_DIR / "final_gas_diagnosis.csv"

    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        print(f"[OK] Saved {csv_path}")
    else:
        print("[INFO] No gas wells below Good threshold. CSV not written.")


def main() -> None:
    payload = build_gas_diagnosis()
    write_outputs(payload)

    print("")
    print("Final gas HM diagnosis completed.")
    print(f"Diagnosed gas wells: {payload['diagnosed_well_count']}")


if __name__ == "__main__":
    main()
