#!/usr/bin/env python3
"""Gate H1 order (H1_PREREGISTRATION.md). Seed 202611051.
  idx  1-60   in-memory cells (Stencil-24K, sparse 8 GiB K = 1 and 512; thresholds 0 and 51): 6 cells, 10 seeded permutation blocks
  idx 61-100  oversubscribed cells (sparse 24 GiB K = 1 and 512; thresholds 0 and 51): 4 cells, 10 seeded permutation blocks
Smoke rows: one per cell (10 rows) in a separate file. usage: h1_make_order.py ORDER_CSV SMOKE_CSV"""
import csv, random, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import h1_cells as C  # noqa: E402
SEED = 202611051
H = ["idx", "label", "workload", "module", "policy", "depth", "prefetch", "L", "W", "fast", "trace_faults", "dump_rings", "threshold", "family", "block"]


def row(i, wl, t, fam, blk):
    return [i, f"{wl} stock-t{t}", wl, "stock", "", "", "1", "", "", "", "0", "0", t, fam, blk]


def main(order_path, smoke_path):
    rng = random.Random(SEED)
    plan = []
    for keys, fam in ((C.IN_KEYS, "IN"), (C.OV_KEYS, "OV")):
        cells = [(k, t) for k in keys for t in C.THR]
        for b in range(10):
            p = cells[:]
            rng.shuffle(p)
            plan += [(k, t, fam, str(b + 1)) for k, t in p]
    assert len(plan) == 100
    for path, rows in ((order_path, plan), (smoke_path, [(k, t, "IN" if k in C.IN_KEYS else "OV", "") for k in C.IN_KEYS + C.OV_KEYS for t in C.THR])):
        with open(path, "w", newline="") as f:
            w = csv.writer(f); w.writerow(H)
            for i, (k, t, fam, blk) in enumerate(rows, 1):
                w.writerow(row(i, k, t, fam, blk))
    print(f"{len(plan)} order rows, 10 smoke rows (seed {SEED})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
