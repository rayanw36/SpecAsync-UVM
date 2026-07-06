#!/usr/bin/env bash
# run_gatec1_decomp.sh — Phase C Part 1: dispatch-window decomposition sweep.
#
# Runs four workloads (stencil-8K, stencil-24K, graphBFS-23, probe-N sweep)
# under the phaseC module (policy=0 depth=0 prefetch=1 log=1).
# Collects decomp ring snapshots and runs G1/G2/G4 validation.
#
# Usage: sudo bash tests/run_gatec1_decomp.sh
# Results land in results/phaseC/

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS="$REPO/results/phaseC"
MODULE="$REPO/driver/build/nvidia-uvm-specasync-phaseC.ko"
DBGFS="/sys/kernel/debug/specasync"
BENCH_STENCIL="$REPO/benchmarks/bench_stencil"
BENCH_BFS="$REPO/benchmarks/graph_bfs/bench_graph_bfs"
BENCH_PROBE="$REPO/tests/gatec1_probe"   # compiled below if present

mkdir -p "$RESULTS"

die() { echo "[ERROR] $*" >&2; exit 1; }
log() { echo "[gatec1] $(date +%T) $*"; }

# ── Module load helper ────────────────────────────────────────────────────────
load_module() {
    local extra="${1:-}"
    log "Loading phaseC module ($extra)"
    sudo rmmod nvidia_uvm 2>/dev/null || true
    sudo insmod "$MODULE" \
        specasync_log_enabled=1 specasync_policy=0 \
        specasync_offload_depth=0 $extra
    sleep 0.5
    sudo bash -c "echo 1 > $DBGFS/specasync_clear"
}

# ── Snapshot helper ───────────────────────────────────────────────────────────
snapshot() {
    local tag="$1"
    local bin="$RESULTS/decomp_${tag}.bin"
    sudo cat "$DBGFS/specasync_decomp_log" > "$bin"
    local n=$(( $(wc -c < "$bin") / 112 ))
    log "  Snapshot $tag: $n records"
    python3 "$REPO/tests/gatec1_decomp_analysis.py" "$bin" "$tag" 2>&1 | tee "$RESULTS/decomp_${tag}.txt"
}

# ── Verify module is Phase C build ───────────────────────────────────────────
test -f "$MODULE" || die "Phase C .ko not found: $MODULE"

# ── 1. Stencil-8K (lower fault pressure) ─────────────────────────────────────
log "=== Run 1: stencil N=8000 ==="
load_module
setarch -R "$BENCH_STENCIL" 8000
snapshot "stencil_8K"

# ── 2. Stencil-24K (high fault pressure) ─────────────────────────────────────
log "=== Run 2: stencil N=24000 ==="
sudo bash -c "echo 1 > $DBGFS/specasync_clear"
setarch -R "$BENCH_STENCIL" 24000
snapshot "stencil_24K"

# ── 3. GraphBFS-23 (irregular access) ────────────────────────────────────────
if [ -x "$BENCH_BFS" ]; then
    log "=== Run 3: GraphBFS N=23 ==="
    sudo bash -c "echo 1 > $DBGFS/specasync_clear"
    setarch -R "$BENCH_BFS" 23
    snapshot "graphbfs_23"
else
    log "GraphBFS not found at $BENCH_BFS — skipping"
fi

# ── 4. Fault-density sweep: stencil at N=4K, 8K, 16K, 24K ───────────────────
log "=== Run 4: fault-density sweep ==="
for N in 4000 8000 16000 24000; do
    sudo bash -c "echo 1 > $DBGFS/specasync_clear"
    setarch -R "$BENCH_STENCIL" $N
    snapshot "stencil_sweep_${N}"
done

# ── Summary comparison across workloads ──────────────────────────────────────
log "=== Summary ==="
python3 - <<'PYEOF'
import struct
import numpy as np
from pathlib import Path

DECOMP_FMT  = '<12Q4I'
DECOMP_SIZE = 112
RESULTS     = Path('results/phaseC')

def load(path):
    raw = path.read_bytes()
    n = len(raw) // DECOMP_SIZE
    recs = []
    for i in range(n):
        f = struct.unpack_from(DECOMP_FMT, raw, i * DECOMP_SIZE)
        recs.append({'d1': f[2]-f[1], 'd2': f[4]-f[3],
                     'svc': f[6]-f[5], 'd3': f[9], 'd4': f[10], 'd5': f[11],
                     'd6': max(0, f[8]-f[7]) if f[7] > 0 else 0,
                     'total': max(f[6], f[8] if f[8]>0 else 0) - f[1],
                     'faults': f[12]})
    return [r for r in recs if r['total'] > 0]

print(f"\n{'Workload':<25} {'n':>5} {'D1%':>6} {'D2%':>6} {'D3%':>6} "
      f"{'D4%':>6} {'D5%':>6} {'D6%':>6} {'total µs':>9}")
print('-'*80)

tags = [
    ('stencil_8K',     'Stencil-8K'),
    ('stencil_24K',    'Stencil-24K'),
    ('graphbfs_23',    'GraphBFS-23'),
    ('stencil_sweep_4000',  'Sweep-4K'),
    ('stencil_sweep_8000',  'Sweep-8K'),
    ('stencil_sweep_16000', 'Sweep-16K'),
    ('stencil_sweep_24000', 'Sweep-24K'),
]

for tag, label in tags:
    p = RESULTS / f'decomp_{tag}.bin'
    if not p.exists():
        continue
    recs = load(p)
    if not recs:
        continue
    t  = np.median([r['total'] for r in recs])
    d1 = np.median([r['d1']    for r in recs]) / t * 100
    d2 = np.median([r['d2']    for r in recs]) / t * 100
    d3 = np.median([r['d3']    for r in recs]) / t * 100
    d4 = np.median([r['d4']    for r in recs]) / t * 100
    d5 = np.median([r['d5']    for r in recs]) / t * 100
    d6 = np.median([r['d6']    for r in recs]) / t * 100
    print(f"{label:<25} {len(recs):>5} {d1:>6.1f} {d2:>6.1f} {d3:>6.1f} "
          f"{d4:>6.1f} {d5:>6.1f} {d6:>6.1f} {t/1e3:>9.1f}")
PYEOF

log "=== Done. Results in $RESULTS/ ==="
