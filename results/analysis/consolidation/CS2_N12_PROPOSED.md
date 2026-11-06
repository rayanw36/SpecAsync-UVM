**SUPERSEDED by `CS2_N12_PROPOSED_v2.md` (C12) and applied in CLAIM_SCOPE.md CS2-N12 (C13).**

# CS2-N12 proposed text (Gate C11; verdict MECHANISM SUPPORTED; CLAIM_SCOPE.md is not edited)

CS2-N12 (HMM, in memory). On `malloc`'d memory under the open driver's HMM mode, lowering `uvm_perf_prefetch_threshold` from 51 to 0 speeds up dense access (Stencil-24K -7.97%, `H1.stencil.stock-t0_vs_stock-t51`; sparse K = 512 -19.56%, `H2.malloc_k512.t0_vs_t51`) and slows down sparse access without oversubscription (K = 1 +203.65%, `H2.malloc_k1.t0_vs_t51`). At threshold 0 the GPU memory made resident by a K = 1 pass is 95% or more of the array on both allocators (malloc 103%, managed 95%; `H2.res.malloc.k1.t0`, `H2.res.managed.k1.t0`), so the volume moved is the same. The cost differs: the K = 1 slowdown is +203.65% on HMM against +3.92% on managed memory (difference and 95% CI: difference +199.73 points, 95% CI [+198.06, +201.66] (10000 resamples within cells, seed 20261106); `H2.Z7`). This is consistent with HMM's per-4 KB `migrate_vma` migration (Section III). The oversubscribed HMM case was not measured (stock-driver defect, Section V).

Numbers come from `h2_tests.csv`, `h2_residency_cells.csv` and `h2_z.csv`; H1 numbers from `h1_tests.csv`.
