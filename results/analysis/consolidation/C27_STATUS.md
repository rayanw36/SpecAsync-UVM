# Session C27 status

No GPU. Finished 16:16 (+03). All changes are in `tests/make_supplementary.py`; `supplementary.tex` is regenerated, not hand-edited.

1. **S3 cells (word for word):** #16 What happened, #16 False conclusion (override applied to the T-CAT shortening in the generator, the shared source `make_paper_tables.py` and `t_cat` are unchanged), #20 What happened, #26 What happened, #26 How caught, #29 How caught.
2. **Closing synthesis:** last sentence replaced as given.
3. **Layout:** every S3 longtable column is `>{\raggedright\arraybackslash}p{...}` (the Family column included).
4. **Checks:** grep of `supplementary.tex` for "re-account", "E8 re", "per-enqueued", "reciprocal coalesce", "each was caught": 0 hits. Recompile: see the commit message and the summary (errors, overfull boxes over 10 pt, pages). PDF in `consolidation/c27_build/` (gitignored).
