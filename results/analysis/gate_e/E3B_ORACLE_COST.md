# Gate E3b Step 4 — Did the oracle's cost come from the lookup and lock?

## Expectation (committed verbatim before the first Step 4 run)

> E1b measured speculation's extra pre-lock servicing time on Stencil-24K
> (prefetch off, C6-L4096 vs C1) at +0.478 s, of which the enqueue itself
> was +0.061 s. If the per-fault cost was the binary search and global lock
> in `specasync_ft_predict`, then with `specasync_ft_fast=1` the pre-lock
> increase should fall substantially toward the enqueue-only level. If it
> barely moves, the per-fault cost lies elsewhere in the prediction path, the
> oracle remains expensive, and the E0.9b and E1 results must carry that
> caveat.

## Design (fixed before the first Step 4 run)

- **Module:** every arm uses the new module (`33FD42E6E16B0A6658E2BEB`),
  W = 1. Speculation-off arms (C1, C0) run at fast = 0.
- **Order:** `e3b/step4_order.csv`, 24 runs, seed 202609263, interleaved.
- **Arms:**
  - Stencil-24K: C1, C6-L4096 fast 0, C6-L4096 fast 1, C0, C7-L4096 fast 0,
    C7-L4096 fast 1, each ×3;
  - GraphBFS-23: C1, C6-L4096 fast 0, C6-L4096 fast 1, each ×2.
- **Tables:** fresh prefetch-off first-touch tables, with the distinct-page
  assertions 1,125,000 / 287,956.
- **Per run:** `specasync_trace_faults=0` (so as not to add per-fault work),
  plus batch-ring and decomp-ring dumps. Coverage must be 100% (fewer than
  131,071 records); otherwise the covered fraction is reported and nothing
  is scaled.
- **Measures:** the same as E1b (`tests/e1b_analyze.py` definitions).
  - **Pre-lock segment:** Σ(t1 − t0 − D3).
  - **Outside-lock:** Σ(svc − D3 − D4).
  - `enqueue_overhead_ns`.
  - **Residual** = pre-lock increase − enqueue-overhead increase.
  - The residual per coalesced fault, fast 0 vs fast 1.
  - D5.
- **Verdict terms:**
  - **Lookup was the cost**: the residual falls substantially, and the
    fraction removed is stated.
  - **Cost is elsewhere**: the residual barely moves, and the caveat then
    applies to E0.9b and E1.
  - **Partial**: how much remains, and what the source suggests the
    remainder might be, without attributing it unmeasured.
- This is descriptive: no wall-clock arm comparisons.

## Results (all 24 runs; no stop condition)

**Integrity**
- All runs used the new module (`33FD42E6…`) at W = 1, with `trace_faults=0`.
- Both rings had **100% coverage** in every run (at most 74,939 records),
  with 0 length mismatches, 0 misaligned batch↔decomp pairs and 0 `t1 = 0`
  records.
- Identity 2 (`ft_predictions = ft_same_region + enqueued + drops`) holds
  with difference **0** on every run. `ft_fast_cas_giveup = 0` and
  `spec_region_invalid = 0` everywhere. Every fast = 1 load had
  `ft_fast_verified = 1` (Stencil 2 ranges, GraphBFS 19).
- There was one non-stop dmesg line, in run 10:
  `workqueue: drm_fb_helper_damage_work hogged CPU for >10000us 5 times`.
  It comes from the framebuffer console, not `nvidia_uvm`, and the run is
  kept.
- "Coalesced faults" means Identity 1's right side. Identity 1 held exactly
  on every Step 2–3 run that had `trace_pushes`; Step 4 runs without the
  trace, so as not to add per-fault work.

Medians per arm (script: `tests/e3b_step4_analyze.py`; per-run data:
`e3b/step4_per_run.csv`):

| arm | n | outside-lock svc−D3−D4 (s) | pre-lock segment t1−t0−D3 (s) | enqueue_overhead (s) | per prediction (ns) | D5 (s) | ft_predictions | enqueued | drops | coalesced faults (I1) | demand faults |
|---|---|---|---|---|---|---|---|---|---|---|---|
| graphbfs C1 | 2 | 0.0034 | 0.0018 | 0.0000 | nan | 0.7635 | 0 | 0 | 0 | 0 | 492910 |
| graphbfs C6f0 | 2 | 0.0932 | 0.0911 | 0.0096 | 116 | 0.6549 | 83258 | 83258 | 0 | 479548 | 479548 |
| graphbfs C6f1 | 2 | 0.0223 | 0.0202 | 0.0091 | 114 | 0.6657 | 79468 | 78998 | 470 | 485896 | 485896 |
| stencil C0 | 3 | 0.0014 | 0.0010 | 0.0000 | nan | 0.1061 | 0 | 0 | 0 | 0 | 346056 |
| stencil C1 | 3 | 0.0140 | 0.0090 | 0.0000 | nan | 1.6008 | 0 | 0 | 0 | 0 | 2926519 |
| stencil C6f0 | 3 | 0.4914 | 0.4854 | 0.0599 | 53 | 0.9289 | 1124999 | 909862 | 215117 | 2985620 | 2985620 |
| stencil C6f1 | 3 | 0.1231 | 0.1173 | 0.0532 | 47 | 1.0855 | 1124999 | 799072 | 325927 | 2981925 | 2981925 |
| stencil C7f0 | 3 | 0.0796 | 0.0790 | 0.0249 | 76 | 0.1406 | 327438 | 327438 | 0 | 327438 | 327438 |
| stencil C7f1 | 3 | 0.0379 | 0.0373 | 0.0245 | 72 | 0.1302 | 341659 | 341659 | 0 | 341659 | 341659 |

| workload | pair | increase outside-lock (s) | Δ enqueue (s) | **residual** (s) | residual per coalesced fault (ns) | residual per demand fault (ns) | D5 change vs baseline (s) |
|---|---|---|---|---|---|---|---|
| stencil | C6f0 − C1 | +0.4775 | +0.0599 | **+0.4175** | 139.8 | 139.8 | -0.6718 |
| stencil | C6f1 − C1 | +0.1091 | +0.0532 | **+0.0559** | 18.7 | 18.7 | -0.5153 |
| stencil | C7f0 − C0 | +0.0782 | +0.0249 | **+0.0534** | 162.9 | 162.9 | +0.0345 |
| stencil | C7f1 − C0 | +0.0365 | +0.0245 | **+0.0120** | 35.0 | 35.0 | +0.0241 |
| graphbfs | C6f0 − C1 | +0.0897 | +0.0096 | **+0.0801** | 167.0 | 167.0 | -0.1085 |
| graphbfs | C6f1 − C1 | +0.0188 | +0.0091 | **+0.0097** | 20.1 | 20.1 | -0.0978 |

| workload | pair | residual fast 0 (s) | residual fast 1 (s) | **fraction of residual removed** |
|---|---|---|---|---|
| stencil | C6 | +0.4175 | +0.0559 | **86.6%** |
| stencil | C7 | +0.0534 | +0.0120 | **77.6%** |
| graphbfs | C6 | +0.0801 | +0.0097 | **87.8%** |
The pre-lock segment (t1 − t0 − D3) tracks the outside-lock quantity within
0.2–6 ms in every arm, as in E1b.

## Verdict: **lookup was the cost**

With `specasync_ft_fast=1`, the per-fault prediction residual falls by:
- **86.6%** on Stencil-24K C6 (0.418 → 0.056 s; 139.8 → 18.7 ns per
  coalesced fault);
- **77.6%** on Stencil-24K C7 (0.053 → 0.012 s; 162.9 → 35.0 ns);
- **87.8%** on GraphBFS-23 C6 (0.080 → 0.010 s; 167.0 → 20.1 ns).

As the committed expectation predicted, the pre-lock increase falls
substantially toward the enqueue level. On Stencil C6 it goes from +0.478 s
to +0.109 s, against an enqueue cost of +0.053 s. **The per-fault cost E1b
measured was mostly the oracle's own binary search and global irqsave
lock.**

The fast = 0 residuals (139.8 / 162.9 / 167.0 ns per fault) reproduce E1b's
139 / 166 / 167 ns, in a new session and on a different module.

**What remains (12–22% of the residual; 19–35 ns per fault) is not
attributed.** From source, the per-fault work still on the servicing
thread at fast = 1 is:
- the `specasync_predict_next` dispatch;
- the `specasync_replay_order_push` early-return check;
- `atomic_fetch_inc(&g_ft_seq)`, a shared counter;
- the range lookup and the `atomic_try_cmpxchg` on the cursor;
- the `hit_table` pointer lookup;
- `specasync_enqueue`'s untimed early checks, including the queue-full drop
  path. That path ran 325,927 times on Stencil C6 at fast = 1;
- loop control.

No counter separates these components.

## D5: the fast path **did** change the under-lock saving (reported, not explained away)

The brief asked for D5 to confirm that the fast path did not change the
under-lock saving. It did not hold on Stencil C6.

| workload | pair | D5 change vs baseline, fast 0 | fast 1 | queue-full drops, fast 0 → fast 1 | enqueued, fast 0 → fast 1 |
|---|---|---|---|---|---|
| Stencil-24K | C6 vs C1 | −0.672 s | **−0.515 s** (0.157 s less saving) | 215,117 → **325,927** | 909,862 → 799,072 |
| Stencil-24K | C7 vs C0 | +0.035 s | +0.024 s | 0 → 0 | 327,438 → 341,659 |
| GraphBFS-23 | C6 vs C1 | −0.109 s | −0.098 s (0.011 s less saving) | 0 → 470 | 83,258 → 78,998 |

On Stencil C6 a faster predictor produces predictions faster than the
worker drains the 1,024-deep queue. So **more predictions are dropped at
enqueue** (+51%) and **fewer pages are pre-staged**, and the under-lock
saving shrinks by 23%.

This is a measured coincidence of two counters, not a proven causal chain.
It is consistent with E0.9b's finding that throughput limits speculation at
large lookahead. It bears directly on the next sweep: a cheap oracle
*exposes* the worker's drain rate as the next bottleneck, which is the
problem speculative width (W > 1) addresses.

The descriptive sum of the two measured components (outside-lock + D5,
ignoring D1/D2/D6) vs baseline:
- Stencil C6: −0.194 s at fast 0, −0.406 s at fast 1.
- Stencil C7: +0.113 s, +0.061 s.
- GraphBFS C6: −0.019 s, −0.079 s.

These are servicing-time components, **not** wall-clock comparisons.

## Caveat for E0.9b and E1

Because the lookup *was* the cost, **E0.9b's and E1's oracle carried an
expensive-oracle burden** on the fault-servicing thread:
- about 0.36 s of servicing time per Stencil C6 run;
- about 0.041 s per Stencil C7 run.

A practical constant-time predictor would not carry that cost. E1's C7
slowdown relative to C0 (+0.093 s wall) coincides with a fast-0 residual of
0.053 s, of which 0.041 s is removable.

**E0.9b's and E1's conclusions (C6 and C7 lose to C0) were reached with the
expensive oracle, and must carry that caveat until they are re-tested with
`specasync_ft_fast=1`.** That is for the next, pre-registered sweep, not
this step. No wall-clock comparison was made here.
