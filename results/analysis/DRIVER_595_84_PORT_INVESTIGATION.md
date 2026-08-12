# Driver 595.84 port investigation (Part 2, gated -- report only, no build attempted)

This machine runs driver **595.84** (`nvidia-smi`: `595.84, NVIDIA GeForce RTX 5070 Ti`).
The project's patches target 595.71.05 (`specasync_uvm_v595.71.05.patch`, the reference/
documentation patch) and 580.95.05 (`specasync_uvm_v580.95.05.patch`, superseded). This
report answers whether the 595.71.05 patch can be expected to apply to 595.84, before any
port is attempted.

## 1. Does a 595.84 tag exist?

**Yes, public source.** `NVIDIA/open-gpu-kernel-modules` on GitHub carries a `595.84` tag
(confirmed via the GitHub API tag list, alongside `595.71.05`, `595.80`, `595.91.07`, and
the 595.44.x/595.58.03 series). Not proprietary-only -- the cross-platform work is not
blocked at this step.

**Local source also present and verified identical to the tag.** `/usr/src/nvidia-595.84/`
exists on this machine (shipped by the installed DKMS driver package) and is byte-identical
(`diff -q`, all five files checked) to the `595.84` tag's `kernel-open/nvidia-uvm/` content
fetched fresh from GitHub -- the local install is not a modified or unofficial build.

## 2. Diff: 595.71.05 vs 595.84, files the patches touch

Two patches exist with different roles, both checked:

- `specasync_uvm_v595.71.05.patch` (39,634 B) -- the full reference/documentation diff
  against pristine 595.71.05. Touches 8 files: `nvidia-uvm-sources.Kbuild`,
  `specasync_debugfs.c` (new), `specasync_internal.h` (new), `specasync_telemetry.h` (new),
  `uvm.c`, `uvm_gpu_replayable_faults.c`, `uvm_va_space.c`, `uvm_va_space.h`.
- `specasync_selective_apply.patch` (5,488 B) -- the **actual glue patch**
  `driver/scripts/reconstruct_build_tree.sh` applies at build time. Touches 5 files:
  `nvidia-uvm-sources.Kbuild`, `specasync_internal.h` (new), `uvm.c`, `uvm_va_space.c`,
  `uvm_va_space.h`. (`uvm_gpu_replayable_faults.c` and `specasync_debugfs.c`/
  `specasync_telemetry.h` are not patched at build time at all -- `driver/src/` carries
  the fully-integrated authoritative copies, which get `cp`'d directly over the pristine
  file, per `reconstruct_build_tree.sh`.)

Fetched `nvidia-uvm-sources.Kbuild`, `uvm.c`, `uvm_gpu_replayable_faults.c`, `uvm_va_space.c`,
`uvm_va_space.h` at both the `595.71.05` and `595.84` tags from the public repo and diffed:

```
nvidia-uvm-sources.Kbuild        0 differences
uvm.c                             0 differences
uvm_gpu_replayable_faults.c       0 differences
uvm_va_space.c                    0 differences
uvm_va_space.h                    0 differences
```

**Every file either patch touches is byte-for-byte identical between 595.71.05 and 595.84.**
Confirmed with `diff -u` (0 lines of output on all five) and cross-checked with `sha256sum`
to rule out an empty-fetch false negative (files are non-trivial: `uvm_gpu_replayable_faults.c`
is 3,081 lines, contains 32 occurrences of `service_fault_batch`, real content).

## 3. Conflict assessment: empirical dry-run

Not content to rest on the diff alone: copied the four pre-existing files
`specasync_selective_apply.patch` touches from the **local** `/usr/src/nvidia-595.84/nvidia-uvm/`
into a scratch directory and ran the actual patch command
(`patch -p0 --forward -N < specasync_selective_apply.patch`) against them.

```
patching file nvidia-uvm-sources.Kbuild
patching file specasync_internal.h
patching file uvm.c
patching file uvm_va_space.c
patching file uvm_va_space.h
exit=0
```

**Applies cleanly: zero fuzz, zero offset, zero rejected hunks, all 5 files.** This is the
strongest confirmation short of an actual kernel build -- every hunk matched at its exact
expected line number, which is only possible because the base files are identical to what
the patch was built against. `uvm_gpu_replayable_faults.c` needs no patch-conflict check at
all (`driver/src/`'s copy overwrites the pristine file outright), and since that file is also
confirmed byte-identical between driver versions, overwriting 595.84's copy with the
595.71.05-derived integrated version is equivalent to a from-scratch port, not a stale
substitution.

**Verdict: the patch should apply to 595.84 with zero conflicts.** No hunks to report as
conflicting because none do.

## 4. sm_120 (Blackwell) compatibility

Searched all of SpecAsync's added code (`driver/src/specasync_*.c`, `driver/src/specasync_*.h`,
and the SpecAsync-authored regions of `uvm_gpu_replayable_faults.c`) for any
architecture-specific logic (SM/compute-capability checks, chip-ID branches, references to
Pascal/Volta/Ampere/Hopper/Blackwell, GPU generation gating): **zero matches.** SpecAsync's
entire added surface operates at the CPU-side fault-servicing/workqueue layer -- predicting
VA addresses, enqueueing work items, doing metadata-only `uvm_va_block_find` lookups on the
existing `uvm_va_block_t` -- and never touches GPU-generation-specific paths (PTE formats,
fault-buffer hardware layout, replay mechanics); those all remain inside the stock,
unmodified UVM code the patch doesn't touch. Separately, the **stock** 595.84 driver (this
patch's unmodified base) is already the driver actively running this Blackwell GPU
(`nvidia-smi` responds correctly) -- Blackwell support is not in question at the base-driver
level, only whether SpecAsync's additions assume something that doesn't hold on it, and
nothing found does.

**No porting work identified beyond a clean patch application.**

## 5. Display server status

```
$XDG_SESSION_TYPE = x11
systemctl status display-manager: gdm.service active (running), GNOME Display Manager
loginctl: 1 active graphical session (seat0, tty2)
```

**This machine is running a full desktop session, not headless.** The T4 instance Part 1-2's
GPU work was collected on had no compositor. If Part 3 (wall-clock replication) proceeds on
this machine without changes, compositor/desktop activity is a noise source the T4 baseline
did not have and must be recorded as a threat to validity; the cleaner option is to run headless
(switch to a non-graphical target for the measurement session, e.g. `systemctl isolate
multi-user.target`, reversing afterward) rather than merely disclosing the caveat.

## Summary

| Question | Answer |
|---|---|
| 595.84 tag exists, public source? | Yes |
| Files the patches touch, changed between 595.71.05 and 595.84? | No -- 0 of 5, byte-identical |
| Patch conflict, empirically tested? | None -- clean apply, zero fuzz/offset/rejects |
| sm_120-specific porting needed? | None identified -- SpecAsync's added code has no architecture-specific logic, and the stock 595.84 base already runs this GPU |
| Display server | X11 desktop session active (GDM) -- not headless, threat to validity for Part 3 |

**Recommendation (not acted on, per this part's gating): the port looks unusually clean --
build and validate (Part 3.2) can very likely proceed directly from `reconstruct_build_tree.sh`
with `SRC=/usr/src/nvidia-595.84`, no patch-hunk editing anticipated.** Stopping here as
instructed; no build attempted, no module loaded, no changes to the running system.
