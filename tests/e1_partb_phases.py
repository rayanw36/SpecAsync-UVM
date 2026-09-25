#!/usr/bin/env python3
"""Gate E1 Part B.1: per-phase decomp totals for the E0.9b pilot runs
(C1 vs C6-L4096, 100% ring coverage). Phase definitions from
driver/src/specasync_telemetry.h:107-141:
  D1 drain, D2 preprocess, D3 VA-lock wait, D4 VA-lock hold (includes D5),
  D5 dispatch inside hold, D6 replay push, svc = full service_fault_batch,
  D7 = window - (D1+D2+svc+D6) residual; window = (d6_end or svc_end) - d1_start.
Writes results/analysis/gate_e/e1/partb_phase_totals.csv and a median table."""
import csv, os, statistics as st, struct, sys
RAW = "results/phaseB1/gate_e09b/pilot_raw"; OUT = "results/analysis/gate_e/e1"
FMT = "<12Q4I"; SZ = struct.calcsize(FMT)
PH = ["D1", "D2", "D3", "D4", "D5", "D4_minus_D5", "svc", "svc_minus_D3_D4", "D6", "D7", "window"]
rows = list(csv.DictReader(open("results/analysis/gate_e/e09b/pilot_runs.csv")))
os.makedirs(OUT, exist_ok=True)
per = []
for r in rows:
    data = open(f"{RAW}/pilot_{r['idx']}_{r['workload']}_{r['arm']}{r['L']}_decomp.bin", "rb").read()
    t = dict.fromkeys(PH, 0); viol = 0
    for (bid, d1s, d1e, d2s, d2e, ss, se, d6s, d6e, d3, d4, d5, nf, nvs, nb, _p) in struct.iter_unpack(FMT, data):
        end = d6e if d6e else se
        D1, D2, svc, D6 = d1e - d1s, d2e - d2s, se - ss, (d6e - d6s if d6e else 0)
        win = end - d1s
        t["D1"] += D1; t["D2"] += D2; t["D3"] += d3; t["D4"] += d4; t["D5"] += d5
        t["D4_minus_D5"] += d4 - d5; t["svc"] += svc; t["svc_minus_D3_D4"] += svc - d3 - d4
        t["D6"] += D6; t["D7"] += win - (D1 + D2 + svc + D6); t["window"] += win
        viol += (d3 + d4 > svc) or (d5 > d4)
    per.append(dict(idx=r["idx"], workload=r["workload"], arm=r["arm"] + r["L"], closure_violations=viol,
                    **{k: t[k] for k in PH}))
with open(f"{OUT}/partb_phase_totals.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(per[0])); w.writeheader(); w.writerows(per)
lines = []
for wl in ("stencil", "graphbfs"):
    a = [p for p in per if p["workload"] == wl and p["arm"] == "C1"]
    b = [p for p in per if p["workload"] == wl and p["arm"] == "C64096"]
    dw = st.median(p["window"] for p in a) - st.median(p["window"] for p in b)
    lines.append(f"## {wl}  (C1 n={len(a)}, C6-L4096 n={len(b)}; closure violations {sum(p['closure_violations'] for p in a+b)})")
    lines.append("| phase | median C1 (s) | median C6-L4096 (s) | C1 − C6 (s) | share of window reduction |")
    lines.append("|---|---|---|---|---|")
    for k in PH:
        m1, m6 = st.median(p[k] for p in a), st.median(p[k] for p in b)
        lines.append(f"| {k} | {m1/1e9:.4f} | {m6/1e9:.4f} | {(m1-m6)/1e9:+.4f} | {100*(m1-m6)/dw if dw and wl=='stencil' else float('nan'):+.1f}% |")
    lines.append("")
open(f"{OUT}/partb_phase_medians.md", "w").write("\n".join(lines))
print("\n".join(lines))
