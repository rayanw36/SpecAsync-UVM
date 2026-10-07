#!/usr/bin/env python3
"""Gate E7 order (E7_PREREGISTRATION.md). Seed 202610071.

Run order, one row per run, idx 1-310:
  Family C block 1   idx   1- 20  spec-C0-t51 / spec-C7W512-t51 (E3a-2 module), 10 seeded pairs
  Family A           idx  21- 50  Stencil-24K, stock module, stock-t0 / stock-t10 / stock-t51, 10 seeded triples
  Family B           idx  51-290  8 workloads x 30 runs (10 seeded triples of stock-t0 / stock-t25 / stock-t51),
                                  in the pre-registered workload order
  Family C block 2   idx 291-310  as block 1
Smoke rows (one per never-run cell: the 3 Family A cells and the 24 Family B cells) go to a separate file.

usage: e7_make_order.py ORDER_CSV SMOKE_CSV
"""
import csv
import random
import sys

SEED = 202610071
H = ["idx", "label", "workload", "module", "policy", "depth", "prefetch", "L", "W", "fast", "trace_faults",
     "dump_rings", "threshold", "family", "block"]
# cell -> (module, policy, depth, prefetch, L, W, fast, threshold)
STOCK = {f"stock-t{t}": ("stock", "", "", "1", "", "", "", str(t)) for t in (0, 10, 25, 51)}
SPEC = {"spec-C0-t51": ("new", "0", "0", "1", "", "1", "0", "51"),
        "spec-C7W512-t51": ("new", "6", "1", "1", "4096", "512", "1", "51")}
FAM_A = ["stock-t0", "stock-t10", "stock-t51"]
FAM_B_CELLS = ["stock-t0", "stock-t25", "stock-t51"]
FAM_B_WL = ["stencil8k", "sweep4k", "sweep16k", "stream", "sgemm", "cufft", "graphbfs", "oversub"]
FAM_C = ["spec-C0-t51", "spec-C7W512-t51"]


def row(i, wl, cell, fam, block):
    mod, pol, dep, pf, L, W, fast, thr = (STOCK.get(cell) or SPEC[cell])
    return [i, f"{wl} {cell}", wl, mod, pol, dep, pf, L, W, fast, "0", "0", thr, fam, block]


def main(order_path, smoke_path):
    rng = random.Random(SEED)
    plan = []                                   # (workload, cell, family, block)

    def blocks(wl, cells, fam, block, n=10):
        for _ in range(n):
            b = cells[:]
            rng.shuffle(b)
            plan.extend((wl, c, fam, block) for c in b)

    blocks("stencil", FAM_C, "C", "1")
    blocks("stencil", FAM_A, "A", "")
    for wl in FAM_B_WL:
        blocks(wl, FAM_B_CELLS, "B", "")
    blocks("stencil", FAM_C, "C", "2")
    assert len(plan) == 20 + 30 + 8 * 30 + 20 == 310
    with open(order_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(H)
        for i, (wl, c, fam, blk) in enumerate(plan, 1):
            w.writerow(row(i, wl, c, fam, blk))
    smoke = [("stencil", c, "A", "") for c in FAM_A] + [(wl, c, "B", "") for wl in FAM_B_WL for c in FAM_B_CELLS]
    with open(smoke_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(H)
        for i, (wl, c, fam, blk) in enumerate(smoke, 1):
            w.writerow(row(i, wl, c, fam, blk))
    print(f"{len(plan)} order rows, {len(smoke)} smoke rows (seed {SEED})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
