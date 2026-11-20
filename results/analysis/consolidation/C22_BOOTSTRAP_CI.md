# C22 M5 / V-4 / VII-3: bootstrap confidence intervals

Script `tests/c22_bootstrap.py` (+ `tests/c22_bootstrap_report.py`); table `C22_BOOTSTRAP_CI.csv` (84 comparisons; columns gate, comparison, delta %, CI low, CI high, MWU p, Holm-adjusted p, MDE % at the family alpha, evidence id). 10,000 resamples within cells, seed 20261117, percentile 95% interval of (median(arm*) - median(base*)) / median(base), median(base) the observed baseline median; medians recomputed from the run files equal the CSV medians (asserted for all 84). Holm-adjusted p is recomputed within each gate CSV's family (E4: all 18 rows; E5 3; E6 four families of 4, 3, 3, 2; E7 A 2, B 16; E7-T4 A 2, B 14; E8 16; H1 3; H2 8). New evidence ids are the comparison's id with the suffix `.ci` (added to `EVIDENCE_EXTRACT.md`). "Excludes +-2%" means the whole CI lies inside (-2, +2).

## (a) The null results the paper relies on

### E6 at t0 and t10 (C7W512 against C0 at the same threshold, wall-clock)

| evidence id | comparison | delta [95% CI] | MDE (family alpha) | CI within (-2, +2)? (excludes +-2%) | CI within (-5, +5)? (excludes +-5%) | Holm |
|---|---|---|---|---|---|---|
| `E6.wall.C7W512-t0_vs_C0-t0` | stencil C7W512-t0 vs C0-t0 | -0.85% [-2.02, +1.49] | 2.04% | no | yes | n.s. |
| `E6.wall.C7W512-t10_vs_C0-t10` | stencil C7W512-t10 vs C0-t10 | -0.28% [-1.91, +1.72] | 2.28% | yes | yes | n.s. |

### GraphBFS-23

| evidence id | comparison | delta [95% CI] | MDE (family alpha) | CI within (-2, +2)? (excludes +-2%) | CI within (-5, +5)? (excludes +-5%) | Holm |
|---|---|---|---|---|---|---|
| `E4.F1.graphbfs.C7-W1_vs_C0` | graphbfs C7-W1 vs C0 | -0.28% [-0.64, +0.31] | 0.59% | yes | yes | n.s. |
| `E4.F1.graphbfs.C7-W64_vs_C0` | graphbfs C7-W64 vs C0 | -0.10% [-0.59, +0.22] | 0.57% | yes | yes | n.s. |
| `E4.F1.graphbfs.C7-W512_vs_C0` | graphbfs C7-W512 vs C0 | -0.06% [-0.40, +0.20] | 0.38% | yes | yes | n.s. |
| `E4.F4.graphbfs.C6-W512_vs_C0` | graphbfs C6-W512 vs C0 | +3.86% [+3.44, +4.32] | 0.52% | no | yes | sig |
| `E6.F2.C0-t0_vs_C0-t51` | graphbfs C0-t0 vs C0-t51 | -0.06% [-0.46, +0.45] | 0.54% | yes | yes | n.s. |
| `E6.F2.C0-t25_vs_C0-t51` | graphbfs C0-t25 vs C0-t51 | +0.12% [-0.27, +0.52] | 0.45% | yes | yes | n.s. |
| `E7.B.graphbfs.stock-t0_vs_stock-t51` | graphbfs stock-t0 vs stock-t51 | -0.26% [-1.05, -0.02] | 0.86% | yes | yes | n.s. |
| `E7.B.graphbfs.stock-t25_vs_stock-t51` | graphbfs stock-t25 vs stock-t51 | +0.06% [-0.72, +0.58] | 1.14% | yes | yes | n.s. |
| `T4.B.graphbfs.stock-t0_vs_stock-t51` | graphbfs stock-t0 vs stock-t51 | -0.14% [-0.24, -0.08] | 0.35% | yes | yes | sig |
| `T4.B.graphbfs.stock-t25_vs_stock-t51` | graphbfs stock-t25 vs stock-t51 | -0.11% [-0.30, -0.03] | 0.30% | yes | yes | sig |

### E7 Stencil-8K, Sweep-4K, cuFFT (RTX 5070 Ti; the T4 rows are in the CSV)

| evidence id | comparison | delta [95% CI] | MDE (family alpha) | CI within (-2, +2)? (excludes +-2%) | CI within (-5, +5)? (excludes +-5%) | Holm |
|---|---|---|---|---|---|---|
| `E7.B.stencil8k.stock-t0_vs_stock-t51` | stencil8k stock-t0 vs stock-t51 | -4.65% [-10.99, +3.62] | 10.41% | no | no | n.s. |
| `E7.B.stencil8k.stock-t25_vs_stock-t51` | stencil8k stock-t25 vs stock-t51 | -3.13% [-8.66, +3.58] | 10.20% | no | no | n.s. |
| `E7.B.sweep4k.stock-t0_vs_stock-t51` | sweep4k stock-t0 vs stock-t51 | +3.34% [-9.59, +13.00] | 11.77% | no | no | n.s. |
| `E7.B.sweep4k.stock-t25_vs_stock-t51` | sweep4k stock-t25 vs stock-t51 | +9.47% [-3.67, +16.12] | 12.42% | no | no | n.s. |
| `E7.B.cufft.stock-t0_vs_stock-t51` | cufft stock-t0 vs stock-t51 | -4.90% [-10.05, +0.83] | 7.27% | no | no | n.s. |
| `E7.B.cufft.stock-t25_vs_stock-t51` | cufft stock-t25 vs stock-t51 | -1.55% [-7.65, +6.31] | 8.38% | no | no | n.s. |

**Summary:** of these 15 null comparisons, the CI excludes +-2% in 8 (graphbfs E4 F1, graphbfs E6 F2, graphbfs E7 B, stencil E6 wall) and excludes +-5% in 9. The three short workloads of E7 (Stencil-8K, Sweep-4K, cuFFT) have CIs 11 to 23 points wide: they exclude neither +-2% nor +-5%, in line with their 7-12% MDEs, so they are underpowered nulls, not evidence of no effect. E6 at t0 and t10 (C7W512 vs C0): see table; GraphBFS-23 CIs in E4 and E6 are within +-1% and exclude +-2% and +-5%.

## (b) SGEMM on the T4 (T4 Family B, t0 against t51)

Delta -2.24% [-2.54, -2.21], Holm-significant (MWU p 1.08e-05, Holm-adjusted p 1.52e-04); MDE at the family alpha 7.72% (SD-based, from the helper's pooled standard deviation). **The CI excludes zero (it spans -2.54 to -2.21%): any true change smaller than 2.2% in magnitude is excluded, and so is -5%.** 

| cell | n | median (s) | SD (s) | SD with Tukey outliers removed (s) | runs flagged (Tukey 1.5 IQR) |
|---|---|---|---|---|---|
| stock-t0 | 10 | 16.5782 | 0.0175 | 0.0039 | 2 |
| stock-t51 | 10 | 16.9586 | 1.1023 | 0.0261 | 1 |

Pooled SD (equal n): 0.7796 s with all runs, 0.0187 s without the flagged runs (42x smaller). **Yes, one outlier inflates the SD:** the t51 cell has one high run, 20.455 s (20.6% above the t51 median, the first run of the cell); the two flagged t0 runs (16.537 s, 16.541 s) are low runs of an extremely tight cluster (all within 0.3% of the median), flagged only because the interquartile range is tiny. Without the flagged runs the t51 SD falls from 1.1023 s to 0.0261 s. The helper's SD-based MDE (7.72% at the family alpha) scales with the SD, so without the outlier it would be about 0.19% (scaled by the SD ratio; the helper was not rerun). The 7.72% MDE therefore says nothing against the -2.24% result: it is inflated by one cold run, and the bootstrap CI is not.

## (c) Comparisons where the bootstrap CI and the Holm decision disagree

Rule: CI excludes zero but Holm not significant, or Holm significant but CI contains zero.

| evidence id | comparison | delta [95% CI] | MDE (family alpha) | CI within (-2, +2)? (excludes +-2%) | CI within (-5, +5)? (excludes +-5%) | Holm |
|---|---|---|---|---|---|---|
| `E7.B.graphbfs.stock-t0_vs_stock-t51` | graphbfs stock-t0 vs stock-t51 | -0.26% [-1.05, -0.02] | 0.86% | yes | yes | n.s. |
| `E8.in.K1.stock-t25_vs_stock-t51` | in_k1 stock-t25 vs stock-t51 | -0.60% [-1.50, +0.14] | 1.06% | yes | yes | sig |

2 of 84 comparisons disagree.
