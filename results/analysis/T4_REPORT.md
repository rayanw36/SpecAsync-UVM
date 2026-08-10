# T4 instance work block — final report

Summarizes the entire block: platform verification, the remaining CPU-only work, the
pre-registered analysis plan, the GPU experiments (T1-T4; T5 skipped), and the resulting
figure/analysis updates. T5 (core-count control) was explicitly skipped per the author's
direction (requires stopping the instance and changing its type -- an infrastructure
action outside what "continue running the GPU experiments" authorized); everything else
in the original brief is complete.

## Platform readout (Gate 0)

- Instance: `g4dn.xlarge` (confirmed via IMDSv2 token, not just assumed), Tesla T4, 15360
  MiB, driver **595.71.05** -- matches the required version exactly, no platform
  ambiguity.
- Kernel `6.17.0-1019-aws`, Ubuntu 24.04.4 LTS, 4 vCPU, 15 GiB RAM.
- `/opt/dlami/nvme` present as a separate ephemeral volume; repo lives on the EBS root
  (`/home/ubuntu/Downloads/SpecAsync-UVM`, not `~/SpecAsync-UVM` as an earlier handoff
  note assumed -- a path difference, not a platform mismatch).
- **Transfer integrity:** 631-entry `MANIFEST.sha256` verified clean except one file,
  `results/phaseB2/gate3/gate3_times.csv`, found truncated to its header in the working
  tree (120 rows of original Gate 3 data missing) -- restored from git HEAD before
  anything else happened; nothing was actually lost. git-lfs was not installed; installed
  it and confirmed all three `driver/patches/*.patch` files resolve to real content
  matching their LFS OIDs exactly. Manifest regenerated (631 -> 635 entries) to also cover
  `driver/patches/` and a report file written after the original manifest.
- An untracked `manuscript_assets/` bundle was found and left untouched (legitimate prior
  work product from an earlier discovery session, per its own internal provenance notes)
  -- flagged for the author's decision (commit, gitignore, or discard), not acted on.

## Phase 1 (CPU-only work, before any GPU run)

- **D5 re-verification (1.1):** the real 595.71.05 UVM source tree exists on this
  instance at `/usr/src/nvidia-595.71.05/nvidia-uvm/` -- closed the provenance gap the
  Phase 1 GPU-free block had to leave open. `uvm_va_block_service_locked` and
  `uvm_va_block_service_copy` (the functions carrying the SYNC-WAIT/ASYNC-SUBMIT
  classification the D5 claim rests on) are byte-identical to the v580.95.05 chain. Four
  small, classification-irrelevant diffs found and reported (dirty-page-tracking /
  eviction-guard refinements). Manuscript sentence unchanged; verdict confirmed, not
  revised.
- **Bibliography (1.2):** applied all six corrections from `BIB_AUDIT.md` (three
  miscited entries, three preprints since published). Original entries preserved in an
  auditable `@Comment` block (a bare `%` prefix does not reliably hide a BibTeX entry from
  `bibtex`'s own parser -- caught and fixed). Rebuilt `paper/main.tex` end-to-end after
  installing TeX Live (this instance had none): zero errors, zero undefined citations.
- **Harnesses (1.3):** wrote and dry-ran all four GPU harnesses (T1-T4) plus a shared
  library giving every one of them a `DRY_RUN=1` no-op mode and the full per-run telemetry
  columns (run-order index, timestamp, config, benchmark, size, srcversion, dmesg delta)
  the original Gate 3 harness lacked. One real bug caught during dry-run (stdout log
  pollution corrupting a captured trace path) and fixed before any GPU run.
- **Pre-registration (1.4):** written and committed before any GPU run. Fixed the
  rotation, warm-up/kept split, statistic of record (median), test of record (Mann-Whitney
  U), the six-comparison Holm-Bonferroni family, the outlier policy, primary-vs-secondary
  designation, and an explicit falsification criterion. One correction made to the
  pre-registration itself, before any data existed: harness authoring revealed
  `uvm_perf_prefetch_enable` and `specasync_oracle_trace_path` are read-only after module
  load (not live-switchable like `specasync_policy`/`specasync_offload_depth`), so the
  interleaving mechanism was corrected to "reload before every run" rather than "live
  param switch," with the rotation order and never-blocked guarantee unchanged.

## Phase 2 (build and module validation)

- Fresh build from `driver/src/` + `driver/patches/specasync_selective_apply.patch`
  against the pristine 595.71.05 tree: srcversion `8A2651D1CB32C7B239FB511`, identical to
  Phase C's original build -- confirms source fidelity.
- **Two safety issues caught before the first module swap:** the existing stock-module
  backup was for the wrong kernel version (`6.17.0-1017-aws` vs. the running
  `6.17.0-1019-aws`; would not have loaded as a rollback target) -- refreshed and
  checksum-verified; the emergency rollback script had a stale hardcoded repo path that
  would have silently failed to find the backup -- fixed.
- Deterministic probe reproduces the ~99.22% hit rate (255/256 = 99.61%, within the
  documented boundary-race variance). Instrumentation overhead passes decisively (<2%
  threshold; measured -0.24%, i.e. negligible) under this session's own matched-config
  measurement, though the absolute wall-clock baseline does not match Phase C's original
  numbers -- the first sighting of a discrepancy (Section "Open items" below) that
  recurred independently in Task T3.

## Phase 3 (GPU experiments) — results by task

### T1 — Interleaved Gate 3 C0-C3 rerun (highest priority)

176 runs, strict `C0,C1,C2,C3` rotation, reload before every run, 2 warmup + 20 kept
rotations/cell, exactly per the pre-registration.

- **Stencil-24K, C3 vs C1 (primary): now significant** (Holm-corrected, p=9.69e-07,
  Cohen's d=1.749) -- more decisive than the original blocked-protocol result (p=0.036,
  Holm-non-significant), and in the **opposite direction** from what the contamination
  hypothesis predicted (clean data made the gap more certain, not less).
- **GraphBFS-23, C3 vs C1 (primary): confirmed indistinguishable** (p=0.776, d=0.103),
  with the minimum detectable effect tightening from the original 1.02% to 0.16% -- a
  materially better-powered null.
- **The C3/Stencil-24K bimodal pattern reproduces** (8/20 runs high vs. 5/15 originally)
  and is now proven **not** position-correlated (Spearman rho=-0.011, p=0.965) -- upgrades
  from "warm-up/contention artifact" to a genuine, reproducible two-state mechanism, per
  the pre-registration's own stated secondary trigger.
- Neither primary comparison shows C3 beating C1 (the pre-registered primary
  falsification trigger), so the paper's negative conclusion about speculative
  prefetching stands -- but the abstract's blanket claim must be split per-workload.

### T2 — cuFFT interleaved rerun

204 runs across 3 sizes. Caught and fixed a real methodological mismatch mid-task
(depth=1 vs. the legacy measurement's depth=0) by cross-checking the raw original data
before trusting the result.

- **The legacy 25.47% hit-rate figure does not reproduce**: 4.07% at the exact matching
  configuration -- a sixth of the original, aggregated over 15 clean interleaved reps.
- **No wall-clock effect** either direction (2 of 3 sizes: identical p0-vs-p2 medians).
- Added as artifact #6 in `ARTIFACT_CATALOG.md` -- the same failure mode as artifact #3
  (a blocked/uncontrolled measurement later debunked by interleaving).

### T3 — Phase C paired wall-clock, 6 missing workloads

30 runs (6 workloads x 5 trials). G1 accounting closure holds essentially perfectly
(0-0.3% violations); D1+D2 window shares reproduce `PIPELINING_CEILING.md`'s original
figures within ~0.5-1.9 percentage points despite being a fresh capture.

- **End-to-end pipelining ceiling now computable for 6 of 7 workloads** (was 1 of 7):
  range **0.20% (GraphBFS-23, compute-bound) to 19.06% (Stencil-8K)**.
- Cross-check against the pre-existing Stencil-24K figure (~7.9%) does **not** reproduce
  on an absolute-time basis (this session's equivalent workload: 4.09s vs. the original's
  1.646s) -- confirmed as the same discrepancy Gate 2 independently found, not a new
  problem. The six new numbers are internally consistent with each other but should be
  reported as a separate set from the one pre-existing figure.

### T4 — Prefetch-OFF hit-rate telemetry

60 runs (C1/C3 x 2 benchmarks x 15 reps), via a separate script that reproduces
`gate3_favorable_run.sh`'s exact sequence without editing that published-results file.

- **Real workloads score 0.02-0.25% hit rate** even under oracle-perfect prediction with
  the prefetcher off -- four orders of magnitude below the deterministic probe's 99.6%.
- **Root cause identified, sharper than the task anticipated:** not a prediction-accuracy
  failure (the oracle predicts perfectly by construction) but a **rate mismatch** -- real
  workloads sustain 0.4-4.7 million demand faults/second, far outrunning the async
  worker's scheduling latency, so a speculative hit-table entry is almost always too late
  to be consumed. The deterministic probe's 99.6% only worked because it artificially
  serialized one fault at a time.
- Doesn't change the conclusion (C3 already showed no benefit over C1 in T1) but adds a
  concrete, quantified mechanism worth a discussion-section sentence.

### T5 — Core-count control

**Skipped, per the author's explicit direction.** Requires stopping this instance and
switching to `g4dn.2xlarge`, a real infrastructure/billing action outside the scope of
"continue running the GPU experiments." `CLAIM_SCOPE.md` was correspondingly left
untouched (its update was conditional on T5 running).

## Phase 4 (analysis and figure regeneration)

- New figures, originals preserved: `decisive_c0c3_interleaved.pdf/png` (F2, T1's clean
  rerun, marks the reproduced position-independent C3/Stencil bimodal cluster) and
  `the_squeeze_v2.pdf/png` (F3, fills the "prefetch OFF, real benchmark" cell the original
  explicitly marked NOT FOUND, using T4's data).
- `exclusion_manifest.csv`: added the cuFFT 25.47% hit-rate exclusion (demonstrated, T2).
- `ARTIFACT_CATALOG.md`: added artifact #6 (cuFFT blocked-protocol outlier).
- `COMPLETENESS_LEDGER.md`: all four originally-blocked items resolved and cross-
  referenced; the outlier-conditional claims table for VI-B marked superseded by T1's
  clean result; the cuFFT-hedge decision point gets a new recommended Option D (report
  both platforms' real data rather than treating the T4 null as a failed replication);
  VI-E updated to 6/7 workloads with the Stencil-24K caveat; two new open items (the
  wall-clock scale mismatch, the unexplained bimodal mechanism) surfaced for a future
  pass, neither blocking anything currently drafted.

## Verdict on the abstract's central claim

**Cannot be stated as one blanket sentence any longer -- must be split per-workload.**

- **GraphBFS-23:** confirmed. C3 (full speculation) is statistically indistinguishable
  from C1 (baseline), now with a tighter, better-powered null (MDE 0.16%).
- **Stencil-24K:** contradicted. C3 is reliably ~6.7% *slower* than C1, significant at
  p=9.69e-07 -- more decisive under the corrected interleaved protocol, not less. A
  reproducible, position-independent bimodal split underlies part of this comparison and
  is a genuine open mechanism question, not an artifact.
- **Neither result shows speculation actually helping** (the pre-registered primary
  falsification trigger never fired), so the paper's core negative finding about
  speculative prefetching's benefit is unchanged and, if anything, reinforced by two
  independent new mechanism findings this block produced: D5's CPU-cost argument (Phase 1,
  confirmed against real 595 source) and T4's worker-latency-vs-fault-rate race (new this
  block).

## End-to-end pipelining ceiling

**0.20% to 19.06%**, computable for 6 of 7 Phase C workloads (was 1 of 7 before this
block). The pre-existing Stencil-24K figure (~7.9%) remains on a different wall-clock
basis than these six and should not be blended into the same table without the caveat
(Section "Open items").

## cuFFT verdict

**The legacy 25.47% hit-rate figure and any implied cuFFT-favorable narrative do not
survive a controlled rerun.** At the exact matching configuration, hit rate is 4.07% (a
sixth of the legacy figure) with no accompanying wall-clock benefit. The RTX 5070 Ti 4.4%
figure (a separate, Phase-1, single-platform measurement) is not directly contradicted by
this -- T2 tested a different thing (SpecAsync's own stride policy on T4, on top of the
already-substantial stock-prefetcher benefit) -- but the manuscript can no longer treat
cuFFT as a platform-agnostic favorable case; `COMPLETENESS_LEDGER.md`'s updated cuFFT-hedge
section recommends reporting both platforms' real data side by side (Option D) rather than
either withholding the T4 null result or letting the RTX figure stand unqualified.

## What the manuscript can and cannot claim, updated

**Can claim, newly available this block:**
- A per-workload (not blanket) statement of the C3-vs-C1 comparison, with the Stencil
  bimodal mechanism noted as a real, reproducible phenomenon under active investigation.
- An end-to-end pipelining ceiling range (0.20-19.06%) for 6 of 7 workloads, replacing
  window-share-only language for those six.
- A cross-platform cuFFT data point (T4: null result) alongside the existing RTX 5070 Ti
  figure, per the updated Option D framing.
- A quantified, mechanism-level explanation for why real-workload speculation captures
  almost no hits even under ideal (oracle, prefetch-off) conditions: a worker-latency-vs-
  fault-rate race, not a prediction-accuracy failure.
- 595.71.05-verified (not v580-inferred) source citations for the full D5 call chain.

**Still cannot claim:**
- A single, workload-general statement that "C3 is statistically indistinguishable from
  C1" -- true for one benchmark, false for the other.
- An end-to-end ceiling for Stencil-24K on the same wall-clock basis as the other six
  workloads (the scale mismatch is unresolved, flagged twice independently, not chased
  further per both gates' own scope decisions).
- A core-count-contamination-ruled-out claim (T5 skipped) -- the 4-vCPU confound a
  reviewer might raise remains open, unlike in the original plan where T5 would have
  closed it.
- An explanation for *why* the C3/Stencil bimodal split exists (confirmed real and
  reproducible, mechanism unidentified).

## Storage and commit status

All GPU-experiment CSVs, harness scripts, Gate reports, updated figures, and analysis-doc
revisions are committed on `manuscript-prep`. Raw per-run telemetry rings (~600+ MB across
T1-T4) are retained on disk under the repo (EBS-backed, durable) but not committed to git,
matching this project's existing convention for raw ring dumps -- aggregate CSVs and Gate
reports carry the numbers that matter. `.gitignore` updated to cover these directories
explicitly rather than relying on an accidental pattern match. Harness run logs (small,
real provenance value) copied from `/opt/dlami/nvme/work/` into
`results/analysis/t4_run_logs/` and committed; nothing durable remains only in the
ephemeral scratch volume -- everything left there (the two 334 MB build trees) is
reconstructible via `driver/scripts/reconstruct_build_tree.sh` and is expected to be wiped
on the next instance Stop, by design.

## Open items for a future pass (not blocking, not chased further here)

1. **Absolute wall-clock scale mismatch** between Phase C's original Stencil-24K pairing
   (~1.6s) and every configuration tried on this instance for the nominally same workload
   (~4.1-4.3s) -- found independently in Gate 2 and Task T3, not resolved. Most likely
   explanation offered (Gate G3's overhead probe may not run the full `bench_stencil`
   binary) but not confirmed.
2. **The C3/Stencil-24K bimodal mechanism** -- confirmed real, reproducible, and
   position-independent, but the underlying cause (candidate: two GPU/CPU scheduling or
   cache/TLB regimes) is not identified.
3. **T5 (core-count control)** -- skipped this session; still available to run later if
   the reviewer-facing CPU-contention question needs closing.
4. **`manuscript_assets/`** -- untracked bundle from an earlier session, left for the
   author's decision (commit, gitignore, or discard).
