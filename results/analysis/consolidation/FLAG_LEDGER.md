# Gate C1 — Flag ledger

Every statement in the Gate E reports (E0 → E5) flagged against an existing document
("flagged, not edited", "bears on", "supersedes", "caveat", "scope flag", or equivalent),
plus three flags surfaced by C1's own source checks (rows 70–72) and two Gate E
statements that bear on metric semantics without being phrased as flags (rows 73–74).
Rows 68–69 are pre-Gate-E / E0.5 flags that Gate E never resolved. Nothing here is
applied; this is the input to `CLAIM_SCOPE_v2_PROPOSED.md`,
`ARTIFACT_CATALOG_ADDITIONS_PROPOSED.md`, and `SUPERSEDED_VALUES.md`.

**The "later report" column decides the action.** A flag is never applied in its original
form if a later gate changed it. Where a later gate overtook a flag, the action given is
for the *final* state, and the original wording is marked "do not apply as written".

Actions: **stands** · **narrow** · **supersede** · **retire** · **new claim** ·
**catalog entry** · **needs decision**.

Quotes are verbatim, from the committed report at HEAD `c266e74`.
`CS` = `CLAIM_SCOPE.md`; `AC` = `ARTIFACT_CATALOG.md`.

| # | source report § | target document and item | the flag, quoted | later report that changes or resolves it | proposed action |
|---|---|---|---|---|---|
| 1 | GATE_E0_REPORT §7 | every oracle (policy 4) result; CS 7, 9, 10 evidence | "The T1 headline oracle traces, while never truncated during recording, are replayed with a cursor that advances roughly 6-12× faster (in per-run terms) than they were recorded" | E0.5 Addition 3 (enumeration, below); E0.5 Step 2/3 (aligned recording, 1:1 verified) | **supersede**: C3 is no longer described as an aligned or "oracle-perfect" predictor anywhere (CS 7 → CS2-7) |
| 2 | GATE_E0_REPORT §3 | trace-ring-derived traces (B9 oversubscription oracle, B10 C4) | "trace-ring truncation with no drop counter and no saturation flag"; the read "returns the correct *set* of the last N pushes but in a **cyclically rotated order**" | E0.5 Step 3 (ring-capacity parameter and a rotation-correcting read path) | **catalog entry** (AC-19) + **supersede** B10 as mechanism evidence (row 69) |
| 3 | GATE_E0_5_REPORT Addition 2 "Consequence" | CS 6 | "The claim's own cited evidence does not support the formula it states." | E0.5 Addendum §3: the formula bounds how many faults *receive* a prediction ("roughly right about *that*"), not the per-enqueued hit rate | **supersede**: CS 6 describes the State-1 one-prediction-per-batch design, which no current module has (CS2-6) |
| 4 | GATE_E0_5_REPORT Addition 3 (table) | gate4_oracle, GATE_B_diagnosis / FIX-1, GATE_D, Gate 1–4 / DECISION ("Path B closed"), T1, T4 / A1, B5 / B6 / B7, A2 / A2b, bimodality, B9 C3, B10 C4, CS 6/7/8/10, manuscript | "no oracle measurement in this project's history has been produced by a driver where recording and consumption operated at matched, aligned rates." | E0.9b, E1, E4: every "upper-bound" question re-measured with an aligned first-touch oracle | **supersede** the "oracle upper bound" framing everywhere. Wall-clock results **stand as measurements of the configuration run** (see SUPERSEDED_VALUES) |
| 5 | GATE_E0_5_REPORT Addendum §3 | AC synthesis | "this is a fourth instance of the project's most recurrent failure mode … alongside artifacts #7, #8, #9. Belongs in the catalog synthesis" | — | **catalog entry** (AC-16) |
| 6 | GATE_E0_5_REPORT "FIX-1's validation rested on single-digit counts" | AC / pitfalls | "'23x more hits' … rests on an absolute difference of 22 events" | — | **catalog entry** (AC-15) |
| 7 | GATE_E0_5_REPORT Addition 2 | FIX-1 validation (`driver/PIPELINE_FIXES.md`) | "`coalesce_probe.cu` is not a good instrument for validating that specific mechanism … it cannot distinguish 'cursor desync fixed' from 'still broken for an unrelated reason.'" | C1 source check: `PIPELINE_FIXES.md:57-63` (the serialized probe scored 0.99 on buggy *and* fixed code) | **catalog entry** (AC-14) |
| 8 | GATE_E0_5_REPORT "Blocked" | platform of record; CS header; manuscript platform table | "The driver was upgraded at the OS level since that port was built, most likely by a routine update" | E0.9b Step 0 (a `COMPLETENESS_LEDGER.md` entry was appended: kernel 7.0.0-34, driver 595.91.07; manuscript platform table stale) | **catalog entry** (AC-23) + CS header platform note (CS2 header) |
| 9 | GATE_E0_7_REPORT Flags | CS 7 "and others citing C3's oracle-upper-bound framing" | "should be read against this gate's finding that the oracle's own 'accuracy' is not a stable, workload-independent property" | E0.8 (reinterpreted as index drift); E0.9 (first-touch oracle replaces index replay) | **supersede** (CS2-7). The accuracy-instability reading itself is superseded by row 12 |
| 10 | GATE_E0_7_REPORT Flags | methodology for any future accuracy proxy | "should report depth=0 alongside depth=1" | — | **stands** (protocol note; no claim-document change) |
| 11 | GATE_E0_7_REPORT §4 (migration compounding) | E0.7's own mechanism | (proposed "later loop iterations" compounding mechanism) | E0.8 §8: "**No.** … recorded here as superseding that section's proposed mechanism" | **retire** |
| 12 | GATE_E0_8_REPORT §7 | E0.7 verdict; new claim | "E0.7's 'closer to genuine divergence' verdict for Stencil-24K is overturned by this gate." | E0.9 §1 Corrections 1–2 (withdraw E0.8's ~51% ceiling and GraphBFS "opposite sense") | **new claim** (CS2-N6, fault-order nondeterminism), with E0.9's corrections applied |
| 13 | GATE_E0_8_REPORT Flags | CS rows citing oracle accuracy | "a self-synchronizing, resync-on-match oracle … has direct empirical support for Stencil-24K specifically" | E0.9: a first-touch oracle was built instead; the resync oracle was never built | **retire** (the path was not taken; no claim rests on it) |
| 14 | GATE_E0_8_REPORT §6 | E0.8's own GraphBFS reading | "the opposite sense from what pure index-drift would predict" | E0.9 §1 Correction 2: "**The 'opposite sense' argument in E0.8 §6 is withdrawn.**" | **retire** — do not apply as written |
| 15 | GATE_E0_8_REPORT §4 | E0.8's "~50% ceiling" | "a real residual disagreement in first-touch order exists for both workloads at the *reduced-sequence* windowed scale" | E0.9 §1 Correction 1: "Withdrawn from E0.8's reading" | **retire** + **catalog entry** (AC-18, recurrence) |
| 16 | GATE_E0_9_REPORT Flags | AC | "forward-only metric mistaken for symmetric; direction-discarding absolute value — both belong alongside artifacts #7-#9's 'aggregation level' pattern" | — | **catalog entry** (AC-18) |
| 17 | GATE_E0_9_REPORT Flags | claim text on hit rates | "the first-touch oracle reaches 92-100% hit rate on Stencil-24K depending on depth" | E0.9a-2 §5: `spec_hits` is a 10 ms staleness window that collapses at large L; E0.9b labels it "not a win counter" | **narrow**: never cite a `spec_hits` hit rate as success; cite `fault_already_resident` and coverage (CS2-N7) |
| 18 | GATE_E0_9_REPORT §2 | policy numbering | "**Implemented as policy 6 instead**" (policy 5 is `SPECASYNC_POLICY_NULL`) | E0.9a-2 §2 "accepted permanently" | **stands** (design record) |
| 19 | GATE_E0_9A2_REPORT §9 | CS; manuscript discussion of off-path designs | "Off-path staging that updates residency without installing a mapping can reduce the cost of a fault but can never eliminate one, under this UVM driver's current design." | **E5 (pre-registered): H-feed supported.** With the prefetcher on, residency staged by speculation lets the prefetcher's service step map regions, and faults fall ~40% (D(51) = +0.401) | **narrow** — do not apply as written. H-map (speculation itself never maps) **stands** (CS2-N2). "Can never eliminate one" holds only when the density rule cannot act: prefetch off, or T_off |
| 20 | GATE_E0_9A2_REPORT Flags | AC | "a real, physical-machine kernel crash caused by an unchecked NULL from a function whose own internal safety check (`UVM_ASSERT`) is silently non-fatal in production" | — | **catalog entry** (AC-22) |
| 21 | GATE_E0_9A2_REPORT §5 | `spec_hits` as a metric | "This is a second, independent way `spec_hits` undercounts real speculative effect" | E0.9b prereg ("10 ms staleness-window counter, not a win counter"); C1 source check: `SPECASYNC_HIT_MAX_AGE_NS` = 10 ms, `SPECASYNC_HIT_TABLE_SLOTS` = 256 | **new claim** (CS2-N7) + **catalog entry** (AC-20) + HITRATE_REREAD |
| 22 | GATE_E0_9A2_REPORT §1 | E0.9a's own reading | "E0.9a's '21,600-fault reduction is directionally right' is withdrawn." | — | **retire** (internal; appears in no claim document) |
| 23 | GATE_E0_9A2_REPORT §8 | the E0.9b win metric | "Prevented faults must not be used as E0.9b's win metric — it is structurally zero under this driver's current mapping architecture" | E5: faults *are* prevented once the prefetcher can act on speculative residency | **narrow**: prevented faults are structurally zero *for speculation acting alone* (prefetch off / T_off); nonzero via H-feed |
| 24 | GATE_E0_9B_REPORT claims — CS 7 | CS 7 | "'absolute upper bound' should no longer attach to C3" | E1 (repeats); E4 (a stronger configuration beats C0) | **supersede** (CS2-7) |
| 25 | GATE_E0_9B_REPORT claims — CS 8 | CS 8 | "**Supported** with the stronger oracle. The best C6 cell recovers 7.7% of the Stencil prefetch-off gap" | E1, E4 (F4 Holm-sig), E5 | **stands**, strengthened (CS2-8) |
| 26 | GATE_E0_9B_REPORT claims — CS 5 | CS 5 | "The claim's direction does not hold for a first-touch oracle with large lookahead, relative to the prefetch-off baseline." | E4: also contradicted relative to **C0** at W = 512 | **supersede** (CS2-5) |
| 27 | GATE_E0_9B_REPORT claims — CS 10 | CS 10 | "The rate mismatch applies to *reactive* prediction … The claim's scope should say 'without lookahead'." | E1b / E3b (the servicing-thread cost is the oracle's lookup, not dispatch latency); E4 (width sidesteps it); C1 row 71 | **retire** the race as the explanation of the near-zero hit rate (CS2-10). A1/B6 dispatch-latency *measurements* stand |
| 28 | GATE_E0_9B_REPORT claims — CS 6 | CS 6 | "not directly tested" | E0.5 row 3 | **supersede** (CS2-6) |
| 29 | GATE_E0_9B_REPORT Step 5 prediction test | servicing-window ceilings | "Any existing or future use of servicing-window differences as a *ceiling* on wall-clock saving should be treated as unreliable on this evidence." | E1 Part B §4: the net window already subtracts the enqueue loop's +0.477 s | **catalog entry** (AC-25) |
| 30 | GATE_E0_9B_REPORT Step 1 Q2 | paper's statement about the prefetcher | "the paper can state it from source" (the prefetcher maps prefetched pages in the same service step; speculation only makes faults cheaper) | E5_MECHANISM §2 (re-confirmed at `uvm_va_block.c:11532/11961/11981`) | **stands** (part of CS2-N2/N3) |
| 31 | GATE_E1_REPORT claims — CS 7 | CS 7 generalisation | "*no tested oracle configuration, prefetch on or off, beats C0*" | **E4 falsification trigger** (C7-W512 beats C0 on Stencil) | **retire** the generalisation — do not apply as written |
| 32 | GATE_E1_REPORT claims — CS 8 | CS 8 | "Consistent, and now complemented." | E4, E5 | **stands** (CS2-8) |
| 33 | GATE_E1_REPORT claims — central claim | paper's central claim | "**Supported under the strongest test so far**" | **E4** (falsified in that form on Stencil); E5 (replicated) | **supersede** (CS2-N1) |
| 34 | GATE_E1_REPORT claims — CS 5 | CS 5 | "The claim holds relative to the shipped driver." | E4 (contradicted at W = 512) | **supersede** (CS2-5) |
| 35 | GATE_E1_REPORT claims — CS 10 | CS 10 | "The worker keeps up with the remaining fault stream, and there is still no wall-clock benefit." | E4 (a wall-clock benefit exists at W = 512) | **retire** (CS2-10) |
| 36 | GATE_E1_REPORT claims — CS 15 | CS 15 | "**Scope flag from Part B.** 'Structural upper limit on what's even offloadable' overreaches." | E4, E5 (gains via D5 and fault prevention, not D1+D2) | **narrow** (CS2-15) |
| 37 | GATE_E1_REPORT Exploratory 2 | handoff cost framing | "about 0.48 s per 1.125M predictions in E0.9b, or roughly 0.42 µs each" | **E1b** ("a ratio, not a per-prediction cost"; enqueue 54–75 ns/prediction); **E3b** (per-fault residual is the oracle lookup) | **retire** (CS2-N5) |
| 38 | E1_PARTB §4 | CS 15 | "scope 'structural upper limit on what's even offloadable' to 'upper limit on what hiding D1+D2 can recover'" | E4, E5 | **narrow** (CS2-15) |
| 39 | E1_PARTB §4 | future manuscript text | "it must say that it bounds *overlapping D1+D2*, not off-path schemes in general. It must not be placed next to E0.9b's 5.65%" | — | **stands** (writing rule; SUPERSEDED_VALUES, Section I list) |
| 40 | E1_PARTB §4 | E0.9b failed prediction | "**E0.9b's failed prediction test is explained, in part.**" | — | **stands** (detail for AC-25) |
| 41 | E1B_HANDOFF_COST §4 | paper's structural claim (handoff on the critical path) | "Its stated mechanism should be **'per-fault prediction work plus the per-prediction enqueue'**, not 'the enqueue handoff'." | **E3b**: the per-fault work was mostly the oracle's own lookup and lock (77.6–87.8% removed at fast = 1); **E4**: amortised by width | **new claim** (CS2-N5), in its E3b/E4 form |
| 42 | E1B_HANDOFF_COST §4 | E3a design premise | "Skipping an enqueue … saves at most the enqueue share (≈13–31%) of the loop's cost." | E3a-2 (skip retained, with an 8-slot history); E4 (W512 outside-lock 0.0058 s) | **stands** (design rationale; no claim-document change) |
| 43 | GATE_E3B_REPORT claims — E0.9b / E1 | E0.9b and E1 conclusions | "These conclusions **carry an expensive-oracle caveat** until re-tested at `specasync_ft_fast=1`." | **E4**: "**The E3b expensive-oracle caveat can now be retired for these questions.**" | **retire** — do not apply as written |
| 44 | GATE_E3B_REPORT claims — E1b | the handoff claim | "Confirmed, and now attributed: that work was mostly the oracle's lookup and lock." | E4 | **new claim** (CS2-N5) |
| 45 | GATE_E3B_REPORT claims — CS 10 | CS 10 | "with a cheap oracle, queue-full drops rise. The worker's drain rate, not the predictor, becomes the limit" | E4 (width: 0 drops at W64/W512 on Stencil) | **retire** (CS2-10); the drain-rate observation is folded into CS2-N5 |
| 46 | E3B_STATUS Step 1 | e09b harness `check_after` | "The shared E0.9b `check_after` has the same weakness: when its prefix check fails it scans the last 200 lines." | E3b fix (`tests/e3b_dmesg.py`), used in E3b, E4, E5 | **catalog entry** (AC-24) |
| 47 | E3B_STATUS Step 2 | E3a-2 test plan ("W × calls" checks) | "`group_probe` did not exercise the widened migration path at all." | E3b Step 3 (Stencil exercised it: 16.00 / 64.00 / 511.83 pages per call) | **catalog entry** (AC-14, second instance: a check that held trivially) |
| 48 | E3B_ORACLE_COST "D5" | copy-offload mechanism | "a faster predictor overruns the worker queue … the under-lock saving shrinks by 23%" | E4 (width removes drops; C6-W64/W512 D5 0.49 s) | **stands** (folded into CS2-N4) |
| 49 | GATE_E4_REPORT headline | paper's central claim | "**The paper's central claim, that speculation cannot improve the driver as it ships, no longer holds in that form.**" | E5 (replicates −5.26%; explains the mechanism) | **new claim** (CS2-N1) |
| 50 | GATE_E4_REPORT claims — E1 | E1's "cannot beat C0" | "**Does not hold for C7-W512.** It must be scoped to single-page speculation." | E5 | **narrow** (CS2-N1 / CS2-7) |
| 51 | GATE_E4_REPORT claims — E0.9b 5.65% | E0.9b result | "The expensive oracle **understated** speculation's gain with the prefetcher off" | — | **supersede** (E0.9b stands only as an expensive-oracle measurement; SUPERSEDED_VALUES) |
| 52 | GATE_E4_REPORT claims — E3b caveat | E3b caveat | "**The E3b expensive-oracle caveat can now be retired for these questions.**" | — | resolves row 43 (**retire**) |
| 53 | GATE_E4_REPORT claims — CS 5 | CS 5 | "contradicted relative to C0 on Stencil at W = 512" | — | **supersede** (CS2-5) |
| 54 | GATE_E4_REPORT claims — CS 7 | CS 7 | "As a statement about C3 it stands. The generalisation … **no longer holds**." | — | **narrow** (CS2-7) |
| 55 | GATE_E4_REPORT claims — CS 8 | CS 8 | "**supported, strongly.**" | E5 | **stands** (CS2-8) |
| 56 | GATE_E4_REPORT claims — CS 10 | CS 10 | "The rate mismatch is sidestepped by width, not by a faster worker." | — | **retire** (CS2-10) |
| 57 | GATE_E4_REPORT claims — CS 15 | CS 15 | "The E1 Part B scope flag stands … The ceiling does not bound it." | E5 | **narrow** (CS2-15) |
| 58 | GATE_E4_REPORT claims — structural claim | handoff on the critical path | "still true. It is **amortised** by width" | — | **new claim** (CS2-N5) |
| 59 | GATE_E4_REPORT Exploratory 4 | mechanism of the E4 gain | "A hypothesis, **untested**: … the demand path's own service step, with the stock prefetcher on, maps the already-resident region" | **E5 pre-registered: H-feed SUPPORTED** | **new claim** (CS2-N3) |
| 60 | GATE_E4_REPORT limitations | scope of every E4 claim | "The first-touch table is a **perfect oracle** … an upper-bound demonstration, not a practical predictor's result." | — | **stands** (scope qualifier on CS2-N1/N3/N4) |
| 61 | GATE_E5_REPORT claims — E4 Expl. 4 | E4 exploratory 4 | "Now **supported by a pre-registered test for the fault reduction.** … **Corrected in scope:** the fault reduction is not the only source" | — | **new claim** (CS2-N3, CS2-N4) |
| 62 | GATE_E5_REPORT claims — central | paper's central claim | "E4's falsification … stands, and E5 **replicates it**" | — | **new claim** (CS2-N1) |
| 63 | GATE_E5_REPORT claims — H-map | H-map | "**stands**. At T_off, 99.95% of pages are staged and no fault is prevented." | — | **new claim** (CS2-N2) |
| 64 | GATE_E5_REPORT claims — CS 8 | CS 8 | "**consistent.** C7W512-toff (3.68 s) is still 3.27× C0-t51 (1.13 s)." | — | **stands** (CS2-8) |
| 65 | GATE_E5_REPORT claims — CS 15 | CS 15 | "the E1 Part B scope flag stands" | — | **narrow** (CS2-15) |
| 66 | GATE_E5_REPORT headline | copy-offload mechanism | "**A pre-registered secondary prediction failed, and it is reported plainly.**" | — | **new claim** (CS2-N4) |
| 67 | E5_MECHANISM §3 | `uvm_perf_prefetch_threshold` usage | "values above 100 **silently fall back to 51**, while read-back still shows the raw value" | averted before any run (T_off chosen as 100) | **needs decision**: do averted hazards belong in the catalog? (OPEN_DECISIONS D5) |
| 68 | OVERSUB_C3_VERIFICATION (end) | AC | "a candidate `ARTIFACT_CATALOG.md` entry (interpretation-against-a-crippled-baseline …) -- **flagged here, not added**" | the standing rule "baselines named explicitly", adopted in every Gate E pre-registration | **catalog entry** (AC-12, promoted) |
| 69 | GATE_E0_5_REPORT Addition 3 (B10 row) | B10 (C4) mechanism narrative | "**2**, additionally truncated + rotated" | — | **supersede**: B10 becomes a wall-clock measurement of a configuration with an invalid predictor, excluded from claims (CS2-N9) |
| 70 | C1 source check: `driver/PIPELINE_FIXES.md:57-63` | AC rejected hypothesis "spec_hits never fires" | "The old code scores high on the *serialized* probe only by a degenerate 'self-hit': it tags the page that is *currently* faulting (zero lead time)." | — | **narrow**: the rejected-hypothesis verdict "the counter is sound" should read "fires as coded; measures a 10 ms window; the 254/256 probe score included zero-lead self-hits" |
| 71 | C1 cross-reading: CS 10, GATE_T4 §2–3, GATE_A1 Result 3, B6-T2 Result 3 | the dispatch-race explanation | GATE_A1: "Near-zero real-workload hit rate is fully explained by (a) dispatch-latency race loss" | E0 §7 / E0.5 (oracle misaligned), E0.8 (index drift), E0.9a-2 (`spec_hits` semantics), E0.9b (`fault_already_resident` = 919,262 at L4096: the worker *does* beat the servicing thread) | **retire** (CS2-10, HITRATE_REREAD) |
| 72 | C1 source check: E0 §1 vs AC #1 | AC #1 root-cause text | AC #1: "Fault trace recorded once **per demand fault**" | E0 §1: recording is "one trace entry per va-block dispatch group"; E0.5 Addition 1 (FIX-1 introduced the over-consumption) | **narrow** AC #1's root cause (AC-13) |
| 73 | E0.9B Step 1 Q1 | `spec_migrations` / coverage | "**`spec_migrations` counts successful `make_resident` calls, including no-op calls on pages already resident.**" | E1 / E4 / E5 prereg (coverage stated as an upper bound) | **new claim** (CS2-N7, metric semantics) |
| 74 | E3A2_REVIEW B3 | analysis identity | "Never add the work ring's THROTTLED count to `spec_region_invalid`." | used in E4/E5 | **stands** (methodology; CS2-N7 note) |

## Summary of actions (primary action per row; 74 rows)

| action | count | rows |
|---|---:|---|
| stands | 13 | 10, 18, 25, 30, 32, 39, 40, 42, 48, 55, 60, 64, 74 |
| narrow | 11 | 17, 19, 23, 36, 38, 50, 54, 57, 65, 70, 72 |
| supersede | 12 | 1, 3, 4, 9, 24, 26, 28, 33, 34, 51, 53, 69 |
| retire | 14 | 11, 13, 14, 15, 22, 27, 31, 35, 37, 43, 45, 52, 56, 71 |
| new claim | 12 | 12, 21, 41, 44, 49, 58, 59, 61, 62, 63, 66, 73 |
| catalog entry | 11 | 2, 5, 6, 7, 8, 16, 20, 29, 46, 47, 68 |
| needs decision | 1 | 67 |

**Secondary actions:**
- Row 2 also supersedes B10 as mechanism evidence (row 69).
- Row 8 also changes the CS header.
- Row 15 is also a catalog entry (AC-18).
- Row 21 is also a catalog entry (AC-20) and HITRATE_REREAD input.
- Row 72 is also a catalog entry (AC-13, which narrows AC #1).
- Rows 29 and 47 also carry a narrowing, expressed through their catalog entries.

**Flags that must not be applied in their original form, because a later gate changed
them:**
- rows 14 and 15 (withdrawn by E0.9);
- row 19 (narrowed by E5);
- row 23 (narrowed by E5);
- row 31 (retired by E4);
- row 33 (superseded by E4);
- row 43 (retired by E4);
- row 45 (overtaken by E4's width result).
