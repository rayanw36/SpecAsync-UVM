# Session summary: Gate C2-APPLY + Gate E7

Phase 0 start 2026-10-07 13:51:00 +03; session cap 16:51:00. All phases finished by about 14:50. Hard stop after Phase 7.

## Phases

| phase | status |
|---|---|
| 0 preflight + platform file | done. 16 unpushed commits pushed; `results/analysis/PLATFORM_5070TI.md` pushed (`cfdf7a1`) for the T4. Remote is **HTTPS, not SSH** (no SSH key on this host); the push worked through `gh` as a one-off credential helper |
| 1 CLAIM_SCOPE edits from the E6 review | done: CS2-N1 replaced, CS2-N3/N4 additions, new CS2-N10, limitation replaced, D1 note, `E6_REVIEW_NOTES.md`; `c1_evidence.py` extended (+27 E6 rows, 191 total); 194 cited ids resolved, **0 unresolved** |
| 2 read-only checks | done: `E6_GAP_ACCOUNT.md`, `E7_PARAM_CHECK.md`, `E7_BENCHMARKS.md` |
| 3 pre-registration + scripts | done; pushed before any run (`88a0f2c`). Positive control PASS (+6.39%, p 1.08e-05, D(51) +0.4017); self-tests PASS (scratch dir only) |
| 4 isolate + smoke | done: 27 smoke runs, all exit 0, excluded from analysis |
| 5 sweep | done: **310 of 310 rows, no Family B workload skipped, no stop** |
| 6 analysis + report | done: `gate_e/GATE_E7_REPORT.md`, figure `e7_threshold_by_workload.{png,pdf}`; one push attempt **failed** (headless) |
| 7 this file | done |

## E7 result (headline)

- **XA held, confirmatory:** stock Stencil-24K, threshold 0 is **−9.57%** vs 51 (p 1.08e-05, Holm-sig); threshold 10 **−7.13%**.
- **No workload was significantly slower at a lower threshold.** Faster at t0 (and t25): Sweep-16K −8.02%, STREAM −12.37%, SGEMM −2.49%, oversubscribed Stencil −16.95%. Not significant: Stencil-8K, Sweep-4K, cuFFT (−4.90%, borderline, p 0.036), GraphBFS-23.
- **XB3 FAILED** (expected oversub t0 slower; it is 17% faster). XB1, XB2, XB4, XC held (XC weakly; both block drifts n.s.).
- Family C: no detectable drift (C0 −0.37%, C7W512 +0.59%, n.s.). E7's C7W512-t51 vs C0-t51 is −5.34%, in line with E4 (−4.93%) and E5 (−5.26%); **E6 (−3.36%) is the outlier session**, cause not established.

## DOC-class items left open (all in `e7/E7_STATUS.md` "Open for review")

1. CS2-N1 item 5: the brief's "MDE about 2.3%" is the cross-threshold figure; the within-threshold MDEs are 1.8% (t0) and 2.0% (t10). Wrote 1.8% / 2.0%.
2. The brief's "C7W512-t51 1.0738 → E5 → 1.0918" skips E5's 1.0673; all three are tabulated.
3. CS2-5 ("only whole-block speculation saves time" vs the shipped C0) is still literally true at t51 and was not on the edit list; left, flagged.
4. STREAM size (268,435,456) and cuFFT size (134,217,728) are choices (CS2-14 records no size; CS2-12's source is two sizes). Timeouts: STREAM/cuFFT/Stencil 22 s, SGEMM 60 s, oversub 10 s (3 × 3.31 s).
5. The E0.9b helper's `mde_bonf_s` is hard-coded to α = 0.05/16, so the `mde_bonf_s` columns in E6's CSVs are not at E6's own family alphas (the E6 report does not quote them). E7 reports `mde_family_s`.
6. The runner-made commits in E4–E6 carry a hard-coded "Co-Authored-By: Claude Opus 5.5" trailer (`e09b_runner.git_commit`); E7's runner uses this session's trailer.
7. The E7 brief defines no verdict or falsification trigger; none was invented.
8. E6 review findings: the second "isolated" log entry in E6 has no matching journal command; the module resident at 19:36:53 was likely the verified specasync module, not stock (`E6_GAP_ACCOUNT.md`).
9. The journal-clock anomaly is explained (a −10,801 s step at about 35 s of uptime in the last two boots); why the clock started 3 h ahead is not established.
10. Existing claims flagged for review, not edited: CS2-N10, CS2-N1 (see the report).
11. Carried over from earlier sessions: X3 unscorable (documented in `E6_REVIEW_NOTES.md`); D6 option (a) regeneration; PATH_AUDIT fixes not applied; E0/E0.8 platform not recorded.

## Unresolved evidence ids

None: `tests/c1_check_ids.py` reports 194 resolved, 0 unresolved, against 191 extract rows.

## Push state

- Pushed: everything through `88a0f2c` (pre-registration) before the isolate.
- **37 commits unpushed** (the smoke commit, the sweep commits, the Phase 6 commit `954acaf` and this summary commit; recount with `git log @{u}..HEAD --oneline`). The push after the isolate failed: `could not read Username for 'https://github.com'`. The remote is HTTPS and `gh` keeps its token in the GNOME keyring, which does not exist without the desktop session. **To push, in the graphical session:** `git -c credential.helper='!gh auth git-credential' push`.

## End state

- Stock module loaded: srcversion `6284DA42F15EDC3AB92332B`, refcnt 0, `uvm_perf_prefetch_threshold` 51, no specasync parameters.
- Runtime target: **`multi-user.target`** (as E6). Boot default still `graphical.target`.
- **Deviation:** `sudo loginctl enable-linger rayenchikhaoui` was run at Phase 4 so that the user manager (and the tmux session this work runs in) survives the isolate. **It is still enabled.** Undo with `sudo loginctl disable-linger rayenchikhaoui`, but that stops `user@1000.service` and ends the tmux session, so I left it for you to run.
- `tests/group_probe` (untracked) left as found.

## Stop

HARD STOP after Phase 7. No further runs.
