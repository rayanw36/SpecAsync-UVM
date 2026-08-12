#!/usr/bin/env python3
"""F6 (new) -- pipelining_ceiling: end-to-end pipelining ceiling vs. each workload's
window-share of wall-clock, for the six workloads Task T3 gave a same-session paired
wall-clock denominator (results/analysis/GATE_T3_REPORT.md Section 3).

ceiling = (D1+D2 share of dispatch window) x (dispatch window / wall-clock).
This figure plots ceiling against the second factor (window/wall-clock) because that
is what drives the spread (0.20%-19.06%): D1+D2 share of the dispatch window itself
only ranges 27-36% across all six workloads, while window-share of wall-clock ranges
1.48%-57.17% -- GraphBFS-23 is compute-bound (barely any of its wall-clock is spent
fault-servicing at all), the stencil family is fault-bound.

The pre-existing standalone Stencil-24K figure (~7.86%, PIPELINING_CEILING.md) is
plotted with a distinct hollow marker and NOT connected to the six T3 points -- per
results/analysis/STENCIL_LABEL_COLLISION.md, its wall-clock denominator (Phase C's G3,
1645.6ms) uses a different timing convention (benchmark-internal kernel-loop time) than
the process-wall-clock convention T3's six points and every other figure use, so it is
not on a comparable basis and must not be visually blended with the six new points.
T3's Sweep-24K point (same N=24000 bench_stencil, process-wall-clock convention) is the
basis-consistent stand-in for "Stencil-24K" and is NOT specially marked -- it's exactly
the workload the retired figure was trying to represent, just measured correctly.

Source: results/analysis/GATE_T3_REPORT.md Section 3 (six workloads) and
results/analysis/PIPELINING_CEILING.md Section 4 (pre-existing Stencil-24K point).
Both are on-disk, already-published numbers -- this script transcribes them into a
plot, it does not recompute from raw telemetry (the raw T3 wall-clock CSV is
results/phaseC/paired_wallclock/t3_paired_times.csv; the decomp sums behind both
reports' D1+D2 shares are cited in-line in each report).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fig_common import (COL_WIDTH_IN, PALETTE, GRID, INK_PRIMARY, INK_SECONDARY,
                          INK_MUTED, savefig)
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]

# workload -> (D1+D2 share %, window/wall-clock %, ceiling %), from GATE_T3_REPORT.md S3
T3_DATA = {
    "Stencil-8K":   (33.34, 57.17, 19.06),
    "GraphBFS-23":  (13.36, 1.48, 0.20),
    "Sweep-4K":     (36.19, 33.65, 12.18),
    "Sweep-8K":     (34.47, 53.17, 18.33),
    "Sweep-16K":    (30.72, 53.36, 16.39),
    "Sweep-24K":    (26.99, 56.73, 15.31),
}
# pre-existing, different wall-clock basis (kernel-loop-time, not process wall-clock)
# -- PIPELINING_CEILING.md Section 4
LEGACY_STENCIL24K = (25.93, 30.32, 7.863)

FAMILY_COLOR = {
    "Stencil-8K": PALETTE[1], "Sweep-4K": PALETTE[1], "Sweep-8K": PALETTE[1],
    "Sweep-16K": PALETTE[1], "Sweep-24K": PALETTE[1], "GraphBFS-23": PALETTE[2],
}


def main():
    fig, ax = plt.subplots(figsize=(COL_WIDTH_IN, 3.1))

    for wl, (d1d2, winshare, ceiling) in T3_DATA.items():
        color = FAMILY_COLOR[wl]
        size = 30 + (d1d2 - 13) * 6  # marker area encodes D1+D2 share, secondary driver
        ax.scatter(winshare, ceiling, s=size, color=color, edgecolor=INK_PRIMARY,
                   linewidth=0.6, zorder=3)
        dx, dy = 1.5, 0.4
        if wl == "GraphBFS-23":
            dx, dy = 2.0, 0.6
        ax.annotate(wl, (winshare, ceiling), xytext=(winshare + dx, ceiling + dy),
                    fontsize=5.6, color=INK_SECONDARY)

    # legacy Stencil-24K point: hollow, dashed edge, distinct basis
    lw_d1d2, lw_win, lw_ceil = LEGACY_STENCIL24K
    ax.scatter(lw_win, lw_ceil, s=30 + (lw_d1d2 - 13) * 6, facecolor="none",
               edgecolor=INK_MUTED, linewidth=1.0, linestyle="--", zorder=3)
    ax.annotate("Stencil-24K\n(legacy G3 basis --\nnot comparable)",
                (lw_win, lw_ceil), xytext=(lw_win - 13, lw_ceil + 3.2),
                fontsize=5.2, color=INK_MUTED, style="italic",
                arrowprops=dict(arrowstyle="-", color=INK_MUTED, linewidth=0.5))

    ax.set_xlabel("dispatch window as share of wall-clock, %", fontsize=7)
    ax.set_ylabel("end-to-end pipelining ceiling, %", fontsize=7)
    ax.set_xlim(-2, 62)
    ax.set_ylim(-1, 22)
    ax.grid(linewidth=0.3, color=GRID)

    legend_handles = [
        plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=PALETTE[1],
                   markeredgecolor=INK_PRIMARY, markersize=6, label="Stencil family (T3)"),
        plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=PALETTE[2],
                   markeredgecolor=INK_PRIMARY, markersize=6, label="GraphBFS-23 (T3)"),
        plt.Line2D([0], [0], marker="o", color="none", markerfacecolor="none",
                   markeredgecolor=INK_MUTED, markersize=6, linestyle="--",
                   label="Stencil-24K, legacy basis"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", fontsize=5.6, frameon=False)
    ax.set_title("Marker area encodes D1+D2 share of dispatch window (27-36%, secondary "
                 "driver);\nwindow-share of wall-clock (x-axis) is the dominant driver "
                 "of the spread.",
                 fontsize=5.2, color=INK_MUTED, style="italic", pad=6)

    fig.tight_layout()
    outstem = REPO / "results/figures/pipelining_ceiling"
    savefig(fig, str(outstem))
    print(f"wrote {outstem}.pdf / .png")
    print("\nData plotted (workload, D1+D2 share%, window/wallclock%, ceiling%):")
    for wl, v in T3_DATA.items():
        print(f"  {wl:<14} {v}")
    print(f"  {'Stencil-24K (legacy)':<14} {LEGACY_STENCIL24K}")


if __name__ == "__main__":
    main()
