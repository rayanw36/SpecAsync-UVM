# Session C16 status

No GPU, no module loads. Section text not edited. Finished 21:26 (+03).

1. **Commit:** `section3_background.tex`, `section6_speculation.tex`, `section7_threshold.tex`, `section8_pitfalls.tex` committed as placed ("Sections III, VI-VIII: C15 fixes"). `tests/c8_ref_check.py`: 49 labels, 61 \ref uses, **0 unresolved, 0 duplicate labels**, 32 cite keys, **0 missing**. The \input paths `tables/t_e7` (section7:54), `tables/t_e8` (section7:85) and `tables/t_cat` (section8:130) **resolve**; the checker now follows t_e7.tex, t_e8.tex and t_cat.tex.
2. **Arm label:** C1 is prefetcher OFF (`uvm_perf_prefetch_enable=0`). Fixed in `C15_PHASE_SHARES.md` and `tests/c15_phase_shares.py`, regenerated; the D5 and D4 rows are identical to before (diff). Same fix noted in `C15_STATUS.md`. Caveat recorded there: the quoted Section III ranges are Phase C arm C0 (prefetcher on), so the 595.91.07 C1 comparison with them is indicative only.
3. **D3 / window (595.91.07, `partb_phase_totals.csv`; window ids `E1PartB.<workload>.window`, no D3 id exists in the extract):**

| workload | arm | D3 / window (ratio of medians) | max per-run |
|---|---|---|---|
| Stencil-24K | C1 | 0.1340% | 0.1341% |
| Stencil-24K | C6-L4096 | 0.1433% | 0.1462% |
| GraphBFS-23 | C1 | 0.1082% | 0.1095% |
| GraphBFS-23 | C6-L4096 | 0.1134% | 0.1139% |

   **Every value, including every per-run value, is below 0.2%.** Section III's "below 0.2% of the batch in the typical case" is consistent (all four cells are in fact below 0.15%). Details: `C15_PHASE_SHARES.md`. Section III not edited.
