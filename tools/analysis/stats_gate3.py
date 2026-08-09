#!/usr/bin/env python3
"""Task B -- statistical validation of the Gate 3 headline claim ("C3 is statistically
indistinguishable from C1") and dispersion (not just medians) for the Phase C
decomposition percentages.

Source: results/phaseB2/gate3/gate3_times.csv -- this IS the raw per-run data (120
rows: 4 configs x 2 benchmarks x n=15 individual wall_s values), not a reconstruction
from summary statistics. GATE3_report.md's table is a summary OF this file; nothing
here is inferred from the summary.

Writes results/analysis/STATISTICS.md.
"""
import csv
import statistics as st
import sys
from pathlib import Path

import numpy as np
from scipy import stats
from statsmodels.stats.power import TTestIndPower

REPO = Path(__file__).resolve().parents[2]
GATE3_CSV = REPO / "results/phaseB2/gate3/gate3_times.csv"
DECOMP = {
    "Stencil-8K": REPO / "results/phaseC/decomp_stencil_8K.csv",
    "Stencil-24K": REPO / "results/phaseC/decomp_stencil_24K.csv",
    "GraphBFS-23": REPO / "results/phaseC/decomp_graphbfs_23.csv",
    "Sweep-4K": REPO / "results/phaseC/decomp_stencil_sweep_4000.csv",
    "Sweep-8K": REPO / "results/phaseC/decomp_stencil_sweep_8000.csv",
    "Sweep-16K": REPO / "results/phaseC/decomp_stencil_sweep_16000.csv",
    "Sweep-24K": REPO / "results/phaseC/decomp_stencil_sweep_24000.csv",
}
CONFIGS = ["C0", "C1", "C2", "C3"]
BENCHES = [("bench_stencil", "Stencil-24K"), ("bench_graph_bfs", "GraphBFS-23")]
ALPHA = 0.05


def load_gate3():
    data = {}
    with open(GATE3_CSV) as f:
        for r in csv.DictReader(f):
            data.setdefault((r["config"], r["bench"]), []).append(float(r["wall_s"]))
    return data


def mean_ci(vals, conf=0.95):
    n = len(vals)
    m = st.mean(vals)
    sem = st.stdev(vals) / n ** 0.5
    tcrit = stats.t.ppf((1 + conf) / 2, df=n - 1)
    return m, m - tcrit * sem, m + tcrit * sem


def cohens_d(a, b):
    na, nb = len(a), len(b)
    sa, sb = st.stdev(a), st.stdev(b)
    pooled_sd = (((na - 1) * sa**2 + (nb - 1) * sb**2) / (na + nb - 2)) ** 0.5
    return (st.mean(a) - st.mean(b)) / pooled_sd, pooled_sd


def diff_ci(a, b, conf=0.95):
    """Welch CI on the difference of means (does not assume equal variance)."""
    na, nb = len(a), len(b)
    ma, mb = st.mean(a), st.mean(b)
    va, vb = st.variance(a), st.variance(b)
    se = (va / na + vb / nb) ** 0.5
    df = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    tcrit = stats.t.ppf((1 + conf) / 2, df=df)
    diff = ma - mb
    return diff, diff - tcrit * se, diff + tcrit * se, df


def compare(a, b, label_a, label_b, lines):
    t_stat, t_p = stats.ttest_ind(a, b, equal_var=False)
    u_stat, u_p = stats.mannwhitneyu(a, b, alternative="two-sided")
    d, pooled_sd = cohens_d(a, b)
    diff, diff_lo, diff_hi, df = diff_ci(a, b)
    sw_a = stats.shapiro(a)
    sw_b = stats.shapiro(b)
    lines.append(f"\n**{label_a} vs {label_b}**\n")
    lines.append(f"- Welch t-test: t={t_stat:.3f}, df={df:.1f}, p={t_p:.4g}")
    lines.append(f"- Mann-Whitney U: U={u_stat:.1f}, p={u_p:.4g}")
    lines.append(f"- Cohen's d (pooled SD={pooled_sd:.4f}): d={d:.3f}")
    lines.append(f"- Mean difference ({label_a}-{label_b}): {diff:+.4f}s, "
                 f"95% CI [{diff_lo:+.4f}, {diff_hi:+.4f}]")
    lines.append(f"- Shapiro-Wilk normality: {label_a} W={sw_a.statistic:.3f} "
                 f"p={sw_a.pvalue:.4g}; {label_b} W={sw_b.statistic:.3f} p={sw_b.pvalue:.4g}")
    normal = sw_a.pvalue > 0.05 and sw_b.pvalue > 0.05
    verdict = ("normality holds for both groups (p>0.05); Welch t-test result is the "
                "primary one" if normal else
                "normality REJECTED for at least one group (p<=0.05); the Mann-Whitney "
                "result is the one to report")
    lines.append(f"- **{verdict}**")
    sig = t_p < ALPHA or u_p < ALPHA
    lines.append(f"- Verdict at alpha=0.05: {'SIGNIFICANT DIFFERENCE' if sig else 'no significant difference'}")
    return dict(t_p=t_p, u_p=u_p, d=d, diff=diff, diff_lo=diff_lo, diff_hi=diff_hi,
                normal=normal, sig=sig, pooled_sd=pooled_sd)


def mde_at_n(n_per_group, alpha=ALPHA, power=0.80):
    analysis = TTestIndPower()
    d = analysis.solve_power(effect_size=None, nobs1=n_per_group, alpha=alpha,
                              power=power, ratio=1.0, alternative="two-sided")
    return d


def main():
    gate3 = load_gate3()
    lines = ["# Statistical validation of the Gate 3 headline claim (Task B)", ""]
    lines.append("Source: `results/phaseB2/gate3/gate3_times.csv` -- raw per-run data, "
                  "n=15/config/benchmark, confirmed present (not reconstructed from "
                  "summary statistics; this file IS the primary record GATE3_report.md "
                  "summarizes).")
    lines.append("")
    lines.append("## Descriptive statistics per configuration")
    lines.append("")
    lines.append("| Config | Benchmark | n | mean (s) | median (s) | SD (s) | min (s) | "
                  "max (s) | 95% CI of mean (s) |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    desc = {}
    for bench_key, bench_label in BENCHES:
        for cfg in CONFIGS:
            vals = gate3[(cfg, bench_key)]
            m, lo, hi = mean_ci(vals)
            desc[(cfg, bench_key)] = vals
            lines.append(f"| {cfg} | {bench_label} | {len(vals)} | {m:.4f} | "
                         f"{st.median(vals):.4f} | {st.stdev(vals):.4f} | {min(vals):.4f} | "
                         f"{max(vals):.4f} | [{lo:.4f}, {hi:.4f}] |")

    print("=== Descriptive stats ===")
    for k, v in desc.items():
        print(k, "n=", len(v), "mean=", round(st.mean(v), 4), "median=", round(st.median(v), 4))

    results = {}
    for bench_key, bench_label in BENCHES:
        lines.append(f"\n## {bench_label}")
        for a_cfg, b_cfg in [("C3", "C1"), ("C2", "C1"), ("C3", "C0")]:
            a, b = gate3[(a_cfg, bench_key)], gate3[(b_cfg, bench_key)]
            r = compare(a, b, a_cfg, b_cfg, lines)
            results[(a_cfg, b_cfg, bench_key)] = r
            print(f"{bench_label} {a_cfg} vs {b_cfg}: t_p={r['t_p']:.4g} u_p={r['u_p']:.4g} "
                  f"d={r['d']:.3f} normal={r['normal']} sig={r['sig']}")

    # ---- Minimum detectable effect at n=15, 80% power ----
    lines.append("\n## Minimum detectable effect (n=15/group, alpha=0.05, power=0.80)")
    lines.append("")
    lines.append("Two-sample (Welch-equivalent, equal-n) t-test power analysis: the "
                  "smallest standardized effect size (Cohen's d) this design could "
                  "detect 80% of the time at alpha=0.05, converted to a % of baseline "
                  "using each benchmark's observed C1 (no-speculation baseline) SD.")
    lines.append("")
    lines.append("| Benchmark | MDE (Cohen's d) | C1 mean (s) | C1 SD (s) | MDE in seconds | MDE as % of C1 mean |")
    lines.append("|---|---|---|---|---|---|")
    mde_d = mde_at_n(15)
    print(f"\nMDE (Cohen's d) at n=15/group, alpha=0.05, power=0.80: {mde_d:.4f}")
    for bench_key, bench_label in BENCHES:
        c1 = gate3[("C1", bench_key)]
        c1_mean, c1_sd = st.mean(c1), st.stdev(c1)
        mde_s = mde_d * c1_sd
        mde_pct = 100.0 * mde_s / c1_mean
        lines.append(f"| {bench_label} | {mde_d:.3f} | {c1_mean:.4f} | {c1_sd:.4f} | "
                     f"{mde_s:.4f} | {mde_pct:.2f}% |")
        print(f"  {bench_label}: MDE = {mde_s:.4f}s = {mde_pct:.2f}% of C1 mean")

    # ---- Verdict on "statistically indistinguishable" ----
    lines.append("\n## Verdict on the abstract's claim")
    lines.append("")
    c3c1_stencil = results[("C3", "C1", "bench_stencil")]
    c3c1_bfs = results[("C3", "C1", "bench_graph_bfs")]
    verdict_lines = []
    for bench_label, r in [("Stencil-24K", c3c1_stencil), ("GraphBFS-23", c3c1_bfs)]:
        status = "NOT significantly different" if not r["sig"] else "SIGNIFICANTLY DIFFERENT"
        verdict_lines.append(f"- {bench_label}: C3 vs C1 is **{status}** "
                             f"(Welch p={r['t_p']:.4g}, MWU p={r['u_p']:.4g}, d={r['d']:.3f})")
    lines.extend(verdict_lines)
    both_ns = not c3c1_stencil["sig"] and not c3c1_bfs["sig"]
    lines.append("")
    if both_ns:
        lines.append("**The claim 'C3 is statistically indistinguishable from C1' IS "
                      "SUPPORTED** by a formal test (not just visual closeness of means) "
                      "on both benchmarks, at alpha=0.05, by both the parametric (Welch) "
                      "and non-parametric (Mann-Whitney) tests. This was previously "
                      "asserted from proximity of medians/means alone; it now has a test "
                      "behind it.")
    else:
        lines.append("**The claim is NOT fully supported as stated** -- at least one "
                      "benchmark shows a statistically significant C3-vs-C1 difference "
                      "at alpha=0.05. The abstract sentence needs to be qualified per "
                      "benchmark rather than stated as a blanket claim. This is a finding "
                      "to report, not a result to adjust.")
    print(f"\nVerdict: both non-significant = {both_ns}")

    # ---- Phase C decomposition dispersion (not just medians) ----
    lines.append("\n## Phase C decomposition: dispersion across batches, not just medians")
    lines.append("")
    lines.append("PHASEC_REPORT.md's 'Decomposition Results' table reports one number per "
                  "workload per sub-phase (the aggregate % share). Recomputed here per "
                  "BATCH (D3, D4+D5 as % of total_ns; D1+D2 as % of total_ns) with full "
                  "dispersion, not just the median/point estimate.")
    lines.append("")
    lines.append("| Workload | n | D3% median | D3% IQR | D3% max | D4+D5% median | "
                 "D4+D5% IQR | D1+D2% median | D1+D2% IQR |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    print("\n=== Phase C dispersion ===")
    for label, path in DECOMP.items():
        rows = list(csv.DictReader(open(path)))
        d3pct = np.array([100 * float(r["d3_ns"]) / float(r["total_ns"]) for r in rows
                           if float(r["total_ns"]) > 0])
        d45pct = np.array([100 * float(r["d4_ns"]) / float(r["total_ns"]) for r in rows
                            if float(r["total_ns"]) > 0])
        d12pct = np.array([100 * (float(r["d1_ns"]) + float(r["d2_ns"])) / float(r["total_ns"])
                            for r in rows if float(r["total_ns"]) > 0])
        def iqr(a):
            return np.percentile(a, 75) - np.percentile(a, 25)
        lines.append(f"| {label} | {len(rows)} | {np.median(d3pct):.2f} | {iqr(d3pct):.2f} | "
                     f"{d3pct.max():.2f} | {np.median(d45pct):.2f} | {iqr(d45pct):.2f} | "
                     f"{np.median(d12pct):.2f} | {iqr(d12pct):.2f} |")
        print(f"  {label}: n={len(rows)} D3% median={np.median(d3pct):.2f} IQR={iqr(d3pct):.2f} "
              f"max={d3pct.max():.2f} | D4+D5% median={np.median(d45pct):.2f} IQR={iqr(d45pct):.2f} "
              f"| D1+D2% median={np.median(d12pct):.2f} IQR={iqr(d12pct):.2f}")
    lines.append("")
    lines.append("**Methodological note / discrepancy check:** these per-batch-median % "
                  "figures do NOT exactly match PHASEC_REPORT.md's D4% column (e.g. "
                  "Stencil-24K: 73.66% here vs 69.6% reported). This is expected, not an "
                  "error: PHASEC_REPORT.md computes ratio-of-medians (median(D4_ns) / "
                  "median(total_ns) across the workload), while this table computes "
                  "median-of-ratios (median across batches of D4_ns[i]/total_ns[i] per "
                  "batch). The two statistics diverge whenever D4 and total are not "
                  "perfectly correlated batch-by-batch, which they are not (IQR columns "
                  "above show real batch-to-batch variation). Both are legitimate "
                  "summaries of different things -- ratio-of-medians describes 'the median "
                  "batch shape'; median-of-ratios describes 'the typical batch's share'. "
                  "Recorded here explicitly so the two documents' numbers are not read as "
                  "contradicting each other.")
    lines.append("")
    lines.append("D3 (lock wait) has a near-zero median everywhere but a **long right tail** "
                  "(max column) -- individual batches do occasionally see real lock wait; the "
                  "report's '<0.2% in all workloads, no lock pressure' claim describes the "
                  "typical batch correctly but should not be read as 'never happens'. D4+D5 "
                  "IQR is narrow relative to its median (tight, consistent dominance). D1+D2's "
                  "IQR is wider, consistent with PHASEC_REPORT.md's own 9-30% range across "
                  "workloads (the 'gain capped at ~25% of total dispatch time on the best "
                  "case, Stencil-8K' language in the report, not a flat ~6% figure -- no "
                  "source file in this repo states a 6% D1+D2 ceiling; reporting the actual "
                  "9-30% range plus per-batch IQR here rather than the ~6% figure from the "
                  "task prompt, which does not match any on-disk value found).")

    STATISTICS = REPO / "results/analysis/STATISTICS.md"
    STATISTICS.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {STATISTICS}")

    return results, mde_d


if __name__ == "__main__":
    main()
