# Measurement artifact catalog, v4 (updated Gate B7 correction pass)

Eleven distinct measurement/methodology artifacts found and resolved over the course of
this project (six as of the T4 GPU work block's Phase 4; five more, below, surfaced by the
Gate A1/A2/B correction passes and the Gate B7 cross-platform block). Two hypotheses were
investigated and explicitly **rejected** as not being real artifacts (listed at the end,
for completeness -- not counted among the eleven).

| # | Short name | Phase found | What was mis-measured | Naive reading it would have produced | Root cause | How caught | Reached a reported result? | Evidence file |
|---|---|---|---|---|---|---|---|---|
| 1 | **Oracle cursor desync** | Phase B.1 (Gate B) | Oracle (policy=4) hit rate on every real benchmark | "Oracle-perfect prediction gives zero benefit -- even a perfect predictor can't help, so speculation is fundamentally useless here" | Fault trace recorded once **per demand fault**, but oracle cursor consulted once **per service batch** -- a batch coalescing *k* faults consumes *k* trace entries of fault stream but advances the cursor by 1, permanently desyncing after the first coalesced batch | Deliberate Gate B re-investigation with a serialized-vs-coalesced positive-control probe (`tests/hit_probe.cu`); coalesced-probe hit rate jumped 0.0175 -> 0.4107 old-ko-vs-new-ko | **Yes** -- Phase B's original writeup (`results/phaseB/gate_reports/gate4_oracle.md`, `results/summary/cost_benefit.md`) reported oracle hit_rate=0.0000 on all 6 cells as a real finding before this was caught | `driver/PIPELINE_FIXES.md` (FIX-1), `results/phaseB1/GATE_B_diagnosis.md` |
| 2 | **ASLR address instability** | Phase B.1 (Gate B), found alongside #1 | Same oracle hit-rate cells as #1 -- an independent, compounding bug | Same naive reading as #1 ("oracle scores zero"), reinforcing the wrong conclusion even after a cursor fix alone | `cudaMallocManaged` returns a different base VA per process; trace collection records **absolute** VAs in one process, replay happens in a **fresh** process with a different base -> zero address overlap regardless of cursor sync | Same Gate B investigation; fixed by pinning the managed-memory base with `setarch -R` across trace-collection and replay, verified stable at `0x7fffce000000` | **Yes** -- compounded with #1 in the same originally-reported 0.0000 hit-rate cells | `driver/PIPELINE_FIXES.md` (FIX-2), `results/phaseB1/GATE_B_diagnosis.md` |
| 3 | **STREAM host-ordering noise** | Phase B.1 (Gate C) | STREAM wall-time delta for p1/p2/p3 vs p0 at 134M/268M element sizes | "SpecAsync speculative prefetch gives STREAM a real -8.8% speedup" (a false positive *in favor of* the technique) | Original runs were all-baseline-then-all-treatment (blocked ordering) on a shared EC2 instance; a slow host-noise drift or neighbor-tenant effect between the two blocks produced a spurious apparent speedup | Re-run interleaved (p0->p1->p5 alternating, 40 cycles/policy/size) plus a null-worker control (p5, enqueues but does zero lookup); the "speedup" flipped sign to a +1.5-2% slowdown that p1 and p5 (null) share almost exactly, proving it is a worker-presence artifact, not prediction | **Yes** -- the -8.8% "speedup" was in the original Phase B report before Gate C's interleaved re-run debunked it | `results/phaseB1/GATE_C_report.md` (C2) |
| 4 | **T2==T3 timer collapse ("metadata ~99% of service time")** | Phase B.1 (Gate C) | The per-batch phase breakdown (metadata vs residency) derived from T0-T4 timestamps | "Metadata/preprocessing is the dominant cost (~99% of service time) -- that's where async offload should target" (wrong bottleneck attribution) | `T2` and `T3` are both set to `ktime_get_ns()` immediately after `service_fault_batch_dispatch()` returns (same two adjacent lines), making `phase_residency = T3-T2` identically zero; the "metadata" window (T1->T2) actually brackets the *entire* dispatch call including residency decision and migration-push construction, not just metadata lookup | Source-level inspection of `service_fault_batch()`'s timer placement, cross-checked against Phase B telemetry showing `metadata_median == lat_median` for every benchmark (residency always exactly 0) | **Yes** -- "metadata ≈ 99% of service time" was reported as a real phase-breakdown finding before Gate C's source inspection caught the timer bug | `results/phaseB1/GATE_C_report.md` (C3) |
| 5 | **`ring_read_binary` byte-offset drift** | Phase C | Decomposition-record readout past slot ~1170 in any long Phase C run (`decomp_*.bin` -> `.csv`) | Not an obviously-broken read: it would have silently produced garbled/shifted D1-D6 sub-phase values for a large fraction of batches in every workload with >1170 records (Stencil-24K, GraphBFS-23, Sweep-16K/24K all exceed this), read as noisy-but-plausible decomposition data rather than as corrupted | `ring_read_binary` (`specasync_debugfs.c`) returned `to_copy` bytes to the caller while only actually writing `floor(to_copy/record_size)*record_size` bytes via `copy_to_user` -- the difference silently accumulated in `*ppos`, reaching exactly 32 bytes of drift by slot 1170 and misaligning every subsequent record boundary | Phase C's own **same-session** G1 accounting-closure gate (`D1+D2+svc+D6+D7 ≈ total` within ±2%) flagged a small (<0.06%) batch failure rate; tracing those specific failures back to the parser led to the byte-offset bug, fixed, and the run re-verified before any report was written | **No** -- caught by an automated gate check within the same Phase C session, before any garbled numbers reached `PHASEC_REPORT.md` or any downstream figure/statistic. This is the one artifact in the catalog that was caught proactively rather than reactively (after being published), which is the point of listing it separately: the project's gate-check discipline worked as designed here | `results/phaseC/PHASEC_REPORT.md` ("Root-Cause Note: ring_read_binary Fix", "G1 — Accounting Closure") |
| 6 | **cuFFT hit-rate blocked-protocol outlier (25.47%)** | Phase B (pre-fix sweep), caught at Task T2 (T4 GPU work block) | cuFFT hit rate at policy=2 (stride), depth=0, prefetch ON, size=67,108,864 (`phaseB_telemetry.csv`) | "SpecAsync's stride predictor gets real traction on cuFFT's large-stride access pattern -- the one real workload where the hit-table mechanism demonstrably works, distinct from the near-zero rates on Stencil/GraphBFS/SGEMM/STREAM" (a false positive suggesting cuFFT was a favorable case for the mechanism) | The 25.47% figure was measured in a **single, non-interleaved, uncontrolled run** during Phase B's pre-fix sweep (`CUFFT_PROVENANCE.md`: "cuFFT ran on the T4 only during the pre-fix Phase B sweep") -- structurally the same failure mode as artifact #3 (STREAM host-ordering noise): a blocked/single-shot measurement with no interleaving to control for host noise, drift, or a favorable transient | Task T2's interleaved rerun (15 clean reps at the exact matching policy/depth/prefetch/size configuration) measured 4.07% aggregate hit rate -- a sixth of the legacy figure -- with no accompanying wall-clock benefit at any of the three tested sizes | **Yes** -- the 25.47% figure was already in circulation in `phaseB_telemetry.csv` and cited in `CUFFT_PROVENANCE.md`'s own provenance audit (correctly, as a real T4/595.71.05 measurement) before Task T2's controlled rerun showed it does not reproduce. Unlike artifact #5, this was not caught by an automated gate -- it required a dedicated interleaved rerun task to surface, which is exactly why `CUFFT_PROVENANCE.md` flagged the cell as needing revisiting rather than treating the number as settled | `results/analysis/GATE_T2_REPORT.md`, `results/figures/CUFFT_PROVENANCE.md`, `results/figures/exclusion_manifest.csv` (cuFFT/67108864/p2/hit_rate row) |
| 7 | **Ring saturation without wraparound** | T4 GPU work block, Task T4 (`t4_prefetch_off_telemetry.sh`'s pre-fix `run_c1/c2/c3_block`) | Absolute demand-fault/enqueue/drop/hit counts read from `specasync_log` across 15 reps per config | "Real workloads sustain 70.6M (Stencil-24K) / 24.9M (GraphBFS-23) demand faults across 15 independent repetitions" -- treating 15 separately-dumped `.bin` files as 15 independent per-rep totals | `specasync_log` is a fixed 131,071-record ring that was never cleared between reps (bug in the per-rep loop, since fixed). Once full, it **stops recording new activity rather than wrapping**, so every dump taken after saturation is a byte-for-byte-identical copy of the same frozen snapshot, not that rep's own data. Stencil-24K saturates during rep 2 of 15 (14 of 15 kept-rep dump files identical; only 2 distinct observations exist); GraphBFS-23 saturates during rep 5 of 15 (11 of 15 identical; 5 distinct observations exist) | First flagged as an "open item" in `GATE_A1_REPORT.md` (its own properly-cleared-per-rep counters showed roughly an order-of-magnitude discrepancy against `GATE_T4_REPORT.md`'s totals); confirmed and precisely quantified by direct `.bin` inspection in `GATE_T4_REPORT.md`'s 2026-08-12 correction note; a later correction pass (2026-08-13) parsed the surviving pre-saturation `.bin` files directly to derive a genuinely clean per-rep fault rate | **Yes** -- the inflated absolute counts, and a derived rate built from them (see artifact #8), were both published as findings in `GATE_T4_REPORT.md` before being caught | Left the ratio-based `hit_rate` conclusion valid (numerator and denominator over-count together, so the ratio is unaffected) but corrupted every absolute-count-derived figure, most importantly the fault-rate calculation feeding artifact #8 | `GATE_T4_REPORT.md` (correction note + updated Section 2), `GATE_A1_REPORT.md` (open item + Result 2) |
| 8 | **Rate-arithmetic 15x aggregation error** | T4 GPU work block, Part 2 verification (`RATE_MISMATCH_VERIFICATION.md`) | The "faults/second" rate derived from `GATE_T4_REPORT.md` Section 1's totals | "Real workloads sustain 0.4-4.7 million demand faults/second, so the speculative worker essentially never wins the race" -- an overstated mismatch (the qualitative direction happened to still be correct, by luck, not by a sound calculation) | Divided the fault total **summed across all 15 repetitions** by **one repetition's** wall-clock duration (the same 15s/58s figures the surrounding sentence itself cited as the "15-58 seconds of wall-clock time" range) instead of the cumulative 15-rep wall-clock time -- inflated the rate by very close to 15x, the repetition count | A dedicated Part 2 verification pass (`RATE_MISMATCH_VERIFICATION.md`) reconstructed the dispatch-granularity argument from source and cross-checked totals against `GATE_T4_REPORT.md` before recomputing the rate independently | **Yes** -- published in `GATE_T4_REPORT.md` Section 2 as a quantified mechanism finding ("essentially never wins the race") before being caught. This entry resolves the "decision point" a prior version of this catalog left open (whether an arithmetic error, as opposed to a measurement/protocol confound, belongs here) -- given it reached a published result and compounds with artifact #7 on the exact same figure, it is catalogued rather than left as a methodology-section footnote | This "corrected" rate was **itself still ~15x too high**, since its numerator inherited artifact #7's ring-duplication problem, not yet known when this correction was written -- doubly corrected in a later pass (2026-08-13, see `GATE_T4_REPORT.md`/`GATE_A1_REPORT.md`'s current sections) | `RATE_MISMATCH_VERIFICATION.md` (intermediate correction, now itself superseded), `GATE_T4_REPORT.md`/`GATE_A1_REPORT.md` (current, doubly-corrected figures) |
| 9 | **Ceiling units mismatch** | This session, Gate B7 cross-platform block (`CEILING_BASIS_VERIFICATION.md`) | End-to-end pipelining ceiling (`GATE_T3_REPORT.md`'s 6-workload extension, and Gate B7's 5070 Ti rerun, which deliberately copied the same formula) | "Up to 19% (T4) / 29% (RTX 5070 Ti) of wall-clock time could be recovered by hiding D1+D2" -- and, downstream, a false cross-platform divergence ("this platform's ceiling runs notably higher than the T4's at large sizes") | Summed the dispatch-window numerator across all 5 trials while dividing by only **one** trial's median wall-clock -- a units mismatch that inflates the ratio by a factor mechanically close to the trial count (~5x) | A verification pass requested to test a *different* hypothesis (batch overlap inflating the numerator -- refuted directly, 0/N adjacent batches overlap on either platform) instead found the formula produces **mathematically impossible >100% window/wall-clock fractions** on 4 of 6 T4 workloads under a span-based numerator -- proof the formula was wrong, not merely suspiciously large | **Yes** -- published in `GATE_T3_REPORT.md` and this session's `GATE_B7_5070TI_PHASEC.md`, including a specific cross-platform "diverges at the high end" finding that did not survive the correction (the corrected convention **reverses** it: the T4 runs higher than the 5070 Ti at 5 of 6 workloads) | Inflated every published ceiling ~5x on both platforms; the cross-platform divergence finding was entirely an artifact of this bug, not a real platform difference | `CEILING_BASIS_VERIFICATION.md`, `GATE_T3_REPORT.md`/`GATE_B7_5070TI_PHASEC.md`/`PIPELINING_CEILING.md`/`CLAIM_SCOPE.md` correction notes |
| 10 | **`setarch -R` regime effect** | This session, Gate A2/A2b | `ASLR_OFF` wall-clock variance and speculative-volume variance, Stencil-24K, oracle policy (C3) | Not a false conclusion in the usual sense -- a **methodological property of oracle-based evaluation** that, if unstated, would let a reader assume T1's `setarch -R`-pinned results reflect general platform noise rather than a regime specifically tied to running the speculative pipeline with a fixed allocation address | Oracle replay (policy=4) requires a fixed `cudaMallocManaged` base address for trace-address alignment across collect/replay sessions, so every oracle-based run in this project necessarily uses `setarch -R`. `GATE_A2B_SETARCH_REGIME.md` (pre-registered, C1-vs-C3 split test) found the `ASLR_ON`/`ASLR_OFF` wall-clock and speculative-volume variance difference is **absent in C1** (no speculation, p=0.970 location, p=0.179 spread) but **present and large in C3** (oracle): Levene's test stat=10.659, p=0.0043, variance ratio (OFF/ON) = **522.7x**, reproducing `GATE_A2_REPORT.md`'s original finding closely on an independent n=10/arm sample two days later | Deliberately investigated, not stumbled into -- `GATE_A2_REPORT.md` first flagged the ASLR-correlated volume difference as "a secondary, unplanned observation... outside this task's scope to chase further"; `GATE_A2B_SETARCH_REGIME.md` was pre-registered specifically to test whether it was general (would implicate T1) or speculation-specific (would not) | **No** -- caught by design, before any claim depending on the distinction was published. Listed here as a methodological property to disclose, not a bug that produced a wrong number | T1 (platform-of-record) is not contaminated by a general paging artifact (C1's null result rules that out), but its reported run-to-run variance should be read as characteristic of the `ASLR_OFF` speculative regime specifically, not general instance noise -- a manuscript methods/limitations sentence, not a retraction | `GATE_A2_REPORT.md`, `GATE_A2B_SETARCH_REGIME.md` |
| 11 | **Host memory leak as a run-order confound** | This session, Gate B6 (`HOST_MEMORY_LEAK_5070TI.md`) | `MemAvailable` across any session of repeated (module reload + CUDA run) cycles on the RTX 5070 Ti / driver 595.84 host | Not a false conclusion produced yet -- a **candidate, unconfirmed contributor** to an already-published finding (B5's run-order wall-clock drift, rho=0.548, p=0.0123) that, if not flagged, could be mistaken for a settled platform property rather than a live open question | Reproducible ~244MB leaked per (module-reload + CUDA-run) cycle, confirmed to reproduce at the same rate on the **stock, unpatched** NVIDIA 595.84 driver (not a SpecAsync defect -- an upstream driver issue), monotonic across a session (not per-run noise), lands in `/proc/meminfo`'s unaccounted pool (not reclaimable via `drop_caches`) | A dedicated characterization pass (4 conditions x n≥5 cycles, batch-overlap-style controlled comparison against the stock driver) run specifically because Task 4's cuFFT rerun hit a near-OOM condition mid-session -- the leak was severe enough to force a stop-and-characterize before continuing, not found by a passive audit | **Partially** -- the leak itself was not previously reported as a finding (it caused an operational stop, not a wrong number in a report), but B5's drift finding it may help explain was already published without this candidate mechanism attached | Flagged explicitly as **candidate, not proven** -- Task 3 (this platform's non-reproduction of B5's drift) is equally consistent with plain session-to-session noise; the leak explanation is offered alongside, not in place of, that simpler account | `HOST_MEMORY_LEAK_5070TI.md`, `GATE_B6_TASK3_A2_REPLICATION.md` (addendum) |

## Second occurrence of artifact #7 (Gate B9, 2026-08-15)

**The fix applied to `t4_prefetch_off_telemetry.sh` addressed one script; the exposure is
architectural.** Any script that reads `specasync_log` (or `specasync_decomp_log`, or
`specasync_worker_log` -- all three are the same 131,072-slot, drop-on-full ring design) a
single time at the end of a run, rather than clearing and re-reading periodically, inherits
this artifact regardless of whether the per-rep-clear bug that caused the *first* occurrence
is present or not. `tests/t_b9_task2_mechanism.sh` (Gate B9 Task 2, C1-vs-C3 mechanism
instrumentation at ~1.08x oversubscription, N=48000/iters=20) did clear the ring correctly
between every rep -- and still saturated **within every single one of its 20 kept runs**,
because a single rep's fault volume at this oversubscription level vastly exceeds ring
capacity on its own; no cross-rep contamination was needed to trigger it this time.

Two new details this occurrence adds, not present in the original:

1. **Different arms saturating at the same record count is not evidence of equal
   coverage.** C1 and C3 both hit exactly 131,071 records in all 20/20 runs -- but C1's run
   took ~161s and C3's took ~69s, so the captured window covers **2.8% of C1's run** versus
   **7.9% of C3's run** (measured directly from each snapshot's `t0_ns`/`t4_ns` span against
   the run's wall-clock). A naive between-arm comparison of ring-derived totals (here,
   `total_demand_faults`: C3 appeared to have +11.5% more than C1) silently compares
   different *fractions* of two runs of very different length, not the same slice of
   comparable work. The direction of the apparent difference cannot be trusted without first
   establishing the arms are looking at the same relative window, which in general they are
   not once either ring saturates.
2. **Not all rings saturate the same way, and the ones that don't can point the opposite
   direction.** `specasync_fault_trace` (the demand-fault address ring used for the
   thrash/re-migration proxy) is a genuine circular *overwrite* buffer with no drop-on-full
   behavior -- it holds the **trailing** window of a run once its 1,048,576-slot capacity is
   exceeded, which it was in all 20/20 runs here too. So in the same Gate B9 Task 2 run, the
   batch/decomp/work-ring metrics reflected the first ~3-8% of each run and the trace-ring
   metric reflected the last portion -- two telemetry sources from the *same* run, covering
   *disjoint* and *non-overlapping* time windows, neither comparable to the other nor to the
   run as a whole.

Caught before any figure was published (Task 2's demand-fault comparison was flagged and
withheld pending a redesigned periodic-drain harness rather than reported), but it is the
second time this exact architectural gap has produced a plausible-looking, wrong headline
number from otherwise-correct per-rep instrumentation. See `GATE_B9_OVERSUB_MECHANISM.md`
(once written) for the drain-harness redesign and its validation.

## Decision point (RESOLVED 2026-08-13): does the rate-arithmetic error belong in this catalog?

**Resolved: yes, as artifact #8.** This entry originally deferred the choice between adding
the `GATE_T4_REPORT.md` rate-arithmetic error as a new "analysis arithmetic error" category
(Option A) or leaving it as a methodology-section footnote only (Option B), on the grounds
that it was "different in kind" from artifacts #1-6 -- a bookkeeping error downstream of
correct measurements, not a wrong measurement itself. Two things changed the calculus:
first, that same figure turned out to be wrong **twice**, compounding with the
independently-discovered artifact #7 (ring saturation) on the exact same headline number --
a single footnote could not represent that compounding relationship as clearly as two linked
catalog entries can. Second, this pass added three more entries (9, 10, 11) that also don't
fit the original "wrong measurement, correctly recorded but misinterpreted" mold cleanly
(#9 is also a pure downstream arithmetic error; #10 is not an error at all, just a
methodological property worth disclosing) -- the catalog's working definition has already
broadened past the original six's shape. Kept in, not deferred further.

## Synthesis: what artifacts #7-9 have in common

**Artifacts #7, #8, and #9 share a pattern worth stating explicitly: each was caught by an
independent verification pass, not by the original analysis that produced the number, and
each inflated an absolute or derived headline figure while leaving a *ratio* computed from
the same underlying data intact.** #7's ring duplication left `hit_rate` (hits/enqueued)
valid while corrupting absolute fault/enqueue counts. #8's denominator error left the
underlying fault and wall-clock totals individually correct while corrupting the rate
computed from them. #9's trial-aggregation error left D1+D2 *share* (which uses the same
aggregation on both its own numerator and denominator, so the units-mismatch factor cancels)
valid while corrupting the window/wall-clock ratio and everything downstream of it. In every
case, none of these were caught by the original analysis, or by peer review of the
resulting report -- each required someone to come back with a specific, adversarial question
("does this number survive a sanity bound?", "what happens if I recompute this from a
different angle?") rather than trusting a plausible-looking result.

**A sharper lesson sits inside artifact #8 specifically, worth stating on its own: a
verification pass that reuses an upstream aggregation inherits that aggregation's defects.**
`RATE_MISMATCH_VERIFICATION.md` was itself a dedicated verification pass -- it caught and
fixed the 15x denominator error carefully, cross-checking its inputs against
`GATE_T4_REPORT.md`'s published totals before recomputing. But "cross-checking against the
published totals" was exactly the mistake: those totals were themselves artifact #7's
ring-duplicated sum, and a match against a wrong number is not validation. The verification
pass corrected the arithmetic it was looking for (the division) while silently carrying
forward the one input it never re-derived from source (the numerator) -- so its own
"corrected" rate was still wrong, by nearly the same order of magnitude the first error was,
and stayed that way until a second pass parsed the raw `.bin` ring dumps directly instead of
trusting any prior report's aggregate figure, including the verification pass's own. **The
lesson is not "verify twice" -- two independent passes both reused the same corrupted
upstream number and both produced a plausible-looking result.** It is that a verification
pass only protects against the specific failure mode it was designed to catch; any input it
takes as given, rather than re-deriving from the rawest available source, can carry a
different, unrelated defect straight through the correction. This is the concrete
argument for verification passes as methodology, not just as cleanup: three of this
project's headline quantitative claims (a real-workload fault rate, an end-to-end
pipelining ceiling, and -- earlier in the project's history -- the STREAM speedup and
metadata-dominance findings, artifacts #3-4) were wrong in ways that looked entirely
plausible until specifically checked, and stayed in circulation, cited by other reports,
until a dedicated pass went looking.

## Hypotheses investigated and rejected (not counted among the six)

These were suspected artifacts that, on investigation, turned out **not** to be real —
included here so the catalog documents the negative results too, not just the confirmed
bugs.

| Hypothesis | Why suspected | Verdict | Evidence |
|---|---|---|---|
| Hit-accounting counter is broken (`spec_hits` never fires) | Near-zero hit rates on every real benchmark looked like a broken counter | **REJECTED** -- a deterministic positive control (`tests/hit_probe.cu`, serialized, prefetch off) scored 254/256 = 99.2%; the counter is sound. Near-zero hit rates on real benchmarks are a real interaction with the UVM prefetcher + per-batch (not per-fault) prediction, not instrumentation failure | `driver/PIPELINE_FIXES.md` (FIX-0), `results/phaseB1/GATE_A_report.md` |
| Oracle replay is O(n²) in trace length | Phase B's original sweep reported the oracle "up to 100x slower"; a quadratic scan was the leading hypothesis | **REJECTED** -- `specasync_oracle_next_addr()` is an O(1) atomic post-increment cursor with modulo wraparound; no per-fault linear scan exists anywhere in the replay path. If a real slowdown exists, it is not this | `results/phaseB1/GATE_B_diagnosis.md` (H1) |

---

# Entries #12–#25 (applied 2026-10-05, Gate C1-APPLY)

Appended from `results/analysis/consolidation/ARTIFACT_CATALOG_ADDITIONS_PROPOSED.md`. The original table above is unchanged; the two amendments below amend its rows.

## Entries

### #12 · Comparison against a crippled baseline *(promoted; long-standing candidate)*
- **What happened (Gate B9):** Task 2b compared the oversubscription oracle arm (C3)
  only against C1, which has speculation off **and** the prefetcher off. C3 was
  54.00% faster at iters = 20, Holm-significant across all five iteration values,
  which fired the project's primary falsification trigger. The verification pass
  added C0, the system as shipped, and C3 was **1.76–4.47× slower than C0** at every
  iteration value.
- **False conclusion it would have produced:** "Speculation delivers a large,
  decisive oversubscription speedup", reversing the paper's central negative claim
  on the strength of a comparison against a configuration nobody runs.
- **How caught:** an **independent verification pass**, required by standing policy
  whenever a falsification trigger fires (`OVERSUB_C3_VERIFICATION.md`). The pass
  explicitly flagged this as "a different failure mode … a correct measurement
  answering the wrong question".
- **Evidence:** `B9.2c.iters1` … `B9.2c.iters20`: C3 vs C0 +447.43% to +176.45%,
  all Holm-significant; C1 = 159.67 s vs C0 = 27.18 s at iters 20.
- **Family:** Validation that could not fail. Beating a baseline built to be beaten
  is a test with almost no power to disappoint.
- **Standing consequence:** "baselines named explicitly" became a standing rule,
  and every Gate E pre-registration names C0 and C1 separately.

### #13 · Oracle recording/consumption granularity mismatch, with a diagnosis that mislabelled the recording side
- **What happened (Gate E0 §1, §7; E0.5 Addition 1):**
  - The oracle trace is **recorded once per va-block dispatch group** (the first
    coalesced fault of each group), but **consumed once per coalesced fault**.
  - The replay cursor therefore runs ~11.7× (Stencil-24K) / ~2.1× (GraphBFS-23)
    faster than the trace was recorded, and it wraps several times during a
    single replay.
  - FIX-1 (`cc90fc1`) introduced the full magnitude; `fc384fb` only redistributed
    it (E0.5 Addition 1 corrected the prior attribution).
- **False conclusion it would have produced (and did):** every C3 result was read as
  "against a maximally favorable, oracle-perfect predictor" (T1, T4/A1, B5–B7, B9,
  B10; CS 6/7/8/10). **No oracle measurement before E0.5 used aligned recording
  and consumption.**
- **Amendment to existing #1:** #1's root-cause text says the trace was "recorded
  once **per demand fault**". E0 §1 shows it was recorded once per **dispatch
  group**. #1's fix therefore addressed the wrong granularity and left this
  mismatch in place. Propose amending #1's root-cause cell to point to #13.
- **How caught:** an **independent source audit** (Gate E0), 103 days after FIX-1
  (`cc90fc1`, 2026-06-13; the audit commit `e7de063`, 2026-09-24), by tracing the consumption loop rather than trusting the recording
  side's description.
- **Evidence:** 11.7× / 2.1× and the wrap counts are **PROSE-ONLY** (E0 §7; E0.5).
  The post-fix 1:1 alignment (2,953,867 = 2,953,867 and 483,896 = 483,896) is also
  **PROSE-ONLY** (E0.5 Step 5; raw traces gitignored).
- **Family:** Aggregation-level mismatch. This is the most consequential instance:
  one quantity recorded at one level and consumed at another.

### #14 · A positive control that could not fail
- **What happened:** three instances.
  1. The **serialized** hit probe (`tests/hit_probe.cu`: one fault per service batch,
     by construction, with a full `cudaDeviceSynchronize()` between touches) scored
     0.99 on **both** the buggy and the fixed module. `PIPELINE_FIXES.md:57-63`:
     "The old code scores high on the *serialized* probe only by a degenerate
     'self-hit': it tags the page that is *currently* faulting (zero lead time)."
     With one fault per batch, recording and consumption granularity coincide, so
     the probe structurally cannot see #13.
  2. The **coalesce** probe used to validate FIX-1 had k ≈ 1 dispatch groups per
     coalesced fault (442 faults / 450 trace entries). So it did not exercise
     dispatch-group collapsing either (E0.5 Addition 2: "cannot distinguish 'cursor
     desync fixed' from 'still broken for an unrelated reason'").
  3. **Recurrence, caught in time:** in E3b Step 2, `group_probe`'s width checks
     ("`spec_pages_requested` ≈ W × calls") held **trivially**, as 0 = W × 0,
     because the worker never reached `make_resident` in that probe.
- **False conclusion it would have produced:**
  - Instances 1–2: "FIX-1 fixed the oracle; the hit-accounting path is sound"
    (the catalog's own rejected-hypothesis row relies on instance 1).
  - Instance 3: "the width path is regression-tested".
- **How caught:**
  - Instances 1–2 were caught by an **independent later pass** (E0.5), although
    instance 1's degeneracy was already written in the original fix note's own
    footnote and not acted on.
  - Instance 3 was caught by **the original analysis**, in the same step, because
    the counters were read with the question "was the path exercised at all?". It
    was recorded before Step 3 relied on it.
- **Amendment to the rejected-hypothesis row** ("`spec_hits` never fires" →
  REJECTED): the probe proves the counter *fires*. Its 254/256 = 99.2% includes
  zero-lead self-hits on old code, and what the counter measures is a 10 ms window
  (#20). Propose narrowing the verdict to "fires as coded; see #14 and #20".
- **Evidence:**
  - 254/256, 0.99/0.99, 442/450 and 56 enqueued are **PROSE-ONLY**
    (`GATE_A_report.md`, `PIPELINE_FIXES.md`, E0.5).
  - Instance 3: `results/analysis/gate_e/e3b/step2_runs.csv` (`spec_migrations = 0`,
    `spec_pages_requested = 0` in all six rows). That is a committed derived file,
    not in the extract because it was read directly.
- **Family:** Validation that could not fail.

### #15 · A relative improvement accepted without an absolute ceiling
- **What happened (E0.5):** FIX-1 was validated as "23× more hits" on the coalesce
  probe: **1 → 23** hits, out of 57 and 56 enqueued. That is an absolute difference
  of 22 events. The expected ceiling for that probe was never computed.
- **False conclusion it would have produced (and did):** "FIXED and verified"
  (`PIPELINE_FIXES.md`), which licensed every later oracle result.
- **How caught:** an **independent pass** (E0.5, "FIX-1's validation rested on
  single-digit counts").
- **Evidence:** 1/57, 23/56 and 22 events are **PROSE-ONLY** (E0.5; raw
  `oracle_coalesce/*.bin` gitignored).
- **Family:** Validation that could not fail (a ratio of small counts has no power).

### #16 · Denominator mismatch: per-enqueued hit rate against a per-fault ceiling
- **What happened (E0.5 Addendum §3; CS row 6):**
  - CS 6's "~1/coalesce_factor" ceiling (≈12.7% for 7.9 faults per batch) bounds
    **how many faults receive a prediction**.
  - The reported 41.07% measures **success among the 56 predictions made**
    (hits ÷ enqueued).
  - The claim's own evidence "exceeds [the] ceiling by more than 3x" only because
    the two use different denominators.
- **False conclusion it would have produced:** "the one-prediction-per-batch design
  caps the hit rate at ~1/coalesce_factor", a mechanistic claim stated as following
  "directly" from the fix.
- **How caught:** an **independent pass** (E0.5), by recomputing both quantities from
  the raw ring.
- **Evidence:** 12.7%, 41.07%, 56 and 442 are **PROSE-ONLY**. The project-wide
  convention (hits ÷ enqueued) is confirmed against `T4hit.*`: for example GraphBFS
  51,569 / 20,505,109 = 0.2515% (`T4hit.bench_graph_bfs.repALL_15_SUMMED.superseded_multicounted`).
- **Family:** Aggregation-level mismatch (E0.5 calls it "a fourth instance … alongside
  artifacts #7, #8, #9").

### #17 · Index drift: duplicate-fault counts vary run to run and silently break index-based replay
- **What happened (E0.8; corrected in E0.9 §1):** the first-touch order of pages is
  nearly identical across runs (Stencil-24K: at most 107 ranks of 1,125,000). The
  **number of duplicate faults per page** differs by 1,247–4,418 between plain C1
  runs. Any position-anchored comparison therefore drifts, and positional accuracy
  swings between ~0% and ~100% with the sign of the drift.
- **False conclusion it would have produced (and did, for one gate):** E0.7's
  "Stencil-24K is closer to genuine divergence", which would have abandoned trace
  replay for the wrong reason.
- **How caught:** an **independent analysis-only pass** (E0.8) on the same data. It
  looked at order after stripping duplicates, rather than at positions.
- **Evidence:** 107, 1,125,000, 1,247–4,418 and the Spearman values are
  **PROSE-ONLY** (E0.8 §4/§6).
- **Family:** Aggregation-level mismatch (a per-position quantity compared across
  runs whose positions do not correspond).

### #18 · Forward-only metric asymmetry under a shift, including its recurrence inside the gate that diagnosed it
- **What happened:**
  - E0.7 measured "does the trace's page appear *later* in the replay?" (forward-set).
    Under a small positional shift this reads ~98% in one drift direction and ~0% in
    the other. For Stencil depth = 1, forward 98.48% against backward 0.0708%.
  - E0.8 diagnosed exactly this, and then **repeated it**: its Check 4 "~51.19%
    ceiling" was the same forward-only blindness applied to a symmetric
    displacement. It also used a direction-discarding absolute value in Check 6.
  - E0.9 §1 corrected both. The symmetric measure gives 99.9997% within ±100 ranks,
    and the correct lopsidedness quantity is monotonic.
- **False conclusion it would have produced:** "a real residual disagreement in
  first-touch order exists … at the reduced-sequence windowed scale" (withdrawn),
  and a GraphBFS "opposite sense" argument (withdrawn).
- **How caught:**
  - E0.7's instance: by the **next independent pass** (E0.8).
  - E0.8's recurrence: by **external review** feeding E0.9. The user's correction
    supplied the expected values, not the originating analysis.
- **Evidence:** 98.48%, 0.0708%, ~51.19%, 99.9997% and 31.4 → 47.5 → 51.7 pts are
  **PROSE-ONLY** (E0.8 §1/§4/§6, E0.9 §1).
- **Family:** Aggregation-level mismatch. The recurrence is itself the lesson:
  diagnosing a failure mode did not immunise the diagnosing analysis against it.

### #19 · Circular trace ring read in physical-slot order: truncated *and* rotated, with no signal *(surfaced by the ledger)*
- **What happened (Gate E0 §3):** `specasync_fault_trace` is a pure circular
  overwrite ring (1,048,576 slots) with no drop counter or saturation flag. When a
  run overflows it, the read path returns the last N pushes in **physical** slot
  order. That is a **cyclically rotated** sequence, not chronological order. The
  oversubscription oracle traces (B9's C3, B10's C4) were therefore truncated *and*
  internally rotated before replay, on top of #13.
- **False conclusion it would have produced (and did):**
  - the B10 "residency accumulation" mechanism narrative;
  - reading B9/B10 oracle-arm wall-clock as oracle behaviour.

  (CS2-N9 excludes them from claims.)
- **How caught:** an **independent source audit** (E0). The
  saturation half had been noticed informally in Gate B9 (`t_b9_task2_*`); the
  rotation half was new.
- **Evidence:** ring size and read-path behaviour come from source (E0 §3,
  `debugfs.c:429-453` pre-fix). No run numbers.
- **Family:** Instrument cost and instrument blindness (a ring that overflows silently
  and scrambles order). Related to #7's second occurrence.

### #20 · `spec_hits` counts a timing window, not wins
- **What happened (E0.9a-2 §5):** `spec_hits` increments when a demand fault arrives
  for a page predicted within the last **10 ms**, from a **256-slot** overwrite
  table (`specasync_telemetry.h:292`, `:304`). At large lookahead it collapses:
  858 hits against 919,262 pages staged ahead of the servicing thread. The fastest
  configuration in the project has almost none (1,322).
- **False conclusion it would have produced (and did):**
  - every "hit rate" in the project's history read as prediction success or failure
    (T4, A1, B6 Task 2, cuFFT);
  - "near-zero hit rate" read as "speculation never wins".
- **How caught:** by **the original analysis**. E0.9a-2 saw `spec_hits` fall while
  a second, independent counter (`fault_already_resident`) kept rising in the same
  table. The redundant measurement exposed the blindness.
- **Evidence:** `E09b.mech.stencil.C64096` (858 vs 919,262), `E09b.mech.stencil.C6256`,
  `E4.mech.stencil.C7-W512` (1,322).
- **Family:** Instrument cost and instrument blindness.

### #21 · An upper-bound instrument carrying its own cost
- **What happened (E1b, E3b):** the first-touch "perfect oracle" spent **139–167 ns
  per coalesced fault** on its own binary search and global irqsave lock, on the
  fault-servicing thread. A constant-time lookup removed **77.6–87.8%** of it. The
  instrument meant to bound what speculation could achieve was making speculation
  look worse. The slow oracle cost **0.2216 s** of wall-clock per Stencil C6 run.
- **False conclusion it would have produced:** E0.9b's and E1's "cannot beat C0"
  read as a property of speculation rather than of the oracle. That reading was
  overturned in E4.
- **How caught:**
  - First, E1b, a measurement **forced by a reviewer's challenge** to E1's
    source-structure attribution.
  - Then E3b, a **pre-registered test** whose expectation was committed before the
    run.
- **Evidence:** `E1b.stencil.C64096-C1` (residual 139 ns/fault), `E3b.stencil.C6.residual`
  (139.8 → 18.7 ns; 86.6% removed), `E3b.stencil.C7.residual`, `E3b.graphbfs.C6.residual`,
  `E4.F2.stencil.C6-W1_vs_C6-slow-W1` (−0.2216 s).
- **Family:** Instrument cost and instrument blindness.

### #22 · A UVM helper guarded only by a non-fatal `UVM_ASSERT` returned NULL: a kernel oops on real hardware
- **What happened (E0.9a-2 §4):** new instrumentation called
  `uvm_page_mask_test(uvm_va_block_resident_mask_get(...))`. The getter returns NULL
  when the GPU has no state in the block. Its only guard was a `UVM_ASSERT`, which is
  compiled non-fatal in release builds. The machine crashed. The fix was a
  `uvm_va_block_gpu_state_get(...) &&` guard (`ea1a262`), verified after a reboot.
- **False conclusion it would have produced:** none about data. The hazard was
  physical. It changed the protocol: from then on every new kernel change needed
  a function-and-precondition table naming every `UVM_ASSERT`-only check, and
  compile-only review before the first load (E3a / E3a-2).
- **How caught:** **by a crash.** A user was present.
- **Evidence:** **PROSE-ONLY** (E0.9a-2 §4).
- **Family:** Operational hazards.

### #23 · Silent platform drift from unattended upgrades
- **What happened (E0.5, E0.9b):** between sessions the host's NVIDIA driver moved
  from **595.84 to 595.91.07**, and the kernel moved `-28` → `-31` → `-34`, through
  OS updates. The 595.84 port "no longer exists", and every earlier `.ko` became
  unloadable.
- **False conclusion it would have produced:** that 595.84-era results (B5–B10) and
  595.91.07-era results (Gate E) are one platform. Also that the manuscript's
  platform table is current (it is stale; `COMPLETENESS_LEDGER.md` E0.9b entry).
- **How caught:** by **operational preflight** (E0.5, when a module refused to load).
  Since E0.9b, preflight records the kernel, driver and srcversion, and requires the
  upgrade timers to be inactive.
- **Evidence:** **PROSE-ONLY** (E0.5 "Blocked"; `COMPLETENESS_LEDGER.md`).
- **Family:** Operational hazards.

### #24 · Line-count `dmesg` diffs fail on a full, rotating log buffer
- **What happened (E3b Step 1):** the harness took new dmesg lines as
  `after[len(before):]`. Once the kernel log buffer filled and began rotating, that
  slice came back **empty**. The E0.9b `check_after` fell back to scanning the last
  200 lines. That fallback is still safe for detecting stop patterns, but it
  **misreports new-line counts**.
- **False conclusion it would have produced:**
  - "insmod rejection printed no error" (a false test failure, which happened);
  - more dangerously, a harness that could miss a real oops line if it scrolled out
    of the 200-line window.
- **How caught:** by **the original harness run**. The rejection test failed loudly,
  was investigated, and the fix was a timestamp-based diff (`tests/e3b_dmesg.py`),
  used in E3b, E4 and E5.
- **Evidence:** `results/analysis/gate_e/e3b/step1_reject.csv` (after the fix); the
  failure itself is PROSE-ONLY (`E3B_STATUS.md` Step 1).
- **Family:** Operational hazards.

### #25 · A pilot ceiling that failed its own prediction test
- **What happened (E0.9b Step 2 → Step 5; E1 Part B):** the pilot estimated a
  wall-clock ceiling from the decomp ring's servicing window: C1 − C6-L4096 =
  **0.1983 s**, pilot interval **[0.1701, 0.2171] s**. The pre-registered sweep
  then measured a **0.2437 s** wall-clock saving, which is **above** the interval.
  E1 Part B explained part of the gap: the net window already subtracts +0.477 s of
  speculation's own enqueue loop, while D5 fell by 0.681 s.
- **False conclusion it would have produced:** "servicing-window time maps
  one-to-one onto wall-clock, so the ceiling bounds the saving". Without the
  pre-registered test, the ceiling would have been reported as a bound.
- **How caught:** by **a pre-registered prediction test** (E0.9b addendum,
  committed before the sweep).
- **Evidence:** `E09b.pilot.stencil.interval`, `E09b.pilot.stencil.C1.window`,
  `E09b.pilot.stencil.C6.window`, `E09b.stencil.C6-L4096_vs_C1` (4.3166 − 4.0729 =
  0.2437 s), `E1PartB.stencil.svc_minus_D3_D4` (−0.4769 s), `E1PartB.stencil.D5`
  (+0.6813 s).
- **Family:** Aggregation-level mismatch (a component-level time used as a
  whole-process bound).

### #26 · A status log asserting a state the primary record contradicts, and times typed as estimates *(appended C6, 2026-10-10)*
- **What happened (instance 1, E6):** `e6/E6_STATUS.md` at 19:36:53 on 2026-10-05 recorded
  "loaded stock 6284DA42 (refcnt 0)" and "Phase 4: isolated to multi-user.target (exit 0)".
  The systemd journal shows the verified specasync module was loaded at 17:48:16 with no
  unload before 19:36:53, and **no `systemctl isolate` command anywhere between 17:48:07
  and 20:06:04** (the machine had been in `multi-user.target` since an isolate at 17:48:07
  killed the session running E6). The "(exit 0)" matches no journal record.
  **Instance 2 (E7, E8):** log lines whose time was typed from memory instead of printed by
  `date` or a script ran later than the real times (E7: "14:20 Phase 3" and "14:05 Phase 2
  DONE"; Phase 2 ended about 14:00 and the Phase 3 push was at 14:04:37 by `date`). E8's
  were corrected to the real clock; E7's were left (git commit times are authoritative).
- **False conclusion it would have produced:** that the stock module was resident at the
  start of E6's table collection and that the isolate ran as logged, i.e. that the status
  log is a primary record of platform state; and a session timeline (and cap arithmetic)
  reconstructed from typed times. Neither is supported. The orchestrators compute their
  deadlines in-script from `phase0_start.txt`, so no decision was affected; only the narrative.
- **How caught:** by a read-only re-account of the gap against the persisted journal
  (`E6_GAP_ACCOUNT.md`; instance 1), and at the E8 review by comparing the log with `date`
  and commit times (instance 2). Neither by the gate's own analysis. No effect on any E6
  datum: every run reloads and verifies srcversion and parameters.
- **Evidence:** `results/analysis/gate_e/e7/E6_GAP_ACCOUNT.md` §1, §2, §4;
  `results/analysis/gate_e/e8/E8_STATUS.md:8`; `results/analysis/gate_e/e7/E7_STATUS.md`.
  Unresolved from the journal: whether E6's second "isolate" ran as a non-journaled no-op or not at all.
  The same hand-typed-time error recurred in C5's own log (the Step 2 line, corrected to its commit time).
- **Family:** Record integrity (new, C6).

### #27 · A helper with a hard-coded multiplicity correction reused across gates *(appended C6)*
- **What happened (E0.9b helper; E1, E4, E5, E6, E7, E8):** `tests/e09b_analyze.py:18` fixes
  `Z_MDE_BONF` for alpha = 0.05/16, E0.9b's family size, and writes it as `mde_bonf_s`. Later
  gates import the helper unchanged. E4 (18) and E5 (3) overwrite the constant before use
  (`e4_analyze.py:21`, `e5_analyze.py:28`); E7 and E8 compute `mde_family_s` instead and say
  why; **E6's CSVs carry the 16-test value for families of 3, 4 and 2**; E1 was not audited.
- **False conclusion it would have produced:** an MDE labelled "at the family alpha" that is
  not at that family's alpha: too small for families larger than 16, too large for smaller ones, so a
  null result would look better or worse powered than it was.
- **How caught:** by the author of E7 reading the helper while writing the pre-registration
  (a later gate, not the one that used it). **Audit result (C6 step 2, `MDE_AUDIT.md`):**
  recomputing from the run CSVs, **all 21 E4 and E5 rows equal their reported MDE and
  family-alpha MDE** (to 5e-5 s), so the E4 and E5 reports are not affected; E6's `mde_bonf_s`
  column is wrong for E6's families but is quoted nowhere. What *is* off is a related
  reporting choice: MDEs quoted in prose (CLAIM_SCOPE, Section I, the E4 report text) are the
  unadjusted alpha 0.05 values while the tests are Holm-corrected, so the stated detection
  limit is smaller than the family-alpha limit (E4 GraphBFS: 0.28-0.43% quoted, 0.38-0.59% at
  alpha/18; E6 t0/t10: 1.8%/2.0% quoted, 2.0%/2.3% at alpha/3). Corrections are proposed, not applied.
- **Reached a reported result?** No wrong number reached a report; an unqualified alpha did.
- **Evidence:** `tests/e09b_analyze.py:18`, `tests/e7_analyze.py:13`, `e7/E7_STATUS.md:21`,
  `E7_PREREGISTRATION.md:32-33`, `consolidation/MDE_AUDIT.md`, `consolidation/mde_audit.csv`.
- **Family:** Aggregation-level mismatch (a constant tied to one family's size applied to another's).

### #28 · A build script that swallows a failure when a Git-LFS patch is only a pointer *(appended C6)*
- **What happened (E3a-2 build on the T4, 2026-10-09; earlier on the 5070 Ti):** `driver/patches/*.patch`
  are stored in Git LFS (`.gitattributes: *.patch filter=lfs`). Without git-lfs they are ~130-byte pointer
  files. `driver/scripts/reconstruct_build_tree.sh` ran `patch -p0 --forward -N < specasync_selective_apply.patch || true`;
  `patch` printed "Only garbage was found in the patch input", `|| true` discarded the status, and the tree was
  assembled without the glue changes. The first verified build failed in the compiler
  (`uvm_va_space_t has no member named specasync_pred`, 5 errors).
- **False conclusion it would have produced:** a misdiagnosed driver-source problem; had a build succeeded without the
  glue, a module with a different srcversion would have been mistaken for the verified one. The srcversion check is what
  stands between the two.
- **How caught:** by the failing compile, then by reading the script output; the same hazard on the 5070 Ti was handled by
  hand ("3 `.patch` files show LFS-pointer-vs-real-content diffs", `GPU_FREE_REPORT_2.md`). **Fixed in C5 step 7a:** the script now exits 2
  with install instructions if the glue patch is a pointer.
- **Evidence:** `results/analysis/t4/E3A2_T4_BUILD_REVIEW.md` "Setup problems" #1; `driver/scripts/reconstruct_build_tree.sh`;
  `.gitattributes`; `MIGRATION_NOTES.md`; `T4_REPORT.md:22`.
- **Family:** Operational hazards (loud failure, but at the wrong place; `|| true` made the step unable to fail).

### #29 · A session that ended itself by killing the login session containing it, and an orchestrator that died with its session *(appended C6)*
- **What happened (E7-T4, 2026-10-08/09; E6 on the 5070 Ti):** (i) the previous Claude session ran
  `loginctl terminate-session` on the remote-desktop (xrdp/XFCE) session that contained it, which ended that session
  (E7-T4 Amendment 2). (ii) The instance was powered off during the smoke pass, killing the orchestrator, and the
  pre-registered cap had to be re-set (Amendment 1); the cause of that poweroff is **not established**. (iii) The same class on
  the 5070 Ti: `systemctl isolate multi-user.target` stopped `user@1000.service`, which SIGKILLed the tmux server holding
  the E6 session (`E6_GAP_ACCOUNT.md`, 17:48:23). Mitigation since: `loginctl enable-linger`, a detached `systemd-run --user`
  unit, and a rule that killing a login session is forbidden.
- **False conclusion it would have produced:** none in a data result (no timed run was in flight in the T4 cases); the hazard is
  lost time, a changed cap, and a half-run gate read as complete or as a stop-condition outcome.
- **How caught:** by the failure itself; recorded as amendments before any timed run.
- **Evidence:** `results/analysis/t4/E7T4_AMENDMENT_1.md`, `E7T4_AMENDMENT_2.md`; `results/analysis/gate_e/e7/E6_GAP_ACCOUNT.md`;
  `e7/E7_STATUS.md` ("enable-linger").
- **Family:** Operational hazards.

### #30 · A pre-registration that checked VRAM but not host RAM *(appended C6)*
- **What happened (E7-T4, smoke row 25):** the pre-registered oversubscribed Stencil (`bench_stencil_oversub 48000 1`, 17.17 GiB
  managed) was sized by the VRAM ratio (1.144 on the T4 vs 1.078 on the 5070 Ti). The g4dn.xlarge has 15.4 GiB of RAM and no swap;
  UVM CPU-side population exhausted host RAM and the kernel OOM-killed the process (`block_populate_pages_cpu`, file-rss 15.1 GB)
  at 2026-10-09 08:05:52 UTC.
- **False conclusion it would have produced:** none reached a result (no timed data existed). With a larger timeout or a swap file, a
  thrashing-on-host run could have been timed as an "oversubscription" measurement.
- **How caught:** by the pre-registered smoke pass, as a kernel OOM kill; Amendment 2 removed the cell and added a stop condition
  (managed bytes < MemAvailable - 4 GiB). The E8 pre-registration (24 GiB array) checked host RAM (minimum `MemAvailable` 30.4 GiB).
- **Evidence:** `results/analysis/t4/E7T4_AMENDMENT_2.md`; `e7t4_smoke.csv`; `e7t4_runner.py` `MANAGED_BYTES`; `E8_PREREGISTRATION.md`.
  The earlier near-OOM from a host leak is #11.
- **Family:** Operational hazards (peer of #11).

---

## Families and synthesis

Each entry, old (#1–#11) and new (#12–#30), is assigned one primary family. **C6 update (2026-10-10):** #26–#30 appended (30 entries in all); a new family, **Record integrity**, holds #26 and #23, and **#23 was moved into it from Operational hazards** (the original assignment is recorded in the amendment at the end of this file).

| family | entries | caught by the original analysis | caught only by a later, independent pass or review | caught by a pre-registered test | caught by the failure itself (crash / loud harness / preflight) |
|---|---|---|---|---|---|
| **Aggregation-level mismatch** | #7, #8, #9, #13, #16, #17, #18, #25, #27 | — | #7, #8, #9, #13, #16, #17, #18 (E0.7 → E0.8; E0.8's recurrence → external review), #27 (a later gate's author) | #25 | — |
| **Validation that could not fail** | #1, #2, #12, #14, #15 | #14 (instance 3, group_probe) | #1, #2 (Gate B re-investigation), #12 (verification pass mandated by the trigger policy), #14 (instances 1–2), #15 | — | — |
| **Instrument cost and instrument blindness** | #4, #5, #19, #20, #21 | #5 (Phase C's same-session accounting-closure check), #20 (a second counter disagreed in the same table) | #4, #19, #21 (E1b, forced by review) | #21 (E3b) | — |
| **Operational hazards** | #3, #10, #11, #22, #24, #28, #29, #30 | — | #3 (interleaved re-run) | #10 (A2b was pre-registered to test it), #30 (the pre-registered smoke pass) | #11 (near-OOM forced a stop), #22 (crash), #24 (loud harness failure), #28 (failed compile), #29 (the session ended) |
| **Record integrity** *(new, C6)* | #23, #26 | — | #26 (journal re-account; E8 review) | — | #23 (preflight) |
| *(uncategorised: a genuine outlier)* | #6 | — | #6 (Task T2 reproduction) | — | — |

### Aggregation-level mismatch
A quantity computed at one level is used at another:
- per-rep vs summed (#7, #8);
- per-trial vs aggregated (#9);
- per-dispatch-group vs per-fault (#13);
- per-enqueued vs per-fault (#16);
- per-position across runs whose positions do not correspond (#17);
- forward-only vs symmetric (#18);
- servicing-thread component vs whole-process wall-clock (#25).

**Scope of the observation, stated exactly.** Among aggregation-family entries that
reached a reported figure or a reported conclusion (#7, #8, #9, #13, #16, #17, #18),
every one was caught by an independent pass or external review, never by the analysis
that produced it. #25 is the one aggregation-family entry caught inside its own gate. Its
pilot ceiling was a pre-registered prediction that failed, and it had not been reported
beyond the pilot report.

**Selection-effect caveat.** The catalog records only errors that were caught and
written up. An in-gate catch never propagates into another report, so it never
enters a catalog that counts reported errors. The catalog therefore cannot count what
pre-registration or redundant measurement missed. The sample behind each mechanism is
small: n = 2–3 per mechanism. Read the family comparisons as descriptive.

#18 sharpens the point. The gate that diagnosed the forward-only failure repeated it
two checks later, and it took outside review to catch the recurrence. Knowing the
failure mode is not protection.

**#25 is instructive.** It was caught by the analysis
itself, but only because the prediction had been pre-registered, so a failed
prediction could not be quietly reinterpreted.

### Validation that could not fail
In each case a control or comparison passed by construction:
- a serialized probe where recording and consumption granularities coincide (#14);
- a probe whose access pattern never exercised the bug (#14);
- a ratio of single-digit counts (#15);
- a comparison against a baseline built to be beaten (#12);
- and, earlier, an oracle whose collection and replay never overlapped in address
  space (#1, #2).

These were caught late, by independent passes. The only instance caught at once
(#14, instance 3) was caught because the reader asked "was the code path exercised
at all?" *before* asking "did the check pass?".

**Proposed standing rule:** every positive control is shown able to fail. Run it on
the known-buggy code (or on a configuration where the effect is absent) and show a
different result.

### Instrument cost and instrument blindness
The measurement machinery either changed the thing measured, or hid it:
- a timer pair that collapsed a phase to zero (#4);
- a read path that drifted byte offsets (#5);
- a ring that overflowed silently and returned rotated order (#19);
- a counter that measured a time window rather than the event it was named for
  (#20);
- an "upper-bound" oracle whose lookup cost ~140–167 ns per fault on the critical
  path it was bounding (#21).

**The pattern differs from the aggregation family.** Two of these were caught by
the original analysis, and in both a *redundant measurement* disagreed:
- #5, by Phase C's own accounting-closure identity, checked in the same session
  before any report was written;
- #20, by a second, independent counter in the same table.

#21 was caught by a pre-registered test. Redundancy and pre-registration did, inside
the gate, what independent verification did later for the aggregation family.

### Operational hazards
Crashes, drift and harness failures (#23, silent upgrades, moved to Record integrity in C6):
- host-ordering noise (#3);
- the `setarch -R` regime (#10);
- a host memory leak (#11);
- a kernel oops (#22);
- *(silent driver and kernel upgrades, #23: moved to Record integrity)*;
- a build script whose failure `|| true` hid when a Git-LFS patch was a pointer (#28);
- a session ending by killing the login session that held it (#29);
- a pre-registration that sized an array by VRAM and not host RAM (#30);
- a dmesg diff broken by a rotating log (#24).

These were mostly caught because they *failed loudly*: a crash, a module that would
not load, a test that stopped. The dangerous members are the quiet ones:
- #11 and #23 would have corrupted comparisons without any visible failure;
- #24's fallback kept working, but with a shrinking safety margin.

The response in this project has been procedural: preflight records, stop
conditions, and compile-only review before the first load.

### Record integrity *(new in C6)*
The record of what happened, written by the person or session that did it, disagrees with the primary record:
- a status log that asserted a module state and an isolate the journal does not show, and times typed as estimates (#26);
- a platform description that went stale between sessions through silent upgrades (#23, moved here from Operational hazards: the
  upgrade itself was an operational hazard, but the false conclusion it would have produced is that a record of the platform
  (the manuscript's platform table) was current).

Both were caught by a comparison with a primary record (the journal, preflight output, commit times), not by the analysis. Neither
affected a measured datum, because every run re-verifies its own platform state; they would have affected a *narrative*. Sample: n = 2,
one of them (#23) moved from another family; read as a candidate family, not a finding.

### Does "#7–#9 were all caught by independent verification" generalise?
**Only within its own family.**
- All seven aggregation-level mismatches that reached a reported figure or conclusion
  (#7, #8, #9, #13, #16, #17, #18) were caught by independent passes or review.
- Across the whole catalog, three other catching mechanisms appear:
  - **pre-registration** (#10, #21, #25);
  - **redundant measurement inside the original analysis** (#5's closure identity,
    #20's second counter);
  - **loud failure** (#11, #22, #23, #24).
- The two cheapest mechanisms, pre-registered predictions and a second counter for
  the same quantity, caught errors *during* the gate that made them. Independent
  verification caught them only later, after they had propagated into other reports
  (#13 reached every oracle result for 103 days, 2026-06-13 → 2026-09-24).

---


## Amendments to existing entries (C1-APPLY, 2026-10-05; C6 note appended below)

These amend text in `ARTIFACT_CATALOG.md`'s existing rows. They are appended here, and
the original rows are left unchanged, so the amendment is auditable.

**Amendment A — #1, root-cause cell.** The existing cell says the fault trace was
"recorded once **per demand fault**". Amended: the trace is recorded **once per va-block
dispatch group** (E0 §1), and consumed once per coalesced fault. The consequence is the
granularity mismatch now catalogued as #13. #1's fix addressed the consumption side and
left the recording-side mismatch in place.

**Amendment B — rejected-hypothesis row, "`spec_hits` never fires".** The existing verdict
(REJECTED: "the counter is sound") is narrowed to: the counter fires as coded. It measures
a 10 ms window over a 256-slot table (#20). The 254/256 = 99.2% probe score included
zero-lead self-hits on the old code (`driver/PIPELINE_FIXES.md:60-62`; #14). The probe
therefore does not establish that the counter measures wins.


**Decision on the averted-hazard candidate (D5, 2026-10-05):** a methodology note, not a catalog entry (`consolidation/OPEN_DECISIONS.md`).

**Amendment C (C6, 2026-10-10) — #23 moved.** #23 ("Silent platform drift from unattended upgrades") was assigned to
*Operational hazards* in the families table. It is moved to the new family *Record integrity* (with #26). The entry text is unchanged. The
families table, the Operational hazards and "loud failure" lists were updated; "caught by the failure itself (preflight)" still applies to it.
Totals after C6: **30 entries** (#1-#30; #6 remains uncategorised): Aggregation-level mismatch 9 (#7, #8, #9, #13, #16, #17, #18, #25, #27),
Validation that could not fail 5 (#1, #2, #12, #14, #15), Instrument cost and instrument blindness 5 (#4, #5, #19, #20, #21),
Operational hazards 8 (#3, #10, #11, #22, #24, #28, #29, #30), Record integrity 2 (#23, #26), uncategorised 1 (#6).
