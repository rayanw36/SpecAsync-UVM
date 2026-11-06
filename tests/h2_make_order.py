#!/usr/bin/env python3
"""Gate H2 orders (H2_PREREGISTRATION.md). 16 cells = 4 K x 2 allocators x 2 thresholds.
  timed order     160 rows (10 seeded permutation blocks of the 16 cells), seed 202611061
  smoke order      16 rows (one per cell, excluded from analysis)
  residency order  48 rows (3 seeded permutation blocks of the 16 cells; mechanism pass, not a timed outcome), seed 202611062
usage: h2_make_order.py TIMED_CSV SMOKE_CSV RESIDENCY_CSV"""
import csv, random, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import h2_cells as C  # noqa: E402
H = ["idx", "label", "workload", "module", "policy", "depth", "prefetch", "L", "W", "fast", "trace_faults", "dump_rings", "threshold", "family", "block"]
CELLS = [(k, t) for k in C.KEYS for t in C.THR]


def row(i, wl, t, fam, blk):
    return [i, f"{wl} stock-t{t}", wl, "stock", "", "", "1", "", "", "", "0", "0", t, fam, blk]


def write(path, plan):
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(H)
        for i, (k, t, fam, blk) in enumerate(plan, 1):
            w.writerow(row(i, k, t, fam, blk))


def main(timed, smoke, res):
    for seed, blocks, path, fam in ((202611061, 10, timed, "T"), (202611062, 3, res, "R")):
        rng = random.Random(seed); plan = []
        for b in range(blocks):
            p = CELLS[:]; rng.shuffle(p); plan += [(k, t, fam, str(b + 1)) for k, t in p]
        write(path, plan)
    write(smoke, [(k, t, "S", "") for k, t in CELLS])
    print("160 timed, 16 smoke, 48 residency rows")


if __name__ == "__main__":
    main(*sys.argv[1:4])
