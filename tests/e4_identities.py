#!/usr/bin/env python3
"""Gate E4: identities per policy-6 run (trace_faults=0, so Identity 1's
left side is demand_faults; see E4_STATUS Step 0 for its E3b validation).
  I1: demand_faults = ft_predictions + ft_held + ft_unknown_page + ft_exhausted + ft_fast_cas_giveup
  I2: ft_predictions = ft_same_region + enqueued + drops
Plus spec_pages_requested / spec_migrations vs W. Wall-clock not read."""
import csv, sys
g = lambda r, k: int(r[k]) if r.get(k, "") not in ("", None) else 0
print("| run | W | I1 left (demand_faults) | I1 right | I1 diff | I2 left | I2 right | I2 diff | pages/migration | spec_region_invalid | cas_giveup | verified | nranges | fault_already_resident |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
bad = 0
for r in csv.DictReader(open(sys.argv[1])):
    if r["policy"] != "6":
        continue
    l1 = g(r, "demand_faults"); r1 = sum(g(r, k) for k in ("ft_predictions", "ft_held", "ft_unknown_page", "ft_exhausted", "ft_fast_cas_giveup"))
    l2 = g(r, "ft_predictions"); r2 = sum(g(r, k) for k in ("ft_same_region", "enqueued", "drops"))
    mig = g(r, "spec_migrations"); ppm = g(r, "spec_pages_requested") / mig if mig else float("nan")
    bad += (l1 != r1) + (l2 != r2)
    print(f"| {r['label']} | {r['W']} | {l1} | {r1} | {l1-r1} | {l2} | {r2} | {l2-r2} | {ppm:.2f} | {r['spec_region_invalid']} | "
          f"{r['ft_fast_cas_giveup']} | {r['ft_fast_verified']} | {r['ft_fast_nranges']} | {r['fault_already_resident']} |")
print(f"\nnonzero identity differences: {bad}")
