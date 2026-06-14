#!/usr/bin/env bash
# run_gate2_depth1.sh — Gate 2 depth=1 validation
# Runs the cross-block sequential probe (1024 pages, 2 VA blocks) and
# computes hit rate + per-hit vs per-miss service time comparison.
# Module must be loaded with specasync_offload_depth=1, prefetch off.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
DBG=/sys/kernel/debug/specasync
OUT="$REPO/results/phaseB2"
mkdir -p "$OUT"

DEPTH=$(cat /sys/module/nvidia_uvm/parameters/specasync_offload_depth 2>/dev/null || echo "?")
POLICY=$(cat /sys/module/nvidia_uvm/parameters/specasync_policy)
PREF=$(cat /sys/module/nvidia_uvm/parameters/uvm_perf_prefetch_enable 2>/dev/null || echo "?")
echo "== Gate 2 depth=1 probe: offload_depth=$DEPTH policy=$POLICY prefetch=$PREF =="

if [ ! -x "$HERE/gate2_depth1_probe" ] || \
   [ "$HERE/gate2_depth1_probe.cu" -nt "$HERE/gate2_depth1_probe" ]; then
    echo "[build] gate2_depth1_probe"
    nvcc -arch=sm_75 -o "$HERE/gate2_depth1_probe" "$HERE/gate2_depth1_probe.cu"
fi

echo 1 | sudo tee "$DBG/specasync_clear" >/dev/null
sleep 0.3

setarch -R "$HERE/gate2_depth1_probe"

sleep 1.5

B="$OUT/gate2_batch.bin"
W="$OUT/gate2_worker.bin"
sudo cat "$DBG/specasync_log"        > "$B"
sudo cat "$DBG/specasync_worker_log" > "$W"

python3 - "$B" "$W" <<'PY'
import struct, sys, statistics as st

B, W = sys.argv[1], sys.argv[2]
BFMT='<6Q6I'; BSZ=struct.calcsize(BFMT)
WFMT='<4Q4I'; WSZ=struct.calcsize(WFMT)

braw = open(B,'rb').read()
wraw = open(W,'rb').read()

brecs = []
for i in range(len(braw)//BSZ):
    v = struct.unpack(BFMT, braw[i*BSZ:(i+1)*BSZ])
    t0, t4 = v[1], v[5]
    if t0 == 0 or t4 < t0: continue
    brecs.append(v)

wrecs = []
for i in range(len(wraw)//WSZ):
    v = struct.unpack(WFMT, wraw[i*WSZ:(i+1)*WSZ])
    eq, dq = v[0], v[1]
    if eq == 0 and dq == 0: continue
    wrecs.append(v)

names = {0:'null', 1:'miss', 2:'hit', 3:'migr_done', 4:'throttled'}
res = {}
for w in wrecs:
    r = w[4]; res[r] = res.get(r, 0) + 1

enq   = sum(r[7] for r in brecs)
hits  = sum(r[9] for r in brecs)
drops = sum(r[8] for r in brecs)
nf    = sum(r[6] for r in brecs)

print(f"  batches(valid)   : {len(brecs)}")
print(f"  num_faults       : {nf}")
print(f"  spec_enqueued    : {enq}")
print(f"  spec_drops       : {drops}")
print(f"  spec_hits        : {hits}")
hr = hits/enq if enq else 0.0
print(f"  hit_rate         : {hr:.4f}  (hits/enqueued)")
print(f"  worker results   : " + ", ".join(f"{names.get(k,k)}={v}" for k,v in sorted(res.items())))

# per-hit vs per-miss service time
hit_svc  = [r[5]-r[1] for r in brecs if r[9] > 0]
miss_svc = [r[5]-r[1] for r in brecs if r[9] == 0 and r[7] > 0]
if hit_svc and miss_svc:
    hm = st.median(hit_svc)
    mm = st.median(miss_svc)
    print(f"\n  Service time comparison (T0→T4):")
    print(f"    hit batches   : median {hm/1e3:8.1f} µs  (n={len(hit_svc)})")
    print(f"    miss batches  : median {mm/1e3:8.1f} µs  (n={len(miss_svc)})")
    saving_pct = 100*(1 - hm/mm)
    print(f"    saving        : {saving_pct:+.1f}%  (negative = faster on hit)")
    if saving_pct < -5:
        print(f"\n  => DEPTH-1 HIT SAVES TIME: hit batches {-saving_pct:.1f}% faster (mechanism works)")
    else:
        print(f"\n  => No significant per-hit saving — depth=1 may win only on wall time")
else:
    print(f"\n  hit batches={len(hit_svc)}  miss batches={len(miss_svc)}")

# Timer phase breakdown (Gate 4 fix verification)
t1t2 = [r[3]-r[2] for r in brecs if r[2]>0 and r[3]>r[2]]
t2t3 = [r[4]-r[3] for r in brecs if r[3]>0 and r[4]>r[3]]
t3t4 = [r[5]-r[4] for r in brecs if r[4]>0 and r[5]>r[4]]
print(f"\n  Timer phase breakdown (Gate 4, corrected):")
if t1t2: print(f"    T1→T2 (metadata lock→dispatch boundary) : {st.median(t1t2)/1e3:6.1f} µs median")
if t2t3: print(f"    T2→T3 (residency dispatch CPU cost)     : {st.median(t2t3)/1e3:6.1f} µs median")
if t3t4: print(f"    T3→T4 (replay/cleanup)                  : {st.median(t3t4)/1e3:6.1f} µs median")
if not t2t3: print("    T2==T3 still zero (no fix took effect? check code)")
PY
echo "  raw: $B  $W"
