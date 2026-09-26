# Gate C1 Step 5 — Superseded values register

Every number or statement found in the manuscript files (`paper/`), `CLAIM_SCOPE.md`
and the earlier reports that later gates superseded. **No file listed here is edited.**
Line numbers are at HEAD `c266e74`.

## Standing distinction
Pre-E0.5 oracle results fall into two kinds.
- **Wall-clock measurements** of a configuration (for example C3 = policy 4, depth 1,
  prefetch off) are *not* superseded as numbers. What is superseded is any
  description of that configuration as "oracle-perfect" or an "upper bound", and
  any mechanism built on its `spec_hits` counts.
- **Hit rates** (`spec_hits ÷ enqueued`) remain valid counts of a 10 ms-window
  coincidence event, and are superseded as measures of prediction success.

Rows marked (i) are superseded *interpretations* of numbers that stand. Rows marked
(v) are superseded *values*.

## Register

| file:line | superseded text | why | replacement, with source |
|---|---|---|---|
| `paper/intro_revisions.md:28-29` | "The oracle policy provides an upper bound on achievable speculation benefit and motivates further policy work." | (i) The policy-4 oracle was never aligned before E0.5 (AC-13). The first-touch oracle is perfect only as a first-touch *table* and still carried its own lookup cost (AC-21). | "A perfect first-touch oracle (a table of the run's own page order) serves as an upper-bound demonstration. With a constant-time lookup, it beats C0 on Stencil-24K only with whole-block staging and the prefetcher on" (CS2-N1; `E4.F1.stencil.C7-W512_vs_C0`) |
| `paper/intro_revisions.md:62-63` | "(the *hit rate*, which our Phase 2 telemetry will measure directly)" as "the fraction of demand faults that find a valid speculative result" | (i) `spec_hits` counts faults on recently predicted pages within 10 ms; it is not "valid speculative results" (AC-20) | use `fault_already_resident` (worker beat the servicing thread) plus wall-clock (CS2-N7) |
| `paper/intro_revisions.md:41`, `:81` | "metadata-only (no residency offload)" | (i) The current design stages residency (depth 1) with width, and that is where its measured effects come from | CS2-N4 (copy offload), CS2-N3 (H-feed) |
| `paper/abstract_v2.md:38-41` | "We attribute the limited end-to-end gains to (a) our current prototype stopping at metadata lookup without fully offloading residency preparation, and (b) tested working sets being well below GPU VRAM capacity" | (i) Superseded explanation. The measured gain over C0 needs whole-block residency staging *and* the prefetcher's mapping (E4, E5); page-granularity staging does not beat C0 | CS2-N1 |
| `paper/abstract_v2.md:35` | "cuFFT gains up to **4.4%**" | not superseded (legacy, already hedged) | keep as hedged in CS2-12; its hit-rate companions are `spec_hits`-based (CS2-N7) |
| `paper/main.tex:114`, `:128` | "excluding pre-Gate-B.1-fix oracle rows" | (i) Incomplete. Post-B.1-fix (FIX-1) oracle rows are *also* misaligned: "no oracle measurement … at matched, aligned rates" (E0.5 Addition 3) | exclude or relabel *all* policy-4 rows before E0.5 as "misaligned oracle" (AC-13) |
| `paper/main.tex:143-144` | "no prefetch-OFF real-benchmark hit-rate data exists anywhere on disk" | (v) Stale. It exists (`results/gate3/telemetry/t4_prefetch_off_hitrate_recovered.csv`), but it is `spec_hits`-based and from the misaligned oracle | do not plot it as success; see HITRATE_REREAD T4-1 |
| `paper/main.tex:150-151` | "Panel A: synthetic probe hit rate (ON/OFF) vs. real-benchmark hit rates" | (i) Not like-for-like: the adjacent policy on a serialized stream (zero-lead self-hits on old code) against a misaligned oracle, both measured with a 10 ms-window counter | drop the panel, or relabel it as counter semantics (AC-14, AC-20) |
| `paper/main.tex:158-165` | "oracle hit-rate collapse under 1.6x oversubscription (results/phaseB1/gate\_d/)"; caption "oracle-vs-p3 separation collapses under oversubscription" | (i)+(v) Gate D used the State-1 misaligned oracle, measured with `spec_hits`. The oversubscription trace was also subject to ring truncation and rotation (AC-19) | exclude from claims (CS2-N9 rationale) |
| `paper/main.tex:215`, `:231-240` (table) | C3 described as run "against a freshly-collected oracle trace"; rows "C3 vs C0 … +278.5% … +302.3%" | (i) The values stand (`T1B5.*`), but C3 is the **misaligned** pre-E0.5 oracle, not an upper bound | relabel C3 per CS2-7. Add the E4 rows (C7-W512 vs C0 −4.93%) for the current claim |
| `paper/main.tex:51-53`, `:67` | "Gate 3 / Phase C conclusions (Path B closed …)" | (i) "Path B closed" rested on C3 losing to C0. E4 found a speculation configuration that beats C0 on Stencil | CS2-N1 (restated central claim) |
| `results/analysis/CLAIM_SCOPE.md:36` (row 5) | "Hit batches are ~5% *slower* than miss batches (no per-hit wall-time saving)" | (i) Per-hit framing via `spec_hits`; contradicted relative to C1 (E0.9b) and to C0 (E4) | CS2-5 |
| `results/analysis/CLAIM_SCOPE.md:37` (row 6) | "one-prediction-per-batch design caps achievable hit rate at ~1/coalesce_factor" | (v) Denominator mismatch (AC-16); describes a design no current module has | CS2-6 |
| `results/analysis/CLAIM_SCOPE.md:38` (row 7) | "C3 (oracle+depth=1, the absolute upper bound of SpecAsync)" | (i) Not an upper bound (AC-13) | CS2-7 |
| `results/analysis/CLAIM_SCOPE.md:39` (row 8) | "SpecAsync's oracle-upper-bound can recover" | (i) Replace with measured perfect staging | CS2-8 (`E4.F4.*`) |
| `results/analysis/CLAIM_SCOPE.md:41` (row 10) | "Rate mismatch … explains SpecAsync's near-zero hit rate … **The mechanism is established for both benchmarks**" | (i) Retired explanation (R1) | CS2-10, R1 |
| `results/analysis/CLAIM_SCOPE.md:46` (row 15) | "The 9-30% D1+D2 window-share bound is architectural-ish (structural upper limit on what's even offloadable)" | (i) Overreach: pre-staging offloads D5 work (E1 Part B) | CS2-15 |
| `results/analysis/CLAIM_SCOPE.md:60-62` (summary) | "The manuscript's strongest, least-hedged claims should be the architectural ones (… the oracle's one-prediction-per-batch ceiling)" | (i) CS 6 is superseded | strongest architectural claims now: CS2-1, CS2-2, CS2-N2 (H-map), CS2-N3 (H-feed), CS2-N5 (handoff) |
| `results/analysis/ARTIFACT_CATALOG.md:11` (#1 root cause) | "Fault trace recorded once **per demand fault**" | (v) Recording is once per va-block dispatch group (E0 §1) | AC-13 amendment |
| `results/analysis/ARTIFACT_CATALOG.md:128` (rejected hypothesis) | "the counter is sound … Near-zero hit rates on real benchmarks are a real interaction with the UVM prefetcher + per-batch (not per-fault) prediction" | (i) The counter fires as coded but measures a 10 ms window (AC-20). The near-zero rates came from a misaligned oracle (AC-13), not the stated interaction | AC-14 / AC-20 amendment |
| `results/phaseB/gate_reports/gate4_oracle.md:8` | "Oracle policy (p4) provides the theoretical upper bound on speculation benefit" | (i) State-0 oracle, under-consuming (E0.5) | CS2-7, CS2-N1 |
| `results/phaseB/gate_reports/gate4_oracle.md:69-71` | oracle `hit_rate` 0.0000 on every benchmark | (v) Artifacts #1/#2 (already catalogued), plus State-0 misalignment | exclude (already excluded by #1's handling) |
| `driver/PIPELINE_FIXES.md:63`, `:66` | "The fix restores genuine ahead-of-fault prediction (23× more hits at 7.9 faults/batch)"; "The residual gap … is the **one-prediction-per-batch**" ceiling | (i) 1 → 23 hits is 22 events (AC-15). The probe could not exercise the mismatch (AC-14); "genuine" was never shown | AC-13, AC-14, AC-15 |
| `results/phaseB1/GATE_D_report.md:69` | "the oracle now genuinely predicts (hit rate ≫ p1–p3) yet still yields no speedup" | (i) State-1 misaligned oracle; `spec_hits` comparison | AC-13, AC-20 |
| `results/phaseB2/GATE3_report.md:12` | "C3 is the absolute upper bound of SpecAsync" | (i) | CS2-7 |
| `results/phaseB2/GATE3_report.md:68`; `results/phaseB2/DECISION.md:17` | "C3 LOSES to C0 on both benchmarks. Path B is closed." | (i) The loss stands as a measurement of C3. "Path B is closed" is superseded by E4 | CS2-7, CS2-N1 |
| `results/analysis/T4_REPORT.md:133` | "the oracle predicts perfectly by construction" | (i) False for policy 4 before E0.5 (AC-13) | R1 |
| `results/analysis/GATE_T4_REPORT.md:33` | "**C3 (the oracle policy -- perfect trace-based prediction, prefetch off) is the real result: 0.02-0.25% hit rate on real workloads**" | (i) See HITRATE_REREAD T4-1. The 0.02–0.25% came from the multi-counted 15-rep sums. The clean values are 0.0132% / 0.2357% | `T4hit.bench_stencil.rep1.corrected_marginal_clean`, `T4hit.graphbfs.pooled_reps1-4` |
| `results/analysis/GATE_T4_REPORT.md:101-104`, `:117`, `:130-136` | "essentially never wins the race"; "predicts with perfect trace-based accuracy and still cannot get credited"; "a second, independent reason speculative prefetching doesn't pay off" | (i) Retired (R1) | HITRATE_REREAD T4-2 … T4-4 |
| `results/analysis/GATE_A1_REPORT.md:223` | "Near-zero real-workload hit rate is fully explained by (a) dispatch-latency race loss" | (i) Retired (R1); the backlog exclusion stands | HITRATE_REREAD A1-2, A1-3 |
| `results/analysis/GATE_B6_TASK2_A1_REPLICATION.md:145` | "Gate A1's core finding — that the near-zero real-workload hit rate is explained by dispatch scheduling delay … holds on this platform" | (i) Retired explanatory link | HITRATE_REREAD B6-2 |
| `results/analysis/RECOVERY_F7_F9_F11.md:158-159` | "Hit rates … Stencil rep1 = 0.0132%, GraphBFS reps1-4 pooled = 0.2357%" | not superseded as values (they match `T4hit.*`). (i) Interpretation only | label as a `spec_hits` coincidence rate (CS2-N7) |
| `results/analysis/gate_e/GATE_E0_7_REPORT.md:255-256` | "closer to genuine divergence than reordering" (Stencil-24K) | (i) Overturned | E0.8 §7; CS2-N6 |
| `results/analysis/gate_e/GATE_E0_8_REPORT.md:182` | "51.19%" forward-only reduced-set ceiling, read as residual disagreement | (v) Withdrawn by E0.9 §1 Correction 1: the symmetric measure gives 99.9997% | AC-18 |
| `results/analysis/gate_e/GATE_E0_8_REPORT.md:251` | "the opposite sense from what pure index-drift would predict" | (i) Withdrawn by E0.9 §1 Correction 2 | AC-18 |
| `results/analysis/gate_e/GATE_E0_9_REPORT.md:335` | "first-touch oracle reaches 92-100% hit rate on Stencil-24K" | (i) A `spec_hits` rate; it collapses at large L | CS2-N7 (`E09b.mech.stencil.C64096`) |
| `results/analysis/gate_e/GATE_E0_9A2_REPORT.md:285`, `:300` | "Prevented faults … structurally zero under this driver's current mapping architecture"; "can reduce the cost of a fault but can never eliminate one" | (i) Narrowed: true for speculation acting alone. With the prefetcher on, faults fall ~40% (H-feed) | CS2-N2, CS2-N3 (`E5.D(51)`) |
| `results/analysis/gate_e/GATE_E0_9B_REPORT.md:14`, `:198` | "Stencil-24K, C6-L4096: 0.244 s faster (−5.65%)" | not superseded as a value (`E09b.stencil.C6-L4096_vs_C1`). (i) It is an expensive-oracle measurement; the cheap oracle gives −9.69% (W1) and −23.29% (W512) | CS2-5, CS2-N5 |
| `results/analysis/gate_e/GATE_E1_REPORT.md:178` | "roughly 0.42 µs each" | (v) A ratio, not a per-prediction cost | R2 (54–75 ns per prediction; `E1b.*`) |
| `results/analysis/gate_e/GATE_E1_REPORT.md:225` | "**Supported under the strongest test so far**" (the central claim) | (i) Falsified in that form by E4 | CS2-N1 |
| `results/analysis/gate_e/GATE_E3B_REPORT.md:189` | "These conclusions **carry an expensive-oracle caveat** until re-tested" | (i) Retired by E4 (F2 measured the cost directly) | `E4.F2.*`; ledger row 43 |

## Searched for, not found in the repository
- **"any such scheme"** (the pipelining ceiling described as bounding any off-path
  scheme): not found in `paper/main.tex`, `paper/abstract_v2.md`,
  `paper/intro_revisions.md`, `CLAIM_SCOPE.md` or any report. E1 Part B already
  recorded this. The only overreaching repository text is CS row 15 (listed above).
  The phrase itself appears only in the chat-session Section I draft (below).

## The Section I draft written in the chat session (not in the repository)

That draft is not a repository file, so it has no line numbers. Per the handoff, it
states the pipelining ceiling "bounds end-to-end speedup" for "any such scheme", and
uses superseded hit rates and the dispatch-race explanation. **When it is rewritten,
it must change:**

1. **The ceiling statement.**
   - Replace "bounds end-to-end speedup for any such scheme" with: the corrected
     ceiling (0.08–7.94%, **PROSE-ONLY**; CS2-15) bounds only what *overlapping
     D1+D2* could recover.
   - It does not bound schemes that remove D4/D5 work or prevent faults, and must not
     be set next to E0.9b's 5.65% or E4's 4.93%.
2. **Hit rates.** Remove every `spec_hits`-based rate used as evidence of prediction
   success or failure: 0.02–0.25%, 0.0132%, 0.2357%, 99.6% / 99.2%, 41%, 25.47%,
   and 92–100%. Where a mechanism number is needed, use `fault_already_resident`
   and coverage (CS2-N7).
3. **The dispatch-race explanation.** Remove "the worker never wins the race"
   and "fully explained by dispatch latency". Replace them with R1's account:
   - a misaligned oracle;
   - index drift;
   - counter semantics;
   - with correct, early predictions, the worker stages 919,262 Stencil pages ahead
     of the servicing thread.
4. **"Oracle-perfect" / "upper bound" language about C3.** Relabel C3 as the pre-E0.5
   misaligned oracle (CS2-7).
5. **The central claim.** Replace "speculation cannot improve the driver as it ships"
   with CS2-N1:
   - it cannot prevent faults alone;
   - page granularity does not beat C0;
   - whole-block staging with the prefetcher on beats C0 on Stencil by ~5% (4.93%,
     replicated 5.26%) through H-feed plus copy offload;
   - no gain on GraphBFS;
   - perfect oracle, single platform.
6. **The handoff cost.** If the draft cites a per-prediction cost (~0.42 µs), replace
   it with CS2-N5: 54–75 ns per prediction for the enqueue; the per-fault prediction
   work was mostly the oracle's own lookup.
7. **The platform.** State RTX 5070 Ti, **driver 595.91.07, kernel 7.0.0-34** for
   every Gate E result, separately from 595.84 (B5–B10) and T4 results (AC-23).
