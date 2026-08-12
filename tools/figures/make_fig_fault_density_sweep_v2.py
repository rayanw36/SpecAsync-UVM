#!/usr/bin/env python3
"""F5v2 -- fault_density_sweep_v2: absolute per-batch dispatch-window cost (us) across
the Phase C fault-density sweep (4K/8K/16K/24K), decomposed into D1-D6 sub-phases.

Regenerated against Task T3's fresh same-session capture
(`results/analysis/GATE_T3_REPORT.md`), which corroborates the original per-workload
D1+D2 percentage share within 0.5-1.9pp on ~5x more batches per size (multi-trial: 5
trials/size vs the original single-run capture). Absolute per-batch medians run
2-18% lower here than the original `fault_density_sweep.pdf` (the original is
PRESERVED, not overwritten) -- consistent with normal run-to-run variance on this
kind of nanosecond-scale per-batch timing, not a change in the qualitative story (D4
dominance, D1/D2 share shrinking as N grows).

Source: results/phaseC/paired_wallclock/decomp_stencil_sweep_{4000,8000,16000,24000}_t3.csv,
generated from the raw T3 decomp ring dumps by tools/analysis/build_t3_sweep_csv.py.
"""
import csv
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fig_common import (COL_WIDTH_IN, PALETTE, GRID, INK_PRIMARY, INK_SECONDARY,
                          savefig, load_exclusion_manifest)
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
SWEEP_SIZES = ["4000", "8000", "16000", "24000"]
PHASES = ["d1_ns", "d2_ns", "d3_ns", "d4_ns", "d6_ns"]  # d5 is measured inside d4's hold
PHASE_LABELS = {"d1_ns": "D1 fault-buffer drain", "d2_ns": "D2 preprocess/sort/dedup",
                "d3_ns": "D3 lock wait", "d4_ns": "D4 lock hold (incl. D5 service)",
                "d6_ns": "D6 replay push"}
PHASE_COLOR = {"d1_ns": PALETTE[1], "d2_ns": PALETTE[2], "d3_ns": PALETTE[4],
               "d4_ns": PALETTE[8], "d6_ns": PALETTE[7]}
PHASE_HATCH = {"d1_ns": "//", "d2_ns": "\\\\", "d3_ns": "..", "d4_ns": None, "d6_ns": "xx"}

MANIFEST = load_exclusion_manifest()


def load(size):
    path = REPO / f"results/phaseC/paired_wallclock/decomp_stencil_sweep_{size}_t3.csv"
    rel = str(path.relative_to(REPO))
    excluded = [r for r in MANIFEST if r["source_file"] == rel]
    rows = list(csv.DictReader(open(path)))
    return rows, excluded, rel


def main():
    print("=== F5v2 source files (T3 fresh capture) and exclusion-manifest check ===")
    data = {}
    for size in SWEEP_SIZES:
        rows, excluded, rel = load(size)
        print(f"  {rel}: {len(rows)} records, manifest exclusions: "
              f"{excluded if excluded else 'none'}")
        data[size] = rows

    print("\n=== Median per-batch sub-phase cost (us) and recomputed %% share ===")
    print("(cross-check against results/analysis/GATE_T3_REPORT.md Section 2's D1+D2 share)")
    medians = {}
    for size in SWEEP_SIZES:
        rows = data[size]
        med_ns = {ph: st.median(float(r[ph]) for r in rows) for ph in PHASES}
        med_total = st.median(float(r["total_ns"]) for r in rows)
        med_svc = st.median(float(r["svc_ns"]) for r in rows)
        medians[size] = med_ns
        pct = {ph: 100.0 * med_ns[ph] / med_total for ph in PHASES}
        print(f"  N={size:>5}  n={len(rows):5}  total_median={med_total/1000:.1f}us  "
              f"svc_median={med_svc/1000:.1f}us")
        for ph in PHASES:
            print(f"      {PHASE_LABELS[ph]:<30} {med_ns[ph]/1000:7.2f}us  ({pct[ph]:5.1f}%)")

    # ---------------- figure: absolute stacked bars ----------------
    fig, ax = plt.subplots(figsize=(COL_WIDTH_IN, 3.0))
    x = np.arange(len(SWEEP_SIZES))
    bottom = np.zeros(len(SWEEP_SIZES))
    for ph in PHASES:
        vals = np.array([medians[s][ph] / 1000.0 for s in SWEEP_SIZES])
        ax.bar(x, vals, bottom=bottom, width=0.6, color=PHASE_COLOR[ph],
               hatch=PHASE_HATCH[ph], edgecolor=INK_PRIMARY, linewidth=0.5,
               label=PHASE_LABELS[ph])
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels([f"N={s}" for s in SWEEP_SIZES], fontsize=7)
    ax.set_ylabel("median per-batch cost, us (T3 fresh capture)", fontsize=7)
    ax.grid(axis="y", linewidth=0.3, color=GRID)
    ax.set_ylim(0, 150)
    ax.legend(loc="upper center", fontsize=5.3, frameon=False, ncol=1,
              bbox_to_anchor=(0.5, 1.0))
    for xi, size in zip(x, SWEEP_SIZES):
        ax.annotate(f"{bottom[xi]:.0f}us", (xi, bottom[xi]), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=6)

    fig.tight_layout()
    outstem = REPO / "results/figures/fault_density_sweep_v2"
    savefig(fig, str(outstem))
    print(f"\nwrote {outstem}.pdf / .png")


if __name__ == "__main__":
    main()
