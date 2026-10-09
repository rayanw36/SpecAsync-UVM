#!/usr/bin/env python3
"""Gate C4 step 5b/5c (read-only; no runs). 5b: split each traced E9 run into phases from its existing nsys report and attribute CPU page
faults to each phase. 5c: for E8, estimate how much of each t0-vs-t51 wall-clock delta lies outside the kernels (DESCRIPTIVE).

Phases (all from the nsys timeline of one run; the trace starts at the first CUDA runtime call, so host work before it, and process exit, are outside):
  alloc  = first runtime call start -> start of the host-fill window
  fill   = HOST FILL WINDOW: end of the last runtime call that ends before the first CPU page fault -> start of the first runtime call after the last CPU fault
  setup  = end of fill -> start of the first kernel
  kernel = first kernel start -> last kernel end (the passes, with the host sync between them)
  post   = last kernel end -> end of the last runtime call (frees)
CPU faults per phase are counted by the start time of each CUDA_UM_CPU_PAGE_FAULT_EVENTS row. nsys stats re-exports the SQLite next to each report;
it is deleted after reading.   usage: c4_cpu_fault_phases.py [--skip-export]  (reads results/phaseB1/gate_e9/sweep/e9_*.nsys-rep, e9/e9_runs.csv, e8/e8_runs.csv)"""
import csv
import os
import sqlite3
import statistics as st
import subprocess
import sys

E9 = "results/analysis/gate_e/e9"
RAW = "results/phaseB1/gate_e9/sweep"
OUTD = "results/analysis/derived"
os.makedirs(OUTD, exist_ok=True)
PH = ["alloc", "fill", "setup", "kernel", "post"]


def phases(rep):
    r = subprocess.run(["nsys", "stats", "--report", "um_total_sum", "--format", "csv", "--force-export=true", rep], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-200:])
    db = rep.replace(".nsys-rep", ".sqlite")
    c = sqlite3.connect(db)
    try:
        api = c.execute("select start, end from CUPTI_ACTIVITY_KIND_RUNTIME order by start").fetchall()
        cpu = [x[0] for x in c.execute("select start from CUDA_UM_CPU_PAGE_FAULT_EVENTS order by start")]
        k = c.execute("select min(start), max(end), count(*) from CUPTI_ACTIVITY_KIND_KERNEL").fetchone()
    finally:
        c.close()
        os.remove(db)
    t0, t_end = api[0][0], max(e for _, e in api)
    first_f, last_f = cpu[0], cpu[-1]
    fs = max((e for _, e in api if e <= first_f), default=t0)
    fe = min((s for s, _ in api if s >= last_f), default=k[0])
    b = [t0, fs, fe, k[0], k[1], t_end]
    spans = [(b[i + 1] - b[i]) / 1e6 for i in range(5)]
    cnt = [sum(1 for x in cpu if b[i] <= x < b[i + 1]) for i in range(5)]
    return dict(zip([f"{p}_ms" for p in PH], spans)), dict(zip([f"cpu_faults_{p}" for p in PH], cnt)), len(cpu), k[2]


def split():
    runs = list(csv.DictReader(open(f"{E9}/e9_runs.csv")))
    out = []
    for r in runs:
        rep = f"{RAW}/e9_{r['idx']}.nsys-rep"
        sp, cn, ncpu, nk = phases(rep)
        out.append(dict(idx=r["idx"], workload=r["workload"], threshold=r["threshold"], kernels=nk, cpu_faults=ncpu, **{k: round(v, 3) for k, v in sp.items()}, **cn))
        print(f"  idx {r['idx']:>2} {r['workload']:8s} t{r['threshold']:<3s} fill {sp['fill_ms']:8.1f} ms  kernel {sp['kernel_ms']:8.1f} ms  cpu faults {ncpu}", flush=True)
    with open(f"{OUTD}/c4_e9_phase_split.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    return out


def e8_outside():
    rows = list(csv.DictReader(open("results/analysis/gate_e/e8/e8_runs.csv")))
    rows = [r for r in rows if r["family"] in ("IN", "OV")]
    out = []
    for size, fam in (("in", "IN"), ("ov", "OV")):
        for K in (1, 8, 64, 512):
            wl = f"{size}_k{K}"
            def med(cell, f):
                v = [f(r) for r in rows if r["workload"] == wl and r["label"].endswith(cell) and r["family"] == fam]
                return st.median(v)
            wall = lambda r: float(r["wall_s"])  # noqa: E731
            kern = lambda r: (float(r["pass1_ms"]) + float(r["pass2_ms"]) + float(r["pass3_ms"])) / 1e3  # noqa: E731
            w51, k51 = med("stock-t51", wall), med("stock-t51", kern)
            for arm in ("stock-t0", "stock-t25"):
                wa, ka = med(arm, wall), med(arm, kern)
                dw, dk = wa - w51, ka - k51
                out.append(dict(size=size, K=K, arm=arm, wall_t51_s=round(w51, 4), wall_arm_s=round(wa, 4), delta_wall_s=round(dw, 4),
                                kernel_t51_s=round(k51, 4), kernel_arm_s=round(ka, 4), delta_kernel_s=round(dk, 4),
                                delta_outside_kernels_s=round(dw - dk, 4), outside_share_of_delta=round((dw - dk) / dw, 3) if abs(dw) > 1e-9 else float("nan"),
                                outside_t51_s=round(w51 - k51, 4), outside_arm_s=round(wa - ka, 4)))
    with open(f"{OUTD}/c4_e8_outside_kernels.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    return out


if __name__ == "__main__":
    if "--skip-export" in sys.argv:
        sp = list(csv.DictReader(open(f"{OUTD}/c4_e9_phase_split.csv")))
    else:
        print("E9 phase split (one nsys export per run):")
        sp = split()
    e8 = e8_outside()
    print(f"wrote {OUTD}/c4_e9_phase_split.csv ({len(sp)} runs) and {OUTD}/c4_e8_outside_kernels.csv ({len(e8)} rows)")
