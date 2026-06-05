from pathlib import Path
from typing import Any
from datetime import datetime
import math

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patheffects as pe

from app.profile_series import get_profile_series


ARTIFACT_DIR = Path("artifacts/dashboard/profiles")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------
# DARK DASHBOARD THEME
# -----------------------------
FIG_BG = "#08111f"
AX_BG = "#0b1728"
GRID = "#304258"
TEXT = "#e8eef7"
SUBTLE = "#9fb0c7"
BORDER = "#223247"

SIM_COLOR = "#38bdf8"       # cyan
OBS_COLOR = "#fb923c"       # orange
OBS_MARKER = "#fdba74"


def _safe_name(value: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(value))


def _parse_datetime(value: Any):
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    # Common formats from summary dates
    candidates = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d-%b-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
    ]

    for fmt in candidates:
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            pass

    # Last fallback for ISO-ish strings
    try:
        return datetime.fromisoformat(text.replace("Z", ""))
    except Exception:
        return None


def _prepare_xy(x_values: list[Any], y_values: list[Any]):
    """
    Returns x, y, is_datetime.
    Negative y values are clipped to zero for display, because these rates/ratios
    should not appear below zero in the user-facing plot.
    """
    clean_x_raw = []
    clean_y = []

    for xv, yv in zip(x_values, y_values):
        try:
            if yv is None:
                continue

            y = float(yv)

            if math.isnan(y) or math.isinf(y):
                continue

            clean_x_raw.append(xv)
            clean_y.append(max(0.0, y))
        except Exception:
            continue

    if not clean_y:
        return [], [], False

    parsed_dates = [_parse_datetime(x) for x in clean_x_raw]
    valid_dates = [d for d in parsed_dates if d is not None]

    if len(valid_dates) >= max(1, int(0.7 * len(clean_y))):
        final_x = []
        final_y = []

        for d, y in zip(parsed_dates, clean_y):
            if d is not None:
                final_x.append(d)
                final_y.append(y)

        return final_x, final_y, True

    return list(range(1, len(clean_y) + 1)), clean_y, False


def _apply_dark_style(ax):
    ax.set_facecolor(AX_BG)

    ax.grid(True, color=GRID, alpha=0.34, linewidth=0.8)

    ax.tick_params(colors=SUBTLE, labelsize=9)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)

    for spine in ax.spines.values():
        spine.set_color(BORDER)
        spine.set_linewidth(1.0)


def _is_sim_trace(name: str) -> bool:
    n = str(name or "").lower()
    return "sim" in n


def _is_obs_trace(name: str) -> bool:
    n = str(name or "").lower()
    return "obs" in n or "hist" in n


def _sort_traces_for_visibility(traces: list[dict]):
    """
    Plot simulated first and observed second.
    Observed is dashed + markers and goes on top, so overlapping lines remain visible.
    """
    def key(t):
        name = t.get("name", "")
        if _is_sim_trace(name):
            return 0
        if _is_obs_trace(name):
            return 1
        return 2

    return sorted(traces, key=key)


def _plot_trace(ax, x, y, name: str, is_datetime: bool):
    name_lower = str(name or "").lower()

    if _is_sim_trace(name_lower):
        color = SIM_COLOR
        linestyle = "-"
        linewidth = 3.0
        marker = None
        zorder = 3
        alpha = 0.98
    elif _is_obs_trace(name_lower):
        color = OBS_COLOR
        linestyle = "--"
        linewidth = 2.6
        marker = "o"
        zorder = 4
        alpha = 0.98
    else:
        color = "#e879f9"
        linestyle = "-"
        linewidth = 2.3
        marker = None
        zorder = 2
        alpha = 0.95

    markevery = max(1, len(y) // 28) if marker else None

    line, = ax.plot(
        x,
        y,
        label=name,
        color=color,
        linestyle=linestyle,
        linewidth=linewidth,
        alpha=alpha,
        marker=marker,
        markersize=4.2 if marker else 0,
        markerfacecolor=OBS_MARKER if marker else color,
        markeredgecolor=FIG_BG if marker else color,
        markeredgewidth=0.7 if marker else 0,
        markevery=markevery,
        zorder=zorder,
        solid_capstyle="round",
    )

    # dark outline: improves visibility when lines overlap
    line.set_path_effects([
        pe.Stroke(linewidth=linewidth + 2.2, foreground=FIG_BG, alpha=0.92),
        pe.Normal(),
    ])

    return line


def _set_y_limits(ax, panel_title: str, all_y: list[float]):
    title = str(panel_title or "").lower()

    if "water cut" in title or "wct" in title:
        ax.set_ylim(0.0, 1.0)
        return

    if not all_y:
        ax.set_ylim(0.0, 1.0)
        return

    ymax = max(all_y)

    if ymax <= 0:
        ymax = 1.0
    else:
        ymax = ymax * 1.08

    ax.set_ylim(0.0, ymax)


def _draw_empty_plot(well: str, variable: str, message: str, output_path: Path):
    fig = plt.figure(figsize=(12.5, 5), facecolor=FIG_BG)
    ax = fig.add_subplot(111)
    _apply_dark_style(ax)

    ax.set_xlabel("Time", color=TEXT)
    ax.set_ylabel(variable.capitalize(), color=TEXT)
    ax.set_ylim(0, 1)

    # Only used for error/no-data cases.
    ax.text(
        0.5,
        0.5,
        message,
        color=SUBTLE,
        fontsize=11,
        ha="center",
        va="center",
        transform=ax.transAxes,
    )

    fig.tight_layout()
    fig.savefig(output_path, dpi=180, facecolor=FIG_BG, bbox_inches="tight")
    plt.close(fig)


def create_profile_plot(well: str, variable: str) -> dict:
    series = get_profile_series(well=well, variable=variable)

    safe_well = _safe_name(well)
    safe_var = _safe_name(variable)
    output_path = ARTIFACT_DIR / f"{safe_well}_{safe_var}_profile.png"

    if not isinstance(series, dict) or not series.get("ok", False):
        message = "Profile data not available."

        if isinstance(series, dict):
            message = series.get("message", message)

        _draw_empty_plot(well, variable, message, output_path)

        return {
            "ok": False,
            "well": well,
            "variable": variable,
            "image_path": str(output_path),
            "image_url": f"/artifacts/dashboard/profiles/{output_path.name}",
            "message": message,
            "sim_key": None,
            "hist_key": None,
        }

    panels = series.get("panels", [])
    sim_key = series.get("sim_key")
    hist_key = series.get("hist_key")

    if not panels:
        _draw_empty_plot(well, variable, "No panels available for this profile.", output_path)

        return {
            "ok": False,
            "well": well,
            "variable": variable,
            "image_path": str(output_path),
            "image_url": f"/artifacts/dashboard/profiles/{output_path.name}",
            "message": "No panels available for this profile.",
            "sim_key": sim_key,
            "hist_key": hist_key,
        }

    n_panels = len(panels)
    fig_height = max(4.8, 4.15 * n_panels)

    fig, axes = plt.subplots(
        n_panels,
        1,
        figsize=(13.5, fig_height),
        facecolor=FIG_BG,
        sharex=False,
    )

    if n_panels == 1:
        axes = [axes]

    legend_handles = []
    legend_labels = []

    for panel_idx, (ax, panel) in enumerate(zip(axes, panels)):
        _apply_dark_style(ax)

        y_title = panel.get("y_title", "")
        panel_title = panel.get("title", "")

        ax.set_ylabel(y_title if y_title else "", fontsize=10, color=TEXT)

        if panel_idx == n_panels - 1:
            ax.set_xlabel("Date / time step", fontsize=10, color=TEXT)

        traces = _sort_traces_for_visibility(panel.get("traces", []))

        panel_all_y = []
        any_datetime = False
        any_data = False

        for trace in traces:
            name = trace.get("name", "Series")
            x_raw = trace.get("x", [])
            y_raw = trace.get("y", [])

            x, y, is_datetime = _prepare_xy(x_raw, y_raw)

            if not y:
                continue

            any_data = True
            any_datetime = any_datetime or is_datetime
            panel_all_y.extend(y)

            line = _plot_trace(ax, x, y, name, is_datetime)

            if name not in legend_labels:
                legend_handles.append(line)
                legend_labels.append(name)

        if not any_data:
            # Only no-data message is allowed inside the plot, because otherwise panel is empty.
            ax.text(
                0.5,
                0.5,
                "No numeric data available",
                color=SUBTLE,
                fontsize=11,
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_ylim(0, 1)
            continue

        _set_y_limits(ax, panel_title, panel_all_y)

        if any_datetime:
            locator = mdates.AutoDateLocator(minticks=4, maxticks=7)
            formatter = mdates.ConciseDateFormatter(locator)
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(formatter)

    # Legend at the bottom, outside the plot area.
    if legend_handles:
        legend = fig.legend(
            legend_handles,
            legend_labels,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.012),
            ncol=min(4, len(legend_handles)),
            frameon=True,
            fontsize=9,
            facecolor="#0e1a2e",
            edgecolor=BORDER,
            labelcolor=TEXT,
        )

        for txt in legend.get_texts():
            txt.set_color(TEXT)

    fig.tight_layout(rect=[0.025, 0.075, 0.985, 0.985])
    fig.savefig(output_path, dpi=185, facecolor=FIG_BG, bbox_inches="tight")
    plt.close(fig)

    return {
        "ok": True,
        "well": well,
        "variable": variable,
        "image_path": str(output_path),
        "image_url": f"/artifacts/dashboard/profiles/{output_path.name}",
        "message": "Profile PNG generated successfully.",
        "sim_key": sim_key,
        "hist_key": hist_key,
    }
