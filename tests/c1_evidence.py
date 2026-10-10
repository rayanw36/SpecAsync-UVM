#!/usr/bin/env python3
"""Gate C1: extract every number the consolidation proposals cite, directly
from COMMITTED derived files (CSV / analysis output), never from report prose.
Each printed row: evidence id | value | file | field / computation.
Writes results/analysis/consolidation/EVIDENCE_EXTRACT.md.
Numbers that exist only in report prose are NOT produced here; the proposals
mark them PROSE-ONLY."""
import csv
import statistics as st
import sys

OUT = "results/analysis/consolidation/EVIDENCE_EXTRACT.md"
rows = []


def rec(eid, value, path, field):
    rows.append((eid, value, path, field))


def load(p):
    return list(csv.DictReader(open(p)))


def f(x, n=4):
    return f"{float(x):.{n}f}"


# ---------- E4 primary comparisons (18) ----------
P = "results/analysis/gate_e/e4/primary_comparisons.csv"
for r in load(P):
    k = f"E4.{r['family']}.{r['workload']}.{r['arm']}_vs_{r['baseline']}"
    rec(k, f"median_base={f(r['median_base'])} median_arm={f(r['median_arm'])} delta_s={float(r['delta_s']):+.4f} "
           f"delta_pct={float(r['delta_pct']):+.2f}% p={float(r['p']):.2e} holm_sig={r['holm_sig']} mde_s={f(r['mde_s'])} "
           f"trigger={r['falsification_trigger']}", P, "median_base, median_arm, delta_s, delta_pct, p, holm_sig, mde_s, falsification_trigger")

# ---------- E4 mechanism ----------
P = "results/analysis/gate_e/e4/mechanism.csv"
for r in load(P):
    rec(f"E4.mech.{r['workload']}.{r['arm']}",
        f"demand_faults={float(r['demand_faults']):,.0f} far={float(r['fault_already_resident']):,.0f} "
        f"far_frac={float(r['far_frac_distinct']):.4f} enqueued={float(r['enqueued']):,.0f} drops={float(r['drops']):,.0f} "
        f"outside_lock_s={f(r['outside_lock_s'])} enq_s={f(r['enqueue_overhead_s'])} d5_s={f(r['d5_s'])} "
        f"spec_hits={float(r['spec_hits_10ms_staleness_counter']):,.0f}", P,
        "demand_faults, fault_already_resident, far_frac_distinct, enqueued, drops, outside_lock_s, enqueue_overhead_s, d5_s, spec_hits_10ms_staleness_counter (per-cell medians)")

# ---------- E5 ----------
P = "results/analysis/gate_e/e5/fault_reduction.csv"
for r in load(P):
    rec(f"E5.D({r['threshold']})", f"D={float(r['D']):+.4f} median_df_C0={float(r['median_df_C0']):,.0f} "
        f"median_df_C7W512={float(r['median_df_C7W512']):,.0f} p={float(r['p']):.2e} holm_sig={r['holm_sig']}", P,
        "D, median_df_C0, median_df_C7W512, p, holm_sig")
P = "results/analysis/gate_e/e5/wallclock_comparisons.csv"
for r in load(P):
    rec(f"E5.wall.t{r['threshold']}", f"median_C0={f(r['median_base'])} median_C7W512={f(r['median_arm'])} "
        f"delta_pct={float(r['delta_pct']):+.2f}% p={float(r['p']):.2e} holm_sig={r['holm_sig']}", P,
        "median_base, median_arm, delta_pct, p, holm_sig")
P = "results/analysis/gate_e/e5/mechanism.csv"
for r in load(P):
    rec(f"E5.mech.t{r['threshold']}.{r['arm']}", f"demand_faults={float(r['demand_faults']):,.0f} "
        f"far={float(r['fault_already_resident']):,.0f} far_frac={float(r['far_frac_distinct']):.4f} d5_s={f(r['d5_s'])} "
        f"prelock_s={f(r['prelock_outside_s'])}", P, "demand_faults, fault_already_resident, far_frac_distinct, d5_s, prelock_outside_s")

# ---------- E0.9b ----------
P = "results/analysis/gate_e/e09b/primary_comparisons.csv"
for r in load(P):
    rec(f"E09b.{r['workload']}.{r['comparison'].replace(' ', '_')}",
        f"median_base={f(r['median_base'])} median_c6={f(r['median_c6'])} delta_pct={float(r['delta_pct']):+.2f}% "
        f"p={float(r['p']):.2e} holm_sig={r['holm_sig']} trigger={r['falsification_trigger']}", P,
        "median_base, median_c6, delta_pct, p, holm_sig, falsification_trigger")
P = "results/analysis/gate_e/e09b/mechanism_by_L.csv"
for r in load(P):
    rec(f"E09b.mech.{r['workload']}.{r['arm']}{r['L']}", f"demand_faults={float(r['demand_faults']):,.0f} "
        f"far={float(r['fault_already_resident']):,.0f} spec_migrations={float(r['spec_migrations']):,.0f} "
        f"spec_hits={float(r['spec_hits_10ms_staleness_counter']):,.0f} coverage_pct={float(r['prestaged_coverage_pct']):.2f} "
        f"drops={float(r['not_enqueued_drops']):,.0f}", P,
        "demand_faults, fault_already_resident, spec_migrations, spec_hits_10ms_staleness_counter, prestaged_coverage_pct, not_enqueued_drops")
P = "results/analysis/gate_e/e09b/pilot_ceiling.csv"
pc = load(P)
for arm in ("C1", "C6"):
    v = [int(r["window_ns"]) for r in pc if r["workload"] == "stencil" and r["arm"] == arm]
    rec(f"E09b.pilot.stencil.{arm}.window", f"median_window_s={st.median(v)/1e9:.4f}", P, "window_ns (median of runs)")

# ---------- E1 ----------
P = "results/analysis/gate_e/e1/primary_comparisons.csv"
for r in load(P):
    rec(f"E1.{r['workload']}.{r['comparison'].replace(' ', '_')}",
        f"median_C0={f(r['median_base'])} median_C7={f(r['median_c7'])} delta_pct={float(r['delta_pct']):+.2f}% "
        f"p={float(r['p']):.2e} holm_sig={r['holm_sig']}", P, "median_base, median_c7, delta_pct, p, holm_sig")
P = "results/analysis/gate_e/e1/partb_phase_totals.csv"
pb = load(P)
for wl in ("stencil", "graphbfs"):
    a = [r for r in pb if r["workload"] == wl and r["arm"] == "C1"]
    b = [r for r in pb if r["workload"] == wl and r["arm"] == "C64096"]
    for k in ("D5", "svc_minus_D3_D4", "window"):
        m1 = st.median(int(r[k]) for r in a) / 1e9; m6 = st.median(int(r[k]) for r in b) / 1e9
        rec(f"E1PartB.{wl}.{k}", f"C1={m1:.4f} C6L4096={m6:.4f} C1_minus_C6={m1-m6:+.4f} s", P, f"{k} (median of runs)")
    d12a = st.median(int(r["D1"]) + int(r["D2"]) for r in a) / 1e9; d12b = st.median(int(r["D1"]) + int(r["D2"]) for r in b) / 1e9
    rec(f"E1PartB.{wl}.D1+D2", f"C1={d12a:.4f} C6L4096={d12b:.4f} C1_minus_C6={d12a-d12b:+.4f} s", P, "D1+D2 per run (median)")

# ---------- E1b ----------
P = "results/analysis/gate_e/e1b/e1b_per_run.csv"
eb = load(P)
M = {}
for wl, arm in (("stencil", "C1"), ("stencil", "C64096"), ("stencil", "C0"), ("stencil", "C74096"), ("graphbfs", "C1"), ("graphbfs", "C64096")):
    rs = [r for r in eb if r["workload"] == wl and r["arm"] == arm]
    M[(wl, arm)] = {k: st.median(int(r[k]) for r in rs) for k in ("enq_ns", "outside_ns", "prelock_ns", "ft_predictions", "demand_faults")}
for wl, base, spec in (("stencil", "C1", "C64096"), ("stencil", "C0", "C74096"), ("graphbfs", "C1", "C64096")):
    a, b = M[(wl, base)], M[(wl, spec)]
    do = b["outside_ns"] - a["outside_ns"]; de = b["enq_ns"] - a["enq_ns"]; dp = b["prelock_ns"] - a["prelock_ns"]
    rec(f"E1b.{wl}.{spec}-{base}", f"d_outside={do/1e9:+.4f}s d_enq={de/1e9:+.4f}s enq_share={de/do:.1%} "
        f"prelock_share={dp/do:.1%} enq_per_pred={b['enq_ns']/b['ft_predictions']:.0f}ns "
        f"residual_per_fault={(dp-de)/b['demand_faults']:.0f}ns", P, "enq_ns, outside_ns, prelock_ns, ft_predictions, demand_faults (medians of runs; differences)")

# ---------- E3b Step 4 ----------
P = "results/analysis/gate_e/e3b/step4_per_run.csv"
s4 = load(P)
S = {}
for r in s4:
    S.setdefault(r["arm"], []).append(r)
med = lambda arm, k: st.median(int(r[k]) for r in S[arm])  # noqa: E731
for wl, base, a0, a1 in (("stencil", "C1", "C6f0", "C6f1"), ("stencil", "C0", "C7f0", "C7f1"), ("graphbfs", "C1", "C6f0", "C6f1")):
    B = f"{wl} {base}"
    res = {}
    for a in (a0, a1):
        A = f"{wl} {a}"
        resid = (med(A, "outside_ns") - med(B, "outside_ns")) - (med(A, "enq_ns") - med(B, "enq_ns"))
        res[a] = (resid, resid / med(A, "coalesced_I1"))
    rec(f"E3b.{wl}.{a0[:2]}.residual", f"fast0={res[a0][0]/1e9:+.4f}s ({res[a0][1]:.1f} ns/fault) fast1={res[a1][0]/1e9:+.4f}s "
        f"({res[a1][1]:.1f} ns/fault) removed={1-res[a1][0]/res[a0][0]:.1%}", P,
        "outside_ns, enq_ns, coalesced_I1 (medians; residual = d_outside - d_enq)")
    rec(f"E3b.{wl}.{a0[:2]}.drops", f"fast0={med(f'{wl} {a0}', 'drops'):,.0f} fast1={med(f'{wl} {a1}', 'drops'):,.0f}", P, "drops (median)")
    rec(f"E3b.{wl}.{a0[:2]}.d5", f"base={med(B,'d5_ns')/1e9:.4f} fast0={med(f'{wl} {a0}','d5_ns')/1e9:.4f} fast1={med(f'{wl} {a1}','d5_ns')/1e9:.4f} s", P, "d5_ns (median)")

# ---------- T1 (T4) and B5 (5070 Ti 595.84) interleaved C0-C3 ----------
for plat, P in (("T4", "results/phaseB2/gate3_interleaved/gate3_interleaved_times.csv"),
                ("5070Ti-595.84", "results/phaseB2/gate3_interleaved_5070ti/gate3_interleaved_times.csv")):
    rr = list(csv.reader(open(P)))[1:]
    kept = [x for x in rr if x[-1] != "warmup"]
    W = {}
    for x in kept:
        W.setdefault((x[3], x[2]), []).append(float(x[6]))
    for bench in ("bench_stencil", "bench_graph_bfs"):
        c0 = st.median(W[(bench, "C0")]); c1 = st.median(W[(bench, "C1")]); c3 = st.median(W[(bench, "C3")])
        rec(f"T1B5.{plat}.{bench}", f"n_kept_per_cell={len(W[(bench,'C0')])} C0={c0:.3f} C1={c1:.3f} C3={c3:.3f} "
            f"C3_vs_C0={100*(c3/c0-1):+.2f}% C1/C0={c1/c0:.2f}x", P, "wall_s medians over rows whose last column != 'warmup' (kept phase)")

# ---------- B9 task 2c (oversubscription C0/C1/C3) ----------
P = "results/analysis/gate_b9_oversub_mechanism/task2c_aggregate_comparison.csv"
for r in load(P):
    rec(f"B9.2c.iters{r['iters']}", f"C0={r['c0_median_s']} C1={r['c1_median_s']} C3={r['c3_median_s']} "
        f"C3_vs_C0={float(r['pct_c3_vs_c0']):+.2f}% holm={r['holm_significant']}", P, "c0/c1/c3_median_s, pct_c3_vs_c0, holm_significant")

# ---------- B10 C4 ----------
for P in ("results/analysis/gate_b10_augmentation/t_b10_aggregate_comparison.csv",
          "results/analysis/gate_b10_replication/t_b10c_aggregate_comparison.csv"):
    for r in load(P):
        rec(f"B10.{P.split('/')[-1]}.iters{r['iters']}", f"C0={r['c0_median_s']} C4={r['c4_median_s']} "
            f"C4_vs_C0={float(r['pct_c4_vs_c0']):+.2f}% holm={r['holm_significant']}", P, "c0_median_s, c4_median_s, pct_c4_vs_c0, holm_significant")

# ---------- T4 prefetch-off hit rates (clean reps) ----------
P = "results/gate3/telemetry/t4_prefetch_off_hitrate_recovered.csv"
for r in load(P):
    rec(f"T4hit.{r['bench']}.rep{r['rep']}.{r['methodology']}", f"hits={r['hits']} enqueued={r['enqueued']} "
        f"hit_rate_pct={r['hit_rate_pct']} faults={r['faults']} fault_rate_per_s={r['fault_rate_per_s']}", P,
        "hits, enqueued, hit_rate_pct, faults, fault_rate_per_s")

# ---------- A1 dispatch latency ----------
P = "results/analysis/t_a1_worker/worker_latency_summary.csv"
for r in load(P):
    rec(f"A1.{r['platform']}.{r['scale']}.{r['bench']}", f"dispatch_median_us={r['dispatch_median_us']} exec_median_us={r['exec_median_us']} n={r['n']}", P,
        "dispatch_median_us, exec_median_us, n")


# ---------- claim 9: C3 vs C1 per platform (same interleaved files) ----------
for plat, P in (("T4", "results/phaseB2/gate3_interleaved/gate3_interleaved_times.csv"),
                ("5070Ti-595.84", "results/phaseB2/gate3_interleaved_5070ti/gate3_interleaved_times.csv")):
    rr = [x for x in list(csv.reader(open(P)))[1:] if x[-1] != "warmup"]
    for bench in ("bench_stencil", "bench_graph_bfs"):
        c1 = st.median(float(x[6]) for x in rr if x[3] == bench and x[2] == "C1")
        c3 = st.median(float(x[6]) for x in rr if x[3] == bench and x[2] == "C3")
        c2 = st.median(float(x[6]) for x in rr if x[3] == bench and x[2] == "C2")
        rec(f"claim9.{plat}.{bench}", f"C3_vs_C1={100*(c3/c1-1):+.2f}% C2_vs_C1={100*(c2/c1-1):+.2f}%", P, "wall_s medians, kept phase")

# ---------- T4 GraphBFS pooled clean-rep hit rate (reps 1-4) ----------
P = "results/gate3/telemetry/t4_prefetch_off_hitrate_recovered.csv"
g = [r for r in load(P) if r["bench"] == "bench_graph_bfs" and r["methodology"] == "corrected_marginal_clean"]
h = sum(int(r["hits"]) for r in g); e = sum(int(r["enqueued"]) for r in g)
rec("T4hit.graphbfs.pooled_reps1-4", f"hits={h} enqueued={e} hit_rate_pct={100*h/e:.4f}", P, "sum(hits)/sum(enqueued), corrected_marginal_clean rows")

# ---------- E0.9b pilot ceiling interval (pairwise C1 - C6 windows) ----------
P = "results/analysis/gate_e/e09b/pilot_ceiling.csv"
pc = load(P)
for wl in ("stencil", "graphbfs"):
    a = [int(r["window_ns"]) for r in pc if r["workload"] == wl and r["arm"] == "C1"]
    b = [int(r["window_ns"]) for r in pc if r["workload"] == wl and r["arm"] == "C6"]
    d = [x - y for x in a for y in b]
    rec(f"E09b.pilot.{wl}.interval", f"[{min(d)/1e9:+.4f}, {max(d)/1e9:+.4f}] s; point {(st.median(a)-st.median(b))/1e9:+.4f} s", P, "pairwise C1-C6 window_ns; medians")

# ---------- claim 16: decomposition-telemetry overhead, 5070 Ti ----------
P = "results/phaseC/decomp_overhead_5070ti/overhead_times_interleaved.csv"
od = load(P)
grp = {}
for r in od:
    grp.setdefault(r["build"], []).append(float(r["time_ms"]))
m0, m1 = st.median(grp["DECOMP0"]), st.median(grp["DECOMP1"])
rec("claim16.5070Ti", f"DECOMP0 median={m0:.3f} ms (n={len(grp['DECOMP0'])}) DECOMP1 median={m1:.3f} ms (n={len(grp['DECOMP1'])}) overhead={100*(m1/m0-1):+.3f}%",
    P, "time_ms median by build (all trials in file)")


# ---------- spec_migrations vs fault_already_resident, prefetch on (E1, E4) ----------
P = "results/analysis/gate_e/e1/mechanism_by_L.csv"
for r in load(P):
    if r["arm"] == "C7":
        rec(f"E1.mech.{r['workload']}.C7-L{r['L']}", f"demand_faults={float(r['demand_faults']):,.0f} "
            f"spec_migrations={float(r['spec_migrations']):,.0f} far={float(r['fault_already_resident']):,.0f} "
            f"enqueued={float(r['enqueued']):,.0f}", P, "demand_faults, spec_migrations, fault_already_resident, enqueued (medians)")
P = "results/analysis/gate_e/e4/mechanism.csv"
for r in load(P):
    if r["arm"].startswith("C7"):
        rec(f"E4.mig.{r['workload']}.{r['arm']}", f"spec_migrations={float(r['spec_migrations']):,.0f} far={float(r['fault_already_resident']):,.0f} "
            f"spec_pages_requested={float(r['spec_pages_requested']):,.0f}", P, "spec_migrations, fault_already_resident, spec_pages_requested (medians)")

# ---------- E6 (threshold baseline; added for Gate C2-APPLY) ----------
E6 = "results/analysis/gate_e/e6/"
P = E6 + "family1_primary.csv"
for r in load(P):
    rec(f"E6.F1.C7W512-t51_vs_{r['base']}", f"median_base={f(r['median_base'])} median_arm={f(r['median_c6'])} "
        f"delta_pct(arm-base)/base={float(r['delta_pct']):+.2f}% p={float(r['p']):.2e} holm_sig={r['holm_sig']} "
        f"cohen_d={float(r['cohen_d']):+.2f} mde_s={f(r['mde_s'])}", P,
        "median_base, median_c6 (=C7W512-t51), delta_pct, p, holm_sig, cohen_d, mde_s")
P = E6 + "secondary_wall.csv"
for r in load(P):
    rec(f"E6.wall.{r['arm']}_vs_{r['base']}", f"median_base={f(r['median_base'])} median_arm={f(r['median_c6'])} "
        f"delta_pct={float(r['delta_pct']):+.2f}% p={float(r['p']):.2e} holm_sig={r['holm_sig']} mde_s={f(r['mde_s'])}", P,
        "median_base, median_c6, delta_pct, p, holm_sig, mde_s")
P = E6 + "secondary_demand.csv"
for r in load(P):
    rec(f"E6.demand.{r['arm']}_vs_{r['base']}", f"median_base={float(r['median_base']):,.0f} median_arm={float(r['median_c6']):,.0f} "
        f"delta_pct={float(r['delta_pct']):+.2f}% p={float(r['p']):.2e} holm_sig={r['holm_sig']}", P,
        "median_base, median_c6, delta_pct, p, holm_sig")
P = E6 + "family2_graphbfs.csv"
for r in load(P):
    rec(f"E6.F2.{r['arm']}_vs_{r['base']}", f"median_base={f(r['median_base'])} median_arm={f(r['median_c6'])} "
        f"delta_pct={float(r['delta_pct']):+.2f}% p={float(r['p']):.2e} holm_sig={r['holm_sig']} "
        f"mde_s={f(r['mde_s'])} mde_pct_of_base={100*float(r['mde_s'])/float(r['median_base']):.2f}%", P,
        "median_base, median_c6, delta_pct, p, holm_sig, mde_s; mde_pct = mde_s / median_base")
P = E6 + "mechanism.csv"
mech = {r["cell"]: r for r in load(P)}
for c, r in mech.items():
    rec(f"E6.mech.{c}", f"wall_median_s={f(r['wall_median_s'])} demand_faults={float(r['demand_faults']):,.1f} "
        f"d5_ns_per_demand_fault={float(r['d5_ns_per_demand_fault']):.1f} spec_pages_requested={float(r['spec_pages_requested']):,.0f}",
        P, "wall_median_s, demand_faults, d5_ns_per_demand_fault, spec_pages_requested (per-cell medians)")
for t in (0, 10, 25, 51):
    c0, c7 = float(mech[f"C0-t{t}"]["demand_faults"]), float(mech[f"C7W512-t{t}"]["demand_faults"])
    rec(f"E6.D(t{t})", f"D={1 - c7 / c0:+.4f} (1 - median faults C7W512-t{t} / C0-t{t})", P, "demand_faults; D = 1 - C7W512 / C0 (E5 definition)")
for t in (0, 10, 25):
    a, b = float(mech[f"C0-t{t}"]["wall_median_s"]), float(mech["C0-t51"]["wall_median_s"])
    rec(f"E6.C0-t{t}_vs_C0-t51.DESCRIPTIVE", f"delta_pct={100 * (a / b - 1):+.2f}% (median {f(a)} vs {f(b)}); NOT a pre-registered E6 comparison", P,
        "wall_median_s, computed (arm-base)/base from medians; descriptive only, no test")

# ---------- E7 (threshold generality) and E8 (sparse access); added for Gate C3 ----------
E7 = "results/analysis/gate_e/e7/"
for name, tag in (("family_a.csv", "A"), ("family_b.csv", "B")):
    P = E7 + name
    for r in load(P):
        rec(f"E7.{tag}.{r['workload']}.{r['arm']}_vs_{r['base']}",
            f"median_base={f(r['median_base'])} median_arm={f(r['median_c6'])} delta_pct(arm-base)/base={float(r['delta_pct']):+.2f}% "
            f"p={float(r['p']):.2e} holm_sig={r['holm_sig']} mde_pct={float(r['mde_pct']):.2f}% mde_family_pct={float(r['mde_family_pct']):.2f}%",
            P, "median_base, median_c6 (=arm), delta_pct, p, holm_sig, mde_pct, mde_family_pct")
P = E7 + "family_c.csv"
for r in load(P):
    rec(f"E7.C.{r['cell']}.block2_vs_block1", f"block1={f(r['median_base'])} block2={f(r['median_c6'])} delta_pct={float(r['delta_pct']):+.2f}% "
        f"p={float(r['p']):.2e} holm_sig={r['holm_sig']}", P, "median_base (block 1), median_c6 (block 2), delta_pct, p, holm_sig")
P = E7 + "session_medians.csv"
for r in load(P):
    rec(f"E7.session.{r['session'].replace(' ', '_')}", f"C0-t51={r['C0-t51 median (s)']} C7W512-t51={r['C7W512-t51 median (s)']} C7_vs_C0={r['C7 vs C0 %']}%",
        P, "per-session medians of the two E3a-2 arms (E4-E7)")
E8 = "results/analysis/gate_e/e8/"
P = E8 + "primary_tests.csv"
for r in load(P):
    rec(f"E8.{r['size']}.K{r['K']}.{r['arm']}_vs_stock-t51",
        f"median_base={f(r['median_base'])} median_arm={f(r['median_c6'])} delta_pct(arm-t51)/t51={float(r['delta_pct']):+.2f}% p={float(r['p']):.2e} "
        f"holm_sig={r['holm_sig']} mde_pct={float(r['mde_pct']):.2f}% mde_family_pct={float(r['mde_family_pct']):.2f}%",
        P, "median_base (t51), median_c6 (=arm), delta_pct, p, holm_sig, mde_pct, mde_family_pct")
P = E8 + "per_pass_descriptive.csv"
for r in load(P):
    rec(f"E8.pass.{r['workload']}.{r['cell']}", f"pass1_ms={float(r['pass1_ms_median']):.1f} pass2_ms={float(r['pass2_ms_median']):.1f} "
        f"pass3_ms={float(r['pass3_ms_median']):.1f}", P, "per-pass kernel time medians (descriptive)")
P = E8 + "family_m_mechanism.csv"
for r in load(P):
    rec(f"E8.M.{r['workload']}.{r['cell']}", f"wall_median_s={f(r['wall_median_s'])} demand_faults={float(r['demand_faults']):,.0f} "
        f"d5_ns_per_demand_fault={float(r['d5_ns_per_demand_fault']):,.0f}", P, "Family M (n=5, descriptive)")

# ---------- D6 regeneration (derived from raw files by tests/d6_regenerate.py; one id per comparison) ----------
import re as _re
P = "results/analysis/derived/d6_comparison.csv"
_seen = set()
for r in load(P):
    slug = _re.sub(r"[^A-Za-z0-9]+", "_", r["quantity"]).strip("_")[:70]
    eid = f"D6.r{int(r['row']):02d}.{slug}"
    k = 2
    while eid in _seen:
        eid = f"D6.r{int(r['row']):02d}.{slug}.{k}"
        k += 1
    _seen.add(eid)
    rec(eid, f"derived={r['derived']} prose={r['prose']} result={r['result']}", P, f"d6_comparison.csv row {r['row']}: {r['prose_source']}")

# ---------- T4 replication of E7 (Gate C4; results/analysis/t4) ----------
T4 = "results/analysis/t4/"
for name, tag in (("family_a.csv", "A"), ("family_b.csv", "B")):
    P = T4 + name
    for r in load(P):
        rec(f"T4.{tag}.{r['workload']}.{r['arm']}_vs_{r['base']}",
            f"median_base={f(r['median_base'])} median_arm={f(r['median_c6'])} delta_pct(arm-base)/base={float(r['delta_pct']):+.2f}% "
            f"p={float(r['p']):.2e} holm_sig={r['holm_sig']} mde_pct={float(r['mde_pct']):.2f}% mde_family_pct={float(r['mde_family_pct']):.2f}%",
            P, "median_base (t51), median_c6 (=arm), delta_pct, p, holm_sig, mde_pct, mde_family_pct (Tesla T4, driver 595.91.07)")
_b = load(T4 + "family_b.csv")
_fast = [r for r in _b if r["holm_sig"] == "True" and float(r["delta_s"]) < 0]
_slow = [r for r in _b if r["holm_sig"] == "True" and float(r["delta_s"]) > 0]
rec("T4.B.count", f"tests={len(_b)} holm_significant_faster={len(_fast)} holm_significant_slower={len(_slow)} not_significant={len(_b) - len(_fast) - len(_slow)}",
    T4 + "family_b.csv", "count of rows by (holm_sig, sign of delta_s)")
_g = [r for r in _b if r["workload"] == "graphbfs"]
rec("T4.B.graphbfs.vs_mde", " ".join(f"{r['arm']}: delta={float(r['delta_pct']):+.2f}% mde_pct={float(r['mde_pct']):.2f}% (unadjusted) mde_family_pct={float(r['mde_family_pct']):.2f}% (family alpha, m = 14) holm_sig={r['holm_sig']}" for r in _g),
    T4 + "family_b.csv", "GraphBFS-23 rows: delta against the MDE (the effect is below the MDE although Holm-significant)")
_a = [r for r in load(T4 + "family_a.csv") if r["arm"] == "stock-t0"][0]
rec("T4.cross_version.stencil_t51", f"this session stock-t51 median={f(_a['median_base'])} s (driver 595.91.07); the old T4 C0 median 4.185 s (595.71.05) is PROSE-ONLY (GATE_T1_REPORT.md) and not in a committed CSV",
    T4 + "family_a.csv", "median_base of stock-t0_vs_stock-t51; cross-version comparison is descriptive and untested")

# ---------- E9 (nsys tracing; results/analysis/gate_e/e9) ----------
E9 = "results/analysis/gate_e/e9/"
P = E9 + "cell_medians.csv"
GIB = 1073741824.0
cm = {(r["workload"], int(r["threshold"])): r for r in load(P)}
for (wl, t), r in cm.items():
    rec(f"E9.cell.{wl}.t{t}",
        f"n={r['n']} htod_gib={float(r['htod_bytes_median']) / GIB:.3f} dtoh_gib={float(r['dtoh_bytes_median']) / GIB:.3f} "
        f"gpu_page_faults={float(r['report_gpu_faults_median']):,.0f} cpu_page_faults={float(r['report_cpu_faults_median']):,.0f} "
        f"dtoh_pass2_gib={float(r['pass2_dtoh_bytes_median']) / GIB if r['pass2_dtoh_bytes_median'] not in ('', 'nan') else float('nan'):.3f} "
        f"dtoh_pass3_gib={float(r['pass3_dtoh_bytes_median']) / GIB if r['pass3_dtoh_bytes_median'] not in ('', 'nan') else float('nan'):.3f} "
        f"htod_pass2_gib={float(r['pass2_htod_bytes_median']) / GIB if r['pass2_htod_bytes_median'] not in ('', 'nan') else float('nan'):.3f} "
        f"htod_pass3_gib={float(r['pass3_htod_bytes_median']) / GIB if r['pass3_htod_bytes_median'] not in ('', 'nan') else float('nan'):.3f}",
        P, "per-cell medians of nsys UM counts, n=3 (descriptive); GiB = 2^30 B")
rec("E9.ratio.ov_k1.htod_t0_over_t51", f"{float(cm[('ov_k1', 0)]['htod_bytes_median']) / float(cm[('ov_k1', 51)]['htod_bytes_median']):.1f}x", P, "htod_bytes_median t0 / t51")
rec("E9.ratio.stencil", f"htod_diff_pct={100 * abs(float(cm[('stencil', 0)]['htod_bytes_median']) - float(cm[('stencil', 51)]['htod_bytes_median'])) / float(cm[('stencil', 51)]['htod_bytes_median']):.2f}% "
    f"gpu_faults_t0={float(cm[('stencil', 0)]['report_gpu_faults_median']):,.0f} gpu_faults_t51={float(cm[('stencil', 51)]['report_gpu_faults_median']):,.0f}", P, "Stencil-24K t0 vs t51")
_cpu = {k: float(v["report_cpu_faults_median"]) for k, v in cm.items()}
rec("E9.ratio.cpu_faults_t51_over_t0", "; ".join(f"{w}={_cpu[(w, 51)] / _cpu[(w, 0)]:.2f}x (t0={_cpu[(w, 0)]:,.0f})" for w in ("ov_k1", "ov_k8", "ov_k64", "ov_k512", "in_k1", "in_k512", "stencil")),
    P, "report_cpu_faults_median t51 / t0; 24 GiB / 2 MiB = 12,288 blocks; 8 GiB / 2 MiB = 4,096")

# ---------- derived ranges and counts quoted by CS2-N10 (computed from the E8 / E7 primary tests; Gate C4) ----------
P = "results/analysis/gate_e/e8/primary_tests.csv"
_e8 = load(P)
_d = lambda rows: [float(r["delta_pct"]) for r in rows]  # noqa: E731
_dense = [r for r in _e8 if int(r["K"]) >= 64]
_ovs = [r for r in _e8 if r["size"] == "ov" and int(r["K"]) <= 8 and r["arm"] == "stock-t0"]
_ovs25 = [r for r in _e8 if r["size"] == "ov" and int(r["K"]) <= 8 and r["arm"] == "stock-t25"]
_ins = [r for r in _e8 if r["size"] == "in" and int(r["K"]) <= 8]
rec("E8.range.dense_K64plus", f"min={min(_d(_dense)):+.2f}% max={max(_d(_dense)):+.2f}% over {len(_dense)} tests (K>=64, both sizes, t0 and t25)", P, "delta_pct over K>=64")
rec("E8.range.ov_sparse_t0", f"min={min(_d(_ovs)):+.2f}% max={max(_d(_ovs)):+.2f}% over {len(_ovs)} tests (oversubscribed K in {{1,8}}, t0)", P, "delta_pct, oversubscribed, K<=8, t0")
rec("E8.range.ov_sparse_t25", f"{'; '.join('K=' + r['K'] + ' ' + format(float(r['delta_pct']), '+.2f') + '%' for r in _ovs25)} (oversubscribed, t25)", P, "delta_pct, oversubscribed, K<=8, t25 (K=1 is outside the t0 range)")
rec("E8.range.in_sparse", f"min={min(_d(_ins)):+.2f}% max={max(_d(_ins)):+.2f}% over {len(_ins)} tests (in-memory K in {{1,8}}, t0 and t25)", P, "delta_pct, in-memory, K<=8")


# ---------- CPU-side population and outside-kernel time (Gate C6; from the derived c4_*.csv files) ----------
_ps = list(csv.DictReader(open("results/analysis/derived/c4_e9_phase_split.csv")))
_PF = "results/analysis/derived/c4_e9_phase_split.csv"
_nonfill = sum(1 for r in _ps if any(float(r[k] or 0) != 0 for k in ("cpu_faults_alloc", "cpu_faults_setup", "cpu_faults_kernel", "cpu_faults_post")))
rec("E9.cpu_phase.fill_only", f"{sum(1 for r in _ps if r['cpu_faults_fill'] == r['cpu_faults'])} of {len(_ps)} traced runs have all CPU faults in the host fill phase; runs with any CPU fault in alloc/setup/kernel/post: {_nonfill}", _PF, "cpu_faults_fill == cpu_faults; other phases zero")
_t0 = {}
for r in _ps:
    if r["threshold"] == "0": _t0.setdefault(r["workload"], set()).add(int(r["cpu_faults"]))
rec("E9.cpu_phase.t0_block_count", "; ".join(f"{w}={sorted(v)[0]:,}" + (f" (= {int(sorted(v)[0])} blocks of 2 MiB)" if w != "stencil" else "") for w, v in sorted(_t0.items())) + "; 24 GiB / 2 MiB = 12,288; 8 GiB / 2 MiB = 4,096", _PF, "cpu_faults at t0 per workload (identical across the 3 runs)")
_o = list(csv.DictReader(open("results/analysis/derived/c4_e8_outside_kernels.csv")))
_OF = "results/analysis/derived/c4_e8_outside_kernels.csv"
_o0 = [r for r in _o if r["arm"] == "stock-t0"]
rec("E8.outside_kernels.t0", f"{sum(1 for r in _o0 if float(r['delta_outside_kernels_s']) < 0)} of {len(_o0)} t0 comparisons have lower time outside the kernels than t51; range {min(-float(r['delta_outside_kernels_s']) for r in _o0) * 1000:.0f}-{max(-float(r['delta_outside_kernels_s']) for r in _o0) * 1000:.0f} ms", _OF, "delta_outside_kernels_s, arm = stock-t0 (untraced E8: wall-clock minus summed kernel time)")
_dn = [r for r in _o0 if int(r["K"]) >= 64]
rec("E8.outside_kernels.share_dense", f"outside-kernel share of the wall-clock gain, K >= 64, t0: {'; '.join(r['size'] + ' K=' + r['K'] + ' ' + format(100 * float(r['outside_share_of_delta']), '.1f') + '%' for r in _dn)}; range {100 * min(float(r['outside_share_of_delta']) for r in _dn):.0f}-{100 * max(float(r['outside_share_of_delta']) for r in _dn):.0f}%", _OF, "outside_share_of_delta, K >= 64, arm = stock-t0")
_sv = [r for r in _o0 if r["size"] == "ov" and int(r["K"]) <= 8]
rec("E8.outside_kernels.sparse_ov", "; ".join(f"K={r['K']}: wall {float(r['delta_wall_s']):+.3f} s, outside kernels {float(r['delta_outside_kernels_s']):+.3f} s, kernels {float(r['delta_kernel_s']):+.3f} s" for r in _sv) + " (oversubscribed, t0 vs t51)", _OF, "delta_wall_s, delta_outside_kernels_s, delta_kernel_s; oversubscribed K <= 8, t0")


# ---------- MDE at the family alpha (Gate C7; MDE_AUDIT.md). mde_s is the alpha-0.05 value; the family value rescales it by the z ratio ----------
from scipy.stats import norm as _norm
_Z80 = _norm.ppf(0.80)
_zr = lambda m: (_norm.ppf(1 - 0.05 / (2 * m)) + _Z80) / (_norm.ppf(0.975) + _Z80)
_sw = {r["arm"]: r for r in csv.DictReader(open("results/analysis/gate_e/e6/secondary_wall.csv"))}
rec("E6.mde_family.stencil_wall", "; ".join(f"{a.split('-')[1]}: {float(r['mde_s']) * _zr(3):.4f} s = {100 * float(r['mde_s']) * _zr(3) / float(r['median_base']):.2f}% of the C0 median (unadjusted {float(r['mde_s']):.4f} s = {100 * float(r['mde_s']) / float(r['median_base']):.2f}%)" for a, r in sorted(_sw.items())) + " [Holm family of 3]",
    "results/analysis/gate_e/e6/secondary_wall.csv", "mde_s x z-ratio(alpha 0.05/3), / median_base")
_f2 = {r["arm"]: r for r in csv.DictReader(open("results/analysis/gate_e/e6/family2_graphbfs.csv"))}
rec("E6.mde_family.graphbfs", "; ".join(f"{a}: {float(r['mde_s']) * _zr(2):.4f} s = {100 * float(r['mde_s']) * _zr(2) / float(r['median_base']):.2f}% (unadjusted {100 * float(r['mde_s']) / float(r['median_base']):.2f}%)" for a, r in sorted(_f2.items())) + " [Holm family of 2]",
    "results/analysis/gate_e/e6/family2_graphbfs.csv", "mde_s x z-ratio(alpha 0.05/2), / median_base")
_e4 = [r for r in csv.DictReader(open("results/analysis/gate_e/e4/primary_comparisons.csv")) if r["family"] == "F1" and r["workload"] == "graphbfs"]
rec("E4.mde_family.graphbfs.F1", "; ".join(f"{r['arm']}: {float(r['mde_bonf_s']):.4f} s = {100 * float(r['mde_bonf_s']) / float(r['median_base']):.2f}% (unadjusted {float(r['mde_s']):.4f} s = {100 * float(r['mde_s']) / float(r['median_base']):.2f}%)" for r in _e4) + " [alpha 0.05/18; mde_bonf_s]",
    "results/analysis/gate_e/e4/primary_comparisons.csv", "mde_bonf_s (alpha 0.05/18, set in e4_analyze.py:21), / median_base")

with open(OUT, "w") as fh:
    fh.write("# Gate C1 — Evidence extract (generated)\n\n")
    fh.write("Generated by `tests/c1_evidence.py` from **committed derived files only**. Every number a\n")
    fh.write("C1 proposal cites as evidence is one of the values below (quoted by evidence id), or is\n")
    fh.write("marked PROSE-ONLY in the proposal. Regenerate with `python3 tests/c1_evidence.py`.\n\n")
    fh.write("| evidence id | value | file | field / computation |\n|---|---|---|---|\n")
    for eid, v, p, fld in rows:
        fh.write(f"| `{eid}` | {v} | `{p}` | {fld} |\n")
print(f"{len(rows)} evidence rows -> {OUT}")
for eid, v, p, fld in rows:
    print(f"{eid}: {v}")
