#!/usr/bin/env python3
"""F11 -- hitrate_vs_speedup: measured hit rate (log x) against wall-clock
delta vs the relevant baseline (y), across every configuration/platform this
project has both numbers for. The visual point: no relationship -- a
near-zero hit rate can mean a 0% wall-clock effect (cuFFT) or a 176% slowdown
(oversub vs C0), and a 99%+ hit rate (the deterministic probe) has no
wall-clock counterpart at all because it is a synthetic microbenchmark, not a
speedup claim.

Source: results/figures/f11_hitrate_vs_speedup_master.csv, built by
tools/analysis/build_f11_master_hitrate_table.py. Baseline is an explicit
column in that CSV (OVERSUB_C3_VERIFICATION.md's methodology note: no
comparison in this project may leave its baseline implicit) and is printed
in this script's stdout and drawn into each point's label -- never silently
assumed.

The probe rows have no wall-clock delta (baseline="n/a" -- a deterministic
positive-control microbenchmark has no comparable speedup claim) and are
drawn as a separate top marginal strip (x-position only), not forced onto a
fabricated y=0.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fig_common import PAGE_WIDTH_IN, PALETTE, GRID, INK_PRIMARY, INK_SECONDARY, INK_MUTED, savefig
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

REPO = Path(__file__).resolve().parents[2]
MASTER_CSV = REPO / "results/figures/f11_hitrate_vs_speedup_master.csv"

CONFIG_COLOR = {
    "probe_prefoff_adj": INK_MUTED, "probe_t4gate2": INK_MUTED, "probe_task1_probe": INK_MUTED,
    "cuFFT_p2_stride": PALETTE[3], "oracle_C3": PALETTE[1], "oversub_C3_iters20": PALETTE[8],
}
CONFIG_MARKER = {
    "probe_prefoff_adj": "|", "probe_t4gate2": "|", "probe_task1_probe": "|",
    "cuFFT_p2_stride": "D", "oracle_C3": "o", "oversub_C3_iters20": "s",
}


def main():
    rows = list(csv.DictReader(open(MASTER_CSV)))
    print("=== F11 master table (baseline column shown explicitly) ===")
    for r in rows:
        print(f"  {r['config']:<22} {r['platform']:<16} hit_rate={r['hit_rate_pct']:>9}% "
              f"delta={r['wall_clock_delta_pct'] or 'n/a':>10} baseline={r['baseline']}")

    with_wall = [r for r in rows if r["wall_clock_delta_pct"]]
    probe_only = [r for r in rows if not r["wall_clock_delta_pct"]]

    fig = plt.figure(figsize=(PAGE_WIDTH_IN * 0.72, 4.4))
    gs = fig.add_gridspec(2, 1, height_ratios=[0.18, 1], hspace=0.08)
    ax_top = fig.add_subplot(gs[0])
    ax = fig.add_subplot(gs[1], sharex=ax_top)

    # main scatter -- label offsets cycle to keep the y~0 cluster (cuFFT x2,
    # oracle x2) from overlapping
    LABEL_OFFSETS = [(8, 6), (8, -18), (-8, 14), (-8, -22), (8, 6), (8, -18)]
    for i, r in enumerate(with_wall):
        x = max(float(r["hit_rate_pct"]), 3e-4)
        y = float(r["wall_clock_delta_pct"])
        cfg = r["config"]
        color = CONFIG_COLOR[cfg]
        marker = CONFIG_MARKER[cfg]
        ax.scatter(x, y, s=55, marker=marker, color=color, edgecolor=INK_PRIMARY,
                   linewidth=0.6, zorder=3)
        short_cfg = {"cuFFT_p2_stride": "cuFFT p2", "oracle_C3": "oracle C3",
                     "oversub_C3_iters20": "oversub C3"}[cfg]
        tag = f"{short_cfg} ({r['platform'].split('_')[0]}, base={r['baseline'].split(' ')[0]})"
        dx, dy = LABEL_OFFSETS[i % len(LABEL_OFFSETS)]
        ha = "left" if dx > 0 else "right"
        ax.annotate(tag, (x, y), xytext=(dx, dy), textcoords="offset points",
                    fontsize=5.2, color=INK_SECONDARY, ha=ha, va="center")

    ax.axhline(0, color=INK_MUTED, linewidth=0.6, zorder=1)
    ax.set_xscale("log")
    ax.set_xlim(2e-4, 200)
    ax.set_ylabel("wall-clock delta vs stated baseline, % (positive = slower)", fontsize=7)
    ax.set_xlabel("measured hit rate, % (log)", fontsize=7)
    ax.grid(which="major", linewidth=0.3, color=GRID)
    ax.grid(which="minor", linewidth=0.12, color=GRID)
    ax.set_title("No relationship between hit rate and wall-clock effect", fontsize=7.5, pad=20)

    # top marginal strip: probe rows (no wall-clock comparison)
    for r in probe_only:
        x = float(r["hit_rate_pct"])
        ax_top.scatter(x, 0, s=60, marker="v", color=INK_MUTED, edgecolor=INK_PRIMARY,
                       linewidth=0.6, zorder=3)
    if probe_only:
        xs = [float(r["hit_rate_pct"]) for r in probe_only]
        ax_top.annotate(f"deterministic probes\n({min(xs):.2f}-{max(xs):.2f}%,\nno wall-clock baseline)",
                        (np.mean(xs), 0), xytext=(0, 2), textcoords="offset points",
                        fontsize=5.2, color=INK_MUTED, ha="center", va="bottom")
    ax_top.set_ylim(-0.5, 1.2)
    ax_top.set_yticks([])
    ax_top.spines["top"].set_visible(False)
    ax_top.spines["right"].set_visible(False)
    ax_top.spines["left"].set_visible(False)
    plt.setp(ax_top.get_xticklabels(), visible=False)
    ax_top.tick_params(axis="x", length=0)

    fig.tight_layout()
    outstem = REPO / "results/figures/hitrate_vs_speedup"
    savefig(fig, str(outstem))
    print(f"\nwrote {outstem}.pdf / .png")


if __name__ == "__main__":
    main()
