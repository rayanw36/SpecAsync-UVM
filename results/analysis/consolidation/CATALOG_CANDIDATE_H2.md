**APPLIED as ARTIFACT_CATALOG.md entry #31 (C13, 2026-11-06).**

# Catalog candidate (proposal; ARTIFACT_CATALOG.md is not edited) - Gate C12

### #31? · `memory.used` read as migrated volume, validated on one allocator only
- **What was measured (H2):** the peak of `nvidia-smi memory.used` minus a pre-launch baseline, used as "GPU memory made resident" on both `malloc` (HMM) and managed memory. C9's validation covered malloc mode only (memory.used rose about 2288 MiB during a 2 GiB malloc run).
- **False conclusion it would have produced:** "the volume moved at threshold 0 is the same on both allocators" (H2 expectation **Z6**, scored **HELD** at 0.950), and, through the managed t51 value (0.856 of the array at K = 1), the impression that managed memory migrates almost everything even at the shipped threshold. Traced bytes (E9) give 0.031 of the array at that cell. On managed memory the driver allocates a whole 2 MB chunk per VA block on the first fault (`uvm_va_block.c:1011-1035`, `:2842`), so `memory.used` tracks allocation, not migration; on HMM chunks are 4 KB (`:1174-1182`) and it tracks migration.
- **How caught:** by inspection of the managed t51 cell against the density rule after the gate (a faulted page widened to 64 KB, the next level failing the 51% test, predicts a small fraction), then confirmed against E9's traced bytes. The gate's own scoring did not catch it (the expectation held).
- **Evidence:** `E9.htod_frac.in_k1.t51`, `E9.htod_frac.in_k1.t0`, `H2.res.managed.k1.t51`, `H2.res.managed.k1.t0`, `H2.res.malloc.k1.t51`, `H2.Z6`, `h2/RESIDENCY_SEMANTICS.md`. The residency instrument and its managed readings were from different sessions than E9; not a same-session comparison.
- **Candidate family:** Instrument cost and instrument blindness (an instrument that measures a different quantity on one allocator); also Validation that could not fail (the validation covered malloc only, where the instrument works, so it could not fail for the managed case).
