# Gate E1 — Can a real oracle improve the driver as it ships?

Status log: `E1_STATUS.md`. **The session completed with no stop condition.**

Platform for every number: RTX 5070 Ti, driver 595.91.07, kernel
7.0.0-34-generic. Module srcversion `5997D238EF080B77DBD2AAF` (built from
`ea1a262`).

## Headline

- **Falsification trigger: did not fire.** With the prefetcher left on,
  perfect first-touch knowledge does **not** improve the driver as it ships
  at any lookahead tested:
  - **Stencil-24K:** every C7-L is **Holm-significantly slower** than C0,
    by +3.9% (L1) to +8.4% (L256). The MDE here is about 0.012 s (≈1.1%).
  - **GraphBFS-23:** **no significant difference** at any L. Δ ranges from
    −0.14% to +0.31%, against an MDE of 0.16–0.18 s (≈0.5–0.6%).
- **The paper's central claim holds in the stronger form this gate tests.**
  Speculation, even with a perfect first-touch oracle and the prefetcher
  left on, cannot improve the shipped driver on these two benchmarks:
  - On Stencil it makes the driver worse.
  - On GraphBFS any effect is below ≈0.5%, the resolution of this design.
- **Part B verdict: scope mismatch.** Pre-staging's saving in E0.9b came
  from D5 (servicing under the VA-space lock), not from D1+D2. The
  pipelining ceiling bounds only the hiding of D1+D2. It is not wrong, but
  it does not bound off-path schemes in general.

## Part A — Push and preflight

- The push ran first, **before** isolating the desktop: `b655a62..a6d3f93`,
  exit 0. `git status -sb` then showed the branch level with origin.
- Preflight passed: tracked tree clean; `tests/group_probe` untracked, as
  always; tmux on `/dev/pts/0` with `DISPLAY` unset; the upgrade units
  inactive; kernel 7.0.0-34; driver 595.91.07; srcversion match (both the
  file and the loaded module); `git diff ea1a262 HEAD -- driver/` empty;
  dmesg clean; MemAvailable 57.6 GB with the desktop up; 40 GiB free.
- Parts A, B and the E1 pre-registration were all committed **and pushed**
  while the desktop session was up (`53f147e`, `61980f1`, `9ac42ab`).

## Part B — Ceiling reconciliation

Full write-up: `E1_PARTB_CEILING_RECONCILIATION.md` (commit `61980f1`).

**Which phases pre-staging shortened** (E0.9b pilot, Stencil-24K, 100%
decomp coverage, n = 3 + 3):
- **D5 fell by 0.681 s.**
- **D1+D2 moved by +0.003 s.**
- `service_fault_batch()` time *outside* the VA-space lock rose by
  **+0.477 s**. From source this is the Gate 1 prediction and enqueue loop
  (`uvm_gpu_replayable_faults.c:2670-2683`), which runs before the lock.
- Net: the 0.198 s window reduction.

All three shifts have non-overlapping per-run ranges. GraphBFS shows the
same pattern and nets to about 0.

**What the ceiling bounds:**
- Its numerator is **D1+D2 only**; it assumes D4/D5 cannot be offloaded.
- It uses process wall-clock (`/usr/bin/time %e` + `setarch -R`).
- It was measured with **prefetch on** (policy 0).
- **There is no Stencil-24K ceiling on the 5070 Ti.** The nearest is
  Sweep-24K, the same binary and N: **7.25%** at driver 595.84.

**Like with like:** not comparable, and not converted. The baselines differ
(the 5.65% is against C1, prefetch off; the ceiling is against a prefetch-on
run), the phases differ, and the instrument and driver version differ.

**Verdict: Scope mismatch.** The brief's quoted "bounds any such scheme"
wording was **not found** in `paper/main.tex`, `abstract_v2.md` or
`intro_revisions.md`. The overreaching text is `CLAIM_SCOPE.md` claim 15's
"structural upper limit on what's even offloadable". This is flagged below.

## Part C — E1

Pre-registration: `E1_PREREGISTRATION.md` (commit `9ac42ab`, before any E1
run). Order `e1/e1_order.csv`: seed 202609261, sha256 `d17cd7de…`.

### Run integrity

| check | result |
|---|---|
| Tables (prefetch off, fresh) | Stencil 1,125,000 distinct (trace 2,948,005, 0 overwrites); GraphBFS 287,956 (trace 481,067, 0 overwrites). **Assertions passed.** |
| Rows | **100 / 100** (`e1/e1_runs.csv`) |
| Order adherence | 100 / 100 in sequence |
| Interruptions / resumes / re-runs | none / none / **none** |
| Commits | every 10 runs, `635c463` … `9813a9f` |
| srcversion | `5997D238EF080B77DBD2AAF` on all 100 runs |
| Exit codes / timeouts | all 0 / none (22 s and 168 s) |
| MemAvailable | before-run 61,050,316–61,438,084 kB; after-run 60,823,884–61,181,644 kB; no drift |
| Free disk | ≥ 39.8 GB |
| dmesg | 0 new lines on 99 runs. Run 92 (GraphBFS C7-L256, ended 18:48:40Z) had 1 line: `workqueue: drm_fb_helper_damage_work hogged CPU for >10000us 4 times, consider switching to WQ_UNBOUND`. This is the framebuffer console, not `nvidia_uvm`, and matches no stop pattern. The run is kept, not re-run. No BUG/Oops/WARNING/GPF/NULL/irqs-disabled line from any source. |
| `ft_predictions = enqueued + drops` | holds on **80 / 80** C7 runs |
| First use of policy 6 + prefetch on | 80 C7 runs with no kernel event |
| `systemctl isolate` | printed "unit file … changed on disk; run daemon-reload". This is informational. It was not acted on, because daemon-reload is outside the allowed commands. |
| Sweep window | 2026-09-25 18:21:57Z – 18:51:02Z |

### Primary family: 8 comparisons, C7-L vs C0

The median is the statistic of record. MWU is exact, with no ties.
Holm is across all 8. Full table: `e1/primary_comparisons.csv`.

| workload | comparison | C0 median (s) | C7-L median (s) | Δ (s) | Δ % | MWU p | Holm thr | verdict | Cohen's d | MDE (s) | MDE α/8 (s) | without outliers: Δ / p / sig (n) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Stencil-24K | C7-L1 vs C0 | 1.1395 | 1.1837 | +0.0443 | +3.89% | 1.08e-5 | 0.0063 | **C7 slower** | +4.15 | 0.0131 | 0.0167 | +0.0446 / 2.2e-5 / yes (10/9) |
| Stencil-24K | C7-L16 vs C0 | 1.1395 | 1.1894 | +0.0500 | +4.38% | 1.08e-5 | 0.0071 | **C7 slower** | +6.73 | 0.0101 | 0.0130 | same / 1.1e-5 / yes (10/10) |
| Stencil-24K | C7-L256 vs C0 | 1.1395 | 1.2350 | +0.0956 | +8.39% | 1.08e-5 | 0.0083 | **C7 slower** | +8.46 | 0.0136 | 0.0174 | same / 1.1e-5 / yes (10/10) |
| Stencil-24K | C7-L4096 vs C0 | 1.1395 | 1.2321 | +0.0926 | +8.13% | 1.08e-5 | 0.0100 | **C7 slower** | +9.73 | 0.0121 | 0.0155 | same / 1.1e-5 / yes (10/10) |
| GraphBFS-23 | C7-L1 vs C0 | 31.5475 | 31.5224 | −0.0251 | −0.08% | 0.853 | 0.0500 | no significant difference | −0.11 | 0.1813 | 0.2314 | same / 0.853 / no (10/10) |
| GraphBFS-23 | C7-L16 vs C0 | 31.5475 | 31.5045 | −0.0430 | −0.14% | 0.315 | 0.0125 | no significant difference | −0.55 | 0.1569 | 0.2003 | −0.0471 / 0.211 / no (10/9) |
| GraphBFS-23 | C7-L256 vs C0 | 31.5475 | 31.5892 | +0.0417 | +0.13% | 0.739 | 0.0167 | no significant difference | +0.04 | 0.1553 | 0.1983 | same / 0.739 / no (10/10) |
| GraphBFS-23 | C7-L4096 vs C0 | 31.5475 | 31.6446 | +0.0971 | +0.31% | 0.796 | 0.0250 | no significant difference | −0.04 | 0.1651 | 0.2108 | same / 0.796 / no (10/10) |

Excluding Tukey-flagged runs changes **no verdict**.

**Falsification trigger:** not fired. No comparison is Holm-significant in
C7's favour. The largest point improvement, GraphBFS L16 at −0.043 s, is
about a quarter of its MDE and p = 0.32.

### Central figure

- `e1_wallclock_vs_L.{png,pdf}`: C0 median as a horizontal line (IQR
  shaded), C7-L runs and medians, one panel per workload.
- Context version: `e1_wallclock_vs_L_with_e09b_context.{png,pdf}`. It adds
  E0.9b's C6-L medians (prefetch off) as a dashed, labelled series from a
  separate session, which is **not tested** against these cells.

### Mechanism metrics (per-cell medians; diagnostic only)

`e1/mechanism_by_L.csv`. **Coverage is a loose upper bound here.** With the
prefetcher on, many predictions target pages it has already brought in, and
`spec_migrations` counts those no-op calls, so coverage must not be read as
pages staged ahead of demand.

| workload | arm | demand faults | predictions | enqueued | not enqueued (drops) | `spec_migrations` | lost after enqueue | coverage (loose upper bound) | `fault_already_resident` (median, min–max) |
|---|---|---|---|---|---|---|---|---|---|
| Stencil | C0 | 347,509 | — | — | — | — | — | — | **0** (0–0) |
| Stencil | C7-L1 | 340,880 | 19,816 | 19,816 | 0 | 16,051 | 3,773 | ≤ 1.4% | 7,513 (7,215–7,702) |
| Stencil | C7-L16 | 338,913 | 79,140 | 79,140 | 0 | 52,624 | 26,310 | ≤ 4.7% | 11,174 (10,465–11,751) |
| Stencil | C7-L256 | 340,024 | 335,030 | 335,030 | 0 | 244,508 | 90,107 | ≤ 21.7% | 29,335 (27,890–31,540) |
| Stencil | C7-L4096 | 344,430 | 344,430 | 344,430 | 0 | 252,656 | 90,782 | ≤ 22.5% | 30,531 (28,579–31,413) |
| GraphBFS | C0 | 44,307 | — | — | — | — | — | — | **0** (0–0) |
| GraphBFS | C7-L1 | 44,487 | 726 | 726 | 0 | 558 | 156 | ≤ 0.19% | 318 (257–400) |
| GraphBFS | C7-L16 | 44,539 | 1,202 | 1,202 | 0 | 1,005 | 192 | ≤ 0.35% | 358 (333–447) |
| GraphBFS | C7-L256 | 44,033 | 1,790 | 1,790 | 0 | 1,511 | 277 | ≤ 0.52% | 399 (316–468) |
| GraphBFS | C7-L4096 | 43,318 | 6,136 | 6,136 | 0 | 5,711 | 449 | ≤ 1.98% | 608 (523–709) |

**C0's `fault_already_resident` is 0 in all 20 C0 runs**, min and max, on
both workloads. The prefetcher alone produces no already-resident faults on
this counter, so **in this gate `fault_already_resident` is attributable to
speculation**.

At most about 8.9% of Stencil's remaining demand faults (30.5k of 344k)
found their page already made resident by the worker. Every such fault
still took the full demand path, because speculation never maps.

`spec_hits` (a 10 ms staleness-window counter, not a win counter) is in the
CSV.

## Exploratory — not confirmatory

None of the following was pre-registered.

1. **At L = 4096 on Stencil, `ft_predictions` equals `demand_faults`
   exactly in all 10 runs** (difference 0, every run).
   - `ft_predictions + ft_skipped` is 1,124,461–1,124,669, essentially the
     whole 1,125,000-entry table, in every C7-L256/L4096 run.
   - Reading: with a large enough window, every remaining demand fault
     yields exactly one prediction, and the cursor sweeps the whole
     first-touch order.
   - About 780k entries are skipped: pages the cursor passes because they
     have already been touched, which with the prefetcher on means mostly
     pages the prefetcher brought in.
   - Predictions drop from 1.125M (E0.9b, prefetch off) to 344k. The work
     queue never saturates: 0 drops, against 205k in E0.9b C6-L4096.
2. **The slowdown grows with L and plateaus at L256–L4096** (+3.9% → +8.4%),
   following the growth in enqueued work (20k → 335k).
   - This fits Part B's finding that the enqueue loop runs on the servicing
     thread and costs real time: about 0.48 s per 1.125M predictions in
     E0.9b, or roughly 0.42 µs each.
   - At 344k predictions that would be about 0.15 s of servicing-thread time,
     against a measured +0.093 s of wall-clock. That is the same order, but
     this is a back-of-envelope link across sessions, not a measurement.
3. **Most `spec_migrations` are probably no-ops here.** At L4096, 252,656
   successful `make_resident` calls coincide with only 30,531 faults finding
   the page already resident. That is consistent with the pre-registered
   caution that many predictions target pages the prefetcher already moved.
   No counter separates the two cases, so this remains an inference.
4. **Across sessions, E0.9b C0 and E1 C0 agree closely:**
   - Stencil 1.1374 s vs 1.1395 s.
   - GraphBFS 31.5931 s vs 31.5475 s.
   - Demand faults 346,440 vs 347,509 (Stencil).

   These were not tested against each other. The agreement is only a
   stability observation.

## Stated limitations

- GraphBFS-23 runs the weakened-cursor oracle. C7 coverage there is
  ≤ 0.19–1.98%, so GraphBFS says little about a first-touch oracle's
  potential. Its null result is a null for *this* oracle.
- `fault_already_resident` means the worker beat the servicing thread, not
  the GPU.
- Coverage is a loose upper bound (see above).
- Speculation never maps; the prefetcher does.
- Single platform: RTX 5070 Ti, 595.91.07, kernel 7.0.0-34.
- Part B's phase attribution rests on the E0.9b pilot (n = 3 + 3 and 2 + 2),
  not a pre-registered sweep.

## Existing claims these results bear on (flagged, not edited)

`CLAIM_SCOPE.md`, the manuscript and all earlier reports are unedited.

- **Claim 7** (the C3 "absolute upper bound" loses to C0):
  - **Strengthened again.** A stronger oracle (first-touch with lookahead)
    also loses to C0 with the prefetcher on (Stencil +3.9% to +8.4%,
    Holm-significant), and does not beat it on GraphBFS.
  - As flagged in E0.9b, "absolute upper bound" should no longer attach to
    C3. The more general statement E1 supports is: *no tested oracle
    configuration, prefetch on or off, beats C0*.
- **Claim 8** (turning off the prefetcher costs more than the oracle can
  recover):
  - Consistent, and now complemented. Keeping the prefetcher on does not
    rescue the oracle either. The combination is worse than the prefetcher
    alone on Stencil.
- **Paper's central claim** (speculation cannot improve the shipped driver):
  - **Supported under the strongest test so far**: perfect first-touch
    knowledge, the prefetcher on, and four lookaheads.
  - The GraphBFS support is bounded by its MDE (≈0.5%) and its weak oracle.
    Any manuscript statement should carry that bound.
- **Claim 5** (no per-hit wall-time saving):
  - E0.9b found a 5.65% saving vs C1 with prefetch off. E1 finds no saving
    vs C0 with prefetch on.
  - The claim holds relative to the shipped driver. E0.9b's qualification
    (it fails relative to prefetch-off C1) still applies.
- **Claim 10** (rate mismatch):
  - No new bearing beyond E0.9b's flag.
  - With prefetch on there are 0 drops. The worker keeps up with the
    remaining fault stream, and there is still no wall-clock benefit.
- **Claim 15** (the pipelining ceiling and D1+D2 offload):
  - **Scope flag from Part B.** "Structural upper limit on what's even
    offloadable" overreaches. The ceiling bounds D1+D2 hiding only.
  - Pre-staging removes D5 work (E0.9b) and falls outside it.
  - Any manuscript use must say "bounds overlapping D1+D2", and must not be
    set beside E0.9b's 5.65%.
- **Manuscript wording:** the brief's "bounds any such scheme" was not found
  in the current manuscript files. If it exists elsewhere (for example an
  unsaved draft), the Part B verdict applies to it.
