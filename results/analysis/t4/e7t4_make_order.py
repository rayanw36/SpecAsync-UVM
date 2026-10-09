#!/usr/bin/env python3
"""E7-T4 order (E7T4_PREREGISTRATION.md). Seed 202610072. Structure of tests/e7_make_order.py minus Family C.

  Family A  idx   1- 30  Stencil-24K, stock-t0 / stock-t10 / stock-t51, 10 seeded triples
  Family B  idx  31-270  8 workloads x 30 runs (10 seeded triples of stock-t0 / stock-t25 / stock-t51),
                         workload order: stencil8k sweep4k sweep16k stream sgemm cufft graphbfs oversub
Smoke rows (one per never-run cell: 3 Family A + 24 Family B) go to a separate file.
usage: e7t4_make_order.py ORDER_CSV SMOKE_CSV
"""
import csv
import random
import sys

SEED = 202610072
H = ["idx", "label", "workload", "module", "policy", "depth", "prefetch", "L", "W", "fast", "trace_faults",
     "dump_rings", "threshold", "family", "block"]
STOCK = {f"stock-t{t}": ("stock", "", "", "1", "", "", "", str(t)) for t in (0, 10, 25, 51)}
FAM_A = ["stock-t0", "stock-t10", "stock-t51"]
FAM_B_CELLS = ["stock-t0", "stock-t25", "stock-t51"]
FAM_B_WL = ["stencil8k", "sweep4k", "sweep16k", "stream", "sgemm", "cufft", "graphbfs", "oversub"]


def row(i, wl, cell, fam):
    mod, pol, dep, pf, L, W, fast, thr = STOCK[cell]
    return [i, f"{wl} {cell}", wl, mod, pol, dep, pf, L, W, fast, "0", "0", thr, fam, ""]


def main(order_path, smoke_path):
    rng = random.Random(SEED)
    plan = []

    def blocks(wl, cells, fam, n=10):
        for _ in range(n):
            b = cells[:]
            rng.shuffle(b)
            plan.extend((wl, c, fam) for c in b)

    blocks("stencil", FAM_A, "A")
    for wl in FAM_B_WL:
        blocks(wl, FAM_B_CELLS, "B")
    assert len(plan) == 30 + 8 * 30 == 270
    for path, items in ((order_path, plan),
                        (smoke_path, [("stencil", c, "A") for c in FAM_A]
                         + [(wl, c, "B") for wl in FAM_B_WL for c in FAM_B_CELLS])):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(H)
            for i, (wl, c, fam) in enumerate(items, 1):
                w.writerow(row(i, wl, c, fam))
    print(f"{len(plan)} order rows, 27 smoke rows (seed {SEED})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
