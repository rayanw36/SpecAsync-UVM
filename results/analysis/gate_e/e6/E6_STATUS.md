# Gate C1-APPLY + D6/PATH audits + Gate E6 — status log

Phase 0 started: 2026-10-05T17:38:51+0300 (3 h wall-time cap from this moment; Family 2 skip rule: Family 1 must end by +2 h 15 min).

## Open for review
(DOC-CLASS items are appended here as they arise.)

## Log
- 2026-10-05T17:38:51+0300 Phase 0 start.
- Push: "Everything up-to-date", exit 0; level with origin. HEAD `b06120f`. Tracked tree clean (untracked tests/group_probe).
- Kernel 7.0.0-34-generic ✓. Driver 595.91.07 ✓. Verified-source check `git diff ea1a262 HEAD -- driver/src` empty ✓.
- Module files: e0.9a2-fixed srcversion 5997D238EF080B77DBD2AAF ✓; e3a2-width-ftfast srcversion 33FD42E6E16B0A6658E2BEB ✓.
- Timers inactive ✓. MemAvailable 59,173,684 kB. / 38 GiB free.
- Observation (not a Phase-0 mismatch): loaded `nvidia_uvm` is the stock module 6284DA42F15EDC3AB92332B, refcnt 0, gdm and graphical.target active. Phase 4 reloads modules, so this does not change the plan.
- Phase 0: PASS, Phases 1–7 proceed.
- 17:42:39 Phase 1 DONE (documentation). Amendments committed first (`b5ce787`). Applied: CLAIM_SCOPE.md (v2, replaces v1); ARTIFACT_CATALOG.md (#12–#25 and two amendments appended).
  - Items 1–13 applied as listed in C1_STATUS.md and CLAIM_SCOPE.md. Per-gate kernel verified from each report (E0 and E0.8 record none; E0.5/E0.7/E0.9 on 7.0.0-31; E0.9a-2 onward on 7.0.0-34).
  - CS2-N4 D5 per demand fault: C0 309.8 ns, C7-W512 276.3 ns (not separable from fault count).
  - CS2-N1 item 4: GraphBFS MDE 0.28–0.43% of C0 median.
  - Evidence ids: `tests/c1_check_ids.py` — 197 cited occurrences across the applied and proposal files, **0 unresolved**; extract 164 rows.
  - Catalog #13 date: "about three months" replaced by 103 days (cc90fc1 2026-06-13 → e7de063 2026-09-24).
  - Item 12: 148 = intermediate count before the spec_migrations rows; 164 = committed file (db708d4).
- Items noted for review (DOC-CLASS): none blocking. Open for review: (a) E0 and E0.8 platform not recorded in their reports (stated as such in CLAIM_SCOPE v2 header; no reconstruction attempted).
- 17:45:07 Phase 2 DONE (read-only). 2a: `consolidation/D6_RAW_INVENTORY.md` — 13 PROSE-ONLY rows: 10 raw inputs on disk (all gitignored; 6 with a committed regenerating script; 3 command-block only; row 7 comparison inline and uncommitted), 2 events recovered from the journal (crash boot 5f825cf7, 12:37:05 on 09-25; harness boot 235bb163, 00:00:33 on 09-26), 1 documentary. Journal clock observation recorded. 2b: `results/analysis/PATH_AUDIT.md` — 22 hits in 10 script files + 2 patch files; 326 portable kernel-interface references excluded.
- 17:47:29 Phase 3: analyzer positive control PASS (E6's comparison reproduces E5: −5.26%, p 1.08e-05, D(51) +0.4009; `e6/analyzer_positive_control.txt`). Refusal paths tested on synthetic data (79 rows refused; 80+skip accepted; 110+skip refused; 110 accepted). A defect (D shadowing) was found and fixed before any real analysis. Synthetic files are in the scratchpad, not committed.
- Pre-registration `E6_PREREGISTRATION.md` written; X3 unscored (DOC-class, see Open for review); X1/X2/X4 operational definitions fixed in the analyzer before the run.
- OPEN FOR REVIEW (DOC-CLASS): X3 ('about even') has no direction; it is recorded as NOT SCORED rather than held/failed. Conservative choice: do not score it.
- 17:47:52 **INCIDENT (self-caught, pre-run, no data):** a synthetic analyzer test (scratchpad data, not real) wrote its outputs to the fixed `results/analysis/gate_e/e6/` directory, and six synthetic files were committed with `413d750`. None were run data. **Fix:** analyzer outputs now follow the data directory (`tests/e6_analyze.py`, one assignment; no statistical code changed); the six files were removed in the next commit. The positive control output is unchanged and remains committed. The analyzer change is a change to pre-registered code made before any run; it is disclosed here and in SESSION_SUMMARY.
17:48:07 Phase 3 DONE. Positive control PASS (exit 0). Phase 3 pushed (413d750; incident fix 4995606). Phase 4 starts.
17:48:16 Phase 4: isolated; platform re-checked (7.0.0-34, 595.91.07; stock nvidia_uvm loaded refcnt 0 before collection, expected).
19:36:53 Phase 4: isolated to multi-user.target (exit 0). Platform re-checked: 7.0.0-34-generic, 595.91.07, loaded stock 6284DA42 (refcnt 0), timers inactive, MemAvailable 61.4 GB, dmesg clean, 38 GB free. Collecting tables.
19:37:32 tables exit 0
19:38:55 smoke exit 0
19:39:17 Phase 5 starts: Family 1 in 10-row chunks (orchestrator scratchpad/run_e6.sh); Family 2 gated by the skip rule.
19:39:28 TIME NOTE: Phase 0 began 17:38:51. Family 2 deadline (Phase 0 + 2h15m) = 19:53:51 has passed; Family 2 will be SKIPPED under the skip rule when Family 1 ends. Session cap (3 h) = 20:38:51: if Family 1 is incomplete at the cap, the orchestrator is stopped at a chunk boundary (rows are resumable; not a stop condition; recorded as incomplete).
19:39:43 family1 chunk through idx 10: runner exit 0
19:40:08 family1 chunk through idx 20: runner exit 0
19:40:34 family1 chunk through idx 30: runner exit 0
19:40:59 family1 chunk through idx 40: runner exit 0
19:41:25 family1 chunk through idx 50: runner exit 0
19:41:48 observation: idx 20 and 22 each counted 1 new dmesg line; matched by timing to 'workqueue: drm_fb_helper_damage_work hogged CPU' (uptime 7936 s, 7941 s). Not in the stop pattern; not a stop. Recorded, not a departure.
19:41:50 family1 chunk through idx 60: runner exit 0
19:42:16 family1 chunk through idx 70: runner exit 0
19:42:41 family1 chunk through idx 80: runner exit 0
19:42:41 FAMILY 2 SKIPPED (skip rule): Family 1 ended after the deadline
19:45:30 INCIDENT (orchestrator): the run script wrote family2_skipped.txt at 19:42:41. Cause: script referenced an unset shell variable, so the deadline parsed as midnight. Correct check: Family 1 ended 19:42:41, deadline 19:53:51, so Family 2 is IN-WINDOW and runs. Skip record removed in a new commit (git rm); nothing else changed. Family 2 started by hand via tests/e6_runner.py chunks 90/100/110.
19:50:59 family2 chunk through 90: runner exit 0
19:56:27 family2 chunk through 100: runner exit 0
20:01:56 family2 chunk through 110: runner exit 0
20:02:04 Phase 5 DONE: 110 rows (80 F1 + 30 F2), all exit 0, no STOP. Phase 6: analyzer.
20:02:10 ANALYZER FIX before first analysis run: __main__ default referenced undefined name D (renamed to OUTDIR in Phase 3 but not here); changed default to OUTDIR. Analysis functions unchanged. Positive control re-run below.
20:05 Phase 6 analysis run. Output: primary_report.txt, family1_primary.csv, secondary_wall.csv, secondary_demand.csv, family2_graphbfs.csv, mechanism.csv; figure results/analysis/gate_e/e6_threshold.{png,pdf}.
20:05 RESULT: V-B FIRED (falsification trigger). C0-t0 and C0-t10 are Holm-significantly FASTER than C7W512-t51; C0-t25 not significant. Nothing further is run.
20:05 Four runs logged one new kernel line each (idx 20, 22, 79, 97), all matching the 'drm_fb_helper_damage_work hogged CPU' workqueue notice by uptime offset (16:40:08 = 7936 s; 79 at 8087 s, 97 at 8816 s). Not in the stop pattern; not a stop.
20:05 X3 not scored (pre-registered); the brief asked for held/failed on X1-X4; X3 cannot be marked without inventing a criterion, so it is recorded as not scored.
