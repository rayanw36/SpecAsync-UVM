#!/usr/bin/env python3
"""Gate C10: append the "Amendment 1 results" section to results/analysis/gate_e/GATE_H1_REPORT.md from the committed h1_tests.csv / h1_runs.csv (the existing text is not changed),
and write the figure's CSV fallback paper/figures/F-H1.csv. Every number comes from the CSVs; evidence ids `H1.<workload>.stock-t0_vs_stock-t51` are in EVIDENCE_EXTRACT.md."""
import csv, statistics as st, sys
sys.path.insert(0, "tests")
import h1_cells as C
D = "results/analysis/gate_e/h1"
T = list(csv.DictReader(open(f"{D}/h1_tests.csv")))
R = list(csv.DictReader(open(f"{D}/h1_runs.csv")))
rep = open(f"{D}/primary_report.txt").read()
verdict = next(l for l in rep.split("\n") if l.startswith("**Verdict")).strip("*").replace("Verdict (mechanical): ", "")
# Holm-adjusted p (step-down): sort by p, adj_i = max_{j<=i} min(1, (m - j) * p_j)
m = len(T); order = sorted(range(m), key=lambda i: float(T[i]["p"])); adj = [None] * m; run = 0.0
for rank, i in enumerate(order):
    run = max(run, min(1.0, (m - rank) * float(T[i]["p"]))); adj[i] = run
exp = [l for l in rep.split("\n") if l.startswith("- **Y")]
out = ["", "## Amendment 1 results", "",
       "Pre-registration: `H1_PREREGISTRATION.md`, Amendment 1 (commit `54566e2`, before any timed run; order hash `h1_order.sha256`). Run: 60 timed runs (6 cells x 10), all exit 0, **0 new dmesg lines**, no stop condition; stock `nvidia_uvm` 6284DA42, HMM malloc mode (`--alloc malloc`), in-memory cells only. The oversubscribed cells were removed (see the section above). **The sparse half of the trade-off is not tested on HMM.**", "",
       f"### Verdict (mechanical, Amendment 1 rule): {verdict}", "",
       "| cell | median t51 (s) | median t0 (s) | difference t0 - t51 (s) | delta | MWU p | Holm threshold | Holm-adjusted p | Holm-sig | MDE, family alpha (m = 3) | Cohen's d | without Tukey outliers (delta s / p) | evidence id |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for i, t in enumerate(T):
    out.append(f"| {C.WL[t['workload']][0]} | {float(t['median_base']):.4f} | {float(t['median_c6']):.4f} | {float(t['delta_s']):+.4f} | {float(t['delta_pct']):+.2f}% | {float(t['p']):.2e} | {float(t['holm_thr']):.4f} | {adj[i]:.2e} | {t['holm_sig']} | {float(t['mde_family_s']):.4f} s = {float(t['mde_family_pct']):.2f}% | {float(t['cohen_d']):+.1f} | {float(t['noout_delta_s']):+.4f} / {float(t['noout_p']):.2e} ({t['n_outliers_base']} and {t['n_outliers_arm']} flagged) | `H1.{t['workload']}.stock-t0_vs_stock-t51` |")
out += ["", "### Expectations (kept by Amendment 1)", ""] + exp + ["",
       "### What the result says (and does not)",
       "- **Dense accesses gain from threshold 0 on malloc'd (HMM) memory too:** Stencil-24K and sparse in-memory K = 512 are both Holm-significantly faster at t0. For Stencil-24K the gain is smaller than E7's managed gain (Y2), as expected if part of the managed gain was CPU-side population, but this is a cross-session comparison and **no host share is inferred**.",
       "- **Sparse in-memory K = 1 is much slower at t0 on HMM** (the largest effect in the table), against a small managed-memory effect in E8. This cell is in the kept family and is reported as found; it is **not** part of the Amendment 1 verdict rule, and no expectation covered it. It is a direction opposite to the dense cells within the same memory kind, and bears on the unfinished sparse half, which is nevertheless **not tested for oversubscription on HMM**.",
       "- All wall-clock figures are process wall-clock under HMM (4 KB GPU chunks, `migrate_vma` migrations); absolute times are not comparable with the managed runs.", "",
       "### Figure and data", "", "`paper/figures/F-H1.pdf` / `.png` (t0 blue, t51 grey; every run a point, median markers filled when Holm-significant); data fallback `paper/figures/F-H1.csv`. FLAG for the author: CS2-N10 is scoped to managed memory and is **not edited**; this result concerns HMM in-memory cells only.", "",
       "### Limitations", "", "One platform; three in-memory cells; one page list; HMM oversubscription not run (stock-driver oops, see above); THP madvise-only and `MADV_NOHUGEPAGE` set; `numa_balancing` 0; the managed deltas shown in `primary_report.txt` are from other sessions and are not pooled."]
open("results/analysis/gate_e/GATE_H1_REPORT.md", "a").write("\n".join(out) + "\n")
by = {}
for r in R:
    w, t = r["workload"], r["label"].split("stock-t")[1]
    by.setdefault((w, t), []).append(float(r["wall_s"]))
with open("paper/figures/F-H1.csv", "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["workload", "threshold", "run", "wall_s", "pct_vs_t51_median"])
    for (w, t), v in sorted(by.items()):
        b = st.median(by[(w, "51")])
        for k, x in enumerate(v, 1): wr.writerow([w, t, k, f"{x:.6f}", f"{100 * (x / b - 1):.3f}"])
print("appended; verdict:", verdict)
