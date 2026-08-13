#!/usr/bin/env bash
# t_b8_sgemm_interleaved.sh — Gate B8 Task 2: SGEMM C0-C3 interleaved on the
# 5070 Ti, matching T1's protocol exactly (results/analysis/GATE_T1_REPORT.md,
# tests/t1_gate3_interleaved.sh): rotation C0,C1,C2,C3 never blocked, 2
# warm-up + 20 kept rotations, module reload before every run, fresh oracle
# trace collected on this machine (not reused from the T4).
#
# Deliberately a new, separate script rather than parameterizing
# t1_gate3_interleaved.sh over a third benchmark -- same convention this
# project already uses (t2_cufft_interleaved.sh, t3_phasec_paired_wallclock.sh
# are each their own script), so T1's pre-registered harness stays untouched.
#
# Usage: bash tests/t_b8_sgemm_interleaved.sh [sgemm_N]
#        DRY_RUN=1 bash tests/t_b8_sgemm_interleaved.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_SGEMM="${1:-24000}"

: "${KO:=$REPO/driver/build/nvidia-uvm-specasync-t4.ko}"
BENCH_SGEMM="$REPO/benchmarks/bench_sgemm"

: "${OUT:=$REPO/results/analysis/t_b8_sgemm_5070ti}"
CSV="$OUT/sgemm_interleaved_times.csv"
TELEM_DIR="$OUT/telemetry"

WARMUP_ROTATIONS=2
TARGET_ROTATIONS=20
TOTAL_ROTATIONS=$((WARMUP_ROTATIONS + TARGET_ROTATIONS))

declare -A POLICY=( [C0]=0 [C1]=0 [C2]=2 [C3]=4 )
declare -A DEPTH=(  [C0]=0 [C1]=0 [C2]=1 [C3]=1 )
declare -A PREFETCH=([C0]=1 [C1]=0 [C2]=0 [C3]=0 )

mkdir -p "$OUT" "$TELEM_DIR"
csv_init "$CSV"

collect_oracle_trace() {
    local bench="$1" bin="$2" args="$3"
    local trace_file="$OUT/c3_${bench}_trace.bin"
    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] collect_oracle_trace bench=$bench -> $trace_file"
        echo "$trace_file"
        return
    fi
    reload_module "$KO" 0 0 0
    sudo -n rmmod nvidia_uvm 2>/dev/null || true
    sudo -n insmod "$KO" specasync_policy=0 specasync_offload_depth=0 \
        uvm_perf_prefetch_enable=0 specasync_trace_faults=1 specasync_log_enabled=0
    sleep 0.3
    setarch -R "$bin" $args >/dev/null
    sleep 0.2
    sudo -n cat "$DBGFS/specasync_fault_trace" > "$trace_file" 2>/dev/null || true
    local nent=$(( $(wc -c < "$trace_file" 2>/dev/null || echo 0) / 8 ))
    harness_log "oracle trace for $bench: $nent entries -> $trace_file"
    echo "$trace_file"
}

run_interleaved_session() {
    local bench="$1" bin="$2" args="$3" size="$4"
    local trace_file
    trace_file="$(collect_oracle_trace "$bench" "$bin" "$args")"

    declare -A rep_count=( [C0]=0 [C1]=0 [C2]=0 [C3]=0 )

    for rotation in $(seq 1 $TOTAL_ROTATIONS); do
        local phase="warmup"
        if [ "$rotation" -gt "$WARMUP_ROTATIONS" ]; then
            phase="kept"
        fi
        for cfg in C0 C1 C2 C3; do
            local trace_arg=""
            [ "$cfg" = "C3" ] && trace_arg="$trace_file"
            reload_module "$KO" "${POLICY[$cfg]}" "${DEPTH[$cfg]}" "${PREFETCH[$cfg]}" "$trace_arg"

            rep_count[$cfg]=$((rep_count[$cfg] + 1))
            local rep_label="${phase}_${rep_count[$cfg]}"
            time_run "$CSV" "$bin" "$args" "$cfg" "$bench" "$size" "$rep_label" "$phase"

            dump_ring "$DBGFS/specasync_log" "$TELEM_DIR/${bench}_${cfg}_run${RUN_ORDER_IDX}.bin"
            clear_ring
        done
    done
}

harness_log "=== Gate B8 Task 2: SGEMM@$N_SGEMM, interleaved C0,C1,C2,C3 x $TOTAL_ROTATIONS rotations ==="
run_interleaved_session bench_sgemm "$BENCH_SGEMM" "$N_SGEMM" "$N_SGEMM"

harness_log "done. CSV: $CSV"
harness_log "kept reps/cell should be $TARGET_ROTATIONS; warm-up reps/cell = $WARMUP_ROTATIONS"
