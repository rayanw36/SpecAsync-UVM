# Gate E0.9a-2 — Why are no faults prevented?

This gate was interrupted mid-session by a real kernel crash caused by its
own instrumentation, on the user's physical machine. **The crash, its
cause, and its fix are documented in full below (§4) and were reported
before this gate resumed.** The user rebooted the machine; system health
was confirmed (fresh boot, `nvidia_uvm` refcount 0, no crash traces) before
any further work. Checks B, C, and D below were completed **after** the
reboot, with the fix applied and re-verified on the smallest, lowest-risk
case first before returning to the exact configuration that had crashed.

All work: RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34-generic (updated
by a routine OS update between sessions; rebuilt against the matching
`/usr/src/linux-headers-7.0.0-34-generic`, confirmed by vermagic match),
headless (`systemctl isolate multi-user.target`, this session's shell
confirmed running under `tmux` on a non-X pty beforehand), restored to
`graphical.target` at the end (confirmed active, `nvidia-smi` working).
`MemAvailable` logged (61.1-61.2 GB across this session's runs, no drift).
Every replay: fresh module reload, `setarch -R`, `specasync_clear` before
the rep, and — following the crash — a `timeout` wrapper on every benchmark
invocation as an added safety margin not present in earlier gates.

## 0. Push confirmation

E0.9a (`b467448`) was confirmed pushed before this gate began. The crash
incident and its fix (`f7d3153`, `ea1a262`) were committed and pushed
**before** the reboot was requested, per the standing rule that a genuine
safety event gets reported immediately rather than folded into a larger
batch. This report's own commit is pushed at the end of this gate.

## 1. Two corrections (E0.9a not edited)

**Both accepted as stated, without qualification.**

- E0.9a's "0% prevented is an artifact of Stencil's 2.6x revisit structure"
  is withdrawn. E0.8 established the repeats are duplicate storms
  (p10-p90 gaps of exactly 1), not spread-out revisits — if speculation
  made a page resident *and usable* before its first touch, there would be
  no storm and no fault. 0% prevented is a real, measured result. (Check A,
  done before any run, and Check B's data, below, both independently
  explain *why* it is 0% — not "why the measure can't see a nonzero value.")
- E0.9a's "21,600-fault reduction is directionally right" is withdrawn.
  E0.8's noise floor (plain-C1-vs-C1: 1,247-4,418; replay-vs-trace:
  ~43,000-44,000) contains a single-run difference of 21,600. It is not
  evidence in either direction on its own.

## 2. Policy 6 — accepted permanently, no further action.

## 3. Check A — source reading, prediction stated before any run

(Unchanged from the version reported before the crash — this section did
not depend on the run that crashed and stands as originally written.)

Traced both paths from source, by function and line:

**Speculative path**: `specasync_worker_fn()`
(`driver/src/uvm_gpu_replayable_faults.c:279-378`) calls
`uvm_va_block_make_resident()` at line 324. That function
(`uvm_va_block.c:4968-4995`) calls only `uvm_va_block_make_resident_copy()`
and `uvm_va_block_make_resident_finish()` (`uvm_va_block.c:4911-4959`) —
data movement and residency bookkeeping. Its own comment states the
opposite of installing a mapping: "Any move operation implies that mappings
have been removed from all non-UVM-Lite GPUs" (`uvm_va_block.c:4886-4887`).

**Demand path**: `uvm_va_block_service_locked()` (`uvm_va_block.c:12021-
12070`) calls `uvm_va_block_service_copy()` then `uvm_va_block_service_
finish()` (`uvm_va_block.c:11926-~11995`), whose own numbered comments
name step 3 — `block_service_finish_map()` (`uvm_va_block.c:11770`) — as
"Map requesting processor with the necessary privileges." This is the only
mapping call in either path's call graph.

**Prediction, stated before Check B ran: H-map holds.** Prevented faults
should stay near 0 at every L, structurally; `fault_already_resident`
should rise with L and track `spec_migrations`.

## 4. The crash: full account

### What happened

Implementing `fault_already_resident` per the gate's own instruction
("place it in the demand-fault servicing path... validate it before
trusting it"), the very first validation run (C1 control, meant to confirm
the counter reads ~0 before it was trusted anywhere else) caused a kernel
NULL-pointer oops:

```c
// The version that crashed:
if (uvm_page_mask_test(uvm_va_block_resident_mask_get(va_block, gpu->id, NUMA_NO_NODE), page_index))
    atomic_inc(&g_specasync_fault_already_resident);
```

### Root cause

`uvm_va_block_resident_mask_get()` (`uvm_va_block.c:2275-2297`) does:

```c
gpu_state = uvm_va_block_gpu_state_get(block, processor);
UVM_ASSERT(gpu_state);
resident_mask = &gpu_state->resident;
```

`UVM_ASSERT` is a soft, non-fatal check in a production build. When this
GPU had never had any page of this `va_block` resident before, `gpu_state`
was genuinely `NULL`; the assert was silently survived; and because
`resident` is the *first* member of `uvm_va_block_gpu_state_t`,
`&gpu_state->resident` evaluated to `NULL` exactly — not a small offset.
That `NULL` was returned to the new code and passed straight into
`uvm_page_mask_test()` with no check.

**Crash signature** (`dmesg`, in full): `BUG: kernel NULL pointer
dereference, address: 0000000000000000`; `RIP: uvm_page_mask_test+0xc/0x20
[nvidia_uvm]`; `RDI: 0000000000000000`; call trace
`service_fault_batch_block_locked` → `service_fault_batch_dispatch` →
`service_fault_batch` → `uvm_parent_gpu_service_replayable_faults` →
`replayable_faults_isr_bottom_half` (interrupt bottom-half context);
`Tainted: G OE` (single oops, not a panic); **`note: UVM GPU1 BH[20671]
exited with irqs disabled`** — the kernel thread responsible for servicing
GPU1's replayable faults was killed mid-service by the fault handler.

### Impact, and what was and was not done in response

Observed directly, not inferred:

- The triggering process (`bench_stencil 24000`) hung at ~99% CPU
  afterward, waiting on a fault a now-dead thread could never service.
  Killed with plain `kill -9` (own process, no `sudo` needed) — confirmed
  it became a zombie.
- `/sys/module/nvidia_uvm/refcnt` read **4** before and after, and did not
  clear.
- No further kernel messages appeared over several minutes of watching —
  no cascading panic. Shell access (this session, over `tmux`) stayed
  fully responsive throughout.
- `graphical.target` was **not** restored after the crash — judged riskier
  than leaving the system on `multi-user.target`, reachable over the
  existing session, pending the user's decision.
- **No further `rmmod`/`insmod` was attempted after the crash.** The fix
  was written, compiled, and committed, but explicitly reported as
  "not loaded, not tested" pending the user's review.
- The user was told directly and immediately, before any further gate
  work: what happened, the current (degraded but stable) system state, and
  a recommendation to reboot — stated as a recommendation, since rebooting
  the user's machine is exactly the kind of action requiring their
  explicit decision, not this session's.

### The fix, and its post-reboot verification

```c
if (uvm_va_block_gpu_state_get(va_block, gpu->id) &&
    uvm_page_mask_test(uvm_va_block_resident_mask_get(va_block, gpu->id, NUMA_NO_NODE), page_index))
    atomic_inc(&g_specasync_fault_already_resident);
```

`uvm_va_block_gpu_state_get()` (`uvm_va_block.h:682-685`) is a plain,
non-asserting array read (`return va_block->gpus[uvm_id_gpu_index(gpu_id)];`).
"No GPU state yet for this block" and "not resident" are the same fact
here, so this is the semantically correct check, not merely the safe one.

**Verified after the reboot, in ascending order of risk, before returning
to the exact configuration that had crashed:**

1. `group_probe` (N=8, the smallest, fastest case) under the fixed module,
   C1: no crash, `fault_already_resident=0` (correct — a fresh probe has
   no prior residency at all, exactly the previously-NULL case, now
   handled safely).
2. Stencil-24K C1 — **the exact configuration that crashed** — under the
   fixed module: no crash, `demand_faults=2,938,754`,
   `fault_already_resident=0`. `dmesg` showed only the module-load lines,
   nothing else.
3. The full Check B/C/D sweep below, all clean.

## 5. Check B — the sweep, both workloads

C1 control (both workloads, required before trusting the counter
anywhere else): **`fault_already_resident = 0` exactly**, both workloads.
Not "near zero" — exactly zero.

### Stencil-24K, depth=1, L ∈ {1, 16, 256, 4096} (fresh table: 1,125,000
distinct pages, matching E0.8 exactly)

| L | demand_faults | enqueued | spec_hits | spec_migrations | ft_predictions | ft_skipped | ft_held | ft_exhausted | **fault_already_resident** | match to spec_migrations |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2,892,440 | 141,484 | 130,878 | 130,928 | 141,484 | 983,516 | 2,750,917 | 39 | **130,928** | 100.0000% |
| 16 | 2,901,823 | 418,849 | 332,542 | 334,000 | 418,849 | 706,151 | 2,482,864 | 110 | **333,844** | 99.9533% |
| 256 | 3,006,455 | 1,124,999 | 436,965 | 851,828 | 1,124,999 | 1 | 1,880,586 | 870 | **851,739** | 99.9896% |
| 4096 | 2,994,349 | 923,563 | 836 | 923,016 | 1,124,999 | 1 | 1,858,311 | 11,039 | **923,016** | 100.0000% |

Depth=0 control at L=4096: `spec_migrations=0`, `fault_already_resident=0`,
despite identical prediction volume (`ft_predictions=1,124,999`) to the
depth=1 run — confirms the counter tracks real migration, not prediction
volume alone.

### GraphBFS-23, depth=1, L ∈ {1, 16, 256, 4096} (fresh table: 287,956
distinct pages, matching E0.8 exactly)

| L | demand_faults | enqueued | spec_hits | spec_migrations | ft_predictions | ft_skipped | ft_held | ft_exhausted | **fault_already_resident** | match |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 481,658 | 9,041 | 2,407 | 2,686 | 9,041 | 278,915 | 467,014 | 5,603 | **2,686** | 100.0000% |
| 16 | 481,652 | 9,967 | 3,086 | 3,582 | 9,967 | 277,989 | 441,029 | 30,656 | **3,582** | 100.0000% |
| 256 | 484,725 | 15,016 | 5,800 | 8,298 | 15,016 | 272,940 | 437,263 | 32,446 | **8,297** | 99.9879% |
| 4096 | 477,162 | 74,865 | 1,453 | 65,925 | 74,865 | 213,091 | 365,696 | 36,601 | **65,923** | 99.9970% |

### Reading against §4 of the gate's brief

**`fault_already_resident` tracks `spec_migrations` almost exactly (≥99.95%
match) at every L, on both workloads.** This is the H-map row of the
reading guide: *prevented stays 0; already-resident rises with L (tracking
migrations)*. The small (<0.1%) gaps are consistent with a handful of
migrated pages being evicted again (or otherwise losing residency) before
their demand fault arrives, at the largest L values where the gap between
prediction and actual use is thousands of faults wide — not measurement
noise in the counter itself, which agrees with `spec_migrations` to within
a few units on every run.

**A second, unplanned finding from the same table**: `spec_hits` collapses
at large L on Stencil (436,965 at L=256 down to 836 at L=4096) even as
`spec_migrations` and `fault_already_resident` both keep climbing. `spec_
hits` requires the hit-table entry to still be within its 10ms staleness
window when the real fault arrives; at L=4096 a prediction can run
thousands of faults ahead of the demand stream it's targeting, long enough
for that entry to go stale regardless of whether the migration itself
succeeded and is still resident. This is a second, independent way `spec_
hits` undercounts real speculative effect, beyond the "can't count a fault
that never happened" problem this whole gate exists to fix —
`fault_already_resident` (and, for GraphBFS, `spec_migrations` directly)
remain reliable at every L where `spec_hits` is not.

## 6. Check C — achieved lead at large L

| workload | L | valid pairs | min | p10 | median | p90 | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| Stencil-24K | 256 | 1,124,999 | 1 | 228 | 246 | 255 | **256** |
| Stencil-24K | 4096 | 1,124,999 | 1 | 4,067 | 4,085 | 4,095 | **4,096** |
| GraphBFS-23 | 1 | 9,041 | 1 | 1 | 1 | 1 | 1 |
| GraphBFS-23 | 16 | 9,967 | 1 | 1 | 1 | 7 | 16 |
| GraphBFS-23 | 256 | 15,016 | 1 | 1 | 1 | 225 | 256 |
| GraphBFS-23 | 4096 | 74,865 | 1 | 1 | 3,656 | 4,067 | 4,096 |

**Stencil-24K's lead saturates tightly against the cap at both L=256 and
L=4096** (median within 96% of L in both cases) — no saturation point
found up to 4,096; the sweep's top end is not redundant for this workload.

**GraphBFS-23's lead distribution is bimodal, not saturating the same
way**: the median sits at 1 for L up to 256 (most predictions get
immediately overtaken by demand) while p90 tracks close to the cap — a
minority of predictions achieve deep lookahead while the majority don't
get the chance to. Only at L=4096 does the median itself climb
substantially (3,656). This is consistent with E0.8's finding that
GraphBFS's fault order is far less stable than Stencil's (Kendall 0.968 vs.
~1.0, ~13% vs. ~0.01% max rank displacement) — frequent skip-corrections
reset the cursor close to current demand for most faults, and only a
subset of runs of locally-consistent order let it pull ahead.

## 7. Check D — GraphBFS-23 completion

All measures now computed and internally consistent, completing E0.9a's
outstanding acceptance gap:

| L | usefulness | prevented |
|---:|---:|---:|
| 1 | 100.0000% | **0.0000%** |
| 16 | 100.0000% | **0.0000%** |
| 256 | 100.0000% | **0.0000%** |
| 4096 | 100.0000% | **0.0000%** |

**Prevented faults are exactly 0.0000% at every L, on both workloads.**
Combined with §5's counter table (fault_already_resident tracking
migrations almost exactly at every L) and §3's source reading, this is now
confirmed three independent ways: from source (the mapping call doesn't
exist in the speculative path), from the aggregate counter
(fault_already_resident ≈ spec_migrations, not ≈ 0), and from the
per-prediction measure (prevented = 0 even at 923,016 successful
migrations on Stencil and 65,925 on GraphBFS). Fault-level and rank-level
counter identities (`predictions+held+unknown+exhausted=demand_faults`;
`predictions+skipped=distinct_pages`) were spot-checked on the GraphBFS L=1
and L=4096 rows above and hold exactly, as they did for Stencil in E0.9a.

## 8. Win metric for E0.9b — H-map confirmed, stated plainly

**H-map holds, on both workloads, confirmed by source and by data at four
lookahead values spanning three orders of magnitude (1 to 4,096).**
H-race does not hold: prevented faults do not rise with L; they are
identically zero regardless of how much lead the oracle achieves or how
many migrations succeed.

**Prevented faults must not be used as E0.9b's win metric — it is
structurally zero under this driver's current mapping architecture,
independent of prediction quality or timeliness.** `fault_already_resident`
is the candidate mechanism metric, with this understanding stated
explicitly: **the most speculation can do here is make a fault cheaper
(residency-only, no data movement) — it can never eliminate the fault
under `uvm_va_block_make_resident()`'s current design, because the mapping
step lives exclusively in the demand path.** Wall-clock remains the only
outcome of record for E0.9b; `fault_already_resident` and `spec_migrations`
are the mechanism counters that should accompany it, not substitute for
it.

## 9. Structural finding, flagged for the claim documents (not edited)

**Off-path staging that updates residency without installing a mapping can
reduce the cost of a fault but can never eliminate one, under this UVM
driver's current design.** This is not a timing/race property of this
project's specific worker implementation (the dispatch-latency race the
paper already documents) — it is a property of which UVM function the
worker calls (`uvm_va_block_make_resident()`) versus which one owns
mapping (`uvm_va_block_service_finish()`, demand-path-only). No amount of
lookahead, prediction accuracy, or timeliness changes this; confirmed
directly at L=4096 with near-total speculative coverage on both workloads.
Flagged for `CLAIM_SCOPE.md` and the manuscript's discussion of what any
off-path speculative design can achieve on this driver, at review.

## Flags for review (not edited)

- The crash itself (§4) is catalog material: a real, physical-machine
  kernel crash caused by an unchecked NULL from a function whose own
  internal safety check (`UVM_ASSERT`) is silently non-fatal in production
  — worth a general note about this driver's assert conventions for anyone
  else instrumenting it.
- §9's structural finding bears directly on `CLAIM_SCOPE.md`'s framing of
  what speculation could achieve if better-timed; the answer here is
  "cheaper, never absent," under the current worker design.

## Artifacts

- `driver/src/uvm_gpu_replayable_faults.c` — buggy version (commit
  `f7d3153`) and fixed, now-verified version (commit `ea1a262`, this
  report's data).
- Raw traces/tables/logs: `results/phaseB1/gate_e09a2_validation/`
  (gitignored per convention, reconstructible from this report's commands).

**HARD STOP.** No oracle design, no E0.9b pre-registration in this gate.
The win-metric decision (§8) is offered as a recommendation from confirmed
source and data, for review before it goes into E0.9b's pre-registration.
