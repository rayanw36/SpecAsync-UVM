# Gate 0 — Read-back: the spec_hits data flow (before touching anything)

Source of truth: `driver/src/uvm_gpu_replayable_faults.c` (the *integrated* file that
actually compiles into the loaded `.ko`), plus `driver/src/specasync_telemetry.h`
and `driver/src/specasync_debugfs.c`. The file `specasync_faults_instrumentation.c`
is **authoring-only scaffolding** (its own header says "cannot be compiled
standalone") — it is NOT in the Kbuild source list and does not run. Quotes below
are from the real, compiled source.

## (a) Where `spec_hits` is incremented and what gates it

`uvm_gpu_replayable_faults.c:2596-2609`, inside `service_fault_batch()`, after a
VA block has been dispatched/serviced:

```c
/* ---- SpecAsync T2/T3: post-dispatch; check hit table ---- */
{
    u64 _now = ktime_get_ns();
    _sa_rec.t2_ns = _now;
    _sa_rec.t3_ns = _now;  /* residency decision folded into dispatch */
    _sa_rec.num_faults++;
    if (va_space && va_space->specasync_pred &&
        va_space->specasync_pred->hit_table) {
        uvm_fault_buffer_entry_t *_fe = batch_context->ordered_fault_cache[i];
        _sa_rec.spec_hits +=
            specasync_hit_table_consume(va_space->specasync_pred->hit_table,
                                        _fe->fault_address, _now);
    }
}
```

Gate: `specasync_hit_table_consume()` returns 1 iff the demand fault address was
previously inserted into the per-VA-space hit table **and** the entry is younger
than `SPECASYNC_HIT_MAX_AGE_NS = 10 ms` (`specasync_telemetry.h:221-252`).

## (b) How a demand fault is matched against speculatively-processed pages

`specasync_hit_table_consume()` hashes the demand `fault_address` (Fibonacci hash
of `addr >> 12`), checks the primary slot + one linear probe, compares the **full
64-bit `va_addr`** for equality, and if found-and-fresh clears the slot and
returns 1. Match key = exact byte address (both sides are 4 KB page-aligned, see
below).

## (c) The oracle trace-replay loop

`specasync_predict_next()` case 4 (`uvm_gpu_replayable_faults.c:196-197`) calls
`specasync_oracle_next_addr()` (`specasync_debugfs.c:276-285`):

```c
idx = atomic_fetch_inc(&g_oracle_idx) % (int)g_oracle_trace_len;
return g_oracle_trace[idx];
```

This is **O(1)** — an atomic post-increment cursor into a preloaded array, wrapping
modulo length. There is **no linear scan**. (See Gate B: the task's "O(n²) scan"
hypothesis is not supported by this source.)

## (d) What the worker leaves behind after `uvm_va_block_find`

`specasync_worker_fn()` (`uvm_gpu_replayable_faults.c:214-245`):

```c
uvm_va_space_down_read(item->va_space);
status = uvm_va_block_find(item->va_space, item->speculative_addr, &va_block);
uvm_va_space_up_read(item->va_space);

if (status == NV_OK && va_block && item->hit_table) {
    specasync_hit_table_insert(item->hit_table,
                               item->speculative_addr, ktime_get_ns());
    wrec.result = SPECASYNC_RESULT_HIT;     /* "HIT" here just means lookup succeeded */
}
```

The **only** durable state the worker leaves is a `(va_addr, ts_ns)` entry in the
hit table. It uses `uvm_va_block_find` (find-existing, NOT find_create) and
**discards `va_block`** immediately. No page is migrated, no residency changed, no
mapping staged (offload_depth=0, the default and the Phase B config). The demand
path consumes nothing but the hit-table tag.

## Data-flow summary (worker processes page X → demand fault on X credited as hit)

1. `service_fault_batch()` entry: takes **only `ordered_fault_cache[0]`** (the first
   fault of the batch), computes `spec_addr = predict_next(fault0)` (adjacent:
   `fault0 + PAGE_SIZE`), and enqueues **one** async work item (`specasync_enqueue`).
2. The work item carries `speculative_addr` and a pointer to the VA-space hit table.
3. Asynchronously, `specasync_worker_fn` takes the VA-space read lock, calls
   `uvm_va_block_find(speculative_addr)`, releases, and on success inserts
   `speculative_addr` into the hit table with a timestamp. **It does no real work** —
   the lookup result is thrown away.
4. Later, when a demand fault is serviced, the bottom of `service_fault_batch`
   calls `hit_table_consume(fault_address)`. If a prior worker inserted exactly
   that page < 10 ms ago, it counts as `spec_hits += 1`.

**Therefore a "hit" measures PREDICTION CORRECTNESS ONLY** — "we tagged a page that
later faulted" — and carries **zero time saving**, because the worker's lookup is
discarded and the demand path still does the full migration. This is the single
most important fact for the writeup: even a perfect oracle (100% hits) cannot
produce speedup at offload_depth=0, because there is no consumable product. See
Gate A step 4 and Gate B success criteria.

## Structural observations (pre-measurement, to be confirmed empirically)

- **One prediction per batch, from fault[0] only.** In a coalesced batch that
  services pages [N..N+k] together, the predicted page N+1 is *already in the same
  batch* and is consumed *before* the async worker could have inserted it → 0 hits
  structurally. Hits are only possible across **separate** batches (i.e. when
  faults are serialized, as in a fully-synced probe). This is a real prediction
  limitation, not (yet) an accounting bug — Gate A's deterministic probe
  discriminates the two.
- **Oracle requires init-time wiring that the runtime sweep may not satisfy:** the
  trace is loaded only if `specasync_policy == 4` *at module-init* AND
  `specasync_oracle_trace_path` is non-NULL (`specasync_debugfs.c:415-416`); the
  path param is `0444` (cannot be set after load). If the oracle was selected by
  flipping the policy param at runtime, `g_oracle_trace == NULL`,
  `oracle_next_addr()` returns 0, `enqueue` early-returns on `spec_addr == 0`, and
  the oracle does **nothing** → exactly 0.000 hits. Strong candidate for the
  observed oracle result; confirm in Gate B.
