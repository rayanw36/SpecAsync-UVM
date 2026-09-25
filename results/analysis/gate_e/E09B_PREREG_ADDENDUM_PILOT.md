# Gate E0.9b — Pre-registration addendum: pilot ceiling estimate

**Dated 2026-09-25. Committed before any Step 3 (sweep) run.** This addendum
is part of the E0.9b pre-registration (`E09B_PREREGISTRATION.md`, written next)
and binds its prediction test.

## Pilot runs

- Order: `e09b/pilot_order.csv` (committed in `7cbf494` before any pilot run).
  Stencil-24K C1 ×3 and C6-L4096 ×3; GraphBFS-23 C1 ×2 and C6-L4096 ×2,
  interleaved.
- Runner: `tests/e09b_runner.py` (per run: reload, check srcversion
  `5997D238EF080B77DBD2AAF` and refcnt 0, `specasync_clear`, `setarch -R`,
  `timeout` 30 s / 180 s, counter snapshot, MemAvailable, dmesg diff,
  decomp-ring dump). First-touch tables: `results/phaseB1/gate_e09b/pilot_tables/`
  (1,125,000 / 287,956 distinct pages, asserted; trace overwrites 0).
- Rows: `e09b/pilot_runs.csv` (committed `710ec7f`). 10/10 runs completed,
  0 new dmesg lines on any run, MemAvailable ≥ 60.9 GB throughout. No stop
  condition fired.
- **Disclosure:** the runner printed each run's wall-clock to stdout during the
  pilot, so the ten per-run values were displayed. No arm-versus-arm comparison
  was computed from them. Wall-clock values were used for exactly one thing:
  pooled per workload (arms not separated), to set the sweep timeouts (see the
  pre-registration). Before the sweep the runner was changed to write
  wall-clock only to the CSV, never to stdout.

## Method (decision rule branch 2: ring, ≥ 50% coverage)

Step 1 found no aggregate servicing-time timer, so the decomp ring is the
source. Every pilot run recorded fewer than 131,071 decomp records (range
23,534–75,199). The ring is drop-on-full and has 131,072 slots, so
**coverage is 100% of top-level batches and dispatch groups in all 10 runs**.
Following the brief, this is labelled a **prefix-based estimate**, here with
a scale factor of exactly 1.0 (the prefix is the whole run).

Per run: total servicing window = Σ over decomp records of
(`d6_end` if nonzero, else `svc_end`) − `d1_start`. `d6_end` was nonzero in
every record, and 0 records were malformed. Script: `tests/e09b_pilot_ceiling.py`.
Per-run output: `e09b/pilot_ceiling.csv`.

| workload | arm | per-run total servicing window (s) | dispatch groups |
|---|---|---|---|
| Stencil-24K | C1 | 2.2397, 2.2391, 2.2433 | 231,627 / 230,459 / 230,864 |
| Stencil-24K | C6-L4096 | 2.0262, 2.0414, 2.0690 | 212,924 / 212,991 / 213,323 |
| GraphBFS-23 | C1 | 0.8714, 0.8987 | 218,127 / 219,301 |
| GraphBFS-23 | C6-L4096 | 0.8879, 0.8822 | 218,724 / 219,144 |

## Estimate

| workload | median C1 − median C6-L4096 servicing window | pairwise range (all C1×C6 pairs) | median C6 `fault_already_resident` | per pre-staged fault |
|---|---|---|---|---|
| Stencil-24K | **0.198 s** | [0.170, 0.217] s | 919,270 | **216 ns** |
| GraphBFS-23 | **≈ 0 s** (−2 µs) | [−0.0165, +0.0165] s | 67,291 | ≈ 0 ns |

## Prediction registered for Step 5

The measured C6-L4096 wall-clock saving is defined as median(C1 wall-clock) −
median(C6-L4096 wall-clock), per workload, from the sweep.

The prediction interval is the pairwise range above: Stencil-24K
**[0.170, 0.217] s**, GraphBFS-23 **[−0.0165, +0.0165] s**.

- **Inside:** the measured saving falls within the interval.
- **Below:** the measured saving is less than the lower bound. This is
  consistent with the ceiling being an upper bound: servicing time saved
  becomes wall-clock saving only when the GPU is stalled on those faults.
- **Above:** the measured saving is greater than the upper bound. This means
  the ceiling was wrong, and the report will say so.

The ceiling applies to L = 4096 only. No ceiling is registered for L ∈ {1, 16, 256}.

## Limitations of the estimate

- The pilot sample is small: n = 3 + 3 (Stencil) and n = 2 + 2 (GraphBFS).
  The interval reflects pilot spread, not a formal confidence interval.
- The window is the servicing thread's busy time per batch. It does not
  measure how much of that time the GPU actually spends stalled, so
  servicing-time → wall-clock is an assumption (an upper-bound mapping), not a
  measurement.
- C6's servicing window also runs with the speculative worker consuming CPU
  and the va_block locks concurrently. The difference is net of that
  contention, not a pure per-fault saving.
- The per-fault figure divides by `fault_already_resident`, which says the
  worker beat the servicing thread, not that the page was ready before GPU
  access (E0.9a-2).
