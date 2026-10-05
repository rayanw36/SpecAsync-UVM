# Gate E6 — Pre-registration: does lowering the stock prefetch threshold match speculation?

**Committed 2026-10-05, before any E6 run.** No E6 run data exists at commit time.

## Question

E5 tested prefetch density thresholds 51, 75 and 100 (off) only. Does lowering the stock
prefetcher's density threshold (a module parameter, range 0–100, strict test
`counter·100 > subregion_pages·threshold`, `uvm_perf_prefetch.c:118`) let **C0** match
**C7W512-t51** with no speculation? If yes, the Stencil gain over the shipped default is
available by tuning, and speculation's own contribution must be measured at matched
thresholds.

## Platform and module

- RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34-generic, headless.
- Module for every arm: `nvidia-uvm-specasync-NEW-e3a2-width-ftfast.ko`
  (srcversion **`33FD42E6E16B0A6658E2BEB`**, sha256 `dc6b226e…45df`).
- Parameters as in E5: `specasync_log_enabled=1`, `specasync_trace_faults=0`.
- `uvm_perf_prefetch_threshold` is set at `insmod` and read back from
  `/sys/module/nvidia_uvm/parameters/`. A mismatch is a stop.

## Arms

**Family 1 — Stencil-24K** (`bench_stencil 24000`, timeout **22 s**), n = 10 per cell,
**80 runs**:

| cell | policy / depth | prefetch | threshold | W | fast | L |
|---|---|---|---|---|---|---|
| C0-t0, C0-t10, C0-t25, C0-t51 | 0 / 0 | on | 0, 10, 25, 51 | 1 | 0 | — |
| C7W512-t0, C7W512-t10, C7W512-t25, C7W512-t51 | 6 / 1 | on | 0, 10, 25, 51 | 512 | 1 | 4096 |

**Family 2 — GraphBFS-23** (`bench_graph_bfs 23`, timeout **168 s**), n = 10 per cell,
**30 runs**, run after Family 1:

| cell | policy / depth | prefetch | threshold | W | fast |
|---|---|---|---|---|---|
| C0-t0, C0-t25, C0-t51 | 0 / 0 | on | 0, 25, 51 | 1 | 0 |

**Skip rule (Family 2).** If Family 1 ends more than **2 h 15 min** after Phase 0 began,
Family 2 is skipped and recorded as skipped (`e6/family2_skipped.txt`). That is not a
departure from this pre-registration.

**Baseline naming.** C0-t51 is the shipped driver. C0-t0, C0-t10 and C0-t25 are **not**
the shipped driver. Every comparison names its baseline.

## Tables

Fresh prefetch-off first-touch tables, collected at the start of the run phase with
`tests/e3b_collect_tables.py` (the E5 procedure). The distinct-page assertions are
**1,125,000 (Stencil-24K)** and **287,956 (GraphBFS-23)**. The session stops if either fails.

## Design

- **Order:** `e6/e6_order.csv`, from `tests/e6_make_order.py` with seed **202610051**.
  - Family 1: 10 blocks, each a seeded permutation of its 8 cells (idx 1–80).
  - Family 2: 10 blocks, each a seeded permutation of its 3 cells (idx 81–110), run after
    Family 1.
  - **SHA-256 `b20b4b2f9fdc37d9bdfc…`** (first 20 characters; full hash in
    `e6/e6_order.sha256`). The order is followed exactly.
- **Smoke test:** one run of each never-run cell (C0-t0, C0-t10, C0-t25, C7W512-t0,
  C7W512-t10, C7W512-t25 on Stencil; C0-t0 and C0-t25 on GraphBFS), with stop conditions
  applied. Rows go to `e6/e6_smoke.csv` (order `e6/e6_smoke_order.csv`) and are
  **excluded from analysis**. Any stop ends the session.
- **Per run, exactly as E5:** reload; srcversion and parameter read-back, including
  `uvm_perf_prefetch_threshold`; `ft_fast_verified` on every fast = 1 load; the timestamp
  dmesg diff (`tests/e3b_dmesg.py`); `specasync_clear`; `timeout T setarch -R <bench>`;
  a 1 s drain; the counters; the batch-ring and decomp-ring dumps outside the timed
  region; the stop checks; one CSV row in `e6/e6_runs.csv`.
- **Runner:** `tests/e6_runner.py`, which wraps `tests/e5_runner.py` **unchanged**
  (`e5_runner` → `e4_runner` → `e3b_runner`). The E6 inputs are only the order file,
  the output paths and the commit message. The bench timeouts are `e3b_runner`'s
  unchanged table (stencil 22 s, graphbfs 168 s).
- **Commits:** every 10 runs. After any interruption that is not a stop condition, the
  run resumes at the next index not in the CSV. Nothing is ever re-run.
- **Wall-clock** goes to the CSV only, never to stdout during the run.
- **Analysis refusal:** `tests/e6_analyze.py` refuses to run on fewer rows than
  pre-registered: 110, or 80 with a skip record.

## Outcome of record

Process wall-clock: `time.monotonic_ns()` around `timeout T setarch -R <bench>`.

## Primary test — Family 1

One Holm family of **4**, two-sided Mann–Whitney U on per-run wall-clock:
**C7W512-t51 vs each of C0-t0, C0-t10, C0-t25, C0-t51.**

**Verdict, applied mechanically:**

- **V-A — "speculation beats tuning".** C7W512-t51 is Holm-significantly faster than
  **all four** C0-t cells.
- **V-B — "tuning matches or beats" (FALSIFICATION TRIGGER for "the Stencil gain requires
  speculation").** **At least one** C0-t cell is **not** Holm-significantly slower than
  C7W512-t51. This includes a cell that is faster, and a cell with no significant
  difference.

V-A and V-B are exclusive and exhaustive.

## Secondary

- **Within-threshold, Stencil, Holm family of 3** for t ∈ {0, 10, 25}, C7W512-t vs C0-t:
  - on wall-clock;
  - on demand faults, as a separate Holm family of 3.
- **D(t)** as defined in E5: `D(t) = 1 − median(demand faults, C7W512-t) ÷ median(demand faults, C0-t)`,
  for t ∈ {0, 10, 25, 51}.
- **Family 2, Holm family of 2** (GraphBFS): C0-t0 and C0-t25 vs C0-t51, on wall-clock.

## Descriptive, not tested

C0 demand faults and wall-clock against t; D5 and **D5 per demand fault** per cell
(from the decomp-ring dumps); `fault_already_resident`; `spec_pages_requested`; drops;
the prefetch-page counters if the collector exposes them.

For every comparison, report:
- MDE at achieved n, and at the family α;
- Cohen's d;
- results with and without Tukey-flagged outliers. **No run is ever removed from the
  primary analysis.**

## Expectations

These were committed by the reviewer before the run. They are **not part of the verdict**.
The analyst's operational definitions below were fixed before the run, in the analyzer,
and do not alter the reviewer's wording.

- **X1.** C0 demand faults fall monotonically as the threshold decreases (high confidence).
  *Operational:* held iff median faults satisfy `t0 < t10 < t25 < t51`.
- **X2.** C0's fastest threshold is below 51 (moderate). *Operational:* held iff the
  C0 cell with the lowest median wall-clock is one of t0, t10, t25.
- **X3.** V-A versus V-B is genuinely uncertain, about even.
  *Operational:* **not scored.** The expectation has no direction, so neither verdict
  contradicts it, and it cannot be marked held or failed without inventing a criterion.
  The verdict is recorded. (This is a DOC-class ambiguity, flagged in `E6_STATUS.md`.)
- **X4.** Within-threshold D(t) at t = 0 is far below +0.40, but the wall-clock gain stays
  nonzero. *Operational:* held iff **D(0) ≤ 0.20** and the wall-clock comparison
  C7W512-t0 vs C0-t0 is **Holm-significant in the faster direction**.

## Falsification trigger

V-B above. If it fires, the report states it at the top, unsoftened, and nothing further
is run.

## Stated limitations

- C0 at thresholds below 51 is **not** the shipped driver. Every comparison is within a
  threshold.
- Single platform: RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34.
- The oracle is the **near-perfect first-touch table** (Stencil) and the **weakened-cursor
  table** (GraphBFS, coverage 0.22–0.81 across the C6 arms in E4). This gate explains the
  mechanism; it does not measure a practical predictor.
- At T_off-like low thresholds the prefetch hint is computed on every fault, so its
  own cost is included in C0-t0 and C0-t10.

## Stop conditions

Identical to E5, verbatim scope:

> Any new `dmesg` line (any source) matching `BUG`, `Oops`, `WARNING`, `general protection`,
> `NULL pointer`, `exited with irqs disabled`, `soft lockup`, `hung_task`, or `RCU stall`
> (timestamp-based diff); `rmmod` failure or nonzero `refcnt`; benchmark timeout;
> `MemAvailable` below 6 GiB; free disk below 10 GiB; srcversion mismatch; nonzero
> benchmark exit; parameter read-back mismatch (including `uvm_perf_prefetch_threshold`);
> `specasync_ft_fast_verified ≠ 1` on any fast = 1 load; `specasync_ft_fast_cas_giveup > 0`;
> `specasync_spec_region_invalid > 0`; **any departure from this pre-registration**.
>
> On any stop: stop immediately, no retries, leave the machine as it is, record the
> evidence, commit locally, and write the Phase 7 summary.

## Code fixed with this commit

| file | role |
|---|---|
| `tests/e6_make_order.py` | order (seed 202610051) |
| `tests/e6_runner.py` | wrapper over `tests/e5_runner.py`, which is unchanged |
| `tests/e6_analyze.py` | analysis; E0.9b statistical helpers imported unchanged; refusal rule; positive control (`--control`) |
| `tests/e5_runner.py`, `tests/e4_runner.py`, `tests/e3b_runner.py`, `tests/e3b_dmesg.py`, `tests/e3b_collect_tables.py` | unchanged |

**Analyzer positive control** (`e6/analyzer_positive_control.txt`): `e6_analyze.py --control`
applies E6's comparison to E5's committed `e5_runs.csv`, C7W512-t51 vs C0-t51. It reproduces
**−5.26%, p = 1.08e-05, D(51) = +0.4009**. **PASS.**
