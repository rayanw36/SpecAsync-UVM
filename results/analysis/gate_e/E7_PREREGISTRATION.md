# Gate E7 — Pre-registration: is prefetch-threshold tuning real, and does it generalise?

**Committed 2026-10-07, before any E7 run.** No E7 run data exists at commit time (the 7 one-off execution
checks in `e7/E7_BENCHMARKS.md` are not data).

## Question

E6 found, descriptively, that the stock driver at `uvm_perf_prefetch_threshold` 0 or 10 is faster on Stencil-24K than
at the shipped 51 (−9.17%, −7.72% on medians; **not** a pre-registered E6 comparison). E7 (A) tests that
confirmatorily on the stock module, (B) asks whether lowering the threshold helps, hurts, or does nothing on other
workloads, and (C) measures session-to-session drift of the E3a-2 arms so that E4/E5/E6 can be read together.

## Platform and modules

- RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34-generic, `multi-user.target`.
- **Stock module** (Families A and B): `/lib/modules/7.0.0-34-generic/updates/dkms/nvidia-uvm.ko.zst`,
  srcversion **`6284DA42F15EDC3AB92332B`**. Inserted per run with `uvm_perf_prefetch_enable=1
  uvm_perf_prefetch_threshold=<t>`; srcversion and both parameters are read back (a mismatch is a stop).
- **E3a-2 module** (Family C): `nvidia-uvm-specasync-NEW-e3a2-width-ftfast.ko`, srcversion
  **`33FD42E6E16B0A6658E2BEB`**; parameters as in E6 (threshold 51).
- **Naming.** `stock-t51` is the shipped driver. `stock-t0/t10/t25` are **not** the shipped driver.
  `spec-C0-t51` is the E3a-2 module with speculation off (policy 0), not the stock module.

## Design

n = 10 per cell. Outcome of record: process wall-clock, `time.monotonic_ns()` around `timeout T setarch -R <bench>`.
Statistics: two-sided Mann–Whitney U (exact when no ties), Holm–Bonferroni within each family at α = 0.05.
**delta = (arm − baseline) ÷ baseline**, so a positive delta means the arm is slower. Reported for every comparison:
MDE at achieved n (α = 0.05, power 0.80) and at the family α, Cohen's d, and results with and without Tukey-flagged
outliers. **No run is removed from the primary analysis.**

**MDE at the family α.** The E0.9b helper's `mde_bonf_s` is hard-coded to α = 0.05/16, so E7 does not use it (this
also means the `mde_bonf_s` columns in E6's CSVs refer to 0.05/16 and not to E6's own families; the E6 report does not
quote them). E7 reports `mde_family_s` = the helper's own sd rescaled by z(1 − 0.05/(2m)) + z(0.80), m = number of
tests in the family (a Bonferroni bound on the Holm family).

### Family A — confirmatory (stock module, Stencil-24K, `bench_stencil 24000`, timeout 22 s)

Cells `stock-t0`, `stock-t10`, `stock-t51`. Tests: **stock-t0 vs stock-t51** and **stock-t10 vs stock-t51**
(Holm of 2).

### Family B — generality (stock module)

Arms `stock-t0`, `stock-t25`, `stock-t51` per workload, in this order (command lines, sizes and timeouts in
`e7/E7_BENCHMARKS.md`):

| # | key | command | timeout |
|---|---|---|---|
| 1 | `stencil8k` | `bench_stencil 8000` | 22 s |
| 2 | `sweep4k` | `bench_stencil 4000` | 22 s |
| 3 | `sweep16k` | `bench_stencil 16000` | 22 s |
| 4 | `stream` | `bench_stream 268435456` | 22 s |
| 5 | `sgemm` | `bench_sgemm 24000` | 60 s |
| 6 | `cufft` | `bench_cufft 134217728` | 22 s |
| 7 | `graphbfs` | `bench_graph_bfs 23` | 168 s |
| 8 | `oversub` | `bench_stencil_oversub 48000 1` | 10 s (= 3 × the B9 iters = 1 C0 median, 3.31 s) |

`Sweep-8K` and `Sweep-24K` are duplicates of Stencil-8K and Stencil-24K and are dropped. Oversubscription is last
because a timeout is a stop. Tests: **stock-t0 vs stock-t51** and **stock-t25 vs stock-t51** for each workload;
**ONE Holm family across all of them** (16 tests, or 2 per workload actually run). **Every significant slowdown is
reported as prominently as every speedup.**

### Family C — session drift (E3a-2 module, Stencil-24K)

`spec-C0-t51` (policy 0) and `spec-C7W512-t51` (as in E6: policy 6, depth 1, L 4096, W 512, fast 1, cheap oracle),
10 runs each in **block 1** and 10 each in **block 2**. Tests: block 1 vs block 2 for each arm, delta = (block 2 −
block 1) ÷ block 1 (Holm of 2). Descriptive, untested: these medians against E4, E5 and E6 (from the committed run
CSVs, `e7/session_medians.csv`); and stock `stock-t51` (Family A) against `spec-C0-t51` (blocks pooled), the module
presence cost (compare CS2-14).

## Run order and idx

`e7/e7_order.csv`, from `tests/e7_make_order.py`, seed **202610071**, SHA-256 `85066b078b9324b4fef1…` (full hash in
`e7/e7_order.sha256`; the runner refuses to run if the file differs). Every cell group is run as 10 consecutive
seeded permutations (blocks) of its cells.

| idx | what |
|---|---|
| 1–20 | Family C block 1 |
| 21–50 | Family A |
| 51–290 | Family B, 30 runs per workload in the table's order |
| 291–310 | Family C block 2 |

**Skip rule (Family B only).** Before each Family B workload `w`, the orchestrator runs it only if
`now + 30 × (max smoke wall of w + 4 s) + 120 s + 25 min ≤ Phase 0 + 3 h`. The first workload that fails the test is
skipped, **with all later Family B workloads, whole**, and each is recorded in `e7/family_b_skipped.txt`. That is not
a departure from this pre-registration. Family C block 2 always runs unless a stop has fired. The analyzer refuses
to run unless it has exactly 310 rows, or 310 − 30 × (number of skipped workloads).

**Smoke test.** One run of each never-run cell (the 3 Family A cells and the 24 Family B cells; `e7/e7_smoke_order.csv`,
rows in `e7/e7_smoke.csv`), with every stop condition applied. Smoke rows are **excluded from analysis**; their
walls are used only for the skip-rule estimate. Any stop ends the session.

**Per run.** Reload; srcversion and parameter read-back (the read-back threshold and prefetch-enable are written to
the CSV); timestamp dmesg diff; `timeout T setarch -R <bench>`; a 1 s drain; for E3a-2 rows the counters and the
`ft_fast_verified`, `ft_fast_cas_giveup` and `spec_region_invalid` checks; the stop checks; one row in
`e7/e7_runs.csv`. The CSV is committed every 10 rows. Wall-clock goes to the CSV only.

## Expectations (reviewer, directional, committed before the run; not part of any verdict)

Operational definitions were fixed in `tests/e7_analyze.py` before the run.

| id | expectation | operational definition (held iff) |
|---|---|---|
| XA | C0-t0 faster than C0-t51 on Stencil-24K, significant (high confidence) | `stock-t0` vs `stock-t51` is Holm-significant (Family A) **and** delta < 0 |
| XB1 | On Stencil-8K, the sweep sizes, STREAM and SGEMM, no workload is significantly slower at t0 than at t51 (moderate) | none of `stencil8k, sweep4k, sweep16k, stream, sgemm` has `stock-t0` vs `stock-t51` Holm-significant with delta > 0 |
| XB2 | GraphBFS-23: no significant difference at either threshold (high) | neither GraphBFS test is Holm-significant |
| XB3 | Oversubscribed Stencil: C0-t0 significantly **slower** than C0-t51 (low-moderate, about 55%) | `stock-t0` vs `stock-t51` on `oversub` is Holm-significant with delta > 0 |
| XB4 | cuFFT: C0-t0 not significantly faster than C0-t51 (low, about 50%) | not (`stock-t0` vs `stock-t51` on `cufft` Holm-significant with delta < 0) |
| XC | C7W512-t51's block-to-block median difference is larger than C0-t51's (moderate) | \|median block 2 − median block 1\| ÷ median block 1 is larger for `spec-C7W512-t51` than for `spec-C0-t51` |

An expectation about a skipped workload is reported as "not evaluable". XB1 is evaluated on the workloads actually run.
There is no verdict and no falsification trigger beyond these; the headline is Family A's result, with Families B and C
reported as found.

## Stop conditions

E6's, verbatim scope:

> Any new `dmesg` line (any source) matching `BUG`, `Oops`, `WARNING`, `general protection`, `NULL pointer`,
> `exited with irqs disabled`, `soft lockup`, `hung_task`, or `RCU stall` (timestamp-based diff); `rmmod` failure or
> nonzero `refcnt`; benchmark timeout; `MemAvailable` below 6 GiB; free disk below 10 GiB; srcversion mismatch; nonzero
> benchmark exit; parameter read-back mismatch (including `uvm_perf_prefetch_threshold`); `specasync_ft_fast_verified
> ≠ 1` on any fast = 1 load; `specasync_ft_fast_cas_giveup > 0`; `specasync_spec_region_invalid > 0`; **any departure
> from this pre-registration**.
>
> On any stop: stop immediately, no retries, leave the machine as it is, record the evidence, commit locally, and write
> the Phase 7 summary.

## Code fixed with this commit

| file | role |
|---|---|
| `tests/e7_make_order.py` | order (seed 202610071) |
| `tests/e7_runner.py` | E6's runner stack imported unchanged (`e5_runner` → `e4_runner` → `e3b_runner`) plus a **stock** module mode; commits carry this session's attribution trailer |
| `tests/e7_orchestrate.py` | smoke and sweep driver; every deadline computed inside the script from `e7/phase0_start.txt`, logged at start, abort if not later than now |
| `tests/e7_analyze.py` | analysis; E0.9b helpers imported unchanged; refusal rule; `--control`; `--selftest` (scratch directory only) |

**Positive control** (`e7/analyzer_positive_control.txt`): `e7_analyze.py --control` applies E7's comparison to E6's
committed `e6_runs.csv`, C7W512-t51 (arm) vs C0-t0 (baseline), and reproduces **+6.39%, p = 1.08e-05, D(51) = +0.4017**.
**PASS.** The refusal paths (79 of 310 rows, 310 rows with a skip record, 280 rows with and without one) were tested on
synthetic data written to a scratch directory outside `results/`. **PASS.**

## Stated limitations

- `stock-t0/t10/t25` are not the shipped driver. Single platform. Two Stencil sizes, STREAM, SGEMM, cuFFT, GraphBFS and
  one oversubscribed configuration; nothing here is a practical predictor.
- STREAM (268,435,456) and cuFFT (134,217,728) sizes are choices, not recovered sizes (`e7/E7_BENCHMARKS.md`).
- The stock module has no specasync counters, so Families A and B report wall-clock only (no demand-fault or D5 data).
- The Stencil first-touch table differs between gates (same pages, different order; `e7/E7_PARAM_CHECK.md` §3). Family C
  uses one table within the session and does not isolate that effect.
- Every Family B workload is compared at only two lowered thresholds (0 and 25), with n = 10.
