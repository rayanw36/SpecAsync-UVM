# Part 2 — Verifying `GATE_T4_REPORT.md` Section 2's rate-mismatch claim

> **CORRECTION (2026-08-13): this report's own "corrected" rate (Section 2 below,
> 0.296M/0.029M faults/s) is itself superseded.** It fixed the denominator bug (dividing by
> one rep's wall-clock instead of the summed 15-rep wall-clock) but its numerator
> (`total demand faults` = 70,655,453 / 24,918,253) was not yet known to be corrupted --
> `GATE_T4_REPORT.md`'s later correction note (not written until after this report) found
> `specasync_log`'s ring saturates partway through rep 2 (Stencil) / rep 5 (GraphBFS) of 15,
> after which every dump is a duplicate of the same frozen snapshot, not that rep's own data.
> Both this report's numerator and the original report's numerator inherit that duplication;
> only the denominator differed between the two, which is why this report's "corrected" rate
> is ~15x lower than the original but still far too high. Doubly-corrected figures, using
> only the pre-saturation reps: **Stencil-24K ~0.188M faults/s (n=1 clean rep), GraphBFS-23
> ~0.00765M faults/s (n=4 clean reps)** -- see `GATE_T4_REPORT.md` Section 2 and
> `GATE_A1_REPORT.md` Result 2 for the full derivation and re-verification against measured
> (not idealized-probe) contended dispatch latency. **Section 4's conclusion below, that the
> corrected numbers "do not support rate mismatch as a sufficient explanation for GraphBFS's
> near-zero hit rate," does NOT survive this further correction** -- GraphBFS-23's properly
> corrected inter-arrival gap (130.7µs) compared against `GATE_A1_REPORT.md`'s measured
> contended dispatch median (10,607.0µs) gives a ratio of ~81x in favor of the worker
> *losing* the race, the opposite of what this report's still-inflated 35.03µs budget
> suggested when compared against the (wrong basis) uncontended probe latency.

## 1. Dispatch granularity, from source

**`specasync_enqueue()` is called once per coalesced fault entry, not once per batch and not
once per VA block.**

Definition: `driver/src/uvm_gpu_replayable_faults.c:330-366`. Guard at entry
(`uvm_gpu_replayable_faults.c:337`): `if (!g_specasync_wq || specasync_policy == 0 ||
spec_addr == 0) return;`; queue-depth check and drop counter at `uvm_gpu_replayable_faults.c:339-342`.

Only call site: `driver/src/uvm_gpu_replayable_faults.c:2582-2595`, inside `service_fault_batch()`,
in a loop ("Gate 1: per-fault prediction") that iterates every coalesced fault in the batch:

```c
2582    if (specasync_log_enabled && batch_context->num_coalesced_faults > 0) {
2583        NvU32 _fi;
2584        for (_fi = 0; _fi < batch_context->num_coalesced_faults; _fi++) {
2585            uvm_fault_buffer_entry_t *_fe = batch_context->ordered_fault_cache[_fi];
2586            if (_fe && _fe->va_space) {
2587                u64 _spec_addr = specasync_predict_next(_fe->va_space,
2588                                                        _fe->fault_address, 1);
...
2592                specasync_enqueue(_fe->va_space, _spec_addr, _ht, &_sa_rec, _fe->gpu);
2593            }
2594        }
2595    }
```

This loop runs once per `service_fault_batch()` invocation (i.e. once per fetched fault-buffer
batch, capped at `uvm_perf_fault_batch_count`, default 256), but the **enqueue call itself fires
once per `_fi`** — one dispatch attempt per coalesced fault entry in that batch. It is a separate,
earlier loop than the main per-VA-block servicing loop at line 2601 that actually migrates data;
the two loops walk the same `ordered_fault_cache` population independently.

**Empirical confirmation, independent of the source read:** `spec_enqueues + spec_drops` equals
`total_demand_faults` **exactly**, for both benchmarks (Section 2 below) — every single
demand-fault entry produces exactly one `specasync_enqueue()` attempt (either it succeeds or it
is dropped for queue depth), which is only possible if dispatch is 1:1 with fault entries, not
with batches. Batch count is smaller than fault count by the batch coalescing factor (mean 36.7
faults/batch for Stencil, 14.3 for GraphBFS — Section 2), so a per-batch dispatch model would have
produced a large, systematic shortfall between `(enqueues+drops)` and `total_demand_faults`; it
does not.

**Verdict on the decisive question:** dispatch is per-fault. The task's concern — that a
per-batch dispatch granularity would inflate the timing budget to hundreds of microseconds and
undercut the argument — does not apply. `GATE_T4_REPORT.md`'s per-fault framing was the right
granularity. **However, its rate arithmetic at that granularity was wrong, independent of the
granularity question — see Section 2.**

## 2. Recomputed rate, from T4 telemetry

Source: `results/gate3/telemetry/*.bin` (`t4_prefetch_off_telemetry.sh`'s C3 runs, the same data
`GATE_T4_REPORT.md` used), parsed with the same struct layout as
`benchmarks/tools/specasync_parse.py`; wall-clock from `results/gate3/telemetry/t4_prefetch_off_times.csv`.
Totals cross-checked and matched exactly against `GATE_T4_REPORT.md`'s published fault/enqueue/drop/hit
counts (Section 1 of that report) before proceeding.

| Benchmark (C3, n=15 runs) | total demand faults | total batches | mean faults/batch | total wall-clock (sum of 15 runs) |
|---|---:|---:|---:|---:|
| Stencil-24K | 70,655,453 | 1,923,165 | 36.74 | 238.36 s |
| GraphBFS-23 | 24,918,253 | 1,746,261 | 14.27 | 872.86 s |

**Per-dispatch (per-fault) time budget** = total wall-clock / total demand faults:

| Benchmark | fault rate | **per-dispatch budget** |
|---|---:|---:|
| Stencil-24K | ~~296,423 faults/s (0.296 M/s)~~ **188,001 faults/s (0.188 M/s), see banner above** | ~~3.374 µs~~ **5.32 µs** |
| GraphBFS-23 | ~~28,548 faults/s (0.029 M/s)~~ **7,652 faults/s (0.00765 M/s), see banner above** | ~~35.03 µs~~ **130.7 µs** |

**This is not what `GATE_T4_REPORT.md` reports.** Its Section 2 states "roughly 0.4-4.7 million
faults/second" and "0.2-2.5 µs per fault." Reverse-engineering that figure:
`70,655,453 / 15 = 4,710,364` and `24,918,253 / 58 = 429,625` — matching its "4.7 million" and
"0.4 million" almost exactly. **The original figure divided the fault total summed across all 15
repetitions by one repetition's wall-clock duration (15s / 58s, the same numbers the same
sentence cites as the "15-58 seconds of wall-clock time" range) instead of by the aggregate
15-repetition wall-clock time.** This inflated the true rate by very close to 15x (the repetition
count) for both benchmarks. The corrected rate is **roughly 16x lower** than published for
Stencil and **~15x lower** for GraphBFS.

**A per-batch rate is reported for context only, since Section 1 established dispatch is
per-fault, not per-batch:** batch rate is 8,068/s (Stencil, 123.9 µs/batch) and 2,001/s
(GraphBFS, 499.8 µs/batch) — the "hundreds of microseconds" figure the task predicted *would*
apply if dispatch were per-batch. It is not the operative number here.

## 3. Comparison against a defensible dispatch-latency figure

The only **measured** SpecAsync worker dispatch-latency figure in this project is
`results/phaseB1/GATE_A_report.md`: "Worker latency on the 99% run: queue ≈ 5.6 µs median,
exec ≈ 0.35 µs" (≈**5.95 µs** enqueue-to-completion), from the deterministic hit probe
(`tests/hit_probe.cu`), measured via the `specasync_worker_log` ring
(`enqueue_ts_ns`→`dequeue_ts_ns`→`completion_ts_ns`).

**This figure must be used with an explicit caveat, marked here as required:** it was measured
under the probe's artificially serialized condition — one fault at a time, full
`cudaDeviceSynchronize()` between touches, no concurrent CPU-side batch-processing load. Neither
T1's nor T4's harness dumps `specasync_worker_log` for the real benchmarks (`t1_gate3_interleaved.sh`
and `t4_prefetch_off_telemetry.sh` both dump only `specasync_log`), so **there is no measured
dispatch latency under real-workload CPU contention.** Comparing the probe's 5.6-5.95 µs figure
against real-workload fault-arrival budgets is therefore an **order-of-magnitude comparison**,
not an apples-to-apples one — real contention (many outstanding work items, the VA-space lock
held during residency decisions, competing UVM kernel threads) could plausibly push actual
dispatch latency well above the idealized probe figure. This project also has a directly
measured, real-workload figure for a related but distinct cost — `enqueue_overhead_ns` (the cost
of the `queue_work()` call itself, not full dispatch-to-completion latency): mean 164 ns/enqueue
(Stencil) and 257 ns/enqueue (GraphBFS), both small relative to either budget below.

| Benchmark | per-dispatch budget | probe dispatch latency (order-of-magnitude, uncontended) | ratio (latency / budget) |
|---|---:|---:|---:|
| Stencil-24K | 3.37 µs | ~5.6-5.95 µs | **~1.7-1.8x** |
| GraphBFS-23 | 35.03 µs | ~5.6-5.95 µs | **~0.16-0.17x** |

## 4. Does the corrected number still support the mechanism claim?

**Partially, and not uniformly across the two workloads — this is a real weakening of the claim
as originally stated.**

- **Stencil-24K:** the corrected budget (3.37 µs) is still somewhat smaller than the probe's
  latency figure (~5.6-5.95 µs), so "the worker usually loses the race" remains a plausible
  reading. But the margin (~1.7-1.8x) is far narrower than the original (erroneous) framing
  implied — under the buggy 15x-inflated rate, the ratio would have looked like 2.2-28x
  depending which endpoint of the original "0.2-2.5 µs" range was used against the same
  5.6-5.95 µs latency, i.e. an "obviously loses" story rather than a "usually loses, sometimes
  close" one.
- **GraphBFS-23:** ~~the corrected budget (35.03 µs) is roughly **6x larger** than the probe's
  latency figure. Taken at face value, the rate-mismatch mechanism as quantified would predict
  the worker should *usually win* this race — yet the measured hit rate for GraphBFS-23 is still
  only 0.21-0.25% (Section 5), barely higher than Stencil's 0.02% despite a ~10x larger nominal
  time budget. **The corrected numbers do not support rate mismatch as a sufficient explanation
  for GraphBFS's near-zero hit rate.**~~ **SUPERSEDED (2026-08-13, see banner at top of this
  report): this conclusion was built on a still-inflated 35.03µs budget AND compared against
  the wrong (uncontended) latency figure.** `GATE_A1_REPORT.md` (written after this report)
  measured the real, *contended* dispatch latency directly: 10,607.0µs median for GraphBFS-23.
  Against the properly corrected budget (130.7µs, ~4x larger than the number used here, itself
  still an underestimate this report inherited from the ring-duplication bug), the ratio is
  ~81x in the worker's *disfavor* -- the opposite conclusion. **Rate mismatch, correctly
  quantified with both fixes applied, is fully consistent with GraphBFS-23's near-zero hit
  rate; option (a) below is now the confirmed explanation, not (b).** The either/or below is
  retained for the historical record of what this report could conclude at the time it was
  written, with real (unmeasured-uncontended-probe) data not yet available:
  Either (a) real-workload dispatch latency is substantially
  higher than the uncontended probe figure (plausible, unmeasured, see Section 3's caveat), or
  (b) some other factor limits GraphBFS's hit rate independent of arrival-rate timing (e.g.
  hit-table capacity/eviction, prediction locality, or something specific to the graph traversal's
  access pattern) — this data cannot distinguish those.

~~**Revised claim:** rate mismatch, correctly computed, is a plausible *contributing* mechanism for
Stencil-24K's near-zero hit rate, where the race is close but still probably unfavorable to the
predictor. It is **not established** as the dominant, workload-general mechanism the original
report claimed — it fails to explain GraphBFS-23 under the same arithmetic, and the real-workload
dispatch latency it depends on is not actually measured (only extrapolated from an idealized
probe).~~

**SUPERSEDED (2026-08-13) — twice over.** `GATE_A1_REPORT.md` (written after this report)
supplied exactly the missing measurement flagged above: real-workload worker dispatch latency
under contention, directly measured via `specasync_worker_log`, not extrapolated from the
uncontended probe. Combined with this report's own numerator-side correction
(`GATE_T4_REPORT.md`'s ring-saturation finding, banner at top of this file), the mechanism is
now **established for both benchmarks**: dispatch latency is ~1,774x the corrected Stencil
inter-arrival gap and ~81x the corrected GraphBFS gap. The manuscript should not carry the
"0.4-4.7 million faults/second" framing forward, nor this report's own intermediate "0.296
million faults/s, Stencil-24K only" framing — cite `GATE_T4_REPORT.md`'s and
`GATE_A1_REPORT.md`'s updated sections instead, which state the doubly-corrected rates
(0.188M/s Stencil, 0.00765M/s GraphBFS) and the measured (not extrapolated) contended
dispatch-latency comparison for both workloads.

## 5. Fault-count plausibility check (Stencil-24K, ~4.6 GB working set)

`benchmarks/bench_stencil.cu`: `N=24000`, two `float` grids (`grid0`, `grid1`), `elems = N*N =
576,000,000`. Working set = `2 * 576,000,000 * 4 bytes = 4,608,000,000 bytes` (**4.608 GB**,
matching the cited "~4.6 GB" exactly) over `ITERS=20` ping-pong stencil iterations
(`#define ITERS 20`, `bench_stencil.cu:25`), reading `src`/writing `dst` each iteration with no
intervening host access.

At 4 KB pages: 4.608 GB / 4 KiB = 1,152,000 pages (both grids). Mean demand faults per run =
70,655,453 / 15 = 4,710,364, i.e. **~4.09 faults/page/run** on average — well above a single
first-touch fault per page (expected if pages, once migrated to GPU, stayed resident for all 20
iterations) and well below the theoretical ceiling of 20 faults/page/run (every iteration
re-faulting every page). **This is consistent with prefetch-off thrashing** (partial re-faulting
across iterations, plausible for a read/write ping-pong pattern with no host-side residency
hints) and is not evidence of a counter that double-counts — a double-counting bug would tend to
produce values exceeding the 20x physical ceiling or an implausible exact multiplier, neither of
which is observed.

GraphBFS-23 (`log2_n=23` → `num_vertices = 2^23 = 8,388,608`, frontier-based, not full-graph
per iteration): mean demand faults/run = 24,918,253 / 15 = 1,661,217, i.e. **~0.20 faults/vertex/run**
— well under 1, consistent with a frontier traversal touching a fraction of vertices per level
rather than the whole graph repeatedly; no plausibility concern here either.

## 6. Drop-rate / hit-rate arithmetic — reconciled precisely

`GATE_T4_REPORT.md` Section 2's stated figure, "9,933 hits out of 50.96M non-dropped-adjusted
enqueues," is arithmetically consistent (9,933 / 50,964,514 = 0.0195%) but the phrase itself
invites a misreading it should not: **`spec_enqueued` (50,964,514) is not a raw count requiring a
drop adjustment — it already *is* the non-dropped population by construction.** In
`specasync_enqueue()` (`uvm_gpu_replayable_faults.c:339-342`), each attempt either increments
`spec_drops` and returns (queue-depth cap exceeded) or falls through to increment `spec_enqueues`
on success; the two counters are mutually exclusive outcomes of the same attempt, and
`spec_enqueues + spec_drops = total_demand_faults` exactly for both benchmarks (Section 2),
confirming this directly. No "adjustment" step exists or is needed — `50,964,514` already is
"the non-dropped population."

**The precise restatement:** of the 70,655,453 attempted dispatches for Stencil-24K, 50,964,514
(72.14%) were successfully queued (`spec_enqueued`) and 19,690,939 (27.87%) were dropped for
queue depth; of the successfully-queued population, 9,933 (0.0195%) registered as hits. For
GraphBFS-23: of 24,918,253 attempts, 20,505,109 (82.29%) queued, 4,413,144 (17.71%) dropped;
of the queued population, 51,569 (0.2515%) registered as hits.

**A real gap the original phrasing papers over, flagged per this project's standing policy
against inferring a missing measurement:** "successfully queued" (`spec_enqueued`) means
`queue_work()` returned successfully — it does **not** mean the item was ever dequeued and
executed by the worker before becoming stale. `GATE_T4_REPORT.md`'s "presumably ran to
completion" is exactly that — a presumption, not a measurement. The population that would settle
it (`spec_processed`, i.e. `specasync_worker_log` record count, per `GATE_A_report.md`'s counter
triad) is not present in either T1's or T4's telemetry for real benchmarks. **The near-zero hit
rate among successfully-queued items could therefore be explained by (a) the queued item losing
the race against the demand fault after being queued but before being dequeued/executed
[the mechanism as claimed], or (b) items sitting queued for a long time without being dequeued at
all under sustained real-workload load [a distinct, unmeasured backlog effect], or some mix of
both — this telemetry cannot separate them.**
