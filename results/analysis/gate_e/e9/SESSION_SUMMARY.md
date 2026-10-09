# Session summary: C3-APPLY (partial) + D6 regeneration + path fixes + Gate E9

Phase 0 start 2026-10-08 20:54:07 +03; the session was **paused** after Phase 3 and resumed 2026-10-09 ~15:49; the 3.5 h cap counted working time
(`e9/cap_anchor.txt` = 2026-10-09 15:40:03, i.e. resume minus the ~10 minutes already used). Everything finished by about 16:10 on the 9th. Hard stop after Phase 5.

## Phases

| phase | status |
|---|---|
| 0 preflight | done; C3-APPLY was **not** applied (no CS2-N11) |
| 1 C3-APPLY | **partial.** The C3-APPLY brief was not available (not in the conversation, the session transcript or on disk), and `paper/section1_introduction_draft3.tex` does not exist. Done: the fully specified mechanical part, evidence extraction for E7 and E8 (+70 rows). **Skipped:** the CS2-N10 rewrite, CS2-N1 item 4, CS2-N11, the D1 note, `E7_E8_REVIEW_NOTES.md`, the Section I swap and its number check (writing canonical claim text without the reviewed wording would invent it). To finish: send the brief and place draft 3 at `paper/section1_introduction_draft3.tex` |
| 2 D6 regeneration | done: `tests/d6_regenerate.py`, derived CSVs in `results/analysis/derived/` (60 KB), summary `consolidation/D6_REGENERATION.md`. **157 comparisons: 154 MATCH, 3 MISMATCH**, both values recorded, prose not edited. +157 `D6.*` ids; id check 194 resolved, 0 unresolved (418 extract rows) |
| 3 path fixes | done: 19 edits / 20 lines in 10 files, env var with today's default, table in `results/analysis/PATH_FIXES.md`; `bash -n`, `py_compile`, default-equivalence, E8 analyzer control and 64 MiB bench validation all PASS. Patch files not edited |
| 4 Gate E9 | done: 4a probe PASS; pre-registration pushed before any traced run (`5ad9e19`); smoke 14 runs; sweep **42 of 42 rows**, no block skipped, no stop; report `gate_e/GATE_E9_REPORT.md`, figure `e9_um_bytes.{png,pdf}` |
| 5 this file | done |

## E9 result

**Y1, Y2, Y3, Y4 all held.** Oversubscribed K=1: HtoD 129.8 GiB at t0 vs 4.0 GiB at t51 (32.8x). Oversubscribed K=1 and K=8 at t0 evict 33-45 GiB per pass (K=8's t51/t0 DtoH ratio 0.24 against the 0.25 limit: a narrow pass).
Stencil-24K: HtoD within 0.74%, GPU page faults -70% at t0. The unexplained E8 observation (oversubscribed K=1 at t51 still costs ~0.3 s per pass) is explained: ~1.2 GiB in and ~1.2 GiB out every repeat pass.
**Unrequested finding:** nsys counts 6x more CPU page faults at t51 than at t0 in every cell (the t0 count equals the number of 2 MB blocks): the host-side first touch depends on the threshold, which contradicts the E8 report's "identical across thresholds" limitation (an inference from counts; the source was not read).

## DOC-class items left open (all in `e9/SESSION_STATUS.md` "Open for review")

1. C3-APPLY not applied (above). CS2-N10's "interpretation" and "unexplained" sentences do not exist yet; E9's report states what it would change when they do.
2. D6 mismatches: Stencil max rank displacement is 107 at depth 1 and 105 at depth 0 in the data, 105 and 107 in the E0.8 table; the Stencil L=1 prediction count is 141,484 (E0.9a-2 raw) vs 140,909 (E0.9a prose). D6 row 10: rotation of the B10 traces cannot be regenerated from the file (truncation is consistent).
3. The cap was re-anchored after the pause (recorded, original start file untouched).
4. The brief's nsys report names (`cuda_um_*`) do not exist in nsys 2025.3.2; `um_total_sum` plus the SQLite export were used. Thrashing, throttling and remote-map events are not observable, so Y4's second arm was untestable.
5. Each traced run logged one `NVRM: GPU0 refcntRequestReference_IMPL: Failed to enter state 1 (status 0x56)` kernel line, only while traced runs were active; not in the stop pattern; source not established.
6. Existing claims and reports flagged, not edited: CS2-N10, GATE_E8's host-initialisation limitation, the E6/E7 reading of the threshold effect as GPU-side only.
7. Carried over: X3 unscorable (E6), E0/E0.8 platform not recorded, PATH_AUDIT patch files not edited.

## Unresolved evidence ids

None (194 cited occurrences resolved, 0 unresolved).

## Push state

All commits pushed (the report push returned `f14821a..5b1e277`); 0 unpushed before this file's own commit.

## End state

- Stock module loaded: srcversion `6284DA42F15EDC3AB92332B`, refcnt 0, `uvm_perf_prefetch_threshold` 51, no specasync parameters.
- Runtime target `multi-user.target`; boot default `graphical.target`. **Lingering is still enabled** (from E7): `sudo loginctl disable-linger rayenchikhaoui` undoes it but ends the user manager and this tmux session.
- Raw data kept (gitignored): `results/phaseB1/gate_e9/` (687 MB of nsys reports).

## Stop

HARD STOP after Phase 5. No further runs.
