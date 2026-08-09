#!/usr/bin/env python3
"""F4 -- oversub_collapse: oracle hit rate collapses under memory oversubscription,
the opposite of the common assumption that pressure creates more prefetch opportunity.

Source: results/phaseB1/gate_d/{stencil,graphbfs,stencil_ovsub}/summary.txt -- all three
are POST-fix (module 81CDE275, corrected cursor + setarch -R), not ambiguous, and are not
in the exclusion manifest (only the pre-fix results/phaseB/phaseB_timing.csv /
phaseB_telemetry.csv Stencil_OvSub@28300_20_11264 p4 row is excluded -- this script does
not touch that file).
"""
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fig_common import (COL_WIDTH_IN, POLICY_STYLE, GRID, INK_PRIMARY, INK_SECONDARY,
                          INK_MUTED, savefig, load_exclusion_manifest)
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
REGIMES = [
    ("Stencil-24K\n(fits in VRAM)", REPO / "results/phaseB1/gate_d/stencil", "Stencil", "24000"),
    ("GraphBFS-23\n(fits in VRAM)", REPO / "results/phaseB1/gate_d/graphbfs", "GraphBFS", "23"),
    ("Stencil_OvSub\n(1.6x oversubscribed)", REPO / "results/phaseB1/gate_d/stencil_ovsub",
     "Stencil_OvSub", "28300_20_11264"),
]
POLICIES = ["p1", "p2", "p3", "p4"]
MANIFEST = load_exclusion_manifest()


def parse_summary(path):
    txt = path.read_text()
    hit = {}
    svc = {}
    for m in re.finditer(
        r"p(\d)(?:\(oracle\))?\s*==\n"
        r"\s*batches=(\d+) demand_faults=(\d+) enqueued=(\d+) hits=(\d+) drops=\d+\n"
        r"\s*hit_rate\(hits/enq\)=([\d.]+)\n"
        r"\s*service T4-T0 ns: median=(\d+) mean=(\d+)\n"
        r"\s*phase median ns: lock_acq=(\d+)\s+metadata\(T1->T2\)=(\d+)\s+residency\(T2->T3\)=(\d+)\n"
        r"\s*service median ns — hit-batches=([\w.]+) \(n=(\d+)\)\s+miss-batches=([\w.]+) \(n=(\d+)\)"
        r"(?:\n\s*per-hit service delta vs miss: ([+-][\d.]+)%.*)?",
        txt):
        (p, batches, faults, enq, hits, hr, med, mean, lock, meta, res,
         hit_svc, hit_n, miss_svc, miss_n, delta) = m.groups()
        hit[int(p)] = float(hr)
        svc[int(p)] = dict(hit_svc=hit_svc, hit_n=int(hit_n), miss_svc=miss_svc,
                            miss_n=int(miss_n), delta=delta)
    return hit, svc


def main():
    print("=== Panel data: hit rate by regime x policy (all POST-fix, results/phaseB1/gate_d/) ===")
    regime_hits = {}
    all_svc = {}
    for label, gdir, bench, size in REGIMES:
        hit, svc = parse_summary(gdir / "summary.txt")
        regime_hits[label] = hit
        all_svc[label] = svc
        gate_d_rows = [r for r in MANIFEST if "gate_d" in r["source_file"]
                       and r["benchmark"] in ("ALL", bench) and r["size"] in ("ALL", size)]
        print(f"  {label.splitlines()[0]}: manifest exclusion = "
              f"{'NONE (clean, post-fix, no matching manifest row)' if not gate_d_rows else gate_d_rows}")
        for p in POLICIES:
            pi = int(p[1])
            print(f"    {p}: hit_rate={hit.get(pi, float('nan')):.4f}")

    print("\n=== stdout-only: hit-batch vs miss-batch service time (selection-effect caveat) ===")
    print("Several cells have n<40 for the hit-batch group; large apparent per-hit "
          "'savings' at low n are selection effects (small coalesced batches are "
          "intrinsically fast, not sped up by the hit -- see GATE_D_report.md), NOT "
          "plotted as causal effects anywhere in this figure.")
    for label, svc in all_svc.items():
        print(f"  --- {label.splitlines()[0]} ---")
        for p in POLICIES:
            pi = int(p[1])
            if pi not in svc:
                continue
            d = svc[pi]
            flag = " <-- n<40, selection effect, see caveat above" if d["hit_n"] < 40 else ""
            print(f"    {p}: hit_svc={d['hit_svc']}ns (n={d['hit_n']})  "
                  f"miss_svc={d['miss_svc']}ns (n={d['miss_n']})  "
                  f"delta={d['delta']}%{flag}")

    # ---------------- figure ----------------
    fig, ax = plt.subplots(figsize=(COL_WIDTH_IN, 3.0))
    x = np.arange(len(REGIMES))
    width = 0.8 / len(POLICIES)
    for j, pname in enumerate(POLICIES):
        p = int(pname[1])
        style = POLICY_STYLE[pname]
        vals = [max(regime_hits[label].get(p, 0.0) * 100, 3e-4) for label, *_ in REGIMES]
        xs = x + (j - 1.5) * width
        ax.bar(xs, vals, width=width * 0.9, color=style["color"], hatch=style["hatch"],
               edgecolor=INK_PRIMARY, linewidth=0.5, label=style["label"])

    ax.set_yscale("log")
    ax.set_ylim(2e-4, 30)
    ax.set_xticks(x)
    ax.set_xticklabels([label for label, *_ in REGIMES], fontsize=6.3)
    ax.set_ylabel("oracle/heuristic hit rate, % (log)", fontsize=7)
    ax.grid(axis="y", which="major", linewidth=0.3, color=GRID)
    ax.legend(loc="lower right", fontsize=5.5, frameon=False, ncol=2)

    p4_vals = [regime_hits[label].get(4, 0.0) * 100 for label, *_ in REGIMES]
    p3_vals = [regime_hits[label].get(3, 0.0) * 100 for label, *_ in REGIMES]
    ax.annotate(f"oracle {p4_vals[2]:.2f}% vs p3 {p3_vals[2]:.2f}%:\nno longer separated",
                xy=(2 + 1.5 * width, p4_vals[2]), xytext=(0.9, 8.0),
                fontsize=5.8, ha="center", color=INK_PRIMARY,
                arrowprops=dict(arrowstyle="-", color=INK_SECONDARY, linewidth=0.6))

    fig.tight_layout()
    outstem = REPO / "results/figures/oversub_collapse"
    savefig(fig, str(outstem))
    print(f"\nwrote {outstem}.pdf / .png")


if __name__ == "__main__":
    main()
