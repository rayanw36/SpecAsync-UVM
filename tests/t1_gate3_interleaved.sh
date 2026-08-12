#!/usr/bin/env bash
# t1_gate3_interleaved.sh — Task T1: interleaved Gate 3 C0-C3 rerun.
#
# Implements results/analysis/PREREGISTRATION.md exactly:
#   - rotation: C0,C1,C2,C3,C0,C1,C2,C3,... (never blocked)
#   - warm-up: first 2 complete rotations (8 runs/config-set) discarded
#   - target: 20 kept reps/cell after warm-up (22 total reps/config/bench)
#   - mechanism: reload before EVERY run (uniform across all 4 configs --
#     see PREREGISTRATION.md's correction on read-only module params)
#   - records run-order index, timestamp, config, bench, size, srcversion,
#     dmesg delta for every single run (the exact columns the original
#     gate3_favorable_run.sh omitted)
#   - writes to results/phaseB2/gate3_interleaved/ -- NEVER touches the
#     original results/phaseB2/gate3/gate3_times.csv
#
# Usage: sudo bash tests/t1_gate3_interleaved.sh [stencil_N] [bfs_nodes]
#        DRY_RUN=1 bash tests/t1_gate3_interleaved.sh   # no-op plumbing check

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib_specasync_harness.sh
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_STENCIL="${1:-24000}"
N_BFS="${2:-23}"

: "${KO:=$REPO/driver/build/nvidia-uvm-specasync-t4.ko}"
BENCH_STENCIL="$REPO/benchmarks/bench_stencil"
BENCH_BFS="$REPO/benchmarks/graph_bfs/bench_graph_bfs"

: "${OUT:=$REPO/results/phaseB2/gate3_interleaved}"
CSV="$OUT/gate3_interleaved_times.csv"
TELEM_DIR="$OUT/telemetry"

WARMUP_ROTATIONS=2
TARGET_ROTATIONS=20
TOTAL_ROTATIONS=$((WARMUP_ROTATIONS + TARGET_ROTATIONS))

# config -> (policy, depth, prefetch) per gate3_favorable_run.sh's original
# definitions, carried forward unchanged (T1 reruns the SAME four configs,
# only the protocol changes):
#   C0: stock, prefetch ON             policy=0 depth=0 prefetch=1
#   C1: no speculation, prefetch OFF   policy=0 depth=0 prefetch=0
#   C2: stride, depth=1, prefetch OFF  policy=2 depth=1 prefetch=0
#   C3: oracle, depth=1, prefetch OFF  policy=4 depth=1 prefetch=0 (needs trace)
declare -A POLICY=( [C0]=0 [C1]=0 [C2]=2 [C3]=4 )
declare -A DEPTH=(  [C0]=0 [C1]=0 [C2]=1 [C3]=1 )
declare -A PREFETCH=([C0]=1 [C1]=0 [C2]=0 [C3]=0 )

mkdir -p "$OUT" "$TELEM_DIR"
csv_init "$CSV"

collect_oracle_trace() {
    # One-time per-benchmark trace collection, before the rotation starts.
    # A trace is a property of the benchmark's fault sequence, not of run
    # order -- collecting once and reusing at every C3 reload within the
    # session does not reintroduce blocking (PREREGISTRATION.md Section 1).
    local bench="$1" bin="$2" args="$3"
    local trace_file="$OUT/c3_${bench}_trace.bin"
    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] collect_oracle_trace bench=$bench -> $trace_file"
        echo "$trace_file"
        return
    fi
    reload_module "$KO" 0 0 0
    sudo rmmod nvidia_uvm 2>/dev/null || true
    sudo insmod "$KO" specasync_policy=0 specasync_offload_depth=0 \
        uvm_perf_prefetch_enable=0 specasync_trace_faults=1 specasync_log_enabled=0
    sleep 0.3
    setarch -R "$bin" $args >/dev/null
    sleep 0.2
    sudo cat "$DBGFS/specasync_fault_trace" > "$trace_file" 2>/dev/null || true
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

            # Per-run telemetry dump (specasync_log ring), tagged by global
            # run-order index so it's traceable back to the CSV row.
            dump_ring "$DBGFS/specasync_log" "$TELEM_DIR/${bench}_${cfg}_run${RUN_ORDER_IDX}.bin"
            clear_ring
        done
    done
}

harness_log "=== T1: Stencil@$N_STENCIL, interleaved C0,C1,C2,C3 x $TOTAL_ROTATIONS rotations ==="
run_interleaved_session bench_stencil "$BENCH_STENCIL" "$N_STENCIL" "$N_STENCIL"

harness_log "=== T1: GraphBFS@$N_BFS, interleaved C0,C1,C2,C3 x $TOTAL_ROTATIONS rotations ==="
run_interleaved_session bench_graph_bfs "$BENCH_BFS" "$N_BFS" "$N_BFS"

harness_log "done. CSV: $CSV"
harness_log "kept reps/cell should be $TARGET_ROTATIONS (>= 15 pre-registered minimum); warm-up reps/cell = $WARMUP_ROTATIONS"
harness_log "next: run the pre-registered statistical pipeline (Task T1 Gate report) against $CSV, filtering phase=kept"
