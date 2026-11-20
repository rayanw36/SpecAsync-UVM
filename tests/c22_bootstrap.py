#!/usr/bin/env python3
"""C22 M5 / V-4 / VII-3: 95% bootstrap CI of the difference of medians, as a percentage of the baseline median, for every comparison the paper cites.
10,000 resamples within cells (each cell resampled independently, with replacement, same n), seed 20261117 (numpy default_rng, comparisons in the fixed order below),
percentile interval; CI = 100 * (median(arm*) - median(base*)) / median(base) with median(base) the observed baseline median. Observed delta, MWU p and the Holm decision are the committed
analysis (read from the gates' CSVs; the medians recomputed here from the run files must equal the CSV medians, asserted). Holm-adjusted p is recomputed within each CSV's family.
Output: consolidation/C22_BOOTSTRAP_CI.csv (+ answers in C22_BOOTSTRAP_CI.md)."""
import csv, os, statistics as st, sys
import numpy as np
from scipy.stats import norm
sys.path.insert(0, "tests")
_a, sys.argv = sys.argv, sys.argv[:1]
import e09b_analyze as H   # noqa: E402  (tukey_keep, unchanged)
sys.argv = _a
GE = "results/analysis/gate_e"; T4 = "results/analysis/t4"
rd = lambda p: list(csv.DictReader(open(p)))   # noqa: E731
B, SEED = 10000, 20261117
rng = np.random.default_rng(SEED)
Z80 = norm.ppf(0.80); zr = lambda m: (norm.ppf(1 - 0.05 / (2 * m)) + Z80) / (norm.ppf(0.975) + Z80)   # noqa: E731
def holm_adj(ps):
    m = len(ps); order = sorted(range(m), key=lambda i: ps[i]); adj = [0.0] * m; run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * ps[i])); adj[i] = run
    return adj
def boot(base, arm):
    base, arm = np.array(base), np.array(arm)
    ib = rng.integers(0, len(base), size=(B, len(base))); ia = rng.integers(0, len(arm), size=(B, len(arm)))
    d = np.median(arm[ia], axis=1) - np.median(base[ib], axis=1)
    mb = np.median(base)
    return tuple(100 * np.percentile(d, [2.5, 97.5]) / mb)
out = []
def add(gate, comp, runs, base_sel, arm_sel, col, row, eid, fam_p, fam_i, mde_pct):
    b = [float(r[col]) for r in runs if base_sel(r)]; a = [float(r[col]) for r in runs if arm_sel(r)]
    assert len(b) >= 5 and len(a) >= 5, (eid, len(b), len(a))
    mb, ma = st.median(b), st.median(a)
    assert abs(mb - float(row["median_base"] if "median_base" in row else row["med_base"])) < 1e-6 * abs(mb) + 1e-9, (eid, "base median")
    assert abs(ma - float(row["median_c6"] if "median_c6" in row else row["median_arm"])) < 1e-6 * abs(ma) + 1e-9, (eid, "arm median")
    lo, hi = boot(b, a)
    out.append(dict(gate=gate, comparison=comp, metric=col, delta_pct=100 * (ma / mb - 1), ci_low=lo, ci_high=hi, p=float(row["p"]), holm_sig=row["holm_sig"], fam_i=fam_i, fam_p=fam_p, mde_pct=mde_pct, evidence_id=eid, n_base=len(b), n_arm=len(a), sd_base=st.pstdev(b) if False else (st.stdev(b) if len(b) > 1 else 0), _b=b, _a=a))
def family(gate, rows, runs, spec):
    ps = [float(r["p"]) for r in rows]; adj = holm_adj(ps)
    for i, r in enumerate(rows):
        base_sel, arm_sel, col, comp, eid, mde = spec(r)
        add(gate, comp, runs, base_sel, arm_sel, col, r, eid, len(rows), i, mde)
        out[-1]["holm_p"] = adj[i]
# ---- E4 F1 and F4 (Holm family of 18 = all rows of the CSV)
e4 = rd(f"{GE}/e4/primary_comparisons.csv"); e4r = rd(f"{GE}/e4/e4_runs.csv")
ps = [float(r["p"]) for r in e4]; adj4 = holm_adj(ps)
for i, r in enumerate(e4):
    if r["family"] not in ("F1", "F4"): continue
    wl, arm, bs = r["workload"], r["arm"], r["baseline"]
    add("E4 " + r["family"], f"{wl} {arm} vs {bs}", e4r, lambda x, wl=wl, bs=bs: x["label"] == f"{wl} {bs}", lambda x, wl=wl, arm=arm: x["label"] == f"{wl} {arm}", "wall_s", r,
        f"E4.{r['family']}.{wl}.{arm}_vs_{bs}", len(e4), i, 100 * float(r["mde_bonf_s"]) / float(r["median_base"]))
    out[-1]["holm_p"] = adj4[i]
# ---- E5
e5 = rd(f"{GE}/e5/wallclock_comparisons.csv"); e5r = rd(f"{GE}/e5/e5_runs.csv"); TL = {"51": "t51", "75": "t75", "100": "toff"}
family("E5", e5, e5r, lambda r: ((lambda x, t=r["threshold"]: x["label"] == f"stencil C0-{TL[t]}"), (lambda x, t=r["threshold"]: x["label"] == f"stencil C7W512-{TL[t]}"), "wall_s",
        f"C7W512 vs C0 at t{r['threshold']}", f"E5.wall.t{r['threshold']}", 100 * float(r["mde_bonf_s"]) / float(r["median_base"])))
# ---- E6 (four CSVs = four Holm families)
e6r = rd(f"{GE}/e6/e6_runs.csv")
for fn, gname, wl, col, m, pref in (("family1_primary", "E6 F1", "stencil", "wall_s", 4, "E6.F1"), ("secondary_wall", "E6 wall", "stencil", "wall_s", 3, "E6.wall"),
                                    ("secondary_demand", "E6 demand", "stencil", "demand_faults", 3, "E6.demand"), ("family2_graphbfs", "E6 F2", "graphbfs", "wall_s", 2, "E6.F2")):
    rows = rd(f"{GE}/e6/{fn}.csv")
    family(gname, rows, e6r, lambda r, wl=wl, col=col, m=m, pref=pref: ((lambda x, r=r: x["label"] == f"{wl} {r['base']}"), (lambda x, r=r: x["label"] == f"{wl} {r['arm']}"), col,
            f"{wl} {r['arm']} vs {r['base']}", f"{pref}.{r['arm']}_vs_{r['base']}", 100 * float(r["mde_s"]) * zr(m) / float(r["median_base"])))
# ---- E7, T4
for gate, d, runsf, pre in (("E7", f"{GE}/e7", f"{GE}/e7/e7_runs.csv", "E7"), ("E7-T4", T4, f"{T4}/e7t4_runs.csv", "T4")):
    rr = rd(runsf)
    for fam in ("A", "B"):
        rows = rd(f"{d}/family_{fam.lower()}.csv")
        family(f"{gate} {fam}", rows, rr, lambda r, fam=fam: ((lambda x, r=r, fam=fam: x["workload"] == r["workload"] and x["family"] == fam and x["label"].endswith(r["base"])),
               (lambda x, r=r, fam=fam: x["workload"] == r["workload"] and x["family"] == fam and x["label"].endswith(r["arm"])), "wall_s",
               f"{r['workload']} {r['arm']} vs {r['base']}", f"{pre}.{fam}.{r['workload']}.{r['arm']}_vs_{r['base']}", float(r["mde_family_pct"])))
# ---- E8
e8 = rd(f"{GE}/e8/primary_tests.csv"); e8r = [r for r in rd(f"{GE}/e8/e8_runs.csv") if r["family"] in ("IN", "OV")]
family("E8", e8, e8r, lambda r: ((lambda x, r=r: x["workload"] == r["workload"] and x["label"].endswith("stock-t51")), (lambda x, r=r: x["workload"] == r["workload"] and x["label"].endswith(r["arm"])), "wall_s",
        f"{r['workload']} {r['arm']} vs stock-t51", f"E8.{r['size']}.K{r['K']}.{r['arm']}_vs_stock-t51", float(r["mde_family_pct"])))
# ---- H1, H2
h1 = rd(f"{GE}/h1/h1_tests.csv"); h1r = rd(f"{GE}/h1/h1_runs.csv")
family("H1", h1, h1r, lambda r: ((lambda x, r=r: x["workload"] == r["workload"] and x["label"].endswith("stock-t51")), (lambda x, r=r: x["workload"] == r["workload"] and x["label"].endswith("stock-t0")), "wall_s",
        f"{r['workload']} t0 vs t51 (HMM)", f"H1.{r['workload']}.stock-t0_vs_stock-t51", float(r["mde_family_pct"])))
h2 = rd(f"{GE}/h2/h2_tests.csv"); h2r = rd(f"{GE}/h2/h2_runs.csv")
family("H2", h2, h2r, lambda r: ((lambda x, r=r: x["workload"] == f"{r['alloc']}_k{r['K']}" and int(x["threshold"]) == 51), (lambda x, r=r: x["workload"] == f"{r['alloc']}_k{r['K']}" and int(x["threshold"]) == 0), "wall_s",
        f"{r['alloc']} K={r['K']} t0 vs t51", f"H2.{r['alloc']}_k{r['K']}.t0_vs_t51", float(r["mde_family_pct"])))
# ---- write CSV
for o in out:
    o["ci_excludes_2"] = not (o["ci_low"] <= 2 and o["ci_high"] >= -2) if False else (o["ci_low"] > -2 and o["ci_high"] < 2)   # CI entirely inside (-2, 2): excludes an effect of +-2%
    o["ci_excludes_5"] = (o["ci_low"] > -5 and o["ci_high"] < 5)
    o["ci_sign_conflict"] = (o["ci_low"] > 0 or o["ci_high"] < 0) != (o["holm_sig"] == "True")
with open("results/analysis/consolidation/C22_BOOTSTRAP_CI.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["gate", "comparison", "delta %", "CI low", "CI high", "MWU p", "Holm-adjusted p", "MDE % (family alpha)", "evidence id"])
    for o in out: w.writerow([o["gate"], o["comparison"], f"{o['delta_pct']:.3f}", f"{o['ci_low']:.3f}", f"{o['ci_high']:.3f}", f"{o['p']:.3e}", f"{o['holm_p']:.3e}", f"{o['mde_pct']:.3f}", o["evidence_id"]])
import pickle; pickle.dump(out, open("/tmp/claude-1000/c22/boot.pkl", "wb"))
print(len(out), "comparisons")
