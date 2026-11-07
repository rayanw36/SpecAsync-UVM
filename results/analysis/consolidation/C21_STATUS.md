# Session C21 status

Only `ref.bib` and the placed Section II changed. No GPU. Finished 13:47 (+03).

1. `paper/section2_related_work.tex` committed as placed.
2. `ref.bib` (script `tests/c21_bib_replace.py`, Crossref records fetched by DOI; keys kept; full authors with initials, title, venue, pages, DOI):
   - `li2019oversubframework` -> 10.1145/3297858.3304044 (ASPLOS 2019, pp. 49--63, 7 authors, title "...in Graphics Processing Units").
   - `diehl2018hpxcl` -> 10.1109/espm2.2018.00006 (ESPM2 2018, pp. 19--28, 4 authors: Diehl, Seshadri, Heller, Kaiser; title "...within the C++ Library for Parallelism and Concurrency (HPX)").
   - `nihaal2024compression` -> 10.1145/3673038.3673058: check passed (Crossref authors are Nihaal and Mutyam; venue is the 53rd International Conference on Parallel Processing, 2024; pp. 189--198); title now "...for GPU Memory Oversubscription Management".
   - `nazaraliyev2024gpuvm` -> DREAM, ICS 2025 (39th ACM ICS, pp. 1190--1205), 10.1145/3721145.3725748; key kept; x-note starts "Preprint: arXiv:2411.05309 (GPUVM)".
   - `gu2020uvmbench` left as arXiv. Old notes stay in `x-note`.
3. Recompile `main_v2.tex`: **18 pages**, 0 errors, 0 BibTeX warnings, 0 undefined citations/references, 32 bibliography items, **no "et al." left in the .bbl**. `c8_ref_check.py`: 0 unresolved, 0 duplicate, 0 missing. PDF in `consolidation/c21_build/` (gitignored).
Note: the in-text mentions of the paper by its preprint name "GPUVM" (if any) are in section text, which was not changed here.
