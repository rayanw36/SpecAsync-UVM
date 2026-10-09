#!/usr/bin/env python3
"""Gate E9 order (E9_PREREGISTRATION.md). Seed 202610091.
14 cells, stock module, n = 3 per cell, 42 runs: 3 blocks, each a seeded permutation of the 14 cells.
  bench_sparse oversubscribed (24 GiB): K in {1, 8, 64, 512} x threshold in {0, 51}   (8 cells)
  bench_sparse in-memory (8 GiB):       K in {1, 512}        x threshold in {0, 51}   (4 cells)
  Stencil-24K:                                                threshold in {0, 51}    (2 cells)
Smoke rows (one per cell, same 14 cells in a fixed order) go to a separate file.
usage: e9_make_order.py ORDER_CSV SMOKE_CSV"""
import csv
import random
import sys

SEED = 202610091
H = ["idx", "label", "workload", "module", "policy", "depth", "prefetch", "L", "W", "fast", "trace_faults",
     "dump_rings", "threshold", "family", "block"]
CELLS = [(f"ov_k{k}", t) for k in (1, 8, 64, 512) for t in (0, 51)] + [(f"in_k{k}", t) for k in (1, 512) for t in (0, 51)] + \
        [("stencil", t) for t in (0, 51)]


def row(i, wl, t, blk):
    return [i, f"{wl} stock-t{t}", wl, "stock", "", "", "1", "", "", "", "0", "0", t, "E9", blk]


def main(order_path, smoke_path):
    rng = random.Random(SEED)
    plan = []
    for b in range(3):
        p = CELLS[:]
        rng.shuffle(p)
        plan += [(wl, t, str(b + 1)) for wl, t in p]
    assert len(plan) == 42
    for path, rows in ((order_path, plan), (smoke_path, [(wl, t, "") for wl, t in CELLS])):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(H)
            for i, (wl, t, blk) in enumerate(rows, 1):
                w.writerow(row(i, wl, t, blk))
    print(f"{len(plan)} order rows, {len(CELLS)} smoke rows (seed {SEED})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
