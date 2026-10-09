# CPU-fault check (Gate C4, step 5; read-only)

Question: E9's nsys counts show **6.00x more CPU page faults at t51 than at t0 in every cell** (`E9.ratio.cpu_faults_t51_over_t0`), and at t0 the count equals the number of 2 MB blocks. Does the stock driver's
CPU fault path use the prefetcher and its threshold, where in a run do those faults occur, and how much of the E8 wall-clock effect lies outside the kernels? No module was loaded and nothing was run: the source tree,
the existing E9 nsys reports and the committed E8 CSV were read. Scripts: `tests/c4_cpu_fault_phases.py` (outputs `results/analysis/derived/c4_e9_phase_split.csv`, `c4_e8_outside_kernels.csv`).

## 5a. Driver source: does the CPU fault path use the same threshold?

**Yes.** Source: the DKMS tree `/usr/src/nvidia-595.91.07/nvidia-uvm/` that the stock module loaded in E8 and E9 is built from. (`driver/src` in this repository holds only the SpecAsync files; the SpecAsync work tree's
`uvm_perf_prefetch.c` is byte-identical to the DKMS file, so the prefetcher is unmodified in every module used.)

**The threshold has one definition and one use.**

| what | where |
|---|---|
| module parameter `uvm_perf_prefetch_threshold` (default `UVM_PREFETCH_THRESHOLD_DEFAULT` = 51) | `uvm_perf_prefetch.c:42`, `:48`, `:60` |
| validated at init: a value <= 100 becomes `g_uvm_perf_prefetch_threshold`, otherwise the default 51 | `uvm_perf_prefetch.c:552-560` |
| **the only use of the threshold**: the strict density test `counter * 100 > subregion_pages * g_uvm_perf_prefetch_threshold`, in `compute_prefetch_region` | `uvm_perf_prefetch.c:118` |
| `compute_prefetch_region` is called once per faulted page by `compute_prefetch_mask` | `uvm_perf_prefetch.c:295` |

**Where the prefetcher is called from (every call site):**

| # | call site | path |
|---|---|---|
| 1 | `uvm_perf_prefetch_get_hint_va_block(...)` at `uvm_va_block.c:11504`, inside `uvm_va_block_get_prefetch_hint` (`uvm_va_block.c:11487`) | called at `uvm_va_block.c:12046` from `uvm_va_block_service_locked` (`uvm_va_block.c:12021`), which is the common servicing function for: **GPU replayable faults** (`uvm_gpu_replayable_faults.c:1568`), non-replayable faults (`uvm_gpu_non_replayable_faults.c:464`), access counters (`uvm_gpu_access_counters.c:1287`) **and CPU faults** |
| 1a | **CPU fault entry**: `uvm_va_block_cpu_fault` (`uvm_va_block.c:12476`) -> `block_cpu_fault_locked` (`:12358`, invoked at `:12507`) -> `uvm_va_block_service_locked(UVM_ID_CPU, ...)` at **`uvm_va_block.c:12467`** | the destination processor is the CPU (`new_residency` = CPU), so the hint is computed for pages migrating or populating **on the CPU** |
| 2 | `uvm_perf_prefetch_compute_ats(...)` at `uvm_ats_faults.c:440` (`uvm_perf_prefetch.c:466-486`) | the ATS fault path; it also ends in `compute_prefetch_mask` (`uvm_perf_prefetch.c:482`) and so uses the same threshold. Not exercised by the managed-memory benchmarks here (not established which path, if any, ATS takes on this host) |

**What the threshold governs on a CPU fault.** Inside `uvm_perf_prefetch_get_hint_va_block` (`uvm_perf_prefetch.c:488`) the destination is the faulting processor. With the benchmarks' settings (no `cudaMemAdvise`, so the
preferred location is unset), `should_apply_prefetch_logic` returns true ("No preferred location set - always allow prefetching", `uvm_perf_prefetch.c:326-328`), so the density path runs
(`uvm_perf_prefetch.c:408-431`): a bitmap tree over the 2 MB block is built from the already-resident and faulting pages, and each faulted page expands to the largest subregion whose resident fraction exceeds the threshold.
**At threshold 0 any one faulting page satisfies the test for the whole block** (`counter >= 1`, `0 * subregion_pages = 0`), so a single CPU fault can populate a whole 2 MB block; at 51 the region grows by successive faults.
This is consistent with E9's 1 fault per block at t0 against 6.00 per block at t51; **the 6.00 is a measurement, the mechanism for the exact factor was not derived here.** The separate first-touch rule
(whole block when the block is empty and the destination is the preferred location, `uvm_perf_prefetch.c:404-407`) is not used here because the preferred location is unset. `uvm_perf_prefetch_min_faults` (default 1, `:51`) is not a factor.
The CPU-side exclusion of pages already CPU-mapped (`uvm_perf_prefetch.c:434-440`) does not change this.

## 5b. E9: where in a run do the CPU faults occur?

Phases from each run's own nsys timeline (definitions in `c4_cpu_fault_phases.py`): *alloc* = first CUDA runtime call to the start of the host-fill window; **host fill** = from the end of the last runtime call that ends before the first CPU
fault to the start of the first runtime call after the last CPU fault; *setup*; *kernels* (first kernel start to last kernel end, passes plus the host sync between them); *post* (frees). The trace starts at the first CUDA call, so host
work before it (building the page list) and process exit are outside it. Medians of 3 runs per cell, **under tracing**:

| cell | thr | n | alloc ms | **host fill ms** | setup ms | kernel ms | post ms | CPU faults in alloc / fill / setup / kernel / post |
|---|---|---:|---:|---:|---:|---:|---:|---|
| oversubscribed K=1 | t0 | 3 | 57.7 | **4431.1** | 0.2 | 5634.2 | 125.6 | 0 / 12,288 / 0 / 0 / 0 |
| oversubscribed K=1 | t51 | 3 | 59.7 | **4844.1** | 0.2 | 1166.1 | 214.8 | 0 / 73,728 / 0 / 0 / 0 |
| oversubscribed K=8 | t0 | 3 | 59.5 | **4432.5** | 0.2 | 6337.7 | 125.4 | 0 / 12,288 / 0 / 0 / 0 |
| oversubscribed K=8 | t51 | 3 | 59.2 | **4816.8** | 0.2 | 4037.6 | 215.8 | 0 / 73,728 / 0 / 0 / 0 |
| oversubscribed K=64 | t0 | 3 | 60.3 | **4413.7** | 0.2 | 3429.8 | 128.0 | 0 / 12,288 / 0 / 0 / 0 |
| oversubscribed K=64 | t51 | 3 | 58.9 | **4888.0** | 0.2 | 4872.9 | 161.6 | 0 / 73,728 / 0 / 0 / 0 |
| oversubscribed K=512 | t0 | 3 | 60.9 | **4421.2** | 0.2 | 3560.5 | 126.1 | 0 / 12,288 / 0 / 0 / 0 |
| oversubscribed K=512 | t51 | 3 | 61.2 | **4801.4** | 0.2 | 4840.0 | 161.9 | 0 / 73,728 / 0 / 0 / 0 |
| in-memory K=1 | t0 | 3 | 58.8 | **1482.0** | 0.2 | 166.0 | 61.2 | 0 / 4,096 / 0 / 0 / 0 |
| in-memory K=1 | t51 | 3 | 60.2 | **1627.3** | 0.2 | 38.4 | 87.2 | 0 / 24,576 / 0 / 0 / 0 |
| in-memory K=512 | t0 | 3 | 60.3 | **1475.1** | 0.2 | 234.7 | 59.6 | 0 / 4,096 / 0 / 0 / 0 |
| in-memory K=512 | t51 | 3 | 59.3 | **1528.7** | 0.2 | 388.4 | 65.3 | 0 / 24,576 / 0 / 0 / 0 |
| Stencil-24K | t0 | 3 | 59.8 | **519.8** | 0.2 | 323.3 | 32.8 | 0 / 2,198 / 0 / 0 / 0 |
| Stencil-24K | t51 | 3 | 59.9 | **599.3** | 0.2 | 468.4 | 34.8 | 0 / 13,188 / 0 / 0 / 0 |

**All CPU page faults are in the host-fill window: 0 of the 42 runs has a CPU fault in any other phase.** The host fill is shorter at t0 in all seven workloads:

| cell | fill t0 (ms) | fill t51 (ms) | fill t0 − t51 (ms) | as % of t51 fill | CPU faults t0 / t51 |
|---|---:|---:|---:|---:|---|
| oversubscribed K=1 | 4431 | 4844 | -413 | -8.5% | 12,288 / 73,728 |
| oversubscribed K=8 | 4433 | 4817 | -384 | -8.0% | 12,288 / 73,728 |
| oversubscribed K=64 | 4414 | 4888 | -474 | -9.7% | 12,288 / 73,728 |
| oversubscribed K=512 | 4421 | 4801 | -380 | -7.9% | 12,288 / 73,728 |
| in-memory K=1 | 1482 | 1627 | -145 | -8.9% | 4,096 / 24,576 |
| in-memory K=512 | 1475 | 1529 | -54 | -3.5% | 4,096 / 24,576 |
| Stencil-24K | 520 | 599 | -79 | -13.3% | 2,198 / 13,188 |

- The fill delta is **3.5% to 13% of the fill time** (380-474 ms in the oversubscribed cells, 54-145 ms in memory, 79 ms for Stencil-24K). The fill time itself is large: about 4.4-4.9 s of a 24 GiB run and 1.5-1.6 s of an 8 GiB run.
- **Tracing caveat:** nsys records every CPU fault, so t51 (6x more faults) carries 6x more tracing events; the traced fill delta may therefore overstate the untraced one. The untraced estimate in 5c is the better size guide.
- Stencil-24K, traced: the fill accounts for 79 of the 224 ms (35%) by which t0's traced phases are shorter than t51's (kernels -145 ms); tracing inflates both parts, so this is an indication, not a split of E7's untraced -9.57%.

## 5c. E8: how much of each wall-clock delta lies outside the kernels? (DESCRIPTIVE)

E8 recorded process wall-clock and the three per-pass kernel times (`cudaEvent`, untraced). **Outside the kernels = wall-clock minus the sum of the three pass times.** It includes host start-up, building the page list,
allocation, the host fill, frees and exit, so it is an upper bound on the host-fill effect. Medians of 10 runs per cell; arm minus t51:

| size | K | arm | wall t51 (s) | wall arm (s) | Δ wall (s) | Δ kernels, 3 passes (s) | **Δ outside kernels (s)** | outside-kernels share of Δ wall |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| in | 1 | t0 | 1.579 | 1.641 | +0.062 | +0.124 | **-0.061** | -99% |
| in | 1 | t25 | 1.579 | 1.569 | -0.009 | +0.006 | **-0.015** | (162%; |Δ wall| < 0.05 s, not meaningful) |
| in | 8 | t0 | 1.693 | 1.653 | -0.039 | +0.021 | **-0.060** | (154%; |Δ wall| < 0.05 s, not meaningful) |
| in | 8 | t25 | 1.693 | 1.706 | +0.013 | +0.046 | **-0.033** | (-248%; |Δ wall| < 0.05 s, not meaningful) |
| in | 64 | t0 | 1.847 | 1.668 | -0.179 | -0.143 | **-0.036** | 20% |
| in | 64 | t25 | 1.847 | 1.710 | -0.137 | -0.126 | **-0.011** | 8% |
| in | 512 | t0 | 1.967 | 1.819 | -0.148 | -0.114 | **-0.034** | 23% |
| in | 512 | t25 | 1.967 | 1.844 | -0.123 | -0.101 | **-0.022** | 18% |
| ov | 1 | t0 | 5.054 | 9.347 | +4.294 | +4.484 | **-0.191** | -4% |
| ov | 1 | t25 | 5.054 | 5.149 | +0.095 | +0.156 | **-0.061** | -65% |
| ov | 8 | t0 | 6.777 | 9.565 | +2.789 | +2.959 | **-0.171** | -6% |
| ov | 8 | t25 | 6.777 | 9.942 | +3.165 | +3.267 | **-0.102** | -3% |
| ov | 64 | t0 | 7.669 | 6.927 | -0.741 | -0.618 | **-0.123** | 17% |
| ov | 64 | t25 | 7.669 | 7.135 | -0.533 | -0.487 | **-0.047** | 9% |
| ov | 512 | t0 | 7.934 | 7.326 | -0.607 | -0.469 | **-0.139** | 23% |
| ov | 512 | t25 | 7.934 | 7.492 | -0.442 | -0.369 | **-0.073** | 16% |

- **The outside-kernels time is lower at t0 (and t25) than at t51 in every one of the 16 comparisons**, by 11-62 ms in memory and 47-191 ms oversubscribed (t0 only: 34-61 ms in memory, 123-191 ms oversubscribed). That is 0.7-4.6% of the outside-kernels time at t51.
- **For the dense cells (K >= 64, t0) the outside-kernels part is 17-23% of the wall-clock gain** (t25: 8-18%); the rest is kernel time.
- **For the sparse oversubscribed cells the slowdown is entirely kernel-side** (+4.5 s and +3.0 s of kernel time against +4.3 s and +2.8 s of wall-clock); the host side partly offsets it (-0.19 s and -0.17 s).
- For in-memory K = 1 and 8 the wall-clock deltas are below 0.07 s, so shares of them are not meaningful (marked).
- The traced fill deltas in 5b are 2-3x the untraced outside-kernels deltas here (for example oversubscribed K = 64: -474 ms traced fill vs -123 ms untraced outside-kernels), as the tracing caveat predicts.

## Conclusions and flags

1. **The CPU fault path uses the same prefetcher and the same single threshold** (5a, file:line above), the faults occur in the host fill (5b), and the host fill is shorter at lower thresholds (5b traced; 5c untraced upper bound).
2. **The effect is real but small next to the GPU-side effects:** at most about 0.2 s per run, 0.7-4.6% of the non-kernel time, and 17-23% of the gain on dense access in E8. No E8 verdict (GENERALITY FALSIFIED) depends on it.
3. **`GATE_E8_REPORT.md`'s limitation** ("identical across thresholds") is wrong in the letter: the host write is cheaper at lower thresholds. E6 and E7 time the same host initialisation inside the process wall-clock, so part of their reported gain (an unquantified fraction; indicatively 35% of Stencil-24K's traced phase reduction) arises on the host, not in kernels.
4. **CS2-N10's mechanism sentence is flagged, not edited.** The current text says "CPU page faults also differ by threshold (about 6x more at t51; at t0 equal to the number of 2 MB blocks). Part of the wall-clock effect may therefore arise on the host; see step 5."
   - "see step 5" is a pointer to the C4 brief and should point to this file.
   - The factual part is now supported (5a-5b) and "may arise" can be replaced by a measured bound (5c: 17-23% of E8's dense-access gains lie outside the kernels; the bound for Stencil-24K is not available untraced).
   - The same sentence's "(E9, nsys tracing, n = 3, descriptive)" scope must stay: the host-fill delta is a traced number.
5. Not done: no untraced timing of the host fill alone (that would need a new run); no source derivation of the factor 6.
