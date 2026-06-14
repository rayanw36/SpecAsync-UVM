# DECISION — Does any SpecAsync operating point beat the stock baseline?

## Question

Does speculative prefetching (SpecAsync-UVM, Path B) improve GPU page-fault
wall-clock time under any tested operating point?

**Decisive comparison:** C3 (oracle-perfect prediction, depth=1 speculative migration,
stock prefetcher OFF) vs C0 (stock module, prefetcher ON, no SpecAsync).

C3 is the *maximally favorable* case: it knows exactly which page will be faulted
next (oracle trace replay) and migrates it to GPU VRAM before the fault arrives.
If C3 does not beat C0, no realistic prediction strategy can.

## Answer

**Path B is closed. C3 LOSES to C0 on both benchmarks.**

| Config | Stencil-24K | vs C0 | GraphBFS-23 | vs C0 |
|--------|------------|-------|------------|-------|
| C0 (stock prefetch ON) | **4.250 s** | baseline | **55.480 s** | baseline |
| C1 (prefetch OFF, no spec) | 15.280 s | +259.5% | 58.580 s | +5.6% |
| C2 (stride+depth=1) | 16.750 s | +294.1% | 58.430 s | +5.3% |
| **C3 (oracle+depth=1)** | **15.680 s** | **+268.9%** | **58.640 s** | **+5.7%** |

C3 is statistically equivalent to C1 (no speculation) on both benchmarks:
- Stencil: C3=15.68s vs C1=15.28s, Δ=+2.6% (within ±0.46s CI)
- BFS: C3=58.64s vs C1=58.58s, Δ=+0.1% (within ±0.17s CI)

Oracle-perfect prediction with actual GPU-page migration provides zero measurable
wall-time benefit over doing nothing. C2 (realistic stride+depth=1) is even worse:
+9.6% overhead vs C1 on stencil.

## Root causes

### 1. Stock prefetcher is the dominant factor

Disabling the stock UVM prefetcher (C1 vs C0) costs **3.6× on stencil** and
**5.6% on BFS**. SpecAsync at C3 (oracle+depth=1, prefetch off) cannot recover
this loss because:

- The prefetcher migrates *multiple pages per batch* directly in the demand-fault
  hot path, with no workqueue overhead.
- SpecAsync migrates one page at a time via a workqueue worker that runs
  asynchronously and must compete for the VA block lock.

### 2. Same-block trylock throttle eliminates most speculative work

For sequential workloads (stencil) and irregular workloads (BFS), the predicted
page (`page[i] + PAGE_SIZE`) almost always falls in the same 2 MB VA block as the
faulting page. The demand path holds that block lock; `uvm_mutex_trylock` fails →
worker aborts. Gate 2 cross-block probe: **76.1% throttled** even in a best-case
cross-block scenario.

### 3. No per-hit wall-time saving at the batch granularity

When depth=1 migration does succeed (23.9% hit rate in Gate 2 probe), hit batches
are **5% slower** than miss batches, not faster. A single successful 4 KB
speculative migration does not offset the fault-batch CPU overhead (~10 µs per
batch for a single-fault probe; 385 µs per batch in real stencil workload).

### 4. Worker presence overhead is structural

Even a null worker (no prediction, SPECASYNC_POLICY_NULL) incurs the same ~2 µs
lock-wait increase as prediction workers (Phase B.1 Gate C). The overhead is
structural (VA-space read lock acquisition, enqueue/dequeue, WQ wakeup) and cannot
be reduced without architectural changes.

## What this means

- **No operating point tested shows improvement.** The progression C1 → C2 → C3
  represents: no speculation → realistic speculation → oracle-perfect speculation.
  None beats C0. C2 is *worse* than C1 on stencil.

- **The mechanism works correctly** (Gate 1: per-fault coverage verified; Gate 2:
  pages are migrated, hit table records hits, no deadlock). The mechanism is
  technically functional but structurally unable to help.

- **The constraint is architectural:** Same-block trylock contention is inherent to
  stride-1 and irregular access patterns on 2 MB UVM blocks. Fixing it would require
  changing the demand path's locking discipline, which is the critical
  fault-service loop in `uvm_gpu_replayable_faults.c`.

## What would be needed to win

A mechanism capable of beating C0 would need to:

1. Migrate *multiple pages per 2 MB block* in a single lock acquisition — matching
   the stock prefetcher's multi-page batch behavior without taking the block lock
   multiple times.
2. Integrate with (not replace) the demand path — complement the stock prefetcher
   rather than disable it.
3. Use block-granularity prediction rather than page-granularity: predict which
   block will be accessed next, then warm an entire 2 MB region.

This is essentially re-implementing the UVM prefetcher at a coarser granularity.
The stock prefetcher already does this. There is no Path B wedge.

## Status: FINAL
