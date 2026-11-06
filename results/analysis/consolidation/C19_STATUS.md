# Session C19 status

Layout only; no wording changes except the one sentence the brief specifies. No GPU. Finished 22:25 (+03).

1. **Section VIII:** the t_cat table float (`tab:catalog`) is removed; the last lines of Section VIII now read "The full catalog, with the false conclusion and the means of detection for each entry, is in the supplementary material (Section S3)." The only `\ref{tab:catalog}` (the sentence "Table~\ref{tab:catalog} lists them." in the first paragraph) is dropped; none remains. (`tables/t_cat.tex` is still generated and no longer input by the paper.)
2. **Tables:** `t_mech` (Section VI) and `t_e7` (Section VII) are now `table*`.
3. **Gates table (Section V):** `\setlength{\tabcolsep}{3pt}` set; **no overfull box remains** in `main_v2` (before: 17.2 pt).
4. **Supplement:** code spans (file names, paths, identifiers) may break after every character, plain-text tokens may break after `/`, `=`, `-` and `_`, catalog tables get `\emergencystretch=3em`, and S1 tables are scaled to the text width (`adjustbox`, max width). Done in `tests/make_supplementary.py` (the `xurl`/`\path` route was not used, because `\url` cannot take the `%`, `#` and braces that occur in code spans; the effect is the same).
5. **Recompile (`latexmk -pdf`, IEEEtran 1.8b from `c18_build/ieeetran`):**

| document | errors | pages | overfull hbox over 10 pt | floats that do not fit | undefined refs/cites |
|---|---|---|---|---|---|
| `main_v2.tex` | 0 | **18** (was 19) | **0** (was 4) | **none** (was the T-CAT float, 62.5 pt too large) | 0 |
| `supplementary.tex` | 0 | **26** | **1**: 11.95 pt, catalog entry #5, the hyphenated word "Decomposition-record" in a narrow column (`supplementary.tex:145`); was 29 | none | 0 |

`tests/c8_ref_check.py`: 50 labels, 75 `\ref` uses, 0 unresolved, 0 duplicate, 0 missing cite keys.
6. PDFs copied to `results/analysis/consolidation/c19_build/` (gitignored).
