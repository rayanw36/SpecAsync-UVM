#!/usr/bin/env python3
"""C22 V-1: workloads table. Commands from the gates' runners (tests/e7_runner.py:41-52, e09b_runner.py:44-45, e8_cells.py), sizes and passes from the benchmark sources, footprints computed from the
cudaMallocManaged calls (GraphBFS-23 edge count from tests/c22_graph_edges.cpp, a verbatim copy of the benchmark's generator), median wall-clock at t51 from the committed run CSVs (RTX 5070 Ti, stock module).
Writes paper/tables/t_workloads.tex and consolidation/C22_WORKLOADS.md. Not input into any section."""
import csv, statistics as st
GIB = 2.0 ** 30
rd = lambda p: list(csv.DictReader(open(p)))   # noqa: E731
E7 = rd("results/analysis/gate_e/e7/e7_runs.csv"); E8 = [r for r in rd("results/analysis/gate_e/e8/e8_runs.csv") if r["family"] in ("IN", "OV")]
def med7(wl, fam): return st.median(float(r["wall_s"]) for r in E7 if r["workload"] == wl and r["family"] == fam and r["label"].endswith("stock-t51"))
def med8(wl): return st.median(float(r["wall_s"]) for r in E8 if r["workload"] == wl and r["label"].endswith("stock-t51"))
V, E = 1 << 23, 131168515   # tests/c22_graph_edges.cpp: unique edges after dedup (target 134,217,728)
graph = ((V + 1) * 8 + E * 8 + V * 4 + V * 8 * 2 + 4) / GIB
rows = [
 ("Stencil-24K", "stencil", "bench_stencil.cu", "bench_stencil 24000", "24000 x 24000 floats, 2 grids", 2 * 24000 ** 2 * 4 / GIB, "20 ping-pong iterations (`ITERS` 20)", med7("stencil", "A"), "E7.A (family A)", "cudaMallocManaged x2, `bench_stencil.cu`"),
 ("Stencil-8K", "stencil8k", "bench_stencil.cu", "bench_stencil 8000", "8000 x 8000, 2 grids", 2 * 8000 ** 2 * 4 / GIB, "20 iterations", med7("stencil8k", "B"), "E7.B", ""),
 ("Sweep-4K", "sweep4k", "bench_stencil.cu", "bench_stencil 4000", "4000 x 4000, 2 grids", 2 * 4000 ** 2 * 4 / GIB, "20 iterations", med7("sweep4k", "B"), "E7.B", ""),
 ("Sweep-16K", "sweep16k", "bench_stencil.cu", "bench_stencil 16000", "16000 x 16000, 2 grids", 2 * 16000 ** 2 * 4 / GIB, "20 iterations", med7("sweep16k", "B"), "E7.B", ""),
 ("STREAM", "stream", "bench_stream.cu", "bench_stream 268435456", "2^28 floats x 3 arrays", 3 * 268435456 * 4 / GIB, "one triad kernel launch", med7("stream", "B"), "E7.B", "A, B, C"),
 ("SGEMM", "sgemm", "bench_sgemm.cu", "bench_sgemm 24000", "24000 x 24000, 3 matrices", 3 * 24000 ** 2 * 4 / GIB, "one `cublasSgemm`", med7("sgemm", "B"), "E7.B", "A, B, C"),
 ("cuFFT", "cufft", "bench_cufft.cu", "bench_cufft 134217728", "2^27 complex (8 B), in place", 134217728 * 8 / GIB, "one forward C2C FFT", med7("cufft", "B"), "E7.B", ""),
 ("GraphBFS-23", "graphbfs", "graph_bfs/bench_graph_bfs.cu", "graph_bfs/bench_graph_bfs 23", f"R-MAT, 2^23 vertices, {E:,} unique edges (target 16 per vertex = 134,217,728)", graph, "level-synchronous BFS until the frontier is empty (level count not recorded)", med7("graphbfs", "B"), "E7.B", "row_ptr, col_idx, visited, 2 frontiers"),
 ("Stencil, oversubscribed", "oversub", "stencil_oversub/bench_stencil_oversub.cu", "stencil_oversub/bench_stencil_oversub 48000 1", "48000 x 48000, 2 grids", 2 * 48000 ** 2 * 4 / GIB, "1 iteration (`iters` argument)", med7("oversub", "B"), "E7.B", "17.2 GiB on the 16 GB GPU"),
]
for size, gib in (("in", 8), ("ov", 24)):
    for K in (1, 8, 64, 512):
        rows.append((f"Sparse, {'in memory' if size == 'in' else 'oversubscribed'}, K = {K}", f"{size}_k{K}", "bench_sparse.cu", f"bench_sparse {gib} {K} 3 202610081", f"{gib} GiB array, {K} of 512 pages touched per 2 MB block", float(gib), "3 passes over the same page list", med8(f"{size}_k{K}"), "E8", "one array"))
o = ["# C22 V-1: workloads of the paper", "", "Script `tests/c22_workloads.py`; table `paper/tables/t_workloads.tex` (generated; **not input into any section**). Median wall-clock = median of 10 runs at threshold 51 (stock module, driver 595.91.07, RTX 5070 Ti): E7 (`results/analysis/gate_e/e7/e7_runs.csv`, `label` ending `stock-t51`) for the E7 workloads, E8 (`e8/e8_runs.csv`) for the sparse benchmark. Commands: `tests/e7_runner.py:41-52`, `tests/e09b_runner.py:44-45`, `tests/e8_cells.py:17`. Footprint = bytes of the `cudaMallocManaged` allocations / 2^30 (GraphBFS-23: unique edge count from `tests/c22_graph_edges.cpp`, a verbatim copy of the benchmark's generator, dedup and self-loop rule). HMM runs (H1, H2) use the same sources with `--alloc malloc` (same sizes).", "",
     "| workload | source file (`benchmarks/`) | command | problem size | managed footprint (GiB) | passes / iterations | median wall t51 (s) | gate | allocations |", "|---|---|---|---|---|---|---|---|---|"]
for nm, key, src, cmd, size, gib, passes, wall, gate, alloc in rows:
    o.append(f"| {nm} | `{src}` | `{cmd}` | {size} | {gib:.3f} | {passes} | {wall:.3f} | {gate} | {alloc} |")
o += ["", "Not recorded: the number of BFS levels of GraphBFS-23 (computed at run time and printed to stderr only). The T4 runs use the same commands; only the 5070 Ti medians are listed.", "", "Evidence ids (new): `C22.workloads.<workload key>` (footprint, median wall)."]
open("results/analysis/consolidation/C22_WORKLOADS.md", "w").write("\n".join(o) + "\n")
def tx(s): return s.replace("_", "\\_").replace("%", "\\%").replace("&", "\\&").replace("`", "")
t = ["\\begin{tabular}{@{}lllrrr@{}}", "\\toprule", "Workload & Command & Problem size & Footprint (GiB) & Passes & Wall t51 (s) \\\\", "\\midrule"]
for nm, key, src, cmd, size, gib, passes, wall, gate, alloc in rows:
    t.append(f"{tx(nm)} & \\texttt{{{tx(cmd)}}} & {tx(size)} & {gib:.2f} & {tx(passes.split(' (')[0])} & {wall:.2f} \\\\ % C22.workloads.{key}")
t += ["\\bottomrule", "\\end{tabular}", ""]
open("paper/tables/t_workloads.tex", "w").write("\n".join(t))
print("\n".join(o[5:16]))
