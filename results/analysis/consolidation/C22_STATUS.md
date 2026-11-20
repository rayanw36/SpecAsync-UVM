# Session C22 status

No GPU, no module loads, no section text edits. Started 2026-11-20T14:36:29 (+03). Cap 3 h. HEAD 9773ae9.

## Items
- III-1 (eviction order): **REFRESHED ON USE** (use = make_resident migration into the 2 MB chunk or allocation, not plain resident access; UNUSED/DISCARDED lists first; HMM and sub-2 MB blocks untracked). `C22_III1_EVICTION.md`
- VII-4 (density sim): rule reproduces E9 volume (in-memory K=1 3.12% predicted = measured; K=512 ~100%; oversubscribed first pass is 2.00x the model at K=1 and K=8, unexplained) and the K=8 t25 bimodality; volume is monotone in t, so XS4/XS5 failures do NOT follow from the rule (K=64 and K=512 have the same predicted volume). HMM t51: K=1 6.1% vs 3.1% (2x), K=8 28% vs 23.4%. `C22_VII4_DENSITY_SIM.md`
- VII-5/M4 (Stencil-24K CPU share): E9 has a kernel split. Traced gain -0.490 s = 29.6% kernels (-0.145), 16.2% host fill (-0.079, 6.00x fewer CPU faults at t0), 54.2% other (tracing residual, grows with GPU faults); outside-kernel share 70.4% traced (upper estimate); traced kernel delta exceeds the untraced total gain (-0.108 s), so no untraced share is claimed. `C22_VII5_STENCIL_CPU.md`
