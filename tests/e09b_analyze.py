#!/usr/bin/env python3
"""Gate E0.9b Step 5: pre-registered analysis (E09B_PREREGISTRATION.md).

Refuses to run unless the sweep CSV holds all rows of the committed order
(no interim peeking). Writes, under results/analysis/gate_e/e09b/:
  primary_comparisons.csv, mechanism_by_L.csv, integrity.txt, prediction_test.txt
and the central figure results/analysis/gate_e/e09b_wallclock_vs_L.{png,pdf}.
"""
import csv
import math
import statistics as st
import sys

from scipy.stats import mannwhitneyu

ALPHA = 0.05
Z_MDE = 1.959964 + 0.841621  # two-sided alpha=0.05, power 0.80
Z_MDE_BONF = 2.955167 + 0.841621  # two-sided alpha=0.05/16
LS = ["1", "16", "256", "4096"]
WLS = ["stencil", "graphbfs"]
DISTINCT = {"stencil": 1125000, "graphbfs": 287956}
CEILING = {"stencil": (0.170, 0.217, 0.198), "graphbfs": (-0.0165, 0.0165, 0.0)}  # addendum 46761ec
D = sys.argv[1] if len(sys.argv) > 1 else "results/analysis/gate_e/e09b"
FIG = sys.argv[2] if len(sys.argv) > 2 else "results/analysis/gate_e/e09b_wallclock_vs_L"


def tukey_keep(xs):
    q = st.quantiles(xs, n=4, method="inclusive")
    lo, hi = q[0] - 1.5 * (q[2] - q[0]), q[2] + 1.5 * (q[2] - q[0])
    return [x for x in xs if lo <= x <= hi]


def mwu(x, y):
    tied = len(set(x + y)) < len(x) + len(y)
    r = mannwhitneyu(x, y, alternative="two-sided", method="asymptotic" if tied else "exact")
    return r.statistic, r.pvalue, ("asymptotic" if tied else "exact")


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    thr, sig, alive = [None] * len(ps), [False] * len(ps), True
    for rank, i in enumerate(order):
        thr[i] = ALPHA / (len(ps) - rank)
        alive = alive and ps[i] <= thr[i]
        sig[i] = alive
    return thr, sig


def compare(base, c6):
    sd = math.sqrt(st.variance(base) / len(base) + st.variance(c6) / len(c6))
    pooled = math.sqrt(((len(base) - 1) * st.variance(base) + (len(c6) - 1) * st.variance(c6)) / (len(base) + len(c6) - 2))
    u, p, meth = mwu(c6, base)
    return dict(n_base=len(base), n_c6=len(c6), median_base=st.median(base), median_c6=st.median(c6),
                delta_s=st.median(c6) - st.median(base), delta_pct=100 * (st.median(c6) - st.median(base)) / st.median(base),
                U=u, p=p, mwu_method=meth, cohen_d=(st.mean(c6) - st.mean(base)) / pooled if pooled else float("nan"),
                mde_s=Z_MDE * sd, mde_bonf_s=Z_MDE_BONF * sd)


def main():
    order = list(csv.DictReader(open(f"{D}/sweep_order.csv")))
    rows = list(csv.DictReader(open(f"{D}/sweep_runs.csv")))
    if len(rows) != len(order):
        sys.exit(f"REFUSING: {len(rows)} of {len(order)} sweep rows present -- no interim analysis")

    # ---- integrity
    integ = [f"rows {len(rows)} / {len(order)}"]
    mism = [o["idx"] for o, r in zip(order, rows)
            if (o["idx"], o["workload"], o["arm"], o["L"]) != (r["idx"], r["workload"], r["arm"], r["L"])]
    integ.append(f"order adherence: {len(order) - len(mism)} / {len(order)} rows match committed order in sequence; mismatches: {mism}")
    integ.append(f"srcversions: {sorted(set(r['srcversion'] for r in rows))}")
    integ.append(f"exit codes: {sorted(set(r['exit_code'] for r in rows))}")
    integ.append(f"dmesg new lines per run: total {sum(int(r['dmesg_new_lines']) for r in rows)}, max {max(int(r['dmesg_new_lines']) for r in rows)}")
    mb = [int(r["mem_before_kb"]) for r in rows]; ma = [int(r["mem_after_kb"]) for r in rows]
    integ.append(f"MemAvailable kB: before min {min(mb)} max {max(mb)}; after min {min(ma)} max {max(ma)}; first {mb[0]} last {ma[-1]}")
    integ.append(f"disk free GB: min {min(float(r['disk_free_gb']) for r in rows)}")
    c6rows = [r for r in rows if r["arm"] == "C6"]
    bad_id = [r["idx"] for r in c6rows if int(r["ft_predictions"]) != int(r["enqueued"]) + int(r["drops"])]
    integ.append(f"identity ft_predictions = enqueued + drops: holds on {len(c6rows) - len(bad_id)} / {len(c6rows)} C6 runs; fails on {bad_id}")
    open(f"{D}/integrity.txt", "w").write("\n".join(integ) + "\n")
    print("\n".join(integ))

    wall = {}
    for r in rows:
        wall.setdefault((r["workload"], r["arm"], r["L"]), []).append(float(r["wall_s"]))

    # ---- primary family: 16 comparisons
    comps = []
    for wl in WLS:
        for base in ("C0", "C1"):
            for L in LS:
                b, c = wall[(wl, base, "")], wall[(wl, "C6", L)]
                d = dict(workload=wl, L=L, comparison=f"C6-L{L} vs {base}", baseline=base)
                d.update(compare(b, c))
                bk, ck = tukey_keep(b), tukey_keep(c)
                d2 = compare(bk, ck)
                d.update({"noout_n_base": len(bk), "noout_n_c6": len(ck), "noout_delta_s": d2["delta_s"], "noout_p": d2["p"]})
                comps.append(d)
    thr, sig = holm([c["p"] for c in comps])
    thr2, sig2 = holm([c["noout_p"] for c in comps])
    for c, t, s, t2, s2 in zip(comps, thr, sig, thr2, sig2):
        c["holm_threshold"], c["holm_sig"] = t, s
        c["noout_holm_threshold"], c["noout_holm_sig"] = t2, s2
        c["verdict"] = ("C6 faster" if c["delta_s"] < 0 else "C6 slower") if s else "no significant difference"
        c["falsification_trigger"] = (c["baseline"] == "C0" and s and (c["median_base"] - c["median_c6"]) > c["mde_s"])
    keys = list(comps[0])
    with open(f"{D}/primary_comparisons.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(comps)
    for c in comps:
        print(f"{c['workload']:8s} {c['comparison']:18s} base {c['median_base']:.4f} c6 {c['median_c6']:.4f} "
              f"d {c['delta_s']:+.4f}s ({c['delta_pct']:+.2f}%) p={c['p']:.2e} thr={c['holm_threshold']:.5f} "
              f"{c['verdict']:26s} d={c['cohen_d']:+.2f} MDE={c['mde_s']:.4f} | no-out d {c['noout_delta_s']:+.4f} "
              f"p={c['noout_p']:.2e} sig={c['noout_holm_sig']} n={c['noout_n_base']}/{c['noout_n_c6']}"
              + ("  ***FALSIFICATION TRIGGER***" if c["falsification_trigger"] else ""))
    print("FALSIFICATION TRIGGER FIRED:", any(c["falsification_trigger"] for c in comps))

    # ---- mechanism metrics (medians over the 10 runs of each cell)
    mech = []
    for wl in WLS:
        for arm, L in [("C0", ""), ("C1", "")] + [("C6", L) for L in LS]:
            rs = [r for r in rows if (r["workload"], r["arm"], r["L"]) == (wl, arm, L)]
            g = lambda k: st.median(int(r[k]) for r in rs)  # noqa: E731
            m = dict(workload=wl, arm=arm, L=L, n=len(rs), demand_faults=g("demand_faults"),
                     ft_predictions=g("ft_predictions"), enqueued=g("enqueued"), not_enqueued_drops=g("drops"),
                     spec_migrations=g("spec_migrations"),
                     lost_after_enqueue=st.median(int(r["enqueued"]) - int(r["spec_migrations"]) for r in rs),
                     prestaged_coverage_pct=100 * g("spec_migrations") / DISTINCT[wl],
                     fault_already_resident=g("fault_already_resident"),
                     spec_hits_10ms_staleness_counter=g("spec_hits"),
                     ft_skipped=g("ft_skipped"), ft_unknown_page=g("ft_unknown_page"), ft_exhausted=g("ft_exhausted"))
            mech.append(m)
    with open(f"{D}/mechanism_by_L.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(mech[0])); w.writeheader(); w.writerows(mech)
    for m in mech:
        print(m)

    # ---- prediction test (addendum 46761ec)
    pt = []
    for wl in WLS:
        lo, hi, pt_est = CEILING[wl]
        saving = st.median(wall[(wl, "C1", "")]) - st.median(wall[(wl, "C6", "4096")])
        where = "inside" if lo <= saving <= hi else ("below" if saving < lo else "above")
        pt.append(f"{wl}: measured C6-L4096 saving vs C1 = {saving:+.4f} s; ceiling {pt_est:+.3f} s, "
                  f"interval [{lo:+.4f}, {hi:+.4f}] s -> {where.upper()}")
    open(f"{D}/prediction_test.txt", "w").write("\n".join(pt) + "\n")
    print("\n".join(pt))

    # ---- central figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    xs = [int(L) for L in LS]
    for ax, wl, title in zip(axes, WLS, ["Stencil-24K", "GraphBFS-23"]):
        for ref, col in (("C0", "tab:blue"), ("C1", "tab:gray")):
            v = wall[(wl, ref, "")]
            q = st.quantiles(v, n=4, method="inclusive")
            ax.axhline(st.median(v), color=col, lw=1.5, label=f"{ref} median (IQR shaded)")
            ax.axhspan(q[0], q[2], color=col, alpha=0.12)
        for x, L in zip(xs, LS):
            v = wall[(wl, "C6", L)]
            ax.scatter([x] * len(v), v, s=12, color="tab:red", alpha=0.45, zorder=3)
        ax.plot(xs, [st.median(wall[(wl, "C6", L)]) for L in LS], "o-", color="tab:red", lw=1.8, zorder=4,
                label="C6-L median (points: runs)")
        ax.set_xscale("log", base=2); ax.set_xticks(xs); ax.set_xticklabels(LS)
        ax.set_xlabel("first-touch lookahead L (pages)"); ax.set_ylabel("process wall-clock (s)")
        ax.set_title(f"{title} (n=10 per cell)"); ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8, loc="best")
    fig.suptitle("Gate E0.9b: wall-clock vs lookahead (RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34)", fontsize=10)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(f"{FIG}.{ext}", dpi=150)


if __name__ == "__main__":
    main()
