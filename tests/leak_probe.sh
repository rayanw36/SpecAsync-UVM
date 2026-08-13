#!/usr/bin/env bash
# leak_probe.sh -- one-shot characterization of the reload+CUDA-run memory
# leak found while running Task 4 (cuFFT) on the 5070 Ti. NOT a standing gate
# harness -- ad hoc, produces results/analysis/leak_probe/leak_probe.csv,
# consumed by results/analysis/HOST_MEMORY_LEAK_5070TI.md. Scope is fixed by
# that report's brief: 4 conditions x n=5 cycles, /proc/meminfo deltas only,
# no ftrace/kmemleak/bisection.
#
# Usage: bash tests/leak_probe.sh <condition> <ko_path> [extra_insmod_params]
#   condition: reload_only | reload_cufft | reload_stencil | cuda_no_reload
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_CUFFT="$REPO/benchmarks/bench_cufft"
BENCH_STENCIL="$REPO/benchmarks/bench_stencil"
CUFFT_SIZE=134217728
STENCIL_N=24000
OUT="$REPO/results/analysis/leak_probe"
CSV="$OUT/leak_probe.csv"
mkdir -p "$OUT"

COND="$1"
KO="$2"
EXTRA="${3:-}"
N_CYCLES=5

if [ ! -f "$CSV" ]; then
    echo "label,condition,cycle,phase,MemFree_kB,MemAvailable_kB,Slab_kB,SReclaimable_kB,SUnreclaim_kB,KernelStack_kB,VmallocUsed_kB,PageTables_kB,Committed_AS_kB,dmesg_delta" > "$CSV"
fi

meminfo_row() {
    python3 - <<'PY'
import re
d = {}
for line in open('/proc/meminfo'):
    m = re.match(r'(\w+):\s+(\d+)', line)
    if m:
        d[m.group(1)] = m.group(2)
fields = ["MemFree","MemAvailable","Slab","SReclaimable","SUnreclaim",
          "KernelStack","VmallocUsed","PageTables","Committed_AS"]
print(",".join(d.get(f, "0") for f in fields))
PY
}

dmesg_count() { sudo -n dmesg | wc -l; }

reload() {
    sudo rmmod nvidia_uvm 2>/dev/null || true
    sudo insmod "$KO" $EXTRA
    sleep 0.3
}

label="$(basename "$KO" .ko)"

log() { echo "[leak_probe $(date '+%H:%M:%S')] $*" >&2; }

snap() {
    local phase="$1" cycle="$2" d0="$3"
    local d1 mi
    d1=$(dmesg_count)
    mi=$(meminfo_row)
    echo "$label,$COND,$cycle,$phase,$mi,$(( d1 - d0 ))" >> "$CSV"
}

case "$COND" in
    reload_only)
        for c in $(seq 1 $N_CYCLES); do
            d0=$(dmesg_count); snap before "$c" "$d0"
            reload
            snap after "$c" "$d0"
            log "reload_only cycle $c done"
        done
        ;;
    reload_cufft)
        for c in $(seq 1 $N_CYCLES); do
            d0=$(dmesg_count); snap before "$c" "$d0"
            reload
            setarch -R "$BENCH_CUFFT" "$CUFFT_SIZE" >/dev/null
            snap after "$c" "$d0"
            log "reload_cufft cycle $c done"
        done
        ;;
    reload_stencil)
        for c in $(seq 1 $N_CYCLES); do
            d0=$(dmesg_count); snap before "$c" "$d0"
            reload
            setarch -R "$BENCH_STENCIL" "$STENCIL_N" >/dev/null
            snap after "$c" "$d0"
            log "reload_stencil cycle $c done"
        done
        ;;
    cuda_no_reload)
        # Single reload at the START of the whole condition, then N_CYCLES
        # CUDA runs with NO reload between them -- isolates whether the leak
        # needs the reload path at all, or accumulates from repeated CUDA
        # execution against one already-loaded module.
        reload
        for c in $(seq 1 $N_CYCLES); do
            d0=$(dmesg_count); snap before "$c" "$d0"
            setarch -R "$BENCH_CUFFT" "$CUFFT_SIZE" >/dev/null
            snap after "$c" "$d0"
            log "cuda_no_reload cycle $c done"
        done
        ;;
    *)
        echo "unknown condition: $COND" >&2
        exit 1
        ;;
esac

log "done. CSV: $CSV"
