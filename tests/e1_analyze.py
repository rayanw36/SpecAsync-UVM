#!/usr/bin/env python3
"""Gate E1 Part C: pre-registered analysis (E1_PREREGISTRATION.md).

Statistical helpers (MWU exact/asymptotic, Holm step-down, MDE, Cohen's d,
Tukey fences) are imported unchanged from tests/e09b_analyze.py.

Refuses to run unless the CSV holds all rows of the committed order (no
interim peeking). Usage: e1_analyze.py [DATA_DIR [FIG_PREFIX]]. Writes
primary_comparisons.csv, mechanism_by_L.csv, integrity.txt under DATA_DIR,
the central figure FIG_PREFIX.{png,pdf}, and a context figure
FIG_PREFIX_with_e09b_context.{png,pdf} overlaying E0.9b's C6 medians as a
separate, untested series.
"""
import csv
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(__file__))
_argv, sys.argv = sys.argv, sys.argv[:1]
import e09b_analyze as H  # noqa: E402
sys.argv = _argv
H.Z_MDE_BONF = 2.734369 + 0.841621  # two-sided alpha=0.05/8 (E1 family of 8), power 0.80

LS = ["1", "16", "256", "4096"]
WLS = ["stencil", "graphbfs"]
DISTINCT = {"stencil": 1125000, "graphbfs": 287956}
D = sys.argv[1] if len(sys.argv) > 1 else "results/analysis/gate_e/e1"
FIG = sys.argv[2] if len(sys.argv) > 2 else "results/analysis/gate_e/e1_wallclock_vs_L"
E09B = "results/analysis/gate_e/e09b/sweep_runs.csv"


def main():
    order = list(csv.DictReader(open(f"{D}/e1_order.csv")))
    rows = list(csv.DictReader(open(f"{D}/e1_runs.csv")))
    if len(rows) != len(order):
        sys.exit(f"REFUSING: {len(rows)} of {len(order)} rows present -- no interim analysis")

    integ = [f"rows {len(rows)} / {len(order)}"]
    mism = [o["idx"] for o, r in zip(order, rows)
            if (o["idx"], o["workload"], o["arm"], o["L"]) != (r["idx"], r["workload"], r["arm"], r["L"])]
    integ.append(f"order adherence: {len(order) - len(mism)} / {len(order)} match in sequence; mismatches: {mism}")
    integ.append(f"srcversions: {sorted(set(r['srcversion'] for r in rows))}")
    integ.append(f"exit codes: {sorted(set(r['exit_code'] for r in rows))}")
    nz = [(r["idx"], r["dmesg_new_lines"]) for r in rows if r["dmesg_new_lines"] != "0"]
    integ.append(f"dmesg new lines: total {sum(int(r['dmesg_new_lines']) for r in rows)}; runs with any: {nz}")
    mb = [int(r["mem_before_kb"]) for r in rows]; ma = [int(r["mem_after_kb"]) for r in rows]
    integ.append(f"MemAvailable kB: before {min(mb)}-{max(mb)}; after {min(ma)}-{max(ma)}; first {mb[0]} last {ma[-1]}")
    integ.append(f"disk free GB: min {min(float(r['disk_free_gb']) for r in rows)}")
    c7 = [r for r in rows if r["arm"] == "C7"]
    bad = [r["idx"] for r in c7 if int(r["ft_predictions"]) != int(r["enqueued"]) + int(r["drops"])]
    integ.append(f"identity ft_predictions = enqueued + drops: holds on {len(c7) - len(bad)} / {len(c7)} C7 runs; fails on {bad}")
    open(f"{D}/integrity.txt", "w").write("\n".join(integ) + "\n")
    print("\n".join(integ))

    wall = {}
    for r in rows:
        wall.setdefault((r["workload"], r["arm"], r["L"]), []).append(float(r["wall_s"]))

    comps = []
    for wl in WLS:
        for L in LS:
            b, c = wall[(wl, "C0", "")], wall[(wl, "C7", L)]
            d = dict(workload=wl, L=L, comparison=f"C7-L{L} vs C0", baseline="C0")
            d.update(H.compare(b, c))
            bk, ck = H.tukey_keep(b), H.tukey_keep(c)
            d2 = H.compare(bk, ck)
            d.update({"noout_n_base": len(bk), "noout_n_c7": len(ck), "noout_delta_s": d2["delta_s"], "noout_p": d2["p"]})
            comps.append(d)
    # H.compare names its columns *_c6; rename for this gate
    comps = [{k.replace("_c6", "_c7"): v for k, v in c.items()} for c in comps]
    thr, sig = H.holm([c["p"] for c in comps])
    thr2, sig2 = H.holm([c["noout_p"] for c in comps])
    for c, t, s, t2, s2 in zip(comps, thr, sig, thr2, sig2):
        c["holm_threshold"], c["holm_sig"] = t, s
        c["noout_holm_threshold"], c["noout_holm_sig"] = t2, s2
        c["verdict"] = ("C7 faster" if c["delta_s"] < 0 else "C7 slower") if s else "no significant difference"
        c["falsification_trigger"] = s and (c["median_base"] - c["median_c7"]) > c["mde_s"]
    with open(f"{D}/primary_comparisons.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(comps[0])); w.writeheader(); w.writerows(comps)
    for c in comps:
        print(f"{c['workload']:8s} {c['comparison']:14s} C0 {c['median_base']:.4f} C7 {c['median_c7']:.4f} "
              f"d {c['delta_s']:+.4f}s ({c['delta_pct']:+.2f}%) p={c['p']:.2e} [{c['mwu_method']}] thr={c['holm_threshold']:.5f} "
              f"{c['verdict']:26s} d={c['cohen_d']:+.2f} MDE={c['mde_s']:.4f} MDEbonf={c['mde_bonf_s']:.4f} | no-out d "
              f"{c['noout_delta_s']:+.4f} p={c['noout_p']:.2e} sig={c['noout_holm_sig']} n={c['noout_n_base']}/{c['noout_n_c7']}"
              + ("  ***FALSIFICATION TRIGGER***" if c["falsification_trigger"] else ""))
    print("FALSIFICATION TRIGGER FIRED:", any(c["falsification_trigger"] for c in comps))

    mech = []
    for wl in WLS:
        for arm, L in [("C0", "")] + [("C7", L) for L in LS]:
            rs = [r for r in rows if (r["workload"], r["arm"], r["L"]) == (wl, arm, L)]
            g = lambda k: st.median(int(r[k]) for r in rs)  # noqa: E731
            mech.append(dict(workload=wl, arm=arm, L=L, n=len(rs), demand_faults=g("demand_faults"),
                             ft_predictions=g("ft_predictions"), enqueued=g("enqueued"), not_enqueued_drops=g("drops"),
                             spec_migrations=g("spec_migrations"),
                             lost_after_enqueue=st.median(int(r["enqueued"]) - int(r["spec_migrations"]) for r in rs),
                             prestaged_coverage_upper_bound_pct=100 * g("spec_migrations") / DISTINCT[wl],
                             fault_already_resident=g("fault_already_resident"),
                             fault_already_resident_min=min(int(r["fault_already_resident"]) for r in rs),
                             fault_already_resident_max=max(int(r["fault_already_resident"]) for r in rs),
                             spec_hits_10ms_staleness_counter=g("spec_hits"),
                             ft_skipped=g("ft_skipped"), ft_exhausted=g("ft_exhausted")))
    with open(f"{D}/mechanism_by_L.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(mech[0])); w.writeheader(); w.writerows(mech)
    for m in mech:
        print(m)
    c0far = [(m["workload"], m["fault_already_resident_min"], m["fault_already_resident_max"]) for m in mech if m["arm"] == "C0"]
    print("C0 fault_already_resident (min, max) per workload:", c0far,
          "-> ATTRIBUTABLE TO SPECULATION" if all(a == 0 and b == 0 for _, a, b in c0far)
          else "-> NONZERO IN C0: counter NOT attributable to speculation in this gate")

    # ---- figures
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ctx = {}
    if os.path.exists(E09B):
        for r in csv.DictReader(open(E09B)):
            ctx.setdefault((r["workload"], r["arm"], r["L"]), []).append(float(r["wall_s"]))
    xs = [int(L) for L in LS]
    for with_ctx in (False, True):
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
        for ax, wl, title in zip(axes, WLS, ["Stencil-24K", "GraphBFS-23"]):
            v = wall[(wl, "C0", "")]
            q = st.quantiles(v, n=4, method="inclusive")
            ax.axhline(st.median(v), color="tab:blue", lw=1.5, label="C0 median, this gate (IQR shaded)")
            ax.axhspan(q[0], q[2], color="tab:blue", alpha=0.15)
            for x, L in zip(xs, LS):
                vv = wall[(wl, "C7", L)]
                ax.scatter([x] * len(vv), vv, s=12, color="tab:green", alpha=0.5, zorder=3)
            ax.plot(xs, [st.median(wall[(wl, "C7", L)]) for L in LS], "o-", color="tab:green", lw=1.8, zorder=4,
                    label="C7-L median, prefetch on (points: runs)")
            if with_ctx and ctx:
                ax.plot(xs, [st.median(ctx[(wl, "C6", L)]) for L in LS], "s--", color="0.45", lw=1.2, zorder=2,
                        label="E0.9b C6-L median, prefetch off\n(separate session; context only, not tested)")
            ax.set_xscale("log", base=2); ax.set_xticks(xs); ax.set_xticklabels(LS)
            ax.set_xlabel("first-touch lookahead L (pages)"); ax.set_ylabel("process wall-clock (s)")
            ax.set_title(f"{title} (n=10 per cell)"); ax.grid(alpha=0.3)
        axes[0].legend(fontsize=7.5, loc="best")
        fig.suptitle("Gate E1: wall-clock vs lookahead, prefetcher on (RTX 5070 Ti, 595.91.07, kernel 7.0.0-34)"
                     + (" -- with E0.9b context" if with_ctx else ""), fontsize=10)
        fig.tight_layout()
        for ext in ("png", "pdf"):
            fig.savefig(f"{FIG}{'_with_e09b_context' if with_ctx else ''}.{ext}", dpi=150)


if __name__ == "__main__":
    main()
