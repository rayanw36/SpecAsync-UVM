# Session C9 status

Start 2026-11-05T21:39:44 (+03). Cap 4 h. Branch manuscript-prep, HEAD b943abb at start.

## Open for review

## Log
- 21:40 Phase 1a done: ref.bib updated by tests/c9_apply_bib.py (authors, volume, number, pages with --, doi for 11 entries; UNVERIFIED sentences removed; one provenance comment). pybtex parse OK; cite-key check on main_v2: 0 missing. OPEN: bastem2017tiles already existed with DOI 10.1109/ICPP.2017.24; the registry gives 10.1109/icpp.2017.26 and was applied as instructed: the two DOIs differ, check which is right. bastemTilesTR (inside the legacy @comment block) left as is.
- 21:41 Phase 1b-c done: F6 copied to retired/ with README line; F7 regenerated (legacy/f7_dispatch_latency_and_fault_interval, no 'race'); FIGURES.md and PROTOCOL_FACTS.md updated.
- 21:42 Phase 2 done: gate_e/h0/H0_MAPPING.md, verdict MAPS (prefetch pages in the HMM mask are mapped via the shared uvm_va_block_service_finish in the same step; exceptions: pages migrate_vma cannot move are dropped; none expected for host-initialised anonymous memory).
- 21:44 Phase 3a/b: --alloc flag added to benchmarks/bench_sparse.cu and bench_stencil.cu (managed mode output identical to the committed source on 8 sparse cells and stencil N=2048); validation tests/h1_validate.py -> gate_e/h1/h1_validation.log: OVERALL PASS (E8 checks (a)-(e) in malloc mode at 64 MiB and 1 GiB; stencil checksum malloc == managed == CPU reference at N = 2048 and 4096; GPU residency rose 2288 MiB during a 2 GiB malloc-mode run). THP: enabled=madvise, defrag=madvise (recorded; fixed); numa_balancing=0.
- 21:46 Phase 3c: H1_PREREGISTRATION.md, h1_cells/make_order/runner/orchestrate/analyze written; order sha256 c9270e39...; analyzer control PASS (+84.96%, p 1.08e-05) and perturbed copy FAILS (+103.46%).
