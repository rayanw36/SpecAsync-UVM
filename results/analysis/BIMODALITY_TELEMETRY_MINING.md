# Part 1 — Telemetry mining for the C3/Stencil-24K bimodality (Tasks 1.1, 1.2)

Data: `results/phaseB2/gate3_interleaved/telemetry/*.bin` (T1's `specasync_log` batch-record
ring, `struct specasync_batch_record`, 72 B/record: `batch_id, t0-t4_ns, num_faults,
spec_enqueues, spec_drops, spec_hits, enqueue_overhead_ns`). Parsed with
`benchmarks/tools/specasync_parse.py`'s exact struct layout (independently re-implemented here
for bulk aggregation; verified byte-identical output against the tool on a sample run). All 22
runs/cell (2 warm-up + 20 kept) parsed cleanly for C0-C3 x {Stencil-24K, GraphBFS-23} -- zero
stale/filtered records anywhere. Per-run wall-clock values cross-checked against
`gate3_interleaved_times.csv` and against `GATE_T1_REPORT.md`'s printed C3/Stencil sequence:
**exact match**, confirming file-to-run mapping (`bench_stencil_C3_run{run_order_idx}.bin`) is
correct.

**What this ring does not contain, reported per this project's standing policy against inferring
missing measurements from a proxy:**
- No `spec_processed` field distinct from `spec_hits`/`spec_drops`/`spec_enqueues` -- work-item
  completion state (`hit`/`miss`/`migration_done`/`throttled`) lives only in the separate
  `specasync_worker_log` ring, which T1's harness (`tests/t1_gate3_interleaved.sh:98-100`) does
  not dump.
- No migration count or bytes-migrated fields -- not present in `specasync_batch_record` at all.
- No D1-D7 fields -- those belong to a *different* ring (`specasync_decomp_record`, Phase C
  only), never dumped by T1. The closest available proxy in this ring is the t0-t4 phase
  breakdown (`lock_acq` = t1-t0, `metadata` = t2-t1, `residency` = t3-t2, plus total t4-t0),
  used below in its place and explicitly labeled as such -- not presented as D1-D7.
- Per `exclusion_manifest.csv` row 26, the pre-Gate-4 bug that zeroed the `residency` phase
  (T2/T3 both stamped at the same point) was fixed before this ring existed; the non-zero
  residency values recovered here (residency dominates over metadata, as expected post-fix)
  confirm this data is post-fix, not a reproduction of that artifact.

## Task 1.1 — C3/Stencil-24K, high vs low cluster comparison

Cluster boundary taken directly from `GATE_T1_REPORT.md` Section 4 (clean 0.37s gap, no
intermediate values): high = wall_s >= 16.135s (8 runs, 16.32-17.18s), low = wall_s < 16.135s
(12 runs, 15.02-15.95s). Family size for Holm-Bonferroni = **12** (every counter this ring can
produce: 4 work-volume counters + 3 speculation-outcome counters + 1 overhead counter + 4
timing-phase-sum counters). Family stated up front per the task's own "fishing pass" caveat.

| Counter | median high | median low | delta% | p (MWU, two-sided) | Holm sig (m=12) |
|---|---:|---:|---:|---:|:---:|
| spec_enqueued | 2,553,013.5 | 1,968,546.0 | **+29.69%** | 1.588e-05 | **YES** |
| spec_drops | 682,847.0 | 1,269,632.0 | **-46.22%** | 1.588e-05 | **YES** |
| enqueue_overhead_ns_sum | 430,912,834.5 | 311,314,336.5 | **+38.42%** | 1.588e-05 | **YES** |
| lock_acq_ns_sum (t1-t0) | 638,275,730.5 | 463,333,878.0 | **+37.76%** | 1.588e-05 | **YES** |
| residency_ns_sum (t3-t2) | 6,769,028,698.0 | 5,764,805,142.0 | **+17.42%** | 1.588e-05 | **YES** |
| total_batch_latency_ns_sum (t4-t0) | 7,419,366,274.5 | 6,278,940,899.5 | **+18.16%** | 1.588e-05 | **YES** |
| metadata_ns_sum (t2-t1) | 4,676,106.5 | 3,894,672.0 | **+20.06%** | 1.111e-04 | **YES** |
| total_demand_faults | 3,236,751.5 | 3,239,486.0 | -0.08% | 4.735e-02 | no |
| mean_batch_size | 36.74 | 36.79 | -0.14% | 4.735e-02 | no |
| n_batches | 88,074.0 | 88,026.0 | +0.05% | 2.468e-01 | no |
| spec_hits | 346.0 | 366.0 | -5.46% | 1.813e-01 | no |
| max_batch_size | 173.5 | 169.5 | +2.36% | 8.767e-01 | no |

**Which counters separate the clusters:** the three direct speculation-queue counters
(`spec_enqueued`, `spec_drops`, `enqueue_overhead_ns_sum`) and the four batch-timing-phase sums
(`lock_acq`, `metadata`, `residency`, `total_batch_latency`) all separate cleanly (Holm-significant,
Cohen's d in 2.5-4.0 -- very large). **Which do not:** every raw work-volume counter
(`total_demand_faults`, `n_batches`, `mean_batch_size`, `max_batch_size`) and `spec_hits` are
statistically indistinguishable between clusters at the corrected threshold.

`total_demand_faults` and `mean_batch_size` have nominal Cohen's d around -1.15 to -1.19, but this
is an artifact of near-zero within-group variance (sd ~0.04-0.08% of the mean), not a meaningful
effect -- the raw delta is -0.08%, and the uncorrected p=0.047 does not survive Holm at m=12. Flagged
here so the large-looking d number isn't misread.

**Interpretation per the pre-registered decision rule:** the high cluster does **not** do more
work (faults, batches, batch sizes are identical within noise) -- it does the **same** work with
a materially different **speculative-queue outcome**: ~30% more successful enqueues, ~46% fewer
drops, and correspondingly ~20-38% more time in lock acquisition, metadata, residency, and total
batch latency. Per the task's own interpretation guide, "same work, running slower" points at
H2 or H3, not H1. The absence of any fault/batch-count separation is itself evidence against
H1 as specifically framed ("changing fault granularity") -- if allocation alignment shifted VA
block boundaries enough to matter, it should show up as a difference in how faults coalesce into
batches, and it does not.

**A caution on causal direction, stated explicitly because it matters for Part 4:** `spec_drops`
fires when `atomic_read(&g_specasync_queue_depth) >= SPECASYNC_MAX_QUEUE_DEPTH`
(`uvm_gpu_replayable_faults.c:339`) -- it is a race between the fault-arrival rate and the
workqueue worker's drain rate. This data cannot distinguish two structurally different stories
that produce the identical correlation pattern:
- **H3 (causal):** the high cluster does more speculative work (more successful enqueues), and
  that extra work is itself what consumes the extra lock/residency/wall time -- a genuine
  software-driven regime in the speculation path.
- **H1/H2 (common-cause):** some external factor (allocation alignment or GPU/CPU scheduling
  state) independently slows the whole batch-processing loop; a slower loop gives the workqueue
  worker more wall-clock slack between fault batches, which *incidentally* lets more items drain
  before the queue fills, so drops fall and enqueues rise as a **symptom**, not a cause.

These are observationally identical in this counter set. Nothing here adjudicates between them.

## Task 1.2 — C2/Stencil-24K, C1/Stencil, C0/Stencil

**Gap-structure check (objective criterion: largest gap must exceed the largest within-side gap
on both sides, with a minimum 4/20 split on the smaller side):**

| Config | range | largest gap | split (below/above) | max within-side gap | clean bimodal? |
|---|---|---:|---|---|:---:|
| C0/Stencil | [4.14, 4.25] | 0.030 | 19/1 | 0.020 / -- | no (single point, not a cluster) |
| C1/Stencil | [14.71, 16.11] | 0.910 | 19/1 | 0.130 / -- | no (single outlier -- matches `GATE_T1_REPORT.md`'s Tukey flag at 16.11) |
| C2/Stencil | [15.68, 18.15] | 0.640 | 19/1 | 0.330 / -- | no (single high point; second-largest gap of 0.33 does not produce a tight cluster -- the resulting "high" side's own internal spread, 0.64, exceeds the gap that would define it) |
| **C3/Stencil** | **[15.02, 17.18]** | **0.370** | **12/8** | **0.320 / 0.240** | **YES** (only config meeting the criterion) |

**C2 does not reproduce the clean two-cluster split.** Its distribution is right-skewed/heavy-tailed,
not bimodal in the discrete sense C3 shows.

**But the same mechanism operates continuously in C2.** Spearman correlation of wall_s against
each counter, n=20 per config (C0/C1 have `spec_enqueued/spec_drops/spec_hits/enqueue_overhead`
identically zero under `policy=0` -- `specasync_enqueue()` no-ops per
`uvm_gpu_replayable_faults.c:337`, matching `GATE_T4_REPORT.md`'s "C1 correctly shows 0/0/0" --
so those cells are correctly `nan`, not missing data):

| Counter | C0 (negative control) | C1 (weak positive) | C2 | C3 |
|---|---|---|---|---|
| total_demand_faults | rho=-0.09, p=0.71 | rho=0.12, p=0.61 | rho=-0.38, p=0.10 | rho=-0.45, p=0.05 |
| n_batches | rho=-0.07, p=0.76 | rho=0.13, p=0.58 | rho=0.57, p=0.009 | rho=0.22, p=0.36 |
| mean_batch_size | rho=0.06, p=0.81 | rho=-0.09, p=0.70 | rho=-0.68, p=0.001 | rho=-0.42, p=0.06 |
| spec_enqueued | n/a (always 0) | n/a (always 0) | **rho=0.985, p<0.001** | **rho=0.964, p<0.001** |
| spec_drops | n/a | n/a | **rho=-0.967, p<0.001** | **rho=-0.965, p<0.001** |
| enqueue_overhead_ns_sum | n/a | n/a | **rho=0.974, p<0.001** | **rho=0.940, p<0.001** |
| lock_acq_ns_sum | rho=0.35, p=0.13 | **rho=0.826, p<0.001** | **rho=0.979, p<0.001** | **rho=0.928, p<0.001** |
| residency_ns_sum | rho=0.38, p=0.10 | **rho=0.878, p<0.001** | **rho=0.971, p<0.001** | **rho=0.980, p<0.001** |
| total_batch_latency_ns_sum | rho=0.38, p=0.10 | **rho=0.867, p<0.001** | **rho=0.974, p<0.001** | **rho=0.986, p<0.001** |

**C2 (stdev 0.75, comparable to C3's 0.76) shows the identical signature as C3's high/low split,
just as a smooth continuum rather than two discrete clusters:** near-perfect correlation between
wall-time and spec_enqueued/spec_drops/enqueue_overhead, none with the raw work-volume counters.
**This satisfies the task's stated test: the mechanism is not oracle-specific** -- it reproduces
under C2's stride/depth=1 policy, not just C3's oracle policy. That in turn weakens a
speculation-content-specific reading (e.g., "the oracle trace lookup itself is slow/bimodal")
and is consistent with either H2 or a queue/scheduling-contention flavor of H3 that doesn't care
which prediction policy is active -- only that speculation is active at all.

**C1 (weak-positive control, zero speculation) still shows lock_acq/residency/total_latency
correlating with wall_s** (rho 0.83-0.88), while **C0 (negative control, prefetch-driven, near-zero
variance) does not** (rho 0.35-0.38, p>0.09). Read with caution: `residency_ns_sum` and
`total_batch_latency_ns_sum` are largely definitional components of wall-clock time once
demand-fault servicing dominates the run (C1-C3 are 3.5-4x C0's wall time), so part of this
correlation is closer to "the parts sum to the whole" than to a substantive causal signal. What
*is* informative: **C1 has no speculative queue at all, yet its core batch-service loop
(lock acquisition, residency decision) still varies enough to correlate with total wall time.**
That variance cannot come from the speculation path -- it points at something in the baseline
UVM fault-servicing loop itself (consistent with H1 or H2), which C2/C3 would then inherit and
additionally couple into their queue-drop dynamics via the common-cause mechanism described above.

## Preliminary hypothesis read

- **H1 (allocation alignment / fault-granularity)**: **disfavored, not dead.** No separation on
  fault count, batch count, or batch size anywhere (Task 1.1's headline finding) argues against
  the "changes fault granularity" mechanism as literally stated. It is not fully excluded because
  alignment could in principle affect cache/TLB timing without changing fault *counts* --
  Part 4.1's allocation-base logging remains the cheap, decisive test for that residual version of
  H1, per the task brief's own framing. That check has not been run (no GPU available in this
  session).
- **H2 (GPU/CPU thermal or scheduling state)**: **plausible, not confirmed.** This ring has no
  clock/thermal counters, so it cannot be directly tested here. The C1 finding (baseline
  batch-loop timing varies even with zero speculation active) is consistent with an external,
  platform-level noise source, which Part 3/4's clock/thermal logging would be needed to confirm
  or rule out.
- **H3 (genuine software regime in the speculation path)**: **the data is consistent with this,
  but cannot be distinguished from a queue-race symptom of H1/H2** (see the causal-direction
  caution in Task 1.1). The mechanism is real and reproducible (extends continuously into C2,
  not oracle-specific) but this session's telemetry cannot establish whether speculative work
  volume is a *cause* or a *downstream symptom* of whatever makes some runs slower.

**Net:** Part 1 alone does not settle the diagnosis. It does one useful thing decisively --
**it rules out the "different amount of work" reading of H1** -- and narrows the remaining
question to a two-way race between an external cause (H1-residual/H2) and an internal one (H3),
which Part 1's no-GPU telemetry cannot adjudicate further. The decisive next checks (allocation-base
logging, GPU clock/thermal logging under the interleaved ASLR protocol) both require Part 3's
platform bring-up.
