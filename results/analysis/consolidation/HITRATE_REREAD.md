# Gate C1 Step 4 — Re-reading the old hit-rate claims

The handoff flagged three reports whose mechanistic claims read `spec_hits` as a win
count. For each such claim this file gives:
- the quote;
- what it assumed;
- a proposed reinterpretation, given E0.9a-2 (`spec_hits` semantics) and E0/E0.5
  (the misaligned oracle).

**No report is edited.** These are proposals for SUPERSEDED_VALUES and the claim
documents.

## The two facts every reinterpretation rests on

1. **`spec_hits` is a 10 ms staleness-window counter over a 256-slot, overwrite-on-collision
   table.** It is not a win counter.
   - Source: `driver/src/specasync_telemetry.h:292`
     (`SPECASYNC_HIT_TABLE_SLOTS 256`), `:304` (`SPECASYNC_HIT_MAX_AGE_NS` = 10 ms),
     and the consume site `uvm_gpu_replayable_faults.c:2893-2907`, on the
     demand-fault path.
   - A "hit" is a demand fault that *occurred* on a page the worker had touched in
     the previous 10 ms and that had not been overwritten.
   - It collapses when predictions run ahead: 858 hits against 919,262 pages staged
     ahead of the servicing thread (`E09b.mech.stencil.C64096`).
   - (CS2-N7; AC-20.)
2. **The C3 oracle used in all three reports was misaligned.** Its trace was
   recorded per dispatch group and consumed per coalesced fault: about 11.7×
   (Stencil-24K) and about 2.1× (GraphBFS-23) over-consumption, with repeated wraps
   (E0 §7; E0.5; **PROSE-ONLY**). "Perfect trace-based prediction" was never true of
   any of these runs (AC-13).

A third, later fact removes the premise that the worker "never wins". With a correct
first-touch oracle, the worker makes 919,262 of Stencil's 1,125,000 distinct pages
resident ahead of the servicing thread at L = 4096, and 129,526 even at L = 1
(`E09b.mech.stencil.C64096`, `E09b.mech.stencil.C61`).

**Wall-clock results are unaffected** wherever they appear. They are measurements of
the configuration that was run. What changes is the *interpretation* of C3 as an
aligned upper bound (CS2-7, CS2-9) and every mechanistic reading of `spec_hits`.

---

## `GATE_T4_REPORT.md`

### T4-1 (§1)
> "**C3 (the oracle policy -- perfect trace-based prediction, prefetch off) is the real
> result: 0.02-0.25% hit rate on real workloads**, four orders of magnitude below the
> deterministic probe's 99.6%"

- **Assumed:**
  - (a) C3 predicted perfectly;
  - (b) `spec_hits ÷ enqueued` measures how often a correct prediction paid off;
  - (c) the probe's 99.6% is a comparable success rate.
- **Reinterpretation:**
  - The figure is the rate at which a **misaligned** prediction stream coincided with
    a demand fault on the same page within 10 ms. It says nothing about the success
    of correct predictions, because there were few correct predictions to make.
  - The probe comparison is also not like-for-like. The probe ran the *adjacent*
    policy on a serialized, one-fault-per-batch stream. On old code its high score
    was a zero-lead "self-hit" (`driver/PIPELINE_FIXES.md:60-62`; AC-14).
  - The numbers remain valid as counts of that event:
    - the clean-rep values are 0.0132% for Stencil
      (`T4hit.bench_stencil.rep1.corrected_marginal_clean`) and 0.2357% pooled for
      GraphBFS (`T4hit.graphbfs.pooled_reps1-4`);
    - the 15-rep sums (0.0195%, 0.2515%) are multi-counted and already superseded in
      the CSV (`…repALL_15_SUMMED.superseded_multicounted`).
- **Wall-clock:** none in this report. T1's C3-vs-C1 wall-clock stands as a
  measurement of the C3 configuration (CS2-9).

### T4-2 (§2)
> "the oracle policy predicts with perfect trace-based accuracy and still cannot get
> credited, because the predicted work item almost never finishes in time to matter."

- **Assumed:** perfect accuracy; that "credited" (a hit) is the measure of whether
  speculation mattered.
- **Reinterpretation:**
  - **Retire.** Accuracy was not perfect (AC-13).
  - "Credit" was a 10 ms-window coincidence (AC-20), which undercounts timely work
    that lands early.
  - Whether speculation "mattered" is answered by wall-clock and by
    `fault_already_resident`. When predictions are correct and early, the worker
    does finish in time (see the third fact above).
- **Kept:** the drop measurements (17.71–27.87% of enqueues dropped at queue depth
  1,024) are measurements of the C3 run. They are UNCHECKED, but not in dispute.

### T4-3 (§3)
> "real fault rates outrun the async worker's scheduling latency long before prediction
> accuracy becomes the bottleneck. The deterministic probe's ~99.6% hit rate was only
> achievable because the probe artificially throttled its own fault rate"

- **Assumed:** accuracy was not the bottleneck, because the oracle was perfect.
- **Reinterpretation:**
  - **Retire the ordering.** Accuracy was the first bottleneck: misaligned before
    E0.5, and index-drifted after it (CS2-N6).
  - The probe's rate throttling is real, but it is not what separates 99.6% from
    0.02%. The probe's predictions were correct by construction (adjacent policy on
    a stride-1 stream), and C3's mostly were not.
- **Wall-clock:** none.

### T4-4 (§4)
> "prediction can't help because the speculative worker's completion latency cannot keep
> pace with real-workload fault rates, so a hit-table entry is essentially always too
> late to be consumed … a second, independent reason speculative prefetching doesn't
> pay off in this architecture."

- **Assumed:** a hit-table entry being consumed is how speculation pays off.
- **Reinterpretation:**
  - **Retire** (R1).
  - Speculation pays off, where it does, through staged residency, which makes
    faults cheaper (D5, CS2-N4). With the prefetcher on and whole-block width, it
    also pays off through the prefetcher mapping staged regions (CS2-N3). Neither
    path requires a hit-table entry to be consumed.
  - E4 measured a wall-clock gain over C0 on Stencil (CS2-N1) in a configuration
    with 1,322 `spec_hits` (`E4.mech.stencil.C7-W512`).
- **Wall-clock:** the report's own statement "C3 … already shows no wall-clock
  benefit over C1" stands as a measurement of C3 (CS2-9).

---

## `GATE_A1_REPORT.md`

### A1-1 (Why this task existed)
> "Two structurally different explanations for the near-zero real-workload hit rate
> (`GATE_T4_REPORT.md`) were indistinguishable without a direct measurement …
> **(a) Race loss** … **(b) Backlog**"

- **Assumed:** the near-zero hit rate reflects the timing of *correct* predictions,
  so the only question was when items executed.
- **Reinterpretation:**
  - The hypothesis space omitted **(c) incorrect predictions** (the misaligned
    oracle, AC-13) and **(d) a counter that does not measure wins** (AC-20).
  - Both (c) and (d) were later established.
  - The (a)-versus-(b) discrimination is valid as a *queueing* measurement, but it
    answered a question whose premise was false.

### A1-2 (Result 3)
> "Processed/enqueued = 1.000000 … **the data supports explanation (a) exclusively.**
> There is no backlog population to attribute any fraction of the near-zero hit rate to."

- **Assumed:** (a) and (b) were exhaustive.
- **Reinterpretation:**
  - **Stands:** backlog is ruled out (processed == enqueued).
  - **Retire:** "(a) exclusively". Ruling out (b) does not establish (a) when (c)
    and (d) were never tested.
- **Kept, as measurements:** the median dispatch latencies are
  - T4 full-run: Stencil 9,438 µs, GraphBFS 10,607 µs;
  - T4 short-run: 3,198 µs and 2,580 µs.

  Evidence: `A1.T4.full_run.bench_stencil`, `A1.T4.full_run.bench_graph_bfs`,
  `A1.T4.short_run.*`. They are real, and relevant to CS2-N5: the handoff sits on the
  servicing path.

### A1-3 (closing verdict)
> "Near-zero real-workload hit rate is fully explained by (a) dispatch-latency race loss
> (500-2,000x the uncontended baseline), a mechanism shared by both benchmarks."

- **Assumed:** as A1-2.
- **Reinterpretation:** **retire** (R1). The latency *blowup* ratios (500–2,000×)
  are measurements of the worker under this load and stand as such (**UNCHECKED**
  in C1: the uncontended baseline is not in `worker_latency_summary.csv`). They do
  not explain the hit rate.

### A1-4 (Result 4)
> "this directly resolves the GraphBFS anomaly `GATE_T4_REPORT.md` could not: the
> earlier 'worker should usually win' prediction was based on the *uncontended* probe's
> dispatch latency"

- **Assumed:** the GraphBFS anomaly needed a timing explanation.
- **Reinterpretation:** GraphBFS's slightly higher `spec_hits` rate (0.2357% against
  0.0132%) fits its much smaller over-consumption ratio (~2.1× against ~11.7×;
  **PROSE-ONLY**). A less-misaligned oracle coincides more often. No timing
  explanation is needed, and the contended-latency comparison is not evidence for
  one.
- **Wall-clock:** A1 reports no arm-versus-arm wall-clock result.

---

## `GATE_B6_TASK2_A1_REPLICATION.md`

### B6-1 (Result 2b)
> "This does not overturn Gate A1's race-loss explanation for the near-zero real-workload
> hit rate (full-run … still shows a ~430x blowup, comfortably enough to lose the race"

- **Assumed:** A1's race-loss explanation.
- **Reinterpretation:**
  - **Stands, as measurement:** dispatch latency on the RTX 5070 Ti (595.84) is
    load-dependent and smaller than on the T4. Full-run medians are Stencil 2,306 µs
    and GraphBFS 2,275 µs (`A1.5070Ti.full_run.*`); short-run medians are 25.6 µs and
    60.3 µs (`A1.5070Ti.short_run.*`). This is consistent with a CPU-contention
    component.
  - The ratios 432.4×/438.5× and 4.9–11.5× are **UNCHECKED**: the uncontended
    baseline is not in the summary CSV.
  - **Retire:** the link to the hit rate.

### B6-2 (Result 3)
> "Gate A1's core finding — that the near-zero real-workload hit rate is explained by
> dispatch scheduling delay, not un-executed backlog — holds on this platform."

- **Reinterpretation:**
  - "not un-executed backlog" **stands** (replicated).
  - "explained by dispatch scheduling delay" is **retired**, as in A1-2 and A1-3.
- **Wall-clock:** B6 Task 2 reports no arm-versus-arm wall-clock result.

---

## Summary

| report | claim | verdict | what stands |
|---|---|---|---|
| GATE_T4 | T4-1 hit rate as success | reinterpret (coincidence rate of a misaligned stream) | the counts, and the clean-rep values in `t4_prefetch_off_hitrate_recovered.csv` |
| GATE_T4 | T4-2 "perfect accuracy, cannot get credited" | retire | the drop measurements |
| GATE_T4 | T4-3 "rates outrun latency before accuracy matters" | retire the ordering | — |
| GATE_T4 | T4-4 "hit-table entry always too late" as why speculation doesn't pay | retire | T1 wall-clock of C3 (CS2-9) |
| GATE_A1 | A1-1 hypothesis space (a)/(b) | reinterpret (incomplete: missing (c) and (d)) | the queueing measurement |
| GATE_A1 | A1-2 "(a) exclusively" | retire (backlog exclusion stands) | processed == enqueued; dispatch-latency medians |
| GATE_A1 | A1-3 "fully explained by race loss" | retire | latency blowup, as a measurement |
| GATE_A1 | A1-4 GraphBFS resolution | reinterpret (misalignment ratio) | — |
| B6 Task 2 | B6-1 does not overturn race loss | retire the link | the latency replication and CPU-contention reading |
| B6 Task 2 | B6-2 core finding holds | split: backlog exclusion stands, explanation retired | — |
