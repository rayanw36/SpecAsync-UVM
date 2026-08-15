#!/usr/bin/env bash
# t_b9_task2c_c0_and_counters.sh -- Gate B9 verification directive, Tasks A+B.
#
# TASK A: C3-vs-C1 (t_b9_task2b_iter_sweep.sh) is speculation-vs-crippled-
# baseline (C1 = prefetch OFF, not the stock system). C0 (prefetch ON,
# policy=0, depth=0) is the actual baseline the paper's claim is about. This
# adds C0 to the iteration sweep, three-way interleaved with C1 and C3 in the
# SAME run (not a separate, non-interleaved rerun) to avoid a between-session
# confound -- same N, same iters list, same protocol as t_b9_task2b's C1/C3.
#
# TASK B: t_b9_task2b logged no atomic counters. This reads all six
# (processed/enqueued/drops/demand_faults/spec_hits/spec_migrations) into the
# CSV immediately after each run finishes and BEFORE the next run's
# reload_module call resets them (every reload = full module reinit = every
# atomic back to 0) -- this is the only point at which a given run's counters
# are readable at all.
#
# C0 gets no oracle trace argument (irrelevant at policy=0, matches C1).
#
# Usage: bash tests/t_b9_task2c_c0_and_counters.sh <N> [iters_list]
#        DRY_RUN=1 bash tests/t_b9_task2c_c0_and_counters.sh <N>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_OVSUB="${1:?usage: t_b9_task2c_c0_and_counters.sh <N> [iters_list]}"
ITERS_LIST="${2:-1 3 5 10 20}"

: "${KO:?KO must be set explicitly to the platform-correct .ko path}"
BENCH_OVSUB="$REPO/benchmarks/stencil_oversub/bench_stencil_oversub"

: "${OUT:=$REPO/results/analysis/gate_b9_oversub_mechanism}"
CSV="$OUT/task2c_c0_threeway_times.csv"
TELEM_DIR="$OUT/telemetry_task2c_threeway"

WARMUP_ROTATIONS=1
TARGET_ROTATIONS=5
TOTAL_ROTATIONS=$((WARMUP_ROTATIONS + TARGET_ROTATIONS))

declare -A POLICY=( [C0]=0 [C1]=0 [C3]=4 )
declare -A DEPTH=(  [C0]=0 [C1]=0 [C3]=1 )
declare -A PREFETCH=([C0]=1 [C1]=0 [C3]=0 )

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
    local trace_file="$OUT/c3_bench_stencil_oversub_task2c_iters${iters}_trace.bin"
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

# read_atomics -- prints 6 comma-separated values: processed,enqueued,drops,
# demand_faults,spec_hits,spec_migrations. Called immediately after a run
# finishes, before the next reload wipes them.
read_atomics() {
    local p e d f h m
    p=$(sudo -n cat "$DBGFS/specasync_processed" 2>/dev/null || echo "")
    e=$(sudo -n cat "$DBGFS/specasync_enqueued" 2>/dev/null || echo "")
    d=$(sudo -n cat "$DBGFS/specasync_drops" 2>/dev/null || echo "")
    f=$(sudo -n cat "$DBGFS/specasync_demand_faults" 2>/dev/null || echo "")
    h=$(sudo -n cat "$DBGFS/specasync_spec_hits" 2>/dev/null || echo "")
    m=$(sudo -n cat "$DBGFS/specasync_spec_migrations" 2>/dev/null || echo "")
    echo "$p,$e,$d,$f,$h,$m"
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
        echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$iters,$rep,$phase,0,0,DRYRUN,0,0,0,,,,,," >> "$CSV"
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
        printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,,,,,,\n' \
            "$RUN_ORDER_IDX" "$ts" "$cfg" "bench_stencil_oversub" "$N_OVSUB" "$iters" "$rep" "$phase" \
            "" "" "$srcv" "" "$mem_before" "$wd_avail" >> "$CSV"
        exit 1
    fi
    set -e
    t1=$(date +%s.%N)

    # Read the atomics NOW, immediately after the run, before anything else
    # (including the next run_iter_case's reload_module call) can reset them.
    local atomics
    atomics="$(read_atomics)"

    wall=$(grep -oP '^[0-9]+\.[0-9]+$' "$wall_out" | tail -1)
    [ -z "$wall" ] && wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.2f", b-a}')
    local per_iter
    per_iter=$(awk -v w="$wall" -v i="$iters" 'BEGIN{printf "%.6f", w/i}')

    ddelta=$(dmesg_delta_count)
    mem_after=$(mem_available_kb)

    harness_log "run_order=$RUN_ORDER_IDX cfg=$cfg iters=$iters rep=$rep wall=${wall}s per_iter=${per_iter}s exit=$exit_code atomics=[$atomics] dmesg_delta=$ddelta mem_avail=${mem_after}kB"

    echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$iters,$rep,$phase,$wall,$per_iter,$srcv,$ddelta,$mem_before,$mem_after,$atomics" >> "$CSV"

    check_memory_or_abort
}

echo "run_order_idx,timestamp_iso8601,config,bench,size,iters,rep_in_cell,phase,wall_s,per_iter_s,srcversion,dmesg_delta,mem_avail_before_kb,mem_avail_after_kb,atomic_processed,atomic_enqueued,atomic_drops,atomic_demand_faults,atomic_spec_hits,atomic_spec_migrations" > "$CSV"

harness_log "=== Gate B9 Task 2c: C0 vs C1 vs C3, N=$N_OVSUB, iters in [$ITERS_LIST], n=$TARGET_ROTATIONS/arm/iters-value, interleaved C0,C1,C3, per-run atomics ==="

for iters in $ITERS_LIST; do
    trace_file="$(collect_oracle_trace "$BENCH_OVSUB" "$iters")"
    declare -A rep_count=( [C0]=0 [C1]=0 [C3]=0 )
    for rotation in $(seq 1 $TOTAL_ROTATIONS); do
        phase="warmup"
        if [ "$rotation" -gt "$WARMUP_ROTATIONS" ]; then
            phase="kept"
        fi
        for cfg in C0 C1 C3; do
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
