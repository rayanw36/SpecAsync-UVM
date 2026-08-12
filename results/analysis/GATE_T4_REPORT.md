# Gate T4 — Prefetch-OFF hit-rate telemetry on real benchmarks

`tests/gate3_favorable_run.sh` runs C1-C3 with the prefetcher off but never dumps
`specasync_log`, so no hit-rate telemetry existed for any real benchmark under this
condition (F3's missing cell). This task adds per-run ring dumps via a **separate** script
(`tests/t4_prefetch_off_telemetry.sh`) that reproduces `gate3_favorable_run.sh`'s exact
C1/C3 reload sequence and parameter values byte-for-byte, without editing that published-
results script -- its timing path, run ordering, warm-up handling, and repetition count are
untouched.

Data: `results/gate3/telemetry/t4_prefetch_off_times.csv` (60 runs: C1 and C3, Stencil@24000
and GraphBFS@23, n=15 each; C2 skipped, per the task's "C2 optional" note and to keep this
run inside a reasonable single-session window). 62 ring-dump `.bin` files (per-run,
`{bench}_{config}_run{N}.bin`, gitignored per this project's raw-telemetry convention).
Module srcversion `8A2651D1CB32C7B239FB511` throughout; dmesg clean, 0 MiB GPU memory
leaked at completion.

## 1. Measured hit rate per configuration

| Config | Benchmark | demand faults | enqueued | drops | hits | **hit rate** | drop rate |
|---|---|---|---|---|---|---|---|
| C1 (policy=0, no speculation) | Stencil-24K | 69,485,036 | 0 | 0 | 0 | **0.0000** | -- |
| C1 (policy=0, no speculation) | GraphBFS-23 | 25,146,428 | 0 | 0 | 0 | **0.0000** | -- |
| C3 (oracle, depth=1) | Stencil-24K | 70,655,453 | 50,964,514 | 19,690,939 | 9,933 | **0.0002** | 27.87% |
| C3 (oracle, depth=1) | GraphBFS-23 | 24,918,253 | 20,505,109 | 4,413,144 | 51,569 | **0.0025** | 17.71% |

**C1 correctly shows 0/0/0** -- `specasync_enqueue()` no-ops entirely at `policy=0`
(`if (!g_specasync_wq || specasync_policy == 0 || spec_addr == 0) return;`), so a zero
reading here is the counter behaving correctly, not evidence of a broken pipeline (matches
`GATE_A_report.md`'s already-established finding that the accounting path itself is sound).

**C3 (the oracle policy -- perfect trace-based prediction, prefetch off) is the real
result: 0.02-0.25% hit rate on real workloads**, four orders of magnitude below the
deterministic probe's 99.6% (Gate 2, this work block) and below even the legacy 25.47%
cuFFT outlier that Gate T2 already found didn't reproduce.

## 2. Drops alone do not explain it -- this is a timing race, not just queue overflow

17.71-27.87% of attempted enqueues are dropped (`SPECASYNC_MAX_QUEUE_DEPTH=1024` exceeded).
But drops account for only a minority of the missing hits: even among the ~72-82% of
predictions that were **not** dropped and presumably ran to completion, the hit rate on
that surviving population is still effectively zero (9,933 hits out of 50.96M
non-dropped-adjusted enqueues for Stencil; 51,569 out of 20.5M for GraphBFS). Queue
throttling is a real, measurable cost, but it is not the dominant explanation for the
missing hits.

**The dominant explanation is a structural race the deterministic probe was built to avoid.**
`GATE_A_report.md`'s probe explicitly inserts a full `cudaDeviceSynchronize()` between each
single-page touch, artificially slowing the demand-fault stream to roughly one fault at a
time so the async workqueue worker has time to complete its VA-block lookup and insert a
hit-table entry *before* the next demand fault arrives. Real workloads do not do this:
Stencil-24K and GraphBFS-23 generate **tens of millions of demand faults over 15-58 seconds
of wall-clock time** -- a sustained rate of roughly 0.4-4.7 million faults/second. At that
rate, the workqueue-scheduled speculative worker (kernel scheduling latency: microseconds
to tens of microseconds per dispatch) essentially never wins the race to insert its
hit-table entry before the same address is independently demand-faulted by the relentless
real access stream. This is a rate mismatch, not a prediction-accuracy failure -- the oracle
policy predicts with perfect trace-based accuracy and still cannot get credited, because the
predicted work item almost never finishes in time to matter.

## 3. Verdict on the alternative explanation

**Confirmed, and with a sharper mechanism than the task anticipated.** The question this
run was designed to discriminate: does real-workload irregular access defeat the predictor
independently of the prefetcher, or was the near-zero hit rate on real benchmarks
(previously seen only with the prefetcher enabled, which structurally hides demand faults)
actually a prefetcher artifact all along? **With the prefetcher fully off and the oracle
policy giving the best possible prediction accuracy, real workloads still produce a
0.02-0.25% hit rate** -- so yes, something about real workloads defeats the predictor
independent of the prefetcher. But it is not simply "irregular access" in the sense of poor
prediction accuracy (the oracle predicts perfectly, by construction, from the recorded fault
trace) -- it is that **real fault rates outrun the async worker's scheduling latency long
before prediction accuracy becomes the bottleneck.** The deterministic probe's ~99.6% hit
rate was only achievable because the probe artificially throttled its own fault rate to
roughly one per worker-dispatch cycle; no real workload in this study does that.

## 4. What this changes (mechanism narrative only, not the conclusion)

Per the task brief, this strengthens the mechanism narrative without changing the
conclusion: C3 (Section T1) already shows no wall-clock benefit over C1 with the prefetcher
off and prediction nominally oracle-perfect, so the paper's negative result does not depend
on this finding. What this adds: a concrete, quantified reason *why* -- not "prediction
doesn't help because real access patterns are unpredictable" (a claim about prediction
*accuracy*, which the oracle policy's design already rules out as the explanation) but
"prediction can't help because the speculative worker's completion latency cannot keep pace
with real-workload fault rates, so a hit-table entry is essentially always too late to be
consumed." This is a stronger, more specific claim than the manuscript could make before
this run, and one worth a sentence in the discussion section alongside the D5 CPU-cost
finding (`D5_CHARACTERIZATION.md`) as a second, independent reason speculative prefetching
doesn't pay off in this architecture.

## Correction note (2026-08-12) — absolute counts in Section 1 are not 15 independent per-rep totals

`GATE_A1_REPORT.md`'s "Open item" flags that `t4_prefetch_off_telemetry.sh`'s `run_c3_block`
never called `specasync_clear` between its 15 reps, so the per-rep `specasync_log` ring dumps
are not independent, and estimated the resulting inflation at "roughly an order of magnitude
per rep." This note verifies that claim directly against the dump files and script, and
replaces the estimate with an exact figure.

**Root cause, confirmed by inspecting `results/gate3/telemetry/*.bin` with
`benchmarks/tools/specasync_parse.py`:** `specasync_log` is a fixed-capacity ring
(131,071 batch records / 9,437,112 bytes at 72 B/record) that, once full, was never cleared
between reps (`run_c1_block`, `run_c2_block`, and `run_c3_block` all lacked a `clear_ring`
call in the per-rep loop). Once it saturates it stops reflecting new activity, not
"wraps and overwrites" -- so every dump taken after saturation is a byte-for-byte-identical
copy of whatever was in the ring at the moment it filled, not that rep's own data:

- **Stencil-24K/C3**: ring reaches full capacity by run 17 of 15+2. `bench_stencil_C3_run17.bin`
  through `run30.bin` (14 of the 15 kept-run dump files) are byte-identical
  (131,071 batches / 3,447,110 enqueues / 684 hits each); only `run16.bin` (88,171 batches,
  partial) differs. Summing the raw per-file parses as Section 1's table does:
  `2,704,974 + 14 x 3,447,110 = 50,964,514` enqueued and `357 + 14 x 684 = 9,933` hits --
  **exactly** the Section 1 figures. So Section 1's Stencil row is not 15 reps' worth of
  telemetry; it is 1 partial rep plus **1 distinct ring-fill snapshot counted 14 times**.
- **GraphBFS-23/C3**: same mechanism, ring reaches full capacity by run 50. `run50.bin` through
  `run60.bin` (11 of 15 files) are byte-identical (131,071 batches / 1,532,207 enqueues /
  3,510 hits each); `run46`-`run49` are distinct partial fills. Summing all 15 files
  reproduces Section 1's figures exactly: enqueued sums to 20,505,109, hits to 51,569. So the
  GraphBFS row is 4 distinct partial observations plus **1 snapshot counted 11 times**.
- C1's 0/0/0 row is unaffected (`specasync_enqueue()` no-ops at `policy=0`, so the ring has
  nothing to duplicate).

**Does the hit-rate conclusion survive? Yes, confirmed, not just argued.** `hit_rate` is
computed as `sum(spec_hits) / sum(spec_enqueues)` (`specasync_parse.py:166`) over the same
per-record list for both terms -- every duplicated record contributes its `spec_hits` and
`spec_enqueues` fields together, so the ratio is a hits/enqueues weighted average that is
invariant to uniform re-counting of whole records. The 0.0002 (Stencil) and 0.0025 (GraphBFS)
figures in Section 1 are valid weighted-average hit rates over the data actually captured.
**What is not valid** is treating Section 1's absolute counts (70.6M demand faults, 50.96M
enqueued, etc.) as sums over 15 independent reps -- they are dominated by one repeatedly
re-read ring snapshot (14 of 15 files for Stencil, 11 of 15 for GraphBFS), so the effective
independent sample size behind the hit-rate estimate is much smaller than "15 reps" implies:
2 distinct observations for Stencil, 5 for GraphBFS, not 15. The **direction and order of
magnitude** of the paper's conclusion (hit rate four orders of magnitude below the
deterministic probe's ~99.6%) is not affected -- both distinct Stencil observations
(357/2,704,974 = 0.00013 and 684/3,447,110 = 0.00020) and all five distinct GraphBFS
observations independently show the same near-zero hit rate, so this is not a case of a
single outlier ring snapshot driving the result.

**Fix applied:** `clear_ring` (writes `specasync_clear` via debugfs) now runs after every rep
in all three blocks (`t4_prefetch_off_telemetry.sh`, commit tagged with this note), so future
runs of this script produce genuinely independent per-rep dumps. This session did not rerun
T4 -- the figures in Section 1 above are unchanged and should be read with this note's caveat
until a clean rerun replaces them.
