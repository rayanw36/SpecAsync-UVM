# CS2-N12 proposed text, version 2 (Gate C12; CLAIM_SCOPE.md is not edited; replaces `CS2_N12_PROPOSED.md`)

**CS2-N12 (HMM and managed memory, in memory).** On `malloc`'d memory under the open driver's HMM mode, lowering `uvm_perf_prefetch_threshold` from 51 to 0 speeds up dense access (Stencil-24K -7.97%, `H1.stencil.stock-t0_vs_stock-t51`; sparse K = 512 -19.56%, `H2.malloc_k512.t0_vs_t51`) and slows down sparse access without oversubscription (K = 1 203.65%, `H2.malloc_k1.t0_vs_t51`). The t0 time on HMM is almost independent of K (max/min 1.028, `H2.Z1`). On HMM the GPU memory made resident follows the density rule (`memory.used` residency, valid because HMM chunks are 4 KB): K = 1 at t51 0.061 of the array, K = 8 at t51 0.280, and at t0 1.030 at every K (`H2.res.malloc.k1.t51`, `H2.res.malloc.k8.t51`, `H2.res.malloc.k1.t0`). The K = 1 slowdown differs by allocator: 203.65% on HMM against 3.92% on managed memory (`H2.Z7`).

Per-K deltas, t0 vs t51, same session (H2, 10 runs per cell; E8 is an earlier session):

| K | malloc (H2) | managed (H2) | managed (E8) | evidence ids |
|---|---|---|---|---|
| 1 | 203.65% | 3.92% | 3.95% | `H2.malloc_k1.t0_vs_t51`, `H2.managed_k1.t0_vs_t51`, `E8.in.K1.stock-t0_vs_stock-t51` |
| 8 | 50.39% | -1.49% | -2.32% | `H2.malloc_k8.t0_vs_t51`, `H2.managed_k8.t0_vs_t51`, `E8.in.K8.stock-t0_vs_stock-t51` |
| 64 | -24.66% | -9.99% | -9.69% | `H2.malloc_k64.t0_vs_t51`, `H2.managed_k64.t0_vs_t51`, `E8.in.K64.stock-t0_vs_stock-t51` |
| 512 | -19.56% | -7.19% | -7.54% | `H2.malloc_k512.t0_vs_t51`, `H2.managed_k512.t0_vs_t51`, `E8.in.K512.stock-t0_vs_stock-t51` |

**Volume moved, by instrument (not pooled):** on malloc, from `memory.used` residency (valid for HMM): 1.030 of the array at K = 1, t0. On managed memory, from traced HtoD bytes (E9, nsys): 1.000 of the array at K = 1, t0 and 0.031 at t51 (`E9.htod_frac.in_k1.t0`, `E9.htod_frac.in_k1.t51`). So at threshold 0 a K = 1 pass moves about the whole array on both allocators, each by its own measure; the managed t51 value shows that the density rule keeps managed K = 1 migration small, as on HMM. H2's managed `memory.used` residency is **not** used for any volume statement (it measures allocated 2 MB chunks, `h2/RESIDENCY_SEMANTICS.md`). K = 8 and K = 64 managed traced bytes were not measured.

**Cross-session agreement (managed, in memory):** the managed t0-vs-t51 deltas of H2 and E8 agree at K = 1 (3.92% vs 3.95%) and at K = 8, 64, 512 (-1.49% vs -2.32%, -9.99% vs -9.69%, -7.19% vs -7.54%).

The difference between the allocators in cost at the same threshold-0 volume is consistent with HMM's per-4 KB `migrate_vma` migration (Section III); that attribution is **not isolated** by H2. The oversubscribed HMM case was not measured (stock-driver defect, Section V).
