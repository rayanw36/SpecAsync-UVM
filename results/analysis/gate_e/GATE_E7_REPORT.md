# Gate E7 — Report: is prefetch-threshold tuning real, and does it generalise?

Pre-registration: `E7_PREREGISTRATION.md` (committed and pushed before any E7 run, `88a0f2c`). Log: `e7/E7_STATUS.md`.
Data: `e7/e7_runs.csv` (310 rows). Analysis: `tests/e7_analyze.py` (outputs in `e7/`). Figure:
`e7_threshold_by_workload.png` / `.pdf`. Platform: RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34, `multi-user.target`.
delta = (arm − baseline) ÷ baseline, so **negative = the arm is faster**. n = 10 per cell. `stock-t51` is the shipped driver;
`stock-t0/t10/t25` are not.

## Headline

**XA is confirmed.** On the stock module, Stencil-24K at threshold 0 is **9.57% faster** than at the shipped 51
(p = 1.08e-05, Holm-significant, MDE 1.1%), and threshold 10 is **7.13% faster** (p = 1.08e-05). E6's descriptive
−9.17% / −7.72% replicate in a separate, pre-registered run on a different module (stock instead of the E3a-2 module).

**Lowering the threshold did not significantly slow any of the 8 other workloads, and sped up four of them.**
Holm family of 16: **faster** at t0 on Sweep-16K (−8.02%), STREAM (−12.37%), SGEMM (−2.49%) and oversubscribed
Stencil (−16.95%); also faster at t25 on those four (−3.98%, −6.20%, −1.64%, −11.56%). No significant slowdown anywhere
(no cell has a Holm-significant positive delta). Not significant: Stencil-8K, Sweep-4K, cuFFT and GraphBFS-23, each
with an MDE at the family α of 0.9–12%, so a real effect of a few percent on the three small workloads would not have been detected.

**Session drift (Family C) is not detectable:** neither E3a-2 arm moved significantly between block 1 and block 2
(C0 −0.37%, C7W512 +0.59%, both n.s.).

## Expectations (reviewer, directional; operational definitions in the pre-registration)

| id | expectation | outcome | basis |
|---|---|---|---|
| XA | C0-t0 faster than C0-t51 on Stencil-24K, significant | **held** | −9.57%, p 1.08e-05, Holm-sig |
| XB1 | no workload among Stencil-8K, Sweep-4K, Sweep-16K, STREAM, SGEMM significantly slower at t0 | **held** | none slower; two n.s., three significantly faster |
| XB2 | GraphBFS-23: no significant difference at either threshold | **held** | t0 −0.26% (p 0.018, above its Holm threshold 0.0063), t25 +0.06% |
| XB3 | oversubscribed Stencil: C0-t0 significantly **slower** than C0-t51 | **FAILED** | the opposite: **−16.95%** faster (p 1.08e-05, Holm-sig) |
| XB4 | cuFFT: C0-t0 not significantly faster than C0-t51 | **held** | −4.90%, p 0.036, not Holm-significant (threshold 0.0071) |
| XC | C7W512-t51's block-to-block median difference larger than C0-t51's | **held, weakly** | 0.59% vs 0.37% by the operational definition; neither is significant and both are far inside the MDE (0.027 s and 0.010 s) |

XB3 had the lowest prior (about 55%) and is the clearest miss. XC is held by its operational definition but supports no
conclusion about drift. cuFFT's −4.90% is borderline: it would count as "faster" under an uncorrected 0.05 test.

## Family A — confirmatory (stock module, Stencil-24K; Holm of 2)

| arm vs stock-t51 | median arm (s) | median t51 (s) | delta | p | Holm thr | result | Cohen's d | MDE (s, %) | MDE at family α (%) | without outliers: delta s / p |
|---|---:|---:|---:|---:|---:|:---:|---:|---|---:|---|
| stock-t0 | 1.0251 | 1.1336 | -9.57% | 1.08e-05 | 0.0250 | **faster** | -10.63 | 0.0127 (1.12%) | 1.23 | -0.1085 / 1.6e-04 |
| stock-t10 | 1.0528 | 1.1336 | -7.13% | 1.08e-05 | 0.0500 | **faster** | -7.73 | 0.0132 (1.16%) | 1.28 | -0.0808 / 4.6e-05 |

## Family B — generality (stock module; one Holm family of 16)

Every significant slowdown would be reported here as prominently as the speedups: **there is none.**

| workload | arm vs stock-t51 | median arm (s) | median t51 (s) | delta | p | Holm thr | result | Cohen's d | MDE (%) | MDE at family α (%) | without outliers: delta s / p |
|---|---|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---|
| Stencil-8K | stock-t0 | 0.3168 | 0.3322 | -4.65% | 1.23e-01 | 0.0083 | n.s. | -0.70 | 7.68 | 10.41 | -0.0130 / 2.1e-01 |
| Stencil-8K | stock-t25 | 0.3218 | 0.3322 | -3.13% | 1.23e-01 | 0.0100 | n.s. | -0.44 | 7.52 | 10.20 | -0.0080 / 7.7e-02 |
| Sweep-4K | stock-t0 | 0.2498 | 0.2418 | +3.34% | 9.71e-01 | 0.0250 | n.s. | +0.13 | 8.68 | 11.77 | +0.0081 / 9.7e-01 |
| Sweep-4K | stock-t25 | 0.2647 | 0.2418 | +9.47% | 2.18e-01 | 0.0125 | n.s. | +0.72 | 9.16 | 12.42 | +0.0229 / 2.2e-01 |
| Sweep-16K | stock-t0 | 0.5790 | 0.6294 | -8.02% | 1.08e-05 | 0.0031 | **faster** | -6.20 | 1.62 | 2.19 | -0.0505 / 1.1e-05 |
| Sweep-16K | stock-t25 | 0.6044 | 0.6294 | -3.98% | 1.50e-03 | 0.0050 | **faster** | -1.64 | 2.56 | 3.47 | -0.0254 / 2.2e-05 |
| STREAM | stock-t0 | 0.5417 | 0.6181 | -12.37% | 1.08e-05 | 0.0033 | **faster** | -5.52 | 2.74 | 3.71 | -0.0772 / 2.2e-05 |
| STREAM | stock-t25 | 0.5798 | 0.6181 | -6.20% | 5.20e-03 | 0.0056 | **faster** | -1.49 | 3.99 | 5.41 | -0.0394 / 4.1e-04 |
| SGEMM | stock-t0 | 4.5152 | 4.6308 | -2.49% | 1.08e-05 | 0.0036 | **faster** | -10.04 | 0.30 | 0.41 | -0.1162 / 2.2e-05 |
| SGEMM | stock-t25 | 4.5547 | 4.6308 | -1.64% | 1.08e-05 | 0.0038 | **faster** | -8.44 | 0.24 | 0.32 | -0.0760 / 1.1e-05 |
| cuFFT | stock-t0 | 0.3711 | 0.3902 | -4.90% | 3.55e-02 | 0.0071 | n.s. | -0.98 | 5.36 | 7.27 | -0.0191 / 3.5e-02 |
| cuFFT | stock-t25 | 0.3842 | 0.3902 | -1.55% | 6.31e-01 | 0.0167 | n.s. | -0.17 | 6.19 | 8.38 | -0.0060 / 6.3e-01 |
| GraphBFS-23 | stock-t0 | 31.4241 | 31.5066 | -0.26% | 1.85e-02 | 0.0063 | n.s. | -1.04 | 0.63 | 0.86 | -0.0910 / 1.1e-02 |
| GraphBFS-23 | stock-t25 | 31.5242 | 31.5066 | +0.06% | 1.00e+00 | 0.0500 | n.s. | -0.08 | 0.84 | 1.14 | +0.0164 / 1.0e+00 |
| Stencil oversub (N=48000, 1 iter) | stock-t0 | 2.7060 | 3.2583 | -16.95% | 1.08e-05 | 0.0042 | **faster** | -24.20 | 0.87 | 1.18 | -0.5523 / 1.1e-05 |
| Stencil oversub (N=48000, 1 iter) | stock-t25 | 2.8816 | 3.2583 | -11.56% | 1.08e-05 | 0.0045 | **faster** | -17.60 | 0.81 | 1.10 | -0.3728 / 4.6e-05 |

Notes: the absolute effect on short workloads is diluted by fixed process start-up and CUDA initialisation inside the
timed region (process wall-clock is the outcome of record), which is also why the MDEs on Stencil-8K, Sweep-4K and cuFFT
are large (5–12% of a 0.25–0.4 s run). GraphBFS-23's MDE is 0.6–0.9%.

## Family C — session drift (E3a-2 module, Stencil-24K; Holm of 2)

| arm | block 1 median (s) | block 2 median (s) | delta (block 2 − block 1) | p | Holm thr | result | MDE (s) |
|---|---:|---:|---:|---:|---:|:---:|---:|
| spec-C0-t51 | 1.1387 | 1.1345 | -0.37% | 6.31e-01 | 0.0500 | n.s. | 0.0104 |
| spec-C7W512-t51 | 1.0705 | 1.0767 | +0.59% | 3.53e-01 | 0.0250 | n.s. | 0.0271 |

Session medians, prefetch on, threshold 51 (descriptive; E4–E6 from the committed run CSVs):

| session | C0-t51 median (s) | C7W512-t51 median (s) | C7 vs C0 |
|---|---:|---:|---:|
| E4 | 1.1295 | 1.0738 | -4.93% |
| E5 | 1.1265 | 1.0673 | -5.26% |
| E6 | 1.1298 | 1.0918 | -3.36% |
| E7 (blocks pooled) | 1.1363 | 1.0756 | -5.34% |
| E7 block 1 | 1.1387 | 1.0705 | -5.99% |
| E7 block 2 | 1.1345 | 1.0767 | -5.09% |

- **C0-t51 is stable across all four sessions** (1.1265–1.1363 s). C7W512-t51 ranges 1.0673–1.0918 s; E6's was the highest
  and E7's pooled value (1.0756 s, −5.34%) agrees with E4 (−4.93%) and E5 (−5.26%). **E6's −3.36% is the outlier session.**
  Within E7 there is no detectable drift between blocks. The cause of E6's higher C7W512 median is **not established**
  (the table-ordering hypothesis in `e7/E7_PARAM_CHECK.md` §3 was not tested; E7 used one table).
- **Module presence cost (descriptive, untested):** the E3a-2 module with speculation off (spec-C0-t51, 1.1363 s) vs the stock module at
  t51 (1.1336 s): +0.24%, p = 0.35. No presence cost is detectable at this n (compare CS2-14, measured on the T4).
- **Cross-check of the E6 headline (descriptive):** pooled spec-C7W512-t51 (1.0756 s) is **4.92% slower than stock-t0**
  (1.0251 s), the same direction as E6's +6.39%.

## Figure

`e7_threshold_by_workload.png` (and `.pdf`): wall-clock change versus the median at t51, per workload, with all runs as points
and the cell median as a line. A filled marker is Holm-significant versus t51; the t51 marker is the baseline and hollow by construction.

## Run integrity

- 310 rows (Family C block 1: 20; Family A: 30; Family B: 240 across 8 workloads; Family C block 2: 20); all `exit_code` 0; the
  read-back threshold equals the order file's in every row; srcversions are only `6284DA42…` (stock rows) and `33FD42E6…` (E3a-2 rows);
  `ft_fast_verified` 1 on every C7W512 load; `ft_fast_cas_giveup` and `spec_region_invalid` 0 throughout. No stop file. No Family B
  workload was skipped. 27 smoke runs (`e7/e7_smoke.csv`) are excluded.
- Four runs (idx 89, 130, 204, 245) each logged one new kernel line: `workqueue: drm_fb_helper_damage_work hogged CPU` (the same notice and
  counts as in E6). It is not in the stop pattern. No run was removed.
- Self-tests wrote only to a scratch directory outside `results/`. The analyzer's positive control reproduces E6 (+6.39%, p 1.08e-05, D(51) +0.4017).
- The first push after `Phase 4` failed headless (`gh` keeps its token in the GNOME keyring). See the status log for what is pushed.

## Limitations

- `stock-t0/t10/t25` are not the shipped driver. A lower threshold means the density rule fires earlier and prefetches more; this gate
  does not measure memory-footprint or bandwidth side-effects, nor behaviour under thrashing beyond the one oversubscribed configuration.
- n = 10 per cell; the three short workloads and cuFFT are underpowered for effects below about 5–12%.
- Stock module only for Families A and B: wall-clock only, no fault counts, so the **mechanism** (fewer demand faults at lower thresholds) is E6's
  evidence, not E7's.
- Single platform. STREAM (268,435,456) and cuFFT (134,217,728) sizes are choices, not recovered (see `e7/E7_BENCHMARKS.md`).
- Process wall-clock includes start-up; relative effects on short runs are understated.

## Existing claims flagged (not edited)

- **CS2-N10 (Prefetch threshold tuning):** it is labelled DESCRIPTIVE for Stencil and defers confirmation to E7 Family A and generality to Family B.
  Family A is now confirmatory (−9.57%, −7.13%), and Family B shows no workload significantly slower and four faster.
  The label and the "generality" sentence should be reviewed.
- **CS2-N1:** item 3 ("magnitude varies across sessions": −4.93, −5.26, −3.36 in E4–E6) should add E7's −5.34%; item 4 ("the same gain is available without
  speculation") is supported by E7 Family A on a different module. The scope line (RTX 5070 Ti only) is unchanged.
- **CS2-N4 / CS2-N3:** no new evidence (E7's stock runs have no fault counters).
- **CLAIM_SCOPE general framing:** "the shipped threshold 51 as the baseline" is now questionable as a default for the paper's headline comparison;
  the choice of baseline is the author's.

The user decides these edits.
