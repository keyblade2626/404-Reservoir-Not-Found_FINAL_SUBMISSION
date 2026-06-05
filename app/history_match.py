import math
import re
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


# Engineering thresholds used to decide whether a signal is material.
# If both simulated and historical rates are below threshold, the variable is considered matched.
NEGLIGIBLE_LIQUID_RATE_THRESHOLD = 10.0
NEGLIGIBLE_GAS_RATE_THRESHOLD = 10.0


VARIABLE_CONFIG = {
    "oil": {
        "label": "Oil rate / cumulative oil",
        "sim_rate": ["WOPR"],
        "hist_rate": ["WOPRH"],
        "sim_cum": ["WOPT"],
        "hist_cum": ["WOPTH"],
        "weight": 0.40,
        "critical": True,
        "negligible_threshold": NEGLIGIBLE_LIQUID_RATE_THRESHOLD,
    },
    "watercut": {
        "label": "Water cut / water behaviour",
        "sim_direct": ["WWCT"],
        "hist_direct": ["WWCTH"],
        "sim_numerator": ["WWPR"],
        "sim_denominator": ["WOPR", "WWPR"],
        "hist_numerator": ["WWPRH"],
        "hist_denominator": ["WOPRH", "WWPRH"],
        "sim_water_rate": ["WWPR"],
        "hist_water_rate": ["WWPRH"],
        "weight": 0.30,
        "critical": True,
        "negligible_threshold": NEGLIGIBLE_LIQUID_RATE_THRESHOLD,
    },
    "gor": {
        "label": "Gas-oil ratio / gas behaviour",
        "sim_direct": ["WGOR"],
        "hist_direct": ["WGORH"],
        "sim_numerator": ["WGPR"],
        "sim_denominator": ["WOPR"],
        "hist_numerator": ["WGPRH"],
        "hist_denominator": ["WOPRH"],
        "sim_gas_rate": ["WGPR"],
        "hist_gas_rate": ["WGPRH"],
        "weight": 0.20,
        "critical": True,
        "negligible_threshold": NEGLIGIBLE_GAS_RATE_THRESHOLD,
    },
    "bhp": {
        "label": "Bottom-hole pressure",
        "sim_direct": ["WBHP"],
        "hist_direct": ["WBHPH"],
        "weight": 0.10,
        "critical": False,
        "optional": True,
    },
}


def _parse_date(value: Any) -> Optional[datetime]:
    text = str(value)
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)

    if match:
        try:
            return datetime.fromisoformat(match.group(0))
        except Exception:
            return None

    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _align_series(
    dates: List[Any],
    sim_values: List[float],
    hist_values: List[float],
) -> Tuple[List[Any], List[float], List[float]]:
    n = min(len(dates), len(sim_values), len(hist_values))

    aligned_dates = []
    aligned_sim = []
    aligned_hist = []

    for i in range(n):
        s = sim_values[i]
        h = hist_values[i]

        if s is None or h is None:
            continue

        try:
            s = float(s)
            h = float(h)
        except Exception:
            continue

        if math.isnan(s) or math.isnan(h):
            continue

        aligned_dates.append(dates[i])
        aligned_sim.append(s)
        aligned_hist.append(h)

    return aligned_dates, aligned_sim, aligned_hist


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0

    m = _mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / len(values))


def _max_abs(values: Optional[List[float]]) -> float:
    if not values:
        return 0.0

    return max(abs(float(v)) for v in values)


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
    """
    Scores visual/profile similarity.

    Primary metric:
    - Pearson correlation converted from [-1, 1] to [0, 100]

    Fallback:
    - relative RMSE score, useful when correlation is not defined.
    """
    if len(sim) < 2 or len(hist) < 2:
        return None

    corr = _pearson(sim, hist)

    if corr is not None:
        return max(0.0, min(100.0, ((corr + 1.0) / 2.0) * 100.0))

    return _relative_rmse_score(sim, hist)


def _last_two_years_subset(
    dates: List[Any],
    sim: List[float],
    hist: List[float],
) -> Tuple[List[Any], List[float], List[float]]:
    parsed_dates = [_parse_date(d) for d in dates]
    valid_dates = [d for d in parsed_dates if d is not None]

    if not valid_dates:
        # Fallback: last 24 points, or all available points if fewer.
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

    # If the well has less than 2 years of valid data, use all available data.
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
        average_rate = 0.5 * (values[i] + values[i - 1])
        total += average_rate * delta_days

    return total


def _score_class(score: Optional[float]) -> str:
    if score is None:
        return "Unavailable"

    if score >= 80:
        return "Good"

    if score >= 60:
        return "Fair"

    return "Poor"


def _well_class(score: Optional[float], variable_results: Dict[str, Any]) -> str:
    """
    Well class is not just a weighted average.

    A well cannot remain Good if a critical variable such as oil, watercut or GOR is Poor.
    BHP is not critical and therefore does not cap the well class by itself.
    """
    if score is None:
        return "Unavailable"

    critical_poor = [
        variable_name
        for variable_name, result in variable_results.items()
        if VARIABLE_CONFIG.get(variable_name, {}).get("critical", False)
        and result.get("status") == "evaluated"
        and result.get("score") is not None
        and result.get("score") < 60
    ]

    if score < 60:
        return "Poor"

    if len(critical_poor) >= 2:
        return "Poor"

    if len(critical_poor) == 1:
        return "Fair"

    if score >= 80:
        return "Good"

    if score >= 60:
        return "Fair"

    return "Poor"


def _technical_flags(variable_results: Dict[str, Any]) -> List[str]:
    flags = []

    for variable_name, result in variable_results.items():
        status = result.get("status")
        score = result.get("score")
        reason = result.get("reason")

        if status == "inactive":
            flags.append(f"{variable_name}: inactive/excluded ({reason})")

        if status == "evaluated" and result.get("negligible_match"):
            flags.append(f"{variable_name}: negligible signal considered matched")

        if status == "evaluated" and score is not None and score < 60:
            if VARIABLE_CONFIG.get(variable_name, {}).get("critical", False):
                flags.append(f"{variable_name}: critical poor match")
            else:
                flags.append(f"{variable_name}: poor match")

    return flags


def _find_key(keys_upper_map: Dict[str, str], vector: str, well: str) -> Optional[str]:
    target = f"{vector.upper()}:{well}".upper()
    return keys_upper_map.get(target)


def _get_existing_vector(
    summary_obj: Any,
    keys_upper_map: Dict[str, str],
    well: str,
    candidates: List[str],
) -> Tuple[Optional[str], Optional[List[float]]]:
    for vector in candidates:
        key = _find_key(keys_upper_map, vector, well)

        if key:
            try:
                values = _get_vector_values(summary_obj, key)
                return key, values
            except Exception:
                continue

    return None, None


def _safe_divide_series(numerator: List[float], denominator: List[float]) -> List[float]:
    n = min(len(numerator), len(denominator))
    result = []

    for i in range(n):
        den = denominator[i]

        if abs(den) <= 1e-12:
            result.append(0.0)
        else:
            result.append(numerator[i] / den)

    return result


def _sum_series(series_list: List[List[float]]) -> List[float]:
    n = min(len(s) for s in series_list)
    return [sum(s[i] for s in series_list) for i in range(n)]


def _build_direct_or_calculated_series(
    summary_obj: Any,
    keys_upper_map: Dict[str, str],
    well: str,
    direct_candidates: Optional[List[str]] = None,
    numerator_candidates: Optional[List[str]] = None,
    denominator_candidates: Optional[List[str]] = None,
) -> Tuple[Optional[str], Optional[List[float]]]:
    direct_candidates = direct_candidates or []
    numerator_candidates = numerator_candidates or []
    denominator_candidates = denominator_candidates or []

    direct_key, direct_values = _get_existing_vector(
        summary_obj,
        keys_upper_map,
        well,
        direct_candidates,
    )

    if direct_values is not None:
        return direct_key, direct_values

    numerator_key, numerator_values = _get_existing_vector(
        summary_obj,
        keys_upper_map,
        well,
        numerator_candidates,
    )

    if numerator_values is None:
        return None, None

    denominator_series = []
    denominator_keys = []

    for candidate in denominator_candidates:
        key, values = _get_existing_vector(summary_obj, keys_upper_map, well, [candidate])

        if values is None:
            return None, None

        denominator_keys.append(key)
        denominator_series.append(values)

    denominator_values = _sum_series(denominator_series)
    calculated = _safe_divide_series(numerator_values, denominator_values)

    return f"calculated_from:{numerator_key}/{' + '.join(denominator_keys)}", calculated


def _water_breakthrough(dates: List[Any], values: List[float], threshold: float = 0.05) -> Optional[str]:
    for d, v in zip(dates, values):
        if v >= threshold:
            return str(d)

    return None


def _gas_rise_event(dates: List[Any], values: List[float]) -> Optional[str]:
    if len(values) < 2:
        return None

    baseline = values[0]
    max_value = max(values)

    if max_value <= baseline:
        return None

    threshold = baseline + 0.30 * (max_value - baseline)

    for d, v in zip(dates, values):
        if v >= threshold:
            return str(d)

    return None


def _evaluate_signal_status(
    variable_name: str,
    sim_signal: Optional[List[float]],
    hist_signal: Optional[List[float]],
    threshold: float,
) -> Optional[Dict[str, Any]]:
    """
    Handles negligible profiles before normal scoring.

    Rules:
    - sim negligible and hist negligible:
        considered matched, score 100, class Good
    - sim significant and hist negligible:
        Poor
    - sim negligible and hist significant:
        Poor
    - both significant:
        continue normal scoring
    """
    if sim_signal is None or hist_signal is None:
        return None

    sim_max = _max_abs(sim_signal)
    hist_max = _max_abs(hist_signal)

    sim_negligible = sim_max <= threshold
    hist_negligible = hist_max <= threshold

    if sim_negligible and hist_negligible:
        return {
            "status": "evaluated",
            "reason": (
                f"Both simulated and historical {variable_name} signals are negligible "
                f"and considered matched "
                f"(max_sim={round(sim_max, 4)}, max_hist={round(hist_max, 4)}, threshold={threshold})."
            ),
            "score": 100.0,
            "class": "Good",
            "components": {
                "full_trend_score": 100.0,
                "recent_2yr_trend_score": 100.0,
                "final_score": 100.0,
            },
            "max_sim_signal": sim_max,
            "max_hist_signal": hist_max,
            "negligible_match": True,
        }

    if not sim_negligible and hist_negligible:
        return {
            "status": "evaluated",
            "reason": (
                f"Simulated {variable_name} signal is significant but historical signal is negligible "
                f"(max_sim={round(sim_max, 4)}, max_hist={round(hist_max, 4)}, threshold={threshold})."
            ),
            "score": 0.0,
            "class": "Poor",
            "components": {
                "full_trend_score": 0.0,
                "recent_2yr_trend_score": 0.0,
                "final_score": 0.0,
            },
            "max_sim_signal": sim_max,
            "max_hist_signal": hist_max,
            "negligible_match": False,
        }

    if sim_negligible and not hist_negligible:
        return {
            "status": "evaluated",
            "reason": (
                f"Historical {variable_name} signal is significant but simulated signal is negligible "
                f"(max_sim={round(sim_max, 4)}, max_hist={round(hist_max, 4)}, threshold={threshold})."
            ),
            "score": 0.0,
            "class": "Poor",
            "components": {
                "full_trend_score": 0.0,
                "recent_2yr_trend_score": 0.0,
                "final_score": 0.0,
            },
            "max_sim_signal": sim_max,
            "max_hist_signal": hist_max,
            "negligible_match": False,
        }

    return None


def _evaluate_variable(
    variable_name: str,
    dates: List[Any],
    sim_values: Optional[List[float]],
    hist_values: Optional[List[float]],
    sim_key: Optional[str],
    hist_key: Optional[str],
    sim_cum_values: Optional[List[float]] = None,
    hist_cum_values: Optional[List[float]] = None,
    sim_signal: Optional[List[float]] = None,
    hist_signal: Optional[List[float]] = None,
    negligible_threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Evaluates one variable.

    Important BHP rule:
    - BHP is optional.
    - If observed/historical BHP is missing, the variable is inactive and excluded from well score.
    """
    if variable_name == "bhp" and hist_values is None:
        return {
            "status": "inactive",
            "reason": "Historical/observed BHP vector is not available; BHP is excluded from this well score.",
            "sim_key": sim_key,
            "hist_key": hist_key,
            "score": None,
            "class": "Inactive",
        }

    if variable_name == "bhp" and sim_values is None:
        return {
            "status": "inactive",
            "reason": "Simulated BHP vector is not available; BHP is excluded from this well score.",
            "sim_key": sim_key,
            "hist_key": hist_key,
            "score": None,
            "class": "Inactive",
        }

    if sim_values is None:
        return {
            "status": "unavailable",
            "reason": "Simulated vector not available.",
            "sim_key": sim_key,
            "hist_key": hist_key,
            "score": None,
            "class": "Unavailable",
        }

    if hist_values is None:
        return {
            "status": "unavailable",
            "reason": "Historical/observed vector not available.",
            "sim_key": sim_key,
            "hist_key": hist_key,
            "score": None,
            "class": "Unavailable",
        }

    if negligible_threshold is not None:
        signal_result = _evaluate_signal_status(
            variable_name=variable_name,
            sim_signal=sim_signal if sim_signal is not None else sim_values,
            hist_signal=hist_signal if hist_signal is not None else hist_values,
            threshold=negligible_threshold,
        )

        if signal_result is not None:
            signal_result["sim_key"] = sim_key
            signal_result["hist_key"] = hist_key
            signal_result["signal_rule_applied"] = True
            return signal_result

    aligned_dates, sim, hist = _align_series(dates, sim_values, hist_values)

    if len(sim) < 2:
        return {
            "status": "unavailable",
            "reason": "Not enough aligned points to evaluate match.",
            "sim_key": sim_key,
            "hist_key": hist_key,
            "score": None,
            "class": "Unavailable",
        }

    full_trend_score = _profile_similarity_score(sim, hist)

    recent_dates, recent_sim, recent_hist = _last_two_years_subset(aligned_dates, sim, hist)
    recent_trend_score = _profile_similarity_score(recent_sim, recent_hist)

    final_score = _final_value_score(sim[-1], hist[-1])
    final_comparison_type = "final_value"

    if variable_name == "oil":
        if sim_cum_values is not None and hist_cum_values is not None:
            _, sim_cum, hist_cum = _align_series(dates, sim_cum_values, hist_cum_values)

            if sim_cum and hist_cum:
                final_score = _final_value_score(sim_cum[-1], hist_cum[-1])
                final_comparison_type = "final_cumulative_vector"
        else:
            sim_integrated = _integrate_rate(aligned_dates, sim)
            hist_integrated = _integrate_rate(aligned_dates, hist)

            if sim_integrated is not None and hist_integrated is not None:
                final_score = _final_value_score(sim_integrated, hist_integrated)
                final_comparison_type = "integrated_rate_cumulative"

    components = {
        "full_trend_score": round(full_trend_score, 2) if full_trend_score is not None else None,
        "recent_2yr_trend_score": round(recent_trend_score, 2) if recent_trend_score is not None else None,
        "final_score": round(final_score, 2) if final_score is not None else None,
    }

    weights = {
        "full_trend_score": 0.50,
        "recent_2yr_trend_score": 0.30,
        "final_score": 0.20,
    }

    available_components = [
        (name, value)
        for name, value in components.items()
        if value is not None
    ]

    if not available_components:
        score = None
    else:
        weight_sum = sum(weights[name] for name, _ in available_components)
        score = sum(value * weights[name] for name, value in available_components) / weight_sum

    events: Dict[str, Any] = {}

    if variable_name == "watercut":
        events["sim_water_breakthrough_date"] = _water_breakthrough(aligned_dates, sim)
        events["hist_water_breakthrough_date"] = _water_breakthrough(aligned_dates, hist)

    if variable_name == "gor":
        events["sim_gas_rise_date"] = _gas_rise_event(aligned_dates, sim)
        events["hist_gas_rise_date"] = _gas_rise_event(aligned_dates, hist)

    return {
        "status": "evaluated",
        "sim_key": sim_key,
        "hist_key": hist_key,
        "point_count": len(sim),
        "recent_point_count": len(recent_sim),
        "final_comparison_type": final_comparison_type,
        "components": components,
        "score": round(score, 2) if score is not None else None,
        "class": _score_class(score),
        "events": events,
        "last_sim_value": sim[-1],
        "last_hist_value": hist[-1],
        "signal_rule_applied": False,
        "negligible_match": False,
    }


def build_history_match_kpis(case_root: Path = DEFAULT_CASE_ROOT) -> Dict[str, Any]:
    summary_obj = _load_resdata_summary(case_root)
    keys = _get_summary_keys(summary_obj)
    dates = _get_dates(summary_obj)

    keys_upper_map = {key.upper(): key for key in keys}
    well_key_map = _detect_well_keys(keys)

    wells = sorted(well_key_map.keys())

    well_results: Dict[str, Any] = {}
    model_weighted_scores = []
    model_weights = []

    for well in wells:
        variable_results: Dict[str, Any] = {}

        # ------------------------------------------------------------
        # Oil
        # ------------------------------------------------------------
        oil_cfg = VARIABLE_CONFIG["oil"]

        oil_sim_key, oil_sim = _get_existing_vector(
            summary_obj,
            keys_upper_map,
            well,
            oil_cfg["sim_rate"],
        )
        oil_hist_key, oil_hist = _get_existing_vector(
            summary_obj,
            keys_upper_map,
            well,
            oil_cfg["hist_rate"],
        )
        oil_sim_cum_key, oil_sim_cum = _get_existing_vector(
            summary_obj,
            keys_upper_map,
            well,
            oil_cfg["sim_cum"],
        )
        oil_hist_cum_key, oil_hist_cum = _get_existing_vector(
            summary_obj,
            keys_upper_map,
            well,
            oil_cfg["hist_cum"],
        )

        variable_results["oil"] = _evaluate_variable(
            "oil",
            dates,
            oil_sim,
            oil_hist,
            oil_sim_key,
            oil_hist_key,
            oil_sim_cum,
            oil_hist_cum,
            sim_signal=oil_sim,
            hist_signal=oil_hist,
            negligible_threshold=oil_cfg["negligible_threshold"],
        )

        variable_results["oil"]["sim_cum_key"] = oil_sim_cum_key
        variable_results["oil"]["hist_cum_key"] = oil_hist_cum_key

        # ------------------------------------------------------------
        # Water cut / water behaviour
        # ------------------------------------------------------------
        wct_cfg = VARIABLE_CONFIG["watercut"]

        water_sim_key, water_sim_rate = _get_existing_vector(
            summary_obj,
            keys_upper_map,
            well,
            wct_cfg["sim_water_rate"],
        )
        water_hist_key, water_hist_rate = _get_existing_vector(
            summary_obj,
            keys_upper_map,
            well,
            wct_cfg["hist_water_rate"],
        )

        wct_sim_key, wct_sim = _build_direct_or_calculated_series(
            summary_obj,
            keys_upper_map,
            well,
            direct_candidates=wct_cfg["sim_direct"],
            numerator_candidates=wct_cfg["sim_numerator"],
            denominator_candidates=wct_cfg["sim_denominator"],
        )
        wct_hist_key, wct_hist = _build_direct_or_calculated_series(
            summary_obj,
            keys_upper_map,
            well,
            direct_candidates=wct_cfg["hist_direct"],
            numerator_candidates=wct_cfg["hist_numerator"],
            denominator_candidates=wct_cfg["hist_denominator"],
        )

        variable_results["watercut"] = _evaluate_variable(
            "watercut",
            dates,
            wct_sim,
            wct_hist,
            wct_sim_key,
            wct_hist_key,
            sim_signal=water_sim_rate,
            hist_signal=water_hist_rate,
            negligible_threshold=wct_cfg["negligible_threshold"],
        )

        variable_results["watercut"]["sim_water_rate_key"] = water_sim_key
        variable_results["watercut"]["hist_water_rate_key"] = water_hist_key

        # ------------------------------------------------------------
        # GOR / gas behaviour
        # ------------------------------------------------------------
        gor_cfg = VARIABLE_CONFIG["gor"]

        gas_sim_key, gas_sim_rate = _get_existing_vector(
            summary_obj,
            keys_upper_map,
            well,
            gor_cfg["sim_gas_rate"],
        )
        gas_hist_key, gas_hist_rate = _get_existing_vector(
            summary_obj,
            keys_upper_map,
            well,
            gor_cfg["hist_gas_rate"],
        )

        gor_sim_key, gor_sim = _build_direct_or_calculated_series(
            summary_obj,
            keys_upper_map,
            well,
            direct_candidates=gor_cfg["sim_direct"],
            numerator_candidates=gor_cfg["sim_numerator"],
            denominator_candidates=gor_cfg["sim_denominator"],
        )
        gor_hist_key, gor_hist = _build_direct_or_calculated_series(
            summary_obj,
            keys_upper_map,
            well,
            direct_candidates=gor_cfg["hist_direct"],
            numerator_candidates=gor_cfg["hist_numerator"],
            denominator_candidates=gor_cfg["hist_denominator"],
        )

        variable_results["gor"] = _evaluate_variable(
            "gor",
            dates,
            gor_sim,
            gor_hist,
            gor_sim_key,
            gor_hist_key,
            sim_signal=gas_sim_rate,
            hist_signal=gas_hist_rate,
            negligible_threshold=gor_cfg["negligible_threshold"],
        )

        variable_results["gor"]["sim_gas_rate_key"] = gas_sim_key
        variable_results["gor"]["hist_gas_rate_key"] = gas_hist_key

        # ------------------------------------------------------------
        # BHP - optional.
        # If WBHPH does not exist, BHP becomes inactive and is excluded.
        # ------------------------------------------------------------
        bhp_cfg = VARIABLE_CONFIG["bhp"]

        bhp_sim_key, bhp_sim = _get_existing_vector(
            summary_obj,
            keys_upper_map,
            well,
            bhp_cfg["sim_direct"],
        )
        bhp_hist_key, bhp_hist = _get_existing_vector(
            summary_obj,
            keys_upper_map,
            well,
            bhp_cfg["hist_direct"],
        )

        variable_results["bhp"] = _evaluate_variable(
            "bhp",
            dates,
            bhp_sim,
            bhp_hist,
            bhp_sim_key,
            bhp_hist_key,
        )

        # ------------------------------------------------------------
        # Well-level score.
        # Only variables with numeric score enter the weighted score.
        # BHP inactive has score None and is therefore ignored.
        # ------------------------------------------------------------
        available_variable_scores = []
        available_variable_weights = []

        for variable_name, result in variable_results.items():
            score = result.get("score")

            if score is None:
                continue

            weight = VARIABLE_CONFIG[variable_name]["weight"]
            available_variable_scores.append(score)
            available_variable_weights.append(weight)

        if available_variable_scores:
            total_weight = sum(available_variable_weights)
            well_score = sum(
                score * weight
                for score, weight in zip(available_variable_scores, available_variable_weights)
            ) / total_weight
        else:
            well_score = None

        # Aggregation weight for model-level score.
        # Prefer observed cumulative oil if available.
        aggregation_weight = 1.0

        if oil_hist_cum:
            aggregation_weight = max(abs(oil_hist_cum[-1]), 1.0)
        elif oil_sim_cum:
            aggregation_weight = max(abs(oil_sim_cum[-1]), 1.0)

        hm_class = _well_class(well_score, variable_results)
        technical_flags = _technical_flags(variable_results)

        if well_score is not None:
            model_weighted_scores.append(well_score * aggregation_weight)
            model_weights.append(aggregation_weight)

        well_results[well] = {
            "hm_score": round(well_score, 2) if well_score is not None else None,
            "hm_class": hm_class,
            "technical_flags": technical_flags,
            "aggregation_weight": aggregation_weight,
            "variables": variable_results,
        }

    # ------------------------------------------------------------
    # Model-level score.
    # ------------------------------------------------------------
    if model_weighted_scores and model_weights:
        model_score = sum(model_weighted_scores) / sum(model_weights)
    else:
        model_score = None

    # ------------------------------------------------------------
    # Variable availability.
    # ------------------------------------------------------------
    variable_availability: Dict[str, Any] = {}

    for variable_name in VARIABLE_CONFIG:
        evaluated = [
            well
            for well, payload in well_results.items()
            if payload["variables"][variable_name]["status"] == "evaluated"
        ]
        inactive = [
            well
            for well, payload in well_results.items()
            if payload["variables"][variable_name]["status"] == "inactive"
        ]
        unavailable = [
            well
            for well, payload in well_results.items()
            if payload["variables"][variable_name]["status"] == "unavailable"
        ]

        variable_availability[variable_name] = {
            "evaluated_well_count": len(evaluated),
            "inactive_well_count": len(inactive),
            "unavailable_well_count": len(unavailable),
            "evaluated_wells": evaluated,
            "inactive_wells": inactive,
            "unavailable_wells": unavailable,
        }

    poor_wells = [
        well
        for well, payload in well_results.items()
        if payload["hm_class"] == "Poor"
    ]

    fair_wells = [
        well
        for well, payload in well_results.items()
        if payload["hm_class"] == "Fair"
    ]

    good_wells = [
        well
        for well, payload in well_results.items()
        if payload["hm_class"] == "Good"
    ]

    return {
        "source_type": "native_smspec_unsmry_history_match",
        "case_root": str(case_root),
        "date_count": len(dates),
        "first_date": str(dates[0]) if dates else None,
        "last_date": str(dates[-1]) if dates else None,
        "summary_vector_count": len(keys),
        "well_count": len(wells),
        "wells": wells,
        "model_hm_score": round(model_score, 2) if model_score is not None else None,
        "model_hm_class": _score_class(model_score),
        "variable_availability": variable_availability,
        "well_results": well_results,
        "summary": {
            "good_wells": good_wells,
            "fair_wells": fair_wells,
            "poor_wells": poor_wells,
            "good_count": len(good_wells),
            "fair_count": len(fair_wells),
            "poor_count": len(poor_wells),
        },
    }
