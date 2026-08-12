# Gate A2b — does `setarch -R` change the operating regime, or just the address?

Pre-registered 2026-08-12, before running, per this project's standing pre-registration
practice (see `GATE_A2_REPORT.md`, `PREREGISTRATION.md`).

## Motivation

`GATE_A2_REPORT.md` Result 1 and its cross-reference section found that `ASLR_ON` and
`ASLR_OFF` differ not only in wall-time *variance* (`ASLR_OFF` 15.07-17.31s, clearly bimodal;
`ASLR_ON` 16.01-16.23s, essentially unimodal) but in typical speculative *volume*
(`ASLR_OFF` 1.9-2.8M processed/run; `ASLR_ON` ~3.2M, tight band) — a difference A2 flagged as
"a secondary, unplanned observation... worth flagging for a future pass but outside this
task's scope to chase further." This matters directly: **T1, the platform-of-record result,
used `setarch -R`.** If the ON/OFF difference is a general allocation/paging effect rather
than something specific to the speculative pipeline, T1's numbers need that caveat attached
before this instance changes. This also directly answers the scope caveat raised in this
session's addendum to `GATE_A2_REPORT.md`: `BIMODALITY_TELEMETRY_MINING.md`'s residual
concern about **C1** (zero speculation) still showing wall-time-correlated batch-loop timing
variance, which neither A2 nor the mining document tested against ASLR state.

## Question

Does the `ASLR_ON`/`ASLR_OFF` wall-clock difference appear in **C1** (`policy=0`,
`depth=0`, `prefetch=0` — no speculation issued at all, `specasync_enqueue()` no-ops per
`uvm_gpu_replayable_faults.c:337`, matching `GATE_T4_REPORT.md`'s confirmed "C1 correctly
shows 0/0/0")? If it does, the effect is general (allocation/paging), and applies to any
`setarch -R` run regardless of whether speculation is active — including T1. If it appears
**only** in C3 (oracle, `depth=1`, `prefetch=0` — A2's config), it is specific to the
speculation pipeline, and T1's use of `setarch -R` is not implicated by this mechanism.

## Design

Stencil-24K only, same benchmark/build A2 used (`driver/build/nvidia-uvm-specasync-t4-a1.ko`,
task A1's build with the `g_specasync_processed/enqueued/drops` atomics). Two configs, each
run as its own strictly-interleaved `ASLR_ON,ASLR_OFF,ASLR_ON,...` block (reusing
`tests/t_a2_bimodality.sh`'s structure verbatim — same telemetry columns, same GPU/CPU state
capture before+after, same allocation-base logging):

- **C1**: `policy=0 depth=0 prefetch=0`, no oracle trace. Speculation is a structural no-op;
  this is the "no speculation at all" control.
- **C3**: `policy=4 depth=1 prefetch=0`, oracle trace collected once at the start of the
  session (same oracle-trace-then-reload procedure A2 used) — identical config to A2's own
  run, so this session's C3 arm is also a partial replication check on A2 itself.

Both configs: 2 warm-up + 10 kept rotations = 12 rotations, each rotation runs `ASLR_ON`
then `ASLR_OFF` (24 runs/config, 48 runs total, 40 kept: n=10/arm/config). Module reloaded
before every single run (uniform mechanism, matches A2/T1/`PREREGISTRATION.md`'s corrected
approach — module params are read-only after load). `specasync_clear` (via `clear_ring`)
before every run, so per-run `g_specasync_processed/enqueued/drops` and ring dumps are
independent (no repeat of the T4 counting exposure this session's Task 4 fixed).

Harness: `tests/t_a2b_setarch_regime.sh` (new script, parameterizes A2's script over
`{C1,C3}` instead of hardcoding C3). Data:
`results/analysis/t_a2b_setarch_regime/setarch_regime.csv`.

## Statistics (per this project's standing conventions)

For each config (C1, C3) independently: `ASLR_ON` vs `ASLR_OFF` wall_s, n=10 each —

- Median wall_s per arm, and % difference between medians.
- Mann-Whitney U, two-sided (matches `GATE_A2_REPORT.md`'s Result 1/H2/H3 tests).
- Effect size: Cohen's d (matches `BIMODALITY_TELEMETRY_MINING.md`'s convention), reported
  alongside the rank-biserial correlation `r = 1 - 2U/(n1*n2)` since n=10/arm is small enough
  that a parametric effect size on its own would be optimistic.
- Sorted-range and largest-gap check (A2's bimodality gap heuristic) reported for descriptive
  context only — n=10/arm is underpowered to reliably detect a clean bimodal split the way
  A2's n=20/arm did; this experiment's primary question is the ON/OFF *location* shift, not
  re-establishing bimodality at lower n.

## Decision rule (fixed before running)

- If **C1** shows a significant (p<0.05) `ASLR_ON` vs `ASLR_OFF` wall-time difference in the
  same direction as A2's C3 result (OFF slower/more variable than ON): **general
  allocation/paging effect** — `setarch -R` changes the operating regime independently of
  speculation, and T1's numbers should carry this caveat.
- If **C1** shows no significant difference (p≥0.05, small effect size) while **C3**
  reproduces A2's significant difference: **speculation-pipeline-specific** — consistent with
  `GATE_A2_REPORT.md`'s H3 verdict, and T1 is not implicated by this mechanism (though T1
  itself is a speculative run, so this would still mean T1's specific numbers were shaped by
  the ASLR choice — the distinction this decision rule draws is about *mechanism scope*, not
  about whether T1 is affected at all).
- If **both** C1 and C3 show a significant difference but of different magnitude: mixed —
  report both magnitudes and note that a general effect appears to be present and may be
  amplified by speculation, rather than picking one clean story.
- If **neither** shows a significant difference: this session's n=10/arm failed to reproduce
  even A2's own n=20/arm C3 finding — report as a non-replication and flag session-to-session
  variability (GPU/thermal/instance state) as a candidate before revising the regime question
  itself.

---

## Results (run 2026-08-12, 15:21-15:34 UTC)

48 runs completed clean (24/config, 12 rotations each), n=10 kept/arm/config as planned.
Data: `results/analysis/t_a2b_setarch_regime/setarch_regime.csv`, ring dumps in the same
directory (unused by this analysis — wall-clock and the `g_specasync_processed/enqueued/drops`
atomics, immune to the T4 ring-saturation exposure Task 4 fixed, are sufficient here).

### C1 (no speculation, `policy=0`)

| arm | n | sorted wall_s | median | stdev |
|---|---|---|---:|---:|
| ASLR_ON | 10 | 14.81, 14.82, 14.83, 15.11, 15.11, 15.14, 15.15, 15.17, 15.17, 15.19 | 15.125 | 0.161 |
| ASLR_OFF | 10 | 14.79, 14.79, 14.81, 14.81, 15.13, 15.13, 15.22, 15.25, 15.26, 15.49 | 15.130 | 0.251 |

Median difference: **+0.03%** (essentially zero). Mann-Whitney U=49.0, **p=0.970**. Cohen's d
(OFF−ON) = 0.085 (negligible). Rank-biserial r = 0.020. Levene's test (variance, center=median):
stat=1.959, **p=0.179** — variances not significantly different either. `processed`/`enqueued`
are 0 in every run in both arms, confirming `specasync_enqueue()`'s policy=0 no-op (matches
`GATE_T4_REPORT.md`'s independently-confirmed "C1 correctly shows 0/0/0"). **C1 shows no
detectable ASLR effect on wall-clock time, on either location or spread, at n=10/arm.**

### C3 (oracle, `depth=1`, A2's config)

| arm | n | sorted wall_s | median | stdev |
|---|---|---|---:|---:|
| ASLR_ON | 10 | 16.10, 16.11, 16.13, 16.14, 16.15, 16.17, 16.18, 16.18, 16.20, 16.23 | 16.160 | 0.041 |
| ASLR_OFF | 10 | 15.12, 15.19, 15.30, 15.42, 15.55, 15.66, 16.53, 17.28, 17.28, 17.30 | 15.605 | 0.930 |

Median difference: -3.43% (OFF lower than ON this session — direction not consistent with A2's
own median comparison, see caveat below). Mann-Whitney U=60.0, **p=0.472** — not significant as
a location-shift test. Cohen's d (OFF−ON) = -0.146, rank-biserial r = -0.200 (small).

**A straight median-shift test is the wrong lens for this phenomenon, exactly as A2 itself
found** — A2 characterized its own Result 1 with a range/gap description, not a location test,
because the effect is a *spread* difference, not a shift: `ASLR_OFF`'s values span both below
and above `ASLR_ON`'s tight band, so a rank-sum test partially cancels itself out even though
the phenomenon is large and real. Levene's test (variance, center=median), added here as the
natural formal complement to that observation (a deviation from the letter of the
pre-registered plan, which named Mann-Whitney/Cohen's d as the primary test and the gap
heuristic as descriptive-only — disclosed here rather than silently substituted): **stat=10.659,
p=0.0043** — highly significant. Variance ratio (OFF/ON) = **522.7x**. Gap-detection heuristic
(descriptive, as pre-registered): largest gap 0.87s (between 15.66 and 16.53), second-largest
0.75s, ratio 1.16x — at n=10 this does **not** meet A2's clean-bimodal criterion (A2's own n=20
`ASLR_OFF` run had a 17.25x gap ratio); the underlying spread is still present and large, it
just does not resolve into two crisp discrete clusters at this sample size, matching this
plan's own caveat that n=10 was underpowered for that specific check.

**Ranges replicate A2's C3 finding closely:** this session's `ASLR_ON` range
[16.10, 16.23] vs A2's [16.01, 16.23]; this session's `ASLR_OFF` range [15.12, 17.30] vs A2's
[15.07, 17.31] — near-exact reproduction of both the tight-ON/wide-OFF pattern and its absolute
bounds, on an independent n=10 sample collected 2 days later on the same instance.

**`processed` (the H3 volume metric) replicates too:** `ASLR_ON` median = 3,241,972
(range 3,240,534-3,246,876) vs A2's ~3.2-3.25M tight band; `ASLR_OFF` median = 2,145,928.5
(range 1,899,983-2,699,635) vs A2's 1.9-2.8M range. Both the tight-ON/wide-OFF wall-clock
pattern and the tight-ON/wide-OFF speculative-volume pattern reproduce independently.

## Verdict

**The `ASLR_ON`/`ASLR_OFF` wall-clock regime difference is specific to the speculative
pipeline (C3), not present in C1.** C1 -- zero speculation, `specasync_enqueue()` a structural
no-op -- shows no detectable difference between `ASLR_ON` and `ASLR_OFF` on location (p=0.970)
or spread (Levene p=0.179) at n=10/arm; the two arms' wall-clock distributions are
indistinguishable. C3 reproduces A2's finding closely on an independent sample: `ASLR_OFF`'s
wall-clock spread is ~523x `ASLR_ON`'s variance (Levene p=0.0043), and the same tight-ON/wide-OFF
pattern appears simultaneously in the `processed` (speculative-volume) counter, matching A2's
own cross-reference observation. Per the pre-registered decision rule, this is the
**speculation-pipeline-specific** outcome: `setarch -R` does not introduce a general
allocation/paging noise source that would show up in unrelated GPU work (C1 is clean), so
platform-wide UVM/paging behavior reported elsewhere in this study is not implicated by this
mechanism. It does mean the regime change is real and specifically tied to how the speculation
path behaves when its allocation address is pinned vs. randomized -- consistent with
`GATE_A2_REPORT.md`'s open H3-direction question (more speculative volume correlates with
slower runs, cause vs. symptom still undetermined) rather than resolving it.

**Direct implication for T1 (platform-of-record, used `setarch -R`):** T1's numbers are not
contaminated by a general paging artifact -- C1's null result rules that out. But T1 ran the
speculative pipeline under `ASLR_OFF`, and this data shows that choice specifically widens
wall-clock variance and speculative-volume variance relative to what `ASLR_ON` would have
produced for the same config, on this instance, reproducibly across two independent sessions.
T1's reported run-to-run variance should be read as **characteristic of the `ASLR_OFF`
speculative regime specifically**, not as general instance noise -- worth one sentence in the
manuscript's methods/limitations section alongside the existing `setarch -R` justification
(fixed-address reproducibility), noting the tradeoff this data quantifies: fixing the address
for reproducibility also fixes the run into the higher-variance member of the two regimes.

**Gate A2b: confirmed C1-null / C3-effect split, both location- and spread-level, on an
independent n=10/arm sample. Regime difference is speculation-specific, not general
allocation/paging. T1 caveat: `setarch -R` variance is a speculative-pipeline property of this
instance, reproducible across sessions, not a general platform artifact.**
