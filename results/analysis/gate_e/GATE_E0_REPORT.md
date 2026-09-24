# Gate E0 — Inventory and feasibility

No benchmark runs, no driver changes. Read-only investigation of
`driver/src/`, existing committed reports, and the repo's on-disk trace
artifacts, per `GATE_E_PLAN.md`'s instructions. Answers the six numbered
questions in order, then reports one significant finding beyond their literal
scope (Section 7) that changes how Gap 1 should be read.

---

## 1. What does the fault trace actually record?

Source: `driver/src/uvm_gpu_replayable_faults.c`, `service_fault_batch()`.

The recording call is:

```
2645:    for (i = 0; i < batch_context->num_coalesced_faults;) {
...
2652:        specasync_trace_push(current_entry->fault_address);
...
2819:        i += block_faults;
```

`specasync_trace_push()` (`driver/src/specasync_telemetry.h:377-388`) is
called **once per iteration of this outer loop**, i.e. once per call to
`service_fault_batch_dispatch()`. That dispatch call groups every coalesced
fault belonging to the same `va_block`/`va_range` into one service call and
returns the count consumed as `block_faults` (`service_fault_batch_dispatch`,
`driver/src/uvm_gpu_replayable_faults.c:2309` on; the grouping loop is
`service_fault_batch_ats_sub`, ~2260-2303, which breaks the group only on a
`va_space`/`gpu` change or address exceeding `outer`). The loop then advances
`i += block_faults` (line 2819), so the *next* `trace_push` fires on the
first coalesced fault of the *next* group, not the next individual fault.

So the trace records **one address per va-block dispatch group — the first
coalesced fault of each group — not one entry per raw hardware fault, and not
one entry per coalesced fault either.** Two collapsing steps happen before an
address ever reaches the trace:

1. **Coalescing** (`fetch_fault_buffer_entries`,
   `driver/src/uvm_gpu_replayable_faults.c:1214-1352`): raw hardware fault
   buffer entries (`num_cached_faults`) with the same instance pointer and
   page address are merged into one representative entry
   (`num_coalesced_faults ≤ num_cached_faults`, comment at 1195-1213).
2. **Dispatch grouping** (this section): consecutive coalesced faults on the
   same va_block/va_range are serviced — and trace-recorded — as one group
   (`num_coalesced_faults` further collapsed to "number of dispatch groups").

Neither step is deduplication of *repeated* addresses across the run (a page
that faults twice at different times gets traced twice, once per group it
falls in); both are within-batch collapsing of *simultaneously present*
faults. This directly answers question 2 below — it is not deduplication in
the global-uniqueness sense the plan document raised as a possibility, and it
is not per-page recording either.

## 2. Reconciling trace length against fault count

The plan's stated committed trace sizes are correct — verified directly, not
assumed:

| trace | path | size | entries (verified: size/8) |
|---|---|---|---|
| Stencil-24K | `results/phaseB2/gate3_interleaved/c3_bench_stencil_trace.bin` | 2,215,688 B | 276,961 |
| GraphBFS-23 | `results/phaseB2/gate3_interleaved/c3_bench_graph_bfs_trace.bin` | 1,660,512 B | 207,564 |

(`results/analysis/GATE_A_report.md:24-28` independently confirms both against
`git status` and a dmesg line; reproduced here by direct arithmetic on the
committed files, not transcribed.)

**Note found in passing, not part of the reconciliation:** `oracles/Stencil/24000/oracle_trace.bin`
(27,125 entries) and `oracles/GraphBFS/23/oracle_trace.bin` (41,672 entries)
are *different, older* trace files for the same nominal benchmark/size,
dated Jun 13 vs. the Aug 10 headline files above. They were produced by
`scripts/collect_oracle_traces.sh` and were never used for the T1/T4 headline
C3 measurements (confirmed by `GATE_A_report.md`'s explicit path reference).
They are stale artifacts of an earlier collection pass, not a second
reconciliation target — flagged only so nobody later assumes they are
interchangeable with the committed headline traces.

Using the per-dispatch-group recording established in §1, entry count should
scale with **the number of dispatch groups in the run**, not with raw or
coalesced fault count. From the closest available same-platform,
same-benchmark, same-policy (C3/oracle) fault counts — `results/analysis/GATE_T4_REPORT.md`'s
doubly-corrected clean-rep figures (Tesla T4, the platform these trace files
were collected on, per `GATE_A_report.md`):

| workload | coalesced faults / run (C3) | trace entries | groups-per-entry ratio |
|---|---:|---:|---:|
| Stencil-24K | 3,237,375 (rep 1, clean, pre-saturation) | 276,961 | ≈ 11.7 |
| GraphBFS-23 | 445,721 (mean of 4 clean reps) | 207,564 | ≈ 2.1 |

These are not the byte-identical run that produced the committed trace files
(the trace files are dated Aug 10 16:01/16:22; the fault counts come from a
separate `t4_prefetch_off_telemetry.sh` session referenced in
`GATE_T4_REPORT.md`) — stated explicitly as an order-of-magnitude
reconciliation using the best available same-platform/benchmark/policy data,
not an exact per-run match.

The gap is explained: Stencil's structured, spatially regular access pattern
groups roughly 12 coalesced faults into each va-block dispatch on average;
GraphBFS's irregular traversal groups only about 2. Neither number involves
ring truncation — 276,961 and 207,564 are both far below the 1,048,576-slot
ring capacity (§3), so **the small entry count relative to fault count is a
recording-granularity artifact, not a capacity artifact.** This is a
different mechanism than either possibility the plan raised (deduplication or
per-page recording), and it does **not** mean the headline traces are
complete in a stronger sense — see §7, which found the opposite for a
different reason.

## 3. Ring inventory

Source: `driver/src/specasync_telemetry.h` (struct/constant definitions),
`driver/src/specasync_debugfs.c` (allocation, read, clear).

| ring | capacity | entry size | total bytes | allocator | overwrite vs. drop |
|---|---:|---:|---:|---|---|
| `specasync_batch_ring` (`specasync_log`) | 131,072 (`SPECASYNC_BATCH_RING_SLOTS = 1<<17`) | 72 B | 9,437,184 B (~9 MiB) | `kvmalloc_array`, `GFP_KERNEL\|__GFP_ZERO` (`alloc_batch_ring`, debugfs.c:377) | **drop-on-full** |
| `specasync_work_ring` (`specasync_worker_log`) | 131,072 (`SPECASYNC_WORK_RING_SLOTS = 1<<17`) | 48 B | 6,291,456 B (~6 MiB) | `kvmalloc_array` (`alloc_work_ring`, debugfs.c:390) | **drop-on-full** |
| `specasync_decomp_ring` (`specasync_decomp_log`) | 131,072 (`SPECASYNC_DECOMP_RING_SLOTS = 1<<17`) | 112 B | 14,680,064 B (~14 MiB) | `kvmalloc_array` (`alloc_decomp_ring`, debugfs.c:403) | **drop-on-full** |
| `specasync_trace_ring` (`specasync_fault_trace`) | 1,048,576 (`SPECASYNC_TRACE_RING_SLOTS = 1<<20`) | 8 B | 8,388,608 B (8 MiB) | `kvmalloc_array` (`alloc_trace_ring`, debugfs.c:416) | **pure overwrite, never drops** |

All four allocation sites are compile-time constants baked into
`specasync_telemetry.h`; none is currently a module parameter (contrast with
`specasync_trace_faults` and `specasync_oracle_trace_path`, which are).

**Overwrite-vs-drop mechanics, verified from `specasync_telemetry.h`:**

- The batch, work, and decomp rings each carry an explicit `tail` field and a
  `drops` counter. Their push functions (`specasync_batch_ring_push`,
  `specasync_work_ring_push`, `specasync_decomp_ring_push`, lines 211-270)
  all share the same guard: `if (((head - tail) & mask) == mask) drops++;
  else { write; head++; }` — i.e. they never overwrite unread data; once full
  they silently drop and count it. Their `tail` is advanced **nowhere** except
  reset to 0 in `clear_write()` (debugfs.c:234-249) — the debugfs read path
  (`ring_read_binary`, lines 78-127) is an explicit snapshot read that does
  not drain the ring (documented in its own comment, lines 70-77). So in
  practice these three rings fill once per `specasync_clear` interval and then
  drop everything until the next clear — this matches the already-documented
  behaviour in `specasync_internal.h:44-53` ("confirmed to saturate within
  ~3-8% of a real oversubscribed run's wall-clock").
- The trace ring has **no `tail` field at all** (struct at
  `specasync_telemetry.h:367-372`). `specasync_trace_push` (377-388)
  unconditionally does `buf[head & mask] = va_addr; head++;` with no
  full/drop check and no drop counter. It is a genuine circular overwrite
  buffer: once `head` exceeds capacity, older entries are silently
  overwritten, and there is no way to detect that this happened from the
  ring's own state (no drop counter, no saturation flag).

**Read-time behaviour that compounds this (relevant to Gate E2's coverage
check, and to §7):** `trace_ring_read()` (debugfs.c:429-453) clamps the
reported byte count to at most `SPECASYNC_TRACE_RING_SLOTS` entries, then
copies from **physical offset 0 of the buffer**, in physical slot order —
it does not rotate the read to start at the oldest surviving entry
(`head % mask`). When `head` (the raw push count) exceeds capacity, physical
slot `k` holds whichever push most recently mapped to `k & mask`; reading the
buffer linearly from slot 0 therefore returns the correct *set* of the last
N pushes but in a **cyclically rotated order** (rotated by `head mod N`
places), not true chronological order, except in the coincidental case where
`head` is an exact multiple of N. `scripts/collect_oracle_traces.sh:51`
(`cp "${DEBUGFS}/specasync_fault_trace" "${outdir}/raw_fault_trace.bin"`)
performs no reordering — the file written to disk, and later loaded verbatim
as `oracle_trace.bin`, is whatever `trace_ring_read` returned. So a truncated
collection does not merely "repeat a small, misaligned slice" as the plan
describes; it repeats a slice that is *itself internally rotated* relative
to true temporal order, with the rotation offset depending on the exact total
push count of that particular run. This refines rather than contradicts the
plan's Gap 1 characterization.

This finding — trace-ring truncation with no drop counter and no
saturation flag — was already identified informally in this project before
Gate E: `tests/t_b9_task2_analyze.py:30-33` and
`tests/t_b9_task2_mechanism.sh:32-39` both describe the same 1,048,576-slot
true-circular-overwrite behaviour for `specasync_fault_trace`, in the context
of Gate B9. Gate E0 confirms that description directly against source (it was
correct) and adds the read-order rotation detail, which those two files do
not mention.

## 4. Can the trace ring be enlarged, and how far?

**What changing capacity requires**, found by tracing every reference to
`SPECASYNC_TRACE_RING_SLOTS`:

1. `alloc_trace_ring()` (debugfs.c:416-426): sizing already comes from the
   constant into a runtime `kvmalloc_array` call — trivially parameterizable,
   already using an allocator (`kvmalloc_array`, which falls back to
   `vmalloc` for large, physically-discontiguous requests) that has no
   contiguity ceiling worth worrying about at the sizes discussed below.
2. `g_trace_ring.mask = SPECASYNC_TRACE_RING_SLOTS - 1` (same site) and every
   use of `head & mask` in `specasync_trace_push` and `trace_ring_read`
   **require the slot count to remain a power of two** — a module parameter
   would need to round up to the next power of two (or the mask-indexing
   scheme would need to become a modulo, at a small per-push cost on a hot
   IRQ-context path, which is not free).
3. `trace_ring_read()`'s clamp (`if (head > SPECASYNC_TRACE_RING_SLOTS) head
   = SPECASYNC_TRACE_RING_SLOTS;`, debugfs.c:442-443) hard-codes the constant
   directly and must be changed to read the ring's actual configured size
   (e.g. `mask + 1`) instead.
4. The oracle *replay* side (`specasync_load_oracle_trace`,
   `specasync_oracle_next_addr[_n]`, debugfs.c:285-373) already derives its
   length (`g_oracle_trace_len`) from the loaded file's byte size, independent
   of `SPECASYNC_TRACE_RING_SLOTS` — **no change needed there**; it already
   scales to whatever file is handed to it. This means E2's "enlarge the
   ring" step only needs to touch the *collection* side.
5. No test or script outside `specasync_debugfs.c` hard-codes the 1,048,576 /
   8,388,608 figures as a *behavioral* assumption — `tests/t_b9_task2_analyze.py:67`
   and `tests/t_b9_task2_mechanism.sh` reference the constant only
   descriptively/for their own saturation-coverage math, not as something a
   ring-size change would silently break.

**Feasibility on this host:** current `MemAvailable` is 59,224,988 kB (~56.5
GiB), `free -h` shows 52 GiB free / 56 GiB available (checked at the time of
this report, not during a run). Both the collection ring and a loaded oracle
replay array are separate allocations that **can coexist within a single
module load** when `specasync_policy=4` (the trace ring is unconditionally
allocated in `specasync_debugfs_init()`; the oracle trace is loaded
immediately after, in the same function, if `specasync_policy == 4` at load
time — debugfs.c:472-548). Worst case per module load is therefore
`ring_bytes + oracle_file_bytes`, not just one or the other.

Given E0's own fault-count findings (§5): the largest committed coalesced-fault
count for any config/iters cell is C1 at iters=20, 237,933,775
(`OVERSUB_C3_VERIFICATION.md`, Arm cleanliness table). Rounding up to the next
power of two gives 2^28 = 268,435,456 slots → 2,147,483,648 B (2 GiB) for the
ring, and up to the same again for a same-sized loaded oracle file — **≈4 GiB
worst case per module load**, comfortably inside the current 56.5 GiB
available and far under the standing 6 GiB `MemAvailable` abort floor, even
accounting for the documented ~244 MB/reload leak across a multi-reload
sweep. This is a recommendation for E2 to size against, not a claim that
2^28 covers every cell E2 might want — it does not cover C3's higher counts at
the same iters values (up to 91,791,947 — well under 2^28 already) nor any
untested iters value beyond 20.

## 5. Fault counts for sizing

All figures below are **coalesced-fault counts read from the global atomic
`g_specasync_demand_faults`** (immune to ring saturation by construction —
see `specasync_internal.h:44-53`), transcribed from the cited reports, not
recomputed from raw telemetry. None are ring-derived; none are flagged
unreliable for that reason. Figures are organized by source report since
three separate sessions each covered a different part of the iters range —
none is a single continuous sweep.

**Normal-size, non-oversubscribed (T1/T4 platform, Tesla T4):**

| workload | config | coalesced faults / run |
|---|---|---:|
| Stencil-24K | C1 | 69,485,036 (`GATE_T4_REPORT.md:20`, 15-rep aggregate, **ring-duplicated total, see below**) |
| Stencil-24K | C1 | 3,237,375 (rep 1 only, clean pre-saturation single rep — the reliable figure) |
| GraphBFS-23 | C1 | 25,146,428 (`GATE_T4_REPORT.md:21`, 15-rep aggregate, **ring-duplicated total**) |
| Stencil-24K | C3 (oracle) | 70,655,453 (`GATE_T4_REPORT.md:22`, 15-rep aggregate, **ring-duplicated total**) |
| Stencil-24K | C3 (oracle) | 3,237,375 (rep 1, clean) |
| GraphBFS-23 | C3 (oracle) | 24,918,253 (`GATE_T4_REPORT.md:23`, 15-rep aggregate, **ring-duplicated total**) |
| GraphBFS-23 | C3 (oracle) | 446,165 / 445,004 / 446,415 / 445,300 (reps 1-4, clean) |

**Flagged as unreliable, explicitly:** the four 15-rep-aggregate figures above
are marked in their own source (`GATE_T4_REPORT.md`'s correction banner,
lines 60-67, and `RATE_MISMATCH_VERIFICATION.md`'s banner, lines 1-8) as
**ring-duplicated totals** — `specasync_log`'s 131,071-record ring saturates
partway through the 15-rep session (rep 2 for Stencil, rep 5 for GraphBFS)
and every subsequent read is the same frozen snapshot re-counted, not
independent data. Only the single-rep clean figures are usable as "one run's
fault count." These are reproduced here exactly as both source reports
present them post-correction; no new arithmetic performed on them.

**Oversubscribed, N=48000 (~1.078× VRAM), 5070 Ti platform:**

| iters | C0 | C1 | C3 | C4 | source |
|---:|---:|---:|---:|---:|---|
| 1  | 1,098,046  | 12,526,687  | 12,618,079  | 1,106,449 (diff. session, see below) | `OVERSUB_C3_VERIFICATION.md:107-121` (C0/C1/C3); `GATE_B10_AUGMENTATION.md` (C4) |
| 3  | 3,323,826  | 37,990,336  | 23,221,368  | — | `OVERSUB_C3_VERIFICATION.md` |
| 5  | 5,542,226  | 61,635,336  | 31,999,020  | 5,219,138 | `OVERSUB_C3_VERIFICATION.md` (C0/C1/C3); `GATE_B10_AUGMENTATION.md` (C4) |
| 8  | 8,877,089  | —  | —  | 5,549,156 | `GATE_B10_REPLICATION.md:103-110` (Task D) |
| 10 | 11,090,636 | 123,477,977 | 59,043,611 | — | `OVERSUB_C3_VERIFICATION.md` |
| 12 | 13,312,036 | —  | —  | 12,857,574 | `GATE_B10_REPLICATION.md` |
| 16 | 17,726,063 | —  | —  | 16,724,754 | `GATE_B10_REPLICATION.md` |
| 20 | 22,184,264 | 237,933,775 | 91,791,947 | 11,302,805 (original) / 11,330,794 (replication) | `OVERSUB_C3_VERIFICATION.md` (C0/C1/C3); `GATE_B10_AUGMENTATION.md` + `GATE_B10_REPLICATION.md` (C4) |

Note the two C0 iters=1 and iters=20 figures differ slightly between the
`OVERSUB_C3_VERIFICATION.md` session (1,098,046 / 22,184,264) and the
`GATE_B10_AUGMENTATION.md`/`GATE_B10_REPLICATION.md` sessions (1,102,370 /
22,176,986 and 22,188,388) — different sessions, different reloads, same
config; the ~0.03-0.4% spread is consistent with ordinary run-to-run
variation already characterized elsewhere in this project, not a
discrepancy requiring resolution here. Not one of these six iters values
(1,3,5,8,10,12,16,20) was tested with all four configs (C0,C1,C3,C4)
simultaneously in one session — C1/C3 only exist at {1,3,5,10,20}; C4 only
exists at {1,5,8,12,16,20}. **Gate E2's sweep, if it wants all four arms at
the same iters values, cannot simply reuse this data — it needs fresh
interleaved runs**, per the standing interleaving rule anyway.

**Sizing implication for E2:** at iters=20, C1's 237,933,775 coalesced faults
is the largest figure in this table, ~227× the trace ring's current 1,048,576
capacity — confirming the plan's premise that iters=20 cannot be captured
without enlarging the ring. At the smallest tested iters=1, even C1
(12,526,687) already exceeds ring capacity by ~12×, and C0's own iters=1
figure (1,098,046-1,106,449) is already close to the ring's 1,048,576
capacity — **there may be no iters value in this oversubscribed regime at
N=48000 where an unmodified ring captures a complete trace**, a stronger
constraint than the plan's framing (which treated "does iters=20 fit" as the
open question).

## 6. Does the replay cursor wrap?

Confirmed from source, `driver/src/specasync_debugfs.c:335-373`. Both replay
functions index with `% g_oracle_trace_len`:

```
342:    idx = atomic_fetch_inc(&g_oracle_idx) % (int)g_oracle_trace_len;
...
371:    return g_oracle_trace[((unsigned)(old + (int)consumed)) % (unsigned)len];
```

When the trace is shorter than the run, it **wraps and repeats from the
start** — there is no stop condition and no error path; both functions return
`0` only if no trace is loaded at all (`g_oracle_trace_len == 0`,
lines 339, 362), never as an end-of-trace signal. This confirms the plan's
description exactly. §7 below shows this wrap can trigger even when the
*ring* (recording side) never overflowed.

## 7. Significant finding beyond the six questions: recording/consumption granularity mismatch means the T1 headline traces also wrap during replay

The plan states the T1 headline traces (276,961 and 207,564 entries) are
"complete" because they are "well under" the 1,048,576-entry ring capacity,
and treats truncation as an oversubscription-only problem. Tracing the
*consumption* side of the oracle policy shows this is not correct for either
headline workload.

The oracle replay cursor is advanced from a different, earlier loop than the
one that populates the trace. Per-fault prediction happens in
`service_fault_batch()`'s "Gate 1" loop
(`driver/src/uvm_gpu_replayable_faults.c:2617-2637`), which iterates **every
coalesced fault** individually:

```
2633:            u64 _spec_addr = specasync_predict_next(_fe->va_space,
                                                          _fe->fault_address, 1);
```

`specasync_predict_next(va_space, fault_addr, batch_faults)` is defined at
line 172; its oracle branch is:

```
240:    case 4: /* oracle */
...
250:            return specasync_oracle_next_addr_n(batch_faults);
```

Called with the literal `1` from line 2633 — so **one call, and one
cursor advance, per coalesced fault** (the code's own comment at
`uvm_gpu_replayable_faults.c` above this loop calls this "true per-fault
trace alignment," meaning per-*coalesced*-fault, not per-dispatch-group).

But §1 established that `specasync_trace_push()` — the function that
*populated* the trace file being replayed — fires only once per **dispatch
group**, not once per coalesced fault. Recording stride and replay-consumption
stride are different units of the same trace array: recording advances by 1
per group (≈12 coalesced faults, on average, for Stencil-24K; ≈2 for
GraphBFS-23, per §2); replay consumption advances by 1 per coalesced fault.

Consequence: over a full run, the oracle cursor advances by the run's total
**coalesced-fault count**, not its dispatch-group count. Using the same
clean single-rep C3 figures already cited in §2 and §5:

| workload | trace entries | coalesced faults / run (C3, same platform) | cursor wraps per run |
|---|---:|---:|---:|
| Stencil-24K | 276,961 | 3,237,375 (rep 1, clean) | ≈ 11.7× |
| GraphBFS-23 | 207,564 | 445,721 (mean of 4 clean reps) | ≈ 2.1× |

**The T1 headline oracle measurements replay a trace that wraps roughly 12
times (Stencil-24K) or 2 times (GraphBFS-23) over the course of a single
run — despite the recording ring itself never overflowing.** This is a
different mechanism from Gap 1 as the plan states it (ring capacity exceeded
during collection), but produces the same symptom (a short, repeating,
non-representative prediction sequence) and applies to exactly the runs the
plan currently treats as unaffected.

This is reported as a finding, not adjudicated further — Gate E0's brief is
inventory, not experiments. It matters directly for Gate E1: E1's plan
already calls for collecting a **fresh** oracle trace in-session under
`prefetch=1` rather than reusing either headline trace, which sidesteps this
specific instance, but the same recording/consumption mismatch will apply to
that fresh trace too unless E1's run is short enough (in coalesced-fault
terms) to stay under whatever dispatch-group count the fresh collection
produces — E1 should check trace-entries-vs-coalesced-faults for its own
collected trace, not just trace-entries-vs-ring-capacity, before trusting its
"trace entry count < ring capacity" assertion as sufficient evidence of a
non-wrapping replay.

---

## Summary of answers

1. One trace entry per va-block dispatch group (first coalesced fault of the
   group), not per raw fault, not per coalesced fault, not deduplicated by
   address across the run.
2. The 276,961/207,564 entry counts are confirmed correct against the
   committed files and against `GATE_A_report.md`. The gap versus fault count
   is explained by dispatch-group recording granularity (§1), not by ring
   truncation (both are far under capacity) and not by address deduplication.
3. Four rings, all `kvmalloc_array`-backed compile-time constants: three
   (batch/work/decomp, 131,072 slots each) are true drop-on-full with an
   explicit drop counter and a `tail` that is never advanced by the reader;
   one (trace, 1,048,576 slots) is a pure circular overwrite with no tail, no
   drop counter, and a read path that does not correct for rotation once
   wrapped.
4. Enlargeable: needs a module parameter, power-of-two rounding (or a modulo
   replacement for the mask trick), and fixing one hard-coded constant
   reference in the read path (`trace_ring_read`'s clamp). The replay side
   needs no change — it already scales to file size. ~2 GiB (2^28 slots)
   covers every committed fault count in this repo with margin; total
   worst-case footprint per module load (ring + loaded replay file) ≈4 GiB,
   comfortably inside this host's current 56.5 GiB available.
5. Full table above; normal-size 15-rep aggregates are explicitly flagged
   unreliable (ring-saturated duplicates) per their own source reports;
   single-rep and global-atomic figures are the reliable ones. No existing
   session tested all four configs at the same set of iters values.
6. Confirmed: both replay functions wrap via `% g_oracle_trace_len`
   unconditionally; no stop condition; repeats from the start indefinitely.
7. (Beyond the six questions.) The T1 headline oracle traces, while never
   truncated during recording, are replayed with a cursor that advances
   roughly 6-12× faster (in per-run terms) than they were recorded, because
   recording and consumption operate at different granularities. Both
   headline runs wrap the "complete" trace multiple times during a single
   replay.

No driver changes were made. No benchmark was run. All figures above are
either read directly from source, computed by direct arithmetic on committed
files (trace byte counts / 8), or transcribed from cited existing reports
with their own reliability caveats preserved.
