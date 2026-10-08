# E7-T4 pre-registration (Tesla T4 replication of the E7 threshold test, stock driver)

Committed and pushed before any timed run. Gate T4-R1. T4 data are analysed separately and **never pooled with 5070 Ti data**.

## Platform (read on this machine)

Tesla T4 (sm_75, 15360 MiB), AWS g4dn.xlarge us-west-2, 4 vCPU, 15 GiB RAM, Ubuntu 24.04.4, kernel 6.17.0-1017-aws,
driver 595.91.07 open (apt debs, SHA256-verified, T4_STATUS.md), CUDA nvcc 13.0.88, gcc 13.3.0.
Stock `nvidia_uvm` srcversion **6284DA42F15EDC3AB92332B** (the value hard-coded in `tests/e7_runner.py`; it equals the 5070 Ti's).
Stock module only; threshold set at insmod and read back (`uvm_perf_prefetch_threshold`), `stock-t51` = the shipped driver (default 51).

## Design

n = 10 per cell. Two-sided Mann-Whitney U on process wall-clock (`timeout T setarch -R <bench>`). Holm within each family,
alpha 0.05. Report the MDE (at achieved n at the single-test alpha, and at the family alpha), Cohen's d, and results with and
without outliers (Tukey). Delta = (arm - t51) / t51.

* **Family A** - Stencil-24K (`bench_stencil 24000`), arms stock-t0 / stock-t10 / stock-t51; tests t0 and t10 vs t51 (Holm of 2).
* **Family B** - arms stock-t0 / stock-t25 / stock-t51; workloads in this order: Stencil-8K (`bench_stencil 8000`), Sweep-4K
  (`bench_stencil 4000`), Sweep-16K (`bench_stencil 16000`), STREAM (`bench_stream 268435456`), SGEMM (`bench_sgemm 24000`),
  cuFFT (`bench_cufft 134217728`), GraphBFS-23 (`graph_bfs/bench_graph_bfs 23`), oversubscribed Stencil last
  (`stencil_oversub/bench_stencil_oversub 48000 1`). Tests t0 and t25 vs t51 for each workload; **ONE Holm family** (16 tests).
  Sizes/commands exactly as `results/analysis/gate_e/e7/E7_BENCHMARKS.md`.
* **Order**: `e7t4_make_order.py`, seed **202610072**; each workload = 10 shuffled blocks of its 3 cells; Family A idx 1-30, Family B idx 31-270
  (270 rows). `e7t4_order.csv` sha256 `be1c14bae6a20abb0b667c81e4ce43db73a3b2c9364274c40a70b5bcec32c263` (e7t4_order.sha256; the runner refuses a non-matching file).
* **Skip rule** (workload boundary, whole workloads only, recorded in `family_b_skipped.txt`): before each Family B workload w, run it only if
  now + 30 x (max smoke wall of w + 4 s) <= cap - 25 min reserve, where cap = T0 + 5 h = 21:38:43 UTC (T0 = 16:38:43 UTC, `phase0_start.txt`).
  The first workload that does not fit is skipped, with every later one. Nothing else is skipped.

## Oversubscribed Stencil sizing (checked here)

Working set = 2 x N^2 x 4 B (`bench_stencil_oversub.cu`: two cudaMallocManaged grids). N = 48000: 18.432 GB = **17.166 GiB**.
5070 Ti VRAM 15.92 GiB (PLATFORM_5070TI.md): ratio **1.078**. T4 VRAM 15360 MiB = 15.000 GiB: ratio **1.144**. Difference 6.1% (limit 10%),
so **N = 48000 is kept**; both ratios recorded here.

## Smoke and timeouts

One smoke run per never-run cell (3 Family A + 24 Family B = 27, `e7t4_smoke_order.csv`, sha256 `ba63d09f13cad92dd3b4539399a251ea5e36271d09a5f2ba6f5f66f15329ce61`), every stop condition applied, rows
excluded from analysis. Smoke itself uses provisional timeouts (300 s; GraphBFS 600 s): a smoke timeout is a hang and is a stop. After smoke, **sweep timeout
per workload = 3 x the median of that workload's 3 smoke walls**, rounded up to whole seconds (`e7t4_timeouts.json`, written by the orchestrator). A timeout is a stop.

## Code (committed with this file)

| file | role |
|---|---|
| `tests/e7_runner.py` (+ e5/e4/e3b/e09b runners) | **unchanged** except `tests/e09b_runner.py:35` `REPO` env override (T2 commit). Stock mode: insmods `/lib/modules/$(uname -r)/updates/dkms/nvidia-uvm.ko.zst`, verifies srcversion, reads back both parameters. |
| `e7t4_runner.py` | imports `e7_runner` unchanged; sets the per-workload timeouts above; adds the stop "active xrdp / desktop session" at every `check_after` |
| `e7t4_orchestrate.py` | smoke and sweep driver; deadlines computed inside the script; skip rule; pushes after each step |
| `e7t4_make_order.py`, `e7t4_analyze.py` | order; analysis (E7's statistical helpers imported unchanged) |

**Positive control** (`e7t4_positive_control.txt`): the analyzer applied to the committed 5070 Ti `e7_runs.csv` Family A reproduces **-9.57%, p = 1.08e-05: PASS**
(otherwise: stop). The refusal rule (row count) and the figure/report path were exercised on synthetic data in a scratch directory.
Known cosmetic carry-over: the unchanged runner's commit messages carry the E7 session's `Claude-Session` URL trailer.

## Stop conditions

E7's, verbatim:

> Any new `dmesg` line (any source) matching `BUG`, `Oops`, `WARNING`, `general protection`, `NULL pointer`,
> `exited with irqs disabled`, `soft lockup`, `hung_task`, or `RCU stall` (timestamp-based diff); `rmmod` failure or
> nonzero `refcnt`; benchmark timeout; `MemAvailable` below 6 GiB; free disk below 10 GiB; srcversion mismatch; nonzero
> benchmark exit; parameter read-back mismatch (including `uvm_perf_prefetch_threshold`); ... **any departure
> from this pre-registration**.

(The specasync-module clauses of E7's text do not apply: no E3a-2 module is loaded.) Plus: **any departure from this pre-registration**, plus **an active xrdp or
desktop session during a timed run**. On any stop: stop immediately, no retries, leave the machine as it is, commit, write the summary.

## Verdict (mechanical)

* **REPLICATED** if Family A's stock-t0 vs stock-t51 is a Holm-significant speedup (delta < 0).
* **FALSIFICATION TRIGGER** for the dense-workload generality claim: any Holm-significant slowdown (delta > 0) at t0 or t25 in Family B. If it fires, it is reported first.

## Expectations (reviewer, directional, committed before the run)

| id | expectation | confidence | held iff |
|---|---|---|---|
| XA | stock-t0 faster than stock-t51 on Stencil-24K, Holm-significant | high | Family A t0 vs t51 Holm-significant and delta < 0 |
| XB | Sweep-16K, STREAM, SGEMM and oversubscribed Stencil are faster at t0 than at t51, direction only | moderate | median(t0) < median(t51) for all four (skipped workloads: not evaluable) |
| XC | no workload is significantly slower at t0 | moderate | no Holm-significant stock-t0 slowdown in Family B |
