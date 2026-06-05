import csv
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.summary_importer import (
    DEFAULT_CASE_ROOT,
    _detect_well_keys,
    _get_dates,
    _get_summary_keys,
    _get_vector_values,
    _load_resdata_summary,
)
from app.well_connections import get_well_spatial_summary


OUTPUT_DIR = Path("artifacts/injection_hm")

WATER_INJECTION_RATE_THRESHOLD = 10.0
GAS_INJECTION_RATE_THRESHOLD = 10.0


INJECTION_CONFIG = {
    "water_injection": {
        "label": "Water injection",
        "sim_rate": ["WWIR"],
        "hist_rate": ["WWIRH"],
        "sim_cum": ["WWIT"],
        "hist_cum": ["WWITH"],
        "threshold": WATER_INJECTION_RATE_THRESHOLD,
        "weight": 0.55,
    },
    "gas_injection": {
        "label": "Gas injection",
        "sim_rate": ["WGIR"],
        "hist_rate": ["WGIRH"],
        "sim_cum": ["WGIT"],
        "hist_cum": ["WGITH"],
        "threshold": GAS_INJECTION_RATE_THRESHOLD,
        "weight": 0.45,
    },
}


PRODUCTION_VECTORS = {
    "oil": ["WOPR", "WOPRH"],
    "water": ["WWPR", "WWPRH"],
    "gas": ["WGPR", "WGPRH"],
}


def _parse_date(value: Any) -> Optional[datetime]:
    text = str(value)

    try:
        return datetime.fromisoformat(text.replace("Z", ""))
    except Exception:
        pass

    import re

    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        try:
            return datetime.fromisoformat(match.group(0))
        except Exception:
            return None

    return None


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0

    m = _mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / len(values))


def _pearson(a: List[float], b: List[float]) -> Optional[float]:
    if len(a) < 2 or len(b) < 2:
        return None

    ma = _mean(a)
    mb = _mean(b)
    sa = _std(a)
    sb = _std(b)

    if sa <= 1e-12 or sb <= 1e-12:
        return None

    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / len(a)
    return cov / (sa * sb)


def _relative_rmse_score(sim: List[float], hist: List[float]) -> Optional[float]:
    if len(sim) < 2 or len(hist) < 2:
        return None

    rmse = math.sqrt(sum((s - h) ** 2 for s, h in zip(sim, hist)) / len(sim))
    scale = max(abs(_mean(hist)), _std(hist), 1e-9)
    relative_error = rmse / scale

    return max(0.0, min(100.0, 100.0 * (1.0 - min(relative_error, 1.0))))


def _profile_similarity_score(sim: List[float], hist: List[float]) -> Optional[float]:
    corr = _pearson(sim, hist)

    if corr is not None:
        return max(0.0, min(100.0, ((corr + 1.0) / 2.0) * 100.0))

    return _relative_rmse_score(sim, hist)


def _score_class(score: Optional[float]) -> str:
    if score is None:
        return "Unavailable"

    if score >= 80:
        return "Good"

    if score >= 60:
        return "Fair"

    return "Poor"


def _align_series(
    dates: List[Any],
    sim_values: Optional[List[float]],
    hist_values: Optional[List[float]],
) -> Tuple[List[Any], List[float], List[float]]:
    if sim_values is None or hist_values is None:
        return [], [], []

    n = min(len(dates), len(sim_values), len(hist_values))

    aligned_dates = []
    aligned_sim = []
    aligned_hist = []

    for i in range(n):
        try:
            s = float(sim_values[i])
            h = float(hist_values[i])
        except Exception:
            continue

        if math.isnan(s) or math.isnan(h):
            continue

        aligned_dates.append(dates[i])
        aligned_sim.append(s)
        aligned_hist.append(h)

    return aligned_dates, aligned_sim, aligned_hist


def _last_two_years_subset(
    dates: List[Any],
    sim: List[float],
    hist: List[float],
) -> Tuple[List[Any], List[float], List[float]]:
    parsed_dates = [_parse_date(d) for d in dates]
    valid_dates = [d for d in parsed_dates if d is not None]

    if not valid_dates:
        n = min(24, len(sim))
        return dates[-n:], sim[-n:], hist[-n:]

    last_date = valid_dates[-1]
    cutoff = last_date - timedelta(days=730)

    recent_dates = []
    recent_sim = []
    recent_hist = []

    for raw_date, parsed_date, s, h in zip(dates, parsed_dates, sim, hist):
        if parsed_date is None:
            continue

        if parsed_date >= cutoff:
            recent_dates.append(raw_date)
            recent_sim.append(s)
            recent_hist.append(h)

    if len(recent_sim) < 2:
        return dates, sim, hist

    return recent_dates, recent_sim, recent_hist


def _final_value_score(sim_final: float, hist_final: float) -> Optional[float]:
    denominator = max(abs(hist_final), 1e-9)
    relative_error = abs(sim_final - hist_final) / denominator

    return max(0.0, min(100.0, 100.0 * (1.0 - min(relative_error, 1.0))))


def _integrate_rate(dates: List[Any], values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return None

    parsed_dates = [_parse_date(d) for d in dates]

    if any(d is None for d in parsed_dates):
        return sum(values)

    total = 0.0

    for i in range(1, len(values)):
        delta_days = max((parsed_dates[i] - parsed_dates[i - 1]).days, 0)
        avg_rate = 0.5 * (values[i] + values[i - 1])
        total += avg_rate * delta_days

    return total


def _get_existing_vector(
    summary_obj: Any,
    keys_upper_map: Dict[str, str],
    well: str,
    candidates: List[str],
) -> Tuple[Optional[str], Optional[List[float]]]:
    for vector in candidates:
        target = f"{vector.upper()}:{well}".upper()
        key = keys_upper_map.get(target)

        if key:
            try:
                return key, _get_vector_values(summary_obj, key)
            except Exception:
                continue

    return None, None


def _max_abs(values: Optional[List[float]]) -> float:
    if not values:
        return 0.0

    return max(abs(float(v)) for v in values)


def _first_material_date(dates: List[Any], values: Optional[List[float]], threshold: float) -> Optional[str]:
    if values is None:
        return None

    n = min(len(dates), len(values))

    for i in range(n):
        try:
            value = abs(float(values[i]))
        except Exception:
            continue

        if value > threshold:
            return str(dates[i])

    return None


def _direction_from_final_or_cum(
    sim_final: Optional[float],
    hist_final: Optional[float],
    threshold: float,
) -> str:
    if sim_final is None or hist_final is None:
        return "unknown"

    sim_final = float(sim_final)
    hist_final = float(hist_final)

    if sim_final <= threshold and hist_final <= threshold:
        return "negligible_injection"

    tolerance = max(threshold, abs(hist_final) * 0.10)

    if sim_final > hist_final + tolerance:
        return "simulated_over_injection"

    if sim_final < hist_final - tolerance:
        return "simulated_under_injection"

    return "final_injection_close"


def _evaluate_injection_variable(
    variable_name: str,
    dates: List[Any],
    sim_rate: Optional[List[float]],
    hist_rate: Optional[List[float]],
    sim_rate_key: Optional[str],
    hist_rate_key: Optional[str],
    sim_cum: Optional[List[float]],
    hist_cum: Optional[List[float]],
    threshold: float,
) -> Dict[str, Any]:
    sim_max = _max_abs(sim_rate)
    hist_max = _max_abs(hist_rate)

    sim_negligible = sim_max <= threshold
    hist_negligible = hist_max <= threshold

    if sim_rate is None and hist_rate is None:
        return {
            "status": "unavailable",
            "reason": "Neither simulated nor historical injection vector is available.",
            "score": None,
            "class": "Unavailable",
            "direction": "unknown",
            "sim_rate_key": sim_rate_key,
            "hist_rate_key": hist_rate_key,
            "max_sim_signal": None,
            "max_hist_signal": None,
        }

    if sim_negligible and hist_negligible:
        return {
            "status": "inactive",
            "reason": "Both simulated and historical injection signals are negligible.",
            "score": None,
            "class": "Inactive",
            "direction": "negligible_injection",
            "sim_rate_key": sim_rate_key,
            "hist_rate_key": hist_rate_key,
            "max_sim_signal": sim_max,
            "max_hist_signal": hist_max,
            "negligible_match": True,
        }

    if not sim_negligible and hist_negligible:
        return {
            "status": "evaluated",
            "reason": "Simulation injects materially while historical injection is negligible.",
            "score": 0.0,
            "class": "Poor",
            "direction": "simulated_over_injection",
            "components": {
                "full_trend_score": 0.0,
                "recent_2yr_trend_score": 0.0,
                "final_score": 0.0,
            },
            "sim_rate_key": sim_rate_key,
            "hist_rate_key": hist_rate_key,
            "max_sim_signal": sim_max,
            "max_hist_signal": hist_max,
            "negligible_match": False,
        }

    if sim_negligible and not hist_negligible:
        return {
            "status": "evaluated",
            "reason": "Historical injection is material while simulated injection is negligible.",
            "score": 0.0,
            "class": "Poor",
            "direction": "simulated_under_injection",
            "components": {
                "full_trend_score": 0.0,
                "recent_2yr_trend_score": 0.0,
                "final_score": 0.0,
            },
            "sim_rate_key": sim_rate_key,
            "hist_rate_key": hist_rate_key,
            "max_sim_signal": sim_max,
            "max_hist_signal": hist_max,
            "negligible_match": False,
        }

    aligned_dates, sim, hist = _align_series(dates, sim_rate, hist_rate)

    if len(sim) < 2:
        return {
            "status": "unavailable",
            "reason": "Not enough aligned injection points to evaluate match.",
            "score": None,
            "class": "Unavailable",
            "direction": "unknown",
            "sim_rate_key": sim_rate_key,
            "hist_rate_key": hist_rate_key,
            "max_sim_signal": sim_max,
            "max_hist_signal": hist_max,
        }

    full_trend_score = _profile_similarity_score(sim, hist)

    _, recent_sim, recent_hist = _last_two_years_subset(aligned_dates, sim, hist)
    recent_score = _profile_similarity_score(recent_sim, recent_hist)

    final_score = None
    final_comparison_type = "final_rate"

    sim_final_for_direction = sim[-1]
    hist_final_for_direction = hist[-1]

    if sim_cum is not None and hist_cum is not None:
        _, sim_c, hist_c = _align_series(dates, sim_cum, hist_cum)

        if sim_c and hist_c:
            final_score = _final_value_score(sim_c[-1], hist_c[-1])
            final_comparison_type = "final_cumulative_vector"
            sim_final_for_direction = sim_c[-1]
            hist_final_for_direction = hist_c[-1]

    if final_score is None:
        sim_integrated = _integrate_rate(aligned_dates, sim)
        hist_integrated = _integrate_rate(aligned_dates, hist)

        if sim_integrated is not None and hist_integrated is not None:
            final_score = _final_value_score(sim_integrated, hist_integrated)
            final_comparison_type = "integrated_rate_cumulative"
            sim_final_for_direction = sim_integrated
            hist_final_for_direction = hist_integrated
        else:
            final_score = _final_value_score(sim[-1], hist[-1])

    components = {
        "full_trend_score": round(full_trend_score, 2) if full_trend_score is not None else None,
        "recent_2yr_trend_score": round(recent_score, 2) if recent_score is not None else None,
        "final_score": round(final_score, 2) if final_score is not None else None,
    }

    weights = {
        "full_trend_score": 0.45,
        "recent_2yr_trend_score": 0.25,
        "final_score": 0.30,
    }

    available = [(name, value) for name, value in components.items() if value is not None]

    if available:
        weight_sum = sum(weights[name] for name, _ in available)
        score = sum(value * weights[name] for name, value in available) / weight_sum
    else:
        score = None

    direction = _direction_from_final_or_cum(
        sim_final_for_direction,
        hist_final_for_direction,
        threshold,
    )

    return {
        "status": "evaluated",
        "reason": "Injection match evaluated using rate profile, recent trend and final cumulative/final value.",
        "score": round(score, 2) if score is not None else None,
        "class": _score_class(score),
        "direction": direction,
        "components": components,
        "final_comparison_type": final_comparison_type,
        "sim_rate_key": sim_rate_key,
        "hist_rate_key": hist_rate_key,
        "point_count": len(sim),
        "max_sim_signal": sim_max,
        "max_hist_signal": hist_max,
        "last_sim_rate": sim[-1],
        "last_hist_rate": hist[-1],
        "sim_injection_start_date": _first_material_date(dates, sim_rate, threshold),
        "hist_injection_start_date": _first_material_date(dates, hist_rate, threshold),
        "negligible_match": False,
    }


def _has_material_signal(result: Dict[str, Any]) -> bool:
    if result.get("status") == "evaluated":
        return True

    if result.get("max_sim_signal") is not None and float(result.get("max_sim_signal")) > 0:
        return True

    if result.get("max_hist_signal") is not None and float(result.get("max_hist_signal")) > 0:
        return True

    return False


def _has_material_production(
    summary_obj: Any,
    keys_upper_map: Dict[str, str],
    well: str,
) -> bool:
    for _, candidates in PRODUCTION_VECTORS.items():
        for vector in candidates:
            _, values = _get_existing_vector(summary_obj, keys_upper_map, well, [vector])

            if values is not None and _max_abs(values) > 10.0:
                return True

    return False


def _classify_injector_role(
    water_result: Dict[str, Any],
    gas_result: Dict[str, Any],
    has_material_production: bool,
) -> str:
    water_active = _has_material_signal(water_result) and water_result.get("direction") != "negligible_injection"
    gas_active = _has_material_signal(gas_result) and gas_result.get("direction") != "negligible_injection"

    if not water_active and not gas_active and not has_material_production:
        return "inactive_or_no_material_signal"

    if has_material_production and not water_active and not gas_active:
        return "producer_only"

    if has_material_production and water_active and gas_active:
        return "mixed_producer_wag"

    if has_material_production and water_active:
        return "mixed_producer_water_injector"

    if has_material_production and gas_active:
        return "mixed_producer_gas_injector"

    if water_active and gas_active:
        return "wag_or_dual_injector"

    if water_active:
        return "water_injector"

    if gas_active:
        return "gas_injector"

    return "not_interpretable"


def _overall_injection_score(water: Dict[str, Any], gas: Dict[str, Any]) -> Tuple[Optional[float], str]:
    scores = []
    weights = []

    for name, result in [("water_injection", water), ("gas_injection", gas)]:
        score = result.get("score")

        if score is None:
            continue

        scores.append(float(score))
        weights.append(INJECTION_CONFIG[name]["weight"])

    if not scores:
        return None, "Unavailable"

    total_weight = sum(weights)
    overall = sum(s * w for s, w in zip(scores, weights)) / total_weight

    return round(overall, 2), _score_class(overall)


def build_injection_hm(case_root: Path = DEFAULT_CASE_ROOT) -> Dict[str, Any]:
    summary_obj = _load_resdata_summary(case_root)
    keys = _get_summary_keys(summary_obj)
    keys_upper_map = {key.upper(): key for key in keys}
    wells = sorted(_detect_well_keys(keys).keys())
    dates = _get_dates(summary_obj)

    spatial = get_well_spatial_summary()
    spatial_wells = spatial.get("wells", {})

    well_results: Dict[str, Any] = {}

    for well in wells:
        variable_results = {}

        for variable_name, cfg in INJECTION_CONFIG.items():
            sim_rate_key, sim_rate = _get_existing_vector(
                summary_obj,
                keys_upper_map,
                well,
                cfg["sim_rate"],
            )
            hist_rate_key, hist_rate = _get_existing_vector(
                summary_obj,
                keys_upper_map,
                well,
                cfg["hist_rate"],
            )
            sim_cum_key, sim_cum = _get_existing_vector(
                summary_obj,
                keys_upper_map,
                well,
                cfg["sim_cum"],
            )
            hist_cum_key, hist_cum = _get_existing_vector(
                summary_obj,
                keys_upper_map,
                well,
                cfg["hist_cum"],
            )

            result = _evaluate_injection_variable(
                variable_name=variable_name,
                dates=dates,
                sim_rate=sim_rate,
                hist_rate=hist_rate,
                sim_rate_key=sim_rate_key,
                hist_rate_key=hist_rate_key,
                sim_cum=sim_cum,
                hist_cum=hist_cum,
                threshold=cfg["threshold"],
            )

            result["sim_cum_key"] = sim_cum_key
            result["hist_cum_key"] = hist_cum_key

            variable_results[variable_name] = result

        has_prod = _has_material_production(summary_obj, keys_upper_map, well)
        role = _classify_injector_role(
            variable_results["water_injection"],
            variable_results["gas_injection"],
            has_prod,
        )

        overall_score, overall_class = _overall_injection_score(
            variable_results["water_injection"],
            variable_results["gas_injection"],
        )

        spatial_payload = spatial_wells.get(well, {})

        well_results[well] = {
            "well": well,
            "role": role,
            "has_material_production": has_prod,
            "i": spatial_payload.get("representative_i"),
            "j": spatial_payload.get("representative_j"),
            "injection_hm_score": overall_score,
            "injection_hm_class": overall_class,
            "variables": variable_results,
        }

    role_counts: Dict[str, int] = {}

    for payload in well_results.values():
        role = payload.get("role")
        role_counts[role] = role_counts.get(role, 0) + 1

    return {
        "source_type": "native_smspec_unsmry_injection_history_match",
        "case_root": str(case_root),
        "well_count": len(well_results),
        "role_counts": role_counts,
        "well_results": well_results,
    }


def write_outputs(payload: Dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = OUTPUT_DIR / "injection_hm_results.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[OK] Saved {json_path}")

    rows = []

    for well, result in payload["well_results"].items():
        water = result["variables"]["water_injection"]
        gas = result["variables"]["gas_injection"]

        rows.append(
            {
                "well": well,
                "role": result.get("role"),
                "i": result.get("i"),
                "j": result.get("j"),
                "injection_hm_score": result.get("injection_hm_score"),
                "injection_hm_class": result.get("injection_hm_class"),
                "water_injection_score": water.get("score"),
                "water_injection_class": water.get("class"),
                "water_injection_direction": water.get("direction"),
                "water_injection_status": water.get("status"),
                "water_max_sim_signal": water.get("max_sim_signal"),
                "water_max_hist_signal": water.get("max_hist_signal"),
                "gas_injection_score": gas.get("score"),
                "gas_injection_class": gas.get("class"),
                "gas_injection_direction": gas.get("direction"),
                "gas_injection_status": gas.get("status"),
                "gas_max_sim_signal": gas.get("max_sim_signal"),
                "gas_max_hist_signal": gas.get("max_hist_signal"),
            }
        )

    csv_path = OUTPUT_DIR / "injection_hm_summary.csv"

    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        print(f"[OK] Saved {csv_path}")


def main() -> None:
    payload = build_injection_hm()
    write_outputs(payload)

    print("")
    print("Injection HM completed.")
    print(f"Role counts: {payload['role_counts']}")


if __name__ == "__main__":
    main()
