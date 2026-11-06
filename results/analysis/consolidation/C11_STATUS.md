# Session C11 status

Start 2026-11-06T16:03:52 (+03). Cap 4 h. Branch manuscript-prep, HEAD 9f617a4.

## Open for review
- **H2 verdict: MECHANISM SUPPORTED** (Z1, Z4, Z5, Z6, Z7 held; Z2 and Z3 failed and are outside the verdict rule). `GATE_H2_REPORT.md`; proposed claim text `CS2_N12_PROPOSED.md` (CLAIM_SCOPE not edited).
- Observation outside the pre-registered criteria: on managed memory the K = 1 residency at t51 is already 0.856 of the array, so the managed small t0 cost is not a volume difference; the t0-vs-t51 residency contrast (Z5) exists only on HMM. The CS2-N12 proposal says "the volume moved is the same" for t0 on both allocators; the author may want to add that managed memory is also mostly resident at t51.
- Naming slip, not a protocol departure: the copied orchestrator wrote the timed CSV as `h1_runs.csv` in the h2 directory; renamed to `h2_runs.csv` after the run (content unchanged).
- The residency sampler query carries an added `timestamp` column (declared in the pre-registration).
- Expectation recount (phase 0): 20 held, 4 failed, 1 unscored, 1 withdrawn, MATCHES Section V's `[CHECK]` line. Section V text not edited; `sec:discussion` label added to the Section IX placeholder.

## Log
- 16:04 Phase 0 done: main_v2 already inputs section5_protocol (no change needed); \label{sec:discussion} added to the Section IX placeholder; refs 0 unresolved; expectation recount 20/4/1/1 MATCHES Section V's [CHECK] (EXPECTATION_COUNT.md). Section V text not edited (paper/section5_protocol.tex committed as the user left it).
- 16:05 Phase 1 done: H2_PREREGISTRATION.md, orders (timed/smoke/residency), three hashes in h2_order.sha256, dry runs accepted, control PASS (synthetic -> SUPPORTED; perturbed -> REFUTED). Pre-registration commit: 11c0c95.
- 16:28 Phases 2-4 done: timed sweep 160 rows and residency pass 48 rows (both exit 0, 0 dmesg stop lines); analysis, report, two figures, 32 H2 evidence ids (501 extract rows, 0 unresolved), CS2_N12_PROPOSED.md. End state: stock module 6284DA42, threshold 51, target restored to graphical.target.
