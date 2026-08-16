#!/usr/bin/env python3
"""F7 -- dispatch_latency_race: the speculative worker's dispatch time against
the interval it must beat, both platforms, log-scale y.

Every number is recovered from raw telemetry that was previously markdown-only
(see results/figures/PROVENANCE_GAPS_F7_F9_F11.md for what was missing before
this recovery pass) and cross-checked against its published figure by the
recovery scripts before being trusted here:
  - Uncontended probe baseline + contended dispatch median/p90:
    tools/analysis/recover_worker_latency.py ->
    results/phaseB1/hit_probe_summary.csv,
    results/analysis/t_a1_worker/worker_latency_summary.csv
  - Corrected demand-fault inter-arrival times (T4 only -- no equivalent
    prefetch-OFF real-workload fault-rate sweep exists for the 5070 Ti, so no
    band is drawn there; not fabricated):
    tools/analysis/recover_t4_prefetch_off_hitrate.py ->
    results/gate3/telemetry/t4_prefetch_off_hitrate_recovered.csv
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fig_common import COL_WIDTH_IN, PAGE_WIDTH_IN, PALETTE, GRID, INK_PRIMARY, INK_SECONDARY, INK_MUTED, savefig
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
WORKER_SUMMARY = REPO / "results/analysis/t_a1_worker/worker_latency_summary.csv"
PROBE_SUMMARY = REPO / "results/phaseB1/hit_probe_summary.csv"
FAULT_RATE_CSV = REPO / "results/gate3/telemetry/t4_prefetch_off_hitrate_recovered.csv"

BENCH_LABEL = {"bench_stencil": "Stencil", "bench_graph_bfs": "GraphBFS"}
BENCH_COLOR = {"bench_stencil": PALETTE[1], "bench_graph_bfs": PALETTE[2]}
SCALE_LABEL = {"full_run": "full-size", "short_run": "short-run"}
CATS = [("full_run", "bench_stencil"), ("full_run", "bench_graph_bfs"),
        ("short_run", "bench_stencil"), ("short_run", "bench_graph_bfs")]


def load_worker_summary():
    d = {}
    with open(WORKER_SUMMARY) as f:
        for r in csv.DictReader(f):
            d[(r["platform"], r["scale"], r["bench"])] = r
    return d


def load_probe():
    d = {}
    with open(PROBE_SUMMARY) as f:
        for r in csv.DictReader(f):
            d.setdefault(r["platform"], []).append(r)
    return d


def load_fault_intervals():
    """T4 only. Returns {bench: interval_us} from the clean marginal reps."""
    intervals = {}
    with open(FAULT_RATE_CSV) as f:
        for r in csv.DictReader(f):
            if r["methodology"] != "corrected_marginal_clean" or not r["fault_rate_per_s"]:
                continue
            rate = float(r["fault_rate_per_s"])
            interval_us = 1e6 / rate
            intervals.setdefault(r["bench"], []).append(interval_us)
    # Stencil has only 1 clean rep; GraphBFS has 4 -- report min/max band per bench
    return {b: (min(v), max(v)) for b, v in intervals.items()}


def main():
    worker = load_worker_summary()
    probes = load_probe()
    intervals = load_fault_intervals()

    print("=== F7 source data ===")
    for k, r in worker.items():
        print(f"  worker {k}: dispatch_med={r['dispatch_median_us']}us dispatch_p90={r['dispatch_p90_us']}us n={r['n']}")
    for plat, plist in probes.items():
        for r in plist:
            print(f"  probe {plat}/{r['tag']}: dispatch_med={r['dispatch_median_us']}us n={r['n']}")
    for bench, (lo, hi) in intervals.items():
        print(f"  T4 fault inter-arrival {bench}: {lo:.3f}-{hi:.3f}us")

    fig, axes = plt.subplots(1, 2, figsize=(PAGE_WIDTH_IN, 3.4), sharey=True)

    for ax, platform in zip(axes, ["T4", "5070Ti"]):
        x = np.arange(len(CATS))
        for xi, (scale, bench) in zip(x, CATS):
            r = worker[(platform, scale, bench)]
            med, p90 = float(r["dispatch_median_us"]), float(r["dispatch_p90_us"])
            color = BENCH_COLOR[bench]
            ax.plot([xi, xi], [med, p90], color=color, linewidth=1.2, zorder=2)
            ax.scatter([xi], [med], marker="o", s=26, color=color, edgecolor=INK_PRIMARY,
                       linewidth=0.5, zorder=3, label="median" if xi == 0 else None)
            ax.scatter([xi], [p90], marker="^", s=26, facecolor="white", edgecolor=color,
                       linewidth=1.1, zorder=3, label="p90" if xi == 0 else None)

        # uncontended probe baseline: primary probe per platform (T4: original Gate A
        # run tied to the published ~5.6us/~0.35us figure; 5070Ti: Task 1's own probe)
        primary_tag = "prefoff_adj" if platform == "T4" else "task1_probe"
        probe_row = next(r for r in probes[platform] if r["tag"] == primary_tag)
        probe_med = float(probe_row["dispatch_median_us"])
        ax.axhline(probe_med, color=INK_MUTED, linewidth=1.0, linestyle="--", zorder=1)
        ax.annotate(f"uncontended probe\n{probe_med:.2f}us", (0.05, probe_med), xytext=(0, 4),
                    textcoords="offset points", fontsize=5.4, color=INK_SECONDARY, ha="left")

        # fault inter-arrival bands (T4 only) -- each band is a few % wide on a
        # 10^1-10^4 log axis, so draw as a solid line (thickened for visibility)
        # rather than a fill, with an in-axes label.
        if platform == "T4":
            label_y_offset = {"bench_stencil": -0.28, "bench_graph_bfs": 0.12}
            for bench, (lo, hi) in intervals.items():
                color = BENCH_COLOR[bench]
                mid = (lo + hi) / 2 if hi > lo else hi
                ax.axhline(mid, color=color, linewidth=1.6, alpha=0.75, zorder=1)
                ax.annotate(f"{BENCH_LABEL[bench]} demand-fault interval ~{mid:.2f}us",
                            (0.05, mid), xytext=(2, label_y_offset[bench] * 20),
                            textcoords="offset points", fontsize=5.0, color=color,
                            ha="left", va="center", fontweight="bold")

        ax.set_xlim(-0.55, len(CATS) - 0.45)
        ax.set_yscale("log")
        ax.set_xticks(x)
        ax.set_xticklabels([f"{SCALE_LABEL[s]}\n{BENCH_LABEL[b]}" for s, b in CATS], fontsize=6)
        ax.set_title(platform, fontsize=8)
        ax.grid(axis="y", which="major", linewidth=0.3, color=GRID)
        ax.grid(axis="y", which="minor", linewidth=0.12, color=GRID)

    axes[0].set_ylabel("dispatch latency (enqueue->dequeue), us (log)", fontsize=7)
    handles = [plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=INK_MUTED,
                          markeredgecolor=INK_PRIMARY, markersize=6, label="median"),
               plt.Line2D([0], [0], marker="^", color="none", markerfacecolor="white",
                          markeredgecolor=INK_MUTED, markersize=6, label="p90"),
               plt.Line2D([0], [0], color=INK_MUTED, linestyle="--", linewidth=1.0,
                          label="uncontended probe baseline")]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1.04), ncol=3,
               frameon=False, fontsize=6.2)
    fig.suptitle("", fontsize=1)  # keep tight_layout rect consistent
    fig.text(0.5, -0.02, "No 5070 Ti fault-inter-arrival band: no matching prefetch-OFF "
             "real-workload fault-rate sweep exists on that platform (not fabricated).",
             ha="center", fontsize=5.2, color=INK_MUTED, style="italic")

    fig.tight_layout(rect=[0, 0.02, 1, 0.94])
    outstem = REPO / "results/figures/dispatch_latency_race"
    savefig(fig, str(outstem))
    print(f"\nwrote {outstem}.pdf / .png")


if __name__ == "__main__":
    main()
