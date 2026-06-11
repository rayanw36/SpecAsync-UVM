#!/usr/bin/env bash
# Install and verify the SpecAsync nvidia-uvm module for driver v595.71.05
# Must be run as root (or with sudo).
set -euo pipefail

WORK=/opt/dlami/nvme/work/nvidia-595.71.05-specasync
POLICY="${SPECASYNC_POLICY:-1}"
LOG="${SPECASYNC_LOG:-1}"
DEPTH="${SPECASYNC_DEPTH:-0}"

if [ ! -f "$WORK/nvidia-uvm.ko" ]; then
    echo "ERROR: $WORK/nvidia-uvm.ko not found. Run build_uvm_v595.sh first." >&2
    exit 1
fi

echo "[install_uvm_v595] Stopping nvidia-persistenced..."
systemctl stop nvidia-persistenced 2>/dev/null || true

echo "[install_uvm_v595] Unloading stock nvidia_uvm..."
modprobe -r nvidia_uvm

echo "[install_uvm_v595] Loading SpecAsync nvidia-uvm.ko (policy=$POLICY log=$LOG depth=$DEPTH)..."
insmod "$WORK/nvidia-uvm.ko" \
    specasync_policy="$POLICY" \
    specasync_log_enabled="$LOG" \
    specasync_offload_depth="$DEPTH"

echo "[install_uvm_v595] srcversion: $(cat /sys/module/nvidia_uvm/srcversion)"
dmesg | tail -5 | grep -i specasync || true

echo "[install_uvm_v595] Restarting nvidia-persistenced..."
systemctl start nvidia-persistenced 2>/dev/null || true

echo "[install_uvm_v595] Done."
