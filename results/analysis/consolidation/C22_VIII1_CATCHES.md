# C22 VIII-1 / I-4: where each catalog entry was caught (all 31)

Script `tests/c22_viii1_catches.py`; source `ARTIFACT_CATALOG.md` ('How caught' of each entry; the families table columns), checked by assertion: the entries the table lists under 'caught by a pre-registered test' are exactly #10, #21, #25, #30; every 'original analysis' entry (#5, #14, #20) is classified in-gate. The supplement S3 reproduces the same entries unchanged.

Definitions used. **Inside its own gate:** the catch happened in the gate or session that produced the error, by that gate's own analysis, checks, pre-registered test, harness or by the failure itself; later independent passes, reviews and later gates are outside. **Pre-registered check:** a test or smoke pass whose expectation or rule was committed before the measurement it judged.

| # | entry | catching mechanism | inside its own gate? | check written before the measurement? | note |
|---|---|---|---|---|---|
| 1 | Oracle cursor desync | later independent re-investigation (Gate B, serialized-vs-coalesced probe) | N | N |  |
| 2 | ASLR address instability | the same Gate B investigation | N | N |  |
| 3 | STREAM host-ordering noise | later interleaved re-run with a null-worker control (Gate C) | N | N |  |
| 4 | T2==T3 timer collapse ("metadata ~99% of service time") | later source inspection (Gate C) | N | N |  |
| 5 | `ring_read_binary` byte-offset drift | same-session accounting-closure gate G1 of Phase C (D1+D2+svc+D6+D7 within 2% of total) | Y | pre-defined in the Phase C plan, not a committed pre-registration | caught before any number reached a report (catalog: 'the one artifact caught within the same session'); catalog column: original analysis |
| 6 | cuFFT hit-rate blocked-protocol outlier (25.47%) | later reproduction (Task T2, interleaved rerun) | N | N |  |
| 7 | Ring saturation without wraparound | later passes (A1 open item, T4 correction note, 2026-08-13 correction pass) | N | N |  |
| 8 | Rate-arithmetic 15x aggregation error | dedicated verification pass (Part 2) | N | N |  |
| 9 | Ceiling units mismatch | verification pass that tested a different hypothesis | N | N |  |
| 10 | `setarch -R` regime effect | pre-registered test A2b (a follow-on gate to A2, before any dependent claim was published) | Y | Y | A2 flagged the observation; A2b was pre-registered to test it; counted in-gate by the catalog (Section VIII) |
| 11 | Host memory leak as a run-order confound | the failure itself: a near-OOM forced a stop and a characterization pass | Y | N | caught in the session that suffered it |
| 12 | Comparison against a crippled baseline | independent verification pass mandated by the trigger policy | N | N | the policy required a pass; no pre-registered check of this error existed |
| 13 | Oracle recording/consumption granularity mismatch, with a diagnosis that mislabelled the recording side | independent source audit (Gate E0), 103 days later | N | N |  |
| 14 | A positive control that could not fail | instances 1-2: independent later pass (E0.5); instance 3: the original analysis, in the same step (counters read with the question 'was the path exercised at all?') | Y (instance 3 only) | N | instance 3 was a question asked of the data, not a committed check |
| 15 | A relative improvement accepted without an absolute ceiling | independent pass (E0.5) | N | N |  |
| 16 | Denominator mismatch: per-enqueued hit rate against a per-fault ceiling | independent pass (E0.5), recomputing from the raw ring | N | N |  |
| 17 | Index drift: duplicate-fault counts vary run to run and silently break index-based replay | independent analysis-only pass (E0.8) | N | N |  |
| 18 | Forward-only metric asymmetry under a shift, including its recurrence inside the gate that diagnosed it | next independent pass (E0.8), then external review | N | N |  |
| 19 | Circular trace ring read in physical-slot order: truncated *and* rotated, with no signal | independent source audit (E0) | N | N |  |
| 20 | `spec_hits` counts a timing window, not wins | the original analysis: a second, redundant counter (`fault_already_resident`) kept rising while `spec_hits` fell, in the same table (E0.9a-2) | Y | N | redundant measurement, not a pre-written check |
| 21 | An upper-bound instrument carrying its own cost | first E1b (forced by a reviewer's challenge to E1), then E3b (pre-registered test, expectation committed before the run) | N | Y (the E3b catch; a later gate than the one that made the error) | the first catch (E1b) was not pre-registered and not in-gate |
| 22 | A UVM helper guarded only by a non-fatal `UVM_ASSERT` returned NULL: a kernel oops on real hardware | a kernel oops (crash), user present | Y | N |  |
| 23 | Silent platform drift from unattended upgrades | operational preflight at the next session (a module refused to load) | N | N | platform drift between sessions, caught by the failure itself |
| 24 | Line-count `dmesg` diffs fail on a full, rotating log buffer | the original harness run: the rejection test failed loudly | Y | N |  |
| 25 | A pilot ceiling that failed its own prediction test | pre-registered prediction test (E0.9b addendum, committed before the sweep) | Y | Y | the only aggregation-level entry caught in-gate |
| 26 | A status log asserting a state the primary record contradicts, and times typed as estimates | read-only journal re-account (E6) and the E8 review | N | N |  |
| 27 | A helper with a hard-coded multiplicity correction reused across gates | the author of a later gate (E7) reading the helper | N | N |  |
| 28 | A build script that swallows a failure when a Git-LFS patch is only a pointer | the failing compile, then reading the script output | Y | N |  |
| 29 | A session that ended itself by killing the login session containing it, and an orchestrator that died with its session | the failure itself; recorded as amendments before any timed run | Y | N |  |
| 30 | A pre-registration that checked VRAM but not host RAM | pre-registered smoke pass (an OOM kill) of the same gate | Y | Y |  |
| 31 | `memory.used` read as migrated volume, validated on one allocator only | inspection of the managed t51 cell against the density rule after the gate, confirmed against E9 | N | N | the gate's own scoring did not catch it |

## Counts

- **Caught inside its own gate (any mechanism): 11 of 31** - #5, #10, #11, #20, #22, #24, #25, #28, #29, #30 outright, and #14 for instance 3 only (instances 1-2 were caught by a later pass). By mechanism: original analysis [5, 14, 20] (#5, #14 instance 3, #20); pre-registered tests or smoke passes #10, #25, #30; the failure itself (crash, loud harness, forced stop, failed compile, session end) #11, #22, #24, #28, #29.
- **Caught by a pre-registered check: 4 of 31** - #10, #21, #25, #30 (the catalog table column). Of these, **inside the gate that made the error: 3** (#10, #25, #30); #21's pre-registered catch (E3b) came in a later gate, after a first, review-forced catch (E1b), so it is not an in-gate catch under the definition above.
- Caught only by a later independent pass, review or later gate: #1, #2, #3, #4, #6, #7, #8, #9, #12, #13, #15, #16, #17, #18, #19, #21, #23, #26, #27, #31 (20 entries; #23 is caught by the next session's preflight).
- Aggregation-level family (9 entries): 8 caught by a later pass or review, 1 (#25) in its own gate by a pre-registered test (unchanged from C14).

## What this means for the two statements

1. **"caught inside its own gate"** (Section VIII: "four errors were caught inside their own gate, and all four by a check written before the measurement"; Section I similar). By the definition above 11 entries (10 plus #14's third instance) were caught inside their own gate, of which only 3 (#10, #25, #30) by a pre-registered check; the four-entry set {#10, #21, #25, #30} is the set caught by a pre-registered check, and #21's catch came in a later gate. The sentence is accurate if read as "four were caught by a check written before the measurement" (with #21's caught in the following gate E3b) and understates the in-gate catches if read literally.
2. **"caught by a pre-registered check"**: 4 of 31 (#10, #21, #25, #30), matching the catalog's families table. #5 (Phase C's accounting-closure gate G1) was a check defined in the phase plan before the run but not a committed pre-registration (the pre-registration regime starts with E0.9b), #14 instance 3 and #20 were caught by the original analysis without a pre-written check.

Suggested wording for the author (not applied): "Eleven of the 31 errors were caught inside the gate that made them (by its own analysis, by a crash or loud harness failure, or by a pre-registered test); four were caught by a check written before the measurement."
