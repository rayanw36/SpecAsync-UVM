# C22 M3: fault-dispatch share of process wall-clock (E4, prefetcher on, threshold 51)

Script `tests/c22_m3_dispatch_share.py`. **Source: E4** (`results/phaseB1/gate_e4/sweep/e3b_<idx>_decomp.bin`, the per-batch decomposition rings, with `gate_e/e4/e4_runs.csv` wall-clock; E1 Part B has no C0 arm). Window = per-batch (replay-push end, or service end) minus drain start, summed over batches; D5 = dispatch inside the lock hold. Ratio of medians over the runs whose rings did not overflow.

| workload | arm | runs used / 10 | median wall (s) | median window (s) | window / wall | median D5 (s) | D5 / wall | D5 / window | evidence |
|---|---|---|---|---|---|---|---|---|---|
| Stencil-24K | C0 | 10 / 10 | 1.129 | 0.1938 | 17.16% | 0.1051 | 9.31% | 54.2% | `E4.mech.stencil.C0` (d5), `C22.M3.stencil.C0` |
| Stencil-24K | C7-W512 | 10 / 10 | 1.074 | 0.1122 | 10.45% | 0.0565 | 5.27% | 50.4% | `E4.mech.stencil.C7-W512` (d5), `C22.M3.stencil.C7-W512` |
| GraphBFS-23 | C0 | 10 / 10 | 31.551 | 0.0585 | 0.19% | 0.0488 | 0.15% | 83.3% | `E4.mech.graphbfs.C0` (d5), `C22.M3.graphbfs.C0` |
| GraphBFS-23 | C7-W512 | 10 / 10 | 31.532 | 0.0408 | 0.13% | 0.0333 | 0.11% | 81.6% | `E4.mech.graphbfs.C7-W512` (d5), `C22.M3.graphbfs.C7-W512` |

Prefetcher off (E4 C1 and C6-W512), for reference in the same units:

| workload | arm | window / wall | D5 / wall |
|---|---|---|---|
| Stencil-24K | C1 | 52.34% | 37.25% |
| Stencil-24K | C6-W512 | 36.22% | 14.93% |
| GraphBFS-23 | C1 | 2.62% | 2.21% |
| GraphBFS-23 | C6-W512 | 1.72% | 1.26% |

Notes: wall-clock is process wall, so the dispatch window is a minority of it with the prefetcher on; per-run values are in the script's data (`e3b_*_decomp.bin`).
