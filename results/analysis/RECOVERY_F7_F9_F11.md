# Recovery of F7/F9/F11's derived intermediates

`PROVENANCE_GAPS_F7_F9_F11.md` documented that three headline findings existed
only as markdown prose, with their raw inputs `.gitignore`d and never
converted to a committed derived CSV. This is not a figure problem -- the
underlying gate reports (`GATE_A1_REPORT.md`, `GATE_T4_REPORT.md`,
`GATE_B7_5070TI_PHASEC.md`) are themselves unreproducible from the
repository as it stood. This document records the recovery: what raw
telemetry was found (on disk vs. in a Release tarball), what was parsed,
and what every recomputed value was cross-checked against.

**No number in the recovered CSVs was transcribed from a markdown table.**
Every one was computed from raw bytes and then compared to its published
figure; the scripts assert the match (not just print it) and fail loudly
on a mismatch. Where a value could not be recovered from either source
(raw `.bin` still on disk, or the two release tarballs), it was left out,
not backfilled from prose -- one such gap remains (T4's kernel-loop time,
see below).

## Sources checked, in the order the task specified

1. **Raw `.bin` telemetry still on disk** -- checked first, before assuming
   anything needed a tarball. This alone recovered:
   - `results/analysis/t_a1_worker/{full_run,short_run}_5070ti/` (5070 Ti
     worker/batch dumps -- all present).
   - `results/gate3/telemetry/*.bin` (T4 prefetch-OFF batch-ring dumps,
     all 60 files present).
   - `results/phaseC/paired_wallclock_5070ti/decomp/*.bin` (30 files,
     same-session paired Task 3/4 capture).
   - `results/phaseB1/hit_probe_5070ti/task1_probe_{batch,worker}.bin`.
   - `results/phaseB1/hit_probe/*.bin` (several T4-era probe sessions,
     including the two that back the two different published T4 hit-rate
     figures -- see Task 1 below).
2. **Release tarball `raw-t4-20260812`** (935 MiB, 1157 files) -- needed for
   T4's `t_a1_worker/{full_run,short_run}` (worker/batch dumps only; the
   oracle trace `.bin`s and `worker_completion.csv` were already committed
   or on disk). Downloaded via `gh release download`, extracted directly
   onto its natural repo paths (all gitignored, so `git status` stays clean
   after extraction).
3. **`raw-5070ti-phasec-20260813`** -- not needed; the one item that might
   have required it (5070 Ti's same-session paired decomp captures) was
   already on local disk (item 1 above).

## Task 1 -- F7's inputs

`tools/analysis/recover_worker_latency.py` parses the 48-byte
`specasync_work_record` format (`"<4Q4I"`: enqueue/dequeue/completion
timestamps + va_addr + result/policy/pad) from every `*_worker_run*.bin`
across both platforms and both scales (full-size, short-run), and from
three deterministic-probe sessions (two T4, one 5070 Ti).

**Cross-check: all 8 recomputed dispatch medians match their published
figures to within 0.01%** (`GATE_A1_REPORT.md` Result 2 table;
`GATE_B6_TASK2_A1_REPLICATION.md` Result 2a table):

| platform | scale | bench | recomputed | published |
|---|---|---|--:|--:|
| T4 | short | GraphBFS-18 | 2579.642us | 2579.6us |
| T4 | short | Stencil-2000 | 3198.006us | 3198.0us |
| T4 | full | GraphBFS-23 | 10606.971us | 10607.0us |
| T4 | full | Stencil-24000 | 9438.138us | 9438.1us |
| 5070Ti | short | GraphBFS-18 | 60.325us | 60.33us |
| 5070Ti | short | Stencil-2000 | 25.609us | 25.61us |
| 5070Ti | full | GraphBFS-23 | 2274.567us | 2274.57us |
| 5070Ti | full | Stencil-24000 | 2306.307us | 2306.31us |

**Probe baseline, also exact**: 5070 Ti's `task1_probe` gives
dispatch=5.260us, exec=0.100us -- an exact match to
`GATE_B6_TASK2_A1_REPLICATION.md`'s cited 5.26us/0.10us. On T4, the raw
`hit_probe/` directory holds *multiple* probe sessions under different
tags; `prefoff_adj` (256/256 worker records, batch-ring hit rate
254/256=99.2188%) reproduces `GATE_A_report.md`'s (results/phaseB1/)
original 254/256 finding exactly, with dispatch=5.598us/exec=0.300us --
matching that report's own "~5.6us/~0.35us" citation. A second session,
`t4gate2`, reproduces the *other* published T4 probe figure
(255/256=99.6094%, `GATE_A_report.md` results/analysis/ / `T4_REPORT.md`)
exactly. Both are genuine, both are kept (not collapsed into one "the"
number) -- this project's own reports already treat 99.22% and 99.61% as
two consistent measurements of the same regime, not a contradiction.

Outputs: `results/analysis/t_a1_worker/worker_latency_records_{t4,5070ti}.csv`
(per-record, ~1.5M rows each), `worker_latency_summary.csv` (medians/p90/n
per workload/scale/platform), `results/phaseB1/hit_probe_summary.csv`.

**F7's third data family** (corrected demand-fault inter-arrival rates) is
recovered separately, see Task 3's fault-rate work below (same script,
`recover_t4_prefetch_off_hitrate.py`) -- it feeds both F7 and F11.

## Task 2 -- F9's inputs

**Which rung was unverifiable, and why:** all four rungs' formulas were
checked against `GATE_B7_5070TI_PHASEC.md` Section 4. Two (PCIe, wall-clock)
were already fully committed-data-backed before this session; two
(kernel-loop, dispatch-window) each had exactly one side markdown-only.
Both were investigated:

- **Dispatch-window's 5070 Ti side (987,448.2us) -- RECOVERED.** The raw
  decomp snapshots (`results/phaseC/paired_wallclock_5070ti/decomp/
  {Stencil-8K,GraphBFS-23,Sweep-4K,Sweep-8K,Sweep-16K,Sweep-24K}_trial{1-5}.bin`)
  were on disk (30 files, no tarball needed).
  `tools/analysis/build_t3_sweep_csv_5070ti.py` (the existing
  `build_t3_sweep_csv.py`'s 5070 Ti counterpart, same 112-byte
  `"<12Q4I"` decomp-record format) parses all 6 workloads.
  **`sum(total_ns)` for Sweep-24K = 987,448,177ns = 987,448.2us -- exact
  match** to `GATE_B7_5070TI_PHASEC.md`'s cited figure.
- **Kernel-loop's T4 side (1645.6ms) -- NOT RECOVERABLE.** Checked the T4
  tarball's file listing: it contains `t_a1_worker`, `gate_c`, `gate_d`,
  `hit_probe`, `oracle_probe`, `oracle_coalesce` and the Phase C
  paired-wallclock decomp dumps -- no per-trial kernel-loop timing file for
  the original 5-trial `PHASEC_REPORT.md` G3 measurement. No committed
  script from that era (`tests/gate_b7_decomp_overhead.sh`, which produced
  the 5070 Ti's `overhead_times*.csv`, is a *later*, 5070-Ti-only script;
  no T4 equivalent was ever written) saved raw trial times to a file. This
  measurement appears to have been run ad hoc and only its median was ever
  written down. **Left out, not backfilled** -- `bandwidth_scaling_ladder`
  shows this rung's reported value (4.45x) but renders it visually distinct
  (hatched, footnoted "reported, not independently verified here").

`tools/analysis/build_f9_ladder_inputs.py` assembles all four rungs into
`results/figures/f9_ladder_inputs.csv`, recomputing PCIe bandwidth from the
already-committed `results/analysis/platform/{T4,5070TI}_PLATFORM_PROVENANCE.txt`
files' own `nvidia-smi --query-gpu` PCIe block (max negotiated generation x
physically-wired current width -- T4's slot is physically x8 despite the
chip supporting x16; the 5070 Ti's *current* generation reading is a
power-saving idle downclock, documented in its own provenance file, so max
generation is used there) via the standard PCI-SIG per-lane throughput
table, and recomputing wall-clock/dispatch-window medians from the CSVs
above. **All three ratios reproduce their published figures almost
exactly**: PCIe 8.000x (cited "~8x"), wall-clock 3.787x (cited "3.79x"),
dispatch-window 2.350x (cited "2.35x").

## Task 3 -- F11's inputs

**Deterministic probe and oversub hit rate**: covered by Task 1 (probes)
and already-committed atomics data (oversub) respectively.

**Oracle real-workload hit rates (Stencil-24K, GraphBFS-23, T4,
non-oversubscribed)** -- the harder recovery. `tools/analysis/
recover_t4_prefetch_off_hitrate.py` parses the same `results/gate3/telemetry/
*.bin` batch-ring dumps behind F7's fault-rate figures, using the 72-byte
`"<6Q6I"` batch-record format.

The recovery had to reconstruct **two different, both-real numbers** from
the same raw files, because `t4_prefetch_off_telemetry.sh` never called
`specasync_clear` between its 15 reps (`GATE_A1_REPORT.md`'s "Root cause
confirmed" open item): every dump after the first is a *cumulative*
snapshot since the last real clear (never), and the 131,071-slot ring
freezes solid once full (Stencil: mid-rep 2; GraphBFS: mid-rep 5) --
confirmed empirically here (`run17`..`run30` are byte-identical for
Stencil; `run50`..`run60` for GraphBFS).

- **CORRECTED (marginal-diff, pre-saturation reps only)**: consecutive
  cumulative dumps subtracted to isolate each rep's own contribution.
  Reproduces `GATE_A1_REPORT.md`'s correction exactly: Stencil rep 1
  faults=3,237,375 (rate=188,000.9/s, published band 187,943-188,001/s);
  GraphBFS reps 1-4 faults=[446165, 445004, 446415, 445300] (exact,
  published exactly), mean rate=7652.24/s (published 7,652/s = 0.00765M/s).
  Hit rates from this same reconstruction: **Stencil rep1 = 0.0132%,
  GraphBFS reps1-4 pooled = 0.2357%.**
- **SUPERSEDED (sum-across-all-15-raw-dumps)**: reproduced *only* to
  confirm where `GATE_T4_REPORT.md` Section 1's original table came from --
  summing all 15 dump files without accounting for post-saturation
  duplication multi-counts the frozen tail 14x. This exactly reproduces
  the original table's enqueued/hits counts (Stencil: 50,964,514 enqueued
  / 9,933 hits; GraphBFS: 20,505,109 / 51,569 -- both exact matches),
  confirming that methodology's provenance, and that its **ratio**
  (0.0002/0.0025 raw = 0.02%/0.25%) happens to land close to the corrected
  clean-rep numbers above (0.0132% and 0.2357% respectively) even though
  the absolute counts were wrong by an order of magnitude -- both
  numerator and denominator over-counted together, as `GATE_A1_REPORT.md`'s
  open item hypothesized, now confirmed rather than just argued.

Both reconstructions are in `results/gate3/telemetry/
t4_prefetch_off_hitrate_recovered.csv`, methodology labeled per row.

**Master table**: `tools/analysis/build_f11_master_hitrate_table.py`
assembles every (configuration, platform, hit_rate, wall_clock_delta,
baseline) tuple into `results/figures/f11_hitrate_vs_speedup_master.csv`,
9 rows, baseline stated explicitly and justified in a `notes` column on
every row (never implicit, per `OVERSUB_C3_VERIFICATION.md`'s methodology
note) -- including two rows for the oversub point (baseline=C0 *and*
baseline=C1, both shown, since picking only one is exactly the error that
methodology note exists to prevent.

## Task 4 -- Figures

Built using the same `_fig_common.py` conventions as F8/F10:
`results/figures/dispatch_latency_race.{pdf,png}`,
`bandwidth_scaling_ladder.{pdf,png}`, `hitrate_vs_speedup.{pdf,png}`.
Each script loads its source CSV(s), prints the underlying data to stdout
for auditability, and (F9) visually distinguishes the one still-unverified
rung rather than presenting it as equally solid.

## Task 5 -- Audit: other exposed derived intermediates

Enumerated every raw-telemetry pattern in `.gitignore` and checked, for
each, whether a derived CSV or summary already exists in git alongside it.
**Not exhaustive** -- this is what was checked with reasonable confidence
in the time available, not a guarantee nothing else is exposed.

**UPDATE (follow-up session): #1 and #2 are now recovered, #3 is partially
recovered.** `tools/analysis/recover_oracle_probe_coalescing_fix.py` and
`tools/analysis/recover_gate_c_gate_d.py` -- see their docstrings and stdout
for the full cross-check record. Summary:

1. **`results/phaseB1/oracle_probe/` + `results/phaseB1/oracle_coalesce/`
   -- RECOVERED.** Parsed with the standard `"<6Q6I"` batch-record format.
   The directory names are swapped from the intuitive guess (`oracle_probe/`
   holds the *serialized* probe, `oracle_coalesce/` the *coalesced* one) --
   confirmed empirically (avg faults/batch), not assumed from the name.
   Both rows of `GATE_B_diagnosis.md`'s table reproduce exactly: serialized
   OLD=0.9922/NEW=0.9922 (published "0.99"/"0.99"), coalesced
   OLD=0.0175/NEW=0.4107 (published exactly), improvement=23.41x (published
   "(23x)"). Written to
   `results/phaseB1/oracle_probe_coalescing_fix_recovered.csv`.
2. **`results/phaseB1/gate_c/{stream_134217728,stream_268435456}.csv` --
   RECOVERED.** These were already clean per-cycle CSVs, just gitignored;
   no parsing needed. p0/p1/p5 medians recomputed and match
   `GATE_C_report.md`'s published table exactly at both sizes (347.99/
   355.13/355.12ms and 675.31/687.24/685.74ms). Copied to
   `results/phaseB1/gate_c_stream_{134217728,268435456}_recovered.csv`.
3. **`results/phaseB1/gate_d/{stencil,graphbfs,stencil_ovsub}/` --
   PARTIALLY recovered.** `times.csv` (per-run wall-clock) was already
   clean and is now copied to `results/phaseB1/gate_d_{stencil,graphbfs,
   stencil_ovsub}_times_recovered.csv`. The `p0-p4_batch.bin` hit-rate
   rings, however, do **not** parse with the standard `"<6Q6I"` format --
   values come out many orders of magnitude wrong (e.g. faults=
   14,185,906,036,344 vs. `summary.txt`'s published 4,191). This ring
   predates the standardized batch-record layout used everywhere else in
   this project, and its correct layout was not identified in the time
   available. **Left unconverted, not backfilled from `summary.txt`'s
   prose** -- `oversub_collapse.pdf`'s hit-rate figures remain
   text-summary-only, not independently reproducible from a committed CSV.
   This is a genuinely open item (unlike the T4 kernel-loop gap, which is
   closed/unrecoverable) if someone wants to reverse-engineer the old ring
   layout later.

**Checked and NOT exposed** (derived CSV already covers what's cited):
`t_a2_bimodality` (T4 and 5070 Ti -- `bimodality.csv` already has a
`processed` column, no need for the missing `ASLR_*.bin` dumps);
`t_a2b_setarch_regime` (`setarch_regime.csv` committed);
`t_b8_sgemm_5070ti`, `t_b8_oversub_5070ti` (derived `*_times.csv` committed
with hit-rate/wall-clock columns already); `gate3_interleaved{,_5070ti}/telemetry/`
and `cufft_interleaved{,_5070ti}/telemetry/` (each has a sibling committed
`*_times.csv` with `wall_s`+`hit_rate` columns covering the headline
numbers those reports cite).

**Not re-flagged**: `results/analysis/gate_b9_oversub_mechanism/telemetry_*/`
(the ring-saturated Task 2 mechanism data) -- already self-flagged as not
trusted for any finding, in this project's own `ARTIFACT_CATALOG.md`, so
there's no exposure risk (no number from it is presented as reliable).
