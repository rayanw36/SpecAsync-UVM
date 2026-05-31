# SpecAsync-UVM: Revised Abstract (v2)

> **Revision note:** This replaces the original abstract in response to reviewer
> Comment 1 (novelty / result magnitude) and Comment 3 (soundness / evidence).
> The revised framing is honest about current result magnitudes, repositions the
> primary contribution as kernel infrastructure rather than end-to-end speedup,
> and sketches the concrete roadmap that Phase 2 hardware experiments will
> address.

---

## Revised Abstract

GPU unified virtual memory (UVM) replayable-fault handling is a serial,
latency-sensitive critical path: every page fault stalls a GPU warp until the
driver completes VA-space lock acquisition, metadata discovery, and residency
preparation.  We present **SpecAsync-UVM**, a prototype modification to the
NVIDIA open-source UVM kernel driver (v580.95.05, Linux 6.14) that decouples
*speculative* preparatory work from this critical path via an in-kernel
producer–consumer design.  A lightweight background worker thread pre-fetches
VA-block metadata for addresses likely to fault next, guided by a pluggable
prediction policy; the demand-fault handler then skips or shortens the
metadata-discovery phase when the worker has already staged the result.

Our primary contribution is the **in-driver speculation infrastructure itself**:
a clean producer–consumer ring, a prediction-policy dispatch layer (adjacent-page,
stride-detector, Markov next-page, and oracle variants), per-batch latency
telemetry (T0–T4 timestamps, hit rate, enqueue overhead), and a debugfs interface
that exports structured binary logs for offline analysis.  This infrastructure
makes the fault-handling critical path *observable* and *amenable to
asymmetric offload* in a way that the stock driver does not support.

Microbenchmark evaluation on an RTX 5070 Ti (50-trial protocol,
`cudaMallocManaged` allocations, workloads from under 1 GB to 2.3 GB) shows
**modest and workload-dependent** wall-time effects: cuFFT gains up to **4.4%**
(mean, n=50, Exp1) at small-to-medium FFT sizes, while SGEMM, STREAM, and
Stencil show results within ±1–2% of baseline — a range consistent with
measurement noise at these working-set sizes.  We attribute the limited
end-to-end gains to (a) our current prototype stopping at metadata lookup
without fully offloading residency preparation, and (b) tested working sets
being well below GPU VRAM capacity, limiting fault-path pressure.

Phase 2 experiments — enabled by the telemetry and residency-offload
infrastructure described in this paper — will directly address both limitations:
per-batch latency breakdowns will provide the critical-path evidence absent from
Phase 1, and oversubscription workloads (1.25×–2× VRAM) will stress the fault
path far more severely.  We present the current prototype honestly as an early
result, and argue that the infrastructure contribution has value independent of
the Phase 1 numbers: it provides a principled, policy-switchable foundation for
future GPU speculation research within a production driver codebase.
