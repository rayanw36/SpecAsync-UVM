# Paper superseded-value status (Gate C5 step 5)

For each of the 41 entries of `SUPERSEDED_VALUES.md`: whether the new Section I (`paper/section1_introduction.tex`, draft 4 with the C5 step 1 edit) or Section III (`paper/section3_background.tex`) already resolves it, and which future section must otherwise. Roadmap from Section I's last paragraph: II related work, III background, IV system and oracle, V measurement protocol, VI speculation results and mechanism, VII threshold measurements, VIII artifact catalog, IX conclusion. **No paper file was edited.**

Check: grep of Sections I and III for `upper bound`, `hit rate`, `metadata-only`, `Path B`, `closed`, `4.4`, `rate mismatch`, `oracle`, `per demand fault`, `ceiling`. Occurrences are the header comments (which name the superseded items), the corrected oracle statements, and the roadmap; **neither section repeats a superseded claim.** Status key: RESOLVED by Section I = Section I states the replacement; OPEN = a future section or the abstract must; `not paper text` = the entry is in a report, CLAIM_SCOPE or the catalog and matters only if a future section quotes it (nothing in the paper depends on it yet).

| # | register row (file:line) | status | must be resolved in | note |
|---|---|---|---|---|
| 1 | `paper/intro_revisions.md:28-29` | OPEN | abstract, IV | 'upper bound' wording in `intro_revisions.md`; Section I has no upper-bound claim (checked). Replace with measured perfect staging (E4 F4) in the abstract and Section IV |
| 2 | `paper/intro_revisions.md:62-63` | OPEN | V, VI | 'hit rate' as prediction success; Section I avoids the measure (header comment lists CS2-N7). Section V must define it as a `spec_hits` coincidence rate or drop it |
| 3 | `paper/intro_revisions.md:41`, `:81` | RESOLVED by Section I | IV | Section I describes depth-1 residency staging with a width (lines ~80-90, 147-150), not 'metadata-only'. Section IV must say the same |
| 4 | `paper/abstract_v2.md:38-41` | OPEN | abstract | draft abstract still attributes limited gains to metadata-only lookup; rewrite to the CS2-N1 framing |
| 5 | `paper/abstract_v2.md:35` | OPEN | abstract, VI | 4.4% cuFFT stands only as a hedged legacy number (CS2-12); Section I does not use it |
| 6 | `paper/main.tex:114`, `:128` | OPEN | V, VI | 'excluding pre-Gate-B.1-fix' must become: every pre-E0.5 oracle row is misaligned (Section I line ~135 says this for the old null result) |
| 7 | `paper/main.tex:143-144` | OPEN | VI | stale 'no prefetch-OFF hit-rate data exists'; the data exist; rewrite or drop |
| 8 | `paper/main.tex:150-151` | OPEN | VI | Panel A not like-for-like (goes with F3, see `paper/figures/EXISTING_FIGURES_ASSESSMENT.md`) |
| 9 | `paper/main.tex:158-165` | OPEN | VI, VII | oversubscription oracle-collapse text retired; replace with E8/E9 (F-E8, F-E9); retire old F4 |
| 10 | `paper/main.tex:215`, `:231-240` (table) | OPEN | VI, VIII | table rows stand as measurements of the misaligned C3; relabel and remove 'freshly-collected' (with F2/F10) |
| 11 | `paper/main.tex:51-53`, `:67` | RESOLVED by Section I | VI, IX | Section I (lines ~135-138) says the old null rested on a misaligned oracle and that the corrected oracle gives a positive result; Sections VI and IX must not restate 'Path B closed' |
| 12 | `results/analysis/CLAIM_SCOPE.md:36` (row 5) | OPEN | VI | CLAIM_SCOPE row 5 (per-hit cost); a future section must frame per-hit effects only against C1/C0 (CS2-5) |
| 13 | `results/analysis/CLAIM_SCOPE.md:37` (row 6) | OPEN | VI, VIII | coalesce-factor cap (CS2-6) retired; do not carry into Section VI's hit-rate discussion |
| 14 | `results/analysis/CLAIM_SCOPE.md:38` (row 7) | RESOLVED by Section I | IV | Section I does not call any oracle an upper bound (checked); Section IV must not either (CS2-7) |
| 15 | `results/analysis/CLAIM_SCOPE.md:39` (row 8) | RESOLVED by Section I | VI | Section I states measured perfect staging (99.95% staged, 2.92x slower with the prefetcher off); Section VI must cite `E4.F4.*` |
| 16 | `results/analysis/CLAIM_SCOPE.md:41` (row 10) | OPEN | VI | rate-mismatch explanation retired (CS2-10, R1); Section VI must use the E1/E5 mechanism; Section I does not use it |
| 17 | `results/analysis/CLAIM_SCOPE.md:46` (row 15) | RESOLVED by Section I | VI, IX | Section I line ~159-160 states the E1 Part B result (D5 offload); Section VI must not call the 9-30% bound structural |
| 18 | `results/analysis/CLAIM_SCOPE.md:60-62` (summary) | OPEN | IX | the conclusion must not name the one-prediction-per-batch ceiling a strongest claim (CS2-6 superseded) |
| 19 | `results/analysis/ARTIFACT_CATALOG.md:11` (#1 root cause) | OPEN | VIII | catalog text 'recorded once per demand fault' (AC-13 amendment); Section VIII quotes the catalog, so use the amended text |
| 20 | `results/analysis/ARTIFACT_CATALOG.md:128` (rejected hypothesis) | OPEN | VIII | catalog rejected-hypothesis text (AC-14 / AC-20 amendment); Section VIII must quote the amendment |
| 21 | `results/phaseB/gate_reports/gate4_oracle.md:8` | not paper text | VIII only if quoted | gate4 report: oracle 'theoretical upper bound' (CS2-7, CS2-N1) |
| 22 | `results/phaseB/gate_reports/gate4_oracle.md:69-71` | not paper text | VIII only if quoted | gate4 report: oracle hit rate 0.0000; already excluded |
| 23 | `driver/PIPELINE_FIXES.md:63`, `:66` | not paper text | VIII only if quoted | `PIPELINE_FIXES.md` '23x more hits'; AC-13/14/15 |
| 24 | `results/phaseB1/GATE_D_report.md:69` | not paper text | VIII only if quoted | GATE_D report 'oracle now genuinely predicts'; AC-13, AC-20 |
| 25 | `results/phaseB2/GATE3_report.md:12` | not paper text | VIII only if quoted | GATE3 report 'absolute upper bound'; CS2-7 |
| 26 | `results/phaseB2/GATE3_report.md:68`; `results/phaseB2/DECISION.md:17` | not paper text | VIII only if quoted | GATE3/DECISION 'C3 loses; Path B is closed'; CS2-7, CS2-N1. Section I already states the opposite |
| 27 | `results/analysis/T4_REPORT.md:133` | not paper text | VIII only if quoted | T4 report 'oracle predicts perfectly by construction'; R1 |
| 28 | `results/analysis/GATE_T4_REPORT.md:33` | not paper text | VI if the T4 hit rate is quoted | T4 hit-rate headline; use `T4hit.*` ids with the CS2-N7 label |
| 29 | `results/analysis/GATE_T4_REPORT.md:101-104`, `:117`, `:130-136` | not paper text | VI | T4 'never wins the race'; HITRATE_REREAD T4-2..T4-4 |
| 30 | `results/analysis/GATE_A1_REPORT.md:223` | not paper text | VI | A1 'fully explained by dispatch-latency race'; HITRATE_REREAD A1-2, A1-3 |
| 31 | `results/analysis/GATE_B6_TASK2_A1_REPLICATION.md:145` | not paper text | VI | B6 replication of the A1 claim; HITRATE_REREAD B6-2 |
| 32 | `results/analysis/RECOVERY_F7_F9_F11.md:158-159` | not paper text | VI | hit rates 0.0132%/0.2357% stand as numbers; label as `spec_hits` coincidence rates (CS2-N7). Section I's header comment already does so |
| 33 | `results/analysis/gate_e/GATE_E0_7_REPORT.md:255-256` | not paper text | VI | E0.7 'genuine divergence' wording; E0.8 s7, CS2-N6 |
| 34 | `results/analysis/gate_e/GATE_E0_8_REPORT.md:182` | not paper text | VI | E0.8 51.19% ceiling read as residual disagreement; AC-18 |
| 35 | `results/analysis/gate_e/GATE_E0_8_REPORT.md:251` | not paper text | VI | E0.8 'opposite sense' wording; AC-18 |
| 36 | `results/analysis/gate_e/GATE_E0_9_REPORT.md:335` | not paper text | VI | E0.9 '92-100% hit rate' on Stencil-24K; CS2-N7 (`E09b.mech.stencil.C64096`) |
| 37 | `results/analysis/gate_e/GATE_E0_9A2_REPORT.md:285`, `:300` | not paper text | VI | E0.9a-2 'prevented faults structurally zero'; CS2-N2/N3 (`E5.D(51)`). Section III states the two channels instead (`sec:bg-where`) |
| 38 | `results/analysis/gate_e/GATE_E0_9B_REPORT.md:14`, `:198` | not paper text | VI | E0.9b '0.244 s faster (-5.65%)' for C6-L4096; CS2-5, CS2-N5. Section I does not quote it |
| 39 | `results/analysis/gate_e/GATE_E1_REPORT.md:178` | RESOLVED by Section I | VI | E1 report 'roughly 0.42 us each' replaced in Section I by '54-75 ns per enqueue' (C5 step 1 edit; R2, `E1b.*`) |
| 40 | `results/analysis/gate_e/GATE_E1_REPORT.md:225` | not paper text | VI, IX | E1 report 'Supported under the strongest test so far' (central claim); CS2-N1. Section I restates the central claim |
| 41 | `results/analysis/gate_e/GATE_E3B_REPORT.md:189` | not paper text | VI | E3b 'expensive-oracle caveat' retired by E4 F2 (`E4.F2.*`); Section I line ~160 states that the first oracle's overhead was its own lookup |

Totals: {'OPEN': 15, 'RESOLVED by Section I': 6, 'not paper text': 20}. Entries 1-11 are the manuscript files (`intro_revisions.md`, `abstract_v2.md`, `main.tex`): 2 resolved by Section I, 9 open. `abstract_v2.md`, `intro_revisions.md` and `main.tex` are unedited by instruction; all open ones need the abstract or Sections IV-IX, none needs Section II or III.

Open for review: row 19 and 20 are catalog edits (the catalog is not edited by C5); row 7's citation of CS2-12 was not re-verified here.
