"""Gate E8 cell table (shared by the order maker, runner, orchestrator and analyzer)."""
import os
IN_GIB, OV_GIB, PASSES, SEED = 8, 24, 3, 202610081
KS = [1, 8, 64, 512]
SIZES = {"in": IN_GIB, "ov": OV_GIB}
THR = [0, 25, 51]
OV_K_ORDER = [1, 512, 8, 64]
MAX_TMO = 300


def wl_key(size, K):
    return f"{size}_k{K}"


def command(repo, key):
    size, k = key.split("_k")
    return [f"{repo}/benchmarks/bench_sparse", str(SIZES[size]), k, str(PASSES), str(SEED)]
