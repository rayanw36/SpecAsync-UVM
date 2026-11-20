#!/usr/bin/env python3
"""C22 M3: servicing window and D5 as fractions of process wall-clock, Stencil-24K and GraphBFS-23, C0 and C7-W512 (prefetcher on, threshold 51), from E4 (the only gate with C0 phase data:
E1 Part B has C1 and C6-L4096 only). Per run: window = sum over decomp records of (d6_end or svc_end) - d1_start; D5 = sum of the D5 field; wall = e4_runs.csv wall_s. Only runs whose rings did not
overflow (records < CAP) are used. Phase definitions as tests/e1_partb_phases.py (driver/src/specasync_telemetry.h:107-141)."""
import csv, statistics as st, struct
RAW = "results/phaseB1/gate_e4/sweep"; FMT = "<12Q4I"; CAP = 131071
runs = list(csv.DictReader(open("results/analysis/gate_e/e4/e4_runs.csv")))
res = {}
for r in runs:
    wl, arm = r["label"].split(" ", 1)
    if arm not in ("C0", "C7-W512", "C1", "C6-W512"): continue
    data = open(f"{RAW}/e3b_{r['idx']}_decomp.bin", "rb").read()
    n = len(data) // struct.calcsize(FMT); win = d5 = d3 = d4 = 0
    for (bid, d1s, d1e, d2s, d2e, ss, se, d6s, d6e, p3, p4, p5, nf, nvs, nb, _p) in struct.iter_unpack(FMT, data):
        win += (d6e if d6e else se) - d1s; d5 += p5; d3 += p3; d4 += p4
    res.setdefault((wl, arm), []).append(dict(idx=r["idx"], wall=float(r["wall_s"]), win=win / 1e9, d5=d5 / 1e9, d4=d4 / 1e9, d3=d3 / 1e9, ok=n < CAP, n=n))
o = ["# C22 M3: fault-dispatch share of process wall-clock (E4, prefetcher on, threshold 51)", "",
     "Script `tests/c22_m3_dispatch_share.py`. **Source: E4** (`results/phaseB1/gate_e4/sweep/e3b_<idx>_decomp.bin`, the per-batch decomposition rings, with `gate_e/e4/e4_runs.csv` wall-clock; E1 Part B has no C0 arm). Window = per-batch (replay-push end, or service end) minus drain start, summed over batches; D5 = dispatch inside the lock hold. Ratio of medians over the runs whose rings did not overflow.", "",
     "| workload | arm | runs used / 10 | median wall (s) | median window (s) | window / wall | median D5 (s) | D5 / wall | D5 / window | evidence |", "|---|---|---|---|---|---|---|---|---|---|"]
for wl, nm in (("stencil", "Stencil-24K"), ("graphbfs", "GraphBFS-23")):
    for arm in ("C0", "C7-W512"):
        v = [x for x in res[(wl, arm)] if x["ok"]]
        w, win, d5 = (st.median(x[k] for x in v) for k in ("wall", "win", "d5"))
        o.append(f"| {nm} | {arm} | {len(v)} / {len(res[(wl, arm)])} | {w:.3f} | {win:.4f} | {100*win/w:.2f}% | {d5:.4f} | {100*d5/w:.2f}% | {100*d5/win:.1f}% | `E4.mech.{wl}.{arm}` (d5), `C22.M3.{wl}.{arm}` |")
o += ["", "Prefetcher off (E4 C1 and C6-W512), for reference in the same units:", "", "| workload | arm | window / wall | D5 / wall |", "|---|---|---|---|"]
for wl, nm in (("stencil", "Stencil-24K"), ("graphbfs", "GraphBFS-23")):
    for arm in ("C1", "C6-W512"):
        v = [x for x in res[(wl, arm)] if x["ok"]]
        w, win, d5 = (st.median(x[k] for x in v) for k in ("wall", "win", "d5"))
        o.append(f"| {nm} | {arm} | {100*win/w:.2f}% | {100*d5/w:.2f}% |")
o += ["", "Notes: wall-clock is process wall, so the dispatch window is a minority of it with the prefetcher on; per-run values are in the script's data (`e3b_*_decomp.bin`).", ""]
open("results/analysis/consolidation/C22_M3_DISPATCH_SHARE.md", "w").write("\n".join(o))
print("\n".join(o[5:11]))
