# Reproducing gates E4-E9 and E7-T4

Written in C5 step 7c from the committed runners, orchestrators, analyzers, pre-registrations and status logs. **Nothing below was re-run to produce this document except the analyzer positive controls marked "run in C5"** (analysis only, outputs to a scratch directory). Re-running a gate needs the machine, driver and module of `PLATFORM_5070TI.md`; read the gate's pre-registration first (cells, seed, order SHA-256, stop conditions). Repository root = `$SPECASYNC_ROOT`; run commands from there. Build the modules first (`README_DRAFT.md`, "Building the modules": git-lfs before the build).

**Common rules.** Preflight (kernel, driver, srcversion; upgrade timers inactive; host RAM above the largest managed allocation; a session that survives `systemctl isolate multi-user.target`: `loginctl enable-linger`, detached `systemd-run --user`; never `loginctl terminate-session` on the session that contains you). The runners reload the module for every run, read srcversion and the parameters back, diff `dmesg` by timestamp, and stop on any stop condition without retrying. Order files are regenerated from the committed seed and must match the committed SHA-256 (E6 to E9 and E7-T4 runners refuse otherwise; E4 and E5 record the hash in the pre-registration and status log only: check it by hand with `sha256sum`). Raw run directories (`results/phaseB1/gate_e*/`) are gitignored; the committed derived data are the `*_runs.csv` files.

Stock-module gates (E7, E8, E9, E7-T4) insert `/lib/modules/$(uname -r)/updates/dkms/nvidia-uvm.ko.zst` with `uvm_perf_prefetch_enable=<0|1> uvm_perf_prefetch_threshold=<t>`; the srcversion check expects `6284DA42F15EDC3AB92332B`. E4, E5 and E6 use the E3a-2 module (`33FD42E6E16B0A6658E2BEB`) and first-touch tables collected at the start of the run phase with `tests/e3b_collect_tables.py <tables_dir>` (the E0.9b collector, prefetch off; see each pre-registration for the distinct-page assertions).

| gate | order generator (seed) | run | analyzer | committed outputs |
|---|---|---|---|---|
| E4 | `tests/e4_make_order.py` (202609264) | `tests/e4_runner.py` | `tests/e4_analyze.py` | `gate_e/e4/` |
| E5 | `tests/e5_make_order.py` (202609265) | `tests/e5_runner.py` | `tests/e5_analyze.py` | `gate_e/e5/` |
| E6 | `tests/e6_make_order.py` (202610051) | `tests/e6_runner.py` (wraps e5_runner) | `tests/e6_analyze.py` | `gate_e/e6/` |
| E7 | `tests/e7_make_order.py` (202610071) | `tests/e7_orchestrate.py` -> `e7_runner.py` | `tests/e7_analyze.py` | `gate_e/e7/` |
| E8 | `tests/e8_make_order.py` (202610082) | `tests/e8_orchestrate.py` -> `e8_runner.py` | `tests/e8_analyze.py` | `gate_e/e8/` |
| E9 | `tests/e9_make_order.py` | `tests/e9_orchestrate.py` -> `e9_runner.py` (nsys) | `tests/e9_analyze.py` | `gate_e/e9/` |
| E7-T4 | `results/analysis/t4/e7t4_make_order.py` (202610072) | `t4/e7t4_orchestrate.py` -> `e7t4_runner.py` | `t4/e7t4_analyze.py` | `results/analysis/t4/` |

## E4 (10 arms x Stencil-24K and GraphBFS-23, n = 10, 200 runs; E3a-2 module)
1. `python3 tests/e3b_collect_tables.py $RAW/tables` (verified module, prefetch off), then `python3 tests/e4_make_order.py results/analysis/gate_e/e4/e4_order.csv` (and the smoke order).
2. `python3 tests/e4_runner.py --order results/analysis/gate_e/e4/e4_order.csv --csv results/analysis/gate_e/e4/e4_runs.csv --out-dir results/phaseB1/gate_e4/sweep --tables $RAW/tables --commit-msg "Gate E4 sweep" --commit-every 10` (the unchanged `e3b_runner` loop in chunks; interrupted sweeps resume at the next index not in the CSV, never restarted).
3. `python3 tests/e4_analyze.py` (defaults: `results/analysis/gate_e/e4`, raw `results/phaseB1/gate_e4/sweep`). It refuses to run unless all 200 rows exist. Identities per policy-6 run: `python3 tests/e4_identities.py results/analysis/gate_e/e4/e4_runs.csv`.
- **Inputs:** `e4_order.csv`, the tables, the module. **Outputs:** `e4_runs.csv`, `primary_comparisons.csv` (18 comparisons, one Holm family), `mechanism.csv`, `integrity.txt`, `f2_f4_statements.txt`, `results/analysis/gate_e/e4_wallclock_by_arm.{pdf,png}`.
- **Positive control: none exists for the E4 analyzer.** The checks that stand in for it are the refusal rule, `integrity.txt` (order adherence 200/200, srcversion, dmesg 0, ring coverage, Identity 1 on 160/160) and the helpers being `tests/e09b_analyze.py` unchanged. Recorded as open in `C5_STATUS.md`.

## E5 (Stencil-24K, C0 / C7W512 x threshold {51, 75, 100}, n = 10, 60 runs; E3a-2 module)
1. Tables as E4; `python3 tests/e5_make_order.py results/analysis/gate_e/e5/e5_order.csv`.
2. `python3 tests/e5_runner.py --order ... --csv results/analysis/gate_e/e5/e5_runs.csv --out-dir results/phaseB1/gate_e5/sweep --tables $RAW/tables --commit-msg "Gate E5 sweep" --commit-every 10` (the threshold column goes to `insmod` and is read back).
3. `python3 tests/e5_analyze.py` (refuses unless all 60 rows exist).
- **Outputs:** `e5_runs.csv`, `fault_reduction.csv` and `.md` (D(t), the H-feed verdict), `wallclock_comparisons.csv`, `mechanism.csv`, `integrity.txt`, `e5_threshold.{pdf,png}`.
- **Positive control: none for the E5 analyzer.** E6's control (below) recomputes E5's headline from the committed `e5_runs.csv` with E6's analyzer, which cross-checks the shared helpers, not E5's own script.

## E6 (threshold {0, 10, 25, 51} x C0 / C7W512, Stencil-24K, plus GraphBFS Family 2 if time allowed)
1. Tables as E4; `python3 tests/e6_make_order.py results/analysis/gate_e/e6/e6_order.csv results/analysis/gate_e/e6/e6_smoke_order.csv`.
2. `python3 tests/e6_runner.py --order ... --csv results/analysis/gate_e/e6/e6_runs.csv --out-dir results/phaseB1/gate_e6/sweep --tables $RAW/tables --commit-msg "Gate E6 ..." --commit-every 10`.
3. Control: `python3 tests/e6_analyze.py --control`. Analysis: `python3 tests/e6_analyze.py` (110 rows, or 80 when Family 2 was skipped and `e6/family2_skipped.txt` exists; E6's status log records that file being written by a script error, see `E6_STATUS.md` 19:45:30).
- **Outputs:** `e6_runs.csv`, `family1_primary.csv`, `family2_graphbfs.csv`, `secondary_wall.csv`, `secondary_demand.csv`, `mechanism.csv`, `primary_report.txt`, `e6_threshold.{pdf,png}`.
- **Positive control (run in C5): PASS.** Reproduces E5: delta -5.26%, MWU p = 1.08e-05, D(51) = +0.4009 (medians 203,331 / 339,386). Note `--control` **overwrites the committed `e6/analyzer_positive_control.txt`** (the rewrite differed only by one trailing blank line; reverted in C5).

## E7 (9 workloads, thresholds {0, 25, 51}, n = 10, 310 rows; stock module)
1. `python3 tests/e7_make_order.py results/analysis/gate_e/e7/e7_order.csv results/analysis/gate_e/e7/e7_smoke_order.csv`; verify against `e7_order.sha256`. Write the Phase 0 timestamp to `e7/phase0_start.txt` (the orchestrator computes all deadlines from it and aborts if any is not later than now).
2. `python3 tests/e7_orchestrate.py smoke` then `python3 tests/e7_orchestrate.py sweep [--start-file F]` (runner called with `--order-sha256 e7_order.sha256 --commit-every 10`; CSVs committed during the run).
3. Control then analysis: `python3 tests/e7_analyze.py --control <scratch_dir>`; `python3 tests/e7_analyze.py --selftest`; `python3 tests/e7_analyze.py`.
- **Outputs:** `e7_runs.csv`, `family_a.csv`, `family_b.csv`, `family_c.csv`, `session_medians.csv`, `primary_report.txt`, `E7_BENCHMARKS.md`, `E7_PARAM_CHECK.md`.
- **Positive control (run in C5): PASS.** Reproduces E6 (D(51) = +0.4017 from `e6_runs.csv`). The committed record is `e7/analyzer_positive_control.txt`.

## E8 (sparse access; K {1, 8, 64, 512} x size {8, 24 GiB} x threshold {0, 25, 51}, n = 10; stock module)
1. `benchmarks/bench_sparse` must be built (`make` in `benchmarks/`); correctness: `python3 tests/e8_validate_bench.py`. `python3 tests/e8_make_order.py results/analysis/gate_e/e8/e8_order.csv results/analysis/gate_e/e8/e8_smoke_order.csv`; verify `e8_order.sha256`; write `e8/phase0_start.txt`. Host RAM must exceed the 24 GiB array plus the floor (pre-registration: min `MemAvailable` 30.4 GiB).
2. `python3 tests/e8_orchestrate.py smoke` (writes `e8_timeouts.csv`, `dropped_cells.txt` if any), then `python3 tests/e8_orchestrate.py sweep [--start-file F]` (Family IN always; OV by K group in the order 1, 512, 8, 64 under the skip rule; Family M last; skips recorded in `ov_skipped.txt`, `m_skipped.txt`).
3. `python3 tests/e8_analyze.py --control <scratch_dir>`; `python3 tests/e8_analyze.py --selftest`; `python3 tests/e8_analyze.py` (refuses unless rows = order rows minus dropped cells and skipped groups).
- **Outputs:** `e8_runs.csv`, `primary_tests.csv` (one Holm family), `family_m_mechanism.csv`, `per_pass_descriptive.csv`, `primary_report.txt`, `bench_validation.log`.
- **Positive control (run in C5): PASS.** Reproduces E7 Family A from `e7_runs.csv`: delta -9.57%, p = 1.08e-05.

## E9 (descriptive, nsys-traced, n = 3; stock module; needs nsys 2025.3.2)
1. `python3 tests/e9_make_order.py results/analysis/gate_e/e9/e9_order.csv results/analysis/gate_e/e9/e9_smoke_order.csv`; verify `e9_order.sha256`; `e9/phase0_start.txt` (or `cap_anchor.txt` after a pause).
2. `python3 tests/e9_orchestrate.py smoke`, then `sweep` (runs each benchmark as `timeout T nsys profile --trace=cuda --cuda-um-gpu-page-faults=true --cuda-um-cpu-page-faults=true ... setarch -R <bench>`, extracts counts with `tests/e9_extract.py`; any nsys failure is a stop; wall-clock is recorded, never compared).
3. `python3 tests/e9_analyze.py --control <scratch_dir>` (**re-derives one traced 1 GiB `bench_sparse` run: needs the GPU, nsys and a loaded stock module; not run in C5**), `--selftest`, then `python3 tests/e9_analyze.py`.
- **Outputs:** `e9_runs.csv`, `cell_medians.csv`, `primary_report.txt`, `e9_timeouts.csv`, `extraction_control.txt`. No hypothesis test (n = 3); the figure `fig_e9` is descriptive.
- **Positive control:** the committed `e9/extraction_control.txt` records PASS (SQLite totals equal nsys's `um_total_sum`: HtoD, DtoH, GPU faults, causes and per-pass sums). **Not re-run in C5 (needs a GPU).**

## E7-T4 (Tesla T4, 24 stock cells x n = 10 = 240 rows; Amendments 1 and 2 apply)
1. On the T4 (g4dn.xlarge, kernel 6.17.0-1017-aws, driver 595.91.07): `python3 results/analysis/t4/e7t4_make_order.py <order> <smoke_order>` (seed 202610072; verify `e7t4_order.sha256`); the sweep covers idx 1-240 (the oversubscribed Stencil rows are not run; `E7T4_AMENDMENT_2.md`); `phase0_start_4.txt`.
2. Launch **once**, detached from any login session: `SPECASYNC_REPO=$PWD T4_CAP_HOURS=4 systemd-run --user --unit=e7t4-sweep bash results/analysis/t4/e7t4_chain.sh` (smoke, timeouts file, sweep; halts on the first failure).
3. `python3 results/analysis/t4/e7t4_analyze.py --control <outfile>`, then `python3 results/analysis/t4/e7t4_analyze.py`.
- **Outputs:** `e7t4_runs.csv`, `family_a.csv`, `family_b.csv` (14 tests, one Holm family), `analyze_stdout.txt`, `e7t4_threshold_by_workload.{pdf,png}`, `GATE_E7T4_REPORT.md`.
- **Positive control (run in C5): PASS.** Reproduces E7 Family A from the 5070 Ti `e7_runs.csv` (stock-t0 vs stock-t51, m = 2): p = 1.08e-05. The committed record is `t4/e7t4_positive_control.txt`.

## Figures and checks that need no hardware
- `python3 tests/make_paper_figures.py [e4 e5 e6 e7 e8 e9 ph]` rebuilds `paper/figures/` and `FIGURES.md` from the committed CSVs.
- `python3 tests/c1_check_ids.py` checks evidence ids against `consolidation/EVIDENCE_EXTRACT.md`.
