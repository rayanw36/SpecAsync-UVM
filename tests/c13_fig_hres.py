#!/usr/bin/env python3
"""Gate C13 phase 3: paper/figures/F-H2-res.{pdf,png,csv}. Fraction of the 8 GiB array made resident.
malloc (HMM): `memory.used` residency (valid: 4 KB chunks), open markers; managed: E9's traced HtoD fraction (nsys; K = 1 and K = 512 only), filled squares,
labelled "managed, traced HtoD (E9)"; t0 blue, t51 grey. Managed `memory.used` is NOT plotted (it measures allocated 2 MB chunks; catalog #31).
Sources: results/analysis/gate_e/h2/residency_summary.csv, results/analysis/gate_e/e9/e9_runs.csv. CSV fallback has an `instrument` column."""
import csv, os, statistics as st, sys
sys.path.insert(0, "tests")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import make_paper_figures as M
import h2_cells as C
rd = lambda p: list(csv.DictReader(open(p)))   # noqa: E731
RES, E9 = rd("results/analysis/gate_e/h2/residency_summary.csv"), rd("results/analysis/gate_e/e9/e9_runs.csv")
M.style()
col = {0: M.THR[0], 51: M.THR[51]}
fig, ax = plt.subplots(figsize=(M.COL1 * 1.3, 2.8))
rows = []
for t in (0, 51):
    xs, ys = [], []
    for i, k in enumerate(C.KS):
        v = [float(r["residency_mib"]) / 8192 for r in RES if r["workload"] == f"malloc_k{k}" and int(r["threshold"]) == t]
        x = i + (-0.05 if t == 0 else 0.05) + 0.12
        M.pts(ax, x, v, col[t], "o", jitter=0.0, size=6, alpha=0.7); xs.append(x); ys.append(st.median(v))
        rows += [["malloc (HMM)", "memory.used residency", k, t, j, f"{y:.4f}"] for j, y in enumerate(v, 1)]
    ax.plot(xs, ys, color=col[t], lw=0.8, zorder=4)
    ax.scatter(xs, ys, s=26, marker="o", facecolor="white", edgecolor=col[t], linewidths=1.1, zorder=5)
    xs, ys = [], []
    for k in (1, 512):
        i = C.KS.index(k)
        v = [float(r["htod_bytes"]) / 2 ** 33 for r in E9 if r["workload"] == f"in_k{k}" and int(r["threshold"]) == t]
        x = i + (-0.05 if t == 0 else 0.05) - 0.12
        M.pts(ax, x, v, col[t], "s", jitter=0.0, size=6, alpha=0.7); xs.append(x); ys.append(st.median(v))
        rows += [["managed", "traced HtoD (E9)", k, t, j, f"{y:.4f}"] for j, y in enumerate(v, 1)]
    ax.scatter(xs, ys, s=26, marker="s", facecolor=col[t], edgecolor=col[t], linewidths=1.1, zorder=5)
ax.axhline(1.0, color=M.MUTED, lw=0.5, ls=":")
ax.set_xticks(range(len(C.KS))); ax.set_xticklabels([str(k) for k in C.KS]); ax.set_xlabel("pages touched per 2 MB block (K)"); ax.set_ylabel("fraction of the 8 GiB array made resident")
from matplotlib.lines import Line2D
ax.legend(handles=[Line2D([], [], marker="o", color=M.THR[0], ms=4, lw=0.8, label="threshold 0"), Line2D([], [], marker="o", color=M.THR[51], ms=4, lw=0.8, label="threshold 51 (shipped)"),
                   Line2D([], [], marker="o", ls="", mfc="w", mec="k", ms=4, label="malloc (HMM), memory.used residency"), Line2D([], [], marker="s", ls="", mfc="k", mec="k", ms=4, label="managed, traced HtoD (E9)")],
          frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=2, fontsize=6.0)
fig.tight_layout()
for ext in ("pdf", "png"): fig.savefig(f"paper/figures/F-H2-res.{ext}", bbox_inches="tight", dpi=300)
with open("paper/figures/F-H2-res.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["allocator", "instrument", "K", "threshold", "run", "fraction_of_8GiB"]); w.writerows(rows)
print("wrote", len(rows), "points")
