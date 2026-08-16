# Gate B10 Replication (Task C) and Crossover Fill (Task D)

Pre-registered in `GATE_B10_REPLICATION_PREREGISTRATION.md` before this ran.
Platform: RTX 5070 Ti, sm_120, driver 595.84, srcversion
`4488C9F6F75570BB2FB34F8` (unchanged from B10), confirmed uniform across all
96 reloads of this run. Fresh reboot, headless, new randomized interleaving
seed (`RANDOM_SEED=20260816`, per-rotation C0/C4 order logged and audited --
46 `C0first` / 42 `C4first` rotations realized, not a fixed alternation).
5070-Ti-only, oversubscription-only scope, same as every other B9/B10 result.

## Task C verdict: iters=20 REPRODUCES

| | median (s) | %Δ (C4 vs C0) | MWU p | Holm-sig | Cohen's d |
|---|---|---|---|---|---|
| B10 original (2026-08-16, earlier session) | C0=27.185, C4=17.390 | **-36.03%** | 0.000176 | YES | -70.42 |
| This replication (fresh reboot, new seed) | C0=27.175, C4=17.410 | **-35.93%** | 0.000180 | YES | -71.87 |

**The effect reproduces almost exactly** -- -35.93% against the original
-36.03%, a 0.10-percentage-point difference, well inside any reasonable
run-to-run tolerance and enormously beyond the pre-registered 1.85% MDE.
Both C0 and C4's absolute medians individually reproduce to within 0.01-0.02s
of the original session. This is not a marginal or borderline replication --
it is as clean a reproduction as this project has produced for any result.
**Per the pre-registered trigger (Section 6): reproduces, same direction,
magnitude within noise of the original.**

## Task D: the crossover is NOT a smooth monotonic curve

| iters | source | n/arm | C0 median (s) | C4 median (s) | %Δ (C4 vs C0) | MWU p | Holm-sig | Cohen's d |
|---|---|---|---|---|---|---|---|---|
| 1  | B10 | 10 | 3.230  | 3.370  | **+4.33%**  | 1.49e-4 | YES | 12.57  |
| 5  | B10 | 10 | 8.265  | 10.820 | **+30.91%** | 1.68e-4 | YES | 21.73  |
| 8  | this session | 10 | 12.050 | 8.965  | **-25.60%** | 1.61e-4 | YES | -34.92 |
| 12 | this session | 10 | 17.085 | 19.520 | **+14.25%** | 1.70e-4 | YES | 20.05  |
| 16 | this session | 10 | 22.105 | 23.030 | **+4.18%**  | 1.76e-4 | YES | 7.94   |
| 20 | this session (replication) | 10 | 27.175 | 17.410 | **-35.93%** | 1.80e-4 | YES | -71.87 |

All 4 of this session's comparisons are Holm-significant within the
pre-registered 4-comparison family (each p far below its Holm threshold),
and all 4 magnitudes are far beyond their pre-registered MDE (2.49% for
8/12/16, 1.85% for 20). **These are not noisy or marginal measurements** --
per-rep wall-clock values within every cell are tight and non-overlapping
between arms (checked explicitly, e.g. iters=12: C0 in [17.07, 17.11], C4 in
[19.24, 19.79], zero overlap across all 10x10 pairs), matching the same data
quality as every other cell in this project.

**Reading all six points together: the sign of %Δ flips three times across
the tested range**, not once:

1. iters=5 (+30.91%) -> iters=8 (-25.60%): crosses negative. Interpolated
   break-even **~iters=6.6**.
2. iters=8 (-25.60%) -> iters=12 (+14.25%): crosses back positive.
   Interpolated break-even **~iters=10.6**.
3. iters=16 (+4.18%) -> iters=20 (-35.93%): crosses negative again.
   Interpolated break-even **~iters=16.4**.

(iters=12 -> iters=16 does not cross -- both positive, shrinking from
+14.25% to +4.18%.)

**This is neither the smooth monotonic crossing the residency-accumulation
mechanism in `GATE_B10_AUGMENTATION.md` Section 3 predicts, nor a single
discontinuous jump.** It is an oscillation with at least three sign changes
across iters=1-20. The brief's framing ("a smooth curve supports the
mechanism; a jump is a reason to look for an artifact") anticipated one of
two outcomes; what was measured is a third: multiple alternating crossings,
each individually as statistically decisive as the original iters=20 result.

### Checks performed against a data-quality or scripting artifact (all clean)

Per this project's standing practice of scrutinizing surprising results
before reporting them as findings, the following were checked -- none found
an anomaly:

- **Per-rep tightness**: every cell's 10 kept reps are tight and
  non-overlapping between arms (no bimodality, no drift with run order
  within a cell, checked for all 4 new iters values).
- **Oracle trace distinctness**: all 4 traces collected this session have
  distinct md5sums (no accidental reuse across iters values) and are each
  at the trace ring's full 1,048,576-entry capacity (expected for this
  workload, not an error).
- **Atomics coherence**: `demand_faults` for C4 is itself non-monotonic in
  iters (5.5M at 8, 12.9M at 12, 16.7M at 16, 11.3M at 20) while C0's
  `demand_faults` is purely linear in iters throughout (8.9M, 13.3M, 17.7M,
  22.2M) -- the non-monotonicity is specific to the speculative arm and
  tracks the wall-clock oscillation's shape, not a flat or garbage signal.
  `drops` follows the same non-monotonic shape (299K, 7.5M, 12.2M, 7.2M).
  This is consistent with a real interaction between speculation and the
  oversubscription eviction dynamics that itself varies non-monotonically
  with iteration count, not with a corrupted or mismatched dataset.
- **Run integrity**: 88/88 rows, zero watchdog fires, single srcversion
  throughout, randomized interleaving order realized as logged (46/42
  split) with no visible order-dependent effect within any cell.

**None of these checks found an artifact. The oscillation is reported as a
genuine, reproducible-within-this-session measurement, with its mechanism
unexplained** -- this report does not offer a causal story for why the
effect alternates sign three times, and does not extend the
residency-accumulation narrative to cover it. That narrative explained a
single crossing; it does not, as written, explain three.

## Atomic counters (median across 10 kept reps, this session's 4 new iters)

| config | iters | demand_faults | spec_hits | spec_hit_rate | spec_migrations | drops |
|---|---|---|---|---|---|---|
| C0 | 8  | 8,877,089  | 0 | 0.0000% | 0 | 0 |
| C0 | 12 | 13,312,036 | 0 | 0.0000% | 0 | 0 |
| C0 | 16 | 17,726,063 | 0 | 0.0000% | 0 | 0 |
| C0 | 20 | 22,188,388 | 0 | 0.0000% | 0 | 0 |
| C4 | 8  | 5,549,156  | 0    | 0.0000% | 5,251,667 | 299,302 |
| C4 | 12 | 12,857,574 | 1094 | 0.0203% | 5,327,690 | 7,465,950 |
| C4 | 16 | 16,724,754 | 0    | 0.0000% | 4,390,541 | 12,229,388 |
| C4 | 20 | 11,330,794 | 1667 | 0.0406% | 4,045,096 | 7,227,130 |

`spec_hits` stays at or near zero throughout (0-0.04%), same regime as B10 --
consistent with B10's finding that this counter does not track the real
driver of the wall-clock effect (see the recorded-not-acted-on note below).
The wall-clock winner at iters=8 (C4, -25.60%) has the *lowest* `spec_hits`
(0) and *lowest* `drops` (299K) of the four new cells -- the opposite of
what "more speculative activity survives to matter" would predict if
`spec_hits` or `drops` alone explained the pattern. Demand-fault suppression
(C4's `demand_faults` vs C0's, same-iters) is the more consistent signal:
iters=8 shows the largest relative suppression (5.5M vs 8.9M, C4 is 37.5%
lower) of any of the four points, coinciding with C4's largest relative
wall-clock win among 8/12/16 -- but iters=20's even larger wall-clock win
(-35.93%) does NOT have the largest relative fault suppression (11.3M vs
22.2M, 49.0% lower, second-largest not first -- iters=8 edges it out on
relative terms though not absolute faults avoided). No single atomic counter
here cleanly tracks the wall-clock oscillation's shape end to end.

## Recorded, not acted on: `spec_hits` undercounting consequence

Per the brief, flagged here for the record, no other document is edited:
B10's mechanism argument implies `spec_hits` systematically undercounts
successful speculation -- it only increments when a demand fault *occurs*
and finds pending/completed speculative work already in the hit table (a
near-miss), not when speculation completes early enough that no fault
occurs at all (a full win, invisible to this counter). This session's data
is consistent with that reading: `spec_hits` is 0 or near-0 at every one of
the four new cells regardless of whether C4 wins or loses the wall-clock
comparison at that cell, so it cannot be the explanatory variable for either
this report's oscillation or B10's original crossover. **If correct, every
hit-rate-based mechanistic claim in `GATE_T4_REPORT.md`, `GATE_A1_REPORT.md`,
and `GATE_B6_TASK2_A1_REPLICATION.md` needs re-reading against this
possibility** -- their wall-clock findings are unaffected, but any sentence
reasoning from "hit rate is near-zero, therefore speculation essentially
never helps" may conflate "rarely wins the race in a way this counter can
see" with "rarely helps at all." Flagged as a consequence requiring review.
None of those three documents, `CLAIM_SCOPE.md`, or `PREREGISTRATION.md` are
edited by this report.

## Scope

5070-Ti-only, oversubscription-only (N=48000, ~1.078x VRAM). The combined
dataset now covers iters in {1, 3, 5, 8, 10, 12, 16, 20} across B9/B10/this
session (not a uniform grid); no claim is made about iters values outside
this set, or about whether the oscillation continues, dampens, or changes
character beyond iters=20.

## Artifacts

- `results/analysis/gate_b10_replication/t_b10c_replication_crossover_times.csv`
  -- raw per-run data (88 rows, all phases, all 6 atomic counters, realized
  interleaving order per rotation).
- `results/analysis/gate_b10_replication/t_b10c_aggregate_comparison.csv` --
  per-iters median/MWU/Holm/Cohen's-d table (this session's 4 points).
- `results/analysis/gate_b10_replication/t_b10c_atomics_summary.csv` --
  per-cell median atomic counters.
- `results/analysis/gate_b10_replication/t_b10c_analyze.py` -- analysis
  script.
- `tests/t_b10c_replication_crossover.sh` -- the harness (seeded randomized
  interleaving order, logged per rotation).
- Raw oracle-trace `.bin` files and per-run telemetry markers are
  `.gitignore`d, consistent with every prior B9/B10 raw-telemetry artifact.
