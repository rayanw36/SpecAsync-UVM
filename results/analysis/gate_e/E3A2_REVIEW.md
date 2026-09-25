# Gate E3a-2 — Width conditions and a cheap oracle (compiled, NOT loaded)

**Status: compiled only. No module was loaded in this session.** Both
features wait for review (HARD STOP).

| item | value |
|---|---|
| Sources | overlay `driver/src-e3a/`; **`driver/src/` untouched** (`git diff ea1a262 HEAD -- driver/src` empty) |
| Patches | **`driver/patches/e3a_spec_width.patch`**, regenerated as the full cumulative `diff -u driver/src driver/src-e3a` (793 lines; §7). New file **`driver/patches/e3a2_region_history_ft_fast.delta.patch`**: this session's delta only (`git diff 031aaae -- driver/src-e3a`, 580 lines), for reviewing what changed since the E3a review. |
| Baseline re-confirmed | `reconstruct_build_tree.sh` into the E3a work tree from the unchanged `driver/src` reproduced srcversion **`5997D238EF080B77DBD2AAF`** before the overlay was applied |
| Build | `make` exit 0, **0 warnings, 0 errors** |
| New module | `driver/build/595.91.07/nvidia-uvm-specasync-NEW-e3a2-width-ftfast-UNREVIEWED.ko`: srcversion **`33FD42E6E16B0A6658E2BEB`**, vermagic **`7.0.0-34-generic SMP preempt mod_unload modversions`**, sha256 `dc6b226e…`. It supersedes the E3a build (`…-e3a-width-UNREVIEWED.ko`, `91F63480…`), which is kept and has never been loaded. |
| Verified module | `…-e0.9a2-fixed.ko` unchanged (sha256 `ab91372b…`), **still the loaded module** (srcversion `5997D238…`; neither `specasync_spec_width` nor `specasync_ft_fast` present in its parameters) |

---

## B1 — What does `continue` skip?

**Loop body as it stood at the start of this session** (E3a,
`driver/src-e3a/uvm_gpu_replayable_faults.c` at `031aaae`, lines 2759–2792):

```c
    if (specasync_log_enabled && batch_context->num_coalesced_faults > 0) {
        NvU32 _fi;
        for (_fi = 0; _fi < batch_context->num_coalesced_faults; _fi++) {
            uvm_fault_buffer_entry_t *_fe = batch_context->ordered_fault_cache[_fi];
            if (_fe && _fe->va_space) {
                u64 _spec_addr = specasync_predict_next(_fe->va_space,
                                                        _fe->fault_address, 1);
                struct specasync_hit_table *_ht =
                    (_fe->va_space->specasync_pred) ?
                    _fe->va_space->specasync_pred->hit_table : NULL;
                /*
                 * Gate E3a: at W > 1, policy 6 does not enqueue a prediction
                 * whose W-page region equals the last ENQUEUED prediction's.
                 * Touches no UVM state: a local, two specasync globals, one
                 * counter. At W = 1 this branch is never taken and the call
                 * below is exactly the pre-E3a call.
                 */
                if (specasync_spec_width > 1 &&
                    specasync_policy == SPECASYNC_POLICY_FIRST_TOUCH &&
                    _spec_addr != 0) {
                    u64 _rid = _spec_addr >> (PAGE_SHIFT + specasync_spec_width_shift);

                    if (_rid == READ_ONCE(g_specasync_last_region)) {
                        atomic_inc(&g_specasync_ft_same_region);
                        continue;
                    }
                    if (specasync_enqueue(_fe->va_space, _spec_addr, _ht, &_sa_rec, _fe->gpu))
                        WRITE_ONCE(g_specasync_last_region, _rid);
                } else {
                    specasync_enqueue(_fe->va_space, _spec_addr, _ht, &_sa_rec, _fe->gpu);
                }
            }
        }
    }
```

**Verdict: correct.**
- `continue` (line 2783) targets the innermost enclosing loop, which is
  `for (_fi = 0; …; _fi++)` at line 2761. The `if` blocks around it are
  not loops.
- After the enqueue calls (2785/2788), the loop body only closes braces.
  **Nothing follows the enqueue** inside the loop: no counter, ring write,
  hit-table update, cursor step or telemetry step.
- The fault-trace push is a separate loop after this one (the "Gate E0.5
  fix" block) and is not skipped.
- So `continue` skips exactly the enqueue and its `WRITE_ONCE`, then runs
  `_fi++`. No restructuring was needed.

**After B2's change** (the current source, line 2763 onward), the loop
body is:

```c
    if (specasync_log_enabled && batch_context->num_coalesced_faults > 0) {
        NvU32 _fi;
        for (_fi = 0; _fi < batch_context->num_coalesced_faults; _fi++) {
            uvm_fault_buffer_entry_t *_fe = batch_context->ordered_fault_cache[_fi];
            if (_fe && _fe->va_space) {
                u64 _spec_addr = specasync_predict_next(_fe->va_space,
                                                        _fe->fault_address, 1);
                struct specasync_hit_table *_ht =
                    (_fe->va_space->specasync_pred) ?
                    _fe->va_space->specasync_pred->hit_table : NULL;
                /*
                 * Gate E3a / E3a-2: at W > 1, policy 6 does not enqueue a
                 * prediction whose W-page region equals any of the last
                 * SPECASYNC_REGION_HISTORY ENQUEUED predictions' regions.
                 * Touches no UVM state: locals, specasync globals, one
                 * counter. The match is recorded in _seen and the `continue`
                 * sits OUTSIDE the inner _k loop, so it targets this _fi loop
                 * (a `continue` inside the _k loop would only advance _k).
                 * At W = 1 this branch is never taken and the call below is
                 * exactly the pre-E3a call.
                 */
                if (specasync_spec_width > 1 &&
                    specasync_policy == SPECASYNC_POLICY_FIRST_TOUCH &&
                    _spec_addr != 0) {
                    u64 _rid = _spec_addr >> (PAGE_SHIFT + specasync_spec_width_shift);
                    bool _seen = false;
                    u32 _k;

                    for (_k = 0; _k < SPECASYNC_REGION_HISTORY; _k++) {
                        if (READ_ONCE(g_specasync_last_regions[_k]) == _rid) {
                            _seen = true;
                            break;
                        }
                    }
                    if (_seen) {
                        atomic_inc(&g_specasync_ft_same_region);
                        continue;
                    }
                    if (specasync_enqueue(_fe->va_space, _spec_addr, _ht, &_sa_rec, _fe->gpu)) {
                        u32 _slot = READ_ONCE(g_specasync_last_region_idx) &
                                    (SPECASYNC_REGION_HISTORY - 1);

                        WRITE_ONCE(g_specasync_last_regions[_slot], _rid);
                        WRITE_ONCE(g_specasync_last_region_idx,
                                   (_slot + 1) & (SPECASYNC_REGION_HISTORY - 1));
                    }
                } else {
                    specasync_enqueue(_fe->va_space, _spec_addr, _ht, &_sa_rec, _fe->gpu);
                }
            }
        }
    }
```

The new history compare introduces an inner loop, `for (_k …)`. A
`continue` inside it would advance `_k`, not `_fi`, which is exactly the
hazard B1 asks about. So the match sets `_seen` and `break`s, and the
`continue` sits **outside** the `_k` loop, where it targets `_fi` as before.
Nothing follows the enqueue in the loop body, as before.

## B2 — Does "last region only" ever fire?

Offline, from the first-touch tables (`tests/e3a2_offline.py`):
- **Primary:** E1b's tables, `results/phaseB1/gate_e1b/tables/`.
- **Stability check:** E1's tables.
- The tables are gitignored raw data, so no *committed* table exists; the
  most recent ones were used.

`consecutive` is the fraction of entries whose region equals the previous
entry's. `K = k` is the fraction of entries whose region is among the last
k distinct regions inserted, where a region is inserted only on a miss,
exactly as the round-robin array inserts only on enqueue.

| table | W | consecutive | K=1 | K=2 | K=4 | K=8 | **K1 / K8** |
|---|---|---|---|---|---|---|---|
| Stencil-24K (E1b) | 16 | 0.0821 | 0.0821 | 0.0821 | 0.0823 | 0.0915 | **0.898** |
| Stencil-24K (E1b) | 64 | 0.3969 | 0.3969 | 0.3969 | 0.3993 | 0.5950 | **0.667** |
| GraphBFS-23 (E1b) | 16 | 0.2388 | 0.2388 | 0.2391 | 0.2419 | 0.2449 | **0.975** |
| GraphBFS-23 (E1b) | 64 | 0.3102 | 0.3102 | 0.3106 | 0.3142 | 0.3182 | **0.975** |
| Stencil-24K (E1) | 16 / 64 | 0.0824 / 0.3994 | — | — | — | 0.0917 / 0.5954 | 0.899 / **0.671** |
| GraphBFS-23 (E1) | 16 / 64 | 0.2372 / 0.3090 | — | — | — | 0.2439 / 0.3176 | 0.973 / 0.973 |

**Decision (rule applied without judgement):** K = 1 must capture ≥ 80% of
K = 8 on both workloads. **Stencil-24K at W = 64 gives 66.7%**, and 67.1%
on the second table, so the rule fails.

**`g_specasync_last_region` has been replaced** by:
- `u64 g_specasync_last_regions[8]` (initialised to `SPECASYNC_NO_REGION`)
  and `u32 g_specasync_last_region_idx`;
- round-robin insertion **only after `specasync_enqueue` returns true**;
- a linear compare over all 8 slots.

These are plain globals, touched only by the fault-servicing thread
(`READ_ONCE`/`WRITE_ONCE`), reset by `specasync_clear`, with no UVM state.
Everything is inside the existing `specasync_spec_width > 1 && policy 6`
guard, so W = 1 is unaffected.

The slot index is **masked** (`& (8 − 1)`), so even a corrupted index
cannot address outside the array. A `static_assert` requires the history
size to be a power of two.

(Predictions are a subsequence of table order: the cursor advances one rank
per prediction and jumps forward on skips. So these fractions estimate skip
frequency in issue order. With a lookahead, consecutive predictions can be
many faults apart; table order still decides which predictions are
consecutive.)

## B3 — Double-counting

No code change. **Stated:**
- An item rejected by `specasync_width_region()` never reaches
  `uvm_mutex_trylock`: `sregion_ok` is false, so the `&&`
  short-circuits.
- It falls into the existing `else { uvm_va_block_retry_deinit(...) }`
  branch with `mstatus` still `NV_ERR_BUSY_RETRY`, so the item's work-ring
  result is **`SPECASYNC_RESULT_THROTTLED`**, *and* it is counted in
  **`spec_region_invalid`**.
- The dead-block branch is the same: the lock *is* taken, `make_resident`
  is skipped, `mstatus` stays `NV_ERR_BUSY_RETRY`, the result is
  THROTTLED, and the item is also counted in `spec_region_invalid`.
- `spec_migrations` is not incremented in either case.

**Analysis identities that count each enqueued item exactly once** (policy
6, depth 1, W > 1):

```
ft_predictions      = ft_same_region + enqueued + drops                (prediction side; every prediction is
                                                                        skipped, enqueued, or dropped at enqueue)
enqueued            = processed  (at quiescence, after the post-run drain)
lost_after_enqueue  = enqueued − spec_migrations                        (global counters only)
                    = spec_region_invalid  +  other_lost
other_lost          = enqueued − spec_migrations − spec_region_invalid  (trylock failure, ctx alloc failure,
                                                                        address outside block, make_resident
                                                                        error, depth-0 fall-through)
```

**Rules for analysis:**
- Never add the work ring's THROTTLED count to `spec_region_invalid`. The
  THROTTLED count already contains every `spec_region_invalid` item.
- If the work ring is used, compute
  `THROTTLED_other = THROTTLED − spec_region_invalid`, and only when the
  work ring has 100% coverage.
- `spec_pages_requested` grows only when `make_resident` is actually called,
  so invalid and dead-block items contribute 0 pages.

---

## Part C — The cheap oracle (`specasync_ft_fast`)

### Design

**Parameter.** `specasync_ft_fast`, 0444, default 0.
- Validated by a `module_param_cb` setter, exactly like
  `specasync_spec_width`: anything but 0 or 1 → `-EINVAL` → `insmod`
  fails, with `pr_err("… rejected: must be 0 or 1")`.

**Dispatch.** The only change to `specasync_ft_predict` is one new first
statement:
- `if (smp_load_acquire(&g_ft_fast_active)) return specasync_ft_predict_fast(fault_addr);`
- Everything below it is the unchanged original body.
- `g_ft_fast_active` becomes true only when `specasync_ft_fast == 1`
  **and** the load-time equivalence check passed.
- **At 0, the path is the original one**, plus one load and one branch.

**Range index**, built at table load in process context during module init:
- It comes from `g_ft_sorted`, the existing page-sorted array.
- One `struct {u64 base_pfn; u32 len; u32 off;}` per maximal run of
  consecutive pages.
- One `u32` rank per page, where `g_ft_range_ranks[i] = g_ft_sorted[i].rank`,
  so `off` is the run's start index in `g_ft_sorted`.
- Build refuses, and leaves the fast path off, if any table page is not
  page-aligned or any page repeats.

**Lookup** (`specasync_ft_fast_rank`):
1. `pfn = page >> PAGE_SHIFT`.
2. Find the range: a linear scan when there are ≤ 16 ranges, else a binary
   search for the last range with `base_pfn ≤ pfn`.
3. `idx = off + (pfn − base_pfn)`, **bounds-checked** against
   `g_ft_table_len`, then the rank itself is checked against
   `g_ft_table_len`.
4. A NULL or empty index, or a page in no range, returns false. The caller
   counts that as `ft_unknown_page` and returns 0.

**Ranges and memory** (from the real tables; allocated with `vmalloc`,
like the existing table):

| workload | pages | **ranges** | lookup | longest run | index size (16 B/range + 4 B/page) | existing table + sorted copy |
|---|---|---|---|---|---|---|
| Stencil-24K | 1,125,000 | **2** | linear scan | 562,500 | **4.50 MB** (4,500,032 B) | 9.0 MB + 18.0 MB |
| GraphBFS-23 | 287,956 | **19** | binary search (> 16) | 256,189 | **1.15 MB** (1,152,128 B) | 2.3 MB + 4.6 MB |

**Freeing.**
- The index is freed by `specasync_ft_fast_free()`: on module unload, in
  `specasync_debugfs_exit` before the table is freed, and at the start of
  every build.
- There is **no runtime table-reload path** in this module: the table
  loads once, in `specasync_debugfs_init`. The build-time free covers any
  future reload.
- `specasync_ft_fast_free` clears `g_ft_fast_active` before freeing.

### How the cmpxchg loop reproduces the rule

The slow path, under `g_ft_cursor_lock`, and the fast path, lock-free, both
do the following:

| step | slow path (under lock) | fast path (per `atomic_try_cmpxchg` attempt, from the observed cursor n) |
|---|---|---|
| 0 | `!g_ft_table \|\| len == 0 → return 0` | identical |
| 1 | `specasync_replay_order_push`; `my_seq = atomic_fetch_inc(&g_ft_seq)` | identical, same order |
| 2 | bsearch; missing → `ft_unknown_page++`, return 0 | range lookup; missing → `ft_unknown_page++`, return 0 |
| 3 | `if (next ≤ r) { ft_skipped += r+1−next; next = r+1 }` | `n' = (n ≤ r) ? r+1 : n`, `skipped = r+1−n` if skipped |
| 4 | `next ≥ len → ft_exhausted++` · `next ≤ r+L → predict table[next], next++, ft_predictions++` · else `ft_held++` | the same three-way decision on n'. The new cursor is n' (exhausted/held) or n'+1 (predict). |
| 5 | unlock; if predicted, `specasync_ft_log_push(my_seq, rank)` | commit with **one** `cmpxchg(n → new)`, even when new == n, so the decision is made against a cursor value that was current at commit. Counters and the ft-log push happen **only after a successful commit**, once each, exactly as the slow path makes them. On failure the reloaded n is used to recompute. |

Arithmetic is identical, including the `u32` expression
`r + (u32)specasync_ft_lookahead`. No wraparound: at the end of the table
it counts `ft_exhausted`.

**Two deliberate deviations from the brief (for review):**
1. **The cursor stays an `atomic_t`, and the loop uses the 32-bit
   `atomic_try_cmpxchg`, not `atomic64`.**
   - `g_ft_next_to_predict` is the existing `atomic_t` that the slow path
     and `specasync_clear` also use.
   - Changing its type to `atomic64_t` would change the fast = 0 path's
     code (`atomic_read` → `atomic64_read`, …). The brief requires that
     path to stay exactly as it is.
   - Ranks are ≤ 1,125,000 < 2³¹, and the cmpxchg is on the very variable
     the other paths use.
2. **A retry bound.** After `SPECASYNC_FT_FAST_MAX_TRIES` = 64 failed
   commits the call returns 0, making no prediction and leaving the cursor
   and counters unchanged, and counts `specasync_ft_fast_cas_giveup`.
   - A bottom half should never spin without limit.
   - With one fault-servicing thread per GPU, a commit can fail only if
     `specasync_clear` writes the cursor at that instant.
   - This is the one outcome the slow path cannot produce, so it has its
     own counter and should read 0.

### `specasync_clear` vs. the fault path

**From source, nothing prevents `specasync_clear` from racing with fault
servicing.**
- `clear_write` (`specasync_debugfs.c:445`) runs in process context
  whenever userspace writes the file.
- The harnesses only write it between runs, when no GPU work is running,
  but the module does not enforce that.

**Slow path today:**
- `clear` resets the counters *outside* `g_ft_cursor_lock` and the cursor
  inside it.
- A concurrent fault can therefore land counter increments on either side
  of the reset. That imprecision already exists and is by convention
  avoided.

**Fast path:**
- The cursor reset (`atomic_set(&g_ft_next_to_predict, 0)`) and the fast
  path's `atomic_try_cmpxchg` are both atomic operations on the same
  `atomic_t`. A cmpxchg computed from a pre-clear value **fails** if the
  clear intervened, and the decision is recomputed from 0.
- The cursor is never torn and never moves backward except through the
  clear itself.
- A clear landing *after* a successful commit can leave that one call's
  counter increments on the post-clear side. That is the same bounded
  imprecision the slow path has.
- The retry bound guarantees that even a stream of clears cannot make the
  bottom half spin.

**The clear path is therefore safe against the cmpxchg loop as it
stands.** It keeps taking `g_ft_cursor_lock`, which is harmless to the
lock-free reader. `clear` now also resets the region history and the
give-up counter.

### Load-time equivalence check (mandatory)

`specasync_ft_fast_build_and_verify()` runs when the table loads with
`specasync_ft_fast = 1`.

1. For **every** table page `g_ft_table[i]`, it looks up the rank with the
   existing `bsearch` and with the range index. Any single difference, or
   either lookup missing, triggers a `pr_err` with the first mismatch
   (index, page, both results), frees the index, and leaves the fast path
   **off** for this load. The slow path is then used.
2. Additionally, for every range, the page just below and just above must
   be **absent** from both lookups.
3. The outcome goes to debugfs:
   - `specasync_ft_fast_verified` (1 = passed; 0 = failed or not attempted);
   - `specasync_ft_fast_verify_ns` (check duration);
   - `specasync_ft_fast_nranges`;
   - `specasync_ft_fast_cas_giveup`.

### Self-check (no module load): the actual source, compiled in userspace

`tests/e3a2_userspace_check.sh` works as follows:
- It **extracts by name** from `driver/src-e3a/specasync_debugfs.c`:
  `specasync_ft_fast_free`, `specasync_ft_fast_rank`,
  `specasync_ft_fast_build_and_verify`, `specasync_ft_predict_fast`, the
  full `specasync_ft_predict` including its original slow body, and the
  structs and comparators.
- It compiles them with gcc against thin shims (atomics → `__atomic`
  builtins, `vmalloc` → `malloc`, the spinlock → a no-op).
- It replays the **recorded prefetch-off fault traces** from the E1b table
  collection through both paths at every L.

| workload | faults replayed | build + equivalence check | L = 1 / 16 / 256 / 4096: every counter (`ft_predictions`, `ft_skipped`, `ft_held`, `ft_unknown_page`, `ft_exhausted`), `g_ft_seq`, final cursor, ft-log pushes and their (seq, rank) checksum, **and a hash of the full returned-prediction stream** | cmpxchg give-ups | disable path |
|---|---|---|---|---|---|
| Stencil-24K | 2,944,267 | verified: 2 ranges, 54 ms | **identical, slow vs. fast, at all four L** | 0 | unaligned page → disabled ✓; duplicate page → disabled ✓ |
| GraphBFS-23 | 480,974 | verified: 19 ranges, 17 ms | **identical at all four L** | 0 | ✓ / ✓ |

Userspace time per call was about 32–55 ns (slow) against about 13 ns
(fast). This is **indicative only**: userspace has no real irqsave lock and
no kernel context, so it is not a measurement of the kernel cost. Test
step 4 below measures that.

**What this does not cover:**
- It is single-threaded, so it does not exercise real contention on the
  cmpxchg.
- The rank-mismatch branch of the check cannot be reached without an
  inconsistent index, because both lookups derive from `g_ft_sorted`. It
  shares its disable path with the unaligned and duplicate cases, which
  *were* exercised.
- The first in-kernel run is test step 3.

---

## Part D — Safety

### Extended function-and-precondition table (new calls in E3a-2)

**No new UVM function is called by E3a-2.** The fast oracle and the region
history touch no UVM state. The E3a table (`E3A_WIDTH_REVIEW.md` §3)
still covers the worker. New calls:

| function | where | context / locks | NULL / error | assert-only checks | guard |
|---|---|---|---|---|---|
| `kstrtoint`, `param_get_int`, `module_param_cb` | `specasync_ft_fast` setter | insmod argument parsing | `kstrtoint` error → `-EINVAL` | — | the kernel never calls `.set` with `val == NULL` for ops without `KERNEL_PARAM_OPS_FL_NOARG` |
| `vmalloc` / `vfree` | build / free | process context (module init / exit) | `vmalloc` may return NULL | — | both allocations checked. On failure: `pr_err`, free both, fast path off. `vfree` is only called on non-NULL, and the pointer is set to NULL after. |
| `bsearch` (lib/bsearch.c) | equivalence check (and the existing slow path) | process context | returns NULL if absent (handled) | — | `found` checked before dereference |
| `ktime_get_ns` | equivalence check timing | process context | — | — | — |
| `atomic_try_cmpxchg` (`atomic_t`) | fast path | bottom half, lock-free | returns bool; updates `old` on failure | — | bounded loop (64) |
| `atomic_fetch_inc`, `atomic_inc`, `atomic_add`, `atomic_read`, `atomic_set` | fast path, clear | any | — | — | — |
| `smp_store_release` / `smp_load_acquire` on `g_ft_fast_active` | build / dispatch | — | — | — | index stores are published before the flag; a reader that sees the flag sees the index |
| `specasync_replay_order_push`, `specasync_ft_log_push` (existing inlines) | fast path (same calls the slow path makes) | return immediately unless `specasync_log_replay_order` / `specasync_log_ft_predictions` is set (both 0 in every planned configuration). When set they take their ring's `spin_lock_irqsave`, exactly as from the slow path. | — | — | unchanged behaviour |
| `debugfs_create_u64`, `debugfs_create_u32`, `debugfs_create_atomic_t` | init | process context | creation failures ignored, like the existing counters | — | — |

**Every new pointer dereference:**
- `g_ft_ranges[j]`: `j < n = g_specasync_ft_fast_nranges`, which is the
  allocated count (set only after the arrays are filled). In the binary
  search, `mid < hi ≤ n` and `j = lo − 1` with `lo ≥ 1` checked.
- `g_ft_range_ranks[idx]`: `idx < g_ft_table_len` is **checked
  explicitly**, and the array has `g_ft_table_len` entries.
- The fast path returns "unknown page" if `g_ft_ranges` or
  `g_ft_range_ranks` is NULL, or `nranges == 0`.
- `g_ft_table[n2]`: `n2 < g_ft_table_len` by the branch that selects
  `FT_PREDICT`. `g_ft_table` non-NULL is checked at the fast path's first
  statement.
- In the build: `g_ft_sorted[i]` and `g_ft_table[i]` for `i < g_ft_table_len`
  (both have that many entries); `g_ft_ranges[k − 1]` with `k ≥ 1` (the
  first iteration always opens a range); `k < n` checked before each new
  range.
- In the check: the probe `base_pfn − 1` is skipped when `base_pfn == 0`
  (no underflow).
- Region history: `g_specasync_last_regions[_k]` with `_k < 8`; the slot
  index is masked `& 7`.

**Bottom-half footprint:**
- The fast path touches only the read-only table and index, the cursor
  atomic, `g_ft_seq`, and specasync counters, plus the two existing
  diagnostic pushes that are off in all planned configurations.
- **No UVM state, no allocation, no blocking, no lock.**
- The region history touches only its own globals and one counter.

### Risk table (E3a-2 additions; E3a's table still applies to the worker)

| # | what could fail | where | consequence for the machine | mitigation |
|---|---|---|---|---|
| 1 | Index bounds error → out-of-bounds read of `g_ft_range_ranks` | fault bottom half | a wrong rank (misprediction), or a read past a vmalloc area → **oops** | explicit `idx < len` check, rank `< len` check, and the load-time check over every page. The userspace replay exercised every table page at 4 L values. |
| 2 | Fast path used before the index is fully built | bottom half | reads a partially built index | the flag is published with `smp_store_release` after the build and check; the reader uses `smp_load_acquire`; the table loads in module init, before any GPU fault can reach the path |
| 3 | Free while a fault is in the fast path | exit | use-after-free → oops | freed only in `specasync_debugfs_exit` (module unload, refcnt 0, no fault servicing), or in build before the flag is set. The flag is cleared first. This is the same lifetime as the existing table. |
| 4 | cmpxchg livelock | bottom half | a stalled fault-servicing thread | bounded at 64 tries, then give up, counted |
| 5 | The fast rule diverges from the slow rule | bottom half | the oracle silently changes, invalidating comparisons | identical counters and prediction stream on real traces (§C self-check); the same arithmetic; test step 2 (group_probe fast = 1 vs 0) and step 4 compare in-kernel counters |
| 6 | Equivalence check too slow at load | module init | slower `insmod` (≈ 17–54 ms in userspace; similar in kernel) | none needed |
| 7 | Region-history compare cost per prediction at W > 1 | bottom half | 8 compares per prediction (a few ns) | only at W > 1, policy 6 |
| 8 | `specasync_ft_fast = 1` with a table that fails the check | init | the fast path is silently off | `specasync_ft_fast_verified` must be read after every load (test plan) |

---

## Combined test plan for the next attended session (one feature at a time)

1. **`insmod` rejection** (no GPU work):
   - `specasync_spec_width` ∈ {0, 3, 1024, abc};
   - `specasync_ft_fast` ∈ {2, −1, abc}.

   Each must fail with its `pr_err` line and leave no module loaded. Reload
   the verified module after each.
2. **`group_probe`**, back to back:
   - the verified module (`5997D238…`);
   - the new module at W = 1 / fast = 0 (regression: counters must match
     the verified module within the probe's recorded noise;
     `ft_same_region = spec_region_invalid = 0`;
     `spec_pages_requested` = the number of `make_resident` calls);
   - W = 1 / fast = 1 (`specasync_ft_fast_verified = 1`, `cas_giveup = 0`,
     policy-6 counters matching fast = 0 if the probe uses policy 6;
     otherwise this confirms that the fast path is dormant for other
     policies);
   - W = 16 / fast = 0 (`spec_region_invalid = 0`,
     `spec_pages_requested ≈ 16 × calls`).
3. **Stencil-24K**, C6 (prefetch off) and C7 (prefetch on) configurations,
   policy 6, L = 4096, one run each:
   - at fast = 1 with W = 1;
   - at W = 16 with fast = 0.

   Read `specasync_ft_fast_verified` after **every** load. Check the full
   E0.9b per-run procedure and stop conditions, and the identities in B3.
4. **E1b-style measurement.** Batch ring plus decomp ring, fast = 0 against
   fast = 1, with C6-L4096 and C7-L4096 and C1/C0 references. The measure
   is outside-lock servicing time (the pre-lock segment). **This is the
   direct test of whether the oracle's own cost was the lookup and
   lock:** the pre-lock increase should shrink by the prediction-side
   share if it was.
5. **Only then**, pre-registered sweeps.

---

## 7. Full cumulative diff (`driver/patches/e3a_spec_width.patch`)

The session delta is in `driver/patches/e3a2_region_history_ft_fast.delta.patch`.

```diff
diff -u driver/src/specasync_debugfs.c driver/src-e3a/specasync_debugfs.c
--- driver/src/specasync_debugfs.c	2026-09-25 12:34:51.018232483 +0300
+++ driver/src-e3a/specasync_debugfs.c	2026-09-25 23:05:17.412060809 +0300
@@ -116,6 +116,95 @@
 MODULE_PARM_DESC(specasync_ft_log_ring_slots,
 	"Gate E0.9 diagnostic ft-log ring capacity, rounded up to a power of two (default 1048576)");
 
+/*
+ * Gate E3a: speculative width W (see specasync_internal.h). Validated in the
+ * setter, which the kernel calls while parsing insmod arguments: returning
+ * -EINVAL there makes insmod itself fail ("Invalid parameters"), which is the
+ * only reliable way to reject a value -- specasync_debugfs_init() failures
+ * are non-fatal to module load (uvm.c). 0444: fixed for the module's life,
+ * so the worker and the fault path never see it change mid-run.
+ */
+int specasync_spec_width       = 1;
+int specasync_spec_width_shift = 0;
+
+static int specasync_spec_width_set(const char *val, const struct kernel_param *kp)
+{
+	int w;
+	int ret = kstrtoint(val, 0, &w);
+
+	if (ret) {
+		pr_err("specasync: specasync_spec_width='%s' rejected: not an integer\n", val);
+		return -EINVAL;
+	}
+	if (w < 1 || w > SPECASYNC_SPEC_WIDTH_MAX || !is_power_of_2(w)) {
+		pr_err("specasync: specasync_spec_width=%d rejected: must be a power of two in [1, %d]\n",
+		       w, SPECASYNC_SPEC_WIDTH_MAX);
+		return -EINVAL;
+	}
+	specasync_spec_width       = w;
+	specasync_spec_width_shift = ilog2(w);
+	return 0;
+}
+
+static const struct kernel_param_ops specasync_spec_width_ops = {
+	.set = specasync_spec_width_set,
+	.get = param_get_int,
+};
+module_param_cb(specasync_spec_width, &specasync_spec_width_ops, &specasync_spec_width, 0444);
+MODULE_PARM_DESC(specasync_spec_width,
+	"Gate E3a: speculative width in pages, power of two in [1, 512] (default 1 = pre-E3a behaviour)");
+
+u64        g_specasync_last_regions[SPECASYNC_REGION_HISTORY] = {
+	[0 ... SPECASYNC_REGION_HISTORY - 1] = SPECASYNC_NO_REGION };
+u32        g_specasync_last_region_idx      = 0;
+atomic_t   g_specasync_ft_same_region       = ATOMIC_INIT(0);
+atomic_t   g_specasync_spec_region_invalid  = ATOMIC_INIT(0);
+atomic64_t g_specasync_spec_pages_requested = ATOMIC64_INIT(0);
+
+static int spec_pages_requested_get(void *data, u64 *val)
+{
+	*val = (u64)atomic64_read(&g_specasync_spec_pages_requested);
+	return 0;
+}
+DEFINE_DEBUGFS_ATTRIBUTE(spec_pages_requested_fops, spec_pages_requested_get, NULL, "%llu\n");
+
+/*
+ * Gate E3a-2: cheap first-touch oracle switch (see specasync_internal.h).
+ * Same validation pattern as specasync_spec_width: anything but 0 or 1 makes
+ * insmod fail. 0444: fixed for the module's life.
+ */
+int specasync_ft_fast = 0;
+
+static int specasync_ft_fast_set(const char *val, const struct kernel_param *kp)
+{
+	int v;
+
+	if (kstrtoint(val, 0, &v)) {
+		pr_err("specasync: specasync_ft_fast='%s' rejected: not an integer\n", val);
+		return -EINVAL;
+	}
+	if (v != 0 && v != 1) {
+		pr_err("specasync: specasync_ft_fast=%d rejected: must be 0 or 1\n", v);
+		return -EINVAL;
+	}
+	specasync_ft_fast = v;
+	return 0;
+}
+
+static const struct kernel_param_ops specasync_ft_fast_ops = {
+	.set = specasync_ft_fast_set,
+	.get = param_get_int,
+};
+module_param_cb(specasync_ft_fast, &specasync_ft_fast_ops, &specasync_ft_fast, 0444);
+MODULE_PARM_DESC(specasync_ft_fast,
+	"Gate E3a-2: 1 = constant-time lock-free first-touch lookup (verified at load), 0 = original bsearch path [default]");
+
+/* Gate E3a-2 fast-path outcome and safety counters (debugfs, read-only). */
+atomic_t   g_specasync_ft_fast_verified   = ATOMIC_INIT(0); /* 1 = equivalence check passed */
+u64        g_specasync_ft_fast_verify_ns  = 0;              /* check duration, written once at load */
+u32        g_specasync_ft_fast_nranges    = 0;              /* ranges in the index (0 = none) */
+atomic_t   g_specasync_ft_fast_cas_giveup = ATOMIC_INIT(0); /* cmpxchg retry bound hit */
+
 /* ── Gate E0.5 counters (defined here, declared extern in specasync_telemetry.h / specasync_internal.h) ── */
 atomic_t g_specasync_trace_pushes           = ATOMIC_INIT(0);
 atomic_t g_specasync_trace_overwrites       = ATOMIC_INIT(0);
@@ -182,6 +271,27 @@
 static atomic_t                      g_ft_seq             = ATOMIC_INIT(0);
 static DEFINE_SPINLOCK(g_ft_cursor_lock);
 
+/*
+ * Gate E3a-2: range index over g_ft_sorted (page-sorted). One entry per
+ * maximal run of consecutive pages: pages [base_pfn, base_pfn + len) have
+ * ranks g_ft_range_ranks[off .. off + len). off is the run's start index in
+ * g_ft_sorted, so g_ft_range_ranks[i] == g_ft_sorted[i].rank. Built and
+ * verified at load (process context), read-only afterwards. g_ft_fast_active
+ * is set true only after the equivalence check passes, before any fault can
+ * reach specasync_ft_predict() (the table and index are loaded in module
+ * init), and cleared before anything is freed.
+ */
+struct specasync_ft_range {
+	u64 base_pfn;
+	u32 len;
+	u32 off;
+};
+static struct specasync_ft_range *g_ft_ranges       = NULL;  /* vmalloc'd */
+static u32                       *g_ft_range_ranks  = NULL;  /* vmalloc'd, g_ft_table_len entries */
+static bool                       g_ft_fast_active  = false;
+#define SPECASYNC_FT_FAST_LINEAR_MAX   16   /* <= this many ranges: linear scan */
+#define SPECASYNC_FT_FAST_MAX_TRIES    64   /* cmpxchg retry bound (bottom half never spins unbounded) */
+
 /* ── Static debugfs dentries ─────────────────────────────────────────────── */
 
 static struct dentry *specasync_dir;
@@ -400,6 +510,18 @@
 	atomic_set(&g_specasync_ft_unknown_page, 0);
 	atomic_set(&g_specasync_ft_exhausted, 0);
 	atomic_set(&g_specasync_fault_already_resident, 0);
+	/* Gate E3a: per-run-clean totals, and no carried-over "last region". */
+	atomic_set(&g_specasync_ft_same_region, 0);
+	atomic_set(&g_specasync_spec_region_invalid, 0);
+	atomic64_set(&g_specasync_spec_pages_requested, 0);
+	{
+		int _r;
+
+		for (_r = 0; _r < SPECASYNC_REGION_HISTORY; _r++)
+			WRITE_ONCE(g_specasync_last_regions[_r], SPECASYNC_NO_REGION);
+		WRITE_ONCE(g_specasync_last_region_idx, 0);
+	}
+	atomic_set(&g_specasync_ft_fast_cas_giveup, 0);
 	{
 		unsigned long _flags;
 		spin_lock_irqsave(&g_ft_cursor_lock, _flags);
@@ -634,6 +756,183 @@
 	return 0;
 }
 
+/* Gate E3a-2: free the range index (safe to call when nothing is allocated). */
+static void specasync_ft_fast_free(void)
+{
+	WRITE_ONCE(g_ft_fast_active, false);
+	if (g_ft_ranges) {
+		vfree(g_ft_ranges);
+		g_ft_ranges = NULL;
+	}
+	if (g_ft_range_ranks) {
+		vfree(g_ft_range_ranks);
+		g_ft_range_ranks = NULL;
+	}
+	g_specasync_ft_fast_nranges = 0;
+}
+
+/*
+ * Gate E3a-2: constant-time rank lookup via the range index. Returns false
+ * ("unknown page") if the index is absent or the page is in no range. Every
+ * array access is bounds-checked explicitly.
+ */
+static bool specasync_ft_fast_rank(u64 page, u32 *rank_out)
+{
+	const struct specasync_ft_range *rg = g_ft_ranges;
+	const u32 *ranks = g_ft_range_ranks;
+	u32 n = g_specasync_ft_fast_nranges;
+	u64 pfn = page >> PAGE_SHIFT;
+	u64 idx;
+	u32 j, lo, hi, rank;
+
+	if (!rg || !ranks || n == 0 || g_ft_table_len == 0 || !rank_out)
+		return false;
+
+	if (n <= SPECASYNC_FT_FAST_LINEAR_MAX) {
+		for (j = 0; j < n; j++)
+			if (pfn >= rg[j].base_pfn && pfn - rg[j].base_pfn < (u64)rg[j].len)
+				goto found;
+		return false;
+	}
+	/* Binary search: lo = number of ranges with base_pfn <= pfn. */
+	lo = 0;
+	hi = n;
+	while (lo < hi) {
+		u32 mid = lo + (hi - lo) / 2;
+
+		if (rg[mid].base_pfn <= pfn)
+			lo = mid + 1;
+		else
+			hi = mid;
+	}
+	if (lo == 0)
+		return false;
+	j = lo - 1;
+	if (pfn - rg[j].base_pfn >= (u64)rg[j].len)
+		return false;
+found:
+	idx = (u64)rg[j].off + (pfn - rg[j].base_pfn);
+	if (idx >= (u64)g_ft_table_len)
+		return false;
+	rank = ranks[idx];
+	if (rank >= g_ft_table_len)
+		return false;
+	*rank_out = rank;
+	return true;
+}
+
+/*
+ * Gate E3a-2: build the range index from g_ft_sorted and verify it against
+ * the existing bsearch for every table page (plus the page just below and
+ * just above every range, which must be unknown to both). Process context,
+ * module init. On any failure the index is freed and the fast path stays
+ * off; the slow path is unaffected either way.
+ */
+static void specasync_ft_fast_build_and_verify(void)
+{
+	u32 i, n, r, k;
+	u64 t0;
+
+	specasync_ft_fast_free();            /* no stale index from any earlier load */
+	atomic_set(&g_specasync_ft_fast_verified, 0);
+	g_specasync_ft_fast_verify_ns = 0;
+	if (!g_ft_table || !g_ft_sorted || g_ft_table_len == 0)
+		return;
+
+	/* Count maximal runs; refuse unaligned or duplicate pages outright. */
+	n = 0;
+	for (i = 0; i < g_ft_table_len; i++) {
+		if (g_ft_sorted[i].page & (PAGE_SIZE - 1)) {
+			pr_err("specasync: ft_fast: table page %llx not page-aligned; fast path disabled\n",
+			       (unsigned long long)g_ft_sorted[i].page);
+			return;
+		}
+		if (i > 0 && g_ft_sorted[i].page == g_ft_sorted[i - 1].page) {
+			pr_err("specasync: ft_fast: duplicate table page %llx; fast path disabled\n",
+			       (unsigned long long)g_ft_sorted[i].page);
+			return;
+		}
+		if (i == 0 || g_ft_sorted[i].page != g_ft_sorted[i - 1].page + PAGE_SIZE)
+			n++;
+	}
+
+	g_ft_ranges = vmalloc((size_t)n * sizeof(*g_ft_ranges));
+	g_ft_range_ranks = vmalloc((size_t)g_ft_table_len * sizeof(*g_ft_range_ranks));
+	if (!g_ft_ranges || !g_ft_range_ranks) {
+		pr_err("specasync: ft_fast: index allocation failed; fast path disabled\n");
+		specasync_ft_fast_free();
+		return;
+	}
+	k = 0;
+	for (i = 0; i < g_ft_table_len; i++) {
+		if (i == 0 || g_ft_sorted[i].page != g_ft_sorted[i - 1].page + PAGE_SIZE) {
+			if (k >= n) {            /* cannot happen: n counted identically above */
+				pr_err("specasync: ft_fast: range count overflow; fast path disabled\n");
+				specasync_ft_fast_free();
+				return;
+			}
+			g_ft_ranges[k].base_pfn = g_ft_sorted[i].page >> PAGE_SHIFT;
+			g_ft_ranges[k].len = 0;
+			g_ft_ranges[k].off = i;
+			k++;
+		}
+		g_ft_ranges[k - 1].len++;
+		g_ft_range_ranks[i] = g_ft_sorted[i].rank;
+	}
+	g_specasync_ft_fast_nranges = n;
+
+	/* Equivalence check: every table page, both lookups, identical rank. */
+	t0 = ktime_get_ns();
+	for (i = 0; i < g_ft_table_len; i++) {
+		u64 page = g_ft_table[i];
+		struct specasync_ft_sorted_entry *found =
+			bsearch(&page, g_ft_sorted, g_ft_table_len,
+				sizeof(struct specasync_ft_sorted_entry), cmp_ft_bsearch_key);
+		bool fast_ok = specasync_ft_fast_rank(page, &r);
+
+		if (!found || !fast_ok || found->rank != r) {
+			pr_err("specasync: ft_fast: equivalence FAILED at table index %u page %llx: bsearch %s rank %u, range index %s rank %u; fast path disabled\n",
+			       i, (unsigned long long)page,
+			       found ? "found" : "missing", found ? found->rank : 0,
+			       fast_ok ? "found" : "missing", fast_ok ? r : 0);
+			specasync_ft_fast_free();
+			return;
+		}
+	}
+	/* Negative side: the page just outside each range is unknown to both. */
+	for (k = 0; k < n; k++) {
+		u64 probes[2];
+		int p;
+
+		probes[0] = (g_ft_ranges[k].base_pfn - 1) << PAGE_SHIFT;
+		probes[1] = (g_ft_ranges[k].base_pfn + g_ft_ranges[k].len) << PAGE_SHIFT;
+		for (p = 0; p < 2; p++) {
+			bool in_bs, in_fast;
+
+			if (p == 0 && g_ft_ranges[k].base_pfn == 0)
+				continue;        /* no page below pfn 0 */
+			in_bs = bsearch(&probes[p], g_ft_sorted, g_ft_table_len,
+					sizeof(struct specasync_ft_sorted_entry),
+					cmp_ft_bsearch_key) != NULL;
+			in_fast = specasync_ft_fast_rank(probes[p], &r);
+
+			if (in_bs != in_fast) {
+				pr_err("specasync: ft_fast: equivalence FAILED on absent-page probe %llx (bsearch %d, range index %d); fast path disabled\n",
+				       (unsigned long long)probes[p], in_bs, in_fast);
+				specasync_ft_fast_free();
+				return;
+			}
+		}
+	}
+	g_specasync_ft_fast_verify_ns = ktime_get_ns() - t0;
+	atomic_set(&g_specasync_ft_fast_verified, 1);
+	smp_store_release(&g_ft_fast_active, true);   /* index stores visible before the flag */
+	pr_info("specasync: ft_fast: range index verified: %u pages, %u ranges, index %zu bytes, check %llu ns\n",
+		g_ft_table_len, n,
+		(size_t)n * sizeof(*g_ft_ranges) + (size_t)g_ft_table_len * sizeof(*g_ft_range_ranks),
+		(unsigned long long)g_specasync_ft_fast_verify_ns);
+}
+
 /*
  * Load a first-touch table built by tests/prepare_first_touch_table.py:
  *   u64 magic, u64 count, u64 first_touch[count]   (rank -> page)
@@ -731,6 +1030,9 @@
 	atomic_set(&g_ft_next_to_predict, 0);
 	pr_info("specasync: first-touch table loaded: %u distinct pages, lookahead=%d\n",
 		g_ft_table_len, specasync_ft_lookahead);
+	/* Gate E3a-2: build + verify the range index only when asked to. */
+	if (specasync_ft_fast == 1)
+		specasync_ft_fast_build_and_verify();
 	return 0;
 }
 
@@ -742,6 +1044,106 @@
  * again here anyway, defensively, since a wrong page lookup here would
  * silently mispredict rather than fail loudly.
  */
+/*
+ * Gate E3a-2: the fast path. Same observable behaviour as the slow path
+ * below -- same early return, same replay-order push, same g_ft_seq
+ * increment, same counter updates, same prediction, same ft-log push -- with
+ * the bsearch replaced by specasync_ft_fast_rank() and the cursor lock
+ * replaced by a bounded atomic_try_cmpxchg loop on the same atomic_t cursor.
+ *
+ * Each loop iteration computes, from the cursor value n it observed, exactly
+ * what the slow path computes under its lock:
+ *   skip:  if n <= r:  skipped = r + 1 - n,  n' = r + 1      (else n' = n)
+ *   then:  n' >= len        -> exhausted,  new cursor n'
+ *          n' <= r + L      -> predict table[n'],  new cursor n' + 1
+ *          otherwise        -> held,       new cursor n'
+ * and commits the new cursor with one cmpxchg(n -> new), even when
+ * new == n, so every decision is made against a cursor value that was
+ * current at the commit. Counters are updated only after a successful
+ * commit, so each is updated exactly once per call, exactly as the slow
+ * path updates it. On contention the cmpxchg reloads n and the decision is
+ * recomputed. The loop is bounded: after SPECASYNC_FT_FAST_MAX_TRIES
+ * failed commits the call returns 0 (no prediction, no cursor change) and
+ * counts g_specasync_ft_fast_cas_giveup. That can only happen under a
+ * concurrent cursor writer, which the single fault-servicing thread per
+ * GPU does not provide (see the g_ft_next_to_predict comment above).
+ *
+ * Touches only: the read-only table and range index, the cursor atomic,
+ * g_ft_seq, specasync counters, and the two existing diagnostic ring
+ * pushes the slow path also makes. No UVM state, no allocation, no lock.
+ */
+static u64 specasync_ft_predict_fast(u64 fault_addr)
+{
+	u64 page = fault_addr & ~((u64)PAGE_SIZE - 1);
+	u32 r, my_seq, n2 = 0, skipped = 0;
+	int old, newv = 0, tries;
+	bool did_skip = false;
+	enum { FT_EXHAUSTED, FT_PREDICT, FT_HELD } outcome = FT_HELD;
+	u64 result = 0;
+
+	if (!g_ft_table || g_ft_table_len == 0)
+		return 0;
+
+	specasync_replay_order_push(fault_addr);
+
+	my_seq = (u32)atomic_fetch_inc(&g_ft_seq);
+
+	if (!specasync_ft_fast_rank(page, &r)) {
+		atomic_inc(&g_specasync_ft_unknown_page);
+		return 0;
+	}
+
+	old = atomic_read(&g_ft_next_to_predict);
+	for (tries = 0; tries < SPECASYNC_FT_FAST_MAX_TRIES; tries++) {
+		n2 = (u32)old;
+		did_skip = false;
+		skipped = 0;
+		if (n2 <= r) {
+			skipped = r + 1 - n2;
+			n2 = r + 1;
+			did_skip = true;
+		}
+		if (n2 >= g_ft_table_len) {
+			outcome = FT_EXHAUSTED;
+			newv = (int)n2;
+		} else if (n2 <= r + (u32)specasync_ft_lookahead) {
+			outcome = FT_PREDICT;
+			newv = (int)(n2 + 1);
+		} else {
+			outcome = FT_HELD;
+			newv = (int)n2;
+		}
+		if (atomic_try_cmpxchg(&g_ft_next_to_predict, &old, newv))
+			break;
+		/* old now holds the current cursor; recompute from it. */
+	}
+	if (tries >= SPECASYNC_FT_FAST_MAX_TRIES) {
+		atomic_inc(&g_specasync_ft_fast_cas_giveup);
+		return 0;
+	}
+
+	if (did_skip)
+		atomic_add((int)skipped, &g_specasync_ft_skipped);
+
+	switch (outcome) {
+	case FT_EXHAUSTED:
+		atomic_inc(&g_specasync_ft_exhausted);
+		break;
+	case FT_PREDICT:
+		result = g_ft_table[n2];          /* n2 < g_ft_table_len by the branch above */
+		atomic_inc(&g_specasync_ft_predictions);
+		break;
+	case FT_HELD:
+		atomic_inc(&g_specasync_ft_held);
+		break;
+	}
+
+	if (outcome == FT_PREDICT)
+		specasync_ft_log_push(my_seq, n2);
+
+	return result;
+}
+
 u64 specasync_ft_predict(u64 fault_addr)
 {
 	u64 page = fault_addr & ~((u64)PAGE_SIZE - 1);
@@ -751,6 +1153,10 @@
 	u64 result = 0;
 	bool did_predict = false;
 
+	/* Gate E3a-2: verified fast path; otherwise exactly the original path below. */
+	if (smp_load_acquire(&g_ft_fast_active))
+		return specasync_ft_predict_fast(fault_addr);
+
 	if (!g_ft_table || g_ft_table_len == 0)
 		return 0;
 
@@ -1183,14 +1589,33 @@
 	debugfs_create_atomic_t("specasync_fault_already_resident", 0444, specasync_dir,
 				&g_specasync_fault_already_resident);
 
+	/* Gate E3a: speculative-width counters (see specasync_internal.h). */
+	debugfs_create_atomic_t("specasync_ft_same_region", 0444, specasync_dir,
+				&g_specasync_ft_same_region);
+	debugfs_create_atomic_t("specasync_spec_region_invalid", 0444, specasync_dir,
+				&g_specasync_spec_region_invalid);
+	debugfs_create_file_unsafe("specasync_spec_pages_requested", 0444, specasync_dir,
+				   NULL, &spec_pages_requested_fops);
+
+	/* Gate E3a-2: cheap-oracle outcome (see specasync_internal.h). */
+	debugfs_create_atomic_t("specasync_ft_fast_verified", 0444, specasync_dir,
+				&g_specasync_ft_fast_verified);
+	debugfs_create_u64("specasync_ft_fast_verify_ns", 0444, specasync_dir,
+			   &g_specasync_ft_fast_verify_ns);
+	debugfs_create_u32("specasync_ft_fast_nranges", 0444, specasync_dir,
+			   &g_specasync_ft_fast_nranges);
+	debugfs_create_atomic_t("specasync_ft_fast_cas_giveup", 0444, specasync_dir,
+				&g_specasync_ft_fast_cas_giveup);
+
 	if (specasync_policy == 4)
 		specasync_load_oracle_trace();
 	if (specasync_policy == SPECASYNC_POLICY_FIRST_TOUCH)
 		specasync_load_ft_table();
 
-	pr_info("specasync: init OK  log_enabled=%d policy=%d offload_depth=%d decomp=%d\n",
+	pr_info("specasync: init OK  log_enabled=%d policy=%d offload_depth=%d decomp=%d spec_width=%d ft_fast=%d(active=%d)\n",
 		specasync_log_enabled, specasync_policy, specasync_offload_depth,
-		SPECASYNC_DECOMP);
+		SPECASYNC_DECOMP, specasync_spec_width, specasync_ft_fast,
+		(int)READ_ONCE(g_ft_fast_active));
 	return 0;
 
 err_files:
@@ -1246,6 +1671,8 @@
 		g_oracle_trace = NULL;
 	}
 
+	/* Gate E3a-2: disable and free the range index before the table. */
+	specasync_ft_fast_free();
 	if (g_ft_table) {
 		vfree(g_ft_table);
 		g_ft_table = NULL;
Only in driver/src: specasync_faults_instrumentation.c
diff -u driver/src/specasync_internal.h driver/src-e3a/specasync_internal.h
--- driver/src/specasync_internal.h	2026-09-25 12:34:10.966964869 +0300
+++ driver/src-e3a/specasync_internal.h	2026-09-25 23:03:22.555211281 +0300
@@ -133,4 +133,58 @@
 u64  specasync_ft_predict(u64 fault_addr);
 extern int specasync_ft_lookahead;
 
+/*
+ * Gate E3a: speculative width W (pages). One speculative worker call makes
+ * the W-aligned region containing the predicted page resident, and policy 6
+ * does not enqueue a prediction whose region equals the last ENQUEUED
+ * prediction's region. W is validated at insmod (power of two in
+ * [1, SPECASYNC_SPEC_WIDTH_MAX]); invalid values make insmod fail. W = 1
+ * (default) takes exactly the pre-E3a code paths -- every new branch is
+ * guarded by specasync_spec_width > 1.
+ *
+ * specasync_spec_width_shift            log2(W), set by the same param setter
+ * g_specasync_last_regions[8]           region IDs (va >> (PAGE_SHIFT + shift))
+ * g_specasync_last_region_idx           of the last 8 ENQUEUED policy-6
+ *                                       predictions, round-robin insertion
+ *                                       (E3a-2 B2: the single last region
+ *                                       captured < 80% of an 8-region history
+ *                                       on Stencil at W = 64).
+ *                                       SPECASYNC_NO_REGION = empty slot.
+ *                                       Plain u64/u32 globals, written/read
+ *                                       only by the fault-servicing thread
+ *                                       (READ_ONCE/WRITE_ONCE), reset by
+ *                                       specasync_clear; no UVM state.
+ * g_specasync_ft_same_region            predictions not enqueued: same region
+ * g_specasync_spec_region_invalid       worker items skipped because the region
+ *                                       failed an explicit bounds/block check
+ * g_specasync_spec_pages_requested      sum of region sizes (pages) passed to
+ *                                       uvm_va_block_make_resident by the worker
+ */
+#define SPECASYNC_SPEC_WIDTH_MAX  512
+#define SPECASYNC_NO_REGION       (~0ULL)
+#define SPECASYNC_REGION_HISTORY  8     /* must be a power of two (index is masked) */
+extern int        specasync_spec_width;
+extern int        specasync_spec_width_shift;
+extern u64        g_specasync_last_regions[SPECASYNC_REGION_HISTORY];
+extern u32        g_specasync_last_region_idx;
+extern atomic_t   g_specasync_ft_same_region;
+extern atomic_t   g_specasync_spec_region_invalid;
+extern atomic64_t g_specasync_spec_pages_requested;
+
+/*
+ * Gate E3a-2: cheap first-touch oracle (specasync_ft_fast, 0444, 0|1,
+ * default 0). At 1, specasync_load_ft_table() builds a range index over the
+ * page-sorted table (maximal runs of consecutive pages: base pfn, length,
+ * offset into a u32 rank array), then looks up EVERY table page with both
+ * the range index and the existing bsearch; any single rank difference
+ * logs the first mismatch with pr_err, frees the index, and leaves the
+ * fast path disabled for this load. specasync_ft_predict() takes the fast
+ * path only when that check passed; at 0 (or on failure) it takes exactly
+ * the pre-E3a-2 path. The fast path takes no lock: the table and index are
+ * read-only after load, and the cursor (g_ft_next_to_predict) is advanced
+ * with a bounded atomic_try_cmpxchg loop that reproduces the slow path's
+ * skip / predict / held / exhausted rule and counter updates exactly.
+ */
+extern int specasync_ft_fast;
+
 #endif /* SPECASYNC_INTERNAL_H */
diff -u driver/src/uvm_gpu_replayable_faults.c driver/src-e3a/uvm_gpu_replayable_faults.c
--- driver/src/uvm_gpu_replayable_faults.c	2026-09-25 12:41:43.763793118 +0300
+++ driver/src-e3a/uvm_gpu_replayable_faults.c	2026-09-25 23:03:36.006661548 +0300
@@ -22,6 +22,7 @@
 *******************************************************************************/
 
 #include "linux/sort.h"
+#include <linux/log2.h>   /* Gate E3a: is_power_of_2() */
 #include "nv_uvm_interface.h"
 #include "uvm_common.h"
 #include "uvm_linux.h"
@@ -276,6 +277,50 @@
 	uvm_gpu_t                  *gpu;  /* retained; NULL at depth=0, set at depth>=1 */
 };
 
+/*
+ * Gate E3a: the W-aligned region of va_block that contains pidx, for W =
+ * specasync_spec_width > 1. Every bound that the UVM helpers only
+ * UVM_ASSERT (non-fatal in release builds) -- uvm_va_block_region() checks
+ * first <= outer; uvm_va_block_num_cpu_pages() checks the block size;
+ * uvm_page_mask_region_fill() checks nothing at all (raw bitmap_set on the
+ * caller's 512-bit mask) -- is checked here explicitly. Also refuses any
+ * block that is not a managed, non-HMM block: the only kind this worker has
+ * been run on, and the only kind for which make_resident with ctx->mm == NULL
+ * is the verified W = 1 configuration. Returns false on any violation; the
+ * caller then skips the item (no lock taken, no make_resident call) and
+ * counts it in g_specasync_spec_region_invalid.
+ */
+static bool specasync_width_region(uvm_va_block_t *va_block,
+				   uvm_page_index_t pidx,
+				   uvm_va_block_region_t *out)
+{
+	size_t w, npages, first, outer;
+
+	if (!va_block || !out)
+		return false;
+	if (uvm_va_block_is_hmm(va_block) || !va_block->managed_range)
+		return false;
+	if (va_block->end < va_block->start)
+		return false;
+
+	w = (size_t)specasync_spec_width;
+	if (w < 2 || w > SPECASYNC_SPEC_WIDTH_MAX || !is_power_of_2(w))
+		return false;
+
+	npages = (size_t)((va_block->end - va_block->start + 1) >> PAGE_SHIFT);
+	if (npages == 0 || npages > PAGES_PER_UVM_VA_BLOCK || (size_t)pidx >= npages)
+		return false;
+
+	first = (size_t)pidx & ~(w - 1);
+	outer = min(first + w, npages);
+	if (first > (size_t)pidx || outer <= (size_t)pidx ||
+	    outer > npages || outer > PAGES_PER_UVM_VA_BLOCK)
+		return false;
+
+	*out = uvm_va_block_region((uvm_page_index_t)first, (uvm_page_index_t)outer);
+	return true;
+}
+
 static void specasync_worker_fn(struct work_struct *work)
 {
 	struct spec_work_item  *item = container_of(work, struct spec_work_item, work);
@@ -313,20 +358,48 @@
 			uvm_page_mask_t      pmask;
 			uvm_page_index_t     pidx;
 			NV_STATUS            mstatus = NV_ERR_BUSY_RETRY;
+			/*
+			 * Gate E3a: sregion is exactly the pre-E3a region
+			 * (region_for_page(pidx)) and pmask exactly the pre-E3a
+			 * one-bit mask unless W > 1.
+			 */
+			uvm_va_block_region_t sregion;
+			bool                 sregion_ok = true;
 
 			uvm_va_block_context_init(ctx, NULL);
 			pidx = uvm_va_block_cpu_page_index(va_block, item->speculative_addr);
+			sregion = uvm_va_block_region_for_page(pidx);
 			uvm_page_mask_zero(&pmask);
-			uvm_page_mask_set(&pmask, pidx);
+			if (specasync_spec_width > 1) {
+				sregion_ok = specasync_width_region(va_block, pidx, &sregion);
+				if (sregion_ok)
+					uvm_page_mask_region_fill(&pmask, sregion);
+				else
+					atomic_inc(&g_specasync_spec_region_invalid);
+			} else {
+				uvm_page_mask_set(&pmask, pidx);
+			}
 			uvm_va_block_retry_init(&retry);
 
-			if (uvm_mutex_trylock(&va_block->lock)) {
-				mstatus = uvm_va_block_make_resident(
-					va_block, &retry, ctx,
-					item->gpu->id,
-					uvm_va_block_region_for_page(pidx),
-					&pmask, NULL,
-					UVM_MAKE_RESIDENT_CAUSE_PREFETCH);
+			if (sregion_ok && uvm_mutex_trylock(&va_block->lock)) {
+				/*
+				 * Gate E3a: at W > 1, re-check liveness under the
+				 * block lock (block kill clears managed_range) before
+				 * handing make_resident a multi-page region. W = 1
+				 * never takes this branch.
+				 */
+				if (specasync_spec_width > 1 && uvm_va_block_is_dead(va_block)) {
+					atomic_inc(&g_specasync_spec_region_invalid);
+				} else {
+					mstatus = uvm_va_block_make_resident(
+						va_block, &retry, ctx,
+						item->gpu->id,
+						sregion,
+						&pmask, NULL,
+						UVM_MAKE_RESIDENT_CAUSE_PREFETCH);
+					atomic64_add((s64)uvm_va_block_region_num_pages(sregion),
+						     &g_specasync_spec_pages_requested);
+				}
 				uvm_va_block_retry_deinit(&retry, va_block);
 				uvm_mutex_unlock(&va_block->lock);
 			} else {
@@ -379,7 +452,12 @@
 
 /* ---- Enqueue helper ----------------------------------------------- */
 
-static void specasync_enqueue(uvm_va_space_t *va_space, u64 spec_addr,
+/*
+ * Gate E3a: returns true iff a work item was queued. The return value is new;
+ * every side effect (counters, ring fields, allocation, queueing) is
+ * unchanged. Pre-E3a callers ignore it.
+ */
+static bool specasync_enqueue(uvm_va_space_t *va_space, u64 spec_addr,
 			      struct specasync_hit_table *hit_table,
 			      struct specasync_batch_record *sa_rec,
 			      uvm_gpu_t *gpu)
@@ -388,11 +466,11 @@
 	u64 t0;
 
 	if (!g_specasync_wq || specasync_policy == 0 || spec_addr == 0)
-		return;
+		return false;
 	if (atomic_read(&g_specasync_queue_depth) >= SPECASYNC_MAX_QUEUE_DEPTH) {
 		sa_rec->spec_drops++;
 		atomic_inc(&g_specasync_drops);
-		return;
+		return false;
 	}
 
 	t0   = ktime_get_ns();
@@ -400,7 +478,7 @@
 	if (!item) {
 		sa_rec->spec_drops++;
 		atomic_inc(&g_specasync_drops);
-		return;
+		return false;
 	}
 
 	INIT_WORK(&item->work, specasync_worker_fn);
@@ -418,8 +496,23 @@
 	sa_rec->spec_enqueues++;
 	atomic_inc(&g_specasync_enqueued);
 	sa_rec->enqueue_overhead_ns += (u32)(ktime_get_ns() - t0);
+	return true;
 }
 
+/*
+ * Gate E3a: W divides the VA-block page count, so a W-aligned region of a
+ * 2MB-aligned block never crosses the block. The worker still checks every
+ * region bound explicitly at runtime (see specasync_width_region()).
+ */
+static_assert(SPECASYNC_SPEC_WIDTH_MAX <= PAGES_PER_UVM_VA_BLOCK,
+	      "spec width must not exceed a VA block");
+static_assert(PAGES_PER_UVM_VA_BLOCK % SPECASYNC_SPEC_WIDTH_MAX == 0,
+	      "spec width max must divide the VA block page count");
+/* Gate E3a-2: the region-history slot index is masked, so it must be 2^k. */
+static_assert(SPECASYNC_REGION_HISTORY > 0 &&
+	      (SPECASYNC_REGION_HISTORY & (SPECASYNC_REGION_HISTORY - 1)) == 0,
+	      "region history size must be a power of two");
+
 /* ---- Compile-time ABI sanity checks -------------------------------- */
 static_assert(sizeof(struct specasync_batch_record) == 72,
 	      "specasync_batch_record size mismatch — update Python BATCH_FMT");
@@ -2677,7 +2770,45 @@
                 struct specasync_hit_table *_ht =
                     (_fe->va_space->specasync_pred) ?
                     _fe->va_space->specasync_pred->hit_table : NULL;
-                specasync_enqueue(_fe->va_space, _spec_addr, _ht, &_sa_rec, _fe->gpu);
+                /*
+                 * Gate E3a / E3a-2: at W > 1, policy 6 does not enqueue a
+                 * prediction whose W-page region equals any of the last
+                 * SPECASYNC_REGION_HISTORY ENQUEUED predictions' regions.
+                 * Touches no UVM state: locals, specasync globals, one
+                 * counter. The match is recorded in _seen and the `continue`
+                 * sits OUTSIDE the inner _k loop, so it targets this _fi loop
+                 * (a `continue` inside the _k loop would only advance _k).
+                 * At W = 1 this branch is never taken and the call below is
+                 * exactly the pre-E3a call.
+                 */
+                if (specasync_spec_width > 1 &&
+                    specasync_policy == SPECASYNC_POLICY_FIRST_TOUCH &&
+                    _spec_addr != 0) {
+                    u64 _rid = _spec_addr >> (PAGE_SHIFT + specasync_spec_width_shift);
+                    bool _seen = false;
+                    u32 _k;
+
+                    for (_k = 0; _k < SPECASYNC_REGION_HISTORY; _k++) {
+                        if (READ_ONCE(g_specasync_last_regions[_k]) == _rid) {
+                            _seen = true;
+                            break;
+                        }
+                    }
+                    if (_seen) {
+                        atomic_inc(&g_specasync_ft_same_region);
+                        continue;
+                    }
+                    if (specasync_enqueue(_fe->va_space, _spec_addr, _ht, &_sa_rec, _fe->gpu)) {
+                        u32 _slot = READ_ONCE(g_specasync_last_region_idx) &
+                                    (SPECASYNC_REGION_HISTORY - 1);
+
+                        WRITE_ONCE(g_specasync_last_regions[_slot], _rid);
+                        WRITE_ONCE(g_specasync_last_region_idx,
+                                   (_slot + 1) & (SPECASYNC_REGION_HISTORY - 1));
+                    }
+                } else {
+                    specasync_enqueue(_fe->va_space, _spec_addr, _ht, &_sa_rec, _fe->gpu);
+                }
             }
         }
     }
```
