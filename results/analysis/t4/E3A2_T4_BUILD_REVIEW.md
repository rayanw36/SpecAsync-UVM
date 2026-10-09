# E3a-2 module: T4 build review packet (compile only, nothing inserted)

Gate T4-R1, T3. Built 2026-10-08 on the AWS g4dn.xlarge (Tesla T4), kernel **6.17.0-1017-aws**, gcc 13.3.0
(Ubuntu 13.3.0-6ubuntu2~24.04.1), source tree `/usr/src/nvidia-595.91.07` (apt `nvidia-kernel-source-595-open`
595.91.07-0ubuntu0.24.04.1, SHA256-verified against Launchpad, see T4_STATUS.md). WORK =
`/home/ubuntu/specasync-work/nvidia-595.91.07-specasync-e3a` (EBS root). **No module was insmod'ed**; the loaded
`nvidia_uvm` is still the stock one (srcversion 6284DA42F15EDC3AB92332B, threshold 51).

Precondition: `git diff ea1a262 HEAD -- driver/src` is empty (0 bytes).

## Result

| module | srcversion | vermagic | sha256 of .ko | 5070 Ti srcversion (PLATFORM_5070TI.md) |
|---|---|---|---|---|
| verified specasync (`reconstruct_build_tree.sh`) | **5997D238EF080B77DBD2AAF** | `6.17.0-1017-aws SMP mod_unload modversions` | 23904ec44f1e7e9a003f2b8130b0e0eb3e346357c8deafaab842e73cb5613112 | 5997D238EF080B77DBD2AAF: **identical** |
| E3a-2 (overlay of `driver/src-e3a`, incremental rebuild) | **33FD42E6E16B0A6658E2BEB** | `6.17.0-1017-aws SMP mod_unload modversions` | 1e6fcaac6a748effeec93cc4a827cca8d6f54b8e25758dcfdd9e6c2b43727654 | 33FD42E6E16B0A6658E2BEB: **identical** |

Both srcversions equal the 5070 Ti's. Explanation: a module srcversion is computed by modpost from the module's
**source files** (the files listed in each object's `.cmd`/`.mod`), not from the compiler, kernel config or the binary. Same 595.91.07
source tree + same specasync files gives the same hash on a different kernel. It does **not** mean the binaries are
identical: the .ko sha256 differs by construction (different kernel headers / vermagic), and the 5070 Ti .ko hashes are
not recorded in the repo, so no binary comparison is possible. (The stock srcversion likewise matched, 6284DA42...,
which the gate brief expected to differ; recorded in T4_STATUS.md.)

Procedure followed exactly as in PLATFORM_5070TI.md: `SRC=/usr/src/nvidia-595.91.07 WORK=... NV_KERNEL_MODULES="nvidia
nvidia-uvm nvidia-modeset nvidia-drm nvidia-peermem" driver/scripts/reconstruct_build_tree.sh` (4 vCPUs, 1m15s), then the
`cp driver/src-e3a/{specasync_debugfs.c,specasync_internal.h,specasync_telemetry.h,uvm_gpu_replayable_faults.c}`, `rm` of the two
stale .o and the .ko, and `make -C $WORK NV_KERNEL_MODULES=... modules -j4`.
Full make output: `build_verified_make_full.log`, `build_e3a2_make_full.log` (this directory).

## Setup problems met (and how they were resolved)

1. **The first verified build FAILED** (`uvm_va_space_t has no member named specasync_pred`, 5 errors). Cause:
   the `*.patch` files in `driver/patches/` are **Git LFS pointers** (`.gitattributes: *.patch filter=lfs`). The script's
   `patch -p0 --forward -N < specasync_selective_apply.patch || true` printed "Only garbage was found in the patch input" and
   the `|| true` swallowed it; the build then failed in the compiler. Fix: installed `git-lfs` (named package) and
   `git lfs pull --include="driver/patches/*"` (also fetched the 190 MB v580 patch, unused). Second build: all five files
   patched cleanly (`nvidia-uvm-sources.Kbuild`, `specasync_internal.h`, `uvm.c`, `uvm_va_space.c`, `uvm_va_space.h`), srcversion as above.
   **Worth knowing for any fresh clone:** `reconstruct_build_tree.sh` fails silently into a confusing compile error unless git-lfs is installed.
2. The script pipes make through `tail -25`; the full output was captured with a PATH shim (`make` wrapper that tees to a
   log; the script itself is unmodified).

## Warnings

Verified build, whole tree (full log): **13 warnings, 0 errors**, all in the core `nvidia` module, none in `nvidia-uvm` or any specasync file:

| count | file | warning |
|---:|---|---|
| 7 | `nvidia/nv-imp.c` lines 133, 171, 230, 305, 364 | `this use of "defined" may not be portable [-Wexpansion-to-defined]` |
| 6 | `nvidia/nv-vm.c` lines 601, 709, 739, 793, 873, 899 | `no previous prototype for nv_mem_pool_* / nv_init_page_pools / nv_destroy_page_pools [-Wmissing-prototypes]` |

E3a-2 incremental rebuild (recompiles `uvm_gpu_replayable_faults.o` and `specasync_debugfs.o`, relinks nvidia-uvm.ko): **0 warnings, 0 errors**.
These warnings are vendor-source style warnings in files this work does not touch; they say nothing about the specasync code.

## Kbuild / config differences from the 5070 Ti host

| item | T4 host (this gate) | 5070 Ti host (PLATFORM_5070TI.md / E3A_WIDTH_REVIEW.md) |
|---|---|---|
| kernel | 6.17.0-1017-aws | 7.0.0-34-generic |
| vermagic | `6.17.0-1017-aws SMP mod_unload modversions` | `7.0.0-34-generic SMP preempt mod_unload modversions` |
| preemption model | `CONFIG_PREEMPT_VOLUNTARY=y` (no `preempt` in vermagic) | `preempt` (CONFIG_PREEMPT*), from vermagic |
| kernel built with | gcc 13.3.0 (`CONFIG_CC_VERSION_TEXT`); module gcc 13.3.0, **same** | gcc 13.3.0 per /proc/driver/nvidia/version |
| driver source | 595.91.07 open, Ubuntu 24.04.1 package | same version/package |
| relevant CONFIG here | MODVERSIONS=y, MODULE_SIG=y (not forced), HMM_MIRROR=y, DEVICE_PRIVATE=y, MMU_NOTIFIER=y, TRANSPARENT_HUGEPAGE=y, NUMA_BALANCING=y, X86_KERNEL_IBT unset, MITIGATION_RETPOLINE=y, HZ=1000, PROVE_LOCKING unset | not recorded in the repo |
| distro patch applied | `patches/disable_fstack-clash-protection_fcf-protection.patch` (shipped in the apt source package) | same |

The `PREEMPT_VOLUNTARY` vs `PREEMPT` difference changes locking/scheduling behaviour around the fault-handler paths the
specasync code lives in (mutex/spinlock preemption). It does not change what compiles, but it is a **behavioural** difference to
keep in mind if the module is ever loaded here; stock-driver E7-T4 is unaffected by the E3a-2 module.

## Kernel-API differences for 6.17.0-1017-aws

* Conftest generated all its headers without error (functions.h 89 lines, headers.h 47, types.h 83, symbols.h 44,
  generic.h 32, patches.h 5, macros.h 1). The 5070 Ti conftest output is **not committed**, so a line-by-line API diff
  against 7.0.0-34 cannot be made from the repo; I did not guess. The 5-module set was needed again: it built without extra steps.
* No compile error or warning arises in the UVM tree, so no 6.17-specific API break was met in the code this work touches
  (`nvidia-uvm`, including all specasync hooks).
* `nvidia-drm.ko` builds but **cannot load** on this kernel: `nvidia_drm: Unknown symbol drm_fbdev_ttm_driver_fbdev_probe (err -2)`
  (dmesg 2026-10-08 16:49:25 UTC, while the stock driver was first modprobed; `nm -u` confirms the undefined symbol). The AWS kernel has
  `CONFIG_DRM_TTM_HELPER=m` but `drm_ttm_helper.ko` is not installed (linux-modules-extra not present); `find /lib/modules/6.17.0-1017-aws -name 'drm_ttm_helper*'` is empty.
  This concerns display only. `nvidia`, `nvidia_uvm` and `nvidia_modeset` load and the T4 compute stack works.
  Not fixed (no extra package installs beyond the brief); the message is not matched by the runner's stop regex.

## Not done in this gate (by design)

No `insmod` of either built module; no timing with them; no use of the specasync debugfs. Built artefacts are in
`~/specasync-work/out/` (`nvidia-uvm-verified.ko`, `nvidia-uvm-e3a2.ko`; `*.ko` is gitignored, not committed).
