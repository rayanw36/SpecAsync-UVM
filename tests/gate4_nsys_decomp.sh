#!/usr/bin/env bash
# gate4_nsys_decomp.sh — Gate 4: migration-inclusive cost decomposition.
#
# Uses Nsight Systems (nsys) to profile stencil + GraphBFS under our module
# and extract CPU-side UVM fault time + DMA/HtoD transfer bytes and time.
# The driver timers (T0-T4) give CPU-side only; nsys gives the DMA piece.
#
# After the run, reports:
#   - CPU fault-handling time (from batch telemetry)
#   - HtoD DMA bytes + estimated time (from nsys)
#   - Fraction breakdown: metadata / dispatch CPU / DMA (off-window)
#
# Usage: sudo bash gate4_nsys_decomp.sh [stencil_N]
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BENCH_STENCIL="$REPO/benchmarks/bench_stencil"
BENCH_BFS="$REPO/benchmarks/graph_bfs/bench_graph_bfs"
KO_B2="$REPO/driver/build/nvidia-uvm-specasync-phaseB2.ko"
DBG=/sys/kernel/debug/specasync
OUT="$REPO/results/phaseB2/gate4"; mkdir -p "$OUT"

N_STENCIL="${1:-24000}"
N_BFS="${2:-23}"

log(){ echo "[gate4] $*"; }

# Load module: policy=0 (disabled), prefetch ON (real-world default)
rmmod nvidia_uvm 2>/dev/null || true
insmod "$KO_B2" specasync_policy=0 specasync_offload_depth=0 \
    uvm_perf_prefetch_enable=1 specasync_log_enabled=1
sleep 0.3

profile_bench(){
    local name="$1" bin="$2" args="$3"
    local nsys_out="$OUT/${name}_nsys"
    log "profiling $name with nsys..."

    # Clear ring
    echo 1 | tee "$DBG/specasync_clear" >/dev/null; sleep 0.1

    # Run under nsys (UVM tracing)
    nsys profile \
        --output="$nsys_out" \
        --force-overwrite=true \
        --trace=cuda,nvtx,uvm \
        --stats=false \
        setarch -R "$bin" $args >/dev/null 2>&1 || \
    nsys profile \
        --output="$nsys_out" \
        --force-overwrite=true \
        --trace=cuda,uvm \
        --stats=false \
        setarch -R "$bin" $args >/dev/null 2>&1

    # Snapshot batch telemetry
    sleep 0.3
    cat "$DBG/specasync_log" > "$OUT/${name}_batch.bin"

    # Parse nsys SQLite for DMA info
    local db="${nsys_out}.sqlite"
    if [ -f "$db" ]; then
        log "parsing nsys SQLite: $db"
        python3 - "$db" "$OUT/${name}_batch.bin" "$name" <<'PYEOF'
import sys, struct, statistics as st

db_path, batch_path, name = sys.argv[1], sys.argv[2], sys.argv[3]

# Parse batch telemetry for CPU-side timing
BFMT='<6Q6I'; BSZ=struct.calcsize(BFMT)
braw = open(batch_path,'rb').read()
brecs=[]
for i in range(len(braw)//BSZ):
    v=struct.unpack(BFMT,braw[i*BSZ:(i+1)*BSZ])
    if v[1]==0 or v[5]<v[1]: continue
    brecs.append(v)

t0t4=[r[5]-r[1] for r in brecs]
t1t2=[r[3]-r[2] for r in brecs if r[2]>0 and r[3]>r[2]]
t2t3=[r[4]-r[3] for r in brecs if r[3]>0 and r[4]>r[3]]
nf=sum(r[6] for r in brecs)
enq=sum(r[7] for r in brecs)

print(f"\n=== {name} — CPU-side fault-handling (driver timers) ===")
print(f"  batches: {len(brecs)}  total faults: {nf}  enqueued: {enq}")
if t0t4: print(f"  T0->T4 total    median: {st.median(t0t4)/1e3:8.1f} µs")
if t1t2: print(f"  T1->T2 metadata median: {st.median(t1t2)/1e3:8.1f} µs")
if t2t3: print(f"  T2->T3 dispatch median: {st.median(t2t3)/1e3:8.1f} µs")

# Try to read DMA info from nsys SQLite
try:
    import sqlite3
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    # Check available tables
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print(f"\n=== {name} — Nsight Systems DMA/migration stats ===")

    # Try CUDA_GPU_MEMCPY or UVM_TRANSFERS
    htod_bytes = htod_dur = 0
    if 'CUDA_GPU_MEMCPY' in tables:
        rows = cur.execute(
            "SELECT SUM(bytes), SUM(end-start) FROM CUDA_GPU_MEMCPY WHERE copyKind=1"
        ).fetchone()
        if rows and rows[0]:
            htod_bytes, htod_dur = rows
            print(f"  HtoD (CUDA_GPU_MEMCPY): {htod_bytes/1e6:.1f} MB  dur={htod_dur/1e6:.1f} ms")

    # Try generic memcpy table
    for t in tables:
        if 'memcpy' in t.lower() or 'transfer' in t.lower() or 'uvm' in t.lower():
            try:
                info = cur.execute(f"SELECT COUNT(*),SUM(end-start) FROM '{t}'").fetchone()
                if info and info[0]:
                    print(f"  Table {t}: {info[0]} events, total_ns={info[1]}")
            except Exception:
                pass

    # UVM page fault events
    for t in tables:
        if 'fault' in t.lower() or 'page' in t.lower():
            try:
                info = cur.execute(f"SELECT COUNT(*) FROM '{t}'").fetchone()
                if info and info[0]:
                    print(f"  Table {t}: {info[0]} events")
            except Exception:
                pass

    conn.close()
except ImportError:
    print("  sqlite3 not available; skipping DMA breakdown")
except Exception as e:
    print(f"  nsys parse error: {e}")

# Summary: phase attribution
print(f"\n=== {name} — Phase attribution (CPU-path only) ===")
tot=st.median(t0t4)/1e3 if t0t4 else 0
t12=st.median(t1t2)/1e3 if t1t2 else 0
t23=st.median(t2t3)/1e3 if t2t3 else 0
if tot>0:
    print(f"  lock-wait(T0→T1): {tot-t12-t23:.1f} µs ({100*(tot-t12-t23)/tot:.0f}%)")
    print(f"  metadata(T1→T2) : {t12:.1f} µs ({100*t12/tot:.0f}%)")
    print(f"  dispatch(T2→T3) : {t23:.1f} µs ({100*t23/tot:.0f}%)")
    print(f"  [migration DMA is off-window: completes after T4, measured by nsys above]")
PYEOF
    else
        log "nsys SQLite not found at $db — raw report only"
        # Fall back to nsys stats export
        nsys stats --report cuda_api_sum "${nsys_out}.nsys-rep" 2>/dev/null || true
    fi
}

profile_bench "stencil_${N_STENCIL}" "$BENCH_STENCIL" "$N_STENCIL"
profile_bench "graphbfs_${N_BFS}" "$BENCH_BFS" "$N_BFS"

log "Gate 4 complete. results in $OUT"
