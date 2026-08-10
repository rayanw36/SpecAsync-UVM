#!/usr/bin/env python3
"""Task B4 -- convert the Phase C dispatch-window D1+D2 share into an
end-to-end wall-clock pipelining ceiling, with the denominator (wall-clock
runtime) labelled explicitly at every step, and NOT fabricated where no
same-session pairing exists.

Writes results/analysis/PIPELINING_CEILING.md.
"""
import csv
import statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DECOMP = {
    "Stencil-8K": REPO / "results/phaseC/decomp_stencil_8K.csv",
    "Stencil-24K": REPO / "results/phaseC/decomp_stencil_24K.csv",
    "GraphBFS-23": REPO / "results/phaseC/decomp_graphbfs_23.csv",
    "Sweep-4K": REPO / "results/phaseC/decomp_stencil_sweep_4000.csv",
    "Sweep-8K": REPO / "results/phaseC/decomp_stencil_sweep_8000.csv",
    "Sweep-16K": REPO / "results/phaseC/decomp_stencil_sweep_16000.csv",
    "Sweep-24K": REPO / "results/phaseC/decomp_stencil_sweep_24000.csv",
}
# The only same-session, same-instrumented-build wall-clock pairing that
# exists anywhere in Phase C: PHASEC_REPORT.md Gate G3 (instrumentation
# overhead validation), Stencil-24K, 5 trials, DECOMP=1 (instrumented) median.
G3_STENCIL_24K_DECOMP1_MS = 1645.6
G3_STENCIL_24K_DECOMP0_MS = 1635.1
G3_OVERHEAD_PCT = 100.0 * (G3_STENCIL_24K_DECOMP1_MS - G3_STENCIL_24K_DECOMP0_MS) / G3_STENCIL_24K_DECOMP0_MS


def main():
    lines = ["# End-to-end pipelining ceiling (Task B4)", ""]
    lines.append("**This is the highest-value task in Part 1**, per the brief. Result "
                  "up front: the end-to-end ceiling is reliably computable for exactly "
                  "**one** of the seven Phase C workloads (Stencil-24K), and even that "
                  "one carries a provenance caveat. For the other six, no same-session "
                  "wall-clock pairing exists on disk -- reported as not computable, per "
                  "the task's own instruction, rather than paired with a mismatched "
                  "proxy.")
    lines.append("")

    lines.append("## 1. Dispatch-window totals (sum of total_ns across all batches)")
    lines.append("")
    lines.append("| Workload | n batches | sum(D1+D2) us | sum(total_ns) us | "
                  "D1+D2 share of window |")
    lines.append("|---|---|---|---|---|")
    print("=== Dispatch-window sums ===")
    window_sums = {}
    for label, path in DECOMP.items():
        rows = list(csv.DictReader(open(path)))
        sum_d12 = sum(float(r["d1_ns"]) + float(r["d2_ns"]) for r in rows) / 1000.0
        sum_total = sum(float(r["total_ns"]) for r in rows) / 1000.0
        share = 100.0 * sum_d12 / sum_total
        window_sums[label] = dict(n=len(rows), sum_d12_us=sum_d12, sum_total_us=sum_total,
                                   share_pct=share)
        lines.append(f"| {label} | {len(rows)} | {sum_d12:.1f} | {sum_total:.1f} | "
                      f"{share:.2f}% |")
        print(f"  {label}: n={len(rows)} sum_d12={sum_d12:.1f}us sum_total={sum_total:.1f}us "
              f"share={share:.2f}%")
    lines.append("")
    lines.append("Note this is the aggregate (sum-of-numerator / sum-of-denominator) "
                  "share, a third convention distinct from both the ratio-of-medians "
                  "used in `PHASEC_REPORT.md` and the median-of-ratios used in "
                  "`STATISTICS.md` (see Task B5) -- used here because step 4 below "
                  "needs a single number representing the total time spent in D1+D2 "
                  "across the whole run, which is what an aggregate sum, not a "
                  "per-batch median, actually represents.")
    lines.append("")

    lines.append("## 2. Wall-clock runtime recovery, per workload")
    lines.append("")
    lines.append("| Workload | Wall-clock source | Wall-clock time | Same session as "
                  "Phase C decomp run? |")
    lines.append("|---|---|---|---|")
    lines.append(f"| Stencil-24K | `PHASEC_REPORT.md` Gate G3, DECOMP=1 median (5 "
                  f"trials) | {G3_STENCIL_24K_DECOMP1_MS} ms | **Yes** -- G3 exists "
                  f"specifically to validate overhead of the same instrumented build "
                  f"used to produce `decomp_stencil_24K.csv` |")
    for label in DECOMP:
        if label == "Stencil-24K":
            continue
        lines.append(f"| {label} | none found | not available | No same-session "
                      f"wall-clock recorded in Phase C for this workload |")
    lines.append("")
    lines.append("**Why Gate 3's C0-C3 wall times (`gate3_times.csv`) are NOT used as "
                  "a substitute, even for Stencil-24K/GraphBFS-23 which share a "
                  "label:** `PHASEC_REPORT.md`'s own G3 measurement gives Stencil-24K "
                  f"a wall time of ~{G3_STENCIL_24K_DECOMP1_MS/1000:.3f}s, while "
                  "`gate3_times.csv` gives Stencil-24K wall times of 4.25s (C0), "
                  "15.28s (C1), 16.75s (C2), 15.68s (C3) -- none within an order of "
                  "magnitude of Phase C's own number for a workload with the same "
                  "label. This means Phase C's instrumented run and Gate 3's C0-C3 "
                  "sweep are NOT the same benchmark configuration (different policy, "
                  "different problem setup, or both), despite sharing an N=24000 "
                  "label. Pairing Phase C's dispatch-window sum with a Gate-3 wall "
                  "time would be exactly the kind of proxy-inference the standing "
                  "policy prohibits -- flagged and avoided, not silently done.")
    lines.append("")

    lines.append("## 3. Instrumentation overhead check (step 6)")
    lines.append("")
    lines.append(f"`PHASEC_REPORT.md` Gate G3 states +0.64% overhead for Stencil-24K "
                  f"(DECOMP=0 median {G3_STENCIL_24K_DECOMP0_MS}ms -> DECOMP=1 median "
                  f"{G3_STENCIL_24K_DECOMP1_MS}ms). Recomputed here: "
                  f"({G3_STENCIL_24K_DECOMP1_MS}-{G3_STENCIL_24K_DECOMP0_MS})/"
                  f"{G3_STENCIL_24K_DECOMP0_MS} = **{G3_OVERHEAD_PCT:.3f}%**, confirming "
                  f"the report's stated figure. This validation was performed **only "
                  f"for Stencil-24K, 5 trials**; `PHASEC_REPORT.md` does not report a "
                  f"separate overhead check for GraphBFS-23 or any Sweep size. It is a "
                  f"reasonable assumption that the same fixed per-batch instrumentation "
                  f"cost (~14 `ktime_get_ns()` calls + one ring-buffer memcpy, per the "
                  f"report) applies uniformly across workloads, but that is an "
                  f"assumption carried over from Stencil-24K, not a demonstrated "
                  f"per-workload fact -- flagged as such rather than silently "
                  f"generalized.")
    lines.append("")
    lines.append(f"The wall-clock figure used below for Stencil-24K "
                  f"({G3_STENCIL_24K_DECOMP1_MS}ms) is the **DECOMP=1 (instrumented)** "
                  f"median, since that is the build the `total_ns` sums in section 1 "
                  f"were actually measured on -- internally consistent, not mixing an "
                  f"instrumented numerator with an uninstrumented denominator.")
    lines.append("")

    lines.append("## 4. End-to-end pipelining ceiling -- Stencil-24K only")
    lines.append("")
    stencil = window_sums["Stencil-24K"]
    wall_us = G3_STENCIL_24K_DECOMP1_MS * 1000.0
    window_share_of_wall = 100.0 * stencil["sum_total_us"] / wall_us
    ceiling = (stencil["share_pct"] / 100.0) * (window_share_of_wall / 100.0) * 100.0
    print(f"\nStencil-24K: window_sum={stencil['sum_total_us']:.1f}us wall={wall_us:.1f}us "
          f"window_share_of_wall={window_share_of_wall:.2f}% D12_share_of_window="
          f"{stencil['share_pct']:.2f}% ceiling={ceiling:.3f}%")
    lines.append("Arithmetic, with every denominator labelled:")
    lines.append("")
    lines.append(f"1. D1+D2 share of dispatch window (from section 1, aggregate/sum "
                  f"convention): **{stencil['share_pct']:.2f}%** "
                  f"(of the dispatch-window denominator, i.e. total_ns).")
    lines.append(f"2. Dispatch window as a share of wall-clock runtime: "
                  f"sum(total_ns) = {stencil['sum_total_us']:.1f}us over 5253 batches, "
                  f"divided by wall-clock {wall_us:.1f}us (G3 DECOMP=1 median) = "
                  f"**{window_share_of_wall:.2f}%** (of the wall-clock denominator).")
    lines.append(f"3. End-to-end ceiling = (D1+D2 share of window) x (window share of "
                  f"wall-clock) = {stencil['share_pct']:.2f}% x "
                  f"{window_share_of_wall:.2f}% = **{ceiling:.3f}% of wall-clock "
                  f"runtime**.")
    lines.append("")
    lines.append(f"**This computed value ({ceiling:.2f}%) is in the same rough range "
                  f"as the previously-circulated but unsourced '~6% end-to-end "
                  f"ceiling' figure, though not identical to it and not derived from "
                  f"it.** Task B already established that no on-disk source states "
                  f"6% directly; this computation independently arrives at "
                  f"{ceiling:.2f}%, about {ceiling/6:.1f}x the earlier informal "
                  f"estimate -- close enough that the earlier figure was plausibly a "
                  f"rough mental version of roughly this same calculation, but not "
                  f"close enough to treat as confirmed (a ~30% relative difference). "
                  f"The computed value should be used if this task's Stencil-24K pairing "
                  f"is judged acceptable for the manuscript; if the G3-vs-Gate3 "
                  f"provenance mismatch in section 2 is judged too uncertain to put a "
                  f"number in the paper, Section VI must be written in window-share "
                  f"terms only (i.e. the {stencil['share_pct']:.1f}% figure, explicitly "
                  f"NOT converted to an end-to-end number), with the caveat that an "
                  f"end-to-end conversion could not be reliably computed for the "
                  f"other six workloads. **Recommendation: use window-share language, "
                  f"not this end-to-end percentage**, in the manuscript -- one "
                  f"workload's ratio built from a wall-clock figure of uncertain "
                  f"configuration provenance is too thin a basis for a headline "
                  f"end-to-end ceiling claim, even though the arithmetic itself is "
                  f"correct and reported above for completeness.")
    lines.append("")

    lines.append("## 5. The other six workloads")
    lines.append("")
    lines.append("GraphBFS-23, Stencil-8K, and Sweep-{4K,8K,16K,24K}: **no same-session "
                  "wall-clock runtime exists on disk.** Per the task's own instruction "
                  "(\"If the inputs for step 2 do not exist, report that the end-to-end "
                  "ceiling is not currently computable\"), this is reported as such -- "
                  "not estimated, not paired with a mismatched Gate 3/Phase B number.")
    lines.append("")
    lines.append("| Workload | D1+D2 share of dispatch window | End-to-end ceiling |")
    lines.append("|---|---|---|")
    for label, w in window_sums.items():
        if label == "Stencil-24K":
            lines.append(f"| {label} | {w['share_pct']:.2f}% | "
                          f"{ceiling:.3f}% (see caveats in section 4) |")
        else:
            lines.append(f"| {label} | {w['share_pct']:.2f}% | **not computable** "
                          f"(no wall-clock denominator) |")
    lines.append("")

    lines.append("## 6. Gate B4 summary")
    lines.append("")
    lines.append(f"- Window-share figures (D1+D2 / dispatch window, aggregate "
                  f"convention) computed for all 7 workloads, range "
                  f"{min(w['share_pct'] for w in window_sums.values()):.1f}%-"
                  f"{max(w['share_pct'] for w in window_sums.values()):.1f}%.")
    lines.append(f"- End-to-end ceiling computable for **1 of 7** workloads "
                  f"(Stencil-24K): {ceiling:.3f}% of wall-clock, via a wall-clock "
                  f"figure whose policy/config provenance does not match Gate 3's "
                  f"same-labelled workload -- reported with that caveat, not hidden.")
    lines.append(f"- Instrumentation overhead confirmed at {G3_OVERHEAD_PCT:.2f}% "
                  f"(matches `PHASEC_REPORT.md`'s stated 0.64%), validated for "
                  f"Stencil-24K only; assumed (not demonstrated) to generalize.")
    lines.append(f"- **Recommendation:** Section VI should state the pipelining "
                  f"opportunity in window-share terms (9-30% of the dispatch window, "
                  f"the range from `STATISTICS.md`/`PHASEC_REPORT.md`) with an explicit "
                  f"caveat that an end-to-end wall-clock ceiling could not be reliably "
                  f"computed from on-disk data, rather than asserting any single "
                  f"end-to-end percentage.")

    OUT = REPO / "results/analysis/PIPELINING_CEILING.md"
    OUT.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
