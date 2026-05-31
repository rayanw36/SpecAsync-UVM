# Benchmark Reconstruction Notes

## Background

The `.cu` source files for the four core benchmarks were not in the repository
at the start of Phase 2 — the `.gitignore` rule `bench_*` (intended for
compiled binaries) also silently excluded `.cu` source files.  The `.gitignore`
has been updated to `bench_*` + `!bench_*.cu` to fix this.

All four core benchmark sources were **reconstructed from scratch** during Phase 2
based on the following evidence:
1. `run_robust.py` documents exact size arguments, benchmark names, and binary
   names (`./bench_stream`, `./bench_sgemm`, etc.).
2. `robust_results_baseline.csv` provides measured wall times and bandwidth
   values to cross-check against.
3. `benchmarks/README_benchmarks.md` documents the build command flags.
4. The paper describes the access pattern for each benchmark (STREAM triad,
   cuBLAS SGEMM, 2D stencil, cuFFT).

---

## Core benchmarks (bench_*.cu)

### bench_stream.cu

- **Pattern:** STREAM Triad — `C[i] = A[i] + scalar * B[i]`
- **Allocation:** 3 × N float arrays via `cudaMallocManaged`
- **Size argument:** N elements (e.g. 134217728 = 128M)
- **Timing:** single kernel execution between `cudaDeviceSynchronize` calls;
  `clock_gettime(CLOCK_MONOTONIC)` wall clock
- **Bandwidth formula:** `3 × N × sizeof(float) / time_s / 1e9` GB/s
  (1 read A, 1 read B, 1 write C)
- **Reconstruction decision:** Scalar constant is 2.0f (arbitrary; does not
  affect memory traffic or fault pattern)
- **Expected ballpark (from baseline CSV):**
  - N=128M  → ~88 ms,  ~18.5 GB/s
  - N=256M  → ~174 ms, ~18.5 GB/s
  - N=512M  → ~345 ms, ~18.7 GB/s
- **Validation:** Order-of-magnitude correct; relative ordering preserved

---

### bench_sgemm.cu

- **Pattern:** cuBLAS SGEMM — `C = A × B` (N×N float matrices, no transpose)
- **Allocation:** 3 × N² float matrices via `cudaMallocManaged`
- **Size argument:** N (side length, e.g. 8192)
- **Timing:** `cublasCreate` / `cublasSgemm` / `cudaDeviceSynchronize`;
  timer wraps only the SGEMM call
- **Bandwidth formula:** `3 × N² × sizeof(float) / time_s / 1e9` GB/s
  (reads A, B; writes C)
- **Reconstruction decision:** alpha=1.0f, beta=0.0f; column-major layout as
  required by cuBLAS
- **Expected ballpark (from baseline CSV):**
  - N=8192   → ~152 ms
  - N=16384  → ~1025 ms
  - N=24000  → ~3077 ms
- **Note:** SGEMM is compute-bound at large N; page faults occur on first
  access to managed arrays. Timing is dominated by FLOPS, not memory.

---

### bench_stencil.cu

- **Pattern:** 2D 5-point stencil on N×N float grid, ping-pong
- **Allocation:** 2 × N² float grids via `cudaMallocManaged`
- **Size argument:** N (grid side length)
- **Kernel:** `new[i,j] = 0.25 × (old[i-1,j] + old[i+1,j] + old[i,j-1] + old[i,j+1])`
  (boundary rows/cols skipped)
- **Iterations:** 20 ping-pong iterations
- **Thread block:** 16×16 threads
- **Bandwidth formula:** `20 × N² × 2 × sizeof(float) / time_s / 1e9` GB/s
  (read old + write new per iteration)
- **Expected ballpark (from baseline CSV):**
  - N=8192   → ~28.7 ms
  - N=16384  → ~90.8 ms
  - N=24000  → ~213 ms

---

### bench_cufft.cu

- **Pattern:** 1D complex-to-complex FFT (cuFFT)
- **Allocation:** N `cufftComplex` elements via `cudaMallocManaged`
- **Size argument:** N elements (e.g. 67108864 = 64M)
- **API:** `cufftPlan1d` → `cufftExecC2C(CUFFT_FORWARD)` → `cudaDeviceSynchronize`
- **Bandwidth formula:** `2 × N × sizeof(cufftComplex) / time_s / 1e9` GB/s
  (input read + output write; cuFFT operates in-place on `cudaMallocManaged` buffer)
- **Expected ballpark (from baseline CSV):**
  - N=64M   → ~23.4 ms
  - N=128M  → ~44.0 ms
  - N=256M  → ~86.4 ms
- **Note:** cuFFT is the benchmark most responsive to SpecAsync-UVM (Exp1
  shows up to 4.4% speedup). The irregular access pattern of FFT butterfly
  stages produces scattered page faults.

---

## New oversubscription benchmarks (Phase 2)

### stencil_oversub/bench_stencil_oversub.cu

- **Pattern:** Identical to bench_stencil.cu (same 5-point stencil, 20 iters)
- **Purpose:** Large working sets that exceed GPU VRAM (16 GB on RTX 5070 Ti)
- **Size argument:** N (grid side length)
- **Working-set calculation:** `2 × N² × sizeof(float)` total managed memory

| N     | Working set | VRAM ratio (16 GB) |
|-------|-------------|---------------------|
| 51200 | 20.97 GB    | 1.31× (≈1.25×)     |
| 55000 | 24.20 GB    | 1.51× (≈1.5×)      |
| 63000 | 31.75 GB    | 1.98× (≈2×)        |

- **Design decision:** Accepts optional second argument `[iters]` (default 20)
  for flexibility. Start-up prints `[INFO] Grid NxN = X.XX GB managed memory`
  to stderr so you can track allocation progress on large grids.

---

### graph_bfs/bench_graph_bfs.cu

- **Pattern:** Frontier-based level-synchronous BFS on R-MAT synthetic graph
- **Size argument:** `log2_vertices` (24 → 16M, 25 → 33M, 26 → 67M vertices)
- **Graph generation:** R-MAT with parameters a=0.57, b=0.19, c=0.19, d=0.05
  (Kronecker-style, per SSCA benchmark). Per-edge LCG seed. Self-loops removed.
  Sorted and deduplicated via `std::sort`.
- **CSR layout:** `row_ptr` (N+1 `long long`) + `col_idx` (M `long long`),
  both `cudaMallocManaged`. BFS arrays (`visited`, `frontier`, `next_frontier`)
  also `cudaMallocManaged` to drive UVM faults.
- **BFS kernel:** `atomicCAS` on visited array; one kernel launch per level.
- **Bandwidth formula:** `edges_traversed × 8 / time_s / 1e9` GB/s
  (4B col_idx read + 4B visited read per traversed edge)
- **Working-set target:** ~20, 24, 32 GB total managed memory at log2=24,25,26
  (actual size depends on generated edge count)
- **Reconstruction decision:** log2_vertices was chosen as the natural
  parameterisation for R-MAT; the harness maps this to GB targets.

---

## Validation plan (Phase B)

1. Compile all benchmarks on the GPU box: `make -C benchmarks/`
2. Run a single trial for each benchmark × size from `run_robust.py`'s size list:
   ```
   ./bench_stream 134217728   # expect ~88 ms
   ./bench_sgemm  8192        # expect ~152 ms
   ./bench_stencil 8192       # expect ~28.7 ms
   ./bench_cufft  67108864    # expect ~23.4 ms
   ```
3. Compare to `results/baseline/robust_results_baseline.csv` means.
   Accept if within ±20% — variance is expected given driver differences,
   GPU boost state, and measurement noise.
4. If a benchmark is more than 2× off, investigate before running the full suite.
