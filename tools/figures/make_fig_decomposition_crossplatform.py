#!/usr/bin/env python3
"""F8 -- decomposition_crossplatform: D1-D7 fault-servicing decomposition,
7 workloads x 2 platforms (T4, RTX 5070 Ti), grouped so each workload's two
platforms sit adjacent.

Stacked segments are D1, D2, D3, D4 (encompassing D5 -- D5 is measured
*inside* D4's lock-hold window, per PHASEC_REPORT.md's own definitions:
"D4 = va_space lock HOLD (encompasses D5)", "D5 = service_fault_batch_dispatch()
CPU time inside lock" -- so D5 is not a 7th additive segment, it is annotated
as a sub-share of D4), D6, and D7 (residual = total - (D1+D2+D3+D4+D6), per
PHASEC_REPORT.md's own D7 definition: "residual (scheduling jitter, prefetch,
enable/disable prefetch)"). All values are the ratio-of-medians convention
(median of each raw ns column independently, then median/median_total) --
verified to reproduce GATE_B7_5070TI_PHASEC.md Section 5's published D4%
figures exactly (57.3/76.9/52.1/54.7/56.7/57.2 for Stencil-24K/GraphBFS-23/
Sweep-4K/Sweep-8K/Sweep-16K/Sweep-24K) before trusting this script's own
recomputation.

Sources (all committed, git-tracked CSVs, no raw .bin/txt involved):
  T4:      results/phaseC/decomp_{stencil_8K,stencil_24K,graphbfs_23,
           stencil_sweep_{4000,8000,16000,24000}}.csv
  5070 Ti: results/phaseC/decomp_5070ti/decomp_{...same 7 filenames...}.csv
Both sets confirmed by PHASEC_REPORT.md's G1 table (T4 n's) and
GATE_B7_5070TI_PHASEC.md Section 5's table (5070 Ti n's) to be the exact
7-workload set both reports already establish as canonical -- row counts
match both tables exactly (checked programmatically below, not just by name).
"""
import csv
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fig_common import (PAGE_WIDTH_IN, PALETTE, GRID, INK_PRIMARY, INK_SECONDARY,
                          INK_MUTED, savefig, load_exclusion_manifest, find_exclusion)
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]

WORKLOADS = [
    ("Stencil-8K", "decomp_stencil_8K.csv"),
    ("Stencil-24K", "decomp_stencil_24K.csv"),
    ("GraphBFS-23", "decomp_graphbfs_23.csv"),
    ("Sweep-4K", "decomp_stencil_sweep_4000.csv"),
    ("Sweep-8K", "decomp_stencil_sweep_8000.csv"),
    ("Sweep-16K", "decomp_stencil_sweep_16000.csv"),
    ("Sweep-24K", "decomp_stencil_sweep_24000.csv"),
]
# Expected row counts (batches), cross-checked against both reports' own tables
# (PHASEC_REPORT.md G1 for T4; GATE_B7_5070TI_PHASEC.md Section 5 for 5070 Ti).
EXPECTED_N = {
    ("Stencil-8K", "T4"): 839, ("Stencil-8K", "5070Ti"): 866,
    ("Stencil-24K", "T4"): 5253, ("Stencil-24K", "5070Ti"): 6007,
    ("GraphBFS-23", "T4"): 473, ("GraphBFS-23", "5070Ti"): 455,
    ("Sweep-4K", "T4"): 259, ("Sweep-4K", "5070Ti"): 245,
    ("Sweep-8K", "T4"): 835, ("Sweep-8K", "5070Ti"): 845,
    ("Sweep-16K", "T4"): 2367, ("Sweep-16K", "5070Ti"): 2904,
    ("Sweep-24K", "T4"): 5207, ("Sweep-24K", "5070Ti"): 6047,
}
PLATFORMS = [("T4", REPO / "results/phaseC"), ("5070Ti", REPO / "results/phaseC/decomp_5070ti")]

PHASES = ["d1_ns", "d2_ns", "d3_ns", "d4_ns", "d6_ns"]  # d7 computed as residual; d5 annotated, not stacked
PHASE_LABELS = {"d1_ns": "D1 fault-buffer drain", "d2_ns": "D2 preprocess/sort/dedup",
                "d3_ns": "D3 lock wait", "d4_ns": "D4 lock hold (incl. D5 service)",
                "d6_ns": "D6 replay push", "d7": "D7 residual"}
PHASE_COLOR = {"d1_ns": PALETTE[1], "d2_ns": PALETTE[2], "d3_ns": PALETTE[4],
               "d4_ns": PALETTE[8], "d6_ns": PALETTE[7], "d7": INK_MUTED}
PHASE_HATCH = {"d1_ns": "//", "d2_ns": "\\\\", "d3_ns": "..", "d4_ns": None,
               "d6_ns": "xx", "d7": "oo"}

MANIFEST = load_exclusion_manifest()


def load(base, fname):
    path = base / fname
    rel = str(path.relative_to(REPO))
    excl = find_exclusion(MANIFEST, rel)
    rows = list(csv.DictReader(open(path)))
    return rows, excl, rel


def main():
    print("=== F8 source files and exclusion-manifest check ===")
    cells = {}
    for label, fname in WORKLOADS:
        for plat, base in PLATFORMS:
            rows, excl, rel = load(base, fname)
            if excl:
                raise RuntimeError(f"{rel} is flagged in the exclusion manifest: {excl} "
                                    f"-- this figure must not plot it silently.")
            n = len(rows)
            expected = EXPECTED_N[(label, plat)]
            status = "OK" if n == expected else f"MISMATCH (expected {expected})"
            print(f"  {rel}: n={n} [{plat}/{label}] {status}")
            assert n == expected, f"row count mismatch for {rel}: got {n}, expected {expected}"
            med = {k: st.median(float(r[k]) for r in rows)
                   for k in ("d1_ns", "d2_ns", "d3_ns", "d4_ns", "d5_ns", "d6_ns", "total_ns")}
            med["d7"] = med["total_ns"] - (med["d1_ns"] + med["d2_ns"] + med["d3_ns"]
                                            + med["d4_ns"] + med["d6_ns"])
            cells[(label, plat)] = med

    print("\n=== Median per-phase %% of total (ratio-of-medians) ===")
    print(f"{'workload':<12} {'plat':<7} {'total_us':>9} " +
          " ".join(f"{k[:2].upper():>6}%" for k in ["d1_ns", "d2_ns", "d3_ns", "d4_ns", "d6_ns", "d7"]) +
          f"  {'D5%':>6}")
    for label, _ in WORKLOADS:
        for plat, _ in PLATFORMS:
            m = cells[(label, plat)]
            tot = m["total_ns"]
            pct = {k: 100.0 * m[k] / tot for k in ("d1_ns", "d2_ns", "d3_ns", "d4_ns", "d6_ns", "d7")}
            pct_d5 = 100.0 * m["d5_ns"] / tot
            print(f"{label:<12} {plat:<7} {tot/1000:>9.2f} " +
                  " ".join(f"{pct[k]:>6.2f}" for k in ["d1_ns", "d2_ns", "d3_ns", "d4_ns", "d6_ns", "d7"]) +
                  f"  {pct_d5:>6.2f}")

    # ---------------- figure: grouped stacked bars (%), platforms adjacent per workload ----------------
    fig, ax = plt.subplots(figsize=(PAGE_WIDTH_IN, 3.6))
    n_wl = len(WORKLOADS)
    group_w = 0.8
    bar_w = group_w / 2
    x = np.arange(n_wl)

    for pi, (plat, _) in enumerate(PLATFORMS):
        xs = x + (pi - 0.5) * bar_w
        bottom = np.zeros(n_wl)
        for k in ("d1_ns", "d2_ns", "d3_ns", "d4_ns", "d6_ns", "d7"):
            vals = np.array([100.0 * cells[(label, plat)][k] / cells[(label, plat)]["total_ns"]
                              for label, _ in WORKLOADS])
            ax.bar(xs, vals, bottom=bottom, width=bar_w * 0.92, color=PHASE_COLOR[k],
                   hatch=PHASE_HATCH[k], edgecolor=INK_PRIMARY, linewidth=0.4,
                   label=PHASE_LABELS[k] if pi == 0 else None, zorder=3)
            bottom += vals
        # platform label under each sub-bar (pushed below the x-axis line, clear
        # of the workload-name row which is given extra tick padding below)
        for xi, label in zip(xs, [l for l, _ in WORKLOADS]):
            ax.annotate(plat, (xi, -6), ha="center", va="top", fontsize=4.6,
                        color=INK_SECONDARY, rotation=90, annotation_clip=False)

    # D4/D5 and D3 share annotations (the instructed annotation, per-workload,
    # placed above each platform pair rather than per-bar to avoid clutter)
    for wi, (label, _) in enumerate(WORKLOADS):
        m_t4 = cells[(label, "T4")]
        m_5070 = cells[(label, "5070Ti")]
        d4_t4 = 100.0 * m_t4["d4_ns"] / m_t4["total_ns"]
        d5_t4 = 100.0 * m_t4["d5_ns"] / m_t4["total_ns"]
        d4_5070 = 100.0 * m_5070["d4_ns"] / m_5070["total_ns"]
        d5_5070 = 100.0 * m_5070["d5_ns"] / m_5070["total_ns"]
        ax.annotate(f"D4/D5\n{d4_t4:.0f}/{d5_t4:.0f}%\nvs {d4_5070:.0f}/{d5_5070:.0f}%",
                    (x[wi], 102), ha="center", va="bottom", fontsize=4.0, color=INK_PRIMARY)

    ax.set_xticks(x)
    ax.set_xticklabels([label for label, _ in WORKLOADS], fontsize=6.5)
    ax.tick_params(axis="x", pad=16, length=0)
    ax.set_ylabel("share of total dispatch-window cost, %", fontsize=7)
    ax.set_ylim(0, 122)
    ax.set_xlim(-0.6, n_wl - 0.4)
    ax.grid(axis="y", linewidth=0.3, color=GRID)
    ax.set_title("D3 (lock wait) stays 0.04-0.15% on both platforms, at every workload -- "
                 "no lock contention anywhere",
                 fontsize=5.6, color=INK_MUTED, style="italic", pad=18)

    handles, labels_ = ax.get_legend_handles_labels()
    fig.legend(handles, labels_, loc="upper center", bbox_to_anchor=(0.5, 1.06),
               ncol=3, frameon=False, fontsize=5.8)

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    outstem = REPO / "results/figures/decomposition_crossplatform"
    savefig(fig, str(outstem))
    print(f"\nwrote {outstem}.pdf / .png")


if __name__ == "__main__":
    main()
