# Data-completeness ledger (Task G)

Walks all 9 sections of `paper/main.tex` and classifies every number, figure, or table
each section needs as **exists** (path given), **blocked-on-T4** (which of the two
explicitly-scoped T4 tasks, 2a/2b, unblocks it -- or, where neither does, a new gap
flagged explicitly), or **not-planned** (no data dependency / out of this project's
scope). Per this block's brief, also records which statistical claims are conditional on
outlier handling (Task B1/B2) and whether the end-to-end pipelining ceiling is computable
(Task B4).

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
| Deeper call-tree citations (`uvm_va_block.c`) | **Exists but with a provenance caveat** -- only available via the v580.95.05 patch-embedded source; no 595.71.05 copy of this file exists anywhere on this machine. Not blocked on T4 (T4 doesn't have driver *source*, only running binaries) -- would require either locating a 595 source archive or accepting the v580 chain as representative (recommended in `D5_CHARACTERIZATION.md` \S0) |

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
| Figure 2 (`decisive_c0c3`) | **Exists** -- `results/figures/decisive_c0c3.pdf` |
| Table I (Gate 3 summary numbers) | **Exists as data**, not yet transcribed into the LaTeX table body -- source `results/analysis/STATISTIC_OF_RECORD.md` |
| Statistical validation of "C3 statistically indistinguishable from C1" | **Exists, and is NOT a blanket-supportable claim** -- `results/analysis/STATISTICS.md` |
| **Outlier-conditional claims (new requirement, Task B1/B2)** | See table below |

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

### VI-C. Prefetch Opportunity vs. Cost

| Needed | Status |
|---|---|
| Figure 3 (`the_squeeze`) | **Exists** -- `results/figures/the_squeeze.pdf` |
| Prefetch-OFF real-benchmark hit-rate data | **Blocked-on-T4, Task 2a** (prefetch-off hit-rate rerun) -- confirmed not to exist anywhere on disk by `tools/figures/make_fig_the_squeeze.py`'s own stdout check; the figure documents this gap rather than estimating it |

### VI-D. Oversubscription

| Needed | Status |
|---|---|
| Figure 4 (`oversub_collapse`) | **Exists** -- all three regimes are POST-fix Phase B.1 data, `results/phaseB1/gate_d/` |

### VI-E. Fault-Dispatch-Window Decomposition

| Needed | Status |
|---|---|
| Figure 5 (`fault_density_sweep`) | **Exists** -- `results/figures/fault_density_sweep.pdf` |
| D4/D5 async-not-sync-wait mechanism | **Exists** -- `results/analysis/D5_CHARACTERIZATION.md` |
| **End-to-end pipelining ceiling (new requirement, Task B4)** | **Computable for 1 of 7 workloads only** (Stencil-24K, ~7.9% of wall-clock, via Phase C's own G3 overhead-validation harness -- see `results/analysis/PIPELINING_CEILING.md`). The other 6 (GraphBFS-23, Stencil-8K, Sweep-4K/8K/16K/24K) have **no same-session wall-clock pairing on disk at all** -- this is **not** one of the currently-scoped T4 tasks (2a/2b); it is a genuine third gap this ledger is surfacing for the first time: call it **Task 2c (not yet authorized)** -- re-run each Phase C workload with paired instrumented-build wall-clock timing, so the dispatch-window share can be converted to an end-to-end percentage for all 7 workloads, not just 1. Until 2c happens (on T4, since that's where the Phase C driver build lives), Section VI-E should report window-share percentages (9-30%) with an explicit caveat, not an end-to-end number, per `PIPELINING_CEILING.md`'s own recommendation |

### VI-C (commented, not drafted) -- Cross-Platform Confirmation

| Needed | Status |
|---|---|
| Prefetch-off hit-rate on T4 | **Blocked-on-T4, Task 2a** |
| cuFFT interleaved rerun on T4 | **Blocked-on-T4, Task 2b** |

**This entire subsection is out of scope for the current GPU-free work block** and remains
commented out in `paper/main.tex` per Task F's instruction. Both blocking tasks are
explicitly declared out of scope on this machine by this block's own brief -- "do not
attempt them, do not simulate them, do not estimate their results."

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

`paper/abstract_v2.md` currently states cuFFT gains "up to 4.4% (mean, n=50, Exp1)" as a
Phase 1 headline number, measured **only on the RTX 5070 Ti**. Task 2b (a cuFFT
interleaved rerun on the T4) would provide a second-platform check, and is **explicitly
out of scope for this work block** ("do not attempt, do not simulate, do not estimate").

This leaves the manuscript with a real, unresolved decision that this ledger can surface
but not make on the author's behalf:

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

## Gate G summary: missing + unblockable + load-bearing items

Short list, per the brief's closing instruction -- items that are (a) missing, (b) not
resolvable on this machine even with more time, and (c) load-bearing for a specific
section:

1. **Prefetch-off real-benchmark hit-rate data** (VI-C) -- blocked on T4 Task 2a. Load-bearing for the "opportunity vs. cost" figure's completeness (currently documents the gap rather than filling it).
2. **cuFFT T4 cross-platform rerun** (VIII, cuFFT hedge) -- blocked on T4 Task 2b. Load-bearing for whether the abstract's 4.4% figure can be stated as more than single-platform.
3. **Paired wall-clock timing for 6 of 7 Phase C workloads** (VI-E, pipelining ceiling) -- not currently an authorized task (candidate "Task 2c", not yet approved). Load-bearing for whether Section VI-E can state an end-to-end speedup ceiling at all, vs. window-share language only.
4. **`uvm_va_block.c` for the 595.71.05 tree** (III, Background) -- not a T4 problem (T4 would only have a running binary, not source); would require locating a 595 driver source archive. Load-bearing for whether Section III's deeper call-tree citations are 595-verified or only 580-inferred.

Items 1-3 all trace back to the same root cause: **this GPU-free work block correctly
declined to simulate, estimate, or infer any of them**, per its own standing policy. None
of the four are optional polish -- each is directly load-bearing for a specific claim's
scope or a specific figure's completeness.
