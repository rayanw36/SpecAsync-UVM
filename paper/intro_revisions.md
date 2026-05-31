# Introduction Revisions

> **Scope:** These are drop-in replacements for specific paragraphs in the
> introduction that overclaim, not a full rewrite.  The surrounding text
> (problem motivation, related work survey) should be unchanged.  Each section
> below identifies the paragraph to replace and provides the replacement text.

---

## Replacement 1 — Opening contribution claim

**Replace** the paragraph that currently summarises contributions and implies
broad latency reduction (typically the last paragraph of §1, beginning
something like "We show that…" or "Our contributions are…").

**Replacement text:**

> We make the following contributions:
>
> 1. **In-driver speculation infrastructure.** We modify the NVIDIA UVM kernel
>    driver to support pluggable, policy-driven speculative metadata prefetch on
>    the demand-fault critical path. The design is minimal (< 400 lines of net
>    new kernel C), preserves all upstream safety invariants, and introduces no
>    new kernel threads beyond the existing workqueue mechanism.
>
> 2. **Policy framework.** We implement four prediction policies — adjacent-page
>    (baseline), stride-detector, Markov next-page, and oracle — switchable via a
>    kernel module parameter at load time. The oracle policy provides an upper
>    bound on achievable speculation benefit and motivates further policy work.
>
> 3. **Telemetry and analysis toolchain.** We instrument the fault-handler with
>    per-batch T0–T4 timestamps and hit-rate counters exported via a debugfs
>    binary interface. A Python analysis suite parses these logs and computes
>    cost-benefit metrics (enqueue overhead, speculation hit rate, net benefit
>    per fault, phase breakdown). This makes critical-path latency directly
>    observable for the first time in the stock driver.
>
> 4. **Preliminary evaluation.** On an RTX 5070 Ti, cuFFT workloads show up to
>    4.4% wall-time improvement; SGEMM, STREAM, and Stencil show results within
>    measurement noise. We interpret these results honestly: the current prototype
>    is metadata-only (no residency offload) and all tested working sets fit
>    comfortably in VRAM. Phase 2 experiments with the telemetry infrastructure
>    and oversubscription workloads are expected to surface larger, more
>    attributable gains.

---

## Replacement 2 — Motivation / hypothesis paragraph

**Replace** the paragraph that currently asserts speculation will shorten the
critical path (typically in §1.2 or wherever the design hypothesis is stated,
beginning with something like "By pre-staging metadata…" or "Speculation allows
the demand handler to skip…").

**Replacement text:**

> Our hypothesis is that speculative metadata prefetch *can* shorten the
> VA-space-locked critical section of the demand-fault handler, by staging
> VA-block lookups before they are needed. Whether this shortening produces
> measurable end-to-end speedup depends on three factors that our current
> prototype does not yet fully characterise: (a) the fraction of demand faults
> that find a valid speculative result (the *hit rate*, which our Phase 2
> telemetry will measure directly); (b) the ratio of critical-path savings to
> speculative-enqueue overhead (the *net benefit per fault*, also measured by our
> telemetry); and (c) the degree to which the fault path is actually the
> bottleneck at a given working-set size (which oversubscription experiments will
> stress). The Phase 1 results are consistent with the hypothesis — cuFFT, the
> benchmark most dominated by irregular fault patterns, shows the strongest
> response — but they do not yet constitute direct evidence of critical-path
> shortening. That evidence is the goal of Phase 2.

---

## Notes for final paper integration

- Do **not** change §2 (related work) or §3 (design) — they are unaffected by
  these revisions.
- The results section (§4 or §5) should add a paragraph acknowledging that
  per-batch latency breakdowns are deferred to Phase 2 and explaining *why* the
  current results are consistent but not conclusive (working-set sizes,
  metadata-only offload).
- If there is a "limitations" subsection, add: "The current prototype's
  speculation stops at metadata lookup (depth=0); the residency-offload path
  (depth=1) is implemented in Phase 2 and is expected to produce larger
  critical-path savings for oversubscribed workloads."
