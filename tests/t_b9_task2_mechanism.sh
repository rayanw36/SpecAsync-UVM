#!/usr/bin/env bash
# t_b9_task2_mechanism.sh -- Gate B9 Task 2: mechanism instrumentation.
# C1 vs C3 at ~1.08x oversubscription (N=48000, full iters=20 -- NOT reduced;
# Task 1's control found the C3-vs-C1 advantage scales with iteration count
# [-28.49% at iters=3 vs -56.52% at iters=20], so a reduced-iters run would
# understate the effect this task is trying to characterize), n=10/arm,
# strictly interleaved.
#
# What's actually instrumented, confirmed by reading driver/src/*.c and
# specasync_telemetry.h before designing this (per the brief: "confirm which
# of these the telemetry actually exposes... say plainly if thrash cannot be
# measured either"):
#
#   - specasync_log (batch_record, 72B): num_faults is populated
#     UNCONDITIONALLY per batch (gated only on specasync_log_enabled, not on
#     policy) -- this is DIRECTLY comparable between C1 and C3 and is the
#     single most direct test of the brief's pre-registered hypothesis
#     (does C3 generate fewer total demand faults than C1, i.e. does
#     speculative migration avoid faults rather than just resolve them
#     faster). spec_enqueues/spec_drops/spec_hits are also per-batch here.
#   - specasync_processed / specasync_enqueued / specasync_drops (debugfs
#     atomics, reset by specasync_clear): ring-wraparound-immune totals,
#     cross-checked against the batch_record sums.
#   - specasync_worker_log (work_record, 48B): per-speculative-attempt
#     va_addr + result (0=null 1=miss 2=hit 3=migration_done 4=throttled).
#     result==migration_done is a genuine speculative-migration COUNT (C3
#     only -- C1 has policy=0, specasync_enqueue() returns immediately, this
#     ring stays empty for C1 by construction).
#   - specasync_decomp_log (decomp_record, 112B): D1/D2/D3/D4/D5/D6 phase
#     timings per top-level batch iteration; D7 computed from the recorded
#     fields per the accounting-closure formula in specasync_telemetry.h.
#   - specasync_fault_trace (raw u64 VA ring, 1,048,576 slots, TRUE circular
#     overwrite -- no drop-on-full, confirmed by reading
#     specasync_trace_push(): unconditional write + increment, no bounds
#     check): per-page repeat-fault count is the project's established
#     thrash/re-migration proxy (same method as GATE_D). CAVEAT, load-bearing:
#     an 18.43GB grid is ~4.8M pages; a single full pass already exceeds the
#     ring's 1,048,576-slot capacity, so on any run with total demand faults
#     > 1,048,576 this ring holds ONLY the trailing ~1,048,576 fault events,
#     not the whole run. The analysis script discloses whether each run's
#     trace wrapped and, if so, reports the repeat-count distribution as a
#     trailing-window statistic, not a full-run one.
#   - NOT available: migration BYTE counts (established unmeasurable in
#     Task 1c) and no dedicated EVICTION event counter anywhere in the
#     driver -- uvm_va_block_make_resident()'s internals (stock UVM) are not
#     instrumented by SpecAsync. The fault-trace repeat-count proxy stands in
#     for both thrash and (indirectly) eviction; this script does not invent
#     a substitute eviction counter.
#
# NOTE on the batch/work/decomp rings: unlike the fault_trace ring, these are
# DROP-ON-FULL (131,072 slots each; specasync_*_ring_push() increments a
# drops counter and discards the record once head-tail reaches capacity --
# confirmed by reading the push functions). drops is not exposed via debugfs,
# so it can't be read directly; the analysis script flags any run whose
# record count lands at/near 131,072 as a possible-drop warning (opposite
# bias from fault_trace: if this ring fills, it's the LATE part of the run
# that's missing, not the trailing window).
#
# Every run reloads the module fresh (existing project convention -- every
# config switch reloads), which also gives every run a genuinely empty
# fault_trace ring to start from (module reinit re-kvmallocs it) -- no
# cross-run contamination even though specasync_clear does not itself reset
# g_trace_ring (confirmed by reading clear_write(): it resets batch/work/
# decomp rings and the 3 atomics, but not g_trace_ring).
#
# Usage: bash tests/t_b9_task2_mechanism.sh <N> [iters]
#        DRY_RUN=1 bash tests/t_b9_task2_mechanism.sh <N>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_OVSUB="${1:?usage: t_b9_task2_mechanism.sh <N> [iters]}"
ITERS="${2:-20}"

: "${KO:?KO must be set explicitly to the platform-correct .ko path}"
BENCH_OVSUB="$REPO/benchmarks/stencil_oversub/bench_stencil_oversub"

: "${OUT:=$REPO/results/analysis/gate_b9_oversub_mechanism}"
CSV="$OUT/task2_mechanism_times.csv"
TELEM_DIR="$OUT/telemetry_task2_mechanism"

WARMUP_ROTATIONS=2
TARGET_ROTATIONS=10
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
    echo "run_order_idx,timestamp_iso8601,config,bench,size,rep_in_cell,phase,wall_s,internal_time_ms,bandwidth_gbs,exit_code,atomic_processed,atomic_enqueued,atomic_drops,telemetry_prefix,srcversion,dmesg_delta,mem_avail_before_kb,mem_avail_after_kb" > "$CSV"
}

# Bespoke reload (adds specasync_trace_faults=1, which the shared
# reload_module in lib_specasync_harness.sh does not support) -- every
# config switch reloads, matching this project's standing convention.
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
    local trace_file="$OUT/c3_${bench}_task2_trace.bin"
    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] collect_oracle_trace bench=$bench -> $trace_file"
        echo "$trace_file"
        return
    fi
    # A single reload_module_t2 call suffices -- it already sets
    # specasync_trace_faults=1 unconditionally, so the separate second
    # rmmod+insmod pair this used to do (only to flip log_enabled off) was
    # redundant AND the source of a double-reload race that, combined with
    # a leaked nsys helper process holding nvidia_uvm open, silently
    # produced a 0-entry oracle trace in an earlier attempt at this gate.
    reload_module_t2 0 0 0
    harness_log "collecting oracle trace ($bench $args) -- oversubscribed, may take a while"
    setarch -R "$bin" $args >/dev/null
    sleep 0.2
    sudo -n cat "$DBGFS/specasync_fault_trace" > "$trace_file" 2>/dev/null || true
    local nent=$(( $(wc -c < "$trace_file" 2>/dev/null || echo 0) / 8 ))
    harness_log "oracle trace for $bench: $nent entries -> $trace_file"
    echo "$trace_file"
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

    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] run_mechanism_case cfg=$cfg rep=$rep phase=$phase"
        echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$rep,$phase,0,0,0,0,0,0,0,$prefix,DRYRUN,0,0,0" >> "$CSV"
        return
    fi

    local wall exit_code
    set +e
    run_with_memory_watchdog 6291456 "$marker" -- \
        /usr/bin/time -f "%e" setarch -R "$BENCH_OVSUB" "$N_OVSUB" "$ITERS" \
        > "$out_file" 2>"${out_file}.stderr"
    exit_code=$?

    if [ "$exit_code" = 137 ]; then
        local wd_floor="" wd_avail="" wd_pgid=""
        mem_watchdog_read_marker "$marker" wd_floor wd_avail wd_pgid
        harness_log_nofork "WATCHDOG FIRED run_order=$RUN_ORDER_IDX cfg=$cfg floor_kb=$wd_floor avail_kb=$wd_avail pgid=$wd_pgid"
        harness_log_nofork "ABORT: per standing directive, stop rather than retry at a lower setting -- report and stop"
        printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
            "$RUN_ORDER_IDX" "$ts" "$cfg" "bench_stencil_oversub" "$N_OVSUB" "$rep" "$phase" \
            "" "" "" "$exit_code" "" "" "" "$prefix" "$srcv" "" "$mem_before" "$wd_avail" >> "$CSV"
        exit 1
    fi
    set -e

    wall=$(grep -oP '^[0-9]+\.[0-9]+$' "${out_file}.stderr" | tail -1)

    ddelta=$(dmesg_delta_count)
    mem_after=$(mem_available_kb)

    local internal_ms bw
    internal_ms=$(grep -oP '(?<=Time: )[0-9.]+' "$out_file" || echo "")
    bw=$(grep -oP '(?<=Bandwidth: )[0-9.]+' "$out_file" || echo "")

    local proc_n enq_n drop_n
    proc_n=$(sudo -n cat "$DBGFS/specasync_processed" 2>/dev/null || echo "")
    enq_n=$(sudo -n cat "$DBGFS/specasync_enqueued" 2>/dev/null || echo "")
    drop_n=$(sudo -n cat "$DBGFS/specasync_drops" 2>/dev/null || echo "")

    harness_log "run_order=$RUN_ORDER_IDX cfg=$cfg rep=$rep wall=${wall}s exit=$exit_code processed=$proc_n enqueued=$enq_n drops=$drop_n dmesg_delta=$ddelta mem_avail=${mem_after}kB"

    echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$rep,$phase,$wall,$internal_ms,$bw,$exit_code,$proc_n,$enq_n,$drop_n,$prefix,$srcv,$ddelta,$mem_before,$mem_after" >> "$CSV"

    dump_ring "$DBGFS/specasync_log" "$TELEM_DIR/${prefix}_batch.bin"
    dump_ring "$DBGFS/specasync_worker_log" "$TELEM_DIR/${prefix}_work.bin"
    dump_ring "$DBGFS/specasync_decomp_log" "$TELEM_DIR/${prefix}_decomp.bin"
    dump_ring "$DBGFS/specasync_fault_trace" "$TELEM_DIR/${prefix}_trace.bin"
    clear_ring
    check_memory_or_abort
}

csv_header
trace_file="$(collect_oracle_trace bench_stencil_oversub "$BENCH_OVSUB" "$N_OVSUB $ITERS")"

declare -A rep_count=( [C1]=0 [C3]=0 )

harness_log "=== Gate B9 Task 2: mechanism instrumentation, N=$N_OVSUB iters=$ITERS, interleaved C1,C3 x $TOTAL_ROTATIONS rotations ==="

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
