# Gate H2 - Pre-registration: the sparse-access cost of threshold 0 on HMM vs managed memory (in memory only)

**Committed 2026-11-06 16:05, before any H2 timed run.** No H2 timing or residency data exists at commit time.

## Question and hypothesis
H1 (Amendment 1) found, on HMM (`malloc`) memory in memory, sparse K = 1 at threshold 0 **+200.52%** slower than at 51 (managed memory, E8: +3.95%), with t0 times almost equal for K = 1 and K = 512 (6.50 s vs 6.70 s). Hypothesis: at t0 the prefetcher makes whole regions resident on the first fault, so a sparse pass migrates nearly the whole array whatever K is; on managed memory this is cheap (2 MB chunks), on HMM it is expensive because each prefetched page is a separate 4 KB device-private page moved through `migrate_vma` (`h0/H0_MAPPING.md` section 2). Two tests: the timing pattern across K, and GPU memory residency directly. Both allocators are run in the same session.

**Falsification note (verbatim):** "H2 tests a hypothesis formed after seeing H1's K = 1 result. Its K = 1 malloc timing cells repeat a condition already observed; only the new K values, the residency measures and the allocator contrast are tests of a prediction made before the data."

## Platform
RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34-generic, `multi-user.target`; **stock `nvidia_uvm` 6284DA42F15EDC3AB92332B** inserted per run with `uvm_perf_prefetch_enable=1 uvm_perf_prefetch_threshold=<t>` (srcversion and both parameters read back); HMM addressing mode. THP `enabled` = `always [madvise] never`, `defrag` = `always defer defer+madvise [madvise] never`, `numa_balancing` = 0 (the values recorded in C9; re-read before the run and fixed). Binary `benchmarks/bench_sparse_h1` (sha256 in `h1/h1_binaries.sha256`, unchanged since H1; managed mode is byte-identical to the E8 binary's output, H1 validation). No specasync module, no new kernel code. **No oversubscribed cell with either allocator.**

## Cells
`bench_sparse` 8 GiB, 3 passes, seed 202610081 (the E8 page list), prefetcher on; K in {1, 8, 64, 512} (E8's in-memory K set, `e8_cells.KS`) x allocator {managed, malloc} x threshold {0, 51} = **16 cells**, **n = 10**, 160 timed runs. Outcome of record: process wall-clock (`time.monotonic_ns()` around `timeout T setarch -R bench_sparse_h1 ... --alloc <a>`). Interleaved by a seeded order (`tests/h2_make_order.py`, seed 202611061: 10 blocks, each a permutation of the 16 cells). **Smoke:** one run per cell (16 rows, excluded from analysis), timeout 300 s; per-cell sweep timeout = ceil(5 x smoke wall), at most 300 s; a cell whose smoke exceeds 300 s is dropped and recorded (not a departure).

## Timing family
One Holm family of **8**: t0 vs t51 for each (allocator, K), two-sided Mann-Whitney U (exact when no ties), alpha 0.05, delta = (t0 - t51) / t51. Reported: median, delta, p, Holm-adjusted p, MDE at the family alpha (`mde_family`, m = 8), Cohen's d, results with and without Tukey-flagged outliers. No run is removed from the primary analysis.

## Residency pass (mechanism; separate from the timed sweep)
After the timed sweep, for each of the 16 cells **n = 3 extra runs** (48 runs; own seeded order, seed 202611062, 3 blocks) with a GPU-memory sampler: `nvidia-smi --query-gpu=timestamp,memory.used --format=csv,noheader,nounits -lms 50` (the `timestamp` column is added to the specified query so that the 1 s before launch can be identified), started before the benchmark, stopped 0.3 s after it. **baseline** = the median of the samples taken in the 1 s before launch; **residency** = the peak sample minus baseline. These runs are not timed outcomes and never enter the timing family. C9's validation showed that `memory.used` rises in a malloc-mode run (HMM device-private pages are visible). A sampler that produces no samples (or none in the pre-launch second) is a stop. 8 GiB = 8192 MiB.

## Numbered expectations (scored HELD / FAILED / UNSCORED)
- **Z1 (t0 flat in K, HMM):** across the K set, the largest t0 median on malloc is at most 1.10 x the smallest.
- **Z2 (t51 rises with K, HMM):** on malloc at t51 the medians are strictly increasing in K.
- **Z3 (direction ordering, HMM):** on malloc the delta (t0 vs t51) is strictly decreasing in K; the K = 1 delta is Holm-significant and positive, the K = 512 delta Holm-significant and negative.
- **Z4 (t0 migrates the whole array, HMM):** median residency at malloc, K = 1, t0 is at least 0.8 x 8 GiB.
- **Z5 (t51 does not, HMM):** median residency at malloc, K = 1, t51 is at most 0.1 x 8 GiB.
- **Z6 (same volume on managed memory):** median residency at managed, K = 1, t0 is at least 0.8 x 8 GiB.
- **Z7 (cost differs by allocator):** the K = 1 t0-vs-t51 delta is larger on malloc than on managed. Report the difference of the two percentage deltas with a 95% bootstrap CI (10,000 resamples within cells, seed 20261106, percentile interval of the difference of median ratios). Z7 holds iff the CI's lower bound is above 0.

## Verdict rule (mechanical)
- **MECHANISM SUPPORTED** if Z1, Z4, Z6 and Z7 all hold.
- **MECHANISM REFUTED** if either the malloc K = 1 t0 residency is at most 0.5 x 8 GiB, or the largest malloc t0 median across K is more than 1.25 x the smallest.
- **PARTIAL** otherwise. Z2, Z3 and Z5 are reported but do not enter the verdict.

## Stop conditions
H1 Amendment 1's: new `dmesg` lines matching `BUG`, `Oops`, `exited with irqs disabled`, `soft lockup`, `hung_task` or `RCU stall`; host available memory below 4 GiB; a nonzero benchmark exit (including a checksum failure); a timeout; a srcversion or parameter read-back mismatch; any departure from this pre-registration. Plus the sampler rule above. On any stop: write `h2/STOP`, restore threshold 51, no retry.

## Code fixed with this commit
| file | role |
|---|---|
| `tests/h2_cells.py`, `tests/h2_make_order.py` | cell table; the three orders |
| `tests/h2_runner.py` | a copy of `h1_runner.py` (cell table, paths) |
| `tests/h2_orchestrate.py`, `h2/h2_chain.sh`, `h2/h2_res_chain.sh` | timed smoke + sweep; residency chain |
| `tests/h2_residency.py` | residency pass (sampler, baseline, peak) |
| `tests/h2_analyze.py` | analysis, Z1-Z7, verdict, `--control` |
**Order hashes** (`h2/h2_order.sha256`, all three): timed `0064b2f50371d8b7...`, smoke `783430b965c76472...`, residency `5f50b02b9692b3a2...`; each order accepted by a dry run (nothing executed). **Analyzer control** (`h2/h2_control.txt`): the synthetic predicted pattern gives MECHANISM SUPPORTED; the perturbed copy (t0 medians scaled by K, Z1 fails) gives MECHANISM REFUTED. PASS.

## Stated limitations
One platform; one benchmark and page list; four K values; in memory only (HMM oversubscription is not run: stock-driver defect, `GATE_H1_REPORT.md`). `memory.used` residency is a device-level measure (baseline subtraction assumes nothing else changes GPU memory during the run; the host is headless). The malloc and managed runs share the session but not a block structure beyond interleaving. HMM GPU chunks are PAGE_SIZE and eviction runs through `migrate_device_pages`, so absolute times are not comparable across allocators; only within-allocator contrasts and the difference of deltas are.
