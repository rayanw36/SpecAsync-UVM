"""Gate H1 cell table (shared by the order maker, runner, orchestrator and analyzer). Every cell uses --alloc malloc (HMM, malloc'd memory) and the STOCK module."""
SEED_SPARSE = 202610081          # the E8 page-list seed (same page list as E8 for the same size and K)
PASSES = 3
THR = [0, 51]
MAX_TMO = 300
# workload key -> (label, kind, args after the binary). kind decides the output check (sparse: 3 passes + CHECKSUM OK; stencil: [RESULT] Time).
WL = {
    "stencil": ("Stencil-24K", "stencil", ["24000"]),
    "in_k1": ("sparse 8 GiB K=1", "sparse", ["8", "1"]),
    "in_k512": ("sparse 8 GiB K=512", "sparse", ["8", "512"]),
    "ov_k1": ("sparse 24 GiB K=1", "sparse", ["24", "1"]),
    "ov_k512": ("sparse 24 GiB K=512", "sparse", ["24", "512"]),
}
IN_KEYS = ["stencil", "in_k1", "in_k512"]
OV_KEYS = ["ov_k1", "ov_k512"]
TESTED = ["stencil", "in_k512", "in_k1", "ov_k1", "ov_k512"]     # one Holm family of 5 (t0 vs t51 per workload)


def command(repo, key):
    label, kind, a = WL[key]
    if kind == "stencil":
        return [f"{repo}/benchmarks/bench_stencil_h1"] + a + ["--alloc", "malloc"]
    return [f"{repo}/benchmarks/bench_sparse_h1"] + a + [str(PASSES), str(SEED_SPARSE), "--alloc", "malloc"]


def kind(key):
    return WL[key][1]
