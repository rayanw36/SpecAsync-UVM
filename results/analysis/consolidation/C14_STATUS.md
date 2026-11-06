# Session C14 status

Start 2026-11-06T16:51:28 (+03). Cap 2 h. HEAD e4d20aa. Read-only apart from the step-0 commit and paper/support/RESULTS_FACTS.md. No GPU.

## Open for review
Intro numbers that failed to match (Section I; Section II has none that fail):
1. `section1_introduction.tex:91` "four independent sessions": the data and CS2-N1 item 3 give **three** C7-W512 vs C0 sessions at t51 (E4 -4.93%, E5 -5.26%, E6 -3.36%). The 3.4-5.3% range matches those three.
2. `:107` "Across nine dense or streaming workloads, the lower threshold sped up four, by 2.5--17%": Family B has 8 workloads, 4 significantly faster (2.49% to 16.95%), none slower. With Stencil-24K (Family A, -9.57%) the count is **five of nine**. The sentence mixes the two counts.
3. Not from our data (cited prior work, Go et al.): "RTX 3090", "515.65.01", "150%" (Sections I and II): listed as not found, expected.
Other disagreements between sources: none found by the script checks. Observations: "Two triggers fired" matches the E4 and E6 reports (E8's report states no trigger; the brief's "six cells that fired the trigger" for E8 is not in the E8 report wording, scored through XS1-XS5 instead); #14 "later passes; one caught in-gate" is not a pre-registered catch (reader's question), so the in-gate pre-registered count is 4 (#10, #21, #25, #30).
Section I's catalog sentence: the first half (aggregation-level errors caught only by later passes) is supported for the 7 that reached a report (8 of 9 aggregation entries caught later; #25 caught in-gate); the contrast is descriptive (n = 2-3 per mechanism, selection effect), so "whereas pre-registered predictions caught errors inside the gate" overstates it. Not edited.

## Log
- 16:51 Step 0 done: Sections II and V committed and pushed.
- 16:54 Built paper/support/RESULTS_FACTS.md (tests/c14_results_facts.py; generated, ~550 lines): Section VI (a-g), VII (a-f), VIII (family counts total 31, 31-row table, Section I sentence counts), cross-check of Sections I and II numbers. 0 requested ids missing from the extract. Evidence-id check 307 resolved, 0 unresolved. No GPU, no module loads.
- 16:54 CS2-1/CS2-3 shares carry their UNCHECKED status in VI-g (quoted from CLAIM_SCOPE).
