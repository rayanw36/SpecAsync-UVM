#!/usr/bin/env bash
# t2_cufft_interleaved.sh — Task T2: cuFFT interleaved rerun on T4.
#
# Per CUFFT_PROVENANCE.md (Gate 1, Figure Phase 2): cuFFT has no trustworthy
# T4 wall-clock number under any protocol -- it ran on the T4 only during
# the pre-fix Phase B sweep (blocked, not interleaved) and was dropped from
# every later gate. The 25.47% hit-rate outlier in phaseB_telemetry.csv is
# policy p2 (stride), not the oracle (p4).
#
# Primary comparison (this task's whole point): p0 vs p2, PREFETCHER ON,
# interleaved, n>=15 -- the exact configuration the 25.47% hit rate was
# measured in, where a wall-clock benefit would show up if one existed.
# Secondary: C0 (=p0, prefetch ON) and C1 (=p0, prefetch OFF) for
# continuity with the rest of the paper's C0-C3 naming.
#
# Sizes: the three Phase B cuFFT sizes (67108864, 134217728, 268435456
# elements). 67108864 * 8 bytes/cufftComplex = 536,870,912 bytes ~= 0.537
# GiB -- already the size closest to the legacy ~0.54 GB working set, so no
# additional size is needed beyond the existing three.
#
# Usage: sudo bash tests/t2_cufft_interleaved.sh [n_reps]
#        DRY_RUN=1 bash tests/t2_cufft_interleaved.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_specasync_harness.sh"

N_REPS="${1:-15}"
WARMUP=2
TOTAL_REPS=$((N_REPS + WARMUP))

: "${KO:=$REPO/driver/build/nvidia-uvm-specasync-t4.ko}"
BENCH_CUFFT="$REPO/benchmarks/bench_cufft"
SIZES=(67108864 134217728 268435456)

: "${OUT:=$REPO/results/phaseB2/cufft_interleaved}"
CSV="$OUT/cufft_interleaved_times.csv"
TELEM_DIR="$OUT/telemetry"
mkdir -p "$OUT" "$TELEM_DIR"
csv_init "$CSV" "hit_rate,enqueues,hits"

build_cufft_sm75() {
    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] build cuFFT for -arch=sm_75"
        return
    fi
    harness_log "building bench_cufft for -arch=sm_75"
    ( cd "$REPO/benchmarks" && nvcc -O3 -arch=sm_75 -o bench_cufft bench_cufft.cu -lcufft )
}

# ---- hit-rate extraction from the specasync_log ring ----------------------
# Reuses the BFMT struct convention from tests/gate_d_analyze.py ('<6Q6I',
# 72 bytes): batch_id,t0,t1,t2,t3,t4 / num_faults,spec_enqueues,spec_drops,
# spec_hits,enqueue_overhead_ns,_pad.
hit_rate_from_ring() {
    local bin_path="$1"
    if [ "$DRY_RUN" = "1" ] || [ ! -s "$bin_path" ]; then
        echo "0.0,0,0"
        return
    fi
    python3 - "$bin_path" <<'PY'
import struct, sys
BFMT='<6Q6I'; BSZ=struct.calcsize(BFMT)
raw = open(sys.argv[1], 'rb').read()
enq = hits = 0
for i in range(len(raw)//BSZ):
    v = struct.unpack(BFMT, raw[i*BSZ:(i+1)*BSZ])
    _, t0, _, _, _, t4, _, seq, _, shit, _, _ = v
    if t0 == 0 or t4 < t0:
        continue
    enq += seq
    hits += shit
rate = hits/enq if enq else 0.0
print(f"{rate:.5f},{enq},{hits}")
PY
}


# Abort guard added for the post-reboot rerun, per HOST_MEMORY_LEAK_5070TI.md:
# the ~230-250MB/reload-cycle host leak means a 204-run session can run the
# host out of memory before completion. Checked after every run (both
# primary and secondary configs) -- stopping cleanly at a run boundary is
# better than pushing through under pressure, since the pressure itself is a
# confound on the timing data.
: "${ABORT_MIN_AVAIL_KB:=6291456}"  # 6 GiB
check_memory_or_abort() {
    if [ "$DRY_RUN" = "1" ]; then
        return
    fi
    local avail
    avail=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    if [ "$avail" -lt "$ABORT_MIN_AVAIL_KB" ]; then
        harness_log "ABORT: MemAvailable=${avail}kB < ${ABORT_MIN_AVAIL_KB}kB threshold at run_order=$RUN_ORDER_IDX -- stopping per HOST_MEMORY_LEAK_5070TI.md abort condition (see leak_probe.csv / harness CSV mem_avail_after_kb column for the full trajectory)"
        exit 1
    fi
}

run_config() {
    local size="$1" cfg="$2" policy="$3" depth="$4" prefetch="$5" rep="$6" phase="$7"
    reload_module "$KO" "$policy" "$depth" "$prefetch"
    time_run "$CSV" "$BENCH_CUFFT" "$size" "$cfg" bench_cufft "$size" "${phase}_${rep}" "PENDING"
    local dump="$TELEM_DIR/cufft_${size}_${cfg}_run${RUN_ORDER_IDX}.bin"
    dump_ring "$DBGFS/specasync_log" "$dump"
    local hr
    hr="$(hit_rate_from_ring "$dump")"
    clear_ring
    # Patch the just-written CSV row's placeholder hit-rate fields in place
    # (last row = the one time_run just appended).
    if [ "$DRY_RUN" != "1" ]; then
        sed -i "\$s/,PENDING\$/,$hr/" "$CSV"
    else
        sed -i "\$s/,PENDING\$/,0.0,0,0/" "$CSV"
    fi
    check_memory_or_abort
}

build_cufft_sm75

for size in "${SIZES[@]}"; do
    harness_log "=== T2 size=$size: primary p0-vs-p2 prefetch-ON interleaved (n=$N_REPS + $WARMUP warmup) ==="
    for rep in $(seq 1 $TOTAL_REPS); do
        phase="warmup"; [ "$rep" -gt "$WARMUP" ] && phase="kept"
        # p0: policy=0 (no speculation), prefetch ON
        run_config "$size" p0_prefetchON 0 0 1 "$rep" "$phase"
        # p2: policy=2 (stride), depth=0, prefetch ON -- the EXACT configuration
        # the 25.47% hit rate was originally measured in (phaseB_telemetry.csv
        # row "2,0,cuFFT,...": policy=2, depth=0 -- metadata-only lookup, no
        # actual migration). Do not change to depth=1 without re-checking
        # CUFFT_PROVENANCE.md's raw row first.
        run_config "$size" p2_prefetchON 2 0 1 "$rep" "$phase"
    done

    harness_log "=== T2 size=$size: secondary C0/C1 for continuity (n=$N_REPS + $WARMUP warmup) ==="
    for rep in $(seq 1 $TOTAL_REPS); do
        phase="warmup"; [ "$rep" -gt "$WARMUP" ] && phase="kept"
        # C0: stock, prefetch ON (policy=0 depth=0, matches gate3 C0)
        run_config "$size" C0 0 0 1 "$rep" "$phase"
        # C1: no speculation, prefetch OFF (matches gate3 C1)
        run_config "$size" C1 0 0 0 "$rep" "$phase"
    done
done

harness_log "done. CSV: $CSV"
harness_log "verdict to report at Gate T2: does the 25.47% hit rate reproduce for p2 (prefetch ON)?"
harness_log "and: does it correspond to ANY wall-clock effect vs p0 (expected: no)?"
