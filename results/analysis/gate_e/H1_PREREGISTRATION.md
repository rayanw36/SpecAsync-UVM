# Gate H1 - Pre-registration: does the prefetch-threshold trade-off hold for HMM-managed (malloc'd) memory?

**Committed 2026-11-05 21:46, before any H1 timed run.** No H1 timing data exists at commit time. The only runs are the correctness validation in `h1/h1_validation.log` (timings dropped).

## Question
Does the threshold trade-off hold for HMM-managed (malloc'd) memory, where the CPU-side population effect of CS2-N10 does not exist? (Source check: `h0/H0_REPORT.md` verdict A, `h0/H0_MAPPING.md` verdict MAPS: the same density prefetcher and threshold act on HMM blocks, and prefetched pages are mapped in the same service step.)

## Platform
RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34-generic, `multi-user.target`. **Stock `nvidia_uvm`** (srcversion `6284DA42F15EDC3AB92332B`), inserted per run with `uvm_perf_prefetch_enable=1 uvm_perf_prefetch_threshold=<t>`; srcversion and both parameters are read back (a mismatch is a stop). `nvidia-smi -q`: Addressing Mode HMM. **THP recorded and fixed for the whole gate:** `/sys/kernel/mm/transparent_hugepage/enabled` = `always [madvise] never`, `defrag` = `always defer defer+madvise [madvise] never`; the benchmarks also call `madvise(MADV_NOHUGEPAGE)` on the malloc'd array. `/proc/sys/kernel/numa_balancing` = 0. No specasync module, no new kernel code.

## Benchmarks
`benchmarks/bench_sparse.cu` and `bench_stencil.cu` gained an optional `--alloc {managed,malloc}` flag (default managed). Malloc mode uses `aligned_alloc` with 2 MiB alignment (size rounded up to 2 MiB), `madvise(MADV_NOHUGEPAGE)`, the same host initialisation, the same kernels and the same checksum. **Managed mode output is unchanged** (8 bench_sparse cells and bench_stencil N = 2048 compared with a binary built from the committed source: identical after masking timing and pointers). `bench_stencil` gained a validation-only `STENCIL_CHECKSUM=1` mode (unset = no extra work). H1 uses binaries `benchmarks/bench_sparse_h1` and `bench_stencil_h1` (sha256 in `h1/h1_binaries.sha256`); the E7/E8 binaries are untouched. Validation (`tests/h1_validate.py`, `h1/h1_validation.log`, OVERALL PASS): E8 checks (a)-(e) in malloc mode at 64 MiB and 1 GiB; stencil checksum malloc = managed = CPU reference at N = 2048 and 4096; **GPU residency**: `nvidia-smi` memory.used rose by 2288 MiB during a 2 GiB malloc-mode run. **The stock module exposes no UVM fault counter** (`/proc/driver/nvidia-uvm` has no per-GPU statistics), so GPU faults in malloc mode are evidenced by that residency rise and, in the sweep, by the wall-clock difference between thresholds.

## Cells
All cells use **`--alloc malloc`**, **n = 10 per cell**; outcome of record: process wall-clock (`time.monotonic_ns()` around `timeout T setarch -R <bench> --alloc malloc`). Thresholds {0, 51} x
- Stencil-24K (`bench_stencil 24000`), in memory;
- bench_sparse 8 GiB, K in {1, 512}, in memory;
- bench_sparse 24 GiB, K in {1, 512}, 1.5x oversubscribed;
bench_sparse with 3 passes and seed 202610081 (the E8 page list). 10 cells, **100 runs**.

## Order and smoke
`h1/h1_order.csv` from `tests/h1_make_order.py`, seed **202611051**: idx 1-60 in-memory cells (6 cells, 10 seeded permutation blocks), then idx 61-100 oversubscribed cells (4 cells, 10 blocks). SHA-256 `c9270e3979e632be3f0e...` (full hash in `h1/h1_order.sha256`; the runner refuses to run if the file differs). **Smoke:** one run per cell (`h1_smoke_order.csv`, 10 rows, excluded from analysis), timeout 300 s with every stop condition applied; the per-cell sweep timeout is **ceil(5 x the cell's smoke wall-clock), at most 300 s** (`h1/h1_timeouts.csv`). A cell whose smoke run exceeds 300 s is **dropped and recorded** (`h1/dropped_cells.txt`; not a departure). Any other smoke stop ends the session.
**Skip rule.** Session cap = the C9 session start (`h1/phase0_start.txt`) + 4 h, with 25 min reserved for the summary. The in-memory cells always run. Before the oversubscribed cells: they run only if now + 10 x sum over their cells of (smoke wall + 4 s) <= cap - reserve; otherwise they are **skipped whole** and recorded (`h1/ov_skipped.txt`). Not a departure. The analyzer refuses to run unless the rows present equal the order rows minus dropped cells and the skipped oversubscribed cells.

## Tests and verdict (mechanical)
Two-sided Mann-Whitney U (exact when no ties), **t0 vs t51 per workload, ONE Holm family of 5**, alpha 0.05; delta = (t0 - t51) / t51 (negative = t0 faster). Reported for every test: MDE at the family alpha (`mde_family_s` = (z(1 - 0.05/(2m)) + z(0.80)) x sd, m = tests actually present; the E0.9b helper's `mde_bonf_s` is not used), Cohen's d, results with and without Tukey-flagged outliers. **No run is removed from the primary analysis.** The 5 tests: Stencil-24K, sparse in-memory K = 512, sparse in-memory K = 1, sparse oversubscribed K = 1, sparse oversubscribed K = 512.
- **REPLICATED (both directions)** if Stencil-24K **or** sparse in-memory K = 512 is Holm-significantly **faster** at t0, **and** sparse oversubscribed K = 1 is Holm-significantly **slower** at t0.
- **DENSE ONLY / SPARSE ONLY** if just one of the two conditions holds; **NOT REPLICATED** if neither.

**Descriptive, no test:** each malloc-mode delta is shown beside the managed-mode delta from E7 (Stencil-24K) or E8 (sparse cells) for the same workload and threshold; they are different sessions and are **never pooled**. For Stencil-24K the comparison is labelled "GPU-side effect without CPU population (HMM) vs managed total"; **no subtraction is reported as a measured host share.**

## Expectations (reviewer, directional, committed before the run; not part of the verdict)
Operational definitions are fixed in `tests/h1_analyze.py` before the run.
| id | expectation | held iff |
|---|---|---|
| Y1 | Stencil-24K: t0 faster than t51, Holm-significant (moderate-high) | that test is Holm-significant with delta < 0 |
| Y2 | Stencil-24K: the malloc-mode gain is smaller than E7's managed -9.57% (moderate; the CPU-side part is absent) | delta_pct(H1) > delta_pct(E7 Family A, stock-t0) |
| Y3 | sparse oversubscribed K = 1: t0 slower than t51, Holm-significant (moderate) | that test is Holm-significant with delta > 0 |
| Y4 | sparse in-memory K = 512: t0 faster than t51 (moderate) | delta < 0 (direction only) |
An expectation about a dropped or skipped cell is reported as "not evaluable".

## Stop conditions
E8's, verbatim scope (E7's text plus a nonzero benchmark exit, which includes a checksum mismatch), **plus any departure from this pre-registration**:
> Any new `dmesg` line (any source) matching `BUG`, `Oops`, `WARNING`, `general protection`, `NULL pointer`, `exited with irqs disabled`, `soft lockup`, `hung_task`, or `RCU stall` (timestamp-based diff); `rmmod` failure or nonzero `refcnt`; benchmark timeout; `MemAvailable` below 6 GiB; free disk below 10 GiB; srcversion mismatch; nonzero benchmark exit; parameter read-back mismatch (including `uvm_perf_prefetch_threshold`); **any departure from this pre-registration**.
>
> On any stop: stop immediately, no retries, leave the machine as it is, commit, write the summary and end.
The H1 runner also stops if the benchmark's output is incomplete (sparse: 3 pass lines and CHECKSUM OK; stencil: the [RESULT] Time line).

## Code fixed with this commit
| file | role |
|---|---|
| `benchmarks/bench_sparse.cu`, `bench_stencil.cu`, `tests/h1_validate.py` | the `--alloc` flag, its correctness validation |
| `tests/h1_cells.py`, `tests/h1_make_order.py` | cell table; order (seed 202611051) |
| `tests/h1_runner.py` | a **copy** of `tests/e8_runner.py`; changes only: the cell table, the `--alloc malloc` command, a per-workload output check, paths, stock module only |
| `tests/h1_orchestrate.py` | smoke and sweep driver; deadlines computed inside the script from `h1/phase0_start.txt`; pushes after each stage |
| `tests/h1_analyze.py` | analysis; helpers imported unchanged (`e7_analyze` -> `e09b_analyze`); refusal rule; `--control` |

**Positive control** (`h1_analyze.py --control`): reproduces E8's oversubscribed K = 1 t0 vs t51 from the committed `e8_runs.csv`: **+84.96%, p = 1.08e-05: PASS**; on a copy with the t0 wall-clock shifted by 10% it **FAILS** (+103.46%), so it can fail.

## Stated limitations
- One platform, one synthetic sparse benchmark and one stencil size; K in {1, 512} only; one oversubscription ratio (1.5x). HMM GPU chunks are PAGE_SIZE and eviction runs through `migrate_device_pages`, so absolute times are not comparable with the managed runs; only the within-mode threshold contrast is.
- The malloc-mode and managed-mode runs are from different sessions; the descriptive comparison is not a test.
- Pages that `migrate_vma` cannot move (file-backed, swapped, pinned) would be dropped from the service set (`h0/H0_MAPPING.md` section 3); none is expected for host-initialised anonymous memory, and the benchmark has no counter for it.
- The stock module has no counters: only wall-clock is analysed.
