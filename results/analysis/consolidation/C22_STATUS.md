# Session C22 status

No GPU, no module loads, no section text edits. Started 2026-11-20T14:36:29 (+03). Cap 3 h. HEAD 9773ae9. Finished 14:48.

## Items
- III-1 (eviction order): **REFRESHED ON USE** (use = make_resident migration into the 2 MB chunk or allocation, not plain resident access; UNUSED/DISCARDED lists first; HMM and sub-2 MB blocks untracked). `C22_III1_EVICTION.md`
- VII-4 (density sim): rule reproduces E9 volume (in-memory K=1 3.12% predicted = measured; K=512 ~100%; oversubscribed first pass is 2.00x the model at K=1 and K=8, unexplained) and the K=8 t25 bimodality; volume is monotone in t, so XS4/XS5 failures do NOT follow from the rule (K=64 and K=512 have the same predicted volume). HMM t51: K=1 6.1% vs 3.1% (2x), K=8 28% vs 23.4%. `C22_VII4_DENSITY_SIM.md`
- VII-5/M4 (Stencil-24K CPU share): E9 has a kernel split. Traced gain -0.490 s = 29.6% kernels (-0.145), 16.2% host fill (-0.079, 6.00x fewer CPU faults at t0), 54.2% other (tracing residual, grows with GPU faults); outside-kernel share 70.4% traced (upper estimate); traced kernel delta exceeds the untraced total gain (-0.108 s), so no untraced share is claimed. `C22_VII5_STENCIL_CPU.md`
- M5/V-4/VII-3 (bootstrap CIs): 84 comparisons, CSV + 84 `.ci` evidence ids; (a) of 15 nulls the CI excludes +-2% in 8 and +-5% in 9 (GraphBFS-23 all excluded; Stencil-8K, Sweep-4K, cuFFT CIs 11-23 points wide, underpowered); (b) SGEMM T4 CI [-2.54, -2.21]; one cold t51 run (20.455 s) inflates SD 0.78 vs 0.019 s, MDE 7.72% would be ~0.19%; (c) 2 disagreements (E7 GraphBFS t0, E8 in_k1 t25). `C22_BOOTSTRAP_CI.csv/.md`
- VI-1/VI-2 (copy offload vs fault reduction): D5 reduction C0->C7-W512 is 85.9% fault count (E4 Stencil), 99.1% (E4 GraphBFS); counter `fault_already_resident` = demand-fault entries on already-resident pages (`uvm_gpu_replayable_faults.c:2019-2021`); `pages requested` = 512 x processed items (`:398-401`), 832,392 = 1626.5 x 512; Table V rows from E4 (Stencil, GraphBFS) and E5 (t100). `C22_VI1_DECOMPOSITION.md`
- IV-4 (GraphBFS repeated staging): requested 25.55M = 49,924 items x 512 = 88.7x the 287,956 distinct pages (last-8-region filter only); worker made at most 80.6% of distinct pages resident ahead of fault (C6-W512; 22.3% at W=1; 0.85% C7-W512). `C22_IV4_GRAPHBFS.md`
- M3 (dispatch share): E4 rings; Stencil-24K C0 window 17.2% of wall, D5 9.3%; C7-W512 10.5% / 5.3%; GraphBFS-23 C0 0.19% / 0.15%, C7-W512 0.13% / 0.11%. `C22_M3_DISPATCH_SHARE.md`
- VIII-1/I-4 (catches): in own gate (any mechanism) 11 of 31 (10 + #14 instance 3); pre-registered check 4 (#10, #21, #25, #30); both in-gate and pre-registered 3 (#10, #25, #30; #21's E3b is a later gate). Section VIII's 'four caught inside their own gate' = the pre-registered four, understates in-gate catches (11) and #21 is not in-gate. `C22_VIII1_CATCHES.md`
- V-1 (workloads): 17 rows (8 E7 workloads + Stencil-24K + 8 sparse cells) with source, command, size, footprint (GraphBFS-23: 131,168,515 unique edges, 1.196 GiB; oversub 17.17 GiB), passes, median wall t51. `paper/tables/t_workloads.tex`, `C22_WORKLOADS.md` (not wired)
- S-7 (supplementary tables): `paper/tables/t_e7_full.tex` (both GPUs, 20 + 16 rows with MWU p and Holm-adjusted p), `t_h1.tex` (3), `t_h2.tex` (8), captions in `paper/tables/TABLES_C22.md`; not wired into supplementary.tex.
- Evidence: 84 new `.ci` ids in EVIDENCE_EXTRACT.md (589 rows; 307 CLAIM_SCOPE ids resolved, 0 unresolved). New scripts: tests/c22_*.py, c22_pagelist.cpp, c22_graph_edges.cpp.

## Findings the author should look at (no section text was edited)
1. III-1: the driver refreshes a root chunk's position on migration into it (make_resident), not only at allocation; Section III-D's 'allocation order, not by recency of access' is true only for plain access to resident data (verdict REFRESHED ON USE).
2. VII-4: Eq. 1 reproduces the E9 volume (in-memory K=1 3.12% = measured) but not XS4/XS5, which are time orderings; the oversubscribed first-pass HtoD is exactly 2.00x the model at K=1 and K=8 (unexplained).
3. VIII-1: 'four caught inside their own gate' is the pre-registered set {#10, #21, #25, #30}; in-gate catches total 11, and #21's pre-registered catch (E3b) is a later gate.
4. M5: Stencil-8K, Sweep-4K and cuFFT nulls are underpowered (CIs 11-23 points wide); GraphBFS-23 nulls exclude +-2%; T4 SGEMM MDE 7.72% is inflated by one cold run (20.455 s); 2 CI/Holm disagreements (E7 GraphBFS t0, E8 in_k1 t25).
5. VI-1/IV-4: the prefetch-on D5 reduction is 86-99% fault count; 'pages requested' counts 512 x worker items (88.7x the distinct pages on GraphBFS-23), not staged distinct pages.

