# Session C20 status

Only `paper/ref.bib` changed (plus the archive copy, scripts and reports); no section text. No GPU. Finished 22:50 (+03).

## Result
- **`results/analysis/consolidation/BIB_VERIFY_C20.md`**: per key before/after, source, status. Of the 32 cited keys: **29 FIXED, 0 UNCHANGED, 3 OPEN** (`diehl2018hpxcl`, `li2019oversubframework`, `nihaal2024compression`: no exact Crossref title match, candidates with DOIs are listed in the report; they keep "Diehl et al.", "Li et al." and "Nihaal and Mutyam" until you decide).
- **Notes:** all 31 `note`/`annote`/`addendum`/`comment` fields are now `x-note` (nothing lost; list in the report). One real note kept: `long2022oversub` "Art. no. 11" (Crossref article number).
- **Why the arXiv versions were printed:** BibTeX parses entries inside `@Comment{...}`, so the old file defined the arXiv keys the text cites; the `_published` duplicates were never used. The cited keys `long2022dlprefetch` (JPDC 174, 2023), `choi2022gpuaware` (IPDPSW 2022) and `parravicini2021dagpolyglot` (IPDPS 2021) now carry the peer-reviewed data. Crossref's DOIs for the last two (`10.1109/ipdpsw55747.2022.00097`, `10.1109/ipdps49936.2021.00020`) differ from those recorded in BIB_AUDIT (`.00164`, `.00105`); the Crossref ones are used. `jain2020crac`'s DOI `10.5555/3433701.3433803` is not in Crossref; the exact-title record is SC20, `10.1109/sc41405.2020.00081`.
- **Other venue changes:** `diehl2018hpxcl`, `nazaraliyev2024gpuvm` (possibly published as DREAM, ICS 2025: candidate in the report, authors filled from arXiv) and `gu2020uvmbench` (authors filled from arXiv, no peer-reviewed record found) stay arXiv.
- **Removed from `ref.bib`** (kept in `paper/archive/ref_c19.bib`): the 3 `_published` duplicates and 3 uncited entries that were inside `@Comment` (`anonymous2022learningoversub`, `jain2019crac`, `bastemTilesTR`).
- **Braces:** acronyms and proper nouns in every title protected (`{GPU}`, `{UVM}`, `{CUDA}`, `{CPU--GPU}`, `{R-Max}`, `{MI300A}`, `{HELM}`, ...), by rule (two capitals in a row, capital next to a digit, inner capital, short list of names).

## Compile (`latexmk -pdf`, IEEEtran 1.8b from `c18_build/ieeetran`)
`main_v2.tex`: **18 pages**, 0 errors, 0 undefined citations or references, **0 BibTeX warnings**, 32 bibliography items. `.bbl` grep for "audit", "cited as", "worth", "useful model", "contrast", "our ", "x-note", "Directly upstream", "recovered": **0 hits**. "et al": only the three OPEN entries (as `\emph{et~al.}`). `tests/c8_ref_check.py` 0 unresolved, 0 duplicate, 0 missing. PDF copied to `consolidation/c20_build/` (gitignored).

## Scripts
`tests/c20_bibio.py`, `tests/c20_bib_lookup.py` (Crossref and arXiv; no email or user identifier sent; responses cached in the scratchpad), `tests/c20_bib_apply.py`, `tests/c20_bib_report.py`.
