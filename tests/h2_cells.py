"""Gate H2 cell table. bench_sparse 8 GiB (in memory only; NO oversubscribed cell, either allocator), allocator in {managed, malloc}, K as in E8's in-memory set."""
SEED_SPARSE = 202610081          # the E8/H1 page-list seed
PASSES = 3
GIB = 8
KS = [1, 8, 64, 512]             # = e8_cells.KS
ALLOCS = ["managed", "malloc"]
THR = [0, 51]
MAX_TMO = 300
WL = {f"{a}_k{k}": (f"{a} K={k}", "sparse", a, k) for a in ALLOCS for k in KS}
KEYS = list(WL)
TESTED = [f"{a}_k{k}" for a in ALLOCS for k in KS]      # one Holm family of 8: t0 vs t51 per (allocator, K)


def command(repo, key):
    label, kind, a, k = WL[key]
    return [f"{repo}/benchmarks/bench_sparse_h1", str(GIB), str(k), str(PASSES), str(SEED_SPARSE), "--alloc", a]


def kind(key):
    return "sparse"
