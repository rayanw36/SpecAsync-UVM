#!/usr/bin/env bash
# t_b8_oversub_verify_depth0.sh -- Section 6 of
# results/analysis/OVERSUB_SPEEDUP_VERIFICATION.md: mechanism check for the
# C3-vs-C1 oversubscription finding confirmed in Section 5. Adds C3d0
# (oracle policy, depth=0 -- metadata-only, no real migration per Gate D's
# "architecturally incapable" claim) alongside C1 (reference, no benefit)
# and C3 (reference, depth=1, confirmed benefit) to test whether the benefit
# requires depth=1 or persists at depth=0. C0 intentionally excluded --
# not informative for this specific question, already answered in Section 5.
#
# Usage: bash tests/t_b8_oversub_verify_depth0.sh <N> [iters]
#        DRY_RUN=1 bash tests/t_b8_oversub_verify_depth0.sh <N>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_OVSUB="${1:?usage: t_b8_oversub_verify_depth0.sh <N> [iters]}"
ITERS="${2:-20}"

: "${KO:?KO must be set explicitly to the platform-correct .ko path -- see OVERSUB_SPEEDUP_VERIFICATION.md Errors note, the driver/build/ default in this repo is a stale AWS build}"
BENCH_OVSUB="$REPO/benchmarks/stencil_oversub/bench_stencil_oversub"

: "${OUT:=$REPO/results/analysis/t_b8_oversub_5070ti}"
CSV="$OUT/oversub_depth0_verify_times.csv"
TELEM_DIR="$OUT/telemetry_depth0_verify"

WARMUP_ROTATIONS=2
TARGET_ROTATIONS=10
TOTAL_ROTATIONS=$((WARMUP_ROTATIONS + TARGET_ROTATIONS))

declare -A POLICY=( [C1]=0 [C3]=4 [C3d0]=4 )
declare -A DEPTH=(  [C1]=0 [C3]=1 [C3d0]=0 )
declare -A PREFETCH=([C1]=0 [C3]=0 [C3d0]=0 )

mkdir -p "$OUT" "$TELEM_DIR"
csv_init "$CSV"

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
    local trace_file="$OUT/c3_${bench}_depth0verify_trace.bin"
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

    declare -A rep_count=( [C1]=0 [C3]=0 [C3d0]=0 )

    for rotation in $(seq 1 $TOTAL_ROTATIONS); do
        local phase="warmup"
        if [ "$rotation" -gt "$WARMUP_ROTATIONS" ]; then
            phase="kept"
        fi
        for cfg in C1 C3 C3d0; do
            local trace_arg=""
            [[ "$cfg" == C3* ]] && trace_arg="$trace_file"
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

harness_log "=== OVERSUB_SPEEDUP_VERIFICATION Section 6 (depth=0 mechanism check): Stencil_OvSub N=$N_OVSUB iters=$ITERS, interleaved C1,C3,C3d0 x $TOTAL_ROTATIONS rotations ==="
run_interleaved_session bench_stencil_oversub "$BENCH_OVSUB" "$N_OVSUB $ITERS" "$N_OVSUB"

harness_log "done. CSV: $CSV"
harness_log "kept reps/cell should be $TARGET_ROTATIONS; warm-up reps/cell = $WARMUP_ROTATIONS"
