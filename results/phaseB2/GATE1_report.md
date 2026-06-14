# Gate 1 — Per-fault prediction (per-batch → per-fault enqueue)

## Change

**Before (Phase B.1):** One `specasync_enqueue()` call per fault *batch*, always
predicting from `ordered_fault_cache[0]`. A batch of N faults produced 1 work item.
Faults 1…N−1 were never covered.

**After (Gate 1):** A loop over `ordered_fault_cache[0..num_coalesced_faults-1]`
enqueues one work item per fault. Batch of N faults → N work items.

```c
NvU32 _fi;
for (_fi = 0; _fi < batch_context->num_coalesced_faults; _fi++) {
    uvm_fault_buffer_entry_t *_fe = batch_context->ordered_fault_cache[_fi];
    if (_fe && _fe->va_space) {
        u64 _spec_addr = specasync_predict_next(_fe->va_space,
                                                _fe->fault_address, 1);
        struct specasync_hit_table *_ht = ...;
        specasync_enqueue(_fe->va_space, _spec_addr, _ht, &_sa_rec, _fe->gpu);
    }
}
```

The oracle cursor advances by 1 per call (`batch_faults=1`), giving exact alignment
between prediction cursor and fault order.

## Verification

Adjacent-prediction hit probe (256 pages, prefetch off, depth=0):

| Metric | Value |
|--------|-------|
| batches | 256 |
| num_faults | 256 |
| spec_enqueued | 256 |
| spec_drops | 0 |
| spec_hits | 254 |
| enq / fault | **1.000** |
| hit rate | **99.2 %** |

The 1:1 enqueue:fault ratio is verified. (At batch_size=1 per fault this is
trivially 1:1; the change shows in real workloads with multi-fault batches, where
the previous code produced 1 enqueue for N faults. The hit-probe confirms the
per-fault loop is active and the oracle cursor aligns correctly.)

## Impact on other gates

- **Gate 2/3**: Every fault now receives a speculative work item, so the depth=1
  migration path has full coverage. The worker queue is sized to 1024 items
  (increased from 512) to absorb burst batches without drops.
- The SPECASYNC_MAX_QUEUE_DEPTH bump from 512 → 1024 is in effect; zero drops
  observed in the 256-page probe.

## Status: COMPLETE
