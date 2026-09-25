# Gate E1 Part B — Ceiling reconciliation (analysis only, no runs)

**Verdict: Scope mismatch.** Pre-staging shortened the servicing-under-lock
phase D5 and left D1+D2 essentially unchanged. The pipelining ceiling bounds
only the hiding of D1+D2, so E0.9b's result neither contradicts it nor falls
under it. The ceiling is not wrong. It is also not a bound on off-path
schemes in general. See §4 for exactly which text overreaches: it is narrower
than the brief assumed.

Scripts and data:
- `tests/e1_partb_phases.py` reads the E0.9b pilot decomp dumps in
  `results/phaseB1/gate_e09b/pilot_raw/` (gitignored). These are the full
  ring, 100% coverage, n = 3 + 3 (Stencil-24K) and 2 + 2 (GraphBFS-23).
- Outputs: `e1/partb_phase_totals.csv` (per run) and `e1/partb_phase_medians.md`.
- Phase definitions: `driver/src/specasync_telemetry.h:107-141`.
- Accounting checks pass on all 10 runs: D3 + D4 ≤ svc and D5 ≤ D4, with 0
  violations.

## 1. Which phases did pre-staging shorten?

Stencil-24K, per-run totals summed over all top-level batches, median of
3 runs per arm:

| phase | what it is | C1 (s) | C6-L4096 (s) | C1 − C6 (s) | share of the 0.198 s window reduction |
|---|---|---|---|---|---|
| D1 | fault-buffer drain | 0.2924 | 0.2829 | +0.0095 | +4.8% |
| D2 | preprocess / sort / dedup | 0.1911 | 0.1976 | −0.0065 | −3.3% |
| **D1+D2** | *what the pipelining ceiling bounds* (median of per-run D1+D2) | 0.4838 | 0.4805 | **+0.0033** | **+1.7%** |
| D3 | VA-space lock wait | 0.0030 | 0.0029 | +0.0001 | 0.0% |
| D4 | VA-space lock hold (includes D5) | 1.6279 | 0.9473 | +0.6806 | +343% |
| **D5** | **dispatch/servicing inside the hold** | 1.5952 | 0.9139 | **+0.6813** | **+344%** |
| D4 − D5 | hold outside dispatch | 0.0328 | 0.0335 | −0.0007 | −0.4% |
| **svc − D3 − D4** | **`service_fault_batch()` time outside the VA-space lock** | 0.0117 | 0.4886 | **−0.4769** | **−241%** |
| svc | whole `service_fault_batch()` | 1.6427 | 1.4389 | +0.2038 | +103% |
| D6 | replay push | 0.1124 | 0.1179 | −0.0054 | −2.7% |
| D7 | residual | 0.0034 | 0.0031 | +0.0003 | +0.1% |
| window | (d6_end ∨ svc_end) − d1_start | 2.2397 | 2.0414 | +0.1983 | 100% |

Every row is a separate median, so the rows do not sum exactly.

**Reading.**

- **Pre-staging removed 0.681 s of work from D5**, the servicing phase that
  runs under the VA-space lock. This fits the mechanism: when a page is
  already resident, the demand path's `make_resident` copy is a no-op.
- **D1+D2 moved by only +0.003 s**, which is 1.7% of the window reduction
  and within run-to-run noise at this n.
- The **net** window reduction is only 0.198 s because speculation adds
  +0.477 s in `service_fault_batch()` *outside* the VA-space lock. From
  source (`uvm_gpu_replayable_faults.c:2670-2683`), the Gate 1 per-fault
  prediction/enqueue loop runs at the top of `service_fault_batch()`, before
  any VA-space lock is taken. That puts it inside `svc` but outside D3 and D4.
  Its costs are `specasync_ft_predict`, `kzalloc(GFP_ATOMIC)`,
  `uvm_gpu_retain` and `queue_work`, for each of the roughly 1.125M
  predictions (lines 382-421).
- In C1 (policy 0), `specasync_enqueue` returns at line 390, and the same
  interval is 0.012 s.
- Attributing the +0.477 s to that loop rests on source structure, not a
  separate measurement. The batch ring's `enqueue_overhead_ns` would measure
  it directly, but the pilot did not dump that ring.

GraphBFS-23 shows the same pattern at a smaller scale:
- D5: −0.092 s.
- Outside-lock time in svc: +0.089 s.
- D1+D2: +0.000 s.
- Net window: ≈ 0.

This matches its null wall-clock result in E0.9b.

**Answer to Part B.1: the reduction sits entirely in D4/D5, not in D1+D2, as
predicted.** The gross saving (0.681 s) is 3.4× the net window reduction.
Most of it is spent again on the servicing thread by speculation's own
enqueue path.

## 2. What the pipelining ceiling bounds

From `PIPELINING_CEILING.md`, `GATE_T3_REPORT.md`, `GATE_B7_5070TI_PHASEC.md`
§6 and `CEILING_BASIS_VERIFICATION.md` §5–7.

**Numerator.** It covers **D1+D2 only**: fault-buffer drain plus
preprocessing. The formula is ceiling = (D1+D2 share of the dispatch window)
× (dispatch window ÷ process wall-clock). It is the fraction of wall-clock
that would be recovered if D1+D2 were fully hidden, meaning overlapped with
servicing. D3–D6 are excluded by construction. D4/D5 (52–77% of the window
on the 5070 Ti, B7 §5) is treated as non-offloadable.

**Aggregation.** The corrected convention (CEILING_BASIS_VERIFICATION §7) is
"span, median-of-trials": the numerator is the elapsed span of the dispatch
window, as a median over 5 trials, against the median wall-clock of the same
5 trials.

**Wall-clock convention.**
- The ceiling uses **process wall-clock**: `lib_specasync_harness.sh`
  `time_run()` runs `/usr/bin/time -f "%e" setarch -R <bin>` at 10 ms
  resolution (B7 §0; `tests/lib_specasync_harness.sh:204`).
- E0.9b's 5.65% is also whole-process wall-clock, but measured by a
  different instrument: Python `time.monotonic_ns()` around
  `timeout T setarch -R <bin>`, at ns resolution.
- The two are the same *kind* of quantity, but not the same instrument.

**Configuration.** The ceiling was measured with **policy 0, depth 0,
prefetch on** (B7 §5: the `run_gatec1_decomp.sh` config). That is C0, not C1.

**Stencil-24K's own value on the 5070 Ti.** **There is none.**
- B7 Task 4 and T3 cover Stencil-8K, GraphBFS-23 and Sweep-4K/8K/16K/24K.
  Stencil-24K appears only in B7's D1–D7 breakdown (Task 3, D1+D2 = 32.7%
  of the window), with no paired wall-clock.
- The nearest ceiling is **Sweep-24K: 7.25%** (corrected; superseded value
  29.02%) on the 5070 Ti, **driver 595.84**, at a wall-clock median of
  1.080 s. T3 §4 identifies Sweep-24K as the same binary and size
  (`bench_stencil`, N = 24000).
- The only ceiling actually labelled "Stencil-24K" is `PIPELINING_CEILING.md`'s
  7.86%. That is **T4**, on a **kernel-loop** timing convention, and is
  superseded for manuscript use.
- The published range "0.08–7.94%" spans both platforms: 5070 Ti
  0.08–7.25%, T4 0.13–7.94%.

## 3. Like with like

The two numbers are **not like-for-like**, so no comparison is made and no
conversion is attempted. There are three separate reasons:

1. **Different baseline configuration.** E0.9b's 5.65% is C6-L4096 relative
   to **C1 (prefetch off)**, a 4.317 s denominator. The ceiling is a share of
   the **prefetch-on** (C0-configuration) wall-clock, 1.080 s at 595.84. The
   denominators differ by about 4×, and so do the fault counts
   (2.93M vs 0.35M).
2. **Different phases.** As §1 shows, the 5.65% comes through D5, which the
   ceiling excludes by construction.
3. **Different instrument and driver.** `/usr/bin/time %e` (10 ms) at
   595.84, against `monotonic_ns` at 595.91.07.

Reason 2 alone decides the verdict. Reasons 1 and 3 are why no numerical
comparison is made even so.

## 4. Verdict and what it bears on

**Scope mismatch.** Pre-staging acted on D5, a phase the ceiling excludes.
The ceiling is not contradicted: D1+D2 did not shrink, and no scheme in this
project has shown a saving through D1+D2 larger than the ceiling. It is
simply silent about schemes that remove work from D4/D5.

**Where the overreach actually is.** The brief says the manuscript uses the
ceiling "to bound what any off-path scheme can recover". **I could not find
that wording** in `paper/main.tex`, `paper/abstract_v2.md` or
`paper/intro_revisions.md`:
- `main.tex:171-178` contains only a TODO comment, which already warns
  against stating a single end-to-end percentage.
- No "0.08–7.94%" figure appears in any manuscript file.

The text that does overreach is in **`CLAIM_SCOPE.md` claim 15**, which
describes "the 9–30% D1+D2 window-share bound" as a "structural upper limit
on what's even offloadable". E0.9b shows work leaving D5 because an
off-path worker did the copy ahead of time. So D4/D5 work *is* partly
offloadable in this sense, but only by pre-staging, and at an enqueue cost
paid back on the servicing thread.

**Flag for `CLAIM_SCOPE.md`** (not edited):
- **Claim 15:** scope "structural upper limit on what's even offloadable"
  to "upper limit on what hiding D1+D2 can recover". Record that pre-staging
  acts on D5 and falls outside this bound (E1 Part B, E0.9b).
- **Future manuscript text:** if Section VI states the ceiling, it must say
  that it bounds *overlapping D1+D2*, not off-path schemes in general. It
  must not be placed next to E0.9b's 5.65% as if the two measured the same
  thing.
- **E0.9b's failed prediction test is explained, in part.** The pilot
  ceiling was the *net* window reduction, which already subtracts the
  enqueue loop's +0.477 s. If that loop's servicing-thread cost overlaps
  with GPU execution, it costs less wall-clock than servicing-window time,
  while the D5 reduction removes stall time. That would make the net window
  an under-estimate. This is a hypothesis, not tested here. E0.9b's finding
  that the ceiling was wrong stands as recorded.

**Limitation:** the §1 attribution comes from the pilot (n = 3 + 3 Stencil,
2 + 2 GraphBFS), not the pre-registered sweep. The direction is large and
consistent in every run, with non-overlapping ranges:
- Stencil D5: C1 1.591–1.596 s vs C6 0.901–0.939 s.
- Stencil outside-lock svc: C1 0.0117–0.0118 s vs C6 0.488–0.490 s.
- GraphBFS D5: C1 0.737–0.765 s vs C6 0.659–0.660 s.

The exact shares are pilot-precision.
