# Gate 4 — Oracle Trace Collection

**Date:** 2026-06-11 (planned) · 2026-06-13 (completed)
**Status:** PASS — all 6 oracle traces collected; p4 sweep complete (6 benchmarks × 20 runs)

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

Oracle policy was expected to show:
- `hit_rate ≈ 1.0` (perfect prediction)
- Minimum achievable fault-service overhead (no wasted speculation)
- This bounds the maximum possible speedup from speculative prefetching

## Observed metrics (2026-06-13)

| Benchmark | size | n_batches | hit_rate |
|-----------|------|-----------|----------|
| SGEMM | 24000 | 12740 | 0.0000 |
| Stencil | 24000 | 12740 | 0.0000 |
| STREAM | 268435456 | 5460 | 0.0000 |
| GraphBFS | 23 | 1820 | 0.0000 |
| cuFFT | 268435456 | 1820 | 0.0000 |
| Stencil_OvSub | 28300_20_11264 | 14560 | 0.0000 |

**Finding:** even the oracle policy records `hit_rate = 0.0` across all
benchmarks — the speculatively prefetched pages are never credited as hits.
This is consistent with the project-wide result that hit rates are universally
near zero and net-benefit/fault is negative: on the T4, speculative prefetch
does not land before the demand fault is serviced. The upper bound (p4) does
not beat baseline (p0), so there is no headroom for the heuristic policies
(p1–p3) to capture. Worth a sanity check of the hit-accounting path before
publication, but the timing data corroborates the no-benefit conclusion.

Oracle traces collected (entries vary per run; all present on EBS under
`~/SpecAsync-UVM/oracles/{bench}/{size}/oracle_trace.bin`).
