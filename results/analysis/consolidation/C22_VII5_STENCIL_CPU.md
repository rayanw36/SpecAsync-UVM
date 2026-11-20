# C22 VII-5 / M4: CPU-side share of the threshold-0 gain on Stencil-24K

Script `tests/c22_vii5_stencil_cpu.py`. Sources: `results/analysis/derived/c4_e9_phase_split.csv` (nsys phase split of the 3 + 3 traced E9 Stencil-24K runs; produced by `tests/c4_cpu_fault_phases.py`), `gate_e/e9/e9_runs.csv` (traced wall, column `wall_s_NOT_COMPARED`), `gate_e/e7/e7_runs.csv` (untraced wall, 10 + 10 runs). **E9 has a kernel-time split for Stencil-24K** (phase `kernel` = first kernel start to last kernel end of the 20 iterations, host sync between them included).

## Phase medians (s), traced, n = 3 per threshold

| phase | t0 | t51 | t0 - t51 |
|---|---|---|---|
| alloc | 0.060 | 0.060 | -0.000 |
| fill | 0.520 | 0.599 | -0.079 |
| setup | 0.000 | 0.000 | +0.000 |
| kernel | 0.323 | 0.468 | -0.145 |
| post | 0.033 | 0.035 | -0.002 |
| **traced wall** | 2.889 | 3.379 | -0.490 |
| CPU page faults (all in the host fill phase, `E9.cpu_phase.fill_only`) | 2198 | 13188 | -10990 (6.00x fewer at t0) |

## Share of the gain outside the kernels

- Traced gain (t0 - t51 wall): -0.490 s, of which kernels -0.145 s and everything else -0.345 s. **Outside-kernel share of the traced gain = 70.4% (an upper estimate: the tracing residual is included)** (host fill phase alone -0.079 s = 16.2%).
- Where the traced wall is not in a phase: wall minus the five phases = 1.953 s at t0 and 2.217 s at t51 (CUDA initialisation, nsys start-up and trace flush), a difference of -0.264 s, i.e. 53.8% of the traced gain. The traced `post` and `alloc` phases differ by -0.002 s. The traced gain is therefore 29.6% kernels, 16.2% host fill, and 54.2% other (mostly the tracing residual, which grows with the GPU fault count: 27,876 faults at t0 against 91,935 at t51, `E9.ratio.stencil`).
- Untraced Stencil-24K gain (E7 Family A, medians of 10): -0.1085 s (-9.57%). The traced kernel difference (-0.145 s) is **larger than the whole untraced gain**, so the traced kernel/untraced wall mixture is not valid and no untraced share is given: the traced runs cannot be used to split the untraced gain.
- Compare E8 dense cells (K >= 64, t0): 17-23% outside the kernels (`E8.outside_kernels.share_dense`), computed from untraced wall and benchmark-reported kernel time; E9 traced runs are inflated by nsys, so the traced share is an estimate with n = 3.

Per-run values: idx 8 t51: wall 3.357, fill 0.599, kernel 0.472; idx 13 t0: wall 2.932, fill 0.518, kernel 0.316; idx 21 t0: wall 2.889, fill 0.520, kernel 0.337; idx 28 t51: wall 3.421, fill 0.598, kernel 0.453; idx 31 t51: wall 3.379, fill 0.601, kernel 0.468; idx 35 t0: wall 2.827, fill 0.520, kernel 0.323.

Evidence ids (new): `C22.M4.stencil.outside_share_traced`, `C22.M4.stencil.fill_delta`, `C22.M4.stencil.cpu_faults`.
