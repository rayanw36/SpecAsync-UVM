#!/usr/bin/env python3
"""Gate E5: 6 cells (Stencil-24K; C0 / C7W512 x threshold 51 / 75 / 100) x
n=10 = 60 runs, as 10 blocks; each block is one random.Random(SEED)
permutation of all 6 cells. New module everywhere; trace_faults=0; rings dumped."""
import csv, random, sys
SEED = 202609265
T_OFF = "100"
cells = []
for t, tn in (("51", "t51"), ("75", "t75"), (T_OFF, "toff")):
    cells.append((f"C0-{tn}", "0", "0", "1", "", "1", "0", t))
    cells.append((f"C7W512-{tn}", "6", "1", "1", "4096", "512", "1", t))
rng = random.Random(SEED)
rows = []
for _ in range(10):
    b = cells[:]; rng.shuffle(b); rows += b
with open(sys.argv[1], "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["idx", "label", "workload", "module", "policy", "depth", "prefetch", "L", "W", "fast",
                "trace_faults", "dump_rings", "threshold"])
    for i, (name, pol, dep, pf, L, W, fast, t) in enumerate(rows, 1):
        w.writerow([i, f"stencil {name}", "stencil", "new", pol, dep, pf, L, W, fast, "0", "1", t])
