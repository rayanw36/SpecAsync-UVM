# Session C18 status

No GPU, no module loads. Section text not edited. Finished 22:02 (+03).

## 0. Commit
`section3_background.tex`, `section4_design.tex`, `title.tex`, `abstract.tex`, `fig1_faultpath.tex`, `fig2_specasync.tex` committed as placed; `abstract_title.tex` deleted in the same commit. **Path fix:** the two TikZ files were in `paper/`, but Sections III and IV `\input{figures/fig1_faultpath}` / `{figures/fig2_specasync}`, so they were moved to `paper/figures/` (mechanical; contents unchanged).

## 1. Wiring
`main_v2.tex`: `\usepackage{tikz}` and `\usetikzlibrary{positioning,arrows.meta,fit,calc}` added (were missing); C17's double-input trick removed; order is `\input{title}`, author block, `\maketitle`, `\input{abstract}`. Sections III and IV already input the two figures (`fig:faultpath`, `fig:design` defined once). `tests/c8_ref_check.py`: 51 labels, 76 `\ref` uses, **0 unresolved, 0 duplicate labels**, 32 cite keys, **0 missing**.

## 2. Figure fixes (`tests/make_paper_figures.py`)
1. `fig_h2_hmm`: each panel has its own legend with only its own markers: (a) managed solid circle, HMM dashed triangle, filled: Holm-significant, one run; (b) threshold 0, threshold 51, HMM GPU memory in use (triangle), managed traced bytes (E9) (square), one run.
2. "managed (UVM)" renamed "managed (cudaMallocManaged)" in the legend and in the FIGURES.md convention text.
3. Panel (b) caption (FIGURES.md) now says why HMM values sit above 1.0: from the CSV, the 18 fully resident HMM runs are **248 to 264 MiB** above 8 GiB (**0.030 to 0.032** of the array); the driver allocates root chunks in batches up to 128 MiB per call (`RESIDENCY_SEMANTICS.md` section 2c). The two figures are sentences generated from `residency_summary.csv`. (The excess, about two batches, is larger than one 128 MiB batch; the caption states the batch size as the reason for allocation ahead of use and does not claim it accounts for the whole excess.)
4. `fig_e8_sparse_access`: legend now has "filled: Holm-significant" and "one run".
5. `tests/h2_report.py`: no longer draws any figure (the output code is removed, the report text points to `supplementary/`), so a rerun cannot bring back the old encoding. Not rerun here (it would overwrite `GATE_H2_REPORT.md` and the superseded marker on `CS2_N12_PROPOSED.md`).
6. All figures regenerated; previews of `fig_h2_hmm` and `fig_e8_sparse_access` are in `consolidation/c18_previews/`.

## 3. First full compile (run later the same day, after `pdflatex` and `latexmk` were installed)
Built with `latexmk -g -pdf` (bibtex included) into `consolidation/c18_build/` (gitignored; PDFs not committed). `IEEEtran.cls` and `IEEEtran.bst` are not in the installed TeX Live (`texlive-publishers` is missing and `sudo` needs a password), so the CTAN copy (IEEEtran 1.8b, 2015/08/26) was downloaded into `c18_build/ieeetran/` and put on `TEXINPUTS`/`BSTINPUTS` for the build only.

| document | result | pages |
|---|---|---|
| `paper/main_v2.tex` | **compiles, 0 errors** | **19** |
| `paper/supplementary.tex` | **compiles, 0 errors** | **26** |

- **Undefined citations / references:** 0 and 0 in both; no multiply defined labels; no "labels may have changed" after the final pass; BibTeX 0 warnings.
- **LaTeX errors found and fixed (all mechanical, below):** `main_v2`: `\makecell` undefined (Section II table; package missing). `supplementary`: catalog table #1-#11 has 10 cells in rows #7-#11 against 9 header cells ("Extra alignment tab", 15 errors), and its float was too large for a page.
- **Overfull `\hbox` over 10 pt (not fixed: layout, not mechanical; paragraph line numbers are those of the file named):**
  - `main_v2`: `section5_protocol.tex:239-256` 17.2 pt; `tables/t_mech.tex` (Section VI, single column) 176.7 pt; `tables/t_e7.tex` (Section VII) 105.3 pt; `tables/t_cat.tex:17` 11.4 pt.
  - `supplementary`: `tables/t_hand.tex` 75.6 pt; 28 more over 10 pt, all in the first catalog table (`supplementary.tex:141-149`, entries #4-#11: long `\texttt` file names in narrow columns; worst 74.6 and 55.5 pt at line 145).
- **Other warnings that need an author decision:** `main_v2`: `LaTeX Warning: Float too large for page by 62.5499pt` on `section8_pitfalls.tex:131` (the T-CAT table is longer than a page; the table does not fit as a float).
- Only 4 overfull boxes over 10 pt in the main paper, three of them wide tables that need `\resizebox`/column changes or `table*`; that is a layout decision left to the author.

## Mechanical fixes made
- `\usepackage{makecell}` added to `main_v2.tex` (Section II table uses `\makecell`).
- `tests/make_supplementary.py`: `longtable` package; catalog tables set as `longtable` inside `\onecolumn ... \twocolumn` (a float of 11 long rows cannot fit a page); rows with one more cell than the header (#7-#11) get an empty header cell, text unchanged. `supplementary.tex` regenerated.
- `IEEEtran.cls`/`.bst` from CTAN used for the build only (not added to the repo).
- TikZ files moved from `paper/` to `paper/figures/` (path).
- `tikz` package and libraries added to `main_v2.tex`.
