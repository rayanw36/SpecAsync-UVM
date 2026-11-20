# C22 V-1: workloads of the paper

Script `tests/c22_workloads.py`; table `paper/tables/t_workloads.tex` (generated; **not input into any section**). Median wall-clock = median of 10 runs at threshold 51 (stock module, driver 595.91.07, RTX 5070 Ti): E7 (`results/analysis/gate_e/e7/e7_runs.csv`, `label` ending `stock-t51`) for the E7 workloads, E8 (`e8/e8_runs.csv`) for the sparse benchmark. Commands: `tests/e7_runner.py:41-52`, `tests/e09b_runner.py:44-45`, `tests/e8_cells.py:17`. Footprint = bytes of the `cudaMallocManaged` allocations / 2^30 (GraphBFS-23: unique edge count from `tests/c22_graph_edges.cpp`, a verbatim copy of the benchmark's generator, dedup and self-loop rule). HMM runs (H1, H2) use the same sources with `--alloc malloc` (same sizes).

| workload | source file (`benchmarks/`) | command | problem size | managed footprint (GiB) | passes / iterations | median wall t51 (s) | gate | allocations |
|---|---|---|---|---|---|---|---|---|
| Stencil-24K | `bench_stencil.cu` | `bench_stencil 24000` | 24000 x 24000 floats, 2 grids | 4.292 | 20 ping-pong iterations (`ITERS` 20) | 1.134 | E7.A (family A) | cudaMallocManaged x2, `bench_stencil.cu` |
| Stencil-8K | `bench_stencil.cu` | `bench_stencil 8000` | 8000 x 8000, 2 grids | 0.477 | 20 iterations | 0.332 | E7.B |  |
| Sweep-4K | `bench_stencil.cu` | `bench_stencil 4000` | 4000 x 4000, 2 grids | 0.119 | 20 iterations | 0.242 | E7.B |  |
| Sweep-16K | `bench_stencil.cu` | `bench_stencil 16000` | 16000 x 16000, 2 grids | 1.907 | 20 iterations | 0.629 | E7.B |  |
| STREAM | `bench_stream.cu` | `bench_stream 268435456` | 2^28 floats x 3 arrays | 3.000 | one triad kernel launch | 0.618 | E7.B | A, B, C |
| SGEMM | `bench_sgemm.cu` | `bench_sgemm 24000` | 24000 x 24000, 3 matrices | 6.437 | one `cublasSgemm` | 4.631 | E7.B | A, B, C |
| cuFFT | `bench_cufft.cu` | `bench_cufft 134217728` | 2^27 complex (8 B), in place | 1.000 | one forward C2C FFT | 0.390 | E7.B |  |
| GraphBFS-23 | `graph_bfs/bench_graph_bfs.cu` | `graph_bfs/bench_graph_bfs 23` | R-MAT, 2^23 vertices, 131,168,515 unique edges (target 16 per vertex = 134,217,728) | 1.196 | level-synchronous BFS until the frontier is empty (level count not recorded) | 31.507 | E7.B | row_ptr, col_idx, visited, 2 frontiers |
| Stencil, oversubscribed | `stencil_oversub/bench_stencil_oversub.cu` | `stencil_oversub/bench_stencil_oversub 48000 1` | 48000 x 48000, 2 grids | 17.166 | 1 iteration (`iters` argument) | 3.258 | E7.B | 17.2 GiB on the 16 GB GPU |
| Sparse, in memory, K = 1 | `bench_sparse.cu` | `bench_sparse 8 1 3 202610081` | 8 GiB array, 1 of 512 pages touched per 2 MB block | 8.000 | 3 passes over the same page list | 1.579 | E8 | one array |
| Sparse, in memory, K = 8 | `bench_sparse.cu` | `bench_sparse 8 8 3 202610081` | 8 GiB array, 8 of 512 pages touched per 2 MB block | 8.000 | 3 passes over the same page list | 1.693 | E8 | one array |
| Sparse, in memory, K = 64 | `bench_sparse.cu` | `bench_sparse 8 64 3 202610081` | 8 GiB array, 64 of 512 pages touched per 2 MB block | 8.000 | 3 passes over the same page list | 1.847 | E8 | one array |
| Sparse, in memory, K = 512 | `bench_sparse.cu` | `bench_sparse 8 512 3 202610081` | 8 GiB array, 512 of 512 pages touched per 2 MB block | 8.000 | 3 passes over the same page list | 1.967 | E8 | one array |
| Sparse, oversubscribed, K = 1 | `bench_sparse.cu` | `bench_sparse 24 1 3 202610081` | 24 GiB array, 1 of 512 pages touched per 2 MB block | 24.000 | 3 passes over the same page list | 5.054 | E8 | one array |
| Sparse, oversubscribed, K = 8 | `bench_sparse.cu` | `bench_sparse 24 8 3 202610081` | 24 GiB array, 8 of 512 pages touched per 2 MB block | 24.000 | 3 passes over the same page list | 6.777 | E8 | one array |
| Sparse, oversubscribed, K = 64 | `bench_sparse.cu` | `bench_sparse 24 64 3 202610081` | 24 GiB array, 64 of 512 pages touched per 2 MB block | 24.000 | 3 passes over the same page list | 7.669 | E8 | one array |
| Sparse, oversubscribed, K = 512 | `bench_sparse.cu` | `bench_sparse 24 512 3 202610081` | 24 GiB array, 512 of 512 pages touched per 2 MB block | 24.000 | 3 passes over the same page list | 7.934 | E8 | one array |

Not recorded: the number of BFS levels of GraphBFS-23 (computed at run time and printed to stderr only). The T4 runs use the same commands; only the 5070 Ti medians are listed.

Evidence ids (new): `C22.workloads.<workload key>` (footprint, median wall).
