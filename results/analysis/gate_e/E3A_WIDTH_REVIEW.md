# Gate E3a — Speculative width: implementation for review (compiled, NOT loaded)

**Status: compiled only. The new module has never been loaded.** It must not
be loaded until this diff has been reviewed (HARD STOP, per the gate brief).

| item | value |
|---|---|
| Sources | `driver/src-e3a/` (overlay; **`driver/src/` is untouched**, so `git diff ea1a262 HEAD -- driver/src` stays empty and the verified module's preflight is unaffected) |
| Patch | `driver/patches/e3a_spec_width.patch` (`diff -u driver/src driver/src-e3a`), reproduced in full in §7 |
| Build tree | `~/specasync-work/nvidia-595.91.07-specasync-e3a`, a **new** tree. The verified tree is untouched. |
| Build procedure | `driver/scripts/reconstruct_build_tree.sh` (SRC=`/usr/src/nvidia-595.91.07`, full 5-module set), unmodified, **first built from the unmodified `driver/src`, which reproduced srcversion `5997D238EF080B77DBD2AAF` exactly** (so the tree is the verified build's tree). Then the 4 overlay files were copied in and rebuilt incrementally. |
| Compiler output | `make` exit 0; **0 warnings, 0 errors** (only "Skipping BTF generation … vmlinux", as in every earlier build) |
| New module | `driver/build/595.91.07/nvidia-uvm-specasync-NEW-e3a-width-UNREVIEWED.ko`, srcversion **`91F634807244D31148A8597`**, vermagic **`7.0.0-34-generic SMP preempt mod_unload modversions`** (matches `uname -r`), sha256 `7aaf7c19…2c78`. Gitignored (`*.ko`); rebuild from the patch. |
| Verified module | `nvidia-uvm-specasync-NEW-e0.9a2-fixed.ko`: unchanged (sha256 `ab91372b…31be`, srcversion `5997D238…`), **still the loaded module** |

## 1. What the change does

- **`specasync_spec_width` (W).** A new module parameter, in pages, with
  default 1.
  - It is validated by a `module_param_cb` setter: an integer, a power of
    two, in [1, 512]. Anything else makes the setter return `-EINVAL`, so
    **`insmod` itself fails**, with `pr_err("specasync: specasync_spec_width=%d
    rejected: must be a power of two in [1, 512]")`.
  - `specasync_debugfs_init()` could not do this, because its failure is
    non-fatal to module load (`uvm.c:1197`).
  - Permissions are 0444, so W is fixed for the module's lifetime.
- **Worker** (`specasync_worker_fn`). At W > 1, for a predicted page at
  index *i* in its VA block, it makes the region
  `[align_down(i, W), min(align_down(i, W) + W, block_pages))` resident. It
  uses the same `uvm_va_block_make_resident()` call as before, with that
  region and a mask filled over it.
  - Every bound is checked explicitly in `specasync_width_region()`.
  - Block liveness is re-checked under the block lock.
  - On any failure the item is skipped (no `make_resident` call) and
    counted in `specasync_spec_region_invalid`.
- **Prediction side** (Gate 1 loop, policy 6 only, W > 1).
  - `region_id = va >> (PAGE_SHIFT + log2 W)`.
  - If `region_id` equals the region ID of the last **enqueued** prediction,
    the prediction is not enqueued: `ft_same_region++`.
  - Otherwise it is enqueued as before. The stored ID is updated only if
    `specasync_enqueue` actually queued the item; it now returns `bool`,
    with every side effect unchanged. So a queue-full drop does not suppress
    the next prediction in that region.
  - The cursor logic in `specasync_ft_predict` is **unchanged**.
- **New counters** (debugfs; reset by `specasync_clear`):
  - `specasync_ft_same_region`;
  - `specasync_spec_pages_requested`: the sum of region sizes passed to
    `make_resident`, atomic64, counted at every W. At W = 1 it equals the
    number of `make_resident` calls, which is a regression check.
  - `specasync_spec_region_invalid`.

## 2. W = 1 is the pre-E3a behaviour

Every new branch is guarded by `specasync_spec_width > 1`. At W = 1:

| site | W = 1 path | vs. pre-E3a |
|---|---|---|
| Gate 1 loop | `else { specasync_enqueue(...) }`, the same call with the same arguments; the new `bool` return is discarded | identical UVM/specasync behaviour. The only addition is one extra `int` compare per coalesced fault. |
| `specasync_enqueue` | return type `void` → `bool`; every statement and side effect unchanged | identical |
| Worker, region/mask | `sregion = uvm_va_block_region_for_page(pidx)` (the same pure value the old code computed inline at the call), `uvm_page_mask_zero`, `uvm_page_mask_set(&pmask, pidx)`, in the same order as before | identical arguments to `make_resident` |
| Worker, lock | `sregion_ok` is `true`, and the `is_dead` re-check is skipped at W = 1 | identical |
| Worker, counter | `atomic64_add(1, &g_specasync_spec_pages_requested)` after `make_resident` | **new side effect**: one atomic add on a specasync counter, touching no UVM state |
| Init log line | `init OK … spec_width=%d` | dmesg text only |

**No duplicate predictions under policy 6, so the same-region rule would be
inert at W = 1 even if it were not guarded.**
- `specasync_ft_predict` (`specasync_debugfs.c:745-799`) returns
  `g_ft_table[old_next]` and, under `g_ft_cursor_lock`, sets
  `g_ft_next_to_predict = old_next + 1`.
- The cursor otherwise only moves forward (`= r + 1` when `old_next <= r`).
  It is reset only by `specasync_clear`.
- The table is the list of **distinct** pages in first-touch order
  (`prepare_first_touch_table.py`; the distinct-page assertion holds).
- So each table entry is returned at most once per clear, and no two
  predictions in a run name the same page.

At W = 1 a region is one page, so the rule could only have fired on a
duplicate, and there are none.

## 3. Functions the new code calls, and their preconditions

Line numbers are in the pristine `/usr/src/nvidia-595.91.07/nvidia-uvm/`. "Worker line N" refers to the **pre-E3a** `driver/src/uvm_gpu_replayable_faults.c`; the same lines sit 45 lines lower in `driver/src-e3a/`.
**"Assert-only"** means the check is a `UVM_ASSERT`, which is non-fatal in
release builds. Each such check is guarded explicitly.

| function (file:line) | where called | locks required | can return NULL / error? | assert-only checks | how the new code guards it |
|---|---|---|---|---|---|
| `uvm_va_block_is_hmm` (uvm_va_block.h:656) | `specasync_width_region` | none (reads `va_block->hmm.va_space`) | no | none | `va_block` NULL-checked first; the caller only reaches it with `status == NV_OK && va_block` (existing condition) |
| `va_block->managed_range` (field, uvm_va_block.h:290) | `specasync_width_region` | read under the VA-space read lock (held from `uvm_va_space_down_read`, worker line 297) | may be NULL for HMM or dead blocks | — | the region is refused unless `!is_hmm && managed_range`, **and** liveness is re-checked under the block lock (next row) |
| `uvm_va_block_is_dead` (uvm_va_block.h:669) | worker, under `va_block->lock`, W > 1 only | block lock (held: `uvm_mutex_trylock` succeeded) | no | none | block kill sets `managed_range = NULL` (uvm_va_block.c:9444). If dead: skip and count, no `make_resident` |
| `uvm_va_block_region` (uvm_va_block.h:1601) | `specasync_width_region` | none (pure) | no | **`UVM_ASSERT(first <= outer)`** | explicitly `first ≤ pidx < outer ≤ npages ≤ 512` before the call |
| `uvm_va_block_region_for_page` (uvm_va_block.h:1610) | worker (initial `sregion`) | none | no | via `uvm_va_block_region` (`pidx ≤ pidx + 1`, always true) | same call the verified code made |
| `uvm_va_block_region_num_pages` (uvm_va_block.h:1615) | worker counter | none | no | none | region already validated |
| `uvm_page_mask_zero` (uvm_va_block.h:1782) | worker (existing call) | none | no | none | `bitmap_zero` over the full 512-bit stack mask |
| **`uvm_page_mask_region_fill`** (uvm_va_block.h:1764) | worker, W > 1 | none | no | **none at all**: raw `bitmap_set(mask, first, outer − first)`. An out-of-range region would **corrupt the kworker stack** | only called when `specasync_width_region` returned true, which guarantees `outer ≤ npages ≤ PAGES_PER_UVM_VA_BLOCK = 512` |
| `uvm_page_mask_set` (uvm_va_block.h:1720) | worker, W = 1 | none | no | — | the existing call, unchanged |
| `uvm_va_block_cpu_page_index` (uvm_va_block.h:1580) | worker (existing call) | none | no | **`UVM_ASSERT(addr >= start)`, `UVM_ASSERT(addr <= end)`** | the existing guard `speculative_addr >= start && < end` (worker line 309-310), unchanged. `specasync_width_region` re-checks `pidx < npages` |
| **`uvm_va_block_make_resident`** (uvm_va_block.c:4968; contract uvm_va_block.h:760-787) | worker (existing call, now with a multi-page region at W > 1) | **block lock held** (trylock succeeded; `uvm_assert_mutex_locked` is assert-only, and satisfied). With `ctx->mm == NULL`, no `mmap_lock` is required. The VA-space read lock is held. | returns `NV_STATUS`, never a pointer. Internally uses **`block_resident_mask_get_alloc`** (uvm_va_block.c:2304), the *allocating* getter, which returns NULL → `NV_ERR_NO_MEMORY` handled inside. This is not the non-allocating getter behind the E0.9a-2 crash. | `UVM_ASSERT(is_hmm \|\| managed_range)` (make_resident_copy, :4765). The prefetch-cause assert (:4758) is not reached, because `prefetch_page_mask == NULL`. | managed, non-HMM, not dead: checked explicitly before and under the lock. Region ⊆ block (checked). `page_mask` is filled exactly from the region. `ctx` non-NULL (existing `ctx &&`) and initialised (`uvm_va_block_context_init(ctx, NULL)`, existing). Non-OK status → item counted THROTTLED (existing handling). |
| `uvm_va_block_retry_init` / `_deinit` (uvm_va_block.c:169 / 810) | worker (existing calls) | deinit is called with or without the block lock, exactly as the existing trylock-failure path already does | no | HMM-only assert in deinit (:831); non-HMM enforced | a new path, "region invalid", calls `retry_deinit` without the lock, the same as the existing trylock-failure path |
| `uvm_mutex_trylock` / `uvm_mutex_unlock` (uvm_lock.h:959) | worker (existing) | — | — | lock-tracking asserts | unchanged; never a blocking lock |
| kernel: `kstrtoint`, `is_power_of_2`, `ilog2`, `param_get_int`, `module_param_cb` | param setter | none | `kstrtoint` returns an error code | — | the error → `-EINVAL`. The kernel never calls `.set` with `val == NULL` for ops without `KERNEL_PARAM_OPS_FL_NOARG` (`kernel/params.c` `parse_one`). |
| kernel: `DEFINE_DEBUGFS_ATTRIBUTE` + `debugfs_create_file_unsafe` | debugfs init | none | creation failure is ignored, like the existing `debugfs_create_atomic_t` calls | — | the getter reads an atomic64; no pointers |
| kernel: `READ_ONCE`/`WRITE_ONCE` on `g_specasync_last_region`, `atomic_inc`, `atomic64_add/set` | Gate 1 loop, worker, clear | none | no | — | plain globals; see the race note in §5 |

**Every pointer the new code dereferences:**
- `va_block` in `specasync_width_region`: NULL-checked in the helper, and
  non-NULL by the caller's existing condition.
- `va_block->hmm.va_space`, `->managed_range`, `->start`, `->end`: fields
  of that non-NULL block, read under the VA-space read lock.
- `out`: NULL-checked, and always the address of a stack local.
- `&pmask`, `&sregion`: stack locals.
- `item->gpu->id`: the existing call, already guarded by
  `item->gpu` in the enclosing condition (worker line 300).
- `ctx`: guarded by the existing `ctx &&`.
- In the Gate 1 loop the new code dereferences **nothing**: `_spec_addr` is
  a local, and `specasync_spec_width`, `specasync_spec_width_shift` and
  `g_specasync_last_region` are globals.
- `val` in the setter: non-NULL, as established above.

**Placement:**
- The **only** addition inside the fault-servicing bottom half is the
  region-ID comparison: a shift, a compare, a `READ_ONCE`/`WRITE_ONCE` on a
  specasync global, and an `atomic_inc`. It touches no UVM state.
- All other new logic is in the worker (`specasync_width_region`, the
  region/mask selection, the liveness re-check) and in module-parameter and
  debugfs plumbing.

## 4. E1b bears on this design (flag for the reviewer)

E1b (`E1B_HANDOFF_COST.md`) measured the enqueue handoff (`kzalloc` …
`queue_work`) at only **12.7%** (Stencil, prefetch off), **31.0%** (prefetch
on) and **9.8%** (GraphBFS) of speculation's cost on the servicing thread.
The remainder is prediction-side work that runs once per coalesced fault,
including `specasync_ft_predict`'s bsearch and global irqsave spinlock.

**This design's same-region skip happens *after* `specasync_ft_predict`.**
It can therefore remove at most the enqueue share. The per-fault prediction
cost is untouched, because every coalesced fault still calls
`specasync_predict_next`. The width half of the design (moving W pages per
worker call) is motivated independently, by E0.9b's throughput limit.

If amortizing the servicing-thread cost is the goal, a follow-up design
would have to avoid the per-fault `specasync_ft_predict` call itself. That
is **not implemented here**, because it was not asked for.

## 5. Risk assessment

| # | what could fail | where | consequence for the machine | mitigation in the code / plan |
|---|---|---|---|---|
| 1 | Region bounds wrong → `bitmap_set` past the 512-bit mask | worker (kworker stack) | **stack corruption in a kworker → oops or panic → machine needs a reboot** | explicit bounds in `specasync_width_region` (`outer ≤ npages ≤ 512`); `static_assert`s that 512 ≤ and divides `PAGES_PER_UVM_VA_BLOCK`. Test step 1 reads `spec_region_invalid` (expected 0) |
| 2 | `make_resident` on an HMM or dead block | worker | UVM state corruption, or a NULL dereference inside UVM → oops | refused at W > 1 unless managed, non-HMM, and not dead under the block lock |
| 3 | Multi-page `make_resident` needs GPU memory the 1-page path rarely needed → allocation failure or eviction | worker, inside `block_populate_pages` | allocation failure returns `NV_ERR_NO_MEMORY` or retry → counted THROTTLED; **no crash expected**. The eviction path under the worker's trylocked block lock is **not exercised by any test so far**, and a lock-ordering problem there would hang the fault path | test only non-oversubscribed configurations first: Stencil-24K ≈ 4.6 GB and GraphBFS on a 16 GB GPU. Oversubscription is out of scope until a separate review |
| 4 | Worker holds the block lock longer (up to 512 pages copied) → demand path waits on that block's lock | worker vs. fault-servicing thread | slower demand servicing (performance). A worker stuck inside `make_resident` would stall the GPU's faults → **benchmark hangs → timeout stop condition**, and the module could not be unloaded until reboot | the worker only `trylock`s and never waits. Test step 2 uses a timeout and watches dmesg |
| 5 | CPU mappings of up to W pages unmapped by the worker's migration | worker | the host takes CPU faults to get pages back (ping-pong): performance, not safety | same semantics as the stock prefetcher's region migration |
| 6 | Wasted migration of pages in the region the GPU never touches | worker | bandwidth and memory use, bounded by the 2 MB block | this is what the gate measures |
| 7 | Race on `g_specasync_last_region` between two fault-servicing threads (multi-GPU) | Gate 1 loop | a stale compare means one extra or one skipped enqueue. **No memory-safety consequence** (aligned u64 accesses; value only compared) | single-GPU platform; documented |
| 8 | Prediction-side regions are VA-aligned, worker regions are block-index-aligned. They coincide only when `va_block->start` is W-page aligned (true for 2 MB-aligned blocks) | both | efficiency only: a skipped prediction may fall in a region the worker aligned differently. Never out of bounds, because the worker computes its region inside the block | documented; test step 2 compares `ft_same_region` with `spec_pages_requested` |
| 9 | `insmod` with an invalid W | param setter | `insmod` fails cleanly; the module is not loaded | test step 0 |
| 10 | W = 1 regression | all | would silently invalidate comparability with verified results | §2 argument; test step 1 compares counters with the verified module |

## 6. Planned test sequence for the next session (attended, not unattended)

**0. Parameter rejection (no GPU work).**
- `insmod` with W ∈ {0, 3, 1024, abc} must fail with the `pr_err`
  message, and the module must not load.
- Reload the verified module afterwards.

**1. `group_probe` at W = 1 (regression) and W = 16.**
- Run the same `group_probe` configuration used in E0.5, back to back:
  - verified module (`5997D238…`);
  - new module at W = 1;
  - new module at W = 16.
- W = 1 must match the verified module on `enqueued`, `drops`,
  `spec_migrations`, `processed` and `demand_faults`, within the run-to-run
  noise already recorded for the probe. It must also show
  `ft_same_region == 0`, `spec_region_invalid == 0`, and
  `spec_pages_requested == spec_migrations + (make_resident calls that
  failed)`.
- W = 16: dmesg clean, `spec_region_invalid == 0`,
  `spec_pages_requested ≈ 16 × make_resident calls`, minus clipping at
  block ends.

**2. Stencil-24K at W = 16**, in the C6 configuration (policy 6, depth 1,
prefetch off, L = 4096) and then the C7 configuration (prefetch on).
- One run each, full E0.9b per-run procedure and stop conditions.
- Check: dmesg clean, `spec_region_invalid == 0`, `ft_same_region > 0`,
  `ft_predictions = enqueued + drops + ft_same_region` (the new identity),
  MemAvailable stable.

**3. Only then, a pre-registered sweep** over W, and possibly L. It follows
the E0.9b/E1 protocol, with the E1b batch-ring measurement included so the
servicing-thread cost is tracked per W.

## 7. Full diff (`driver/patches/e3a_spec_width.patch`)

```diff
diff -u driver/src/specasync_debugfs.c driver/src-e3a/specasync_debugfs.c
--- driver/src/specasync_debugfs.c	2026-09-25 12:34:51.018232483 +0300
+++ driver/src-e3a/specasync_debugfs.c	2026-09-25 22:45:27.219440107 +0300
@@ -116,6 +116,56 @@
 MODULE_PARM_DESC(specasync_ft_log_ring_slots,
 	"Gate E0.9 diagnostic ft-log ring capacity, rounded up to a power of two (default 1048576)");
 
+/*
+ * Gate E3a: speculative width W (see specasync_internal.h). Validated in the
+ * setter, which the kernel calls while parsing insmod arguments: returning
+ * -EINVAL there makes insmod itself fail ("Invalid parameters"), which is the
+ * only reliable way to reject a value -- specasync_debugfs_init() failures
+ * are non-fatal to module load (uvm.c). 0444: fixed for the module's life,
+ * so the worker and the fault path never see it change mid-run.
+ */
+int specasync_spec_width       = 1;
+int specasync_spec_width_shift = 0;
+
+static int specasync_spec_width_set(const char *val, const struct kernel_param *kp)
+{
+	int w;
+	int ret = kstrtoint(val, 0, &w);
+
+	if (ret) {
+		pr_err("specasync: specasync_spec_width='%s' rejected: not an integer\n", val);
+		return -EINVAL;
+	}
+	if (w < 1 || w > SPECASYNC_SPEC_WIDTH_MAX || !is_power_of_2(w)) {
+		pr_err("specasync: specasync_spec_width=%d rejected: must be a power of two in [1, %d]\n",
+		       w, SPECASYNC_SPEC_WIDTH_MAX);
+		return -EINVAL;
+	}
+	specasync_spec_width       = w;
+	specasync_spec_width_shift = ilog2(w);
+	return 0;
+}
+
+static const struct kernel_param_ops specasync_spec_width_ops = {
+	.set = specasync_spec_width_set,
+	.get = param_get_int,
+};
+module_param_cb(specasync_spec_width, &specasync_spec_width_ops, &specasync_spec_width, 0444);
+MODULE_PARM_DESC(specasync_spec_width,
+	"Gate E3a: speculative width in pages, power of two in [1, 512] (default 1 = pre-E3a behaviour)");
+
+u64        g_specasync_last_region          = SPECASYNC_NO_REGION;
+atomic_t   g_specasync_ft_same_region       = ATOMIC_INIT(0);
+atomic_t   g_specasync_spec_region_invalid  = ATOMIC_INIT(0);
+atomic64_t g_specasync_spec_pages_requested = ATOMIC64_INIT(0);
+
+static int spec_pages_requested_get(void *data, u64 *val)
+{
+	*val = (u64)atomic64_read(&g_specasync_spec_pages_requested);
+	return 0;
+}
+DEFINE_DEBUGFS_ATTRIBUTE(spec_pages_requested_fops, spec_pages_requested_get, NULL, "%llu\n");
+
 /* ── Gate E0.5 counters (defined here, declared extern in specasync_telemetry.h / specasync_internal.h) ── */
 atomic_t g_specasync_trace_pushes           = ATOMIC_INIT(0);
 atomic_t g_specasync_trace_overwrites       = ATOMIC_INIT(0);
@@ -400,6 +450,11 @@
 	atomic_set(&g_specasync_ft_unknown_page, 0);
 	atomic_set(&g_specasync_ft_exhausted, 0);
 	atomic_set(&g_specasync_fault_already_resident, 0);
+	/* Gate E3a: per-run-clean totals, and no carried-over "last region". */
+	atomic_set(&g_specasync_ft_same_region, 0);
+	atomic_set(&g_specasync_spec_region_invalid, 0);
+	atomic64_set(&g_specasync_spec_pages_requested, 0);
+	WRITE_ONCE(g_specasync_last_region, SPECASYNC_NO_REGION);
 	{
 		unsigned long _flags;
 		spin_lock_irqsave(&g_ft_cursor_lock, _flags);
@@ -1183,14 +1238,22 @@
 	debugfs_create_atomic_t("specasync_fault_already_resident", 0444, specasync_dir,
 				&g_specasync_fault_already_resident);
 
+	/* Gate E3a: speculative-width counters (see specasync_internal.h). */
+	debugfs_create_atomic_t("specasync_ft_same_region", 0444, specasync_dir,
+				&g_specasync_ft_same_region);
+	debugfs_create_atomic_t("specasync_spec_region_invalid", 0444, specasync_dir,
+				&g_specasync_spec_region_invalid);
+	debugfs_create_file_unsafe("specasync_spec_pages_requested", 0444, specasync_dir,
+				   NULL, &spec_pages_requested_fops);
+
 	if (specasync_policy == 4)
 		specasync_load_oracle_trace();
 	if (specasync_policy == SPECASYNC_POLICY_FIRST_TOUCH)
 		specasync_load_ft_table();
 
-	pr_info("specasync: init OK  log_enabled=%d policy=%d offload_depth=%d decomp=%d\n",
+	pr_info("specasync: init OK  log_enabled=%d policy=%d offload_depth=%d decomp=%d spec_width=%d\n",
 		specasync_log_enabled, specasync_policy, specasync_offload_depth,
-		SPECASYNC_DECOMP);
+		SPECASYNC_DECOMP, specasync_spec_width);
 	return 0;
 
 err_files:
Only in driver/src: specasync_faults_instrumentation.c
diff -u driver/src/specasync_internal.h driver/src-e3a/specasync_internal.h
--- driver/src/specasync_internal.h	2026-09-25 12:34:10.966964869 +0300
+++ driver/src-e3a/specasync_internal.h	2026-09-25 22:45:07.175838240 +0300
@@ -133,4 +133,35 @@
 u64  specasync_ft_predict(u64 fault_addr);
 extern int specasync_ft_lookahead;
 
+/*
+ * Gate E3a: speculative width W (pages). One speculative worker call makes
+ * the W-aligned region containing the predicted page resident, and policy 6
+ * does not enqueue a prediction whose region equals the last ENQUEUED
+ * prediction's region. W is validated at insmod (power of two in
+ * [1, SPECASYNC_SPEC_WIDTH_MAX]); invalid values make insmod fail. W = 1
+ * (default) takes exactly the pre-E3a code paths -- every new branch is
+ * guarded by specasync_spec_width > 1.
+ *
+ * specasync_spec_width_shift            log2(W), set by the same param setter
+ * g_specasync_last_region               region ID (va >> (PAGE_SHIFT + shift))
+ *                                       of the last enqueued policy-6
+ *                                       prediction; SPECASYNC_NO_REGION = none.
+ *                                       Written/read only by the fault-servicing
+ *                                       thread (READ_ONCE/WRITE_ONCE) and reset
+ *                                       by specasync_clear.
+ * g_specasync_ft_same_region            predictions not enqueued: same region
+ * g_specasync_spec_region_invalid       worker items skipped because the region
+ *                                       failed an explicit bounds/block check
+ * g_specasync_spec_pages_requested      sum of region sizes (pages) passed to
+ *                                       uvm_va_block_make_resident by the worker
+ */
+#define SPECASYNC_SPEC_WIDTH_MAX 512
+#define SPECASYNC_NO_REGION      (~0ULL)
+extern int        specasync_spec_width;
+extern int        specasync_spec_width_shift;
+extern u64        g_specasync_last_region;
+extern atomic_t   g_specasync_ft_same_region;
+extern atomic_t   g_specasync_spec_region_invalid;
+extern atomic64_t g_specasync_spec_pages_requested;
+
 #endif /* SPECASYNC_INTERNAL_H */
diff -u driver/src/uvm_gpu_replayable_faults.c driver/src-e3a/uvm_gpu_replayable_faults.c
--- driver/src/uvm_gpu_replayable_faults.c	2026-09-25 12:41:43.763793118 +0300
+++ driver/src-e3a/uvm_gpu_replayable_faults.c	2026-09-25 22:48:28.588009803 +0300
@@ -22,6 +22,7 @@
 *******************************************************************************/
 
 #include "linux/sort.h"
+#include <linux/log2.h>   /* Gate E3a: is_power_of_2() */
 #include "nv_uvm_interface.h"
 #include "uvm_common.h"
 #include "uvm_linux.h"
@@ -276,6 +277,50 @@
 	uvm_gpu_t                  *gpu;  /* retained; NULL at depth=0, set at depth>=1 */
 };
 
+/*
+ * Gate E3a: the W-aligned region of va_block that contains pidx, for W =
+ * specasync_spec_width > 1. Every bound that the UVM helpers only
+ * UVM_ASSERT (non-fatal in release builds) -- uvm_va_block_region() checks
+ * first <= outer; uvm_va_block_num_cpu_pages() checks the block size;
+ * uvm_page_mask_region_fill() checks nothing at all (raw bitmap_set on the
+ * caller's 512-bit mask) -- is checked here explicitly. Also refuses any
+ * block that is not a managed, non-HMM block: the only kind this worker has
+ * been run on, and the only kind for which make_resident with ctx->mm == NULL
+ * is the verified W = 1 configuration. Returns false on any violation; the
+ * caller then skips the item (no lock taken, no make_resident call) and
+ * counts it in g_specasync_spec_region_invalid.
+ */
+static bool specasync_width_region(uvm_va_block_t *va_block,
+				   uvm_page_index_t pidx,
+				   uvm_va_block_region_t *out)
+{
+	size_t w, npages, first, outer;
+
+	if (!va_block || !out)
+		return false;
+	if (uvm_va_block_is_hmm(va_block) || !va_block->managed_range)
+		return false;
+	if (va_block->end < va_block->start)
+		return false;
+
+	w = (size_t)specasync_spec_width;
+	if (w < 2 || w > SPECASYNC_SPEC_WIDTH_MAX || !is_power_of_2(w))
+		return false;
+
+	npages = (size_t)((va_block->end - va_block->start + 1) >> PAGE_SHIFT);
+	if (npages == 0 || npages > PAGES_PER_UVM_VA_BLOCK || (size_t)pidx >= npages)
+		return false;
+
+	first = (size_t)pidx & ~(w - 1);
+	outer = min(first + w, npages);
+	if (first > (size_t)pidx || outer <= (size_t)pidx ||
+	    outer > npages || outer > PAGES_PER_UVM_VA_BLOCK)
+		return false;
+
+	*out = uvm_va_block_region((uvm_page_index_t)first, (uvm_page_index_t)outer);
+	return true;
+}
+
 static void specasync_worker_fn(struct work_struct *work)
 {
 	struct spec_work_item  *item = container_of(work, struct spec_work_item, work);
@@ -313,20 +358,48 @@
 			uvm_page_mask_t      pmask;
 			uvm_page_index_t     pidx;
 			NV_STATUS            mstatus = NV_ERR_BUSY_RETRY;
+			/*
+			 * Gate E3a: sregion is exactly the pre-E3a region
+			 * (region_for_page(pidx)) and pmask exactly the pre-E3a
+			 * one-bit mask unless W > 1.
+			 */
+			uvm_va_block_region_t sregion;
+			bool                 sregion_ok = true;
 
 			uvm_va_block_context_init(ctx, NULL);
 			pidx = uvm_va_block_cpu_page_index(va_block, item->speculative_addr);
+			sregion = uvm_va_block_region_for_page(pidx);
 			uvm_page_mask_zero(&pmask);
-			uvm_page_mask_set(&pmask, pidx);
+			if (specasync_spec_width > 1) {
+				sregion_ok = specasync_width_region(va_block, pidx, &sregion);
+				if (sregion_ok)
+					uvm_page_mask_region_fill(&pmask, sregion);
+				else
+					atomic_inc(&g_specasync_spec_region_invalid);
+			} else {
+				uvm_page_mask_set(&pmask, pidx);
+			}
 			uvm_va_block_retry_init(&retry);
 
-			if (uvm_mutex_trylock(&va_block->lock)) {
-				mstatus = uvm_va_block_make_resident(
-					va_block, &retry, ctx,
-					item->gpu->id,
-					uvm_va_block_region_for_page(pidx),
-					&pmask, NULL,
-					UVM_MAKE_RESIDENT_CAUSE_PREFETCH);
+			if (sregion_ok && uvm_mutex_trylock(&va_block->lock)) {
+				/*
+				 * Gate E3a: at W > 1, re-check liveness under the
+				 * block lock (block kill clears managed_range) before
+				 * handing make_resident a multi-page region. W = 1
+				 * never takes this branch.
+				 */
+				if (specasync_spec_width > 1 && uvm_va_block_is_dead(va_block)) {
+					atomic_inc(&g_specasync_spec_region_invalid);
+				} else {
+					mstatus = uvm_va_block_make_resident(
+						va_block, &retry, ctx,
+						item->gpu->id,
+						sregion,
+						&pmask, NULL,
+						UVM_MAKE_RESIDENT_CAUSE_PREFETCH);
+					atomic64_add((s64)uvm_va_block_region_num_pages(sregion),
+						     &g_specasync_spec_pages_requested);
+				}
 				uvm_va_block_retry_deinit(&retry, va_block);
 				uvm_mutex_unlock(&va_block->lock);
 			} else {
@@ -379,7 +452,12 @@
 
 /* ---- Enqueue helper ----------------------------------------------- */
 
-static void specasync_enqueue(uvm_va_space_t *va_space, u64 spec_addr,
+/*
+ * Gate E3a: returns true iff a work item was queued. The return value is new;
+ * every side effect (counters, ring fields, allocation, queueing) is
+ * unchanged. Pre-E3a callers ignore it.
+ */
+static bool specasync_enqueue(uvm_va_space_t *va_space, u64 spec_addr,
 			      struct specasync_hit_table *hit_table,
 			      struct specasync_batch_record *sa_rec,
 			      uvm_gpu_t *gpu)
@@ -388,11 +466,11 @@
 	u64 t0;
 
 	if (!g_specasync_wq || specasync_policy == 0 || spec_addr == 0)
-		return;
+		return false;
 	if (atomic_read(&g_specasync_queue_depth) >= SPECASYNC_MAX_QUEUE_DEPTH) {
 		sa_rec->spec_drops++;
 		atomic_inc(&g_specasync_drops);
-		return;
+		return false;
 	}
 
 	t0   = ktime_get_ns();
@@ -400,7 +478,7 @@
 	if (!item) {
 		sa_rec->spec_drops++;
 		atomic_inc(&g_specasync_drops);
-		return;
+		return false;
 	}
 
 	INIT_WORK(&item->work, specasync_worker_fn);
@@ -418,8 +496,19 @@
 	sa_rec->spec_enqueues++;
 	atomic_inc(&g_specasync_enqueued);
 	sa_rec->enqueue_overhead_ns += (u32)(ktime_get_ns() - t0);
+	return true;
 }
 
+/*
+ * Gate E3a: W divides the VA-block page count, so a W-aligned region of a
+ * 2MB-aligned block never crosses the block. The worker still checks every
+ * region bound explicitly at runtime (see specasync_width_region()).
+ */
+static_assert(SPECASYNC_SPEC_WIDTH_MAX <= PAGES_PER_UVM_VA_BLOCK,
+	      "spec width must not exceed a VA block");
+static_assert(PAGES_PER_UVM_VA_BLOCK % SPECASYNC_SPEC_WIDTH_MAX == 0,
+	      "spec width max must divide the VA block page count");
+
 /* ---- Compile-time ABI sanity checks -------------------------------- */
 static_assert(sizeof(struct specasync_batch_record) == 72,
 	      "specasync_batch_record size mismatch — update Python BATCH_FMT");
@@ -2677,7 +2766,27 @@
                 struct specasync_hit_table *_ht =
                     (_fe->va_space->specasync_pred) ?
                     _fe->va_space->specasync_pred->hit_table : NULL;
-                specasync_enqueue(_fe->va_space, _spec_addr, _ht, &_sa_rec, _fe->gpu);
+                /*
+                 * Gate E3a: at W > 1, policy 6 does not enqueue a prediction
+                 * whose W-page region equals the last ENQUEUED prediction's.
+                 * Touches no UVM state: a local, two specasync globals, one
+                 * counter. At W = 1 this branch is never taken and the call
+                 * below is exactly the pre-E3a call.
+                 */
+                if (specasync_spec_width > 1 &&
+                    specasync_policy == SPECASYNC_POLICY_FIRST_TOUCH &&
+                    _spec_addr != 0) {
+                    u64 _rid = _spec_addr >> (PAGE_SHIFT + specasync_spec_width_shift);
+
+                    if (_rid == READ_ONCE(g_specasync_last_region)) {
+                        atomic_inc(&g_specasync_ft_same_region);
+                        continue;
+                    }
+                    if (specasync_enqueue(_fe->va_space, _spec_addr, _ht, &_sa_rec, _fe->gpu))
+                        WRITE_ONCE(g_specasync_last_region, _rid);
+                } else {
+                    specasync_enqueue(_fe->va_space, _spec_addr, _ht, &_sa_rec, _fe->gpu);
+                }
             }
         }
     }
```
