#!/usr/bin/env python3
"""Gate E4: sweep order. 20 cells (2 workloads x 10 arms) x n=10 = 200 runs,
as 10 blocks; each block is one random.Random(SEED) permutation of all 20
cells. Every run uses the new module; trace_faults=0; rings dumped."""
import csv, random, sys
SEED = 202609264
ARMS = [  # name, policy, depth, prefetch, W, fast
    ("C0", "0", "0", "1", "1", "0"), ("C7-slow-W1", "6", "1", "1", "1", "0"), ("C7-W1", "6", "1", "1", "1", "1"),
    ("C7-W64", "6", "1", "1", "64", "1"), ("C7-W512", "6", "1", "1", "512", "1"),
    ("C1", "0", "0", "0", "1", "0"), ("C6-slow-W1", "6", "1", "0", "1", "0"), ("C6-W1", "6", "1", "0", "1", "1"),
    ("C6-W64", "6", "1", "0", "64", "1"), ("C6-W512", "6", "1", "0", "512", "1")]
cells = [(wl, a) for wl in ("stencil", "graphbfs") for a in ARMS]
rng = random.Random(SEED)
rows = []
for _ in range(10):
    b = cells[:]; rng.shuffle(b); rows += b
with open(sys.argv[1], "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["idx", "label", "workload", "module", "policy", "depth", "prefetch", "L", "W", "fast", "trace_faults", "dump_rings"])
    for i, (wl, (name, pol, dep, pf, W, fast)) in enumerate(rows, 1):
        w.writerow([i, f"{wl} {name}", wl, "new", pol, dep, pf, "4096" if pol == "6" else "", W, fast, "0", "1"])
