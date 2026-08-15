#!/usr/bin/env bash
# t_b9_task1_checksum.sh -- Gate B9 Task 1(a,b,d): output equivalence check
# for C1 vs C3 at ~1.08x oversubscription (N=48000, matches
# OVERSUB_SPEEDUP_VERIFICATION.md Sections 5-6). Uses
# bench_stencil_oversub_checksum (disclosed benchmark modification -- see
# that .cu file's header) to capture a checksum of the final output buffer,
# iteration/kernel-launch counts, and peak VRAM residency (via an nvidia-smi
# poller) for every run. Does NOT measure H2D/D2H migrated bytes -- that is
# t_b9_task1_nsys.sh, run separately against the UNMODIFIED benchmark binary
# so the checksum readback doesn't contaminate the migration-byte count.
#
# Usage: bash tests/t_b9_task1_checksum.sh <N> [iters]
#        DRY_RUN=1 bash tests/t_b9_task1_checksum.sh <N>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_OVSUB="${1:?usage: t_b9_task1_checksum.sh <N> [iters]}"
ITERS="${2:-20}"

: "${KO:?KO must be set explicitly to the platform-correct .ko path -- the driver/build/ default in this repo is a stale AWS build}"
BENCH_OVSUB="$REPO/benchmarks/stencil_oversub/bench_stencil_oversub_checksum"

: "${OUT:=$REPO/results/analysis/gate_b9_oversub_mechanism}"
CSV="$OUT/task1_checksum_times.csv"
TELEM_DIR="$OUT/telemetry_task1_checksum"
SMI_DIR="$OUT/task1_smi_polls"

WARMUP_ROTATIONS=2
TARGET_ROTATIONS=10
TOTAL_ROTATIONS=$((WARMUP_ROTATIONS + TARGET_ROTATIONS))

declare -A POLICY=( [C1]=0 [C3]=4 )
declare -A DEPTH=(  [C1]=0 [C3]=1 )
declare -A PREFETCH=([C1]=0 [C3]=0 )

mkdir -p "$OUT" "$TELEM_DIR" "$SMI_DIR"

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
    echo "run_order_idx,timestamp_iso8601,config,bench,size,rep_in_cell,phase,wall_s,internal_time_ms,bandwidth_gbs,elems,checksum_sum,checksum_fnv1a64,iters_reported,kernel_launches,exit_code,peak_mem_used_mib,srcversion,dmesg_delta,mem_avail_before_kb,mem_avail_after_kb" > "$CSV"
}

collect_oracle_trace() {
    local bench="$1" bin="$2" args="$3"
    local trace_file="$OUT/c3_${bench}_task1_trace.bin"
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

# run_checksum_case <cfg> <trace_arg> <rep_label> <phase>
run_checksum_case() {
    local cfg="$1" trace_arg="$2" rep="$3" phase="$4"
    RUN_ORDER_IDX=$((RUN_ORDER_IDX + 1))
    local ts srcv mem_before mem_after ddelta
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    reload_module "$KO" "${POLICY[$cfg]}" "${DEPTH[$cfg]}" "${PREFETCH[$cfg]}" "$trace_arg"
    srcv=$(current_srcversion)
    mem_before=$(mem_available_kb)
    dmesg_mark

    local out_file="$TELEM_DIR/stdout_${cfg}_run${RUN_ORDER_IDX}.txt"
    local smi_file="$SMI_DIR/smi_${cfg}_run${RUN_ORDER_IDX}.csv"

    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] run_checksum_case cfg=$cfg rep=$rep phase=$phase"
        echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$rep,$phase,0,0,0,0,0,0000000000000000,0,0,0,0,DRYRUN,0,0,0" >> "$CSV"
        return
    fi

    # Background VRAM poller: 200ms samples for the duration of this run.
    nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -lms 200 \
        > "$smi_file" 2>/dev/null &
    local smi_pid=$!

    local wall exit_code
    set +e
    /usr/bin/time -f "%e" setarch -R "$BENCH_OVSUB" "$N_OVSUB" "$ITERS" \
        > "$out_file" 2>"${out_file}.stderr"
    exit_code=$?
    set -e
    echo "EXIT:$exit_code" >> "${out_file}.stderr"
    wall=$(grep -oP '^[0-9]+\.[0-9]+$' "${out_file}.stderr" | tail -1)

    kill "$smi_pid" 2>/dev/null || true
    wait "$smi_pid" 2>/dev/null || true

    ddelta=$(dmesg_delta_count)
    mem_after=$(mem_available_kb)

    local internal_ms bw elems csum_sum csum_fnv iters_rep klaunch peak_mib
    internal_ms=$(grep -oP '(?<=Time: )[0-9.]+' "$out_file" || echo "")
    bw=$(grep -oP '(?<=Bandwidth: )[0-9.]+' "$out_file" || echo "")
    elems=$(grep -oP '(?<=elems=)[0-9]+' "$out_file" || echo "")
    csum_sum=$(grep -oP '(?<=sum=)[-0-9.eE+]+' "$out_file" || echo "")
    csum_fnv=$(grep -oP '(?<=fnv1a64=)[0-9a-f]+' "$out_file" || echo "")
    iters_rep=$(grep -oP '(?<=iters=)[0-9]+' "$out_file" || echo "")
    klaunch=$(grep -oP '(?<=kernel_launches=)[0-9]+' "$out_file" || echo "")
    peak_mib=$(awk -F',' 'NF{gsub(/ /,"",$1); if ($1+0>max) max=$1+0} END{print max+0}' "$smi_file")

    harness_log "run_order=$RUN_ORDER_IDX cfg=$cfg rep=$rep wall=${wall}s internal_ms=$internal_ms exit=$exit_code peak_mib=$peak_mib fnv=$csum_fnv dmesg_delta=$ddelta mem_avail=${mem_after}kB"

    echo "$RUN_ORDER_IDX,$ts,$cfg,bench_stencil_oversub,$N_OVSUB,$rep,$phase,$wall,$internal_ms,$bw,$elems,$csum_sum,$csum_fnv,$iters_rep,$klaunch,$exit_code,$peak_mib,$srcv,$ddelta,$mem_before,$mem_after" >> "$CSV"

    dump_ring "$DBGFS/specasync_log" "$TELEM_DIR/${cfg}_run${RUN_ORDER_IDX}.bin"
    clear_ring
    check_memory_or_abort
}

csv_header
trace_file="$(collect_oracle_trace bench_stencil_oversub "$BENCH_OVSUB" "$N_OVSUB $ITERS")"

declare -A rep_count=( [C1]=0 [C3]=0 )

harness_log "=== Gate B9 Task 1: output-equivalence, checksum binary, N=$N_OVSUB iters=$ITERS, interleaved C1,C3 x $TOTAL_ROTATIONS rotations ==="

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
        run_checksum_case "$cfg" "$trace_arg" "$rep_label" "$phase"
    done
done

harness_log "done. CSV: $CSV"
harness_log "kept reps/cell should be $TARGET_ROTATIONS; warm-up reps/cell = $WARMUP_ROTATIONS"
