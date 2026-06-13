# Gate 3 — Policy Sweep Execution

**Date:** 2026-06-11 (started) · 2026-06-13 (completed)
**Status:** PASS — p0–p3 sweep complete (72 experiments: 6 benchmarks × 3 sizes × 4 policies × 20 runs)

## Sweep configuration

```
POLICY_LIST=(0 1 2 3)    # disabled, adjacent, stride, markov
DEPTH_LIST=(0)           # no residency offload (reduces sweep time)
NUM_STAT_RUNS=20         # per config×size (reduced from 50)
WARMUP_RUNS=1
```

## Sweep invocation

```bash
mkdir -p ~/SpecAsync-UVM/results/phaseB/logs
export SPECASYNC_SRCVERSION="251C8BBDE47D3B328768262"
cd ~/SpecAsync-UVM/benchmarks
sudo bash run_all_experiments.sh 2>&1 | tee results/phaseB/logs/sweep_run1.log &
```

## Results directory layout

```
results/
  p0_d0/   speculation disabled (baseline)
  p1_d0/   adjacent-page prediction
  p2_d0/   stride prediction
  p3_d0/   markov-chain prediction
  p4_d0/   oracle (upper bound) — collected separately after rebuild
```

## Per-experiment outputs

Each `results/p{N}_d0/{bench}/{size}/` contains:
- `timing_raw.csv`    — Run_ID, Time_ms, Bandwidth_GBs (20 rows)
- `batch_records.csv` — parsed batch telemetry (one row per fault batch)
- `work_records.csv`  — parsed work-item telemetry
- `raw_batch.bin`     — raw binary ring snapshot
- `raw_worker.bin`    — raw binary worker log snapshot

## Telemetry stale-record filtering

Due to a ring-buffer wrap-around issue (now fixed in the rebuilt module), the
raw `batch_records.csv` files from this sweep may contain stale records from
previous module sessions. These are filtered by `specasync_parse.py`:
- `t0_ns == 0` → zero-initialized ring slots (never written)
- `t4_ns < t0_ns` → timestamp ordering violation
- `t4_ns - t0_ns > 30e9` → cross-session record (>30s latency impossible)

The primary timing metric (`timing_raw.csv`) is NOT affected by this issue.

## Estimated sweep completion

| Phase | Estimated time |
|-------|---------------|
| p0_d0 | ~110 min |
| p1_d0 | ~110 min |
| p2_d0 | ~110 min |
| p3_d0 | ~110 min |
| **Total** | **~7.3 hours** |

Most time is in Stencil_OvSub (~38.7s/run × 21 × 3 sizes = 41 min per policy)
and GraphBFS (~2 min/run × 21 × 3 sizes = 126 min per policy).

## Progress — COMPLETE

- [x] p0_d0 — all 6 benchmarks × 3 sizes
- [x] p1_d0 — all 6 benchmarks × 3 sizes
- [x] p2_d0 — all 6 benchmarks × 3 sizes
- [x] p3_d0 — all 6 benchmarks × 3 sizes

All configs have `timing_raw.csv` (20 rows) plus parsed `batch_records.csv` /
`work_records.csv`. Aggregated into `results/phaseB/phaseB_timing.csv` and
`phaseB_telemetry.csv` (78 timing + 78 telemetry configs incl. p4).
