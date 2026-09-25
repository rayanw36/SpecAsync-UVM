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
