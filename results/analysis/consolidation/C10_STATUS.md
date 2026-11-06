# Session C10 status

Start 2026-11-06T13:46:30 (+03). Cap 4 h. Branch manuscript-prep, HEAD 1cdbb32.

## Open for review

## Log
- 13:46 Phase 1 done: DOI 10.1109/ICPP.2017.26 matches (ICPP.2017.24 is the MPI-GDS paper); ref.bib set to upper case, pages 171--180; pybtex OK; 0 missing cite keys.
- 13:47 Phase 2: Amendment 1 appended to H1_PREREGISTRATION.md; order and both hashes regenerated; dry run accepts both orders; control PASS/perturbed FAIL.
- Amendment commit: 54566e2 (timed results are valid only for a run whose order hash matches this commit).
- 13:52 Phase 4 done: UPSTREAM_BUG_DRAFT.md (not posted): duplicate search (closest: #1223 same trigger family, trace not shown), newer tags exist (595.99.02, 595.104.02, 595.112.07: uvm_pmm_gpu.c unchanged, uvm_hmm.c 64 lines; 620.70.06 large rewrite not examined), free_chunk+0x4d = chunk->parent->suballoc->allocated with suballoc NULL (hypothesis: stale parent after merge, uvm_pmm_gpu.c:815).
