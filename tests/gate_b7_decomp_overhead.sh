#!/usr/bin/env bash
# gate_b7_decomp_overhead.sh — Gate B7 Task 1: DECOMP=0 vs DECOMP=1 instrumentation
# overhead, kernel-loop-time convention (bench_stencil's own "[RESULT] Time:"
# line -- matches PHASEC_REPORT.md's inferred Gate G3 convention, per
# STENCIL_LABEL_COLLISION.md; NOT lib_specasync_harness.sh's process-wall-clock
# wrapper, which would dilute the same fixed per-batch overhead against a much
# larger denominator (~4.2s vs ~1.6-2.6s) and produce a non-comparable %).
#
# Strictly interleaved DECOMP0/DECOMP1 (standing policy: strict interleaving
# wherever a comparison is involved -- this compares two builds, so unlike the
# rest of Phase C, EVERY run here needs a reload, since the two arms are two
# different .ko files, not a config parameter switch).
#
# Usage: bash tests/gate_b7_decomp_overhead.sh <decomp0.ko> <decomp1.ko> [n_per_arm] [N]
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_STENCIL="$REPO/benchmarks/bench_stencil"

KO0="$1"
KO1="$2"
N_PER_ARM="${3:-10}"
STENCIL_N="${4:-24000}"

OUT="$REPO/results/phaseC/decomp_overhead_5070ti"
CSV="$OUT/overhead_times_interleaved.csv"
mkdir -p "$OUT"
echo "run_order,build,trial,time_ms,mem_avail_before_kb,mem_avail_after_kb" > "$CSV"

log() { echo "[gate_b7_overhead $(date '+%H:%M:%S')] $*" >&2; }

mem_avail_kb() { awk '/^MemAvailable:/ {print $2}' /proc/meminfo; }

reload() {
    local ko="$1"
    sudo -n rmmod nvidia_uvm 2>/dev/null || true
    sudo -n insmod "$ko" specasync_log_enabled=1 specasync_policy=0 specasync_offload_depth=0 uvm_perf_prefetch_enable=1
    sleep 0.5
}

run_order=0
run_one() {
    local label="$1" ko="$2" trial="$3"
    run_order=$((run_order + 1))
    reload "$ko"
    local mb ma out ms
    mb=$(mem_avail_kb)
    out=$("$BENCH_STENCIL" "$STENCIL_N")
    ma=$(mem_avail_kb)
    ms=$(echo "$out" | grep -oP '\[RESULT\] Time:\s+\K[0-9.]+')
    log "run_order=$run_order $label trial=$trial time_ms=$ms mem_avail_after=${ma}kB"
    echo "$run_order,$label,$trial,$ms,$mb,$ma" >> "$CSV"
}

for t in $(seq 1 "$N_PER_ARM"); do
    run_one "DECOMP0" "$KO0" "$t"
    run_one "DECOMP1" "$KO1" "$t"
done

log "done. CSV: $CSV"
