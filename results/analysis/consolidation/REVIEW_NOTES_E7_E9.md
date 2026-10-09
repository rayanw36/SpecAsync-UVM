# Review notes: Gates E7, E7-T4, E8, E9 (Gate C4)

No report is edited; this file sits beside them. Evidence ids are in `EVIDENCE_EXTRACT.md`.

## 1. E7's "no workload slower" is scoped to E7's workloads

`GATE_E7_REPORT.md` finds no Holm-significant slowdown at a lower threshold on the eight other workloads it tested (`E7.B.*`), and the T4 replication finds none either
(`T4.B.count`: 14 tests, 12 faster, 0 slower). E8's adversarial benchmark gives counter-examples: oversubscribed sparse access is +41.15% to +84.96% slower at t0
(`E8.range.ov_sparse_t0`). The E7 statement is true of E7's workloads and is not a general property; CS2-N10 now says so.

## 2. E8's "host write identical across thresholds" is contradicted by E9's CPU-fault counts (status: see the update below)

`GATE_E8_REPORT.md` (Limitations) states that the host's initial write of the whole array, inside the timed process, is identical across thresholds and only dilutes relative effects.
E9 counts **6.00x more CPU page faults at t51 than at t0 in all seven workloads** (`E9.ratio.cpu_faults_t51_over_t0`); at t0 the count equals the number of 2 MB blocks. If those faults are on the host
first-touch path, the host write is **not** identical across thresholds. The source-code and phase-split checks that bear on this are in `CPU_FAULT_CHECK.md`.

## 3. E8's XS4 and XS5 failed

XS4 (t0's delta rises monotonically as K falls) failed in both sizes: K = 64 is faster than K = 512 (in-memory -9.69% vs -7.54%; oversubscribed -9.67% vs -7.66%).
XS5 (the t25 delta lies between the t0 delta and 0, cell by cell) failed in three cells: in-memory K = 1 and K = 8, and oversubscribed K = 8 (t25 +46.71% is worse than t0 +41.15%).
The pre-registered verdict (GENERALITY FALSIFIED) does not depend on either. They show the dependence on K is not monotonic and t25 is not an interpolation of t0.

## 4. E9's cap re-anchor

The E9 session was paused after Phase 3 and resumed the next day; by wall-clock the 3.5 h cap had expired. I applied the cap to **working time** and recorded the re-anchor in `e9/cap_anchor.txt`
(resume minus the ~10 minutes already used), leaving `e9/phase0_start.txt` unchanged. The **E9 pre-registration was committed after the pause** (it was written and pushed on the resumed day, before any traced run), so the
pause did not separate a pre-registration from its data. The decision is mine and was not authorised in advance; it should be reviewed.

## 5. Kernel lines logged under nsys

Every traced E9 run logged one new kernel line, `NVRM: GPU0 refcntRequestReference_IMPL: Failed to enter state 1 (current state: 0, status: 0x00000056)`, only while traced runs were active; untraced E8 runs counted none.
It is not in the stop pattern and no run failed. Its source (nsys's GPU-control path, by timing) is **not established**. If E9's counts matter for a claim, a short untraced-vs-traced comparison would show whether tracing changes behaviour.

## 6. The three D6 mismatches (`consolidation/D6_REGENERATION.md`; prose not corrected)

| row | quantity | data | report prose |
|---|---|---:|---:|
| 5 | Stencil-24K max \|rank diff\|, trace vs depth=1 replay | 107 | 105 (`GATE_E0_8_REPORT.md` section 4) |
| 5 | same, vs depth=0 replay | 105 | 107 |
| 8 | Stencil L=1 depth=1 logged predictions | 141,484 (E0.9a-2 raw) | 140,909 (E0.9a prose; a different run) |

## 7. The T4 cross-version Stencil observation (untested)

On the T4, this session's stock-t51 Stencil-24K median is **5.808 s** (driver 595.91.07, `T4.cross_version.stencil_t51`), against **4.185 s** for the old T4 C0 runs (driver 595.71.05, `GATE_T1_REPORT.md`; **PROSE-ONLY**,
no committed CSV): +38.8%. Different driver version, kernel, instance and session; no test was run and no inference is drawn. It is recorded because it is large.

## 8. Other observations from this session

- CS2-N10's "+41.15% to +84.96%" is the oversubscribed K in {1, 8} **t0** range. The oversubscribed K = 1 **t25** cell is only +1.88% (`E8.range.ov_sparse_t25`), outside that range; the text is applied as written.
- T4 GraphBFS-23 is Holm-significantly "faster" at -0.14% and -0.11%, but both are below their MDEs (0.26%, 0.22%) (`T4.B.graphbfs.vs_mde`), so "no effect beyond the MDE" holds while the rows are labelled significant.
- The Section I draft 3 states "All Gate-series results are from one platform" (a `[T4]` placeholder in the draft); that sentence is now out of date (CS2-N10's dense-access part has two platforms).
- The id checker `tests/c1_check_ids.py` did not recognise E6, E7, E8, E9, T4 or D6 ids until this gate; its prefix list was extended (234 cited ids now resolve, 0 unresolved).
