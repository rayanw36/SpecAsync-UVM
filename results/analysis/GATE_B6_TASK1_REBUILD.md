# Gate B6, Task 1 — rebuild with A1 counters on RTX 5070 Ti (sm_120, driver 595.84)

Platform: local RTX 5070 Ti, Blackwell (sm_120), driver 595.84, kernel 7.0.0-28-generic.
See `results/analysis/platform/5070TI_PLATFORM_PROVENANCE.txt` for full provenance.

## Starting state

The `nvidia_uvm` module loaded on this machine at the start of this session
(srcversion `FADA940587C8B92B63A0FFF`) was confirmed, by diffing its build tree
(`~/build/nvidia-595.84-specasync/nvidia-uvm/`) against `driver/src/`, to predate the
`g_specasync_processed` / `g_specasync_enqueued` / `g_specasync_drops` atomics merged in
from the T4 work (`GATE_A1_REPORT.md`). `nm` on the built `.ko` confirmed zero occurrences
of those three symbols. This matches the task brief's premise exactly.

## Build

Ran `driver/scripts/reconstruct_build_tree.sh` with `SRC=/usr/src/nvidia-595.84`,
`WORK=/home/rayenchikhaoui/build/nvidia-595.84-specasync`.

**First attempt (nvidia-uvm alone, the script's default) failed**, but not on the new
counters: `nv-linux.h` (unmodified NVIDIA infrastructure header, unrelated to specasync)
referenced conftest macros (`NV_IS_EXPORT_SYMBOL_GPL_set_memory_encrypted`,
`NV_IS_EXPORT_SYMBOL_PRESENT_swiotlb_map_sg_attrs`, etc.) that were never generated because
those checks are only registered by the core `nvidia` module's Kbuild, not `nvidia-uvm`'s.
This is the same conftest-registration gap `GATE_B5_5070TI_REPLICATION.md` hit and worked
around by building all 5 modules together — that workaround had not been folded back into
the script. Building all 5 modules together after a full `make clean` (conftest/ must be
regenerated from scratch, not just the changed `.o` files) resolved it; the specasync `.c`
files themselves compiled without incident on the first pass, before this was fixed.

**Made `reconstruct_build_tree.sh` host-portable for this**: `NV_KERNEL_MODULES` is now
`: "${NV_KERNEL_MODULES:=nvidia-uvm}"` (overridable, default unchanged, so the T4 path is
untouched), the full-module-set path now runs `make clean` first, and
`KBUILD_EXTRA_SYMBOLS=$WORK/Module.symvers` is only passed when building `nvidia-uvm` alone
against an already-built symvers file (passing a self-referential, not-yet-existing
`Module.symvers` to a fresh 5-module build was a second bug this surfaced and fixed). Verified
by re-running the edited script standalone end-to-end (`NV_KERNEL_MODULES="nvidia nvidia-uvm
nvidia-modeset nvidia-drm nvidia-peermem"`): exit 0, identical resulting srcversion both times
(determinism check).

Only `nvidia-uvm.ko` was ever unloaded/reloaded; `nvidia`/`nvidia-modeset`/`nvidia-drm` stayed
the running (stock DKMS) instances throughout, since this machine has an active GNOME/X11
desktop session using them and `nvidia_uvm` had zero users at reload time — same approach
`GATE_B5_5070TI_REPLICATION.md` used.

## Verification (all four required checks)

| Check | Result |
|---|---|
| New srcversion differs from `FADA940587C8B92B63A0FFF` | **`9E98EF08CBA769C50A24937`** — differs |
| `nm` shows `g_specasync_processed`/`enqueued`/`drops` | Present (confirmed before load) |
| Three debugfs files exist and are readable | `/sys/kernel/debug/specasync/specasync_{processed,enqueued,drops}` all readable, all `0` post-reload/pre-probe |
| Deterministic hit-probe: ~99.6% hit rate | **255/256 = 99.61%** (T4: ~99.6%; 5070 Ti B5 replication: 99.61% — consistent) |
| Non-wrapping validation: processed == enqueued == 256, drops == 0 | **processed=256, enqueued=256, drops=0** — confirmed |
| Zero dmesg warnings | Confirmed — only the two expected init lines (`specasync: init OK ...`, `nvidia-uvm: SpecAsync-UVM v595 port loaded`) at module load; `dmesg` clean (no new lines) through the probe run |

Probe run parameters (matching `GATE_A_report.md`'s Gate A setup): `specasync_policy=1`,
`specasync_offload_depth=0`, `uvm_perf_prefetch_enable=0`, `specasync_log_enabled=1`.
Reloaded module with these as insmod arguments; `specasync_clear` written before the probe.
Run-order index 1, timestamp `2026-08-12T19:08:44Z`. Raw batch/worker ring snapshots:
`results/phaseB1/hit_probe_5070ti/task1_probe_{batch,worker}.bin` (gitignored, raw
telemetry).

## Verdict

**The counters build cleanly on sm_120/595.84 and validate identically to the T4's Gate A
setup.** Task 1 is not blocked; Tasks 2 and 3 may proceed.
