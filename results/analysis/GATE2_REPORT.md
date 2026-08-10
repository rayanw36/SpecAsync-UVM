# Gate 2 — Build and module validation (T4 work block, Phase 2)

## 1. Stock module backup

The pre-existing `driver/stock_backup/nvidia-uvm.ko.stock` was taken for kernel
`6.17.0-1017-aws` (per `readelf -p .modinfo`'s vermagic field); this instance runs
`6.17.0-1019-aws`. Same srcversion (`85A79790636BBD99BA3E43B`, source-identical) but a
different vermagic/build, so the old backup's checksum did not match the live module and
would not have `insmod`'d cleanly as a rollback target. **Refreshed before any custom
module swap** (commit `1816e4a`): copied the live
`/lib/modules/6.17.0-1019-aws/updates/dkms/nvidia-uvm.ko`, checksum-verified identical
(`sha256sum` match). `driver/scripts/restore_stock_v595.sh` also had a stale hardcoded
`$HOME/SpecAsync-UVM` path (repo is actually at `$HOME/Downloads/SpecAsync-UVM`) — fixed
(commit `3810ad0`) before it would have been needed for an emergency rollback.

## 2. Build

`driver/scripts/reconstruct_build_tree.sh`, run against `/usr/src/nvidia-595.71.05`
(pristine, on-disk) + `driver/patches/specasync_selective_apply.patch` (glue) +
`driver/src/*.c,*.h` (authoritative SpecAsync sources), built in
`/opt/dlami/nvme/work/nvidia-595.71.05-specasync/` per the storage rules. Build succeeded
cleanly (`make ... modules`, no errors). Durable copy at
`driver/build/nvidia-uvm-specasync-t4.ko` (gitignored, like all `*.ko` in this repo --
reconstructible from source + patch, not committed, per `MIGRATION_NOTES.md`'s own
recommendation).

**srcversion: `8A2651D1CB32C7B239FB511`** -- identical to Phase C's build
(`nvidia-uvm-specasync-phaseC.ko`, per `D5_CHARACTERIZATION.md`/`PHASEC_REPORT.md`), which
is exactly what's expected: `driver/src/` is the same authoritative source tree this
session started from, and srcversion is a content hash of that source, so a faithful
rebuild reproduces it. Good corroborating evidence the reconstruction is correct, not a
divergent build.

A second variant was built with `ccflags-y += -DSPECASYNC_DECOMP=0` (for the overhead
check, Section 4), at `driver/build/nvidia-uvm-specasync-t4-decomp0.ko`. **Note:**
`srcversion` is a hash of on-disk `.c` source text, computed independent of compiler
macros/`ccflags-y` -- both builds report the identical srcversion string despite genuinely
different compiled code (confirmed by differing file size, 56,710,120 vs 56,703,896 bytes,
and by dmesg's own `decomp=0`/`decomp=1` init-time log line, which reads the actual
`SPECASYNC_DECOMP` value compiled in). Do not use `srcversion` alone to distinguish these
two builds when loaded -- check the dmesg init line or the file checksum instead.

## 3. Load, srcversion, debugfs surfaces

Loaded via `insmod` with `specasync_policy=0 specasync_offload_depth=0
uvm_perf_prefetch_enable=1 specasync_log_enabled=1` (a C0-equivalent baseline). Verified
after every load in this session (multiple reloads for the different checks below):
`/sys/module/nvidia_uvm/srcversion` matches the build's reported value every time; dmesg
shows only the expected `specasync: init OK ...` / `nvidia-uvm: SpecAsync-UVM v595 port
loaded` lines, no oops/warn/bug/panic/call-trace anywhere in the session's dmesg (scanned
explicitly, matches found are all pre-existing boot-time/unrelated-userspace lines, none
touching `nvidia_uvm` or `specasync`).

debugfs surfaces confirmed present at `/sys/kernel/debug/specasync/`: `specasync_clear`,
`specasync_decomp_log`, `specasync_fault_trace`, `specasync_log`, `specasync_worker_log`.
All five expected files exist with correct permissions (write-only clear, read-only rings).

## 4. Deterministic probe (Gate A sanity check)

Reloaded with `specasync_policy=1` (adjacent), `uvm_perf_prefetch_enable=0`,
`specasync_log_enabled=1` -- the exact configuration `GATE_A_report.md` used. Ran
`tests/run_hit_probe.sh 256 1`:

| metric | value |
|---|---|
| batches (valid) | 256 |
| demand faults | 256 |
| spec_enqueued | 256 |
| spec_processed | 256 (all "hit") |
| spec_hits | **255** |
| hit_rate | **0.9961** |

**Reproduces the ~99.22% reference** (`GATE_A_report.md`: 254/256 = 99.22%) within the
documented boundary-race variance -- one fewer expected miss this run (255/256 vs 254/256),
consistent with `GATE_A_report.md`'s own explanation ("page 0 is never predicted, and the
very first prediction races the first re-touch -- both expected boundary misses"; a
timing-dependent race can resolve either way run to run). The hit counter fires correctly;
the port is functioning.

## 5. Instrumentation overhead check

**No committed harness exists for Phase C's original G3 check** (`PHASEC_REPORT.md` states
the result -- DECOMP=0 1635.1ms vs DECOMP=1 1645.6ms, +0.64%, Stencil-24K, 5 trials -- but
no script in `tests/` reproduces the exact procedure). Ran a fresh comparison instead:

- Config: C0-equivalent (`policy=0 depth=0 prefetch=1`), the closest analog available.
- n=10 trials per build (Stencil@24000), median statistic (project's standard, per
  `STATISTIC_OF_RECORD.md`).

| Build | Median wall time | 
|---|---|
| DECOMP=0 | 4.180s |
| DECOMP=1 | 4.170s |
| **Overhead** | **-0.24%** |

**PASS against the <2% threshold**, decisively -- the measured overhead here is
negligible and even slightly negative (noise-dominated at this sample size, not a real
slowdown). **This does not reproduce Phase C's original absolute wall-clock baseline**
(1635-1646ms vs this session's 4170-4180ms for the nominally same Stencil-24K workload
under a C0-equivalent config) -- consistent with, not a new instance of,
`PIPELINING_CEILING.md`'s already-documented finding that Phase C's own decomp-harness
runs and Gate 3's C0-C3 sweep are not the same benchmark configuration under any config
tried in that task either. Also checked prefetch-OFF (C1-equivalent): 15.12s single run,
even further from Phase C's number, not closer -- ruling out "G3 used prefetch off" as the
explanation. This gap remains unresolved and out of scope for Gate 2 (which needs "is
overhead negligible," answered yes); it is not re-litigated further here, consistent with
`PIPELINING_CEILING.md`'s own decision not to force a resolution.

**Verdict: instrumentation overhead is negligible (well under the 2% threshold) under this
session's own matched-config measurement.** The specific 0.64% figure from Phase C is not
independently reproduced at the absolute-time level, for the pre-existing reason above, not
because the instrumentation itself is suspect.

## 6. Final state

Module left loaded: `driver/build/nvidia-uvm-specasync-t4.ko`, `policy=0 depth=0
prefetch=1 log_enabled=1` (C0-equivalent baseline), srcversion `8A2651D1CB32C7B239FB511`.
`nvidia-smi` confirms the GPU responds correctly through the loaded module. dmesg clean.
Ready for Phase 3.

**Gate 2: PASS.** Build log, srcversion, probe result, overhead figure, and dmesg-clean
confirmation all reported above.
