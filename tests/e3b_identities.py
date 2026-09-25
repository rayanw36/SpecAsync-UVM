#!/usr/bin/env python3
"""Gate E3b: per-run counter table and the two prediction-side identities.
  I1: trace_pushes (coalesced faults on the policy-6 path)
        = ft_predictions + ft_held + ft_unknown_page + ft_exhausted + ft_fast_cas_giveup
  I2: ft_predictions = ft_same_region + enqueued + drops
(verified-module rows have no ft_same_region / ft_fast_cas_giveup counters:
 treated as 0, since that module cannot skip or give up). Wall-clock not read."""
import csv, sys
def i(r, k):
    v = r.get(k, "")
    return int(v) if v not in ("", None) else 0
rows = list(csv.DictReader(open(sys.argv[1])))
cols = ["label", "W", "fast", "ft_fast_verified", "ft_fast_nranges", "ft_fast_verify_ns", "demand_faults",
        "trace_pushes", "ft_predictions", "ft_held", "ft_unknown_page", "ft_exhausted", "ft_skipped",
        "ft_same_region", "enqueued", "drops", "processed", "spec_migrations", "spec_pages_requested",
        "spec_region_invalid", "ft_fast_cas_giveup", "fault_already_resident", "dmesg_new_lines"]
print("| " + " | ".join(cols) + " |"); print("|" + "---|" * len(cols))
for r in rows:
    print("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
print()
print("| run | I1 left: trace_pushes | I1 right: pred+held+unk+exh+giveup | I1 diff | I2 left: ft_predictions | I2 right: same_region+enqueued+drops | I2 diff |")
print("|---|---|---|---|---|---|---|")
for r in rows:
    if r["policy"] != "6":
        continue
    l1 = i(r, "trace_pushes"); r1 = sum(i(r, k) for k in ("ft_predictions", "ft_held", "ft_unknown_page", "ft_exhausted", "ft_fast_cas_giveup"))
    l2 = i(r, "ft_predictions"); r2 = sum(i(r, k) for k in ("ft_same_region", "enqueued", "drops"))
    print(f"| {r['label']} | {l1} | {r1} | {l1 - r1} | {l2} | {r2} | {l2 - r2} |")
