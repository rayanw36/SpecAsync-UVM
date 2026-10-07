# Platform facts for the T4 port (5070 Ti reference host)

Recorded 2026-10-07 (Gate C2-APPLY / E7, Phase 0). Every value below was read from this host
today unless marked otherwise.

| item | value |
|---|---|
| GPU | NVIDIA GeForce RTX 5070 Ti |
| `/proc/driver/nvidia/version` | `NVRM version: NVIDIA UNIX Open Kernel Module for x86_64  595.91.07  Release Build  (dvs-builder@U22-I3-B08-02-2)  Wed Jul 29 03:01:16 UTC 2026` ; `GCC version: gcc version 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1)` |
| Kernel module flavour | **Open** (`nvidia-dkms-595-open`). `modinfo nvidia`: `license: Dual MIT/GPL`, `version: 595.91.07`, file `/lib/modules/7.0.0-34-generic/updates/dkms/nvidia.ko.zst` |
| How 595.91.07 was installed | **Ubuntu apt packages, not the runfile.** `dpkg -l`: `nvidia-dkms-595-open`, `nvidia-driver-595-open`, `nvidia-kernel-common-595`, `nvidia-kernel-source-595-open`, all `595.91.07-0ubuntu0.24.04.1` (changelog: "New upstream version 595.91.07", Canonical, 2026-08-09). DKMS builds it per kernel (`dkms status`: installed for 7.0.0-28, -31, -34). DKMS source tree: `/usr/src/nvidia-595.91.07`. |
| Kernel | 7.0.0-34-generic |
| CUDA toolkit | 13.0 (`/usr/local/cuda/bin/nvcc`: release 13.0, V13.0.88; `nvcc` is not on `PATH`). Also apt `libcudart12` etc. 12.0.146 (distro runtime libs, not the toolkit used for the benchmarks). |
| gcc | 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1) |
| Source `driver/src` builds against | The open-gpu-kernel-modules source shipped in `nvidia-kernel-source-595-open` 595.91.07, i.e. upstream release **595.91.07**. NVIDIA's open-gpu-kernel-modules repo tags releases by driver version, so the tag is `595.91.07`. **The commit hash was not recorded and cannot be read from the installed package** (no `.git`); the Ubuntu package does carry `patches/disable_fstack-clash-protection_fcf-protection.patch`. The 595.91.07 build from committed `driver/src` reproduces srcversion `5997D238EF080B77DBD2AAF` exactly (E3A_WIDTH_REVIEW.md). |
| srcversions | stock `6284DA42F15EDC3AB92332B`; verified specasync (`driver/src`) `5997D238EF080B77DBD2AAF`; E3a-2 module `33FD42E6E16B0A6658E2BEB` |

## Build command for the E3a-2 module (`nvidia-uvm-specasync-NEW-e3a2-width-ftfast.ko`)

From the repo root (needs `rsync`, `patch`, `make`, kernel headers for the running kernel; no sudo):

```
SRC=/usr/src/nvidia-595.91.07 \
WORK=$HOME/specasync-work/nvidia-595.91.07-specasync-e3a \
NV_KERNEL_MODULES="nvidia nvidia-uvm nvidia-modeset nvidia-drm nvidia-peermem" \
  driver/scripts/reconstruct_build_tree.sh
# this reproduces the VERIFIED module (srcversion 5997D238EF080B77DBD2AAF) from driver/src

# overlay the E3a-2 sources (cumulative E3a + E3a-2 files; see driver/patches/e3a_spec_width.patch
# and driver/patches/e3a2_region_history_ft_fast.delta.patch), then rebuild incrementally:
cp driver/src-e3a/{specasync_debugfs.c,specasync_internal.h,specasync_telemetry.h,uvm_gpu_replayable_faults.c} \
   "$WORK/nvidia-uvm/"
rm -f "$WORK"/nvidia-uvm/{uvm_gpu_replayable_faults.o,specasync_debugfs.o} "$WORK"/nvidia-uvm.ko
make -C "$WORK" NV_KERNEL_MODULES="nvidia nvidia-uvm nvidia-modeset nvidia-drm nvidia-peermem" \
     modules -j"$(nproc)"
modinfo "$WORK/nvidia-uvm.ko" | grep -E '^srcversion|^vermagic'   # expect 33FD42E6E16B0A6658E2BEB on this host
```

Notes for the T4:

- The full 5-module set is needed on this host because `nvidia-uvm` alone fails conftest
  (`NV_IS_EXPORT_SYMBOL_GPL_*`); the script's default `SRC`/`WORK` are the old AWS T4 paths
  (`/usr/src/nvidia-595.71.05`, `/opt/dlami/nvme/...`), hence the explicit overrides (see `PATH_AUDIT.md`).
- A srcversion depends on source plus build inputs, so a different kernel or header set on the T4 can give
  a different srcversion for identical source. Compare the verified-module rebuild first, as E3A did.
- The build order above is reconstructed from `GATE_E0_5_REPORT.md` and `E3A_WIDTH_REVIEW.md`; I did not
  re-run the build today.
- The E3a-2 module was the one used for E4, E5, E6; the stock module is loaded by default.
