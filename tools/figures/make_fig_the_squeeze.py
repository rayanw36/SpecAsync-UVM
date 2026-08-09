#!/usr/bin/env python3
"""F3 -- the_squeeze: speculation only has room to work when the stock prefetcher
is off, but turning the prefetcher off costs more than speculation can recover.

Panel A (opportunity): hit rate on the deterministic adjacent-policy probe with the
stock prefetcher ON vs OFF (results/phaseB1/GATE_A_report.md: 0/256=0.0000 ON,
254/256=0.9922 OFF), against the real Phase B benchmark hit rates -- all measured
with the prefetcher ON (results/phaseB/phaseB_telemetry.csv; no benchmark run in this
repo captured hit-rate telemetry with the prefetcher OFF -- tests/gate3_favorable_run.sh
runs C1-C3 prefetch-off but only logs wall_s, not the specasync_log ring -- so that
cell is NOT FOUND rather than estimated).

Panel B (cost): wall-clock cost of disabling the prefetcher, C0 (prefetch ON) vs C1
(prefetch OFF, no speculation), from results/phaseB2/gate3/gate3_times.csv.
"""
import csv
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fig_common import (COL_WIDTH_IN, PALETTE, GRID, INK_PRIMARY, INK_SECONDARY,
                          INK_MUTED, savefig)
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
TELEM_CSV = REPO / "results/phaseB/phaseB_telemetry.csv"
GATE3_CSV = REPO / "results/phaseB2/gate3/gate3_times.csv"

# results/phaseB1/GATE_A_report.md, "Result -- the decisive comparison" table.
PROBE_ON_HITS, PROBE_ON_N = 0, 256
PROBE_OFF_HITS, PROBE_OFF_N = 254, 256

COLOR_ON = "#898781"
COLOR_OFF = PALETTE[1]


def load_real_hit_rates():
    rates = []
    with open(TELEM_CSV) as f:
        for r in csv.DictReader(f):
            rates.append(100.0 * float(r["hit_rate"]))
    return rates


def load_gate3_c0c1():
    data = {}
    with open(GATE3_CSV) as f:
        for r in csv.DictReader(f):
            if r["config"] in ("C0", "C1"):
                data.setdefault((r["config"], r["bench"]), []).append(float(r["wall_s"]))
    return {k: st.median(v) for k, v in data.items()}


def main():
    real_rates = load_real_hit_rates()
    probe_on_pct = 100.0 * PROBE_ON_HITS / PROBE_ON_N
    probe_off_pct = 100.0 * PROBE_OFF_HITS / PROBE_OFF_N

    print("=== Panel A: opportunity (hit rate) ===")
    print(f"Deterministic probe (adjacent, GATE_A_report.md): "
          f"prefetch ON = {PROBE_ON_HITS}/{PROBE_ON_N} = {probe_on_pct:.4f}%, "
          f"prefetch OFF = {PROBE_OFF_HITS}/{PROBE_OFF_N} = {probe_off_pct:.4f}%")
    print(f"Real Phase B benchmarks, prefetch ON, all policies/sizes (n={len(real_rates)}): "
          f"min={min(real_rates):.4f}% max={max(real_rates):.4f}% "
          f"median={st.median(real_rates):.4f}% mean={st.mean(real_rates):.4f}%")
    print("Real Phase B benchmarks, prefetch OFF: NOT FOUND -- gate3_favorable_run.sh "
          "runs C1/C2/C3 with prefetch off but records only wall_s, not the "
          "specasync_log hit-rate ring; no hit-rate telemetry with prefetch off "
          "exists on disk for any non-synthetic benchmark.")

    times = load_gate3_c0c1()
    print("\n=== Panel B: cost of disabling the prefetcher (Gate 3 C0 vs C1 medians) ===")
    benches = [("bench_stencil", "Stencil-24K"), ("bench_graph_bfs", "GraphBFS-23")]
    cost = {}
    for key, label in benches:
        c0 = times[("C0", key)]
        c1 = times[("C1", key)]
        delta = 100.0 * (c1 - c0) / c0
        ratio = c1 / c0
        cost[key] = (c0, c1, delta, ratio)
        print(f"  {label}: C0={c0:.3f}s  C1={c1:.3f}s  Delta={delta:+.1f}%  ({ratio:.2f}x)")

    # ---------------- figure ----------------
    fig, (axA, axB) = plt.subplots(2, 1, figsize=(COL_WIDTH_IN, 4.3),
                                    gridspec_kw=dict(height_ratios=[1.05, 1]))

    # Panel A: probe bars (log-safe: use plain axis since only 2 nonzero-ish values,
    # 0.0% must show as a visible zero-height bar, not vanish on a log axis).
    xs = [0, 1]
    probe_vals = [probe_on_pct, probe_off_pct]
    bars = axA.bar(xs, probe_vals, width=0.55,
                    color=[COLOR_ON, COLOR_OFF], edgecolor=INK_PRIMARY, linewidth=0.6,
                    hatch=[None, "//"])
    for x, v, n, h in zip(xs, probe_vals, (PROBE_ON_HITS, PROBE_OFF_HITS), (PROBE_ON_N,) * 2):
        va = "bottom" if v < 90 else "top"
        yoff = 6 if v < 90 else -3
        ytxt = v if v < 90 else v - 2
        axA.annotate(f"{v:.2f}%  ({n}/{h})", (x, ytxt), xytext=(0, yoff),
                     textcoords="offset points", ha="center", va=va, fontsize=6)
    axA.set_xticks(xs)
    axA.set_xticklabels(["prefetch ON", "prefetch OFF"], fontsize=6.5)
    axA.set_ylabel("hit rate, %\n(deterministic probe)", fontsize=6.5)
    axA.set_ylim(0, 112)
    axA.set_title("Opportunity: adjacent-policy hit rate", fontsize=7.2, pad=3)
    axA.grid(axis="y", linewidth=0.3, color=GRID)

    # inset strip: real Phase B benchmark hit rates (prefetch ON only -- no OFF data),
    # placed over the empty space above the near-zero ON bar.
    axA_ins = axA.inset_axes([0.08, 0.32, 0.38, 0.38])
    jitter = np.random.default_rng(1).uniform(-0.15, 0.15, size=len(real_rates))
    axA_ins.scatter(jitter, real_rates, s=4, color=COLOR_ON, alpha=0.55,
                     edgecolor="none")
    axA_ins.set_xlim(-0.5, 0.5)
    axA_ins.margins(y=0.2)
    axA_ins.set_xticks([])
    axA_ins.set_ylabel("%", fontsize=5, labelpad=1)
    axA_ins.tick_params(axis="y", labelsize=4.5, length=1.5)
    axA_ins.set_title("real benchmarks,\nprefetch ON (n=%d)" % len(real_rates),
                       fontsize=4.5, color=INK_SECONDARY, pad=1)
    for spine in axA_ins.spines.values():
        spine.set_linewidth(0.4)

    # Panel B: C0 vs C1 wall time, both benchmarks, own y each via twin axis pairing
    width = 0.32
    x0 = np.array([0, 1.0])
    b_c0 = axB.bar(x0 - width / 2, [cost[k][0] for k, _ in benches], width=width,
                    color=COLOR_ON, edgecolor=INK_PRIMARY, linewidth=0.6, label="C0 (prefetch ON)")
    b_c1 = axB.bar(x0 + width / 2, [cost[k][1] for k, _ in benches], width=width,
                    color=COLOR_OFF, hatch="//", edgecolor=INK_PRIMARY, linewidth=0.6,
                    label="C1 (prefetch OFF)")
    axB.set_yscale("log")
    for xi, (key, label) in zip(x0, benches):
        c0, c1, delta, ratio = cost[key]
        axB.annotate(f"{ratio:.2f}x", (xi, c1), xytext=(0, 4), textcoords="offset points",
                     ha="center", fontsize=6.5, color=INK_PRIMARY, fontweight="bold")
    axB.set_xticks(x0)
    axB.set_xticklabels([label for _, label in benches], fontsize=6.5)
    axB.set_ylabel("wall time, s (log)", fontsize=6.5)
    axB.set_title("Cost: disabling the prefetcher", fontsize=7.2, pad=3)
    axB.legend(loc="upper left", fontsize=5.5, frameon=False)
    axB.grid(axis="y", which="both", linewidth=0.3, color=GRID)
    axB.margins(y=0.3)

    fig.suptitle("", fontsize=1)  # no figure title per spec; keep tight_layout happy
    fig.tight_layout(rect=[0, 0, 1, 1])
    outstem = REPO / "results/figures/the_squeeze"
    savefig(fig, str(outstem))
    print(f"\nwrote {outstem}.pdf / .png")


if __name__ == "__main__":
    main()
