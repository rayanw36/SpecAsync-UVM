# Gate C1 — Review packet

**Documentation only, and nothing is applied.** `CLAIM_SCOPE.md`,
`ARTIFACT_CATALOG.md`, `PREREGISTRATION.md`, `COMPLETENESS_LEDGER.md`, the manuscript
and every existing report are unedited. All C1 output is in
`results/analysis/consolidation/`, plus one script (`tests/c1_evidence.py`).
HEAD at start: `c266e74`.

## What changes (one page)

1. **The central claim is restated** (CS2-N1).
   - Speculation cannot prevent a fault by itself.
   - Page-granularity speculation does not beat the shipped driver: Stencil +5.87% at
     W = 1; GraphBFS n.s.
   - Whole-block staging with the prefetcher on **beats C0 on Stencil-24K by 4.93%**
     (replicated at 5.26%), through two mechanisms:
     - H-feed: the prefetcher maps regions pushed over its density threshold by
       speculative residency, giving about 40% fewer faults;
     - copy offload (D5).
   - There is no measurable gain on GraphBFS-23.
   - Perfect first-touch oracle; RTX 5070 Ti, driver 595.91.07 only.
2. **Four mechanism claims become explicit, evidence-backed claims.**
   - H-map (N2): speculation never maps.
   - H-feed (N3): pre-registered in E5.
   - Copy offload (N4).
   - The handoff (N5): on the critical path, 54–75 ns per enqueue, with the per-fault
     cost mostly the oracle's own lookup, and amortised by width.
3. **Every pre-E0.5 oracle result is relabelled** as a *misaligned* oracle, not an
   upper bound (CS2-7, CS2-9). The wall-clock numbers stand as measurements of that
   configuration.
4. **Two explanations are retired.**
   - The dispatch race as the cause of near-zero hit rates (R1). It is replaced by:
     the misaligned oracle, index drift, and `spec_hits` semantics; with correct,
     early predictions, the worker stages 919,262 pages ahead.
   - "~0.42 µs per prediction" (R2). It is replaced by 54–75 ns per enqueue plus
     per-fault prediction work.
5. **`spec_hits` is redefined for all uses** as a 10 ms staleness-window counter over
   a 256-slot table (N7, confirmed from source). Every historical "hit rate" becomes
   a coincidence rate, not a success rate (HITRATE_REREAD).
6. **The pipelining ceiling is narrowed** to D1+D2 overlap only (CS2-15). The
   "any such scheme" wording was not found in the repository; it exists only in the
   chat-session Section I draft.
7. **B10 is excluded** (N9): an invalid predictor (misaligned, truncated and rotated
   trace). B9's C3-vs-C0 comparison becomes the worked example for the promoted
   catalog entry #12, the crippled baseline.
8. **Fourteen catalog entries (#12–#25) are proposed, with two amendments to existing
   entries.**
   - #1's root cause is wrong about the recording side.
   - The rejected-hypothesis row's "counter is sound" rests on a probe that could
     not fail.
   - A cross-catalog finding: aggregation-level mismatches were **always** caught
     late, by independent passes. Pre-registration and redundant measurement caught
     errors **inside** the gate that made them.

## Counts

**CLAIM_SCOPE v2 (27 blocks: 17 existing + 8 new + 2 retired explanations):**

| status | count | IDs |
|---|---:|---|
| stands | 9 | CS2-1, 2, 3, 4, 8, 11, 13, 14, 16 |
| narrowed | 5 | CS2-7, 9, 12 (hit-rate part), 15, 17 |
| superseded | 2 | CS2-5, 6 |
| retired | 3 | CS2-10 (as an explanation), R1, R2 |
| new | 8 | CS2-N1, N2, N3, N4, N5, N6, N7, N9 |

**Flag ledger (74 rows, by primary action):** stands 13 · narrow 11 · supersede 12 ·
retire 14 · new claim 12 · catalog entry 11 · needs decision 1. Eight flags are
marked **do not apply as written**, because a later gate changed them (rows 14, 15,
19, 23, 31, 33, 43, 45).

**Catalog:** 14 new entries and 2 amendments, grouped into 4 families plus one
uncategorised (#6).

**Superseded-values register:** 41 file:line entries, and a 7-item change list for
the Section I draft.

**Evidence extract:** 164 values, each from a committed derived file.

## Every PROSE-ONLY number (in the proposals; no committed derived file)

| number | where cited | source prose | why no derived file |
|---|---|---|---|
| 11.7× / 2.1× recording-vs-consumption over-consumption; trace wrap counts | CS2-7, R1, AC-13, HITRATE_REREAD | E0 §7; E0.5 | raw traces gitignored |
| post-fix 1:1 alignment (2,953,867 / 483,896) | AC-13 | E0.5 Step 5 | raw gitignored |
| 442/56 ≈ 7.9 faults/batch; 23/56 = 41.07%; 1/7.9 ≈ 12.7%; 1/57 → 23/56 (22 events); 442/450 | CS2-6, AC-14, AC-15, AC-16 | E0.5 Addition 2, Addendum §3 | `results/phaseB1/oracle_coalesce/*.bin` gitignored |
| serialized probe 254/256 = 99.2%; 0.99 on both modules | AC-14 | `GATE_A_report.md`, `PIPELINE_FIXES.md:57-63` | probe output not committed as a CSV |
| E0.8: max rank displacement 107 / 1,125,000; Spearman 0.9999999983; GraphBFS 36,618–38,990; duplicate-count differences 1,247–4,418 | CS2-N6, AC-17 | E0.8 §4/§6 | E0.7 raw sequences gitignored |
| E0.8/E0.9: forward 98.48% vs backward 0.0708%; ~51.19%; symmetric 99.9997%; 31.4 → 47.5 → 51.7 pts | AC-18 | E0.8 §1/§4/§6, E0.9 §1 | same |
| E4 post-reboot table check: 98 / 35,823 vs 96 / 37,992 | CS2-N6 | `E4_STATUS.md` | computed live, not saved |
| "prevented = 0.0000% at every L" (per-prediction measure) | CS2-N2 | E0.9a-2 §7 | E0.9a-2 raw gitignored. The aggregate H-map evidence *is* in committed CSVs (E4, E5) |
| corrected pipelining ceilings 0.08–7.94%; 7.25% (Sweep-24K, 595.84); window share 9–30% | CS2-15, SUPERSEDED_VALUES | `CEILING_BASIS_VERIFICATION.md` §6 | no ceiling CSV committed |
| B10 "truncated + rotated" classification | CS2-N9 | E0.5 Addition 3; E0 §3 | a property derived from ring capacity; not a CSV value |
| the E0.9a-2 kernel crash | CS2-17, AC-22 | E0.9a-2 §4 | event, not data |
| platform drift (595.84 → 595.91.07; kernel -28 → -31 → -34) | AC-23 | E0.5 "Blocked"; `COMPLETENESS_LEDGER.md` | event |
| the dmesg harness failure (empty slice) | AC-24 | `E3B_STATUS.md` Step 1 | event (post-fix evidence: `e3b/step1_reject.csv`) |

## Every UNCHECKED number (carried unchanged; outside Gate E; not re-derived in C1)

| claim | number(s) |
|---|---|
| CS2-1 | 63–74%, 60.75–86.00% (T4); 52.1–76.9%, 50.38–84.56% (5070 Ti 595.84) |
| CS2-3 | <0.2%; 0.05–0.14% |
| CS2-4 | 76.1% |
| CS2-5 | "~5%" (retired with the claim) |
| CS2-8 | T4 "3.6x/1.06x" as originally cited. The recomputed 3.55× / 1.07× are evidence-backed |
| CS2-9 | p-values, Cohen's d and MDEs in the current row (the percentages are evidence-backed) |
| CS2-10 | ~1,774× / ~81× latency-to-gap ratios |
| CS2-12 | 4.4%, 25.47%, 4.07%, 13.80% |
| CS2-13, CS2-14 | all figures |
| CS2-16 | T4 +0.64% (1635.1 → 1645.6 ms). The 5070 Ti +0.331% is evidence-backed |
| CS2-17 | "<400 net new lines" |
| HITRATE_REREAD | T4 drop rates 17.71–27.87%; latency blowups 500–2,000×, 432.4× / 438.5×, 4.9–11.5× |

## Open decisions (`OPEN_DECISIONS.md`)
- **D1** A practical block-level predictor: this paper, or the follow-on.
- **D2** T4 replication scope.
- **D3** Presentation of GraphBFS's weakened-cursor oracle.
- **D4** Five unresolved items: CS2-4 restatement, CS2-17 wording, B9 C3-vs-C0 in the
  paper, whether to report the expensive-oracle numbers, and apportioning E5's gain.
- **D5** Averted hazards in the catalog.
- **D6** Regenerating derived CSVs for the PROSE-ONLY numbers.

## Files
- `C1_STATUS.md` — status log.
- `FLAG_LEDGER.md` — 74 flags, with the later report that changes each, and a
  proposed action.
- `CLAIM_SCOPE_v2_PROPOSED.md` — 27 claim blocks with evidence ids.
- `ARTIFACT_CATALOG_ADDITIONS_PROPOSED.md` — entries #12–#25, 2 amendments, families
  and synthesis.
- `HITRATE_REREAD.md` — 10 re-read claims across GATE_T4, GATE_A1 and B6 Task 2.
- `SUPERSEDED_VALUES.md` — 41 file:line entries, and the Section I change list.
- `OPEN_DECISIONS.md` — D1–D6.
- `EVIDENCE_EXTRACT.md` — 164 evidence values (generated; regenerate with
  `python3 tests/c1_evidence.py`).

**HARD STOP.** The proposals are applied only after review.
