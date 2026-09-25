#!/usr/bin/env python3
"""Gate E0.9b Step 2: servicing-time ceiling from the decomp ring.

Per run: total servicing window = sum over decomp records of
((d6_end if d6_end else svc_end) - d1_start). Coverage is 100% iff the
record count is < 131,071 (drop-on-full ring, 131,072 slots).
Ceiling per workload = median(C1 window) - median(C6-L4096 window);
per pre-staged fault = ceiling / median(C6 fault_already_resident).
Does not read or compare wall-clock."""
import csv, statistics, struct, sys
RAW, CSVIN, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
FMT = "<12Q4I"; SZ = struct.calcsize(FMT); CAP = 131071
rows = list(csv.DictReader(open(CSVIN)))
per = []
for r in rows:
    path = f"{RAW}/pilot_{r['idx']}_{r['workload']}_{r['arm']}{r['L']}_decomp.bin"
    data = open(path, "rb").read()
    n = len(data) // SZ
    tot = 0; blocks = 0; faults = 0; bad = 0; used_d6 = 0
    for rec in struct.iter_unpack(FMT, data[:n * SZ]):
        (bid, d1s, d1e, d2s, d2e, ss, se, d6s, d6e, d3, d4, d5, nf, nvs, nb, _p) = rec
        end = d6e if d6e else se
        used_d6 += bool(d6e)
        if d1s == 0 or end < d1s:
            bad += 1; continue
        tot += end - d1s; blocks += nb; faults += nf
    per.append(dict(idx=r["idx"], workload=r["workload"], arm=r["arm"], L=r["L"], records=n,
                    full_coverage=int(n < CAP), bad_records=bad, records_with_d6=used_d6,
                    window_ns=tot, dispatch_groups=blocks, rec_faults=faults,
                    fault_already_resident=r["fault_already_resident"]))
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(per[0])); w.writeheader(); w.writerows(per)
for p in per: print(p)
for wl in ("stencil", "graphbfs"):
    c1 = [p for p in per if p["workload"] == wl and p["arm"] == "C1"]
    c6 = [p for p in per if p["workload"] == wl and p["arm"] == "C6"]
    if not all(p["full_coverage"] for p in c1 + c6):
        print(wl, "NO CEILING: ring saturated"); continue
    m1 = statistics.median(p["window_ns"] for p in c1); m6 = statistics.median(p["window_ns"] for p in c6)
    far = statistics.median(int(p["fault_already_resident"]) for p in c6)
    d = m1 - m6
    print(f"{wl}: median C1 window {m1/1e9:.4f} s; median C6-L4096 window {m6/1e9:.4f} s; "
          f"difference {d/1e9:+.4f} s; median C6 fault_already_resident {far}; per pre-staged fault {d/far if far else float('nan'):.1f} ns")
