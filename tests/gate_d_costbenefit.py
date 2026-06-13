#!/usr/bin/env python3
# gate_d_costbenefit.py <dir-with-p0..p4_batch.bin> [label]
# Reproduces the Phase B cost-benefit metric per policy:
#   net_benefit_per_fault_ns = service_latency_delta_ns * hit_rate - enqueue_overhead_ns
# where service_latency_delta = mean(baseline T4-T0) - mean(config T4-T0).
# NOTE (Gate C): T0-T4 is CPU-side fault-handling latency and excludes migration
# DMA, so "service_latency_delta" is not a real time saving — net_benefit here is
# the same (telemetry-bounded) figure Phase B used, kept for comparability.
import struct, sys, os, statistics as st
F='<6Q6I'; S=struct.calcsize(F)
def load(p):
    if not os.path.exists(p): return None
    r=open(p,'rb').read(); svc=[]; enq=hits=oh=0
    for i in range(len(r)//S):
        v=struct.unpack(F, r[i*S:(i+1)*S])
        t0,t4=v[1],v[5]
        if t0==0 or t4<t0 or (t4-t0)>30e9: continue
        svc.append(t4-t0); enq+=v[7]; hits+=v[9]; oh+=v[10]
    if not svc: return None
    return dict(mean_svc=st.mean(svc), n=len(svc), enq=enq, hits=hits,
               hit_rate=hits/enq if enq else 0.0,
               oh_per_enq=oh/enq if enq else 0.0)
d=sys.argv[1]; label=sys.argv[2] if len(sys.argv)>2 else d
base=load(os.path.join(d,'p0_batch.bin'))
print(f"== cost-benefit: {label} ==")
print(f"  {'pol':3} {'hit_rate':>9} {'mean_svc_ns':>12} {'Δsvc_ns':>10} {'enq_oh_ns':>10} {'net_benefit/fault_ns':>20}")
for p in range(5):
    c=load(os.path.join(d,f'p{p}_batch.bin'))
    if not c: continue
    dsvc=(base['mean_svc']-c['mean_svc']) if base else 0.0
    net=dsvc*c['hit_rate']-c['oh_per_enq']
    print(f"  p{p:<2} {c['hit_rate']:9.4f} {c['mean_svc']:12.0f} {dsvc:10.0f} {c['oh_per_enq']:10.0f} {net:20.0f}")
print("  (net_benefit<0 => speculation costs more than it saves, per telemetry)")
