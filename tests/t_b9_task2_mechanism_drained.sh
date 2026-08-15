#!/usr/bin/env bash
# t_b9_task2_mechanism_drained.sh -- Gate B9 Task 2 mechanism run, periodic-
# drain variant.
#
# WHY THIS EXISTS: tests/t_b9_task2_mechanism.sh's single end-of-run read of
# specasync_log / specasync_decomp_log / specasync_worker_log saturates all
# three (131,072-slot, drop-on-full rings) within the first ~3-8% of a run's
# wall-clock at this oversubscription level (N=48000, ~18.43GB managed,
# ~4.8M pages) -- confirmed by inspecting batch-record timestamp spans
# against measured wall_s: C1 captured ~4.55s of a ~161s run (2.8%), C3
# captured ~5.5s of a ~69s run (7.9%). This is the SECOND occurrence of
# ARTIFACT_CATALOG.md artifact #7 ("ring saturation without wraparound") --
# see that file's "Second occurrence" note for the two new details this
# occurrence adds (unequal captured FRACTIONS between arms of different
# length; the trace ring holding the opposite, TRAILING window).
#
# FIX: read-and-clear the three drop-on-full rings at a fixed wall-clock
# interval WHILE the benchmark runs (not just once at the end), accumulating
# an ordered sequence of snapshots that -- IF VALIDATED -- tile the run's
# full timeline. Validation is not optional; see t_b9_task2_drain_validate.py
# for the four checks (coverage %, no single snapshot saturated, drain
# overhead vs an undrained baseline, batch_id contiguity as a direct loss
# check) that must all pass before this data is trusted for anything.
#
# specasync_clear ALSO resets the specasync_processed/enqueued/drops ATOMICS
# (confirmed by reading clear_write() in specasync_debugfs.c) -- a periodic
# clear would silently destroy their previously-established full-run
# reliability unless each interval's atomic reading is captured BEFORE that
# interval's clear and summed across all snapshots afterward, which this
# script's per-snapshot log (and the analyzer) does.
#
# specasync_fault_trace (thrash proxy) is NOT drained periodically here --
# out of scope for this fix; it keeps its existing, already-disclosed
# trailing-window-only caveat (true circular overwrite ring, no drop-on-full,
# a single end-of-run read is a defensible "just the tail", unlike the other
# three rings' end-of-run read being wrongly presentable as a full-run total).
#
# DRAIN_MODE=off disables periodic draining (single end-of-run dump, exactly
# matching t_b9_task2_mechanism.sh's behavior) -- used as the undrained
# baseline for the drain-overhead comparison.
#
# Usage: bash tests/t_b9_task2_mechanism_drained.sh <N> [iters] [drain_interval_s]
#        DRAIN_MODE=off bash tests/t_b9_task2_mechanism_drained.sh <N> [iters]
#        DRY_RUN=1 bash tests/t_b9_task2_mechanism_drained.sh <N>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_OVSUB="${1:?usage: t_b9_task2_mechanism_drained.sh <N> [iters] [drain_interval_s]}"
ITERS="${2:-20}"
DRAIN_INTERVAL="${3:-1}"
DRAIN_MODE="${DRAIN_MODE:-on}"

: "${KO:?KO must be set explicitly to the platform-correct .ko path}"
BENCH_OVSUB="$REPO/benchmarks/stencil_oversub/bench_stencil_oversub"

: "${OUT:=$REPO/results/analysis/gate_b9_oversub_mechanism}"
SUFFIX="drained"
[ "$DRAIN_MODE" = "off" ] && SUFFIX="undrained"
CSV="$OUT/task2_mechanism_${SUFFIX}_times.csv"
TELEM_DIR="$OUT/telemetry_task2_${SUFFIX}"

WARMUP_ROTATIONS="${WARMUP_ROTATIONS:-1}"
TARGET_ROTATIONS="${TARGET_ROTATIONS:-5}"
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

csv_header() {
    echo "run_order_idx,timestamp_iso8601,config,bench,size,rep_in_cell,phase,wall_s,exit_code,n_snapshots,telemetry_prefix,drain_mode,drain_interval_s,srcversion,dmesg_delta,mem_avail_before_kb,mem_avail_after_kb" > "$CSV"
}

reload_module_t2() {
    local policy="$1" depth="$2" prefetch="$3" trace_path="${4:-}"
    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] reload_module_t2 policy=$policy depth=$depth prefetch=$prefetch trace_path=${trace_path:-none}"
        return
    fi
    [ -f "$KO" ] || harness_die "module not found: $KO"
    dmesg_mark
    sudo rmmod nvidia_uvm 2>/dev/null || true
    if [ -d /sys/module/nvidia_uvm ]; then
        local refcnt
        refcnt=$(cat /sys/module/nvidia_uvm/refcnt 2>/dev/null || echo "?")
        harness_die "reload_module_t2: rmmod failed to unload nvidia_uvm (refcnt=$refcnt) -- module is busy, likely a leaked process holding it open (check: find /proc/*/fd -lname '*nvidia*' 2>/dev/null). NOT proceeding with insmod against a wrong/stale module state."
    fi
    local extra="specasync_policy=$policy specasync_offload_depth=$depth uvm_perf_prefetch_enable=$prefetch specasync_log_enabled=1 specasync_trace_faults=1"
    if [ -n "$trace_path" ]; then
        extra="$extra specasync_oracle_trace_path=$trace_path"
    fi
    sudo insmod "$KO" $extra
    sleep 0.3
    verify_module_reload "$policy" "$depth"
    local d
    d=$(dmesg_delta_count)
    if [ "$d" -gt 0 ]; then
        harness_log "reload: $d new dmesg line(s) -- logged, not necessarily an error"
    fi
}

collect_oracle_trace() {
    local bench="$1" bin="$2" args="$3"
    local trace_file="$OUT/c3_${bench}_task2_${SUFFIX}_trace.bin"
    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] collect_oracle_trace bench=$bench -> $trace_file"
        echo "$trace_file"
        return
    fi
    reload_module_t2 0 0 0
    harness_log "collecting oracle trace ($bench $args) -- oversubscribed, may take a while"
    setarch -R "$bin" $args >/dev/null
    sleep 0.2
    sudo -n cat "$DBGFS/specasync_fault_trace" > "$trace_file" 2>/dev/null || true
    local nent=$(( $(wc -c < "$trace_file" 2>/dev/null || echo 0) / 8 ))
    harness_log "oracle trace for $bench: $nent entries -> $trace_file"
    echo "$trace_file"
}

# drain_snapshot <prefix> <idx>
# Read-then-clear the three drop-on-full rings; log this interval's atomic
# readings (accurate for just this interval, since cleared beforehand) so
# the analyzer can sum them into a full-run total.
drain_snapshot() {
    local prefix="$1" idx="$2"
    dump_ring "$DBGFS/specasync_log"        "$TELEM_DIR/${prefix}_batch_snap${idx}.bin"
    dump_ring "$DBGFS/specasync_worker_log" "$TELEM_DIR/${prefix}_work_snap${idx}.bin"
    dump_ring "$DBGFS/specasync_decomp_log" "$TELEM_DIR/${prefix}_decomp_snap${idx}.bin"
    local p e d
    p=$(sudo -n cat "$DBGFS/specasync_processed" 2>/dev/null || echo 0)
    e=$(sudo -n cat "$DBGFS/specasync_enqueued" 2>/dev/null || echo 0)
    d=$(sudo -n cat "$DBGFS/specasync_drops" 2>/dev/null || echo 0)
    echo "$idx,$(date +%s.%N),$p,$e,$d" >> "$TELEM_DIR/${prefix}_snapshot_log.csv"
    clear_ring
}

# run_mechanism_case <cfg> <trace_arg> <rep_label> <phase>
run_mechanism_case() {
    local cfg="$1" trace_arg="$2" rep="$3" phase="$4"
    RUN_ORDER_IDX=$((RUN_ORDER_IDX + 1))
    local ts srcv mem_before mem_after ddelta

    reload_module_t2 "${POLICY[$cfg]}" "${DEPTH[$cfg]}" "${PREFETCH[$cfg]}" "$trace_arg"
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    srcv=$(current_srcversion)
    mem_before=$(mem_available_kb)
    dmesg_mark

    local prefix="${cfg}_run${RUN_ORDER_IDX}"
    local out_file="$TELEM_DIR/stdout_${prefix}.txt"
    local marker="$TELEM_DIR/watchdog_${prefix}.marker"
    echo "idx,epoch_s,processed,enqueued,drops" > "$TELEM_DIR/${prefix}_snapshot_log.csv"

    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] run_mechanism_case cfg=$cfg rep=$rep phase=$phase drain_mode=$DRAIN_MODE"
        echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$rep,$phase,0,0,0,$prefix,$DRAIN_MODE,$DRAIN_INTERVAL,DRYRUN,0,0,0" >> "$CSV"
        return
    fi

    local wall exit_code t0 t1 snap_idx=0
    t0=$(date +%s.%N)

    if [ "$DRAIN_MODE" = "off" ]; then
        set +e
        run_with_memory_watchdog 6291456 "$marker" -- \
            /usr/bin/time -f "%e" setarch -R "$BENCH_OVSUB" "$N_OVSUB" "$ITERS" \
            > "$out_file" 2>"${out_file}.stderr"
        exit_code=$?
    else
        set +e
        run_with_memory_watchdog 6291456 "$marker" -- \
            /usr/bin/time -f "%e" setarch -R "$BENCH_OVSUB" "$N_OVSUB" "$ITERS" \
            > "$out_file" 2>"${out_file}.stderr" &
        local run_pid=$!
        while kill -0 "$run_pid" 2>/dev/null; do
            sleep "$DRAIN_INTERVAL"
            if kill -0 "$run_pid" 2>/dev/null; then
                snap_idx=$((snap_idx + 1))
                drain_snapshot "$prefix" "$snap_idx"
            fi
        done
        wait "$run_pid"
        exit_code=$?
    fi

    if [ "$exit_code" = 137 ]; then
        local wd_floor="" wd_avail="" wd_pgid=""
        mem_watchdog_read_marker "$marker" wd_floor wd_avail wd_pgid
        harness_log_nofork "WATCHDOG FIRED run_order=$RUN_ORDER_IDX cfg=$cfg floor_kb=$wd_floor avail_kb=$wd_avail pgid=$wd_pgid"
        harness_log_nofork "ABORT: per standing directive, stop rather than retry at a lower setting -- report and stop"
        printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
            "$RUN_ORDER_IDX" "$ts" "$cfg" "bench_stencil_oversub" "$N_OVSUB" "$rep" "$phase" \
            "" "$exit_code" "$snap_idx" "$prefix" "$DRAIN_MODE" "$DRAIN_INTERVAL" "$srcv" "" "$mem_before" "$wd_avail" >> "$CSV"
        exit 1
    fi
    set -e

    # Final drain to catch whatever ran since the last periodic snapshot.
    if [ "$DRAIN_MODE" != "off" ]; then
        snap_idx=$((snap_idx + 1))
        drain_snapshot "$prefix" "$snap_idx"
    fi

    t1=$(date +%s.%N)
    wall=$(grep -oP '^[0-9]+\.[0-9]+$' "${out_file}.stderr" | tail -1)
    [ -z "$wall" ] && wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.2f", b-a}')

    ddelta=$(dmesg_delta_count)
    mem_after=$(mem_available_kb)

    harness_log "run_order=$RUN_ORDER_IDX cfg=$cfg rep=$rep wall=${wall}s exit=$exit_code snapshots=$snap_idx dmesg_delta=$ddelta mem_avail=${mem_after}kB"

    echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$rep,$phase,$wall,$exit_code,$snap_idx,$prefix,$DRAIN_MODE,$DRAIN_INTERVAL,$srcv,$ddelta,$mem_before,$mem_after" >> "$CSV"

    if [ "$DRAIN_MODE" = "off" ]; then
        dump_ring "$DBGFS/specasync_log" "$TELEM_DIR/${prefix}_batch_snap1.bin"
        dump_ring "$DBGFS/specasync_worker_log" "$TELEM_DIR/${prefix}_work_snap1.bin"
        dump_ring "$DBGFS/specasync_decomp_log" "$TELEM_DIR/${prefix}_decomp_snap1.bin"
        local p e d
        p=$(sudo -n cat "$DBGFS/specasync_processed" 2>/dev/null || echo 0)
        e=$(sudo -n cat "$DBGFS/specasync_enqueued" 2>/dev/null || echo 0)
        d=$(sudo -n cat "$DBGFS/specasync_drops" 2>/dev/null || echo 0)
        echo "1,$(date +%s.%N),$p,$e,$d" >> "$TELEM_DIR/${prefix}_snapshot_log.csv"
        clear_ring
    fi
    dump_ring "$DBGFS/specasync_fault_trace" "$TELEM_DIR/${prefix}_trace.bin"
    check_memory_or_abort
}

csv_header
trace_file="$(collect_oracle_trace bench_stencil_oversub "$BENCH_OVSUB" "$N_OVSUB $ITERS")"

declare -A rep_count=( [C1]=0 [C3]=0 )

harness_log "=== Gate B9 Task 2 ($SUFFIX): N=$N_OVSUB iters=$ITERS drain_interval=${DRAIN_INTERVAL}s, interleaved C1,C3 x $TOTAL_ROTATIONS rotations ==="

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
        run_mechanism_case "$cfg" "$trace_arg" "$rep_label" "$phase"
    done
done

harness_log "done. CSV: $CSV"
harness_log "kept reps/cell should be $TARGET_ROTATIONS; warm-up reps/cell = $WARMUP_ROTATIONS"
