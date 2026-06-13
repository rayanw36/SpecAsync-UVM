#!/usr/bin/env python3
# gate_d_analyze.py <batch.bin> [label] — summarise SpecAsync batch telemetry for
# Gate D: hit rate, and per-batch service time split by whether the batch scored a
# speculation hit (tests whether a "hit" actually saves service time).
import struct, sys, statistics as st
BFMT='<6Q6I'; BSZ=struct.calcsize(BFMT)
raw=open(sys.argv[1],'rb').read()
label=sys.argv[2] if len(sys.argv)>2 else sys.argv[1]
enq=hits=drops=nf=0
svc_hit=[]; svc_miss=[]; lock=[]; meta=[]; resid=[]; svc_all=[]
for i in range(len(raw)//BSZ):
    v=struct.unpack(BFMT, raw[i*BSZ:(i+1)*BSZ])
    bid,t0,t1,t2,t3,t4,num,seq,sdr,shit,oh,_=v
    if t0==0 or t4<t0 or (t4-t0)>30_000_000_000: continue
    enq+=seq; hits+=shit; drops+=sdr; nf+=num
    total=t4-t0
    svc_all.append(total)
    lock.append(t1-t0 if t1>=t0 else 0)
    meta.append(t2-t1 if t2>=t1 else 0)
    resid.append(t3-t2)
    (svc_hit if shit>0 else svc_miss).append(total)
def med(x): return st.median(x) if x else float('nan')
print(f"== {label} ==")
print(f"  batches={len(svc_all)} demand_faults={nf} enqueued={enq} hits={hits} drops={drops}")
print(f"  hit_rate(hits/enq)={hits/enq if enq else 0:.4f}")
print(f"  service T4-T0 ns: median={med(svc_all):.0f} mean={st.mean(svc_all) if svc_all else 0:.0f}")
print(f"  phase median ns: lock_acq={med(lock):.0f}  metadata(T1->T2)={med(meta):.0f}  residency(T2->T3)={med(resid):.0f}")
print(f"  service median ns — hit-batches={med(svc_hit):.0f} (n={len(svc_hit)})  miss-batches={med(svc_miss):.0f} (n={len(svc_miss)})")
if svc_hit and svc_miss:
    d=100*(med(svc_hit)-med(svc_miss))/med(svc_miss)
    print(f"  per-hit service delta vs miss: {d:+.1f}%  (negative = hit batches faster)")
