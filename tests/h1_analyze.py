#!/usr/bin/env python3
"""Gate H1 analysis (H1_PREREGISTRATION.md). Statistical helpers are imported UNCHANGED: e7_analyze (compare, holm_apply, mde_family), which use tests/e09b_analyze.py's
H.mwu / H.holm / H.compare / H.tukey_keep. delta = (arm - t51) / t51; negative = t0 is faster.

  h1_analyze.py --control [SCRATCH_DIR]   positive control: reproduces E8's oversubscribed K = 1 t0 vs t51 (+84.96%, p 1.08e-05) from the committed e8_runs.csv,
                                          and must FAIL on a copy with one cell shifted by 10% (writes only to a scratch directory outside results/)
  h1_analyze.py [DATA_DIR [FIG_PREFIX]]   the pre-registered analysis

Refuses to run unless the rows present equal the order rows minus: cells in dropped_cells.txt and (if ov_skipped.txt exists) the oversubscribed cells.
One Holm family: t0 vs t51 for each of the 5 workloads (Stencil-24K, sparse in-memory K = 512 and K = 1, sparse oversubscribed K = 1 and K = 512), alpha 0.05.
MDE at the family alpha: mde_family_s = (z(1 - 0.05/(2m)) + z(0.80)) * sd, m = number of tests actually in the family (e7_analyze.mde_family)."""
import csv
import math
import os
import statistics as st
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import e7_analyze as A  # noqa: E402
import h1_cells as C  # noqa: E402

H = A.H
E8_RUNS = "results/analysis/gate_e/e8/e8_runs.csv"
E7_FAM_A = "results/analysis/gate_e/e7/family_a.csv"
E8_TESTS = "results/analysis/gate_e/e8/primary_tests.csv"
DATA = "results/analysis/gate_e/h1"
FIG = "results/analysis/gate_e/h1_hmm_threshold"


def lines(path):
    return [l.split(" | ")[0].split(" skipped")[0].strip() for l in open(path) if l.strip() and not l.startswith("#")] if os.path.exists(path) else []


def expected_rows(data_dir, order):
    drop = set(lines(f"{data_dir}/dropped_cells.txt"))
    ov_skip = os.path.exists(f"{data_dir}/ov_skipped.txt")
    return [o for o in order if o["label"] not in drop and not (o["family"] == "OV" and ov_skip)]


def walls(rows, wl, thr):
    return [float(r["wall_s"]) for r in rows if r["workload"] == wl and r["label"].endswith(f"stock-t{thr}")]


def control(scratch=None, perturb=False):
    scratch = scratch or tempfile.mkdtemp(prefix="h1_control_")
    rows = list(csv.DictReader(open(E8_RUNS)))
    base = [float(r["wall_s"]) for r in rows if r["workload"] == "ov_k1" and r["label"].endswith("stock-t51")]
    arm = [float(r["wall_s"]) for r in rows if r["workload"] == "ov_k1" and r["label"].endswith("stock-t0")]
    if perturb:
        arm = [v * 1.10 for v in arm]     # one cell's median shifted by 10%
    c = A.compare(base, arm, 16)
    ok = f"{c['delta_pct']:+.2f}" == "+84.96" and f"{c['p']:.2e}" == "1.08e-05"
    out = ["# H1 analyzer positive control (E8 committed e8_runs.csv, oversubscribed K = 1, stock-t0 vs stock-t51)" + (" -- PERTURBED copy (t0 wall-clock x 1.10)" if perturb else ""),
           f"n = {c['n_base']} / {c['n_c6']}; median t51 = {c['median_base']:.4f} s; median t0 = {c['median_c6']:.4f} s",
           f"delta = {c['delta_pct']:+.2f}%  (E8 reported +84.96%)   MWU p = {c['p']:.2e}  (E8 reported 1.08e-05)",
           f"CONTROL: {'PASS - reproduces E8' if ok else 'FAIL - does not reproduce E8'}"]
    os.makedirs(scratch, exist_ok=True)
    open(f"{scratch}/h1_control{'_perturbed' if perturb else ''}.txt", "w").write("\n".join(out) + "\n")
    print("\n".join(out))
    return ok


def managed_deltas():
    """Managed-mode deltas (t0 vs t51) from the committed E7 / E8 analyses (different sessions; never pooled)."""
    d = {}
    for r in csv.DictReader(open(E7_FAM_A)):
        if r["workload"] == "stencil" and r["arm"] == "stock-t0":
            d["stencil"] = (float(r["delta_pct"]), r["holm_sig"] == "True", "E7 Family A")
    for r in csv.DictReader(open(E8_TESTS)):
        if r["arm"] == "stock-t0" and r["workload"] in ("in_k1", "in_k512", "ov_k1", "ov_k512"):
            d[r["workload"]] = (float(r["delta_pct"]), r["holm_sig"] == "True", "E8")
    return d


def analyze(data_dir, fig):
    order = list(csv.DictReader(open(f"{data_dir}/h1_order.csv")))
    rows = list(csv.DictReader(open(f"{data_dir}/h1_runs.csv")))
    exp = expected_rows(data_dir, order)
    if [r["idx"] for r in rows] != [o["idx"] for o in exp] or any(r["label"] != o["label"] for r, o in zip(rows, exp)):
        sys.exit(f"REFUSING: {len(rows)} rows present, {len(exp)} expected (order minus dropped cells and skipped oversubscribed cells); no interim analysis")
    present = [w for w in C.TESTED if walls(rows, w, 0) and walls(rows, w, 51)]
    tests = []
    for w in present:
        c = A.compare(walls(rows, w, 51), walls(rows, w, 0), len(present))
        c.update(workload=w, arm="stock-t0", base="stock-t51")
        tests.append(c)
    A.holm_apply(tests)
    T = {c["workload"]: c for c in tests}
    fast = lambda w: w in T and T[w]["holm_sig"] and T[w]["delta_s"] < 0   # noqa: E731
    slow = lambda w: w in T and T[w]["holm_sig"] and T[w]["delta_s"] > 0   # noqa: E731
    dense = fast("stencil") or fast("in_k512")
    sparse = slow("ov_k1")
    verdict = "REPLICATED (both directions)" if dense and sparse else "DENSE ONLY" if dense else "SPARSE ONLY" if sparse else "NOT REPLICATED"
    man = managed_deltas()
    exps = {
        "Y1": ("Stencil-24K: t0 faster than t51, Holm-significant", fast("stencil") if "stencil" in T else None),
        "Y2": ("Stencil-24K: the malloc-mode gain is smaller than E7's managed gain", (T["stencil"]["delta_pct"] > man["stencil"][0]) if "stencil" in T else None),
        "Y3": ("sparse oversubscribed K = 1: t0 slower than t51, Holm-significant", slow("ov_k1") if "ov_k1" in T else None),
        "Y4": ("sparse in-memory K = 512: t0 faster than t51 (direction only)", (T["in_k512"]["delta_s"] < 0) if "in_k512" in T else None)}
    keys = ["workload", "arm", "base", "n_base", "n_c6", "median_base", "median_c6", "delta_s", "delta_pct", "U", "p", "mwu_method", "cohen_d", "mde_s", "mde_family_s", "m_family", "mde_pct",
            "mde_family_pct", "noout_delta_s", "noout_p", "n_outliers_base", "n_outliers_arm", "holm_thr", "holm_sig"]
    with open(f"{data_dir}/h1_tests.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore"); w.writeheader(); w.writerows(tests)
    rep = [f"# Gate H1 primary report (generated by tests/h1_analyze.py)", "", f"**Verdict (mechanical): {verdict}**", "",
           f"Tests present: {len(present)} (one Holm family, alpha 0.05)", "", "| workload | median t51 (s) | median t0 (s) | delta | p | Holm thr | Holm-sig | MDE family (%) | managed delta (E7/E8, different session) |", "|---|---|---|---|---|---|---|---|---|"]
    for c in tests:
        m = man.get(c["workload"])
        rep.append(f"| {C.WL[c['workload']][0]} | {c['median_base']:.4f} | {c['median_c6']:.4f} | {c['delta_pct']:+.2f}% | {c['p']:.2e} | {c['holm_thr']:.4f} | {c['holm_sig']} | {c['mde_family_pct']:.2f} | "
                   f"{m[0]:+.2f}% ({m[2]}, Holm-sig {m[1]}) |" if m else "n/a |")
    rep += ["", "## Expectations (reviewer, committed before the run)", ""] + [f"- **{k}** {t}: {'not evaluable' if v is None else ('HELD' if v else 'FAILED')}" for k, (t, v) in exps.items()]
    open(f"{data_dir}/primary_report.txt", "w").write("\n".join(rep) + "\n")
    print("\n".join(rep))
    figure(rows, T, man, fig)
    return 0


def figure(rows, T, man, fig):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sys.path.insert(0, os.path.dirname(__file__))
    import make_paper_figures as M
    M.style()
    names = [("stencil", "Stencil-24K"), ("in_k512", "sparse in memory\nK=512"), ("in_k1", "sparse in memory\nK=1"), ("ov_k512", "sparse oversub.\nK=512"), ("ov_k1", "sparse oversub.\nK=1")]
    e7 = list(csv.DictReader(open("results/analysis/gate_e/e7/e7_runs.csv")))
    e8 = list(csv.DictReader(open(E8_RUNS)))
    fig_, ax = plt.subplots(figsize=(M.COL2 * 0.8, 2.6))
    for i, (w, lab) in enumerate(names):
        if w not in T:
            continue
        # malloc (H1)
        b = st.median(walls(rows, w, 51))
        v = [100 * (x / b - 1) for x in walls(rows, w, 0)]
        M.pts(ax, i + 0.17, v, M.THR[0], "o", jitter=0.06, size=6, alpha=0.5)
        M.med_marker(ax, i + 0.17, T[w]["delta_pct"], M.THR[0], "o", "sig" if T[w]["holm_sig"] else "ns", size=22)
        # managed (E7 / E8)
        if w == "stencil":
            base = [float(r["wall_s"]) for r in e7 if r["workload"] == "stencil" and r.get("family") == "A" and r["label"].endswith("stock-t51")]
            arm = [float(r["wall_s"]) for r in e7 if r["workload"] == "stencil" and r.get("family") == "A" and r["label"].endswith("stock-t0")]
        else:
            base = [float(r["wall_s"]) for r in e8 if r["workload"] == w and r["label"].endswith("stock-t51")]
            arm = [float(r["wall_s"]) for r in e8 if r["workload"] == w and r["label"].endswith("stock-t0")]
        bm = st.median(base)
        M.pts(ax, i - 0.17, [100 * (x / bm - 1) for x in arm], M.THR[51], "s", jitter=0.06, size=6, alpha=0.5)
        M.med_marker(ax, i - 0.17, man[w][0], M.THR[51], "s", "sig" if man[w][1] else "ns", size=22)
    ax.axhline(0, color=M.THR[51], lw=0.8)
    ax.set_xticks(range(len(names))); ax.set_xticklabels([n[1] for n in names], fontsize=6.3)
    ax.set_ylabel("t0 wall-clock vs t51 (%)")
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker="o", ls="", color=M.THR[0], ms=4, label="malloc'd (HMM), H1"), Line2D([], [], marker="s", ls="", color=M.THR[51], ms=4, label="managed (E7/E8, other session)")],
              frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, fontsize=6.5)
    fig_.tight_layout()
    for ext in ("png", "pdf"):
        fig_.savefig(f"{fig}.{ext}", bbox_inches="tight", dpi=300)
    plt.close(fig_)


if __name__ == "__main__":
    if "--control" in sys.argv:
        k = sys.argv.index("--control")
        sc = sys.argv[k + 1] if len(sys.argv) > k + 1 else None
        good, bad = control(sc), control(sc, perturb=True)
        print("control can fail:", not bad)
        sys.exit(0 if (good and not bad) else 3)
    sys.exit(analyze(sys.argv[1] if len(sys.argv) > 1 else DATA, sys.argv[2] if len(sys.argv) > 2 else FIG))
