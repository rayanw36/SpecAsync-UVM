# Gate E1b — Measuring the handoff cost directly

**Result.** E1 put the +0.477 s in the right *place*: the batch ring
measures the pre-lock segment of `service_fault_batch()` as **99.9%** of the
outside-lock increase. E1 was wrong about *what* costs the time.

- The **enqueue handoff itself** (`kzalloc` … `queue_work`, measured by
  `enqueue_overhead_ns`) accounts for only **12.7%** of the increase on
  Stencil-24K with prefetch off. It is **31.0%** with prefetch on and
  **9.8%** on GraphBFS-23.
- The rest (≈87% on Stencil prefetch-off) is **prediction-side work** in the
  same loop. It runs **once per coalesced fault**, at about 139–167 ns per
  demand fault, not once per prediction.
- From source, the largest component of that work is `specasync_ft_predict`
  (a bsearch over 1.125M entries plus a global `spin_lock_irqsave`). No
  counter separates it from the rest of the loop, so it is **not attributed
  by measurement**.
- E1's framing of "~0.42 µs per prediction" is therefore a ratio, not a
  per-prediction cost. The measured enqueue cost is **54–75 ns per
  prediction**.


*The source check (§1) was written and committed (`82b15b9`) before any E1b run. The run
order `e1b/e1b_order.csv` (seed 202609262, sha256 `e3f6c140…`) was committed
before the first run.*

## 1. Source check: what `enqueue_overhead_ns` times

**The field.** `struct specasync_batch_record` (`specasync_telemetry.h:46-59`,
72 B, `'<6Q6I'`) has `u32 enqueue_overhead_ns` at offset 64. It is written
only in `specasync_enqueue()` (`uvm_gpu_replayable_faults.c:382-421`):

```
390  if (!g_specasync_wq || specasync_policy == 0 || spec_addr == 0) return;   // not timed
392  if (atomic_read(&g_specasync_queue_depth) >= MAX) { drops++; return; }   // not timed
398  t0 = ktime_get_ns();                                                     // ── start
399  item = kzalloc(sizeof(*item), GFP_ATOMIC);
400  if (!item) { drops++; return; }          // kzalloc failure: returns WITHOUT adding time
406  INIT_WORK(...); field stores
413  if (item->gpu) uvm_gpu_retain(item->gpu);
416  atomic_inc(&g_specasync_queue_depth);
417  queue_work(g_specasync_wq, &item->work);
418  sa_rec->spec_enqueues++;  atomic_inc(&g_specasync_enqueued);
420  sa_rec->enqueue_overhead_ns += (u32)(ktime_get_ns() - t0);               // ── end
```

| part of the Gate 1 loop (`:2670-2683`) | inside `enqueue_overhead_ns`? |
|---|---|
| `kzalloc(GFP_ATOMIC)` | **yes** |
| `INIT_WORK`, item field stores | **yes** |
| `uvm_gpu_retain` (depth ≥ 1) | **yes** |
| `queue_work` | **yes** |
| `atomic_inc` ×2, `spec_enqueues++` | **yes** |
| `specasync_predict_next` → **`specasync_ft_predict`** (policy 6) | **no** |
| `hit_table` pointer lookup (`:2677-2679`) | **no** |
| `specasync_enqueue` early returns (`spec_addr == 0`, queue-full drop) | **no** |
| loop control over `ordered_fault_cache` | **no** |

**`enqueue_overhead_ns` covers only the enqueue half of the loop.**

The part it misses is not small. `specasync_ft_predict`
(`specasync_debugfs.c:745-799`) runs for **every coalesced fault**, not only
for those that yield a prediction: every coalesced fault calls
`specasync_predict_next` (`:2675`). Each call:
- calls `specasync_replay_order_push` (a no-op at `log_replay_order=0`);
- does an `atomic_fetch_inc`;
- runs a **`bsearch` over the 1,125,000-entry sorted table** (about 20
  comparisons);
- takes the **global `g_ft_cursor_lock` with `spin_lock_irqsave`**.

On Stencil-24K C6-L4096 that is about 3.0M calls against 1.125M predictions
(E0.9b).

**A second, complete measure exists in the same ring.** `t0_ns` is stamped at
`service_fault_batch()` entry (`:2661`), before the Gate 1 loop. `t1_ns` is
stamped once, right after the **first** VA-space lock is acquired (`:2799`,
after `uvm_va_space_down_read`). So `t1 − t0` brackets:
- the entire Gate 1 loop (predict **and** enqueue);
- the trace loop (`specasync_trace_push` returns immediately at
  `trace_faults=0`);
- one flag store;
- the first `mm_retain_lock` + `down_read`, which is the first D3 wait.

It is 0 when no fault in the batch has a va_space; such records are counted
and excluded.

**Ring properties (confirmed).**
- **Gated on `specasync_log_enabled`**: `specasync_batch_ring_push`
  (`specasync_telemetry.h:221-236`) returns if `!specasync_log_enabled || !r->buf`.
- **Drop-on-full**: when `((head − tail) & mask) == mask` it increments
  `drops` and discards the record. It holds at most **131,071** records;
  `SPECASYNC_BATCH_RING_SLOTS = 1 << 17` = 131,072 (`:183`).
- **One record per `service_fault_batch()` call**: the push is at `:2947`,
  after the `fail:` label (`:2934`). The function's only `return` is the
  next line (`:2949`), so every path, including `goto fail`, pushes exactly
  one record.
- The debugfs read (`specasync_log`, `ring_read_binary`,
  `specasync_debugfs.c:206+`) copies head..tail **without advancing tail**.
  It is non-destructive.
- `enqueue_overhead_ns` is a per-batch u32 sum of per-call u32 deltas. It
  would overflow only past 4.29 s within one batch, which is impossible here.

The decomp ring has the same properties (131,071 max, gated, drop-on-full,
one record per top-level batch; E0.9b Step 1).

## 2. Runs

- The existing verified module, srcversion `5997D238EF080B77DBD2AAF`, with
  no changes.
- 16 runs in the committed seeded order: Stencil-24K C1/C6-L4096/C0/C7-L4096
  ×3 each, and GraphBFS-23 C1/C6-L4096 ×2 each.
- Fresh prefetch-off tables: 1,125,000 and 287,956 pages, assertions passed.
- Per run: reload, verify srcversion and parameters, check refcnt,
  `specasync_clear`, `setarch -R`, `timeout` (22 s / 168 s), counters,
  dmesg diff, then dumps of the batch ring and the decomp ring.
- Rows are in `e1b/e1b_runs.csv`, with wall-clock in the CSV only; it was
  **not** read or compared.
- **No stop condition**, 0 new dmesg lines on all 16 runs, MemAvailable
  ≥ 60.9 GB.

### Coverage: 100% in every run, both rings

| check | result |
|---|---|
| Record counts | batch ring 5,677–74,896; decomp ring equal to the batch ring in every run. All below 131,071, so **100% coverage**. Nothing scaled. |
| Batch ↔ decomp pairing | record k ↔ record k; `svc_start ≤ t0 ≤ t4 ≤ svc_end` holds for **every** pair (0 misaligned, 0 length mismatches) |
| `t1 = 0` records | 0 |
| Batches with more than one VA space | 0, so "first-acquisition D3" = the record's D3 |
| Ring-summed `spec_enqueues` / `spec_drops` vs the global `enqueued` / `drops` counters | **equal in every run** (for example 914,893 / 210,106), an independent check that no records were lost |

Per-run detail: `e1b/e1b_per_run.csv`.

## 3. Measurements (per arm, median of runs)

- **Pre-lock segment** = Σ (t1 − t0 − D3). This is everything in
  `service_fault_batch()` before the first VA-space lock request: the Gate 1
  predict + enqueue loop, the no-op trace loop, and one flag store.
- **Outside-lock** = Σ (svc − D3 − D4). This is E1 Part B's quantity.
- **Post-lock remainder** = outside-lock − pre-lock.

| workload | arm | n | `enqueue_overhead` total (s) | per prediction (ns) | per enqueued (ns) | pre-lock segment (s) | outside-lock svc − D3 − D4 (s) | post-lock remainder (s) | `ft_predictions` | enqueued | demand faults |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Stencil | C1 | 3 | 0 | — | — | 0.0070 | 0.0117 | 0.0048 | 0 | 0 | 2,931,773 |
| Stencil | **C6-L4096** | 3 | **0.0606** | **54** | 66 | 0.4847 | 0.4898 | 0.0051 | 1,124,999 | 916,440 | 2,990,841 |
| Stencil | C0 | 3 | 0 | — | — | 0.0007 | 0.0011 | 0.0004 | 0 | 0 | 335,489 |
| Stencil | **C7-L4096** | 3 | **0.0249** | **75** | 75 | 0.0811 | 0.0815 | 0.0004 | 334,330 | 334,330 | 334,330 |
| GraphBFS | C1 | 2 | 0 | — | — | 0.0014 | 0.0030 | 0.0015 | 0 | 0 | 490,265 |
| GraphBFS | **C6-L4096** | 2 | **0.0088** | **114** | 115 | 0.0913 | 0.0929 | 0.0017 | 77,180 | 76,895 | 485,028 |

### The comparison that matters

| pair | Δ outside-lock (s) | Δ `enqueue_overhead` (s) | **enqueue ÷ Δ outside** | Δ pre-lock (s) | pre-lock ÷ Δ outside | Δ pre-lock − Δ enqueue (s) | the same per demand fault in the speculative arm | Δ post-lock (s) |
|---|---|---|---|---|---|---|---|---|
| Stencil C6-L4096 − C1 (prefetch off) | +0.4780 | +0.0606 | **12.7%** | +0.4777 | **99.9%** | +0.4171 | 139 ns | +0.0003 |
| Stencil C7-L4096 − C0 (prefetch on) | +0.0805 | +0.0249 | **31.0%** | +0.0804 | **100.0%** | +0.0555 | 166 ns | +0.0000 |
| GraphBFS C6-L4096 − C1 | +0.0900 | +0.0088 | **9.8%** | +0.0898 | **99.9%** | +0.0810 | 167 ns | +0.0001 |

Median-of-arms differences. The Stencil C6 − C1 figure (+0.478 s) reproduces
E1 Part B's pilot value (+0.477 s) in a fresh session.

## 4. Interpretation

**Location: confirmed by measurement.** In all three pairs, 99.9–100% of the
outside-lock increase falls between `service_fault_batch()` entry and the
first VA-space lock request. The post-lock remainder is unchanged (±0.3 ms).
The only speculative code in that interval is the Gate 1 loop
(`:2670-2683`). **The speculative handoff sits on the servicing thread's
critical path. That structural claim is now measured, not inferred.**

**Composition: the source-structure attribution was incomplete.** The
enqueue handoff is **not** the dominant cost:
- It accounts for 12.7% of the increase on Stencil with prefetch off,
  31.0% with prefetch on, and 9.8% on GraphBFS.
- Measured per call, it costs **54–75 ns per prediction** (66–115 ns per
  enqueued item), **not ~0.42 µs**.

The remaining 69–90% (0.417 s on Stencil prefetch-off) is in the same loop,
outside the timed enqueue region. From source it consists of:
- `specasync_predict_next` → `specasync_ft_predict`: a bsearch over
  1,125,000 entries, an `atomic_fetch_inc`, and a
  **global `spin_lock_irqsave`**, run for every coalesced fault;
- the `hit_table` pointer lookup;
- `specasync_enqueue`'s untimed early checks, including the queue-full drop
  path, which ran about 200k times on Stencil C6;
- loop control and the `ktime_get_ns` pair around each enqueue, which falls
  partly outside the timed interval.

It scales with **demand faults** (139–167 ns each), not with predictions:
- In C7, predictions fall 3.4× from C6 while the per-fault figure *rises*.
- **Which of those components dominates is not measured.** No existing
  counter separates `specasync_ft_predict` from the rest of the loop. This
  report does not attribute it further.

**What this means:**
- The paper's structural claim, that the "off-path" design puts work on the
  critical path, is **confirmed**.
- Its stated mechanism should be **"per-fault prediction work plus the
  per-prediction enqueue"**, not "the enqueue handoff". The per-fault
  prediction work is the larger part in every configuration measured.
- **This bears directly on E3a's premise** (Part C). Skipping an enqueue for
  a prediction in the same region as the last one saves at most the enqueue
  share (≈13–31%) of the loop's cost. It cannot reduce the per-fault
  prediction work, which runs before the region check.

### Limitations

- n = 3 per Stencil arm and 2 per GraphBFS arm: descriptive, not
  confirmatory. The between-run spread is small (for example Stencil C6
  pre-lock 0.483–0.489 s).
- `enqueue_overhead_ns` includes one `ktime_get_ns()` of timing overhead
  per call. The pre-lock segment includes two `ktime_get_ns()` per enqueue
  (inside `specasync_enqueue`).
- The remainder is attributed to the prediction side **by elimination
  within a measured interval**, not measured per function.
- Single platform: RTX 5070 Ti, 595.91.07, kernel 7.0.0-34.
