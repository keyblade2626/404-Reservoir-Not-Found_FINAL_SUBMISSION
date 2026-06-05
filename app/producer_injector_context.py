import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


PRODUCER_CONTEXT_CSV = Path("artifacts/diagnosis/well_property_driver_context.csv")
PRODUCER_DIAGNOSIS_JSON = Path("artifacts/diagnosis/water_driver_diagnosis.json")
INJECTION_JSON = Path("artifacts/injection_hm/injection_hm_results.json")
CLUSTER_SNAP_JSON = Path("artifacts/streamlines/cluster_snap/cluster_snap_streamline_connections.json")

OUTPUT_DIR = Path("artifacts/integrated_context")


def to_float(value: Any) -> Optional[float]:
    if value in [None, "", "None", "null", "N/A"]:
        return None
    try:
        return float(value)
    except Exception:
        return None


def read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")

    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def load_producer_diagnoses() -> Dict[str, Dict[str, Any]]:
    data = load_json(PRODUCER_DIAGNOSIS_JSON)

    if isinstance(data, list):
        return {item.get("well"): item for item in data if item.get("well")}

    if isinstance(data, dict):
        if "diagnoses" in data and isinstance(data["diagnoses"], list):
            return {item.get("well"): item for item in data["diagnoses"] if item.get("well")}

        if "water_driver_diagnosis" in data and isinstance(data["water_driver_diagnosis"], list):
            return {item.get("well"): item for item in data["water_driver_diagnosis"] if item.get("well")}

    return {}


def load_injection_results() -> Dict[str, Dict[str, Any]]:
    data = load_json(INJECTION_JSON)
    return data.get("well_results", {})


def load_cluster_snap_connections() -> Dict[str, Any]:
    data = load_json(CLUSTER_SNAP_JSON)

    # Do not fail if available=False.
    # In this project, available=False can simply mean that producer snapping worked
    # but no injector-producer connection was accepted yet, usually because injector
    # roles/distances were not detected.
    return data


def producer_has_water_problem(row: Dict[str, Any], diagnosis: Dict[str, Any]) -> bool:
    score = to_float(row.get("water_hm_score"))

    if score is None:
        score = to_float(diagnosis.get("water_hm_score"))

    if score is None:
        return False

    if score >= 80:
        return False

    action = diagnosis.get("action_category")

    if action in [
        "no_hm_comment",
        "inactive_water_in_sim_and_history",
        "inactive_in_sim_and_history",
        "no_water_action",
        "water_signal_not_interpretable",
    ]:
        return False

    return True


def injector_water_direction(injection_payload: Dict[str, Any]) -> str:
    return (
        injection_payload
        .get("variables", {})
        .get("water_injection", {})
        .get("direction", "unknown")
    )


def injector_water_score(injection_payload: Dict[str, Any]) -> Optional[float]:
    return (
        injection_payload
        .get("variables", {})
        .get("water_injection", {})
        .get("score")
    )


def injector_gas_direction(injection_payload: Dict[str, Any]) -> str:
    return (
        injection_payload
        .get("variables", {})
        .get("gas_injection", {})
        .get("direction", "unknown")
    )


def injector_gas_score(injection_payload: Dict[str, Any]) -> Optional[float]:
    return (
        injection_payload
        .get("variables", {})
        .get("gas_injection", {})
        .get("score")
    )


def build_connection_lookup(cluster_payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Uses cluster-snap connection_changes as the official injector-producer connectivity.
    Key = producer.
    """
    by_producer: Dict[str, List[Dict[str, Any]]] = {}

    for conn in cluster_payload.get("connection_changes", []):
        producer = conn.get("producer")

        if not producer:
            continue

        by_producer.setdefault(producer, [])
        by_producer[producer].append(conn)

    for producer, rows in by_producer.items():
        by_producer[producer] = sorted(
            rows,
            key=lambda x: -float(x.get("eoh_connection_strength") or 0.0),
        )

    return by_producer


def enrich_connected_injectors(
    producer: str,
    connection_lookup: Dict[str, List[Dict[str, Any]]],
    injection_results: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows = []

    for conn in connection_lookup.get(producer, []):
        injector = conn.get("injector")
        inj_payload = injection_results.get(injector, {})

        rows.append({
            "injector": injector,
            "role": inj_payload.get("role", "unknown"),
            "injection_hm_score": inj_payload.get("injection_hm_score"),
            "injection_hm_class": inj_payload.get("injection_hm_class"),
            "water_injection_score": injector_water_score(inj_payload),
            "water_injection_direction": injector_water_direction(inj_payload),
            "gas_injection_score": injector_gas_score(inj_payload),
            "gas_injection_direction": injector_gas_direction(inj_payload),
            "init_connection_strength": conn.get("init_connection_strength"),
            "eoh_connection_strength": conn.get("eoh_connection_strength"),
            "delta_connection_strength": conn.get("delta_connection_strength"),
            "init_connection_fraction": conn.get("init_connection_fraction"),
            "eoh_connection_fraction": conn.get("eoh_connection_fraction"),
            "delta_connection_fraction": conn.get("delta_connection_fraction"),
            "appeared_by_eoh": conn.get("appeared_by_eoh"),
            "disappeared_by_eoh": conn.get("disappeared_by_eoh"),
        })

    return rows


def build_interpretation(
    producer: str,
    producer_timing: str,
    producer_direction: str,
    connected_injectors: List[Dict[str, Any]],
) -> Dict[str, Any]:

    overinjecting = [
        inj for inj in connected_injectors
        if inj.get("water_injection_direction") == "simulated_over_injection"
    ]

    underinjecting = [
        inj for inj in connected_injectors
        if inj.get("water_injection_direction") == "simulated_under_injection"
    ]

    strengthening = [
        inj for inj in connected_injectors
        if to_float(inj.get("delta_connection_strength")) is not None
        and to_float(inj.get("delta_connection_strength")) > 0
    ]

    producer_over_water = (
        producer_timing in ["early_breakthrough", "simulated_breakthrough_only"]
        or producer_direction in ["simulated_too_high", "simulated_too_high_signal"]
    )

    producer_under_water = (
        producer_timing in ["delayed_breakthrough", "historical_breakthrough_only"]
        or producer_direction in ["simulated_too_low", "simulated_too_low_signal"]
    )

    interpretation = []
    primary_action = "No injector-related action identified."

    if producer_over_water:
        if overinjecting:
            names = ", ".join(i["injector"] for i in overinjecting)
            interpretation.append(
                f"{producer} shows early/over-predicted water behaviour and connected injector(s) "
                f"{names} are simulated over-injecting water relative to history. "
                f"This may contribute to early simulated water arrival."
            )
            primary_action = (
                "Review injector water injection match and injector-producer streamline support "
                "before changing local producer transmissibility."
            )
        elif strengthening:
            names = ", ".join(i["injector"] for i in strengthening[:3])
            interpretation.append(
                f"{producer} shows early/over-predicted water behaviour. Connected injector support "
                f"increases toward EOH for injector(s) {names}, even if direct over-injection was not detected."
            )
            primary_action = (
                "Inspect streamline support evolution, water-front movement and injection allocation "
                "before modifying producer-local properties."
            )
        else:
            interpretation.append(
                f"{producer} shows early/over-predicted water behaviour, but no connected water over-injector "
                f"was detected from the cluster-snap streamline connectivity."
            )
            primary_action = (
                "Check non-local connectivity, relperm/SATNUM, water contact/aquifer support, "
                "and producer-local properties."
            )

    elif producer_under_water:
        if underinjecting:
            names = ", ".join(i["injector"] for i in underinjecting)
            interpretation.append(
                f"{producer} shows delayed/under-predicted water behaviour and connected injector(s) "
                f"{names} are simulated under-injecting water relative to history. "
                f"This may contribute to insufficient simulated water support."
            )
            primary_action = (
                "Review injector water injection match and allocation before increasing producer-local transmissibility."
            )
        else:
            interpretation.append(
                f"{producer} shows delayed/under-predicted water behaviour, but no connected water under-injector "
                f"was detected from the cluster-snap streamline connectivity."
            )
            primary_action = (
                "Check water-front movement, pressure support, relperm/SATNUM and regional connectivity."
            )

    else:
        interpretation.append(
            f"{producer} has a water HM issue, but timing/direction is not clear enough to link it confidently "
            f"to injector behaviour."
        )

    return {
        "integrated_interpretation": interpretation,
        "primary_integrated_action": primary_action,
        "overinjecting_water_injectors": overinjecting,
        "underinjecting_water_injectors": underinjecting,
        "strengthening_connections": strengthening,
    }


def build_context() -> Dict[str, Any]:
    producer_rows = read_csv_rows(PRODUCER_CONTEXT_CSV)
    diagnoses = load_producer_diagnoses()
    injection_results = load_injection_results()
    cluster_payload = load_cluster_snap_connections()
    connection_lookup = build_connection_lookup(cluster_payload)

    integrated = []

    for row in producer_rows:
        producer = row.get("well")

        if not producer:
            continue

        diagnosis = diagnoses.get(producer, {})

        if not producer_has_water_problem(row, diagnosis):
            continue

        producer_timing = row.get("water_timing_issue") or diagnosis.get("water_timing_issue")
        producer_direction = row.get("water_direction") or diagnosis.get("water_direction")
        producer_score = to_float(row.get("water_hm_score"))

        if producer_score is None:
            producer_score = to_float(diagnosis.get("water_hm_score"))

        connected = enrich_connected_injectors(
            producer=producer,
            connection_lookup=connection_lookup,
            injection_results=injection_results,
        )

        interpretation_payload = build_interpretation(
            producer=producer,
            producer_timing=producer_timing,
            producer_direction=producer_direction,
            connected_injectors=connected,
        )

        integrated.append({
            "producer": producer,
            "connection_method": "cluster_snap_streamline_alignment",
            "producer_water_hm_score": producer_score,
            "producer_water_timing_issue": producer_timing,
            "producer_water_direction": producer_direction,
            "producer_action_category": diagnosis.get("action_category"),
            "connected_or_nearby_injectors": connected,
            **interpretation_payload,
            "note": (
                "Injector-producer connectivity comes from the validated cluster-snap streamline mapping. "
                "This is geometry-based streamline alignment, not raw ID_CELL matching."
            ),
        })

    return {
        "method": {
            "streamlines_available": True,
            "streamline_method": "cluster_snap_streamline_alignment",
            "source_file": str(CLUSTER_SNAP_JSON),
        },
        "producer_count_with_water_issue": len(integrated),
        "integrated_context": integrated,
    }


def write_outputs(payload: Dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = OUTPUT_DIR / "producer_injector_water_context.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[OK] Saved {json_path}")

    rows = []

    for item in payload["integrated_context"]:
        connected = item.get("connected_or_nearby_injectors", [])

        rows.append({
            "producer": item["producer"],
            "connection_method": item["connection_method"],
            "producer_water_hm_score": item["producer_water_hm_score"],
            "producer_water_timing_issue": item["producer_water_timing_issue"],
            "producer_water_direction": item["producer_water_direction"],
            "producer_action_category": item["producer_action_category"],
            "connected_injector_count": len(connected),
            "connected_injectors": "; ".join(i["injector"] for i in connected if i.get("injector")),
            "overinjecting_water_injectors": "; ".join(
                i["injector"] for i in item.get("overinjecting_water_injectors", []) if i.get("injector")
            ),
            "underinjecting_water_injectors": "; ".join(
                i["injector"] for i in item.get("underinjecting_water_injectors", []) if i.get("injector")
            ),
            "strengthening_connections": "; ".join(
                i["injector"] for i in item.get("strengthening_connections", []) if i.get("injector")
            ),
            "primary_integrated_action": item["primary_integrated_action"],
            "integrated_interpretation": " ".join(item["integrated_interpretation"]),
        })

    csv_path = OUTPUT_DIR / "producer_injector_water_context.csv"

    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        print(f"[OK] Saved {csv_path}")


def main() -> None:
    payload = build_context()
    write_outputs(payload)

    print("")
    print("Producer-injector context completed.")
    print(f"Method: {payload['method']['streamline_method']}")
    print(f"Producer count with water issue: {payload['producer_count_with_water_issue']}")


if __name__ == "__main__":
    main()
