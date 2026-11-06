#!/usr/bin/env python3
"""Gate H2 analysis (H2_PREREGISTRATION.md). Helpers imported UNCHANGED: e7_analyze (compare, holm_apply, mde_family) -> e09b_analyze.
delta = (arm - t51) / t51; negative = t0 is faster. Timing family: ONE Holm family of 8 (t0 vs t51 for each allocator x K), alpha 0.05, MDE at the family alpha (m = 8).
Residency (mechanism): peak - baseline of nvidia-smi memory.used per run (MiB); 8 GiB = 8192 MiB.
  h2_analyze.py --control [SCRATCH]   synthetic control: the predicted pattern must give MECHANISM SUPPORTED; a copy with the t0 medians scaled by K (Z1 fails) must give REFUTED or PARTIAL
  h2_analyze.py [DATA_DIR]            the pre-registered analysis (refuses unless the timed rows equal the timed order)"""
import csv, os, random, statistics as st, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import e7_analyze as A  # noqa: E402
import h2_cells as C  # noqa: E402
D = "results/analysis/gate_e/h2"
MIB8 = 8192.0
BOOT_SEED, BOOT_N = 20261106, 10000


def cell(rows, a, k, t): return [float(r["wall_s"]) for r in rows if r["workload"] == f"{a}_k{k}" and r["label"].endswith(f"stock-t{t}")]
def rcell(res, a, k, t): return [float(r["residency_mib"]) for r in res if r["workload"] == f"{a}_k{k}" and int(r["threshold"]) == t]


def evaluate(rows, res):
    tests = []
    for a in C.ALLOCS:
        for k in C.KS:
            c = A.compare(cell(rows, a, k, 51), cell(rows, a, k, 0), len(C.TESTED)); c.update(alloc=a, K=k, workload=f"{a}_k{k}"); tests.append(c)
    A.holm_apply(tests)
    T = {(c["alloc"], c["K"]): c for c in tests}
    med = lambda a, k, t: st.median(cell(rows, a, k, t))   # noqa: E731
    rmed = lambda a, k, t: st.median(rcell(res, a, k, t))  # noqa: E731
    z = {}
    m0 = [med("malloc", k, 0) for k in C.KS]; m51 = [med("malloc", k, 51) for k in C.KS]
    z["Z1"] = ("t0 flat in K on malloc: max/min of t0 medians <= 1.10", max(m0) / min(m0) <= 1.10, f"max/min = {max(m0) / min(m0):.3f}")
    z["Z2"] = ("t51 strictly increasing in K on malloc", all(b > a_ for a_, b in zip(m51, m51[1:])), "t51 medians " + ", ".join(f"{v:.3f}" for v in m51))
    d = [T[("malloc", k)]["delta_pct"] for k in C.KS]
    z["Z3"] = ("malloc delta strictly decreasing in K; K=1 Holm-sig and positive; K=512 Holm-sig and negative",
               all(b < a_ for a_, b in zip(d, d[1:])) and T[("malloc", 1)]["holm_sig"] and d[0] > 0 and T[("malloc", 512)]["holm_sig"] and d[-1] < 0, "deltas " + ", ".join(f"{v:+.2f}%" for v in d))
    r_m0, r_m51, r_g0 = rmed("malloc", 1, 0), rmed("malloc", 1, 51), rmed("managed", 1, 0)
    z["Z4"] = ("malloc K=1 t0 residency >= 0.8 x 8 GiB", r_m0 >= 0.8 * MIB8, f"{r_m0:.0f} MiB = {r_m0 / MIB8:.3f} of 8 GiB")
    z["Z5"] = ("malloc K=1 t51 residency <= 0.1 x 8 GiB", r_m51 <= 0.1 * MIB8, f"{r_m51:.0f} MiB = {r_m51 / MIB8:.3f} of 8 GiB")
    z["Z6"] = ("managed K=1 t0 residency >= 0.8 x 8 GiB", r_g0 >= 0.8 * MIB8, f"{r_g0:.0f} MiB = {r_g0 / MIB8:.3f} of 8 GiB")
    rng = random.Random(BOOT_SEED)
    cells = {(a, t): cell(rows, a, 1, t) for a in C.ALLOCS for t in (0, 51)}
    diffs = []
    for _ in range(BOOT_N):
        dd = {}
        for a in C.ALLOCS:
            s0 = [rng.choice(cells[(a, 0)]) for _ in cells[(a, 0)]]; s51 = [rng.choice(cells[(a, 51)]) for _ in cells[(a, 51)]]
            dd[a] = 100 * (st.median(s0) / st.median(s51) - 1)
        diffs.append(dd["malloc"] - dd["managed"])
    diffs.sort(); lo, hi = diffs[int(0.025 * BOOT_N)], diffs[int(0.975 * BOOT_N) - 1]
    dpt = T[("malloc", 1)]["delta_pct"] - T[("managed", 1)]["delta_pct"]
    z["Z7"] = ("K=1 delta larger on malloc than managed; 95% bootstrap CI of the difference has lower bound > 0", lo > 0, f"difference {dpt:+.2f} points, 95% CI [{lo:+.2f}, {hi:+.2f}] ({BOOT_N} resamples within cells, seed {BOOT_SEED})")
    if all(z[k][1] for k in ("Z1", "Z4", "Z6", "Z7")): verdict = "MECHANISM SUPPORTED"
    elif r_m0 <= 0.5 * MIB8 or max(m0) / min(m0) > 1.25: verdict = "MECHANISM REFUTED"
    else: verdict = "PARTIAL"
    return tests, z, verdict, dict(res=dict(m0=r_m0, m51=r_m51, g0=r_g0), ci=(lo, hi, dpt))


def synthetic(perturb=False):
    rows, res = [], []
    for a in C.ALLOCS:
        for k in C.KS:
            for t in C.THR:
                if a == "malloc": base = (6.5 if t == 0 else 2.0 + 0.01 * k) if True else 0
                else: base = (2.2 + 0.0003 * k if t == 0 else 2.0 + 0.01 * k)
                if a == "malloc" and t == 51: base = 2.1 + 0.012 * k
                if perturb and t == 0: base *= k
                for j in range(10):
                    rows.append(dict(workload=f"{a}_k{k}", label=f"{a}_k{k} stock-t{t}", wall_s=f"{base * (1 + 0.002 * ((j * 7) % 5 - 2)):.6f}"))
                resi = 7400 if t == 0 else 300
                for j in range(3): res.append(dict(workload=f"{a}_k{k}", threshold=str(t), residency_mib=str(resi + j)))
    return rows, res


def control(scratch=None):
    scratch = scratch or tempfile.mkdtemp(prefix="h2_control_")
    out = []
    _, z, v1, _ = evaluate(*synthetic())
    _, z2, v2, _ = evaluate(*synthetic(perturb=True))
    ok = v1 == "MECHANISM SUPPORTED" and v2 in ("MECHANISM REFUTED", "PARTIAL")
    out = [f"synthetic predicted pattern -> {v1} (expected MECHANISM SUPPORTED)", f"perturbed copy (t0 scaled by K, Z1 fails: {z2['Z1'][2]}) -> {v2} (expected REFUTED or PARTIAL)", f"CONTROL: {'PASS' if ok else 'FAIL'}"]
    os.makedirs(scratch, exist_ok=True); open(f"{scratch}/h2_control.txt", "w").write("\n".join(out) + "\n"); print("\n".join(out))
    return ok


def analyze(data_dir):
    order = list(csv.DictReader(open(f"{data_dir}/h2_order.csv")))
    rows = list(csv.DictReader(open(f"{data_dir}/h2_runs.csv")))
    if [r["idx"] for r in rows] != [o["idx"] for o in order] or any(r["label"] != o["label"] for r, o in zip(rows, order)):
        sys.exit(f"REFUSING: {len(rows)} timed rows present, {len(order)} expected")
    res = list(csv.DictReader(open(f"{data_dir}/residency_summary.csv"))) if os.path.exists(f"{data_dir}/residency_summary.csv") else []
    if not res: sys.exit("REFUSING: no residency summary")
    tests, z, verdict, extra = evaluate(rows, res)
    keys = ["alloc", "K", "n_base", "n_c6", "median_base", "median_c6", "delta_s", "delta_pct", "U", "p", "mwu_method", "cohen_d", "mde_s", "mde_family_s", "m_family", "mde_pct", "mde_family_pct", "noout_delta_s", "noout_p", "n_outliers_base", "n_outliers_arm", "holm_thr", "holm_sig"]
    with open(f"{data_dir}/h2_tests.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore"); w.writeheader(); w.writerows(tests)
    rcells = []
    for a in C.ALLOCS:
        for k in C.KS:
            for t in (0, 51):
                v = rcell(res, a, k, t); rcells.append(dict(alloc=a, K=k, threshold=t, n=len(v), median_mib=st.median(v), min_mib=min(v), max_mib=max(v), median_frac=st.median(v) / MIB8))
    with open(f"{data_dir}/h2_residency_cells.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rcells[0])); w.writeheader(); w.writerows(rcells)
    with open(f"{data_dir}/h2_z.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "criterion", "outcome", "detail"])
        for k, (c, ok, d) in z.items(): w.writerow([k, c, "HELD" if ok else "FAILED", d])
        w.writerow(["verdict", "", verdict, ""])
    print(verdict)
    for k, (c, ok, d) in z.items(): print(k, "HELD" if ok else "FAILED", d)
    return 0


if __name__ == "__main__":
    if "--control" in sys.argv:
        k = sys.argv.index("--control"); sys.exit(0 if control(sys.argv[k + 1] if len(sys.argv) > k + 1 else None) else 3)
    sys.exit(analyze(sys.argv[1] if len(sys.argv) > 1 else D))
