import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from app.history_match import _parse_date, build_history_match_kpis
from app.summary_importer import (
    DEFAULT_CASE_ROOT,
    _get_dates,
    _get_summary_keys,
    _get_vector_values,
    _load_resdata_summary,
)


PLOT_CONFIG = {
    "oil_rate": {
        "title": "Oil Production Rate",
        "sim_vector": "WOPR",
        "hist_vector": "WOPRH",
        "ylabel": "Oil rate",
        "filename_suffix": "oil_rate",
    },
    "water_rate": {
        "title": "Water Production Rate",
        "sim_vector": "WWPR",
        "hist_vector": "WWPRH",
        "ylabel": "Water rate",
        "filename_suffix": "water_rate",
    },
    "gas_rate": {
        "title": "Gas Production Rate",
        "sim_vector": "WGPR",
        "hist_vector": "WGPRH",
        "ylabel": "Gas rate",
        "filename_suffix": "gas_rate",
    },
}


def get_key(keys_upper_map: Dict[str, str], vector: str, well: str) -> Optional[str]:
    return keys_upper_map.get(f"{vector}:{well}".upper())


def get_values(summary_obj: Any, keys_upper_map: Dict[str, str], vector: str, well: str) -> Tuple[Optional[str], Optional[List[float]]]:
    key = get_key(keys_upper_map, vector, well)
    if not key:
        return None, None

    try:
        values = _get_vector_values(summary_obj, key)
        return key, values
    except Exception:
        return key, None


def build_x_axis(raw_dates: List[Any], n: int) -> Tuple[List[Any], str]:
    parsed = [_parse_date(d) for d in raw_dates[:n]]

    if all(d is not None for d in parsed) and parsed:
        return parsed, "date"

    return list(range(n)), "index"


def align_for_plot(dates: List[Any], sim_values: List[float], hist_values: List[float]) -> Tuple[List[Any], List[float], List[float], str]:
    n = min(len(dates), len(sim_values), len(hist_values))
    x, x_label = build_x_axis(dates, n)
    return x, sim_values[:n], hist_values[:n], x_label


def plot_variable(
    well: str,
    variable_name: str,
    config: Dict[str, str],
    dates: List[Any],
    summary_obj: Any,
    keys_upper_map: Dict[str, str],
    output_dir: Path,
) -> Optional[Path]:
    sim_key, sim_values = get_values(summary_obj, keys_upper_map, config["sim_vector"], well)
    hist_key, hist_values = get_values(summary_obj, keys_upper_map, config["hist_vector"], well)

    if sim_values is None or hist_values is None:
        print(
            f"[SKIP] {well} {variable_name}: missing vectors. "
            f"sim_key={sim_key}, hist_key={hist_key}"
        )
        return None

    x, sim, hist, x_label = align_for_plot(dates, sim_values, hist_values)

    if len(sim) < 2:
        print(f"[SKIP] {well} {variable_name}: not enough aligned points.")
        return None

    plt.figure(figsize=(11, 5))
    plt.plot(x, sim, label=f"Simulated ({sim_key})", linewidth=2)
    plt.plot(x, hist, label=f"Observed/History ({hist_key})", linewidth=2, linestyle="--")

    plt.title(f"{well} - {config['title']}")
    plt.xlabel("Date" if x_label == "date" else "Time index")
    plt.ylabel(config["ylabel"])
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    if x_label == "date":
        plt.xticks(rotation=30)

    output_path = output_dir / f"{well}_{config['filename_suffix']}.png"
    plt.savefig(output_path, dpi=160)
    plt.close()

    print(f"[OK] Saved {output_path}")
    return output_path


def plot_wells(wells: List[str], output_dir: Path, case_root: Path = DEFAULT_CASE_ROOT) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_obj = _load_resdata_summary(case_root)
    keys = _get_summary_keys(summary_obj)
    dates = _get_dates(summary_obj)
    keys_upper_map = {key.upper(): key for key in keys}

    created_files: List[Path] = []

    for well in wells:
        for variable_name, config in PLOT_CONFIG.items():
            path = plot_variable(
                well=well,
                variable_name=variable_name,
                config=config,
                dates=dates,
                summary_obj=summary_obj,
                keys_upper_map=keys_upper_map,
                output_dir=output_dir,
            )
            if path:
                created_files.append(path)

    return created_files


def choose_default_wells(max_wells: int = 3) -> List[str]:
    hm = build_history_match_kpis()

    # Prefer wells with lower HM score so the plots are diagnostically useful.
    ranked = []

    for well, payload in hm.get("well_results", {}).items():
        score = payload.get("hm_score")
        if score is not None:
            ranked.append((score, well))

    ranked.sort(key=lambda item: item[0])

    return [well for _, well in ranked[:max_wells]]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate simulated vs observed history-match plots from native SMSPEC/UNSMRY files."
    )

    parser.add_argument(
        "--wells",
        nargs="*",
        default=None,
        help="Well names to plot, e.g. --wells HW-10 HW-31 HW-24",
    )

    parser.add_argument(
        "--max-wells",
        type=int,
        default=3,
        help="Number of automatically selected wells if --wells is not provided.",
    )

    parser.add_argument(
        "--output-dir",
        default="artifacts/plots",
        help="Directory where PNG plots will be saved.",
    )

    args = parser.parse_args()

    if args.wells:
        wells = args.wells
    else:
        wells = choose_default_wells(args.max_wells)

    print(f"Selected wells: {wells}")

    created = plot_wells(
        wells=wells,
        output_dir=Path(args.output_dir),
    )

    print("")
    print(f"Created {len(created)} plot files.")
    for path in created:
        print(path)


if __name__ == "__main__":
    main()
