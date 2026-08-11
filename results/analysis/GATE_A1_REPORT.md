# Gate A1 — worker completion telemetry

## Why this task existed

`RATE_MISMATCH_VERIFICATION.md` Section 6: `spec_enqueued` means `queue_work()` returned
successfully, not that the item was ever dequeued and executed. Two structurally different
explanations for the near-zero real-workload hit rate (`GATE_T4_REPORT.md`) were
indistinguishable without a direct measurement of what fraction of queued items actually run:

- **(a) Race loss** — items are dequeued and executed, but the demand fault reaches the
  address first.
- **(b) Backlog** — items are queued and never dequeued at all under sustained load, going
  stale without executing.

## What was found: no counter existed

`tests/run_hit_probe.sh`'s own header defines `spec_processed` as "count of
`specasync_worker_log` records" — a **ring-derived count**, correct only because the
deterministic probe's 256 items never wrap the 131,072-slot ring
(`SPECASYNC_WORK_RING_SLOTS`). No kernel-side global counter existed. Real benchmarks wrap
this ring hundreds of times over (Stencil-24K: millions of enqueues/run), so a ring count
there would report a recent window, not a total. Confirmed during Gate A's probe run before
any source change (`GATE_A_report.md`, "Note carried into Task A1").

## Change made

Added three global `atomic_t` counters, incremented at the true completion/enqueue points
(immune to ring wraparound), and exposed read-only via debugfs:

- `g_specasync_processed` — incremented unconditionally in `specasync_worker_fn`'s `out:`
  path, which every branch (NULL policy, depth≥1 migration done/throttled, depth=0 hit/miss)
  funnels through.
- `g_specasync_enqueued` — incremented in `specasync_enqueue()` on successful `queue_work()`.
- `g_specasync_drops` — incremented at both existing `sa_rec->spec_drops++` sites (queue-depth
  cap, `kzalloc` failure).

All three are reset to 0 by `specasync_clear` (alongside the existing ring resets), so each
harness rep's read is a clean per-run total, not a running sum. `g_specasync_queue_depth`
(pre-existing, tracks live outstanding work) is deliberately **not** reset there.

**No stale-item counter was added.** Every dequeued item in `specasync_worker_fn` is
unconditionally processed to one of `NULL/HIT/MISS/MIGRATION_DONE/THROTTLED` — there is no
staleness check or expiry path in the source to instrument. This was verified by reading the
function in full before deciding not to add one, per the task's "if that path is
distinguishable in the source" condition — it is not.

New files: `results/debugfs/specasync_processed`, `specasync_enqueued`, `specasync_drops`
(decimal text, `debugfs_create_atomic_t`). New srcversion after rebuild:
**`24219FEEEB0B96D78E4E1AC`** (differs from the unmodified `8A2651D1CB32C7B239FB511`, as
expected for a source change). Verified against the deterministic probe first
(`spec_processed=256, spec_enqueued=256, spec_drops=0` — exact match with the pre-existing
ring-derived numbers at a scale where the ring doesn't wrap) before trusting it on real
workloads.

## Runs

`tests/t_a1_worker_completion.sh` (new script; does not modify `t4_prefetch_off_telemetry.sh`
or `gate3_favorable_run.sh`). C3 (oracle, depth=1, prefetch OFF) only. `specasync_clear`
called before every rep. Dumps both `specasync_log` and `specasync_worker_log` per rep.

- **Full-size** (`results/analysis/t_a1_worker/full_run/`): Stencil@24000, GraphBFS@23, n=5
  each — the published sizes. Worker ring wraps (window = last 131,071 records of each run).
- **Short-run non-wrapping cross-check** (`results/analysis/t_a1_worker/short_run/`):
  Stencil@2000, GraphBFS@18 (log2 vertices) — calibrated this session so
  `specasync_enqueued` stays under 131,072 per run (verified: `worker_ring_wrapped=no` for
  every rep, `window_records == processed` exactly). Gives a complete, non-windowed picture.

`tests/t_a1_analyze.py` parses both, cross-checks `processed == enqueued` per rep, and pools
the worker-ring records into a latency distribution.

## Result 1 — processed/enqueued ratio: **exactly 1.000000, every rep, both scales**

| run set | bench | reps | sum(processed) | sum(enqueued) | ratio | sum(drops) |
|---|---|---|---|---|---|---|
| short | GraphBFS-18 | 5 | 58,852 | 58,852 | **1.000000** | 16,681 |
| short | Stencil-2000 | 5 | 82,261 | 82,261 | **1.000000** | 88,490 |
| full | GraphBFS-23 | 5 | 1,917,595 | 1,917,595 | **1.000000** | 321,401 |
| full | Stencil-24000 | 5 | 11,513,176 | 11,513,176 | **1.000000** | 4,686,076 |

Every one of the 20 individual reps (asserted programmatically, not just on the sums) shows
`processed == enqueued` exactly. **100% of items that clear the queue-depth cap execute to
completion.** Nothing is queued and abandoned. **(b) Backlog is ruled out entirely** — there
is no population of never-executed work.

Drops (queue-depth-cap rejections at enqueue time, before an item ever enters the queue) are
real and substantial (17-52% of attempted enqueues depending on run), but that is a separate,
already-understood mechanism from `GATE_T4_REPORT.md` Section 2 — and orthogonal to the
processed/enqueued question this task answers.

## Result 2 — dispatch latency distribution (contended) vs the uncontended probe

`GATE_A_report.md` / this session's Gate A probe: uncontended dispatch (enqueue→dequeue)
≈5.6 µs, exec (dequeue→completion) ≈0.35 µs.

| run set | bench | dispatch median | dispatch p90 | exec median | exec p90 |
|---|---|---|---|---|---|
| short | GraphBFS-18 | 2,579.6 µs | 6,577.9 µs | 2.96 µs | 10.19 µs |
| short | Stencil-2000 | 3,198.0 µs | 3,804.2 µs | 2.82 µs | 3.09 µs |
| full | GraphBFS-23 | 10,607.0 µs | 12,068.9 µs | 10.09 µs | 12.73 µs |
| full | Stencil-24000 | 9,438.1 µs | 11,535.9 µs | 9.33 µs | 11.88 µs |

**Dispatch (queue-wait) latency under real-workload contention is 500-2,000x the uncontended
probe's ~5.6 µs** — climbing from single-digit microseconds to low-single-digit
*milliseconds*, and further under the full-size (higher-contention, more queue pressure)
runs than the short runs. Exec latency itself stays low (a few µs to ~10 µs), 10-30x the
uncontended 0.35 µs but two to three orders of magnitude smaller than the dispatch
component — **dispatch scheduling delay, not execution time, is where the race is lost.**

This is the number `RATE_MISMATCH_VERIFICATION.md` Section 3 had to substitute the idealized
probe for. Real demand-fault inter-arrival rates run 0.4-4.7M faults/sec (`GATE_T4_REPORT.md`)
— sub-microsecond to low-microsecond gaps between demand faults. A worker item that takes
2.6-10.6 ms (median) just to be *dispatched* is racing against a demand stream arriving
orders of magnitude faster; it essentially always loses, even though it always eventually
runs.

## Result 3 — verdict: (a) race loss, no (b) backlog, no meaningful mix

Processed/enqueued = 1.000000 in all 20 reps at two very different scales (13K-19K items/run
short-run, 380K-2.7M items/run full-run) settles this cleanly: **the data supports
explanation (a) exclusively.** There is no backlog population to attribute any fraction of
the near-zero hit rate to. The dispatch-latency distribution explains *why* the race is lost:
median dispatch time is 3-4 orders of magnitude above the uncontended baseline and comparable
to or exceeding the demand-fault inter-arrival time, so by the time a speculative item is
even *dequeued* — let alone completed — the same address has almost always already been
serviced by the demand path.

## Result 4 — GraphBFS vs Stencil: same mechanism, not the split `GATE_T4_REPORT.md` needed

`GATE_T4_REPORT.md` flagged GraphBFS as a case where the corrected rate-mismatch arithmetic
predicted the worker should usually win the race, yet hit rate was still ~0.25%. This run
finds **no qualitative difference** between the two benchmarks: both show the same
order-of-magnitude dispatch-latency blowup (GraphBFS 2.6-10.6 ms median vs Stencil 3.2-9.4 ms
median — the same regime, GraphBFS if anything slightly *lower* short-run and higher
full-run than Stencil, not systematically faster). **Both are dominated by the same
dispatch-latency race, not by a workload-specific mechanism** — this directly resolves the
GraphBFS anomaly `GATE_T4_REPORT.md` could not: the earlier "worker should usually win"
prediction was based on the *uncontended* probe's dispatch latency, not the *contended*
figure this task measured for the first time.

## Open item: magnitude discrepancy vs `GATE_T4_REPORT.md`'s per-run totals

This run's full-size `sum(enqueued)` over 5 reps (Stencil: 11.5M; GraphBFS: 1.9M) is well
below `GATE_T4_REPORT.md`'s single-run figures (Stencil: 50.96M; GraphBFS: 20.51M) — roughly
an order of magnitude per rep. Root-cause candidate, **not chased further here** (out of
this task's scope, flagged per this project's standing policy against silently absorbing
anomalies): `t4_prefetch_off_telemetry.sh`'s `run_c3_block` never calls `specasync_clear`
between its 15 reps, so successive `dump_after_run` snapshots of `specasync_log` (the batch
ring, same wraparound exposure as the worker ring this task fixed) are **cumulative**, not
per-rep — later reps' dump files contain earlier reps' records too. If the batch ring did not
wrap across those 15 reps, summing across all 15 dump files (rather than reading only the
last one) would overcount by roughly the same records multiple times. This would inflate
**absolute** counts but likely leaves the **hit_rate ratio** (hits/enqueued, both drawn from
the same over-counted batch records) approximately valid, since both numerator and
denominator scale together — so `GATE_T4_REPORT.md`'s headline 0.02-0.25% hit-rate
conclusion is not directly undermined by this observation, but its absolute enqueue/fault
counts should not be read as true per-run totals. This task's own counters (`g_specasync_*`,
reset via `specasync_clear` before every rep) do not have this exposure.

**Gate A1: processed == enqueued in all 20 reps at two scales — (b) backlog is ruled out.
Near-zero real-workload hit rate is fully explained by (a) dispatch-latency race loss
(500-2,000x the uncontended baseline), a mechanism shared by both benchmarks. Proceeding to
Task A2.**
