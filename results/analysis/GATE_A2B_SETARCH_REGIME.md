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

*(Results appended below after the run.)*
