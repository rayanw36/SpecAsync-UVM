# Gate H1 - Report: threshold trade-off on HMM-managed (malloc'd) memory

## Verdict: NOT RUN. The gate stopped in its smoke pass on a kernel oops in the stock driver's HMM path

No timed H1 run exists and the analysis was not run (the sweep never started; there is no `h1_runs.csv`). The pre-registered stop condition (E8's list: new `dmesg` lines matching `BUG`, `Oops`, `exited with irqs disabled`, `soft lockup`; any of the four) fired on the **first oversubscribed malloc-mode cell**.

## What happened (evidence: `h1/STOP`, `h1/h1_lockup_excerpt.txt`, `h1/H1_STATUS.md`)
- Smoke idx 1-6 (the three in-memory cells, both thresholds) completed with exit code 0 and no stop (smoke rows are excluded from analysis by the pre-registration; no number from them is reported).
- Smoke idx 7, **`ov_k1 stock-t0`** (bench_sparse 24 GiB, K = 1, `--alloc malloc`, stock `nvidia_uvm` 6284DA42, threshold 0): 21:49:23 `BUG: kernel NULL pointer dereference` in `free_chunk+0x4d/0xd0 [nvidia_uvm]`, from the kernel thread "vidmem lazy free" (`process_lazy_free`), which then "exited with irqs disabled". From 21:49:48 the UVM GPU fault bottom half spun on a spin lock for 1527 s (soft lockup, CPU 2; trace `uvm_pmm_gpu_unpin_allocated` <- `sync_page_and_chunk_state` <- `uvm_hmm_va_block_service_locked` <- `uvm_va_block_service_locked` <- `service_fault_batch_block_locked`, the HMM GPU-fault path). The machine did not recover and was power-cycled; the chain died with the boot.
- No retry and no further run, per the pre-registered stop rule. End state: stock module, threshold 51, `graphical.target`.

## Interpretation (stated as far as the evidence goes)
- This is a defect in the **stock 595.91.07 driver's HMM eviction/free path under oversubscription** (device-private page chunks freed while another path holds or has dropped the pinned state). It was triggered by an unmodified module, an unmodified kernel and a plain `malloc` array: no specasync code was loaded. The oops precedes the lock-up, so the lock-up is probably the consequence (the lazy-free thread died holding a lock the fault handler needs); that causal order is read from the timestamps, not proven.
- It means the sparse **oversubscribed HMM** cells of H1 cannot be run on this platform without risking a host hang. The in-memory cells ran without incident in the smoke pass, so a reduced gate (in-memory cells only) may be possible, but that is a change of the pre-registration and was not made.
- Consequently **CS2-N10 is not tested on HMM** and nothing in it is flagged as contradicted; the claim stays scoped to managed (`cudaMallocManaged`) memory, which Section III and CS2-N10 already state.

## Limitations
One occurrence. Not reproduced (retrying is forbidden by the stop rule). The trigger cell is the oversubscribed K = 1 at threshold 0; whether other oversubscribed HMM cells (or threshold 51) trigger it is unknown.

## Amendment 1 results

Pre-registration: `H1_PREREGISTRATION.md`, Amendment 1 (commit `54566e2`, before any timed run; order hash `h1_order.sha256`). Run: 60 timed runs (6 cells x 10), all exit 0, **0 new dmesg lines**, no stop condition; stock `nvidia_uvm` 6284DA42, HMM malloc mode (`--alloc malloc`), in-memory cells only. The oversubscribed cells were removed (see the section above). **The sparse half of the trade-off is not tested on HMM.**

### Verdict (mechanical, Amendment 1 rule): DENSE REPLICATED ON HMM

| cell | median t51 (s) | median t0 (s) | difference t0 - t51 (s) | delta | MWU p | Holm threshold | Holm-adjusted p | Holm-sig | MDE, family alpha (m = 3) | Cohen's d | without Tukey outliers (delta s / p) | evidence id |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Stencil-24K | 3.9706 | 3.6541 | -0.3165 | -7.97% | 1.08e-05 | 0.0167 | 3.25e-05 | True | 0.0336 s = 0.85% | -13.4 | -0.3176 / 1.03e-04 (0 and 3 flagged) | `H1.stencil.stock-t0_vs_stock-t51` |
| sparse 8 GiB K=512 | 8.3109 | 6.7010 | -1.6099 | -19.37% | 1.08e-05 | 0.0250 | 3.25e-05 | True | 0.0729 s = 0.88% | -32.1 | -1.6099 / 1.08e-05 (0 and 0 flagged) | `H1.in_k512.stock-t0_vs_stock-t51` |
| sparse 8 GiB K=1 | 2.1617 | 6.4962 | +4.3346 | +200.52% | 1.08e-05 | 0.0500 | 3.25e-05 | True | 0.0522 s = 2.41% | +120.1 | +4.3346 / 1.08e-05 (0 and 0 flagged) | `H1.in_k1.stock-t0_vs_stock-t51` |

### Expectations (kept by Amendment 1)

- **Y1** Stencil-24K: t0 faster than t51, Holm-significant: HELD
- **Y2** Stencil-24K: the malloc-mode gain is smaller than E7's managed -9.57%: HELD
- **Y3** sparse oversubscribed K = 1: t0 slower than t51, Holm-significant: WITHDRAWN (Amendment 1), not scored
- **Y4** sparse in-memory K = 512: t0 faster than t51 (direction only): HELD

### What the result says (and does not)
- **Dense accesses gain from threshold 0 on malloc'd (HMM) memory too:** Stencil-24K and sparse in-memory K = 512 are both Holm-significantly faster at t0. For Stencil-24K the gain is smaller than E7's managed gain (Y2), as expected if part of the managed gain was CPU-side population, but this is a cross-session comparison and **no host share is inferred**.
- **Sparse in-memory K = 1 is much slower at t0 on HMM** (the largest effect in the table), against a small managed-memory effect in E8. This cell is in the kept family and is reported as found; it is **not** part of the Amendment 1 verdict rule, and no expectation covered it. It is a direction opposite to the dense cells within the same memory kind, and bears on the unfinished sparse half, which is nevertheless **not tested for oversubscription on HMM**.
- All wall-clock figures are process wall-clock under HMM (4 KB GPU chunks, `migrate_vma` migrations); absolute times are not comparable with the managed runs.

### Figure and data

`paper/figures/F-H1.pdf` / `.png` (t0 blue, t51 grey; every run a point, median markers filled when Holm-significant); data fallback `paper/figures/F-H1.csv`. FLAG for the author: CS2-N10 is scoped to managed memory and is **not edited**; this result concerns HMM in-memory cells only.

### Limitations

One platform; three in-memory cells; one page list; HMM oversubscription not run (stock-driver oops, see above); THP madvise-only and `MADV_NOHUGEPAGE` set; `numa_balancing` 0; the managed deltas shown in `primary_report.txt` are from other sessions and are not pooled.
