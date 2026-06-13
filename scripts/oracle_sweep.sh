#!/usr/bin/env bash
# oracle_sweep.sh — Run policy=4 (oracle) experiments after collect_oracle_traces.sh.
#
# Sets specasync_oracle_trace_path for each benchmark and runs 20-run timing sweeps.
# Results go to ~/SpecAsync-UVM/results/p4_d0/{bench}/{size}/
#
# Must be run as root.

set -euo pipefail

BENCH_DIR="$(cd "$(dirname "$0")/../benchmarks" && pwd)"
UBUNTU_HOME="/home/ubuntu"
ORACLE_DIR="${UBUNTU_HOME}/SpecAsync-UVM/oracles"
RESULTS_DIR="${UBUNTU_HOME}/SpecAsync-UVM/results/p4_d0"
DEBUGFS="/sys/kernel/debug/specasync"
TOOLS_DIR="${BENCH_DIR}/tools"
PARSE="${TOOLS_DIR}/specasync_parse.py"

NUM_STAT_RUNS=20
WARMUP_RUNS=1

BENCHMARKS=(
    "SGEMM:${BENCH_DIR}/bench_sgemm:24000"
    "Stencil:${BENCH_DIR}/bench_stencil:24000"
    "STREAM:${BENCH_DIR}/bench_stream:268435456"
    "GraphBFS:${BENCH_DIR}/graph_bfs/bench_graph_bfs:23"
    "cuFFT:${BENCH_DIR}/bench_cufft:268435456"
    "Stencil_OvSub:${BENCH_DIR}/stencil_oversub/bench_stencil_oversub:28300 20 11264"
)

# Verify module is the SpecAsync build
ACTUAL_SRCVER="$(cat /sys/module/nvidia_uvm/srcversion 2>/dev/null || echo unknown)"
echo "[oracle_sweep] Module srcversion: ${ACTUAL_SRCVER}"
if [[ "${ACTUAL_SRCVER}" == "85A79790636BBD99BA3E43B" ]]; then
    echo "[oracle_sweep] FATAL: stock module loaded — run rebuild_and_reload.sh first" >&2
    exit 1
fi

echo "[oracle_sweep] Policy=4 is set per module reload (oracle trace loaded at init)."

UBUNTU_HOME="/home/ubuntu"
EBS_KO="${UBUNTU_HOME}/SpecAsync-UVM/driver/build/nvidia-uvm-specasync.ko"
NVME_KO="/opt/dlami/nvme/work/nvidia-595.71.05-specasync/nvidia-uvm.ko"
# Use EBS copy when NVMe is wiped (stop/start clears instance store)
if [[ -f "${NVME_KO}" ]]; then
    PATCHED_KO="${NVME_KO}"
else
    PATCHED_KO="${EBS_KO}"
fi
STOCK_KO="/lib/modules/$(uname -r)/updates/dkms/nvidia-uvm.ko"
echo "[oracle_sweep] Using module: ${PATCHED_KO}"

reload_module_with_trace() {
    local trace_path="$1"
    rmmod nvidia_uvm 2>/dev/null || true
    if ! insmod "${PATCHED_KO}" specasync_oracle_trace_path="${trace_path}" \
                                specasync_policy=4 specasync_log_enabled=1; then
        echo "[oracle_sweep] ERROR: insmod failed, restoring stock module" >&2
        insmod "${STOCK_KO}" || true
        exit 1
    fi
}

for entry in "${BENCHMARKS[@]}"; do
    IFS=':' read -r name binary size_str <<< "${entry}"
    size_label="${size_str// /_}"
    oracle_bin="${ORACLE_DIR}/${name}/${size_label}/oracle_trace.bin"

    if [[ ! -f "${oracle_bin}" ]]; then
        echo "[oracle_sweep] SKIP ${name}/${size_label}: no oracle trace (run collect_oracle_traces.sh first)"
        continue
    fi

    outdir="${RESULTS_DIR}/${name}/${size_label}"
    mkdir -p "${outdir}"

    # Reload module with this benchmark's oracle trace (trace is loaded at init only)
    echo "[p4_d0] Reloading module with oracle trace for ${name} ..."
    reload_module_with_trace "${oracle_bin}"

    echo ""
    echo "[p4_d0] ${name} size=${size_str}"

    # Warmup
    echo "  Warmup (${WARMUP_RUNS} run(s)) ..."
    for _ in $(seq 1 ${WARMUP_RUNS}); do
        # shellcheck disable=SC2086
        ${binary} ${size_str} > /dev/null 2>&1 || true
    done

    # Timed runs
    echo "  Timing (${NUM_STAT_RUNS} runs) ..."
    echo "Run_ID,Time_ms" > "${outdir}/timing_raw.csv"
    for run in $(seq 1 ${NUM_STAT_RUNS}); do
        t_start=$(date +%s%N)
        # shellcheck disable=SC2086
        ${binary} ${size_str} > /dev/null 2>&1 || true
        t_end=$(date +%s%N)
        ms=$(( (t_end - t_start) / 1000000 ))
        echo "${run},${ms}" >> "${outdir}/timing_raw.csv"
        printf "      ... run %d/%d (%d ms)\r" "${run}" "${NUM_STAT_RUNS}" "${ms}"
    done
    echo ""

    # Collect telemetry
    cp "${DEBUGFS}/specasync_log"        "${outdir}/raw_batch.bin" 2>/dev/null || true
    cp "${DEBUGFS}/specasync_worker_log" "${outdir}/raw_worker.bin" 2>/dev/null || true

    # Parse telemetry (batch_log is positional; worker via --work-log; CSVs land in --out-dir)
    if [[ -s "${outdir}/raw_batch.bin" ]]; then
        python3 "${PARSE}" "${outdir}/raw_batch.bin" \
            --work-log "${outdir}/raw_worker.bin" \
            --out-dir "${outdir}" 2>&1 || true
    fi

    echo "  Done → ${outdir}"
done

# Reload module without oracle trace, restore policy=1 for future experiments
rmmod nvidia_uvm 2>/dev/null || true
insmod "${PATCHED_KO}" specasync_policy=1 specasync_log_enabled=1 || \
    insmod "${STOCK_KO}" || true

echo ""
echo "=== Oracle sweep complete ==="
echo "Results: ${RESULTS_DIR}"
echo ""
echo "Next: run full analysis"
echo "  python3 ${TOOLS_DIR}/analyze_phaseB.py"
echo "  python3 ${TOOLS_DIR}/cost_benefit.py"
