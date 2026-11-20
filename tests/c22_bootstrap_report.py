#!/usr/bin/env python3
"""C22 M5: answers (a)-(c) from the bootstrap results (/tmp/claude-1000/c22/boot.pkl written by c22_bootstrap.py) and the SGEMM-on-T4 SD analysis. Writes consolidation/C22_BOOTSTRAP_CI.md."""
import csv, pickle, statistics as st, sys
sys.path.insert(0, "tests")
_a, sys.argv = sys.argv, sys.argv[:1]
import e09b_analyze as H   # noqa: E402
sys.argv = _a
out = pickle.load(open("/tmp/claude-1000/c22/boot.pkl", "rb"))
by = {o["evidence_id"]: o for o in out}
fmt = lambda o: f"{o['delta_pct']:+.2f}% [{o['ci_low']:+.2f}, {o['ci_high']:+.2f}]"   # noqa: E731
def row(o): return f"| `{o['evidence_id']}` | {o['comparison']} | {fmt(o)} | {o['mde_pct']:.2f}% | {'yes' if o['ci_excludes_2'] else 'no'} | {'yes' if o['ci_excludes_5'] else 'no'} | {'sig' if o['holm_sig'] == 'True' else 'n.s.'} |"
HDR = ["| evidence id | comparison | delta [95% CI] | MDE (family alpha) | CI within (-2, +2)? (excludes +-2%) | CI within (-5, +5)? (excludes +-5%) | Holm |", "|---|---|---|---|---|---|---|"]
o = ["# C22 M5 / V-4 / VII-3: bootstrap confidence intervals", "",
     "Script `tests/c22_bootstrap.py` (+ `tests/c22_bootstrap_report.py`); table `C22_BOOTSTRAP_CI.csv` (84 comparisons; columns gate, comparison, delta %, CI low, CI high, MWU p, Holm-adjusted p, MDE % at the family alpha, evidence id). 10,000 resamples within cells, seed 20261117, percentile 95% interval of (median(arm*) - median(base*)) / median(base), median(base) the observed baseline median; medians recomputed from the run files equal the CSV medians (asserted for all 84). Holm-adjusted p is recomputed within each gate CSV's family (E4: all 18 rows; E5 3; E6 four families of 4, 3, 3, 2; E7 A 2, B 16; E7-T4 A 2, B 14; E8 16; H1 3; H2 8). New evidence ids are the comparison's id with the suffix `.ci` (added to `EVIDENCE_EXTRACT.md`). \"Excludes +-2%\" means the whole CI lies inside (-2, +2).", ""]
def sel(prefixes, gates=None):
    return [x for x in out if any(x["evidence_id"].startswith(p) for p in prefixes)]
o += ["## (a) The null results the paper relies on", "", "### E6 at t0 and t10 (C7W512 against C0 at the same threshold, wall-clock)", ""] + HDR + [row(by[i]) for i in ("E6.wall.C7W512-t0_vs_C0-t0", "E6.wall.C7W512-t10_vs_C0-t10")]
o += ["", "### GraphBFS-23", ""] + HDR + [row(x) for x in out if "graphbfs" in x["comparison"] and x["gate"] != "E8"]
o += ["", "### E7 Stencil-8K, Sweep-4K, cuFFT (RTX 5070 Ti; the T4 rows are in the CSV)", ""] + HDR + [row(x) for x in out if x["gate"] == "E7 B" and any(w in x["comparison"] for w in ("stencil8k", "sweep4k", "cufft"))]
nulls = [x for x in out if (x["gate"] == "E6 wall" and ("t0 vs" in x["comparison"] or "t10 vs" in x["comparison"])) or ("graphbfs" in x["comparison"] and x["gate"] in ("E4 F1", "E6 F2", "E7 B")) or (x["gate"] == "E7 B" and any(w in x["comparison"] for w in ("stencil8k", "sweep4k", "cufft")))]
n2 = [x for x in nulls if x["ci_excludes_2"]]; n5 = [x for x in nulls if x["ci_excludes_5"]]
o += ["", f"**Summary:** of these {len(nulls)} null comparisons, the CI excludes +-2% in {len(n2)} ({', '.join(sorted({x['comparison'].split()[0] + ' ' + x['gate'] for x in n2}))}) and excludes +-5% in {len(n5)}. The three short workloads of E7 (Stencil-8K, Sweep-4K, cuFFT) have CIs {min(x['ci_high']-x['ci_low'] for x in out if x['gate']=='E7 B' and any(w in x['comparison'] for w in ('stencil8k','sweep4k','cufft'))):.0f} to {max(x['ci_high']-x['ci_low'] for x in out if x['gate']=='E7 B' and any(w in x['comparison'] for w in ('stencil8k','sweep4k','cufft'))):.0f} points wide: they exclude neither +-2% nor +-5%, in line with their 7-12% MDEs, so they are underpowered nulls, not evidence of no effect. E6 at t0 and t10 (C7W512 vs C0): see table; GraphBFS-23 CIs in E4 and E6 are within +-1% and exclude +-2% and +-5%.", ""]
# (b) SGEMM on T4
T4 = [r for r in csv.DictReader(open("results/analysis/t4/e7t4_runs.csv")) if r["workload"] == "sgemm"]
cells = {c: [float(r["wall_s"]) for r in T4 if r["label"].endswith(c)] for c in ("stock-t0", "stock-t51")}
b = by["T4.B.sgemm.stock-t0_vs_stock-t51"]
o += ["## (b) SGEMM on the T4 (T4 Family B, t0 against t51)", "", f"Delta {fmt(b)}, Holm-significant (MWU p {b['p']:.2e}, Holm-adjusted p {b['holm_p']:.2e}); MDE at the family alpha {b['mde_pct']:.2f}% (SD-based, from the helper's pooled standard deviation). **The CI excludes zero (it spans -2.54 to -2.21%): any true change smaller than 2.2% in magnitude is excluded, and so is -5%.** ", ""]
o += ["| cell | n | median (s) | SD (s) | SD with Tukey outliers removed (s) | runs flagged (Tukey 1.5 IQR) |", "|---|---|---|---|---|---|"]
for c, v in cells.items():
    keep = H.tukey_keep(v)
    o.append(f"| {c} | {len(v)} | {st.median(v):.4f} | {st.stdev(v):.4f} | {st.stdev(keep):.4f} | {len(v) - len(keep)} |")
sd_all = (st.stdev(cells['stock-t0']) ** 2 / 2 + st.stdev(cells['stock-t51']) ** 2 / 2) ** 0.5
keep0, keep51 = H.tukey_keep(cells["stock-t0"]), H.tukey_keep(cells["stock-t51"])
sd_keep = (st.stdev(keep0) ** 2 / 2 + st.stdev(keep51) ** 2 / 2) ** 0.5 if len(keep0) > 1 and len(keep51) > 1 else float("nan")
m = st.median(cells["stock-t51"])
mde_all = (1.959964 + 0.841621) * sd_all * (2 / 10) ** 0.5 / m * 100 * (1.0)
ol = [(c, [x for x in v if x not in H.tukey_keep(v)]) for c, v in cells.items()]
sc = b["mde_pct"] * sd_keep / sd_all
o += ["", f"Pooled SD (equal n): {sd_all:.4f} s with all runs, {sd_keep:.4f} s without the flagged runs ({sd_all/sd_keep:.0f}x smaller). **Yes, one outlier inflates the SD:** the t51 cell has one high run, " + ", ".join(f"{x:.3f} s" for x in ol[1][1]) + f" ({100*(max(ol[1][1])/m-1):.1f}% above the t51 median, the first run of the cell); the two flagged t0 runs ({', '.join(f'{x:.3f} s' for x in ol[0][1])}) are low runs of an extremely tight cluster (all within 0.3% of the median), flagged only because the interquartile range is tiny. Without the flagged runs the t51 SD falls from {st.stdev(cells['stock-t51']):.4f} s to {st.stdev(keep51):.4f} s. The helper's SD-based MDE ({b['mde_pct']:.2f}% at the family alpha) scales with the SD, so without the outlier it would be about {sc:.2f}% (scaled by the SD ratio; the helper was not rerun). The 7.72% MDE therefore says nothing against the -2.24% result: it is inflated by one cold run, and the bootstrap CI is not.", ""]
# (c) disagreements
dis = [x for x in out if x["ci_sign_conflict"]]
o += ["## (c) Comparisons where the bootstrap CI and the Holm decision disagree", "", "Rule: CI excludes zero but Holm not significant, or Holm significant but CI contains zero.", ""] + HDR + [row(x) for x in dis]
o += ["", f"{len(dis)} of {len(out)} comparisons disagree." if dis else "None.", ""]
open("results/analysis/consolidation/C22_BOOTSTRAP_CI.md", "w").write("\n".join(o))
print("\n".join(o[40:75]) if False else "")
print(len(dis), "disagreements;", [x["evidence_id"] for x in dis]); print(cells["stock-t0"], cells["stock-t51"]); print(sd_all, sd_keep)
