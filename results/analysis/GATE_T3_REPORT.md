# Gate T3 — Phase C paired wall-clock capture, 6 missing workloads

Per `PIPELINING_CEILING.md` (Task B4), the end-to-end pipelining ceiling was computable for
exactly 1 of 7 Phase C workloads (Stencil-24K, ~7.9%), because only that one had a
same-session wall-clock pairing on disk. This task closes that gap for the other six:
**Stencil-8K, GraphBFS-23, Sweep-4K, Sweep-8K, Sweep-16K, Sweep-24K.**

Data: `results/phaseC/paired_wallclock/t3_paired_times.csv` (30 rows, 6 workloads x 5
trials, matching `PHASEC_REPORT.md`'s own G3 trial count). Decomp snapshots:
`results/phaseC/paired_wallclock/decomp/*.bin` (not committed -- raw ring dumps, per this
project's convention; aggregate numbers below are the record of what matters). Module:
policy=0 depth=0 prefetch=1 log=1 (identical to `run_gatec1_decomp.sh`'s `load_module` and
to `PHASEC_REPORT.md`'s stated configuration for every other Phase C gate), srcversion
`8A2651D1CB32C7B239FB511` throughout, one continuous session (no reloads between trials,
since the config doesn't change run to run -- unlike T1/T2, nothing here needs the
reload-per-run mechanism). dmesg clean.

## 1. Accounting closure (G1), reused as a data-quality check

Before trusting the arithmetic below, checked that every batch record satisfies Phase C's
own G1 closure gate (`d1+d2+svc+d6` within 2% of the measured total window):

| Workload | valid records | G1 violations |
|---|---|---|
| Stencil-8K | 4,224 | 0 (0.00%) |
| GraphBFS-23 | 2,359 | 7 (0.30%) |
| Sweep-4K | 1,307 | 0 (0.00%) |
| Sweep-8K | 4,212 | 0 (0.00%) |
| Sweep-16K | 11,958 | 4 (0.03%) |
| Sweep-24K | 26,123 | 5 (0.02%) |

Closure holds essentially perfectly across all six workloads. The decomp telemetry
mechanism itself is sound for this new data.

## 2. D1+D2 window share -- reproduces PIPELINING_CEILING.md closely

| Workload | n batches (this run) | D1+D2 share (this run) | D1+D2 share (`PIPELINING_CEILING.md`) |
|---|---|---|---|
| Stencil-8K | 4,224 | 33.34% | 33.41% |
| GraphBFS-23 | 2,359 | 13.36% | 12.75% |
| Sweep-4K | 1,307 | 36.19% | 34.33% |
| Sweep-8K | 4,212 | 34.47% | 34.20% |
| Sweep-16K | 11,958 | 30.72% | 31.25% |
| Sweep-24K | 26,123 | 26.99% | 26.14% |

All six within ~0.5-1.9 percentage points of the original figures, despite being an
entirely fresh capture session. Strong corroboration that the D1+D2 share is a stable,
reproducible property of each workload's fault pattern, not an artifact of a particular
run.

## 3. Full arithmetic, every denominator labelled

Per workload: `sum(D1+D2)` and `sum(total_ns)` across all batches (aggregate/sum
convention, matching `PIPELINING_CEILING.md` section 1's choice, since this step needs a
total-time representation, not a per-batch median); wall-clock median (5 trials, this
session, DECOMP=1 build -- same run the decomp numbers came from, so no separate
instrumentation-overhead correction is layered on top, matching section 3's convention);
dispatch window as a fraction of wall-clock; end-to-end ceiling as their product.

| Workload | sum(D1+D2) us | sum(total_ns) us | D1+D2 share | wall-clock median | window/wall-clock | **ceiling** |
|---|---|---|---|---|---|---|
| Stencil-8K | 131,521.8 | 394,503.4 | 33.34% | 0.690s | 57.17% | **19.06%** |
| GraphBFS-23 | 107,210.1 | 802,584.8 | 13.36% | 54.230s | 1.48% | **0.20%** |
| Sweep-4K | 40,193.0 | 111,053.5 | 36.19% | 0.330s | 33.65% | **12.18%** |
| Sweep-8K | 122,811.7 | 356,249.7 | 34.47% | 0.670s | 53.17% | **18.33%** |
| Sweep-16K | 321,229.8 | 1,045,794.6 | 30.72% | 1.960s | 53.36% | **16.39%** |
| Sweep-24K | 626,339.5 | 2,320,404.6 | 26.99% | 4.090s | 56.73% | **15.31%** |

**End-to-end ceiling range across these six: 0.20% (GraphBFS-23) to 19.06% (Stencil-8K).**

> **CORRECTION (2026-08-13, `CEILING_BASIS_VERIFICATION.md`): the `window/wall-clock` step
> above is wrong — SUPERSEDED, not deleted.** The numerator (`sum(total_ns)`) is aggregated
> across all 5 trials' batches, while the denominator (wall-clock median) represents only
> one trial. Summing five roughly-similar trials and dividing by one trial's median inflates
> the ratio by a factor mechanically close to 5 — confirmed both algebraically and by direct
> evidence: recomputing the same formula on the T4's own committed data (same defect, see
> `CEILING_BASIS_VERIFICATION.md` Section 4) produces `window/wall-clock` fractions **above
> 100%** at 4 of 6 workloads under the span convention, which is physically impossible for a
> quantity that must be a subset of process wall-clock time. The formula was never checked
> against an elapsed-span sanity bound before now (`CEILING_BASIS_VERIFICATION.md` Section 5).
>
> Corrected convention (median-of-trials aggregation, matching the wall-clock denominator's
> own single-trial scale; span instead of sum as the numerator, since a ceiling meant to
> bound wall-clock savings should be measured against elapsed calendar time, not summed
> per-batch busy time — see `CEILING_BASIS_VERIFICATION.md` Section 7 for the reasoning):
>
> | Workload | **Superseded ceiling** | **Corrected ceiling** |
> |---|--:|--:|
> | Stencil-8K | ~~19.06%~~ | **7.09%** |
> | GraphBFS-23 | ~~0.20%~~ | **0.13%** |
> | Sweep-4K | ~~12.18%~~ | **4.34%** |
> | Sweep-8K | ~~18.33%~~ | **7.39%** |
> | Sweep-16K | ~~16.39%~~ | **7.94%** |
> | Sweep-24K | ~~15.31%~~ | **7.43%** |
>
> **Corrected range: 0.13% to 7.94%** (vs. the superseded 0.20-19.06%). Full derivation,
> the 4-convention comparison, and the recommendation rationale: `CEILING_BASIS_VERIFICATION.md`.

## 4. Cross-check against the original Stencil-24K (~7.9%): does NOT reproduce, and why

**No.** `Sweep-24K` is the same underlying benchmark and size as the original
`PIPELINING_CEILING.md` "Stencil-24K" entry (`bench_stencil`, N=24000) -- but the two were
never claimed to be the same *measurement session* even in the original report (Section 2
of `PIPELINING_CEILING.md` already flags them as separate figures, 25.93% vs 26.14% D1+D2
share, from different parts of Phase C's original data collection). This session's
Sweep-24K wall-clock median is **4.09s**; the original Stencil-24K entry's paired
wall-clock (from `PHASEC_REPORT.md`'s Gate G3) was **1.646s** -- roughly 2.5x shorter, for
what should be the same workload under the same module configuration.

**This is the identical discrepancy Gate 2 (`GATE2_REPORT.md`) already found and flagged as
pre-existing and out of scope**, not a new problem introduced here: this session's own
instrumentation-overhead check (Gate 2, Section 5) got 4.17-4.18s for Stencil-24K under a
C0-equivalent config, and could not reproduce Phase C's 1.6s figure under any config tried
there either (including prefetch-OFF, which made it worse, not better). The most likely
explanation, offered here but not confirmed: Gate G3's overhead micro-benchmark may not run
the full `bench_stencil.cu` application (which includes non-fault-path setup/compute work)
but a narrower, fault-path-only stress probe -- which would run much faster than the full
benchmark binary this session (and Gate 3, and Gate 2) all used. Not chased down further,
consistent with Gate 2's decision and `PIPELINING_CEILING.md`'s own choice not to force a
resolution.

**What this means for the ceiling numbers above:** they are internally consistent with each
other (all six computed the same way, in the same session, same module config, same
benchmark binaries) but **not on the same wall-clock basis as the original standalone
Stencil-24K's 7.86% figure**. Reported as a fresh, self-consistent set of six, not as
directly comparable additions to the one pre-existing number.

## 5. Instrumentation overhead

**Applied by construction, not as a separate correction.** Per `PIPELINING_CEILING.md`
section 3's convention (reused here deliberately): the wall-clock numerator and the
decomp-derived denominator both come from the same DECOMP=1 instrumented run, so the
+0.64%-class overhead is already baked into both sides of the ratio and does not need a
separate adjustment (adding one would double-count).

## 6. What the manuscript can now say

Before this task: end-to-end ceiling computable for 1/7 workloads. After: computable for
6/7, on a consistent basis with each other (Section 4's caveat on the 7th). ~~Range: 0.20%
(GraphBFS-23) to 19.06% (Stencil-8K)~~ **SUPERSEDED — see the correction note under Section 3.
Corrected range: 0.13% (GraphBFS-23) to 7.94% (Sweep-16K)**, still driven mostly by how much
of each workload's wall-clock time is spent in fault servicing at all: GraphBFS-23 spends
only a small fraction of its wall-clock inside the dispatch window (it's compute-bound, not
fault-bound), while the stencil family spends much more. Section VI can now state a real
range instead of falling back to window-share-only language for six of seven workloads --
but should present the six new numbers and the one pre-existing Stencil-24K number as two
separately sourced sets, per Section 4's caveat, rather than blend them into one continuous
seven-workload table without the footnote. **Also note**: the corrected, much smaller
ceiling range (sub-8% everywhere) is more consistent with this project's own negative
result for speculative prefetching (Phase B/C's "no net throughput gain" conclusion) than
the superseded up-to-19% figure was — a small pipelining headroom that SpecAsync's own
architecture cannot reach (D4/D5 is not offloadable, Section "Decision" in
`PHASEC_REPORT.md`) is a better fit for "no benefit materializes" than a headroom as large
as 19% would have been.
