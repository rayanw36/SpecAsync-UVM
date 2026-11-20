#!/usr/bin/env python3
"""C25 step 2: evidence ids for the density-rule volume statements (from tests/c22_vii4_density_sim.py: SIM, E9, E9R) and the T4 SGEMM MDE rerun. Writes results/analysis/consolidation/C25_CHECKS.csv
(read by tests/c1_evidence.py)."""
import csv, statistics as st, sys, io, contextlib
sys.path.insert(0, "tests")
with contextlib.redirect_stdout(io.StringIO()):
    ns = {}
    exec(open("tests/c22_vii4_density_sim.py").read(), ns)
SIM, E9, E9R, GIB = ns["SIM"], ns["E9"], ns["E9R"], ns["GIB"]
rows = []
for t in (0, 51):
    pr = SIM[("in", 1)][t][0]; me = float(E9[("in_k1", t)]["htod_bytes_median"]) / GIB / 8
    rows.append((f"C25.vii4.in_k1.t{t}.predicted_vs_measured", f"density-rule first-touch volume {100*pr:.2f}% of the 8 GiB array predicted, E9 traced HtoD {100*me:.2f}% measured (measured/predicted {me/pr:.2f})", "tests/c22_vii4_density_sim.py; gate_e/e9/cell_medians.csv", "mean over blocks of (faulted U prefetch regions)/512 on E8's page list; htod_bytes_median / 8 GiB"))
for K in (1, 8):
    for t in (0, 51):
        p1 = st.median(float(r["pass1_htod_bytes"]) for r in E9R if r["workload"] == f"ov_k{K}" and int(r["threshold"]) == t) / GIB / 24
        pr = SIM[("ov", K)][t][0]
        rows.append((f"C25.vii4.ov_k{K}.t{t}.first_pass_ratio", f"oversubscribed first-pass HtoD {100*p1:.2f}% of the 24 GiB array measured against {100*pr:.2f}% predicted = {p1/pr:.2f}x", "tests/c22_vii4_density_sim.py; gate_e/e9/e9_runs.csv", "median pass1_htod_bytes / 24 GiB over predicted fraction"))
# SGEMM T4 MDE rerun
_a = sys.argv; sys.argv = sys.argv[:1]
import e7_analyze as E   # noqa: E402
sys.argv = _a
T4 = [r for r in csv.DictReader(open("results/analysis/t4/e7t4_runs.csv")) if r["workload"] == "sgemm"]
c = {k: [float(r["wall_s"]) for r in T4 if r["label"].endswith(k)] for k in ("stock-t0", "stock-t51")}
x = E.compare(c["stock-t51"], c["stock-t0"], 14); y = E.compare([v for v in c["stock-t51"] if v < 20], c["stock-t0"], 14); z = E.compare(E.H.tukey_keep(c["stock-t51"]), E.H.tukey_keep(c["stock-t0"]), 14)
rows.append(("C25.v.t4_sgemm.mde_rerun", f"T4 SGEMM t0 vs t51, MDE at the family alpha (m = 14): all runs {x['mde_family_pct']:.2f}%; without the one cold t51 run (20.455 s) {y['mde_family_pct']:.3f}%; Tukey-trimmed cells {z['mde_family_pct']:.3f}%", "t4/e7t4_runs.csv; tests/e7_analyze.py (compare, mde_family)", "helper rerun on the cells without the flagged run(s)"))
with open("results/analysis/consolidation/C25_CHECKS.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["id", "value", "source", "computation"]); w.writerows(rows)
for r in rows: print(r[0], "|", r[1])
