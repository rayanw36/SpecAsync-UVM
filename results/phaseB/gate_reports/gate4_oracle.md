# Gate 4 — Oracle Trace Collection

**Date:** 2026-06-11
**Status:** PENDING (requires module rebuild after sweep)

## Overview

Oracle policy (p4) provides the theoretical upper bound on speculation benefit:
it uses a pre-recorded sequence of demand-fault addresses to predict exactly
which pages will be faulted next.

## Infrastructure

The oracle trace infrastructure was added to the module in Phase B:

1. **Kernel-side trace ring** (`specasync_telemetry.h`):
   - `struct specasync_trace_ring`: 1M slots × 8 B = 8 MB
   - `specasync_trace_push(va_addr)`: records each demand-fault VA in order
   - Enabled by `specasync_trace_faults=1` module parameter

2. **Fault trace debugfs** (`specasync_debugfs.c`):
   - `/sys/kernel/debug/specasync_fault_trace`: read-only, returns packed u64 array
   - `specasync_trace_push()` called per coalesced fault in service loop
     (`uvm_gpu_replayable_faults.c:2505`)

3. **Oracle trace reader** (`specasync_debugfs.c`):
   - Reads oracle binary at init when `specasync_policy=4`
   - Serves addresses round-robin to speculative workers

## Rebuild requirement

The oracle trace changes require a module rebuild:
```bash
sudo bash ~/SpecAsync-UVM/scripts/rebuild_and_reload.sh
```

## Collection procedure

```bash
# After rebuild and reload:
sudo bash ~/SpecAsync-UVM/scripts/collect_oracle_traces.sh
```

This runs each benchmark once with `specasync_trace_faults=1` and copies
`/sys/kernel/debug/specasync_fault_trace` to:
```
~/SpecAsync-UVM/oracles/{benchmark}/{size}/oracle_trace.bin
```

## Oracle sweep

```bash
sudo bash ~/SpecAsync-UVM/scripts/oracle_sweep.sh
```

Results to `results/p4_d0/`.

## Expected metrics

Oracle policy should show:
- `hit_rate ≈ 1.0` (perfect prediction)
- Minimum achievable fault-service overhead (no wasted speculation)
- This bounds the maximum possible speedup from speculative prefetching
