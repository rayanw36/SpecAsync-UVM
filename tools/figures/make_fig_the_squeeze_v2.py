#!/usr/bin/env python3
"""F3 v2 -- the_squeeze_v2: fills the "prefetch OFF, real benchmark" cell the
original the_squeeze.pdf/.png (preserved, not overwritten) explicitly marked
NOT FOUND.

Panel A (opportunity): hit rate on the deterministic adjacent-policy probe with the
stock prefetcher ON vs OFF (results/phaseB1/GATE_A_report.md), against real Phase B
benchmark hit rates prefetch-ON (results/phaseB/phaseB_telemetry.csv) AND, new in
this version, real benchmark hit rates prefetch-OFF, oracle policy
(results/gate3/telemetry/t4_prefetch_off_times.csv + its per-run specasync_log ring
dumps -- Task T4, results/analysis/GATE_T4_REPORT.md). The new data shows the
"opportunity" essentially does not exist for real workloads even with the
prefetcher off: 0.02-0.25% hit rate, four orders of magnitude below the
deterministic probe's 99.6%, because real fault rates outrun the async worker's
scheduling latency (a rate mismatch, not a prediction-accuracy failure -- the oracle
policy predicts perfectly by construction and still can't get credited).

Panel B (cost): unchanged from the original -- wall-clock cost of disabling the
prefetcher, C0 (prefetch ON) vs C1 (prefetch OFF, no speculation), from
results/phaseB2/gate3/gate3_times.csv (the original Gate 3 data; T1's interleaved
rerun of the same comparison is in decisive_c0c3_interleaved.pdf/.png).
"""
import csv
import struct
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fig_common import (COL_WIDTH_IN, PALETTE, GRID, INK_PRIMARY, INK_SECONDARY,
                          INK_MUTED, savefig, load_exclusion_manifest, find_exclusion)
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
TELEM_CSV = REPO / "results/phaseB/phaseB_telemetry.csv"
GATE3_CSV = REPO / "results/phaseB2/gate3/gate3_times.csv"
T4_CSV = REPO / "results/gate3/telemetry/t4_prefetch_off_times.csv"
T4_TELEM_DIR = REPO / "results/gate3/telemetry"

# results/phaseB1/GATE_A_report.md, "Result -- the decisive comparison" table.
PROBE_ON_HITS, PROBE_ON_N = 0, 256
PROBE_OFF_HITS, PROBE_OFF_N = 254, 256

COLOR_ON = "#898781"
COLOR_OFF = PALETTE[1]
COLOR_OFF_REAL = PALETTE[7]
MANIFEST = load_exclusion_manifest()

BFMT = "<6Q6I"
BSZ = struct.calcsize(BFMT)


def load_real_hit_rates_on():
    telem_rel = str(TELEM_CSV.relative_to(REPO))
    rates, excluded = [], []
    with open(TELEM_CSV) as f:
        for r in csv.DictReader(f):
            pname = f"p{r['policy']}"
            excl = find_exclusion(MANIFEST, telem_rel, r["benchmark"], r["size"], pname, "hit_rate")
            if excl:
                excluded.append((r["benchmark"], r["size"], pname, excl["exclusion_type"]))
                continue
            rates.append(100.0 * float(r["hit_rate"]))
    for bench, size, pname, kind in excluded:
        print(f"  excluded from real-benchmark ON hit-rate panel: {bench} {size} {pname} "
              f"(manifest: {kind})")
    return rates


def load_real_hit_rates_off():
    """Task T4: per-run specasync_log rings for C3 (oracle, prefetch OFF)."""
    per_run_rates = []
    with open(T4_CSV) as f:
        for r in csv.DictReader(f):
            if r["config"] != "C3":
                continue
            fp = T4_TELEM_DIR / f"{r['bench']}_{r['config']}_run{r['run_order_idx']}.bin"
            if not fp.exists():
                continue
            raw = fp.read_bytes()
            enq = hits = 0
            for i in range(len(raw) // BSZ):
                v = struct.unpack(BFMT, raw[i * BSZ:(i + 1) * BSZ])
                t0, t4 = v[1], v[5]
                if t0 == 0 or t4 < t0:
                    continue
                enq += v[7]
                hits += v[9]
            if enq:
                per_run_rates.append(100.0 * hits / enq)
    return per_run_rates


def load_gate3_c0c1():
    data = {}
    with open(GATE3_CSV) as f:
        for r in csv.DictReader(f):
            if r["config"] in ("C0", "C1"):
                data.setdefault((r["config"], r["bench"]), []).append(float(r["wall_s"]))
    return {k: st.median(v) for k, v in data.items()}


def main():
    real_rates_on = load_real_hit_rates_on()
    real_rates_off = load_real_hit_rates_off()
    probe_on_pct = 100.0 * PROBE_ON_HITS / PROBE_ON_N
    probe_off_pct = 100.0 * PROBE_OFF_HITS / PROBE_OFF_N

    print("=== Panel A: opportunity (hit rate) ===")
    print(f"Deterministic probe (adjacent, GATE_A_report.md): "
          f"prefetch ON = {probe_on_pct:.4f}%, prefetch OFF = {probe_off_pct:.4f}%")
    print(f"Real Phase B benchmarks, prefetch ON (n={len(real_rates_on)}): "
          f"median={st.median(real_rates_on):.4f}%")
    print(f"Real benchmarks, prefetch OFF, oracle policy, Task T4 (n={len(real_rates_off)} "
          f"per-run rates): median={st.median(real_rates_off):.4f}% "
          f"min={min(real_rates_off):.4f}% max={max(real_rates_off):.4f}%")
    print("  -- this cell was NOT FOUND in the original the_squeeze.pdf/.png; now filled.")

    times = load_gate3_c0c1()
    print("\n=== Panel B: cost of disabling the prefetcher (Gate 3 C0 vs C1 medians, unchanged) ===")
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
    fig, (axA, axB) = plt.subplots(2, 1, figsize=(COL_WIDTH_IN, 4.6),
                                    gridspec_kw=dict(height_ratios=[1.15, 1]))

    xs = [0, 1]
    probe_vals = [probe_on_pct, probe_off_pct]
    axA.bar(xs, probe_vals, width=0.55,
            color=[COLOR_ON, COLOR_OFF], edgecolor=INK_PRIMARY, linewidth=0.6,
            hatch=[None, "//"])
    # Both value labels sit above their own bar (not inset over it), so neither
    # collides with the opportunity insets placed low inside each bar's area.
    for x, v in zip(xs, probe_vals):
        axA.annotate(f"{v:.2f}%", (x, v), xytext=(0, 4),
                     textcoords="offset points", ha="center", va="bottom", fontsize=6)
    axA.set_xticks(xs)
    axA.set_xticklabels(["prefetch ON", "prefetch OFF"], fontsize=6.5)
    axA.set_ylabel("hit rate, %\n(deterministic probe)", fontsize=6.5)
    axA.set_ylim(0, 112)
    axA.set_title("Opportunity: adjacent-policy hit rate", fontsize=7.2, pad=3)
    axA.grid(axis="y", linewidth=0.3, color=GRID)

    # inset over the ON bar: real Phase B benchmarks, prefetch ON (unchanged from v1)
    axA_ins_on = axA.inset_axes([0.06, 0.10, 0.34, 0.34], zorder=5)
    axA_ins_on.set_facecolor("white")
    jitter_on = np.random.default_rng(1).uniform(-0.15, 0.15, size=len(real_rates_on))
    axA_ins_on.scatter(jitter_on, real_rates_on, s=4, color=COLOR_ON, alpha=0.55, edgecolor="none")
    axA_ins_on.set_xlim(-0.5, 0.5)
    axA_ins_on.margins(y=0.2)
    axA_ins_on.set_xticks([])
    axA_ins_on.set_ylabel("%", fontsize=5, labelpad=1)
    axA_ins_on.tick_params(axis="y", labelsize=4.5, length=1.5)
    axA_ins_on.set_title("real, prefetch ON\n(n=%d)" % len(real_rates_on),
                          fontsize=4.5, color=INK_SECONDARY, pad=1)
    for spine in axA_ins_on.spines.values():
        spine.set_linewidth(0.4)

    # NEW inset over the OFF bar: real benchmarks, prefetch OFF, oracle (Task T4).
    # Placed low and given an opaque white facecolor + high zorder so it reads
    # cleanly against the tall, densely-hatched OFF bar instead of colliding with
    # the "99.22%" probe-value annotation near the bar's top.
    axA_ins_off = axA.inset_axes([0.58, 0.10, 0.36, 0.34], zorder=5)
    axA_ins_off.set_facecolor("white")
    jitter_off = np.random.default_rng(2).uniform(-0.15, 0.15, size=len(real_rates_off))
    axA_ins_off.scatter(jitter_off, real_rates_off, s=4, color=COLOR_OFF_REAL, alpha=0.55,
                         edgecolor="none")
    axA_ins_off.set_xlim(-0.5, 0.5)
    axA_ins_off.set_ylim(0, max(real_rates_off) * 1.3 if real_rates_off else 1)
    axA_ins_off.set_xticks([])
    axA_ins_off.set_ylabel("%", fontsize=5, labelpad=1)
    axA_ins_off.tick_params(axis="y", labelsize=4.5, length=1.5)
    axA_ins_off.set_title("real, prefetch OFF,\noracle (n=%d, Task T4)" % len(real_rates_off),
                           fontsize=4.5, color=INK_SECONDARY, pad=1)
    for spine in axA_ins_off.spines.values():
        spine.set_linewidth(0.4)

    # Panel B: unchanged from v1
    width = 0.32
    x0 = np.array([0, 1.0])
    axB.bar(x0 - width / 2, [cost[k][0] for k, _ in benches], width=width,
            color=COLOR_ON, edgecolor=INK_PRIMARY, linewidth=0.6, label="C0 (prefetch ON)")
    axB.bar(x0 + width / 2, [cost[k][1] for k, _ in benches], width=width,
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

    fig.tight_layout(rect=[0, 0, 1, 1])
    outstem = REPO / "results/figures/the_squeeze_v2"
    savefig(fig, str(outstem))
    print(f"\nwrote {outstem}.pdf / .png (original the_squeeze.pdf/.png preserved, not overwritten)")


if __name__ == "__main__":
    main()
