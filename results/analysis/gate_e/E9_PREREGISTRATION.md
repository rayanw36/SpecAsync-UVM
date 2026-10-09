# Gate E9 — Pre-registration: unified-memory tracing of the threshold effect

**Committed 2026-10-09, before any traced E9 run.** The only traced runs that exist at commit time are the two 1 GiB probes (4a and its regenerated control), which are not data.

## Question

E6–E8 measured wall-clock only (the stock module has no counters) and **inferred** a mechanism: a lower `uvm_perf_prefetch_threshold` migrates whole
regions for few touched pages; on an oversubscribed array the data does not stay resident, so every pass re-pays migration. E9 measures the migrated
bytes and fault counts directly with `nsys`, to test that reading and to explain the unexplained E8 observation (oversubscribed K = 1 at the shipped
threshold 51 still costs about 0.3 s in every pass).

## Platform

RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34-generic, `multi-user.target`, **stock `nvidia_uvm`** (srcversion `6284DA42F15EDC3AB92332B`), inserted per run
with `uvm_perf_prefetch_enable=1 uvm_perf_prefetch_threshold=<t>`; srcversion and both parameters are read back (a mismatch is a stop).
nsys 2025.3.2 (`/usr/local/bin/nsys`, CUDA 13.0 toolkit).

## Probe result (4a; PASS)

`nsys profile --trace=cuda --cuda-um-gpu-page-faults=true --cuda-um-cpu-page-faults=true` on one 1 GiB `bench_sparse 1 8 3 202610081` run records unified-memory events.
- **Report used:** `nsys stats --report um_total_sum` (HtoD MB, DtoH MB, CPU page faults, GPU page faults). The brief's `cuda_um_*` names do not exist in this version; the available UM reports are `um_total_sum`, `um_sum` (per address) and `um_cpu_page_faults_sum`.
- **Also used (SQLite exported by `nsys stats`):** `CUPTI_ACTIVITY_KIND_MEMCPY` (copyKind 11/12/13 = UVM HtoD/DtoH/DtoD; `migrationCause` 2 = page fault, 3 = speculative prefetch, 4 = eviction), `CUDA_UM_GPU_PAGE_FAULT_EVENTS`, `CUPTI_ACTIVITY_KIND_KERNEL` (per-pass windows).
- **Not available in this nsys:** thrashing, throttling and remote-map events (no table, no report).
- **Extraction control** (`e9/extraction_control.txt`, PASS): the SQLite totals equal nsys's own report (HtoD MB, DtoH MB, GPU faults), the causes sum to the total, and the per-pass counts sum to the total.

## Outcome and design

**Outcome (per run):** HtoD bytes, DtoH bytes (total, by migration cause, and per pass for `bench_sparse`), GPU page-fault count (`um_total_sum`; the sum of
`numberOfPageFaults` equals it), CPU page-fault count. **Wall-clock is NOT an outcome:** tracing perturbs timing; it is recorded (`wall_s_NOT_COMPARED`) and never compared.

**Cells** (stock module; threshold set at insmod and read back), **n = 3 per cell, 42 runs:**

| workload | command | thresholds |
|---|---|---|
| `bench_sparse` oversubscribed | `bench_sparse 24 K 3 202610081`, K ∈ {1, 8, 64, 512} | 0, 51 (8 cells) |
| `bench_sparse` in-memory | `bench_sparse 8 K 3 202610081`, K ∈ {1, 512} | 0, 51 (4 cells) |
| Stencil-24K | `bench_stencil 24000` | 0, 51 (2 cells) |

**Run order:** `e9/e9_order.csv` from `tests/e9_make_order.py`, seed **202610091**, 3 blocks, each a seeded permutation of the 14 cells (idx 1–14, 15–28, 29–42);
SHA-256 `52d3056acb5f1cd59359…` (full hash in `e9/e9_order.sha256`; the runner refuses a different file). **Smoke:** one run per cell (14 rows, `e9/e9_smoke.csv`), 300 s timeout, any stop ends the session; smoke rows are excluded from analysis.
**Per-cell timeout** = 3 × E8's timeout for the cell (tracing overhead), fixed in `e9/e9_timeouts.csv` before any run (Stencil-24K: 3 × 22 s = 66 s, the cell was not in E8).

**Per run:** reload; srcversion and parameter read-back; timestamp dmesg diff; `timeout T nsys profile … setarch -R <bench>` (the traced command, including nsys's finalisation);
a 1 s drain; extraction (`tests/e9_extract.py`) outside the timed region; stop checks; one row in `e9/e9_runs.csv`. The CSV is committed and pushed after every block.
Reports (`.nsys-rep`) are kept under the gitignored `results/phaseB1/gate_e9/`; the SQLite exports are deleted after extraction.

**Skip rule.** Session cap = 3.5 h of working time (anchor in `e9/cap_anchor.txt`, see below) with 25 min reserved. Before each block the orchestrator runs it only if `now + Σ(smoke wall + 8 s over the 14 smoke rows) + reserve ≤ cap`;
the first block that does not fit is skipped with all later blocks, whole, and recorded (`e9/blocks_skipped.txt`). That is not a departure.

**Analysis: descriptive only** (per-cell medians and ranges; no tests, n = 3). The analyzer (`tests/e9_analyze.py`) refuses to run unless the rows equal the order minus skipped blocks.

## Expectations (reviewer, directional, committed before the run; not part of any verdict)

Operational definitions were fixed in `tests/e9_analyze.py` before the run.

| id | expectation | held iff (medians) |
|---|---|---|
| Y1 | oversubscribed K = 1: HtoD bytes at t0 at least 10× those at t51 | HtoD(t0) ≥ 10 × HtoD(t51) |
| Y2 | oversubscribed K = 1 and K = 8 at t0: DtoH (eviction) bytes large, at least 1 GiB per pass, and much smaller at t51 | for **both** K: t0 DtoH ≥ 1 GiB in **each** of the 3 passes, and t51 total DtoH ≤ 0.25 × t0 total ("much smaller" = 4× smaller) |
| Y3 | Stencil-24K: HtoD at t0 and t51 within 5%; GPU fault count at t0 below t51 | \|HtoD(t0) − HtoD(t51)\| ÷ HtoD(t51) ≤ 5% **and** GPU page faults(t0) < GPU page faults(t51) |
| Y4 | oversubscribed K = 1 at t51: the repeat-pass cost comes with DtoH eviction or remote-map/thrashing events, not with zero migration | DtoH bytes > 0 in **both** repeat passes (2 and 3). Remote-map/thrashing events are not observable here, so only the DtoH arm is testable; the outcome is reported whichever way it goes |

## Stop conditions

E8's (E7's verbatim scope plus a nonzero benchmark exit), **plus a failure of nsys on any run** (nonzero exit, missing report, extraction error):

> Any new `dmesg` line (any source) matching `BUG`, `Oops`, `WARNING`, `general protection`, `NULL pointer`, `exited with irqs disabled`, `soft lockup`, `hung_task`, or `RCU stall`
> (timestamp-based diff); `rmmod` failure or nonzero `refcnt`; benchmark timeout; `MemAvailable` below 6 GiB; free disk below 10 GiB; srcversion mismatch; nonzero benchmark exit
> (including a checksum mismatch); parameter read-back mismatch (including `uvm_perf_prefetch_threshold`); **any departure from this pre-registration**.
>
> On any stop: stop immediately, no retries, leave the machine as it is, record the evidence, commit locally, and write the Phase 5 summary.

## Code fixed with this commit

| file | role |
|---|---|
| `tests/e9_make_order.py` | order (seed 202610091) and smoke order |
| `tests/e9_extract.py` | nsys extraction (`um_total_sum` + SQLite) |
| `tests/e9_runner.py` | a copy of `tests/e8_runner.py` (stock module only, imported unchanged for the stock load and the commit helper): nsys wrapper, extraction, workload table |
| `tests/e9_orchestrate.py` | smoke and sweep driver; deadlines computed in-script from `e9/cap_anchor.txt`, logged, abort if not later than now; pushes after every block |
| `tests/e9_analyze.py` | descriptive analysis, `--control`, `--selftest` (scratch directory only) |

## Stated limitations

- Tracing perturbs timing and may perturb the fault and migration pattern itself; E9 counts are counts **under tracing**, not under the E6–E8 conditions. This is why wall-clock is not compared.
- nsys groups GPU faults (a 1 GiB probe shows 77–82 GPU faults for 4,096 touched pages), so "GPU page faults" is nsys's count, not the driver's demand-fault count.
- n = 3 per cell; descriptive only. One page list per size (seed 202610081). Stock module only, one platform.
- Thrashing, throttling and remote-map events are not observable with this nsys version; Y4's second arm cannot be tested.
- The cap: the session was paused after Phase 3 and resumed on 2026-10-09; the cap counts working time (`e9/cap_anchor.txt`).
