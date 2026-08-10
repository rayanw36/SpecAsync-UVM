# Pre-registration of the T1 analysis plan (Task 1.4)

Written and committed **before** any GPU run in this work block produces a number, per the
standing ordering rule: B1 and B2 (see `OUTLIER_FORENSICS.md`, `MULTIPLE_COMPARISONS.md`)
established that Gate 3's C3-vs-C1 and C3-vs-C0 pairs were measured under a blocked protocol
with no drift control between the two arms being compared, while only C2-vs-C1 was
interleaved. This document fixes, in advance, every analytic decision for T1's interleaved
rerun so that whatever the result turns out to be, it is reportable without appearing
post-hoc.

## 1. Interleaving scheme

**Exact rotation: `C0, C1, C2, C3, C0, C1, C2, C3, ...`**, repeating, within a single
uninterrupted session per benchmark. No blocking of any config against any other at any
point in the sequence.

Two benchmarks (Stencil@24000, GraphBFS@23) each get their **own** full interleaved
session -- benchmark identity is not itself interleaved run-to-run, since switching
benchmark binaries on every single run would introduce process-startup/working-set-reload
overhead as a confound unrelated to the config comparison this task is designed to isolate.
Within each benchmark's session, all four configs rotate every single run; no config is
ever run twice in a row and no config gets its own separate reload the way C0 and C3 did in
the original Gate 3 protocol.

The kernel module itself is loaded once per session, before the rotation starts, and never
reloaded mid-session; `C0`-`C3` are runtime parameter switches (per `GATE3_report.md`'s own
description of how C1/C2 were already switched), applied at the start of each run in the
rotation.

## 2. n per cell

**Minimum: 15** (matches the original Gate 3 sample size, preserving comparability).
**Target: 20** post-warm-up-discard reps per (config, benchmark) cell.

## 3. Warm-up policy

**Discard the first 2 complete rotations (8 runs: 2 reps of each of C0/C1/C2/C3) at the
start of every session**, uniformly, regardless of benchmark. This is decided now, before
any data exists, and applied identically to every configuration -- no cell gets a different
warm-up count based on how its early runs look.

Total runs per session, per benchmark: 2 (warm-up rotations) + 20 (target rotations) = 22
rotations x 4 configs = 88 runs. If a session must stop early, the floor for a usable cell
is 15 post-warm-up reps (see Section 2); anything short of that is reported as underpowered
for that cell rather than padded.

## 4. Statistic of record: median

Per `STATISTIC_OF_RECORD.md` (Task B5): Shapiro-Wilk rejects normality for at least one
group in every Gate 3 config/benchmark cell measured so far, so mean/SD is not the
defensible default. **Median is the statistic of record** for every headline wall-clock
number this task produces. This carries forward unchanged from the original Gate 3 analysis
-- not a new decision, restated here so the T1 rerun follows the same rule without needing
to re-derive it.

## 5. Test of record: Mann-Whitney U, two-sided

Per `STATISTICS.md`/`MULTIPLE_COMPARISONS.md`: MWU is the authoritative test in every cell
where normality is rejected, which is every cell so far. **Mann-Whitney U, two-sided, is
the test of record.** Welch's t-test is still computed and reported alongside (as the prior
tasks did) for transparency, but MWU is what significance verdicts are based on.

## 6. Correction: Holm-Bonferroni across the family

**Family, enumerated in advance (6 comparisons, mirroring `MULTIPLE_COMPARISONS.md`'s
Task B2 family so the corrected family doesn't shift between the original Gate 3 analysis
and this rerun):**

1. Stencil-24K, C3 vs C1 (**primary**)
2. GraphBFS-23, C3 vs C1 (**primary**)
3. Stencil-24K, C3 vs C0 (secondary)
4. GraphBFS-23, C3 vs C0 (secondary)
5. Stencil-24K, C2 vs C1 (secondary)
6. GraphBFS-23, C2 vs C1 (secondary)

**Family size = 6.** Holm-Bonferroni step-down procedure applied exactly as in
`MULTIPLE_COMPARISONS.md`: sort the six MWU p-values ascending, compare the k-th smallest to
alpha/(6-k+1); once one comparison fails its threshold, every larger p-value in sorted order
is also rejected-from-significance regardless of its own threshold. Benjamini-Hochberg
(q=0.05) is reported alongside as a secondary, less conservative view, exactly as before --
Holm remains the correction of record for the headline verdict.

## 7. Outlier policy

**Report with and without outliers; remove none from the headline number.** The headline
median/MWU/MDE figures are always computed on the full, un-trimmed sample. A secondary
sensitivity table (with vs. without) is reported alongside, exactly as
`OUTLIER_FORENSICS.md` did for the original Gate 3 data, so a reader can judge either way --
but the headline never depends on which one was chosen.

**Outlier rule (fixed in advance, not a case-by-case judgement): Tukey fence**, i.e. a point
is flagged if it falls outside `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]` computed on that cell's own
sample. This is the identical rule `OUTLIER_FORENSICS.md` used, chosen for continuity so the
T1 rerun's outlier findings are directly comparable to the original Gate 3 forensics rather
than using a different threshold that would make "did the five high C3 runs reproduce" an
apples-to-oranges question.

## 8. Primary vs. secondary comparisons

**C3-vs-C1, for both benchmarks (Stencil-24K and GraphBFS-23), is primary.** This is the
comparison the abstract's blanket "C3 is statistically indistinguishable from C1" claim
rests on, and the one whose measurement protocol B1 found compromised (blocked, not
interleaved) in the original Gate 3 run. Every other comparison in the family (C3-vs-C0,
C2-vs-C1) is secondary context.

The 1.02% minimum detectable effect (MDE) figure, which converts the primary comparisons
from "underpowered null" into "well-powered negative result" in the original writeup, is
recomputed against the new interleaved data as part of this task -- see `T1`'s Gate report
for the value. The MDE is reported per primary comparison, not as one project-wide number.

## 9. What result would change the paper's conclusion

Stated explicitly so this document is falsifiable, not decorative:

**The paper's conclusion would change if, under strict interleaving, C3 shows a
statistically significant (Holm-corrected, alpha=0.05) *and* practically meaningful
improvement over C1 in either primary comparison** -- i.e., if properly interleaved data
shows speculative prefetching actually reducing wall-clock time by more than the
pre-registered MDE, rather than being statistically indistinguishable from (or worse than)
baseline. "Practically meaningful" here means an effect size and direction that would
change the paper's abstract from a negative/null result to a positive one; a
statistically-significant-but-negligible improvement smaller than the MDE would not, by
itself, overturn the conclusion.

**A secondary, weaker trigger:** if the five high C3-Stencil runs flagged in
`OUTLIER_FORENSICS.md` (Section 2a; masked by a Tukey fence under the old blocked protocol,
clustered early-to-mid-block) reproduce under strict interleaving as a stable pattern that
correlates with configuration rather than with run-order position, that would upgrade the
current "warm-up/contention artifact" reading to "two genuine, reproducible operating
regimes" -- a materially different mechanistic story that the manuscript's discussion
section would need to address even if it didn't flip the headline significance verdict.

Any outcome other than these two triggers -- including C3 remaining statistically
indistinguishable from C1, or C3 remaining significantly *worse* than C1 -- is consistent
with the paper's current conclusion and does not require revising the abstract's claim,
only (per the standing brief) tightening the statistical apparatus supporting it.

## 10. Telemetry and provenance requirements (not analytic decisions, but load-bearing)

Every run harness built for T1 (and T2-T4) must record, per run: run-order index,
wall-clock timestamp, configuration, benchmark, size, module `srcversion`, and any `dmesg`
deltas. This directly addresses `OUTLIER_FORENSICS.md` Section 5's finding that the original
Gate 3 harness recorded only a per-config ordinal index with no timestamps, which is a
large part of why B1 could not fully settle the outlier question. New data is written to
`results/phaseB2/gate3_interleaved/`; the original `gate3_times.csv` is never overwritten.
