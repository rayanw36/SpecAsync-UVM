# Data-completeness ledger (Task G)

Walks all 9 sections of `paper/main.tex` and classifies every number, figure, or table
each section needs as **exists** (path given), **blocked-on-T4** (which of the two
explicitly-scoped T4 tasks, 2a/2b, unblocks it -- or, where neither does, a new gap
flagged explicitly), or **not-planned** (no data dependency / out of this project's
scope). Per this block's brief, also records which statistical claims are conditional on
outlier handling (Task B1/B2) and whether the end-to-end pipelining ceiling is computable
(Task B4).

**Update (T4 GPU work block, Phase 4): all four items in the "Gate G summary" below are
now resolved.** Task 2a -> T4 (`results/analysis/GATE_T4_REPORT.md`), Task 2b -> T2
(`results/analysis/GATE_T2_REPORT.md`), Task 2c -> T3 (`results/analysis/GATE_T3_REPORT.md`),
and the `uvm_va_block.c` 595.71.05 provenance gap -> Task 1.1
(`results/analysis/D5_CHARACTERIZATION.md`). Section-by-section updates below; original
text kept where still accurate rather than rewritten wholesale, so the history of what was
known when is legible.

## I. Introduction

| Needed | Status |
|---|---|
| Contribution list | **Exists** (draft) -- `paper/intro_revisions.md` Replacement 1, but written against Phase 1 results only; needs revision to incorporate the Phase 2/Gate 3 "Path B closed" finding before use |
| Motivation/hypothesis paragraph | **Exists** (draft) -- `paper/intro_revisions.md` Replacement 2, same caveat |
| No figures/tables in this section | not-planned |

## II. Related Work

| Needed | Status |
|---|---|
| Correctly-cited bibliography | **Exists** -- `results/analysis/BIB_AUDIT.md` (all 20 entries classified, 3 miscited entries with replacement BibTeX provided) |
| Related-work prose | Not yet drafted; no data blocker, purely a writing task |

## III. Background: UVM Replayable Fault Handling

| Needed | Status |
|---|---|
| D1-D6 sub-phase definitions, call tree | **Exists** -- `results/analysis/D5_CHARACTERIZATION.md`, cited against the confirmed 595.71.05 tree for `uvm_gpu_replayable_faults.c` |
| Deeper call-tree citations (`uvm_va_block.c`) | **Exists, provenance gap closed** -- the T4 GPU instance's `/usr/src/nvidia-595.71.05/` DOES carry driver source (a fact the original ledger's "T4 has only running binaries" assumption got wrong), so Task 1.1 re-traced the full D5 span against the real 595.71.05 file. `uvm_va_block_service_locked`/`uvm_va_block_service_copy` (the functions carrying the classification) are byte-identical to the v580.95.05 chain; four small, classification-irrelevant diffs found and reported. See `D5_CHARACTERIZATION.md` \S0, \S2b |

## IV. Design: SpecAsync Infrastructure

| Needed | Status |
|---|---|
| Infrastructure description (ring, policy dispatch, telemetry) | **Exists** (draft) -- `paper/intro_revisions.md` Replacement 1, and the design is directly readable from `driver/src/specasync_*` |
| No figures/tables required | not-planned |

## V. Implementation

| Needed | Status |
|---|---|
| Module/patch structure description | **Exists** -- `driver/PORTING_NOTES_595.md`, `driver/src/` |
| Line-count / invariant-preservation claims | **Exists** -- verifiable directly from source; `paper/intro_revisions.md` already states "<400 lines of net new kernel C" (not independently re-verified by this ledger -- flag for a `wc -l`-style check before the number is finalized) |

## VI. Evaluation

### VI-A. Experimental Setup

| Needed | Status |
|---|---|
| RTX 5070 Ti platform spec | **Exists** -- `paper/abstract_v2.md`, `results/figures/CUFFT_PROVENANCE.md` |
| Tesla T4 / g4dn.xlarge platform spec | **Exists** -- `results/phaseC/PHASEC_REPORT.md` header |
| Consolidated setup table (both platforms, one place) | Not yet assembled; no data blocker, an editorial consolidation task |

### VI-B. Policy Sweep and the Decisive C0-C3 Comparison

| Needed | Status |
|---|---|
| Figure 1 (`policy_matrix`) | **Exists** -- `results/figures/policy_matrix.pdf` |
| Figure 2 (`decisive_c0c3`) | **Exists**, plus a second, cleaner version -- `results/figures/decisive_c0c3.pdf` (original, blocked protocol) and `results/figures/decisive_c0c3_interleaved.pdf` (T1, strictly interleaved, the figure that should carry the headline claim going forward) |
| Table I (Gate 3 summary numbers) | **Exists as data**, not yet transcribed into the LaTeX table body -- source `results/analysis/STATISTIC_OF_RECORD.md` for the original data, `results/analysis/GATE_T1_REPORT.md` for the interleaved rerun (the version that should be transcribed) |
| Statistical validation of "C3 statistically indistinguishable from C1" | **Exists, and is NOT a blanket-supportable claim -- confirmed again, in more detail, by the interleaved rerun** -- `results/analysis/STATISTICS.md` (original), `results/analysis/GATE_T1_REPORT.md` (T1, authoritative) |
| **Outlier-conditional claims (original, Task B1/B2)** | See table below -- **superseded by T1's clean rerun**, kept for provenance |
| **T1 interleaved rerun result (new, supersedes the table below for the headline claim)** | See "T1 update" subsection immediately after the table |

**Claims conditional on outlier handling / multiple-comparison correction:**

| Claim | Uncorrected verdict | Holm-corrected verdict | BH-corrected verdict | With Tukey outliers removed |
|---|---|---|---|---|
| C3 vs C1, Stencil-24K, significant? | Significant (MWU p=0.036) | **Not significant** | Significant | Unchanged (no Tukey points flagged in this cell -- masking effect, see `OUTLIER_FORENSICS.md` \S2a) |
| C2 vs C1, GraphBFS-23, significant? | Significant (MWU p=0.031) | **Not significant** | Significant | Unchanged/strengthens (MWU p drops to 0.014) |
| C3 vs C1, GraphBFS-23, significant? | Not significant | Not significant | Not significant | **Flips to borderline** by the OR-of-Welch/MWU rule after removing C1's own outliers, though MWU alone (the authoritative test per `STATISTICS.md`'s own normality-rejection rule) stays non-significant at p=0.063 -- see `OUTLIER_FORENSICS.md` \S3 caveat |

**Implication for the manuscript:** the abstract's headline claim cannot be stated as a
single unconditional sentence. It must specify (a) per-benchmark scope, (b) whether Holm
or BH correction is being applied (they disagree on 2 of 6 comparisons), and (c) that the
GraphBFS C3-vs-C1 result is sensitive to outlier handling in exactly the direction that
would, if anything, *strengthen* rather than weaken "Path B closed."

**T1 update (interleaved rerun, authoritative going forward):** the table above was built
on Gate 3's original protocol, which B1 found only C2-vs-C1 was actually interleaved --
C3-vs-C1 and C3-vs-C0 (the abstract's headline pair) were blocked, with no drift control.
`results/analysis/GATE_T1_REPORT.md` reran all four configs under a strict, fully
interleaved rotation (pre-registered in advance, `PREREGISTRATION.md`). Result, and it
is the opposite of what the contamination hypothesis predicted:

| Primary comparison | Holm-corrected verdict (interleaved) | vs. original (blocked) |
|---|---|---|
| C3 vs C1, Stencil-24K | **SIGNIFICANT** (p=9.69e-07, d=1.749) | was marginal/Holm-non-significant (p=0.036) -- now far more decisive, not less |
| C3 vs C1, GraphBFS-23 | Not significant (p=0.776, d=0.103) | consistent with original; MDE tightened from 1.02% to 0.16% |

The abstract's claim must now be split per-workload: confirmed indistinguishable for
GraphBFS-23 (well-powered null), contradicted for Stencil-24K (C3 reliably ~6.7% slower
than C1). This is the authoritative statistical result for the headline claim -- the
outlier-conditional table above is retained for provenance but should not be the version
cited in the manuscript. Also new: the C3/Stencil-24K bimodal split (visible in both the
original and interleaved data) is now proven NOT position-correlated
(Spearman rho=-0.011, p=0.965 against run-order) -- a genuine two-state mechanism worth a
discussion-section sentence, not a warm-up artifact.

### VI-C. Prefetch Opportunity vs. Cost

| Needed | Status |
|---|---|
| Figure 3 (`the_squeeze`) | **Exists**, plus an updated version filling the gap below -- `results/figures/the_squeeze.pdf` (original) and `results/figures/the_squeeze_v2.pdf` (T4, adds the previously-missing prefetch-OFF real-benchmark inset) |
| Prefetch-OFF real-benchmark hit-rate data | **Exists -- Task 2a resolved as Task T4** (`results/analysis/GATE_T4_REPORT.md`). Real workloads under prefetch-OFF, oracle policy: 0.02-0.25% hit rate, four orders of magnitude below the deterministic probe's 99.6%. Root cause identified: real fault rates (0.4-4.7M/s) outrun the async worker's scheduling latency -- a rate mismatch, not a prediction-accuracy failure (the oracle predicts perfectly by construction and still can't get credited). This is a sharper, more specific mechanism finding than "irregular access defeats prediction" |

### VI-D. Oversubscription

| Needed | Status |
|---|---|
| Figure 4 (`oversub_collapse`) | **Exists** -- all three regimes are POST-fix Phase B.1 data, `results/phaseB1/gate_d/` |

### VI-E. Fault-Dispatch-Window Decomposition

| Needed | Status |
|---|---|
| Figure 5 (`fault_density_sweep`) | **Exists** -- `results/figures/fault_density_sweep.pdf` |
| D4/D5 async-not-sync-wait mechanism | **Exists** -- `results/analysis/D5_CHARACTERIZATION.md` |
| **End-to-end pipelining ceiling (new requirement, Task B4)** | **Now computable for 6 of 7 workloads -- Task 2c resolved as Task T3** (`results/analysis/GATE_T3_REPORT.md`). Stencil-8K, GraphBFS-23, Sweep-4K/8K/16K/24K now have same-session paired wall-clock: ceiling range 0.20% (GraphBFS-23, compute-bound) to 19.06% (Stencil-8K). **Caveat, not a new problem:** the pre-existing Stencil-24K figure (~7.9%, `PIPELINING_CEILING.md`) uses a wall-clock provenance that does not match this session's measurement of the same nominal workload under the same module config (1.6s vs 4.1s) -- confirmed as the same discrepancy Gate 2 (`GATE2_REPORT.md`) independently found and flagged, not resolved further. Report the six new numbers and the one pre-existing Stencil-24K number as two separately-sourced sets, per `GATE_T3_REPORT.md` \S4 and \S6, rather than blending into one seven-workload table without the footnote |

### VI-C (commented, not drafted) -- Cross-Platform Confirmation

| Needed | Status |
|---|---|
| Prefetch-off hit-rate on T4 | **Exists -- Task 2a resolved as Task T4**, see above |
| cuFFT interleaved rerun on T4 | **Exists -- Task 2b resolved as Task T2** (`results/analysis/GATE_T2_REPORT.md`). Result: the legacy 25.47% hit-rate figure does NOT reproduce (4.07% at the exact matching size/policy/depth/prefetch configuration -- a sixth of the original), and no wall-clock effect either direction |

**Both data blockers for this subsection are now resolved.** This ledger does not draft
the prose or un-comment the section in `paper/main.tex` (out of this work block's charter
-- "Do not draft manuscript prose"), but the data dependency that justified keeping it
commented out is gone. The manuscript author can now write this subsection with real
T4 data for both of its planned claims.

## VII. Discussion

| Needed | Status |
|---|---|
| Median-of-ratios vs. ratio-of-medians methodology sentence | **Exists** -- `results/analysis/STATISTIC_OF_RECORD.md` \S3 |
| D3 "no lock pressure" honest sentence | **Exists** -- `results/analysis/STATISTIC_OF_RECORD.md` \S4 |
| GraphBFS C2-vs-C1 anomaly treatment | **Exists** -- `results/analysis/GRAPHBFS_C2_ANOMALY.md` \S5 |

## VIII. Limitations and Threats to Validity

| Needed | Status |
|---|---|
| Five-artifact catalog | **Exists** -- `results/analysis/ARTIFACT_CATALOG.md` |
| Claim-scope split (architectural vs. platform-cost-ratio) | **Exists** -- `results/analysis/CLAIM_SCOPE.md` |
| Gate 3 run-ordering limitation | **Exists** -- `results/analysis/OUTLIER_FORENSICS.md` \S1 (only C2-vs-C1 has drift control between its two arms) |
| **The cuFFT single-platform hedge -- decision point, flagged explicitly per the brief** | See dedicated section below |

## IX. Conclusion

No new data dependency -- synthesizes the above. Not blocked.

---

## The cuFFT-hedge decision point (flagged explicitly, as required)

**Update: Task 2b is no longer out of scope -- it ran as Task T2, and materially changes
this decision point.** `paper/abstract_v2.md` currently states cuFFT gains "up to 4.4%
(mean, n=50, Exp1)" as a Phase 1 headline number, measured **only on the RTX 5070 Ti**.
Task T2's controlled, interleaved T4 rerun (`results/analysis/GATE_T2_REPORT.md`) found
**no wall-clock benefit from SpecAsync speculation on cuFFT on T4** (p0-vs-p2 wall-clock:
0.00-0.94% delta, not a reproducible benefit in either direction) and that the
telemetry-level hit-rate figure this project's own T4 data previously showed for cuFFT
(25.47%, `phaseB_telemetry.csv`) does not reproduce under a controlled rerun (4.07% at the
exact matching configuration). This is a genuine second-platform data point, and it is a
null result, not a confirmation.

Below is the original three-option framing, followed by how T2's result should update it.

Original framing (Phase 1, before T2 existed):

- **Option A:** Publish the 4.4% figure as-is with an explicit single-platform hedge
  ("measured on RTX 5070 Ti only; cross-platform confirmation pending") -- consistent with
  how `CLAIM_SCOPE.md` classifies it (platform-specific-cost-ratio) and with the paper's
  own already-honest framing elsewhere ("modest and workload-dependent," "(mean, n=50,
  Exp1)").
- **Option B:** Withhold the specific percentage from the abstract/headline until Task 2b
  lands, and describe the Phase 1 cuFFT result only qualitatively ("a measurable but
  modest gain on one platform") in the body, reserving the number for a table.
- **Option C:** Keep the number but explicitly frame it as a Phase-1/single-platform
  result throughout, with the VI-C cross-platform subsection (currently commented out)
  as the designated place a future T4 number would go, and no claim of generality made
  anywhere else in the paper.

This ledger recommends **Option A or C** (both keep the number, differ only in placement)
over **Option B**, since the number is real, correctly attributed, and already hedged in
the existing abstract draft -- withholding it entirely would understate a genuine, if
platform-specific, positive result. But this is the author's call, not a data question;
flagged here rather than decided.

**With T2's result in hand, this recommendation still holds, but needs a fourth option
added to the menu:**

- **Option D (new):** Publish the 4.4% RTX 5070 Ti figure as in Option A/C, AND
  separately report the T4 null result (Task T2) as its own data point -- explicitly
  framed as "measured on a different platform, not a replication of the RTX 5070 Ti
  finding" rather than as a failed cross-platform confirmation. The two results are not
  necessarily in tension: cuFFT's 4.4% figure on RTX 5070 Ti was never claimed to be
  SpecAsync-attributable at the mechanism level this ledger can verify (Task 1's
  provenance audit already flagged it as a Phase-1/single-platform number of uncertain
  generality), and T2's T4 finding is specifically about SpecAsync's own stride policy on
  top of the (already very effective) stock prefetcher, not about cuFFT overall. Silently
  dropping the RTX number because a differently-configured T4 rerun found nothing would
  overstate what T2 actually tested; silently omitting the T4 null result would understate
  what this project now knows. **Recommended: Option D**, superseding the original A/C
  preference now that real T4 data exists to report alongside the RTX figure rather than
  in its place.

## Gate G summary: missing + unblockable + load-bearing items

Original short list (Phase 1/GPU-free work block), all four now resolved by the T4 GPU
work block:

1. **Prefetch-off real-benchmark hit-rate data** (VI-C) -- ~~blocked on T4 Task 2a~~ **RESOLVED, Task T4.** `results/analysis/GATE_T4_REPORT.md`.
2. **cuFFT T4 cross-platform rerun** (VIII, cuFFT hedge) -- ~~blocked on T4 Task 2b~~ **RESOLVED, Task T2.** `results/analysis/GATE_T2_REPORT.md`.
3. **Paired wall-clock timing for 6 of 7 Phase C workloads** (VI-E, pipelining ceiling) -- ~~not currently an authorized task~~ **RESOLVED, Task T3** (authorized and run this work block). `results/analysis/GATE_T3_REPORT.md`.
4. **`uvm_va_block.c` for the 595.71.05 tree** (III, Background) -- ~~not a T4 problem~~ **RESOLVED, Task 1.1.** The original assumption that T4 "would only have a running binary, not source" was wrong -- `/usr/src/nvidia-595.71.05/` on the T4 instance does carry driver source. `results/analysis/D5_CHARACTERIZATION.md`.

**New items surfaced by this work block's own results, not yet resolved (candidates for a
future pass, not blocking anything already drafted):**

5. **Absolute wall-clock scale mismatch, Phase C vs. Gate 3 vs. this session** (VI-E) -- Gate 2 (`GATE2_REPORT.md`) and Gate T3 (`GATE_T3_REPORT.md` \S4) both independently found that Phase C's original Stencil-24K wall-clock pairing (~1.6s) does not reproduce under any module configuration tried on this instance (~4.1-4.3s under the closest analog, C0-equivalent). Not resolved; most likely explanation offered (Gate G3's overhead probe may not run the full `bench_stencil` binary) but not confirmed. Load-bearing only for whether the pre-existing Stencil-24K ceiling figure (~7.9%) can be presented on the same basis as the six new Task T3 numbers -- it currently cannot and should be flagged as such (Task T3 \S4/\S6).
6. **C3/Stencil-24K bimodal mechanism, unexplained** (VII, Discussion) -- Task T1 confirmed the bimodal wall-time split is real and reproducible under strict interleaving, and ruled out position/warm-up/drift as the cause (Spearman rho=-0.011, p=0.965), but did not identify the underlying mechanism (candidate: two GPU/CPU scheduling or cache/TLB regimes). Worth a sentence acknowledging the open question in the discussion section; not load-bearing for any existing claim's correctness.

Items 1-4 all trace back to the same root cause the original ledger correctly identified:
this project consistently declines to simulate, estimate, or infer missing data rather
than collect it -- and the T4 GPU work block existed specifically to collect it. Items 5-6
are the same discipline applied one level deeper: report what's now known, flag what
still isn't, rather than paper over either.
