# F7, F9, F11: not built -- committed-data provenance gaps

Per this figure-generation task's policy ("every number must come from a committed CSV
... if a value exists only in a markdown report and not in a CSV, say so and do not
hardcode it"), F7, F9, and F11 as specified cannot be built purely from committed data.
This documents exactly what's missing and why, so the gap is a recorded fact, not a
silent omission. F8 (`decomposition_crossplatform`) and F10 (`oversub_threeway`) ARE
fully CSV-backed and were built -- see their own script docstrings.

## F7 -- dispatch_latency_race: not built (0 of 3 data families are CSV-backed)

All three required data families exist only as markdown-table transcriptions in gate
reports, computed from raw `.bin` telemetry that is `.gitignore`d, not committed:

- **Uncontended probe baseline** (T4 ~5.6/0.35us dispatch/exec median, `GATE_A_report.md`;
  5070 Ti 5.26/0.10us, `GATE_B6_TASK2_A1_REPLICATION.md`): computed from
  `tests/run_hit_probe.sh`'s worker-log dump, written only to
  `results/phaseB1/hit_probe{,_5070ti}/*.bin` -- gitignored
  (".gitignore: results/phaseB1/hit_probe/*.bin", "hit_probe_5070ti/*.bin"). No CSV.
- **Contended dispatch median/p90** (`GATE_A1_REPORT.md` Result 2, T4;
  `GATE_B6_TASK2_A1_REPLICATION.md` Result 2a, 5070 Ti): computed by
  `tests/t_a1_analyze.py` from per-record `*_worker_run*.bin` dumps under
  `results/analysis/t_a1_worker/{full_run,short_run}[_5070ti]/` -- confirmed gitignored
  (`.gitignore:119: results/analysis/t_a1_worker/**/*.bin`; only 4 of 48 on-disk `.bin`
  files in that tree are tracked, and those 4 are the oracle trace files, not the worker
  dumps). The committed `worker_completion.csv` in each of those four directories has
  only `processed,enqueued,drops,wall_s,...` -- no per-record dispatch-latency column.
- **Corrected demand-fault inter-arrival rates** (0.188M/s Stencil-24K, 0.00765M/s
  GraphBFS-23, `GATE_T4_REPORT.md` Section 2 correction / `GATE_A1_REPORT.md` Result 2):
  derived from per-rep batch/fault counts read out of `specasync_log` ring dumps under
  `results/gate3/telemetry/*.bin` -- gitignored (`.gitignore:62`). The committed
  `results/gate3/telemetry/t4_prefetch_off_times.csv` has only
  `run_order_idx,timestamp_iso8601,config,bench,size,rep_in_cell,wall_s,srcversion,
  dmesg_delta` -- no fault or batch count column.

**None of F7's three data families can be recomputed from anything currently committed.**
Rerunning the underlying harnesses (`tests/run_hit_probe.sh`,
`tests/t_a1_worker_completion.sh`, the Gate 3 prefetch-off sweep) would regenerate the raw
`.bin` files needed; that is out of scope for a plotting-only task working from existing
commits.

## F9 -- bandwidth_scaling_ladder: not built (2 of 4 rungs unverifiable)

Source: `GATE_B7_5070TI_PHASEC.md` Section 4.

| Rung | T4 side | 5070 Ti side | Verdict |
|---|---|---|---|
| PCIe raw, 8x | -- | -- | Hardware spec (gen3x8 vs gen5x16), not an experimental measurement -- no CSV applies by nature |
| Kernel-loop, 4.45x | 1645.6ms, `PHASEC_REPORT.md` G3, 5-trial median -- **markdown only, no CSV** | 369.735ms -- **CSV-backed**: `results/phaseC/decomp_overhead_5070ti/overhead_times_interleaved.csv` (n=10, interleaved; median recomputed here = 369.735ms, exact match) | T4 side unverifiable |
| Process wall-clock, 3.79x | 4.090s -- **CSV-backed**: `results/phaseC/paired_wallclock/t3_paired_times.csv` | 1.080s -- **CSV-backed**: `results/phaseC/paired_wallclock_5070ti/t3_paired_times_5070ti.csv` | **Fully verifiable, both sides** |
| Dispatch-window sum, 2.35x | 2,320,404.6us -- **CSV-backed**: `results/phaseC/paired_wallclock/decomp_stencil_sweep_24000_t3.csv`, `sum(total_ns)` recomputed here = 2,320,404,576ns = 2,320,404.6us, exact match | 987,448.2us -- **markdown only, no CSV**: the same-session paired capture's raw decomp snapshots live at `results/phaseC/paired_wallclock_5070ti/decomp/*.bin`, 0 of which are git-tracked. The standalone Task-3 5070 Ti file (`results/phaseC/decomp_5070ti/decomp_stencil_sweep_24000.csv`) is a *different* single-trial capture, not this same-session paired one -- confirmed by recomputing its sum (196,289us), which does not match 987,448.2us | 5070 Ti side unverifiable |

**Only the wall-clock rung (3.79x) is fully reproducible from committed data.** The rung
that carries the figure's central point -- "the fault-servicing path benefits least" --
is the dispatch-window rung, and its 5070 Ti denominator cannot be verified from anything
committed. A reduced ladder omitting the unverifiable rungs would drop exactly the
comparison the figure exists to make, so no partial figure was built either; if useful,
the 3.79x rung alone is available and exactly reproducible on request.

## F11 -- hitrate_vs_speedup: not built (2 of 4 point-families unverifiable)

| Point family | Status |
|---|---|
| Deterministic probe, 99.61% (255/256) | **markdown only** -- `tests/run_hit_probe.sh` writes only `.bin` ring dumps to `results/phaseB1/hit_probe{,_5070ti}/`, gitignored, no CSV, same gap as F7's probe baseline |
| cuFFT, 13.80% (5070 Ti) / 4.07% (T4) | **CSV-backed**: `results/phaseB2/cufft_interleaved{,_5070ti}/cufft_interleaved_times.csv`, `hit_rate` column present per-run. Recomputed here (median, n=15 kept reps, size=67108864, p2/stride): T4 = 3.94%, 5070 Ti = 13.75% -- both within rounding of the cited 4.07%/13.80% (those were aggregate hit-rate ratios over pooled enqueue/hit counts, not per-rep medians; same data, different aggregation statistic, confirms the CSV is the right source) |
| Oracle real workloads, 0.02-0.25% (non-oversub Stencil/GraphBFS) | **markdown only** -- `GATE_T4_REPORT.md`'s hit rates come from the same gitignored `specasync_log` ring dumps as F7's fault-rate figures; `t4_prefetch_off_times.csv` has no hit-rate column |
| Oversub, ~0.0025% (C3, oversubscribed) | **CSV-backed**: `results/analysis/gate_b9_oversub_mechanism/task2c_c0_threeway_times_MERGED.csv`, `atomic_spec_hits`/`atomic_enqueued` columns (this project's own Gate B9 atomics work). Recomputed here (C3, all kept reps/iters pooled): enqueued=956,792,350, hits=26,280, rate=0.0027% -- matches the cited ~0.0025% closely |

**2 of 4 point-families (cuFFT, oversub) are solidly CSV-backed and reproduce the cited
values closely.** The other two are not just unverifiable but are exactly the scatter's
two extremes -- the probe anchors the high end (99.61%) and the oracle real-workload band
anchors the low-but-not-lowest end; without them the "no relationship" visual argument
loses the contrast it depends on (a scatter of only the cuFFT and oversub points, both
already low/near-zero hit rate, would not by itself demonstrate "no relationship" the way
a full high-to-low span does). No partial figure was built for the same reason as F9.
