#!/usr/bin/env bash
# run_oracle_probe.sh — Gate B oracle verification.
#
# 1. Collect a per-fault demand trace from the deterministic probe (policy=0,
#    prefetch off, ASLR off so managed VAs are stable across processes).
# 2. Reload a given .ko with policy=4 + that trace and replay the SAME probe.
# 3. Print the oracle hit triad.
#
# The probe is run under `setarch -R` (ASLR disabled) for BOTH collect and
# replay — without this the managed VA base is re-randomised each process and
# the recorded absolute addresses never match (oracle bug #2).
#
# Usage: sudo ./run_oracle_probe.sh <ko_path> [num_pages] [tag]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
KO="${1:?need ko path}"
NP="${2:-256}"
TAG="${3:-oracle}"
DBG=/sys/kernel/debug/specasync
OUT="$REPO/results/phaseB1/oracle_probe"
TRACE="$OUT/${TAG}_trace.bin"
mkdir -p "$OUT"
PROBE="$HERE/hit_probe"
[ -x "$PROBE" ] || nvcc -arch=sm_75 -o "$PROBE" "$HERE/hit_probe.cu"

run_probe() { setarch -R "$PROBE" "$NP" 1 >/dev/null; }

echo "== [collect] reload policy=0 prefetch=off trace_faults=1 =="
sudo rmmod nvidia_uvm
sudo insmod "$KO" specasync_policy=0 specasync_log_enabled=1 \
                  uvm_perf_prefetch_enable=0 specasync_trace_faults=1
run_probe
sleep 0.5
sudo cat "$DBG/specasync_fault_trace" > "$TRACE"
NENT=$(( $(stat -c%s "$TRACE") / 8 ))
echo "   collected $NENT fault-trace entries -> $TRACE"

echo "== [replay] reload $(basename "$KO") policy=4 prefetch=off oracle_trace=$TRACE =="
sudo rmmod nvidia_uvm
sudo insmod "$KO" specasync_policy=4 specasync_log_enabled=1 \
                  uvm_perf_prefetch_enable=0 \
                  specasync_oracle_trace_path="$TRACE"
echo 1 | sudo tee "$DBG/specasync_clear" >/dev/null
sleep 0.3
run_probe
sleep 1.0
B="$OUT/${TAG}_batch.bin"; W="$OUT/${TAG}_worker.bin"
sudo cat "$DBG/specasync_log" > "$B"
sudo cat "$DBG/specasync_worker_log" > "$W"

python3 - "$B" "$W" "$(cat /sys/module/nvidia_uvm/srcversion)" <<'PY'
import struct,sys
B,W,sv=sys.argv[1],sys.argv[2],sys.argv[3]
BFMT='<6Q6I';BSZ=struct.calcsize(BFMT);WFMT='<4Q4I';WSZ=struct.calcsize(WFMT)
br=open(B,'rb').read();wr=open(W,'rb').read()
enq=hits=drops=nf=v=0
for i in range(len(br)//BSZ):
    x=struct.unpack(BFMT,br[i*BSZ:(i+1)*BSZ])
    if x[1]==0 or x[5]<x[1]: continue
    v+=1;nf+=x[6];enq+=x[7];drops+=x[8];hits+=x[9]
proc=sum(1 for i in range(len(wr)//WSZ)
         if struct.unpack(WFMT,wr[i*WSZ:(i+1)*WSZ])[:2]!=(0,0))
print(f"  srcversion   : {sv}")
print(f"  batches      : {v}   demand_faults: {nf}")
print(f"  spec_enqueued: {enq}   spec_processed: {proc}")
print(f"  spec_hits    : {hits}")
print(f"  hit_rate     : {hits/enq if enq else 0:.4f}")
PY
