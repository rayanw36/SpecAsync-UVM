#!/usr/bin/env python3
"""Gate E6 analysis (E6_PREREGISTRATION.md). Statistical helpers are imported unchanged
from tests/e09b_analyze.py (H.mwu, H.holm, H.compare, H.tukey_keep). Refuses to run on
fewer rows than pre-registered: 110 rows, or 80 rows when Family 2 was skipped under the
skip rule (then e6/family2_skipped.txt must exist).

  e6_analyze.py --control              positive control on E5's committed e5_runs.csv
  e6_analyze.py [DATA_DIR [FIG_PREFIX]] the pre-registered analysis
"""
import csv, os, statistics as st, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
_argv, sys.argv = sys.argv, sys.argv[:1]
import e09b_analyze as H  # noqa: E402
sys.argv = _argv

E5_RUNS = "results/analysis/gate_e/e5/e5_runs.csv"
OUTDIR = "results/analysis/gate_e/e6"
FIG = "results/analysis/gate_e/e6_threshold"
RAW = "results/phaseB1/gate_e6/sweep"
N_FULL, N_FAM1 = 110, 80
F1_BASES = ["C0-t0", "C0-t10", "C0-t25", "C0-t51"]
SEC_T = ["t0", "t10", "t25"]
F2 = ["C0-t0", "C0-t25"]


def load(path):
    rows = list(csv.DictReader(open(path)))
    for r in rows:
        r["cell"] = r["label"].split(" ", 1)[1]           # e.g. "C7W512-t51"
        r["wl"] = r["workload"]
    return rows


def vals(rows, wl, cell, key="wall_s"):
    return [float(r[key]) if key == "wall_s" else float(r[key]) for r in rows if r["wl"] == wl and r["cell"] == cell]


def compare(rows, base, arm, key="wall_s", wl="stencil"):
    """Pre-registered comparison: arm vs base (negative delta = arm faster). Uses H's MWU/Tukey/MDE."""
    b, a = vals(rows, wl, base, key), vals(rows, wl, arm, key)
    c = H.compare(b, a)                                    # dict with delta_s, delta_pct, p, mde_s, cohen_d, ...
    bk, ak = H.tukey_keep(b), H.tukey_keep(a)
    d2 = H.compare(bk, ak)
    c.update(base=base, arm=arm, n_base=len(b), n_arm=len(a), noout_delta_s=d2["delta_s"], noout_p=d2["p"],
             med_base=st.median(b), med_arm=st.median(a))
    return c


def demand_ratio(rows, t_arm, t_base, wl="stencil"):
    base = st.median(vals(rows, wl, t_base, "demand_faults"))
    arm = st.median(vals(rows, wl, t_arm, "demand_faults"))
    return 1 - arm / base, base, arm


def control():
    rows = load(E5_RUNS)
    rows = [r for r in rows if r["wl"] == "stencil"]
    c = compare(rows, "C0-t51", "C7W512-t51")
    dval, b, a = demand_ratio(rows, "C7W512-t51", "C0-t51")
    ok = (f"{c['delta_pct']:+.2f}" == "-5.26" and f"{c['p']:.2e}" == "1.08e-05" and f"{dval:+.4f}" == "+0.4009")
    lines = [
        "# E6 analyzer positive control (run on E5's committed e5_runs.csv)",
        f"comparison: C7W512-t51 vs C0-t51 (E5 n = {c['n_base']} / {c['n_arm']})",
        f"median C0-t51 = {c['med_base']:.4f} s; median C7W512-t51 = {c['med_arm']:.4f} s",
        f"delta = {c['delta_s']:+.4f} s = {c['delta_pct']:+.2f}%  (E5 reported -5.26%)",
        f"MWU two-sided p = {c['p']:.2e}  (E5 reported 1.08e-05)",
        f"D(51) = 1 - median demand faults C7W512 / C0 = {dval:+.4f}  (E5 reported +0.4009; medians {a:,.0f} / {b:,.0f})",
        f"CONTROL: {'PASS — reproduces E5' if ok else 'FAIL — does not reproduce E5'}",
    ]
    out = "\n".join(lines) + "\n"
    os.makedirs(OUTDIR, exist_ok=True)
    open(f"{OUTDIR}/analyzer_positive_control.txt", "w").write(out)
    print(out)
    return 0 if ok else 3


def analyze(data_dir, fig):
    global OUTDIR
    order = list(csv.DictReader(open(f"{data_dir}/e6_order.csv")))
    rows = load(f"{data_dir}/e6_runs.csv")
    skipped = os.path.exists(f"{data_dir}/family2_skipped.txt")
    need = N_FAM1 if skipped else N_FULL
    if skipped and len(rows) == N_FULL:
        sys.exit("REFUSING: family2_skipped.txt exists but 110 rows are present (inconsistent record).")
    if len(rows) < need or (not skipped and len(rows) != N_FULL):
        sys.exit(f"REFUSING: {len(rows)} rows present; pre-registered {need} "
                 f"({'Family 2 skipped' if skipped else 'full'}). No interim analysis.")
    for o, r in zip(order, rows):
        assert (o["idx"], o["label"]) == (r["idx"], r["label"]), ("order mismatch", o["idx"])
    for r in rows:   # D5 (servicing time under the VA-space lock) from the decomp ring dump, if present
        dpath = f"{RAW}/e3b_{r['idx']}_decomp.bin"
        r["d5_ns"] = (str(sum(x[11] for x in struct.iter_unpack("<12Q4I", open(dpath, "rb").read())))
                      if os.path.exists(dpath) else "")

    # --- Family 1: C7W512-t51 vs each C0-t (Holm over 4)
    f1 = [compare(rows, b, "C7W512-t51") for b in F1_BASES]
    thr, sig = H.holm([c["p"] for c in f1])
    for c, t, s in zip(f1, thr, sig):
        c.update(holm_thr=t, holm_sig=s)
    v_a = all(c["holm_sig"] and c["delta_s"] < 0 for c in f1)
    verdict = ("V-A: speculation beats tuning (C7W512-t51 Holm-significantly faster than all four C0-t)" if v_a
               else "V-B: tuning matches or beats speculation (FALSIFICATION TRIGGER for 'the Stencil gain requires speculation'): "
                    + ", ".join(c["base"] for c in f1 if not (c["holm_sig"] and c["delta_s"] < 0)) + " not Holm-significantly slower")

    # --- Secondary: within-threshold, wall-clock and demand faults (Holm 3 each)
    sec_w = [compare(rows, f"C0-{t}", f"C7W512-{t}") for t in SEC_T]
    tw, sw = H.holm([c["p"] for c in sec_w])
    for c, t, s in zip(sec_w, tw, sw):
        c.update(holm_thr=t, holm_sig=s)
    sec_d = [compare(rows, f"C0-{t}", f"C7W512-{t}", key="demand_faults") for t in SEC_T]
    td, sd = H.holm([c["p"] for c in sec_d])
    for c, t, s in zip(sec_d, td, sd):
        c.update(holm_thr=t, holm_sig=s)
    DR = {t: demand_ratio(rows, f"C7W512-{t}", f"C0-{t}")[0] for t in SEC_T + ["t51"]}

    # --- Family 2 (GraphBFS, Holm 2): C0-t0, C0-t25 vs C0-t51
    f2 = []
    if not skipped:
        f2 = [compare(rows, "C0-t51", b, wl="graphbfs") for b in F2]
        t2, s2 = H.holm([c["p"] for c in f2])
        for c, t, s in zip(f2, t2, s2):
            c.update(holm_thr=t, holm_sig=s)

    # --- Expectations X1–X4 (descriptive; not part of the verdict)
    df_c0 = {t: st.median(vals(rows, "stencil", f"C0-{t}", "demand_faults")) for t in ["t0", "t10", "t25", "t51"]}
    w_c0 = {t: st.median(vals(rows, "stencil", f"C0-{t}")) for t in ["t0", "t10", "t25", "t51"]}
    x1 = df_c0["t0"] < df_c0["t10"] < df_c0["t25"] < df_c0["t51"]
    fastest = min(w_c0, key=w_c0.get)
    x2 = fastest != "t51"
    x3 = "not scored (expectation 'about even' has no direction); verdict recorded: " + verdict.split(":")[0]
    x4_w = sec_w[0]
    x4 = (DR["t0"] <= 0.20) and x4_w["holm_sig"] and x4_w["delta_s"] < 0

    # --- mechanism, descriptive (Stencil, every cell)
    mech = []
    for t in ["t0", "t10", "t25", "t51"]:
        for arm in (f"C0-{t}", f"C7W512-{t}"):
            v = lambda k: st.median(float(r[k]) for r in rows if r["wl"] == "stencil" and r["cell"] == arm)  # noqa
            df = v("demand_faults")
            d5s = [float(r["d5_ns"]) for r in rows if r["wl"] == "stencil" and r["cell"] == arm and r["d5_ns"] != ""]
            d5 = st.median(d5s) if d5s else float("nan")
            mech.append(dict(cell=arm, n=sum(1 for r in rows if r["cell"] == arm and r["wl"] == "stencil"),
                             wall_median_s=st.median(vals(rows, "stencil", arm)), demand_faults=df,
                             d5_ns_per_demand_fault=d5 / df if df else float("nan"),
                             fault_already_resident=v("fault_already_resident"),
                             spec_pages_requested=v("spec_pages_requested"), drops=v("drops"),
                             ft_fast_verified=v("ft_fast_verified") if arm.startswith("C7") else ""))

    # --- write outputs
    def wcsv(name, items):
        if not items: return
        with open(f"{OUTDIR}/{name}", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(items[0].keys()), extrasaction="ignore")
            w.writeheader(); w.writerows(items)
    wcsv("family1_primary.csv", f1); wcsv("secondary_wall.csv", sec_w); wcsv("secondary_demand.csv", sec_d)
    wcsv("family2_graphbfs.csv", f2); wcsv("mechanism.csv", mech)
    lines = [f"VERDICT: {verdict}", "",
             "Family 1 (Stencil, C7W512-t51 vs C0-t; Holm 4):"]
    for c in f1:
        lines.append(f"  {c['base']:8s} med {c['med_base']:.4f}  C7W512-t51 med {c['med_arm']:.4f}  delta {c['delta_pct']:+.2f}%  p {c['p']:.2e}  Holm-thr {c['holm_thr']:.4f}  sig {c['holm_sig']}  d {c['cohen_d']:+.2f}  MDE {c['mde_s']:.4f}  noout {c['noout_delta_s']:+.4f}/{c['noout_p']:.1e}")
    lines += ["", "D(t) (demand-fault reduction, E5 definition):"]
    for t in SEC_T + ["t51"]:
        lines.append(f"  {t}: D = {DR[t]:+.4f}")
    lines += ["", "Secondary wall-clock (within-threshold, Holm 3):"]
    for c in sec_w:
        lines.append(f"  {c['comparison'] if 'comparison' in c else c['base']+' vs '+c['arm']}: delta {c['delta_pct']:+.2f}%  p {c['p']:.2e}  Holm-thr {c['holm_thr']:.4f}  sig {c['holm_sig']}")
    lines += ["", "Secondary demand faults (Holm 3):"]
    for c in sec_d:
        lines.append(f"  {c['base']} vs {c['arm']}: delta {c['delta_pct']:+.2f}%  p {c['p']:.2e}  sig {c['holm_sig']}")
    if f2:
        lines += ["", "Family 2 (GraphBFS, Holm 2): arm vs C0-t51"]
        for c in f2:
            lines.append(f"  {c['arm']} vs C0-t51: delta {c['delta_pct']:+.2f}%  p {c['p']:.2e}  Holm-thr {c['holm_thr']:.4f}  sig {c['holm_sig']}")
    else:
        lines += ["", "Family 2: SKIPPED under the skip rule (recorded in family2_skipped.txt)."]
    lines += ["", "Expectations (descriptive, not part of the verdict):",
              f"  X1 C0 demand faults fall monotonically with t: {'HELD' if x1 else 'FAILED'}  ({df_c0})",
              f"  X2 C0's fastest threshold is below 51: {'HELD' if x2 else 'FAILED'}  (fastest = {fastest}; {w_c0})",
              f"  X3 {x3}",
              f"  X4 within-threshold D(0) <= 0.20 AND wall-clock gain at t0 Holm-significant: {'HELD' if x4 else 'FAILED'}  (D(0) = {DR['t0']:+.4f}; delta {x4_w['delta_pct']:+.2f}%, sig {x4_w['holm_sig']})"]
    open(f"{OUTDIR}/primary_report.txt", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))

    # --- figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ts = [0, 10, 25, 51]
    fig_, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, key, ylab in ((axes[0], "demand_faults", "demand faults per run"), (axes[1], "wall_s", "process wall-clock (s)")):
        for arm, col, dx in (("C0", "tab:blue", -0.8), ("C7W512", "tab:green", 0.8)):
            meds = []
            for t in ts:
                cell = f"{arm}-t{t}"
                v = vals(rows, "stencil", cell, key)
                ax.scatter([t + dx] * len(v), v, s=12, color=col, alpha=0.45, zorder=3)
                meds.append(st.median(v))
            ax.plot([t + dx for t in ts], meds, "o-", color=col, lw=1.8, zorder=4, label=f"{arm} median (points: runs)")
        ax.set_xticks(ts); ax.set_xticklabels(["0", "10", "25", "51 (default)"])
        ax.set_xlabel("uvm_perf_prefetch_threshold"); ax.set_ylabel(ylab); ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    fig_.suptitle("Gate E6: Stencil-24K, prefetcher on; C7W512 = cheap oracle + W=512 (n=10 per cell)", fontsize=10)
    fig_.tight_layout()
    for ext in ("png", "pdf"):
        fig_.savefig(f"{fig}.{ext}", dpi=150)
    return 0


if __name__ == "__main__":
    if "--control" in sys.argv:
        sys.exit(control())
    dd = sys.argv[1] if len(sys.argv) > 1 else D
    ff = sys.argv[2] if len(sys.argv) > 2 else FIG
    sys.exit(analyze(dd, ff))
