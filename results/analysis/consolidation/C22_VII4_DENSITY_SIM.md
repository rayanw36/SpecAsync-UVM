# C22 VII-4: does the density rule (Eq. 1) explain E8's failed expectations? (descriptive simulation)

Script `tests/c22_vii4_density_sim.py`; page list reproduced by `tests/c22_pagelist.cpp` (same `mt19937_64`, `std::shuffle`, partial Fisher-Yates as `benchmarks/bench_sparse.cu`; the 8 GiB hashes equal the logged `page_list_hash` of the H2 runs: K=1 `8033df96e71bf8eb`, K=8 `79f57bb182dc47ca`, K=64 `4167c60bd21b7c0e`, K=512 `34416921a498ff60`; the 24 GiB lists use the same code and are not independently validated). Rule from `uvm_perf_prefetch.c:118` (`100*count > threshold*size`, strict), `grow_fault_granularity` (`:176-227`, whole 64 KB big pages filled in the bitmap when any page of the big page faults and nothing is thrashing) and `compute_prefetch_region` (`:102-146`, the largest passing subregion containing a faulted page wins; leaf-to-root traversal, `uvm_perf_prefetch.h:108-113`).

**Model assumptions:** every K page of a block is in one service call, the block is GPU-empty, no thrashing, no prefetch of other blocks. Predicted fraction = mean over blocks of (faulted pages U prefetch regions) / 512. This is the first-touch fraction of a block, so it predicts the *first-pass* HtoD volume as a fraction of the array.

## Predicted migrated fraction of the array per cell (mean over blocks; min..max per block)

| size | K | t0 | t25 | t51 |
|---|---|---|---|---|
| in | 1 | 100.00% (100.0..100.0) | 6.25% (6.2..6.2) | 3.12% (3.1..3.1) |
| in | 8 | 100.00% (100.0..100.0) | 55.50% (25.0..75.0) | 23.41% (12.5..37.5) |
| in | 64 | 100.00% (100.0..100.0) | 100.00% (100.0..100.0) | 100.00% (100.0..100.0) |
| in | 512 | 100.00% (0.0..100.0) | 100.00% (0.0..100.0) | 100.00% (0.0..100.0) |
| ov | 1 | 100.00% (100.0..100.0) | 6.25% (6.2..6.2) | 3.12% (3.1..3.1) |
| ov | 8 | 100.00% (100.0..100.0) | 55.48% (25.0..75.0) | 23.40% (12.5..37.5) |
| ov | 64 | 100.00% (100.0..100.0) | 100.00% (100.0..100.0) | 100.00% (100.0..100.0) |
| ov | 512 | 100.00% (0.0..100.0) | 100.00% (0.0..100.0) | 100.00% (0.0..100.0) |

## Measured: E9 traced HtoD (n = 3, medians) and H2 HMM residency (n = 3)

In-memory E9 cells exist for K = 1 and 512 only. Oversubscribed E9 cells: the first-pass column uses `pass1_htod_bytes` (median of the 3 runs) as a fraction of the 24 GiB array, the total column `htod_bytes` / (3 x 24 GiB).

| cell | threshold | predicted first-touch fraction | measured | measured / predicted | evidence |
|---|---|---|---|---|---|
| in_k1 | 0 | 100.00% | 100.00% (htod 8.000 GiB) | 1.00 | `E9.cell.in_k1.t0` |
| in_k1 | 51 | 3.12% | 3.12% (htod 0.250 GiB) | 1.00 | `E9.cell.in_k1.t51` |
| in_k512 | 0 | 100.00% | 95.44% (htod 7.635 GiB) | 0.95 | `E9.cell.in_k512.t0` |
| in_k512 | 51 | 100.00% | 99.26% (htod 7.941 GiB) | 0.99 | `E9.cell.in_k512.t51` |
| ov_k1 (first pass) | 0 | 100.00% | 200.00% | 2.00 | `E9.cell.ov_k1.t0` (`pass1_htod_bytes`) |
| ov_k1 (first pass) | 51 | 3.12% | 6.25% | 2.00 | `E9.cell.ov_k1.t51` (`pass1_htod_bytes`) |
| ov_k8 (first pass) | 0 | 100.00% | 199.93% | 2.00 | `E9.cell.ov_k8.t0` (`pass1_htod_bytes`) |
| ov_k8 (first pass) | 51 | 23.40% | 47.26% | 2.02 | `E9.cell.ov_k8.t51` (`pass1_htod_bytes`) |
| ov_k64 (first pass) | 0 | 100.00% | 100.00% | 1.00 | `E9.cell.ov_k64.t0` (`pass1_htod_bytes`) |
| ov_k64 (first pass) | 51 | 100.00% | 100.00% | 1.00 | `E9.cell.ov_k64.t51` (`pass1_htod_bytes`) |
| ov_k512 (first pass) | 0 | 100.00% | 99.66% | 1.00 | `E9.cell.ov_k512.t0` (`pass1_htod_bytes`) |
| ov_k512 (first pass) | 51 | 100.00% | 100.00% | 1.00 | `E9.cell.ov_k512.t51` (`pass1_htod_bytes`) |

Oversubscribed first-pass HtoD at K = 1 is exactly 2.00x the model at both thresholds (48 GiB at t0 = 2 x 24 GiB; 1.5 GiB at t51 = 2 x 0.75 GiB), and 1.9-2.0x at K = 8; at K = 64 and 512 the first pass is near 1x. The model does not predict the doubling; it is not explained here (candidate causes not tested: eviction write-back followed by re-fault of the same block within a pass, or nsys counting each prefetch migration twice under oversubscription).

## H2 HMM residency (`memory.used` residency, valid on HMM) against the same rule

HMM blocks use 4 KB GPU chunks and a prefetch region clamped to the VMA/policy (`uvm_hmm_get_prefetch_region`), so the managed rule is only a reference; the second column of predictions applies the same tree with a 32-page (128 KB) granule-growth to test whether the HMM t51 values look like a doubled granule (exploratory, not a documented behaviour).

| K | threshold | managed-rule prediction | granule 32 pages (exploratory) | measured HMM residency (median frac of 8 GiB) | evidence |
|---|---|---|---|---|---|
| 1 | 0 | 100.00% | 100.00% | 103.0% | `H2.res.malloc.k1.t0` |
| 1 | 51 | 3.12% | 6.25% | 6.1% | `H2.res.malloc.k1.t51` |
| 8 | 0 | 100.00% | 100.00% | 103.0% | `H2.res.malloc.k8.t0` |
| 8 | 51 | 23.41% | 47.19% | 28.0% | `H2.res.malloc.k8.t51` |
| 64 | 0 | 100.00% | 100.00% | 103.0% | `H2.res.malloc.k64.t0` |
| 64 | 51 | 100.00% | 100.00% | 103.0% | `H2.res.malloc.k64.t51` |
| 512 | 0 | 100.00% | 100.00% | 103.2% | `H2.res.malloc.k512.t0` |
| 512 | 51 | 100.00% | 100.00% | 103.2% | `H2.res.malloc.k512.t51` |

(H2 measured thresholds are t0 and t51 only; t25 rows appear only where a cell exists.)

## XS4 and XS5 (E8 expectations that FAILED)

**Result of the simulation (volume only):** the rule reproduces the measured first-touch volume where E9 has a cell (in-memory K = 1: 100% at t0 and 3.12% at t51, measured/predicted 1.00 and 1.00; K = 512: about 100%), predicts t25 = 6.25% at K = 1 (a 32-page subregion passes, the 64-page one fails the strict test: 16 counted pages x 100 = 1600 is not > 64 x 25 = 1600) and predicts the K = 8 bimodality (t25 per-block volume 25% to 75%: blocks whose widened groups do not overlap reach exactly 128 counted pages = 25% of 512, which fails the strict test, as hypothesised). Predicted volume is monotone in the threshold in every cell (t51 <= t25 <= t0: True).

**XS4** (the t0 delta rises monotonically as K falls; FAILED because K = 64 is faster than K = 512: in-memory -9.69% against -7.54%, oversubscribed -9.67% against -7.66%). The rule predicts that t0 moves the whole block at every K and t51 moves K=1: 3.1%, K=8: 23.4%, K=64: 100.0%, K=512: 100.0%, so the extra volume of t0 over t51 is K=1: 96.9%, K=8: 76.6%, K=64: 0.0%, K=512: 0.0% of the array: non-increasing in K, and **identical (zero) at K = 64 and K = 512**. A volume-only rule therefore predicts no difference between those two cells, so the XS4 violation (a 2.2-point difference between two cells with the same predicted volume) does **not follow from the rule**; it must come from something the rule does not model (fault counts and batch structure: K = 64 raises more faults per block than K = 512 at t51, E9 `gpu_faults_sum`).

**XS5** (t25 between t0 and t51 cell by cell; FAILED in-memory K = 1 and K = 8 and oversubscribed K = 8). Predicted t25 volumes: K=1: 6.2% (t0 100%, t51 3.1%); K=8: 55.5% (t0 100%, t51 23.4%). The ordering of *volume* is t51 <= t25 <= t0 in every cell, so XS5 holds for volume; its failures are wall-clock orderings (in-memory K = 1: t25 -0.60% against t0 +3.95%, the extra 0.25 GiB cannot make t25 faster than t51; K = 8: t25 +0.78% with t25 volume between t51 and t0 while t0 is -2.32%), so they do **not follow from the rule alone**. E9 has no t25 cells, so t25 volume is a prediction only.

**Verdict:** Eq. 1 with the 64 KB growth explains the volume at t0 and t51 (and the in-memory K = 1 and 512 E9 cells to 1%), and explains the bimodal t25 at K = 8, but it does not explain the XS4 and XS5 failures, which are time orderings among cells whose predicted volume is equal or monotone.
