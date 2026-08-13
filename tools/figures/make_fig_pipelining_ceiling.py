#!/usr/bin/env python3
"""F6 -- pipelining_ceiling: end-to-end pipelining ceiling vs. each workload's
window-share of wall-clock, for the six workloads Task T3 gave a same-session paired
wall-clock denominator (results/analysis/GATE_T3_REPORT.md Section 3).

ceiling = (D1+D2 share of dispatch window) x (dispatch window / wall-clock).

CORRECTED (2026-08-13, results/analysis/CEILING_BASIS_VERIFICATION.md): the window/wall
values below use the "span, median-of-trials" convention, not the originally-published
"sum(total_ns) summed across 5 trials / single-trial median wall-clock" convention. The
original convention had a units mismatch (numerator aggregated across 5 trials, denominator
from 1 trial) that inflated every ceiling by a factor close to 5x -- proven wrong, not just
suspected, by span-based window/wall-clock fractions exceeding 100% (a physical
impossibility) under the same formula on the T4's own data. See CEILING_BASIS_VERIFICATION.md
Sections 5-7 for the full derivation and the recommendation this figure now follows.

D1+D2 share of the dispatch window is unaffected by the correction (both its own numerator
and denominator use the same aggregation, so the units-mismatch factor cancels) -- only
window-share of wall-clock and the resulting ceiling moved.

The pre-existing standalone Stencil-24K figure (~7.86%, PIPELINING_CEILING.md) is plotted
with a distinct hollow marker and NOT connected to the six T3 points -- per
results/analysis/STENCIL_LABEL_COLLISION.md, its wall-clock denominator (Phase C's G3,
1645.6ms) uses a different timing convention (benchmark-internal kernel-loop time) than the
process-wall-clock convention T3's six points and every other figure use, so it is not on a
comparable basis and must not be visually blended with the six new points. This legacy point
is unaffected by the units-mismatch correction (its numerator was never multi-trial-
aggregated, CEILING_BASIS_VERIFICATION.md Section 5) and now sits close to the corrected T3
points despite the different convention -- independent corroboration, noted in the caption.

Source: results/analysis/GATE_T3_REPORT.md Section 3 correction note (six workloads,
corrected) and results/analysis/PIPELINING_CEILING.md Section 4 (pre-existing Stencil-24K
point, unaffected). Both are on-disk, already-published numbers -- this script transcribes
them into a plot, it does not recompute from raw telemetry (the raw T3 wall-clock CSV is
results/phaseC/paired_wallclock/t3_paired_times.csv; the decomp sums behind both reports'
D1+D2 shares are cited in-line in each report).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fig_common import (COL_WIDTH_IN, PALETTE, GRID, INK_PRIMARY, INK_SECONDARY,
                          INK_MUTED, savefig, load_exclusion_manifest, find_exclusion)
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]

# Consistency check, matching the convention every other fig script in this directory
# uses: confirm none of this figure's source rows are flagged in the exclusion manifest
# before trusting them. This figure transcribes summary numbers rather than reading a
# per-row CSV directly, so there's nothing to filter row-by-row -- this only verifies
# the source files themselves were never marked excluded wholesale.
MANIFEST = load_exclusion_manifest()
_T3_SOURCE = "results/phaseC/paired_wallclock/t3_paired_times.csv"
_excl = find_exclusion(MANIFEST, _T3_SOURCE)
if _excl:
    raise RuntimeError(f"{_T3_SOURCE} is flagged in the exclusion manifest: {_excl}")
print(f"exclusion_manifest.csv loaded ({len(MANIFEST)} rows); {_T3_SOURCE} not excluded.")

# workload -> (D1+D2 share %, window/wall-clock %, ceiling %).
# D1+D2 share: GATE_T3_REPORT.md S3 (unaffected by the units-mismatch correction).
# window/wall-clock and ceiling: CORRECTED, "span, median-of-trials" convention, per
# CEILING_BASIS_VERIFICATION.md Section 6 (T4 column).
T3_DATA = {
    "Stencil-8K":   (33.34, 21.27, 7.09),
    "GraphBFS-23":  (13.36, 0.96, 0.13),
    "Sweep-4K":     (36.19, 11.99, 4.34),
    "Sweep-8K":     (34.47, 21.43, 7.39),
    "Sweep-16K":    (30.72, 25.86, 7.94),
    "Sweep-24K":    (26.99, 27.52, 7.43),
}
# pre-existing, different wall-clock basis (kernel-loop-time, not process wall-clock);
# unaffected by the units-mismatch correction (PIPELINING_CEILING.md banner) --
# PIPELINING_CEILING.md Section 4
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
        # Per-label offsets: Stencil-8K/Sweep-8K and Sweep-16K/Sweep-24K sit almost on
        # top of each other under the corrected (much tighter) coordinate range, so
        # each pair is pushed in opposite directions rather than using one default.
        offsets = {
            "Stencil-8K":  (-6.0, -1.1),
            "Sweep-8K":    (-4.0, 1.0),
            "Sweep-16K":   (0.8, 0.4),
            "Sweep-24K":   (0.9, -0.9),
            "Sweep-4K":    (0.9, 0.2),
            "GraphBFS-23": (1.1, 0.3),
        }
        dx, dy = offsets[wl]
        ax.annotate(wl, (winshare, ceiling), xytext=(winshare + dx, ceiling + dy),
                    fontsize=5.6, color=INK_SECONDARY)

    # legacy Stencil-24K point: hollow, dashed edge, distinct basis
    lw_d1d2, lw_win, lw_ceil = LEGACY_STENCIL24K
    ax.scatter(lw_win, lw_ceil, s=30 + (lw_d1d2 - 13) * 6, facecolor="none",
               edgecolor=INK_MUTED, linewidth=1.0, linestyle="--", zorder=3)
    ax.annotate("Stencil-24K (legacy G3\nbasis -- not comparable,\nbut agrees closely)",
                (lw_win, lw_ceil), xytext=(lw_win - 15, lw_ceil - 3.4),
                fontsize=5.2, color=INK_MUTED, style="italic",
                arrowprops=dict(arrowstyle="-", color=INK_MUTED, linewidth=0.5))

    ax.set_xlabel("dispatch window as share of wall-clock, %", fontsize=7)
    ax.set_ylabel("end-to-end pipelining ceiling, %", fontsize=7)
    ax.set_xlim(-2, 36)
    ax.set_ylim(-0.5, 10)
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
    ax.set_title("Marker area encodes D1+D2 share of dispatch window (13-36%, secondary "
                 "driver);\nwindow-share of wall-clock (x-axis) is the dominant driver of "
                 "the spread. Corrected span/median-of-trials convention,\n"
                 "CEILING_BASIS_VERIFICATION.md -- supersedes the ~5x-inflated figures in "
                 "earlier drafts.",
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
