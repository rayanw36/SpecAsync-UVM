# Gate E1 — Pre-registration: first-touch oracle with the prefetcher on

**Written and committed 2026-09-25, before the first data-producing run of
this gate.** No E1 data exists at commit time. The structure follows
`E09B_PREREGISTRATION.md`.

Code fixed with this commit (not to be changed after the first run):
- `tests/e1_runner.py`: E0.9b's `e09b_runner.py` execution and
  stop-condition logic, unchanged, with E1's arm table.
- `tests/e09b_collect_tables.py`: tables, unchanged from E0.9b.
- `tests/e1_make_order.py`: run order.
- `tests/e1_analyze.py`: analysis. It imports E0.9b's statistical helpers
  unchanged, and sets the Bonferroni-level MDE for a family of 8.

## Question

E0.9b showed that a real first-touch oracle cannot beat the driver as it
ships when the prefetcher is off. This gate asks the question a reader cares
about most: **with the prefetcher left on, can perfect first-touch knowledge
improve the driver as it ships?**

With the prefetcher on, about 88% of Stencil-24K's demand faults are
prevented. E0.9b C0 had a median of 346,440 demand faults, against 2,930,091
for C1. Only those remaining faults are left for speculation to act on.

## Platform and module

- RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34-generic, headless
  (`multi-user.target`).
- Module `driver/build/595.91.07/nvidia-uvm-specasync-NEW-e0.9a2-fixed.ko`,
  srcversion **`5997D238EF080B77DBD2AAF`** (from `ea1a262`; verified in Part A).
- No kernel code changes and no rebuilds.

## Arms (module parameters at `insmod`; all arms `specasync_log_enabled=1`, as in E0.9b)

| arm | `specasync_policy` | `specasync_offload_depth` | `uvm_perf_prefetch_enable` | other |
|---|---|---|---|---|
| **C0**: the driver as shipped | 0 | 0 | **1** | — |
| **C7-L**: first-touch oracle, prefetch on | 6 | 1 | **1** | `specasync_ft_lookahead=L`, `specasync_ft_table_path=<fresh table>` |

L ∈ {1, 16, 256, 4096}. After every `insmod` the runner reads policy, depth,
prefetch and lookahead back from `/sys/module/nvidia_uvm/parameters/`, and
stops on any mismatch.

**First use of this combination.** No earlier gate ran policy 6 with the
prefetcher on. This is a new parameter combination for the verified module,
not new code. The worker path (`make_resident` under a block-lock `trylock`)
and the demand path (which now also migrates and maps prefetched pages) are
the same code that has run in earlier gates. The automatic stop conditions
are the mitigation. A hard hang that the runner cannot observe remains a
risk; it is stated here and is not specific to this combination.

## Table choice

Fresh first-touch tables are collected **with the prefetcher off**, exactly
as in E0.9b. The tool is `tests/e09b_collect_tables.py`:
- policy 0, `specasync_log_enabled=0`, prefetch off, trace ring 4,194,304 slots;
- trace overwrites must be 0;
- distinct-page assertion **Stencil 1,125,000 and GraphBFS 287,956**, and the
  session stops if either fails;
- output to `results/phaseB1/gate_e1/tables/`.

Reasoning:
- **The prefetch-off fault stream is the true first-touch order of every
  page**: each page faults exactly once on first touch, in program order.
- A prefetch-on trace would record only the faults the prefetcher *failed to
  prevent*. That is not the order in which the program touches memory, and
  it omits roughly 88% of Stencil's pages.
- With the prefetch-off table, a prediction for a page the prefetcher has
  already brought in is simply a no-op prediction. The oracle stays a
  statement of "what the program will touch next", independent of the
  prefetcher.

## Design

- Stencil-24K (`benchmarks/bench_stencil 24000`) and GraphBFS-23
  (`benchmarks/graph_bfs/bench_graph_bfs 23`).
- **n = 10 per cell**, 10 cells (C0 plus 4 C7-L, × 2 workloads), **100 runs**.
- **Run order:** `e1/e1_order.csv`, from `tests/e1_make_order.py` with seed
  **202609261**. It has 10 blocks, each a seeded permutation of all 10 cells,
  so everything is fully interleaved. SHA-256
  `d17cd7de099c6a7706596d7d2fa8105f9547459ee3ae03cacb1a362f6aec8a3c`. The
  order is followed exactly.
- **Per run**, identical to E0.9b:
  1. Check refcnt is 0, then `rmmod`.
  2. `insmod` with the arm's parameters.
  3. Verify srcversion and parameters.
  4. Diff dmesg.
  5. `specasync_clear`.
  6. Run `timeout T setarch -R <bench>`.
  7. Wait 1 s, outside the timed region.
  8. Snapshot all counters, MemAvailable, free disk and the dmesg diff.
  9. Check every stop condition.
  10. Append one CSV row to `e1/e1_runs.csv`. Commit every 10 runs.
- **Timeouts:** 5× the E0.9b C0 median per workload, with floors.
  - Stencil: 5 × 1.1374 = 5.7 s, raised to the floor → **22 s**.
  - GraphBFS: 5 × 31.5931 = 158 s, raised to the floor → **168 s**.
- **Resume:** after any interruption that is not a stop condition, the
  runner resumes at the next index not already in the CSV. The interruption
  is recorded. The sweep is never restarted and no cell is ever re-run.
- Wall-clock is written to the CSV only, never to stdout. There are no
  interim arm comparisons: `e1_analyze.py` refuses to run on fewer than 100
  rows.

## Outcome of record

**Process wall-clock**: the `time.monotonic_ns()` difference around
`timeout T setarch -R <bench>`, the same instrument as E0.9b.

## Primary family: 8 comparisons (baseline C0 in every case)

**C7-L vs C0**, for each L ∈ {1, 16, 256, 4096} and each workload. The
question each answers is whether perfect first-touch knowledge at this
lookahead, with the prefetcher on, improves on the driver as it ships.

## Statistics

- The **median** is the statistic of record. Δ = median(C7-L) − median(C0),
  reported in seconds and %.
- **Two-sided Mann–Whitney U**: exact when the 20 values contain no ties,
  asymptotic with continuity correction otherwise.
- **Holm–Bonferroni step-down across all 8**, family α = 0.05.
- **Cohen's d** with pooled SD.
- **MDE at achieved n** = (z₀.₉₇₅ + z₀.₈₀) × √(s₁²/n₁ + s₂²/n₂). The MDE at the
  Bonferroni level α/8 is also reported.
- **Outliers:** Tukey fences (1.5 × IQR) within each cell. Every comparison
  is reported both with all runs (primary) and with flagged runs excluded,
  and the without-outliers set gets its own Holm correction. **No run is
  ever removed from the primary analysis.**
- **Verdict:** *C7 faster* / *C7 slower* if Holm-significant, by the sign
  of Δ; otherwise *no significant difference*.

## Falsification trigger

**Any C7-L beats C0 by more than its MDE, Holm-significant, on either
workload.** Formally: Holm-significant and median(C0) − median(C7-L) > MDE.

If it fires:
- it is reported **at the top of the report, without softening**;
- **nothing further is run**.

**This result would narrow the paper's central claim.** If it fires, the
central claim no longer holds in the form "speculation cannot improve the
driver as it ships". The report will say that plainly.

## Mechanism metrics (diagnostic only, never a substitute for wall-clock)

Per-cell medians, by workload and L:

- **Demand faults.**
- **Pipeline:** `ft_predictions` → `enqueued` → `spec_migrations`, with
  **not-enqueued** (`drops`) and **lost-after-enqueue**
  (`enqueued − spec_migrations`) shown separately. The identity
  `ft_predictions = enqueued + drops` is checked on every C7 run.
- **`fault_already_resident`**, including its min and max per cell.
- **Pre-staged coverage** = `spec_migrations` ÷ distinct pages.

**Coverage is a much looser upper bound here than in E0.9b, and must not be
read as pages staged ahead of demand.** With the prefetcher on, many
predictions target pages the prefetcher has already brought in.
`spec_migrations` counts those no-op `make_resident` successes (E0.9b Step 1
Q1), so the figure can include many pages that speculation did not move.

**`fault_already_resident` in C0 is recorded explicitly.** It was 0 in
E0.9b's prefetch-off arms. If C0 (prefetcher alone, no speculation) shows
nonzero `fault_already_resident`, the counter cannot be attributed to
speculation in this gate, and the report must say so. It would then be
reported, but not interpreted as speculation's effect.

`spec_hits` is also recorded, labelled as a 10 ms staleness-window counter
and not a win counter.

## Stated limitations (carried over)

- **GraphBFS-23 runs the weakened-cursor oracle.** Policy 6's cursor jumps
  past out-of-order late-ranked faults. In E0.9b, GraphBFS coverage was
  ≤ 0.96–24.98% depending on L. GraphBFS results understate what a
  first-touch oracle could achieve there.
- **`fault_already_resident`** means the worker beat the *servicing thread*,
  not the GPU.
- **Coverage is an upper bound**, much looser here than in E0.9b (see above).
- **Speculation never maps; the prefetcher does** (E0.9b Step 1 Q2).
  Speculation can make a remaining fault cheaper, never prevent it.
- **Single platform:** RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34.
- **The E0.9b C6 cells** may appear only as a labelled context series in a
  separate figure. They come from a different session and are **never
  tested** against this gate's cells.

## Stop conditions (verbatim from the E1 brief)

> Any new `dmesg` line matching `BUG`, `Oops`, `WARNING`, `general protection`,
> `NULL pointer`, or `exited with irqs disabled`; `rmmod` failure or nonzero
> `refcnt`; a benchmark timeout; `MemAvailable` below 6 GiB; free disk below
> 10 GiB; srcversion mismatch; a nonzero benchmark exit code; or anything
> requiring a departure from the committed pre-registration.
>
> On any of these: stop immediately, no retries, no reload, leave the system as
> it is, record the evidence in `E1_STATUS.md`, commit locally.

Implementation, identical to E0.9b:
- The dmesg pattern is applied to **every** new line, not only
  `nvidia_uvm` lines.
- A failed `insmod`, a parameter read-back mismatch or a failed
  `specasync_clear` is treated as a departure from the pre-registration,
  and therefore as a stop.

## Outputs

- `e1/e1_runs.csv`, `e1/primary_comparisons.csv`, `e1/mechanism_by_L.csv`
  and `e1/integrity.txt`.
- The central figure `e1_wallclock_vs_L.{png,pdf}`: wall-clock against L,
  with C0 as a horizontal line (IQR shaded) and one panel per workload.
- A context figure `e1_wallclock_vs_L_with_e09b_context.{png,pdf}`, the same
  plot with E0.9b's C6-L medians as a separate dashed series labelled
  "separate session; context only, not tested".
- Anything not pre-registered goes under **Exploratory — not confirmatory**
  in `GATE_E1_REPORT.md`.
