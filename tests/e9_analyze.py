#!/usr/bin/env python3
"""Gate E9 analysis (E9_PREREGISTRATION.md). DESCRIPTIVE ONLY: per-cell medians and ranges of unified-memory counts; no hypothesis
test (n = 3); wall-clock is recorded but never compared or tabulated here.

  e9_analyze.py --control [SCRATCH_DIR]   extraction control: re-derives one traced 1 GiB bench_sparse run and checks that the SQLite
                                          totals equal nsys's own um_total_sum report (HtoD, DtoH, GPU faults, CPU faults)
  e9_analyze.py --selftest                refusal tests on synthetic data (scratch directory only)
  e9_analyze.py [DATA_DIR [FIG_PREFIX]]   the pre-registered analysis

Refuses to run unless the rows present equal the order rows minus blocks recorded in blocks_skipped.txt.
Operational definitions of the reviewer's expectations (fixed here before any traced run):
  Y1  oversubscribed K=1: median HtoD bytes at t0 >= 10 x median HtoD bytes at t51.
  Y2  oversubscribed K=1 AND K=8: at t0 the median DtoH bytes are >= 1 GiB in EACH of the 3 passes, AND the median total DtoH at t51 is
      <= 0.25 x that at t0 ("much smaller" is operationalised as 4x smaller).
  Y3  Stencil-24K: |median HtoD(t0) - median HtoD(t51)| / median HtoD(t51) <= 5% AND median GPU page faults (nsys um_total_sum) at t0 < at t51.
  Y4  oversubscribed K=1 at t51: in BOTH repeat passes (2 and 3) the median DtoH bytes are > 0 (eviction accompanies the repeat-pass cost; the
      migration is not zero). Remote-map / thrashing events cannot be observed (nsys 2025.3.2 has no table or report for them), so only the DtoH
      arm of the expectation is testable. Reported whichever way it goes.
"""
import csv
import math
import os
import statistics as st
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
DATA = "results/analysis/gate_e/e9"
FIG = "results/analysis/gate_e/e9_um_bytes"
PROBE = "results/phaseB1/gate_e9/probe/probe.nsys-rep"
GIB = 1073741824
BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#d8d8d4"
WLS = ["ov_k1", "ov_k8", "ov_k64", "ov_k512", "in_k1", "in_k512", "stencil"]
TITLE = {"ov_k1": "oversub K=1", "ov_k8": "oversub K=8", "ov_k64": "oversub K=64", "ov_k512": "oversub K=512",
         "in_k1": "in-memory K=1", "in_k512": "in-memory K=512", "stencil": "Stencil-24K"}
NUM = ["htod_bytes", "dtoh_bytes", "dtod_bytes", "uvm_migrations", "htod_fault_bytes", "htod_prefetch_bytes", "htod_evict_bytes", "dtoh_fault_bytes",
       "dtoh_prefetch_bytes", "dtoh_evict_bytes", "gpu_fault_events", "gpu_faults_sum", "report_gpu_faults", "report_cpu_faults"] + \
      [f"pass{i}_{d}_bytes" for i in (1, 2, 3) for d in ("htod", "dtoh")]


def skipped_blocks(data_dir):
    p = f"{data_dir}/blocks_skipped.txt"
    return {int(l.split()[1]) for l in open(p) if l.startswith("block")} if os.path.exists(p) else set()


def num(r, k):
    return float(r[k]) if r.get(k, "") not in ("", None) else float("nan")


def med(rows, k):
    return st.median(num(r, k) for r in rows)


def control(scratch):
    import e9_extract as X
    if not os.path.exists(PROBE):
        print(f"CONTROL: cannot run, no probe report at {PROBE}")
        return 3
    keep = os.path.join(scratch, "probe_copy")
    os.makedirs(scratch, exist_ok=True)
    e = X.extract(PROBE, keep_sqlite=False)
    checks = [("HtoD: report MB == sum of UVM HtoD memcpy bytes / 1e6 (3 dp)", round(e["htod_bytes"] / 1e6, 3), e["report_htod_mb"]),
              ("DtoH: report MB == sum of UVM DtoH memcpy bytes / 1e6 (3 dp)", round(e["dtoh_bytes"] / 1e6, 3), e["report_dtoh_mb"]),
              ("GPU faults: report == sum of numberOfPageFaults", e["gpu_faults_sum"], e["report_gpu_faults"]),
              ("HtoD causes sum to the total", e["htod_fault_bytes"] + e["htod_prefetch_bytes"] + e["htod_evict_bytes"] + e["htod_other_bytes"], e["htod_bytes"]),
              ("per-pass HtoD sums to the total", sum(e[f"pass{i}_htod_bytes"] for i in (1, 2, 3)), e["htod_bytes"])]
    ok = all(a == b for _, a, b in checks)
    lines = ["# E9 extraction control (one fresh traced 1 GiB bench_sparse run, K=8, 3 passes, seed 202610081, threshold 51)"]
    lines += [f"{'OK ' if a == b else 'BAD'} {n}: {a} vs {b}" for n, a, b in checks]
    lines.append(f"CONTROL: {'PASS' if ok else 'FAIL'}")
    out = "\n".join(lines) + "\n"
    open(os.path.join(scratch, "extraction_control.txt"), "w").write(out)
    print(out, "written to", scratch)
    return 0 if ok else 3


def analyze(data_dir, fig):
    order = list(csv.DictReader(open(f"{data_dir}/e9_order.csv")))
    rows = list(csv.DictReader(open(f"{data_dir}/e9_runs.csv")))
    sk = skipped_blocks(data_dir)
    exp = [o for o in order if ((int(o["idx"]) - 1) // 14 + 1) not in sk]
    if len(rows) != len(exp):
        sys.exit(f"REFUSING: {len(rows)} rows present; pre-registered {len(exp)} (order minus skipped blocks {sorted(sk) or 'none'}). No interim analysis.")
    for o, r in zip(exp, rows):
        if (o["idx"], o["label"]) != (r["idx"], r["label"]):
            sys.exit(f"REFUSING: order mismatch at idx {o['idx']}")
    for r in rows:
        if r["exit_code"] != "0" or r["threshold_readback"] != r["threshold"]:
            sys.exit(f"REFUSING: idx {r['idx']} exit/threshold read-back inconsistent")
    cell = {}
    for r in rows:
        cell.setdefault((r["workload"], int(r["threshold"])), []).append(r)
    summ = []
    for wl in WLS:
        for t in (0, 51):
            rs = cell.get((wl, t), [])
            if not rs:
                continue
            d = dict(workload=wl, threshold=t, n=len(rs))
            for k in NUM:
                v = [num(r, k) for r in rs]
                d[f"{k}_median"] = st.median(v)
                d[f"{k}_min"], d[f"{k}_max"] = min(v), max(v)
            summ.append(d)
    with open(f"{data_dir}/cell_medians.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0].keys()))
        w.writeheader()
        w.writerows(summ)

    def M(wl, t, k):
        rs = cell.get((wl, t))
        return med(rs, k) if rs else float("nan")
    L = ["E9 descriptive results (medians of n runs per cell; ranges in cell_medians.csv; wall-clock NOT compared)", ""]
    L.append(f"{'cell':16s} thr  n  HtoD GiB  DtoH GiB  GPU faults  CPU faults  | per-pass DtoH GiB (1,2,3) | HtoD by cause GiB: fault / prefetch")
    for d in summ:
        wl, t = d["workload"], d["threshold"]
        L.append(f"{TITLE[wl]:16s} t{t:<3d} {d['n']} {d['htod_bytes_median'] / GIB:9.3f} {d['dtoh_bytes_median'] / GIB:9.3f} {d['report_gpu_faults_median']:11,.0f} "
                 f"{d['report_cpu_faults_median']:11,.0f}  | " + " ".join(f"{M(wl, t, f'pass{i}_dtoh_bytes') / GIB:7.3f}" for i in (1, 2, 3)) +
                 f"  | {d['htod_fault_bytes_median'] / GIB:7.3f} / {d['htod_prefetch_bytes_median'] / GIB:7.3f}")
    y1 = M("ov_k1", 0, "htod_bytes"), M("ov_k1", 51, "htod_bytes")
    Y1 = None if any(math.isnan(x) for x in y1) else (y1[0] >= 10 * y1[1], y1)
    y2 = {}
    for K in (1, 8):
        wl = f"ov_k{K}"
        per = [M(wl, 0, f"pass{i}_dtoh_bytes") for i in (1, 2, 3)]
        tot0, tot51 = M(wl, 0, "dtoh_bytes"), M(wl, 51, "dtoh_bytes")
        y2[K] = (all(p >= GIB for p in per) and tot51 <= 0.25 * tot0, per, tot0, tot51)
    Y2 = None if any(any(math.isnan(p) for p in v[1]) for v in y2.values()) else all(v[0] for v in y2.values())
    h0, h51 = M("stencil", 0, "htod_bytes"), M("stencil", 51, "htod_bytes")
    f0, f51 = M("stencil", 0, "report_gpu_faults"), M("stencil", 51, "report_gpu_faults")
    Y3 = None if any(math.isnan(x) for x in (h0, h51, f0, f51)) else (abs(h0 - h51) / h51 <= 0.05 and f0 < f51, abs(h0 - h51) / h51, f0, f51)
    p23 = [M("ov_k1", 51, f"pass{i}_dtoh_bytes") for i in (2, 3)]
    m23 = [M("ov_k1", 51, f"pass{i}_htod_bytes") + M("ov_k1", 51, f"pass{i}_dtoh_bytes") for i in (2, 3)]
    Y4 = None if any(math.isnan(x) for x in p23) else (all(x > 0 for x in p23), p23, m23)
    hf = lambda y: "not evaluable (cells missing)" if y is None else ("HELD" if (y if isinstance(y, bool) else y[0]) else "FAILED")  # noqa: E731
    L += ["", "Expectations (reviewer, directional; operational definitions fixed before the run):",
          f"  Y1 oversub K=1: HtoD at t0 >= 10x t51: {hf(Y1)}" + (f"  (t0 {y1[0] / GIB:.3f} GiB vs t51 {y1[1] / GIB:.3f} GiB, ratio {y1[0] / y1[1]:.2f}x)" if Y1 else ""),
          f"  Y2 oversub K=1 and K=8: t0 DtoH >= 1 GiB in each pass, t51 total <= 0.25 x t0: {hf(Y2)}" +
          ("  (" + "; ".join(f"K={K}: t0 passes {[round(p / GIB, 3) for p in v[1]]} GiB, total t0 {v[2] / GIB:.3f} vs t51 {v[3] / GIB:.3f} GiB, {'ok' if v[0] else 'no'}" for K, v in y2.items()) + ")" if Y2 is not None else ""),
          f"  Y3 Stencil-24K: HtoD within 5% and fewer GPU faults at t0: {hf(Y3)}" + (f"  (HtoD diff {100 * Y3[1]:.2f}%; GPU faults t0 {Y3[2]:,.0f} vs t51 {Y3[3]:,.0f})" if Y3 else ""),
          f"  Y4 oversub K=1 at t51: DtoH eviction in both repeat passes (migration not zero): {hf(Y4)}" +
          (f"  (DtoH GiB passes 2,3: {[round(x / GIB, 4) for x in Y4[1]]}; HtoD+DtoH GiB: {[round(x / GIB, 4) for x in Y4[2]]}; thrashing/remote-map events not observable in this nsys)" if Y4 else "")]
    open(f"{data_dir}/primary_report.txt", "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    figure(summ, rows, fig)
    return 0


def figure(summ, rows, fig):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    f_, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))
    wls = [w for w in WLS if any(d["workload"] == w for d in summ)]
    for ax, key, title in ((axes[0], "htod_bytes", "Host-to-device migrated (GiB)"), (axes[1], "dtoh_bytes", "Device-to-host migrated (GiB)")):
        for t, col, dx, name in ((0, BLUE, -0.2, "threshold 0"), (51, ORANGE, 0.2, "threshold 51")):
            xs, ys = [], []
            for i, w in enumerate(wls):
                rs = [r for r in rows if r["workload"] == w and int(r["threshold"]) == t]
                if not rs:
                    continue
                v = [float(r[key]) / GIB for r in rs]
                ax.scatter([i + dx] * len(v), v, s=14, color=col, alpha=0.4, linewidths=0, zorder=3)
                xs.append(i + dx)
                ys.append(st.median(v))
            ax.bar(xs, ys, width=0.36, color=col, alpha=0.85, label=name, zorder=2)
        ax.set_yscale("symlog", linthresh=0.01)
        ax.set_xticks(range(len(wls)))
        ax.set_xticklabels([TITLE[w].replace(" ", "\n", 1) for w in wls], fontsize=7.5, color=MUTED)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.grid(axis="y", color=GRID, lw=0.6)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.legend(fontsize=8, frameon=False, loc="upper right")
    f_.suptitle("Gate E9: unified-memory bytes migrated per run, stock driver, threshold 0 vs 51 (bars = median of 3; points = runs; symlog axis)",
                fontsize=9.5, color=INK, x=0.01, ha="left")
    f_.tight_layout(rect=(0, 0, 1, 0.95))
    for ext in ("png", "pdf"):
        f_.savefig(f"{fig}.{ext}", dpi=150)


def selftest():
    import shutil
    import subprocess
    scratch = tempfile.mkdtemp(prefix="e9_selftest_")
    order = list(csv.DictReader(open(f"{DATA}/e9_order.csv")))
    hdr = ["idx", "label", "workload", "threshold", "threshold_readback", "exit_code", "pass1_ms"] + NUM

    def write(rows_, path):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(hdr)
            for o in rows_:
                w.writerow([o["idx"], o["label"], o["workload"], o["threshold"], o["threshold"], 0, 1.0] + [1000 + int(o["idx"])] * len(NUM))
    res = {}
    for name, rows_, skip in (("20-of-42", order[:20], []), ("42", order, []), ("42-with-skip", order, [3]), ("28-skip3", order[:28], [3])):
        d = f"{scratch}/{name}"
        os.makedirs(d)
        shutil.copy(f"{DATA}/e9_order.csv", d)
        write(rows_, f"{d}/e9_runs.csv")
        if skip:
            open(f"{d}/blocks_skipped.txt", "w").write("".join(f"block {b} skipped at 0\n" for b in skip))
        r = subprocess.run([sys.executable, __file__, d, f"{d}/fig"], capture_output=True, text=True)
        res[name] = (r.returncode, "REFUSING" in (r.stdout + r.stderr))
    ok = res["20-of-42"] == (1, True) and res["42"][0] == 0 and res["42-with-skip"] == (1, True) and res["28-skip3"][0] == 0
    print("selftest results (returncode, refused):", res, "scratch:", scratch)
    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 3


if __name__ == "__main__":
    if "--control" in sys.argv:
        k = sys.argv.index("--control")
        sys.exit(control(sys.argv[k + 1] if len(sys.argv) > k + 1 else tempfile.mkdtemp(prefix="e9_control_")))
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(analyze(sys.argv[1] if len(sys.argv) > 1 else DATA, sys.argv[2] if len(sys.argv) > 2 else FIG))
