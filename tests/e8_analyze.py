#!/usr/bin/env python3
"""Gate E8 analysis (E8_PREREGISTRATION.md). Statistical helpers are imported UNCHANGED: e7_analyze (compare, holm_apply,
mde_family, which themselves use tests/e09b_analyze.py's H.mwu / H.holm / H.compare / H.tukey_keep unchanged).
delta = (arm - t51) / t51; negative = the lower threshold is faster.

  e8_analyze.py --control [SCRATCH_DIR]   positive control: reproduces E7 Family A from e7_runs.csv (-9.57%, p 1.08e-05)
  e8_analyze.py --selftest                synthetic refusal tests (scratch directory only)
  e8_analyze.py [DATA_DIR [FIG_PREFIX]]   the pre-registered analysis

Refuses to run unless the rows present equal the order rows minus: cells in dropped_cells.txt, OV K-groups in
ov_skipped.txt, and Family M if m_skipped.txt exists. Self-tests and the control write ONLY to a scratch directory
outside results/.
"""
import csv
import math
import os
import statistics as st
import struct
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import e7_analyze as A  # noqa: E402
import e8_cells as C  # noqa: E402

H = A.H
E7_RUNS = "results/analysis/gate_e/e7/e7_runs.csv"
DATA = "results/analysis/gate_e/e8"
FIG = "results/analysis/gate_e/e8_sparse_threshold"
RAW = "results/phaseB1/gate_e8/sweep"
BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#d8d8d4"


def lines(path):
    return [l.split(" | ")[0].split(" skipped")[0].strip() for l in open(path) if l.strip() and not l.startswith("#")] if os.path.exists(path) else []


def expected_rows(data_dir, order):
    drop = set(lines(f"{data_dir}/dropped_cells.txt"))
    ovs = set(lines(f"{data_dir}/ov_skipped.txt"))
    m_skip = os.path.exists(f"{data_dir}/m_skipped.txt")
    return [o for o in order if o["label"] not in drop and not (o["family"] == "OV" and o["workload"] in ovs)
            and not (o["family"] == "M" and m_skip)]


def control(scratch):
    rows = [r for r in A.load(E7_RUNS) if r["wl"] == "stencil" and r.get("family") == "A"]
    c = A.compare(A.pick(rows, "stencil", "stock-t51", family="A"), A.pick(rows, "stencil", "stock-t0", family="A"), 2)
    ok = f"{c['delta_pct']:+.2f}" == "-9.57" and f"{c['p']:.2e}" == "1.08e-05"
    out = "\n".join([
        "# E8 analyzer positive control (run on E7's committed e7_runs.csv, Family A)",
        f"comparison: stock-t0 (arm) vs stock-t51 (baseline), Stencil-24K; n = {c['n_base']} / {c['n_c6']}",
        f"median stock-t51 = {c['median_base']:.4f} s; median stock-t0 = {c['median_c6']:.4f} s",
        f"delta = (arm - base) / base = {c['delta_pct']:+.2f}%  (E7 reported -9.57%)",
        f"MWU two-sided p = {c['p']:.2e}  (E7 reported 1.08e-05)",
        f"CONTROL: {'PASS - reproduces E7 Family A' if ok else 'FAIL - does not reproduce E7 Family A'}", ""])
    os.makedirs(scratch, exist_ok=True)
    open(f"{scratch}/analyzer_positive_control.txt", "w").write(out)
    print(out, "written to", scratch)
    return 0 if ok else 3


def cellrows(rows, wl, cell, family):
    return A.pick(rows, wl, cell, family=family)


def analyze(data_dir, fig):
    order = list(csv.DictReader(open(f"{data_dir}/e8_order.csv")))
    rows = A.load(f"{data_dir}/e8_runs.csv")
    exp = expected_rows(data_dir, order)
    if len(rows) != len(exp):
        sys.exit(f"REFUSING: {len(rows)} rows present; pre-registered {len(exp)} (order minus dropped/skipped). No interim analysis.")
    for o, r in zip(exp, rows):
        if (o["idx"], o["label"]) != (r["idx"], r["label"]):
            sys.exit(f"REFUSING: order mismatch at idx {o['idx']}")
    for r in rows:
        if r["exit_code"] != "0" or r["threshold_readback"] != r["threshold"]:
            sys.exit(f"REFUSING: idx {r['idx']} exit/threshold read-back inconsistent")

    # ---- primary tests: (size, K) x {t0, t25} vs t51; ONE Holm family (up to 16)
    tests = []
    for size, fam in (("in", "IN"), ("ov", "OV")):
        for K in C.KS:
            wl = C.wl_key(size, K)
            b = cellrows(rows, wl, "stock-t51", fam)
            if len(b) < 10:
                continue
            for arm in ("stock-t0", "stock-t25"):
                a = cellrows(rows, wl, arm, fam)
                if len(a) < 10:
                    continue
                tests.append(dict(size=size, K=K, arm=arm, workload=wl, _b=b, _a=a))
    m = len(tests)
    res = []
    for t in tests:
        c = A.compare(t["_b"], t["_a"], m)
        c.update(size=t["size"], K=t["K"], arm=t["arm"], workload=t["workload"])
        res.append(c)
    if res:
        A.holm_apply(res)
    get = lambda size, K, arm: next((c for c in res if c["size"] == size and c["K"] == K and c["arm"] == arm), None)  # noqa: E731

    # ---- verdict (mechanical)
    slow = sorted([c for c in res if c["K"] < 512 and c["holm_sig"] and c["delta_s"] > 0], key=lambda c: -c["delta_pct"])
    k512 = get("in", 512, "stock-t0")
    if k512 is None:
        suspect_txt = "BENCHMARK SUSPECT check: not evaluable (in-memory K=512 cell missing)"
        suspect = None
    else:
        suspect = not (k512["median_c6"] < k512["median_base"])
        suspect_txt = (f"BENCHMARK SUSPECT: in-memory K=512 is NOT faster at t0 than at t51 (delta {k512['delta_pct']:+.2f}%)" if suspect
                       else f"benchmark not suspect: in-memory K=512 t0 is faster than t51 (delta {k512['delta_pct']:+.2f}%)")
    if slow:
        verdict = ("GENERALITY FALSIFIED: Holm-significant slowdown(s) at K < 512: "
                   + "; ".join(f"{c['size']} K={c['K']} {c['arm']} {c['delta_pct']:+.2f}% (p {c['p']:.2e})" for c in slow)
                   + f". Largest slowdown: {slow[0]['size']} K={slow[0]['K']} {slow[0]['arm']} {slow[0]['delta_pct']:+.2f}%")
    else:
        k1 = [c for c in res if c["K"] == 1]
        verdict = ("GENERALITY NOT FALSIFIED: no K < 512 cell has a Holm-significant slowdown at t0 or t25. K=1 MDEs (at achieved n / at family alpha): "
                   + "; ".join(f"{c['size']} {c['arm']} {c['mde_pct']:.2f}% / {c['mde_family_pct']:.2f}%" for c in k1))

    # ---- expectations
    def sig_slower(c):
        return bool(c and c["holm_sig"] and c["delta_s"] > 0)
    xs1 = None if get("in", 1, "stock-t0") is None else sig_slower(get("in", 1, "stock-t0"))
    ov18 = [get("ov", k, "stock-t0") for k in (1, 8)]
    xs2 = None if all(c is None for c in ov18) else any(sig_slower(c) for c in ov18)
    k512c = [get("in", 512, "stock-t0"), get("ov", 512, "stock-t0")]
    xs3 = None if any(c is None for c in k512c) else all(c["delta_s"] < 0 for c in k512c)
    xs4, xs4d = [], {}
    for size in ("in", "ov"):
        seq = [(K, get(size, K, "stock-t0")) for K in (512, 64, 8, 1)]
        seq = [(K, c["delta_pct"]) for K, c in seq if c is not None]
        xs4d[size] = seq
        xs4.append(None if len(seq) < 3 else all(seq[i][1] < seq[i + 1][1] for i in range(len(seq) - 1)))
    xs4v = None if any(v is None for v in xs4) else all(xs4)
    xs5l = []
    for size in ("in", "ov"):
        for K in C.KS:
            c0, c25 = get(size, K, "stock-t0"), get(size, K, "stock-t25")
            if c0 and c25:
                lo, hi = sorted((c0["delta_pct"], 0.0))
                xs5l.append((size, K, lo <= c25["delta_pct"] <= hi))
    xs5 = None if not xs5l else all(v for _, _, v in xs5l)

    # ---- descriptive: per-pass kernel time, Family M mechanism
    pas = []
    for r0 in sorted({(r["wl"], r["cell"], r["family"]) for r in rows if r["family"] in ("IN", "OV")}):
        sel = [r for r in rows if (r["wl"], r["cell"], r["family"]) == r0]
        pas.append(dict(workload=r0[0], cell=r0[1], n=len(sel), **{f"pass{i}_ms_median": st.median(float(r[f"pass{i}_ms"]) for r in sel) for i in (1, 2, 3)}))
    mech = []
    for r0 in sorted({(r["wl"], r["cell"]) for r in rows if r["family"] == "M"}):
        sel = [r for r in rows if (r["wl"], r["cell"]) == r0 and r["family"] == "M"]
        df = st.median(float(r["demand_faults"]) for r in sel)
        d5 = []
        for r in sel:
            p = f"{RAW}/e8_{r['idx']}_decomp.bin"
            if os.path.exists(p):
                d5.append(sum(x[11] for x in struct.iter_unpack("<12Q4I", open(p, "rb").read())))
        mech.append(dict(workload=r0[0], cell=r0[1], n=len(sel), wall_median_s=st.median(float(r["wall_s"]) for r in sel),
                         demand_faults=df, d5_ns_per_demand_fault=(st.median(d5) / df if d5 and df else float("nan")),
                         fault_already_resident=st.median(float(r["fault_already_resident"]) for r in sel)))

    # ---- write
    def wcsv(name, items, drop=()):
        if not items:
            return
        keys = [k for k in items[0].keys() if k not in drop]
        with open(f"{data_dir}/{name}", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(items)
    wcsv("primary_tests.csv", res)
    wcsv("per_pass_descriptive.csv", pas)
    wcsv("family_m_mechanism.csv", mech)
    hf = lambda x: "not evaluable (cells missing)" if x is None else ("HELD" if x else "FAILED")  # noqa: E731
    L = [suspect_txt if suspect else "", f"VERDICT: {verdict}", "", f"Primary tests (one Holm family of {m}; delta = (arm - t51)/t51):"]
    L = [x for x in L if x != ""] if not suspect else L
    for c in res:
        tag = "SLOWER" if (c["holm_sig"] and c["delta_s"] > 0) else ("FASTER" if (c["holm_sig"] and c["delta_s"] < 0) else "n.s.")
        L.append(f"  {c['size']:2s} K={c['K']:<3d} {c['arm']:9s} med {c['median_c6']:.4f} vs t51 {c['median_base']:.4f}  delta {c['delta_pct']:+.2f}%  "
                 f"p {c['p']:.2e}  Holm-thr {c['holm_thr']:.4f}  {tag}  d {c['cohen_d']:+.2f}  MDE {c['mde_pct']:.2f}%  MDE@family {c['mde_family_pct']:.2f}%  "
                 f"noout {c['noout_delta_s']:+.4f}/{c['noout_p']:.1e}")
    L += ["", "Expectations (reviewer, directional; operational definitions fixed before the run):",
          f"  XS1 in-memory K=1: t0 significantly slower than t51: {hf(xs1)}",
          f"  XS2 oversubscribed K=1 or 8: t0 significantly slower than t51 (at least one): {hf(xs2)}",
          f"  XS3 K=512, both sizes: t0 faster than t51 (direction): {hf(xs3)}  ({[(c['size'], round(c['delta_pct'], 2)) for c in k512c if c]})",
          f"  XS4 within each size, t0 delta rises monotonically as K falls (512 < 64 < 8 < 1): {hf(xs4v)}  ({ {s: [(k, round(d, 2)) for k, d in v] for s, v in xs4d.items()} })",
          f"  XS5 t25 delta lies between the t0 delta and 0, cell by cell: {hf(xs5)}  ({[(s, k, v) for s, k, v in xs5l if not v] or 'all cells'})"]
    open(f"{data_dir}/primary_report.txt", "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    figure(rows, res, fig)
    return 0


def figure(rows, res, fig):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    f_, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=False)
    xpos = {1: 0, 8: 1, 64: 2, 512: 3}
    for ax, size, fam, title in ((axes[0], "in", "IN", "In-memory (8 GiB)"), (axes[1], "ov", "OV", "Oversubscribed (24 GiB)")):
        for arm, col, mk, dx in (("stock-t0", BLUE, "o", -0.07), ("stock-t25", ORANGE, "s", 0.07)):
            meds = []
            for K in C.KS:
                wl = C.wl_key(size, K)
                b = cellrows(rows, wl, "stock-t51", fam)
                a = cellrows(rows, wl, arm, fam)
                if len(b) < 10 or len(a) < 10:
                    continue
                base = st.median(b)
                d = [100 * (x / base - 1) for x in a]
                ax.scatter([xpos[K] + dx] * len(d), d, s=12, color=col, alpha=0.35, linewidths=0, zorder=3)
                c = next((c for c in res if c["size"] == size and c["K"] == K and c["arm"] == arm), None)
                filled = bool(c and c["holm_sig"])
                ax.scatter([xpos[K] + dx], [st.median(d)], s=48, marker=mk, facecolor=col if filled else "white", edgecolor=col, linewidths=1.6, zorder=5)
                meds.append((xpos[K] + dx, st.median(d)))
            if meds:
                ax.plot([a for a, _ in meds], [b for _, b in meds], color=col, lw=1.6, zorder=4, label=arm.replace("stock-", "threshold "))
        ax.axhline(0, color=MUTED, lw=0.8)
        ax.set_xticks(list(xpos.values()))
        ax.set_xticklabels([f"K={k}" for k in xpos], fontsize=8, color=MUTED)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.set_xlabel("distinct 4 KB pages touched per 2 MB block", fontsize=8, color=MUTED)
        ax.set_ylabel("wall-clock vs median at t51 (%)", fontsize=8, color=MUTED)
        ax.grid(axis="y", color=GRID, lw=0.6)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        if ax.get_legend_handles_labels()[0]:
            ax.legend(fontsize=8, frameon=False, loc="best")
    f_.suptitle("Gate E8: stock driver, sparse access; lower threshold vs 51 (n=10 per cell; filled = Holm-significant; points = runs)",
                fontsize=9.5, color=INK, x=0.01, ha="left")
    f_.tight_layout(rect=(0, 0, 1, 0.95))
    for ext in ("png", "pdf"):
        f_.savefig(f"{fig}.{ext}", dpi=150)


def selftest():
    import random
    import shutil
    import subprocess
    scratch = tempfile.mkdtemp(prefix="e8_selftest_")
    order = list(csv.DictReader(open(f"{DATA}/e8_order.csv")))
    rng = random.Random(1)
    hdr = ["idx", "label", "workload", "family", "block", "threshold", "threshold_readback", "wall_s", "exit_code",
           "pass1_ms", "pass2_ms", "pass3_ms", "demand_faults", "fault_already_resident"]

    def write(rows_, path):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(hdr)
            for o in rows_:
                w.writerow([o["idx"], o["label"], o["workload"], o["family"], o["block"], o["threshold"], o["threshold"],
                            f"{1 + rng.random() * 0.02:.6f}", 0, 1.0, 1.0, 1.0, 1000, 0])
    results = {}
    cases = (("79-of-260", order[:79], []), ("260", order, []),
             ("ov-k64-skipped-with-260", order, ["ov_k64"]),
             ("ov-k64-skipped-ok", [o for o in order if not (o["family"] == "OV" and o["workload"] == "ov_k64")], ["ov_k64"]))
    for name, rows_, skip in cases:
        d = f"{scratch}/{name}"
        os.makedirs(d)
        shutil.copy(f"{DATA}/e8_order.csv", d)
        write(rows_, f"{d}/e8_runs.csv")
        if skip:
            open(f"{d}/ov_skipped.txt", "w").write("\n".join(f"{k} skipped at 0" for k in skip) + "\n")
        r = subprocess.run([sys.executable, __file__, d, f"{d}/fig"], capture_output=True, text=True)
        results[name] = (r.returncode, "REFUSING" in (r.stdout + r.stderr))
    ok = (results["79-of-260"] == (1, True) and results["260"][0] == 0 and results["ov-k64-skipped-with-260"] == (1, True)
          and results["ov-k64-skipped-ok"][0] == 0)
    print("selftest results (returncode, refused):", results, "scratch:", scratch)
    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 3


if __name__ == "__main__":
    if "--control" in sys.argv:
        k = sys.argv.index("--control")
        sys.exit(control(sys.argv[k + 1] if len(sys.argv) > k + 1 else tempfile.mkdtemp(prefix="e8_control_")))
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    dd = sys.argv[1] if len(sys.argv) > 1 else DATA
    ff = sys.argv[2] if len(sys.argv) > 2 else FIG
    sys.exit(analyze(dd, ff))
