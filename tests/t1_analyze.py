#!/usr/bin/env python3
"""t1_analyze.py -- pre-registered statistical pipeline for T1's interleaved
Gate 3 rerun, per results/analysis/PREREGISTRATION.md. Filters to phase=kept
(discards the 2-rotation warm-up), computes medians, Mann-Whitney U
(two-sided), Holm-Bonferroni correction across the pre-declared 6-comparison
family, MDE per primary comparison, and a Tukey-fence outlier scan compared
against OUTLIER_FORENSICS.md's original findings.
"""
import csv, sys, statistics as st
from scipy import stats
import numpy as np

CSV = sys.argv[1] if len(sys.argv) > 1 else "results/phaseB2/gate3_interleaved/gate3_interleaved_times.csv"

data = {}  # (config, bench) -> list of (rep_in_cell, wall_s, run_order)
with open(CSV) as f:
    for row in csv.DictReader(f):
        if row.get("dmesg_delta", "").isdigit() or True:
            pass
        phase = row["rep_in_cell"].split("_")[0]
        if phase != "kept":
            continue
        key = (row["config"], row["bench"])
        data.setdefault(key, []).append((row["rep_in_cell"], float(row["wall_s"]), int(row["run_order_idx"])))

print("=== Descriptive: n, median per cell (kept phase only) ===")
for k in sorted(data):
    vals = [v[1] for v in data[k]]
    print(f"  {k[0]:<4} {k[1]:<16} n={len(vals):<3} median={st.median(vals):.4f}s  mean={st.mean(vals):.4f}s  stdev={st.stdev(vals):.4f}")

def tukey_fence(vals):
    q1, q3 = np.percentile(vals, [25, 75])
    iqr = q3 - q1
    lo, hi = q1 - 1.5*iqr, q3 + 1.5*iqr
    return lo, hi, [v for v in vals if v < lo or v > hi]

print("\n=== Outlier scan (Tukey fence, kept phase, per PREREGISTRATION.md Section 7) ===")
for k in sorted(data):
    vals = [v[1] for v in data[k]]
    lo, hi, flagged = tukey_fence(vals)
    print(f"  {k[0]:<4} {k[1]:<16} fence=[{lo:.3f},{hi:.3f}] flagged={flagged if flagged else 'none'}")

print("\n=== C3/Stencil-24K bimodal check (does the 5-high/10-low split from OUTLIER_FORENSICS.md reproduce?) ===")
c3_stencil = sorted(data[("C3", "bench_stencil")], key=lambda x: x[2])
for rep, wall, order in c3_stencil:
    print(f"    run_order={order} rep={rep} wall={wall:.2f}s")
vals = [v[1] for v in c3_stencil]
print(f"  n={len(vals)} median={st.median(vals):.3f} min={min(vals):.3f} max={max(vals):.3f}")

FAMILY = [
    ("Stencil-24K", "bench_stencil", "C3", "C1", "primary"),
    ("GraphBFS-23", "bench_graph_bfs", "C3", "C1", "primary"),
    ("Stencil-24K", "bench_stencil", "C3", "C0", "secondary"),
    ("GraphBFS-23", "bench_graph_bfs", "C3", "C0", "secondary"),
    ("Stencil-24K", "bench_stencil", "C2", "C1", "secondary"),
    ("GraphBFS-23", "bench_graph_bfs", "C2", "C1", "secondary"),
]

results = []
for label, bench, cfg_a, cfg_b, kind in FAMILY:
    a = [v[1] for v in data[(cfg_a, bench)]]
    b = [v[1] for v in data[(cfg_b, bench)]]
    u_stat, p_mwu = stats.mannwhitneyu(a, b, alternative="two-sided")
    t_stat, p_welch = stats.ttest_ind(a, b, equal_var=False)
    med_a, med_b = st.median(a), st.median(b)
    pct = 100 * (med_a - med_b) / med_b
    pooled_sd = ((st.stdev(a)**2 + st.stdev(b)**2) / 2) ** 0.5
    cohens_d = (st.mean(a) - st.mean(b)) / pooled_sd if pooled_sd else float("nan")
    results.append(dict(label=label, bench=bench, cfg_a=cfg_a, cfg_b=cfg_b, kind=kind,
                         med_a=med_a, med_b=med_b, pct=pct, p_mwu=p_mwu, p_welch=p_welch,
                         d=cohens_d, n_a=len(a), n_b=len(b)))

print("\n=== Six pre-registered comparisons (family size=6, Holm-Bonferroni) ===")
sorted_r = sorted(results, key=lambda r: r["p_mwu"])
m = len(sorted_r)
holm_reject = [False]*m
still_rejecting = True
for i, r in enumerate(sorted_r):
    threshold = 0.05 / (m - i)
    r["holm_threshold"] = threshold
    if still_rejecting and r["p_mwu"] <= threshold:
        holm_reject[i] = True
    else:
        still_rejecting = False
    r["holm_significant"] = holm_reject[i]

print(f"{'Comparison':<28} {'kind':<10} {'med_A':>9} {'med_B':>9} {'delta%':>8} {'p_MWU':>10} {'holm_thr':>9} {'Holm sig':>9}")
for r in sorted_r:
    comp = f"{r['cfg_a']}vs{r['cfg_b']} {r['label']}"
    print(f"{comp:<28} {r['kind']:<10} {r['med_a']:>9.4f} {r['med_b']:>9.4f} {r['pct']:>7.2f}% {r['p_mwu']:>10.4g} {r['holm_threshold']:>9.4g} {str(r['holm_significant']):>9}")

print("\n=== Primary comparisons (C3 vs C1) detail, with MDE ===")
for r in results:
    if r["kind"] != "primary":
        continue
    a = [v[1] for v in data[(r["cfg_a"], r["bench"])]]
    b = [v[1] for v in data[(r["cfg_b"], r["bench"])]]
    pooled_sd = ((st.stdev(a)**2 + st.stdev(b)**2) / 2) ** 0.5
    n = min(len(a), len(b))
    # MDE at 80% power, alpha=0.05 two-sided, using standard two-sample formula
    from scipy.stats import norm
    z_alpha = norm.ppf(1 - 0.05/2)
    z_beta = norm.ppf(0.80)
    mde_abs = (z_alpha + z_beta) * pooled_sd * (2/n) ** 0.5
    mde_pct = 100 * mde_abs / r["med_b"]
    print(f"  {r['label']}: C3 median={r['med_a']:.4f}s C1 median={r['med_b']:.4f}s delta={r['pct']:+.2f}%")
    print(f"    MWU p={r['p_mwu']:.4g} (Holm sig={r['holm_significant']}), Welch p={r['p_welch']:.4g}, Cohen's d={r['d']:.3f}")
    print(f"    MDE (80% power, alpha=0.05, n={n}/arm, pooled_sd={pooled_sd:.4f}s): {mde_abs:.4f}s = {mde_pct:.2f}% of C1 median")
