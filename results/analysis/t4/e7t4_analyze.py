#!/usr/bin/env python3
"""E7-T4 analysis (E7T4_PREREGISTRATION.md). Statistics are tests/e7_analyze.py's helpers (-> e09b_analyze), unchanged.
delta = (arm - stock-t51) / stock-t51. T4 data are analysed on their own and NEVER pooled with 5070 Ti data; the
5070 Ti E7 numbers are only read from origin's committed family_a.csv / family_b.csv for a side-by-side table / figure line.

  e7t4_analyze.py --control [OUTFILE]    positive control: E7 Family A from the committed 5070 Ti e7_runs.csv
  e7t4_analyze.py [DATA_DIR]             the pre-registered analysis (refuses unless all pre-registered rows are present)
"""
import csv
import math
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, f"{REPO}/tests")
import e7_analyze as X  # noqa: E402
H = X.H
E7 = f"{REPO}/results/analysis/gate_e/e7"
WLB = [w for w in X.FAM_B_WL if w != "oversub"]   # Amendment 2: oversubscribed Stencil removed
N_FULL = 240


def control(out):
    rows = X.load(f"{E7}/e7_runs.csv")
    c = X.compare(X.pick(rows, "stencil", "stock-t51", family="A"), X.pick(rows, "stencil", "stock-t0", family="A"), 2)
    ok = f"{c['delta_pct']:+.2f}" == "-9.57" and f"{c['p']:.2e}" == "1.08e-05"
    txt = "\n".join(["# E7-T4 analyzer positive control (5070 Ti E7 e7_runs.csv, Family A, stock-t0 vs stock-t51, m = 2)",
                     f"n = {c['n_base']} / {c['n_c6']}; median t51 {c['median_base']:.4f} s, t0 {c['median_c6']:.4f} s",
                     f"delta = {c['delta_pct']:+.2f}%  (E7 reported -9.57%)", f"MWU two-sided p = {c['p']:.2e}  (E7 reported 1.08e-05)",
                     f"CONTROL: {'PASS - reproduces E7 Family A' if ok else 'FAIL'}", ""])
    open(out, "w").write(txt)
    print(txt)
    return 0 if ok else 3


def ref5070():
    fa = {r["arm"]: r for r in csv.DictReader(open(f"{E7}/family_a.csv"))}
    fb = {(r["workload"], r["arm"]): r for r in csv.DictReader(open(f"{E7}/family_b.csv"))}
    return fa, fb


def analyze(d):
    order = [o for o in csv.DictReader(open(f"{HERE}/e7t4_order.csv")) if o["workload"] != "oversub"]
    rows = X.load(f"{d}/e7t4_runs.csv")
    skipped = X.read_skipped(d)
    need = N_FULL - 30 * len(skipped)
    if len(rows) != need:
        sys.exit(f"REFUSING: {len(rows)} rows; pre-registered {need} (skipped: {skipped or 'none'}). No interim analysis.")
    exp = [o for o in order if o["workload"] not in skipped]
    for o, r in zip(exp, rows):
        if (o["idx"], o["label"]) != (r["idx"], r["label"]):
            sys.exit(f"REFUSING: order mismatch at idx {o['idx']}")
        if r["exit_code"] != "0" or r["threshold_readback"] != r["threshold"]:
            sys.exit(f"REFUSING: idx {r['idx']} exit/threshold read-back inconsistent")
    fa = []
    for arm in ("stock-t0", "stock-t10"):
        c = X.compare(X.pick(rows, "stencil", "stock-t51", family="A"), X.pick(rows, "stencil", arm, family="A"), 2)
        c.update(workload="stencil", arm=arm, base="stock-t51")
        fa.append(c)
    X.holm_apply(fa)
    wls = [w for w in WLB if w not in skipped]
    fb = []
    for w in wls:
        for arm in ("stock-t0", "stock-t25"):
            c = X.compare(X.pick(rows, w, "stock-t51", family="B"), X.pick(rows, w, arm, family="B"), 2 * len(wls))
            c.update(workload=w, arm=arm, base="stock-t51")
            fb.append(c)
    X.holm_apply(fb)
    for c in fa + fb:
        c["arm_median"], c["base_median"] = c["median_c6"], c["median_base"]

    def wcsv(name, items):
        with open(f"{d}/{name}", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(items[0].keys()), extrasaction="ignore")
            w.writeheader()
            w.writerows(items)
    wcsv("family_a.csv", fa)
    wcsv("family_b.csv", fb)

    replicated = fa[0]["holm_sig"] and fa[0]["delta_s"] < 0
    slow = [c for c in fb if c["arm"] in ("stock-t0", "stock-t25") and c["holm_sig"] and c["delta_s"] > 0]
    trigger = bool(slow)
    xa = replicated
    xb_wl = [w for w in ("sweep16k", "stream", "sgemm") if w in wls]
    xb_d = {w: next(c for c in fb if c["workload"] == w and c["arm"] == "stock-t0")["delta_s"] for w in xb_wl}
    xb = all(v < 0 for v in xb_d.values()) if xb_wl else None
    xc_bad = [c["workload"] for c in fb if c["arm"] == "stock-t0" and c["holm_sig"] and c["delta_s"] > 0]
    xc = not xc_bad
    hf = lambda x: "not evaluable" if x is None else ("HELD" if x else "FAILED")  # noqa: E731
    R5a, R5b = ref5070()
    L = []
    if trigger:
        L.append("FALSIFICATION TRIGGER FIRED (dense-workload generality claim): Holm-significant slowdown(s) in Family B: "
                 + "; ".join(f"{c['workload']} {c['arm']} {c['delta_pct']:+.2f}% (p {c['p']:.2e}, Holm-thr {c['holm_thr']:.4f})" for c in slow))
    else:
        L.append("Falsification trigger: NOT fired (no Holm-significant slowdown at t0 or t25 in Family B).")
    L.append(f"Verdict: {'REPLICATED' if replicated else 'NOT REPLICATED'} (Family A stock-t0 vs stock-t51: {fa[0]['delta_pct']:+.2f}%, "
             f"p {fa[0]['p']:.2e}, Holm-thr {fa[0]['holm_thr']:.4f}, significant={fa[0]['holm_sig']})")
    L += ["", "Family A (Stencil-24K, stock; Holm of 2; delta = (arm - t51) / t51)"]
    for c in fa:
        L.append(f"  {c['arm']:9s} med {c['median_c6']:.4f} vs t51 {c['median_base']:.4f}  delta {c['delta_pct']:+.2f}%  p {c['p']:.2e}  "
                 f"Holm-thr {c['holm_thr']:.4f}  sig {c['holm_sig']}  d {c['cohen_d']:+.2f}  MDE {c['mde_s']:.4f} s ({c['mde_pct']:.2f}%)  "
                 f"MDE@family {c['mde_family_s']:.4f} s ({c['mde_family_pct']:.2f}%)  no-outliers {c['noout_delta_s']:+.4f} s / p {c['noout_p']:.1e}"
                 f"  [outliers base/arm {c['n_outliers_base']}/{c['n_outliers_arm']}]")
    L += ["", f"Family B (one Holm family of {len(fb)})"]
    for c in fb:
        tag = "SLOWER" if (c["holm_sig"] and c["delta_s"] > 0) else ("FASTER" if (c["holm_sig"] and c["delta_s"] < 0) else "n.s.")
        L.append(f"  {c['workload']:10s} {c['arm']:9s} med {c['median_c6']:.4f} vs t51 {c['median_base']:.4f}  delta {c['delta_pct']:+.2f}%  p {c['p']:.2e}  "
                 f"Holm-thr {c['holm_thr']:.4f}  {tag}  d {c['cohen_d']:+.2f}  MDE {c['mde_s']:.4f} s ({c['mde_pct']:.2f}%)  "
                 f"MDE@family {c['mde_family_pct']:.2f}%  no-outliers {c['noout_delta_s']:+.4f} s / p {c['noout_p']:.1e}"
                 f"  [outliers {c['n_outliers_base']}/{c['n_outliers_arm']}]")
    if skipped:
        L.append(f"  SKIPPED whole (family_b_skipped.txt): {', '.join(skipped)}")
    L += ["", "Expectations (committed before the run):",
          f"  XA stock-t0 faster than t51 on Stencil-24K, Holm-significant: {hf(xa)}",
          f"  XB Sweep-16K, STREAM, SGEMM faster at t0 than t51, direction only: {hf(xb)}  ("
          + ", ".join(f"{w} {100 * xb_d[w] / next(c for c in fb if c['workload'] == w)['median_base']:+.2f}%" for w in xb_wl) + ")",
          f"  XC no workload significantly slower at t0: {hf(xc)}" + (f"  (violations: {xc_bad})" if xc_bad else "")]
    L += ["", "5070 Ti E7 for comparison (SEPARATE data, never pooled; delta % / Holm-significant in that analysis):"]
    L.append(f"  Stencil-24K t0 {float(R5a['stock-t0']['delta_pct']):+.2f}% ({R5a['stock-t0']['holm_sig']}), t10 {float(R5a['stock-t10']['delta_pct']):+.2f}% ({R5a['stock-t10']['holm_sig']})")
    for w in WLB:
        a, b = R5b.get((w, "stock-t0")), R5b.get((w, "stock-t25"))
        if a and b:
            L.append(f"  {w:10s} t0 {float(a['delta_pct']):+.2f}% ({a['holm_sig']})  t25 {float(b['delta_pct']):+.2f}% ({b['holm_sig']})")
    open(f"{d}/primary_report.txt", "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    figure(rows, wls, fa, fb, R5a, R5b, f"{d}/e7t4_threshold_by_workload")
    return 0


def figure(rows, wls, fa, fb, R5a, R5b, fig):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    INK, MUTED, GRID, HUE, REF = "#1f2328", "#59636e", "#d8dee4", "#2a6fb0", "#8c959f"
    panels = ["stencil"] + wls
    cols = 3
    nr = math.ceil(len(panels) / cols)
    f_, axes = plt.subplots(nr, cols, figsize=(11, 3.2 * nr + 0.4), sharey=False, squeeze=False)
    sig = {(c["workload"], c["arm"]): c["holm_sig"] for c in fa + fb}
    xs = {"stock-t0": 0, "stock-t10": 10, "stock-t25": 25, "stock-t51": 51}
    for ax, w in zip(axes.flat, panels):
        fam = "A" if w == "stencil" else "B"
        base = st.median(X.pick(rows, w, "stock-t51", family=fam))
        cells = [c for c in ("stock-t0", "stock-t10", "stock-t25", "stock-t51") if X.pick(rows, w, c, family=fam)]
        meds = []
        for c in cells:
            v = [100 * (x / base - 1) for x in X.pick(rows, w, c, family=fam)]
            ax.scatter([xs[c]] * len(v), v, s=14, color=HUE, alpha=0.35, zorder=3, linewidths=0)
            meds.append((xs[c], st.median(v)))
            ax.scatter([xs[c]], [meds[-1][1]], s=46, facecolor=HUE if sig.get((w, c), False) else "white", edgecolor=HUE, linewidths=1.6, zorder=5)
        ax.plot([a for a, _ in meds], [b for _, b in meds], color=HUE, lw=1.6, zorder=4, label="Tesla T4 (this gate)")
        ref = [(0, 0.0), (51, 0.0)]
        src = {c: (R5a.get(c) if w == "stencil" else R5b.get((w, c))) for c in ("stock-t0", "stock-t10", "stock-t25")}
        rp = [(xs[c], float(r["delta_pct"])) for c, r in src.items() if r]
        ref = sorted(rp + [(51, 0.0)])
        ax.plot([a for a, _ in ref], [b for _, b in ref], color=REF, lw=1.2, ls="--", zorder=2, label="RTX 5070 Ti (E7, separate data)")
        ax.axhline(0, color=MUTED, lw=0.8)
        ax.set_title(X.WL_TITLE[w], fontsize=10, color=INK, loc="left")
        ax.set_xticks([xs[c] for c in cells])
        ax.set_xticklabels([c.split("-t")[1] for c in cells], fontsize=8, color=MUTED)
        ax.tick_params(axis="y", labelsize=8, colors=MUTED)
        ax.grid(axis="y", color=GRID, lw=0.6)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.set_ylabel("wall-clock vs t51 median (%)", fontsize=8, color=MUTED)
        ax.set_xlabel("uvm_perf_prefetch_threshold", fontsize=8, color=MUTED)
    for ax in axes.flat[len(panels):]:
        ax.axis("off")
    h, l = axes.flat[0].get_legend_handles_labels()
    f_.legend(h, l, loc="lower right", bbox_to_anchor=(0.97, 0.08), fontsize=8, frameon=False, ncol=1)
    f_.suptitle("E7-T4: stock driver 595.91.07 on Tesla T4, wall-clock change vs threshold 51 (n=10 per cell; filled = Holm-significant; dashes = 5070 Ti medians, not pooled)",
                fontsize=9, color=INK, x=0.01, ha="left")
    f_.tight_layout(rect=(0, 0, 1, 0.95))
    for ext in ("png", "pdf"):
        f_.savefig(f"{fig}.{ext}", dpi=150)


if __name__ == "__main__":
    if "--control" in sys.argv:
        k = sys.argv.index("--control")
        sys.exit(control(sys.argv[k + 1] if len(sys.argv) > k + 1 else f"{HERE}/e7t4_positive_control.txt"))
    sys.exit(analyze(sys.argv[1] if len(sys.argv) > 1 else HERE))
