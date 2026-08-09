#!/usr/bin/env python3
"""F2 -- decisive_c0c3: Gate 3 C0-C3 wall-time distributions (120 runs).

Source: results/phaseB2/gate3/gate3_times.csv (config,bench,run,wall_s), n=15 per
(config,bench). C0=stock prefetch ON, C1=prefetch OFF/no spec, C2=stride+depth=1,
C3=oracle+depth=1 (decisive upper bound). See results/phaseB2/GATE3_report.md,
DECISION.md.
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
CSV = REPO / "results/phaseB2/gate3/gate3_times.csv"
CONFIGS = ["C0", "C1", "C2", "C3"]
BENCHES = [("bench_stencil", "Stencil-24K"), ("bench_graph_bfs", "GraphBFS-23")]

# results/phaseB2/GATE3_report.md "C0 GraphBFS anomaly detail": runs 14-15 (61.51s,
# 59.78s) vs 55.3-55.7s for runs 1-13, attributed to EC2 scheduling noise. Marked
# visibly per the brief, not dropped.
KNOWN_OUTLIERS = {("C0", "bench_graph_bfs"): {14, 15}}

rng = np.random.default_rng(0)


def load():
    data = {}
    with open(CSV) as f:
        for r in csv.DictReader(f):
            key = (r["config"], r["bench"])
            data.setdefault(key, []).append((int(r["run"]), float(r["wall_s"])))
    return data


def main():
    data = load()

    print(f"{'config':<6} {'bench':<16} {'n':>3} {'median_s':>10} {'mean_s':>10} "
          f"{'std_s':>8} {'note':<30}")
    print("-" * 90)
    medians = {}
    for bench_key, bench_label in BENCHES:
        for cfg in CONFIGS:
            vals = [v for _, v in data[(cfg, bench_key)]]
            med = st.median(vals)
            medians[(cfg, bench_key)] = med
            note = ""
            outliers = KNOWN_OUTLIERS.get((cfg, bench_key))
            if outliers:
                clean = [v for run, v in data[(cfg, bench_key)] if run not in outliers]
                note = f"median w/o runs {sorted(outliers)}: {st.median(clean):.3f}s"
            print(f"{cfg:<6} {bench_label:<16} {len(vals):>3} {med:>10.3f} "
                  f"{st.mean(vals):>10.3f} {st.stdev(vals):>8.3f} {note:<30}")

    print("\n=== Decisive comparison: C3 vs C0 (median) ===")
    for bench_key, bench_label in BENCHES:
        c0 = medians[("C0", bench_key)]
        c3 = medians[("C3", bench_key)]
        delta = 100.0 * (c3 - c0) / c0
        print(f"  {bench_label}: C0={c0:.3f}s  C3={c3:.3f}s  Delta={delta:+.1f}%")

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
            outliers = KNOWN_OUTLIERS.get((cfg, bench_key), set())
            xj = positions[i] + rng.uniform(-0.12, 0.12, size=len(runs_vals))
            for (run, v), xx in zip(runs_vals, xj):
                is_out = run in outliers
                ax.scatter(xx, v, s=10 if not is_out else 20,
                           marker=style["marker"] if not is_out else "X",
                           facecolor=style["color"] if not is_out else "none",
                           edgecolor=INK_PRIMARY if not is_out else "#e34948",
                           linewidth=0.4 if not is_out else 1.1, alpha=0.85, zorder=4)

        c0 = medians[("C0", bench_key)]
        c3 = medians[("C3", bench_key)]
        delta = 100.0 * (c3 - c0) / c0
        ax.text(0.03, 0.95, f"C3 vs C0 (median): {delta:+.1f}%",
                transform=ax.transAxes, ha="left", va="top", fontsize=6.5,
                color=INK_PRIMARY)

        ax.set_xticks(positions)
        ax.set_xticklabels([CONFIG_STYLE[c]["label"] for c in CONFIGS], fontsize=6, rotation=12)
        ax.set_ylabel("wall time (s)")
        ax.set_title(bench_label, fontsize=7.5, pad=3)
        ax.grid(axis="y", linewidth=0.3, color=GRID)
        ax.margins(y=0.22)

    outlier_handle = plt.Line2D([], [], marker="X", linestyle="none", markerfacecolor="none",
                                 markeredgecolor="#e34948", markeredgewidth=1.1,
                                 label="known outlier, runs 14-15\n(EC2 scheduling noise)")
    fig.legend(handles=[outlier_handle], loc="upper center", bbox_to_anchor=(0.5, 1.045),
               fontsize=5.5, frameon=False)

    fig.tight_layout()
    outstem = REPO / "results/figures/decisive_c0c3"
    savefig(fig, str(outstem))
    print(f"\nwrote {outstem}.pdf / .png")


if __name__ == "__main__":
    main()
