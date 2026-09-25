# Gate E1b — Measuring the handoff cost directly

*Draft. The source check below was written before any E1b run. The run
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
