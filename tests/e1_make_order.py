#!/usr/bin/env python3
"""Gate E1: sweep run order. 10 cells (2 workloads x {C0, C7-L1, C7-L16,
C7-L256, C7-L4096}) x n=10 = 100 runs, as 10 blocks; each block is one
random.Random(SEED) permutation of all 10 cells."""
import csv, random, sys
SEED = 202609261
cells = [(wl, a, L) for wl in ("stencil", "graphbfs")
         for (a, L) in [("C0", ""), ("C7", "1"), ("C7", "16"), ("C7", "256"), ("C7", "4096")]]
rng = random.Random(SEED)
rows = []
for _ in range(10):
    blk = cells[:]; rng.shuffle(blk); rows += blk
with open(sys.argv[1], "w", newline="") as f:
    w = csv.writer(f); w.writerow(["idx", "workload", "arm", "L"])
    for i, (wl, a, L) in enumerate(rows, 1): w.writerow([i, wl, a, L])
