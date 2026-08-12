#!/usr/bin/env bash
# t_a1_worker_completion.sh — Task A1: worker completion telemetry.
#
# RATE_MISMATCH_VERIFICATION.md Section 6: spec_enqueued only means
# queue_work() returned successfully, not that the item ever executed. This
# script measures the actual processed/enqueued ratio using the new
# g_specasync_processed / g_specasync_enqueued / g_specasync_drops kernel
# atomics (added this session -- see specasync_internal.h, srcversion
# 24219FEEEB0B96D78E4E1AC), which are immune to specasync_worker_log ring
# wraparound (SPECASYNC_WORK_RING_SLOTS=131072; Stencil-24K enqueues ~51M
# items/run -- ~390x wrap). The ring itself is still dumped per run for its
# latency-distribution window, but totals come from the counters, never from
# counting ring records.
#
# Does NOT modify t4_prefetch_off_telemetry.sh or gate3_favorable_run.sh.
# clear_ring() is called before every rep (t4_prefetch_off_telemetry.sh does
# not do this -- it doesn't need to, since it never reads the cumulative
# counters) so each rep's processed/enqueued/drops are a clean per-run total,
# not a running sum across reps.
#
# Usage: sudo bash tests/t_a1_worker_completion.sh [n_reps]
#        SHORT_RUN=1 sudo bash tests/t_a1_worker_completion.sh [n_reps]  # non-wrapping cross-check sizes
#        DRY_RUN=1 bash tests/t_a1_worker_completion.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_REPS="${1:-5}"
SHORT_RUN="${SHORT_RUN:-0}"

: "${KO:=$REPO/driver/build/nvidia-uvm-specasync-t4-a1.ko}"
BENCH_STENCIL="$REPO/benchmarks/bench_stencil"
BENCH_BFS="$REPO/benchmarks/graph_bfs/bench_graph_bfs"

if [ "$SHORT_RUN" = "1" ]; then
    # Calibrated (this session, empirically) so specasync_enqueued stays
    # well under SPECASYNC_WORK_RING_SLOTS=131072 -- worker ring holds the
    # COMPLETE run, not a window, for a same-mechanism cross-check.
    N_STENCIL=2000   # ~35K enqueues, calibrated
    N_BFS=18         # ~15K enqueues, calibrated
    : "${OUT:=$REPO/results/analysis/t_a1_worker/short_run}"
else
    N_STENCIL=24000
    N_BFS=23
    : "${OUT:=$REPO/results/analysis/t_a1_worker/full_run}"
fi

CSV="$OUT/worker_completion.csv"
mkdir -p "$OUT"
csv_init "$CSV" "processed,enqueued,drops,worker_records_in_window,worker_ring_wrapped"

WORK_RING_SLOTS=131072

read_counters() {
    local p e d
    p=$(sudo cat "$DBGFS/specasync_processed" 2>/dev/null || echo 0)
    e=$(sudo cat "$DBGFS/specasync_enqueued" 2>/dev/null || echo 0)
    d=$(sudo cat "$DBGFS/specasync_drops" 2>/dev/null || echo 0)
    echo "$p $e $d"
}

collect_oracle_trace() {
    local bench="$1" bin="$2" args="$3"
    local trace_file="$OUT/c3_${bench}_trace.bin"
    if [ "$DRY_RUN" = "1" ]; then
        echo "$trace_file"
        return
    fi
    reload_module "$KO" 0 0 0
    sudo rmmod nvidia_uvm 2>/dev/null || true
    sudo insmod "$KO" specasync_policy=0 specasync_offload_depth=0 \
        uvm_perf_prefetch_enable=0 specasync_trace_faults=1 specasync_log_enabled=0
    sleep 0.3
    setarch "$(uname -m)" -R "$bin" $args >/dev/null
    sleep 0.2
    sudo cat "$DBGFS/specasync_fault_trace" > "$trace_file" 2>/dev/null || true
    local nent=$(( $(wc -c < "$trace_file" 2>/dev/null || echo 0) / 8 ))
    harness_log "oracle trace for $bench: $nent entries -> $trace_file"
    echo "$trace_file"
}

run_bench() {
    local bench="$1" bin="$2" args="$3"
    local trace_file
    trace_file="$(collect_oracle_trace "$bench" "$bin" "$args")"
    harness_log "=== C3: oracle, depth=1, prefetch OFF, $bench args=$args ==="
    reload_module "$KO" 4 1 0 "$trace_file"

    for run in $(seq 1 "$N_REPS"); do
        clear_ring
        RUN_ORDER_IDX=$((RUN_ORDER_IDX))  # time_run increments internally
        if [ "$DRY_RUN" = "1" ]; then
            harness_log "[dry-run] worker-completion rep=$run bench=$bench"
            time_run "$CSV" "$bin" "$args" C3 "$bench" "$args" "$run" "0,0,0,0,no"
            continue
        fi
        dmesg_mark
        wall=$({ /usr/bin/time -f "%e" setarch "$(uname -m)" -R "$bin" $args >/dev/null; } 2>&1 | tail -1)
        ddelta=$(dmesg_delta_count)
        read -r processed enqueued drops <<< "$(read_counters)"

        dump_ring "$DBGFS/specasync_worker_log" "$OUT/${bench}_worker_run${run}.bin"
        dump_ring "$DBGFS/specasync_log" "$OUT/${bench}_batch_run${run}.bin"

        local wsz
        wsz=$(wc -c < "$OUT/${bench}_worker_run${run}.bin" 2>/dev/null || echo 0)
        local window_records=$((wsz / 48))
        local wrapped="no"
        [ "$processed" -gt "$WORK_RING_SLOTS" ] && wrapped="yes"

        local ts srcv
        ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
        srcv=$(current_srcversion)
        RUN_ORDER_IDX=$((RUN_ORDER_IDX + 1))
        echo "$RUN_ORDER_IDX,$ts,C3,$bench,$args,$run,$wall,$srcv,$ddelta,$processed,$enqueued,$drops,$window_records,$wrapped" >> "$CSV"
        harness_log "rep=$run wall=${wall}s processed=$processed enqueued=$enqueued drops=$drops window_records=$window_records wrapped=$wrapped"
    done
}

run_bench "bench_stencil" "$BENCH_STENCIL" "$N_STENCIL"
run_bench "bench_graph_bfs" "$BENCH_BFS" "$N_BFS"

harness_log "done. CSV: $CSV; worker/batch ring dumps: $OUT/*_run*.bin"
