# Ceiling basis verification — is `window/wall-clock` physically sound?

Analysis-only, no new experiments. Uses the already-collected Task 4 telemetry:
`results/phaseC/paired_wallclock_5070ti/decomp/*.bin` (RTX 5070 Ti, 595.84) and
`results/phaseC/paired_wallclock/decomp/*.bin` (T4, 595.71.05, committed).

**Short answer: the specific hypothesis (batch overlap inflating `sum(total_ns)`) is
false — batches never overlap, on either platform. But the investigation surfaced a
different, larger problem: both platforms' published end-to-end ceilings mix a
numerator summed across 5 trials with a denominator from only 1 trial, inflating every
published ceiling by a factor close to 5x. This is a real, unresolved issue affecting
`GATE_T3_REPORT.md` (T4) and `GATE_B7_5070TI_PHASEC.md` (5070 Ti) equally. No published
number has been changed — see the side-by-side table in Section 6.**

## 1. Per-run elapsed span vs `sum(total_ns)`

Per trial, `span = max(end) − min(d1_start)` across that trial's batch records (`end` =
`max(svc_end, d6_end)`, same definition `gatec1_decomp_analysis.py` uses for `total`),
compared against `sum(total_ns)` for the same trial.

**On both platforms, every single trial has `sum(total_ns) < span`** — the opposite of
the overcounting hypothesis. Representative trials:

| Workload | Platform | span (us) | sum(total_ns) (us) | sum/span ratio |
|---|---|--:|--:|--:|
| Stencil-8K, trial 1 | 5070 Ti | 35,617.6 | 31,126.8 | 0.874 |
| GraphBFS-23, trial 1 | 5070 Ti | 170,807.3 | 57,192.2 | 0.335 |
| Sweep-24K, trial 1 | 5070 Ti | 246,443.7 | 194,535.0 | 0.789 |
| Stencil-8K, trial 1 | T4 | 146,652.9 | 75,918.5 | 0.518 |
| GraphBFS-23, trial 1 | T4 | 526,482.4 | 160,662.5 | 0.305 |
| Sweep-24K, trial 1 | T4 | 1,125,732.0 | 469,503.6 | 0.417 |

`sum(total_ns)` is **51-87% of span** depending on workload (GraphBFS-23 lowest on both
platforms, T4 systematically lower than the 5070 Ti at every matched workload). This
means there are real **gaps between dispatch batches** — periods where no fault-service
batch is active, presumably non-fault GPU compute or host-side work between fault
bursts — not overlapping/concurrent batches. `sum(total_ns)` is, if anything, an
**undercount** of the elapsed window relative to `span`, not an overcount.

## 2. Batch overlap check

Sorted by `d1_start` within each trial; counted pairs where a record's `d1_start`
precedes the previous record's `d6_end` (as specified), cross-checked against the more
general `end` field (`max(svc_end, d6_end)`, robust to batches where D6 didn't fire).

**Overlap rate: 0/N pairs on every single trial, both platforms, both definitions.**
Aggregated: 0 overlaps out of 4,172-30,213 adjacent pairs per workload on the 5070 Ti;
0 out of 2,281-26,118 on the T4. **Batches never overlap in time on either platform.**
The overlap hypothesis is refuted directly, not just by inference from the span/sum
comparison in Section 1.

## 3. Span-based vs sum-based fractions and ceilings, both platforms, as requested

Computed exactly as asked: same aggregation (sum across all 5 trials' batches) and same
single-trial wall-clock median denominator as the published formula, only swapping the
numerator source (span vs sum). D1+D2 share is unaffected by this choice (both its
numerator and denominator use the same aggregation, so any scaling factor cancels).

| Workload | Platform | D1+D2 share | window/wall (sum, published) | window/wall (span) | ceiling (sum, published) | ceiling (span) |
|---|---|--:|--:|--:|--:|--:|
| Stencil-8K | 5070 Ti | 31.85% | 53.13% | 62.13% | 16.92% | 19.79% |
| GraphBFS-23 | 5070 Ti | 13.71% | 0.92% | 2.74% | 0.13% | 0.38% |
| Sweep-4K | 5070 Ti | 32.54% | 25.17% | 28.58% | 8.19% | 9.30% |
| Sweep-8K | 5070 Ti | 31.94% | 52.37% | 61.58% | 16.73% | 19.67% |
| Sweep-16K | 5070 Ti | 32.20% | 81.76% | 101.29% | 26.33% | 32.61% |
| Sweep-24K | 5070 Ti | 31.74% | 91.43% | 115.15% | 29.02% | 36.55% |
| Stencil-8K | T4 | 33.34% | 57.17% | 107.70% | 19.06% | 35.90% |
| GraphBFS-23 | T4 | 13.36% | 1.48% | 4.83% | 0.20% | 0.64% |
| Sweep-4K | T4 | 36.19% | 33.65% | 59.93% | 12.18% | 21.69% |
| Sweep-8K | T4 | 34.47% | 53.17% | 106.76% | 18.33% | 36.80% |
| Sweep-16K | T4 | 30.72% | 53.36% | 130.00% | 16.39% | 39.93% |
| Sweep-24K | T4 | 26.99% | 56.73% | 137.47% | 15.31% | 37.11% |

Switching from sum to span moves every ceiling **up**, not down (consistent with
Section 1: span is the larger quantity). On the T4, several span-based
`window/wall-clock` fractions **exceed 100%** (107.70%, 106.76%, 130.00%, 137.47%) —
a physically impossible value for "fraction of wall-clock time," since the dispatch
window is by construction a subset of the process's wall-clock time. This is the
clearest available proof that the aggregation, not the span/sum choice, is the primary
defect — see Section 5.

## 4. T4 comparison — same pattern, same magnitude

Requested explicitly: is this a 5070 Ti issue or project-wide? **Project-wide.** Every
qualitative feature reproduces on the T4's committed data: zero overlap, `sum(total_ns)
< span` at every workload, and impossible (>100%) span-based fractions at 4 of 6
workloads (worse than the 5070 Ti, where none exceed 100% even under the span
convention — because the T4's `sum/span` ratio runs lower, 0.30-0.56 vs the 5070 Ti's
0.33-0.89, so its span is proportionally larger relative to its own sum). **If the
sum-based figures need correction, `GATE_T3_REPORT.md`'s 0.20-19.06% range needs the
same correction, not just this report's 5070 Ti figures.**

## 5. What convention did `GATE_T3_REPORT.md` and `PIPELINING_CEILING.md` actually use?

**Different conventions, and only one of the two has the aggregation defect:**

- **`PIPELINING_CEILING.md` (original, Stencil-24K only)**: numerator is `sum(total_ns)
  = 498,937.6us` from **one single canonical decomposition capture** (`PHASEC_REPORT.md`'s
  own 5,253-record run, not re-aggregated across multiple trials), denominator is
  `PHASEC_REPORT.md` Gate G3's **separately-measured** 5-trial median wall-clock
  (1,645,600us). Numerator and denominator here are NOT drawn from the same 5-trial
  session, and the numerator was never itself summed across multiple trials — so this
  calculation does **not** have the trial-aggregation defect Section 6 describes (it has
  its own, already-documented and separate provenance problem: the numerator's capture
  session and the denominator's G3 session are different runs under different timing
  conventions, per `STENCIL_LABEL_COLLISION.md` — a different issue, not this one).
- **`GATE_T3_REPORT.md` (the 6-workload extension, and this report's Gate B7 rerun,
  which deliberately matched T3's convention)**: explicitly aggregates
  `sum(D1+D2)`/`sum(total_ns)` **across all batches from all 5 trials** (`t3_paired_
  times.csv`/`t3_paired_times_5070ti.csv`'s own per-trial `decomp_snapshot_path` column
  confirms 5 separate ring captures, one per trial, cleared between each), then divides
  by the **median of those same 5 trials' wall-clock times** — a single-trial-scale
  number. This is the formula with the defect.
- **Was the formula ever validated against an elapsed span?** No. Neither
  `PIPELINING_CEILING.md` nor `GATE_T3_REPORT.md` computes or checks an elapsed-span
  quantity anywhere; `sum(total_ns)` was taken as the window measure without a sanity
  check against the actual time interval it should fit inside. This verification task is
  the first time that check has been done.

## 6. The larger finding: trial-count aggregation mismatch (~5x), not overlap

Not part of the original hypothesis, surfaced by Section 3's >100% values. Comparing the
published `sum-agg` fraction to a `median-agg` fraction (median of the 5 trials' own
sums, instead of their sum — the convention that actually matches the wall-clock
denominator's own "median of 5 trials" scale) isolates it cleanly:

| Workload | Platform | window/wall (sum-agg, published) | window/wall (sum, median-agg) | ratio |
|---|---|--:|--:|--:|
| Stencil-8K | 5070 Ti | 53.13% | 10.50% | 5.06x |
| GraphBFS-23 | 5070 Ti | 0.92% | 0.18% | 5.11x |
| Sweep-24K | 5070 Ti | 91.43% | 18.09% | 5.05x |
| Stencil-8K | T4 | 57.17% | 11.00% | 5.20x |
| GraphBFS-23 | T4 | 1.48% | 0.30% | 4.93x |
| Sweep-24K | T4 | 56.73% | 11.32% | 5.01x |

**Every workload on both platforms inflates by almost exactly 5x** — mechanically
expected, since summing 5 roughly-similar trials and dividing by 1 trial's median is
approximately `5 × (median-agg)` by construction. This is **independent of the
span/overlap question**: it would apply equally whether the numerator were sum-based or
span-based (see the full 4-convention table below).

### Full corrected-candidate table (all 4 conventions, both platforms)

| Workload | Platform | ceiling: published (sum, sum-agg) | span, sum-agg | sum, median-agg | span, median-agg |
|---|---|--:|--:|--:|--:|
| Stencil-8K | 5070 Ti | 16.92% | 19.79% | 3.34% | 3.92% |
| GraphBFS-23 | 5070 Ti | 0.13% | 0.38% | 0.03% | 0.08% |
| Sweep-4K | 5070 Ti | 8.19% | 9.30% | 1.63% | 1.86% |
| Sweep-8K | 5070 Ti | 16.73% | 19.67% | 3.34% | 3.94% |
| Sweep-16K | 5070 Ti | 26.33% | 32.61% | 5.27% | 6.53% |
| Sweep-24K | 5070 Ti | 29.02% | 36.55% | 5.74% | 7.25% |
| Stencil-8K | T4 | 19.06% | 35.90% | 3.67% | 7.09% |
| GraphBFS-23 | T4 | 0.20% | 0.64% | 0.04% | 0.13% |
| Sweep-4K | T4 | 12.18% | 21.69% | 2.44% | 4.34% |
| Sweep-8K | T4 | 18.33% | 36.80% | 3.67% | 7.39% |
| Sweep-16K | T4 | 16.39% | 39.93% | 3.26% | 7.94% |
| Sweep-24K | T4 | 15.31% | 37.11% | 3.05% | 7.43% |

Reading the table: the **aggregation choice (sum-agg vs median-agg) moves ceilings by
~5x**; the **numerator choice (sum vs span) moves them by ~1.05-2.4x**, always upward.
The two effects partially offset in the "published" column's favor only by coincidence
of direction (sum-agg inflates, span would inflate further) — there is no version of
this arithmetic that recovers the published numbers as correct.

## 7. Recommendation (not applied)

Median-of-trials aggregation (matching the wall-clock denominator's own convention) is
the internally consistent choice — it is the only one of the four that never produces an
impossible >100% window/wall-clock fraction on either platform. Between sum and span as
the numerator within that convention: **span is more defensible for this formula's
stated purpose** (estimating what fraction of wall-clock time D1+D2-hiding could
recover) — a ceiling meant to bound wall-clock savings should be measured against the
elapsed calendar time fault-servicing occupies, gaps included, not just the summed busy
time within it. That would make **"sum, median-agg" too conservative and "span,
median-agg" the recommended corrected convention** — but this is a judgment call, not a
re-derivation from first principles, and is offered as a recommendation only.

**Nothing has been changed in `GATE_T3_REPORT.md`, `GATE_B7_5070TI_PHASEC.md`,
`PIPELINING_CEILING.md`, or `CLAIM_SCOPE.md`.** All four still state the original
sum-agg/single-median figures. This report exists so that decision can be made
deliberately: candidate corrected ceiling range across both platforms, under the
recommended "span, median-agg" convention, is **0.08-7.94%** (vs the published
0.13-29.02% on the 5070 Ti and 0.20-19.06% on the T4) — small enough, and different
enough in shape (T4 no longer systematically lower than the 5070 Ti at every workload;
under this convention T4's Stencil/Sweep-8K/16K/24K figures are all *higher* than the
5070 Ti's, reversing Gate B7's reported "diverges at the high end" finding) that this
should be resolved before Section VI cites any end-to-end percentage from either
platform. Flagged as a candidate entry for a measurement-artifact catalog (the same kind
of entry `STENCIL_LABEL_COLLISION.md` and `RATE_MISMATCH_VERIFICATION.md` already are),
pending a decision on which convention to adopt.
