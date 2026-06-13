# Gate A — Can the hit counter fire? YES. The accounting is sound.

**Verdict: case (i).** With a deterministic positive control the counter fires at
**99.2 %**. The hit-accounting path is **not** broken. The "bug" hypothesised in the
task brief (hit counter never fires on the v595 port) is **REJECTED**. The near-zero
hit rates on the real Phase B benchmarks are a *real* interaction finding, not an
instrumentation artifact — see "What this means" below.

## Counter triad — already distinct, read per-run from debugfs

No code change was needed to expose the triad. They already exist and reset on
`echo 1 > /sys/kernel/debug/specasync/specasync_clear`:

| metric          | source                                              |
|-----------------|-----------------------------------------------------|
| `spec_enqueued` | `specasync_batch_record.spec_enqueues` (batch ring) |
| `spec_processed`| count of `specasync_worker_log` records             |
| `spec_hits`     | `specasync_batch_record.spec_hits` (batch ring)     |
| `spec_drops`    | `specasync_batch_record.spec_drops` (batch ring)    |

`tests/run_hit_probe.sh` reads and prints all four + a verdict.

## The probe (`tests/hit_probe.cu`, sm_75)

One `cudaMallocManaged` buffer; whole buffer forced resident on the CPU; then each
4 KB page touched in ascending order with a full `cudaDeviceSynchronize()` between
touches → faults are serialized, one demand fault per service batch. This ascending
stride-1 pattern is exactly what `specasync_policy=adjacent` predicts (page N faults
→ predict N+1), so a correctly-accounted pipeline must score a high hit rate.

## Result — the decisive comparison

Module = loaded `nvidia-uvm-specasync.ko` (srcversion `B83C15D…`), policy=1
(adjacent), `specasync_log_enabled=1`. 256 pages, stride 1.

| condition                       | batches | demand faults | spec_enqueued | spec_processed | **spec_hits** | hit_rate |
|---------------------------------|--------:|--------------:|--------------:|---------------:|--------------:|---------:|
| prefetch **ON** (as-found)      |       5 |             5 |             5 |   5 (all "hit")|         **0** |  0.0000  |
| prefetch **OFF** (`uvm_perf_prefetch_enable=0`) | 256 |   256 |           256 | 256 (all "hit")|       **254** |  0.9922  |

Worker latency on the 99 % run: queue ≈ 5.6 µs median, exec ≈ 0.35 µs — three orders
of magnitude inside the 10 ms hit window, so timing/staleness is not a factor.
(254 not 256: page 0 is never predicted, and the very first prediction races the
first re-touch — both expected boundary misses.)

## Why prefetch-ON collapses to 0 hits (the real finding)

With the stock prefetcher enabled, the 1 MiB buffer is migrated in **5 large
batches** instead of 256 single-page faults. The pages the predictor tags are then
brought in by the **prefetcher**, not by a demand fault, so they never reach the
`hit_table_consume()` path. The predictor is structurally racing the UVM prefetcher
and losing. Two compounding causes, both confirmed in code:

1. **Prefetch hides demand faults** — predicted pages arrive via prefetch, so there
   is no later demand fault to credit (this experiment).
2. **One prediction per batch, from `ordered_fault_cache[0]` only**
   (`uvm_gpu_replayable_faults.c:2484-2494`), and the predicted page N+1 is usually
   *already inside the same coalesced batch*, consumed before the async worker can
   tag it. Hits are only possible across **separate** batches.

## What a "hit" means here (decides the paper's conclusion)

The worker (`specasync_worker_fn`) does a **metadata-only** `uvm_va_block_find` and
**discards the block**; `offload_depth=0` (default, and the Phase B config) means no
migration, no mapping, nothing staged. Therefore:

> **`spec_hits` measures PREDICTION CORRECTNESS ONLY — "we tagged a page that later
> faulted." It carries ZERO time saving.** Even the 99.2 %-hit probe would show no
> speedup, because the demand path still does the full migration. A perfect oracle
> cannot beat baseline at `offload_depth=0`.

This is the single most important caveat for the writeup and is independent of the
prefetch interaction above.

## Bottom line for Gate A

- The counter works; accounting is correct (case **i**). No fix required to hit
  accounting.
- The near-zero real-benchmark hit rates are **real**, driven by (a) the UVM
  prefetcher hiding the demand faults the predictor needs and (b) per-batch,
  fault[0]-only prediction that is too late for coalesced batches.
- Because the mechanism is metadata-only, hit rate is an *upper bound on prediction
  accuracy*, not on achievable speedup — the speedup ceiling is ~0 by construction.
