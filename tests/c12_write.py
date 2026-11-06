#!/usr/bin/env python3
"""Gate C12: write gate_e/h2/RESIDENCY_SEMANTICS.md (§1 data; §2 is the source reading, text), consolidation/CS2_N12_PROPOSED_v2.md and CATALOG_CANDIDATE_H2.md.
Every number comes from committed CSVs: h2_tests.csv, h2_residency_cells.csv, e9/cell_medians.csv, e8/primary_tests.csv (evidence ids E9.htod_frac.*, H2.*, E8.*)."""
import csv
rd = lambda p: list(csv.DictReader(open(p)))   # noqa: E731
G = "results/analysis/gate_e/"
T = {(r["alloc"], int(r["K"])): r for r in rd(G + "h2/h2_tests.csv")}
RC = {(r["alloc"], int(r["K"]), int(r["threshold"])): r for r in rd(G + "h2/h2_residency_cells.csv")}
E9 = {(r["workload"], int(r["threshold"])): r for r in rd(G + "e9/cell_medians.csv")}
E8 = {(int(r["K"]), r["arm"]): r for r in rd(G + "e8/primary_tests.csv") if r["size"] == "in"}
f = lambda x, n=2: f"{float(x):.{n}f}"   # noqa: E731
g8 = lambda b: float(b) / 2 ** 33         # fraction of 8 GiB
# ---------------- RESIDENCY_SEMANTICS
rows = []
for k in (1, 512):
    for t in (0, 51):
        x, h = E9[(f"in_k{k}", t)], RC[("managed", k, t)]
        rows.append(f"| managed K={k} t{t} | {g8(x['htod_bytes_median']):.3f} ({g8(x['htod_bytes_min']):.3f} to {g8(x['htod_bytes_max']):.3f}, n={x['n']}) | {float(h['median_frac']):.3f} ({float(h['min_mib']) / 8192:.3f} to {float(h['max_mib']) / 8192:.3f}, n={h['n']}) | `E9.htod_frac.in_k{k}.t{t}` |")
md = f"""# What H2's residency measure means on managed memory (Gate C12)

## §1 Traced bytes for in-memory managed `bench_sparse` (E9) against H2's `memory.used` residency
E9 (nsys, stock module, 8 GiB array, **managed**, in memory) has traced host-to-device bytes for K = 1 and K = 512 at t0 and t51 (`e9/cell_medians.csv`); it has **no K = 8 or K = 64 in-memory cell**. Fractions of 8 GiB; the two columns are from different sessions and different instruments.

| cell | E9 traced HtoD (median; range) | H2 `memory.used` residency (median; range) | evidence id |
|---|---|---|---|
""" + "\n".join(rows) + f"""

**Reading.** At **t0** both instruments read about the whole array on managed memory (traced {g8(E9[('in_k1', 0)]['htod_bytes_median']):.3f}, residency {f(RC[('managed', 1, 0)]['median_frac'], 3)} at K = 1). At **t51, K = 1** they disagree by a factor of about {float(RC[('managed', 1, 51)]['median_frac']) / g8(E9[('in_k1', 51)]['htod_bytes_median']):.0f}: the traced HtoD is {g8(E9[('in_k1', 51)]['htod_bytes_median']):.3f} of the array (the density rule's small fraction, as predicted), while `memory.used` rises by {f(RC[('managed', 1, 51)]['median_frac'], 3)} of it. **`memory.used` on managed memory therefore does not measure migrated data; it measures allocated GPU memory.** It is validated only where it follows migration (malloc/HMM, C9 validation and the H2 malloc cells, where K = 1 t51 reads {f(RC[('malloc', 1, 51)]['median_frac'], 3)}).
Phase 2 of the C12 brief (a new traced run) was **not needed**: §1 found in-memory managed traced bytes (K = 1 and K = 512), so no GPU run was made in this session. B1-B3 were therefore not run (B3, allocation differs from migration, is answered by the table above, across sessions).

## §2 Source reading (pristine 595.91.07 tree; read-only; labelled **hypothesis** where not certain)
- **(a) Managed block, chunk size: a whole 2 MB chunk for the block, whatever migrates.** `uvm_va_block_gpu_chunk_index_range` (`uvm_va_block.c:1011-1035`): "Optimize the ideal Pascal+ case: the whole block is covered by a single 2M page" when `mmu_user_chunk_sizes` has 2M (`uvm_mmu.c:2451`; Blackwell supports 2M pages, `uvm_blackwell_mmu.c:47`) and the block is a full 2 MB. `uvm_va_block_populate_pages_gpu` (`:2934`) then populates the chunk that covers the first page needing memory (`block_populate_gpu_chunk`, `:2842`): `block_alloc_gpu_chunk(block, retry, gpu, chunk_size, ...)` with `chunk_size = uvm_va_block_region_size(chunk_region)`, i.e. **2 MB for the whole block**, and zeroes it (`block_zero_new_gpu_chunk`, `:2730`; pages already resident elsewhere are not zeroed, `:2748-2760`). So one faulted page (or one 64 KB prefetch region) in a block allocates the block's whole 2 MB chunk. With K = 1 every 2 MB block of the array receives a 2 MB chunk: allocated GPU memory is about the array size at any threshold, while migrated bytes follow the density rule. **Hypothesis consistent with the data above** (allocated about 0.86 of the array vs traced 0.03 at t51); not confirmed with a per-chunk trace.
- **(b) HMM block: PAGE_SIZE chunks.** `block_gpu_chunk_size` returns `PAGE_SIZE` for an HMM block (`uvm_va_block.c:1174-1182`) and `block_gpu_chunk_index_range` likewise (`:1125-1134`): only the pages that migrate get (4 KB) chunks, so `memory.used` follows migrated volume (up to root-chunk granularity, next item). This is why the same instrument is valid on malloc and not on managed memory.
- **(c) PMM obtains memory from RM/PMA in 2 MB root chunks, on demand but in batches.** "PMM always allocates 2M (UVM_CHUNK_SIZE_MAX) chunks from PMA" (`uvm_pmm_gpu.c:42-44`); `alloc_root_chunk` (`:1925`) allocates **a batch of `1 << uvm_perf_pma_batch_nonpinned_order` root chunks per PMA call** for non-pinned memory (`:188-193`, `:1972`, `nvUvmInterfacePmaAllocPages` at `:1997`); this host's parameter value is 6, i.e. 64 root chunks = 128 MiB per call, best-effort. So `memory.used` counts whole root chunks, up to 128 MiB ahead of use, on both allocators. This granularity is small against 8 GiB and does not explain the managed t51 value.
- **(d) Other reasons for managed `memory.used` to rise without migration:** zeroing writes to the new chunk but does not allocate more; PMM keeps freed root chunks on its free lists (no immediate return to RM), so a run's peak can include chunks left from the previous run in the same process only (each run is a new process and a module reload, so none carries over; **hypothesis**: not checked per run). Eviction reserve is not involved in these in-memory cells.

## Verdict
**On managed memory the H2 `memory.used` residency measures allocated GPU memory at 2 MB-chunk granularity, not migrated bytes**, so H2's Z6 (held at 0.950) was scored on an instrument that cannot distinguish "whole array migrated" from "whole array allocated". The t0 statement is nevertheless supported on managed memory by E9's traced bytes (K = 1 t0: {g8(E9[('in_k1', 0)]['htod_bytes_median']):.3f} of the array). The managed t51 residency (0.856) must not be read as migrated volume.
"""
open(G + "h2/RESIDENCY_SEMANTICS.md", "w").write(md)
# ---------------- CS2_N12_PROPOSED_v2
tab = "\n".join(f"| {k} | {f(T[('malloc', k)]['delta_pct'])}% | {f(T[('managed', k)]['delta_pct'])}% | {f(E8[(k, 'stock-t0')]['delta_pct'])}% | `H2.malloc_k{k}.t0_vs_t51`, `H2.managed_k{k}.t0_vs_t51`, `E8.in.K{k}.stock-t0_vs_stock-t51` |" for k in (1, 8, 64, 512))
v2 = f"""# CS2-N12 proposed text, version 2 (Gate C12; CLAIM_SCOPE.md is not edited; replaces `CS2_N12_PROPOSED.md`)

**CS2-N12 (HMM and managed memory, in memory).** On `malloc`'d memory under the open driver's HMM mode, lowering `uvm_perf_prefetch_threshold` from 51 to 0 speeds up dense access (Stencil-24K -7.97%, `H1.stencil.stock-t0_vs_stock-t51`; sparse K = 512 {f(T[('malloc', 512)]['delta_pct'])}%, `H2.malloc_k512.t0_vs_t51`) and slows down sparse access without oversubscription (K = 1 {f(T[('malloc', 1)]['delta_pct'])}%, `H2.malloc_k1.t0_vs_t51`). The t0 time on HMM is almost independent of K (max/min {f(max(float(T[('malloc', k)]['median_c6']) for k in (1, 8, 64, 512)) / min(float(T[('malloc', k)]['median_c6']) for k in (1, 8, 64, 512)), 3)}, `H2.Z1`). On HMM the GPU memory made resident follows the density rule (`memory.used` residency, valid because HMM chunks are 4 KB): K = 1 at t51 {f(RC[('malloc', 1, 51)]['median_frac'], 3)} of the array, K = 8 at t51 {f(RC[('malloc', 8, 51)]['median_frac'], 3)}, and at t0 {f(RC[('malloc', 1, 0)]['median_frac'], 3)} at every K (`H2.res.malloc.k1.t51`, `H2.res.malloc.k8.t51`, `H2.res.malloc.k1.t0`). The K = 1 slowdown differs by allocator: {f(T[('malloc', 1)]['delta_pct'])}% on HMM against {f(T[('managed', 1)]['delta_pct'])}% on managed memory (`H2.Z7`).

Per-K deltas, t0 vs t51, same session (H2, 10 runs per cell; E8 is an earlier session):

| K | malloc (H2) | managed (H2) | managed (E8) | evidence ids |
|---|---|---|---|---|
{tab}

**Volume moved, by instrument (not pooled):** on malloc, from `memory.used` residency (valid for HMM): {f(RC[('malloc', 1, 0)]['median_frac'], 3)} of the array at K = 1, t0. On managed memory, from traced HtoD bytes (E9, nsys): {g8(E9[('in_k1', 0)]['htod_bytes_median']):.3f} of the array at K = 1, t0 and {g8(E9[('in_k1', 51)]['htod_bytes_median']):.3f} at t51 (`E9.htod_frac.in_k1.t0`, `E9.htod_frac.in_k1.t51`). So at threshold 0 a K = 1 pass moves about the whole array on both allocators, each by its own measure; the managed t51 value shows that the density rule keeps managed K = 1 migration small, as on HMM. H2's managed `memory.used` residency is **not** used for any volume statement (it measures allocated 2 MB chunks, `h2/RESIDENCY_SEMANTICS.md`). K = 8 and K = 64 managed traced bytes were not measured.

**Cross-session agreement (managed, in memory):** the managed t0-vs-t51 deltas of H2 and E8 agree at K = 1 ({f(T[('managed', 1)]['delta_pct'])}% vs {f(E8[(1, 'stock-t0')]['delta_pct'])}%) and at K = 8, 64, 512 ({', '.join(f(T[('managed', k)]['delta_pct']) + '% vs ' + f(E8[(k, 'stock-t0')]['delta_pct']) + '%' for k in (8, 64, 512))}).

The difference between the allocators in cost at the same threshold-0 volume is consistent with HMM's per-4 KB `migrate_vma` migration (Section III); that attribution is **not isolated** by H2. The oversubscribed HMM case was not measured (stock-driver defect, Section V).
"""
open("results/analysis/consolidation/CS2_N12_PROPOSED_v2.md", "w").write(v2)
# ---------------- catalog candidate
cat = f"""# Catalog candidate (proposal; ARTIFACT_CATALOG.md is not edited) - Gate C12

### #31? · `memory.used` read as migrated volume, validated on one allocator only
- **What was measured (H2):** the peak of `nvidia-smi memory.used` minus a pre-launch baseline, used as "GPU memory made resident" on both `malloc` (HMM) and managed memory. C9's validation covered malloc mode only (memory.used rose about 2288 MiB during a 2 GiB malloc run).
- **False conclusion it would have produced:** "the volume moved at threshold 0 is the same on both allocators" (H2 expectation **Z6**, scored **HELD** at {f(RC[('managed', 1, 0)]['median_frac'], 3)}), and, through the managed t51 value ({f(RC[('managed', 1, 51)]['median_frac'], 3)} of the array at K = 1), the impression that managed memory migrates almost everything even at the shipped threshold. Traced bytes (E9) give {g8(E9[('in_k1', 51)]['htod_bytes_median']):.3f} of the array at that cell. On managed memory the driver allocates a whole 2 MB chunk per VA block on the first fault (`uvm_va_block.c:1011-1035`, `:2842`), so `memory.used` tracks allocation, not migration; on HMM chunks are 4 KB (`:1174-1182`) and it tracks migration.
- **How caught:** by inspection of the managed t51 cell against the density rule after the gate (a faulted page widened to 64 KB, the next level failing the 51% test, predicts a small fraction), then confirmed against E9's traced bytes. The gate's own scoring did not catch it (the expectation held).
- **Evidence:** `E9.htod_frac.in_k1.t51`, `E9.htod_frac.in_k1.t0`, `H2.res.managed.k1.t51`, `H2.res.managed.k1.t0`, `H2.res.malloc.k1.t51`, `H2.Z6`, `h2/RESIDENCY_SEMANTICS.md`. The residency instrument and its managed readings were from different sessions than E9; not a same-session comparison.
- **Candidate family:** Instrument cost and instrument blindness (an instrument that measures a different quantity on one allocator); also Validation that could not fail (the validation covered malloc only, where the instrument works, so it could not fail for the managed case).
"""
open("results/analysis/consolidation/CATALOG_CANDIDATE_H2.md", "w").write(cat)
print("written")
