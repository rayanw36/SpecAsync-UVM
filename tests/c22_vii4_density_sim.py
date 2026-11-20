#!/usr/bin/env python3
"""C22 VII-4: simulate the density prefetcher (uvm_perf_prefetch.c:118 strict test, 64 KB fault-granularity growth grow_fault_granularity, binary subregion tree) on E8's page list
(seed 202610081, reproduced by tests/c22_pagelist.cpp; hashes validated against the H2 stdout logs) and compare with E9 traced bytes and H2 HMM residency.
Model (one service call per block with all K pages faulted, GPU-empty block, no thrashing): bitmap = faulted pages with their 64 KB (16-page) aligned groups filled; for each faulted page the
largest subregion (1,2,...,512 pages containing it) with 100*count > threshold*size is the prefetch region; migrated = faulted U regions. Output: consolidation/C22_VII4_DENSITY_SIM.md."""
import csv, statistics as st, subprocess
import numpy as np
D = "/tmp/claude-1000/c22"
THR = (0, 25, 51)
def sim_block(pages, t, widen=16):
    bm = np.zeros(512, bool)
    for p in pages: bm[(p // widen) * widen:(p // widen + 1) * widen] = True
    cs = np.concatenate(([0], np.cumsum(bm)))
    out = np.zeros(512, bool); out[list(pages)] = True
    for p in pages:
        best = None
        sz = 1
        while sz <= 512:
            a = (p // sz) * sz; cnt = cs[a + sz] - cs[a]
            if cnt * 100 > sz * t: best = (a, sz)
            sz *= 2
        if best: out[best[0]:best[0] + best[1]] = True
        if best and best[1] == 512: break
    return int(out.sum())
def run(size, K, widen=16):
    a = np.fromfile(f"{D}/{size}_k{K}.bin", dtype=np.uint32).reshape(-1, K)
    res = {}
    for t in THR:
        if K == 512: res[t] = (1.0, 0.0, 1.0); continue
        mig = []
        for row in a:
            pg = sorted(int(x) % 512 for x in row)
            mig.append(sim_block(pg, t, widen))
        mig = np.array(mig) / 512.0
        res[t] = (float(mig.mean()), float(mig.min()), float(mig.max()))
    return res
SIM = {(s, K): run(s, K) for s in ("in", "ov") for K in (1, 8, 64, 512)}
SIM32 = {(s, K): run(s, K, widen=32) for s in ("in",) for K in (1, 8, 64)}
rd = lambda p: list(csv.DictReader(open(p)))   # noqa: E731
E9 = {(r["workload"], int(r["threshold"])): r for r in rd("results/analysis/gate_e/e9/cell_medians.csv")}
E9R = rd("results/analysis/gate_e/e9/e9_runs.csv")
RES = rd("results/analysis/gate_e/h2/residency_summary.csv")
GIB = 2 ** 30
o = ["# C22 VII-4: does the density rule (Eq. 1) explain E8's failed expectations? (descriptive simulation)", "",
     "Script `tests/c22_vii4_density_sim.py`; page list reproduced by `tests/c22_pagelist.cpp` (same `mt19937_64`, `std::shuffle`, partial Fisher-Yates as `benchmarks/bench_sparse.cu`; the 8 GiB hashes equal the logged `page_list_hash` of the H2 runs: K=1 `8033df96e71bf8eb`, K=8 `79f57bb182dc47ca`, K=64 `4167c60bd21b7c0e`, K=512 `34416921a498ff60`; the 24 GiB lists use the same code and are not independently validated). Rule from `uvm_perf_prefetch.c:118` (`100*count > threshold*size`, strict), `grow_fault_granularity` (`:176-227`, whole 64 KB big pages filled in the bitmap when any page of the big page faults and nothing is thrashing) and `compute_prefetch_region` (`:102-146`, the largest passing subregion containing a faulted page wins; leaf-to-root traversal, `uvm_perf_prefetch.h:108-113`).", "",
     "**Model assumptions:** every K page of a block is in one service call, the block is GPU-empty, no thrashing, no prefetch of other blocks. Predicted fraction = mean over blocks of (faulted pages U prefetch regions) / 512. This is the first-touch fraction of a block, so it predicts the *first-pass* HtoD volume as a fraction of the array.", "",
     "## Predicted migrated fraction of the array per cell (mean over blocks; min..max per block)", "", "| size | K | t0 | t25 | t51 |", "|---|---|---|---|---|"]
for (s, K), r in SIM.items():
    o.append(f"| {s} | {K} | " + " | ".join(f"{100*r[t][0]:.2f}% ({100*r[t][1]:.1f}..{100*r[t][2]:.1f})" for t in THR) + " |")
o += ["", "## Measured: E9 traced HtoD (n = 3, medians) and H2 HMM residency (n = 3)", "",
      "In-memory E9 cells exist for K = 1 and 512 only. Oversubscribed E9 cells: the first-pass column uses `pass1_htod_bytes` (median of the 3 runs) as a fraction of the 24 GiB array, the total column `htod_bytes` / (3 x 24 GiB).", "",
      "| cell | threshold | predicted first-touch fraction | measured | measured / predicted | evidence |", "|---|---|---|---|---|---|"]
for wl in ("in_k1", "in_k512"):
    s, K = wl.split("_k"); K = int(K)
    for t in (0, 51):
        meas = float(E9[(wl, t)]["htod_bytes_median"]) / GIB / 8
        pr = SIM[("in", K)][t][0]
        o.append(f"| {wl} | {t} | {100*pr:.2f}% | {100*meas:.2f}% (htod {float(E9[(wl, t)]['htod_bytes_median'])/GIB:.3f} GiB) | {meas/pr:.2f} | `E9.cell.{wl}.t{t}` |")
for K in (1, 8, 64, 512):
    for t in (0, 51):
        rows = [r for r in E9R if r["workload"] == f"ov_k{K}" and int(r["threshold"]) == t]
        p1 = st.median(float(r["pass1_htod_bytes"]) for r in rows) / GIB / 24
        tot = st.median(float(r["htod_bytes"]) for r in rows) / GIB / 72
        pr = SIM[("ov", K)][t][0]
        o.append(f"| ov_k{K} (first pass) | {t} | {100*pr:.2f}% | {100*p1:.2f}% | {p1/pr:.2f} | `E9.cell.ov_k{K}.t{t}` (`pass1_htod_bytes`) |")
o += ["", "Oversubscribed first-pass HtoD at K = 1 is exactly 2.00x the model at both thresholds (48 GiB at t0 = 2 x 24 GiB; 1.5 GiB at t51 = 2 x 0.75 GiB), and 1.9-2.0x at K = 8; at K = 64 and 512 the first pass is near 1x. The model does not predict the doubling; it is not explained here (candidate causes not tested: eviction write-back followed by re-fault of the same block within a pass, or nsys counting each prefetch migration twice under oversubscription).", ""]
o += ["## H2 HMM residency (`memory.used` residency, valid on HMM) against the same rule", "", "HMM blocks use 4 KB GPU chunks and a prefetch region clamped to the VMA/policy (`uvm_hmm_get_prefetch_region`), so the managed rule is only a reference; the second column of predictions applies the same tree with a 32-page (128 KB) granule-growth to test whether the HMM t51 values look like a doubled granule (exploratory, not a documented behaviour).", "",
      "| K | threshold | managed-rule prediction | granule 32 pages (exploratory) | measured HMM residency (median frac of 8 GiB) | evidence |", "|---|---|---|---|---|---|"]
for K in (1, 8, 64, 512):
    for t in (0, 25, 51):
        meas = [float(r["residency_frac_8gib"]) for r in RES if r["workload"] == f"malloc_k{K}" and int(r["threshold"]) == t]
        if not meas: continue
        p16 = SIM[("in", K)][t][0]
        p32 = SIM32.get(("in", K), {}).get(t, (None,))[0] if K != 512 else 1.0
        o.append(f"| {K} | {t} | {100*p16:.2f}% | {('%.2f%%' % (100*p32)) if p32 is not None else '-'} | {100*st.median(meas):.1f}% | `H2.res.malloc.k{K}.t{t}` |")
o += ["", "(H2 measured thresholds are t0 and t51 only; t25 rows appear only where a cell exists.)", ""]
# XS4 / XS5
tp = {(s, K, t): SIM[(s, K)][t][0] for s in ("in", "ov") for K in (1, 8, 64, 512) for t in THR}
ex = {K: tp[("in", K, 0)] - tp[("in", K, 51)] for K in (1, 8, 64, 512)}
mono = all(tp[(s, K, 51)] <= tp[(s, K, 25)] + 1e-9 <= tp[(s, K, 0)] + 2e-9 for s in ("in", "ov") for K in (1, 8, 64, 512))
o += ["## XS4 and XS5 (E8 expectations that FAILED)", "",
      "**Result of the simulation (volume only):** the rule reproduces the measured first-touch volume where E9 has a cell (in-memory K = 1: 100% at t0 and 3.12% at t51, measured/predicted 1.00 and 1.00; K = 512: about 100%), predicts t25 = 6.25% at K = 1 (a 32-page subregion passes, the 64-page one fails the strict test: 16 counted pages x 100 = 1600 is not > 64 x 25 = 1600) and predicts the K = 8 bimodality (t25 per-block volume 25% to 75%: blocks whose widened groups do not overlap reach exactly 128 counted pages = 25% of 512, which fails the strict test, as hypothesised). Predicted volume is monotone in the threshold in every cell (t51 <= t25 <= t0: " + str(mono) + ").", "",
      "**XS4** (the t0 delta rises monotonically as K falls; FAILED because K = 64 is faster than K = 512: in-memory -9.69% against -7.54%, oversubscribed -9.67% against -7.66%). The rule predicts that t0 moves the whole block at every K and t51 moves " + ", ".join(f"K={K}: {100*tp[('in', K, 51)]:.1f}%" for K in (1, 8, 64, 512)) + ", so the extra volume of t0 over t51 is " + ", ".join(f"K={K}: {100*ex[K]:.1f}%" for K in (1, 8, 64, 512)) + " of the array: non-increasing in K, and **identical (zero) at K = 64 and K = 512**. A volume-only rule therefore predicts no difference between those two cells, so the XS4 violation (a 2.2-point difference between two cells with the same predicted volume) does **not follow from the rule**; it must come from something the rule does not model (fault counts and batch structure: K = 64 raises more faults per block than K = 512 at t51, E9 `gpu_faults_sum`).", "",
      "**XS5** (t25 between t0 and t51 cell by cell; FAILED in-memory K = 1 and K = 8 and oversubscribed K = 8). Predicted t25 volumes: " + "; ".join(f"K={K}: {100*tp[('in', K, 25)]:.1f}% (t0 {100*tp[('in', K, 0)]:.0f}%, t51 {100*tp[('in', K, 51)]:.1f}%)" for K in (1, 8)) + ". The ordering of *volume* is t51 <= t25 <= t0 in every cell, so XS5 holds for volume; its failures are wall-clock orderings (in-memory K = 1: t25 -0.60% against t0 +3.95%, the extra 0.25 GiB cannot make t25 faster than t51; K = 8: t25 +0.78% with t25 volume between t51 and t0 while t0 is -2.32%), so they do **not follow from the rule alone**. E9 has no t25 cells, so t25 volume is a prediction only.", "",
      "**Verdict:** Eq. 1 with the 64 KB growth explains the volume at t0 and t51 (and the in-memory K = 1 and 512 E9 cells to 1%), and explains the bimodal t25 at K = 8, but it does not explain the XS4 and XS5 failures, which are time orderings among cells whose predicted volume is equal or monotone.", ""]
open("results/analysis/consolidation/C22_VII4_DENSITY_SIM.md", "w").write("\n".join(o))
print("\n".join(o[14:50]))
