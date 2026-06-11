#!/usr/bin/env bash
# oracle_sweep.sh — Run policy=4 (oracle) experiments after collect_oracle_traces.sh.
#
# Sets specasync_oracle_trace_path for each benchmark and runs 20-run timing sweeps.
# Results go to ~/SpecAsync-UVM/results/p4_d0/{bench}/{size}/
#
# Must be run as root.

set -euo pipefail

BENCH_DIR="$(cd "$(dirname "$0")/../benchmarks" && pwd)"
ORACLE_DIR="${HOME}/SpecAsync-UVM/oracles"
RESULTS_DIR="${HOME}/SpecAsync-UVM/results/p4_d0"
DEBUGFS="/sys/kernel/debug"
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

echo "[oracle_sweep] Setting policy=4 ..."
echo 1 | sudo tee /sys/module/nvidia_uvm/parameters/specasync_log_enabled > /dev/null
echo 4 | sudo tee /sys/module/nvidia_uvm/parameters/specasync_policy > /dev/null
echo 0 | sudo tee /sys/module/nvidia_uvm/parameters/specasync_trace_faults > /dev/null

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

    # Point module to oracle trace for this benchmark
    echo "${oracle_bin}" | sudo tee /sys/module/nvidia_uvm/parameters/specasync_oracle_trace_path > /dev/null

    echo ""
    echo "[p4_d0] ${name} size=${size_str}"

    # Clear ring buffers
    echo 1 > "${DEBUGFS}/specasync_clear"

    # Warmup
    echo "  Warmup (${WARMUP_RUNS} run(s)) ..."
    for _ in $(seq 1 ${WARMUP_RUNS}); do
        # shellcheck disable=SC2086
        ${binary} ${size_str} > /dev/null 2>&1 || true
    done
    echo 1 > "${DEBUGFS}/specasync_clear"

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

    # Parse telemetry
    if [[ -s "${outdir}/raw_batch.bin" ]]; then
        python3 "${PARSE}" batch "${outdir}/raw_batch.bin" \
            --out "${outdir}/batch_records.csv" 2>&1 || true
    fi
    if [[ -s "${outdir}/raw_worker.bin" ]]; then
        python3 "${PARSE}" work "${outdir}/raw_worker.bin" \
            --out "${outdir}/work_records.csv" 2>&1 || true
    fi

    echo 1 > "${DEBUGFS}/specasync_clear"
    echo "  Done → ${outdir}"
done

# Restore policy=1 (adjacent) for future experiments
echo 1 | sudo tee /sys/module/nvidia_uvm/parameters/specasync_policy > /dev/null

echo ""
echo "=== Oracle sweep complete ==="
echo "Results: ${RESULTS_DIR}"
echo ""
echo "Next: run full analysis"
echo "  python3 ${TOOLS_DIR}/analyze_phaseB.py"
echo "  python3 ${TOOLS_DIR}/cost_benefit.py"
