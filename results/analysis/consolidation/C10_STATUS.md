# Session C10 status

Start 2026-11-06T13:46:30 (+03). Cap 4 h. Branch manuscript-prep, HEAD 1cdbb32.

## Open for review
- **H1 Amendment 1 verdict: DENSE REPLICATED ON HMM** (details in `GATE_H1_REPORT.md`, "Amendment 1 results"). Unrequested but material: sparse in-memory K = 1 on HMM is much slower at t0 than t51 (+200.52% in the kept family; managed E8: +3.95%). It is not covered by the verdict rule or any expectation; the author should decide how to present it (CS2-N10 not edited).
- The oversubscribed HMM cells remain unrun; the upstream bug draft (`h1/UPSTREAM_BUG_DRAFT.md`) is not posted and needs the user: the proprietary-driver confirmation, `nvidia-bug-report.sh`, and the crash boot's journal (boot id 46abc43f535443cebe6fe28fb6efc99b).
- Two pre-run guard aborts in the amendment run (nothing ran): the orchestrator refused to start because `phase0_start.txt` still held the C9 start; it was set to the C10 start and the chain relaunched once. The leftover `h1/STOP` is the C9 stop record, not a C10 stop (no `STOP_A1` exists).
- `bastem2017tiles`: closed (DOI 10.1109/ICPP.2017.26, pages 171--180).
- Amendment commit `54566e2` precedes every timed run; the first (aborted) launch attempts and the 6-row C9 smoke are in git history.

## Log
- 13:46 Phase 1 done: DOI 10.1109/ICPP.2017.26 matches (ICPP.2017.24 is the MPI-GDS paper); ref.bib set to upper case, pages 171--180; pybtex OK; 0 missing cite keys.
- 13:47 Phase 2: Amendment 1 appended to H1_PREREGISTRATION.md; order and both hashes regenerated; dry run accepts both orders; control PASS/perturbed FAIL.
- Amendment commit: 54566e2 (timed results are valid only for a run whose order hash matches this commit).
- 13:52 Phase 4 done: UPSTREAM_BUG_DRAFT.md (not posted): duplicate search (closest: #1223 same trigger family, trace not shown), newer tags exist (595.99.02, 595.104.02, 595.112.07: uvm_pmm_gpu.c unchanged, uvm_hmm.c 64 lines; 620.70.06 large rewrite not examined), free_chunk+0x4d = chunk->parent->suballoc->allocated with suballoc NULL (hypothesis: stale parent after merge, uvm_pmm_gpu.c:815).
- 13:56 Phase 3 done: smoke 6 rows, timed 60 rows (runner exit 0, 0 dmesg lines), analysis verdict DENSE REPLICATED ON HMM; threshold restored to 51 (module reloaded with defaults). Phase 5: evidence-id check 258 resolved, 0 unresolved (469 extract rows incl. 3 new H1 ids).
