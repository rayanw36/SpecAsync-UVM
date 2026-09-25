# Gate E0.9b — First-touch oracle lookahead sweep (unattended session)

*Draft — sections are filled in as each step completes. Status log:
`E09B_STATUS.md`.*

Platform for every number in this report: RTX 5070 Ti, driver 595.91.07,
kernel 7.0.0-34-generic, SpecAsync module srcversion
`5997D238EF080B77DBD2AAF` (built from `ea1a262`, verified in E0.9a-2).

## Step 0 — Preflight

See `E09B_STATUS.md` Step 0. All checks passed.

## Step 1 — Source checks (read-only)

### Q1. Where are speculative predictions lost?

**`ft_predictions − enqueued` counts items dropped at enqueue, and the drop
counter is `specasync_drops`** (`g_specasync_drops`). Every nonzero policy-6
prediction reaches `specasync_enqueue()`
(`driver/src/uvm_gpu_replayable_faults.c:382-420`). Its three early returns
are: (a) `!g_specasync_wq || specasync_policy == 0 || spec_addr == 0`
(line 390) — never taken for a policy-6 prediction, which is nonzero by
construction; (b) queue full, `g_specasync_queue_depth >=
SPECASYNC_MAX_QUEUE_DEPTH` (1,024, line 101) — increments
`g_specasync_drops` (lines 392-394); (c) `kzalloc(GFP_ATOMIC)` failure —
also increments `g_specasync_drops` (line 402). Every other path
increments `g_specasync_enqueued` (line 419). So, by construction:

    ft_predictions = enqueued + drops        (exact identity)

This identity is checked on every sweep run (Step 4) rather than assumed.

**An enqueued item whose page is already resident on the GPU when the
worker reaches it *is* counted in `spec_migrations`.** The worker
(`specasync_worker_fn`, lines 279-378) counts `spec_migrations` whenever
`uvm_va_block_make_resident()` returns `NV_OK` (lines 341-344). That
function's copy step (`uvm_va_block_make_resident_copy`,
`uvm_va_block.c:4740-4845`) masks already-resident pages out of both the
unmap set (`uvm_page_mask_andnot(unmap_page_mask, page_mask,
resident_mask)`, line 4783) and the copy, and has no error path for "nothing
to do" — it returns `NV_OK`. **So `spec_migrations` counts successful
`make_resident` calls, including no-op calls on pages already resident.**
It is not a count of pages actually moved. No existing counter separates the
two (stock UVM's `num_pages_in` lives in a debug-only procfs file, disabled
in this release build — `uvm_procfs.c:36-42`, `uvm_gpu.c:1044-1045`).

Items lost *after* enqueue are `enqueued − spec_migrations`: `THROTTLED`
results (block-lock `trylock` failure, context-alloc failure, address outside
the block, or `make_resident` error — lines 309-347), plus items whose block
lookup fails and fall through to the depth-0 path (lines 356-366).

Bearing on the pre-registered metric *pre-staged coverage =
`spec_migrations` ÷ distinct pages*: it is an **upper bound** on pages
actually moved ahead of demand, not an exact count. E0.9a-2's data
(`fault_already_resident` within 0.05% of `spec_migrations` at every L)
indicates the no-op share is small, but that is an inference from a second
counter, not a measurement of it — stated as such in the pre-registration.

### Q2. Does the stock prefetcher's region get mapped in the same service step?

**Yes.** On the demand path, `uvm_va_block_service_locked()`
(`uvm_va_block.c:12021`) calls `uvm_va_block_get_prefetch_hint()` (line 12046)
(`uvm_va_block.c:11487-11539`) before servicing. That function ORs the
prefetcher's pages into the same `new_residency` mask as the faulting pages
(`uvm_page_mask_or(new_residency_mask, new_residency_mask,
prefetch_pages_mask)`, line 11532), gives them access type
`UVM_FAULT_ACCESS_TYPE_PREFETCH` (line 11520), and widens the service region
to cover them (line 11533). `uvm_va_block_service_finish()` then computes a
mapping protection for **every page in `new_residency_mask`**
(`uvm_va_block.c:11961`) and `block_service_finish_map()`
(`uvm_va_block.c:11770`, step "3.2 — Add new mappings") maps each
protection group via `uvm_va_block_map()`.

**So prefetched pages are migrated and mapped in the same call as the fault
that triggered them.** A later access to a prefetched page finds a valid GPU
mapping and does not fault. The prefetcher can therefore *prevent* faults;
the off-path speculative worker, which only calls
`uvm_va_block_make_resident()` and never reaches `service_finish()`
(E0.9a-2 §3), can only make them cheaper. This asymmetry is structural and
the paper can state it from source.

### Q3. What servicing-time instrumentation exists without new code?

**No per-run aggregate timer exists.** The full set of debugfs aggregate
counters is: `processed, enqueued, drops, demand_faults, spec_hits,
spec_migrations, trace_pushes, trace_overwrites, oracle_consumes,
oracle_wraps, oracle_correct, oracle_predictions, ft_predictions,
ft_skipped, ft_held, ft_unknown_page, ft_exhausted, fault_already_resident`
(`specasync_debugfs.c`) — all counts, no time sums. Stock UVM's
`fault_stats` procfs file is counts only (`uvm_gpu.c:711-757`) and is
debug-build-only.

Time exists only in three **drop-on-full** rings, each 131,072 slots
(`specasync_telemetry.h:161,183,184`), all gated on `specasync_log_enabled`:

| ring | record | granularity | time fields |
|---|---|---|---|
| `specasync_decomp_log` | 112 B | one per serviced top-level batch in `uvm_parent_gpu_service_replayable_faults()` (pushed at `uvm_gpu_replayable_faults.c:~3577` cancel path, `~3626` normal path) | `d1_start … d6_end`, `svc_start/svc_end`, `num_faults`, `num_blocks` |
| `specasync_log` (batch) | 72 B | one per `service_fault_batch()` call | `t0 … t4` |
| `specasync_worker_log` | 48 B | one per worker item | enqueue/dequeue/completion |

The decomp ring is the natural servicing-time source: per top-level batch,
servicing window = (`d6_end` if nonzero, else `svc_end`) − `d1_start`, and
`num_blocks` counts dispatch groups. **Whether it saturates on a full
Stencil-24K run is not known from source** — it depends on the number of
top-level batches per run (the T4 recorded 88,171 batch records for a
3.24M-fault Stencil-24K rep, under the 131,071 cap, but that is a different
platform). Because the ring is drop-on-full with no reader-side draining,
**a run whose record count is below 131,071 dropped nothing and covers 100%
of batches and dispatch groups exactly**; a run at exactly 131,071 saturated
and covers an unknown-to-the-ring fraction. Step 2 measures this directly.
