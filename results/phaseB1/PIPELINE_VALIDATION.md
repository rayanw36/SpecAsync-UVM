# SpecAsync-UVM Phase B.1 — Pipeline Validation Summary

**Question the brief posed:** the Phase B negative result (near-zero hits p1–p3,
oracle 0.000 hits while up to 100× slower) might be an *instrumentation artifact*.
Prove the pipeline before trusting any result.

**Bottom line:** the pipeline's hit accounting is **sound** (proven by a 99 %
positive control). The oracle had two real bugs, now **fixed and verified**. The
STREAM "speedup" was **host noise** and the per-phase "metadata bottleneck" is a
**timer artifact**. After all corrections **the headline does not change: this
metadata-only speculation mechanism produces no speedup, and cannot, by
construction.** Details per suspected problem below.

---

## Problem 1 — hit accounting (suspected broken counter)

**Wrong?** No — accounting is correct. **Evidence:** deterministic positive control
`tests/hit_probe.cu` (serialized adjacent touches, `uvm_perf_prefetch_enable=0`)
scores **254/256 = 99.2 %**. With prefetch on the same probe gives 5 faults / 0 hits.

**What the corrected understanding says:** the near-zero real-benchmark hit rates are
**real**, caused by (a) the UVM prefetcher bringing in pages before they demand-fault
(so the predictor never gets credited) and (b) prediction issued once per batch from
`ordered_fault_cache[0]`, too late for coalesced batches. **A "hit" measures
prediction correctness only** — the worker is metadata-only (`offload_depth=0`),
discards the looked-up block, and stages nothing the demand path consumes, so a hit
carries **zero time saving**. Confirmed in Gate D: hit-batches are not faster than
miss-batches (stencil p4: +1.8 %). Full detail: `GATE_A_report.md`.

## Problem 2 — oracle (0.000 hits, "100× slower")

**Wrong?** Yes — two independent bugs (the brief's O(n²)-scan hypothesis is rejected;
replay was already O(1)):

1. **Cursor desync (code).** Fault trace recorded per-fault but oracle cursor advanced
   once per batch → permanent desync after the first coalesced batch → every prediction
   is an already-faulted page. **Fix:** `specasync_oracle_next_addr_n(consumed)`
   advances by faults-this-batch and returns the next-to-fault page (still O(1)).
2. **ASLR address instability (procedure).** `cudaMallocManaged` re-randomises the base
   VA per process, so an absolute-VA trace never matches a fresh replay. **Fix:** run
   collect + replay under `setarch -R` (stable base verified).

**Evidence (old `B83C15DA` vs fixed):** serialized probe 0.99 vs 0.99 (old self-hits
the current page, zero lead); **coalesced 7.9 faults/batch: 0.0175 → 0.4107** (23×).
On real stencil the fixed oracle gets 24 hits vs p1–p3's 0–2 — clearly ≫ p1–p3 — but
the absolute ceiling stays low (rate 0.0066) because of one-prediction-per-batch +
prefetch making the real fault stream only partially match the recorded trace.
**"100× slower" did not reproduce with the fix** (stencil p4 = +0.2 % vs baseline;
GraphBFS / Stencil_OvSub: see Gate D below). Full detail: `GATE_B_diagnosis.md`,
`../../driver/PIPELINE_FIXES.md`.

## Problem 3 — STREAM −8.8 % "speedup" and the metadata-bottleneck timers

**Wrong?** Yes, both.

- **STREAM speedup was host noise.** Interleaved (40 runs/policy, alternating), the
  −8.8 % vanishes and reverses to **+1.5–2.0 % slowdown** at both mid sizes (134M,
  268M; p<1e-4). It was an artifact of all-baseline-then-all-treatment ordering on a
  shared EC2 host. The residual slowdown is **worker presence, not prediction**:
  p1(adjacent) ≈ p5(null) within 0.5 %. → **Drop the STREAM speedup claim.**
- **"Metadata ≈ 99 % of service time" is a timer artifact.** `T2 == T3` so the
  residency phase is identically zero; the "metadata" window (T1→T2) actually brackets
  the whole dispatch incl. the migration *issue*; and there is no `tracker_wait` before
  T4, so migration DMA completes asynchronously **outside** the timed window. T0–T4
  measures CPU-side fault-handling latency, **not** transfer time. Full detail:
  `GATE_C_report.md`.

---

## Gate D — corrected results, fault-heavy workloads (p0–p4, corrected pipeline)

All runs `setarch -R`, telemetry on, fixed module `81CDE275`. Hit rate = hits/enqueued
(aggregate over runs); wall Δ vs p0.

| benchmark | size | p1 hit | p2 hit | p3 hit | **p4 hit (oracle)** | p1 wallΔ | p4 wallΔ | hit saves time? |
|-----------|------|-------:|-------:|-------:|--------------------:|---------:|---------:|-----------------|
| Stencil   | 24000 | 0.0000 | 0.0003 | 0.0005 | **0.0066** | +0.9 % | +0.2 % | no (+1.8 %) |
| GraphBFS  | 23 | 0.0016 | 0.0044 | 0.0044 | **0.0648** | −0.2 % | **−1.6 %** | no |
| Stencil_OvSub | 28300 20 11264 | 0.0006 | 0.0007 | 0.0025 | **0.0026** | +1.6 % | −0.1 % | no |

**The "100× slower" oracle does NOT reproduce.** Phase B reported GraphBFS oracle
+10,027 %. Under controlled measurement (setarch -R, matched per-run trace) the
**fixed** oracle is **−1.6 %** vs baseline (54.4 s vs 55.3 s), and the **old buggy
ko** oracle is also ≈ baseline (55.4 s, 3 runs). So the catastrophic slowdown is **not
a property of the oracle code path in either ko** — it was a methodology artifact of
the original Phase B oracle sweep (which also had the known `specasync_parse.py`
mis-call and ran without ASLR control). I could not reproduce 10,027× in any
controlled configuration; the corrected verdict is "oracle runtime ≈ baseline."

**Reading (stencil + GraphBFS):** the fixed oracle is the only policy with a
non-trivial hit count (0.0648 on GraphBFS, ≫ p1–p3's ≤0.0044), confirming the fix
works *and* that p1–p3 genuinely predict almost nothing on real prefetched/coalesced
fault streams. **No policy yields wall-clock speedup** (all within ±2 % of baseline,
i.e. noise), and hits do not reduce per-batch service time — the metadata-only
mechanism has no consumable product, so its speedup ceiling is ~0 by construction.

Across all three fault-heavy workloads (Stencil, GraphBFS, Stencil_OvSub × p0–p4):
**no policy produced a wall-clock speedup** (all within ±2 %), per-hit service time
shows **hits save no time**, and cost-benefit is **net-negative for every policy**
(enqueue overhead ~2.4–2.8 µs/fault dominates). The fixed oracle predicts genuinely
(hit rate ≫ p1–p3 on Stencil/GraphBFS; it only ties p3 under oversubscription, where
the fault stream is thrash-dominated and unpredictable) — and still yields nothing.

---

## What changed vs the original Phase B writeup

| original claim | corrected |
|---|---|
| oracle 0.000 hits everywhere (counter suspect) | counter sound; oracle had a real cursor-desync + ASLR bug, now **fixed** → hit rate ≫ p1–p3 |
| oracle up to 100× slower | **not reproduced** in any ko under controlled measurement; oracle ≈ baseline; original was a sweep artifact |
| STREAM −8.8 % speedup | **host noise**; interleaved it is +1.5–2 % slowdown = worker presence (null reproduces it) |
| metadata ≈ 99 % of service time | **timer artifact**; residency phase is zero-width and migration DMA is off-window |
| near-zero p1–p3 hits, negative cost-benefit (headline) | **confirmed and explained** — real prediction failure under prefetch/coalescing + zero-saving metadata-only hits |

---

## Verdict on the headline

The corrected pipeline **confirms** the Phase B negative result rather than overturning
it — but for the right reasons and with the artifacts removed:

- Hits are real and correctly counted; they are simply rare on real (prefetched,
  coalesced) fault streams, and **even when they occur they save no time**.
- The oracle, once fixed, sets a genuine upper bound — and that bound is still ~no
  speedup, because the mechanism is metadata-only.
- The two "positive/negative signals" that could have misled the writeup (STREAM
  speedup, metadata bottleneck) were artifacts and are removed.

The mechanism needs a *consumable product* (residency offload, `offload_depth≥1`) to
have any chance of speedup; at depth 0 the ceiling is zero regardless of prediction
quality.
