#!/usr/bin/env bash
# reconstruct_build_tree.sh — rebuild the SpecAsync v595 work tree from scratch.
#
# The NVMe instance store (/opt/dlami/nvme) is wiped on every instance stop, so
# the buildable tree must be reconstructed from:
#   - the pristine DKMS source at /usr/src/nvidia-595.71.05  (kernel build infra)
#   - the authoritative specasync sources in driver/src/      (post-patch, fixed)
#   - the glue diff driver/patches/specasync_selective_apply.patch
#     (uvm.c, uvm_va_space.{c,h}, Kbuild sources list)
#
# driver/src/ is the source of truth for the big specasync files (newer than the
# full patch). Run from anywhere; needs no sudo (writes only to the work tree).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
: "${SRC:=/usr/src/nvidia-595.71.05}"
: "${WORK:=/opt/dlami/nvme/work/nvidia-595.71.05-specasync}"
# nvidia-uvm alone can leave conftest/ missing symbol checks (e.g.
# NV_IS_EXPORT_SYMBOL_GPL_set_memory_encrypted) that nv-linux.h references
# unconditionally -- those checks are only registered by the core "nvidia"
# module's Kbuild. Building the full module set regenerates conftest/
# completely; only nvidia-uvm.ko needs to actually be loaded afterward.
# Confirmed necessary on the 5070 Ti (595.84); default kept at "nvidia-uvm"
# only since the T4 (595.71.05) build has not been observed to need this.
: "${NV_KERNEL_MODULES:=nvidia-uvm}"
UVM="$WORK/nvidia-uvm"

echo "[reconstruct] rsync $SRC -> $WORK (--delete: make dest exactly pristine)"
mkdir -p "$WORK"
rsync -a --delete "$SRC/" "$WORK/"

echo "[reconstruct] apply glue patch (uvm.c, uvm_va_space.*, Kbuild)"
# --forward -N: skip already-applied/new-file hunks silently, never prompt.
( cd "$UVM" && patch -p0 --forward -N < "$REPO/driver/patches/specasync_selective_apply.patch" || true )

echo "[reconstruct] copy authoritative specasync sources from driver/src"
cp "$REPO"/driver/src/uvm_gpu_replayable_faults.c "$UVM/"
cp "$REPO"/driver/src/specasync_debugfs.c        "$UVM/"
cp "$REPO"/driver/src/specasync_telemetry.h      "$UVM/"
cp "$REPO"/driver/src/specasync_internal.h       "$UVM/"   # overwrites patch's older copy

echo "[reconstruct] drop stale objects for changed translation units"
rm -f "$UVM"/uvm_gpu_replayable_faults.o "$UVM"/uvm_va_space.o "$UVM"/uvm.o \
      "$UVM"/specasync_debugfs.o "$WORK"/nvidia-uvm.ko "$WORK"/nvidia-uvm.o 2>/dev/null || true
if [ "$NV_KERNEL_MODULES" != "nvidia-uvm" ]; then
    echo "[reconstruct] NV_KERNEL_MODULES=$NV_KERNEL_MODULES (not just nvidia-uvm): full clean so conftest/ regenerates for all modules"
    make -C "$WORK" clean >/dev/null 2>&1 || true
fi

echo "[reconstruct] build $NV_KERNEL_MODULES module(s)"
# Limit the build to nvidia-uvm but feed it the core nvidia module's exported
# symbol versions (nvUvmInterface*) so modpost can resolve them without
# rebuilding the (prebuilt) nvidia.ko. Only meaningful (and only exists) when
# nvidia-uvm is built alone against an already-built nvidia.ko's symvers; when
# the full module set is built together in one invocation, Module.symvers is
# produced internally by that same build and must not be pre-fed to itself.
EXTRA_SYMS=()
if [ "$NV_KERNEL_MODULES" = "nvidia-uvm" ] && [ -f "$WORK/Module.symvers" ]; then
    EXTRA_SYMS=(KBUILD_EXTRA_SYMBOLS="$WORK/Module.symvers")
fi
make -C "$WORK" NV_KERNEL_MODULES="$NV_KERNEL_MODULES" \
     "${EXTRA_SYMS[@]}" \
     modules -j"$(nproc)" 2>&1 | tail -25

test -f "$WORK/nvidia-uvm.ko" || { echo "[reconstruct] BUILD FAILED: no .ko" >&2; exit 1; }
echo "[reconstruct] OK: $WORK/nvidia-uvm.ko"
modinfo "$WORK/nvidia-uvm.ko" | grep -E '^srcversion|^vermagic'
