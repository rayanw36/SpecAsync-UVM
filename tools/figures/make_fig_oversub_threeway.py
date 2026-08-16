#!/usr/bin/env python3
"""F10 -- oversub_threeway: C0/C1/C3 median wall-clock vs iteration count under
oversubscription (N=48000, ~1.078x VRAM), iters in {1,3,5,10,20}.

C0 = stock (prefetch ON, policy=0, depth=0) -- the real baseline.
C1 = crippled baseline (prefetch OFF, policy=0, depth=0) -- NOT the practical
     baseline; included to show why comparing against it alone is misleading.
C3 = oracle speculation (prefetch OFF, policy=4, depth=1).

C3 beats C1 by up to 4.5x (the alarm OVERSUB_C3_VERIFICATION.md investigated),
but loses to the real baseline C0 by 1.76-4.47x at every iters value -- the
central resolution of that report. This figure is the visual form of that
table (OVERSUB_C3_VERIFICATION.md's C0-vs-C3 resolution section).

Source: results/analysis/gate_b9_oversub_mechanism/task2c_c0_threeway_times_MERGED.csv
(kept-phase rows only, n=5/arm/iters -- strictly interleaved C0,C1,C3, module
reloaded before every run, per GATE_B9_TASK2_REBUILD.md/OVERSUB_C3_VERIFICATION.md).
Medians and the C3-vs-C0 percentage are recomputed here directly from that raw
CSV, not transcribed from the committed aggregate CSV
(task2c_aggregate_comparison.csv) -- both should and do agree; the aggregate
CSV is not read by this script so there is no risk of silently drifting from it.
"""
import csv
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fig_common import (COL_WIDTH_IN, CONFIG_STYLE, GRID, INK_PRIMARY, INK_SECONDARY,
                          INK_MUTED, savefig, load_exclusion_manifest, find_exclusion)
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
CSV = REPO / "results/analysis/gate_b9_oversub_mechanism/task2c_c0_threeway_times_MERGED.csv"
CONFIGS = ["C0", "C1", "C3"]
ITERS = [1, 3, 5, 10, 20]

MANIFEST = load_exclusion_manifest()


def main():
    rel = str(CSV.relative_to(REPO))
    excl = find_exclusion(MANIFEST, rel)
    if excl:
        raise RuntimeError(f"{rel} is flagged in the exclusion manifest: {excl}")
    print(f"exclusion_manifest.csv loaded ({len(MANIFEST)} rows); {rel} not excluded.")

    data = {}
    with open(CSV) as f:
        for r in csv.DictReader(f):
            if r["phase"] != "kept":
                continue
            key = (r["config"], int(r["iters"]))
            data.setdefault(key, []).append(float(r["wall_s"]))

    print(f"\n{'config':<6} {'iters':>5} {'n':>3} {'median_s':>10} {'C3_vs_C0_pct':>14}")
    medians = {}
    for cfg in CONFIGS:
        for it in ITERS:
            vals = data[(cfg, it)]
            assert len(vals) == 5, f"{cfg}/{it}: expected n=5 kept reps, got {len(vals)}"
            medians[(cfg, it)] = st.median(vals)

    for it in ITERS:
        c0, c3 = medians[("C0", it)], medians[("C3", it)]
        pct = 100.0 * (c3 - c0) / c0
        for cfg in CONFIGS:
            tag = f"{pct:+.1f}%" if cfg == "C3" else ""
            print(f"{cfg:<6} {it:>5} {5:>3} {medians[(cfg, it)]:>10.3f} {tag:>14}")

    # ---------------- figure ----------------
    fig, ax = plt.subplots(figsize=(COL_WIDTH_IN, 3.2))
    for cfg in CONFIGS:
        style = CONFIG_STYLE[cfg]
        ys = [medians[(cfg, it)] for it in ITERS]
        ax.plot(ITERS, ys, marker=style["marker"], color=style["color"],
                markeredgecolor=INK_PRIMARY, markeredgewidth=0.4, markersize=5,
                linewidth=1.1, label=style["label"], zorder=3)

    ax.set_yscale("log")
    ax.set_xscale("log")
    ax.set_xticks(ITERS)
    ax.set_xticklabels([str(i) for i in ITERS])
    ax.set_xlabel("iterations")
    ax.set_ylabel("wall time, s (log)")
    ax.grid(which="major", linewidth=0.3, color=GRID)
    ax.grid(which="minor", linewidth=0.15, color=GRID)
    ax.legend(loc="upper left", fontsize=6.2, frameon=False)

    # Annotate C3-vs-C0 delta at each iters value (the resolution finding)
    for it in ITERS:
        c0, c3 = medians[("C0", it)], medians[("C3", it)]
        pct = 100.0 * (c3 - c0) / c0
        ax.annotate(f"{pct:+.0f}%", (it, c3), xytext=(0, 5), textcoords="offset points",
                    ha="center", fontsize=5.4, color=INK_SECONDARY)

    ax.text(0.02, 0.03,
            "C3 beats C1 by up to 4.5x, but loses to the real\nbaseline C0 by 1.76-4.47x at every iters value.",
            transform=ax.transAxes, ha="left", va="bottom", fontsize=5.6,
            color=INK_MUTED, style="italic")

    fig.tight_layout()
    outstem = REPO / "results/figures/oversub_threeway"
    savefig(fig, str(outstem))
    print(f"\nwrote {outstem}.pdf / .png")


if __name__ == "__main__":
    main()
