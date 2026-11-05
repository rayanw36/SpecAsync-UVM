# Session C8 status

Start 2026-11-05T20:54:48 (+03). Cap 4 h. Branch manuscript-prep, HEAD 96a2300 at start. Stock module loaded (srcversion 6284DA42F15EDC3AB92332B, threshold 51), kernel 7.0.0-34-generic, driver 595.91.07. Evidence-id check: 258 resolved, 0 unresolved.

## Open for review

## Log
- 20:54 Phase 0 done.
- 20:57 Phase 1 done: H0_REPORT.md (verdict A with a CPU-side caveat), tests/h0_caps.cu run once -> h0_caps_output.txt (PageableMemoryAccess 1, UsesHostPageTables 0, ConcurrentManagedAccess 1).
- 21:00 Phase 2 done: paper/support/PROTOCOL_FACTS.md (3 tables).
- 21:03 Phase 3 tables generated (9 tables, script-checked; no TeX toolchain).
- 21:03 Phase 4 done: paper/main_v2.tex + 5 placeholder section files (section2_related_work.tex copied from Downloads); tests/c8_ref_check.py -> MAIN_V2_CHECK.md: 0 unresolved refs, 0 duplicate labels, 0 missing cite keys. Placeholders define sec:squeeze (section6) and sec:pitfalls (section8), which Section II refers to. No TeX toolchain, so main_v2.tex was NOT compiled.
- 21:05 Phase 5 done: `tests/make_legacy_figures.py` regenerates F1, F2, F3 (panel B), F10 into `paper/figures/legacy/` (misaligned-oracle label); F4 and F11 COPIED to `paper/figures/retired/` with README (originals left: `main.tex` references `oversub_collapse`); F6 paragraph and KEEP-caption checks in `paper/figures/FIGURES.md`.
- 21:07 Phase 6 done: `--control` added to e4_analyze.py and e5_analyze.py (PASS on committed CSVs; FAIL on a copy with one cell shifted 10%: E4 -> +4.58%, E5 D(51) -> +0.3410); e6_analyze.py --control now writes to a scratch directory only; REPRODUCE.md updated. Open: the controls recompute the headline from the committed run CSVs with the analyzers' own helpers and family definitions, not the full script (the full scripts also read gitignored ring dumps, so they cannot run from a clean clone).
