#!/usr/bin/env bash
# t_b8_oversub_verify_n10.sh — pre-registered n=10 re-run of the Gate B8
# Task 3 oversubscription finding (results/analysis/OVERSUB_SPEEDUP_VERIFICATION.md
# Section 5): C3 (oracle, depth=1) beat C1 (no speculation) by -55.77% wall-clock
# at n=3 despite a 0.0019% oracle hit rate. C2 is intentionally excluded here --
# the brief's re-run instruction names only C0/C1/C3. Same target as Task 3
# (N=48000, ~18.43GB working set, ~1.08x this platform's VRAM), same
# check_memory_or_abort guard, but 2 warm-up + 10 kept rotations (n=10/arm)
# instead of 1+3, and a strict C0,C1,C3 rotation instead of C0,C1,C2,C3.
#
# Usage: bash tests/t_b8_oversub_verify_n10.sh <N> [iters]
#        DRY_RUN=1 bash tests/t_b8_oversub_verify_n10.sh <N>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_OVSUB="${1:?usage: t_b8_oversub_verify_n10.sh <N> [iters]}"
ITERS="${2:-20}"

: "${KO:=$REPO/driver/build/nvidia-uvm-specasync-t4.ko}"
BENCH_OVSUB="$REPO/benchmarks/stencil_oversub/bench_stencil_oversub"

: "${OUT:=$REPO/results/analysis/t_b8_oversub_5070ti}"
CSV="$OUT/oversub_n10_verify_times.csv"
TELEM_DIR="$OUT/telemetry_n10_verify"

WARMUP_ROTATIONS=2
TARGET_ROTATIONS=10
TOTAL_ROTATIONS=$((WARMUP_ROTATIONS + TARGET_ROTATIONS))

declare -A POLICY=( [C0]=0 [C1]=0 [C3]=4 )
declare -A DEPTH=(  [C0]=0 [C1]=0 [C3]=1 )
declare -A PREFETCH=([C0]=1 [C1]=0 [C3]=0 )

mkdir -p "$OUT" "$TELEM_DIR"
csv_init "$CSV"

# Abort guard (HOST_MEMORY_LEAK_5070TI.md), same convention as Task 3's
# harness and t2_cufft_interleaved.sh.
: "${ABORT_MIN_AVAIL_KB:=6291456}"  # 6 GiB
check_memory_or_abort() {
    if [ "$DRY_RUN" = "1" ]; then
        return
    fi
    local avail
    avail=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    if [ "$avail" -lt "$ABORT_MIN_AVAIL_KB" ]; then
        harness_log "ABORT: MemAvailable=${avail}kB < ${ABORT_MIN_AVAIL_KB}kB at run_order=$RUN_ORDER_IDX -- stopping, oversubscribed runs risk host OOM"
        exit 1
    fi
}

collect_oracle_trace() {
    local bench="$1" bin="$2" args="$3"
    local trace_file="$OUT/c3_${bench}_n10verify_trace.bin"
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
    harness_log "collecting oracle trace ($bench $args) -- oversubscribed, may take a while"
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

    declare -A rep_count=( [C0]=0 [C1]=0 [C3]=0 )

    for rotation in $(seq 1 $TOTAL_ROTATIONS); do
        local phase="warmup"
        if [ "$rotation" -gt "$WARMUP_ROTATIONS" ]; then
            phase="kept"
        fi
        for cfg in C0 C1 C3; do
            local trace_arg=""
            [ "$cfg" = "C3" ] && trace_arg="$trace_file"
            reload_module "$KO" "${POLICY[$cfg]}" "${DEPTH[$cfg]}" "${PREFETCH[$cfg]}" "$trace_arg"

            rep_count[$cfg]=$((rep_count[$cfg] + 1))
            local rep_label="${phase}_${rep_count[$cfg]}"
            harness_log "starting rotation=$rotation cfg=$cfg ($phase) -- oversubscribed run, may be slow"
            time_run "$CSV" "$bin" "$args" "$cfg" "$bench" "$size" "$rep_label" "$phase"

            dump_ring "$DBGFS/specasync_log" "$TELEM_DIR/${bench}_${cfg}_run${RUN_ORDER_IDX}.bin"
            clear_ring
            check_memory_or_abort
        done
    done
}

harness_log "=== OVERSUB_SPEEDUP_VERIFICATION n=10 re-run: Stencil_OvSub N=$N_OVSUB iters=$ITERS, interleaved C0,C1,C3 x $TOTAL_ROTATIONS rotations ==="
run_interleaved_session bench_stencil_oversub "$BENCH_OVSUB" "$N_OVSUB $ITERS" "$N_OVSUB"

harness_log "done. CSV: $CSV"
harness_log "kept reps/cell should be $TARGET_ROTATIONS; warm-up reps/cell = $WARMUP_ROTATIONS"
