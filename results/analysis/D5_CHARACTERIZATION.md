# D4/D5 source-level characterization (Task C)

Read-only driver-source analysis. No GPU required, none used.

## 0. Provenance of the source cited

Two source trees exist on this machine:

1. **`driver/src/uvm_gpu_replayable_faults.c`** -- confirmed the 595.71.05 tree.
   Byte-identical (`diff` empty) to `manuscript_assets/source/phaseC-decomp__uvm_gpu_replayable_faults.c`,
   which is the exact file Phase C's instrumented build (`nvidia-uvm-specasync-phaseC.ko`,
   srcversion `8A2651D1CB32C7B239FB511`, per `PHASEC_REPORT.md`) was compiled from. All
   D1-D6 instrumentation lives in this one file. **All citations to this file below are
   against the real 595.71.05 tree**, not a reconstruction.

2. **`uvm_va_block.c`** -- the D5 span calls into this file (`uvm_va_block_service_locked`
   and its callees), but **it does not exist anywhere on this machine** for the 595.71.05
   tree (confirmed: `find / -iname uvm_va_block.c` returns nothing outside the patch
   below). The only available copy of this file's source is embedded in
   `driver/patches/specasync_uvm_v580.95.05.patch`, which per `driver/PORTING_NOTES_595.md`
   ("The v580 patch stored in LFS is the entire unmodified 580 source tree committed as
   an initial git blob") contains the **v580.95.05** source, not v595.71.05. `PORTING_NOTES_595.md`
   spot-checks several unrelated APIs as "present and unchanged" between 580 and 595, but
   does **not** spot-check any of `uvm_va_block_service_locked`, `uvm_va_block_service_copy`,
   `uvm_va_block_make_resident_copy`, or the push/copy helpers used below. **Section 2's
   citations into `uvm_va_block.c` are therefore v580.95.05, not verified-595.71.05** --
   flagged explicitly rather than silently presented as 595 source. This is a real
   limitation on this task's citation requirement, reported rather than papered over.
   Core VA-block residency/copy plumbing is not the kind of code that changes fault-path
   sync/async structure between adjacent point releases within the same major driver
   branch, so the v580 chain is a reasonable basis for the characterization below, but it
   is an inference, not a demonstrated fact for 595.

## 1. The D4/D5-bracketed code span (595.71.05 tree, confirmed)

`driver/src/uvm_gpu_replayable_faults.c`:

- **D4 (va_space lock HOLD, encompasses D5):** measured inside `service_fault_batch()`
  (function at lines 2550-2809). `_hold_start` is set right after
  `uvm_va_space_down_read()` at **line 2649**; `_dec->d4_hold_ns` accumulates at three
  release points: **lines 2622-2628** (switching to a new va_space), **lines 2728-2733**
  (early exit on `NV_WARN_MORE_PROCESSING_REQUIRED`/`NV_WARN_MISMATCHED_TARGET`), and
  **lines 2793-2799** (function exit via the `fail:` label). D3 (lock WAIT) is measured
  immediately before D4 starts, at **lines 2642-2654**.
- **D5 (`service_fault_batch_dispatch()` CPU time inside the D4 hold):** measured at
  **lines 2700-2714**, wrapping a single call to `service_fault_batch_dispatch()`
  (function defined at **lines 2265-2354**).
- **Outer D1/D2/D3+D4+D5/D6 harness:** the batch-processing loop that calls
  `service_fault_batch()` -- D1 (`fetch_fault_buffer_entries`) at **lines 3358-3362**, D2
  (`preprocess_fault_batch`) at **lines 3373-3379**, the D3/D4/D5-bearing
  `service_fault_batch()` call at **lines 3389-3391**, D6 (`push_replay_on_parent_gpu` /
  `fault_buffer_flush_locked`) at **lines 3446-3470**.

## 2. Call tree from the D5 span, with classification

Every function called from inside the D5-measured window
(`service_fault_batch_dispatch()`, line 2265) down through the point where GPU work is
either waited on or submitted. Classification key: **CPU** = pure CPU computation/data
structure work; **ALLOC** = memory allocation; **LOCK** = lock acquire/release (distinct
from the va_space lock already accounted for as D3/D4); **SYNC-WAIT** = blocks the CPU
until GPU work completes; **ASYNC-SUBMIT** = pushes GPU work and returns without waiting.

```
service_fault_batch_dispatch()                                    [replayable_faults.c:2265]
  CPU  uvm_va_space_iter_gmmu_mappable_first / _next               [2286, 2291]  -- VA-range lookup
  ALLOC/CPU uvm_va_block_find_create_in_range() / uvm_hmm_va_block_find_create() [2295, 2297]
            (creates the va_block object if not already present -- allocation on
             first touch, cheap lookup on repeat touches to the same block)
  |
  +-- service_fault_batch_block()                                  [replayable_faults.c:1923]
        LOCK  uvm_mutex_lock(&va_block->lock)                      [1941]  -- per-block mutex,
              separate from the va_space rwsem already counted as D3/D4
        |
        +-- service_fault_batch_block_locked()                     [replayable_faults.c:1696]
              CPU  fault scan/classify loop (duplicate detection, permission check,
                   thrashing-hint lookup, uvm_va_block_select_residency())  [1754-1900]
                   -- this is the bulk of D5's CPU cost: per-fault bookkeeping, NOT
                      any GPU interaction
              |
              +-- uvm_va_block_service_locked()                     [uvm_va_block.c,
                                                                       v580 patch:1760042]
                    CPU  prefetch hint computation                  [patch:~1760055]
                    |
                    +-- uvm_va_block_service_copy()                 [v580 patch:1759548]
                          CPU  cause/mask bookkeeping                [patch:1759548-1759596]
                          ASYNC-SUBMIT (see below)
                            uvm_va_block_make_resident_read_duplicate() /
                            uvm_va_block_make_resident_copy()        [patch:1759596-1759618]
                          SYNC-WAIT (CONDITIONAL -- see note below)
                            uvm_tracker_wait(&va_block->tracker)     [patch:1759640]
                    |
                    +-- uvm_va_block_service_finish()                [v580 patch, not
                                                                       traced further --
                                                                       CPU-side PTE/mapping
                                                                       bookkeeping per its
                                                                       header comment]
        LOCK  uvm_mutex_unlock(&va_block->lock)                     [1945]
        ASYNC uvm_tracker_add_tracker_safe(&batch_context->tracker,
                                           &va_block->tracker)       [1953]
              -- merges the block's (possibly still-in-flight) GPU-work tracker into the
                 batch tracker; does NOT wait on it
```

**`uvm_va_block_make_resident_copy()` chain (v580 patch, traced to its GPU-facing base):**

```
uvm_va_block_make_resident_copy()          [patch:1752498]
  CPU  unmap-mask bookkeeping, alloc unmap_processor_mask               [patch:1752498-~1752545]
  |
  +-- block_copy_resident_pages() -> ... -> block_copy_resident_pages_between()
                                                                          [patch:1751656]
        CPU   per-page copy-mask / contiguity computation                [patch:1751656-1751745]
        ASYNC-SUBMIT
          block_copy_begin_push()          [patch:1750972]  -- uvm_push_begin*, selects a
                                            GPU channel, opens a push (CPU-side command
                                            buffer construction, no wait)
          block_copy_pages()               [patch:1751536]  -- issues CE copy methods into
                                            the open push (CPU writes commands, no wait)
          block_copy_end_push()            [patch:1751484]
              uvm_push_end(push)           [patch:1751496]  -- **not** uvm_push_end_and_wait;
                                            submits the push to the channel and returns
              uvm_tracker_add_push_safe(copy_tracker, push)  [patch:1751504]  -- records the
                                            push in a tracker for later/async waiting,
                                            does not block here
```

## 3. The one conditional synchronous wait, and why it doesn't apply here

The **only** `uvm_tracker_wait` found anywhere in the D5 call chain is in
`uvm_va_block_service_copy()` (v580 patch line 1759640), and it is explicitly gated:

```c
if (service_context->operation == UVM_SERVICE_OPERATION_REPLAYABLE_FAULTS &&
    UVM_ID_IS_CPU(new_residency) &&
    !uvm_processor_mask_empty(all_involved_processors)) {
    ...
    status = uvm_tracker_wait(&va_block->tracker);
```

The comment above it explains why: this wait exists so the CPU can run an ECC/NVLink
error check on the GPU(s) involved **before exposing possibly-corrupt data to CPU
threads** -- it fires only when the migration destination (`new_residency`) is the CPU.
For every benchmark in this study (Stencil, GraphBFS, SGEMM, STREAM, cuFFT), the fault
path being measured is a **GPU fault requesting a page be migrated onto the GPU** --
`new_residency` is a GPU, not the CPU -- so this branch, and the only synchronous GPU
wait in the entire chain, **does not execute** on the path D5 measures for this project's
workloads.

## 4. Verdict

**D5's measured CPU time is dominated by CPU-side orchestration and async-submit, not by
waiting for the GPU to finish the migration copy.** Concretely: `service_fault_batch_block_locked()`'s
scan/classify/residency-selection loop (duplicate detection, permission checks,
thrashing-hint lookup, `uvm_va_block_select_residency()`) is pure CPU bookkeeping; the
actual data movement is handed to the GPU via `uvm_push_end()` (an async submit that adds
the push to a tracker and returns immediately) inside `block_copy_end_push()`, not via a
blocking wait. The one `uvm_tracker_wait` anywhere in the chain is conditioned on a
CPU-destination migration, which none of this project's fault-driven benchmark paths
exercise.

This refines, rather than contradicts, `PHASEC_REPORT.md`'s own framing ("D4/D5... GPU
fault service — page-table walks, TLB shootdown, migration decisions... irreducible on
the CPU path: the GPU must be told about each mapping change while the va_space lock is
held"). The precise mechanism is: D5's cost is the CPU work of *deciding* residency and
*constructing and submitting* the GPU work (channel/push selection, per-page copy-mask
computation, PTE/mapping updates in `uvm_va_block_service_finish()`), all of which must
happen while the va_space lock is held regardless of whether the fault was demand-driven
or speculatively prefetched. This is also the source-level reason Phase B's async offload
found no system-level gain (per `PHASEC_REPORT.md`'s "Decision" section): moving *when* a
fault is discovered (prefetch vs demand) does not reduce the *per-fault* CPU cost of this
orchestration step, since that cost is paid inside the lock either way and is not GPU-wait
time that async submission could have hidden in the first place.

## 5. Manuscript-ready sentence

> Source-level analysis of `service_fault_batch_dispatch()` (`uvm_gpu_replayable_faults.c:2265-2354`,
> the 595.71.05 tree) shows that D5's measured cost is CPU-side fault classification and
> residency bookkeeping culminating in an asynchronous GPU push (`uvm_push_end()`, not a
> blocking wait) for GPU-destination migrations, confirming that the va_space-lock-held
> dispatch cost this project measures is not itself GPU wait time and therefore cannot be
> hidden by asynchronous prefetching, regardless of when the underlying fault is
> discovered.

*(Citations into `uvm_va_block.c` supporting sections 2-4 above are against the
v580.95.05 tree, per the provenance caveat in section 0 -- not independently verified
against 595.71.05, since no 595 copy of that file exists on this machine.)*
