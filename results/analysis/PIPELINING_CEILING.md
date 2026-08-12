# End-to-end pipelining ceiling (Task B4)

**Superseded, kept for provenance -- see `STENCIL_LABEL_COLLISION.md` and `GATE_T3_REPORT.md` for the current recommendation.** The "provenance caveat" this report could only flag has since been diagnosed: the 1645.6ms G3 figure used below is the **kernel-loop-time** convention (`run_robust.py`'s internal timer), not the **process-wall-clock** convention (`lib_specasync_harness.sh`) used by every C0-C3 table in this project, including `gate3_times.csv`. The two are not comparable, which is exactly why they disagreed by ~2.5x below. The manuscript should use Task T3's Sweep-24K point (15.31%, process-wall-clock basis, same N=24000 workload) in place of the 7.86% figure computed in section 4 here.

**This is the highest-value task in Part 1**, per the brief. Result up front: the end-to-end ceiling is reliably computable for exactly **one** of the seven Phase C workloads (Stencil-24K, kernel-loop time), and even that one carries a provenance caveat. For the other six, no same-session wall-clock pairing exists on disk -- reported as not computable, per the task's own instruction, rather than paired with a mismatched proxy.

## 1. Dispatch-window totals (sum of total_ns across all batches)

| Workload | n batches | sum(D1+D2) us | sum(total_ns) us | D1+D2 share of window |
|---|---|---|---|---|
| Stencil-8K | 839 | 25539.7 | 76450.9 | 33.41% |
| Stencil-24K | 5253 | 129397.4 | 498937.6 | 25.93% |
| GraphBFS-23 | 473 | 21027.1 | 164950.1 | 12.75% |
| Sweep-4K | 259 | 9477.0 | 27604.6 | 34.33% |
| Sweep-8K | 835 | 24950.1 | 72953.4 | 34.20% |
| Sweep-16K | 2367 | 73076.6 | 233865.4 | 31.25% |
| Sweep-24K | 5207 | 135145.8 | 516982.5 | 26.14% |

Note this is the aggregate (sum-of-numerator / sum-of-denominator) share, a third convention distinct from both the ratio-of-medians used in `PHASEC_REPORT.md` and the median-of-ratios used in `STATISTICS.md` (see Task B5) -- used here because step 4 below needs a single number representing the total time spent in D1+D2 across the whole run, which is what an aggregate sum, not a per-batch median, actually represents.

## 2. Wall-clock runtime recovery, per workload

| Workload | Wall-clock source | Wall-clock time | Same session as Phase C decomp run? |
|---|---|---|---|
| Stencil-24K | `PHASEC_REPORT.md` Gate G3, DECOMP=1 median (5 trials) | 1645.6 ms | **Yes** -- G3 exists specifically to validate overhead of the same instrumented build used to produce `decomp_stencil_24K.csv` |
| Stencil-8K | none found | not available | No same-session wall-clock recorded in Phase C for this workload |
| GraphBFS-23 | none found | not available | No same-session wall-clock recorded in Phase C for this workload |
| Sweep-4K | none found | not available | No same-session wall-clock recorded in Phase C for this workload |
| Sweep-8K | none found | not available | No same-session wall-clock recorded in Phase C for this workload |
| Sweep-16K | none found | not available | No same-session wall-clock recorded in Phase C for this workload |
| Sweep-24K | none found | not available | No same-session wall-clock recorded in Phase C for this workload |

**Why Gate 3's C0-C3 wall times (`gate3_times.csv`) are NOT used as a substitute, even for Stencil-24K/GraphBFS-23 which share a label:** `PHASEC_REPORT.md`'s own G3 measurement gives Stencil-24K a wall time of ~1.646s, while `gate3_times.csv` gives Stencil-24K wall times of 4.25s (C0), 15.28s (C1), 16.75s (C2), 15.68s (C3) -- none within an order of magnitude of Phase C's own number for a workload with the same label. This means Phase C's instrumented run and Gate 3's C0-C3 sweep are NOT the same benchmark configuration (different policy, different problem setup, or both), despite sharing an N=24000 label. Pairing Phase C's dispatch-window sum with a Gate-3 wall time would be exactly the kind of proxy-inference the standing policy prohibits -- flagged and avoided, not silently done.

## 3. Instrumentation overhead check (step 6)

`PHASEC_REPORT.md` Gate G3 states +0.64% overhead for Stencil-24K (DECOMP=0 median 1635.1ms -> DECOMP=1 median 1645.6ms). Recomputed here: (1645.6-1635.1)/1635.1 = **0.642%**, confirming the report's stated figure. This validation was performed **only for Stencil-24K, 5 trials**; `PHASEC_REPORT.md` does not report a separate overhead check for GraphBFS-23 or any Sweep size. It is a reasonable assumption that the same fixed per-batch instrumentation cost (~14 `ktime_get_ns()` calls + one ring-buffer memcpy, per the report) applies uniformly across workloads, but that is an assumption carried over from Stencil-24K, not a demonstrated per-workload fact -- flagged as such rather than silently generalized.

The wall-clock figure used below for Stencil-24K (1645.6ms) is the **DECOMP=1 (instrumented)** median, since that is the build the `total_ns` sums in section 1 were actually measured on -- internally consistent, not mixing an instrumented numerator with an uninstrumented denominator.

## 4. End-to-end pipelining ceiling -- Stencil-24K only

Arithmetic, with every denominator labelled:

1. D1+D2 share of dispatch window (from section 1, aggregate/sum convention): **25.93%** (of the dispatch-window denominator, i.e. total_ns).
2. Dispatch window as a share of wall-clock runtime: sum(total_ns) = 498937.6us over 5253 batches, divided by wall-clock 1645600.0us (G3 DECOMP=1 median) = **30.32%** (of the wall-clock denominator).
3. End-to-end ceiling = (D1+D2 share of window) x (window share of wall-clock) = 25.93% x 30.32% = **7.863% of wall-clock runtime**.

**This computed value (7.86%) is in the same rough range as the previously-circulated but unsourced '~6% end-to-end ceiling' figure, though not identical to it and not derived from it.** Task B already established that no on-disk source states 6% directly; this computation independently arrives at 7.86%, about 1.3x the earlier informal estimate -- close enough that the earlier figure was plausibly a rough mental version of roughly this same calculation, but not close enough to treat as confirmed (a ~30% relative difference). The computed value should be used if this task's Stencil-24K pairing is judged acceptable for the manuscript; if the G3-vs-Gate3 provenance mismatch in section 2 is judged too uncertain to put a number in the paper, Section VI must be written in window-share terms only (i.e. the 25.9% figure, explicitly NOT converted to an end-to-end number), with the caveat that an end-to-end conversion could not be reliably computed for the other six workloads. **Recommendation: use window-share language, not this end-to-end percentage**, in the manuscript -- one workload's ratio built from a wall-clock figure of uncertain configuration provenance is too thin a basis for a headline end-to-end ceiling claim, even though the arithmetic itself is correct and reported above for completeness.

## 5. The other six workloads

GraphBFS-23, Stencil-8K, and Sweep-{4K,8K,16K,24K}: **no same-session wall-clock runtime exists on disk.** Per the task's own instruction ("If the inputs for step 2 do not exist, report that the end-to-end ceiling is not currently computable"), this is reported as such -- not estimated, not paired with a mismatched Gate 3/Phase B number.

| Workload | D1+D2 share of dispatch window | End-to-end ceiling |
|---|---|---|
| Stencil-8K | 33.41% | **not computable** (no wall-clock denominator) |
| Stencil-24K | 25.93% | 7.863% (see caveats in section 4) |
| GraphBFS-23 | 12.75% | **not computable** (no wall-clock denominator) |
| Sweep-4K | 34.33% | **not computable** (no wall-clock denominator) |
| Sweep-8K | 34.20% | **not computable** (no wall-clock denominator) |
| Sweep-16K | 31.25% | **not computable** (no wall-clock denominator) |
| Sweep-24K | 26.14% | **not computable** (no wall-clock denominator) |

## 6. Gate B4 summary

- Window-share figures (D1+D2 / dispatch window, aggregate convention) computed for all 7 workloads, range 12.7%-34.3%.
- End-to-end ceiling computable for **1 of 7** workloads (Stencil-24K): 7.863% of wall-clock, via a wall-clock figure whose policy/config provenance does not match Gate 3's same-labelled workload -- reported with that caveat, not hidden.
- Instrumentation overhead confirmed at 0.64% (matches `PHASEC_REPORT.md`'s stated 0.64%), validated for Stencil-24K only; assumed (not demonstrated) to generalize.
- **Recommendation:** Section VI should state the pipelining opportunity in window-share terms (9-30% of the dispatch window, the range from `STATISTICS.md`/`PHASEC_REPORT.md`) with an explicit caveat that an end-to-end wall-clock ceiling could not be reliably computed from on-disk data, rather than asserting any single end-to-end percentage.
