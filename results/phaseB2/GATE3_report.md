# Gate 3 — Decisive Favorable Comparison (C0 / C1 / C2 / C3)

## Configuration definitions

| Config | Policy | Depth | Prefetch | Description |
|--------|--------|-------|----------|-------------|
| **C0** | 0 (null) | 0 | **ON** | Stock prefetcher on — real-world default |
| **C1** | 0 (null) | 0 | OFF | Prefetch off, no speculation — prefetch-off baseline |
| **C2** | 2 (stride) | 1 | OFF | Stride predict + depth=1 migration, prefetch off |
| **C3** | 4 (oracle) | 1 | OFF | Oracle-perfect predict + depth=1 migration, prefetch off |

**Decisive comparison: C3 vs C0.** C3 is the absolute upper bound of SpecAsync:
perfect prediction (fault replay trace) + actual speculative migration (depth=1).
C0 is the real-world default with the stock UVM prefetcher. If C3 ≤ C0, Path B is
closed under any realistic operating point.

**C1/C2 are interleaved** (runtime param switch per run, no reload) to control for
drift. C0 and C3 are separate reloads.

## Benchmark parameters

- **Stencil**: N=24000 (5-point 2D stencil, GPU-resident, ~576M points)
- **GraphBFS**: N=23 (BFS on a 23-level graph, ~8 M nodes)
- **Oracle traces**: stencil=277,239 entries, GraphBFS=207,609 entries
- **Runs per config per bench**: 15
- **`setarch -R`** on all timed runs (ASLR off)

## Results table (n=15)

| Config | Benchmark | n | Median (s) | 95% CI (s) | vs C0 | vs C1 |
|--------|-----------|---|----------:|----------:|-------|-------|
| C0 | Stencil-24K | 15 | **4.250** | ±0.013 | — | — |
| C0 | GraphBFS-23 | 15 | **55.480** | ±0.935 | — | — |
| C1 | Stencil-24K | 15 | 15.280 | ±0.075 | +259.5% | — |
| C1 | GraphBFS-23 | 15 | 58.580 | ±0.095 | +5.6% | — |
| C2 | Stencil-24K | 15 | 16.750 | ±0.232 | +294.1% | +9.6% |
| C2 | GraphBFS-23 | 15 | 58.430 | ±0.120 | +5.3% | −0.3% |
| **C3** | **Stencil-24K** | 15 | **15.680** | ±0.461 | **+268.9%** | +2.6% |
| **C3** | **GraphBFS-23** | 15 | **58.640** | ±0.165 | **+5.7%** | +0.1% |

## Final analysis

```
Config   Benchmark              n   median_s    vs C0    vs C1  CI95
------------------------------------------------------------------------
C0       Stencil-24K           15      4.250     +0.0%      ---  ±0.013s
C0       GraphBFS-23           15     55.480     +0.0%      ---  ±0.935s
C1       Stencil-24K           15     15.280   +259.5%      ---  ±0.075s
C1       GraphBFS-23           15     58.580     +5.6%      ---  ±0.095s
C2       Stencil-24K           15     16.750   +294.1%    +9.6%  ±0.232s
C2       GraphBFS-23           15     58.430     +5.3%    -0.3%  ±0.120s
C3       Stencil-24K           15     15.680   +268.9%    +2.6%  ±0.461s
C3       GraphBFS-23           15     58.640     +5.7%    +0.1%  ±0.165s

=== DECISIVE VERDICT: C3 vs C0 ===
  Stencil-24K: C3=15.680s  C0=4.250s  Δ=+268.9%  → LOSES to C0
  GraphBFS-23: C3=58.640s  C0=55.480s  Δ=+5.7%   → LOSES to C0

  C2 vs C1 (Stencil-24K): C2=16.750s C1=15.280s Δ=+9.6%
  C2 vs C1 (GraphBFS-23): C2=58.430s C1=58.580s Δ=-0.3%

  C3 vs C1 (Stencil-24K): C3=15.680s C1=15.280s Δ=+2.6%
  C3 vs C1 (GraphBFS-23): C3=58.640s C1=58.580s Δ=+0.1%
```

## Verdict

**C3 LOSES to C0 on both benchmarks. Path B is closed.**

### Stencil-24K

C0 = 4.250s (prefetch ON) vs C3 = 15.680s (oracle+depth=1, prefetch OFF): **+268.9%**.

C3 is statistically indistinguishable from C1 (+2.6%, within ±0.461s CI). Oracle-perfect
prediction with actual GPU-page migration provides no measurable advantage over doing
nothing (C1 = no speculation). The stock UVM prefetcher in C0 reduces stencil time from
15.3s to 4.25s (3.6× improvement); disabling it to test SpecAsync costs exactly that 3.6×
and is not recovered.

C2 (stride+depth=1) is **9.6% slower than C1** — stride speculation with depth=1 adds net
overhead even on a perfectly sequential workload.

### GraphBFS-23

C0 = 55.480s (prefetch ON) vs C3 = 58.640s (oracle+depth=1): **+5.7%**.

All prefetch-off configs (C1=58.58s, C2=58.43s, C3=58.64s) cluster within 0.4% of each
other — speculation has no effect on BFS in either direction. The small C0 advantage
(+5.6% C1-vs-C0) represents the prefetcher's more modest benefit on irregular BFS access.

Note: C0 BFS runs 14–15 showed anomalous times (61.5s, 59.8s) vs 55.3–55.7s for runs 1–13,
likely EC2 scheduling noise. The 15-run median (55.48s) is robust.

### Why oracle+depth=1 doesn't help

1. **Same-block trylock throttle:** stride-1 sequential access (stencil) and irregular
   (BFS) both predict pages that are almost always in the same 2 MB VA block as the
   faulting page. The demand path holds that block lock; `uvm_mutex_trylock` fails →
   THROTTLED. Gate 2 cross-block probe measured 76.1% throttle rate.

2. **No per-hit wall-time saving:** Gate 2 showed hit batches are 5% *slower* than miss
   batches. A successful speculative migration of a single 4 KB page doesn't offset the
   fault-batch CPU overhead.

3. **Prefetcher cost is the dominant factor:** Turning off the stock prefetcher costs
   3.6× on stencil and 5.6% on BFS. SpecAsync cannot compensate for this because it
   operates one page at a time via a workqueue worker, whereas the UVM prefetcher migrates
   multiple pages per batch in the fault-service hot path.

## Notes on partial stencil results (Preliminary — superseded by full table above)

At n=11, the stencil partial results showed C1=15.37s, C2=16.76s. The final n=15 values
(C1=15.28s, C2=16.75s, C3=15.68s) confirm these early observations.

## C0 GraphBFS anomaly detail

Runs 14 and 15 (61.51s, 59.78s) against a 55.3–55.7s baseline for runs 1–13. The median
of all 15 runs is 55.48s — within 0.02s of the runs 1–13 median — confirming the outliers
do not shift the central tendency. All prefetch-off configs (C1/C2/C3) clustered at
58.4–58.6s, showing a consistent +5.6% cost vs C0 (excluding outlier inflation).

## Status: COMPLETE
