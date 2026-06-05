import csv
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from app.history_match import build_history_match_kpis
from app.well_connections import get_well_spatial_summary


MODEL_DIR = Path("data/sample_model")
GRID_DIMENSIONS_FILE = MODEL_DIR / "grid_dimensions.json"
OUTPUT_DIR = Path("artifacts/correlation")

TRAN_FILES = {
    "tran_x": MODEL_DIR / "TRANX.GRDECL",
    "tran_y": MODEL_DIR / "TRANY.GRDECL",
    "tran_z": MODEL_DIR / "TRANZ.GRDECL",
}

TRAN_KEYWORDS = {
    "tran_x": "TRANX",
    "tran_y": "TRANY",
    "tran_z": "TRANZ",
}

TOKEN_PATTERN = re.compile(
    r"(?P<repeat>\d+)\*(?P<value>[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?)|"
    r"(?P<number>[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?)|"
    r"(?P<default_repeat>\d+)\*"
)

CLASS_COLORS = {
    "Good": "green",
    "Fair": "gold",
    "Poor": "red",
    "Inactive": "lightgray",
    "Unavailable": "lightgray",
    None: "lightgray",
}


def strip_comments(text: str) -> str:
    cleaned = []

    for line in text.splitlines():
        if "--" in line:
            line = line.split("--", 1)[0]
        cleaned.append(line)

    return "\n".join(cleaned)


def expand_grdecl_values(block: str) -> List[float]:
    values: List[float] = []

    for match in TOKEN_PATTERN.finditer(block):
        if match.group("repeat") is not None:
            repeat = int(match.group("repeat"))
            value = float(match.group("value"))
            values.extend([value] * repeat)

        elif match.group("number") is not None:
            values.append(float(match.group("number")))

        elif match.group("default_repeat") is not None:
            repeat = int(match.group("default_repeat"))
            values.extend([0.0] * repeat)

    return values


def read_grdecl_keyword(path: Path, keyword: str) -> List[float]:
    if not path.exists():
        raise FileNotFoundError(f"Missing GRDECL file: {path}")

    text = path.read_text(encoding="utf-8", errors="ignore")
    text = strip_comments(text)

    pattern = re.compile(
        rf"\b{re.escape(keyword)}\b(?P<body>.*?)/",
        re.IGNORECASE | re.DOTALL,
    )

    match = pattern.search(text)

    if not match:
        raise ValueError(f"Could not find keyword {keyword} in {path}")

    values = expand_grdecl_values(match.group("body"))

    if not values:
        raise ValueError(f"No values found for {keyword} in {path}")

    return values


def load_grid_dimensions() -> Dict[str, int]:
    data = json.loads(GRID_DIMENSIONS_FILE.read_text(encoding="utf-8-sig"))

    nx = int(data["nx"])
    ny = int(data["ny"])
    nz = int(data["nz"])

    return {
        "nx": nx,
        "ny": ny,
        "nz": nz,
        "cell_count": nx * ny * nz,
    }


def cell_to_index(i: int, j: int, k: int, dims: Dict[str, int]) -> int:
    nx = dims["nx"]
    ny = dims["ny"]
    nz = dims["nz"]

    if not (1 <= i <= nx and 1 <= j <= ny and 1 <= k <= nz):
        raise IndexError(
            f"Cell ({i},{j},{k}) outside grid dimensions ({nx},{ny},{nz})."
        )

    return (k - 1) * nx * ny + (j - 1) * nx + (i - 1)


def safe_value(values: List[float], i: int, j: int, k: int, dims: Dict[str, int]) -> Optional[float]:
    try:
        idx = cell_to_index(i, j, k, dims)
        return float(values[idx])
    except Exception:
        return None


def weighted_average(values: List[float], weights: Optional[List[float]] = None) -> Optional[float]:
    if not values:
        return None

    if not weights:
        return sum(values) / len(values)

    clean_weights = [max(float(w), 0.0) for w in weights]
    weight_sum = sum(clean_weights)

    if weight_sum <= 1e-12:
        return sum(values) / len(values)

    return sum(v * w for v, w in zip(values, clean_weights)) / weight_sum


def percentile_rank(value: Optional[float], population: List[float]) -> Optional[float]:
    if value is None or not population:
        return None

    count = sum(1 for v in population if v <= value)
    return round(100.0 * count / len(population), 2)


def pearson(x: List[float], y: List[float]) -> Optional[float]:
    clean = [
        (float(a), float(b))
        for a, b in zip(x, y)
        if a is not None and b is not None
    ]

    if len(clean) < 2:
        return None

    xs = [p[0] for p in clean]
    ys = [p[1] for p in clean]

    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)

    sx = math.sqrt(sum((v - mx) ** 2 for v in xs) / len(xs))
    sy = math.sqrt(sum((v - my) ** 2 for v in ys) / len(ys))

    if sx <= 1e-12 or sy <= 1e-12:
        return None

    cov = sum((a - mx) * (b - my) for a, b in clean) / len(clean)
    return cov / (sx * sy)


def load_transmissibility_properties() -> Dict[str, Any]:
    dims = load_grid_dimensions()

    properties = {}

    for name, path in TRAN_FILES.items():
        keyword = TRAN_KEYWORDS[name]
        values = read_grdecl_keyword(path, keyword)

        if len(values) != dims["cell_count"]:
            raise ValueError(
                f"{path.name} has {len(values)} values, but grid dimensions require "
                f"{dims['cell_count']} cells. Check nx, ny, nz or export format."
            )

        properties[name] = values

    return {
        "dims": dims,
        "properties": properties,
    }


def build_well_tran_context() -> Dict[str, Any]:
    loaded = load_transmissibility_properties()
    dims = loaded["dims"]
    tran = loaded["properties"]

    spatial = get_well_spatial_summary()
    hm = build_history_match_kpis()

    rows = []

    for well, spatial_payload in spatial["wells"].items():
        hm_payload = hm.get("well_results", {}).get(well)

        if not hm_payload:
            continue

        connections = [
            c for c in spatial_payload.get("connections", [])
            if str(c.get("status", "")).upper() == "OPEN"
        ]

        if not connections:
            connections = spatial_payload.get("connections", [])

        tran_x_values = []
        tran_y_values = []
        tran_z_values = []
        tran_h_values = []
        well_connection_trans_weights = []

        skipped_cells = 0

        for c in connections:
            i = int(c["i"])
            j = int(c["j"])
            k = int(c["k"])

            tx = safe_value(tran["tran_x"], i, j, k, dims)
            ty = safe_value(tran["tran_y"], i, j, k, dims)
            tz = safe_value(tran["tran_z"], i, j, k, dims)

            if tx is None or ty is None or tz is None:
                skipped_cells += 1
                continue

            tran_x_values.append(tx)
            tran_y_values.append(ty)
            tran_z_values.append(tz)

            # Horizontal transmissibility proxy.
            tran_h = math.sqrt(max(tx, 0.0) * max(ty, 0.0))
            tran_h_values.append(tran_h)

            well_connection_trans_weights.append(float(c.get("transmissibility") or 0.0))

        variables = hm_payload.get("variables", {})

        watercut = variables.get("watercut", {})
        oil = variables.get("oil", {})
        gor = variables.get("gor", {})
        bhp = variables.get("bhp", {})

        row = {
            "well": well,
            "i": spatial_payload.get("representative_i"),
            "j": spatial_payload.get("representative_j"),
            "open_connection_count": spatial_payload.get("open_connection_count"),
            "used_cell_count": len(tran_h_values),
            "skipped_cell_count": skipped_cells,

            "overall_hm_score": hm_payload.get("hm_score"),
            "overall_hm_class": hm_payload.get("hm_class"),

            "watercut_hm_score": watercut.get("score"),
            "watercut_hm_class": watercut.get("class"),
            "watercut_status": watercut.get("status"),

            "oil_hm_score": oil.get("score"),
            "oil_hm_class": oil.get("class"),
            "oil_status": oil.get("status"),

            "gor_hm_score": gor.get("score"),
            "gor_hm_class": gor.get("class"),
            "gor_status": gor.get("status"),

            "bhp_hm_score": bhp.get("score"),
            "bhp_hm_class": bhp.get("class"),
            "bhp_status": bhp.get("status"),

            "mean_tran_x": weighted_average(tran_x_values),
            "mean_tran_y": weighted_average(tran_y_values),
            "mean_tran_z": weighted_average(tran_z_values),
            "mean_tran_h": weighted_average(tran_h_values),

            "max_tran_x": max(tran_x_values) if tran_x_values else None,
            "max_tran_y": max(tran_y_values) if tran_y_values else None,
            "max_tran_z": max(tran_z_values) if tran_z_values else None,
            "max_tran_h": max(tran_h_values) if tran_h_values else None,

            "wellconn_total_transmissibility": spatial_payload.get("total_transmissibility"),
            "wellconn_mean_transmissibility": spatial_payload.get("mean_transmissibility"),
            "wellconn_max_transmissibility": spatial_payload.get("max_transmissibility"),

            "wellconn_total_kh": spatial_payload.get("total_permeability_thickness"),
            "wellconn_mean_kh": spatial_payload.get("mean_permeability_thickness"),

            "wellconn_weighted_tran_h": weighted_average(
                tran_h_values,
                well_connection_trans_weights,
            ),
        }

        rows.append(row)

    tran_h_population = [
        r["mean_tran_h"]
        for r in rows
        if r.get("mean_tran_h") is not None
    ]

    wellconn_trans_population = [
        r["wellconn_total_transmissibility"]
        for r in rows
        if r.get("wellconn_total_transmissibility") is not None
    ]

    for row in rows:
        row["mean_tran_h_percentile"] = percentile_rank(
            row.get("mean_tran_h"),
            tran_h_population,
        )
        row["wellconn_total_transmissibility_percentile"] = percentile_rank(
            row.get("wellconn_total_transmissibility"),
            wellconn_trans_population,
        )

    return {
        "grid_dimensions": dims,
        "rows": rows,
    }


def write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        raise RuntimeError("No rows to write.")

    fieldnames = list(rows[0].keys())

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def class_group_stats(rows: List[Dict[str, Any]], class_column: str = "watercut_hm_class") -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    for cls in ["Good", "Fair", "Poor", "Inactive", "Unavailable"]:
        group = [r for r in rows if r.get(class_column) == cls]

        def avg(field: str) -> Optional[float]:
            values = [
                r.get(field)
                for r in group
                if r.get(field) is not None
            ]
            if not values:
                return None
            return sum(float(v) for v in values) / len(values)

        result[cls] = {
            "count": len(group),
            "avg_watercut_hm_score": avg("watercut_hm_score"),
            "avg_mean_tran_h": avg("mean_tran_h"),
            "avg_max_tran_h": avg("max_tran_h"),
            "avg_wellconn_total_transmissibility": avg("wellconn_total_transmissibility"),
            "avg_wellconn_mean_transmissibility": avg("wellconn_mean_transmissibility"),
            "avg_wellconn_total_kh": avg("wellconn_total_kh"),
        }

    return result


def plot_scatter(
    rows: List[Dict[str, Any]],
    x_field: str,
    y_field: str,
    title: str,
    output_path: Path,
) -> None:
    plt.figure(figsize=(9, 6))

    xs_for_corr = []
    ys_for_corr = []

    for row in rows:
        x = row.get(x_field)
        y = row.get(y_field)

        if x is None or y is None:
            continue

        cls = row.get("watercut_hm_class")
        color = CLASS_COLORS.get(cls, "lightgray")

        plt.scatter(x, y, s=120, color=color, edgecolor="black", alpha=0.85)

        plt.text(
            x,
            y,
            row["well"],
            fontsize=8,
            ha="left",
            va="bottom",
        )

        xs_for_corr.append(float(x))
        ys_for_corr.append(float(y))

    corr = pearson(xs_for_corr, ys_for_corr)

    if corr is not None:
        title = f"{title}\nPearson correlation = {corr:.2f}"

    plt.title(title)
    plt.xlabel(x_field)
    plt.ylabel(y_field)
    plt.grid(True, alpha=0.3)

    for label, color in [
        ("Good", "green"),
        ("Fair", "gold"),
        ("Poor", "red"),
        ("Inactive/Unavailable", "lightgray"),
    ]:
        plt.scatter([], [], color=color, edgecolor="black", label=label)

    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()

    print(f"[OK] Saved {output_path}")


def build_tran_h_2d_map(dims: Dict[str, int], tran_x: List[float], tran_y: List[float]) -> List[List[float]]:
    nx = dims["nx"]
    ny = dims["ny"]
    nz = dims["nz"]

    sums = [[0.0 for _ in range(nx)] for _ in range(ny)]
    counts = [[0 for _ in range(nx)] for _ in range(ny)]

    for k in range(1, nz + 1):
        layer_offset = (k - 1) * nx * ny

        for j in range(1, ny + 1):
            row_offset = layer_offset + (j - 1) * nx

            for i in range(1, nx + 1):
                idx = row_offset + (i - 1)
                tx = tran_x[idx]
                ty = tran_y[idx]

                if tx > 0 and ty > 0:
                    th = math.sqrt(tx * ty)
                    sums[j - 1][i - 1] += th
                    counts[j - 1][i - 1] += 1

    result = []

    for j in range(ny):
        row = []

        for i in range(nx):
            if counts[j][i] > 0:
                value = sums[j][i] / counts[j][i]
                row.append(math.log10(value + 1e-30))
            else:
                row.append(None)

        result.append(row)

    # Replace None by a very low background value for plotting.
    finite_values = [
        v
        for row in result
        for v in row
        if v is not None
    ]

    low_value = min(finite_values) if finite_values else -30.0

    return [
        [v if v is not None else low_value for v in row]
        for row in result
    ]


def plot_tran_map(rows: List[Dict[str, Any]], output_path: Path) -> None:
    loaded = load_transmissibility_properties()
    dims = loaded["dims"]
    tran = loaded["properties"]

    background = build_tran_h_2d_map(
        dims=dims,
        tran_x=tran["tran_x"],
        tran_y=tran["tran_y"],
    )

    plt.figure(figsize=(11, 9))

    plt.imshow(
        background,
        origin="upper",
        extent=[1, dims["nx"], dims["ny"], 1],
        aspect="auto",
    )

    plt.colorbar(label="log10(mean positive TRAN_H over K)")

    for row in rows:
        i = row.get("i")
        j = row.get("j")

        if i is None or j is None:
            continue

        cls = row.get("watercut_hm_class")
        color = CLASS_COLORS.get(cls, "lightgray")

        size_base = row.get("wellconn_total_transmissibility") or 0.0
        size = 90 + min(260, math.log10(size_base + 1.0) * 65)

        plt.scatter(
            i,
            j,
            s=size,
            color=color,
            edgecolor="black",
            linewidth=0.8,
            alpha=0.9,
        )

        score = row.get("watercut_hm_score")
        score_text = "NA" if score is None else f"{float(score):.0f}"

        plt.text(
            i + 0.7,
            j + 0.7,
            f"{row['well']}\nWCT {score_text}",
            fontsize=8,
        )

    plt.title("TRAN_H background with Watercut History-Match Class Overlay")
    plt.xlabel("Grid I")
    plt.ylabel("Grid J")

    for label, color in [
        ("Good", "green"),
        ("Fair", "gold"),
        ("Poor", "red"),
        ("Inactive/Unavailable", "lightgray"),
    ]:
        plt.scatter([], [], color=color, edgecolor="black", label=label)

    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()

    print(f"[OK] Saved {output_path}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = build_well_tran_context()
    rows = payload["rows"]

    csv_path = OUTPUT_DIR / "well_tran_hm_correlation.csv"
    write_csv(rows, csv_path)
    print(f"[OK] Saved {csv_path}")

    stats = class_group_stats(rows)

    stats_path = OUTPUT_DIR / "watercut_class_tran_stats.json"
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"[OK] Saved {stats_path}")

    plot_scatter(
        rows,
        x_field="mean_tran_h",
        y_field="watercut_hm_score",
        title="Watercut HM Score vs Mean TRAN_H in Open Completion Cells",
        output_path=OUTPUT_DIR / "scatter_watercut_score_vs_mean_tran_h.png",
    )

    plot_scatter(
        rows,
        x_field="wellconn_total_transmissibility",
        y_field="watercut_hm_score",
        title="Watercut HM Score vs Well-Connection Total Transmissibility",
        output_path=OUTPUT_DIR / "scatter_watercut_score_vs_wellconn_total_trans.png",
    )

    plot_tran_map(
        rows,
        output_path=OUTPUT_DIR / "map_tran_h_background_watercut_hm.png",
    )

    print("")
    print("Correlation package created in:")
    print(OUTPUT_DIR)


if __name__ == "__main__":
    main()
