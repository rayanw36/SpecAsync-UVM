# Gate 0 — Environment Verification

**Date:** 2026-06-11
**Instance:** AWS g4dn.xlarge
**Status:** PASS

## Platform

| Component | Value |
|-----------|-------|
| Instance type | g4dn.xlarge |
| GPU | Tesla T4 (NVIDIA, sm_75) |
| VRAM | 16 GiB GDDR6 |
| Kernel | 6.17.0-1017-aws |
| Driver | NVIDIA 595.71.05 |
| CUDA | 12.0 (`/usr/bin/nvcc`) |
| OS | Ubuntu (DLAMI) |
| EBS mount | `/home/ubuntu/` |
| NVMe mount | `/opt/dlami/nvme/` |

## Module state

- Stock `nvidia-uvm.ko` backed up to `driver/stock_backup/nvidia-uvm.ko.stock`
- Stock srcversion: `85A79790636BBD99BA3E43B`
- Stock path: `/lib/modules/6.17.0-1017-aws/updates/dkms/nvidia-uvm.ko`

## Patch application

```
Source tree: /opt/dlami/nvme/work/nvidia-595.71.05-specasync/
Patch:       driver/patches/specasync_uvm_v595.71.05.patch (1112 lines)
Method:      patch -p4 (absolute-path diff, strip 4 components)
Result:      All hunks applied cleanly
Files patched: nvidia-uvm-sources.Kbuild, specasync_debugfs.c (new),
               specasync_internal.h (new), specasync_telemetry.h (new),
               uvm.c, uvm_gpu_replayable_faults.c,
               uvm_va_space.c, uvm_va_space.h
```

## Module loaded

```
srcversion: 251C8BBDE47D3B328768262  (SpecAsync-UVM v595 build)
debugfs:    /sys/kernel/debug/specasync_{log,worker_log,clear,fault_trace}
dmesg:      specasync: init OK  log_enabled=1 policy=1 offload_depth=0
```

## Benchmark build

All benchmarks compiled with `-arch=sm_75`:
- `bench_sgemm`, `bench_stencil`, `bench_stream`, `bench_cufft`
- `graph_bfs/bench_graph_bfs`
- `stencil_oversub/bench_stencil_oversub` (with balloon_mib support)
