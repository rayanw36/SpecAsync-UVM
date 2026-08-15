#!/usr/bin/env bash
# t_b9_task1_nsys.sh -- Gate B9 Task 1(c): H2D/D2H migrated bytes, C1 vs C3
# at ~1.08x oversubscription (N=48000), via Nsight Systems UM tracing.
#
# Uses the ORIGINAL, unmodified bench_stencil_oversub binary -- NOT the
# checksum variant -- because the checksum variant reads the whole output
# buffer back on the host after the timed region, which would add a large,
# config-independent D2H migration and contaminate the byte comparison this
# script exists to make.
#
# nsys's --cuda-um-cpu-page-faults / --cuda-um-gpu-page-faults tracing adds
# real overhead (per-fault trap sampling), so this is a SEPARATE, small
# (n=3/arm) dataset -- not folded into the main timing sweeps in Tasks 2-4,
# and not meant to reproduce Section 5/6's wall-clock numbers. Its only job
# is a coarse equivalence check: do C1 and C3 move comparable amounts of
# data, or does one do substantially less work than the other.
#
# SAFETY INCIDENT (2026-08-15): the first full-iters=20 invocation of this
# script OOM-killed the host mid-run (nsys's live UM-fault-trace buffer, on
# top of the 18.43GB managed workload, exceeded available RAM -- the
# between-runs check_memory_or_abort guard cannot catch a mid-run spike).
# See task1_nsys_um_bytes_OOM_INCIDENT_iters20_ABORTED.csv for that run's
# (partial) record. Remediation, per explicit user directive:
#   1. tests/lib_specasync_harness.sh now provides run_with_memory_watchdog,
#      an in-run poller that kills the process group if MemAvailable drops
#      below a caller-set floor. This script wraps nsys profile in it with a
#      10 GiB floor (not the usual 6 GiB) -- nsys flushes its own state at
#      teardown, which needs headroom beyond the bare workload's.
#   2. Default ITERS dropped from 20 to 3, matching
#      tests/t_b9_task1c_iters_control.sh, which confirmed (n=5/arm,
#      complete separation, exact MWU p=0.0079) that the C3-vs-C1 advantage
#      still appears at iters=3 -- median -28.49% (22.64s vs 31.66s), same
#      direction as the iters=20 result but roughly half the magnitude
#      (-56.52% at iters=20, OVERSUB_SPEEDUP_VERIFICATION.md Section 5). The
#      reduced-iters config is therefore a valid but NOT fully representative
#      proxy: nsys numbers taken here characterize an effect that is real at
#      iters=3, not the full-magnitude iters=20 effect. State this caveat
#      wherever these numbers are used downstream (Task 2 must run at full
#      iters for that reason).
#   3. --export=none on nsys profile, to skip the offline sqlite conversion
#      that produced a 3.76GB file in the incident run; `nsys stats` below
#      converts on demand, after the profiled process has already exited and
#      its memory been freed.
#   4. Strictly sequential, one report at a time -- no backgrounding.
#
# Usage: bash tests/t_b9_task1_nsys.sh <N> [iters]
#        DRY_RUN=1 bash tests/t_b9_task1_nsys.sh <N>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_OVSUB="${1:?usage: t_b9_task1_nsys.sh <N> [iters]}"
ITERS="${2:-3}"

: "${KO:?KO must be set explicitly to the platform-correct .ko path}"
BENCH_OVSUB="$REPO/benchmarks/stencil_oversub/bench_stencil_oversub"

: "${OUT:=$REPO/results/analysis/gate_b9_oversub_mechanism}"
CSV="$OUT/task1_nsys_um_bytes_iters${ITERS}.csv"
NSYS_DIR="$OUT/task1_nsys_reports"

WARMUP_ROTATIONS=1
TARGET_ROTATIONS=3
TOTAL_ROTATIONS=$((WARMUP_ROTATIONS + TARGET_ROTATIONS))

declare -A POLICY=( [C1]=0 [C3]=4 )
declare -A DEPTH=(  [C1]=0 [C3]=1 )
declare -A PREFETCH=([C1]=0 [C3]=0 )

mkdir -p "$OUT" "$NSYS_DIR"

WATCHDOG_FLOOR_KB=10485760  # 10 GiB -- nsys teardown-flush headroom
: "${ABORT_MIN_AVAIL_KB:=10485760}"  # 10 GiB, matches watchdog floor
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
    echo "run_order_idx,timestamp_iso8601,config,bench,size,rep_in_cell,phase,wall_s,htod_mb,dtoh_mb,cpu_page_faults,gpu_page_faults,exit_code,srcversion,mem_avail_before_kb,mem_avail_after_kb" > "$CSV"
}

collect_oracle_trace() {
    local bench="$1" bin="$2" args="$3"
    local trace_file="$OUT/c3_${bench}_task1nsys_trace.bin"
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

# run_nsys_case <cfg> <trace_arg> <rep_label> <phase>
run_nsys_case() {
    local cfg="$1" trace_arg="$2" rep="$3" phase="$4"
    RUN_ORDER_IDX=$((RUN_ORDER_IDX + 1))
    local ts srcv mem_before mem_after

    reload_module "$KO" "${POLICY[$cfg]}" "${DEPTH[$cfg]}" "${PREFETCH[$cfg]}" "$trace_arg"
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    srcv=$(current_srcversion)
    mem_before=$(mem_available_kb)

    local report_base="$NSYS_DIR/${cfg}_run${RUN_ORDER_IDX}"

    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] run_nsys_case cfg=$cfg rep=$rep phase=$phase"
        echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$rep,$phase,0,0,0,0,0,0,DRYRUN,0,0" >> "$CSV"
        return
    fi

    local wall exit_code t0 t1 marker
    marker="$NSYS_DIR/watchdog_${cfg}_run${RUN_ORDER_IDX}.marker"

    # Pre-open the incident-row fd and have every static field already in a
    # plain variable BEFORE the run starts -- if the watchdog fires, the
    # abort branch below must not fork anything (see
    # lib_specasync_harness.sh's run_with_memory_watchdog header for the
    # incident this pattern fixes).
    exec {__abort_fd}>>"$CSV"

    t0=$(date +%s.%N)
    set +e
    run_with_memory_watchdog "$WATCHDOG_FLOOR_KB" "$marker" -- \
        nsys profile --trace=cuda --cuda-um-cpu-page-faults=true --cuda-um-gpu-page-faults=true \
        --export=none -o "$report_base" --force-overwrite=true \
        setarch -R "$BENCH_OVSUB" "$N_OVSUB" "$ITERS" \
        > "${report_base}.stdout" 2> "${report_base}.stderr"
    exit_code=$?

    if [ "$exit_code" = 137 ]; then
        local wd_floor="" wd_avail="" wd_pgid=""
        mem_watchdog_read_marker "$marker" wd_floor wd_avail wd_pgid
        harness_log_nofork "WATCHDOG FIRED run_order=$RUN_ORDER_IDX cfg=$cfg floor_kb=$wd_floor avail_kb=$wd_avail pgid=$wd_pgid"
        harness_log_nofork "ABORT: per standing directive, stop rather than retry at a lower setting -- report and stop"
        printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
            "$RUN_ORDER_IDX" "$ts" "$cfg" "bench_stencil_oversub" "$N_OVSUB" "$rep" "$phase" \
            "" "" "" "" "" "$exit_code" "$srcv" "$mem_before" "$wd_avail" >&"$__abort_fd"
        exec {__abort_fd}>&-
        exit 1
    fi
    set -e
    exec {__abort_fd}>&-
    t1=$(date +%s.%N)
    wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.2f", b-a}')

    local mem_after ddelta
    mem_after=$(mem_available_kb)

    local htod dtoh cpuf gpuf
    if [ -f "${report_base}.nsys-rep" ]; then
        local stats_out
        stats_out=$(nsys stats --report um_total_sum "${report_base}.nsys-rep" 2>/dev/null | \
            awk '/^ +[0-9.]+ / {print; exit}')
        # Columns: HtoD(MB) DtoH(MB) CPU_faults GPU_faults MinVA MaxVA -- space separated, some may be blank
        htod=$(echo "$stats_out" | awk '{print $1}')
        dtoh=$(echo "$stats_out" | awk '{print $2}')
        cpuf=$(echo "$stats_out" | awk '{print $3}')
        gpuf=$(echo "$stats_out" | awk '{print $4}')
    else
        harness_log "WARNING: no .nsys-rep produced for run_order=$RUN_ORDER_IDX (cfg=$cfg) -- nsys or benchmark may have failed, see ${report_base}.stderr"
        htod=""; dtoh=""; cpuf=""; gpuf=""
    fi

    harness_log "run_order=$RUN_ORDER_IDX cfg=$cfg rep=$rep wall=${wall}s exit=$exit_code htod_mb=$htod dtoh_mb=$dtoh cpu_faults=$cpuf gpu_faults=$gpuf mem_avail=${mem_after}kB"

    echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$rep,$phase,$wall,$htod,$dtoh,$cpuf,$gpuf,$exit_code,$srcv,$mem_before,$mem_after" >> "$CSV"

    check_memory_or_abort
}

csv_header
trace_file="$(collect_oracle_trace bench_stencil_oversub "$BENCH_OVSUB" "$N_OVSUB $ITERS")"

declare -A rep_count=( [C1]=0 [C3]=0 )

harness_log "=== Gate B9 Task 1c: nsys UM byte totals, N=$N_OVSUB iters=$ITERS, interleaved C1,C3 x $TOTAL_ROTATIONS rotations ==="

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
        run_nsys_case "$cfg" "$trace_arg" "$rep_label" "$phase"
    done
done

harness_log "done. CSV: $CSV"
harness_log "kept reps/cell should be $TARGET_ROTATIONS; warm-up reps/cell = $WARMUP_ROTATIONS"
