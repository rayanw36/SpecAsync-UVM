# SpecAsync-UVM — Annotated Source Excerpts

Extracted from `driver/src/` on branch `phaseC-decomp` (commit `f8d058b`), the
most complete branch. Per `results/phaseB1/DATAFLOW_READBACK.md`, the file
`uvm_gpu_replayable_faults.c` in `driver/src/` is the **integrated file that
actually compiles into the loaded `.ko`** — `specasync_faults_instrumentation.c`
(also present in `driver/src/`) is authoring-only scaffolding, not compiled
(not in the Kbuild source list), and should not be quoted as the real
implementation.

Raw copies of all five `driver/src/` files are included alongside this file in
`manuscript_assets/source/` for exact reference. Line numbers below refer to
`driver/src/uvm_gpu_replayable_faults.c` as it stood at commit `f8d058b`.

---

## 1. `spec_work_item` struct and synchronization primitives

`driver/src/uvm_gpu_replayable_faults.c:221-228`

```c
struct spec_work_item {
	struct work_struct          work;
	uvm_va_space_t             *va_space;
	u64                         speculative_addr;
	struct specasync_hit_table *hit_table;
	u64                         enqueue_ts_ns;
	uvm_gpu_t                  *gpu;  /* retained; NULL at depth=0, set at depth>=1 */
};
```

Queue primitive: a single global `struct workqueue_struct *g_specasync_wq`
(`WQ_UNBOUND | WQ_HIGHPRI`, allocated in `uvm.c:uvm_init()`), with an
`atomic_t g_specasync_queue_depth` admission counter capped at
`SPECASYNC_MAX_QUEUE_DEPTH = 1024` (line 63; raised from 512 during Phase B.2
Gate 1 to absorb per-fault enqueue bursts). Work items are heap-allocated
(`kzalloc(GFP_ATOMIC)`) per speculative address and freed by the worker itself
after `specasync_work_ring_push()`.

---

## 2. Predictor policy implementations

`driver/src/uvm_gpu_replayable_faults.c:134-217`, dispatched by
`specasync_predict_next(va_space, fault_addr, batch_faults)`. Policy constants
(`driver/src/specasync_telemetry.h:90-95`):

| Value | Constant | Candidate-generation logic |
|---|---|---|
| 0 | `SPECASYNC_POLICY_DISABLED` | Returns 0 (no-op). |
| 1 | `SPECASYNC_POLICY_ADJACENT` | `fault_addr + PAGE_SIZE`. Fixed next-page guess. |
| 2 | `SPECASYNC_POLICY_STRIDE` | Per-VA-space `specasync_stride_state{last_fault_addr, last_delta, confidence}`. On each call, compares the new delta to the last; matching deltas saturate `confidence` up to 4, mismatches decay it. Predicts `fault_addr + last_delta` once `confidence >= 2 && last_delta != 0`, else falls back to adjacent. |
| 3 | `SPECASYNC_POLICY_MARKOV` | Per-VA-space open-addressed hash table, `SPECASYNC_MARKOV_SLOTS = 256` entries keyed by Fibonacci hash of the *previous* fault page (`page * 0x9e3779b97f4a7c15ULL`). Records `last_page → current_page` transitions on each call, then looks up `current_page → next_page`. Falls back to adjacent if no entry. |
| 5 | `SPECASYNC_POLICY_NULL` | Returns `fault_addr + PAGE_SIZE` (so `specasync_enqueue()` still fires) but the worker (`specasync_worker_fn`) checks `specasync_policy == SPECASYNC_POLICY_NULL` first and returns immediately with `result = SPECASYNC_RESULT_NULL`, doing **no** lookup. This is the Gate C isolation control — it separates "worker exists and runs" overhead from "worker does prediction work" overhead. |
| 4 | `SPECASYNC_POLICY_ORACLE` | Calls `specasync_oracle_next_addr_n(batch_faults)` (`specasync_debugfs.c:343-358`) — an O(1) atomic cursor (`atomic_fetch_add`) into a preloaded trace array, advanced by the number of faults the *current batch* will service (the Gate B fix; the original code advanced by 1 per batch regardless of batch size, permanently desyncing the cursor after the first coalesced batch). |
| default | — | Falls back to adjacent. |

Per-VA-space prediction state (`struct specasync_predict_state`, allocated in
`specasync_predict_state_alloc()` / freed in `specasync_predict_state_free()`,
lines 93-126) bundles the stride state, the Markov table (`kvmalloc`'d), and
the hit table.

---

## 3. Depth-0 vs depth-1 branch (`specasync_worker_fn`)

`driver/src/uvm_gpu_replayable_faults.c:230-326`

The worker always takes `uvm_va_space_down_read(item->va_space)` then calls
`uvm_va_block_find(item->va_space, item->speculative_addr, &va_block)` — a
find-existing (not find-create) lookup.

**depth=0 (metadata-only, the Phase B / Phase B.1 default), lines 305-315:**
```c
uvm_va_space_up_read(item->va_space);

if (status == NV_OK && va_block && item->hit_table) {
	specasync_hit_table_insert(item->hit_table,
				   item->speculative_addr,
				   ktime_get_ns());
	wrec.result = SPECASYNC_RESULT_HIT;
} else {
	wrec.result = SPECASYNC_RESULT_MISS;
}
```
The looked-up `va_block` is discarded immediately. No migration, no mapping —
only a `(va_addr, ts_ns)` tag is left in the per-VA-space hit table. This is
why a "hit" at depth=0 measures prediction correctness only and carries zero
time saving (established in Phase B.1 Gate A, re-confirmed Phase B.2 Gate 2).

**depth=1 (residency offload, added Phase B.2 Gate 2), lines 251-303** — the
`make_resident` call site:
```c
if (status == NV_OK && va_block && specasync_offload_depth >= 1 && item->gpu) {
	uvm_va_block_context_t *ctx = uvm_va_block_context_alloc(NULL);

	if (ctx && item->speculative_addr >= va_block->start &&
	    item->speculative_addr <  va_block->end) {

		uvm_va_block_retry_t retry;
		uvm_page_mask_t      pmask;
		uvm_page_index_t     pidx;
		NV_STATUS            mstatus = NV_ERR_BUSY_RETRY;

		uvm_va_block_context_init(ctx, NULL);
		pidx = uvm_va_block_cpu_page_index(va_block, item->speculative_addr);
		uvm_page_mask_zero(&pmask);
		uvm_page_mask_set(&pmask, pidx);
		uvm_va_block_retry_init(&retry);

		if (uvm_mutex_trylock(&va_block->lock)) {
			mstatus = uvm_va_block_make_resident(
				va_block, &retry, ctx,
				item->gpu->id,
				uvm_va_block_region_for_page(pidx),
				&pmask, NULL,
				UVM_MAKE_RESIDENT_CAUSE_PREFETCH);
			uvm_va_block_retry_deinit(&retry, va_block);
			uvm_mutex_unlock(&va_block->lock);
		} else {
			uvm_va_block_retry_deinit(&retry, va_block);
		}
		...
```
`uvm_va_block_make_resident()` is the exact call site — one page
(`uvm_page_mask_set(&pmask, pidx)` selects a single page index), destination
`item->gpu->id`, cause `UVM_MAKE_RESIDENT_CAUSE_PREFETCH`. `item->gpu` is only
non-NULL when `specasync_offload_depth >= 1` (retained in `specasync_enqueue()`,
line 358-360, released in the worker at line 318-319 / 301 on the depth=1 path).

---

## 4. Throttle / trylock logic

`driver/src/uvm_gpu_replayable_faults.c:274-296`. The depth=1 path takes
`uvm_mutex_trylock(&va_block->lock)` — **non-blocking**. If the block lock is
already held (almost always true when the predicted page falls in the same 2 MB
VA block as the fault currently being serviced by the demand path, which Phase
B.2 Gate 2 measured at 76.1% of predictions), the trylock fails and the branch
aborts with `wrec.result = SPECASYNC_RESULT_THROTTLED` (line 295, and the
`mstatus != NV_OK` case at line 292-293). No blocking wait, no retry — the
speculative migration is simply dropped for that prediction. This is the
mechanism Phase B.2's `DECISION.md` identifies as the primary reason Path B
cannot win: predicted pages are almost always in the same locked block as the
fault that triggered the prediction.

---

## 5. Instrumentation points — T0–T4 and D1–D7

All timestamps use `ktime_get_ns()`. T0–T4 live in `service_fault_batch()`
(per-batch record, `struct specasync_batch_record`, pushed every batch
regardless of `SPECASYNC_DECOMP`). D1–D7 live in the caller,
`uvm_parent_gpu_service_replayable_faults()` (per-outer-iteration record,
`struct specasync_decomp_record`, pushed only when `SPECASYNC_DECOMP=1`,
Phase C addition).

| Label | File | Function | Line | What it brackets |
|---|---|---|---|---|
| T0 | `uvm_gpu_replayable_faults.c` | `service_fault_batch` | 2575 | `_sa_rec.t0_ns = ktime_get_ns();` — batch entry, immediately after batch-record init. |
| T1 | `uvm_gpu_replayable_faults.c` | `service_fault_batch` | 2661 | `if (!_sa_rec.t1_ns) _sa_rec.t1_ns = ktime_get_ns();` — set once, right after the first `uvm_va_space_down_read(va_space)` for this batch. |
| T2 | `uvm_gpu_replayable_faults.c` | `service_fault_batch` | 2698 | `if (!_sa_rec.t2_ns) _sa_rec.t2_ns = ktime_get_ns();` — set once, immediately **before** the first call to `service_fault_batch_dispatch()`. (Phase B.2 Gate 4 fix: previously T2 and T3 were both stamped *after* dispatch, making the "residency" phase identically zero — see Gate C / Gate 4 reports.) |
| T3 | `uvm_gpu_replayable_faults.c` | `service_fault_batch` | 2754-2755 | `u64 _t3 = ktime_get_ns(); _sa_rec.t3_ns = _t3;` — immediately **after** `service_fault_batch_dispatch()` returns; overwritten on each dispatch call within the batch, so it holds the timestamp of the *last* dispatch. Also the point at which `specasync_hit_table_consume()` is called for every fault the just-completed dispatch serviced. |
| T4 | `uvm_gpu_replayable_faults.c` | `service_fault_batch` | 2805 | `_sa_rec.t4_ns = ktime_get_ns();` — batch exit, right before `specasync_batch_ring_push(&_sa_rec)` and the `return status;`. No `uvm_tracker_wait()` occurs before this — migration DMA completes asynchronously, off-window (Gate C finding). |
| D1 | `uvm_gpu_replayable_faults.c` | `uvm_parent_gpu_service_replayable_faults` | 3359 (start) / 3363 (end) | `fetch_fault_buffer_entries()` — fault-buffer drain. |
| D2 | `uvm_gpu_replayable_faults.c` | `uvm_parent_gpu_service_replayable_faults` | 3375 (start) / 3379 (end) | `preprocess_fault_batch()` — sort/dedup/coalesce. |
| D3 | `uvm_gpu_replayable_faults.c` | `service_fault_batch` (accumulated into `_dec` param passed from caller) | 2645-2653 | Cumulative VA-space lock **wait**: `_lock_req = ktime_get_ns(); mm = uvm_va_space_mm_retain_lock(...); ...; uvm_va_space_down_read(va_space); _hold_start = ktime_get_ns(); _dec->d3_wait_ns += _hold_start - _lock_req;` — accumulated across every va_space acquisition in the batch. |
| D4 | `uvm_gpu_replayable_faults.c` | `service_fault_batch` | 2624-2626 (release-on-switch), 2729-2731 (release-on-continue), 2797-2798 (release-on-exit) | Cumulative VA-space lock **hold**: `_dec->d4_hold_ns += ktime_get_ns() - _hold_start;` at every point the lock is released. Encompasses D5 by construction. |
| D5 | `uvm_gpu_replayable_faults.c` | `service_fault_batch` | 2702-2711 | Cumulative CPU time inside `service_fault_batch_dispatch()`: `_d5_start = ktime_get_ns(); status = service_fault_batch_dispatch(...); _dec->d5_serv_ns += ktime_get_ns() - _d5_start;`. Subset of D4. |
| D6 | `uvm_gpu_replayable_faults.c` | `uvm_parent_gpu_service_replayable_faults` | 3447/3451 (BATCH policy) or 3466/3470 (BATCH_FLUSH policy) | Replay push: `push_replay_on_parent_gpu()` or `fault_buffer_flush_locked()`. |
| D7 | *(derived, not a direct timestamp)* | — | — | Residual: `(svc_start − d2_end) + (d6_start − svc_end) + other` — scheduling gaps and untimed work between the measured windows. Defined in `specasync_telemetry.h:110-112`. |
| svc | `uvm_gpu_replayable_faults.c` | `uvm_parent_gpu_service_replayable_faults` | 3390/3392 | `_dec.svc_start = ktime_get_ns(); status = service_fault_batch(...); _dec.svc_end = ktime_get_ns();` — wraps the entire `service_fault_batch()` call (≈ D3+D4+overhead). |

All D-phase instrumentation is compiled out entirely when `SPECASYNC_DECOMP=0`
(`specasync_telemetry.h:19-21`, default 1) — this is what Gate G3 in
`results/phaseC/PHASEC_REPORT.md` measured at +0.64% overhead when enabled.

---

## 6. Module parameters (`specasync_*`)

Defined in `driver/src/specasync_debugfs.c:38-57`.

| Parameter | Type | Default | Permission | Meaning |
|---|---|---|---|---|
| `specasync_log_enabled` | `int` | `1` | `0644` (runtime-writable) | Enable/disable telemetry ring buffers (batch/work/decomp rings). |
| `specasync_policy` | `int` | `1` (adjacent) | `0644` | Prediction policy: 0=disabled, 1=adjacent, 2=stride, 3=markov, 4=oracle, 5=null. |
| `specasync_offload_depth` | `int` | `0` (metadata-only) | `0644` | 0 = metadata lookup only; 1 = speculative `make_resident` migration; 2 is referenced as "stub(unsafe)" in the MODULE_PARM_DESC but the depth=1 code path is the only one implemented in this source. |
| `specasync_trace_faults` | `int` | `0` | `0644` | Enable recording of demand-fault addresses into the fault-trace ring (used to build oracle traces). |
| `specasync_oracle_trace_path` | `char *` | `NULL` | `0444` (**init-only**, cannot be changed after module load) | Path to a flat binary `u64[]` file of future fault addresses, loaded at `specasync_debugfs_init()` time only if `specasync_policy == 4` at that moment. This 0444 permission is a documented foot-gun (`PIPELINE_FIXES.md` FIX-2, `GATE_B_diagnosis.md`): flipping `specasync_policy` to 4 *after* load without having set this path at insmod time silently loads no trace. |

Stock UVM parameters also present in the same file for context (unmodified by
SpecAsync, `uvm_gpu_replayable_faults.c:403-454`):
`uvm_perf_reenable_prefetch_faults_lapse_msec` (default 1000),
`uvm_perf_fault_batch_count` (default 256),
`uvm_perf_fault_replay_policy` (default `BATCH_FLUSH`),
`uvm_perf_fault_replay_update_put_ratio` (default 50),
`uvm_perf_fault_max_batches_per_service` (default 20),
`uvm_perf_fault_max_throttle_per_service` (default 5),
`uvm_perf_fault_coalesce` (default 1).

---

## 7. debugfs interface

Implemented in `driver/src/specasync_debugfs.c`. Root directory:
`debugfs_create_dir("specasync", parent_dentry)` (line 477), mounted under
whatever `parent_dentry` the caller passes — the v595 port passes `NULL`
(`driver/PORTING_NOTES_595.md`), so files land at `/sys/kernel/debug/specasync/`.

| File | Mode | Record format | Ring size |
|---|---|---|---|
| `specasync_log` | `0444` (read-only) | `struct specasync_batch_record`, 72 B, `struct.unpack('<6Q6I')` | `SPECASYNC_BATCH_RING_SLOTS = 1<<17` (131,072 slots × 72 B ≈ 9.4 MB) |
| `specasync_worker_log` | `0444` | `struct specasync_work_record`, 48 B, `struct.unpack('<4Q4I')` | `SPECASYNC_WORK_RING_SLOTS = 1<<17` (131,072 × 48 B ≈ 6.3 MB) |
| `specasync_decomp_log` | `0444` | `struct specasync_decomp_record`, 112 B, `'<12Q4I'` | `SPECASYNC_DECOMP_RING_SLOTS = 1<<17` (131,072 × 112 B ≈ 14.7 MB) |
| `specasync_clear` | `0222` (write-only) | write any byte to reset all three rings (head/tail/drops to 0, then `memset` the backing buffers outside the lock) | — |
| `specasync_fault_trace` | `0444` | flat `u64[]` of demand-fault VAs, no header | `SPECASYNC_TRACE_RING_SLOTS = 1<<20` (1,048,576 × 8 B = 8 MB) |

`specasync_batch_record` field layout (`specasync_telemetry.h:46-59`):
`batch_id`(u64) `t0_ns..t4_ns`(5×u64) `num_faults, spec_enqueues, spec_drops,
spec_hits, enqueue_overhead_ns`(5×u32) `_pad`(u32) = 72 B, verified by
`static_assert` in `uvm_gpu_replayable_faults.c:369-379`.

`specasync_work_record` (`specasync_telemetry.h:73-81`): `enqueue_ts_ns,
dequeue_ts_ns, completion_ts_ns, va_addr`(4×u64) `result, policy_used`(2×u32)
`_pad[2]` = 48 B. `result`: 0=null 1=miss 2=hit 3=migration_done 4=throttled.

`specasync_decomp_record` (`specasync_telemetry.h:132-149`): `batch_id,
d1_start, d1_end, d2_start, d2_end, svc_start, svc_end, d6_start, d6_end,
d3_wait_ns, d4_hold_ns, d5_serv_ns`(12×u64) `num_faults, num_va_spaces,
num_blocks`(3×u32) `_pad`(u32) = 112 B.

The ring read implementation (`ring_read_binary()`, lines 78-127) had a bug
found and fixed during Phase C: it returned `to_copy` bytes to the caller
while only writing a record-size-aligned subset via `copy_to_user`, causing
`*ppos` drift that corrupted downstream Python parsing after ~1170 records
(`PHASEC_REPORT.md`, "Root-Cause Note: ring_read_binary Fix"). Fixed by
snapping `to_copy` to a multiple of `record_size` before advancing `*ppos`
(reflected in the current source above).

---

## 8. Diff size vs. stock

**Could not be computed directly** — the pristine NVIDIA 595.71.05 source tree
is not present anywhere in this repository (it lives only at
`/usr/src/nvidia-595.71.05/` on the original GPU instance, per
`EXPERIMENTS.md` and `results/phaseB/gate_reports/gate0_env.md`, which this
discovery task's environment does not have access to — see MANIFEST.md
environment-mismatch note). `git diff --stat` against the pristine tree could
not be run.

What is available instead: `driver/patches/specasync_uvm_v595.71.05.patch`
(the originally-generated unified diff against stock 595.71.05, unified-diff
`-p4` format). Parsed directly from the patch text:

- **8 files touched**: `nvidia-uvm-sources.Kbuild`, `specasync_debugfs.c` (new),
  `specasync_internal.h` (new), `specasync_telemetry.h` (new), `uvm.c`,
  `uvm_gpu_replayable_faults.c`, `uvm_va_space.c`, `uvm_va_space.h`.
- **1,112 lines** in the patch file; **835 added lines**, **0 removed lines**
  counted from `+`/`-` diff markers (Phase B baseline only adds code, never
  deletes stock lines).

**Caveat — this patch is stale relative to the current source.** It captures
only the original Phase B port. `driver/src/uvm_gpu_replayable_faults.c` at
HEAD is 3,591 lines and includes substantial later additions not reflected in
any regenerated patch file: the Gate 1 per-fault enqueue loop, the Gate 2
depth=1 residency path in `specasync_worker_fn`, the `SPECASYNC_POLICY_NULL`
control, and all of the Phase C `SPECASYNC_DECOMP` D1–D7 instrumentation. No
patch file capturing the cumulative Phase B+B.1+B.2+C diff against stock was
found in the repository — see MANIFEST.md gap list.
