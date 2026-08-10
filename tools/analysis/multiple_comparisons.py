#!/usr/bin/env python3
"""Task B2 -- Holm-Bonferroni and Benjamini-Hochberg correction across the
family of six Gate 3 comparisons (C3vC1, C2vC1, C3vC0 x {Stencil-24K,
GraphBFS-23}) reported uncorrected in STATISTICS.md.

Recomputes p-values directly from results/phaseB2/gate3/gate3_times.csv
(does not transcribe STATISTICS.md's numbers) so there is no risk of a
transcription mismatch between the two documents.

Writes results/analysis/MULTIPLE_COMPARISONS.md.
"""
import csv
import statistics as st
from pathlib import Path

from scipy import stats

REPO = Path(__file__).resolve().parents[2]
GATE3_CSV = REPO / "results/phaseB2/gate3/gate3_times.csv"
BENCHES = [("bench_stencil", "Stencil-24K"), ("bench_graph_bfs", "GraphBFS-23")]
FAMILY = [("C3", "C1"), ("C2", "C1"), ("C3", "C0")]
ALPHA = 0.05


def load_gate3():
    data = {}
    with open(GATE3_CSV) as f:
        for r in csv.DictReader(f):
            data.setdefault((r["config"], r["bench"]), []).append(float(r["wall_s"]))
    return data


def cohens_d(a, b):
    na, nb = len(a), len(b)
    sa, sb = st.stdev(a), st.stdev(b)
    pooled_sd = (((na - 1) * sa**2 + (nb - 1) * sb**2) / (na + nb - 2)) ** 0.5
    return (st.mean(a) - st.mean(b)) / pooled_sd


def holm_bonferroni(pvals, alpha=ALPHA):
    """Returns list of (orig_index, p, threshold, reject) in the ORIGINAL order,
    after sorting internally to apply the step-down procedure."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    reject = [False] * m
    thresholds = [None] * m
    still_rejecting = True
    for rank, i in enumerate(order):  # rank is 0-indexed
        thr = alpha / (m - rank)
        thresholds[i] = thr
        if still_rejecting and pvals[i] <= thr:
            reject[i] = True
        else:
            still_rejecting = False  # once one fails, all subsequent (larger p) also fail
    return thresholds, reject


def benjamini_hochberg(pvals, q=ALPHA):
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    thresholds = [None] * m
    reject = [False] * m
    # find largest k such that p_(k) <= (k/m) * q
    max_k_that_passes = -1
    for rank, i in enumerate(order):  # rank 0-indexed -> k = rank+1
        k = rank + 1
        thr = (k / m) * q
        thresholds[i] = thr
        if pvals[i] <= thr:
            max_k_that_passes = rank
    for rank, i in enumerate(order):
        if rank <= max_k_that_passes:
            reject[i] = True
    return thresholds, reject


def main():
    gate3 = load_gate3()
    comparisons = []  # (label, bench_label, mwu_p, welch_p, d)
    print("=== Recomputed per-comparison stats (MWU is the family under correction) ===")
    for bench_key, bench_label in BENCHES:
        for a_cfg, b_cfg in FAMILY:
            a, b = gate3[(a_cfg, bench_key)], gate3[(b_cfg, bench_key)]
            t_stat, t_p = stats.ttest_ind(a, b, equal_var=False)
            u_stat, u_p = stats.mannwhitneyu(a, b, alternative="two-sided")
            d = cohens_d(a, b)
            label = f"{a_cfg} vs {b_cfg}"
            comparisons.append(dict(label=label, bench=bench_label, mwu_p=u_p,
                                     welch_p=t_p, d=d))
            print(f"  {label} {bench_label}: MWU p={u_p:.4g} Welch p={t_p:.4g} d={d:.3f}")

    mwu_ps = [c["mwu_p"] for c in comparisons]
    holm_thr, holm_reject = holm_bonferroni(mwu_ps)
    bh_thr, bh_reject = benjamini_hochberg(mwu_ps)

    lines = ["# Multiple-comparison correction across the Gate 3 family of six tests (Task B2)", ""]
    lines.append("Source: `results/phaseB2/gate3/gate3_times.csv`, recomputed directly "
                  "(not transcribed from `STATISTICS.md`) so the two documents cannot "
                  "silently drift apart. The corrected family is the six Mann-Whitney "
                  "p-values (MWU is `STATISTICS.md`'s designated authoritative test in "
                  "every one of these eight cells, since Shapiro-Wilk rejects normality "
                  "for at least one group in each comparison).")
    lines.append("")
    lines.append("**Why these six form one family:** all six comparisons are drawn from "
                  "the same Gate 3 experiment (2 benchmarks x 3 comparison pairs) and "
                  "collectively support one manuscript claim (\"C3 is statistically "
                  "indistinguishable from C1\") plus two secondary claims about C2. "
                  "Testing six hypotheses at alpha=0.05 uncorrected gives a family-wise "
                  "false-positive rate of 1-(1-0.05)^6 = "
                  f"{1 - (1-ALPHA)**6:.3f} (~{100*(1-(1-ALPHA)**6):.0f}%) if all six null "
                  "hypotheses were true. This section applies the pre-declared "
                  "correction and reports both corrected and uncorrected values so the "
                  "reader can judge either way.")
    lines.append("")
    lines.append("## Correction table")
    lines.append("")
    lines.append("| Comparison | Benchmark | MWU p (uncorrected) | Holm threshold | "
                  "Holm-adjusted verdict | BH threshold | BH-adjusted verdict | "
                  "Welch p (uncorrected) | Cohen's d | Verdict: uncorrected | "
                  "Verdict: Holm | Verdict: BH |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")

    # Sort rows by p-value ascending for readability, matching how the step-down
    # procedures actually operate, but keep original labels.
    order = sorted(range(len(comparisons)), key=lambda i: comparisons[i]["mwu_p"])
    for i in order:
        c = comparisons[i]
        unc_v = "SIGNIFICANT" if c["mwu_p"] < ALPHA else "not significant"
        holm_v = "SIGNIFICANT" if holm_reject[i] else "not significant"
        bh_v = "SIGNIFICANT" if bh_reject[i] else "not significant"
        lines.append(f"| {c['label']} | {c['bench']} | {c['mwu_p']:.4g} | "
                      f"{holm_thr[i]:.4g} | {holm_v} | {bh_thr[i]:.4g} | {bh_v} | "
                      f"{c['welch_p']:.4g} | {c['d']:.3f} | {unc_v} | {holm_v} | {bh_v} |")

    lines.append("")
    lines.append("Holm-Bonferroni is a step-down procedure: sort p-values ascending, "
                  "compare the k-th smallest to alpha/(6-k+1); once one comparison "
                  "fails its threshold, every larger p-value in the sorted order is "
                  "also rejected-from-significance regardless of its own threshold "
                  "(applied above). Benjamini-Hochberg (secondary view, q=0.05) instead "
                  "controls the expected false-discovery proportion and is generally "
                  "less conservative than Holm.")
    lines.append("")

    changed = [c["label"] + " " + c["bench"] for i, c in enumerate(comparisons)
               if (c["mwu_p"] < ALPHA) != holm_reject[i]]
    changed_bh = [c["label"] + " " + c["bench"] for i, c in enumerate(comparisons)
                  if (c["mwu_p"] < ALPHA) != bh_reject[i]]
    lines.append("## What changes under correction")
    lines.append("")
    if changed:
        lines.append(f"**Holm-Bonferroni flips these from significant (uncorrected) to "
                      f"not significant:** {', '.join(changed)}.")
    else:
        lines.append("**Holm-Bonferroni changes no comparison's significance call** "
                      "relative to uncorrected MWU at alpha=0.05.")
    lines.append("")
    if changed_bh:
        lines.append(f"**Benjamini-Hochberg flips these from significant (uncorrected) "
                      f"to not significant:** {', '.join(changed_bh)}.")
    else:
        lines.append("**Benjamini-Hochberg changes no comparison's significance call** "
                      "relative to uncorrected MWU at alpha=0.05.")
    lines.append("")

    stencil_c3c1 = next(c for c in comparisons if c["label"] == "C3 vs C1" and c["bench"] == "Stencil-24K")
    i_stencil = comparisons.index(stencil_c3c1)
    lines.append("## Effect on the headline claim")
    lines.append("")
    lines.append(f"Stencil-24K C3-vs-C1 (the comparison driving \"the claim is not "
                  f"fully supported as stated\" in `STATISTICS.md`): uncorrected MWU "
                  f"p={stencil_c3c1['mwu_p']:.4g}, Holm-adjusted verdict "
                  f"**{'SIGNIFICANT' if holm_reject[i_stencil] else 'not significant'}**, "
                  f"BH-adjusted verdict "
                  f"**{'SIGNIFICANT' if bh_reject[i_stencil] else 'not significant'}**. "
                  f"Cohen's d={stencil_c3c1['d']:.3f} is unaffected by any multiple-"
                  f"comparison correction (correction changes only which p-values clear "
                  f"a significance bar, not the effect size itself).")

    OUT = REPO / "results/analysis/MULTIPLE_COMPARISONS.md"
    OUT.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
