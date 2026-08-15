# Gate B9 Task 2 — three new full-run atomics, RTX 5070 Ti rebuild

Platform: local RTX 5070 Ti, Blackwell (sm_120), driver 595.84, kernel 7.0.0-28-generic.

## Why

`GATE_B9_OVERSUB_MECHANISM.md`'s Task 2 mechanism run found `specasync_log` /
`specasync_worker_log` / `specasync_decomp_log` (131,072-slot, drop-on-full rings)
saturate within the first ~3-8% of a full oversubscribed run's wall-clock
(N=48000/iters=20: C1 captured 2.8%, C3 captured 7.9% — see `ARTIFACT_CATALOG.md`'s
"Second occurrence of artifact #7"). A periodic-drain redesign was built and smoke-
tested next, and that surfaced a second, independent problem: the debugfs
read-then-clear pattern is not atomic, and a real ~30ms gap between the two
separate `sudo` subprocess calls loses ~1.2% of records per drain boundary under
this workload's fault rate — confirmed by exact `batch_id` gap detection, not
inferred.

Two kernel-side fixes were evaluated (consumer-cursor ring semantics vs.
enlarging the rings) and neither was adopted for now — see "Deferred: consumer-
cursor ring semantics" below for the full assessment, kept for the record.
Instead: three of the five metrics Task 2 needs turned out to have a single,
unambiguous per-event increment site already in the source, making a true
kernel-side atomic (same pattern as the existing Task A1 counters
`g_specasync_processed`/`enqueued`/`drops`) trivial to add. Atomics are immune to
ring saturation by construction — this sidesteps the whole problem for the
metrics it can reach.

## What was added

Three new `atomic_t` globals in `uvm_gpu_replayable_faults.c`, declared alongside
the existing three (`g_specasync_processed` et al.), extern-declared in
`specasync_internal.h`, exposed read-only via `debugfs_create_atomic_t` in
`specasync_debugfs.c`, and reset by `specasync_clear` alongside the existing three
— exactly the Task A1 pattern, no new mechanism introduced.

| Atomic | debugfs path | Increment site | Semantics |
|---|---|---|---|
| `g_specasync_demand_faults` | `specasync_demand_faults` | `uvm_gpu_replayable_faults.c:2800` (`atomic_add(block_faults, ...)`, right next to `_sa_rec.num_faults += block_faults`) | Total demand faults serviced. Runs unconditionally, independent of `specasync_policy` — valid for C1 too. |
| `g_specasync_spec_hits` | `specasync_spec_hits` | Same loop as `_sa_rec.spec_hits`, `uvm_gpu_replayable_faults.c:2807-2811` (`atomic_inc` when `specasync_hit_table_consume()` returns 1) | Total speculative hit-table hits. |
| `g_specasync_spec_migrations` | `specasync_spec_migrations` | `uvm_gpu_replayable_faults.c:330-332` (`atomic_inc` when `mstatus == NV_OK`) | Total **successful speculative** migrations only (depth>=1 worker-issued `uvm_va_block_make_resident()` returning `NV_OK`). Does **not** count demand-path migrations (C1's entire workload, and C3's own fallback path) — those run through stock UVM's `make_resident`/`service_fault_batch_block` with zero specasync instrumentation. See "What stays ring-derived" below. |

## Build

`SRC=/usr/src/nvidia-595.84 WORK=/home/rayenchikhaoui/build/nvidia-595.84-specasync NV_KERNEL_MODULES="nvidia nvidia-uvm nvidia-modeset nvidia-drm nvidia-peermem" bash driver/scripts/reconstruct_build_tree.sh` — full 5-module build (the `nvidia-uvm`-alone default hits a conftest-registration gap on this platform's kernel, already documented in `GATE_B6_TASK1_REBUILD.md`; only `nvidia-uvm.ko` was ever unloaded/reloaded, `nvidia`/`nvidia-modeset`/`nvidia-drm` stayed the running instances the desktop session was already using). Clean build, no errors.

**New srcversion: `4488C9F6F75570BB2FB34F8`** — differs from the srcversion every
prior Gate B9 result in this session was measured under
(`9E98EF08CBA769C50A24937`, itself the Gate B6 Task 1 rebuild that added the
original three A1 atomics). **Provenance**: Task 1 (output equivalence) and the
original (ring-limited) Task 2 mechanism run were measured under
`9E98EF08CBA769C50A24937`; everything from this point forward in Gate B9 —
including the relaunched Task 2b iteration sweep — runs under
`4488C9F6F75570BB2FB34F8`.

## Verification

| Check | Result |
|---|---|
| New srcversion differs from `9E98EF08CBA769C50A24937` | **`4488C9F6F75570BB2FB34F8`** — differs |
| `nm` shows all 6 atomics (3 new + 3 existing) | All present, confirmed before load |
| Three new debugfs files exist and are readable | `/sys/kernel/debug/specasync/specasync_{demand_faults,spec_hits,spec_migrations}` all readable, all `0` post-reload/pre-probe |
| Zero dmesg warnings | Confirmed — only the expected `specasync: init OK ...` / `nvidia-uvm: SpecAsync-UVM v595 port loaded` pair per reload |

## Validation: atomic counts vs. ring-derived counts, at a scale the ring cannot wrap

`tests/hit_probe.cu` / `run_hit_probe.sh` (the project's existing deterministic
positive control: 256 pages, stride 1, serialized full-sync-between-touches
adjacent policy) — 256 events is far below the 131,072-slot ring capacity on any
of the three rings, so this is a clean, non-wrapped, exact comparison.

**Pass 1 — policy=1 (adjacent), depth=0** (demand faults + hits; no migration possible at depth=0):

| Metric | Ring-derived (`specasync_parse.py` summary) | Atomic | Match |
|---|---:|---:|:---:|
| demand faults | 256 | 256 | **exact** |
| spec_hits | 255 | 255 | **exact** |
| hit rate | 0.9961 (255/256) | — | matches Gate A / `GATE_B6_TASK1_REBUILD.md`'s 99.61% |

**Pass 2 — policy=1 (adjacent), depth=1** (exercises the migration path):

| Metric | Ring-derived | Atomic | Match |
|---|---:|---:|:---:|
| demand faults | 256 | 256 | **exact** |
| spec_hits | 1 | 1 | **exact** |
| spec_migrations | 1 (`migration_done` count in `worker.bin`) | 1 | **exact** |

(Side observation, not chased further here: under serialized single-page-at-a-time
touches at depth=1, 255/256 speculative migration attempts came back
`THROTTLED` rather than `MIGRATION_DONE` — lock contention between the worker and
the near-simultaneous demand path. Consistent with `SPECASYNC_RESULT_THROTTLED`
existing as a real, common outcome, not a rare edge case.)

Both passes: exact agreement, zero drift, at a scale where the ring reads are
themselves known-complete (well under capacity). This is not proof the atomics
stay correct under the ring-saturating conditions Task 2 actually needs them
for — it's proof the increment logic itself is correct, which is what a
same-run, non-wrapped comparison can establish. The whole point of adding these
atomics is that they don't need the ring to stay valid at scale.

## What stays ring-derived (not fixed by this change)

- **Eviction count**: no counter exists anywhere in this driver source, ring or
  atomic. The only eviction-adjacent reference in `driver/src/` is a comment
  (`uvm_gpu_replayable_faults.c:1926`); the actual eviction logic lives inside
  stock UVM's `uvm_va_block_make_resident`, which is not present in this
  driver/src checkout. Adding a counter there would require source outside what
  this project currently patches — out of scope here, not engineered around.
- **Thrash (pages migrated more than once)**: categorically cannot be a single
  atomic — it needs per-page state (a counter per VA/page), not a running total.
  `specasync_hit_table` (256 slots, unconditional overwrite-on-insert, 10ms
  staleness) is sized for a small sliding window of recent speculative
  addresses, not full-address-space page tracking, and would collide/overwrite
  almost immediately at the 29K-1M+ events/sec this workload produces. Thrash
  stays on the fault-trace-ring repeat-count proxy already in use, with its
  existing trailing-window-only caveat undisturbed by this change.
- **Demand-path migrations** (as distinct from speculative migrations): C1's
  entire workload and C3's non-speculative fallback both migrate pages via
  stock UVM's demand-fault path, which `g_specasync_spec_migrations` does not
  count. No full-run migration total exists for the demand path.

## Deferred: consumer-cursor ring semantics (recommended future change, not implemented)

Evaluated as an alternative/complement to the atomics above, specifically for
thrash and any other ring-only metric this change doesn't reach. Not
implemented now — rejected for this gate on cost-of-revalidation grounds (see
decision below), logged here so the analysis isn't lost.

**The idea**: `specasync_batch_ring`/`specasync_work_ring`/`specasync_decomp_ring`
already have a `tail` field, currently only ever reset to 0 by `specasync_clear`.
Converting the read path to advance `tail` on every successful read (a real
producer/consumer FIFO instead of reset-on-clear semantics) would make each
record consumed exactly once — no read-then-clear race, and a periodic drain
would need only a single syscall per interval instead of a read followed by a
separate clear with kernel activity free to run in the gap between them. This
would retire `ARTIFACT_CATALOG.md` artifact #7's exposure **project-wide**, not
per-script, since every current and future ring consumer inherits the new
contract for free.

**Call sites**: `ring_read_binary()` and the three `*_log_read` wrappers in
`specasync_debugfs.c` currently take `head`/`tail` by value from a frozen
snapshot; they'd need the ring struct itself so a completed read can write back
an advanced `tail` under the lock. The real work is semantic, not line count:
today `*ppos` walks a stable window across multiple `read()` syscalls within one
`cat` invocation (large dumps need several); once `tail` moves per-read, that
model breaks and the file becomes a genuine consuming stream (`default_llseek`
should likely be dropped too). No new race is introduced against the producer —
`tail` only ever increases and the existing drop-on-full design already
guarantees the producer never overwrites unconsumed data — but **concurrent
readers** would start racing with each other (today any number of processes can
safely re-read the same snapshot; after this change, two simultaneous `cat`s
would split the same records unpredictably). Checked `specasync_parse.py`,
`extract_fault_trace.py`, and every existing harness's `dump_ring`/`clear_ring`
call pattern — none assume re-readability, all read-once-then-clear-once per
run, unaffected either way.

**Why deferred rather than rejected**: this is good engineering and the
right long-term fix for the underlying architectural exposure (not just this
one script's symptom) — but it changes read-path semantics on the exact
instrumentation every prior gate in this project's history depended on. It
would need a new srcversion (as this atomics change already does) *and* the
closure/overhead validation gates (Phase C's G1 accounting-closure check, and
whatever overhead-comparison gates B5/B6/B7 relied on) re-run and re-passed
before any post-change measurement could be compared against pre-change
numbers with confidence. That revalidation cost is real and not owed to this
specific gate's three-atomic fix, which needed neither a semantics change nor
new revalidation scope. Worth doing as dedicated, scoped work of its own.

The enlarge-the-rings alternative (compute: batch/decomp ring would need
~6.97M slots at C1's observed 28,808 records/sec over 161s with 1.5x margin,
~502MB/~781MB respectively; work ring would need ~83.2M slots at C3's net
921K items/sec (enqueued minus drops, verified dropped enqueues never reach
`queue_work()`) with 1.3x margin, ~4.0GB — **~5.27GB total new allocation**)
was rejected outright, not deferred: at Task 2's actual starting memory
(~30GB avail), the 18.43GB workload plus this allocation leaves ~6.2GB, right
at the standing 6GB OOM floor before the per-reload leak or anything else is
counted. Spending most of the safety margin the watchdog exists to protect,
on the exact host where oversubscription is already the binding memory
constraint, was judged not worth it for a fix that doesn't even remove the
underlying race.

## Reproduce

```bash
SRC=/usr/src/nvidia-595.84 \
WORK=/home/rayenchikhaoui/build/nvidia-595.84-specasync \
NV_KERNEL_MODULES="nvidia nvidia-uvm nvidia-modeset nvidia-drm nvidia-peermem" \
  bash driver/scripts/reconstruct_build_tree.sh
sudo tests/run_hit_probe.sh 256 1 validate_atomics_p1d0   # depth=0 in module params: faults+hits
sudo tests/run_hit_probe.sh 256 1 validate_atomics_p1d1   # depth=1 in module params: +migrations
```

Built module: `/home/rayenchikhaoui/build/nvidia-595.84-specasync/nvidia-uvm.ko`
(srcversion `4488C9F6F75570BB2FB34F8`).
