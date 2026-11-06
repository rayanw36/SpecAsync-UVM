# Session C12 status

Start 2026-11-06T16:34:29 (+03). Cap 3 h. Branch manuscript-prep, HEAD ba50fa3.

## Open for review
- **Residency-semantics verdict:** on managed memory H2's `memory.used` residency measures allocated GPU memory (a whole 2 MB chunk per VA block, `uvm_va_block.c:1011-1035`, `:2842`), not migrated bytes; E9 traced HtoD for managed in-memory K = 1 at t51 is 0.031 of the array against residency 0.856. Z6 was scored HELD on an instrument that cannot see the difference; the t0 "whole array moved" statement is supported on managed memory by E9's traced bytes instead (1.000). The causal explanation (whole-chunk allocation) is a source-reading **hypothesis**, consistent with the data, not confirmed by a per-chunk trace.
- Phase 2 (H2b traced run) was **not run**: E9 already has traced in-memory managed bytes (K = 1 and K = 512; no K = 8 or 64), the brief's stated condition. B1-B3 are therefore unscored (not run); the cross-session E9 vs H2 comparison answers the B3 question. E9 and H2 are different sessions and instruments.
- `CS2_N12_PROPOSED.md` (C11) is superseded by `CS2_N12_PROPOSED_v2.md` (volume sentence rewritten from traced bytes; managed K = 8, 64, 512 deltas included). `GATE_H2_REPORT.md` and its Z6 scoring were not edited, as instructed; the report's observation paragraph already notes the managed t51 residency.
- Catalog candidate proposed, not applied: `CATALOG_CANDIDATE_H2.md`.

## Log
- 16:35 All phases done (read-only plus scripts; no GPU run, module untouched). Evidence ids: 4 new E9.htod_frac.* rows (505 extract rows), 0 unresolved. End state: stock srcversion 6284DA42F15EDC3AB92332B, threshold 51, graphical.target active.
