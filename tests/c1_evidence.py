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
