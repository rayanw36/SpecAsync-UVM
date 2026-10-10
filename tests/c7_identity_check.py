#!/usr/bin/env python3
"""Gate C7 step 2: check accounting identities I1, I2 on every policy-6 row of the E4-E7 run CSVs (read-only).
  I1: demand_faults = ft_predictions + ft_held + ft_unknown_page + ft_exhausted + ft_fast_cas_giveup
  I2: ft_predictions = ft_same_region + enqueued + drops
Writes results/analysis/consolidation/identity_check.csv (one row per CSV) and prints per-CSV counts and every nonzero difference."""
import csv
G = "results/analysis/gate_e"
FILES = [f"{G}/e4/e4_runs.csv", f"{G}/e5/e5_runs.csv", f"{G}/e6/e6_runs.csv", f"{G}/e7/e7_runs.csv"]
g = lambda r, k: int(r[k]) if r.get(k, "") not in ("", None) else None
out = []
for p in FILES:
    rows = [r for r in csv.DictReader(open(p)) if r["policy"] == "6" and r["module"] == "new"]
    n = len(rows); bad1 = bad2 = missing = 0; detail = []
    for r in rows:
        v = {k: g(r, k) for k in ("demand_faults", "ft_predictions", "ft_held", "ft_unknown_page", "ft_exhausted", "ft_fast_cas_giveup", "ft_same_region", "enqueued", "drops")}
        if any(x is None for x in v.values()): missing += 1; detail.append((r["idx"], "missing counter")); continue
        d1 = v["demand_faults"] - (v["ft_predictions"] + v["ft_held"] + v["ft_unknown_page"] + v["ft_exhausted"] + v["ft_fast_cas_giveup"])
        d2 = v["ft_predictions"] - (v["ft_same_region"] + v["enqueued"] + v["drops"])
        bad1 += d1 != 0; bad2 += d2 != 0
        if d1 or d2: detail.append((r["idx"], r["label"], d1, d2))
    out.append(dict(csv=p, policy6_rows=n, I1_nonzero=bad1, I2_nonzero=bad2, rows_missing_counters=missing))
    print(p, "policy-6 rows", n, "| I1 nonzero", bad1, "| I2 nonzero", bad2, "| missing", missing, detail[:5])
with open("results/analysis/consolidation/identity_check.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
