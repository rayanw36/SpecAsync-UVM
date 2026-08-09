# Statistical validation of the Gate 3 headline claim (Task B)

Source: `results/phaseB2/gate3/gate3_times.csv` -- raw per-run data, n=15/config/benchmark, confirmed present (not reconstructed from summary statistics; this file IS the primary record GATE3_report.md summarizes).

## Descriptive statistics per configuration

| Config | Benchmark | n | mean (s) | median (s) | SD (s) | min (s) | max (s) | 95% CI of mean (s) |
|---|---|---|---|---|---|---|---|---|
| C0 | Stencil-24K | 15 | 4.2593 | 4.2500 | 0.0263 | 4.2300 | 4.3400 | [4.2448, 4.2739] |
| C1 | Stencil-24K | 15 | 15.3433 | 15.2800 | 0.1473 | 15.1700 | 15.6300 | [15.2618, 15.4249] |
| C2 | Stencil-24K | 15 | 16.8747 | 16.7500 | 0.4578 | 16.4000 | 17.7300 | [16.6212, 17.1282] |
| C3 | Stencil-24K | 15 | 16.0507 | 15.6800 | 0.9106 | 15.1400 | 17.3000 | [15.5464, 16.5550] |
| C0 | GraphBFS-23 | 15 | 56.1713 | 55.4800 | 1.8475 | 55.2800 | 61.5100 | [55.1482, 57.1945] |
| C1 | GraphBFS-23 | 15 | 58.6580 | 58.5800 | 0.1882 | 58.4700 | 59.0300 | [58.5538, 58.7622] |
| C2 | GraphBFS-23 | 15 | 58.5413 | 58.4300 | 0.2379 | 58.2700 | 59.0700 | [58.4096, 58.6731] |
| C3 | GraphBFS-23 | 15 | 58.7987 | 58.6400 | 0.3266 | 58.4600 | 59.4700 | [58.6178, 58.9796] |

## Stencil-24K

**C3 vs C1**

- Welch t-test: t=2.970, df=14.7, p=0.009693
- Mann-Whitney U: U=163.5, p=0.0361
- Cohen's d (pooled SD=0.6523): d=1.084
- Mean difference (C3-C1): +0.7073s, 95% CI [+0.1989, +1.2158]
- Shapiro-Wilk normality: C3 W=0.769 p=0.001499; C1 W=0.883 p=0.05213
- **normality REJECTED for at least one group (p<=0.05); the Mann-Whitney result is the one to report**
- Verdict at alpha=0.05: SIGNIFICANT DIFFERENCE

**C2 vs C1**

- Welch t-test: t=12.334, df=16.9, p=7.271e-10
- Mann-Whitney U: U=225.0, p=3.366e-06
- Cohen's d (pooled SD=0.3400): d=4.504
- Mean difference (C2-C1): +1.5313s, 95% CI [+1.2692, +1.7934]
- Shapiro-Wilk normality: C2 W=0.829 p=0.008896; C1 W=0.883 p=0.05213
- **normality REJECTED for at least one group (p<=0.05); the Mann-Whitney result is the one to report**
- Verdict at alpha=0.05: SIGNIFICANT DIFFERENCE

**C3 vs C0**

- Welch t-test: t=50.129, df=14.0, p=3.201e-17
- Mann-Whitney U: U=225.0, p=3.161e-06
- Cohen's d (pooled SD=0.6442): d=18.304
- Mean difference (C3-C0): +11.7913s, 95% CI [+11.2869, +12.2958]
- Shapiro-Wilk normality: C3 W=0.769 p=0.001499; C0 W=0.782 p=0.002209
- **normality REJECTED for at least one group (p<=0.05); the Mann-Whitney result is the one to report**
- Verdict at alpha=0.05: SIGNIFICANT DIFFERENCE

## GraphBFS-23

**C3 vs C1**

- Welch t-test: t=1.445, df=22.4, p=0.1623
- Mann-Whitney U: U=141.5, p=0.2367
- Cohen's d (pooled SD=0.2666): d=0.528
- Mean difference (C3-C1): +0.1407s, 95% CI [-0.0610, +0.3423]
- Shapiro-Wilk normality: C3 W=0.836 p=0.01116; C1 W=0.775 p=0.001797
- **normality REJECTED for at least one group (p<=0.05); the Mann-Whitney result is the one to report**
- Verdict at alpha=0.05: no significant difference

**C2 vs C1**

- Welch t-test: t=-1.490, df=26.6, p=0.1481
- Mann-Whitney U: U=60.0, p=0.03087
- Cohen's d (pooled SD=0.2145): d=-0.544
- Mean difference (C2-C1): -0.1167s, 95% CI [-0.2775, +0.0442]
- Shapiro-Wilk normality: C2 W=0.845 p=0.01473; C1 W=0.775 p=0.001797
- **normality REJECTED for at least one group (p<=0.05); the Mann-Whitney result is the one to report**
- Verdict at alpha=0.05: SIGNIFICANT DIFFERENCE

**C3 vs C0**

- Welch t-test: t=5.424, df=14.9, p=7.258e-05
- Mann-Whitney U: U=195.0, p=0.0006663
- Cohen's d (pooled SD=1.3267): d=1.980
- Mean difference (C3-C0): +2.6273s, 95% CI [+1.5940, +3.6606]
- Shapiro-Wilk normality: C3 W=0.836 p=0.01116; C0 W=0.474 p=2.198e-06
- **normality REJECTED for at least one group (p<=0.05); the Mann-Whitney result is the one to report**
- Verdict at alpha=0.05: SIGNIFICANT DIFFERENCE

## Minimum detectable effect (n=15/group, alpha=0.05, power=0.80)

Two-sample (Welch-equivalent, equal-n) t-test power analysis: the smallest standardized effect size (Cohen's d) this design could detect 80% of the time at alpha=0.05, converted to a % of baseline using each benchmark's observed C1 (no-speculation baseline) SD.

| Benchmark | MDE (Cohen's d) | C1 mean (s) | C1 SD (s) | MDE in seconds | MDE as % of C1 mean |
|---|---|---|---|---|---|
| Stencil-24K | 1.060 | 15.3433 | 0.1473 | 0.1561 | 1.02% |
| GraphBFS-23 | 1.060 | 58.6580 | 0.1882 | 0.1994 | 0.34% |

## Verdict on the abstract's claim

- Stencil-24K: C3 vs C1 is **SIGNIFICANTLY DIFFERENT** (Welch p=0.009693, MWU p=0.0361, d=1.084)
- GraphBFS-23: C3 vs C1 is **NOT significantly different** (Welch p=0.1623, MWU p=0.2367, d=0.528)

**The claim is NOT fully supported as stated** -- at least one benchmark shows a statistically significant C3-vs-C1 difference at alpha=0.05. The abstract sentence needs to be qualified per benchmark rather than stated as a blanket claim. This is a finding to report, not a result to adjust.

## Phase C decomposition: dispersion across batches, not just medians

PHASEC_REPORT.md's 'Decomposition Results' table reports one number per workload per sub-phase (the aggregate % share). Recomputed here per BATCH (D3, D4+D5 as % of total_ns; D1+D2 as % of total_ns) with full dispersion, not just the median/point estimate.

| Workload | n | D3% median | D3% IQR | D3% max | D4+D5% median | D4+D5% IQR | D1+D2% median | D1+D2% IQR |
|---|---|---|---|---|---|---|---|---|
| Stencil-8K | 839 | 0.14 | 0.09 | 0.76 | 63.27 | 14.39 | 30.49 | 17.50 |
| Stencil-24K | 5253 | 0.14 | 0.11 | 1.46 | 73.66 | 17.42 | 20.93 | 19.36 |
| GraphBFS-23 | 473 | 0.05 | 0.32 | 2.95 | 86.00 | 10.81 | 12.29 | 12.70 |
| Sweep-4K | 259 | 0.14 | 0.07 | 0.61 | 60.75 | 12.48 | 33.74 | 13.39 |
| Sweep-8K | 835 | 0.14 | 0.09 | 0.69 | 62.47 | 15.97 | 30.53 | 17.73 |
| Sweep-16K | 2367 | 0.13 | 0.08 | 3.41 | 65.56 | 15.94 | 28.31 | 18.39 |
| Sweep-24K | 5207 | 0.14 | 0.11 | 18.67 | 73.24 | 17.08 | 21.29 | 19.50 |

**Methodological note / discrepancy check:** these per-batch-median % figures do NOT exactly match PHASEC_REPORT.md's D4% column (e.g. Stencil-24K: 73.66% here vs 69.6% reported). This is expected, not an error: PHASEC_REPORT.md computes ratio-of-medians (median(D4_ns) / median(total_ns) across the workload), while this table computes median-of-ratios (median across batches of D4_ns[i]/total_ns[i] per batch). The two statistics diverge whenever D4 and total are not perfectly correlated batch-by-batch, which they are not (IQR columns above show real batch-to-batch variation). Both are legitimate summaries of different things -- ratio-of-medians describes 'the median batch shape'; median-of-ratios describes 'the typical batch's share'. Recorded here explicitly so the two documents' numbers are not read as contradicting each other.

D3 (lock wait) has a near-zero median everywhere but a **long right tail** (max column) -- individual batches do occasionally see real lock wait; the report's '<0.2% in all workloads, no lock pressure' claim describes the typical batch correctly but should not be read as 'never happens'. D4+D5 IQR is narrow relative to its median (tight, consistent dominance). D1+D2's IQR is wider, consistent with PHASEC_REPORT.md's own 9-30% range across workloads (the 'gain capped at ~25% of total dispatch time on the best case, Stencil-8K' language in the report, not a flat ~6% figure -- no source file in this repo states a 6% D1+D2 ceiling; reporting the actual 9-30% range plus per-batch IQR here rather than the ~6% figure from the task prompt, which does not match any on-disk value found).
