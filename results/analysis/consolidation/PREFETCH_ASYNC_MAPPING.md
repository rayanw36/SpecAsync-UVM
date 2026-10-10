# Does a prefetch to a GPU install mappings? (read-only; driver 595.91.07)

Source: `/usr/src/nvidia-595.91.07/nvidia-uvm/uvm_migrate.c` (the DKMS tree the stock module is built from). Nothing was run.

**Answer: yes, for managed memory. A migration whose destination is a GPU always adds the mappings; there is no flag that turns it off for a GPU destination.**

## Caveat on the premise

The driver sees `UVM_MIGRATE` (`uvm_api_migrate`, `uvm_migrate.c:868`). That `cudaMemPrefetchAsync` issues this call is the documented behaviour of the CUDA runtime, which is closed source: it is **not** verifiable from the driver tree and I did not verify it. Everything below is about what the driver does when that ioctl arrives.

## The path, with file:line

| step | where | what it does |
|---|---|---|
| 1 | `uvm_migrate.c:868` `uvm_api_migrate` | entry; for a managed range it calls `uvm_migrate(...)` at `:1022`, passing `params->flags` and `dest_id` (the GPU, or the CPU if `dest_gpu` is null, `:977`) |
| 2 | `uvm_migrate.c:616` `uvm_migrate` | decides whether to add mappings (next row) |
| 3 | **`uvm_migrate.c:680`**: `do_mappings = UVM_ID_IS_GPU(dest_id) \|\| !(migrate_flags & UVM_MIGRATE_FLAG_SKIP_CPU_MAP);` | **always true when the destination is a GPU.** The only flag that can clear it, `UVM_MIGRATE_FLAG_SKIP_CPU_MAP` (`uvm_ioctl.h:635`), is test-only (`UVM_MIGRATE_FLAGS_TEST_ALL`, `uvm_ioctl.h:647`; rejected unless builtin tests are enabled, `uvm_migrate.c:896`) and is evaluated only for a CPU destination |
| 4 | `uvm_migrate.c:698-699` | `mode = do_mappings ? UVM_MIGRATE_MODE_MAKE_RESIDENT_AND_MAP : UVM_MIGRATE_MODE_MAKE_RESIDENT`, so `MAKE_RESIDENT_AND_MAP` for a GPU. If the migration spans more than one VA block it runs two passes: first `MAKE_RESIDENT` only (`:692`), then, block by block, `MAKE_RESIDENT_AND_MAP` as the second pass (`:696-712`, rationale in the comment at `:659-678`); a single-block migration does it in one pass |
| 5 | `uvm_migrate.c:265-268` (in the per-block routine) | `if (status == NV_OK && mode == UVM_MIGRATE_MODE_MAKE_RESIDENT_AND_MAP) status = block_migrate_add_mappings(...)` after `uvm_va_block_make_resident` |
| 6 | `uvm_migrate.c:152` `block_migrate_add_mappings` | calls `block_migrate_map_unmapped_pages` (`:163`) and then `uvm_va_block_migrate_map_mapped_pages(..., dest_id, ...)` (`:188-193`) |
| 7 | `uvm_migrate.c:74` `block_migrate_map_unmapped_pages` | **`uvm_va_block_map(va_block, va_block_context, dest_id, region, ..., UVM_PROT_READ_WRITE_ATOMIC, UvmEventMapRemoteCauseInvalid, ...)` at `:94-101`**, which installs the destination GPU's page-table entries (`uvm_va_block_map`, `uvm_va_block.c:8368`) with read-write-atomic permission, for pages not already mapped elsewhere; the already-mapped pages are covered by step 6's second call |

## Why this matters here

This is the opposite of the SpecAsync worker: the worker calls `uvm_va_block_make_resident()` and **no** mapping step (CS2-N2), so a staged page still faults when the GPU first touches it. A `cudaMemPrefetchAsync` to the GPU
goes through `MAKE_RESIDENT_AND_MAP`, so the prefetched pages are resident **and** mapped and do not fault. (The non-managed system-memory path, `uvm_migrate_pageable` at `uvm_migrate.c:1018`, is a different mechanism and was not read.)
