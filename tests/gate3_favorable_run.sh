#!/usr/bin/env bash
# gate3_favorable_run.sh — Gate 3: the decisive favorable experiment.
#
# Compares four configurations on stencil + GraphBFS:
#   C0: stock module, prefetch ON  (real-world default to beat)
#   C1: depth=0, prefetch OFF      (baseline showing prefetch-off cost)
#   C2: depth=1, stride, prefetch OFF (realistic speculation)
#   C3: depth=1, oracle, prefetch OFF (upper bound, requires reload)
#
# C1 and C2 are INTERLEAVED (runtime param switch, no reload).
# C0 and C3 are run in separate blocks (prefetch or oracle trace requires reload).
# Decisive comparison: C3 vs C0 — does perfect prediction at depth=1
# without the stock prefetcher beat the stock default?
#
# Usage: sudo bash gate3_favorable_run.sh [stencil_N] [bfs_nodes] [runs_per_config]
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BENCH_STENCIL="$REPO/benchmarks/bench_stencil"
BENCH_BFS="$REPO/benchmarks/graph_bfs/bench_graph_bfs"
KO_B2="$REPO/driver/build/nvidia-uvm-specasync-phaseB2.ko"
KO_STOCK="$REPO/driver/stock_backup/nvidia-uvm.ko.stock"
DBG=/sys/kernel/debug/specasync
OUT="$REPO/results/phaseB2/gate3"; mkdir -p "$OUT"

N_STENCIL="${1:-24000}"
N_BFS="${2:-23}"
RUNS="${3:-15}"

POL=/sys/module/nvidia_uvm/parameters/specasync_policy
DEPTH=/sys/module/nvidia_uvm/parameters/specasync_offload_depth

TIME_BIN=/usr/bin/time
CSV="$OUT/gate3_times.csv"
echo "config,bench,run,wall_s" > "$CSV"

log(){ echo "[gate3] $*"; }

reload_b2(){
    local policy="${1:-0}" depth="${2:-0}" prefetch="${3:-0}" trace_path="${4:-}"
    log "reload: policy=$policy depth=$depth prefetch=$prefetch trace=${trace_path:-none}"
    rmmod nvidia_uvm 2>/dev/null || true
    local extra_args="specasync_policy=$policy specasync_offload_depth=$depth uvm_perf_prefetch_enable=$prefetch specasync_log_enabled=1"
    if [ -n "$trace_path" ]; then
        extra_args="$extra_args specasync_oracle_trace_path=$trace_path"
    fi
    insmod "$KO_B2" $extra_args
    sleep 0.3
}

time_run(){
    local cfg="$1" bench="$2" run="$3" args="$4"
    local bin="$([ "$bench" = "bench_stencil" ] && echo "$BENCH_STENCIL" || echo "$BENCH_BFS")"
    local wall
    wall=$({ $TIME_BIN -f "%e" setarch -R "$bin" $args >/dev/null; } 2>&1 | tail -1)
    echo "$cfg,$bench,$run,$wall" >> "$CSV"
    echo "  $cfg $bench run=$run wall=${wall}s"
}

# ────────────────────────────────────────────────────────────────
# C0 block: stock prefetch ON, speculation OFF
# ────────────────────────────────────────────────────────────────
log "=== C0: prefetch ON, speculation OFF ==="
reload_b2 0 0 1
for run in $(seq 1 $RUNS); do
    time_run C0 bench_stencil $run "$N_STENCIL"
done
for run in $(seq 1 $RUNS); do
    time_run C0 bench_graph_bfs $run "$N_BFS"
done

# ────────────────────────────────────────────────────────────────
# C1/C2 interleaved: prefetch OFF, alternating p0/depth=0 and p2/depth=1
# ────────────────────────────────────────────────────────────────
log "=== C1/C2 interleaved: prefetch OFF (30 pairs each bench) ==="
reload_b2 0 0 0   # start: p0, depth=0, prefetch off

for run in $(seq 1 $RUNS); do
    # C1: policy=0, depth=0
    echo 0 | tee "$POL" >/dev/null
    echo 0 | tee "$DEPTH" >/dev/null
    time_run C1 bench_stencil $run "$N_STENCIL"
    # C2: policy=2 (stride), depth=1
    echo 2 | tee "$POL" >/dev/null
    echo 1 | tee "$DEPTH" >/dev/null
    time_run C2 bench_stencil $run "$N_STENCIL"
done

for run in $(seq 1 $RUNS); do
    echo 0 | tee "$POL" >/dev/null; echo 0 | tee "$DEPTH" >/dev/null
    time_run C1 bench_graph_bfs $run "$N_BFS"
    echo 2 | tee "$POL" >/dev/null; echo 1 | tee "$DEPTH" >/dev/null
    time_run C2 bench_graph_bfs $run "$N_BFS"
done

# ────────────────────────────────────────────────────────────────
# C3 oracle: trace collect → reload → run
# ────────────────────────────────────────────────────────────────
log "=== C3: oracle, depth=1, prefetch OFF ==="

run_c3_bench(){
    local bench="$1" args="$2"
    local trace_file="$OUT/c3_${bench}_trace.bin"
    # Collect trace under policy=0, trace_faults=1
    reload_b2 0 0 0
    rmmod nvidia_uvm; insmod "$KO_B2" specasync_policy=0 specasync_offload_depth=0 \
        uvm_perf_prefetch_enable=0 specasync_trace_faults=1 specasync_log_enabled=0
    log "collecting oracle trace for $bench..."
    setarch -R "$([ "$bench" = "bench_stencil" ] && echo "$BENCH_STENCIL" || echo "$BENCH_BFS")" $args >/dev/null
    sleep 0.2
    # Save trace
    sudo cat "$DBG/specasync_fault_trace" > "$trace_file" 2>/dev/null || true
    local nent=$(( $(wc -c < "$trace_file") / 8 ))
    log "trace: $nent entries → $trace_file"

    # Reload with oracle policy, depth=1
    rmmod nvidia_uvm
    insmod "$KO_B2" specasync_policy=4 specasync_offload_depth=1 \
        uvm_perf_prefetch_enable=0 specasync_oracle_trace_path="$trace_file" \
        specasync_log_enabled=1
    sleep 0.3

    for run in $(seq 1 $RUNS); do
        time_run C3 "$bench" $run "$args"
    done
}

run_c3_bench bench_stencil "$N_STENCIL"
run_c3_bench bench_graph_bfs "$N_BFS"

# ────────────────────────────────────────────────────────────────
# Analysis
# ────────────────────────────────────────────────────────────────
log "=== Gate 3 analysis ==="
python3 - "$CSV" "$RUNS" <<'PY'
import sys, csv, statistics as st

fname = sys.argv[1]
runs  = int(sys.argv[2])

data = {}
with open(fname) as f:
    for row in csv.DictReader(f):
        key = (row['config'], row['bench'])
        data.setdefault(key, []).append(float(row['wall_s']))

configs = ['C0','C1','C2','C3']
benches = ['bench_stencil','bench_graph_bfs']

print(f"\n{'Config':<8} {'Benchmark':<20} {'n':>3} {'median_s':>10} {'pct_vs_C0':>10}")
print("-" * 56)

baseline = {}
for b in benches:
    k = ('C0', b)
    if k in data:
        baseline[b] = st.median(data[k])

for c in configs:
    for b in benches:
        k = (c, b)
        if k not in data: continue
        vals = data[k]
        med = st.median(vals)
        base = baseline.get(b)
        pct = f"{100*(med-base)/base:+.1f}%" if base else "N/A"
        ci = 1.96 * st.stdev(vals) / len(vals)**0.5 if len(vals) > 1 else 0
        print(f"{c:<8} {b:<20} {len(vals):>3} {med:>10.3f}   {pct:>10}  (±{ci:.3f}s)")

print("\n=== Decisive comparison: C3 vs C0 ===")
for b in benches:
    kc3 = ('C3', b); kc0 = ('C0', b)
    if kc3 not in data or kc0 not in data: continue
    c3 = st.median(data[kc3]); c0 = st.median(data[kc0])
    delta_pct = 100*(c3-c0)/c0
    verdict = "BEATS C0 ✓" if delta_pct < -2 else \
              "TIES C0" if abs(delta_pct) < 2 else "LOSES to C0"
    print(f"  {b}: C3={c3:.3f}s  C0={c0:.3f}s  Δ={delta_pct:+.1f}%  → {verdict}")

print("\n=== C3 vs C1 (depth=1 overhead relative to no-prefetch baseline) ===")
for b in benches:
    kc3=('C3',b); kc1=('C1',b)
    if kc3 not in data or kc1 not in data: continue
    c3=st.median(data[kc3]); c1=st.median(data[kc1])
    print(f"  {b}: C3={c3:.3f}s  C1={c1:.3f}s  Δ={100*(c3-c1)/c1:+.1f}%")

print("\n=== C2 vs C1 (stride+depth=1 overhead vs no-speculation, prefetch off) ===")
for b in benches:
    kc2=('C2',b); kc1=('C1',b)
    if kc2 not in data or kc1 not in data: continue
    c2=st.median(data[kc2]); c1=st.median(data[kc1])
    print(f"  {b}: C2={c2:.3f}s  C1={c1:.3f}s  Δ={100*(c2-c1)/c1:+.1f}%")
PY

log "raw CSV: $CSV"
echo 0 | tee "$POL" >/dev/null 2>/dev/null || true
