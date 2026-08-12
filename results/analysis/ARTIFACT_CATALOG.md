# Measurement artifact catalog, v3 (Task D, updated Phase 4 of the T4 GPU work block)

Six distinct measurement/methodology artifacts found and resolved over the course of
this project (five as of Task D; a sixth, below, surfaced by Task T2's cuFFT interleaved
rerun on the T4 instance). Two hypotheses were investigated and explicitly **rejected** as
not being real artifacts (listed at the end, for completeness -- not counted among the
six).

| # | Short name | Phase found | What was mis-measured | Naive reading it would have produced | Root cause | How caught | Reached a reported result? | Evidence file |
|---|---|---|---|---|---|---|---|---|
| 1 | **Oracle cursor desync** | Phase B.1 (Gate B) | Oracle (policy=4) hit rate on every real benchmark | "Oracle-perfect prediction gives zero benefit -- even a perfect predictor can't help, so speculation is fundamentally useless here" | Fault trace recorded once **per demand fault**, but oracle cursor consulted once **per service batch** -- a batch coalescing *k* faults consumes *k* trace entries of fault stream but advances the cursor by 1, permanently desyncing after the first coalesced batch | Deliberate Gate B re-investigation with a serialized-vs-coalesced positive-control probe (`tests/hit_probe.cu`); coalesced-probe hit rate jumped 0.0175 -> 0.4107 old-ko-vs-new-ko | **Yes** -- Phase B's original writeup (`results/phaseB/gate_reports/gate4_oracle.md`, `results/summary/cost_benefit.md`) reported oracle hit_rate=0.0000 on all 6 cells as a real finding before this was caught | `driver/PIPELINE_FIXES.md` (FIX-1), `results/phaseB1/GATE_B_diagnosis.md` |
| 2 | **ASLR address instability** | Phase B.1 (Gate B), found alongside #1 | Same oracle hit-rate cells as #1 -- an independent, compounding bug | Same naive reading as #1 ("oracle scores zero"), reinforcing the wrong conclusion even after a cursor fix alone | `cudaMallocManaged` returns a different base VA per process; trace collection records **absolute** VAs in one process, replay happens in a **fresh** process with a different base -> zero address overlap regardless of cursor sync | Same Gate B investigation; fixed by pinning the managed-memory base with `setarch -R` across trace-collection and replay, verified stable at `0x7fffce000000` | **Yes** -- compounded with #1 in the same originally-reported 0.0000 hit-rate cells | `driver/PIPELINE_FIXES.md` (FIX-2), `results/phaseB1/GATE_B_diagnosis.md` |
| 3 | **STREAM host-ordering noise** | Phase B.1 (Gate C) | STREAM wall-time delta for p1/p2/p3 vs p0 at 134M/268M element sizes | "SpecAsync speculative prefetch gives STREAM a real -8.8% speedup" (a false positive *in favor of* the technique) | Original runs were all-baseline-then-all-treatment (blocked ordering) on a shared EC2 instance; a slow host-noise drift or neighbor-tenant effect between the two blocks produced a spurious apparent speedup | Re-run interleaved (p0->p1->p5 alternating, 40 cycles/policy/size) plus a null-worker control (p5, enqueues but does zero lookup); the "speedup" flipped sign to a +1.5-2% slowdown that p1 and p5 (null) share almost exactly, proving it is a worker-presence artifact, not prediction | **Yes** -- the -8.8% "speedup" was in the original Phase B report before Gate C's interleaved re-run debunked it | `results/phaseB1/GATE_C_report.md` (C2) |
| 4 | **T2==T3 timer collapse ("metadata ~99% of service time")** | Phase B.1 (Gate C) | The per-batch phase breakdown (metadata vs residency) derived from T0-T4 timestamps | "Metadata/preprocessing is the dominant cost (~99% of service time) -- that's where async offload should target" (wrong bottleneck attribution) | `T2` and `T3` are both set to `ktime_get_ns()` immediately after `service_fault_batch_dispatch()` returns (same two adjacent lines), making `phase_residency = T3-T2` identically zero; the "metadata" window (T1->T2) actually brackets the *entire* dispatch call including residency decision and migration-push construction, not just metadata lookup | Source-level inspection of `service_fault_batch()`'s timer placement, cross-checked against Phase B telemetry showing `metadata_median == lat_median` for every benchmark (residency always exactly 0) | **Yes** -- "metadata ≈ 99% of service time" was reported as a real phase-breakdown finding before Gate C's source inspection caught the timer bug | `results/phaseB1/GATE_C_report.md` (C3) |
| 5 | **`ring_read_binary` byte-offset drift** | Phase C | Decomposition-record readout past slot ~1170 in any long Phase C run (`decomp_*.bin` -> `.csv`) | Not an obviously-broken read: it would have silently produced garbled/shifted D1-D6 sub-phase values for a large fraction of batches in every workload with >1170 records (Stencil-24K, GraphBFS-23, Sweep-16K/24K all exceed this), read as noisy-but-plausible decomposition data rather than as corrupted | `ring_read_binary` (`specasync_debugfs.c`) returned `to_copy` bytes to the caller while only actually writing `floor(to_copy/record_size)*record_size` bytes via `copy_to_user` -- the difference silently accumulated in `*ppos`, reaching exactly 32 bytes of drift by slot 1170 and misaligning every subsequent record boundary | Phase C's own **same-session** G1 accounting-closure gate (`D1+D2+svc+D6+D7 ≈ total` within ±2%) flagged a small (<0.06%) batch failure rate; tracing those specific failures back to the parser led to the byte-offset bug, fixed, and the run re-verified before any report was written | **No** -- caught by an automated gate check within the same Phase C session, before any garbled numbers reached `PHASEC_REPORT.md` or any downstream figure/statistic. This is the one artifact in the catalog that was caught proactively rather than reactively (after being published), which is the point of listing it separately: the project's gate-check discipline worked as designed here | `results/phaseC/PHASEC_REPORT.md` ("Root-Cause Note: ring_read_binary Fix", "G1 — Accounting Closure") |
| 6 | **cuFFT hit-rate blocked-protocol outlier (25.47%)** | Phase B (pre-fix sweep), caught at Task T2 (T4 GPU work block) | cuFFT hit rate at policy=2 (stride), depth=0, prefetch ON, size=67,108,864 (`phaseB_telemetry.csv`) | "SpecAsync's stride predictor gets real traction on cuFFT's large-stride access pattern -- the one real workload where the hit-table mechanism demonstrably works, distinct from the near-zero rates on Stencil/GraphBFS/SGEMM/STREAM" (a false positive suggesting cuFFT was a favorable case for the mechanism) | The 25.47% figure was measured in a **single, non-interleaved, uncontrolled run** during Phase B's pre-fix sweep (`CUFFT_PROVENANCE.md`: "cuFFT ran on the T4 only during the pre-fix Phase B sweep") -- structurally the same failure mode as artifact #3 (STREAM host-ordering noise): a blocked/single-shot measurement with no interleaving to control for host noise, drift, or a favorable transient | Task T2's interleaved rerun (15 clean reps at the exact matching policy/depth/prefetch/size configuration) measured 4.07% aggregate hit rate -- a sixth of the legacy figure -- with no accompanying wall-clock benefit at any of the three tested sizes | **Yes** -- the 25.47% figure was already in circulation in `phaseB_telemetry.csv` and cited in `CUFFT_PROVENANCE.md`'s own provenance audit (correctly, as a real T4/595.71.05 measurement) before Task T2's controlled rerun showed it does not reproduce. Unlike artifact #5, this was not caught by an automated gate -- it required a dedicated interleaved rerun task to surface, which is exactly why `CUFFT_PROVENANCE.md` flagged the cell as needing revisiting rather than treating the number as settled | `results/analysis/GATE_T2_REPORT.md`, `results/figures/CUFFT_PROVENANCE.md`, `results/figures/exclusion_manifest.csv` (cuFFT/67108864/p2/hit_rate row) |

## Decision point: does the GATE_T4_REPORT.md rate-arithmetic error belong in this catalog?

**Flagged, not resolved — the manuscript author's call.** Part 2 verification of
`GATE_T4_REPORT.md` Section 2 (`results/analysis/RATE_MISMATCH_VERIFICATION.md`) found that
its headline "0.4-4.7 million faults/second" rate figure divided the fault count *summed
across all 15 repetitions* by *one repetition's* wall-clock duration — inflating the true
rate by ~15x (corrected: ~0.3M/s Stencil-24K, ~0.03M/s GraphBFS-23). This is different in
kind from artifacts #1-6 above: none of those involved a wrong *measurement* — every one is
a real value, correctly recorded, that was then misinterpreted, mislabeled, or contaminated
by an experimental-protocol confound. This one is an **arithmetic mistake made downstream of
correct measurements** (the underlying `total_demand_faults` and wall-clock figures are both
individually correct and cross-checked; the error is purely in how they were combined into a
rate). Two ways to place it:

- **Option A — add as artifact #7, a new category ("analysis arithmetic error," distinct
  from "measurement artifact").** Consistent with this catalog's existing purpose (a
  complete record of every debunked number that once looked real), and it did reach a
  reported result before being caught (`GATE_T4_REPORT.md` stated it as a finding). Cost:
  stretches the catalog's implicit definition ("measurement/methodology artifact") to cover
  pure arithmetic, which arguably belongs to a different failure class entirely (no rerun,
  no new data, no protocol fix — just redoing the division correctly).
- **Option B — do not add it here; cite it in the methodology/limitations section as an
  argument for independent verification passes.** The catalog's stated purpose is measurement
  artifacts (wrong data or wrong interpretation of real data collected under a flawed
  protocol); this is neither — it's a bookkeeping error in aggregation, closer to a
  proofreading category than a methodology finding. Its natural home is a sentence in the
  paper's methodology section noting that a dedicated verification pass (this project's Part
  2 practice) caught an aggregation error the original analysis missed, as a concrete
  argument for why the practice is worth keeping, rather than a numbered catalog entry
  alongside genuine measurement artifacts.

Both preserve the finding somewhere load-bearing; neither loses it. This ledger has no basis
to prefer one over the other — it's an editorial/taxonomic choice about what the catalog is
*for*, not a factual question. Recommendation deferred to the manuscript author.

## Hypotheses investigated and rejected (not counted among the six)

These were suspected artifacts that, on investigation, turned out **not** to be real —
included here so the catalog documents the negative results too, not just the confirmed
bugs.

| Hypothesis | Why suspected | Verdict | Evidence |
|---|---|---|---|
| Hit-accounting counter is broken (`spec_hits` never fires) | Near-zero hit rates on every real benchmark looked like a broken counter | **REJECTED** -- a deterministic positive control (`tests/hit_probe.cu`, serialized, prefetch off) scored 254/256 = 99.2%; the counter is sound. Near-zero hit rates on real benchmarks are a real interaction with the UVM prefetcher + per-batch (not per-fault) prediction, not instrumentation failure | `driver/PIPELINE_FIXES.md` (FIX-0), `results/phaseB1/GATE_A_report.md` |
| Oracle replay is O(n²) in trace length | Phase B's original sweep reported the oracle "up to 100x slower"; a quadratic scan was the leading hypothesis | **REJECTED** -- `specasync_oracle_next_addr()` is an O(1) atomic post-increment cursor with modulo wraparound; no per-fault linear scan exists anywhere in the replay path. If a real slowdown exists, it is not this | `results/phaseB1/GATE_B_diagnosis.md` (H1) |
