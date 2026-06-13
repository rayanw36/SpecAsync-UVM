# Gate B — Oracle diagnosis (root cause by inspection)

Status: **diagnosed, not yet fixed.** The fix is a code change + rebuild + re-run;
holding for the Gate checkpoint before that cycle.

## H1 (task's leading hypothesis): O(n²) trace scan — **REJECTED**

The oracle replay is already **O(1)**. `specasync_oracle_next_addr()`
(`specasync_debugfs.c:276-285`) is an atomic post-increment cursor into a preloaded
array, wrapping modulo length:

```c
idx = atomic_fetch_inc(&g_oracle_idx) % (int)g_oracle_trace_len;
return g_oracle_trace[idx];
```

There is no per-fault linear scan anywhere. The "cost is quadratic in fault count"
hypothesis is not supported by this source. (If Phase B's oracle was genuinely
~100× slower, that slowdown is **not** an O(n²) replay — see H3.)

## H2 (the real bug): cursor/fault **rate desynchronisation** → ~0 hits

This explains the oracle's 0.000 hits on every benchmark.

- The fault **trace** is recorded **once per demand fault**: `specasync_trace_push`
  is inside the per-fault loop (`uvm_gpu_replayable_faults.c:2505`). So the trace
  has *one entry per fault*.
- The oracle is **consumed once per batch**: `specasync_predict_next()` →
  `oracle_next_addr()` is called a single time per `service_fault_batch`, from
  `ordered_fault_cache[0]` only (`uvm_gpu_replayable_faults.c:2484-2494`), advancing
  `g_oracle_idx` by exactly 1.

Consequence: a batch that coalesces *k* faults consumes *k* trace entries' worth of
fault stream but advances the oracle cursor by **1**. After the first multi-fault
batch the cursor points at an address the demand stream has **already passed**, so
every oracle "prediction" is a stale, already-faulted page. It is tagged, then never
demand-faulted again → `spec_hits = 0`. The desync is permanent and grows with batch
size, so the heaviest-coalescing benchmarks (GraphBFS) are the worst — consistent
with the observed ordering.

This is the same per-batch / fault[0]-only limitation that hurts p1–p3 (Gate A),
but for the oracle it is fatal: a perfect-trace predictor scores zero purely from
the indexing mismatch.

## H3 (secondary): where could a real slowdown come from?

Not destructive migration — `offload_depth=0` in the oracle sweep
(`scripts/oracle_sweep.sh` sets only `specasync_oracle_trace_path`,
`specasync_policy=4`, `specasync_log_enabled=1`; depth defaults to 0), so the worker
is metadata-only and never calls `make_resident`. Candidate real costs to measure
when reproducing: per-batch workqueue churn + `uvm_va_space_down_read/up_read` in the
worker contending the demand path's VA-space lock under very high batch counts. **To
be confirmed empirically** on one short benchmark before any claim — the O(n²) story
should not be repeated.

## Fix plan (for the post-checkpoint build cycle)

1. **Match consumption rate to fault rate.** Either (a) drive prediction once per
   *serviced fault* rather than once per batch, or (b) advance the oracle cursor by
   the number of faults consumed. Cleanest: move the predict/enqueue inside the
   per-fault service loop so every policy (p1–p3 and oracle) predicts per fault.
2. **Preload remains O(1)** — no change needed; the cursor is already a hash/array
   advance. Document that H1 was wrong.
3. **Same work primitive** — keep the oracle metadata-only (matches p1–p3) so it
   measures the ceiling *of the same mechanism*. An active-migration oracle, if
   wanted, becomes a separate clearly-labelled policy.
4. **Trace-load fragility note:** the trace loads only if `specasync_policy==4` *at
   module init* **and** `specasync_oracle_trace_path` is set (`0444`, init-only)
   (`specasync_debugfs.c:415-416`). Selecting the oracle by flipping the policy param
   at runtime would silently load no trace → `oracle_next_addr()` returns 0 → enqueue
   skipped → inert oracle. Phase B's `oracle_sweep.sh` reloads with both set, so it
   avoided this, but it is a foot-gun worth hardening (load on first use / warn).

## Success criteria when re-run (unchanged from brief)

Oracle hit rate ≫ p1–p3, ideally ≈1.0 on the deterministic probe, and runtime not
catastrophically worse than baseline. If hits go high but speedup stays ~0, that is
the real and expected ceiling result (metadata-only speculation has no consumable
product — see Gate A).
