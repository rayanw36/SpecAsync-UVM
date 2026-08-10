# Statistic of record and range re-derivation (Task B5)

## 1. Statistic of record: median

**Declared: the median is the statistic of record for this project's wall-clock comparisons.** Justification: Shapiro-Wilk rejects normality for at least one group in every one of the eight Gate 3 config/benchmark cells (`STATISTICS.md`), so a mean/SD-based summary is not the defensible default; `GATE3_report.md`'s own headline table is already medians (with a 95% CI computed on the median, not the mean).

| Headline number | Value | Statistic | Verified against |
|---|---|---|---|
| C0 Stencil-24K | 4.250s | median (n=15) | `gate3_times.csv` -- recomputed directly, matches `GATE3_report.md`'s table |
| C3 Stencil-24K | 15.680s | median (n=15) | `gate3_times.csv` -- recomputed directly, matches `GATE3_report.md`'s table |
| C0 GraphBFS-23 | 55.480s | median (n=15) | `gate3_times.csv` -- recomputed directly, matches `GATE3_report.md`'s table |
| C3 GraphBFS-23 | 58.640s | median (n=15) | `gate3_times.csv` -- recomputed directly, matches `GATE3_report.md`'s table |

C3-vs-C0 delta, Stencil-24K: (15.680-4.250)/4.250 = **+268.9%** (manuscript headline states +268.9% -- MATCHES).
C3-vs-C0 delta, GraphBFS-23: (58.640-55.480)/55.480 = **+5.7%** (manuscript headline states +5.7% -- MATCHES).

**Numbers currently in circulation flagged as means (not medians):** searched `paper/*.md` and `README.md` for headline percentages. Only one substantive number found: `paper/abstract_v2.md` line 35-36 states cuFFT gains "up to 4.4% (mean, n=50, Exp1)" -- **already explicitly labelled as a mean in the text itself**, not silently presented as if it were the statistic of record. No correction needed there; flagged here to confirm the search was actually done, not skipped. No Gate 3 C0/C1/C2/C3 numbers currently appear in `paper/*.md` (Section VI / results prose has not been drafted yet -- confirmed via grep for "C3", "Path B", "indistinguishable" returning no results in those files), so there is nothing yet in circulation to correct for the Gate 3 headline; this declaration is for when that prose is written.

## 2. D4+D5 range re-derivation

Two genuinely different statistics, both computed here from the same raw per-batch CSVs, labelled separately (see the discrepancy note in `STATISTICS.md`):

| Workload | ratio-of-medians (`PHASEC_REPORT.md`, D4%) | median-of-ratios (per-batch, recomputed here) |
|---|---|---|
| Stencil-8K | 63.3% | 63.27% |
| Stencil-24K | 69.6% | 73.66% |
| GraphBFS-23 | 73.8% | 86.00% |
| Sweep-4K | 63.0% | 60.75% |
| Sweep-8K | 62.9% | 62.47% |
| Sweep-16K | 65.3% | 65.56% |
| Sweep-24K | 69.5% | 73.24% |

**Ratio-of-medians range (matches the project notes' "63-74%" language):** 62.9%-73.8% (min=Sweep-8K, max=GraphBFS-23).
**Median-of-ratios range:** 60.75%-86.00% (min=Sweep-4K, max=GraphBFS-23).

**Which the manuscript should use:** the ratio-of-medians figure (63-74%) for the headline sentence -- it is the number already in `PHASEC_REPORT.md`, it is less sensitive to a handful of extreme individual batches (GraphBFS-23's per-batch max D3 is 2.95% and its distribution is heavy-tailed, per `STATISTICS.md`), and it answers "what does the typical run look like in aggregate" which is what a single headline percentage should mean. **But the median-of-ratios range (60.75-86.00%, wider and with a higher GraphBFS ceiling) should also appear in the methods/appendix as the batch-to-batch dispersion figure**, per Task B's original dispersion table -- a single point estimate of 69.6% for Stencil-24K masks that individual batches range considerably (see IQR columns in `STATISTICS.md`).

## 3. Draft methodology statement (2-3 sentences, as requested)

> We report D4/D5 dispatch-window share using two complementary statistics: a per-workload point estimate computed as the ratio of median sub-phase time to median total dispatch time across all batches ("ratio-of-medians", used for headline percentages throughout this paper), and a batch-level distribution computed as the median across batches of each batch's own D4/total ratio ("median-of-ratios", used where per-batch dispersion is reported). The two are not interchangeable: they diverge whenever D4 and total dispatch time are not perfectly correlated batch-by-batch, which they are not, and the ratio-of-medians is the more conservative, outlier-resistant summary we use for single-number claims.

## 4. D3 "no lock pressure" claim -- honest one-sentence version

D3 (lock wait) per-batch max, worst workload: Sweep-24K at 18.67% (recomputed here; `STATISTICS.md` reports 18.67% for Sweep-24K -- matches).

> Lock-wait time (D3) has a near-zero median in every workload we measured (<0.2%) and shows no lock contention in the typical batch; a minority of individual batches do see real, occasionally substantial lock wait (up to 18.7% of that batch's dispatch window, on Sweep-24K), so we characterize D3 as negligible for the typical batch rather than absent.
