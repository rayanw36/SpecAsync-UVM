# Gate B10: Does Speculation Help ON TOP of the Prefetcher Under Oversubscription?

Pre-registered in `GATE_B10_PREREGISTRATION.md` before this ran. Platform:
RTX 5070 Ti, sm_120, driver 595.84, srcversion `4488C9F6F75570BB2FB34F8`
(the atomics build, confirmed uniform across all 72 reloads of this run --
see Section 3). **5070-Ti-only, oversubscription-only scope**, same as every
other B9/B10 result on this platform.

## 1. Verdict against the pre-registered trigger

**The trigger fires at iters=20.** C4 (oracle speculation, `depth=1`, stock
prefetcher **on**) is statistically significantly (Holm-corrected) *and*
practically (far beyond the pre-registered MDE) **faster** than C0 (stock
prefetcher alone) at iters=20. This is a genuine, well-powered positive
result for augmentation -- not a weak positive, not hedged.

**The trigger does not fire at iters=1 or iters=5.** At both points C4 is
statistically significantly *and* practically **slower** than C0 -- the
opposite of the trigger direction. These are not nulls; they are clean
negative results against augmentation at low iteration counts.

| iters | n/arm | C0 median (s) | C4 median (s) | %Δ (C4 vs C0) | MWU p | Holm threshold | Holm-sig | Cohen's d | pre-reg MDE |
|---|---|---|---|---|---|---|---|---|---|
| 1  | 10 | 3.230  | 3.370  | **+4.33%** (C4 slower) | 0.000149 | 0.01667 | YES | 12.57  | 3.9%  |
| 5  | 10 | 8.265  | 10.820 | **+30.91%** (C4 slower) | 0.000168 | 0.02500 | YES | 21.73  | 5.6%  |
| 20 | 10 | 27.185 | 17.390 | **-36.03%** (C4 faster) | 0.000176 | 0.05000 | YES | -70.42 | 0.13% |

All three comparisons are Holm-significant (each p far below its Holm
threshold). At iters=1 and iters=5, the effect exceeds its pre-registered
MDE but in the direction of harm. At iters=20, the effect (-36.03%) exceeds
even the least reliable, most optimistic MDE estimate (0.13%, flagged in the
pre-registration as an unreliable lower bound) by two orders of magnitude --
there is no plausible MDE-based objection to calling this real.

**Reading the three points together: this is a crossover, not a uniform
answer.** Augmentation is a net loss at low iteration counts and a
substantial net win at high iteration counts, under oversubscription. Which
regime a real workload falls into determines whether adding speculation on
top of the prefetcher helps or hurts.

## 2. Run integrity

- 66/66 rows present (11 rotations x 2 arms x 3 iters values), zero
  watchdog fires, zero incomplete rows.
- Single srcversion (`4488C9F6F75570BB2FB34F8`) across every one of the 72
  reloads (66 run reloads + 6 oracle-trace-collection reloads, 2 per iters
  value) -- verified via `verify_module_reload` at every reload, not just
  attempted.
- Per-cell wall-clock values are tight and non-overlapping between arms at
  every iters value (e.g. iters=20: C0 in [27.15, 27.21], C4 in
  [16.93, 17.57] -- zero overlap across all 10x10 pairs). No drift across
  run order within a cell (ruling out thermal throttling or progressive
  leak contamination as an explanation for the iters=20 win -- if leak
  pressure were inflating C4's apparent speed, later-in-block reps would
  trend faster or slower than earlier ones; they don't).
- `specasync_clear` called explicitly before every rep, on top of the
  per-rep module reload that already zeroes the rings/atomics as a side
  effect -- no residual-state ambiguity between reps.
- Memory: 58.34 GiB available at launch (fresh boot, headless) -> 41.90 GiB
  at completion, a clean, monotonic, ~234 MB/reload decline across all 72
  reloads -- in line with the historical ~244 MB/reload estimate
  (`HOST_MEMORY_LEAK_5070TI.md`). Never approached the 6 GiB abort floor;
  no abort, no retry.
- Oracle trace collected fresh per iters value (not reused): 3 trace files,
  each exactly 8,388,608 bytes = 1,048,576 entries = the full trace ring
  capacity (expected for this ring's true-circular-overwrite design, not an
  error).

Nothing in the run-integrity checks available without new data collection
points to a measurement artifact. The iters=20 result is large, clean, and
reproducible within this session.

## 3. Mechanism: the diagnostic in Section 10 of the pre-registration was
   the wrong question

The pre-registration asked whether C4's `spec_hits` would rise materially
above C3's ~0.0025% rate. It does not, meaningfully:

| config | iters | median processed=enqueued | median drops | median demand_faults | median spec_hits | spec_hit_rate | median spec_migrations |
|---|---|---|---|---|---|---|---|
| C0 | 1  | 0 | 0 | 1,102,370 | 0 | 0.0000% | 0 |
| C0 | 5  | 0 | 0 | 5,534,845 | 0 | 0.0000% | 0 |
| C0 | 20 | 0 | 0 | 22,176,986 | 0 | 0.0000% | 0 |
| C4 | 1  | 1,000,777 | 105,035 | 1,106,449 | 0 | 0.0000% | 1,000,777 |
| C4 | 5  | 1,189,902 | 4,026,170 | 5,219,138 | 0 | 0.0000% | 1,163,810 |
| C4 | 20 | 4,382,092 | 6,920,713 | 11,302,805 | **1,289** | **0.0294%** | 4,324,711 |

`spec_hits` stays at 0 (median) at iters=1 and iters=5, and only reaches a
still-negligible 0.0294% at iters=20 -- the same order-of-magnitude-near-zero
regime as C3's ~0.0025%. **`spec_hits` does not explain the iters=20
speedup.** That counter only increments when a demand fault *does* occur and
the fault handler finds a pending/completed speculative migration already in
the hit table -- i.e. it measures a narrow race condition, not "did
speculation help."

**The real driver is visible in `demand_faults` directly:** at iters=20, C4
sees 11,302,805 demand faults against C0's 22,176,986 -- **a 49.0%
reduction**, despite `spec_hits` being nearly zero. The interpretation: when
`spec_migrations` (4,324,711 successful speculative migrations at iters=20)
completes fast enough, the touched page is already resident by the time the
access happens, so **no fault occurs on that page at all** -- not "fault,
then found already in flight" (which `spec_hits` counts), but "no fault, full
stop." This is the intended, best-case behavior of a working prefetcher-like
mechanism, and it is invisible to the counter the pre-registration proposed
to watch for it.

**This mechanism explains the crossover:**

- At iters=1: `spec_migrations` (1,000,777) is comparable in volume to
  `demand_faults` (1,106,449), yet `demand_faults` is *not* reduced relative
  to C0 (1,106,449 vs 1,102,370, essentially flat, +0.4%). One pass through
  the working set gives the speculative migrator no time to get ahead of the
  first-touch fault it would need to preempt -- migrating a page after (or
  barely before) it's already been touched buys nothing. All of the
  enqueue/process/drop cost (105,035 drops) is pure overhead against zero
  fault-avoidance benefit. Net: slower.
- At iters=5: `demand_faults` drops modestly (5,534,845 -> 5,219,138, -5.7%)
  but `drops` grows sharply (4,026,170, the ring saturating hard under 5x
  the fault volume) -- overhead scales faster than the still-small benefit.
  Net: substantially slower.
- At iters=20: `demand_faults` drops by nearly half. Once the workload
  revisits the same working set enough times, pages migrated speculatively
  early stay resident and keep paying off across every subsequent
  iteration -- a cumulative, steady-state benefit, not a one-shot cold-start
  effect. This is the same dose-response shape B9 established for C3-vs-C1
  (benefit growing with iteration count), but here it has to clear a much
  higher bar first: it has to overcome the enqueue/processing/drop overhead
  *and* beat an already-prefetched baseline, not just a crippled one. At
  iters=20 it does, decisively.

## 4. Flagged for follow-up, not acted on here

This result is a genuine positive finding that would narrow the scope of
this project's central negative claim (speculation-as-replacement is a
net loss; speculation-as-augmentation is a net loss at low iteration counts
but a substantial net win at high iteration counts, under oversubscription).
Per this project's standing practice of treating consequential,
narrative-changing results as requiring scrutiny before being written into
scope-defining documents: **`CLAIM_SCOPE.md` and `PREREGISTRATION.md` are
intentionally NOT updated by this report.** Every run-integrity check
available without new data collection came back clean (Section 2), but the
magnitude and the sign-flip both warrant an independent look -- in
particular, confirming the iters=20 result reproduces on a fresh session
(new reboot, new interleaving order) before it is promoted from "this
session's finding" to "the project's claim." This is flagged explicitly for
the user's review, not silently acted on.

## 5. Scope

5070-Ti-only, oversubscription-only (N=48000, ~1.078x VRAM). No claim is
made about non-oversubscribed regimes, other iteration ranges outside
{1,5,20}, or other hardware.

## 6. Artifacts

- `results/analysis/gate_b10_augmentation/t_b10_c0_vs_c4_times.csv` -- raw
  per-run data (66 rows, all kept/warmup phases, all 6 atomic counters).
- `results/analysis/gate_b10_augmentation/t_b10_aggregate_comparison.csv` --
  per-iters median/MWU/Holm/Cohen's-d table (Section 1).
- `results/analysis/gate_b10_augmentation/t_b10_atomics_summary.csv` --
  per-cell median atomic counters (Section 3).
- `results/analysis/gate_b10_augmentation/t_b10_analyze.py` -- analysis
  script that produced both aggregate CSVs from the raw data.
- `tests/t_b10_c0_vs_c4.sh` -- the harness that generated the raw data.
- Raw oracle-trace `.bin` files and per-run telemetry markers are
  `.gitignore`d, consistent with every prior B9/B10 raw-telemetry artifact.
