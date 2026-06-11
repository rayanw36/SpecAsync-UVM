# SpecAsync-UVM — Porting Notes: v580.95.05 → v595.71.05

## Summary

All SpecAsync logic was implemented fresh in the v595.71.05 driver tree.
The v580 "patch" stored in LFS is the entire unmodified 580 source tree committed as an
initial git blob; it contains no SpecAsync changes. The reference implementation for
porting is in `driver/src/` (Phase A).

## Source Tree Layout Change

| v580 path (PHASE_B_INTEGRATION.md) | v595 path (actual) |
|-----------------------------------|--------------------|
| `kernel-open/nvidia-uvm/*.c`      | `nvidia-uvm/*.c`   |
| `kernel-open/nvidia-uvm/Kbuild`   | `nvidia-uvm/nvidia-uvm.Kbuild` |

The v595 dkms package ships the pre-extracted kernel-open source without the outer
`kernel-open/` wrapper. All grep and integration commands must target `nvidia-uvm/` directly.

## API Verification (595 vs 580 references in PHASE_B_INTEGRATION.md)

### `uvm_va_space_down_read` / `uvm_va_space_up_read`
- **Status**: Present and unchanged in 595.
- **Location**: `uvm_va_space.h` (macro wrappers).

### `uvm_va_block_find(va_space, addr, &va_block)`
- **Status**: Present and unchanged in 595.
- **Location**: `uvm_va_block.c:12515`, declared in `uvm_va_block.h:1461`.
- Used in worker for metadata-only pre-locate (no-create, read-side safe).

### `service_fault_batch` signature (595)
```c
static NV_STATUS service_fault_batch(uvm_parent_gpu_t *parent_gpu,
                                     fault_service_mode_t service_mode,
                                     uvm_fault_service_batch_context_t *batch_context)
```
- **Batch loop**: `for (i = 0; i < batch_context->num_coalesced_faults;)` (line ~2479 in stock 595)
- **Fault cache fields**:
  - `batch_context->ordered_fault_cache[i]` → `uvm_fault_buffer_entry_t *`
  - `->fault_address` → virtual address of the fault
  - `batch_context->num_coalesced_faults` → count of unique faults after coalescing
- **VA space lock**: `uvm_va_space_down_read(va_space)` called inside the loop when va_space changes.

### `struct uvm_va_space_struct`
- **Status**: Found at `uvm_va_space.h:186`. No typedef alias (declared as `struct uvm_va_space_struct`).
- **Field added**: `struct specasync_predict_state *specasync_pred;` at end of struct (before `};`).
- **Forward declaration required** in `uvm_va_space.h` because the struct is defined in `uvm_gpu_replayable_faults.c`.

### `uvm_va_space_create` / `uvm_va_space_destroy`
- **Status**: Present at `uvm_va_space.c:181` and `uvm_va_space.c:456`.
- **Alloc hook**: After `init_tools_data(va_space)` in create.
- **Free hook**: After `uvm_tools_flush_events()` in destroy, before `uvm_deferred_free_object_list()`.

### Module init/exit (`uvm.c`)
- **`uvm_init()`**: line 1163 in stock 595; workqueue + debugfs init added after `uvm_tools_init()`.
- **`uvm_exit()`**: line 1213 in stock 595; debugfs exit + workqueue destroy added before `uvm_tools_exit()`.

### debugfs parent
- `uvm_init()` / `uvm_tools_init()` do NOT create a debugfs root directory for nvidia_uvm.
- **Decision**: pass `NULL` to `specasync_debugfs_init()` → files created at `/sys/kernel/debug/specasync_log` etc. (debugfs root).
- A dedicated `specasync_dir` is created at `/sys/kernel/debug/specasync/` for grouping.

### `copy_raw_buf_to_user` (specasync_debugfs.c)
- **Does not exist** in the Linux kernel API.
- **Fixed**: replaced with `copy_to_user()` in the 595 port.

## New Files Added

| File | Purpose |
|------|---------|
| `nvidia-uvm/specasync_telemetry.h` | Ring buffer structs, hit table, push API |
| `nvidia-uvm/specasync_debugfs.c` | debugfs interface, module params, oracle trace load |
| `nvidia-uvm/specasync_internal.h` | Cross-file extern declarations |

## Modified Files

| File | What Changed |
|------|-------------|
| `nvidia-uvm/uvm_gpu_replayable_faults.c` | SpecAsync globals, worker, enqueue, prediction policies, T0–T4 instrumentation |
| `nvidia-uvm/uvm_va_space.h` | `specasync_pred` field + forward declaration |
| `nvidia-uvm/uvm_va_space.c` | `specasync_predict_state_alloc/free` lifecycle hooks |
| `nvidia-uvm/uvm.c` | Workqueue + debugfs init/exit, SpecAsync banner |
| `nvidia-uvm/nvidia-uvm-sources.Kbuild` | `specasync_debugfs.c` added to sources list |

## Verified Module Load

- **SpecAsync srcversion**: `EF55E64556352EDABEBE583` (differs from stock `85A79790636BBD99BA3E43B`)
- **dmesg banner**: `specasync: init OK  log_enabled=1 policy=1 offload_depth=0`
- **debugfs files**: `/sys/kernel/debug/specasync_log`, `specasync_worker_log`, `specasync_clear`
- **UVM smoke test**: `cudaMallocManaged` + GPU kernel passes with SpecAsync module

## Platform Notes (T4 vs RTX 5070 Ti)

| Property | Tesla T4 (this machine) | RTX 5070 Ti (Phase A) |
|----------|------------------------|----------------------|
| Compute capability | sm_75 (Turing) | sm_120 (Blackwell) |
| VRAM | 15,360 MiB | ~16,384 MiB |
| Fault batch replay policy | `BLOCK` (per-VA-block replay) | unknown |
| PCIe | Gen3 ×16 | Gen5 ×16 |
| `uvm_va_block_find` locking | Read-side safe (no write lock needed) | same |

All benchmarks compiled with `-arch=sm_75`.
Fault batch behavior on Turing: replay policy is `BLOCK` — `push_replay_on_gpu` is called
after each VA block dispatch, so T2/T3 instrumentation measures per-block granularity.
