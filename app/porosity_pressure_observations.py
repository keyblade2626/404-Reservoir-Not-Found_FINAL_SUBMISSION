import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


DRIVER_CONTEXT_CSV = Path("artifacts/diagnosis/well_property_driver_context.csv")
FINAL_WATER_JSON = Path("artifacts/final_diagnosis/final_hm_diagnosis.json")
FINAL_GAS_JSON = Path("artifacts/final_diagnosis/final_gas_diagnosis.json")

OUTPUT_DIR = Path("artifacts/final_diagnosis")


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


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return

    fieldnames = []
    seen = set()

    for row in rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Saved {path}")


def percentile_thresholds(values: List[float]) -> Dict[str, float]:
    arr = np.asarray([v for v in values if v is not None and np.isfinite(v)], dtype=float)

    if arr.size == 0:
        return {"p25": np.nan, "p75": np.nan}

    return {
        "p25": float(np.percentile(arr, 25)),
        "p75": float(np.percentile(arr, 75)),
    }


def build_context_lookup(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {r["well"]: r for r in rows if r.get("well")}


def classify_storage_pressure_signal(row: Dict[str, Any], delta_pressure_thresholds: Dict[str, float]) -> Dict[str, Any]:
    mean_poro = to_float(row.get("mean_poro"))
    mean_poro_pct = to_float(row.get("mean_poro_percentile"))
    poro_mult = to_float(row.get("mean_poro_mult"))

    mean_pressure_init = to_float(row.get("mean_pressure_init"))
    mean_pressure_eoh = to_float(row.get("mean_pressure_eoh"))
    delta_pressure = to_float(row.get("delta_pressure"))
    delta_pressure_pct = to_float(row.get("delta_pressure_percentile"))

    bhp_score = to_float(row.get("bhp_hm_score"))
    bhp_class = row.get("bhp_hm_class")
    bhp_status = row.get("bhp_status")

    bhp_direction = row.get("bhp_direction")
    bhp_final_direction = row.get("bhp_final_direction")
    bhp_recent_2yr_direction = row.get("bhp_recent_2yr_direction")
    sim_bhp_final = to_float(row.get("sim_bhp_final"))
    hist_bhp_final = to_float(row.get("hist_bhp_final"))
    bhp_final_delta = to_float(row.get("bhp_final_delta"))
    bhp_mean_bias_pct_recent_2yr = to_float(row.get("bhp_mean_bias_pct_recent_2yr"))

    # Relative signals.
    low_poro = (
        mean_poro_pct is not None and mean_poro_pct <= 25.0
    ) or (
        poro_mult is not None and poro_mult < 0.95
    )

    high_poro = (
        mean_poro_pct is not None and mean_poro_pct >= 75.0
    ) or (
        poro_mult is not None and poro_mult > 1.05
    )

    # delta_pressure is usually negative.
    # More negative = stronger depletion.
    p25 = delta_pressure_thresholds["p25"]
    p75 = delta_pressure_thresholds["p75"]

    strong_depletion = False
    weak_depletion = False

    if delta_pressure is not None and np.isfinite(p25) and np.isfinite(p75):
        strong_depletion = delta_pressure <= p25
        weak_depletion = delta_pressure >= p75

    # Absolute fallback.
    if delta_pressure is not None:
        if delta_pressure <= -500:
            strong_depletion = True
        if delta_pressure > -100:
            weak_depletion = True

    bhp_problem = (
        bhp_score is not None
        and bhp_score < 80
        and str(bhp_status).lower() == "evaluated"
    )

    pressure_too_low = str(bhp_direction).lower() == "simulated_pressure_too_low"
    pressure_too_high = str(bhp_direction).lower() == "simulated_pressure_too_high"

    observations = []
    caution = (
        "Porosity/pore-volume changes are volumetric calibration items and should not be used as a first-line "
        "local HM multiplier unless supported by STOIIP/GIIP/PV review and pressure evidence."
    )

    signal_category = "no_strong_porosity_pressure_signal"
    recommended_review = "No direct porosity/PV review signal."

    if bhp_problem and pressure_too_low and low_poro and strong_depletion:
        signal_category = "low_pore_volume_possible_excessive_depletion"
        observations.append(
            "Simulated BHP/pressure is too low, and low porosity / low pore-volume storage signal is present together with strong local pressure depletion."
        )
        observations.append(
            "Insufficient pore volume/storage may contribute to excessive depletion, but porosity/PV changes must be validated volumetrically."
        )
        recommended_review = (
            "Review local pore volume assumptions, porosity/NTG/PV consistency and volumetrics. "
            "Do this after checking injection/aquifer support and transmissibility connectivity."
        )

    elif bhp_problem and pressure_too_high and high_poro and weak_depletion:
        signal_category = "high_pore_volume_possible_damped_depletion"
        observations.append(
            "Simulated BHP/pressure is too high, and high porosity / high pore-volume storage signal is present together with weak local pressure depletion."
        )
        observations.append(
            "Excessive pore volume/storage may be damping pressure decline, but this should be confirmed against STOIIP/GIIP/PV constraints."
        )
        recommended_review = (
            "Review local pore volume assumptions and volumetrics only if pressure HM confirms insufficient simulated depletion. "
            "Also check aquifer/injection support and regional transmissibility."
        )

    elif bhp_problem and pressure_too_low and high_poro:
        signal_category = "pressure_too_low_not_explained_by_high_poro"
        observations.append(
            "Simulated BHP/pressure is too low, but porosity/PV signal is high rather than low. Porosity is unlikely to be the first explanation."
        )
        recommended_review = (
            "Prioritize pressure support, injection/aquifer balance, regional transmissibility and fault communication before porosity/PV tuning."
        )

    elif bhp_problem and pressure_too_high and low_poro:
        signal_category = "pressure_too_high_not_explained_by_low_poro"
        observations.append(
            "Simulated BHP/pressure is too high, but porosity/PV signal is low rather than high. Porosity is unlikely to be the first explanation."
        )
        recommended_review = (
            "Prioritize excessive pressure support, aquifer/injection balance, regional transmissibility and sealing assumptions before porosity/PV tuning."
        )

    elif low_poro and strong_depletion:
        signal_category = "low_pore_volume_storage_review"
        observations.append(
            "Low porosity / low pore-volume storage signal coincides with strong model pressure depletion."
        )
        observations.append(
            "This is a storage/depletion warning, but pressure mismatch direction is required before proposing a porosity/PV correction."
        )
        recommended_review = (
            "Use as a review flag. Check BHP plots, pressure maps, PV/STOIIP and support mechanisms before any porosity/PV change."
        )

    elif high_poro and weak_depletion:
        signal_category = "high_pore_volume_storage_review"
        observations.append(
            "High porosity / high pore-volume storage signal coincides with weak model pressure depletion."
        )
        observations.append(
            "This may indicate high storage/PV, but pressure mismatch direction is required before proposing any porosity/PV correction."
        )
        recommended_review = (
            "Use as a review flag. Check BHP plots, pressure maps, PV/STOIIP and support mechanisms."
        )

    elif bhp_problem:
        signal_category = "pressure_hm_issue_without_clear_poro_signal"
        observations.append(
            "BHP/pressure HM is below Good, but no strong local porosity/PV signal was detected."
        )
        recommended_review = (
            "Prioritize pressure support, injection/aquifer balance, regional transmissibility and fault communication before porosity/PV tuning."
        )

    return {
        "mean_poro": mean_poro,
        "mean_poro_percentile": mean_poro_pct,
        "mean_poro_mult": poro_mult,
        "mean_pressure_init": mean_pressure_init,
        "mean_pressure_eoh": mean_pressure_eoh,
        "delta_pressure": delta_pressure,
        "delta_pressure_percentile": delta_pressure_pct,
        "bhp_hm_score": bhp_score,
        "bhp_hm_class": bhp_class,
        "bhp_status": bhp_status,
        "bhp_direction": bhp_direction,
        "bhp_final_direction": bhp_final_direction,
        "bhp_recent_2yr_direction": bhp_recent_2yr_direction,
        "sim_bhp_final": sim_bhp_final,
        "hist_bhp_final": hist_bhp_final,
        "bhp_final_delta": bhp_final_delta,
        "bhp_mean_bias_pct_recent_2yr": bhp_mean_bias_pct_recent_2yr,
        "pressure_too_low": pressure_too_low,
        "pressure_too_high": pressure_too_high,
        "low_poro_signal": low_poro,
        "high_poro_signal": high_poro,
        "strong_depletion_signal": strong_depletion,
        "weak_depletion_signal": weak_depletion,
        "bhp_problem": bhp_problem,
        "porosity_pressure_signal_category": signal_category,
        "porosity_pressure_observations": observations,
        "porosity_pressure_recommended_review": recommended_review,
        "porosity_pressure_caution": caution,
    }


def enrich_final_payload(payload: Dict[str, Any], context_lookup: Dict[str, Dict[str, Any]], poro_obs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    enriched = json.loads(json.dumps(payload))

    for item in enriched.get("diagnoses", []):
        well = item.get("well")

        if not well:
            continue

        obs = poro_obs.get(well)

        if obs is None:
            continue

        item["porosity_pressure_observation"] = obs

        # Add a short evidence line if relevant.
        category = obs.get("porosity_pressure_signal_category")

        if category and category != "no_strong_porosity_pressure_signal":
            evidence = item.get("decision_evidence", [])

            short = (
                f"Porosity/pressure review: {category}. "
                f"mean_poro={obs.get('mean_poro')}, "
                f"mean_poro_percentile={obs.get('mean_poro_percentile')}, "
                f"delta_pressure={obs.get('delta_pressure')}."
            )

            if short not in evidence:
                evidence.append(short)

            item["decision_evidence"] = evidence

    return enriched


def flatten_observation_rows(poro_obs: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []

    for well, obs in poro_obs.items():
        rows.append({
            "well": well,
            "porosity_pressure_signal_category": obs.get("porosity_pressure_signal_category"),
            "mean_poro": obs.get("mean_poro"),
            "mean_poro_percentile": obs.get("mean_poro_percentile"),
            "mean_poro_mult": obs.get("mean_poro_mult"),
            "delta_pressure": obs.get("delta_pressure"),
            "delta_pressure_percentile": obs.get("delta_pressure_percentile"),
            "bhp_hm_score": obs.get("bhp_hm_score"),
            "bhp_hm_class": obs.get("bhp_hm_class"),
            "bhp_direction": obs.get("bhp_direction"),
            "bhp_final_direction": obs.get("bhp_final_direction"),
            "bhp_recent_2yr_direction": obs.get("bhp_recent_2yr_direction"),
            "sim_bhp_final": obs.get("sim_bhp_final"),
            "hist_bhp_final": obs.get("hist_bhp_final"),
            "bhp_final_delta": obs.get("bhp_final_delta"),
            "pressure_too_low": obs.get("pressure_too_low"),
            "pressure_too_high": obs.get("pressure_too_high"),
            "low_poro_signal": obs.get("low_poro_signal"),
            "high_poro_signal": obs.get("high_poro_signal"),
            "strong_depletion_signal": obs.get("strong_depletion_signal"),
            "weak_depletion_signal": obs.get("weak_depletion_signal"),
            "bhp_problem": obs.get("bhp_problem"),
            "recommended_review": obs.get("porosity_pressure_recommended_review"),
            "observations": " | ".join(obs.get("porosity_pressure_observations", [])),
            "caution": obs.get("porosity_pressure_caution"),
        })

    return rows


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    context_rows = read_csv_rows(DRIVER_CONTEXT_CSV)
    context_lookup = build_context_lookup(context_rows)

    delta_pressures = [
        to_float(r.get("delta_pressure"))
        for r in context_rows
        if to_float(r.get("delta_pressure")) is not None
    ]

    dp_thresholds = percentile_thresholds(delta_pressures)

    poro_obs = {}

    for well, row in context_lookup.items():
        poro_obs[well] = classify_storage_pressure_signal(row, dp_thresholds)

    obs_json = {
        "method": {
            "description": (
                "Porosity-pressure observations for HM interpretation. Porosity is treated as a pore-volume/storage review signal, "
                "not as an automatic local multiplier recommendation."
            ),
            "delta_pressure_p25": dp_thresholds["p25"],
            "delta_pressure_p75": dp_thresholds["p75"],
        },
        "observations": poro_obs,
    }

    obs_json_path = OUTPUT_DIR / "porosity_pressure_observations.json"
    obs_json_path.write_text(json.dumps(obs_json, indent=2), encoding="utf-8")
    print(f"[OK] Saved {obs_json_path}")

    write_csv(
        OUTPUT_DIR / "porosity_pressure_observations.csv",
        flatten_observation_rows(poro_obs),
    )

    water_payload = load_json(FINAL_WATER_JSON)
    if water_payload:
        enriched_water = enrich_final_payload(water_payload, context_lookup, poro_obs)
        out = OUTPUT_DIR / "final_hm_diagnosis_with_porosity_pressure.json"
        out.write_text(json.dumps(enriched_water, indent=2), encoding="utf-8")
        print(f"[OK] Saved {out}")

    gas_payload = load_json(FINAL_GAS_JSON)
    if gas_payload:
        enriched_gas = enrich_final_payload(gas_payload, context_lookup, poro_obs)
        out = OUTPUT_DIR / "final_gas_diagnosis_with_porosity_pressure.json"
        out.write_text(json.dumps(enriched_gas, indent=2), encoding="utf-8")
        print(f"[OK] Saved {out}")

    print("")
    print("Porosity-pressure observations completed.")
    print("Important: these are storage/PV review flags, not automatic porosity multiplier recommendations.")


if __name__ == "__main__":
    main()
