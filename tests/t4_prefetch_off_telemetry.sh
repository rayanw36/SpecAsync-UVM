#!/usr/bin/env bash
# t4_prefetch_off_telemetry.sh — Task T4: prefetch-OFF hit-rate telemetry.
#
# tests/gate3_favorable_run.sh runs C1-C3 with the prefetcher off but logs
# only wall-clock, never the specasync_log ring -- so no hit-rate telemetry
# exists for any real benchmark with the prefetcher off (F3's missing cell).
#
# This script does NOT modify gate3_favorable_run.sh (its timing path, run
# ordering, warm-up handling, and repetition count must stay exactly as
# published, since its wall-clock results are already reported). Instead it
# is a SEPARATE script that reproduces gate3_favorable_run.sh's C1 and C3
# reload/param sequence byte-for-byte (same policy/depth/prefetch values,
# same RUNS=15 default, same oracle-trace-then-reload procedure for C3) and
# adds a specasync_log ring dump after every run. C2 is written but OFF by
# default (--with-c2 to enable), per the task's "C2 optional" note.
#
# What this resolves: the deterministic probe (GATE_A_report.md) proves the
# hit counter works, but the probe is stride-friendly by construction, so it
# can't rule out real workloads having irregular access that defeats the
# predictor independently of the prefetcher. This run discriminates.
#
# One debugging attempt, no more (per the task brief) -- if insmod/reload
# fails or debugfs is unreadable, report and move on to the next task rather
# than iterating.
#
# Usage: sudo bash tests/t4_prefetch_off_telemetry.sh [stencil_N] [bfs_nodes] [runs] [--with-c2]
#        DRY_RUN=1 bash tests/t4_prefetch_off_telemetry.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_STENCIL="${1:-24000}"
N_BFS="${2:-23}"
RUNS="${3:-15}"
WITH_C2=0
for a in "$@"; do [ "$a" = "--with-c2" ] && WITH_C2=1; done

# Same build the original gate3_favorable_run.sh referenced (phaseB2) is
# stale by now on this instance; use the T4 work block's own build, unless
# overridden -- the module identity doesn't affect telemetry format, only
# which srcversion gets logged alongside it.
KO="${SPECASYNC_KO:-$REPO/driver/build/nvidia-uvm-specasync-t4.ko}"
BENCH_STENCIL="$REPO/benchmarks/bench_stencil"
BENCH_BFS="$REPO/benchmarks/graph_bfs/bench_graph_bfs"

OUT="$REPO/results/gate3/telemetry"
CSV="$OUT/t4_prefetch_off_times.csv"
mkdir -p "$OUT"
csv_init "$CSV"

dump_after_run() {
    local cfg="$1" bench="$2"
    dump_ring "$DBGFS/specasync_log" "$OUT/${bench}_${cfg}_run${RUN_ORDER_IDX}.bin"
}

run_c1_block() {
    local bench="$1" bin="$2" args="$3"
    harness_log "=== C1: policy=0 depth=0 prefetch=0, $bench ==="
    reload_module "$KO" 0 0 0
    for run in $(seq 1 $RUNS); do
        time_run "$CSV" "$bin" "$args" C1 "$bench" "$args" "$run"
        dump_after_run C1 "$bench"
    done
}

run_c2_block() {
    local bench="$1" bin="$2" args="$3"
    harness_log "=== C2 (optional): policy=2 depth=1 prefetch=0, $bench ==="
    reload_module "$KO" 2 1 0
    for run in $(seq 1 $RUNS); do
        time_run "$CSV" "$bin" "$args" C2 "$bench" "$args" "$run"
        dump_after_run C2 "$bench"
    done
}

run_c3_block() {
    local bench="$1" bin="$2" args="$3"
    harness_log "=== C3: oracle trace collect -> reload -> run, $bench ==="
    local trace_file="$OUT/c3_${bench}_trace.bin"
    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] collect oracle trace -> $trace_file"
    else
        reload_module "$KO" 0 0 0
        sudo rmmod nvidia_uvm 2>/dev/null || true
        sudo insmod "$KO" specasync_policy=0 specasync_offload_depth=0 \
            uvm_perf_prefetch_enable=0 specasync_trace_faults=1 specasync_log_enabled=0
        sleep 0.3
        setarch -R "$bin" $args >/dev/null
        sleep 0.2
        sudo cat "$DBGFS/specasync_fault_trace" > "$trace_file" 2>/dev/null || true
    fi
    reload_module "$KO" 4 1 0 "$trace_file"
    for run in $(seq 1 $RUNS); do
        time_run "$CSV" "$bin" "$args" C3 "$bench" "$args" "$run"
        dump_after_run C3 "$bench"
    done
}

for pair in "bench_stencil:$BENCH_STENCIL:$N_STENCIL" "bench_graph_bfs:$BENCH_BFS:$N_BFS"; do
    IFS=: read -r bench bin args <<< "$pair"
    run_c1_block "$bench" "$bin" "$args"
    [ "$WITH_C2" = "1" ] && run_c2_block "$bench" "$bin" "$args"
    run_c3_block "$bench" "$bin" "$args"
done

harness_log "done. Timing CSV: $CSV; ring dumps: $OUT/*_run*.bin"
harness_log "verdict to report at Gate T4: measured hit rate per config, and whether"
harness_log "real-workload irregular access defeats the predictor independent of the"
harness_log "prefetcher (the alternative-explanation question this run exists to answer)."
