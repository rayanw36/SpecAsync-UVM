#!/usr/bin/env bash
# gate_c_stream_interleave.sh — Gate C interleaved STREAM: baseline(p0) vs
# treatment(p1=adjacent) vs null(p5=worker-no-work), alternating run-by-run so a
# stable host-noise offset cannot masquerade as a treatment effect.
#
# Policy is switched at runtime via the writable specasync_policy sysfs param —
# no module reload between runs, so all three conditions see identical module/GPU
# state and interleave at the finest granularity.
#
# Usage: sudo ./gate_c_stream_interleave.sh <N_elements> <cycles> <out_csv>
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SIZE="${1:?N_elements}"; CYCLES="${2:-40}"; OUT="${3:-$REPO/results/phaseB1/gate_c/stream_${SIZE}.csv}"
BIN="$REPO/benchmarks/bench_stream"
POLPARAM=/sys/module/nvidia_uvm/parameters/specasync_policy
mkdir -p "$(dirname "$OUT")"
echo "cycle,policy,time_ms" > "$OUT"

# warmup (not recorded)
for p in 0 1 5; do echo $p | sudo tee "$POLPARAM" >/dev/null; "$BIN" "$SIZE" >/dev/null 2>&1 || true; done

extract(){ "$BIN" "$SIZE" 2>/dev/null | sed -n 's/.*\[RESULT\] Time: \([0-9.]*\) ms.*/\1/p'; }

for c in $(seq 1 "$CYCLES"); do
  for p in 0 1 5; do
    echo $p | sudo tee "$POLPARAM" >/dev/null
    t=$(extract)
    echo "$c,$p,$t" >> "$OUT"
  done
done
echo 0 | sudo tee "$POLPARAM" >/dev/null   # leave inactive
echo "[gate_c] wrote $OUT ($(( $(wc -l < "$OUT") - 1 )) runs)"

python3 - "$OUT" <<'PY'
import csv,sys,statistics as st
rows=list(csv.DictReader(open(sys.argv[1])))
by={}
for r in rows:
    by.setdefault(int(r['policy']),[]).append(float(r['time_ms']))
name={0:'baseline p0',1:'adjacent p1',5:'null     p5'}
base=by.get(0,[])
b_med=st.median(base) if base else float('nan')
print(f"  size runs/policy={len(base)}")
print(f"  {'policy':12} {'n':>3} {'mean':>9} {'median':>9} {'std':>8} {'Δmed%vs p0':>11}")
def mwu(a,b):
    # Mann-Whitney U (two-sided) via rank-sum, normal approx — no scipy dependency
    import math
    n1,n2=len(a),len(b); allv=sorted([(v,0) for v in a]+[(v,1) for v in b])
    ranks={}; i=0
    # average ranks for ties
    vals=[v for v,_ in allv]
    rsum=[0.0,0.0]
    j=0
    while j<len(allv):
        k=j
        while k+1<len(allv) and vals[k+1]==vals[j]: k+=1
        avg=(j+k)/2.0+1
        for m in range(j,k+1): rsum[allv[m][1]]+=avg
        j=k+1
    U1=rsum[0]-n1*(n1+1)/2.0
    mu=n1*n2/2.0; sd=math.sqrt(n1*n2*(n1+n2+1)/12.0)
    z=(U1-mu)/sd if sd else 0.0
    from math import erf,sqrt
    p=2*(1-0.5*(1+erf(abs(z)/sqrt(2))))
    return z,p
for pol in (0,1,5):
    v=by.get(pol,[])
    if not v: continue
    med=st.median(v); dm=100*(med-b_med)/b_med if b_med else 0
    print(f"  {name[pol]:12} {len(v):3d} {st.mean(v):9.2f} {med:9.2f} {st.pstdev(v):8.2f} {dm:+11.2f}")
for pol in (1,5):
    if by.get(pol) and base:
        z,p=mwu(by[pol],base)
        print(f"  MWU {name[pol]} vs baseline: z={z:.2f} p={p:.4f}  {'(significant)' if p<0.05 else '(n.s.)'}")
PY
