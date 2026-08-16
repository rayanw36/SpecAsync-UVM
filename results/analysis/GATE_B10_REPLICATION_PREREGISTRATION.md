# Gate B10 Replication + Crossover Fill: Pre-Registration

Written and committed **before** this session's run executes, covering both
Task C (replicate B10's iters=20 result) and Task D (fill iters={8,12,16}
to characterize the crossover), which run together in one fresh-boot,
headless session per the brief.

## 1. Why this runs

`GATE_B10_AUGMENTATION.md`'s entire positive claim (augmentation helps under
oversubscription) rests on a single point: C4 vs C0 at iters=20, -36.03%,
Cohen's d=-70.42. That report itself flagged this for independent
reproduction before being promoted from "this session's finding" to "the
project's claim." This session does that, and additionally fills
iters={8,12,16} to characterize whether the sign flip between iters=5
(+30.91%, C4 slower) and iters=20 (-36.03%, C4 faster) is a smooth
monotonic crossing (supports the residency-accumulation mechanism
`GATE_B10_AUGMENTATION.md` Section 3 argues for) or a discontinuous jump
(would be a reason to suspect an artifact rather than a real mechanism).

## 2. Protocol

- Benchmark: `bench_stencil_oversub`, N=48000 (unchanged from B10).
- Arms: C0 (policy=0, depth=0, prefetch=1) and C4 (policy=4, depth=1,
  prefetch=1) only -- unchanged definitions from B10.
- `iters` in {8, 12, 16, 20} -- 20 is the replication point; 8/12/16 fill
  the gap between B10's tested 5 and 20.
- n = 10 kept reps/arm/iters (matches B10 exactly), 1 warm-up rotation +
  10 kept = 11 rotations/iters value.
- **New interleaving seed** (the brief's explicit requirement): B10's
  harness (`tests/t_b10_c0_vs_c4.sh`) always ran `C0` then `C4` within every
  rotation -- a fixed order, not actually randomized, so "interleaved" there
  meant "alternating," not "order-randomized." This session's harness
  (`tests/t_b10c_replication_crossover.sh`) draws the within-rotation order
  from a seeded PRNG (`RANDOM_SEED=20260816`, recorded here and in the run
  log; bash `RANDOM` reseeded from it at script start) and logs the realized
  order per rotation to the CSV (`order` column) -- so the order is both
  genuinely randomized and independently auditable after the fact, not just
  claimed.
- Module reload before every run, verified via `verify_module_reload`.
  `specasync_clear` called explicitly before every rep (on top of the
  reload-per-rep design that already zeroes the atomics/rings).
- Fresh oracle trace collected per `iters` value (not reused across values
  or from B10's session).
- `setarch -R` for both arms.
- Fresh reboot, headless (`multi-user.target`) for the full session, per the
  brief -- matching B10's own launch conditions exactly (B10 also ran on a
  freshly-booted, headless system).
- srcversion: `4488C9F6F75570BB2FB34F8` (unchanged from B10), confirmed via
  `modinfo` before launch.

## 3. Statistic and test of record

Unchanged from every prior gate in this project: **median** is the
statistic of record; **Mann-Whitney U, two-sided** is the test of record
(`PREREGISTRATION.md` Sections 4-5).

## 4. Comparison family and correction

**Family, enumerated in advance (4 comparisons, all primary):**

1. C4 vs C0, iters=8
2. C4 vs C0, iters=12
3. C4 vs C0, iters=16
4. C4 vs C0, iters=20 (Task C's replication point)

**Family size = 4.** Holm-Bonferroni step-down exactly as every prior gate:
sort the four MWU p-values ascending, compare the k-th smallest to
alpha/(4-k+1). The iters=20 replication point is included in the SAME
family as the three new crossover points, not treated as a separate,
unprotected test -- it is exactly as much a hypothesis test as the other
three, and gets exactly the same correction discipline.

## 5. Minimum detectable effect (MDE) at n=10, from B10's own observed variance

Computed via the same noncentral-t two-sample power calculation as
`GATE_B10_PREREGISTRATION.md` (df=18, power=0.80), but this time using
**B10's own n=10 C0/C4 data** (`results/analysis/gate_b10_augmentation/
t_b10_c0_vs_c4_times.csv`) directly, not an older sweep, at the most
conservative Holm step for a 4-comparison family (alpha/4 = 0.0125,
two-sided): **required Cohen's d = 1.638**.

| iters | source | conservative CV (max of C0/C4 observed) | **MDE at n=10** |
|---|---|---|---|
| 20 | B10's own iters=20 cell (this is the replication point) | 1.130% (C4) | **1.85%** |
| 8, 12, 16 | untested by B10 -- no direct variance estimate exists. Conservative prior: the LARGEST CV B10 observed anywhere (C4, iters=5, 1.523%) | 1.523% | **2.49%** |

**Stated before running, as required:** at n=10/arm, iters=20's replication
is well-powered to detect anything at or above ~1.85% -- the -36.03%
original effect is roughly 19x this MDE, so if the true effect is anywhere
near the original magnitude, this run will detect it decisively; a
non-replication at this power is a real null, not an underpowered
non-result. The 8/12/16 MDE (2.49%) is a conservative estimate borrowed
from the noisiest point B10 measured (iters=5), since no direct prior
exists for these untested values; if variance at these points turns out
smaller (as iters=20's own 1.130% CV suggests is plausible), the true MDE
there will be smaller than stated, never larger -- this estimate errs
toward being pessimistic, not optimistic.

## 6. Falsification trigger (Task C)

**Task C's question is binary and pre-specified:** does C4 vs C0 at
iters=20 reproduce a statistically significant (Holm-corrected within the
4-comparison family) AND practically significant (magnitude exceeding the
1.85% MDE) advantage for C4, in the SAME direction as B10 (C4 faster)?

- **Reproduces**: significant, C4 faster, magnitude exceeds MDE. Report the
  magnitude alongside the original -36.03% for direct comparison.
- **Does not reproduce**: null, wrong direction, or below MDE. **This IS the
  result and is reported as such, not explained away or re-run under
  different conditions to chase significance.** Per the brief's explicit
  instruction: a failure to reproduce is itself the finding.

## 7. Task D question: smooth crossover or discontinuity?

With four points (8, 12, 16, 20) plus B10's own five (1, 3, 5, 10, 20 --
note iters=20 is shared/replicated across both datasets), the %Δ(C4 vs C0)
curve as a function of iters is inspected for: (a) monotonicity of the
trend between the last known-negative point (iters=5 or iters=8/12/16,
whichever are negative) and the last known-positive point: a smooth,
monotonic crossing supports the residency-accumulation mechanism argued in
`GATE_B10_AUGMENTATION.md` Section 3; (b) any single-point discontinuity
(a jump inconsistent with the neighboring points' trend) is a flag for a
possible artifact at that specific point, not folded into the mechanism
narrative without a follow-up check. The break-even iteration count
(%Δ=0 crossing) is estimated by linear interpolation between the two
adjacent measured points that bracket the sign change, reported as a range
determined by the measured points, not extrapolated beyond them.

## 8. Scope

5070-Ti-only, oversubscription-only (N=48000, ~1.078x VRAM). No claim about
other iteration ranges outside {1,3,5,8,10,12,16,20} (the union of B10's and
this session's tested points) or other hardware.

## 9. Memory budget

72 reloads (Task C+D combined: 4 iters values x (2 oracle-trace reloads + 22
run reloads) = 4 x 24 = 96 reloads) x ~230-250MB/reload (the rate B10's own
session observed, `GATE_B10_AUGMENTATION.md` Section 2) ~ 22-24GB projected
leak. Starting from a fresh headless boot (~58-60GB typical, confirmed at
launch), this leaves a comfortable margin above the 6GiB abort floor. Logged
per-run in the CSV (`mem_avail_before_kb`/`mem_avail_after_kb`), same
convention as every prior harness this project uses.

## 10. Recorded, not acted on: a consequence for hit-rate-based claims

The brief flags, for the record only (no document edits): B10's mechanism
argument (`GATE_B10_AUGMENTATION.md` Section 3) implies `spec_hits`
systematically undercounts successful speculation -- it only increments when
a demand fault *occurs* and finds pending/completed speculative work
already in the hit table, i.e. it counts near-misses where speculation
almost-but-not-quite avoided the fault, not full wins where speculation
completed early enough that no fault occurred at all. If this is right,
every hit-rate-based *mechanistic* claim in `GATE_T4_REPORT.md`,
`GATE_A1_REPORT.md`, and `GATE_B6_TASK2_A1_REPLICATION.md` needs re-reading
against this possibility -- those reports' wall-clock findings are
unaffected (wall-clock doesn't depend on how hits are counted), but any
sentence that reasons from "hit rate is near-zero, therefore speculation
essentially never helps" may be conflating "rarely wins the race in a way
this counter can see" with "rarely helps at all." **This is flagged as a
consequence requiring review, not corrected here** -- none of those three
documents are edited by this session.
