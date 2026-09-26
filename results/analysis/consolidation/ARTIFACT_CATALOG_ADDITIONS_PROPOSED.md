# ARTIFACT_CATALOG — proposed additions (not applied)

This is a proposal for review. **`ARTIFACT_CATALOG.md` is not edited.** The current
catalog ends at entry **#11** ("Host memory leak as a run-order confound"), so new
entries start at **#12**. The long-standing candidate is promoted first. Each entry
below was checked against the report named in it.

Two amendments to **existing** entries are also proposed:
- to #1 (root-cause text), in AC-13;
- to the rejected-hypothesis row "`spec_hits` never fires", in AC-14 / AC-20.

Numbers carry the same markers as `CLAIM_SCOPE_v2_PROPOSED.md`: an evidence id from
`EVIDENCE_EXTRACT.md`, or **PROSE-ONLY**.

---

## New entries

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
- **How caught:** an **independent source audit** (Gate E0), about three months
  after FIX-1, by tracing the consumption loop rather than trusting the recording
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

---

## Families and synthesis

Each entry, old (#1–#11) and new (#12–#25), is assigned one primary family.

| family | entries | caught by the original analysis | caught only by a later, independent pass or review | caught by a pre-registered test | caught by the failure itself (crash / loud harness / preflight) |
|---|---|---|---|---|---|
| **Aggregation-level mismatch** | #7, #8, #9, #13, #16, #17, #18, #25 | — | #7, #8, #9, #13, #16, #17, #18 (E0.7 → E0.8; E0.8's recurrence → external review) | #25 | — |
| **Validation that could not fail** | #1, #2, #12, #14, #15 | #14 (instance 3, group_probe) | #1, #2 (Gate B re-investigation), #12 (verification pass mandated by the trigger policy), #14 (instances 1–2), #15 | — | — |
| **Instrument cost and instrument blindness** | #4, #5, #19, #20, #21 | #5 (Phase C's same-session accounting-closure check), #20 (a second counter disagreed in the same table) | #4, #19, #21 (E1b, forced by review) | #21 (E3b) | — |
| **Operational hazards** | #3, #10, #11, #22, #23, #24 | — | #3 (interleaved re-run) | #10 (A2b was pre-registered to test it) | #11 (near-OOM forced a stop), #22 (crash), #23 (preflight), #24 (loud harness failure) |
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

**The catalog's existing observation holds for this family without exception so
far.** Every instance that produced a published number was caught by an
independent pass or external review, never by the analysis that produced it.

#18 sharpens the point. The gate that diagnosed the forward-only failure repeated it
two checks later, and it took outside review to catch the recurrence. Knowing the
failure mode is not protection.

**The one exception is #25, and it is instructive.** It was caught by the analysis
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
Crashes, drift and harness failures:
- host-ordering noise (#3);
- the `setarch -R` regime (#10);
- a host memory leak (#11);
- a kernel oops (#22);
- silent driver and kernel upgrades (#23);
- a dmesg diff broken by a rotating log (#24).

These were mostly caught because they *failed loudly*: a crash, a module that would
not load, a test that stopped. The dangerous members are the quiet ones:
- #11 and #23 would have corrupted comparisons without any visible failure;
- #24's fallback kept working, but with a shrinking safety margin.

The response in this project has been procedural: preflight records, stop
conditions, and compile-only review before the first load.

### Does "#7–#9 were all caught by independent verification" generalise?
**Only within its own family.**
- All seven aggregation-level mismatches that produced published numbers were
  caught by independent passes or review.
- Across the whole catalog, three other catching mechanisms appear:
  - **pre-registration** (#10, #21, #25);
  - **redundant measurement inside the original analysis** (#5's closure identity,
    #20's second counter);
  - **loud failure** (#11, #22, #23, #24).
- The two cheapest mechanisms, pre-registered predictions and a second counter for
  the same quantity, caught errors *during* the gate that made them. Independent
  verification caught them only later, after they had propagated into other reports
  (#13 reached every oracle result for about three months).

---

## Candidate not added (needs decision)
- **Silent parameter fallback invisible to read-back** (`E5_MECHANISM.md` §3):
  `uvm_perf_prefetch_threshold` above 100 silently becomes 51, while
  `/sys/module/.../parameters/` still shows the raw value. It was **averted** by
  the source check before any run, so it never produced a result. Whether averted
  hazards belong in a catalog of artifacts is `OPEN_DECISIONS.md` D5.
