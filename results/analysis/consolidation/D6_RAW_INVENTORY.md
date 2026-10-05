# D6 raw-input inventory (Gate C1-APPLY, Phase 2a)

Read-only. For each PROSE-ONLY number in `C1_REVIEW.md`: is its raw input still on disk,
and which committed script would regenerate a derived CSV? **Nothing was regenerated.**
Inventory taken 2026-10-05 ~18:00 +03.

**Headline.** Of the 13 PROSE-ONLY rows:
- **10 have raw inputs on disk.** All 10 directories are gitignored, so no derived CSV
  exists in git. Six of the ten have a committed script that regenerates them. Three
  rely on command blocks in the report prose, with no committed script. One comparison
  (row 7) was run inline and never committed.
- **2 events are recovered from the persisted systemd journal** (rows 11 and 13).
- **1 is documentary** (row 12), recorded in a tracked ledger file.

Decision D6 (a) is therefore feasible for 10 rows, and needs the 3 command-block rows
and the row-7 comparison turned into committed scripts first.

## Table

| row | number(s) | raw input | on disk | size, files, mtime | gitignored | committed regenerating script | regenerates derived CSV? |
|---|---|---|---|---|---|---|---|
| 1 | E0 §7 over-consumption 11.7× / 2.1×; wrap counts | `results/phaseB1/gate_e05_realworkload/` **and** the committed traces `results/analysis/t_a1_worker/full_run/c3_bench_{stencil,graph_bfs}_trace.bin` | yes | 38 MB, 5 files, 2026-09-24 17:49; traces 2.2 MB and 1.6 MB, 2026-08-11 | the directory: yes (`.gitignore` line 188). **The traces are tracked in git.** | **none**: E0.5 Step 5 is a command block in `GATE_E0_5_REPORT.md` | **no** (command block only). The trace-entry counts can be recomputed from the tracked traces (entries = bytes ÷ 8) |
| 2 | E0.5 post-fix 1:1 alignment 2,953,867 / 483,896 | `results/phaseB1/gate_e05_realworkload/` | yes | as row 1 | yes | **none** (command block) | **no** |
| 3 | `oracle_coalesce` 442/56, 23/56, 1/57, 442/450 (E0.5 Addendum) | `results/phaseB1/oracle_coalesce/` | yes | 24 KB, 4 files, 2026-08-10 14:57 | yes (`.gitignore` line 49) | `tests/run_oracle_coalesce.sh` | **yes**, with the module and a GPU |
| 4 | serialized probe 254/256 (GATE_A) | `results/phaseB1/oracle_probe/` | yes | 76 KB, 6 files, 2026-08-10 14:57 | yes (line 48) | `tests/run_oracle_probe.sh` | **yes**, with the module and a GPU |
| 5 | E0.8 index-drift statistics (displacement 107; Spearman; duplicate-count differences 1,247–4,418) | `results/phaseB1/gate_e07_check1/` and `…/gate_e07_check2/` | yes | 79 MB + 79 MB; 7 + 6 files; 2026-09-24 21:01–21:07 | yes (`.gitignore` lines 195–197) | `tests/gate_e08_index_drift_analysis.py` (reads both); `tests/gate_e07_accuracy_analysis.py` | **partly**: the script prints to stdout; no committed derived CSV exists |
| 6 | E0.8/E0.9 forward-set 98.48%, backward 0.0708%, 51.19%, symmetric 99.9997%, the 31.4→51.7 pts progression | as row 5 | yes | as row 5 | yes | as row 5 | **partly**, as row 5 |
| 7 | E4 post-reboot table check: displacement 98 / 35,823 against 96 / 37,992 | `results/phaseB1/gate_e4/postreboot_check/` and `results/phaseB1/gate_e4/tables/` | yes | 37 MB each; 4 files each; 2026-09-26 09:41 and 00:27 | yes (`results/phaseB1/gate_e4/` is ignored) | the tables: `tests/e3b_collect_tables.py` (committed). **The comparison was an inline script, not committed** | **no**. The comparison has to be written as a committed script |
| 8 | E0.9a-2 "prevented = 0.0000% at every L" | `results/phaseB1/gate_e09a2_validation/` | yes | 195 MB, 22 files, 2026-09-25 13:02 | yes (`.gitignore` lines 211) | **none**: no committed script names this directory; the command block is in `GATE_E0_9A2_REPORT.md` | **no**. The aggregate H-map evidence *is* in committed CSVs (E4 `mechanism.csv`, E5 `mechanism.csv`) |
| 9 | corrected pipelining ceilings 0.08–7.94%, 7.25%, 9–30% | `results/phaseC/paired_wallclock_5070ti/decomp/` (5.5 MB, 30 files, 2026-08-13) and `results/phaseC/paired_wallclock/decomp/` (5.5 MB, 30 files, 2026-08-10) | yes | as stated | yes (`.gitignore` lines 61, 139) | `tests/t3_phasec_paired_wallclock.sh` (capture) and `tests/gatec1_decomp_analysis.py` (analysis; the formula is prose in `CEILING_BASIS_VERIFICATION.md` §6) | **yes**, provided the corrected formula is applied, which is itself prose; that formula is what D6 must commit |
| 10 | B10 "truncated + rotated" classification | `results/analysis/gate_b10_augmentation/` (25 MB, 140 files) and `…gate_b10_replication/` (33 MB, 185 files) | yes | as stated | **mixed**: `*.bin` and the telemetry directories are ignored (`.gitignore` lines 172–174, 179–181); other files are tracked | `tests/t_b10_c0_vs_c4.sh`; `tests/t_b10c_replication_crossover.sh` | **yes** for the wall-clock CSVs. The classification is a source property (ring capacity 1,048,576, with a truncation check), not a CSV value |
| 11 | E0.9a-2 crash signature (kernel NULL dereference; "exited with irqs disabled") | **the persisted journal**, boot `5f825cf714844fdfa62fdf5ce38e62ef` (2026-09-25 12:28–12:46) | yes (recovered) | `12:37:05` lines: `BUG: kernel NULL pointer dereference, address: 0000000000000000` and `note: UVM GPU1 BH[20671] exited with irqs disabled` | n/a | n/a (event) | n/a |
| 12 | platform drift (595.84 → 595.91.07; kernel -28 → -31 → -34) | `results/analysis/COMPLETENESS_LEDGER.md` (tracked) | yes | 32 KB, 2026-09-25 17:38 | no | n/a (documentary) | n/a |
| 13 | E3b harness failure (empty line-count dmesg slice) | **the persisted journal**, boot `235bb163b4c44589a9be5b360145619e` (2026-09-25 12:51 → 09-26 00:48), **and** the tracked post-fix `results/analysis/gate_e/e3b/step1_reject.csv` | yes (recovered) | lines at `2026-09-26 00:00:33`: `specasync: specasync_spec_width=0 rejected: must be a power of two in [1, 512]`; `nvidia_uvm: '0' invalid for parameter …` (14 matching lines in that boot) | n/a | n/a (event) | n/a |

## Observations that affect reliance on this inventory

- **Journal coverage is limited.** Only 11 boots are retained (2026-09-08 onward). The
  E0.9a-2 crash boot survived because it is one of the last ones. Once the journal
  rotates past it, row 11 becomes prose-only. Copying the two lines into the catalog
  entry (#22) would preserve them. That is a decision for review, not done here.
- **The journal's own clock looks wrong.** The current boot (index 0) lists a first entry
  at `Mon 2026-10-05 20:27:54`, later than the present time, about 17:45 +03. Recovered
  timestamps are used as printed, and this should be checked before they are cited as
  wall-clock evidence.
- **All derived CSVs for rows 1–10 are absent from git.** The raw dirs are ignored by
  design (see the `.gitignore` comments), so "derived CSV committed" is currently false
  for every PROSE-ONLY number in `C1_REVIEW.md`.
- **Row 7's comparison** (98 / 35,823 against 96 / 37,992) was computed in a session
  shell, not saved. The inputs are on disk, but the result is reproducible only by
  rerunning that comparison.
