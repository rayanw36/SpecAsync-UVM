#!/usr/bin/env bash
# t_b10c_replication_crossover.sh -- Gate B10 Task C+D: replicate B10's
# iters=20 result and fill iters={8,12,16} to characterize the crossover.
#
# TASK C: iters=20 is B10's entire positive-claim point (-36.03%, C4 faster
# than C0). This reruns it fresh (new reboot, new interleaving order) as an
# independent reproduction attempt, not a confirmatory rerun under identical
# conditions.
#
# TASK D: iters in {8,12,16} fill the gap between B10's iters=5 (+30.91%, C4
# slower) and iters=20 (-36.03%, C4 faster) to see whether the sign flip is
# a smooth crossing or a jump. See GATE_B10_REPLICATION_PREREGISTRATION.md
# for the pre-declared family/MDE/falsification trigger, committed before
# this script was ever run.
#
# NEW INTERLEAVING SEED: B10's harness (t_b10_c0_vs_c4.sh) always ran C0
# then C4 within every rotation -- alternating, but not order-randomized.
# This script draws the within-rotation order from a seeded PRNG (bash
# RANDOM, reseeded from RANDOM_SEED at script start) and logs the realized
# order to the CSV's `order` column, so the randomization is both real and
# auditable after the fact.
#
# Usage: bash tests/t_b10c_replication_crossover.sh <N> [iters_list]
#        DRY_RUN=1 bash tests/t_b10c_replication_crossover.sh <N>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_OVSUB="${1:?usage: t_b10c_replication_crossover.sh <N> [iters_list]}"
ITERS_LIST="${2:-8 12 16 20}"

: "${KO:?KO must be set explicitly to the platform-correct .ko path}"
BENCH_OVSUB="$REPO/benchmarks/stencil_oversub/bench_stencil_oversub"

: "${OUT:=$REPO/results/analysis/gate_b10_replication}"
CSV="$OUT/t_b10c_replication_crossover_times.csv"
TELEM_DIR="$OUT/telemetry_b10c"

RANDOM_SEED="${RANDOM_SEED:-20260816}"
RANDOM=$RANDOM_SEED

WARMUP_ROTATIONS=1
TARGET_ROTATIONS=10
TOTAL_ROTATIONS=$((WARMUP_ROTATIONS + TARGET_ROTATIONS))

declare -A POLICY=(   [C0]=0 [C4]=4 )
declare -A DEPTH=(     [C0]=0 [C4]=1 )
declare -A PREFETCH=(  [C0]=1 [C4]=1 )

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
    local trace_file="$OUT/c4_bench_stencil_oversub_task_b10c_iters${iters}_trace.bin"
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

# run_iter_case <cfg> <trace_arg> <iters> <rep_label> <phase> <order_in_rotation>
run_iter_case() {
    local cfg="$1" trace_arg="$2" iters="$3" rep="$4" phase="$5" order="$6"
    RUN_ORDER_IDX=$((RUN_ORDER_IDX + 1))
    local ts srcv mem_before mem_after ddelta

    reload_module "$KO" "${POLICY[$cfg]}" "${DEPTH[$cfg]}" "${PREFETCH[$cfg]}" "$trace_arg"
    clear_ring
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    srcv=$(current_srcversion)
    mem_before=$(mem_available_kb)
    dmesg_mark

    local prefix="${cfg}_iters${iters}_run${RUN_ORDER_IDX}"
    local marker="$TELEM_DIR/watchdog_${prefix}.marker"
    local wall_out="$TELEM_DIR/wall_${prefix}.txt"

    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] run_iter_case cfg=$cfg iters=$iters rep=$rep phase=$phase order=$order"
        echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$iters,$rep,$phase,$order,0,0,DRYRUN,0,0,0,,,,,," >> "$CSV"
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
        printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,,,,,,\n' \
            "$RUN_ORDER_IDX" "$ts" "$cfg" "bench_stencil_oversub" "$N_OVSUB" "$iters" "$rep" "$phase" "$order" \
            "" "" "$srcv" "" "$mem_before" "$wd_avail" >> "$CSV"
        exit 1
    fi
    set -e
    t1=$(date +%s.%N)

    local atomics
    atomics="$(read_atomics)"

    wall=$(grep -oP '^[0-9]+\.[0-9]+$' "$wall_out" | tail -1)
    [ -z "$wall" ] && wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.2f", b-a}')
    local per_iter
    per_iter=$(awk -v w="$wall" -v i="$iters" 'BEGIN{printf "%.6f", w/i}')

    ddelta=$(dmesg_delta_count)
    mem_after=$(mem_available_kb)

    harness_log "run_order=$RUN_ORDER_IDX cfg=$cfg iters=$iters rep=$rep order=$order wall=${wall}s per_iter=${per_iter}s exit=$exit_code atomics=[$atomics] dmesg_delta=$ddelta mem_avail=${mem_after}kB"

    echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$iters,$rep,$phase,$order,$wall,$per_iter,$srcv,$ddelta,$mem_before,$mem_after,$atomics" >> "$CSV"

    check_memory_or_abort
}

echo "run_order_idx,timestamp_iso8601,config,bench,size,iters,rep_in_cell,phase,order_in_rotation,wall_s,per_iter_s,srcversion,dmesg_delta,mem_avail_before_kb,mem_avail_after_kb,atomic_processed,atomic_enqueued,atomic_drops,atomic_demand_faults,atomic_spec_hits,atomic_spec_migrations" > "$CSV"

harness_log "=== Gate B10 Task C+D: replication (iters=20) + crossover fill (iters=8,12,16), N=$N_OVSUB, iters in [$ITERS_LIST], n=$TARGET_ROTATIONS/arm/iters-value, RANDOM_SEED=$RANDOM_SEED ==="

for iters in $ITERS_LIST; do
    trace_file="$(collect_oracle_trace "$BENCH_OVSUB" "$iters")"
    declare -A rep_count=( [C0]=0 [C4]=0 )
    for rotation in $(seq 1 $TOTAL_ROTATIONS); do
        phase="warmup"
        if [ "$rotation" -gt "$WARMUP_ROTATIONS" ]; then
            phase="kept"
        fi
        # Seeded random order for this rotation: C0-first or C4-first.
        if (( RANDOM % 2 == 0 )); then
            order_cfgs=(C0 C4)
            order_label="C0first"
        else
            order_cfgs=(C4 C0)
            order_label="C4first"
        fi
        for cfg in "${order_cfgs[@]}"; do
            trace_arg=""
            [ "$cfg" = "C4" ] && trace_arg="$trace_file"
            rep_count[$cfg]=$((rep_count[$cfg] + 1))
            rep_label="${phase}_${rep_count[$cfg]}"
            run_iter_case "$cfg" "$trace_arg" "$iters" "$rep_label" "$phase" "$order_label"
        done
    done
done

harness_log "done. CSV: $CSV"
harness_log "kept reps/cell should be $TARGET_ROTATIONS; warm-up reps/cell = $WARMUP_ROTATIONS, per iters value"
