# Gate E6 — Report: does lowering the stock prefetch threshold match speculation?

Pre-registration: `results/analysis/gate_e/E6_PREREGISTRATION.md` (committed before any E6 run).
Log: `results/analysis/gate_e/e6/E6_STATUS.md`. Data: `results/analysis/gate_e/e6/e6_runs.csv` (110 rows).
Analysis: `tests/e6_analyze.py` (outputs in `e6/`). Figure: `e6_threshold.png` / `e6_threshold.pdf`.

## Headline — V-B (FALSIFICATION TRIGGER FIRED)

**The pre-registered falsification trigger fired.** Under the prefetcher's own density threshold,
the stock driver (C0) matches or beats speculation (C7W512) on Stencil-24K.

- At `uvm_perf_prefetch_threshold = 0` (C0-t0) and `= 10` (C0-t10), C0 is **Holm-significantly
  faster** than C7W512-t51: +6.39% (p = 1.08e-05) and +4.72% (p = 2.06e-04). C7W512-t51 is the
  speculation arm at the shipped threshold.
- C0-t25 is **not** Holm-significantly slower than C7W512-t51 (+2.11%, p = 0.28).
- So "the Stencil gain requires speculation" is **not supported** by this run. The gain from the
  shipped threshold (C0-t51 vs C7W512-t51, −3.36%) is reproduced by changing one module
  parameter, with no speculation, to a threshold below 51.

Per the pre-registration, nothing further was run after the trigger fired.

## Expectations (pre-registered; not part of the verdict)

| id | expectation | result | basis |
|---|---|---|---|
| X1 | C0 demand faults fall monotonically as threshold decreases | **held** | medians t0 134,993 < t10 171,872 < t25 222,142 < t51 338,838 |
| X2 | C0's fastest threshold is below 51 | **held** | fastest C0 is t0 (1.0262 s), vs t51 (1.1298 s) |
| X3 | V-A vs V-B is about even | **not scored** | the expectation has no direction; recorded verdict V-B (see Limitations) |
| X4 | within-threshold D(0) ≤ 0.20 and C7W512-t0 vs C0-t0 Holm-significant, faster | **failed** | D(0) = +0.0532 (≤ 0.20 holds), but the wall-clock gain is −0.85%, p = 0.315, not significant |

## Primary test — Family 1 (Stencil-24K, Holm family of 4)

Two-sided Mann–Whitney U, exact; n = 10 per cell. Delta is (C7W512-t51 − base) ÷ base;
**negative = speculation arm faster**.

| baseline | median (s) | C7W512-t51 median (s) | delta | p | Holm threshold | Holm-sig | Cohen's d | MDE (s) | outliers removed (Tukey): delta s / p |
|---|---:|---:|---:|---:|---:|:---:|---:|---:|---|
| C0-t0  | 1.0262 | 1.0918 | +6.39% | 1.08e-05 | 0.0125 | yes | +3.18 | 0.0231 | +0.0675 s / 2.2e-05 |
| C0-t10 | 1.0426 | 1.0918 | +4.72% | 2.06e-04 | 0.0167 | yes | +2.09 | 0.0238 | +0.0492 s / 2.1e-04 |
| C0-t25 | 1.0692 | 1.0918 | +2.11% | 0.280 | 0.0500 | no  | +0.69 | 0.0247 | +0.0226 s / 0.280 |
| C0-t51 | 1.1298 | 1.0918 | −3.36% | 3.25e-04 | 0.0250 | yes | −2.34 | 0.0236 | −0.0380 s / 3.2e-04 |

**Verdict, applied mechanically:** V-A ("speculation beats tuning") requires C7W512-t51 to be
significantly faster than all four baselines. It is significantly faster only than C0-t51.
V-B ("tuning matches or beats") requires at least one baseline that is not significantly slower.
C0-t0, C0-t10 and C0-t25 all qualify. **V-B.**

## Secondary

**Within-threshold wall-clock (Stencil, Holm family of 3; C7W512-t vs C0-t, negative = C7 faster):**

| t | median C0-t (s) | median C7W512-t (s) | delta | p | Holm-sig |
|---:|---:|---:|---:|---:|:---:|
| 0  | 1.0262 | 1.0175 | −0.85% | 0.315 | no |
| 10 | 1.0426 | 1.0396 | −0.28% | 0.529 | no |
| 25 | 1.0692 | 1.0398 | −2.76% | 1.30e-04 | yes |

**Within-threshold demand faults (Stencil, separate Holm family of 3):**

| t | C0 median | C7W512 median | delta | p | Holm-sig |
|---:|---:|---:|---:|---:|:---:|
| 0  | 134,993 | 127,815 | −5.32% | 1.08e-05 | yes |
| 10 | 171,872 | 157,350 | −8.45% | 1.08e-05 | yes |
| 25 | 222,142 | 172,981 | −22.13% | 1.08e-05 | yes |

**D(t)** (E5 definition, `1 − median faults(C7W512-t) ÷ median faults(C0-t)`):
t0 +0.0532, t10 +0.0845, t25 +0.2213, **t51 +0.4017** (E5 reported +0.4009; the same definition on E5's data, see the positive control).

**Family 2 — GraphBFS-23 (Holm family of 2; C0-t0 and C0-t25 vs C0-t51, wall-clock):**

| comparison | median C0-t (s) | median C0-t51 (s) | delta | p | Holm-sig |
|---|---:|---:|---:|---:|:---:|
| C0-t0 vs C0-t51  | 31.525 | 31.543 | −0.06% | 0.971 | no |
| C0-t25 vs C0-t51 | 31.580 | 31.543 | +0.12% | 0.436 | no |

GraphBFS shows **no threshold effect** on wall-clock across 0–51, which matches E4's GraphBFS null (prefetcher already doing most of the work).

**Mechanism (descriptive; `e6/mechanism.csv`):**

| cell | median wall (s) | demand faults | D5 ns per demand fault | fault already resident | spec pages requested |
|---|---:|---:|---:|---:|---:|
| C0-t0  | 1.026 | 134,993 | 373.2 | 0 | 0 |
| C7W512-t0 | 1.018 | 127,815 | 332.0 | 21,619 | 830,088 |
| C0-t10 | 1.043 | 171,872 | 339.0 | 0 | 0 |
| C7W512-t10 | 1.040 | 157,350 | 299.0 | 23,803 | 828,296 |
| C0-t25 | 1.069 | 222,142 | 332.0 | 0 | 0 |
| C7W512-t25 | 1.040 | 172,981 | 283.9 | 24,328 | 849,800 |
| C0-t51 | 1.130 | 338,838 | 310.0 | 0 | 0 |
| C7W512-t51 | 1.092 | 202,740 | 279.7 | 23,724 | 850,824 |

D5 per demand fault is descriptive only (it is not separable from fault count, as in CS2-N4).

## Replication against E5

The E5 comparison at the shipped threshold (C7W512-t51 vs C0-t51) was **−5.26%, p = 1.08e-05** (E5 report).
In E6's independent sweep it is **−3.36%, p = 3.25e-04**. Demand-fault D(51) agrees (+0.4017 vs +0.4009).
The direction and significance replicate; the wall-clock magnitude does not replicate at the same size.
This difference is reported as found, not reconciled.

## Figure

`results/analysis/gate_e/e6_threshold.png` (and `.pdf`): Stencil wall-clock and demand faults against threshold, C0 and C7W512, n = 10 per cell.

## Stop conditions and run integrity

- 110 rows (Stencil 80, GraphBFS 30), all `exit_code` 0, every read-back and `ft_fast_verified` check passed, no stop file written.
- Family 2 ran. (An orchestrator error wrote a skip record at 19:42:41; the cause was an unset variable, the deadline was 19:53:51, and Family 2 was in-window. The skip record was removed in a new commit. See `E6_STATUS.md`.)
- Four runs logged one new kernel line each: idx 20 (C0-t51), 22 (C7W512-t10), 79 (C7W512-t51) and 97 (GraphBFS C0-t0). All four are `workqueue: drm_fb_helper_damage_work hogged CPU for >10000us` notices, matched by uptime offset. They are not in the stop pattern and do not affect the Family 1 or Family 2 comparisons beyond the normal run-to-run spread.
- Smoke rows (`e6/e6_smoke.csv`, 8 runs) are excluded from every analysis.
- Analyzer change before the first analysis run: the `__main__` default data path referenced an undefined name. It was changed to the module constant `OUTDIR`; the analysis functions are unchanged. The positive control was re-run after the change and still passes (`e6/analyzer_positive_control.txt`).

## Limitations

- **C0 at thresholds below 51 is not the shipped driver.** Every comparison in this gate is within a threshold, or against the shipped threshold 51 explicitly named as such. The headline result depends on C0 at t0/t10/t25 being a valid baseline; it is one, but it is a different driver configuration from the one shipped.
- **Single platform:** RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34.
- **Oracle:** the Stencil arm uses the near-perfect first-touch table; GraphBFS uses the weakened-cursor table (coverage 0.22–0.81 across E4's C6 arms). This gate explains the mechanism and does not measure a practical predictor.
- **At low thresholds the prefetch hint is computed on every fault**, so its own cost is inside C0-t0 and C0-t10 (as pre-registered).
- **X3 is not scored.** The pre-registered expectation has no direction. The brief asked for each of X1–X4 to be marked held or failed; X3 was left unscored rather than given an invented criterion. This is a DOC-class ambiguity for review.
- **The E5 replication difference** (−5.26% vs −3.36%) is not explained by this gate.

## Existing claims flagged (not edited)

Per the brief, existing claims are flagged for review and not changed in this gate:

- **CS2-N1** (Stencil speculation gain): the V-B result tests its premise that the Stencil gain requires speculation. Flagged, not edited.
- **CS2-N3** and **CS2-N4**: E6 bears on the wording and the D5-per-demand-fault figures; flagged, not edited.
- **Limitation on C0 at thresholds below 51** (CLAIM_SCOPE): E6 shows these C0 configurations are not only valid baselines but the faster ones; the limitation as written should be reviewed. Flagged, not edited.

The user decides these edits.
