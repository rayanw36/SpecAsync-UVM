# Gate B7 — Phase C dispatch-window decomposition on RTX 5070 Ti (driver 595.84)

**Platform: RTX 5070 Ti, sm_120 Blackwell, driver 595.84, srcversion `9E98EF08CBA769C50A24937`.
Not the T4.** Every T4 figure in this report is quoted from `PHASEC_REPORT.md` or
`GATE_T3_REPORT.md` for comparison, never presented as if measured here. Ran headless
(`systemctl isolate multi-user.target`) from a fresh post-reboot baseline (~58.7GB
`MemAvailable`).

## 0. Wall-clock convention table (read this before any number below)

Per `STENCIL_LABEL_COLLISION.md`, this project has two incompatible timing conventions for
the same workload label, and this single report uses **both**, in different sections. Every
number below is labelled; this table is the map.

| Section | Convention | Source | What it measures |
|---|---|---|---|
| Task 1 (overhead gate) | **kernel-loop time** | `bench_stencil`'s own `[RESULT] Time:` line | Only the 20-iteration kernel loop — matches `PHASEC_REPORT.md`'s inferred Gate G3 method, not comparable to Task 4 |
| Task 3 (D1-D7 breakdown) | **dispatch-window telemetry (driver-side ns)** | `specasync_decomp_log` ring, `d1_start`..`d6_end` | Not a wall-clock number at all — per-batch driver telemetry; the "total µs" column is dispatch-window time, not process time |
| Task 4 (paired wall-clock, ceilings) | **process wall-clock** | `lib_specasync_harness.sh`'s `time_run()`, `/usr/bin/time -f "%e"` | Whole process: alloc, host init, CUDA context, kernel loop, teardown |

**The collision recurs inside this report**: Task 1's Stencil-24K kernel-loop figure
(369.735ms) and Task 4's Sweep-24K process-wall-clock figure (1.080s) are the **same
underlying workload** (`bench_stencil`, N=24000) under two different measured regions —
they are not directly comparable to each other, exactly as `STENCIL_LABEL_COLLISION.md`
diagnosed for the T4. Anywhere this report needs "the Stencil-24K number," it says which one.

## 1. Protocol

- `driver/scripts/reconstruct_build_tree.sh` rebuilt `nvidia-uvm.ko` twice: once with
  `NVIDIA_UVM_CFLAGS += -DSPECASYNC_DECOMP=0` added to `nvidia-uvm/nvidia-uvm.Kbuild`
  (guarded behind a new `SPECASYNC_DECOMP_OVERRIDE=0` make variable, so the default build is
  unaffected), once without — producing `nvidia-uvm-decomp0.ko` and `nvidia-uvm-decomp1.ko`.
  Confirmed empirically, not just by flag inspection: DECOMP0 produces **0** decomp records
  after a real run; DECOMP1's srcversion (`9E98EF08CBA769C50A24937`) matches the build used
  for every other Gate B6/B7 task this session (`SPECASYNC_DECOMP` defaults to 1, so this
  *is* the same module already in use — no separate "Phase C module" exists here the way
  `nvidia-uvm-specasync-phaseC.ko` was a distinct T4 artifact).
- **Reload-per-run does NOT apply to Phase C**, confirmed against the T4 scripts before
  running anything: `GATE_T3_REPORT.md` states its own capture used "one continuous session
  (no reloads between trials, since the config doesn't change run to run)", and
  `t3_phasec_paired_wallclock.sh` reloads exactly once at the top of the script, not per
  workload. Reproduced here. The only exception is Task 1, which compares two different
  `.ko` files and therefore needs a reload on every run by construction — see Task 1.
- **Memory budget**: projected before running anything (see transcript) — Task 1 (interleaved,
  20 reloads), Task 3 (1 reload, 7 workloads), Task 4 (1 reload, 30 runs) ≈ 22 reloads total
  ≈ ~5.5GB of the characterized ~230-250MB/cycle leak, against a fresh ~58.7GB budget. Never
  came close to the 6GiB abort floor: `MemAvailable` after all four tasks was **52GB**.
- Two bugs found and fixed in existing T4-era scripts before they could contaminate T4 data,
  both from missing host-portability, same class as prior sessions' fixes:
  - `tests/run_gatec1_decomp.sh` and `tests/gatec1_decomp_analysis.py` had hardcoded
    `sudo` (no `-n`, briefly failed non-interactively) and a hardcoded CSV output path
    (`results/phaseC/decomp_*.csv`) that **overwrote the T4's own committed CSVs** on first
    run here. Caught via `git status` before anything was staged, restored with
    `git restore` (verified clean), fixed both scripts to take `RESULTS`/`MODULE` env
    overrides. No T4 data was lost.
  - `tests/t3_phasec_paired_wallclock.sh` had a hardcoded `OUT` that would have collided
    with the T4's `results/phaseC/paired_wallclock/t3_paired_times.csv` the same way; fixed
    with the same `: "${VAR:=default}"` pattern before running.

## 2. Task 1 — Instrumentation overhead gate (blocking)

**First pass (n=5, blocked DECOMP0-then-DECOMP1, kernel-loop convention):** DECOMP0 median
368.77ms, DECOMP1 median 368.52ms, delta **-0.068%**. This is nominally negative, i.e. not
physically meaningful as a point estimate — flagged, not reported as the final answer.

**Corrected pass (n=10/arm, strictly interleaved, per standing policy on comparisons):**

| Build | n | median | range |
|---|--:|--:|--:|
| DECOMP0 | 10 | 368.515ms | 367.62 - 369.96ms |
| DECOMP1 | 10 | 369.735ms | 367.53 - 375.33ms |

Delta: **+0.331%** (correct physical sign this time — instrumentation costs time, not saves
it). Mann-Whitney U p = **0.0962** (n.s. at α=0.05). Minimum detectable effect at this n
(two-sided α=0.05, power=0.80, pooled SD=1.840ms): **MDE = 0.626%**. The observed effect
(0.331%) is below the MDE — this measurement did not have the power to confirm or rule out
an effect of that size; "no measurable overhead" is the right description, not "zero
overhead." **PASS at the 2% threshold either way** (both point estimates and the MWU result
are far below 2%, further below than the MDE itself), so Task 1's gate verdict is not in
question — only the precision of the point estimate was.

**The tension, stated and not resolved:** a fixed per-batch instrumentation cost (~14
`ktime_get_ns()` calls + a 112-byte memcpy, per `PHASEC_REPORT.md`) measured against this
platform's ~4.45x smaller kernel-loop denominator (Section 3 below) should mechanically
appear **larger** in percentage terms than the T4's 0.64%, not smaller or absent — the same
absolute overhead is a bigger fraction of a smaller total. It does not: this platform's
measured overhead (0.331%, n.s.) is smaller than T4's 0.64% point estimate, not ~4.45x
larger as a naive fixed-cost model predicts. Two explanations are consistent with this and
neither is confirmed here: (a) the fixed-cost model is wrong — the actual per-batch
instrumentation cost (clocksource reads, ring-buffer memcpy) may itself be architecture-
dependent and genuinely cheaper in absolute nanoseconds on this platform, not a constant
carried over from Turing; or (b) some other factor (batch count, cache locality of the ring
buffer, spinlock contention profile) differs enough to break the naive scaling argument.
**Not chased down further** — resolving it needs per-batch instrumentation-cost profiling,
out of scope for this gate. Reported as an open tension, not resolved by assertion.

**Verdict: PASS.** Overhead is below the 2% threshold under both the original and corrected
protocol; the corrected (interleaved, MWU-backed) measurement is the one to cite.

## 3. Task 2 — Accounting closure gate (blocking)

`d1+d2+svc+d6` within 2% of measured total, per batch record, across the same 7-workload
sweep used for Task 3 (one reload, no per-run reload — see Section 1).

| Workload | valid records | violations | violation % |
|---|--:|--:|--:|
| Stencil-8K | 866 | 0 | 0.00% |
| Stencil-24K | 6,007 | 2 | 0.03% |
| GraphBFS-23 | 455 | 0 | 0.00% |
| Sweep-4K | 245 | 0 | 0.00% |
| Sweep-8K | 845 | 0 | 0.00% |
| Sweep-16K | 2,904 | 0 | 0.00% |
| Sweep-24K | 6,047 | 1 | 0.02% |

**Reproduces, within (tighter than) T4's 0-0.30% range.** G2 (monotonicity) also 100% pass
on all seven. **Verdict: PASS.** The decomposition telemetry is sound on this platform.

## 4. Platform speed-difference finding (informs Task 3's D4/D5 interpretation)

Three independent same-workload (N=24000 `bench_stencil`) speed ratios, T4 vs this platform,
each in its own correct convention:

| Quantity | T4 | This platform | Speedup | Convention |
|---|--:|--:|--:|---|
| Kernel-loop time | 1645.6ms | 369.735ms | **4.45x** | kernel-loop (Task 1) |
| Process wall-clock (Sweep-24K) | 4.090s | 1.080s | **3.79x** | process wall-clock (Task 4) |
| Dispatch-window sum (Sweep-24K, same-session paired) | 2,320,404.6us | 987,448.2us | **2.35x** | driver telemetry (Task 3/4) |

Against a PCIe **gen3 x8 → gen5 x16 raw bandwidth improvement of ~8x**. **None of the three
measured speedups reach the raw bandwidth improvement, and they form a strict ordering:
PCIe (8x) > wall-clock (3.79x) ≈ kernel-loop (4.45x) > dispatch-window (2.35x).** The
dispatch-window component — D1+D2+D3+D4/D5+D6, i.e. exactly the fault-servicing path this
whole report decomposes — speeds up the *least* of anything measured, well below even the
already-sub-linear whole-workload speedups. **This directly informs how to read Section 5's
D4/D5 dominance**: D4/D5 is GPU fault service time held under the va_space lock, and it is
migration-adjacent (the GPU is being told about mapping changes, which is what the PCIe link
carries). If D4/D5 were purely migration-bandwidth-bound, it should have benefited *most*
from the 8x PCIe improvement, not least. It didn't. This is evidence — not proof, one
workload — that D4/D5's cost has a floor set by something other than transfer bandwidth
(page-table walk logic, per-fault CPU-side dispatch overhead, lock-hold bookkeeping)
that does not shrink when the interconnect gets faster. Stated as a finding to carry into
the manuscript's interpretation of D4/D5, not resolved beyond what one workload's ratio can
support.

## 5. Task 3 — D1-D7 decomposition

7 workloads, config `policy=0 depth=0 prefetch=1 log=1` (matches `run_gatec1_decomp.sh` and
`PHASEC_REPORT.md` exactly), one reload, dispatch-window telemetry convention.

| Workload | n | D1% | D2% | D3% | D4% (RoM) | D5% (RoM) | D6% | D4% (MoR) | D1+D2% |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Stencil-8K | 866 | 18.4 | 11.2 | 0.1 | 55.4 | 53.9 | 8.0 | 54.61 | 29.6 |
| Stencil-24K | 6,007 | 20.2 | 12.6 | 0.1 | 57.3 | 55.8 | 6.2 | 57.26 | 32.7 |
| GraphBFS-23 | 455 | 7.6 | 2.8 | 0.1 | 76.9 | 76.3 | 1.5 | 84.56 | 10.4 |
| Sweep-4K | 245 | 19.4 | 12.9 | 0.1 | 52.1 | 50.1 | 8.2 | 50.38 | 32.3 |
| Sweep-8K | 845 | 19.6 | 12.5 | 0.1 | 54.7 | 53.0 | 8.7 | 53.13 | 32.1 |
| Sweep-16K | 2,904 | 19.0 | 10.8 | 0.1 | 56.7 | 55.1 | 7.0 | 56.51 | 29.8 |
| Sweep-24K | 6,047 | 20.4 | 12.8 | 0.1 | 57.2 | 55.9 | 6.3 | 57.12 | 33.2 |

RoM = ratio-of-medians (headline convention, per `PHASEC_REPORT.md`); MoR = median-of-ratios
(dispersion convention, per `STATISTIC_OF_RECORD.md`) — both reported per this project's
established dual-statistic policy for D4/D5, not a new convention invented here.

### Comparison to T4

| Metric | T4 | This platform | Verdict |
|---|---|---|---|
| D4/D5 share, ratio-of-medians | 63-74% (`PHASEC_REPORT.md`) | 52.1-76.9% | **Reproduces the magnitude; wider range on both ends** |
| D4/D5 share, median-of-ratios | 60.75-86.00% (`STATISTIC_OF_RECORD.md`) | 50.38-84.56% | **Reproduces closely** — nearly identical span, same max workload (GraphBFS-23) |
| D3 (lock wait) | ~0.1% | 0.05-0.14% | **Reproduces** — no lock contention on either platform |
| D1+D2 (offloadable share) | 9-36% (per-workload, `PHASEC_REPORT.md`/`GATE_T3_REPORT.md`) | 10.4-33.2% | **Reproduces the range** |
| GraphBFS-23 as the D4/D5-heaviest, D1+D2-lightest outlier | Yes (73.8% / 9.6-13.36%) | Yes (76.9% / 10.4%) | **Reproduces the qualitative pattern exactly** |

**D4/D5 dominance reproduces cross-architecture, both in magnitude and in which workload
sits at each end of the range.** GraphBFS-23's irregular-access, multi-dispatch-per-batch
signature (median dispatch calls/batch: 4 here vs 1 for every stencil variant, matching
`PHASEC_REPORT.md`'s "7 dispatches/batch" T4 finding qualitatively) is the same mechanism
driving the same outlier position on both platforms. D3's near-zero lock-wait also
reproduces exactly — SpecAsync's async-offload hypothesis (that lock contention would be the
bottleneck) is rejected on both platforms, for the same reason.

## 6. Task 4 — Paired wall-clock and end-to-end pipelining ceilings

6 workloads (matching `GATE_T3_REPORT.md`'s set, the 6 that needed a wall-clock pairing), 5
trials each, one reload, process-wall-clock convention (Section 0). Every denominator
labelled, aggregate sum convention (matches `GATE_T3_REPORT.md` Section 3 exactly): wall-
clock numerator and decomp-derived denominator both from the same DECOMP=1 run, so the
~0.33%-class overhead (Section 2) is baked into both sides and not separately corrected.

| Workload | sum(D1+D2) us | sum(total) us | D1+D2 share | wall-clock median | window/wall-clock | **ceiling** |
|---|--:|--:|--:|--:|--:|--:|
| Stencil-8K | 45,689.1 | 143,445.5 | 31.85% | 0.270s | 53.13% | **16.92%** |
| GraphBFS-23 | 39,101.5 | 285,239.7 | 13.71% | 31.160s | 0.92% | **0.13%** |
| Sweep-4K | 14,744.0 | 45,306.6 | 32.54% | 0.180s | 25.17% | **8.19%** |
| Sweep-8K | 45,171.9 | 141,411.1 | 31.94% | 0.270s | 52.37% | **16.73%** |
| Sweep-16K | 150,062.4 | 466,049.4 | 32.20% | 0.570s | 81.76% | **26.33%** |
| Sweep-24K | 313,403.2 | 987,448.2 | 31.74% | 1.080s | 91.43% | **29.02%** |

~~**End-to-end ceiling range: 0.13% (GraphBFS-23) to 29.02% (Sweep-24K).**~~ **SUPERSEDED —
see the correction below.**

> **CORRECTION (2026-08-13, `CEILING_BASIS_VERIFICATION.md`): the table above shares a units
> bug with `GATE_T3_REPORT.md`, which this report deliberately copied.** The numerator
> (`sum(total_ns)`) is aggregated across all 5 trials' batches while the denominator
> (wall-clock median) is a single trial's value — inflates every ceiling by a factor
> mechanically close to 5x, proven wrong (not just suspected) by span-based fractions
> exceeding 100% on the T4's own data under the same formula. Corrected convention:
> median-of-trials aggregation, span instead of sum as the numerator (see
> `CEILING_BASIS_VERIFICATION.md` Section 7).
>
> | Workload | **Superseded ceiling** | **Corrected ceiling** |
> |---|--:|--:|
> | Stencil-8K | ~~16.92%~~ | **3.92%** |
> | GraphBFS-23 | ~~0.13%~~ | **0.08%** |
> | Sweep-4K | ~~8.19%~~ | **1.86%** |
> | Sweep-8K | ~~16.73%~~ | **3.94%** |
> | Sweep-16K | ~~26.33%~~ | **6.53%** |
> | Sweep-24K | ~~29.02%~~ | **7.25%** |
>
> **Corrected range: 0.08% to 7.25%** (vs. the superseded 0.13-29.02%).

### Comparison to T4 — SUPERSEDED, direction reverses under the corrected convention

~~| Workload | T4 ceiling | This platform | Verdict |~~
~~|---|--:|--:|---|~~
~~| Stencil-8K | 19.06% | 16.92% | Reproduces (same order, ~2pt lower) |~~
~~| GraphBFS-23 | 0.20% | 0.13% | Reproduces (both near-zero, compute-bound) |~~
~~| Sweep-4K | 12.18% | 8.19% | Reproduces the qualitative pattern (lowest of the Sweep family on both) |~~
~~| Sweep-8K | 18.33% | 16.73% | Reproduces closely |~~
~~| Sweep-16K | 16.39% | 26.33% | **Diverges** — this platform notably higher |~~
~~| Sweep-24K | 15.31% | 29.02% | **Diverges** — this platform notably higher (~1.9x) |~~

**Corrected table** (using each platform's "span, median-of-trials" ceiling from
`CEILING_BASIS_VERIFICATION.md` Section 6):

| Workload | T4 ceiling (corrected) | This platform (corrected) | Verdict |
|---|--:|--:|---|
| Stencil-8K | 7.09% | 3.92% | T4 higher |
| GraphBFS-23 | 0.13% | 0.08% | Both near-zero, T4 slightly higher |
| Sweep-4K | 4.34% | 1.86% | T4 higher |
| Sweep-8K | 7.39% | 3.94% | T4 higher |
| Sweep-16K | 7.94% | 6.53% | T4 higher |
| Sweep-24K | 7.43% | 7.25% | Roughly equal |

**Downstream consequence (a), as flagged when the units bug was found: the "diverges at the
high end, this platform notably higher" finding reported in the superseded table above was
itself an artifact of the same 5x-and-worse-scaled bug, not a real cross-platform
divergence.** Under the corrected convention, **the T4 is higher than the 5070 Ti at 5 of 6
workloads**, the opposite pattern from what was originally reported. Section 4's mechanism
(dispatch window shrinking less than overall wall-clock between platforms) is not itself
wrong — the 2.35x/3.79x/8x ordering there doesn't depend on the ceiling formula — but the
specific claim that this mechanism produces a *higher* ceiling on the faster platform does
not survive the correction. Retracted as stated; Section 4's underlying speedup-ordering
finding stands on its own (it never used the flawed ceiling formula).

**Sweep-24K/Stencil-24K label-collision caveat, restated for this platform's own numbers**:
Task 1's kernel-loop Stencil-24K figure (369.735ms) is *not* the wall-clock denominator used
for this section's Sweep-24K ceiling (that denominator is the process-wall-clock 1.080s,
Section 0). Both are reported in this document; they must not be blended.

**Downstream consequence (b): the corrected range resolves an apparent tension, not creates
one.** This report and every other Phase C document report an oracle-perfect, zero-cost
speculation mechanism (D1+D2 fully hidden) yielding no measurable net benefit (Phase B's
decisive result, `PHASEC_REPORT.md`'s "Decision" section). Under the superseded formula, that
sat awkwardly next to a headline "up to 29%" (this platform) or "up to 19%" (T4) pipelining
ceiling — a reader could reasonably ask why up to a fifth or a quarter of wall-clock time
being theoretically recoverable produced zero measured gain. **Under the corrected range
(sub-8% everywhere on both platforms), that tension mostly dissolves**: a ceiling that small
is consistent with a negative result rather than in tension with it — there was never much
headroom to capture in the first place, and Phase B's own finding (D4/D5 is not offloadable,
D1+D2's offloadable share does not translate to a system-level win even where it exists) is
sufficient on its own without needing the ceiling to have been small too. The correction
strengthens the coherence of the paper's existing negative conclusion; it does not weaken it.

## 7. What this block does and does not extend

**Extends to cross-architecture**: D4/D5 dominance (magnitude and which workload is at each
extreme), D3's near-zero lock contention, the D1+D2 offloadable-share range, the closure
gate's near-perfect pass rate, and the qualitative end-to-end-ceiling pattern (GraphBFS
near-zero / stencil family double-digit). Section VI can now state these as **cross-
architecture findings**, not T4-only, per the manuscript-scope motivation for this block.

**Does not extend / diverges**: ~~the absolute end-to-end ceiling magnitude at the two
largest Sweep sizes (this platform runs ~1.7-1.9x higher than T4 there)~~ **RETRACTED — this
was an artifact of the ceiling-formula units bug (Section 6 correction,
`CEILING_BASIS_VERIFICATION.md`), not a real divergence. Under the corrected convention the
T4 runs higher than this platform at 5 of 6 workloads, not lower.** The instrumentation-
overhead absolute-percentage comparison (Section 2) is flagged as an open tension, not a
reproduction or a divergence in the ordinary sense — the direction of the discrepancy
(smaller, not larger, than a naive fixed-cost model predicts) is itself the interesting part.

**Not comparable**: any number using this report's kernel-loop convention (Task 1) against
any number using this report's or the T4's process-wall-clock convention (Task 4, all of
Gate 3/T1-T4) — see Section 0.

## 8. Platform axes (why any divergence above might exist)

- **PCIe gen5 x16 (this platform) vs gen3 x8 (T4)**: ~8x raw interconnect bandwidth
  difference. Directly relevant to D4/D5 (GPU fault servicing, migration-adjacent) per
  Section 4's finding that D4/D5 does *not* scale with this improvement — the strongest
  single piece of evidence in this report that D4/D5's cost is not simply bandwidth-bound.
- **12 cores/24 threads (this platform) vs 2 cores/4 threads (T4, g4dn.xlarge)**: relevant to
  D1/D2 (fault-buffer drain, preprocess/sort/dedup — CPU-side work) and to host-side
  init/allocation overhead (the gap between kernel-loop and process-wall-clock, Section 0).
  Not isolated or measured directly here (both axes change together on this platform vs the
  T4, there is no controlled single-axis comparison available) — flagged as a candidate
  contributor to the D1/D2 and non-fault-path speedups, not confirmed as the mechanism.

## 9. Findings summary

| Finding | T4 | This platform | Verdict |
|---|---|---|---|
| Instrumentation overhead < 2% | 0.64% | 0.331% (n.s., MDE 0.626%) | **Reproduces (PASS)**; magnitude comparison is an open tension (Section 2) |
| Accounting closure (G1) | 0-0.30% violations | 0.00-0.03% violations | **Reproduces** |
| D4/D5 dominance | 63-74% (RoM) / 60.75-86.00% (MoR) | 52.1-76.9% (RoM) / 50.38-84.56% (MoR) | **Reproduces** |
| D3 ≈ 0 (no lock contention) | ~0.1% | 0.05-0.14% | **Reproduces** |
| D1+D2 offloadable share | 9-36% | 10.4-33.2% | **Reproduces** |
| GraphBFS-23 outlier position | heaviest D4/D5, lightest D1+D2 | heaviest D4/D5, lightest D1+D2 | **Reproduces** |
| End-to-end ceiling range | ~~0.20-19.06%~~ **0.13-7.94%** | ~~0.13-29.02%~~ **0.08-7.25%** | ~~Diverges at the high end~~ **SUPERSEDED: was a units-mismatch artifact (Section 6 correction); corrected, T4 runs higher at 5/6 workloads** |
| Kernel-loop / wall-clock speedup vs PCIe bandwidth | n/a (single platform) | 4.45x / 3.79x vs ~8x PCIe | **New cross-platform finding**, not a T4 comparison |

## Artifacts

- `results/phaseC/decomp_overhead_5070ti/overhead_times.csv` (n=5 blocked, superseded)
- `results/phaseC/decomp_overhead_5070ti/overhead_times_interleaved.csv` (n=10 interleaved, authoritative)
- `results/phaseC/decomp_5070ti/decomp_*.{bin,txt,csv}` (Task 2/3 7-workload sweep)
- `results/phaseC/paired_wallclock_5070ti/t3_paired_times_5070ti.csv` + `decomp/*.bin` (Task 4)
- `tests/gate_b7_decomp_overhead.sh` (new), `tests/run_gatec1_decomp.sh` and
  `tests/gatec1_decomp_analysis.py` and `tests/t3_phasec_paired_wallclock.sh` (host-portability
  fixes)
- Raw `.bin` ring dumps are gitignored (EBS-only, reconstructible); CSVs, `.txt` summaries,
  and this report are committed.
