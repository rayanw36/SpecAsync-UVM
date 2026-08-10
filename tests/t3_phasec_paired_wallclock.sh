#!/usr/bin/env bash
# t3_phasec_paired_wallclock.sh — Task T3: Phase C paired wall-clock capture
# for the 6 of 7 workloads currently missing a same-session wall-clock
# denominator (per PIPELINING_CEILING.md: only Stencil-24K has one, via
# PHASEC_REPORT.md's Gate G3 overhead-validation run).
#
# Workloads: Stencil-8K, GraphBFS-23, Sweep-4K, Sweep-8K, Sweep-16K, Sweep-24K.
#
# Design, directly addressing PIPELINING_CEILING.md's stated reason the
# other six workloads have no ceiling: capture wall-clock runtime (via
# /usr/bin/time) in the SAME session, immediately bracketing the decomp
# telemetry snapshot for that exact run -- not a Gate-3 number with a
# different policy/config pasted in after the fact (the mismatch
# PIPELINING_CEILING.md explicitly flags and refuses to do for Stencil-24K).
#
# Module config: policy=0 depth=0 prefetch=1 log=1 -- identical to
# run_gatec1_decomp.sh's load_module and to PHASEC_REPORT.md's own runs, so
# the wall-clock and decomp numbers this task produces are governed by the
# same configuration as every other Phase C number already in the paper.
#
# REQUIRES a module built with SPECASYNC_DECOMP=1 (the compile-time flag
# gating all D1-D7 decomp instrumentation in uvm_gpu_replayable_faults.c;
# without it, specasync_decomp_log will not exist). Phase 2 must build with
# this flag, or point SPECASYNC_KO at a suitable existing build.
#
# Usage: sudo bash tests/t3_phasec_paired_wallclock.sh [n_trials]
#        DRY_RUN=1 bash tests/t3_phasec_paired_wallclock.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_TRIALS="${1:-5}"   # matches PHASEC_REPORT.md's G3 overhead check (5 trials)

KO="${SPECASYNC_KO:-$REPO/driver/build/nvidia-uvm-specasync-t4.ko}"
BENCH_STENCIL="$REPO/benchmarks/bench_stencil"
BENCH_BFS="$REPO/benchmarks/graph_bfs/bench_graph_bfs"

OUT="$REPO/results/phaseC/paired_wallclock"
CSV="$OUT/t3_paired_times.csv"
DECOMP_DIR="$OUT/decomp"
mkdir -p "$OUT" "$DECOMP_DIR"
csv_init "$CSV" "decomp_snapshot_path"

# workload_name -> (bin, args, size_label)
declare -A WL_BIN=(
    [Stencil-8K]="$BENCH_STENCIL"
    [GraphBFS-23]="$BENCH_BFS"
    [Sweep-4K]="$BENCH_STENCIL"
    [Sweep-8K]="$BENCH_STENCIL"
    [Sweep-16K]="$BENCH_STENCIL"
    [Sweep-24K]="$BENCH_STENCIL"
)
declare -A WL_ARGS=(
    [Stencil-8K]=8000
    [GraphBFS-23]=23
    [Sweep-4K]=4000
    [Sweep-8K]=8000
    [Sweep-16K]=16000
    [Sweep-24K]=24000
)

load_phasec_module() {
    reload_module "$KO" 0 0 1
}

run_workload() {
    local wl="$1"
    local bin="${WL_BIN[$wl]}" args="${WL_ARGS[$wl]}"
    harness_log "=== $wl: $bin $args, $N_TRIALS trials ==="
    for trial in $(seq 1 $N_TRIALS); do
        clear_ring
        time_run "$CSV" "$bin" "$args" "$wl" "$(basename "$bin")" "$args" "$trial" "PENDING"
        local snap="$DECOMP_DIR/${wl}_trial${trial}.bin"
        dump_ring "$DBGFS/specasync_decomp_log" "$snap"
        if [ "$DRY_RUN" != "1" ]; then
            sed -i "\$s#,PENDING\$#,$snap#" "$CSV"
        else
            sed -i "\$s#,PENDING\$#,$snap#" "$CSV"
        fi
    done
}

load_phasec_module

for wl in Stencil-8K GraphBFS-23 Sweep-4K Sweep-8K Sweep-16K Sweep-24K; do
    run_workload "$wl"
done

harness_log "done. Timing CSV: $CSV, decomp snapshots: $DECOMP_DIR"
harness_log "next: compute, per workload, sum(D1+D2)/sum(total_ns) from the decomp"
harness_log "snapshots (see tests/gatec1_decomp_analysis.py's DECOMP_FMT), pair with"
harness_log "the median wall-clock from \$CSV, and report the arithmetic exactly as"
harness_log "PIPELINING_CEILING.md section 4 did for Stencil-24K: D1+D2 share of"
harness_log "window x window share of wall-clock = end-to-end ceiling. Label every"
harness_log "denominator. Cross-check: does the Stencil-24K method (n=$N_TRIALS,"
harness_log "same module config) reproduce ~7.9% when run through this same harness?"

if [ "$DRY_RUN" != "1" ]; then
    harness_log "confirming 0.64% instrumentation overhead applies: this run's module IS the"
    harness_log "instrumented (DECOMP=1) build, per PIPELINING_CEILING.md section 3's"
    harness_log "convention -- both the wall-clock numerator and the decomp-derived"
    harness_log "denominator come from the same instrumented run, so no separate overhead"
    harness_log "correction is applied on top (would double-count)."
fi
