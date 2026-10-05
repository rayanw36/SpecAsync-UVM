# Session summary — Gate C1-APPLY + D6/path audits + Gate E6

Session start (Phase 0): 2026-10-05 17:38:51 +03. Hard stop after Phase 7.

## Phases completed

| phase | status | commits (local unless noted) |
|---|---|---|
| 0 preflight | done | tree clean except `tests/group_probe`; kernel 7.0.0-34; driver 595.91.07; srcversions as pre-registered; driver/src unchanged since ea1a262 |
| 1 C1 review amendments + C1-APPLY | done | `b5ce787` (review amendments), `f3eda9d` (CLAIM_SCOPE v2, catalog #12–#25, EVIDENCE_EXTRACT regenerated; 197 ids resolved, 0 unresolved) |
| 2 D6 inventory + path audit | done (read-only) | `8b9d083` |
| 3 E6 pre-registration, scripts, positive control | done | `413d750` (pushed), `4995606` (pushed; removes six synthetic outputs committed in error) |
| 4 isolate + smoke | done | smoke `df97fb7` (8 rows, excluded from analysis) |
| 5 E6 sweep | done: 110 rows, all exit 0 | Family 1 chunks `ca262dd`…`a98caa4` (80 rows, 8 commits); Family 2 `13404b1`, `bc8d89c`, `ec8e2f2` (30 rows); skip record `24a11b3` reverted in `b5a05aa` |
| 6 analysis + report | done; push failed | `436ba2e` (report, analysis outputs, analyzer fix) |
| 7 this summary | done | this commit |

## E6 verdict

**V-B — falsification trigger fired.** C0 at threshold 0 and 10 is Holm-significantly faster than
C7W512-t51 (+6.39%, p 1.08e-05; +4.72%, p 2.06e-04). C0-t25 is not significantly slower (+2.11%, p 0.28).
Family 2 (GraphBFS): no threshold effect (|delta| ≤ 0.12%, not significant).
X1 held, X2 held, X3 not scored, X4 failed. Full report: `results/analysis/gate_e/GATE_E6_REPORT.md`.
The trigger was evaluated after all 110 pre-registered runs (the analysis step), and nothing was run after it.

## Open for review (DOC-class; not edited)

- X3 is not scored (its pre-registered expectation has no direction).
- E0 and E0.8 platform (kernel/driver) not recorded.
- Journal clock: the current boot lists an entry later than the present time.
- D6 option (a) execution (regenerate derived CSVs from raw data) is a follow-up; not done.
- PATH_AUDIT fixes not applied (22 hits in 10 script files; 2 patch files).
- Existing claims flagged for review, not edited: CS2-N1, CS2-N3, CS2-N4, and the limitation on C0 at thresholds below 51.
- E5 replication difference: C7W512-t51 vs C0-t51 is −5.26% in E5 and −3.36% in E6 (both significant). Not reconciled.

## Unresolved evidence ids

None. `tests/c1_check_ids.py`: 197 occurrences resolved, 0 unresolved, against 164 extracted rows.

## D6 raw-input inventory headline

13 PROSE-ONLY rows. 10 have raw inputs on disk (all gitignored; 6 have a committed regenerating script,
3 rely on command blocks only, 1 comparison was run inline and never committed). 2 events are recovered
from the persisted systemd journal. 1 is documentary.

## Path-audit count

22 hits in 10 script files (1 in `tests/`, 15 in `scripts/`, 6 in `driver/scripts/`), plus embedded
paths in 2 patch files. 326 portable kernel-interface references excluded.

## Incidents this session (all disclosed in `E6_STATUS.md`)

1. Synthetic analyzer outputs were written to the fixed output directory and committed in `413d750`; removed in `4995606`.
2. Analyzer variable shadowing (dict `D` vs output path `D`), fixed before any E6 run.
3. Orchestrator deadline bug: an unset shell variable made the deadline parse as midnight, so `family2_skipped.txt` was written at 19:42:41 (`24a11b3`). Family 2 was in-window (deadline 19:53:51); the record was reverted (`b5a05aa`) and Family 2 was run by hand in three chunks.
4. Analyzer entry point referenced an undefined name (`D`); fixed to `OUTDIR` before the first analysis run; positive control re-run and still PASS (−5.26%, p 1.08e-05, D(51) +0.4009).
5. Four E6 runs logged one new kernel line each (`workqueue: drm_fb_helper_damage_work hogged CPU`); not in the stop pattern; matched by uptime offset.

## Push and unpushed commits

- Push attempt after Phase 6 (`436ba2e`): **failed** — `fatal: could not read Username for 'https://github.com'` (headless; not worked around).
- Unpushed local commits: **15** (`git rev-list --count @{u}..HEAD`): `436ba2e`, the E6 sweep and smoke commits, the skip-record commit `24a11b3`, and its revert `b5a05aa`. Commits stay local until a push is possible.

## End state

- The specasync module was unloaded (`rmmod nvidia_uvm`, exit 0). `modprobe` needed a password, so the stock module was loaded from its file with `sudo -n insmod /lib/modules/7.0.0-34-generic/updates/dkms/nvidia-uvm.ko.zst`.
- Verified: `/sys/module/nvidia_uvm/srcversion` = `6284DA42F15EDC3AB92332B`, refcnt 0, `uvm_perf_prefetch_threshold` 51.
- Runtime target: multi-user.target (active). The boot default is still graphical.target; it was not changed.
- Untracked `tests/group_probe` was left as found.

## Stop

HARD STOP after Phase 7. No further runs.
