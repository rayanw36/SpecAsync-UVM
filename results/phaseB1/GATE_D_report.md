# Gate D — corrected re-baseline of fault-heavy workloads (p0–p4)

Corrected pipeline: fixed module `81CDE275` (oracle cursor-sync + null policy),
telemetry on, all runs `setarch -R`. Oracle (p4) uses a per-run trace collected
under the same conditions (FIX-2). Hit rate = Σhits/Σenqueued aggregated over runs;
wall Δ vs p0 from median of N timed runs.

## Hit rates and wall-time

| benchmark | size | runs | p1 | p2 | p3 | **p4 oracle** | p1 wallΔ | p2 | p3 | **p4 wallΔ** |
|-----------|------|-----:|---:|---:|---:|--------------:|---------:|---:|---:|-------------:|
| Stencil   | 24000 | 6 | 0.0000 | 0.0003 | 0.0005 | **0.0066** | +0.9 % | +0.6 % | +0.9 % | **+0.2 %** |
| GraphBFS  | 23 | 4 | 0.0016 | 0.0011 | 0.0044 | **0.0648** | −0.2 % | −0.1 % | −1.9 % | **−1.6 %** |
| Stencil_OvSub | 28300 20 11264 | 4 | _pending_ | | | | | | | |

## Per-hit service-time saving (does a hit save time?)

No. Comparing median batch service time (T4−T0) for batches **with** a hit vs
**without**, same workload:

| benchmark | policy | hit-batches median ns | miss-batches median ns | Δ |
|-----------|--------|----------------------:|-----------------------:|---|
| Stencil   | p4 | 69,812 (n=24) | 68,585 | **+1.8 %** (not faster) |
| GraphBFS  | p4 | 30,082 (n=118) | 266,870 | −88.7 %ᵃ |

ᵃ The GraphBFS hit-batches being "faster" is a **selection effect**, not causation:
the oracle only gets credited on small single-fault batches (which are intrinsically
fast); the large coalesced batches that dominate wall-clock are never hit. Wall-time
shows no speedup (−1.6 %, within noise). A hit does not *cause* a batch to be faster —
the worker is metadata-only and stages nothing the demand path consumes (Gate A).

## Cost-benefit (Phase B metric: Δsvc·hit_rate − enqueue_overhead, per fault)

Net benefit is **negative for every policy** — the ~2.4–2.8 µs/enqueue overhead
dominates while the hit term is ≈0:

| benchmark | p1 | p2 | p3 | p4 |
|-----------|---:|---:|---:|---:|
| Stencil   | −2427 | −2392 | −2487 | −2428 |
| GraphBFS  | −2798 | −2740 | −2287 | −1869 |

(ns/fault; caveat: Δsvc is CPU-side latency only — migration excluded per Gate C — so
even this telemetry-bounded figure overstates any benefit.)

## The "100× slower" oracle — not reproduced

| GraphBFS oracle | wall median |
|-----------------|------------:|
| Phase B reported | +10,027 % |
| **fixed ko (this run)** | **−1.6 %** (54.4 s) |
| old buggy ko (control, 3 runs) | ≈ baseline (55.4 s) |

Under controlled measurement neither ko is slow. The original +10,027 % was a Phase B
sweep methodology artifact, not an oracle-mechanism property.

## Verdict

The corrected pipeline **confirms the Phase B headline** (no speedup; negative
cost-benefit; oracle ceiling ~0) while removing the artifacts that surrounded it:
the oracle now genuinely predicts (hit rate ≫ p1–p3) yet still yields no speedup,
because at `offload_depth=0` a "hit" has no consumable product. The residency timer
phase is identically zero on every benchmark (Gate C timer artifact, reconfirmed
here). The path to any speedup is `offload_depth≥1` (residency offload), not better
prediction.
