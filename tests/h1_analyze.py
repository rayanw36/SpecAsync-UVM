#!/usr/bin/env python3
"""Gate H1 analysis (H1_PREREGISTRATION.md). Statistical helpers are imported UNCHANGED: e7_analyze (compare, holm_apply, mde_family), which use tests/e09b_analyze.py's
H.mwu / H.holm / H.compare / H.tukey_keep. delta = (arm - t51) / t51; negative = t0 is faster.

  h1_analyze.py --control [SCRATCH_DIR]   positive control: reproduces E8's oversubscribed K = 1 t0 vs t51 (+84.96%, p 1.08e-05) from the committed e8_runs.csv,
                                          and must FAIL on a copy with one cell shifted by 10% (writes only to a scratch directory outside results/)
  h1_analyze.py [DATA_DIR [FIG_PREFIX]]   the pre-registered analysis

Refuses to run unless the rows present equal the order rows minus the cells in dropped_cells.txt.
Amendment 1: one Holm family of 3: t0 vs t51 for Stencil-24K and sparse in-memory K = 512 and K = 1, alpha 0.05 (the oversubscribed cells were removed).
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
FIG = "paper/figures/supplementary/F-H1"   # (C17) the figure itself is drawn by tests/make_paper_figures.py (fig_h1)


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
    c = A.compare(base, arm, 3)     # Amendment 1: the reduced family has 3 tests
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
    man = managed_deltas()
    # Amendment 1 verdict: dense cells = Stencil-24K and bench_sparse in memory at the largest K kept (512)
    dense = [w for w in ("stencil", "in_k512") if w in T]
    powered = all(T[w]["mde_family_pct"] <= abs(man[w][0]) for w in dense)
    if any(fast(w) for w in dense):
        verdict = "DENSE REPLICATED ON HMM"
    elif len(dense) == 2 and powered:
        verdict = "NOT REPLICATED"
    else:
        verdict = "INCONCLUSIVE"
    exps = {
        "Y1": ("Stencil-24K: t0 faster than t51, Holm-significant", fast("stencil") if "stencil" in T else None),
        "Y2": ("Stencil-24K: the malloc-mode gain is smaller than E7's managed -9.57%", (T["stencil"]["delta_pct"] > man["stencil"][0]) if "stencil" in T else None),
        "Y3": ("sparse oversubscribed K = 1: t0 slower than t51, Holm-significant", "WITHDRAWN (Amendment 1), not scored"),
        "Y4": ("sparse in-memory K = 512: t0 faster than t51 (direction only)", (T["in_k512"]["delta_s"] < 0) if "in_k512" in T else None)}
    keys = ["workload", "arm", "base", "n_base", "n_c6", "median_base", "median_c6", "delta_s", "delta_pct", "U", "p", "mwu_method", "cohen_d", "mde_s", "mde_family_s", "m_family", "mde_pct",
            "mde_family_pct", "noout_delta_s", "noout_p", "n_outliers_base", "n_outliers_arm", "holm_thr", "holm_sig"]
    with open(f"{data_dir}/h1_tests.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore"); w.writeheader(); w.writerows(tests)
    rep = [f"# Gate H1 primary report (generated by tests/h1_analyze.py)", "", f"**Verdict (mechanical): {verdict}**", "",
           f"Tests present: {len(present)} (one Holm family, alpha 0.05; Amendment 1). The sparse half of the trade-off is NOT tested on HMM, whatever the result.", "", "| workload | median t51 (s) | median t0 (s) | delta | p | Holm thr | Holm-sig | MDE family (%) | managed delta (E7/E8, different session) |", "|---|---|---|---|---|---|---|---|---|"]
    for c in tests:
        m = man.get(c["workload"])
        rep.append(f"| {C.WL[c['workload']][0]} | {c['median_base']:.4f} | {c['median_c6']:.4f} | {c['delta_pct']:+.2f}% | {c['p']:.2e} | {c['holm_thr']:.4f} | {c['holm_sig']} | {c['mde_family_pct']:.2f} | "
                   f"{m[0]:+.2f}% ({m[2]}, Holm-sig {m[1]}) |" if m else "n/a |")
    rep += ["", "## Expectations (reviewer, committed before the run)", ""] + [f"- **{k}** {t}: {v if isinstance(v, str) else ('not evaluable' if v is None else ('HELD' if v else 'FAILED'))}" for k, (t, v) in exps.items()]
    open(f"{data_dir}/primary_report.txt", "w").write("\n".join(rep) + "\n")
    print("\n".join(rep))
    figure(rows, T, man, fig)
    return 0


def figure(rows, T, man, fig):
    """(C17) F-H1 is drawn by tests/make_paper_figures.py (fig_h1; paper marker convention: HMM = triangles). Kept as a pointer so the analysis script still regenerates it."""
    sys.path.insert(0, os.path.dirname(__file__))
    import make_paper_figures as M
    M.style()
    M.fig_h1()


if __name__ == "__main__":
    if "--control" in sys.argv:
        k = sys.argv.index("--control")
        sc = sys.argv[k + 1] if len(sys.argv) > k + 1 else None
        good, bad = control(sc), control(sc, perturb=True)
        print("control can fail:", not bad)
        sys.exit(0 if (good and not bad) else 3)
    sys.exit(analyze(sys.argv[1] if len(sys.argv) > 1 else DATA, sys.argv[2] if len(sys.argv) > 2 else FIG))
