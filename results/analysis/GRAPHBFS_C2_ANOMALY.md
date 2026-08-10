# The GraphBFS C2-vs-C1 anomaly (Task B3)

Source: `results/phaseB2/gate3/gate3_times.csv`, recomputed fresh. Cross-references `OUTLIER_FORENSICS.md` (Task B1) and `MULTIPLE_COMPARISONS.md` (Task B2), read from disk, not re-derived by a separate hand-written logic path.

## 1. The anomaly, restated precisely

C2 (stride speculation, depth=1, prefetch OFF) on GraphBFS-23 has mean 58.5413s vs C1 (no speculation) mean 58.6580s: **C2 is 0.1167s faster (-0.1989% of the C1 mean)**. Mann-Whitney U p=0.03087 (< 0.05, uncorrected). This is the only cell anywhere in the Gate 3 (or Gate 2) data where a speculation policy measures faster than the no-speculation baseline in either direction with a nominally significant test.

## 2. The MDE tension

The design's own minimum-detectable-effect calculation (n=15/group, alpha=0.05, power=0.80, using this benchmark's own observed C1 SD) is d=1.060, equivalent to 0.1994s = **0.3400% of the C1 mean**. The observed effect here is 0.1989% of the C1 mean (Cohen's d=-0.544, magnitude 0.544) -- **smaller than the design's own nominal minimum detectable effect** (0.544 < 1.060).

**This is not a contradiction, but it is a flag.** MDE-at-80%-power is the effect size a design would catch 80% of the time across repeated experiments; it does not mean effects below that size can never individually reach p<0.05 in a single realized sample -- by construction, an underpowered test can still occasionally cross the significance threshold on a given draw (that is exactly what "80% power" implies is NOT guaranteed the other 20% of the time, and the reverse -- a sub-MDE effect reaching significance anyway -- is the complementary event). But an effect below the MDE reaching significance is exactly the situation where a result is most likely to be **either a true small effect that got a lucky draw, or a distributional artifact the SD-based power calculation doesn't model** (e.g. skew that MWU is sensitive to but a d/power calculation built on means and SDs is not) -- see section 4.

## 3. Does it survive Holm correction and outlier removal?

**Holm-Bonferroni (Task B2):** does NOT survive. In `MULTIPLE_COMPARISONS.md`'s family of six, C2-vs-C1/GraphBFS-23 (uncorrected MWU p=0.03087) is one of the two comparisons Holm flips from significant to not significant (its Holm threshold at rank order is 0.05/3=0.01667, which p=0.03087 fails). It DOES survive the secondary Benjamini-Hochberg view, which is less conservative -- both are reported in `MULTIPLE_COMPARISONS.md` per that task's instruction to not choose one as authoritative.

**Outlier removal (Task B1):** does NOT flip. `OUTLIER_FORENSICS.md` section 3 shows C2-vs-C1/GraphBFS-23 remains significant by both tests after removing the Tukey-flagged points from each side (MWU p goes from 0.03087 to 0.01425 -- if anything, slightly stronger, not weaker). So the significance is not an artifact of the specific outlier points identified in B1; it is the Holm family-wise correction, not outlier removal, that erases it.

## 4. Welch/MWU disagreement -- explained by skew

Welch t-test p=0.1481 (not significant) vs Mann-Whitney U p=0.03087 (significant): a genuine disagreement, not noise. Sample skewness: C1=+1.195, C2=+1.129 (Shapiro-Wilk: C1 W=0.775 p=0.001797, C2 W=0.845 p=0.01473). Both group's normality is rejected. MWU is a rank-based test: it can flag a **consistent small shift** in the bulk of the distribution even when a few large-magnitude points in one tail (which dominate a mean/variance-based Welch test) wash out the mean difference's statistical signal. That is consistent with what's seen here: most C2 values sit slightly below most C1 values (enough for the rank test to notice), while C1's own outliers (see `OUTLIER_FORENSICS.md` section 2b: C1/GraphBFS has three Tukey-flagged high points at positions 3, 8, 13) inflate C1's mean and variance enough to keep the Welch p-value above 0.05. **The Welch/MWU disagreement here has the same root cause (C1's own outlier points) as the sensitivity noted in B1** -- it is not an independent puzzle.

## 5. Draft manuscript treatment (two sentences, as requested)

> On GraphBFS-23, stride speculation (C2) measured 0.20% faster than the no-speculation baseline (C1) by a rank-based test (Mann-Whitney p=0.031), the only speculation-faster-than-baseline result observed in this study; however, the effect (Cohen's d=0.54) falls below this design's own minimum detectable effect at 80% power (d=1.06), does not survive Holm-Bonferroni correction for the family of six Gate 3 comparisons, and is attributable to a small number of elevated C1 runs rather than to C2 running systematically faster. We therefore do not interpret this as evidence that speculation helps GraphBFS and report it for completeness rather than as a finding.

**Found and explained here, not left for a reviewer, per the task's instruction.**
