#!/usr/bin/env bash
# t_b9_task2b_iter_sweep.sh -- Gate B9 Task 2b: iteration sweep.
#
# C1 vs C3, N=48000 (~1.08x oversubscription), n=5/arm strictly interleaved
# WITHIN each iters value, for iters in {1,3,5,10,20} (default; overridable).
# Plain wall-clock only -- no debugfs rings involved, so this is entirely
# unaffected by the ring-saturation/clear-race problems currently blocking
# the rest of Task 2 (see ARTIFACT_CATALOG.md's "Second occurrence of
# artifact #7" note).
#
# Motivation (from t_b9_task1c_iters_control.sh's control result): the C3-
# vs-C1 wall-clock advantage was -28.49% at iters=3 and -56.52% at iters=20
# (OVERSUB_SPEEDUP_VERIFICATION.md Section 5) -- the benefit GROWS with
# iteration count. A cold-population effect would be roughly constant per
# run and shrink as a fraction of total runtime at higher iters; growth in
# the opposite direction is evidence for a cumulative/steady-state
# mechanism (eviction-ordering, not initial placement). This sweep tests
# that directly: is the benefit present at iters=1 (pure cold population,
# no steady state possible), and does it scale monotonically?
#
# A fresh oracle trace is collected for EACH iters value (the demand-fault
# address sequence a C3 replay depends on is itself a function of N AND
# iters, not just N).
#
# Usage: bash tests/t_b9_task2b_iter_sweep.sh <N> [iters_list]
#        DRY_RUN=1 bash tests/t_b9_task2b_iter_sweep.sh <N>
#   iters_list: space-separated, quoted, e.g. "1 3 5 10 20" (default)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_OVSUB="${1:?usage: t_b9_task2b_iter_sweep.sh <N> [iters_list]}"
ITERS_LIST="${2:-1 3 5 10 20}"

: "${KO:?KO must be set explicitly to the platform-correct .ko path}"
BENCH_OVSUB="$REPO/benchmarks/stencil_oversub/bench_stencil_oversub"

: "${OUT:=$REPO/results/analysis/gate_b9_oversub_mechanism}"
CSV="$OUT/task2b_iter_sweep_times.csv"
TELEM_DIR="$OUT/telemetry_task2b_iter_sweep"

WARMUP_ROTATIONS=1
TARGET_ROTATIONS=5
TOTAL_ROTATIONS=$((WARMUP_ROTATIONS + TARGET_ROTATIONS))

declare -A POLICY=( [C1]=0 [C3]=4 )
declare -A DEPTH=(  [C1]=0 [C3]=1 )
declare -A PREFETCH=([C1]=0 [C3]=0 )

mkdir -p "$OUT" "$TELEM_DIR"

: "${ABORT_MIN_AVAIL_KB:=6291456}"  # 6 GiB
check_memory_or_abort() {
    if [ "$DRY_RUN" = "1" ]; then
        return
    fi
    local avail
    avail=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    if [ "$avail" -lt "$ABORT_MIN_AVAIL_KB" ]; then
        harness_log "ABORT: MemAvailable=${avail}kB < ${ABORT_MIN_AVAIL_KB}kB at run_order=$RUN_ORDER_IDX -- stopping"
        exit 1
    fi
}

collect_oracle_trace() {
    local bin="$1" iters="$2"
    local trace_file="$OUT/c3_bench_stencil_oversub_task2b_iters${iters}_trace.bin"
    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] collect_oracle_trace iters=$iters -> $trace_file"
        echo "$trace_file"
        return
    fi
    reload_module "$KO" 0 0 0
    sudo -n rmmod nvidia_uvm 2>/dev/null || true
    sudo -n insmod "$KO" specasync_policy=0 specasync_offload_depth=0 \
        uvm_perf_prefetch_enable=0 specasync_trace_faults=1 specasync_log_enabled=0
    sleep 0.3
    verify_module_reload 0 0
    harness_log "collecting oracle trace (iters=$iters) -- oversubscribed, may take a while"
    setarch -R "$bin" "$N_OVSUB" "$iters" >/dev/null
    sleep 0.2
    sudo -n cat "$DBGFS/specasync_fault_trace" > "$trace_file" 2>/dev/null || true
    local nent=$(( $(wc -c < "$trace_file" 2>/dev/null || echo 0) / 8 ))
    harness_log "oracle trace for iters=$iters: $nent entries -> $trace_file"
    echo "$trace_file"
}

# run_iter_case <cfg> <trace_arg> <iters> <rep_label> <phase>
run_iter_case() {
    local cfg="$1" trace_arg="$2" iters="$3" rep="$4" phase="$5"
    RUN_ORDER_IDX=$((RUN_ORDER_IDX + 1))
    local ts srcv mem_before mem_after ddelta

    reload_module "$KO" "${POLICY[$cfg]}" "${DEPTH[$cfg]}" "${PREFETCH[$cfg]}" "$trace_arg"
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    srcv=$(current_srcversion)
    mem_before=$(mem_available_kb)
    dmesg_mark

    local prefix="${cfg}_iters${iters}_run${RUN_ORDER_IDX}"
    local marker="$TELEM_DIR/watchdog_${prefix}.marker"
    local wall_out="$TELEM_DIR/wall_${prefix}.txt"

    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] run_iter_case cfg=$cfg iters=$iters rep=$rep phase=$phase"
        echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$iters,$rep,$phase,0,0,DRYRUN,0,0,0" >> "$CSV"
        return
    fi

    local t0 t1 wall exit_code
    t0=$(date +%s.%N)
    set +e
    run_with_memory_watchdog 6291456 "$marker" -- \
        /usr/bin/time -f "%e" setarch -R "$BENCH_OVSUB" "$N_OVSUB" "$iters" \
        > /dev/null 2>"$wall_out"
    exit_code=$?

    if [ "$exit_code" = 137 ]; then
        local wd_floor="" wd_avail="" wd_pgid=""
        mem_watchdog_read_marker "$marker" wd_floor wd_avail wd_pgid
        harness_log_nofork "WATCHDOG FIRED run_order=$RUN_ORDER_IDX cfg=$cfg iters=$iters floor_kb=$wd_floor avail_kb=$wd_avail pgid=$wd_pgid"
        harness_log_nofork "ABORT: per standing directive, stop rather than retry at a lower setting -- report and stop"
        printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
            "$RUN_ORDER_IDX" "$ts" "$cfg" "bench_stencil_oversub" "$N_OVSUB" "$iters" "$rep" "$phase" \
            "" "" "$srcv" "" "$mem_before" "$wd_avail" >> "$CSV"
        exit 1
    fi
    set -e
    t1=$(date +%s.%N)

    wall=$(grep -oP '^[0-9]+\.[0-9]+$' "$wall_out" | tail -1)
    [ -z "$wall" ] && wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.2f", b-a}')
    local per_iter
    per_iter=$(awk -v w="$wall" -v i="$iters" 'BEGIN{printf "%.6f", w/i}')

    ddelta=$(dmesg_delta_count)
    mem_after=$(mem_available_kb)

    harness_log "run_order=$RUN_ORDER_IDX cfg=$cfg iters=$iters rep=$rep wall=${wall}s per_iter=${per_iter}s exit=$exit_code dmesg_delta=$ddelta mem_avail=${mem_after}kB"

    echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$iters,$rep,$phase,$wall,$per_iter,$srcv,$ddelta,$mem_before,$mem_after" >> "$CSV"

    check_memory_or_abort
}

echo "run_order_idx,timestamp_iso8601,config,bench,size,iters,rep_in_cell,phase,wall_s,per_iter_s,srcversion,dmesg_delta,mem_avail_before_kb,mem_avail_after_kb" > "$CSV"

harness_log "=== Gate B9 Task 2b: iteration sweep, N=$N_OVSUB, iters in [$ITERS_LIST], n=$TARGET_ROTATIONS/arm/iters-value, interleaved C1,C3 ==="

for iters in $ITERS_LIST; do
    trace_file="$(collect_oracle_trace "$BENCH_OVSUB" "$iters")"
    declare -A rep_count=( [C1]=0 [C3]=0 )
    for rotation in $(seq 1 $TOTAL_ROTATIONS); do
        phase="warmup"
        if [ "$rotation" -gt "$WARMUP_ROTATIONS" ]; then
            phase="kept"
        fi
        for cfg in C1 C3; do
            trace_arg=""
            [ "$cfg" = "C3" ] && trace_arg="$trace_file"
            rep_count[$cfg]=$((rep_count[$cfg] + 1))
            rep_label="${phase}_${rep_count[$cfg]}"
            run_iter_case "$cfg" "$trace_arg" "$iters" "$rep_label" "$phase"
        done
    done
done

harness_log "done. CSV: $CSV"
harness_log "kept reps/cell should be $TARGET_ROTATIONS; warm-up reps/cell = $WARMUP_ROTATIONS, per iters value"
