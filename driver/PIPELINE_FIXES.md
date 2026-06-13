# PIPELINE_FIXES.md — SpecAsync-UVM Phase B.1 corrections

Every pipeline bug found and fixed (or ruled out) while validating the Phase B
measurement pipeline. Branch `phaseB1-pipeline-fix`. Companion evidence in
`results/phaseB1/`.

---

## FIX-0 (not a bug): hit accounting is correct

The brief suspected the spec_hits counter never fires on the v595 port. **It does.**
A deterministic positive control (`tests/hit_probe.cu`, serialized adjacent touches,
`uvm_perf_prefetch_enable=0`) scores **254/256 = 99.2 %**. No change made to hit
accounting. The near-zero hit rates on real benchmarks are a real interaction with
the UVM prefetcher + per-batch prediction, not a broken counter. See
`results/phaseB1/GATE_A_report.md`. **Key semantic caveat:** a "hit" = prediction
correctness only; the worker is metadata-only (`offload_depth=0`) and discards the
block, so a hit carries zero time saving and the speedup ceiling is ~0 by design.

---

## FIX-1: oracle replay cursor desynchronisation  *(code fix)*

**Symptom:** oracle (policy=4) scored 0.000 hits on every Phase B benchmark.

**Root cause:** the fault trace is recorded **once per demand fault**
(`uvm_gpu_replayable_faults.c:2505`, inside the per-fault loop) but the oracle was
consulted **once per service batch** (`specasync_predict_next` →
`specasync_oracle_next_addr`, single call site at the top of `service_fault_batch`,
advancing the cursor by 1). A batch that coalesces *k* faults consumes *k* trace
entries' worth of fault stream while the cursor moves by 1, so after the first
multi-fault batch every "prediction" points at a page the demand stream already
passed. Heaviest-coalescing workloads (GraphBFS) are worst — matching the observed
ordering.

**Note — the brief's O(n²) hypothesis is REJECTED:** `specasync_oracle_next_addr`
was already O(1) (atomic cursor + modulo). The slowdown, if real, is not a quadratic
replay scan.

**Fix:** advance the cursor by the number of faults the batch will service and
return the page that faults *next*. New O(1) helper
`specasync_oracle_next_addr_n(consumed)` (`specasync_debugfs.c`):

```c
old = atomic_fetch_add((int)consumed, &g_oracle_idx);   /* cursor += faults this batch */
return g_oracle_trace[(old + consumed) % len];          /* first page to fault AFTER this batch */
```

`specasync_predict_next()` now takes `batch_faults` and the oracle case passes
`batch_context->num_coalesced_faults`. Files: `specasync_debugfs.c`,
`specasync_internal.h`, `uvm_gpu_replayable_faults.c`.

**Before/after (probe evidence):**

| probe                         | OLD ko `B83C15DA` | NEW ko `090C90A` |
|-------------------------------|------------------:|-----------------:|
| serialized (1 fault/batch)    | 0.99¹             | 0.99             |
| **coalesced (7.9 faults/batch)** | **0.0175**     | **0.4107**       |

¹ The old code scores high on the *serialized* probe only by a degenerate
"self-hit": it tags the page that is *currently* faulting (zero lead time). Under
coalescing — the regime every real benchmark is in — it collapses to ~0, which is
exactly the Phase B oracle result. The fix restores genuine ahead-of-fault
prediction (23× more hits at 7.9 faults/batch).

The residual gap from 1.0 under coalescing is the **one-prediction-per-batch**
design (the oracle preloads only the next batch's first fault, ~1/coalesce_factor
ceiling), *not* the desync bug. This is the same mechanism ceiling that limits
p1–p3 and is itself a finding (see GATE_B report).

---

## FIX-2: oracle trace uses absolute VAs that ASLR re-randomises  *(run-procedure fix)*

**Symptom (independent of FIX-1):** even with a perfectly synced cursor, replayed
addresses never match the measurement run.

**Root cause:** `cudaMallocManaged` returns a different base VA every process
(`0x7fc5… / 0x7ad9… / 0x7efa…`). `collect_oracle_traces.sh` records **absolute**
fault VAs in one process and `oracle_sweep.sh` replays them in a **fresh** process
with a new base → zero address overlap → 0 hits, regardless of FIX-1.

**Fix (procedure):** run both the trace-collection and the replay benchmark under
disabled ASLR so the managed base is stable. Verified: `setarch -R` pins the base to
`0x7fffce000000` across processes. `tests/run_oracle_probe.sh` and
`run_oracle_coalesce.sh` already wrap the probe in `setarch -R`; the Phase B oracle
scripts must do the same for any real re-run (TODO if Gate D proceeds). A more
robust long-term fix is to record page *offsets* relative to allocation base rather
than absolute VAs, but that needs allocation-boundary tracking in the driver.

---

## Reproduce

```bash
bash   driver/scripts/reconstruct_build_tree.sh        # rebuild work tree + module
sudo   tests/run_hit_probe.sh 256 1 adj                # FIX-0 positive control (prefetch off needed)
sudo   tests/run_oracle_coalesce.sh <ko> 4096 tag      # FIX-1/2 old-vs-new oracle
```

Fixed module persisted at `driver/build/nvidia-uvm-specasync-phaseB1.ko`
(srcversion `090C90A438763086CA2D055`). Pre-fix module kept at
`driver/build/nvidia-uvm-specasync.ko` (`B83C15DA…`) for comparison/rollback;
stock fallback at `driver/stock_backup/nvidia-uvm.ko.stock` (`85A79790…`).
