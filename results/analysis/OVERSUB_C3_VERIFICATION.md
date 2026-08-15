# Verification: does C3's oversubscription speedup survive a stock-baseline comparison?

Platform: RTX 5070 Ti, sm_120 Blackwell, driver 595.84, kernel 7.0.0-28-generic.
srcversion `4488C9F6F75570BB2FB34F8` (post-`GATE_B9_TASK2_REBUILD.md`) for all data in
this report except where the alarm section cites the earlier `9E98EF08CBA769C50A24937`
figures for context. N=48000, ~1.078x this platform's VRAM (16,303 MiB), matching
`OVERSUB_SPEEDUP_VERIFICATION.md`/`GATE_B8_5070TI_REMAINING.md`'s established target.

## The alarm

`GATE_B9_OVERSUB_MECHANISM.md` Task 2b (iteration sweep, C1 vs C3, N=48000, iters in
{1,3,5,10,20}, n=5/arm interleaved) found the C3-vs-C1 wall-clock advantage **grows
monotonically with iteration count**: +4.02% (C3 slower) at iters=1, then -27.87%,
-39.02%, -49.83%, and **-54.00% at iters=20** -- all five comparisons Holm-significant
across the family. This is a large, clean, statistically decisive result, and it fires
`PREREGISTRATION.md`'s primary falsification trigger for this project's central negative
claim ("speculation does not help"). Per standing policy, a result that fires that
trigger gets an independent verification pass before it is believed or acted on, not
acceptance on the strength of clean statistics alone.

## The verification pass

Five checks, run against the existing Task 2b output with no new runs and no
interpretation, before anything was trusted:

1. **Run integrity.** 61 CSV lines (60 data rows), exactly 1 warmup + 5 kept per of 10
   cells (2 configs x 5 iters values), `run_order_idx` contiguous 1-60 with zero
   duplicates or gaps, every inter-row timestamp gap explained by the preceding run's
   own wall_s plus reload overhead, zero `WATCHDOG`/`ABORT` log entries. Clean.
2. **Build provenance.** The run used srcversion `4488C9F6F75570BB2FB34F8`
   (`GATE_B9_TASK2_REBUILD.md`'s three-atomic addition), differing from every prior
   Gate B9 result's `9E98EF08CBA769C50A24937`. `git log --oneline -- driver/src/` shows
   exactly one commit (`e3abb76`) between the two srcversions, and its full diff is
   additive-only: new `atomic_t` declarations, new `debugfs_create_atomic_t` exposure
   calls, new `atomic_set(..., 0)` reset lines for the new atomics only, and
   side-effect-only counter increments inserted alongside existing, value-unchanged
   computations (`wrec.result`'s assignment is byte-identical before/after;
   `_sa_rec.spec_hits`'s accumulated value is identical, just decomposed into a named
   variable). No control flow, no existing value, no function signature changed.
3. **Configuration.** N=48000 (~1.078x VRAM, matches this project's established
   oversubscription target, confirmed via `nvidia-smi` + the benchmark's own reported
   18.43GB grid size), `setarch -R` wraps the measured benchmark invocation for both
   arms (not just oracle-trace collection), `PREFETCH=0` for both C1 and C3 explicitly.
   C1's 16.67s at iters=1 (vs. B5's 4.31s Stencil-24K figure) is a different,
   non-oversubscribed benchmark/size, not a discrepancy -- a linear fit of C1's wall_s
   against iters gives ~9.2s fixed allocation/init cost + ~7.47s/iteration marginal
   cost, predicting iters=10 at 83.9s against an observed 83.69s.
4. **Is C3 actually speculating?** The live module (undisturbed since Task 2b's last
   run, C3/iters=20) showed real, massive speculative activity: 76,983,670
   enqueued/processed, 76,946,704 successful migrations (99.95% success rate), explicit
   hit-table credit only 2,232 (~0.0029%, consistent with the previously-established
   ~0.0019% figure). Per-run counters for the other 59 Task 2b runs were not
   recoverable (the wall-clock-only harness never logged them, and each run's own
   module reload resets the atomics) -- disclosed as a limitation, not papered over.
5. **Arm symmetry.** Only `specasync_policy`/`specasync_offload_depth`/oracle-trace-path
   differ between C1 and C3 in the harness; `PREFETCH=([C1]=0 [C3]=0)` explicitly, and
   `reload_module` passes `uvm_perf_prefetch_enable` as an insmod parameter on every
   single reload (fresh per load, not inherited state) -- live-verified against the
   loaded module.

**Verdict on the five checks: sound.** No integrity, provenance, configuration, or
symmetry defect was found, and the atomics confirmed real (if inefficient) speculative
work. This did **not** debunk the -54% figure -- it confirmed the measurement was real.
What it left open was a different question: real compared to *what*.

## The missing comparison: C1 is not the baseline the paper's claim is about

C1 in this project's naming convention is `policy=0, depth=0, prefetch=0` --
speculation disabled **and** the stock UVM prefetcher disabled. It is a deliberately
crippled configuration, used elsewhere in this project specifically to isolate
speculation's own marginal effect from the driver's existing prefetch heuristic. C0
(`policy=0, depth=0, prefetch=1`) is the stock system: no SpecAsync speculation, driver
prefetch enabled -- the actual baseline this project's negative claim is about. C3-vs-C1
answers "does speculation beat a system with prefetch turned off"; it does not by itself
answer "does speculation beat the system as it actually ships."

## Resolution: C3 loses to C0 at every iters value tested

C0 was added to the iteration sweep, three-way interleaved with C1 and C3 in a single
run (not a separate, non-interleaved rerun, to avoid a between-session confound),
n=5/arm/iters-value, same protocol, same N=48000, iters in {1,3,5,10,20}
(`tests/t_b9_task2c_c0_and_counters.sh`). One watchdog-driven interruption occurred
partway through iters=20 (host-RAM leak accumulated across ~74 reloads, caught and
stopped cleanly per the standing no-retry-lower policy, zero data loss on
already-completed cells) and was resumed after a reboot restored headroom; the merged,
final dataset is 91 rows (75 kept + 16 warmup, one harmless duplicate warmup rep for
C0/iters=20 from the interrupted-then-resumed run, warmup data unused in any statistic)
-- `task2c_c0_threeway_times_MERGED.csv`.

| iters | C0 median (s) | C1 median (s) | C3 median (s) | C3 vs C0 | MWU p (C3 vs C0) | Holm threshold | Holm sig | Cohen's d |
|---:|---:|---:|---:|---:|---:|---:|:---:|---:|
| 1  | 3.310   | 17.290  | 18.120 | **+447.43%** | 0.0079 | 0.0100 | YES | 28.18 |
| 3  | 6.020   | 34.380  | 26.330 | **+337.38%** | 0.0119 | 0.0250 | YES | 45.85 |
| 5  | 8.580   | 48.990  | 32.410 | **+277.74%** | 0.0079 | 0.0125 | YES | 18.99 |
| 10 | 15.730  | 88.760  | 52.040 | **+230.83%** | 0.0079 | 0.0167 | YES | 182.05 |
| 20 | 27.180  | 159.670 | 75.140 | **+176.45%** | 0.0119 | 0.0500 | YES | 43.74 |

**C3 is 1.76x-4.47x slower than C0 at every tested iters value, Holm-significant across
the full 5-value family with no exceptions.** The `PREREGISTRATION.md` primary
falsification trigger does not fire against the practical baseline. C1-vs-C0 is also
Holm-significant at every iters value (full table: `task2c_aggregate_comparison.csv`) --
at iters=20, C1 (159.670s) is **5.87x slower than C0** (27.180s). C1 is a crippled
baseline; beating it is not, by itself, evidence of a real benefit.

## Arm cleanliness (per-run atomic counters, all iters values, all three arms)

| iters | cfg | enqueued (med) | processed (med) | drops (med) | demand_faults (med) | spec_hits (med) | spec_migrations (med) |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1  | C0 | 0 | 0 | 0 | 1,098,046 | 0 | 0 |
| 1  | C1 | 0 | 0 | 0 | 12,526,687 | 0 | 0 |
| 1  | C3 | 10,944,051 | 10,944,051 | 1,678,985 | 12,618,079 | 224 | 10,940,904 |
| 3  | C0 | 0 | 0 | 0 | 3,323,826 | 0 | 0 |
| 3  | C1 | 0 | 0 | 0 | 37,990,336 | 0 | 0 |
| 3  | C3 | 19,909,514 | 19,909,514 | 3,299,595 | 23,221,368 | 481 | 19,901,547 |
| 5  | C0 | 0 | 0 | 0 | 5,542,226 | 0 | 0 |
| 5  | C1 | 0 | 0 | 0 | 61,635,336 | 0 | 0 |
| 5  | C3 | 27,282,830 | 27,282,830 | 4,706,740 | 31,999,020 | 1,175 | 27,269,972 |
| 10 | C0 | 0 | 0 | 0 | 11,090,636 | 0 | 0 |
| 10 | C1 | 0 | 0 | 0 | 123,477,977 | 0 | 0 |
| 10 | C3 | 50,433,943 | 50,433,943 | 8,612,649 | 59,043,611 | 1,530 | 50,404,781 |
| 20 | C0 | 0 | 0 | 0 | 22,184,264 | 0 | 0 |
| 20 | C1 | 0 | 0 | 0 | 237,933,775 | 0 | 0 |
| 20 | C3 | 80,423,900 | 80,423,900 | 11,379,129 | 91,791,947 | 1,984 | 80,384,153 |

**C0 and C1 show `enqueued=processed=drops=spec_hits=spec_migrations=0` at every single
iters value, no exceptions** -- the expected policy=0 no-op, confirmed directly rather
than assumed. No prefetch asymmetry or cross-arm contamination: `PREFETCH` is `1` for
C0 and `0` for C1/C3 exactly as configured, live-verified against the loaded module
during the verification pass, and every reload sets it explicitly (no inherited state
possible between runs).

## The mechanism

At iters=20: C3 executes **80,423,900 speculative migrations for 1,984 explicit
hit-table credits (0.0025%)** -- essentially none of that migration volume is ever
"claimed" by the bookkeeping that exists to detect a successful prediction. C3's demand
faults (91,791,947) are lower than C1's (237,933,775) -- speculation does measurably
reduce demand-fault volume relative to the crippled baseline -- but **C0 needs only
22,184,264** demand faults to do the same work, roughly a quarter of C3's count, with
zero speculative machinery running at all. The same ordering holds at every iters value
in the table above.

**Granularity asymmetry, as a cost explanation.** Read directly from
`driver/src/uvm_gpu_replayable_faults.c`: the speculative path
(`specasync_worker_fn`, :313-317) is fixed at exactly one page per migration call --
`uvm_page_mask_set(&pmask, pidx)` sets a single bit, and `uvm_va_block_region_for_page(pidx)`
constructs a single-page region by construction, passed to `uvm_va_block_make_resident()`.
The demand path (:1940-1950) tracks `first_page_index`/`last_page_index` across every
fault landing in the same VA block within one batch and constructs
`uvm_va_block_region(first_page_index, last_page_index + 1)` -- a region that can span
multiple pages per call when a batch coalesces several faults. **What is not visible
from this checkout**: `uvm_va_block_service_locked()` and `uvm_va_block_make_resident()`
are stock UVM functions not present in `driver/src` -- their internal DMA/copy chunking
cannot be confirmed from source here, so this is reported as a call-site-level
granularity difference, not a proven per-transfer-efficiency claim. No byte-count
telemetry exists anywhere in this driver (ring or atomic) to measure bytes migrated per
arm directly -- confirmed absent by direct inventory, not inferred.

**Read together**: 80.4 million single-page speculative migration operations, of which
99.95% are never explicitly credited as a correct prediction, executing under a
granularity that -- as far as visible source shows -- is finer (and by extension,
plausibly less DMA-efficient) than the demand path's own batching. Speculation is doing
enormous real work and it is not idle or broken, but the pattern is consistent with an
extremely costly *accidental page-replacement policy operating under thrash* --
migrating pages one at a time, in volume, largely without credit -- rather than a
working predictive mechanism earning its keep through accurate anticipation. This
reading follows directly from the counters and the source; it is not a claim this
report can make about the *unobserved* internals of the demand path's own transfer
efficiency.

## Scope

**5070-Ti-only.** `OVERSUB_SPEEDUP_VERIFICATION.md` verifies `GATE_B8_5070TI_REMAINING.md`'s
Task 3 finding directly (same CSV lineage, same srcversion family) -- that file is headed
explicitly "Not the T4." The only T4 oversubscription data anywhere in this project is a
single line in `results/phaseB1/GATE_D_report.md` (`Stencil_OvSub 28300 20 11264`, oracle
hit rate 0.26%) -- hit-rate-only, no wall-clock comparison, no C0/C1/C3 sweep, using a
3-argument benchmark interface that no longer exists in this repo (`GATE_B8_5070TI_REMAINING.md`
states this precisely: the exact configuration cannot be reconstructed with confidence).
**There is no T4 C0/C1/C3 oversubscription wall-clock data of any kind.** This report, and
every wall-clock oversubscription figure in Gate B9, must not be presented as a
cross-platform finding.

## Methodology note: baseline choice

The alarm this report resolves arose specifically from comparing C3 against C1 --
speculation disabled *and* prefetch disabled -- rather than against C0, the system as it
actually ships. C1 is a legitimate, deliberately-isolated configuration for measuring
speculation's marginal effect over "no prefetch at all," and other results in this
project that use C1-vs-C3 for that purpose remain valid for what they measure. What
this pass demonstrates is that a comparison against C1 alone can produce a large,
clean, statistically airtight result that reverses sign entirely once the practical
baseline (C0) is added -- not because the C1 measurement was wrong, but because C1
answers a different, narrower question than "does this beat the system as shipped."

**Any future comparison in this project must state explicitly which baseline it uses
and why**, rather than leaving C1 to stand in silently for "no speculation." This is a
candidate `ARTIFACT_CATALOG.md` entry (interpretation-against-a-crippled-baseline, a
different failure mode from the eleven already catalogued there, all of which are
measurement/arithmetic defects rather than a correct measurement answering the wrong
question) -- **flagged here, not added**, pending a decision on whether it fits the
catalog's existing definition or needs its own category.

## Data

- `results/analysis/gate_b9_oversub_mechanism/task2c_c0_threeway_times_MERGED.csv` --
  full 91-row per-run dataset (C0/C1/C3 x iters in {1,3,5,10,20} x n=5/arm kept +
  warmup), including all six per-run atomic counters.
- `results/analysis/gate_b9_oversub_mechanism/task2c_c0_threeway_times_iters1-3-5-10.csv`,
  `task2c_c0_threeway_times.csv` -- the two raw pre-merge harness outputs (first attempt,
  interrupted by the watchdog partway through iters=20; the resumed iters=20-only rerun).
- `results/analysis/gate_b9_oversub_mechanism/task2c_aggregate_comparison.csv` -- the
  per-iters median/MWU/Holm/Cohen's-d table.
- `results/analysis/gate_b9_oversub_mechanism/task2b_iter_sweep_times.csv`,
  `task2b_aggregate_comparison.csv` -- the original Task 2b (C1-vs-C3-only) alarm data,
  retained for the record.
- `tests/t_b9_task2c_c0_and_counters.sh` -- the harness used for this report's Task A/B
  data.
