#!/usr/bin/env bash
# t_a2_bimodality.sh — Task A2: combined bimodality experiment (H1/H2/H3).
#
# C3/Stencil-24K only. Arms: ASLR-on (default randomize_va_space=2, no
# setarch wrapper -- confirmed this session to actually randomize
# cudaMallocManaged's base) vs ASLR-off (setarch -R, confirmed this session
# to pin the base to a fixed address across runs). Strictly interleaved
# ON,OFF,ON,OFF,... never blocked. Module reloaded before every run
# (uniform mechanism, matches T1/PREREGISTRATION.md's corrected approach --
# module params are read-only after load).
#
# Logs per run: allocation base address (bench_stencil.cu now prints
# [SPECASYNC_ALLOC] to stderr -- Task A2 addition), GPU
# clock/temp/power/pstate/throttle state before+after, CPU load average
# before+after, and full specasync_log + specasync_worker_log telemetry
# (processed/enqueued/drops from the Task A1 kernel atomics, immune to ring
# wrap).
#
# Usage: sudo bash tests/t_a2_bimodality.sh
#        DRY_RUN=1 bash tests/t_a2_bimodality.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

KO="$REPO/driver/build/nvidia-uvm-specasync-t4-a1.ko"
BENCH_STENCIL="$REPO/benchmarks/bench_stencil"
N_STENCIL=24000

OUT="$REPO/results/analysis/t_a2_bimodality"
CSV="$OUT/bimodality.csv"
mkdir -p "$OUT"
csv_init "$CSV" "phase,arm,alloc_grid0,alloc_grid1,base_mod_2mb,processed,enqueued,drops,gpu_sm_before,gpu_sm_after,gpu_mem_before,gpu_mem_after,gpu_temp_before,gpu_temp_after,gpu_power_before,gpu_power_after,gpu_pstate_before,gpu_pstate_after,throttle_before,throttle_after,persistence,loadavg_before,loadavg_after"

WARMUP_ROTATIONS=2
TARGET_ROTATIONS=20
TOTAL_ROTATIONS=$((WARMUP_ROTATIONS + TARGET_ROTATIONS))

GPU_QUERY="clocks.current.sm,clocks.current.memory,temperature.gpu,power.draw,pstate,clocks_throttle_reasons.active,persistence_mode"

gpu_state() {
    nvidia-smi --query-gpu="$GPU_QUERY" --format=csv,noheader,nounits 2>/dev/null | tr -d ' '
}

loadavg() {
    awk '{print $1}' /proc/loadavg
}

collect_oracle_trace() {
    local trace_file="$OUT/c3_bench_stencil_trace.bin"
    if [ "$DRY_RUN" = "1" ]; then
        echo "$trace_file"
        return
    fi
    reload_module "$KO" 0 0 0
    sudo rmmod nvidia_uvm 2>/dev/null || true
    sudo insmod "$KO" specasync_policy=0 specasync_offload_depth=0 \
        uvm_perf_prefetch_enable=0 specasync_trace_faults=1 specasync_log_enabled=0
    sleep 0.3
    setarch "$(uname -m)" -R "$BENCH_STENCIL" "$N_STENCIL" >/dev/null 2>&1
    sleep 0.2
    sudo cat "$DBGFS/specasync_fault_trace" > "$trace_file" 2>/dev/null || true
    local nent=$(( $(wc -c < "$trace_file" 2>/dev/null || echo 0) / 8 ))
    harness_log "oracle trace: $nent entries -> $trace_file"
    echo "$trace_file"
}

run_one() {
    local arm="$1" phase="$2" rep="$3"
    RUN_ORDER_IDX=$((RUN_ORDER_IDX + 1))

    reload_module "$KO" 4 1 0 "$TRACE_FILE"

    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] run_order=$RUN_ORDER_IDX arm=$arm phase=$phase rep=$rep"
        return
    fi

    clear_ring
    local before_gpu before_load
    before_gpu="$(gpu_state)"
    before_load="$(loadavg)"

    dmesg_mark
    local stderr_file="$OUT/.last_stderr"
    local time_file="$OUT/.last_time"
    # /usr/bin/time -o writes its own report to a file, separate from the
    # benchmark's own stderr (needed intact for the [SPECASYNC_ALLOC] line) --
    # mixing both into one stream (the earlier version of this script) left
    # wall_s empty because the outer capture only ever saw one of the two.
    if [ "$arm" = "ASLR_ON" ]; then
        /usr/bin/time -f "%e" -o "$time_file" "$BENCH_STENCIL" "$N_STENCIL" >/dev/null 2>"$stderr_file"
    else
        /usr/bin/time -f "%e" -o "$time_file" setarch "$(uname -m)" -R "$BENCH_STENCIL" "$N_STENCIL" >/dev/null 2>"$stderr_file"
    fi
    local wall
    wall=$(cat "$time_file" 2>/dev/null || echo "0.000000")
    local ddelta
    ddelta=$(dmesg_delta_count)

    local after_gpu after_load
    after_gpu="$(gpu_state)"
    after_load="$(loadavg)"

    local alloc_line grid0 grid1 base_mod
    alloc_line=$(grep SPECASYNC_ALLOC "$stderr_file" || echo "")
    grid0=$(echo "$alloc_line" | sed -n 's/.*grid0=\(0x[0-9a-f]*\).*/\1/p')
    grid1=$(echo "$alloc_line" | sed -n 's/.*grid1=\(0x[0-9a-f]*\).*/\1/p')
    if [ -n "$grid0" ]; then
        base_mod=$(( grid0 % (2*1024*1024) ))
    else
        grid0="0x0"; grid1="0x0"; base_mod=-1
    fi

    local processed enqueued drops
    processed=$(sudo cat "$DBGFS/specasync_processed" 2>/dev/null || echo 0)
    enqueued=$(sudo cat "$DBGFS/specasync_enqueued" 2>/dev/null || echo 0)
    drops=$(sudo cat "$DBGFS/specasync_drops" 2>/dev/null || echo 0)

    dump_ring "$DBGFS/specasync_worker_log" "$OUT/${arm}_run${RUN_ORDER_IDX}_worker.bin"
    dump_ring "$DBGFS/specasync_log" "$OUT/${arm}_run${RUN_ORDER_IDX}_batch.bin"

    IFS=',' read -r sm_b mem_b temp_b pow_b pst_b thr_b pers_b <<< "$before_gpu"
    IFS=',' read -r sm_a mem_a temp_a pow_a pst_a thr_a pers_a <<< "$after_gpu"

    local ts srcv
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    srcv=$(current_srcversion)
    local row="$RUN_ORDER_IDX,$ts,C3,bench_stencil,$N_STENCIL,$rep,$wall,$srcv,$ddelta"
    row="$row,$phase,$arm,$grid0,$grid1,$base_mod,$processed,$enqueued,$drops"
    row="$row,$sm_b,$sm_a,$mem_b,$mem_a,$temp_b,$temp_a,$pow_b,$pow_a,$pst_b,$pst_a,$thr_b,$thr_a,$pers_b,$before_load,$after_load"
    echo "$row" >> "$CSV"
    harness_log "run_order=$RUN_ORDER_IDX arm=$arm phase=$phase rep=$rep wall=${wall}s base=$grid0 (mod2M=$base_mod) processed=$processed enqueued=$enqueued gpu_sm=${sm_b}->${sm_a} temp=${temp_b}->${temp_a}"
}

TRACE_FILE="$(collect_oracle_trace)"

for rotation in $(seq 1 $TOTAL_ROTATIONS); do
    phase="warmup"
    [ "$rotation" -gt "$WARMUP_ROTATIONS" ] && phase="kept"
    run_one "ASLR_ON" "$phase" "$rotation"
    run_one "ASLR_OFF" "$phase" "$rotation"
done

harness_log "done. CSV: $CSV; ring dumps: $OUT/*_run*.bin"
