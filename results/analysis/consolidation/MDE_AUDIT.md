# MDE audit (Gate C6 step 2; catalog #27)

Script: `tests/c6_mde_audit.py` (reads the committed run CSVs, recomputes MDE = (z(1 - alpha/2) + z(0.80)) * sqrt(s1^2/n1 + s2^2/n2), writes `mde_audit.csv`). No report or claim file was edited.

## Finding

**E4 and E5 carry no wrong MDE.** `e4_analyze.py` and `e5_analyze.py` overwrite the E0.9b helper's hard-coded alpha 0.05/16 constant before use (`H.Z_MDE_BONF`, alpha 0.05/18 for E4 and 0.05/3 for E5), so their `mde_bonf_s` columns, their `MDE18` / `MDE3` labels and the 'MDE alpha/18' and 'MDE alpha/3' columns of the two reports are correct: all 21 rows equal the independent recomputation (to 5e-5 s). The wrong-alpha columns are those of the gates that did **not** override the constant (E0.9b's own 16 is right for E0.9b; E6's CSVs carry it for families of 3, 4 and 2; E1 not audited). Catalog #27's open question is therefore answered: **E4 and E5 are not affected.**

**The issue that does exist is different.** Every MDE *quoted in prose* in CLAIM_SCOPE, Section I and the E4 report text is the unadjusted per-test value (`mde_s`, alpha 0.05), while the tests are Holm-corrected. For a null claim ('no effect beyond the MDE') the relevant MDE is the one at the family alpha, which is larger (E4 by x1.37, E6's family of 3 by x1.16). The quotes are correct values of the column they name; they are not wrong numbers but they understate the detection limit of the Holm family. Corrections below.

Family sizes: E4 one Holm family of 18 (F1 6, F2 4, F3 6, F4 2 are its parts; the sub-family column of `mde_audit.csv` is supplementary); E5 3; E6 secondary wall 3, Family 2 2.

## Quoted values

| where | quoted | value | source column | correct value (alpha 0.05 -> family alpha) |
|---|---|---|---|---|
| GATE_E4_REPORT.md:13 | MDE 0.0144 s | 0.0144 s | mde_s (alpha 0.05) | 0.0144 s: matches |
| GATE_E4_REPORT.md:13 | 0.0197 s at alpha/18 | 0.0197 s | mde_bonf_s (alpha 0.05/18) | 0.0197 s: matches |
| GATE_E4_REPORT.md:28 | MDE of 0.087 s | 0.087 s | mde_s | 0.0873 s at alpha 0.05; 0.1194 s at alpha/18: value matches its column, which is not the family alpha |
| GATE_E4_REPORT.md:28, :247 | MDE of 0.087 s (about 0.28%); MDE about 0.28% | 0.28% | mde_s / median_base | 0.28% at alpha 0.05; 0.38% at alpha/18 |
| GATE_E4_REPORT.md:204 | MDEs of 0.15 and 0.19 s | 0.15, 0.19 s | mde_s | 0.1465, 0.1888 s at alpha 0.05; 0.2004, 0.2583 s at alpha/18 |
| GATE_E4_REPORT.md table, 18 rows | MDE (s) and MDE alpha/18 (s) columns | 18 rows | mde_s, mde_bonf_s | all 18 equal the CSV and the recomputation (max difference 4.7e-05 s) |
| GATE_E5_REPORT.md table, 3 rows | MDE (s) and MDE alpha/3 (s) columns | 3 rows | mde_s, mde_bonf_s | all 3 equal the CSV and the recomputation (max difference 2.8e-05 s) |
| EVIDENCE_EXTRACT.md, E4 rows (18 parsed) | mde_s | per row | mde_s | equal the CSV |
| CLAIM_SCOPE.md:252 | E4.F1.stencil.C7-W512_vs_C0 ... MDE 0.0144 s | 0.0144 s | mde_s | 0.0144 s at alpha 0.05; 0.0197 s at alpha/18; the falsification trigger uses mde_s by pre-registration |
| CLAIM_SCOPE.md:255 | C7-W1/W64/W512 ... MDE 0.0873-0.1351 s | 0.0873-0.1351 s | mde_s | C7-W1 0.1351 -> 0.1848; C7-W64 0.1323 -> 0.1810; C7-W512 0.0873 -> 0.1194 s (alpha 0.05 -> alpha/18) |
| CLAIM_SCOPE.md:246, :255 | GraphBFS-23 E4 ... MDE 0.28-0.43% of the C0 median | 0.28-0.43% | mde_s / median_base | 0.28-0.43% at alpha 0.05; **0.38-0.59% at alpha/18 (the Holm family of the tests)** |
| section1_introduction.tex:104-105 | minimum detectable effects 1.8% and 2.0% (E6 t0, t10) | 1.8%, 2.0% | E6 secondary_wall mde_s / C0 median | 1.76%, 1.97% at alpha 0.05; **2.04%, 2.28% at alpha/3 (E6's family of 3)** |
| CLAIM_SCOPE.md:245, :254 | MDE 1.8% at t0 and 2.0% at t10 (E6) | 1.8%, 2.0% | E6 mde_s | as the row above (same values) |
| CLAIM_SCOPE.md:246, :255 | E6 GraphBFS-23 MDE 0.41-0.49% of the C0-t51 median | 0.41-0.49% | E6 family2 mde_s / base | 0.41-0.49% at alpha 0.05; **0.45-0.54% at alpha/2 (E6's family of 2)** |
| E6 CSVs (secondary_wall, family2_graphbfs) column mde_bonf_s | values in the column | e.g. 0.0245 s (t0) | mde_bonf_s (hard-coded alpha 0.05/16) | E6's own family alpha gives 0.0209 s (t0, m = 3): the column is for a different family. Not quoted in any document checked |

## Table: all E4 and E5 rows (seconds)

| gate | family | workload | comparison | CSV mde_s | CSV mde_bonf_s | recomputed alpha 0.05 | recomputed family alpha (m) | report MDE | report MDE family |
|---|---|---|---|---|---|---|---|---|---|
| E4 | F1 | stencil | C7-W1 vs C0 | 0.0194 | 0.0266 | 0.0194 | 0.0266 (18) | 0.0194 | 0.0266 |
| E4 | F1 | stencil | C7-W64 vs C0 | 0.0201 | 0.0274 | 0.0201 | 0.0274 (18) | 0.0201 | 0.0274 |
| E4 | F1 | stencil | C7-W512 vs C0 | 0.0144 | 0.0197 | 0.0144 | 0.0197 (18) | 0.0144 | 0.0197 |
| E4 | F2 | stencil | C7-W1 vs C7-slow-W1 | 0.0221 | 0.0302 | 0.0221 | 0.0302 (18) | 0.0221 | 0.0302 |
| E4 | F2 | stencil | C6-W1 vs C6-slow-W1 | 0.0280 | 0.0383 | 0.0280 | 0.0383 (18) | 0.0280 | 0.0383 |
| E4 | F3 | stencil | C6-W1 vs C1 | 0.0261 | 0.0358 | 0.0261 | 0.0358 (18) | 0.0261 | 0.0358 |
| E4 | F3 | stencil | C6-W64 vs C1 | 0.0182 | 0.0249 | 0.0182 | 0.0249 (18) | 0.0182 | 0.0249 |
| E4 | F3 | stencil | C6-W512 vs C1 | 0.0199 | 0.0273 | 0.0199 | 0.0273 (18) | 0.0199 | 0.0273 |
| E4 | F4 | stencil | C6-W512 vs C0 | 0.0184 | 0.0252 | 0.0184 | 0.0252 (18) | 0.0184 | 0.0252 |
| E4 | F1 | graphbfs | C7-W1 vs C0 | 0.1351 | 0.1848 | 0.1351 | 0.1848 (18) | 0.1351 | 0.1848 |
| E4 | F1 | graphbfs | C7-W64 vs C0 | 0.1323 | 0.1810 | 0.1323 | 0.1810 (18) | 0.1323 | 0.1810 |
| E4 | F1 | graphbfs | C7-W512 vs C0 | 0.0873 | 0.1194 | 0.0873 | 0.1194 (18) | 0.0873 | 0.1194 |
| E4 | F2 | graphbfs | C7-W1 vs C7-slow-W1 | 0.1465 | 0.2004 | 0.1465 | 0.2004 (18) | 0.1465 | 0.2004 |
| E4 | F2 | graphbfs | C6-W1 vs C6-slow-W1 | 0.1888 | 0.2583 | 0.1888 | 0.2583 (18) | 0.1888 | 0.2583 |
| E4 | F3 | graphbfs | C6-W1 vs C1 | 0.1629 | 0.2229 | 0.1629 | 0.2229 (18) | 0.1629 | 0.2229 |
| E4 | F3 | graphbfs | C6-W64 vs C1 | 0.1296 | 0.1773 | 0.1296 | 0.1773 (18) | 0.1296 | 0.1773 |
| E4 | F3 | graphbfs | C6-W512 vs C1 | 0.1337 | 0.1830 | 0.1337 | 0.1830 (18) | 0.1337 | 0.1830 |
| E4 | F4 | graphbfs | C6-W512 vs C0 | 0.1199 | 0.1641 | 0.1199 | 0.1641 (18) | 0.1199 | 0.1641 |
| E5 | wall | stencil | C7W512-t51 vs C0-t51 | 0.0351 | 0.0405 | 0.0351 | 0.0405 (3) | 0.0351 | 0.0405 |
| E5 | wall | stencil | C7W512-t75 vs C0-t75 | 0.0204 | 0.0236 | 0.0204 | 0.0236 (3) | 0.0204 | 0.0236 |
| E5 | wall | stencil | C7W512-toff vs C0-toff | 0.0238 | 0.0275 | 0.0238 | 0.0275 (3) | 0.0238 | 0.0275 |

## Exact corrections (proposals; nothing edited)

1. `CLAIM_SCOPE.md:246` and `:255`, E4 GraphBFS-23: 'MDE 0.28-0.43% of the C0 median' -> 'MDE 0.38-0.59% of the C0 median at the family alpha (0.05/18); 0.28-0.43% at the unadjusted alpha 0.05'. In `:255` the seconds range '0.0873-0.1351 s' -> '0.1194-0.1848 s at alpha 0.05/18'.
2. `section1_introduction.tex:104-105` (and `CLAIM_SCOPE.md:245`, `:254`), E6: 'minimum detectable effects 1.8% and 2.0%' -> '2.0% and 2.3%' if the MDE is to be stated at the Holm family's alpha (the 1.8% and 2.0% are correct for an unadjusted alpha of 0.05 and the sentence does not say so). Either use the new numbers or add 'at alpha = 0.05, unadjusted'.
3. `CLAIM_SCOPE.md:246`/`:255`, E6 GraphBFS-23: '0.41-0.49%' -> '0.45-0.54%' at alpha/2, or label the quoted range as the unadjusted alpha 0.05.
4. `CLAIM_SCOPE.md:252` and `GATE_E4_REPORT.md:13`, stencil C7-W512 'MDE 0.0144 s': correct as the unadjusted value, and the E4 falsification trigger is pre-registered on `mde_s` (`e4_analyze.py:102`); keep, and state the alpha.
5. E6 CSVs' `mde_bonf_s` column is for alpha 0.05/16, not E6's families (already recorded in `E7_STATUS.md`); no document quotes it. Add a note to the E6 report's next revision.

## Not covered

- T4 and E7/E8 quotes use `mde_pct` and `mde_family_pct` from the E7 helper, which already takes the family size (`e7_analyze.py:56`); not re-audited here.
- E1 and E0.9b quotes of `mde_bonf_s`; E6's own report text.
