# Gate C — confounds ruled out: STREAM "speedup" is host noise; timers miss migration

## C1. Null-worker control (added)

`specasync_policy=5` ("null"): the worker is enqueued and **wakes/dequeues but does
zero lookup** (`specasync_worker_fn` returns immediately with `result=null`). Probe
verification (prefetch off, 256 pages): `spec_enqueued=256`, `spec_processed=256`
(all `result=null`), `spec_hits=0`. This isolates *worker presence* from *worker
prediction work*. Module srcversion `81CDE275…`.

## C2. Interleaved STREAM — the −8.8% does NOT survive

Phase B reported STREAM −8.8 % "speedup" at the two mid sizes (134M, 268M) for
p1/p2/p3. Those runs were all-baseline-then-all-treatment. Re-run **interleaved**
(p0→p1→p5 alternating, runtime policy switch, no reload between runs), 40 cycles =
40 runs/policy/size:

| size | p0 baseline (median ms) | p1 adjacent | p5 null | p1 Δ | p5 Δ | MWU p1 / p5 vs p0 |
|------|------------------------:|------------:|--------:|-----:|-----:|-------------------|
| 134,217,728 | 347.99 | 355.13 | 355.12 | **+2.05 %** | **+2.05 %** | p<1e-4 / p<1e-4 |
| 268,435,456 | 675.31 | 687.24 | 685.74 | **+1.77 %** | **+1.54 %** | p<1e-4 / p<1e-4 |

**Verdict:** the −8.8 % speedup **disappears under interleaving and reverses to a
small (~1.5–2 %) slowdown.** The original effect was a host-ordering artifact on the
shared EC2 instance (drift/neighbour between the baseline block and the treatment
block). Per-run std is tight (~5–6 ms), so this is not measurement scatter — it is a
real but opposite-signed effect that only the interleaved design exposes.

Crucially, **p1 (adjacent) ≈ p5 (null)** at both sizes (within 0.5 %, both highly
significant vs baseline). Since null does no lookup and no prediction, the small
slowdown is a pure **worker-presence side-effect** on fault batching (enqueue +
workqueue wakeups + the worker's VA-space read-lock acquisition raising `lock_acq`
from ~0.2 µs to ~2.2 µs in the Phase B telemetry), **not** speculation. It does not
track hit rate (p1/p2/p3 hit rates ranged 0.004–0.026 but all showed the same
offset). **Drop the "STREAM speedup" claim; report a ~2 % worker-presence overhead.**

## C3. Timer coverage — "metadata is ~99 % of service time" is an artifact

Timer placement in `service_fault_batch` (`uvm_gpu_replayable_faults.c`):

- T0 = batch entry; T1 = after VA-space read lock (line 2565).
- **T2 and T3 are set to the same `ktime_get_ns()`** immediately after
  `service_fault_batch_dispatch()` returns (lines 2627-2628; comment: "residency
  decision folded into dispatch"). So the parser's `phase_residency = T3 − T2` is
  **identically zero** — that phase column is dead.
- T4 = batch exit (line 2668).

Two consequences, both confirmed by inspection + the Phase B telemetry (where
`metadata_median ≈ lat_median` for every benchmark, e.g. STREAM-268M p0:
lat=168.3 µs, metadata=168.0 µs, residency≈0):

1. The window labelled **"metadata" (T1→T2) actually brackets the entire fault
   service path** — `service_fault_batch_dispatch → … → uvm_va_block_service_locked`
   (line 1843), which discovers the block *and* issues the migration copy. It is not
   metadata-discovery time; the `uvm_va_block_find`-style lookup is a tiny fraction
   of it. So "metadata ≈ 99 % of service time" mis-attributes the cost.

2. **Migration DMA is largely outside the timed window.** Between T2 and T4 the main
   path only pushes a fault replay (`push_replay_on_gpu`, line 2644) and invalidates
   TLBs — there is **no `uvm_tracker_wait`** before T4. The copy + replay execute on
   the GPU pushbuffer *after* the CPU exits `service_fault_batch`. So T0–T4 measures
   **CPU-side fault-handling latency, not transfer time.** The real migration/DMA
   cost — which dominates wall-clock — is invisible to this telemetry.

**Correction for the writeup:** the per-batch timestamps do **not** show that metadata
is the bottleneck. They show CPU fault-handling latency with a dead residency phase
and migration completing asynchronously off-window. Any claim about where service
time goes must come from wall-clock / migration accounting, not T0–T4.
