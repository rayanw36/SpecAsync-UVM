#!/usr/bin/env python3
"""Gate E7 analysis (E7_PREREGISTRATION.md). Statistical helpers are imported UNCHANGED from
tests/e09b_analyze.py (H.mwu, H.holm, H.compare, H.tukey_keep). delta = (arm - baseline) / baseline.

  e7_analyze.py --control [SCRATCH_DIR]       positive control on E6's committed e6_runs.csv
  e7_analyze.py --selftest                    synthetic refusal tests (scratch dir only)
  e7_analyze.py [DATA_DIR [FIG_PREFIX]]       the pre-registered analysis

Refuses to run on fewer rows than pre-registered: 310, minus 30 per Family B workload recorded in
DATA_DIR/family_b_skipped.txt (one workload key per line). Every self-test and the control write ONLY to
a scratch directory outside results/ (default: a fresh tempfile.mkdtemp()).

MDE at the family alpha: the helper's `mde_bonf_s` is hard-coded to alpha = 0.05/16 (E0.9b's family),
so E7 does NOT use it; `mde_family_s` below rescales the helper's own sd by z(1 - 0.05/(2m)) + z(0.8),
with m the number of tests in the family (a Bonferroni bound on the Holm family).
"""
import csv
import math
import os
import statistics as st
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
_argv, sys.argv = sys.argv, sys.argv[:1]
import e09b_analyze as H  # noqa: E402
sys.argv = _argv
from scipy.stats import norm  # noqa: E402

E4_RUNS = "results/analysis/gate_e/e4/e4_runs.csv"
E5_RUNS = "results/analysis/gate_e/e5/e5_runs.csv"
E6_RUNS = "results/analysis/gate_e/e6/e6_runs.csv"
DATA = "results/analysis/gate_e/e7"
FIG = "results/analysis/gate_e/e7_threshold_by_workload"
N_FULL = 310
FAM_B_WL = ["stencil8k", "sweep4k", "sweep16k", "stream", "sgemm", "cufft", "graphbfs", "oversub"]
WL_TITLE = {"stencil": "Stencil-24K", "stencil8k": "Stencil-8K", "sweep4k": "Sweep-4K", "sweep16k": "Sweep-16K",
            "stream": "STREAM", "sgemm": "SGEMM", "cufft": "cuFFT", "graphbfs": "GraphBFS-23",
            "oversub": "Stencil oversub N=48000"}
Z_POWER = 0.841621


def load(path):
    rows = list(csv.DictReader(open(path)))
    for r in rows:
        r["cell"] = r["label"].split(" ", 1)[1]
        r["wl"] = r["workload"]
    return rows


def pick(rows, wl, cell, **kw):
    return [float(r["wall_s"]) for r in rows if r["wl"] == wl and r["cell"] == cell
            and all(r.get(k) == v for k, v in kw.items())]


def mde_family(c, m):
    sd = c["mde_s"] / H.Z_MDE
    return (norm.ppf(1 - 0.05 / (2 * m)) + Z_POWER) * sd


def compare(base, arm, m):
    c = H.compare(base, arm)
    d2 = H.compare(H.tukey_keep(base), H.tukey_keep(arm))
    c.update(noout_delta_s=d2["delta_s"], noout_p=d2["p"], mde_family_s=mde_family(c, m), m_family=m,
             mde_pct=100 * c["mde_s"] / c["median_base"], mde_family_pct=100 * mde_family(c, m) / c["median_base"],
             n_outliers_base=len(base) - len(H.tukey_keep(base)), n_outliers_arm=len(arm) - len(H.tukey_keep(arm)))
    return c


def holm_apply(cs):
    thr, sig = H.holm([c["p"] for c in cs])
    for c, t, s in zip(cs, thr, sig):
        c.update(holm_thr=t, holm_sig=s)
    return cs


def read_skipped(data_dir):
    p = f"{data_dir}/family_b_skipped.txt"
    return [l.split()[0] for l in open(p) if l.strip() and not l.startswith("#")] if os.path.exists(p) else []


def control(scratch):
    rows = [r for r in load(E6_RUNS) if r["wl"] == "stencil"]
    c = compare(pick(rows, "stencil", "C0-t0"), pick(rows, "stencil", "C7W512-t51"), 1)
    df = lambda cell: st.median(float(r["demand_faults"]) for r in rows if r["cell"] == cell)  # noqa: E731
    D51 = 1 - df("C7W512-t51") / df("C0-t51")
    ok = f"{c['delta_pct']:+.2f}" == "+6.39" and f"{c['p']:.2e}" == "1.08e-05" and f"{D51:+.4f}" == "+0.4017"
    out = "\n".join([
        "# E7 analyzer positive control (run on E6's committed e6_runs.csv)",
        f"comparison: C7W512-t51 (arm) vs C0-t0 (baseline); n = {c['n_base']} / {c['n_c6']}",
        f"median C0-t0 = {c['median_base']:.4f} s; median C7W512-t51 = {c['median_c6']:.4f} s",
        f"delta = (arm - base) / base = {c['delta_pct']:+.2f}%  (E6 reported +6.39%)",
        f"MWU two-sided p = {c['p']:.2e}  (E6 reported 1.08e-05)",
        f"D(51) = 1 - median demand faults C7W512-t51 / C0-t51 = {D51:+.4f}  (E6 reported +0.4017)",
        f"CONTROL: {'PASS - reproduces E6' if ok else 'FAIL - does not reproduce E6'}", ""])
    os.makedirs(scratch, exist_ok=True)
    open(f"{scratch}/analyzer_positive_control.txt", "w").write(out)
    print(out)
    print("written to", scratch)
    return 0 if ok else 3


def validate(order, rows, skipped):
    need = N_FULL - 30 * len(skipped)
    if len(rows) != need:
        sys.exit(f"REFUSING: {len(rows)} rows present; pre-registered {need} "
                 f"({'skipped: ' + ','.join(skipped) if skipped else 'full'}). No interim analysis.")
    exp = [o for o in order if o["workload"] not in skipped]
    for o, r in zip(exp, rows):
        if (o["idx"], o["label"]) != (r["idx"], r["label"]):
            sys.exit(f"REFUSING: order mismatch at idx {o['idx']}")
    for r in rows:
        if r["exit_code"] != "0" or r["threshold_readback"] != r["threshold"]:
            sys.exit(f"REFUSING: idx {r['idx']} exit/threshold read-back inconsistent")


def analyze(data_dir, fig):
    order = list(csv.DictReader(open(f"{data_dir}/e7_order.csv")))
    rows = load(f"{data_dir}/e7_runs.csv")
    skipped = read_skipped(data_dir)
    validate(order, rows, skipped)
    out = {}

    # ---- Family A (Holm 2): stock-t0, stock-t10 vs stock-t51, Stencil-24K
    fa = [compare(pick(rows, "stencil", "stock-t51", family="A"), pick(rows, "stencil", c, family="A"), 2)
          for c in ("stock-t0", "stock-t10")]
    for c, n in zip(fa, ("stock-t0", "stock-t10")):
        c["arm"], c["base"], c["workload"] = n, "stock-t51", "stencil"
    holm_apply(fa)

    # ---- Family B (one Holm family across all workloads x 2 arms)
    wls = [w for w in FAM_B_WL if w not in skipped]
    fb = []
    for w in wls:
        for arm in ("stock-t0", "stock-t25"):
            c = compare(pick(rows, w, "stock-t51", family="B"), pick(rows, w, arm, family="B"), 2 * len(wls))
            c.update(workload=w, arm=arm, base="stock-t51")
            fb.append(c)
    holm_apply(fb)

    # ---- Family C (Holm 2): block 1 vs block 2 per arm (arm = block 2)
    fc = []
    for cell in ("spec-C0-t51", "spec-C7W512-t51"):
        c = compare(pick(rows, "stencil", cell, family="C", block="1"), pick(rows, "stencil", cell, family="C", block="2"), 2)
        c.update(workload="stencil", arm=cell + " block2", base=cell + " block1", cell=cell)
        fc.append(c)
    holm_apply(fc)

    # ---- Descriptive: session medians across gates; module presence cost
    ref = {}
    for g, path, c0, c7 in (("E4", E4_RUNS, "stencil C0", "stencil C7-W512"), ("E5", E5_RUNS, "stencil C0-t51", "stencil C7W512-t51"),
                            ("E6", E6_RUNS, "stencil C0-t51", "stencil C7W512-t51")):
        rr = list(csv.DictReader(open(path)))
        ref[g] = (st.median(float(r["wall_s"]) for r in rr if r["label"] == c0),
                  st.median(float(r["wall_s"]) for r in rr if r["label"] == c7))
    c0_all = pick(rows, "stencil", "spec-C0-t51", family="C")
    c7_all = pick(rows, "stencil", "spec-C7W512-t51", family="C")
    ref["E7 (blocks pooled)"] = (st.median(c0_all), st.median(c7_all))
    ref["E7 block 1"] = (st.median(pick(rows, "stencil", "spec-C0-t51", family="C", block="1")),
                         st.median(pick(rows, "stencil", "spec-C7W512-t51", family="C", block="1")))
    ref["E7 block 2"] = (st.median(pick(rows, "stencil", "spec-C0-t51", family="C", block="2")),
                         st.median(pick(rows, "stencil", "spec-C7W512-t51", family="C", block="2")))
    stock51 = pick(rows, "stencil", "stock-t51", family="A")
    presence = H.compare(stock51, c0_all)      # arm = specasync C0-t51 (policy 0), baseline = stock t51; DESCRIPTIVE

    # ---- Expectations
    xa = fa[0]["holm_sig"] and fa[0]["delta_s"] < 0
    first5 = [c for c in fb if c["workload"] in ("stencil8k", "sweep4k", "sweep16k", "stream", "sgemm") and c["arm"] == "stock-t0"]
    xb1_bad = [c["workload"] for c in first5 if c["holm_sig"] and c["delta_s"] > 0]
    xb1 = (not xb1_bad) if first5 else None
    gb = [c for c in fb if c["workload"] == "graphbfs"]
    xb2 = (not any(c["holm_sig"] for c in gb)) if gb else None
    ov = [c for c in fb if c["workload"] == "oversub" and c["arm"] == "stock-t0"]
    xb3 = (ov[0]["holm_sig"] and ov[0]["delta_s"] > 0) if ov else None
    cf = [c for c in fb if c["workload"] == "cufft" and c["arm"] == "stock-t0"]
    xb4 = (not (cf[0]["holm_sig"] and cf[0]["delta_s"] < 0)) if cf else None
    rel = {c["cell"]: abs(c["median_c6"] - c["median_base"]) / c["median_base"] for c in fc}
    xc = rel["spec-C7W512-t51"] > rel["spec-C0-t51"]

    # ---- write
    def wcsv(name, items):
        with open(f"{data_dir}/{name}", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(items[0].keys()), extrasaction="ignore")
            w.writeheader()
            w.writerows(items)
    for c in fa + fb + fc:
        c["arm_median"], c["base_median"] = c["median_c6"], c["median_base"]
    wcsv("family_a.csv", fa)
    wcsv("family_b.csv", fb)
    wcsv("family_c.csv", fc)
    with open(f"{data_dir}/session_medians.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["session", "C0-t51 median (s)", "C7W512-t51 median (s)", "C7 vs C0 %"])
        for k, (a, b) in ref.items():
            w.writerow([k, f"{a:.4f}", f"{b:.4f}", f"{100 * (b / a - 1):+.2f}"])
    L = ["Family A (Stencil-24K, stock module; Holm of 2; delta = (arm - stock-t51) / stock-t51)"]
    for c in fa:
        L.append(f"  {c['arm']:9s} med {c['median_c6']:.4f} vs t51 {c['median_base']:.4f}  delta {c['delta_pct']:+.2f}%  p {c['p']:.2e}  "
                 f"Holm-thr {c['holm_thr']:.4f}  sig {c['holm_sig']}  d {c['cohen_d']:+.2f}  MDE {c['mde_s']:.4f} s ({c['mde_pct']:.2f}%)  "
                 f"MDE@family {c['mde_family_s']:.4f} s ({c['mde_family_pct']:.2f}%)  noout {c['noout_delta_s']:+.4f}/{c['noout_p']:.1e}")
    L += ["", f"Family B (one Holm family of {len(fb)}; every significant slowdown is as reportable as every speedup)"]
    for c in fb:
        tag = "SLOWER" if (c["holm_sig"] and c["delta_s"] > 0) else ("FASTER" if (c["holm_sig"] and c["delta_s"] < 0) else "n.s.")
        L.append(f"  {c['workload']:10s} {c['arm']:9s} med {c['median_c6']:.4f} vs t51 {c['median_base']:.4f}  delta {c['delta_pct']:+.2f}%  "
                 f"p {c['p']:.2e}  Holm-thr {c['holm_thr']:.4f}  {tag}  d {c['cohen_d']:+.2f}  MDE {c['mde_s']:.4f} s ({c['mde_pct']:.2f}%)  "
                 f"MDE@family {c['mde_family_pct']:.2f}%  noout {c['noout_delta_s']:+.4f}/{c['noout_p']:.1e}")
    if skipped:
        L.append(f"  SKIPPED whole (recorded in family_b_skipped.txt): {', '.join(skipped)}")
    L += ["", "Family C (E3a-2 module, Stencil-24K; Holm of 2; delta = (block 2 - block 1) / block 1)"]
    for c in fc:
        L.append(f"  {c['cell']:16s} block1 {c['median_base']:.4f}  block2 {c['median_c6']:.4f}  delta {c['delta_pct']:+.2f}%  p {c['p']:.2e}  "
                 f"Holm-thr {c['holm_thr']:.4f}  sig {c['holm_sig']}  MDE {c['mde_s']:.4f} s")
    L += ["", "Session medians (Stencil-24K, prefetch on, t51):"]
    for k, (a, b) in ref.items():
        L.append(f"  {k:20s} C0-t51 {a:.4f}  C7W512-t51 {b:.4f}  C7 vs C0 {100 * (b / a - 1):+.2f}%")
    L.append(f"  module presence (DESCRIPTIVE, not tested): specasync C0-t51 median {st.median(c0_all):.4f} vs stock t51 (Family A) "
             f"{st.median(stock51):.4f}: {presence['delta_pct']:+.2f}% (p {presence['p']:.2e}, descriptive)")
    def hf(x):
        return "n/a (workload skipped)" if x is None else ("HELD" if x else "FAILED")
    L += ["", "Expectations (reviewer, directional; operational definitions fixed before the run):",
          f"  XA  C0-t0 faster than C0-t51 on Stencil-24K, Holm-significant: {hf(xa)}",
          f"  XB1 no workload among Stencil-8K, Sweep-4K, Sweep-16K, STREAM, SGEMM significantly slower at t0 than t51: {hf(xb1)}"
          + (f"  (violations: {xb1_bad})" if xb1_bad else ""),
          f"  XB2 GraphBFS-23: no significant difference at either threshold: {hf(xb2)}",
          f"  XB3 oversub Stencil: C0-t0 significantly SLOWER than C0-t51: {hf(xb3)}",
          f"  XB4 cuFFT: C0-t0 not significantly faster than C0-t51: {hf(xb4)}",
          f"  XC  C7W512-t51 block-to-block |median difference| larger than C0-t51's: {hf(xc)}  "
          f"({', '.join(f'{k} {100 * v:.2f}%' for k, v in rel.items())})"]
    open(f"{data_dir}/primary_report.txt", "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    figure(rows, wls, fb, fa, fig)
    return 0


def figure(rows, wls, fb, fa, fig):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    INK, MUTED, GRID, HUE = "#1f2328", "#59636e", "#d8dee4", "#2a6fb0"
    panels = ["stencil"] + wls
    cols = 3
    f_, axes = plt.subplots(math.ceil(len(panels) / cols), cols, figsize=(11, 3.1 * math.ceil(len(panels) / cols)),
                            sharey=True, squeeze=False)
    sig = {(c["workload"], c["arm"]): c["holm_sig"] for c in fa + fb}
    xs = {"stock-t0": 0, "stock-t10": 10, "stock-t25": 25, "stock-t51": 51}
    for ax, w in zip(axes.flat, panels):
        fam = "A" if w == "stencil" else "B"
        base = st.median(pick(rows, w, "stock-t51", family=fam))
        cells = [c for c in ("stock-t0", "stock-t10", "stock-t25", "stock-t51") if pick(rows, w, c, family=fam)]
        meds = []
        for c in cells:
            v = [100 * (x / base - 1) for x in pick(rows, w, c, family=fam)]
            ax.scatter([xs[c]] * len(v), v, s=14, color=HUE, alpha=0.35, zorder=3, linewidths=0)
            m = st.median(v)
            meds.append((xs[c], m))
            filled = sig.get((w, c), False)
            ax.scatter([xs[c]], [m], s=46, facecolor=HUE if filled else "white", edgecolor=HUE, linewidths=1.6, zorder=5)
        ax.plot([a for a, _ in meds], [b for _, b in meds], color=HUE, lw=1.6, zorder=4)
        ax.axhline(0, color=MUTED, lw=0.8)
        ax.set_title(WL_TITLE[w], fontsize=10, color=INK, loc="left")
        ax.set_xticks([xs[c] for c in cells])
        ax.set_xticklabels([c.split("-t")[1] for c in cells], fontsize=8, color=MUTED)
        ax.grid(axis="y", color=GRID, lw=0.6)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    for ax in axes.flat[len(panels):]:
        ax.axis("off")
    for ax in axes[:, 0]:
        ax.set_ylabel("wall-clock vs median at t51 (%)", fontsize=8, color=MUTED)
    for ax in axes[-1]:
        ax.set_xlabel("uvm_perf_prefetch_threshold", fontsize=8, color=MUTED)
    f_.suptitle("Gate E7: stock driver, wall-clock change vs threshold 51 (n=10 per cell; filled = Holm-significant vs t51; points = runs)",
                fontsize=9.5, color=INK, x=0.01, ha="left")
    f_.tight_layout(rect=(0, 0, 1, 0.96))
    for ext in ("png", "pdf"):
        f_.savefig(f"{fig}.{ext}", dpi=150)


def selftest():
    """Refusal/acceptance tests on synthetic data, written ONLY to a scratch directory."""
    import random
    import shutil
    import subprocess
    scratch = tempfile.mkdtemp(prefix="e7_selftest_")
    order = list(csv.DictReader(open(f"{DATA}/e7_order.csv")))
    rng = random.Random(1)
    hdr = ["idx", "label", "workload", "family", "block", "threshold", "threshold_readback", "wall_s", "exit_code"]

    def write(rows_, path):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(hdr)
            for o in rows_:
                w.writerow([o["idx"], o["label"], o["workload"], o["family"], o["block"], o["threshold"], o["threshold"],
                            f"{1 + rng.random() * 0.02:.6f}", 0])
    results = {}
    for name, rows_, skip in (("79-of-310", order[:79], []), ("310", order, []),
                              ("skip-sgemm-with-310", order, ["sgemm"]),
                              ("skip-sgemm-ok", [o for o in order if o["workload"] != "sgemm"], ["sgemm"])):
        d = f"{scratch}/{name}"
        os.makedirs(d)
        shutil.copy(f"{DATA}/e7_order.csv", d)
        write(rows_, f"{d}/e7_runs.csv")
        if skip:
            open(f"{d}/family_b_skipped.txt", "w").write("\n".join(skip) + "\n")
        r = subprocess.run([sys.executable, __file__, d, f"{d}/fig"], capture_output=True, text=True)
        results[name] = (r.returncode, ("REFUSING" in (r.stdout + r.stderr)))
    ok = (results["79-of-310"] == (1, True) and results["310"][0] == 0 and results["skip-sgemm-with-310"] == (1, True)
          and results["skip-sgemm-ok"][0] == 0)
    print("selftest results (returncode, refused):", results, "scratch:", scratch)
    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 3


if __name__ == "__main__":
    if "--control" in sys.argv:
        k = sys.argv.index("--control")
        sys.exit(control(sys.argv[k + 1] if len(sys.argv) > k + 1 else tempfile.mkdtemp(prefix="e7_control_")))
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    dd = sys.argv[1] if len(sys.argv) > 1 else DATA
    ff = sys.argv[2] if len(sys.argv) > 2 else FIG
    sys.exit(analyze(dd, ff))
