# GPU-Free Work Block 2 — Final Report

Summarizes every gate in this work block. Branch `manuscript-prep`, commits `c2a7e96`
through `7a0b9b6` (this report's own commit follows). No GPU was used or required; the two
explicitly out-of-scope tasks (2a: prefetch-off hit-rate rerun, 2b: cuFFT interleaved T4
rerun) were not attempted, simulated, or estimated, per this block's charter.

## Part 1 — Statistical follow-ups (gate Stencil-24K's significance before it becomes a
manuscript sentence)

- **B1 (Outlier/run-order forensics):** No timestamps exist in Gate 3 data, only per-config
  ordinal run indices. Only C2-vs-C1 has drift control (interleaved); the headline
  C3-vs-C1/C0 pair does not. The "two high runs" framing in the original task prompt was
  wrong — it's actually 5 of 15, positioned early-to-mid-block. A Tukey fence flags **zero**
  points in that cell (a masking artifact of the bimodal spread, not evidence of no
  problem). `results/analysis/OUTLIER_FORENSICS.md`.
- **B2 (Multiple-comparison correction):** Holm-Bonferroni flips **2 of 6** comparisons
  from significant to not significant — including the exact Stencil-24K C3-vs-C1 result
  driving Task B's original "claim not fully supported" finding. BH keeps both significant.
  `results/analysis/MULTIPLE_COMPARISONS.md`.
- **B3 (GraphBFS C2-vs-C1 anomaly):** Effect size (d=0.544) is below this design's own
  minimum detectable effect (d=1.060); doesn't survive Holm; traced to C1's own outlier
  runs, not to speculation helping. Draft manuscript sentence written.
  `results/analysis/GRAPHBFS_C2_ANOMALY.md`.
- **B4 (Pipelining ceiling, highest-value task):** Computable for **1 of 7** workloads only
  (Stencil-24K, ~7.9% of wall-clock, via Phase C's own overhead-validation harness — the
  only same-session wall-clock pairing that exists anywhere in Phase C). The other 6 have
  no wall-clock denominator on disk at all; reported as not computable rather than paired
  with a mismatched Gate 3/Phase B proxy. `results/analysis/PIPELINING_CEILING.md`.
- **B5 (Statistic of record):** Median declared; all four headline deltas verified to
  match exactly (+268.9%, +5.7%). D4+D5 range re-derived under both conventions
  (ratio-of-medians 63-74%, median-of-ratios 60.75-86.00%). `results/analysis/STATISTIC_OF_RECORD.md`.

## Part 2 — Remaining prior-block tasks

- **Task C (D5 source-level characterization):** Traced the D4/D5 span in
  `uvm_gpu_replayable_faults.c` (confirmed 595.71.05 tree) into `uvm_va_block.c`. Found the
  only synchronous `uvm_tracker_wait` in the chain is gated on CPU-destination migrations,
  which none of this project's benchmarks exercise — GPU migrations end via async
  `uvm_push_end()`, not a blocking wait. Flagged a genuine provenance gap: `uvm_va_block.c`
  doesn't exist anywhere on this machine for 595.71.05, only v580.95.05 (via the LFS-stored
  patch). `results/analysis/D5_CHARACTERIZATION.md`.
- **Task D (Artifact catalog v2 + claim scope):** Catalogued all 5 measurement artifacts
  (oracle cursor desync, ASLR instability, STREAM host noise, T2==T3 timer collapse,
  ring_read_binary drift) plus 2 rejected hypotheses. `ring_read_binary` is the one caught
  proactively (same-session gate) rather than after publication. Classified 16 project
  claims as driver-architectural vs. platform-specific-cost-ratio.
  `results/analysis/ARTIFACT_CATALOG.md`, `results/analysis/CLAIM_SCOPE.md`.
- **Task E (Bibliography audit):** All 20 `ref.bib` entries checked live (not just the 2
  flagged). Found 3 entries **miscited**, not just unpublished — `anonymous2022learningoversub`
  has real authors (Long/Gong/Zhou) and a real 2023 journal publication;
  `jain2019crac` has the wrong entry type and year (real venue: SC'20); `bastemTilesTR`
  was never a technical report (real venue: ICPP'17, peer-reviewed). Found 3 more
  preprints that have since been published, unprompted. `ref.bib` itself untouched;
  replacement BibTeX provided. `results/analysis/BIB_AUDIT.md`.
- **Task F (LaTeX skeleton):** No `main.tex` existed anywhere on this machine or in git
  history — built clean from scratch rather than "repairing" a nonexistent file, applying
  all the preamble-correctness constraints proactively. 9 named sections, all 5 figures
  wired to real `results/figures/*.pdf` paths, one table skeleton, commented-out
  cross-platform subsection. Build verified end-to-end (pdflatex → bibtex → pdflatex×2,
  zero errors, 4-page PDF). Caught and fixed a real bug during verification (`%` inside a
  `\caption{}` brace silently ate the TODO marker). `paper/main.tex`, `paper/ref.bib`.
- **Task G (Completeness ledger):** Walked all 9 sections; classified every needed
  number/figure/table. Recorded the B1/B2 outlier-conditional statistical claims and the
  B4 pipelining-ceiling computability finding, per this block's added requirement.
  Surfaced a genuine third gap (paired wall-clock timing for 6 Phase C workloads) beyond
  the two authorized T4 tasks — flagged as a candidate, unauthorized "Task 2c." Flagged
  the cuFFT single-platform hedge as an explicit author decision point (3 options, A/C
  recommended) rather than resolved unilaterally. `results/analysis/COMPLETENESS_LEDGER.md`.

## Part 3 — Pre-migration integrity check

- Working tree confirmed **not clean**, but for a pre-existing, already-diagnosed reason
  (git-lfs not installed on this machine → 3 `.patch` files show LFS-pointer-vs-real-content
  diffs) — left untouched rather than risk a one-way un-LFS'd commit. This session's own
  work is fully committed.
- `MANIFEST.sha256` (631 entries, `results/`+`tools/`+`tests/`+`benchmarks/`+`paper/`)
  written to repo root for post-transfer verification.
- `MIGRATION_NOTES.md` documents the git-lfs blocker, restates the two blocked GPU tasks'
  exact specs plus the new candidate Task 2c, records the 595.71.05 driver-version check
  to run before any T4 work, and recommends excluding `driver/build/` (reconstructible
  binaries) and `work_records.csv`/`batch_records.csv` (raw ring dumps, already restated in
  small aggregates) from the transfer — without deleting them from this machine.

## What changed in the manuscript's own claims as a result of this block

The single most consequential finding: the abstract's "C3 is statistically
indistinguishable from C1" cannot be stated as a blanket claim. It is false for
Stencil-24K under uncorrected testing, that result does not survive Holm-Bonferroni
correction, and it does survive Benjamini-Hochberg — three different defensible readings
of the same data, all reported rather than one silently chosen. This does not weaken "Path
B closed" (C3 still loses badly to C0 either way); if anything it makes that conclusion's
evidentiary chain more honest and more defensible against a reviewer who would otherwise
have found the gap first.

The second most consequential finding: no on-disk source ever stated a "~6% end-to-end
pipelining ceiling," and a rigorous from-scratch computation for the one workload where
it's computable at all (Stencil-24K) gives ~7.9%, in the same rough range but not
confirming the old number. Section VI should use window-share language (9-30%), not an
end-to-end percentage, until Task 2c (or equivalent) exists.

## Outstanding, explicitly not attempted this block

- Task 2a, 2b (blocked, out of scope, per charter).
- Task 2c (proposed but not authorized).
- `results/figures/FIGURE_NOTES.md` (from the original F1-F5 brief) and
  `results/figures/FIGURES_REPORT.md` (from the Figure-Phase-2 brief) — both superseded in
  practice by the exclusion-manifest system, per-script stdout verification, and this
  report, but never produced as the specifically-named files. Flagged for the record, not
  silently dropped.
- No manuscript prose was drafted anywhere, per this block's explicit instruction — the
  draft sentences in B3/B5 (explicitly requested exceptions) and every `% TODO: draft`
  marker in `paper/main.tex` are the only text resembling prose, and none of it is section
  body content.

## Commit range

`c2a7e96` (Part 1) → `d59ba50`(carried over) → `ff3db26` (Task C) → `67806ec` (Task D) →
`048efbc`/`4e526f4` (Task E) → `23cf3fe`/`664b128` (Task F) → `16d3dc6` (Task G) →
`7a0b9b6` (Part 3) → this report, on branch `manuscript-prep`.
