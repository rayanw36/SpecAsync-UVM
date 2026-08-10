# Multiple-comparison correction across the Gate 3 family of six tests (Task B2)

Source: `results/phaseB2/gate3/gate3_times.csv`, recomputed directly (not transcribed from `STATISTICS.md`) so the two documents cannot silently drift apart. The corrected family is the six Mann-Whitney p-values (MWU is `STATISTICS.md`'s designated authoritative test in every one of these eight cells, since Shapiro-Wilk rejects normality for at least one group in each comparison).

**Why these six form one family:** all six comparisons are drawn from the same Gate 3 experiment (2 benchmarks x 3 comparison pairs) and collectively support one manuscript claim ("C3 is statistically indistinguishable from C1") plus two secondary claims about C2. Testing six hypotheses at alpha=0.05 uncorrected gives a family-wise false-positive rate of 1-(1-0.05)^6 = 0.265 (~26%) if all six null hypotheses were true. This section applies the pre-declared correction and reports both corrected and uncorrected values so the reader can judge either way.

## Correction table

| Comparison | Benchmark | MWU p (uncorrected) | Holm threshold | Holm-adjusted verdict | BH threshold | BH-adjusted verdict | Welch p (uncorrected) | Cohen's d | Verdict: uncorrected | Verdict: Holm | Verdict: BH |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C3 vs C0 | Stencil-24K | 3.161e-06 | 0.008333 | SIGNIFICANT | 0.008333 | SIGNIFICANT | 3.201e-17 | 18.304 | SIGNIFICANT | SIGNIFICANT | SIGNIFICANT |
| C2 vs C1 | Stencil-24K | 3.366e-06 | 0.01 | SIGNIFICANT | 0.01667 | SIGNIFICANT | 7.271e-10 | 4.504 | SIGNIFICANT | SIGNIFICANT | SIGNIFICANT |
| C3 vs C0 | GraphBFS-23 | 0.0006663 | 0.0125 | SIGNIFICANT | 0.025 | SIGNIFICANT | 7.258e-05 | 1.980 | SIGNIFICANT | SIGNIFICANT | SIGNIFICANT |
| C2 vs C1 | GraphBFS-23 | 0.03087 | 0.01667 | not significant | 0.03333 | SIGNIFICANT | 0.1481 | -0.544 | SIGNIFICANT | not significant | SIGNIFICANT |
| C3 vs C1 | Stencil-24K | 0.0361 | 0.025 | not significant | 0.04167 | SIGNIFICANT | 0.009693 | 1.084 | SIGNIFICANT | not significant | SIGNIFICANT |
| C3 vs C1 | GraphBFS-23 | 0.2367 | 0.05 | not significant | 0.05 | not significant | 0.1623 | 0.528 | not significant | not significant | not significant |

Holm-Bonferroni is a step-down procedure: sort p-values ascending, compare the k-th smallest to alpha/(6-k+1); once one comparison fails its threshold, every larger p-value in the sorted order is also rejected-from-significance regardless of its own threshold (applied above). Benjamini-Hochberg (secondary view, q=0.05) instead controls the expected false-discovery proportion and is generally less conservative than Holm.

## What changes under correction

**Holm-Bonferroni flips these from significant (uncorrected) to not significant:** C3 vs C1 Stencil-24K, C2 vs C1 GraphBFS-23.

**Benjamini-Hochberg changes no comparison's significance call** relative to uncorrected MWU at alpha=0.05.

## Effect on the headline claim

Stencil-24K C3-vs-C1 (the comparison driving "the claim is not fully supported as stated" in `STATISTICS.md`): uncorrected MWU p=0.0361, Holm-adjusted verdict **not significant**, BH-adjusted verdict **SIGNIFICANT**. Cohen's d=1.084 is unaffected by any multiple-comparison correction (correction changes only which p-values clear a significance bar, not the effect size itself).
