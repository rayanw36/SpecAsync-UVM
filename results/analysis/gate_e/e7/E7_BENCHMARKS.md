# Phase 2c: Family B benchmarks, command lines and checks

Read-only apart from **one execution check per benchmark** on 2026-10-07 (stock module 6284DA42…, threshold 51,
`timeout 200 setarch -R <bench>`, wall-clock of the process, GUI session still active). These single runs are a
build/execute check and a timeout basis. They are **not data**, enter no analysis, and are not the C0 median.

Binaries are the committed ones in `benchmarks/` (built by `benchmarks/Makefile`; the Makefile targets sm_75, the
binaries ran unchanged on the RTX 5070 Ti). **All seven executed with exit 0**, so none is dropped.

| Family B order | workload | command line | size | single-run check wall (s) | latest C0 median on this platform | source of the size |
|---|---|---|---|---:|---|---|
| 1 | Stencil-8K | `benchmarks/bench_stencil 8000` | 8000² floats, 20 iters, ≈0.27 GB | 0.445 | none on 595.91.07 (Phase C 5070 Ti decomp runs on 595.84 exist; not re-extracted here) | `t3_phasec_paired_wallclock.sh` (`Stencil-8K`) |
| 2 | Sweep-4K | `benchmarks/bench_stencil 4000` | 4000² | 0.214 | none | same script |
| 3 | Sweep-16K | `benchmarks/bench_stencil 16000` | 16000² | 0.614 | none | same script |
| 4 | STREAM | `benchmarks/bench_stream 268435456` | 268,435,456 elements (≈1.07 GB) | 0.703 | none | **DOC-class choice** (see below) |
| 5 | SGEMM | `benchmarks/bench_sgemm 24000` | N=24000 (≈2.3 GB) | 5.294 | none on 595.91.07 | `t_b8_sgemm_interleaved.sh` default |
| 6 | cuFFT | `benchmarks/bench_cufft 134217728` | 134,217,728 complex elements | 0.373 | none | **DOC-class choice** (see below) |
| 7 | GraphBFS-23 | `benchmarks/graph_bfs/bench_graph_bfs 23` | scale 23 | not re-run (≈31.5 s per E6) | **31.5426 s** (E6 C0-t51, `E6.F2.C0-t0_vs_C0-t51` base) | E4/E6 |
| 8 (last) | Stencil oversub | `benchmarks/stencil_oversub/bench_stencil_oversub 48000 1` | N=48000, iters=1 (≈1.08× GPU memory) | 3.300 | **3.31 s** (B9 task 2c, iters=1, driver 595.84, n=5: `B9.2c.iters1` C0) | `t_b9_task2c_c0_and_counters.sh`, N=48000 |

## Decisions (all DOC-class; conservative choice taken)

1. **Duplicates dropped.** `Sweep-8K` is `bench_stencil 8000`, identical to Stencil-8K; `Sweep-24K` is
   `bench_stencil 24000`, identical to Family A's Stencil-24K. Both are dropped from Family B. The "distinct Phase C
   sweep sizes" are therefore **Sweep-4K and Sweep-16K**.
2. **STREAM size.** CS2-14 (STREAM −8.8%) is marked UNCHECKED and records no size. The Gate C T4 interleaved runs
   used 134,217,728 and 268,435,456 (`results/phaseB1/gate_c/`). I use **268,435,456**, the larger of the two, because
   it gives the longer run. Not claimed to be the size behind CS2-14.
3. **cuFFT size.** CS2-12's "up to 4.4%" comes from the "−4.35%/−4.32% pair, the two smaller sizes"
   (`results/figures/CUFFT_PROVENANCE.md` Q5), i.e. **67,108,864 and 134,217,728**: two sizes, not one. Using both
   would add a cell and a Holm term not in the brief. I use the **larger, 134,217,728**, which the legacy suite
   labels 0.54 GB. Recorded here so the choice is visible.
4. **Oversubscribed Stencil.** B9's iteration sweep (`1 3 5 10 20`) has C0 medians 3.31, 6.02, 8.58, 15.73, 27.18 s
   (`B9.2c.iters{1,3,5,10,20}`). The **shortest is iters = 1 (3.31 s)**, so the command is `… 48000 1`, and the
   timeout is **3 × 3.31 = 9.93 s → 10 s**. A timeout is a stop.
5. **Timeouts for the others** (the brief fixes only GraphBFS-23 = 168 s and oversub): Stencil-8K/4K/16K **22 s**
   (E-gate Stencil value), STREAM, cuFFT **22 s**, SGEMM **60 s** (≥ 10× the 5.3 s check run). They are loose
   enough that a timeout means a real hang.
6. **No C0 history on this platform for most workloads**, hence "none" in the C0-median column; the single-run
   check is not a substitute.
