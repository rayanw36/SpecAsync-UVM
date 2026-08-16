#!/usr/bin/env python3
"""Gate B10 analysis: C4 vs C0 at iters in {1,5,20}.

Statistic of record: median. Test of record: Mann-Whitney U, two-sided.
Correction: Holm-Bonferroni across the 3 pre-registered comparisons
(GATE_B10_PREREGISTRATION.md Section 6). Kept reps only (phase == 'kept').
"""
import csv
import sys
from collections import defaultdict

import numpy as np
from scipy import stats

CSV_PATH = "t_b10_c0_vs_c4_times.csv"

rows = defaultdict(list)  # (config, iters) -> list of dict
atomics_rows = defaultdict(list)

with open(CSV_PATH) as f:
    r = csv.DictReader(f)
    for row in r:
        if row["phase"] != "kept":
            continue
        cfg = row["config"]
        iters = int(row["iters"])
        wall = float(row["wall_s"])
        rows[(cfg, iters)].append(wall)
        atomics_rows[(cfg, iters)].append({
            k: (int(row[k]) if row[k] not in ("", None) else None)
            for k in ("atomic_processed", "atomic_enqueued", "atomic_drops",
                       "atomic_demand_faults", "atomic_spec_hits", "atomic_spec_migrations")
        })

iters_list = [1, 5, 20]
results = []
pvals = []

for it in iters_list:
    c0 = np.array(rows[("C0", it)])
    c4 = np.array(rows[("C4", it)])
    assert len(c0) == 10 and len(c4) == 10, f"iters={it}: n_c0={len(c0)} n_c4={len(c4)}"
    med_c0 = np.median(c0)
    med_c4 = np.median(c4)
    pct = (med_c4 - med_c0) / med_c0 * 100.0  # positive = C4 slower
    u, p = stats.mannwhitneyu(c4, c0, alternative="two-sided")
    pooled_sd = np.sqrt(((len(c0)-1)*c0.std(ddof=1)**2 + (len(c4)-1)*c4.std(ddof=1)**2) / (len(c0)+len(c4)-2))
    d = (c4.mean() - c0.mean()) / pooled_sd if pooled_sd > 0 else float('nan')
    results.append(dict(iters=it, n=10, med_c0=med_c0, med_c4=med_c4, pct_c4_vs_c0=pct,
                         mwu_p=p, cohens_d=d))
    pvals.append(p)

# Holm-Bonferroni step-down across the 3 pre-registered comparisons
order = np.argsort(pvals)
m = len(pvals)
holm_reject = [False] * m
holm_thresh = [None] * m
running_reject = True
alpha = 0.05
for rank, idx in enumerate(order):
    thresh = alpha / (m - rank)
    holm_thresh[idx] = thresh
    if running_reject and pvals[idx] < thresh:
        holm_reject[idx] = True
    else:
        running_reject = False  # once one fails, all subsequent (larger p) are non-significant

print("=== Gate B10: C4 vs C0, kept reps only, n=10/arm/iters ===")
print(f"{'iters':>5} {'med_C0':>8} {'med_C4':>8} {'pct_C4_vs_C0':>13} {'mwu_p':>10} {'holm_thr':>10} {'sig':>4} {'cohens_d':>9}")
for i, res in enumerate(results):
    sig = "YES" if holm_reject[i] else "no"
    print(f"{res['iters']:>5} {res['med_c0']:>8.3f} {res['med_c4']:>8.3f} {res['pct_c4_vs_c0']:>12.2f}% {res['mwu_p']:>10.6f} {holm_thresh[i]:>10.6f} {sig:>4} {res['cohens_d']:>9.3f}")

# write aggregate CSV
with open("t_b10_aggregate_comparison.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["iters", "n_per_arm", "c0_median_s", "c4_median_s", "pct_c4_vs_c0",
                "mwu_p", "holm_threshold", "holm_significant", "cohens_d", "mde_pct_preregistered"])
    mde_map = {1: 3.9, 5: 5.6, 20: 0.13}
    for i, res in enumerate(results):
        w.writerow([res["iters"], res["n"], f"{res['med_c0']:.4f}", f"{res['med_c4']:.4f}",
                    f"{res['pct_c4_vs_c0']:.4f}", f"{res['mwu_p']:.8f}", f"{holm_thresh[i]:.8f}",
                    "YES" if holm_reject[i] else "no", f"{res['cohens_d']:.4f}", mde_map[res["iters"]]])

# atomics summary (median per cell)
print()
print("=== Atomic counters (median across 10 kept reps) ===")
print(f"{'cfg':>3} {'iters':>5} {'processed':>10} {'enqueued':>10} {'drops':>10} {'demand_faults':>14} {'spec_hits':>10} {'spec_migrations':>16} {'hit_rate_%':>10}")
atomics_out = []
for cfg in ("C0", "C4"):
    for it in iters_list:
        recs = atomics_rows[(cfg, it)]
        med = {}
        for k in ("atomic_processed", "atomic_enqueued", "atomic_drops",
                   "atomic_demand_faults", "atomic_spec_hits", "atomic_spec_migrations"):
            vals = [r[k] for r in recs if r[k] is not None]
            med[k] = np.median(vals) if vals else None
        enq = med["atomic_enqueued"] or 0
        hits = med["atomic_spec_hits"] or 0
        hit_rate = (hits / enq * 100.0) if enq else 0.0
        print(f"{cfg:>3} {it:>5} {med['atomic_processed']:>10.0f} {med['atomic_enqueued']:>10.0f} {med['atomic_drops']:>10.0f} {med['atomic_demand_faults']:>14.0f} {med['atomic_spec_hits']:>10.0f} {med['atomic_spec_migrations']:>16.0f} {hit_rate:>10.4f}")
        atomics_out.append((cfg, it, med, hit_rate))

with open("t_b10_atomics_summary.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["config", "iters", "median_processed", "median_enqueued", "median_drops",
                "median_demand_faults", "median_spec_hits", "median_spec_migrations", "spec_hit_rate_pct"])
    for cfg, it, med, hit_rate in atomics_out:
        w.writerow([cfg, it, med["atomic_processed"], med["atomic_enqueued"], med["atomic_drops"],
                    med["atomic_demand_faults"], med["atomic_spec_hits"], med["atomic_spec_migrations"],
                    f"{hit_rate:.6f}"])
