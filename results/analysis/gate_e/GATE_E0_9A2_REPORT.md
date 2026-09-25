# Gate E0.9a-2 — Why are no faults prevented?

**Interrupted by a real kernel crash triggered by this gate's own
instrumentation, on first exercise, on the user's physical machine.**
Checks B/C/D were not completed. This report covers what was done before
the crash (§0-§4's source reading and prediction) and the incident itself
in full; Checks B (data)/C/D are not started. **Hard stop — this gate ends
here, pending the user's decision on system recovery.**

## 0. Push confirmation

`b467448` (E0.9a) was confirmed pushed and matching `origin/manuscript-prep`
before this gate began.

## 1. The two corrections (recorded; E0.9a not edited)

**Correction 1 accepted as stated.** E0.9a attributed the 0% prevented-fault
result to Stencil's ~2.6x revisit structure making the measure insensitive.
Withdrawn. E0.8 established the repeats are duplicate storms (p10-p90 gaps
of exactly 1), not spread-out iteration revisits — if speculation made a
page resident *and usable* before its first touch, there would be no storm
and no fault. The 2.6x structure exists precisely because pages were not
ready in time. 0% prevented is a real result, not an artifact of what was
measured. (Check A below, done before any run, independently explains
*why* it is 0% — see §3.)

**Correction 2 accepted as stated.** The 21,600-fault reduction at depth=1
(Stencil, L=1) is withdrawn as "directionally right." E0.8 measured
plain-C1-vs-C1 count differences of 1,247-4,418, and replay-vs-trace
differences of ~43,000-44,000. A single-run difference of 21,600 sits
inside the range spanned by those two noise sources and is not evidence in
either direction on its own.

## 2. Policy 6 accepted permanently

Noted per instruction: the policy-5-vs-6 substitution from E0.9a is
accepted as correct and permanent. No further action needed on that point.

## 3. Check A — source reading, prediction stated before any run

Traced the worker's depth=1 path against the demand path's, both from
source, both cited by function and line:

**Speculative path** (`driver/src/uvm_gpu_replayable_faults.c`,
`specasync_worker_fn()`, lines 279-378): at depth≥1, calls
`uvm_va_block_make_resident()` (line 324) directly. That function
(`/usr/src/nvidia-595.91.07/nvidia-uvm/uvm_va_block.c:4968-4995`) calls only
`uvm_va_block_make_resident_copy()` (moves data) and
`uvm_va_block_make_resident_finish()` (`uvm_va_block.c:4911-4959`, updates
residency bookkeeping, breaks read-duplication, updates eviction
heuristics). **Neither function, nor anything in `uvm_va_block_make_
resident()`'s call graph, calls a mapping function.** The
`make_resident_finish()` code explicitly documents the opposite direction:
"Any move operation implies that mappings have been removed from all
non-UVM-Lite GPUs" (`uvm_va_block.c:4886-4887`) — migration invalidates
mappings, it does not create the new one.

**Demand path** (`uvm_va_block_service_locked()`, `uvm_va_block.c:12021-
12070`): calls `uvm_va_block_service_copy()` then `uvm_va_block_service_
finish()` (`uvm_va_block.c:11926-~11995`). `service_finish()`'s own
numbered comments are explicit: step 1 computes mapping protections, step 2
revokes stale permissions, **step 3 — `block_service_finish_map()`
(`uvm_va_block.c:11770`) — "Map requesting processor with the necessary
privileges."** This is the only call, anywhere in either path, that
installs a GPU page-table mapping.

**Answers to Check A's three questions:**

1. Does the worker install a mapping, or only make the page resident? —
   **Only makes it resident.** Confirmed by exhaustive call-graph tracing,
   not by absence of a keyword search.
2. Permissions / skip / defer / revoke conditions on the worker's mapping —
   **N/A.** There is no mapping attempt in this path to skip; it is
   structurally absent, not conditionally bypassed.
3. How does the demand path treat a fault on an already-resident-but-
   unmapped page, and at what relative cost? — It goes through the same
   `uvm_va_block_service_locked()` → `service_copy()` → `service_finish()`
   chain as any other fault. `service_copy()`'s migration step
   (`uvm_va_block_make_resident_copy()`, called again on the demand path)
   is expected to detect the page already resident at the destination and
   skip the data movement (this specific skip-when-resident code path was
   not traced to the instruction level, given the crash below cut this
   check short — flagged as not fully verified, not assumed). Cost is
   therefore expected to be "cheap relative to a real migration" but
   **not zero** — `service_finish()`'s mapping step still runs
   unconditionally.

**Prediction, stated before Check B ran, per instruction: H-map holds.**
Prevented faults should stay near 0 at every L, structurally, because the
speculative path can never eliminate the demand-side mapping step no matter
how early or how successfully it runs. `fault_already_resident` should rise
with L instead, tracking `spec_migrations`.

## 4. Check B, C, D: not completed — the incident

### What happened

Implementing the `fault_already_resident` counter (per §4 of the gate
prompt: "Place it in the demand-fault servicing path... describe exactly
where and what condition it tests"), the check was placed in
`uvm_gpu_replayable_faults.c`'s per-fault demand-service loop, immediately
after the existing `uvm_va_block_page_is_gpu_authorized()` check had
already ruled out "already mapped" for this fault:

```c
if (uvm_page_mask_test(uvm_va_block_resident_mask_get(va_block, gpu->id, NUMA_NO_NODE), page_index))
    atomic_inc(&g_specasync_fault_already_resident);
```

This compiled clean, with no warnings, against 595.91.07. **On its first
execution** (the very first attempted validation run, C1 control on
Stencil-24K, meant to confirm the counter reads ~0 before trusting it
anywhere else — exactly the validation step the gate's own instructions
required before interpreting the counter), **it caused a kernel NULL-
pointer dereference oops inside `uvm_page_mask_test()`, called from
`service_fault_batch_block_locked()`, in interrupt/bottom-half context, on
the user's physical machine.**

### Root cause

`uvm_va_block_resident_mask_get()` (`uvm_va_block.c:2275-2297`) derefs the
block's per-GPU state unconditionally:

```c
gpu_state = uvm_va_block_gpu_state_get(block, processor);
UVM_ASSERT(gpu_state);
resident_mask = &gpu_state->resident;
```

`UVM_ASSERT` is a soft, non-fatal check in a production build — it logs (or
no-ops) rather than halting. When this GPU has never had any page of this
particular `va_block` resident before, `gpu_state` is genuinely `NULL`, the
assert is silently survived, and — because `resident` is the *first*
member of `uvm_va_block_gpu_state_t` — `&gpu_state->resident` evaluates to
`NULL` too, not a small nonzero offset. `uvm_va_block_resident_mask_get()`
therefore returned a bare `NULL` pointer to my code, which passed it
straight into `uvm_page_mask_test()` with no check. The crash occurred on
the very first coalesced fault that hit this specific condition — early in
the very first validation run, matching the ~2 second gap between module
load and the oops in `dmesg`.

**This was a real, avoidable bug in code this session wrote and did not
validate carefully enough before running against real hardware.** The
gate's own standing rule — "validate any new counter against a
configuration where its expected value is known before interpreting it
elsewhere" — was being followed in spirit (a C1 control run was the very
first thing attempted), but the validation run itself was the one that
crashed, because the bug was in the counter's *implementation*, not in its
interpretation.

### System impact, and what was and was not done about it

`dmesg` showed a single oops (`Tainted: G OE`, `#PF: supervisor read
access`, not a full panic) with the note **"UVM GPU1 BH[20671] exited with
irqs disabled"** — the kernel thread responsible for servicing GPU1's
replayable faults was killed by the fault handler mid-service. Consequences
observed directly, not inferred:

- The triggering process (`bench_stencil 24000`) hung at 99% CPU
  afterward, waiting on a fault that could never be serviced by a thread
  that no longer existed. Killed directly (`kill -9`, no `sudo` needed —
  own process); confirmed it became a zombie, not that it released its
  driver references.
- `/sys/module/nvidia_uvm/refcnt` read **4** before and after killing that
  process, and did not decrease. The module cannot be safely `rmmod`'d in
  this state, and was not attempted.
- No further kernel messages appeared after the initial oops (checked
  repeatedly over several minutes) — the system did not cascade into a
  full panic or hang. Shell access (this session, over `tmux`) remained
  fully responsive throughout, and remains so now.
- **`graphical.target` was not restored.** With the GPU1 fault-servicing
  thread dead and the module's refcount stuck, attempting to bring back
  Xorg/gdm (which would need to open and use `/dev/nvidia*` again) risked
  hanging that attempt too, for no offsetting benefit. The system is left
  on `multi-user.target`, stable and reachable, pending the user's own
  decision.
- **No further module reload, rmmod, or insmod was attempted after the
  crash.** The fix below was compiled but not loaded or tested.

**This machine most likely needs a reboot to fully recover GPU
functionality**, given a kernel worker thread died while holding driver
state and the module's reference count is not clearing on its own. This is
stated as a recommendation, not an action taken — rebooting the user's
machine is exactly the kind of hard-to-reverse, high-blast-radius action
this project's standing rules require checking in for, and it has not been
done.

### The fix

Guard with the non-asserting, plain-lookup accessor
(`uvm_va_block_gpu_state_get()`, a `static inline` array read in
`uvm_va_block.h:682-685`, no assert) before calling the function that
dereferences it:

```c
if (uvm_va_block_gpu_state_get(va_block, gpu->id) &&
    uvm_page_mask_test(uvm_va_block_resident_mask_get(va_block, gpu->id, NUMA_NO_NODE), page_index))
    atomic_inc(&g_specasync_fault_already_resident);
```

"No GPU state yet for this block" and "not resident" are the same fact
here, so this is the semantically correct check, not merely the safe one.
Compiled clean against 595.91.07 (srcversion `5997D238EF080B77DBD2AAF`).
**Not loaded, not tested, not run — this fix is unverified until the
machine is in a known-good state again.** Saved as
`driver/build/595.91.07/nvidia-uvm-specasync-NEW-e0.9a2-fixed.ko`
(gitignored, reproducible from the committed, fixed source).

## What remains

Checks B (data), C, and D are **not done**. The source-level H-map
prediction in §3 stands on its own (it does not depend on any run), but is
unconfirmed empirically. §7's win-metric proposal cannot be finalized
without Check B's data — stated as a recommendation contingent on the
source reading holding up once it's safe to test again:

**If Check A's source reading is confirmed by data (still to be run):**
`prevented faults` is structurally near-zero and must not be used as
E0.9b's win metric. `fault_already_resident` is the candidate mechanism
metric, with the explicit understanding that the most speculation can do
under this driver's current mapping architecture is make a fault cheaper,
never remove it — and that wall-clock remains the only outcome of record
either way. This is offered as a preliminary reading from source alone,
explicitly not yet confirmed by the data this gate was supposed to collect.

## Flags for review (not edited)

- **This incident itself belongs in the catalog and in the paper's methods/
  safety notes once reviewed**: a speculative-migration path that updates
  residency without updating the GPU page-table mapping is exactly the
  structural asymmetry §3 traces from source, and the crash is a direct,
  literal consequence of code that assumed the two always happened
  together.
- If the source reading holds, `CLAIM_SCOPE.md`'s treatment of what
  speculation can and cannot achieve under this driver should be read
  against §3: it is not just that speculation is currently mistimed
  (a race the paper already documents) — under this specific mapping
  architecture, even perfectly-timed speculation cannot eliminate a fault,
  only cheapen it.

## Artifacts

- `driver/src/uvm_gpu_replayable_faults.c`,
  `specasync_debugfs.c`, `specasync_internal.h` — `fault_already_resident`
  counter, buggy version run (commit `f7d3153`) and fixed version (this
  report's commit), neither loaded/tested past the crash.
- `driver/build/595.91.07/nvidia-uvm-specasync-NEW-e0.9a2-fixed.ko` — built,
  gitignored, **unloaded, untested**.

**HARD STOP.** Recommending: (1) the user reboot the machine at their
convenience to clear the wedged `nvidia_uvm` state; (2) review this
incident and the fix before any further module loading is attempted;
(3) Checks B/C/D re-attempted only after both of those, in a fresh
session.
