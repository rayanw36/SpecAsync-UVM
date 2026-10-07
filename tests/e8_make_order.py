#!/usr/bin/env python3
"""Gate E8 order (E8_PREREGISTRATION.md). Seed 202610082.
  Family IN  idx   1-120  in-memory (8 GiB), all 12 cells (3 thresholds x 4 K), 10 seeded permutations of the 12 cells
  Family OV  idx 121-240  oversubscribed (24 GiB), by K group in the order K = 1, 512, 8, 64; each group = 10 seeded
                          permutations of the 3 thresholds (30 rows)
  Family M   idx 241-260  mechanism (E3a-2 module, policy 0, in-memory): K in {1, 512} x threshold in {0, 51}, n = 5,
                          5 seeded permutations of the 4 cells (descriptive, untested; runs last if time remains)
Smoke rows (one per cell: the 24 stock cells and the 4 mechanism cells) go to a separate file.
usage: e8_make_order.py ORDER_CSV SMOKE_CSV"""
import csv
import random
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import e8_cells as C  # noqa: E402

SEED = 202610082
H = ["idx", "label", "workload", "module", "policy", "depth", "prefetch", "L", "W", "fast", "trace_faults",
     "dump_rings", "threshold", "family", "block"]


def row(i, wl, cell, fam, blk):
    stock = cell.startswith("stock")
    t = cell.split("-t")[1]
    return [i, f"{wl} {cell}", wl, "stock" if stock else "new", "" if stock else "0", "" if stock else "0", "1", "",
            "" if stock else "1", "" if stock else "0", "0", "0" if stock else "1", t, fam, blk]


def main(order_path, smoke_path):
    rng = random.Random(SEED)
    plan = []
    cells12 = [(C.wl_key("in", k), f"stock-t{t}") for k in C.KS for t in C.THR]
    for b in range(10):
        p = cells12[:]
        rng.shuffle(p)
        plan += [(wl, c, "IN", str(b + 1)) for wl, c in p]
    for k in C.OV_K_ORDER:
        for b in range(10):
            p = [f"stock-t{t}" for t in C.THR]
            rng.shuffle(p)
            plan += [(C.wl_key("ov", k), c, "OV", str(b + 1)) for c in p]
    cellsM = [(C.wl_key("in", k), f"spec-C0-t{t}") for k in (1, 512) for t in (0, 51)]
    for b in range(5):
        p = cellsM[:]
        rng.shuffle(p)
        plan += [(wl, c, "M", str(b + 1)) for wl, c in p]
    assert len(plan) == 120 + 120 + 20
    with open(order_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(H)
        for i, (wl, c, fam, blk) in enumerate(plan, 1):
            w.writerow(row(i, wl, c, fam, blk))
    smoke = [(C.wl_key(s, k), f"stock-t{t}", "IN" if s == "in" else "OV", "") for s in ("in", "ov")
             for k in C.KS for t in C.THR] + [(wl, c, "M", "") for wl, c in cellsM]
    with open(smoke_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(H)
        for i, (wl, c, fam, blk) in enumerate(smoke, 1):
            w.writerow(row(i, wl, c, fam, blk))
    print(f"{len(plan)} order rows, {len(smoke)} smoke rows (seed {SEED})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
