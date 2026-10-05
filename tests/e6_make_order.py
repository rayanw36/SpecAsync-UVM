#!/usr/bin/env python3
"""Gate E6 order. Family 1 (Stencil-24K): 10 blocks, each a random.Random(SEED)
permutation of the 8 cells -> 80 runs (idx 1-80). Family 2 (GraphBFS-23): 10 blocks of its
3 cells -> 30 runs (idx 81-110), run after Family 1. Smoke rows (one per never-run cell)
go to a separate file. Every run uses the new module; trace_faults=0; rings dumped."""
import csv, random, sys
SEED = 202610051
THR = {"0": "0", "10": "10", "25": "25", "51": "51"}
F1 = [(f"C0-t{t}", "0", "0", "1", "", "1", "0", t) for t in ("0", "10", "25", "51")] + \
     [(f"C7W512-t{t}", "6", "1", "1", "4096", "512", "1", t) for t in ("0", "10", "25", "51")]
F2 = [(f"C0-t{t}", "0", "0", "1", "", "1", "0", t) for t in ("0", "25", "51")]
H = ["idx", "label", "workload", "module", "policy", "depth", "prefetch", "L", "W", "fast",
     "trace_faults", "dump_rings", "threshold", "family"]

def write(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(H)
        for i, (wl, fam, c) in enumerate(rows, 1):
            name, pol, dep, pf, L, W, fast, t = c
            w.writerow([i, f"{wl} {name}", wl, "new", pol, dep, pf, L, W, fast, "0", "1", t, fam])

rng = random.Random(SEED)
rows1 = []
for _ in range(10):
    b = F1[:]; rng.shuffle(b); rows1 += [("stencil", 1, c) for c in b]
rows2 = []
for _ in range(10):
    b = F2[:]; rng.shuffle(b); rows2 += [("graphbfs", 2, c) for c in b]
write(sys.argv[1], rows1 + rows2)
smoke = [("stencil", 1, c) for c in F1 if c[0] in ("C0-t0", "C0-t10", "C0-t25", "C7W512-t0", "C7W512-t10", "C7W512-t25")] + \
        [("graphbfs", 2, c) for c in F2 if c[0] in ("C0-t0", "C0-t25")]
write(sys.argv[2], smoke)
