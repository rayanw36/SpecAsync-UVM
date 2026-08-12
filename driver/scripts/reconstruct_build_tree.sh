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

echo "[reconstruct] build nvidia-uvm module"
# Limit the build to nvidia-uvm but feed it the core nvidia module's exported
# symbol versions (nvUvmInterface*) so modpost can resolve them without
# rebuilding the (prebuilt) nvidia.ko.
make -C "$WORK" NV_KERNEL_MODULES="nvidia-uvm" \
     KBUILD_EXTRA_SYMBOLS="$WORK/Module.symvers" \
     modules -j"$(nproc)" 2>&1 | tail -25

test -f "$WORK/nvidia-uvm.ko" || { echo "[reconstruct] BUILD FAILED: no .ko" >&2; exit 1; }
echo "[reconstruct] OK: $WORK/nvidia-uvm.ko"
modinfo "$WORK/nvidia-uvm.ko" | grep -E '^srcversion|^vermagic'
