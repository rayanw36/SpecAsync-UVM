# Gate T2 — cuFFT interleaved rerun on T4

Data: `results/phaseB2/cufft_interleaved/cufft_interleaved_times.csv` (204 runs: 3 sizes x
(2 primary configs + 2 secondary configs) x 17 reps [2 warmup + 15 kept]). cuFFT built for
`-arch=sm_75` via `nvcc` (CUDA 12.0 toolkit, installed this session -- this instance had
neither `nvcc` nor `libcufft` before; the pre-existing `benchmarks/bench_cufft` binary
could not even run, `error while loading shared libraries: libcufft.so.11`). Module
srcversion `8A2651D1CB32C7B239FB511` throughout; dmesg clean.

## Methodological correction caught mid-task

The harness's first version ran the p0/p2 primary comparison at `specasync_offload_depth=1`.
Checking `CUFFT_PROVENANCE.md`'s raw `phaseB_telemetry.csv` row against the harness before
trusting the result: `2,0,cuFFT,67108864,1700,0.25471,...` -- columns
`policy,depth,benchmark,size,...` -- the original 25.47% figure was measured at
**policy=2, depth=0**, not depth=1. Depth=0 is "metadata-only lookup" (find block, discard,
insert hit-table entry, no actual migration); depth=1 additionally attempts a speculative
migration. Fixed the harness (`tests/t2_cufft_interleaved.sh`) to depth=0 for both p0 and
p2 and reran before analyzing -- the first (depth=1) run's data was discarded, never
committed.

## 1. Does the 25.47% hit rate reproduce?

**No -- not even close, at the exact matching configuration.**

| Size | p2 aggregate hit rate (n=15, kept) | Legacy figure |
|---|---|---|
| 67,108,864 (same size as the legacy row) | **4.07%** | 25.47% |
| 134,217,728 | 2.59% | -- |
| 268,435,456 | 1.70% | -- |

At the exact size, policy, depth, and prefetch-state the legacy 25.47% was measured at,
this interleaved rerun gets **4.07%** -- a sixth of the original figure, aggregated over
15 clean reps rather than the legacy single (uncontrolled, non-interleaved, pre-fix-era)
measurement. `CUFFT_PROVENANCE.md` already established the legacy number is real T4/595
data, just never revisited under a controlled protocol -- this task supplies that revisit,
and the number does not hold up.

## 2. Does it correspond to any wall-clock effect?

**No**, matching the task's stated expectation.

| Size | p0 (no speculation) median | p2 (stride) median | delta | MWU p |
|---|---|---|---|---|
| 67,108,864 | 0.690s | 0.690s | 0.00% | 0.962 (n.s.) |
| 134,217,728 | 1.070s | 1.080s | +0.94% | 0.019 |
| 268,435,456 | 1.840s | 1.840s | 0.00% | 0.351 (n.s.) |

Two of three sizes show no detectable difference at all (identical medians). The one
nominally significant comparison (134M, p=0.019, uncorrected -- not run through a
multiple-comparison correction here since it's not part of the pre-registered 6-comparison
family, which is T1-specific) is in the **wrong direction for a benefit** (p2 marginally
*slower*, +0.94%) and small enough to be a plausible false positive at alpha=0.05 across
3 tests. **No reproduced positive wall-clock effect** -- per the task brief, this is
reported as a clean negative result rather than treated as the "major finding, stop
immediately" trigger, since that trigger was specifically for a *positive* effect.

## 3. The hypothesized mechanism does not hold up either

The task's stated hypothesis worth testing: cuFFT's large-stride access might generate
faults the 2MB block prefetcher misses, which a stride predictor would naturally catch --
making cuFFT "the cleanest possible test... the one real workload where prediction
demonstrably works, and it still buys nothing." **Under this controlled measurement,
prediction does not demonstrably work here either** -- a 1.7-4.1% hit rate is a small
minority of predictions landing, not a stride predictor cleanly tracking cuFFT's access
pattern. The interesting, still-true part of the story: the **stock UVM prefetcher**
matters enormously for cuFFT (Section 4) -- SpecAsync's own stride mechanism on top of it
does not.

## 4. Secondary: C0/C1 for continuity (stock prefetch ON vs OFF, no speculation either way)

| Size | C0 (prefetch ON) median | C1 (prefetch OFF) median | delta |
|---|---|---|---|
| 67,108,864 | 0.690s | 2.550s | +269.6% |
| 134,217,728 | 1.070s | 4.840s | +352.3% |
| 268,435,456 | 1.830s | 9.420s | +414.8% |

Sanity-confirms the obvious: the **stock NVIDIA prefetcher** is doing enormous work for
cuFFT's access pattern (2.7x-4.1x slower with it off) -- consistent with cuFFT's
large-stride/sequential FFT buffer access being exactly what a 2MB block prefetcher is
good at. This is not new information but confirms the experimental setup behaves sanely
before trusting the primary comparison's null result.

## 5. Verdict

**Both expectations from the task brief held: the legacy 25.47% hit rate does not
reproduce under a controlled, interleaved, exact-configuration-matched rerun (4.07% at
best), and there is no wall-clock effect either way.** The manuscript should not carry the
25.47% figure forward as a T4/595.71.05 result -- it was a measurement artifact of the
uncontrolled pre-fix sweep, not something this task's cleaner protocol can recover. cuFFT
gets no additional benefit from SpecAsync speculation, on top of (already-substantial)
benefit from the stock prefetcher it already receives.
