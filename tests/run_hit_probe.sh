#!/usr/bin/env bash
# run_hit_probe.sh — Gate A: run the deterministic positive control and print the
# SpecAsync counter triad (enqueued / processed / hits / drops).
#
# Reads the live debugfs ring buffers. Does NOT reload the module. Assumes the
# specasync nvidia_uvm is loaded with specasync_log_enabled=1 and a chosen
# specasync_policy. Prints a one-line verdict.
#
# Usage: sudo ./run_hit_probe.sh [num_pages] [stride_pages] [tag]
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
DBG=/sys/kernel/debug/specasync
PARSER="$REPO/benchmarks/tools/specasync_parse.py"
OUT="${OUT:-$REPO/results/phaseB1/hit_probe}"
NP="${1:-256}"
STRIDE="${2:-1}"
TAG="${3:-run}"
mkdir -p "$OUT"

POLICY=$(cat /sys/module/nvidia_uvm/parameters/specasync_policy)
LOGEN=$(cat /sys/module/nvidia_uvm/parameters/specasync_log_enabled)
PREF=$(cat /sys/module/nvidia_uvm/parameters/uvm_perf_prefetch_enable 2>/dev/null || echo "?")
echo "== specasync_policy=$POLICY  log_enabled=$LOGEN  prefetch_enable=$PREF =="

# Build probe if needed
if [ ! -x "$HERE/hit_probe" ] || [ "$HERE/hit_probe.cu" -nt "$HERE/hit_probe" ]; then
    echo "[build] nvcc -arch=sm_75 hit_probe.cu"
    nvcc -arch=sm_75 -o "$HERE/hit_probe" "$HERE/hit_probe.cu"
fi

# Reset counters
echo 1 | sudo tee "$DBG/specasync_clear" >/dev/null
sleep 0.3

# Run probe
"$HERE/hit_probe" "$NP" "$STRIDE"

# Let async workers drain
sleep 1.0

# Snapshot the rings
B="$OUT/${TAG}_batch.bin"
W="$OUT/${TAG}_worker.bin"
sudo cat "$DBG/specasync_log"        > "$B"
sudo cat "$DBG/specasync_worker_log" > "$W"

echo "----- counter triad (policy=$POLICY) -----"
python3 - "$B" "$W" <<'PY'
import struct, sys
B,W = sys.argv[1], sys.argv[2]
BFMT='<6Q6I'; BSZ=struct.calcsize(BFMT)
WFMT='<4Q4I'; WSZ=struct.calcsize(WFMT)
braw=open(B,'rb').read(); wraw=open(W,'rb').read()
enq=hits=drops=nf=valid=0
for i in range(len(braw)//BSZ):
    v=struct.unpack(BFMT, braw[i*BSZ:(i+1)*BSZ])
    t0,t4=v[1],v[5]
    if t0==0 or t4<t0: continue          # stale slot
    valid+=1; nf+=v[6]; enq+=v[7]; drops+=v[8]; hits+=v[9]
# worker log: count by result
res={}
proc=0
for i in range(len(wraw)//WSZ):
    v=struct.unpack(WFMT, wraw[i*WSZ:(i+1)*WSZ])
    eq,dq=v[0],v[1]
    if eq==0 and dq==0: continue          # stale/zero slot
    proc+=1; r=v[4]; res[r]=res.get(r,0)+1
names={0:'null',1:'miss',2:'hit',3:'migr',4:'throttled'}
print(f"  batches(valid)   : {valid}")
print(f"  demand faults    : {nf}")
print(f"  spec_enqueued    : {enq}")
print(f"  spec_processed   : {proc}   (worker records; by result: " +
      ", ".join(f"{names.get(k,k)}={res[k]}" for k in sorted(res)) + ")")
print(f"  spec_hits        : {hits}")
print(f"  spec_drops       : {drops}")
rate = hits/enq if enq else 0.0
print(f"  hit_rate         : {rate:.4f}  (hits/enqueued)")
# Verdict
if proc==0:
    print("  VERDICT          : (iii) processed==0 — worker not running (enqueue/wake bug)")
elif hits==0:
    print("  VERDICT          : (ii) processed>0 but hits==0 — accounting/matching suspect")
else:
    print("  VERDICT          : (i) hits fire — counter works")
PY
echo "  raw: $B  $W"
