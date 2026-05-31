# Phase B Integration Checklist

This file is the checklist you work through on the GPU box after `git lfs pull`
and applying the patch. Each `TODO[phase-b]` in the driver source code maps to
an entry here.

**Prerequisites:**
```bash
git lfs pull                        # retrieve the 190 MB patch
cd ~/nvidia-open-580.95.05
patch -p1 < ~/SpecAsync-UVM/driver/patches/specasync_uvm_v580.95.05.patch
make modules -j$(nproc)             # verify patch applies cleanly
```

---

## §1 — debugfs init/exit wiring

**File:** `specasync_debugfs.c` (new file, added in Phase 2)
**What to verify:** Find the nvidia_uvm debugfs init/exit entry points.

**Assumed symbols:**
- `uvm_debug_init()` or similar in `kernel-open/nvidia-uvm/uvm_debug.c`
- Parent dentry: typically `uvm_debugfs_dir` (a `struct dentry *` global or
  returned from `debugfs_create_dir("nvidia_uvm", NULL)`)

**Action:**
```bash
grep -rn "debugfs_create_dir" kernel-open/nvidia-uvm/ | grep -v ".o:"
```
Find where `/sys/kernel/debug/nvidia_uvm` is created. Pass that dentry to
`specasync_debugfs_init()`. Add to the init function:
```c
ret = specasync_debugfs_init(uvm_debugfs_dir);
if (ret) {
    NV_ERROR(gpu, "specasync_debugfs_init failed: %d\n", ret);
    /* non-fatal — driver still works, just without telemetry */
}
```
And to the exit:
```c
specasync_debugfs_exit();
```

**Fallback:** If no debugfs parent exists yet, call
`debugfs_create_dir("nvidia_uvm", NULL)` first and store the result.

---

## §2 — service_fault_batch() T0–T4 instrumentation

**File:** `kernel-open/nvidia-uvm/uvm_gpu_replayable_faults.c`
**What to verify:** Exact function signature and fault-batch loop structure.

**Action:**
```bash
grep -n "service_fault_batch\|uvm_va_space_down_read\|uvm_va_block_find\
\|uvm_va_block_service\|uvm_va_block_make_resident" \
  kernel-open/nvidia-uvm/uvm_gpu_replayable_faults.c | head -50
```

| Marker | Find | Place after |
|--------|------|-------------|
| T0     | entry of `service_fault_batch` | first line after local vars |
| T1     | `uvm_va_space_down_read*` call | the lock call itself |
| T2     | last `uvm_va_block_find*` in batch loop | end of metadata discovery |
| T3     | last residency/migration call | end of batch residency loop |
| T4     | each `return` statement | add before every return |

**Assumed symbol:** `ktime_get_ns()` is available on Linux 6.14 (confirmed).

**Fallback:** If T1 lock call is per-fault (inside the loop), place T1 after
the first iteration's lock rather than all iterations to avoid double-counting.

---

## §3 — spec_hits / hit-table integration

**File:** `uvm_gpu_replayable_faults.c` + `uvm_va_space.h`

**What to add to uvm_va_space_t:**
```c
struct specasync_predict_state *specasync_pred;  /* NULL if allocation failed */
```

**Assumed symbol:** `uvm_va_space_t` is `typedef struct uvm_va_space uvm_va_space_t`
in `uvm_va_space.h`. Find with:
```bash
grep -n "typedef struct uvm_va_space\|struct uvm_va_space {" \
  kernel-open/nvidia-uvm/uvm_va_space.h | head -5
```

**Wire-up locations:**
- `uvm_va_space_create()` → add `va_space->specasync_pred = specasync_predict_state_alloc();`
- `uvm_va_space_destroy()` → add `specasync_predict_state_free(va_space->specasync_pred);`

**Hit-table consume call** (in service_fault_batch, at T2):
```c
if (va_space->specasync_pred && va_space->specasync_pred->hit_table) {
    u64 _now = ktime_get_ns();
    for (i = 0; i < batch_context->num_coalesced_faults; i++) {
        u64 va = batch_context->fault_cache[i].fault_address;
        _sa_rec.spec_hits += specasync_hit_table_consume(
            va_space->specasync_pred->hit_table, va, _now);
    }
}
```

**Assumed fields:**
- `batch_context->num_coalesced_faults`: count of distinct faults in batch
  TODO: verify field name; may be `num_faults` or `num_coalesced_entries`
- `batch_context->fault_cache[i].fault_address`: VA of each fault
  TODO: verify field path; may be nested differently in v580.95.05

```bash
grep -n "fault_cache\|fault_address\|num_coalesced\|num_faults" \
  kernel-open/nvidia-uvm/uvm_gpu_replayable_faults.c | head -30
```

---

## §4 — Residency offload (depth=1) API symbol

**File:** `specasync_faults_instrumentation.c` §4

**What to verify:** The correct v580.95.05 API for speculative residency prep.

**Candidates to check:**
```bash
grep -rn "uvm_va_block_make_resident\|uvm_va_block_migrate_locked\
\|uvm_migrate_ranges\|uvm_va_block_service_fault" \
  kernel-open/nvidia-uvm/ | grep "^[^:]*\.h:" | head -20
```

**Decision tree:**
1. If `uvm_va_block_make_resident()` exists with a signature taking a
   `uvm_processor_id_t` destination — use it. It is the right abstraction level.
2. If it requires the va_block write lock → gate depth=1 to only call it when
   the worker can safely acquire the lock (check locking annotations via sparse
   or lockdep).
3. If no suitable unlocked residency-prep exists → document and disable depth=1
   with `pr_warn_once("specasync: depth=1 requires write lock — disabled")`.

**VRAM utilization gating:**
```bash
grep -rn "vram_usage\|used_sys_heap\|allocated_size\|memory_stats" \
  kernel-open/nvidia-uvm/ | head -20
```
If a usable counter is found, gate: `if (used_vram * 10 < total_vram * 9)` (<90%).
If not found, add comment: `/* VRAM utilization gate: not available in v580.95.05, skipped */`.

---

## §5 — Per-VA-space prediction state

**File:** `uvm_va_space.h` (add field), `uvm_va_space.c` (wire alloc/free)

**Action:**
```bash
grep -n "uvm_va_space_create\|uvm_va_space_destroy\|struct uvm_va_space {" \
  kernel-open/nvidia-uvm/uvm_va_space.c kernel-open/nvidia-uvm/uvm_va_space.h
```

Add to `struct uvm_va_space` (near end of struct, before closing `}`):
```c
/* Phase 2 speculation state (NULL if alloc failed) */
struct specasync_predict_state *specasync_pred;
```

In `uvm_va_space_create()`:
```c
va_space->specasync_pred = specasync_predict_state_alloc();
/* NULL is safe — all callers check before using */
```

In `uvm_va_space_destroy()`:
```c
specasync_predict_state_free(va_space->specasync_pred);
va_space->specasync_pred = NULL;
```

**Fallback:** If `uvm_va_space_t` is opaque or the struct is generated/packed,
find an alternative attachment point (e.g., a per-process structure or a hash
table keyed on `va_space` pointer).

---

## §6 — Oracle trace load from module init

**File:** `specasync_debugfs.c`
**Function:** `specasync_load_oracle_trace()`

**What to verify:** `filp_open()` + `kernel_read()` work from module init
context on Linux 6.14.

```bash
# Check kernel_read() availability and signature
grep -rn "kernel_read\|vfs_read" include/linux/fs.h
```

Known signature (Linux 5.10+):
```c
ssize_t kernel_read(struct file *file, void *buf, size_t count, loff_t *pos);
```
This should be unchanged on 6.14. If it changed, check the fs.h header.

**Alternative if filp_open() is blocked from module init:**
Expose a sysfs write node that accepts a path at runtime:
```c
static ssize_t oracle_load_store(struct kobject *kobj,
                                 struct kobj_attribute *attr,
                                 const char *buf, size_t count);
```
Then load the trace lazily on first `specasync_predict_next()` call with policy=4.

---

## §7 — Existing Phase 1 specasync_worker integration

**What to find:** The Phase 1 patch added `specasync_worker`, `spec_work_item`,
and the workqueue. These are referenced throughout Section 2 of
`specasync_faults_instrumentation.c`.

```bash
grep -n "specasync_worker\|spec_work_item\|specasync_wq\|specasync_enqueue" \
  kernel-open/nvidia-uvm/uvm_gpu_replayable_faults.c
```

Map each Phase 2 addition (work-record telemetry, hit-table insert, residency
call) to the exact lines in the Phase 1 code before editing.

---

## §8 — BUILD_BUG_ON size assertions

Add the following to the compilation unit (e.g., at the top of
`specasync_debugfs.c`, after the struct headers are included) to catch any
ABI drift between kernel and Python parser:

```c
static_assert(sizeof(struct specasync_batch_record) == 72,
              "specasync_batch_record size mismatch — update Python BATCH_FMT");
static_assert(sizeof(struct specasync_work_record) == 48,
              "specasync_work_record size mismatch — update Python WORK_FMT");
static_assert(offsetof(struct specasync_batch_record, t0_ns) == 8,  "t0 offset");
static_assert(offsetof(struct specasync_batch_record, num_faults) == 48, "u32 start");
static_assert(offsetof(struct specasync_work_record, result) == 32,  "result offset");
```

If any assertion fails after integration, update BOTH the kernel struct AND
the Python format string in `benchmarks/tools/specasync_parse.py`.

---

## §9 — Kbuild integration

Add to the nvidia-uvm `Kbuild` or `Makefile`:
```
nvidia-uvm-objs += specasync_debugfs.o
```

The `specasync_faults_instrumentation.c` file is not a separate compilation
unit — it is a reference implementation. Its code should be **inlined** into
`uvm_gpu_replayable_faults.c` at the correct call sites (as described in §2–§5
above).

`specasync_telemetry.h` is a pure header; no Kbuild changes needed for it.

```bash
grep -n "nvidia-uvm-objs\|uvm_gpu_replayable_faults" \
  kernel-open/nvidia-uvm/Makefile
```
