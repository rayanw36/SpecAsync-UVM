# Gate E4 — Pre-registration: cheap oracle, width, and off-path vs in-path

**Written and committed 2026-09-26, before the first sweep run.** No sweep data
exists at commit time. The Step 1 smoke tests ran before this commit; their
wall-clock is excluded from all analysis (`e4/smoke_runs.csv`). Structure
follows `E09B_PREREGISTRATION.md` and `E1_PREREGISTRATION.md`.

Code fixed with this commit (not to be changed after the first sweep run):

| file | role |
|---|---|
| `tests/e4_runner.py` | E3b runner plus the E4 stop on `ft_fast_verified ≠ 1` |
| `tests/e3b_runner.py` | the runner it wraps |
| `tests/e3b_dmesg.py` | timestamp-based dmesg diff |
| `tests/e3b_collect_tables.py` / `tests/e09b_collect_tables.py` | tables |
| `tests/e4_make_order.py` | order |
| `tests/e4_analyze.py` | analysis; it imports E0.9b's statistical helpers unchanged and sets the Bonferroni MDE for 18 |

## Why

E3b showed that the oracle used in E0.9b and E1 spent 140–167 ns per fault on
its own lookup and lock. A practical predictor would not carry that overhead,
and it made speculation look worse. Those conclusions carry a caveat until
they are re-run with the cheap oracle (`specasync_ft_fast=1`).

E3b also showed that a cheaper predictor overruns the worker's queue. Width
(W > 1) addresses that.

E3b smoke run S3e (Stencil, prefetch off, W = 512) staged every distinct page
before its fault, yet demand faults stayed at 2.97M. F4 tests that
properly: perfect off-path staging at the prefetcher's own granularity,
against the in-path prefetcher.

## Platform and module

- RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34-generic, headless.
- **Every arm uses the new module** `nvidia-uvm-specasync-NEW-e3a2-width-ftfast.ko`
  (srcversion **`33FD42E6E16B0A6658E2BEB`**, sha256 `dc6b226e…45df`). This
  includes C0 and C1 at W = 1, fast = 0, which E3b Step 2 showed behave
  identically to the verified module.
- No new kernel code, no rebuilds.
- `specasync_log_enabled=1` on every arm: it gates the prediction loop, and
  the baselines get it for parity.
- `specasync_trace_faults=0` throughout.

## Arms (policy 6, depth 1, L = 4096 for every speculation arm)

| arm | policy / depth | prefetch | W | fast | role |
|---|---|---|---|---|---|
| **C0** | 0 / 0 | on | 1 | 0 | driver as shipped |
| C7-slow-W1 | 6 / 1 | on | 1 | 0 | E1's configuration, re-measured |
| C7-W1 | 6 / 1 | on | 1 | 1 | cheap oracle |
| C7-W64 | 6 / 1 | on | 64 | 1 | cheap oracle + width |
| C7-W512 | 6 / 1 | on | 512 | 1 | cheap oracle + whole-block width |
| **C1** | 0 / 0 | off | 1 | 0 | prefetch off |
| C6-slow-W1 | 6 / 1 | off | 1 | 0 | E0.9b's configuration, re-measured |
| C6-W1 | 6 / 1 | off | 1 | 1 | cheap oracle |
| C6-W64 | 6 / 1 | off | 64 | 1 | cheap oracle + width |
| C6-W512 | 6 / 1 | off | 512 | 1 | cheap oracle + whole-block width |

After every `insmod`, the runner reads back policy, depth, prefetch,
`trace_faults`, lookahead, W and fast from `/sys/module/nvidia_uvm/parameters/`,
and stops on any mismatch.

## Tables

Fresh prefetch-off first-touch tables are collected once at the start of
Step 3 by `tests/e3b_collect_tables.py` (the unchanged E0.9b collector:
verified module, policy 0, prefetch off, trace overwrites must be 0). They go
to `results/phaseB1/gate_e4/tables/`.

The distinct-page assertion is **1,125,000 (Stencil-24K) and 287,956
(GraphBFS-23)**; the session stops if it fails. Every speculation arm uses
these tables.

## Design

- Stencil-24K (`bench_stencil 24000`) and GraphBFS-23 (`bench_graph_bfs 23`).
- **n = 10 per cell**, 20 cells, **200 runs**.
- **Order:** `e4/e4_order.csv`, from `tests/e4_make_order.py` with seed
  **202609264**. It has 10 blocks, each a seeded permutation of all 20 cells,
  so arms and workloads are fully interleaved. **SHA-256
  `6f42b4803cb48ebc8b66d7c5df09fb749da9ee4f304a8a4c05528b35429404f2`.**
  The order is followed exactly.
- **Per run:**
  1. refcnt 0 → `rmmod` → `insmod` → srcversion and parameter read-back;
  2. `ft_fast_verified`, `nranges` and `verify_ns` read after the load;
  3. timestamp-based dmesg diff;
  4. `specasync_clear`;
  5. `timeout T setarch -R <bench>`;
  6. a 1 s drain;
  7. all counters;
  8. batch-ring and decomp-ring dumps, outside the timed region;
  9. stop checks;
  10. one CSV row appended to `e4/e4_runs.csv`.
- **Timeouts:** Stencil 22 s, GraphBFS 168 s.
- **Commits:** every 10 runs. After any interruption that is not a stop
  condition, the run resumes at the next index not in the CSV. The sweep is
  never restarted, and no cell is ever re-run.
- Wall-clock goes to the CSV only. `e4_analyze.py` refuses to run on fewer
  than 200 rows.

## Outcome of record

**Process wall-clock**: `time.monotonic_ns()` around
`timeout T setarch -R <bench>`.

## Primary comparisons: 18, one Holm family (6 + 4 + 6 + 2)

For each workload:

- **F1, the central claim (prefetch on):** C7-W1, C7-W64 and C7-W512, each
  vs **C0**.
- **F2, oracle instrument cost:** C7-W1 vs **C7-slow-W1**, and C6-W1 vs
  **C6-slow-W1**.
- **F3, width with prefetch off:** C6-W1, C6-W64 and C6-W512, each vs **C1**.
- **F4, perfect off-path staging vs the in-path prefetcher:** C6-W512 vs
  **C0**.

## Statistics

- The **median** is the statistic of record. Δ = median(arm) −
  median(baseline), in seconds and %.
- **Two-sided Mann–Whitney U**: exact when there are no ties, asymptotic with
  continuity correction otherwise.
- **Holm–Bonferroni step-down across all 18**, α = 0.05.
- **Cohen's d** with pooled SD.
- **MDE at achieved n**: (z₀.₉₇₅ + z₀.₈₀) · √(s₁²/n₁ + s₂²/n₂), and the same
  at **α/18** (z = 2.9913).
- **Outliers:** Tukey 1.5 × IQR within each cell. Each comparison is reported
  with all runs (primary) and without flagged runs (with its own Holm
  correction). **No run is ever removed from the primary analysis.**
- **Verdict:** *arm faster* / *arm slower* if Holm-significant, else *no
  significant difference*.

## Falsification trigger

**Any F1 arm beats C0 by more than its MDE, Holm-significant, on either
workload.** Formally: F1, Holm-significant, and median(C0) − median(arm) >
MDE.

If it fires:
- it is reported at the top of the report **without softening**;
- the paper's central claim, that speculation cannot improve the driver as it
  ships, **no longer holds in that form**;
- **nothing further is run**.

## Mechanism metrics (diagnostic only)

Per cell (medians):
- demand faults;
- `fault_already_resident`, and it as a fraction of distinct pages;
- the prediction pipeline: `ft_predictions`, `ft_same_region`, `enqueued`,
  `drops`, and lost-after-enqueue = `enqueued − spec_migrations`. These use
  E3a-2's B3 identities, so no item is counted twice: the work ring's
  THROTTLED count is never added to `spec_region_invalid`;
- `spec_region_invalid` and `spec_pages_requested`;
- from the rings: **pre-lock servicing time** Σ(svc − D3 − D4),
  `enqueue_overhead_ns`, and D5;
- `spec_hits`, recorded and **labelled a 10 ms staleness-window counter, not a
  win counter**.

**Integrity identities**, checked on every policy-6 run and reported (a
nonzero difference is reported, not explained away):
- `demand_faults = ft_predictions + ft_held + ft_unknown_page + ft_exhausted + ft_fast_cas_giveup`;
- `ft_predictions = ft_same_region + enqueued + drops`.

With `trace_faults=0`, Identity 1's left side is `demand_faults`. That equalled
`trace_pushes` exactly in 12/12 E3b runs where both exist. Ring coverage must
be 100% (fewer than 131,071 records); otherwise the covered fraction is
reported and nothing is scaled.

## Required statements (Step 4)

- **F4:** the fraction of distinct pages staged ahead of their fault in
  C6-W512, the demand-fault count, and the wall-clock ratio
  median(C6-W512) / median(C0). The ratio is the measured cost of doing
  staging off-path without mappings, relative to doing it in-path with them.
- **F2:** the wall-clock cost of the slow oracle's overhead,
  median(slow) − median(fast), compared with E3b's servicing-time estimates
  (about 0.36 s for C6 and 0.041 s for C7, Stencil) as a **stated
  cross-session comparison, not a test**.
- **Central figure** `e4_wallclock_by_arm.{png,pdf}`: wall-clock per arm, one
  panel per workload, C0 and C1 as horizontal reference lines (IQR shaded),
  and the prefetch-on and prefetch-off arms visually grouped.
- Anything else goes under **Exploratory — not confirmatory**.

## Stated limitations

- GraphBFS runs the **weakened-cursor oracle**. Its coverage understates a
  first-touch oracle's potential.
- `fault_already_resident` means the worker beat the servicing thread, **not
  the GPU**.
- The cheap oracle still carries a residual of about **19–35 ns per fault**,
  unattributed (E3b Step 4).
- **Speculation never installs mappings; the prefetcher does.** F4 measures
  exactly that difference and nothing more.
- With the cheap oracle, **queue-full drops rise** at W = 1 on Stencil
  prefetch-off (E3b), which shrinks the D5 saving. W > 1 is the design's
  answer, and F3 measures it.
- **Single platform:** RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34.

## Stop conditions (verbatim from the E4 brief)

> Any new `dmesg` line (any source) matching `BUG`, `Oops`, `WARNING`,
> `general protection`, `NULL pointer`, `exited with irqs disabled`,
> `soft lockup`, `hung_task`, or `RCU stall`; `rmmod` failure or nonzero
> `refcnt`; benchmark timeout; `MemAvailable` below 6 GiB; free disk below
> 10 GiB; srcversion mismatch; nonzero benchmark exit; parameter read-back
> mismatch; `specasync_ft_fast_verified ≠ 1` on any fast = 1 load;
> `specasync_ft_fast_cas_giveup > 0`; `specasync_spec_region_invalid > 0`; or
> anything requiring a departure from the committed pre-registration.
>
> **On any of these: stop immediately.** No retries, no reload, no desktop
> restore. Record the evidence in `E4_STATUS.md`, commit locally, and end.
