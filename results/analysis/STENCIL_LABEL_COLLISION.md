# Stencil-24K label collision — argument-vector diff and verdict

## 1. What could not be diffed, stated up front

Phase C's G3 overhead check (`PHASEC_REPORT.md`: DECOMP=0 1635.1ms / DECOMP=1 1645.6ms,
Stencil-24K, 5 trials) **has no harness script in this repository.** `GATE2_REPORT.md`
Section 5 already found this independently ("No committed harness exists for Phase C's
original G3 check ... no script in `tests/` reproduces the exact procedure") and this task's
own search confirms it again: no script anywhere in the repo (including git history back to
the Phase C commit `1a70804`) contains the strings `DECOMP=0`/`DECOMP=1`/`1635.1`/`1645.6`
except `PHASEC_REPORT.md` itself, which states the result but not the procedure. **A literal
argument-vector diff of that script against Gate 3's harness is not possible — the artifact
is gone.** What follows is the strongest verdict obtainable from the surrounding evidence:
the benchmark source (unchanged since before Phase C), the harnesses that *do* exist and are
known to feed each family of numbers, and Gate 2's prior elimination of config-based
explanations.

## 2. The benchmark source is not the explanation

`benchmarks/bench_stencil.cu` was last modified 2026-05-31 (commit `63d45f7`), five weeks
before the Phase C commit (`1a70804`, 2026-07-06) and untouched since. Every session in this
project — Phase B/B.1/B.2, Phase C, Gate 3, T1-T4 — that runs "Stencil-24K" runs the
identical binary logic: `N=24000` (command-line arg), `#define ITERS 20`
(`bench_stencil.cu:25`), two `float` grids, ping-pong iteration. **Same workload, confirmed
by source, not by label alone.**

## 3. Two genuinely different timing conventions exist in this repo, confirmed by source

**Gate 3 / T1 / T2 / T3 / T4 (all `~4.1-4.2s` C0-equivalent figures):** `tests/lib_specasync_harness.sh:156`,
`time_run()`:
```bash
wall=$({ /usr/bin/time -f "%e" setarch -R "$bin" $args >/dev/null; } 2>&1 | tail -1)
```
This wraps the **entire process** — `cudaMallocManaged` for both 4.6 GB grids, the host-side
initialization loop (`bench_stencil.cu:92-94`, one CPU write per element across 576M
elements), CUDA context creation/lazy init, the 20 kernel iterations, final sync, and process
teardown.

**Phase B / B.1 / B.2 (`run_robust.py`):** `benchmarks/run_robust.py:97`,
`TIME_REGEX = re.compile(r"\[RESULT\] Time:\s+(\d+\.\d+)")` — parses the benchmark's own
printed line, not an external wrapper. `bench_stencil.cu:104-121` shows exactly what that
line measures:
```c
/* --- Timed region ------------------------------------------------ */
CUDA_CHECK(cudaDeviceSynchronize());
double t0 = now_sec();
for (int iter = 0; iter < ITERS; iter++) { ... }
CUDA_CHECK(cudaDeviceSynchronize());
double t1 = now_sec();
/* ----------------------------------------------------------------- */
printf("[RESULT] Time: %.2f ms\n...", time_ms, ...);
```
This brackets **only the 20-iteration kernel loop** — allocation, host-side init, and CUDA
context/first-touch overhead all happen *before* `t0` and are excluded.

**Phase C's other gates (G1, G2, G4)** are driver-ring telemetry only (`specasync_decomp_log`
D1-D7 nanosecond sums per batch) — they never call `time_run()` or parse `[RESULT] Time:` at
all; `run_gatec1_decomp.sh` has no wall-clock capture of its own. Phase C's *entire*
methodology outside G3 is internal/driver-side timing, not process-wall-clock timing, which
is the same family of convention as `run_robust.py`'s benchmark-internal timer, not
`lib_specasync_harness.sh`'s external wrapper.

## 4. Magnitude check

Missing time = process wall-clock − kernel-loop time ≈ 4.17-4.19s − 1.64s ≈ 2.5-2.6s
(matches the task's own "2.6×" framing). This is the right order of magnitude for
`cudaMallocManaged(4.6 GB total)` + the host-side single-threaded initialization loop over
576M elements + CUDA context/first-touch migration setup — all real, all excluded from the
kernel-loop timer by construction, none of it present in Gate 3/T1-T4's external wrapper
which necessarily includes it.

## 5. Config-based explanations already ruled out (not repeated here, cited)

`GATE2_REPORT.md` Section 5 tried C0-equivalent (`policy=0 depth=0 prefetch=1`, 4.170-4.180s)
and C1-equivalent/prefetch-off (15.12s, **further** from 1.6s, not closer) under the same
module build Phase C used — neither reproduces ~1.6s under any policy tried. This rules out
"G3 used a different speculation policy" as the explanation, leaving timed-region difference
as the remaining, best-supported account. `PIPELINING_CEILING.md` and `GATE_T3_REPORT.md`
both already flagged the discrepancy as real and unresolved; this task adds the mechanism.

## 6. Verdict

**Same workload, different measured region — a labelling problem, not a workload problem.
Both numbers are correct for what they measure; neither is wrong.** Confidence: high on the
mechanism (grounded directly in the two harnesses' source code, which unambiguously time
different regions), but not a certainty for G3 specifically, since its exact script cannot be
recovered to confirm it followed `run_robust.py`'s convention rather than some third
approach. Flagged as the residual uncertainty rather than papered over.

## 7. Proposed disambiguated names and section mapping

| Name | What it measures | Sourced from | Value (Stencil-24K, C0-equivalent) | Belongs in |
|---|---|---|---|---|
| **Stencil-24K (process wall-clock)** | Full process: alloc + host init + CUDA context + 20 kernel iters + teardown | `lib_specasync_harness.sh` (`time_run`) — Gate 3, T1, T2, T3, T4 | 4.185s (T1 median) | Section V (baseline/policy comparisons, all C0-C3 speedup/slowdown claims) |
| **Stencil-24K (kernel-loop time)** | Only the 20-iteration kernel loop, post-alloc/init | `run_robust.py` (`[RESULT] Time:` regex) — Phase B/B.1/B.2; presumably Phase C's lost G3 script | 1635.1-1645.6ms | Internal-only (G3's own DECOMP=0-vs-1 overhead ratio, which is self-consistent regardless of absolute convention); **not** a wall-clock denominator for any cross-phase ratio |

**Every figure and table using an unqualified "Stencil-24K" wall-clock number should adopt
one of these two names explicitly** — the plain label is what created the collision.

## 8. Consequence for the pipelining-ceiling figure

`PIPELINING_CEILING.md`'s pre-existing standalone Stencil-24K ceiling (7.86%) is built as
`(D1+D2 share of dispatch window) × (dispatch window / 1645.6ms G3 wall-clock)` — internally
consistent, but its denominator is the **kernel-loop-time** convention, not the
**process-wall-clock** convention every other figure in the manuscript uses. Given this
diagnosis, that report's own recommendation ("use window-share language, not this end-to-end
percentage... one workload's ratio built from a wall-clock figure of uncertain configuration
provenance is too thin a basis") is now confirmed correct, with the mechanism attached rather
than left as "unresolved."

**Recommendation for the manuscript:** `GATE_T3_REPORT.md`'s **Sweep-24K** entry
(same `bench_stencil` binary, N=24000, **process-wall-clock** convention matching Gate 3/T1,
same-session decomp pairing, **15.31% ceiling**) is the workload-equivalent, correctly-based
figure for "Stencil-24K's end-to-end pipelining ceiling." It should be presented as such in
Section VI, retiring the original 7.86% figure to a footnote (explicitly labeled
kernel-loop-time-based) or dropping it — not blended into the same table without the
distinction, per `GATE_T3_REPORT.md` Section 6's own caveat, which this report now explains
rather than merely flags.
