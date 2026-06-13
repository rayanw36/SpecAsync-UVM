#!/usr/bin/env bash
# resume.sh — Run this after every instance restart to load the patched
#             nvidia-uvm module and relaunch the oracle (p4) sweep.
#
# Usage:  sudo bash ~/SpecAsync-UVM/scripts/resume.sh
#
# Fast path: if the compiled .ko is on EBS, it is loaded directly (no rebuild).
# Slow path: if the .ko is missing, it is rebuilt from source (~3 min).

set -euo pipefail

EBS_HOME="/home/ubuntu/SpecAsync-UVM"
EBS_KO="${EBS_HOME}/driver/build/nvidia-uvm-specasync.ko"   # fast path
SRC_STOCK="/usr/src/nvidia-595.71.05"
WORK_TOP="/opt/dlami/nvme/work/nvidia-595.71.05-specasync"
WORK_KO="${WORK_TOP}/nvidia-uvm.ko"
STOCK_KO="/lib/modules/$(uname -r)/updates/dkms/nvidia-uvm.ko"
STOCK_BACKUP="${EBS_HOME}/driver/stock_backup/nvidia-uvm.ko.stock"
SELECTIVE_PATCH="${EBS_HOME}/driver/patches/specasync_selective_apply.patch"
LOG_DIR="${EBS_HOME}/results/phaseB/logs"

echo "========================================"
echo "  SpecAsync-UVM resume script"
echo "  $(date)"
echo "========================================"

# ── 0. Guard: stock backup must exist ────────────────────────────────────────
if [[ ! -f "${STOCK_BACKUP}" ]]; then
    echo "ERROR: stock backup missing at ${STOCK_BACKUP}" >&2; exit 1
fi

# ── 1. Ensure stock nvidia_uvm is loaded (may not be after cold boot) ─────────
if ! lsmod | grep -q "^nvidia_uvm"; then
    echo "[1/5] Loading stock nvidia_uvm ..."
    insmod "${STOCK_KO}"
fi
echo "[1/5] Stock module loaded: $(cat /sys/module/nvidia_uvm/srcversion)"

# ── 2. Determine which .ko to use ────────────────────────────────────────────
if [[ -f "${EBS_KO}" ]]; then
    echo "[2/5] Using pre-built .ko from EBS (no rebuild needed)"
    NEW_KO="${EBS_KO}"
elif [[ -f "${WORK_KO}" ]]; then
    echo "[2/5] Using .ko from NVMe work tree"
    NEW_KO="${WORK_KO}"
else
    echo "[2/5] No pre-built .ko found — rebuilding from source (~3 min) ..."

    mkdir -p /opt/dlami/nvme/work
    chown ubuntu:ubuntu /opt/dlami/nvme/work

    echo "  Copying stock source tree ..."
    cp -a "${SRC_STOCK}" "${WORK_TOP}"

    # Restore Module.symvers (must be 104 lines — gets overwritten by failed builds)
    cp "${SRC_STOCK}/Module.symvers" "${WORK_TOP}/Module.symvers"
    SYMVER_LINES=$(wc -l < "${WORK_TOP}/Module.symvers")
    echo "  Module.symvers: ${SYMVER_LINES} lines"
    if (( SYMVER_LINES < 100 )); then
        echo "ERROR: Module.symvers only ${SYMVER_LINES} lines" >&2; exit 1
    fi

    # Copy modified SpecAsync source files from EBS
    echo "  Applying SpecAsync source files ..."
    cp "${EBS_HOME}/driver/src/specasync_debugfs.c"               "${WORK_TOP}/nvidia-uvm/"
    cp "${EBS_HOME}/driver/src/specasync_faults_instrumentation.c" "${WORK_TOP}/nvidia-uvm/"
    cp "${EBS_HOME}/driver/src/specasync_telemetry.h"              "${WORK_TOP}/nvidia-uvm/"
    cp "${EBS_HOME}/driver/src/uvm_gpu_replayable_faults.c"        "${WORK_TOP}/nvidia-uvm/"

    # Apply patch for remaining modified files
    echo "  Applying patch ..."
    patch -p0 --directory="${WORK_TOP}/nvidia-uvm" < "${SELECTIVE_PATCH}"

    # Build (restore symvers first — modpost overwrites it)
    echo "  Building nvidia-uvm module ..."
    cp "${SRC_STOCK}/Module.symvers" "${WORK_TOP}/Module.symvers"
    cd "${WORK_TOP}"
    make NV_KERNEL_MODULES="nvidia-uvm" \
         KBUILD_EXTRA_SYMBOLS="${WORK_TOP}/Module.symvers" \
         modules 2>&1 | tail -10

    if [[ ! -f "${WORK_KO}" ]]; then
        echo "ERROR: build failed — ${WORK_KO} not found" >&2; exit 1
    fi

    # Save to EBS for next time (skip the rebuild)
    cp "${WORK_KO}" "${EBS_KO}"
    echo "  Saved to EBS: ${EBS_KO}"
    NEW_KO="${WORK_KO}"
fi

echo "  Module srcversion: $(modinfo "${NEW_KO}" | grep '^srcversion:' | awk '{print $2}')"

# ── 3. Hot-swap to patched module ────────────────────────────────────────────
CURRENT_SRC="$(cat /sys/module/nvidia_uvm/srcversion 2>/dev/null || echo none)"
PATCHED_SRC="$(modinfo "${NEW_KO}" | grep '^srcversion:' | awk '{print $2}')"

if [[ "${CURRENT_SRC}" != "${PATCHED_SRC}" ]]; then
    echo "[3/5] Hot-swapping to patched module ..."
    rmmod nvidia_uvm || { echo "ERROR: rmmod failed — GPU may have a stuck process" >&2; exit 1; }
    if ! insmod "${NEW_KO}"; then
        echo "ERROR: insmod failed — restoring stock module" >&2
        insmod "${STOCK_KO}" || true
        exit 1
    fi
    echo "[3/5] Patched module loaded: $(cat /sys/module/nvidia_uvm/srcversion)"
else
    echo "[3/5] Patched module already active: ${CURRENT_SRC}"
fi

# ── 4. Verify debugfs interface ───────────────────────────────────────────────
NODES=$(ls /sys/kernel/debug/specasync/ 2>/dev/null | wc -l || echo 0)
PARAMS=$(ls /sys/module/nvidia_uvm/parameters/ 2>/dev/null | grep -c specasync || true)
echo "[4/5] Debugfs nodes in /specasync/: ${NODES}, module params: ${PARAMS}"
if (( NODES < 4 || PARAMS < 4 )); then
    echo "ERROR: debugfs interface incomplete" >&2; exit 1
fi

# ── 5. Launch oracle sweep in background (survives disconnect) ────────────────
echo "[5/5] Launching oracle sweep in background ..."
mkdir -p "${LOG_DIR}"

nohup bash -c "
    sudo bash ${EBS_HOME}/scripts/oracle_sweep.sh \
        2>&1 | tee ${LOG_DIR}/p4_sweep.log
    echo SWEEP_DONE >> ${LOG_DIR}/pipeline_status.txt
" > "${LOG_DIR}/nohup_sweep.log" 2>&1 &

SWEEP_PID=$!
sleep 1
PPID_CHECK=$(ps -o ppid= -p ${SWEEP_PID} 2>/dev/null | tr -d ' ' || echo unknown)

echo ""
echo "========================================"
echo "  Oracle sweep launched (PID ${SWEEP_PID}, PPID=${PPID_CHECK})"
echo ""
echo "  Monitor:  tail -f ${LOG_DIR}/p4_sweep.log"
echo "  Done?:    cat ${LOG_DIR}/pipeline_status.txt"
echo "  ETA:      ~15 min (Stencil_OvSub dominates)"
echo "========================================"
