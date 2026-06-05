import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from app.streamlines_reader import (
    MODEL_DIR,
    find_streamline_file,
    try_read_binary_sln_arrays,
    normalize_ptr,
    detect_pointer_units,
    ptr_to_point_slice,
)
from app.streamline_geometric_mapper import get_well_points


GEOMETRIC_JSON = Path("artifacts/streamlines/geometric_streamline_connections.json")
OUTPUT_DIR = Path("artifacts/streamlines/maps")


def apply_transform(points: np.ndarray, scale: float, rotation: np.ndarray, translation: np.ndarray) -> np.ndarray:
    return scale * (points @ rotation.T) + translation


def load_geometric_payload() -> Dict[str, Any]:
    if not GEOMETRIC_JSON.exists():
        raise FileNotFoundError(
            f"Missing {GEOMETRIC_JSON}. Run: python -m app.streamline_geometric_mapper"
        )

    return json.loads(GEOMETRIC_JSON.read_text(encoding="utf-8"))


def extract_streamline_polylines(path: Path) -> List[np.ndarray]:
    data, endian = try_read_binary_sln_arrays(path)

    geom = data.get("GEOMETRY")
    ptr_raw = data.get("GEOMINDX")

    if geom is None or ptr_raw is None:
        raise ValueError("Missing GEOMETRY or GEOMINDX in streamline file.")

    if geom.size % 3 != 0:
        raise ValueError("GEOMETRY length is not divisible by 3.")

    xyz = geom.reshape((geom.size // 3, 3))
    n_points_total = xyz.shape[0]

    ptr = normalize_ptr(ptr_raw)
    pointer_units = detect_pointer_units(ptr, geom.size, n_points_total)
    n_streamlines = ptr.size - 1

    polylines = []

    for sid in range(n_streamlines):
        a = int(ptr[sid])
        b = int(ptr[sid + 1])

        p0, p1 = ptr_to_point_slice(a, b, pointer_units, n_points_total)

        if p1 <= p0:
            continue

        pts = xyz[p0:p1, 0:2].astype(float)

        if len(pts) >= 2:
            polylines.append(pts)

    return polylines


def get_alignment(payload: Dict[str, Any], snapshot: str):
    snap = payload["snapshots"].get(snapshot)

    if snap is None:
        raise ValueError(f"No snapshot '{snapshot}' found in {GEOMETRIC_JSON}")

    alignment = snap.get("alignment")

    if not alignment:
        raise ValueError(f"No alignment data found for snapshot '{snapshot}'")

    scale = float(alignment["scale"])
    rotation = np.asarray(alignment["rotation"], dtype=float)
    translation = np.asarray(alignment["translation"], dtype=float)

    return scale, rotation, translation, alignment


def well_style(well_payload: Dict[str, Any]):
    is_injector = bool(well_payload.get("is_injector"))
    is_producer = bool(well_payload.get("is_producer"))

    if is_injector and is_producer:
        return {
            "marker": "s",
            "color": "purple",
            "label": "mixed producer/injector",
            "size": 95,
        }

    if is_injector:
        return {
            "marker": "^",
            "color": "red",
            "label": "injector",
            "size": 105,
        }

    if is_producer:
        return {
            "marker": "o",
            "color": "black",
            "label": "producer",
            "size": 75,
        }

    return {
        "marker": "x",
        "color": "gray",
        "label": "unknown",
        "size": 75,
    }


def plot_snapshot(snapshot: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = load_geometric_payload()
    scale, rotation, translation, alignment = get_alignment(payload, snapshot)

    path = find_streamline_file(snapshot, model_dir=MODEL_DIR)

    if path is None:
        raise FileNotFoundError(f"No streamline file found for snapshot {snapshot}")

    polylines = extract_streamline_polylines(path)
    well_points = get_well_points()

    if not polylines:
        raise RuntimeError(f"No polylines extracted from {path}")

    fig, ax = plt.subplots(figsize=(15, 11))

    # Plot aligned streamlines.
    for pts in polylines:
        aligned = apply_transform(pts, scale, rotation, translation)

        ax.plot(
            aligned[:, 0],
            aligned[:, 1],
            linewidth=0.7,
            alpha=0.55,
            color="cornflowerblue",
        )

        # First and last points to see direction visually.
        ax.scatter(
            aligned[0, 0],
            aligned[0, 1],
            s=12,
            color="green",
            alpha=0.75,
            zorder=3,
        )
        ax.scatter(
            aligned[-1, 0],
            aligned[-1, 1],
            s=12,
            color="orange",
            alpha=0.75,
            zorder=3,
        )

    # Plot wells.
    used_labels = set()

    for well, wp in well_points.items():
        x = float(wp["x"])
        y = float(wp["y"])
        style = well_style(wp)

        label = style["label"] if style["label"] not in used_labels else None
        used_labels.add(style["label"])

        ax.scatter(
            x,
            y,
            s=style["size"],
            marker=style["marker"],
            color=style["color"],
            edgecolor="white",
            linewidth=0.8,
            zorder=5,
            label=label,
        )

        ax.text(
            x + 0.8,
            y + 0.8,
            well,
            fontsize=8,
            color=style["color"],
            zorder=6,
        )

    # Legend for streamline endpoints.
    ax.scatter([], [], s=20, color="green", label="streamline first point")
    ax.scatter([], [], s=20, color="orange", label="streamline last point")

    ax.set_title(
        f"Aligned Streamlines and Wells - {snapshot.upper()}\n"
        f"source={path.name} | mapped={payload['snapshots'][snapshot].get('raw_mapped_streamline_count')} / "
        f"{payload['snapshots'][snapshot].get('n_streamlines')} streamlines | "
        f"median endpoint distance={alignment.get('median_endpoint_distance'):.2f} cells | "
        f"p90={alignment.get('p90_endpoint_distance'):.2f} cells"
    )

    ax.set_xlabel("Grid I / aligned X")
    ax.set_ylabel("Grid J / aligned Y")
    ax.grid(True, alpha=0.25)
    ax.set_aspect("equal", adjustable="box")
    ax.invert_yaxis()
    ax.legend(loc="best", fontsize=8)

    plt.tight_layout()

    out = OUTPUT_DIR / f"streamlines_{snapshot}_aligned_with_wells.png"
    plt.savefig(out, dpi=220)
    plt.close()

    print(f"[OK] Saved {out}")


def plot_raw_snapshot(snapshot: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    path = find_streamline_file(snapshot, model_dir=MODEL_DIR)

    if path is None:
        raise FileNotFoundError(f"No streamline file found for snapshot {snapshot}")

    polylines = extract_streamline_polylines(path)

    fig, ax = plt.subplots(figsize=(15, 11))

    for pts in polylines:
        ax.plot(
            pts[:, 0],
            pts[:, 1],
            linewidth=0.7,
            alpha=0.55,
            color="steelblue",
        )
        ax.scatter(pts[0, 0], pts[0, 1], s=10, color="green", alpha=0.75)
        ax.scatter(pts[-1, 0], pts[-1, 1], s=10, color="orange", alpha=0.75)

    ax.set_title(f"Raw Streamlines Before Alignment - {snapshot.upper()} - {path.name}")
    ax.set_xlabel("Raw SLN X")
    ax.set_ylabel("Raw SLN Y")
    ax.grid(True, alpha=0.25)
    ax.set_aspect("equal", adjustable="box")

    ax.scatter([], [], s=20, color="green", label="first point")
    ax.scatter([], [], s=20, color="orange", label="last point")
    ax.legend(loc="best", fontsize=8)

    plt.tight_layout()

    out = OUTPUT_DIR / f"streamlines_{snapshot}_raw.png"
    plt.savefig(out, dpi=220)
    plt.close()

    print(f"[OK] Saved {out}")


def main() -> None:
    for snapshot in ["init", "eoh"]:
        plot_raw_snapshot(snapshot)
        plot_snapshot(snapshot)

    print("")
    print(f"Maps saved in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
