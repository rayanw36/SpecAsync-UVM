#!/usr/bin/env bash
# run_oracle_coalesce.sh — Gate B: oracle under COALESCED faults, old vs new ko.
# Collect a per-fault trace (policy=0), then replay it (policy=4) on the given ko.
# Usage: sudo ./run_oracle_coalesce.sh <ko_path> [num_pages] [tag]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/.." && pwd)"
KO="${1:?ko}"; NP="${2:-4096}"; TAG="${3:-coal}"
DBG=/sys/kernel/debug/specasync; OUT="$REPO/results/phaseB1/oracle_coalesce"; mkdir -p "$OUT"
TRACE="$OUT/${TAG}_trace.bin"; PROBE="$HERE/coalesce_probe"
[ -x "$PROBE" ] || nvcc -arch=sm_75 -o "$PROBE" "$HERE/coalesce_probe.cu"
run(){ setarch -R "$PROBE" "$NP" >/dev/null; }

sudo rmmod nvidia_uvm
sudo insmod "$KO" specasync_policy=0 specasync_log_enabled=1 uvm_perf_prefetch_enable=0 specasync_trace_faults=1
run; sleep 0.5
sudo cat "$DBG/specasync_fault_trace" > "$TRACE"
echo "[collect] $(( $(stat -c%s "$TRACE")/8 )) trace entries"

sudo rmmod nvidia_uvm
sudo insmod "$KO" specasync_policy=4 specasync_log_enabled=1 uvm_perf_prefetch_enable=0 specasync_oracle_trace_path="$TRACE"
echo 1 | sudo tee "$DBG/specasync_clear" >/dev/null; sleep 0.3
run; sleep 1.0
B="$OUT/${TAG}_batch.bin"; sudo cat "$DBG/specasync_log" > "$B"
python3 - "$B" "$(cat /sys/module/nvidia_uvm/srcversion)" <<'PY'
import struct,sys
B,sv=sys.argv[1],sys.argv[2];F='<6Q6I';S=struct.calcsize(F);r=open(B,'rb').read()
enq=hits=nf=v=0; bf=[]
for i in range(len(r)//S):
    x=struct.unpack(F,r[i*S:(i+1)*S])
    if x[1]==0 or x[5]<x[1]: continue
    v+=1;nf+=x[6];enq+=x[7];hits+=x[9];bf.append(x[6])
import statistics as st
cf=st.mean(bf) if bf else 0
print(f"  srcversion={sv}")
print(f"  batches={v}  demand_faults={nf}  mean_faults/batch(coalesce)={cf:.1f}")
print(f"  spec_enqueued={enq}  spec_hits={hits}  hit_rate={hits/enq if enq else 0:.4f}")
PY
