# Root-owned paths under `results/` — reproducibility audit

Written 2026-08-12, T4 pre-resize work block. Purpose: the merge into `manuscript-prep`
earlier today broke partway through on files it couldn't overwrite as `ubuntu`, because
several harness scripts write their output as `root`. This is an inventory of every such
path, which harness produced it, and whether root is genuinely required for that output —
for the reproducibility notes, and so a future contributor knows to either `sudo` or
`chown` before re-running these harnesses.

## Method

`sudo find results -user root` enumerated every root-owned file/directory under `results/`.
The four distinct root-owned subtrees below account for all of them (483 paths total). Each
subtree's harness was identified by grepping `tests/*.sh` for the output path, then reading
the harness and its shared library (`tests/lib_specasync_harness.sh`) to determine which
specific operations need root.

## Shared root cause

All four harnesses source `tests/lib_specasync_harness.sh`, whose `reload_module()`
(`sudo rmmod`/`sudo insmod`, driver reload), `dump_ring()` (`sudo cat` of a debugfs file),
and `clear_ring()` (`echo 1 | sudo tee` a debugfs file) are the only operations that
genuinely need root — confirmed on this instance: `/sys/kernel/debug` is `drwx------ root:root`
(mode 0700), so even though the driver creates `specasync_log`/`specasync_fault_trace`/
`specasync_decomp_log` world-readable (0444) and `specasync_clear` world-writable (0222)
(`driver/src/specasync_debugfs.c:494-506`), the enclosing directory blocks all non-root
traversal — reading or clearing the ring is not optional-root, it is real-root.

However, each harness's usage line reads `sudo bash tests/tN_....sh` — the **entire script**
runs as root, not just the reload/debugfs steps. Inside `time_run()`, the benchmark binary
launches directly (`setarch -R "$bin" $args`, no `sudo` of its own) and inherits root only
because its parent shell already is root; the same is true of `csv_init`'s `mkdir -p` and CSV
row writes. CUDA/UVM benchmark execution does not itself need root (GPU device nodes are
normally world-accessible on this AMI). **Every root-owned output file below is root-owned
by inheritance from an unnecessarily-root parent shell, not because writing it requires
root.**

## Root-owned paths

| Path | Files | Size | Harness | Root genuinely needed? |
|---|---:|---:|---|---|
| `results/gate3/telemetry/` | 63 | 508M | `tests/t4_prefetch_off_telemetry.sh` (`run_c1_block`/`run_c3_block`'s `dump_ring` of `specasync_log`) | Only the ring dump (debugfs read, blocked by 0700 dir) and the module reload before each block. Benchmark execution and CSV writes do not need root. |
| `results/phaseB2/cufft_interleaved/` (incl. `telemetry/`) | 205 | 57M | `tests/t2_cufft_interleaved.sh` (interleaved p0-vs-p2 cuFFT rerun) | Same: `reload_module`/`dump_ring`/`clear_ring` need root; `nvcc` build, `bench_cufft` execution, CSV/python post-processing do not. |
| `results/phaseB2/gate3_interleaved/` (incl. `telemetry/`) | 179 | 555M | `tests/t1_gate3_interleaved.sh` (interleaved C0-C3 Gate3 rerun, reload before every run per `PREREGISTRATION.md`) | Root needed for oracle-trace collection (`sudo rmmod`/`insmod`, `sudo cat specasync_fault_trace`) and per-run `dump_ring`/`clear_ring`. Benchmark execution/CSV writes do not need it. |
| `results/phaseC/paired_wallclock/decomp/` | 30 | 5.5M | `tests/t3_phasec_paired_wallclock.sh` (paired wall-clock + `specasync_decomp_log` snapshot, 6 workloads) | Root needed only for `load_phasec_module` (one `insmod`, not per-run) and `dump_ring` reads of `specasync_decomp_log`. All 6 workloads' timed runs and CSV rows run under inherited root unnecessarily. |

`results/phaseB2/cufft_interleaved` and `results/phaseB2/gate3_interleaved` themselves (the
parent directories, mode `drwxr-xr-x root:root`) are also root-owned, though their top-level
`*_times.csv` files inside are `ubuntu`-owned — those CSVs were evidently written or later
`chown`'d separately from the directory creation; the `telemetry/` subdirectories and the two
`c3_*_trace.bin` files in `gate3_interleaved/` are fully root-owned.

## Not in scope here

`benchmarks/bench_cufft` (a compiled binary, root-owned) was also found root-owned by the same
`find`, but it sits outside `results/` and is a build artifact, reconstructible with `nvcc`
regardless of ownership — not included in the table above per this audit's `results/`-only
scope.

## Recommendation

None of the four harnesses need `sudo bash script.sh` for their full duration. The fix that
would prevent this recurring is narrow: change `reload_module`, `dump_ring`, and `clear_ring`
in `tests/lib_specasync_harness.sh` to invoke `sudo` only around their own debugfs/module
operations (already the case — they each call `sudo` internally), and change the four
harnesses' documented usage from `sudo bash tests/tN_....sh` to plain `bash tests/tN_....sh`
with passwordless `sudo` configured for exactly `rmmod`, `insmod`, and `cat`/`tee` on the
`specasync` debugfs nodes. That is a harness-invocation change, not something to make in this
session (out of scope for a pre-resize block, and changing `sudoers` policy is not something
to do unreviewed) — flagged here as the concrete fix for a future pass. Until then, expect
every rerun of these four harnesses to reproduce root-owned output, and `chown -R ubuntu:ubuntu`
(or a merge from a machine that ran them as `ubuntu`) before merging results from a different
machine or user.
