#!/usr/bin/env python3
"""Gate E0.9b: generate the sweep run order. 12 cells (2 workloads x
{C0, C1, C6-L1, C6-L16, C6-L256, C6-L4096}) x n=10 = 120 runs, as 10
blocks; each block is one random.Random(SEED) permutation of all 12 cells,
so every arm, L and workload is interleaved throughout the session."""
import csv, random, sys
SEED = 20260925
cells = [(wl, a, L) for wl in ("stencil", "graphbfs")
         for (a, L) in [("C0", ""), ("C1", ""), ("C6", "1"), ("C6", "16"), ("C6", "256"), ("C6", "4096")]]
rng = random.Random(SEED)
rows = []
for _ in range(10):
    blk = cells[:]; rng.shuffle(blk); rows += blk
with open(sys.argv[1], "w", newline="") as f:
    w = csv.writer(f); w.writerow(["idx", "workload", "arm", "L"])
    for i, (wl, a, L) in enumerate(rows, 1): w.writerow([i, wl, a, L])
