"""Plate map rendering for the bench: PNG and PDF (matplotlib, Agg backend, no display needed)."""
from __future__ import annotations

import io
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from .model import N_COLS, N_ROWS, PlateSettings, Layout, ROW_LETTERS, well_row_col
from .naming import sample_name
from .validate import Report

TARGET_COLORS = ["#4C78A8", "#F58518", "#54A24B", "#B279A2", "#E45756", "#72B7B2", "#EECA3B", "#9D755D"]
NTC_GREY = "#B8B8B8"
EMPTY = "#F4F4F4"
ERROR_RED = "#D62728"


COLOR_BY = ("Target", "Sample", "Condition", "Dilution")


def _category(rec, color_by: str) -> str:
    if color_by == "Sample":
        return rec.sample_row
    if color_by == "Condition":
        return rec.condition
    if color_by == "Dilution":
        return rec.dilution
    return rec.target


def _color_for(rec, tindex, color_by: str = "Target", categories=None) -> str:
    if rec.is_ntc:
        return NTC_GREY
    if categories is None:
        return TARGET_COLORS[tindex.get(rec.target, 0) % len(TARGET_COLORS)]
    return TARGET_COLORS[categories.index(_category(rec, color_by)) % len(TARGET_COLORS)]


def draw_plate(records: list, targets: list, layout: Layout, settings: Optional[PlateSettings] = None,
               report: Optional[Report] = None, title: str = "384-well plate map", color_by: str = "Target"):
    """Return a matplotlib Figure of the plate. color_by: Target, Sample, Condition, or Dilution."""
    settings = settings or PlateSettings()
    if color_by not in COLOR_BY:
        raise ValueError(f"color_by must be one of {COLOR_BY}")
    tindex = {t.assay_id: i for i, t in enumerate(targets)}
    categories = None if color_by == "Target" else sorted({_category(r, color_by) for r in records if not r.is_ntc})
    by_gid = {r.gid: r for r in records}
    err_gids = set(report.error_gids) if report else set()
    fig, ax = plt.subplots(figsize=(14, 9.5), dpi=150)
    for r in range(N_ROWS):
        for c in range(1, N_COLS + 1):
            ax.add_patch(Rectangle((c - 1, N_ROWS - 1 - r), 0.9, 0.9, facecolor=EMPTY, edgecolor="#D0D0D0", lw=0.5))
    for gid, wells in layout.assignments.items():
        rec = by_gid.get(gid)
        if rec is None:
            continue
        color = _color_for(rec, tindex, color_by, categories)
        for w in wells:
            row, col = well_row_col(w)
            ax.add_patch(Rectangle((col - 1, N_ROWS - 1 - row), 0.9, 0.9, facecolor=color, edgecolor="none", alpha=0.85))
        rows = sorted({well_row_col(w)[0] for w in wells})
        cols = sorted({well_row_col(w)[1] for w in wells})
        x0, y0 = cols[0] - 1, N_ROWS - 1 - rows[-1]
        is_err = gid in err_gids
        ax.add_patch(Rectangle((x0 - 0.04, y0 - 0.04), (cols[-1] - cols[0] + 1) + 0.0, (rows[-1] - rows[0] + 1) + 0.0,
                               fill=False, edgecolor=ERROR_RED if is_err else "#222222", lw=2.2 if is_err else 1.0))
        ax.text(x0 + 0.45, y0 + 0.45 + (rows[-1] - rows[0]) * 0.0, rec.sample_row, ha="center", va="center",
                fontsize=6, color="white" if not rec.is_ntc else "#222222")
    ax.set_xlim(0, N_COLS)
    ax.set_ylim(0, N_ROWS)
    ax.set_xticks([i + 0.45 for i in range(N_COLS)])
    ax.set_xticklabels([str(i + 1) for i in range(N_COLS)], fontsize=7)
    ax.set_yticks([N_ROWS - 1 - i + 0.45 for i in range(N_ROWS)])
    ax.set_yticklabels(list(ROW_LETTERS), fontsize=7)
    ax.set_aspect("equal")
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    if categories is None:
        handles = [Rectangle((0, 0), 1, 1, color=TARGET_COLORS[i % len(TARGET_COLORS)], label=t.assay_id)
                   for i, t in enumerate(targets)]
    else:
        handles = [Rectangle((0, 0), 1, 1, color=TARGET_COLORS[i % len(TARGET_COLORS)], label=str(c))
                   for i, c in enumerate(categories)]
    handles += [Rectangle((0, 0), 1, 1, color=NTC_GREY, label="NTC"),
                Rectangle((0, 0), 1, 1, color=EMPTY, label="empty")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=8, frameon=False)
    used = len(layout.assignments)
    ax.set_title(f"{title}   |   {layout.strategy}   |   {used} groups, {3 * used} wells", fontsize=11, loc="left")
    fig.tight_layout()
    return fig


def plate_png(records, targets, layout, settings=None, report=None, color_by="Target") -> bytes:
    fig = draw_plate(records, targets, layout, settings, report, color_by=color_by)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    return buf.getvalue()


def plate_pdf(records, targets, layout, settings=None, report=None, color_by="Target") -> bytes:
    fig = draw_plate(records, targets, layout, settings, report, color_by=color_by)
    buf = io.BytesIO()
    fig.savefig(buf, format="pdf")
    plt.close(fig)
    return buf.getvalue()
