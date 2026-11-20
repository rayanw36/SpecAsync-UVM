#!/usr/bin/env python3
"""C23 step 3: numbers behind the [CHECK] comments of the C23 text edits. Writes results/analysis/consolidation/C23_CHECKS.csv (id, value, source, computation); c1_evidence.py adds the rows to EVIDENCE_EXTRACT.md.
 1 nsys GPU page-fault count vs the driver's demand faults; 2 GraphBFS staging (88.7x, 80.6%); 3 dispatch shares (0.19%, 17.2%); 4 D5 decomposition (85.9%); 5 CPU-fault ratio."""
import csv, statistics as st, struct
rd = lambda p: list(csv.DictReader(open(p)))   # noqa: E731
rows = []
def rec(i, v, s, c): rows.append((i, v, s, c))
E9 = {(r["workload"], int(r["threshold"])): r for r in rd("results/analysis/gate_e/e9/cell_medians.csv")}
E5 = {(r["threshold"], r["arm"]): r for r in rd("results/analysis/gate_e/e5/mechanism.csv")}
E6 = {r["arm"]: r for r in rd("results/analysis/gate_e/e6/mechanism.csv")} if "arm" in rd("results/analysis/gate_e/e6/mechanism.csv")[0] else None
E6m = rd("results/analysis/gate_e/e6/mechanism.csv")
E4 = {(r["workload"], r["arm"]): r for r in rd("results/analysis/gate_e/e4/mechanism.csv")}
# 1. nsys vs demand faults
d51 = float(E5[("51", "C0")]["demand_faults"]); n51 = float(E9[("stencil", 51)]["gpu_faults_sum_median"]); e51 = float(E9[("stencil", 51)]["gpu_fault_events_median"])
c0t0 = next(r for r in E6m if "C0-t0" in str(r.get("arm", r.get("label", "")) ) or r.get("cell", "") == "C0-t0") if False else None
k = [kk for kk in E6m[0].keys()]
def e6(cell):
    for r in E6m:
        if cell in r.values(): return r
d0 = float(e6("C0-t0")["demand_faults"]); n0 = float(E9[("stencil", 0)]["gpu_faults_sum_median"]); e0 = float(E9[("stencil", 0)]["gpu_fault_events_median"])
rec("C23.nsys_vs_demand.stencil.t51", f"demand faults (E5 C0-t51, E3a-2 module, untraced) {d51:,.0f} / nsys GPU page faults (E9 stock module, traced, sum of numberOfPageFaults) {n51:,.0f} = {d51/n51:.2f}x; nsys fault events {e51:,.0f} ({n51/e51:.1f} faults per event)", "gate_e/e5/mechanism.csv; gate_e/e9/cell_medians.csv", "demand_faults / gpu_faults_sum_median (different sessions and modules)")
rec("C23.nsys_vs_demand.stencil.t0", f"demand faults (E6 C0-t0) {d0:,.0f} / nsys {n0:,.0f} = {d0/n0:.2f}x; nsys events {e0:,.0f} ({n0/e0:.1f} faults per event)", "gate_e/e6/mechanism.csv; gate_e/e9/cell_medians.csv", "demand_faults / gpu_faults_sum_median")
E8 = [r for r in rd("results/analysis/gate_e/e8/e8_runs.csv") if "spec-C0" in r["label"] and r.get("demand_faults")]
for wl in ("in_k1", "in_k512"):
    for t in (0, 51):
        dm = st.median(float(r["demand_faults"]) for r in E8 if r["workload"] == wl and r["label"].endswith(f"-t{t}")); ns = float(E9[(wl, t)]["gpu_faults_sum_median"])
        rec(f"C23.nsys_vs_demand.{wl}.t{t}", f"demand faults (E8 Family M spec-C0-t{t}, E3a-2 module, n = 5) {dm:,.0f} / nsys {ns:,.0f} = {dm/ns:.0f}x", "gate_e/e8/e8_runs.csv; gate_e/e9/cell_medians.csv", "median demand_faults / gpu_faults_sum_median")
# 2. GraphBFS
g6 = E4[("graphbfs", "C6-W512")]; DIST = 287956
rec("C23.iv4.graphbfs.requested_over_distinct", f"{float(g6['spec_pages_requested']):,.1f} pages requested / {DIST:,} distinct pages = {float(g6['spec_pages_requested'])/DIST:.1f}x", "gate_e/e4/mechanism.csv (E4.mech.graphbfs.C6-W512); tests/e4_analyze.py:27", "spec_pages_requested / 287,956")
rec("C23.iv4.graphbfs.far_frac_c6w512", f"fault_already_resident {float(g6['fault_already_resident']):,.1f} / {DIST:,} = {100*float(g6['far_frac_distinct']):.1f}% (upper bound on distinct pages made resident ahead of their fault; counts fault entries)", "gate_e/e4/mechanism.csv", "far_frac_distinct")
# 3. dispatch shares (rings, as c22_m3_dispatch_share.py)
RAW = "results/phaseB1/gate_e4/sweep"; FMT = "<12Q4I"; CAP = 131071
runs = rd("results/analysis/gate_e/e4/e4_runs.csv"); res = {}
for r in runs:
    wl, arm = r["label"].split(" ", 1)
    if arm != "C0": continue
    data = open(f"{RAW}/e3b_{r['idx']}_decomp.bin", "rb").read(); n = len(data) // struct.calcsize(FMT); win = 0
    for (bid, d1s, d1e, d2s, d2e, ss, se, d6s, d6e, p3, p4, p5, nf, nvs, nb, _p) in struct.iter_unpack(FMT, data): win += (d6e if d6e else se) - d1s
    if n < CAP: res.setdefault(wl, []).append((float(r["wall_s"]), win / 1e9))
for wl, nm in (("graphbfs", "GraphBFS-23"), ("stencil", "Stencil-24K")):
    w = st.median(x[0] for x in res[wl]); win = st.median(x[1] for x in res[wl])
    rec(f"C23.m3.{wl}.C0.window_share", f"{nm} C0: servicing window {win:.4f} s / process wall {w:.3f} s = {100*win/w:.2f}% (E4, {len(res[wl])} runs, ratio of medians)", "phaseB1/gate_e4/sweep/e3b_*_decomp.bin; gate_e/e4/e4_runs.csv", "sum over batches of (d6_end or svc_end) - d1_start; median over runs")
# 4. decomposition
f0, f7 = float(E4[("stencil", "C0")]["demand_faults"]), float(E4[("stencil", "C7-W512")]["demand_faults"]); d0_, d7_ = float(E4[("stencil", "C0")]["d5_s"]), float(E4[("stencil", "C7-W512")]["d5_s"])
cnt = (f0 - f7) * d0_ / f0; red = d0_ - d7_
rec("C23.vi1.stencil.fault_count_share", f"E4 Stencil-24K C0 -> C7-W512 (t51): D5 reduction {red:.4f} s, of which fault-count part {cnt:.4f} s = {100*cnt/red:.1f}%, per-fault part {100*(red-cnt)/red:.1f}%", "gate_e/e4/mechanism.csv (E4.mech.stencil.C0, .C7-W512)", "(f0 - f7) r0 / (D5_0 - D5_7), r0 = D5_0 / f0")
# 5. CPU faults
c = float(E9[("stencil", 51)]["report_cpu_faults_median"]) / float(E9[("stencil", 0)]["report_cpu_faults_median"]) if "report_cpu_faults_median" in E9[("stencil", 0)] else None
rec("C23.cpu_faults.stencil.t51_over_t0", f"Stencil-24K CPU page faults t51/t0 = {c:.2f}x ({float(E9[('stencil', 51)]['report_cpu_faults_median']):,.0f} / {float(E9[('stencil', 0)]['report_cpu_faults_median']):,.0f}); all in the host fill phase (E9.cpu_phase.fill_only)", "gate_e/e9/cell_medians.csv", "report_cpu_faults_median t51 / t0")
with open("results/analysis/consolidation/C23_CHECKS.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["id", "value", "source", "computation"]); w.writerows(rows)
for r in rows: print(r[0], "|", r[1][:170])
