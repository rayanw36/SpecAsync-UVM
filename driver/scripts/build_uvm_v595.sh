#!/usr/bin/env bash
# Build the SpecAsync nvidia-uvm module for driver v595.71.05
set -euo pipefail

WORK=/opt/dlami/nvme/work/nvidia-595.71.05-specasync
LOGDIR="$HOME/SpecAsync-UVM/results/phaseB/logs"
mkdir -p "$LOGDIR"

echo "[build_uvm_v595] Starting build in $WORK"
make -C "$WORK" -j"$(nproc)" 2>&1 | tee "$LOGDIR/build_v595.log"
echo "[build_uvm_v595] Done. KO: $WORK/nvidia-uvm.ko"
modinfo "$WORK/nvidia-uvm.ko" | grep -E "srcversion|version"
