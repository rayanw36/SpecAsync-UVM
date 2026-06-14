#!/usr/bin/env bash
# gate3_continue.sh — Continues Gate 3 from C0 GraphBFS onward.
# C0 stencil data is already in the CSV; this script appends the rest.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BENCH_STENCIL="$REPO/benchmarks/bench_stencil"
BENCH_BFS="$REPO/benchmarks/graph_bfs/bench_graph_bfs"
KO_B2="$REPO/driver/build/nvidia-uvm-specasync-phaseB2.ko"
DBG=/sys/kernel/debug/specasync
OUT="$REPO/results/phaseB2/gate3"; mkdir -p "$OUT"

N_STENCIL="${1:-24000}"
N_BFS="${2:-23}"
RUNS="${3:-15}"

POL=/sys/module/nvidia_uvm/parameters/specasync_policy
DEPTH=/sys/module/nvidia_uvm/parameters/specasync_offload_depth
TIME_BIN=/usr/bin/time
CSV="$OUT/gate3_times.csv"
# Append to existing CSV (do NOT overwrite header)

log(){ echo "[gate3] $*"; }

reload_b2(){
    local policy="${1:-0}" depth="${2:-0}" prefetch="${3:-0}" trace_path="${4:-}"
    log "reload: policy=$policy depth=$depth prefetch=$prefetch trace=${trace_path:-none}"
    rmmod nvidia_uvm 2>/dev/null || true
    local extra_args="specasync_policy=$policy specasync_offload_depth=$depth uvm_perf_prefetch_enable=$prefetch specasync_log_enabled=1"
    [ -n "$trace_path" ] && extra_args="$extra_args specasync_oracle_trace_path=$trace_path"
    insmod "$KO_B2" $extra_args
    sleep 0.3
}

time_run(){
    local cfg="$1" bench="$2" run="$3" args="$4"
    local bin; [ "$bench" = "bench_stencil" ] && bin="$BENCH_STENCIL" || bin="$BENCH_BFS"
    local wall
    wall=$({ $TIME_BIN -f "%e" setarch -R "$bin" $args >/dev/null; } 2>&1 | tail -1)
    echo "$cfg,$bench,$run,$wall" >> "$CSV"
    echo "  $cfg $bench run=$run wall=${wall}s"
}

# ── C0 GraphBFS ──────────────────────────────────────────────────
log "=== C0: GraphBFS, prefetch ON ==="
reload_b2 0 0 1
for run in $(seq 1 $RUNS); do
    time_run C0 bench_graph_bfs $run "$N_BFS"
done

# ── C1/C2 interleaved (stencil) ──────────────────────────────────
log "=== C1/C2 interleaved: stencil, prefetch OFF ==="
reload_b2 0 0 0
for run in $(seq 1 $RUNS); do
    echo 0 | tee "$POL" >/dev/null; echo 0 | tee "$DEPTH" >/dev/null
    time_run C1 bench_stencil $run "$N_STENCIL"
    echo 2 | tee "$POL" >/dev/null; echo 1 | tee "$DEPTH" >/dev/null
    time_run C2 bench_stencil $run "$N_STENCIL"
done

# ── C1/C2 interleaved (GraphBFS) ─────────────────────────────────
log "=== C1/C2 interleaved: GraphBFS, prefetch OFF ==="
reload_b2 0 0 0
for run in $(seq 1 $RUNS); do
    echo 0 | tee "$POL" >/dev/null; echo 0 | tee "$DEPTH" >/dev/null
    time_run C1 bench_graph_bfs $run "$N_BFS"
    echo 2 | tee "$POL" >/dev/null; echo 1 | tee "$DEPTH" >/dev/null
    time_run C2 bench_graph_bfs $run "$N_BFS"
done

# ── C3 oracle (stencil) ──────────────────────────────────────────
run_c3(){
    local bench="$1" args="$2"
    local trace_file="$OUT/c3_${bench}_trace.bin"
    local bin; [ "$bench" = "bench_stencil" ] && bin="$BENCH_STENCIL" || bin="$BENCH_BFS"

    log "C3 trace collect: $bench"
    rmmod nvidia_uvm
    insmod "$KO_B2" specasync_policy=0 specasync_offload_depth=0 \
        uvm_perf_prefetch_enable=0 specasync_trace_faults=1 specasync_log_enabled=0
    sleep 0.2
    setarch -R "$bin" $args >/dev/null
    sleep 0.3
    cat "$DBG/specasync_fault_trace" > "$trace_file" 2>/dev/null || true
    local nent=$(( $(wc -c < "$trace_file") / 8 ))
    log "trace: $nent entries"

    log "C3 replay: $bench (depth=1, oracle)"
    rmmod nvidia_uvm
    insmod "$KO_B2" specasync_policy=4 specasync_offload_depth=1 \
        uvm_perf_prefetch_enable=0 specasync_oracle_trace_path="$trace_file" \
        specasync_log_enabled=1
    sleep 0.3

    for run in $(seq 1 $RUNS); do
        time_run C3 "$bench" $run "$args"
    done
}

log "=== C3: oracle+depth=1, stencil ==="
run_c3 bench_stencil "$N_STENCIL"

log "=== C3: oracle+depth=1, GraphBFS ==="
run_c3 bench_graph_bfs "$N_BFS"

# ── Analysis ──────────────────────────────────────────────────────
log "=== Gate 3 analysis ==="
python3 - "$CSV" <<'PY'
import sys, csv, statistics as st

fname = sys.argv[1]
data = {}
with open(fname) as f:
    for row in csv.DictReader(f):
        key = (row['config'], row['bench'])
        data.setdefault(key, []).append(float(row['wall_s']))

configs = ['C0','C1','C2','C3']
benches = ['bench_stencil','bench_graph_bfs']
bnames  = {'bench_stencil': 'Stencil-24K', 'bench_graph_bfs': 'GraphBFS-23'}

baseline = {b: st.median(data[('C0', b)]) for b in benches if ('C0', b) in data}

print(f"\n{'Config':<8} {'Benchmark':<20} {'n':>3} {'median_s':>10} {'vs C0':>8} {'vs C1':>8}")
print("-" * 62)

c1_med = {}
for c in configs:
    for b in benches:
        k = (c, b)
        if k not in data: continue
        vals = data[k]; med = st.median(vals)
        if c == 'C1': c1_med[b] = med
        base = baseline.get(b)
        c1 = c1_med.get(b)
        vs_c0 = f"{100*(med-base)/base:+.1f}%" if base else " N/A"
        vs_c1 = f"{100*(med-c1)/c1:+.1f}%" if (c1 and c != 'C1') else "  ---"
        ci = 1.96*st.stdev(vals)/len(vals)**0.5 if len(vals)>1 else 0
        print(f"{c:<8} {bnames.get(b,b):<20} {len(vals):>3} {med:>10.3f}   {vs_c0:>7}  {vs_c1:>7}  (±{ci:.3f}s)")

print("\n=== DECISIVE VERDICT: C3 vs C0 ===")
for b in benches:
    k3,k0 = ('C3',b),('C0',b)
    if k3 not in data or k0 not in data: continue
    c3=st.median(data[k3]); c0=st.median(data[k0])
    d=100*(c3-c0)/c0
    v = "WINS vs real-world default ✓" if d<-2 else \
        "ties (within noise)"         if abs(d)<2 else \
        "LOSES to real-world default ✗"
    print(f"  {bnames.get(b,b)}: C3={c3:.3f}s  C0={c0:.3f}s  Δ={d:+.1f}%  → {v}")

print("\n(C0=prefetch-on baseline; C1=prefetch-off no-spec; C2=stride+depth=1; C3=oracle+depth=1)")
PY

log "Gate 3 complete. raw CSV: $CSV"
# Restore to a clean state
echo 0 | tee "$POL" >/dev/null 2>/dev/null || true
echo 0 | tee "$DEPTH" >/dev/null 2>/dev/null || true
