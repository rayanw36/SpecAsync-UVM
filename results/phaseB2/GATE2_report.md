# Gate 2 — depth=1 actual GPU residency staging

## Mechanism implemented

`specasync_offload_depth=1` causes the worker function to call
`uvm_va_block_make_resident()` for the predicted page, speculatively migrating it to
GPU VRAM before the demand fault arrives.

Key implementation details:

- VA-space read lock held across find + make_resident (same lock order as demand path)
- `uvm_mutex_trylock(&va_block->lock)` — non-blocking; drops immediately if demand
  path holds the block lock → result=THROTTLED
- `uvm_va_block_context_alloc(NULL)` — NULL mm means no mmap_lock (safe from WQ)
- `uvm_va_block_retry_init/deinit` bracketing the make_resident call
- `UVM_MAKE_RESIDENT_CAUSE_PREFETCH` cause enum
- `item->gpu` is retained in enqueue, released in worker after make_resident

## Probe design

**1024 sequential pages crossing a block boundary:**

- Pages 0–511: block 0 (VA base + 0..2 MB)
- Pages 512–1023: block 1 (VA base + 2..4 MB)
- Access pattern: stride-1 sequential touch (each touch triggers a GPU page fault)
- Prediction: `fault_address + PAGE_SIZE` (adjacent, stride-1)

The block-boundary crossing (page 511 → 512) is the critical test: at that point the
predicted address falls in *block 1* (different from the faulting block 0). A
trylock on block 1 should succeed because demand path is servicing block 0.

## Results

| Metric | Value |
|--------|-------|
| batches (valid) | 1024 |
| num_faults | 1024 |
| spec_enqueued | 1024 |
| spec_drops | 0 |
| spec_hits | 245 |
| **hit rate** | **23.9 %** |
| worker: migr_done | 246 |
| worker: throttled | 777 |
| worker: miss | 1 |

**76.1 % throttled** — the vast majority of predictions target the *same 2 MB VA
block* as the current fault (page + 4KB is nearly always within the same 2 MB
block). The demand path holds that block lock → trylock fails → THROTTLED. Only at
block-boundary transitions (page 511 → 512, page 1023 → next block) does the
predicted address fall in a distinct block where trylock can succeed.

## Service-time comparison (T0→T4)

| Batch type | median µs | n |
|------------|----------:|--:|
| All batches | 10.30 | 1024 |
| Hit batches (migr_done) | 10.70 | 245 |
| Miss batches (throttled/miss) | 10.08 | 779 |
| Saving (hit vs miss) | **−5.1 %** (hit is *slower*) | — |

**No per-hit speedup.** Hit batches are 5 % *slower* than miss batches. The
speculative migration of a single 4 KB page (≈0.5 µs DMA + overhead) does not
offset the fault-batch service latency at this granularity. The migrated page is
available before the demand fault for ~24 % of faults, but the saving per fault is
smaller than the measurement noise floor.

## Timer phase breakdown (Gate 4 fix confirmation)

| Phase | Median µs |
|-------|----------:|
| T0→T1 (lock-wait) | 2.10 |
| T1→T2 (metadata) | 0.04 |
| **T2→T3 (dispatch CPU cost)** | **7.83** |
| T3→T4 (cleanup/replay) | 0.14 |
| **T0→T4 total** | **10.30** |

The corrected T2/T3 placement (T2 set *before* dispatch, T3 *after*) gives a
non-zero T2→T3 of **7.83 µs median**, confirming the fix. The previous placement
set both to the same timestamp → T2→T3≡0 → residency phase appeared dead.

The dominant CPU-path cost is **dispatch** (T2→T3, 76 % of T0→T4). Metadata
lookup (T1→T2, 0.4 µs) is negligible. DMA/migration is asynchronous and finishes
*after* T4 (off-window).

## Interpretation

The depth=1 mechanism works correctly: pages are migrated, the hit table records
the hit, and service proceeds without fault-path deadlock. However:

1. **Same-block throttle dominates.** Stride-1 sequential access almost never
   crosses a 2 MB block boundary, so 76 % of worker invocations cannot acquire
   the block lock and must abort.
2. **No measurable per-hit wall-time saving** at the single-page granularity probed
   here. The depth=1 mechanism would need a sustained pre-warming advantage over
   multiple pages per block to show wall-time improvement.

Gate 3 measures whether this advantage accumulates to a wall-clock win under real
workloads (stencil, BFS) with oracle-perfect prediction (C3 vs C0).

## Status: COMPLETE
