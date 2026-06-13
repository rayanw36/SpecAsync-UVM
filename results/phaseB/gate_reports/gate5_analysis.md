# Gate 5 — Cost-Benefit Analysis and Final Report

**Date:** 2026-06-11 (planned) · 2026-06-13 (completed)
**Status:** PASS — analysis run over p0–p4; all output files regenerated 2026-06-13

All output files below were produced by `analyze_phaseB.py` + `cost_benefit.py`
(78 timing + 78 telemetry configs loaded, incl. p4). SUMMARY.md, both aggregated
CSVs, 12 plots, cost_benefit.md, and phase_breakdown.pdf are present and current.

## Analysis commands

```bash
cd ~/SpecAsync-UVM

# Full aggregation, plots, SUMMARY.md:
python3 benchmarks/tools/analyze_phaseB.py

# Cost-benefit table and phase-breakdown chart:
python3 benchmarks/tools/cost_benefit.py
```

## Output files

| File | Description |
|------|-------------|
| `results/phaseB/SUMMARY.md` | Reviewer-comment-ordered findings |
| `results/phaseB/phaseB_timing.csv` | Aggregated timing (all policies × benchmarks × sizes) |
| `results/phaseB/phaseB_telemetry.csv` | Aggregated telemetry (hit rate, latency breakdown) |
| `results/phaseB/plots/timing_{bench}.png` | Bar charts: baseline vs each policy |
| `results/phaseB/plots/latency_cdf_{bench}.png` | Fault-service latency comparison |
| `results/phaseB/plots/policy_sweep_{bench}.png` | Hit rate + timing delta per policy |
| `results/summary/cost_benefit.md` | Markdown cost-benefit table for paper |
| `results/summary/phase_breakdown.pdf` | Stacked bar chart (T0→T1→T2→T3 phases) |

## Key metrics to report

Per reviewer comment:

**C4 (Expanded evaluation):**
- End-to-end speedup: p1/p2/p3 vs p0 for each benchmark×size
- Oracle bound: p4 vs p0 (maximum achievable speedup)
- Statistical: mean ± std, n=20

**C3 (Critical-path evidence):**
- Fault-service latency breakdown by phase (T0→T1 lock acq, T1→T2 metadata, T2→T3 residency)
- Speculation hit rate per policy
- Enqueue overhead vs service latency delta

**C1 (Platform notes):**
- T4 vs RTX 5070 Ti comparison
- PCIe bandwidth difference and its effect on oversubscription benefit

## Cost-benefit formula

```
hit_rate         = sum(spec_hits) / sum(spec_enqueues)
overhead         = mean(enqueue_overhead_ns per batch)
service_delta    = baseline_mean_latency_ns - config_mean_latency_ns
net_benefit      = (service_delta × hit_rate) - overhead
```

Positive `net_benefit` means speculation adds more value than it costs.

## Telemetry quality note

The p0–p3 sweep used the original `clear_write` (tail=head, no memset). Some
batch_records.csv files may contain stale records from previous sessions. These
are filtered by the analysis tools:
- t0_ns == 0 → uninitialized ring slots
- t4_ns - t0_ns > 30 s → cross-session timestamps

The oracle (p4) sweep uses the rebuilt module with memset-based clear, so all
p4 telemetry will be clean.

The timing data (timing_raw.csv) is independent of the ring buffer and is
always clean.
