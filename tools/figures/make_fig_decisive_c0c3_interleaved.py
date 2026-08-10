#!/usr/bin/env python3
"""F2 (interleaved) -- decisive_c0c3_interleaved: Gate 3 C0-C3 wall-time
distributions under the T1 interleaved rerun (176 runs, kept phase only).

Source: results/phaseB2/gate3_interleaved/gate3_interleaved_times.csv
(run_order_idx,timestamp_iso8601,config,bench,size,rep_in_cell,wall_s,srcversion,
dmesg_delta), n=20 per (config,bench) after discarding the pre-registered 2-rotation
warm-up. C0=stock prefetch ON, C1=prefetch OFF/no spec, C2=stride+depth=1,
C3=oracle+depth=1 (decisive upper bound). Unlike the original decisive_c0c3.pdf/.png
(preserved, not overwritten), every run here is preceded by a fresh module reload in
a strict C0,C1,C2,C3 rotation -- no config is blocked against any other. See
results/analysis/PREREGISTRATION.md and results/analysis/GATE_T1_REPORT.md.
"""
import csv
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fig_common import COL_WIDTH_IN, CONFIG_STYLE, GRID, INK_PRIMARY, INK_SECONDARY, savefig
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
CSV = REPO / "results/phaseB2/gate3_interleaved/gate3_interleaved_times.csv"
CONFIGS = ["C0", "C1", "C2", "C3"]
BENCHES = [("bench_stencil", "Stencil-24K"), ("bench_graph_bfs", "GraphBFS-23")]

# results/analysis/GATE_T1_REPORT.md Section 4: the C3/Stencil-24K bimodal split
# reproduces under strict interleaving (8/20 high) and is now proven NOT
# position-correlated (Spearman rho=-0.011, p=0.965) -- a genuine two-state
# mechanism, not a warm-up/contention artifact. Marked visibly, not dropped.
BIMODAL_HIGH_THRESHOLD = {("C3", "bench_stencil"): 16.0}

rng = np.random.default_rng(0)


def load():
    data = {}
    with open(CSV) as f:
        for r in csv.DictReader(f):
            if not r["rep_in_cell"].startswith("kept"):
                continue
            key = (r["config"], r["bench"])
            data.setdefault(key, []).append((int(r["run_order_idx"]), float(r["wall_s"])))
    return data


def main():
    data = load()

    print(f"{'config':<6} {'bench':<16} {'n':>3} {'median_s':>10} {'mean_s':>10} "
          f"{'std_s':>8}")
    print("-" * 70)
    medians = {}
    for bench_key, bench_label in BENCHES:
        for cfg in CONFIGS:
            vals = [v for _, v in data[(cfg, bench_key)]]
            med = st.median(vals)
            medians[(cfg, bench_key)] = med
            print(f"{cfg:<6} {bench_label:<16} {len(vals):>3} {med:>10.4f} "
                  f"{st.mean(vals):>10.4f} {st.stdev(vals):>8.4f}")

    print("\n=== Decisive comparison: C3 vs C1 (primary, per PREREGISTRATION.md) ===")
    for bench_key, bench_label in BENCHES:
        c1 = medians[("C1", bench_key)]
        c3 = medians[("C3", bench_key)]
        delta = 100.0 * (c3 - c1) / c1
        print(f"  {bench_label}: C1={c1:.4f}s  C3={c3:.4f}s  Delta={delta:+.2f}%")

    fig, axes = plt.subplots(2, 1, figsize=(COL_WIDTH_IN, 4.4))

    for ax, (bench_key, bench_label) in zip(axes, BENCHES):
        box_data = [[v for _, v in data[(cfg, bench_key)]] for cfg in CONFIGS]
        positions = np.arange(1, len(CONFIGS) + 1)
        bp = ax.boxplot(box_data, positions=positions, widths=0.5, showfliers=False,
                         patch_artist=True, medianprops=dict(color=INK_PRIMARY, linewidth=1.2),
                         boxprops=dict(linewidth=0.6), whiskerprops=dict(linewidth=0.6),
                         capprops=dict(linewidth=0.6))
        for patch, cfg in zip(bp["boxes"], CONFIGS):
            patch.set_facecolor(CONFIG_STYLE[cfg]["color"])
            patch.set_alpha(0.35)
            patch.set_edgecolor(INK_PRIMARY)

        for i, cfg in enumerate(CONFIGS):
            style = CONFIG_STYLE[cfg]
            runs_vals = data[(cfg, bench_key)]
            high_thresh = BIMODAL_HIGH_THRESHOLD.get((cfg, bench_key))
            xj = positions[i] + rng.uniform(-0.12, 0.12, size=len(runs_vals))
            for (run, v), xx in zip(runs_vals, xj):
                is_high_cluster = high_thresh is not None and v > high_thresh
                ax.scatter(xx, v, s=10 if not is_high_cluster else 20,
                           marker=style["marker"] if not is_high_cluster else "X",
                           facecolor=style["color"] if not is_high_cluster else "none",
                           edgecolor=INK_PRIMARY if not is_high_cluster else "#e34948",
                           linewidth=0.4 if not is_high_cluster else 1.1, alpha=0.85, zorder=4)

        c1 = medians[("C1", bench_key)]
        c3 = medians[("C3", bench_key)]
        delta = 100.0 * (c3 - c1) / c1
        ax.text(0.03, 0.95, f"C3 vs C1 (median): {delta:+.2f}%",
                transform=ax.transAxes, ha="left", va="top", fontsize=6.5,
                color=INK_PRIMARY)

        ax.set_xticks(positions)
        ax.set_xticklabels([CONFIG_STYLE[c]["label"] for c in CONFIGS], fontsize=6, rotation=12)
        ax.set_ylabel("wall time (s)")
        ax.set_title(f"{bench_label} (interleaved rerun)", fontsize=7.5, pad=3)
        ax.grid(axis="y", linewidth=0.3, color=GRID)
        ax.margins(y=0.22)

    bimodal_handle = plt.Line2D([], [], marker="X", linestyle="none", markerfacecolor="none",
                                 markeredgecolor="#e34948", markeredgewidth=1.1,
                                 label="C3/Stencil high cluster\n(reproduces, not position-correlated)")
    fig.legend(handles=[bimodal_handle], loc="upper center", bbox_to_anchor=(0.5, 1.045),
               fontsize=5.5, frameon=False)

    fig.tight_layout()
    outstem = REPO / "results/figures/decisive_c0c3_interleaved"
    savefig(fig, str(outstem))
    print(f"\nwrote {outstem}.pdf / .png (original decisive_c0c3.pdf/.png preserved, not overwritten)")


if __name__ == "__main__":
    main()
