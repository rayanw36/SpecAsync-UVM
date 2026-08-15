#!/usr/bin/env bash
# t_b9_task1c_iters_control.sh -- Gate B9 Task 1(c) prerequisite control.
#
# Before trusting any nsys H2D/D2H byte numbers taken at a reduced iters
# count (full iters=20 nsys tracing OOM-killed the host -- see
# GATE_B9_OVERSUB_MECHANISM.md Task 1 incident writeup), confirm the C3-vs-C1
# wall-clock advantage still appears at that reduced iters count. If it
# doesn't, the reduced-iters config is not a valid stand-in for the effect
# under study and no nsys measurement taken there would be interpretable --
# report that as a finding in its own right (steady-state vs cold-population
# distinction) and do not proceed to nsys at reduced iters.
#
# Plain wall-clock only (original, unmodified bench_stencil_oversub binary --
# no checksum, no nsys). n=5/arm, strictly interleaved C1,C3, N=48000 (same
# ~1.08x target as everywhere else in this gate). Routes through the new
# run_with_memory_watchdog (6 GiB floor) as a standing safety measure, in
# addition to the existing between-runs check_memory_or_abort.
#
# Usage: bash tests/t_b9_task1c_iters_control.sh <N> <iters>
#        DRY_RUN=1 bash tests/t_b9_task1c_iters_control.sh <N> <iters>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_OVSUB="${1:?usage: t_b9_task1c_iters_control.sh <N> <iters>}"
ITERS="${2:?usage: t_b9_task1c_iters_control.sh <N> <iters>}"

: "${KO:?KO must be set explicitly to the platform-correct .ko path}"
BENCH_OVSUB="$REPO/benchmarks/stencil_oversub/bench_stencil_oversub"

: "${OUT:=$REPO/results/analysis/gate_b9_oversub_mechanism}"
CSV="$OUT/task1c_iters${ITERS}_control_times.csv"
TELEM_DIR="$OUT/telemetry_task1c_iters${ITERS}_control"

WARMUP_ROTATIONS=1
TARGET_ROTATIONS=5
TOTAL_ROTATIONS=$((WARMUP_ROTATIONS + TARGET_ROTATIONS))

declare -A POLICY=( [C1]=0 [C3]=4 )
declare -A DEPTH=(  [C1]=0 [C3]=1 )
declare -A PREFETCH=([C1]=0 [C3]=0 )

mkdir -p "$OUT" "$TELEM_DIR"

: "${ABORT_MIN_AVAIL_KB:=6291456}"  # 6 GiB, matches watchdog floor below
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
    local bench="$1" bin="$2" args="$3"
    local trace_file="$OUT/c3_${bench}_task1c_iters${ITERS}_trace.bin"
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

run_watched() {
    local cfg="$1" trace_arg="$2" rep="$3" phase="$4"
    RUN_ORDER_IDX=$((RUN_ORDER_IDX + 1))
    local ts srcv mem_before mem_after ddelta

    reload_module "$KO" "${POLICY[$cfg]}" "${DEPTH[$cfg]}" "${PREFETCH[$cfg]}" "$trace_arg"
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    srcv=$(current_srcversion)
    mem_before=$(mem_available_kb)
    dmesg_mark

    local marker="$TELEM_DIR/watchdog_${cfg}_run${RUN_ORDER_IDX}.marker"
    local wall wall_out="$TELEM_DIR/wall_${cfg}_run${RUN_ORDER_IDX}.txt"

    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] run_watched cfg=$cfg rep=$rep phase=$phase"
        echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$rep,$phase,0,DRYRUN,0,0,0" >> "$CSV"
        return
    fi

    local t0 t1 rc
    t0=$(date +%s.%N)
    set +e
    run_with_memory_watchdog 6291456 "$marker" -- \
        /usr/bin/time -f "%e" setarch -R "$BENCH_OVSUB" "$N_OVSUB" "$ITERS" \
        > /dev/null 2>"$wall_out"
    rc=$?
    if [ "$rc" = 137 ]; then
        local wd_floor="" wd_avail="" wd_pgid=""
        mem_watchdog_read_marker "$marker" wd_floor wd_avail wd_pgid
        harness_log_nofork "WATCHDOG FIRED run_order=$RUN_ORDER_IDX cfg=$cfg floor_kb=$wd_floor avail_kb=$wd_avail pgid=$wd_pgid"
    fi
    set -e
    t1=$(date +%s.%N)
    wall=$(grep -oP '^[0-9]+\.[0-9]+$' "$wall_out" | tail -1)
    [ -z "$wall" ] && wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.2f", b-a}')

    ddelta=$(dmesg_delta_count)
    mem_after=$(mem_available_kb)

    harness_log "run_order=$RUN_ORDER_IDX cfg=$cfg rep=$rep wall=${wall}s exit=$rc dmesg_delta=$ddelta mem_avail=${mem_after}kB"

    echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$rep,$phase,$wall,$srcv,$ddelta,$mem_before,$mem_after" >> "$CSV"

    check_memory_or_abort
}

echo "run_order_idx,timestamp_iso8601,config,bench,size,rep_in_cell,phase,wall_s,srcversion,dmesg_delta,mem_avail_before_kb,mem_avail_after_kb" > "$CSV"

trace_file="$(collect_oracle_trace bench_stencil_oversub "$BENCH_OVSUB" "$N_OVSUB $ITERS")"

declare -A rep_count=( [C1]=0 [C3]=0 )

harness_log "=== Gate B9 Task 1c control: reduced-iters wall-clock, N=$N_OVSUB iters=$ITERS, interleaved C1,C3 x $TOTAL_ROTATIONS rotations ==="

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
        run_watched "$cfg" "$trace_arg" "$rep_label" "$phase"
    done
done

harness_log "done. CSV: $CSV"
harness_log "kept reps/cell should be $TARGET_ROTATIONS; warm-up reps/cell = $WARMUP_ROTATIONS"
