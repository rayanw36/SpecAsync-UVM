# Phase 2b: were E4, E5 and E6's C7W512-t51 and C0-t51 arms parameterised identically?

Read-only. Sources: the committed `e4_runs.csv`, `e5_runs.csv`, `e6_runs.csv` (columns kept per run) and the
runner code (`tests/e3b_runner.py` `params()` / `expected()`, `tests/e5_runner.py`), which builds the `insmod`
line from the order-file row.

## 1. Columns that are in the CSVs (identical across gates)

Every run in each arm has the same value of each of these columns, and the three gates agree:

| column | C0 (E4 `stencil C0`, E5 `stencil C0-t51`, E6 `stencil C0-t51`) | C7W512 (E4 `stencil C7-W512`, E5/E6 `stencil C7W512-t51`) |
|---|---|---|
| `module` | `new` | `new` |
| `srcversion` | `33FD42E6E16B0A6658E2BEB` | `33FD42E6E16B0A6658E2BEB` |
| `policy` | 0 | 6 |
| `depth` (offload) | 0 | 1 |
| `prefetch` (`uvm_perf_prefetch_enable`) | 1 | 1 |
| `L` (`specasync_ft_lookahead`) | blank (not passed) | 4096 |
| `W` (`specasync_spec_width`) | 1 | 512 |
| `fast` (`specasync_ft_fast`) | 0 | 1 |
| `trace_faults` | 0 | 0 |

## 2. Parameters set by the runner code but not stored per run

From `params()` (`e3b_runner.py:48-56`) and `e5_runner.py:18`:

| parameter | E4 | E5 | E6 |
|---|---|---|---|
| `specasync_log_enabled` | 1 | 1 | 1 |
| `specasync_ft_table_path` (policy 6 only) | E4's table | E5's table | E6's table |
| `uvm_perf_prefetch_threshold` | **not passed** (module default; every other source says 51) | `51` passed, read back, stop on mismatch | `51` passed, read back, stop on mismatch |

- The read-back of each parameter is a **stop check** in the runner. It is **not written to the CSV**.
  So the threshold, `log_enabled` and the table path are **not verifiable from the CSVs**; they are verified only
  by the runner's code and by the absence of a stop. For E4 the threshold is the module default.
- This is a gap, not a mismatch. E7's runner writes the read-back threshold to its CSV.

## 3. What does differ between the gates: the first-touch table (C7W512 arm only)

Each gate collected a **fresh** stencil table with `e3b_collect_tables.py` (E4's dated 2026-09-26 00:27, E5's 10:57,
E6's 2026-10-05 19:36; all on disk under the gitignored `results/phaseB1/gate_e{4,5,6}/tables/`).

| pair | same page set | same position | max displacement | median displacement |
|---|---|---:|---:|---:|
| E4 vs E5 | yes (1,125,000 pages) | 25,967 (2.31%) | 98 | 12 |
| E5 vs E6 | yes | 26,125 (2.32%) | 103 | 12 |
| E4 vs E6 | yes | 26,007 (2.31%) | 115 | 12 |

- Caveat on E4: its sweep ran 2026-09-25 21:29 → 09-26 07:22 across a restart, while the table directory's files are dated 00:27. I did not verify that every E4 C7W512 run used that file (the run CSV does not store the table path).
- The three tables are **three different orderings of the same pages**: nearly every entry sits at a different
  index, by at most ~100 positions (this is CS2-N6, fault-order nondeterminism, seen directly).
- The C0 arm has no table. So **the table is the one input that differs across sessions for C7W512 and is absent
  for C0**, which is the arm that varies (see `E6_REVIEW_NOTES.md` §2).
- This is **a candidate explanation, not a finding**: it has not been tested that table ordering moves the C7W512
  median. E7 Family C does not isolate it (it uses one table within the session).

## 4. Conclusion

For `C0-t51` and `C7W512-t51`, every stored parameter column agrees across E4, E5 and E6, and the runner code is
the same code path (`e3b_runner` → `e4_runner` → `e5_runner`), with the one difference that E4 did not pass the
threshold. The only input known to differ is the first-touch table.
