#!/usr/bin/env python3
"""F9 -- bandwidth_scaling_ladder: four descending bars, the fault-servicing
path benefits least from an 8x interconnect improvement.

Source: results/figures/f9_ladder_inputs.csv, built by
tools/analysis/build_f9_ladder_inputs.py from committed data:
  - PCIe: results/analysis/platform/{T4,5070TI}_PLATFORM_PROVENANCE.txt
  - wall-clock, dispatch-window: recovered per-batch/per-trial CSVs (both
    platforms), each cross-checked exactly against GATE_B7_5070TI_PHASEC.md's
    published figures by the builder script.
  - kernel-loop: 5070 Ti side recovered from
    results/phaseC/decomp_overhead_5070ti/overhead_times_interleaved.csv; the
    T4 side has NO committed or recoverable raw-trial source (see
    PROVENANCE_GAPS_F7_F9_F11.md and build_f9_ladder_inputs.py's own check),
    so this rung's RATIO cannot be independently verified here. It is shown
    at its reported value (PHASEC_REPORT.md/GATE_B7_5070TI_PHASEC.md's 4.45x)
    but rendered distinctly (hatched, muted) and labeled "reported, not
    independently verified" -- not silently presented as equally solid as
    the other three, which are exact recomputations from committed CSVs.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fig_common import COL_WIDTH_IN, PALETTE, GRID, INK_PRIMARY, INK_SECONDARY, INK_MUTED, savefig
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
LADDER_CSV = REPO / "results/figures/f9_ladder_inputs.csv"

RUNG_LABEL = {"pcie_raw_bandwidth": "PCIe raw\nbandwidth", "kernel_loop_time": "Kernel-loop\ntime",
              "process_wallclock": "Process\nwall-clock", "dispatch_window_sum": "Dispatch-window\nsum"}
RUNG_ORDER = ["pcie_raw_bandwidth", "kernel_loop_time", "process_wallclock", "dispatch_window_sum"]

# Reported value for the rung whose ratio can't be independently recomputed here
# (PHASEC_REPORT.md's T4 G3 median has no committed/recoverable raw-trial source).
KERNEL_LOOP_REPORTED_RATIO = 4.45


def main():
    rows = {}
    with open(LADDER_CSV) as f:
        for r in csv.DictReader(f):
            rows[r["rung"]] = r

    print("=== F9 ladder values (from f9_ladder_inputs.csv) ===")
    vals, verified = [], []
    for rung in RUNG_ORDER:
        r = rows[rung]
        if r["ratio"]:
            v = float(r["ratio"])
            vals.append(v)
            verified.append(True)
            print(f"  {rung}: ratio={v:.3f}x  VERIFIED (both sides committed) -- {r['source']}")
        else:
            vals.append(KERNEL_LOOP_REPORTED_RATIO)
            verified.append(False)
            print(f"  {rung}: ratio={KERNEL_LOOP_REPORTED_RATIO}x  REPORTED ONLY -- T4 side unrecoverable, "
                  f"see PROVENANCE_GAPS_F7_F9_F11.md")

    fig, ax = plt.subplots(figsize=(COL_WIDTH_IN, 3.0))
    x = np.arange(len(RUNG_ORDER))
    colors = [PALETTE[1], PALETTE[4], PALETTE[3], PALETTE[8]]
    for xi, rung, v, ok, color in zip(x, RUNG_ORDER, vals, verified, colors):
        if ok:
            ax.bar(xi, v, width=0.6, color=color, edgecolor=INK_PRIMARY, linewidth=0.6, zorder=3)
            ax.annotate(f"{v:.2f}x", (xi, v), xytext=(0, 4), textcoords="offset points",
                        ha="center", fontsize=7, fontweight="bold", color=INK_PRIMARY)
        else:
            ax.bar(xi, v, width=0.6, color=INK_MUTED, alpha=0.35, hatch="//",
                   edgecolor=INK_SECONDARY, linewidth=0.6, linestyle="--", zorder=3)
            ax.annotate(f"{v:.2f}x*", (xi, v), xytext=(0, 4), textcoords="offset points",
                        ha="center", fontsize=7, fontweight="bold", color=INK_SECONDARY)

    ax.set_xticks(x)
    ax.set_xticklabels([RUNG_LABEL[r] for r in RUNG_ORDER], fontsize=6.5)
    ax.set_ylabel("speedup, T4 -> RTX 5070 Ti (x)", fontsize=7)
    ax.set_ylim(0, 9.5)
    ax.grid(axis="y", linewidth=0.3, color=GRID)
    ax.set_title("The fault-servicing path (dispatch-window) speeds up least of anything measured",
                 fontsize=6.8, pad=8)
    ax.text(0.02, 0.97, "* kernel-loop: reported value, not independently\n"
            "  verified here (T4 raw trials unrecoverable)",
            transform=ax.transAxes, ha="left", va="top", fontsize=5.2, color=INK_MUTED, style="italic")

    fig.tight_layout()
    outstem = REPO / "results/figures/bandwidth_scaling_ladder"
    savefig(fig, str(outstem))
    print(f"\nwrote {outstem}.pdf / .png")


if __name__ == "__main__":
    main()
