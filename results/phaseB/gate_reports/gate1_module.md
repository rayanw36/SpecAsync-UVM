# Gate 1 — Module Build and Load Verification

**Date:** 2026-06-11
**Status:** PASS

## Build

```bash
cd /opt/dlami/nvme/work/nvidia-595.71.05-specasync/nvidia-uvm
make -C /lib/modules/6.17.0-1017-aws/build M=$(pwd) \
    -f $(pwd)/nvidia-uvm-sources.Kbuild modules
```

Build output (key lines):
```
CC [M]  nvidia-uvm/specasync_debugfs.o
LD [M]  nvidia-uvm/nvidia-uvm.ko
```

## Srcversion

```
Built module:   251C8BBDE47D3B328768262
Loaded module:  251C8BBDE47D3B328768262  ✓ match
Stock module:   85A79790636BBD99BA3E43B  (backed up, NOT loaded)
```

## Module parameters (runtime-tunable)

```
/sys/module/nvidia_uvm/parameters/specasync_log_enabled  = 1
/sys/module/nvidia_uvm/parameters/specasync_policy       = 1  (adjacent)
/sys/module/nvidia_uvm/parameters/specasync_offload_depth = 0
/sys/module/nvidia_uvm/parameters/specasync_trace_faults = 0
/sys/module/nvidia_uvm/parameters/specasync_oracle_trace_path = (null)
```

## Debugfs interface

```
/sys/kernel/debug/specasync_log          (batch telemetry, binary)
/sys/kernel/debug/specasync_worker_log   (per-work-item telemetry, binary)
/sys/kernel/debug/specasync_clear        (write-only, resets rings with memset)
/sys/kernel/debug/specasync_fault_trace  (demand-fault VA ring, binary u64)
```

## Telemetry record formats

**Batch record** (72 bytes, `struct.unpack('<6Q6I')`):
- `batch_id`, `t0_ns`, `t1_ns`, `t2_ns`, `t3_ns`, `t4_ns`
- `num_faults`, `spec_enqueues`, `spec_drops`, `spec_hits`
- `enqueue_overhead_ns`, `_pad`

**Work record** (48 bytes, `struct.unpack('<4Q4I')`):
- `enqueue_ts_ns`, `dequeue_ts_ns`, `completion_ts_ns`, `va_addr`
- `result` (0=null,1=miss,2=hit,3=migration_done,4=throttled)
- `policy_used`, `_pad[2]`

## Ring buffer sizes

- Batch ring: 131072 slots × 72 B = 9.4 MB
- Work ring: 131072 slots × 48 B = 6.3 MB
- Fault trace ring: 1M slots × 8 B = 8 MB
