#!/usr/bin/env bash
# rebuild_and_reload.sh — Build SpecAsync-UVM module and hot-swap it safely.
#
# Must be run as root (or via sudo).  Safe to re-run; does not touch nvidia.ko.
#
# Usage:
#   sudo bash rebuild_and_reload.sh
#
# After success, prints the new srcversion so you can set SPECASYNC_SRCVERSION.

set -euo pipefail

WORK_SRC="/opt/dlami/nvme/work/nvidia-595.71.05-specasync/nvidia-uvm"
TOP_DIR="/opt/dlami/nvme/work/nvidia-595.71.05-specasync"
STOCK_KO="/lib/modules/6.17.0-1017-aws/updates/dkms/nvidia-uvm.ko"
STOCK_BACKUP="/home/ubuntu/SpecAsync-UVM/driver/stock_backup/nvidia-uvm.ko.stock"
NEW_KO="${TOP_DIR}/nvidia-uvm.ko"
KVER="$(uname -r)"

echo "[rebuild] Working dir: ${TOP_DIR}"
echo "[rebuild] Kernel: ${KVER}"

# ── 0. Guard: ensure stock backup exists ──────────────────────────────────────
if [[ ! -f "${STOCK_BACKUP}" ]]; then
    echo "[rebuild] ERROR: stock backup missing at ${STOCK_BACKUP}" >&2
    exit 1
fi

# ── 1. Build ──────────────────────────────────────────────────────────────────
echo "[rebuild] Building nvidia-uvm module ..."
cd "${TOP_DIR}"
make NV_KERNEL_MODULES="nvidia-uvm" KBUILD_EXTRA_SYMBOLS="${TOP_DIR}/Module.symvers" modules 2>&1 | tail -30

if [[ ! -f "${NEW_KO}" ]]; then
    echo "[rebuild] ERROR: build failed — ${NEW_KO} not found" >&2
    exit 1
fi

NEW_SRCVERSION="$(modinfo "${NEW_KO}" | grep '^srcversion:' | awk '{print $2}')"
echo "[rebuild] New srcversion: ${NEW_SRCVERSION}"

# ── 2. Safe module swap ───────────────────────────────────────────────────────
echo "[reload] Stopping nvidia-persistenced ..."
systemctl stop nvidia-persistenced 2>/dev/null || true

echo "[reload] Unloading current nvidia_uvm ..."
rmmod nvidia_uvm || { echo "[reload] ERROR: rmmod failed — GPU may be busy" >&2; exit 1; }

echo "[reload] Loading new module ..."
insmod "${NEW_KO}" || {
    echo "[reload] ERROR: insmod failed — restoring stock module" >&2
    insmod "${STOCK_BACKUP}"
    echo "[reload] Stock module restored." >&2
    exit 1
}

LOADED_SRCVERSION="$(cat /sys/module/nvidia_uvm/srcversion 2>/dev/null || echo unknown)"
echo "[reload] Loaded srcversion: ${LOADED_SRCVERSION}"

if [[ "${LOADED_SRCVERSION}" != "${NEW_SRCVERSION}" ]]; then
    echo "[reload] WARN: srcversion mismatch after load (kernel may have modified it)" >&2
fi

echo "[reload] Restarting nvidia-persistenced ..."
systemctl start nvidia-persistenced 2>/dev/null || true

echo ""
echo "=== SUCCESS ==="
echo "export SPECASYNC_SRCVERSION=\"${LOADED_SRCVERSION}\""
echo ""
echo "Rsync results to EBS:"
echo "  rsync -av /opt/dlami/nvme/work/nvidia-595.71.05-specasync/nvidia-uvm/nvidia-uvm.ko \\"
echo "    ~/SpecAsync-UVM/driver/build/nvidia-uvm-specasync-v595.ko"
