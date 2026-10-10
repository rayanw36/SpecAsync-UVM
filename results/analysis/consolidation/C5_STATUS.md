# Session C5 status

Start 2026-10-10 13:03:07; session cap 4 h. Documentation, analysis and figures only: no module loads, no runs, no isolate, no history rewrite, no force-push.

## Open for review
- **Step 1d, labels:** `\ref{sec:squeeze}` (Section II, line 125) and `\ref{sec:pitfalls}` (Section II, line 226) do not resolve; `main.tex` has `sec:eval-squeeze` (a similar label) but no `sec:pitfalls`. **Duplicate label `sec:background`**: defined in `main.tex:80` and in the new `section3_background.tex:49`; it matters as soon as Section III is `\input` into `main.tex`. Not fixed (Section II is being revised; the duplicate is for the author to settle when Section III is wired in).
- **Step 1b:** `main.tex` does not use `\input` for sections: all sections (Introduction, Related Work, Background, Design, Implementation, Evaluation, Discussion, Limitations, Conclusion) are written inline, and the inline Background section (`main.tex:79`) is the old text. `\input` lines were therefore **not** added; Sections I and III exist only as separate files until the author wires them in.
- **Step 1c, Section III numbers:** the measured numbers in Section III are 63--74% (T4) and 52--77% (RTX 5070 Ti, driver 595.84) for D5's share of the batch window (line 105-106) and 0.2% (line 104): these are **CS2-1 and CS2-3, UNCHECKED in C1; no rows added**. The generic matcher's hits on 63, 74, 77 and 0.2 are coincidences. The other tokens are architecture or parameter constants (2 MB, 64 KB, the thresholds 0, 51, 100; verified from source in step 2), GPU names (5070, 3090) and LaTeX lengths mis-read as numbers (`4pt`, `0.52\columnwidth`).

## Log

## Log
- 13:03 **Step 1 DONE.** (a) Section I: the one allowed edit made ("54--75\,ns per enqueue on the stencil workload, on the critical path"); number check unchanged (25 intended-id OK, 2 literature figures, 0 FAIL). (b) `~/Downloads/section3_background.tex` (12,889 B, 230 lines) copied to `paper/section3_background.tex`; `~/Downloads/section1_introduction.tex` is identical to `paper/section1_introduction.tex` as of the preflight. (c) `SECTION3_NUMBER_CHECK.csv`. (d) `tests/c5_label_check.py` -> `LABEL_CHECK.csv`: 6 references, 31 labels, 2 unresolved, 1 duplicate (see Open for review).
