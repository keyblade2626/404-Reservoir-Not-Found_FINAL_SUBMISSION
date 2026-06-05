import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from app.history_match import build_history_match_kpis
from app.well_connections import get_well_spatial_summary


COLOR_MAP = {
    "Good": "green",
    "Fair": "gold",
    "Poor": "red",
    "Inactive": "lightgray",
    "Unavailable": "lightgray",
    None: "lightgray",
}


VARIABLE_LABELS = {
    "overall": "Overall History Match",
    "oil": "Oil History Match",
    "watercut": "Water Cut History Match",
    "gor": "GOR History Match",
    "bhp": "BHP History Match",
}


def get_class_and_score(well_payload: Dict[str, Any], variable: str) -> Dict[str, Any]:
    if variable == "overall":
        return {
            "class": well_payload.get("hm_class"),
            "score": well_payload.get("hm_score"),
            "status": "evaluated" if well_payload.get("hm_score") is not None else "unavailable",
        }

    result = well_payload.get("variables", {}).get(variable, {})

    return {
        "class": result.get("class"),
        "score": result.get("score"),
        "status": result.get("status"),
        "reason": result.get("reason"),
    }


def plot_hm_map(
    variable: str,
    hm_payload: Dict[str, Any],
    spatial_payload: Dict[str, Any],
    output_dir: Path,
    annotate: bool = True,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    well_results = hm_payload.get("well_results", {})
    spatial_wells = spatial_payload.get("wells", {})

    rows = []

    for well, well_payload in well_results.items():
        spatial = spatial_wells.get(well)

        if not spatial:
            continue

        x = spatial.get("representative_i")
        y = spatial.get("representative_j")

        if x is None or y is None:
            continue

        class_score = get_class_and_score(well_payload, variable)

        rows.append(
            {
                "well": well,
                "x": x,
                "y": y,
                "class": class_score.get("class"),
                "score": class_score.get("score"),
                "status": class_score.get("status"),
                "reason": class_score.get("reason"),
                "trajectory": spatial.get("trajectory_ij", []),
                "open_connection_count": spatial.get("open_connection_count"),
                "total_transmissibility": spatial.get("total_transmissibility"),
            }
        )

    if not rows:
        raise RuntimeError(f"No wells with both HM results and spatial connections for variable: {variable}")

    plt.figure(figsize=(11, 9))

    # Draw all completion cells as a pseudo-grid/trajectory context.
    for row in rows:
        trajectory = row.get("trajectory", [])

        if trajectory:
            xs = [p[0] for p in trajectory]
            ys = [p[1] for p in trajectory]
            plt.plot(xs, ys, linewidth=1, alpha=0.25)
            plt.scatter(xs, ys, s=6, alpha=0.18)

    # Draw representative well marker.
    for row in rows:
        color = COLOR_MAP.get(row["class"], "lightgray")

        plt.scatter(
            row["x"],
            row["y"],
            s=180,
            color=color,
            edgecolor="black",
            linewidth=0.8,
            zorder=5,
        )

        if annotate:
            score = row["score"]
            score_text = "NA" if score is None else f"{score:.1f}"
            plt.text(
                row["x"] + 0.8,
                row["y"] + 0.8,
                f"{row['well']}\n{score_text}",
                fontsize=8,
                zorder=6,
            )

    title = VARIABLE_LABELS.get(variable, variable)

    plt.title(f"{title} Map - Pseudo Grid I/J Location")
    plt.xlabel("Grid I index")
    plt.ylabel("Grid J index")
    plt.grid(True, alpha=0.25)

    # In many grid viewers J increases downward; invert only if you prefer Petrel-like view.
    plt.gca().invert_yaxis()

    legend_items = [
        ("Good", "green"),
        ("Fair", "gold"),
        ("Poor", "red"),
        ("Inactive/Unavailable", "lightgray"),
    ]

    for label, color in legend_items:
        plt.scatter([], [], color=color, edgecolor="black", label=label)

    plt.legend(loc="best")
    plt.tight_layout()

    output_path = output_dir / f"hm_map_{variable}.png"
    plt.savefig(output_path, dpi=180)
    plt.close()

    print(f"[OK] Saved {output_path}")

    return output_path


def create_all_maps(
    variables: List[str],
    output_dir: Path,
    annotate: bool = True,
) -> List[Path]:
    hm_payload = build_history_match_kpis()
    spatial_payload = get_well_spatial_summary()

    print(f"HM wells: {len(hm_payload.get('well_results', {}))}")
    print(f"Spatial wells: {spatial_payload.get('well_count')}")

    created = []

    for variable in variables:
        created.append(
            plot_hm_map(
                variable=variable,
                hm_payload=hm_payload,
                spatial_payload=spatial_payload,
                output_dir=output_dir,
                annotate=annotate,
            )
        )

    return created


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create 2D pseudo-grid maps of history-match quality using WELL_CONNECTIONS.IXF."
    )

    parser.add_argument(
        "--variables",
        nargs="*",
        default=["overall", "oil", "watercut", "gor", "bhp"],
        help="Variables to map: overall oil watercut gor bhp",
    )

    parser.add_argument(
        "--output-dir",
        default="artifacts/maps",
        help="Output directory for map PNG files.",
    )

    parser.add_argument(
        "--no-annotate",
        action="store_true",
        help="Disable well name annotations.",
    )

    args = parser.parse_args()

    created = create_all_maps(
        variables=args.variables,
        output_dir=Path(args.output_dir),
        annotate=not args.no_annotate,
    )

    print("")
    print(f"Created {len(created)} map files.")
    for path in created:
        print(path)


if __name__ == "__main__":
    main()
