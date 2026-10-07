# Gate E8 — Pre-registration: adversarial sparse-access test of the prefetch threshold

**Committed 2026-10-07, before any E8 timed run.** No E8 timing data exists at commit time (the Phase 1 validation
timings were dropped, and the one 24 GiB memory check in `e8/E8_STATUS.md` is not data).

## Question

E7 found that lowering `uvm_perf_prefetch_threshold` helped or did nothing on every workload tried, but those workloads
are dense or streaming. The threshold's purpose is to prefetch the rest of a region once enough of it is touched; the
adversarial case is **sparse** access, where a lower threshold makes the prefetcher migrate whole 2 MB regions of which
the program uses only a few pages. E8 asks whether the E6/E7 tuning result **generalises** to sparse access, in memory
and oversubscribed.

## Platform

RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34-generic, `multi-user.target`. **Stock `nvidia_uvm`** (srcversion
`6284DA42F15EDC3AB92332B`), inserted per run with `uvm_perf_prefetch_enable=1 uvm_perf_prefetch_threshold=<t>`;
srcversion and both parameters are read back (a mismatch is a stop). Family M uses the E3a-2 module
(`33FD42E6E16B0A6658E2BEB`, speculation off).

## Benchmark

`benchmarks/bench_sparse <GiB> <K> <passes> <seed>` (userspace only, no kernel code; committed, validated, reviewed in
`e8/E8_STATUS.md`). One `cudaMallocManaged` array, no `cudaMemAdvise` or `cudaMemPrefetchAsync`; the host writes every page
before the first kernel (all pages start CPU-resident, preferred location unset). The 2 MB blocks are visited in a seeded
random permutation; within each block K distinct seeded-random 4 KB pages are chosen; the page list lives in a
`cudaMalloc` (not managed) array. Each of 3 passes is one kernel launch, one thread per listed page, a read-modify-write of
one 4-byte word; the same list is used in every pass. The checksum is accumulated on the GPU in the last pass and compared
with an independent host reference; a mismatch exits nonzero (a stop). Validation (64 MiB and 1 GiB; correctness only)
passed all of (a)–(e) (`e8/bench_validation.log`).

- In-memory size **8 GiB**. Oversubscribed size **24 GiB** (1.5 × the GPU's 15.92 GiB, rounded up to whole GiB). Passes
  **3**. Seed **202610081** (the same page list in every run of a given size and K).
- Host memory with the oversubscribed array allocated: minimum `MemAvailable` 30.4 GiB (> 12 GiB), so no size reduction.

## Cells and design

Thresholds {0, 25, 51} × K {1, 8, 64, 512} × size {in-memory, oversubscribed} = 24 stock cells; **n = 10 per cell**.
`stock-t51` is the shipped driver. Outcome of record: process wall-clock, `time.monotonic_ns()` around `timeout T setarch -R
bench_sparse …`. **Descriptive only:** per-pass kernel time (`cudaEvent`). Two-sided Mann–Whitney U (exact when no ties),
Holm–Bonferroni, α = 0.05. **delta = (arm − t51) ÷ t51; negative = the lower threshold is faster.** Reported for every test:
MDE at achieved n and at the family α (`mde_family_s`: the helper's sd rescaled by z(1 − 0.05/(2m)) + z(0.80), m = number of
tests; the E0.9b helper's own `mde_bonf_s` is α = 0.05/16 and is not used), Cohen's d, and results with and without
Tukey-flagged outliers. **No run is removed from the primary analysis.**

**Smoke.** One run per cell: the 24 stock cells and the 4 Family M cells (`e8/e8_smoke_order.csv` → `e8/e8_smoke.csv`),
each with a 300 s timeout, with every stop condition applied. **Smoke rows are excluded from analysis.** The per-cell
timeout for the sweep is **ceil(5 × the cell's smoke wall-clock), at most 300 s** (`e8/e8_timeouts.csv`). If a cell's smoke run
itself exceeds 300 s the cell is **dropped and recorded** (`e8/dropped_cells.txt`) and the smoke continues; that is not a
departure. Any other smoke stop ends the session. A sweep run that hits its (smoke-derived) timeout is a stop.

## Run order

`e8/e8_order.csv` from `tests/e8_make_order.py`, seed **202610082**, SHA-256 `fa27582c6523823ad3bb…` (full hash in
`e8/e8_order.sha256`; the runner refuses to run if the file differs).

| idx | family | what |
|---|---|---|
| 1–120 | **IN** | in-memory, all 12 cells, 10 seeded permutations (blocks) of the 12 cells |
| 121–240 | **OV** | oversubscribed, by K group in the order **K = 1, 512, 8, 64**, 30 rows each (10 seeded permutations of the 3 thresholds) |
| 241–260 | **M** | mechanism, descriptive, untested, runs last if time remains (below) |

**Skip rule.** Session cap = Phase 0 + 3.5 h, with 25 min reserved for Phases 6–7. Before each OV K-group the orchestrator
runs it only if `now + 10 × Σ over its cells (smoke wall + 4 s) + reserve ≤ cap`; the first group that does not fit is skipped
**with all later OV groups, whole**, and recorded (`e8/ov_skipped.txt`). Family M runs only if `now + 5 × Σ over its 4 cells
(smoke wall + 5 s) + reserve ≤ cap`, else it is recorded (`e8/m_skipped.txt`). Family IN always runs. None of this is a
departure. The analyzer refuses to run unless the rows present equal the order rows minus dropped cells, skipped OV groups,
and a skipped Family M.

**Family M (mechanism, descriptive, untested).** E3a-2 module, policy 0 (speculation off), in-memory, K ∈ {1, 512} ×
threshold ∈ {0, 51}, **n = 5**; demand faults and D5 from the counters and decomp-ring dumps, as in E6. No test is applied.

## Tests and verdict (mechanical)

Two-sided Mann–Whitney U on wall-clock, **t0 vs t51 and t25 vs t51 for every (size, K)** (up to 16). **ONE Holm family**
across all IN and OV tests.

1. **GENERALITY FALSIFIED** if any cell with **K < 512** shows a **Holm-significant slowdown** (delta > 0) at t0 or t25. The
   cells and the largest slowdown are reported first.
2. **GENERALITY NOT FALSIFIED** otherwise, stated together with the MDEs of the K = 1 cells.
3. **BENCHMARK SUSPECT** if the in-memory **K = 512** cell is **not faster at t0 than at t51** (median t0 ≥ median t51;
   direction only). It is reported **before interpreting anything else**.

## Expectations (reviewer, directional, committed before the run; not part of the verdict)

Operational definitions were fixed in `tests/e8_analyze.py` before the run.

| id | expectation | held iff |
|---|---|---|
| XS1 | in-memory K = 1: t0 significantly slower than t51 (~70%) | that test is Holm-significant with delta > 0 |
| XS2 | oversubscribed K = 1 or 8: t0 significantly slower than t51 (~60%) | at least one of the two t0-vs-t51 tests is Holm-significant with delta > 0 |
| XS3 | K = 512, both sizes: t0 faster than t51 (high) | delta < 0 (direction) in both sizes |
| XS4 | within each size, t0's delta rises monotonically as K falls (~55%) | delta(K=512) < delta(K=64) < delta(K=8) < delta(K=1), in both sizes |
| XS5 | the t25 deltas lie between the t0 and t51 deltas, cell by cell (~60%) | for every cell, delta(t25) lies between delta(t0) and 0 |

An expectation whose cells were dropped or skipped is reported as "not evaluable" (XS4 needs at least 3 K values per size).

## Stop conditions

E7's, verbatim scope, **plus** a nonzero benchmark exit (which includes a checksum mismatch) and any departure:

> Any new `dmesg` line (any source) matching `BUG`, `Oops`, `WARNING`, `general protection`, `NULL pointer`,
> `exited with irqs disabled`, `soft lockup`, `hung_task`, or `RCU stall` (timestamp-based diff); `rmmod` failure or nonzero
> `refcnt`; benchmark timeout; `MemAvailable` below 6 GiB; free disk below 10 GiB; srcversion mismatch; nonzero benchmark exit;
> parameter read-back mismatch (including `uvm_perf_prefetch_threshold`); `specasync_ft_fast_verified ≠ 1` on any fast = 1
> load; `specasync_ft_fast_cas_giveup > 0`; `specasync_spec_region_invalid > 0`; **any departure from this pre-registration**.
>
> On any stop: stop immediately, no retries, leave the machine as it is, record the evidence, commit locally, and write the
> Phase 7 summary.

## Code fixed with this commit

| file | role |
|---|---|
| `benchmarks/bench_sparse.cu`, `tests/e8_validate_bench.py` | the benchmark and its correctness validation (committed earlier, `c7fb05c`) |
| `tests/e8_cells.py`, `tests/e8_make_order.py` | cell table; order (seed 202610082) |
| `tests/e8_runner.py` | a **copy** of `tests/e7_runner.py` (E7's could not be used unchanged); changes: E8 cell table and per-label timeouts, benchmark stdout saved and per-pass times parsed, ring dumps for `dump_rings = 1` rows, dropped-cell filter, paths |
| `tests/e8_orchestrate.py` | smoke and sweep driver; deadlines computed inside the script from `e8/phase0_start.txt`, logged at start, abort if not later than now; pushes after every family/group |
| `tests/e8_analyze.py` | analysis; helpers imported unchanged (via `e7_analyze` → `e09b_analyze`); refusal rule; `--control`; `--selftest` (scratch directory only) |

**Positive control** (`e8/analyzer_positive_control.txt`): reproduces E7 Family A from the committed `e7_runs.csv`:
**−9.57%, p = 1.08e-05. PASS.** The refusal paths (79 of 260 rows; 260 rows with a skipped OV group; 260 rows; 230 rows with the
skip record) were tested on synthetic data in a scratch directory outside `results/`. **PASS.**

## Stated limitations

- `stock-t0/t25` are not the shipped driver. One platform; one synthetic benchmark; K ∈ {1, 8, 64, 512} only; a single page list
  per size (seed 202610081). Process wall-clock includes the host's initial write of the whole array and CUDA start-up, which is
  identical across thresholds but dilutes relative effects, most for K = 1.
- The stock module has no counters, so Families IN and OV report wall-clock (and per-pass kernel time) only; the mechanism is
  Family M, which is descriptive and small (n = 5).
- A dropped or skipped cell removes its tests from the Holm family and from the verdict; the report states which.
