#!/usr/bin/env bash
# collect_oracle_traces.sh — Run each benchmark with specasync_trace_faults=1
# to capture demand-fault VA sequences, then write oracle trace binaries.
#
# Requires: SpecAsync-UVM module loaded with oracle trace support (rebuild_and_reload.sh).
# Must be run as root (for /sys/module writes).
#
# Output: ~/SpecAsync-UVM/oracles/{bench}/{size}/oracle_trace.bin
#
# After this runs, use the oracle traces with policy=4 via run_all_experiments.sh
# or the oracle_sweep.sh below.

set -euo pipefail

BENCH_DIR="$(cd "$(dirname "$0")/../benchmarks" && pwd)"
ORACLE_DIR="${HOME}/SpecAsync-UVM/oracles"
DEBUGFS="/sys/kernel/debug"
TOOLS_DIR="${BENCH_DIR}/tools"

BENCHMARKS=(
    "SGEMM:${BENCH_DIR}/bench_sgemm:24000"
    "Stencil:${BENCH_DIR}/bench_stencil:24000"
    "STREAM:${BENCH_DIR}/bench_stream:268435456"
    "GraphBFS:${BENCH_DIR}/graph_bfs/bench_graph_bfs:23"
    "cuFFT:${BENCH_DIR}/bench_cufft:268435456"
    "Stencil_OvSub:${BENCH_DIR}/stencil_oversub/bench_stencil_oversub:28300 20 11264"
)

echo "[oracle] Setting up module parameters ..."
echo 1 | sudo tee /sys/module/nvidia_uvm/parameters/specasync_log_enabled > /dev/null
echo 1 | sudo tee /sys/module/nvidia_uvm/parameters/specasync_policy > /dev/null       # adjacent
echo 1 | sudo tee /sys/module/nvidia_uvm/parameters/specasync_trace_faults > /dev/null

for entry in "${BENCHMARKS[@]}"; do
    IFS=':' read -r name binary size_str <<< "${entry}"
    size_label="${size_str// /_}"
    outdir="${ORACLE_DIR}/${name}/${size_label}"
    mkdir -p "${outdir}"

    echo ""
    echo "[oracle] ${name} size=${size_str}"

    # Clear ring buffers
    echo 1 > "${DEBUGFS}/specasync_clear"

    # Run benchmark once to collect fault trace
    echo "  Collecting fault trace (1 warm run) ..."
    # shellcheck disable=SC2086
    ${binary} ${size_str} > /dev/null 2>&1 || true

    # Read the fault trace from debugfs
    echo "  Reading trace ring from debugfs ..."
    cp "${DEBUGFS}/specasync_fault_trace" "${outdir}/raw_fault_trace.bin"
    wc -c "${outdir}/raw_fault_trace.bin"

    n_addrs=$(( $(wc -c < "${outdir}/raw_fault_trace.bin") / 8 ))
    echo "  ${n_addrs} fault addresses captured"

    if (( n_addrs == 0 )); then
        echo "  WARN: no fault addresses for ${name}/${size_label} — skipping"
        continue
    fi

    # Copy the raw trace as the oracle input (already in packed u64 LE format)
    cp "${outdir}/raw_fault_trace.bin" "${outdir}/oracle_trace.bin"
    echo "  Written: ${outdir}/oracle_trace.bin"

    echo "  Clearing ring for next benchmark ..."
    echo 1 > "${DEBUGFS}/specasync_clear"
done

# Disable trace recording to avoid overhead in subsequent runs
echo 0 | sudo tee /sys/module/nvidia_uvm/parameters/specasync_trace_faults > /dev/null

echo ""
echo "=== Oracle traces collected ==="
find "${ORACLE_DIR}" -name oracle_trace.bin | sort
echo ""
echo "Next: run oracle sweep with policy=4"
echo "  sudo bash scripts/oracle_sweep.sh"
