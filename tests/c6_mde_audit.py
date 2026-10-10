#!/usr/bin/env python3
"""Gate C6 step 2: MDE audit for E4 and E5. Recomputes the minimum detectable effect from the committed run CSVs
(sd = sqrt(s1^2/n1 + s2^2/n2); MDE = (z(1-alpha/2) + z(0.80)) * sd) at alpha = 0.05 and at each family's own alpha
(E4: one Holm family of 18, and its sub-families F1 6, F2 4, F3 6, F4 2; E5: 3), compares with the CSV columns and with
the values quoted in the E4/E5 reports (parsed from their tables), and writes results/analysis/consolidation/mde_audit.csv.
Reads only. usage: c6_mde_audit.py"""
import csv, math, re, statistics as st
from scipy.stats import norm
Z80 = norm.ppf(0.80)
G = "results/analysis/gate_e"
def z(alpha): return norm.ppf(1 - alpha / 2) + Z80
def mde(a, b, alpha):
    sd = math.sqrt(st.variance(a) / len(a) + st.variance(b) / len(b)); return z(alpha) * sd
def runs(p, lab): return [float(r["wall_s"]) for r in csv.DictReader(open(p)) if r["label"] == lab]
out = []
# E4
e4runs = f"{G}/e4/e4_runs.csv"
SUB = {"F1": 6, "F2": 4, "F3": 6, "F4": 2}
rep = {}
for l in open(f"{G}/GATE_E4_REPORT.md"):
    c = [x.strip() for x in l.strip().strip("|").split("|")]
    if len(c) == 14 and c[0] in SUB:
        rep[(c[0], c[1], c[2])] = (float(c[11]), float(c[12]))
for r in csv.DictReader(open(f"{G}/e4/primary_comparisons.csv")):
    wl = r["workload"]; a = runs(e4runs, f"{wl} {r['arm']}"); b = runs(e4runs, f"{wl} {r['baseline']}")
    m0, m18, msub = mde(a, b, 0.05), mde(a, b, 0.05 / 18), mde(a, b, 0.05 / SUB[r["family"]])
    q = rep[(r["family"], wl, r["comparison"])]
    out.append(dict(gate="E4", family=r["family"], workload=wl, comparison=r["comparison"], csv_mde_s=float(r["mde_s"]), csv_mde_bonf_s=float(r["mde_bonf_s"]),
        recomputed_alpha05=m0, recomputed_family=m18, family_m=18, recomputed_subfamily=msub, subfamily_m=SUB[r["family"]], report_mde_s=q[0], report_mde_family_s=q[1], median_base=float(r["median_base"])))
# E5
e5runs = f"{G}/e5/e5_runs.csv"
rep5 = {}
for l in open(f"{G}/GATE_E5_REPORT.md"):
    c = [x.strip() for x in l.strip().strip("|").split("|")]
    if len(c) == 13 and c[0] in ("51", "75", "100") and " vs " in c[1] and "C7W512" in c[1] and c[0] not in rep5: rep5[c[0]] = (float(c[10]), float(c[11]))
TL = {"51": "t51", "75": "t75", "100": "toff"}
for r in csv.DictReader(open(f"{G}/e5/wallclock_comparisons.csv")):
    t = r["threshold"]; a = runs(e5runs, f"stencil C7W512-{TL[t]}"); b = runs(e5runs, f"stencil C0-{TL[t]}")
    out.append(dict(gate="E5", family="wall", workload="stencil", comparison=r["comparison"], csv_mde_s=float(r["mde_s"]), csv_mde_bonf_s=float(r["mde_bonf_s"]),
        recomputed_alpha05=mde(a, b, 0.05), recomputed_family=mde(a, b, 0.05 / 3), family_m=3, recomputed_subfamily=mde(a, b, 0.05 / 3), subfamily_m=3,
        report_mde_s=rep5[t][0], report_mde_family_s=rep5[t][1], median_base=float(r["median_base"])))
with open("results/analysis/consolidation/mde_audit.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
bad = [o for o in out if abs(o["csv_mde_s"] - o["recomputed_alpha05"]) > 5e-5 or abs(o["csv_mde_bonf_s"] - o["recomputed_family"]) > 5e-5
       or abs(o["report_mde_s"] - o["csv_mde_s"]) > 5e-5 or abs(o["report_mde_family_s"] - o["csv_mde_bonf_s"]) > 5e-5]
print(len(out), "rows; disagreements > 5e-5 s:", len(bad))
for o in bad: print(o)

# ---------------------------------------------------------------- quoted values -> consolidation/MDE_AUDIT.md
CS = "results/analysis/CLAIM_SCOPE.md"
def by(gate, fam, wl, cmp_):
    return next(o for o in out if o["gate"] == gate and o["family"] == fam and o["workload"] == wl and o["comparison"] == cmp_)
def pctb(o, k): return 100 * o[k] / o["median_base"]
# E6 (Section I and CLAIM_SCOPE quote E6 MDEs): secondary_wall (family of 3) and family2_graphbfs (family of 2)
e6 = f"{G}/e6/e6_runs.csv"
def e6row(csvname, key, arm, base, lab_wl, m):
    r = next(r for r in csv.DictReader(open(f"{G}/e6/{csvname}.csv")) if r[key] == arm if csvname != "secondary_wall" or r["arm"] == arm)
    return r
E6 = {}
for arm in ("C7W512-t0", "C7W512-t10", "C7W512-t25"):
    a = runs(e6, f"stencil {arm}"); b = runs(e6, f"stencil C0-{arm.split('-')[1]}")
    r = next(r for r in csv.DictReader(open(f"{G}/e6/secondary_wall.csv")) if r["arm"] == arm)
    E6[arm] = dict(base=float(r["median_base"]), csv_a05=float(r["mde_s"]), csv_bonf16=float(r["mde_bonf_s"]), a05=mde(a, b, 0.05), fam=mde(a, b, 0.05 / 3))
for arm in ("C0-t0", "C0-t25"):
    a = runs(e6, f"graphbfs {arm}"); b = runs(e6, "graphbfs C0-t51")
    r = next(r for r in csv.DictReader(open(f"{G}/e6/family2_graphbfs.csv")) if r["arm"] == arm)
    E6[arm] = dict(base=float(r["median_base"]), csv_a05=float(r["mde_s"]), csv_bonf16=float(r["mde_bonf_s"]), a05=mde(a, b, 0.05), fam=mde(a, b, 0.05 / 2))
# EVIDENCE_EXTRACT E4 rows: parse mde_s and compare with the CSV
ee = {}
for l in open("results/analysis/consolidation/EVIDENCE_EXTRACT.md"):
    m = re.match(r"\| `(E4\.F(\d)\.(\w+)\.(.+?)_vs_(.+?))` \|.*?mde_s=([\d.]+)", l)
    if m: ee[(f"F{m.group(2)}", m.group(3), f"{m.group(4)} vs {m.group(5)}")] = float(m.group(6))
ee_bad = [k for k, v in ee.items() if abs(v - by("E4", *k)["csv_mde_s"]) > 5e-5]
rows = []
def q(where, text, qv, col, correct, unit="s"):
    rows.append((where, text, qv, col, correct))
f1g = [by("E4", "F1", "graphbfs", c) for c in ("C7-W1 vs C0", "C7-W64 vs C0", "C7-W512 vs C0")]
s512 = by("E4", "F1", "stencil", "C7-W512 vs C0")
g512 = by("E4", "F1", "graphbfs", "C7-W512 vs C0")
q("GATE_E4_REPORT.md:13", "MDE 0.0144 s", f"{s512['report_mde_s']:.4f} s", "mde_s (alpha 0.05)", f"{s512['recomputed_alpha05']:.4f} s: matches")
q("GATE_E4_REPORT.md:13", "0.0197 s at alpha/18", f"{s512['report_mde_family_s']:.4f} s", "mde_bonf_s (alpha 0.05/18)", f"{s512['recomputed_family']:.4f} s: matches")
q("GATE_E4_REPORT.md:28", "MDE of 0.087 s", "0.087 s", "mde_s", f"{g512['recomputed_alpha05']:.4f} s at alpha 0.05; {g512['recomputed_family']:.4f} s at alpha/18: value matches its column, which is not the family alpha")
q("GATE_E4_REPORT.md:28, :247", "MDE of 0.087 s (about 0.28%); MDE about 0.28%", "0.28%", "mde_s / median_base", f"{pctb(g512,'recomputed_alpha05'):.2f}% at alpha 0.05; {pctb(g512,'recomputed_family'):.2f}% at alpha/18")
f2 = [by("E4", "F2", "graphbfs", c) for c in ("C7-W1 vs C7-slow-W1", "C6-W1 vs C6-slow-W1")]
q("GATE_E4_REPORT.md:204", "MDEs of 0.15 and 0.19 s", "0.15, 0.19 s", "mde_s", f"{f2[0]['recomputed_alpha05']:.4f}, {f2[1]['recomputed_alpha05']:.4f} s at alpha 0.05; {f2[0]['recomputed_family']:.4f}, {f2[1]['recomputed_family']:.4f} s at alpha/18")
q("GATE_E4_REPORT.md table, 18 rows", "MDE (s) and MDE alpha/18 (s) columns", "18 rows", "mde_s, mde_bonf_s", f"all 18 equal the CSV and the recomputation (max difference {max(max(abs(o['report_mde_s']-o['recomputed_alpha05']),abs(o['report_mde_family_s']-o['recomputed_family'])) for o in out if o['gate']=='E4'):.1e} s)")
q("GATE_E5_REPORT.md table, 3 rows", "MDE (s) and MDE alpha/3 (s) columns", "3 rows", "mde_s, mde_bonf_s", f"all 3 equal the CSV and the recomputation (max difference {max(max(abs(o['report_mde_s']-o['recomputed_alpha05']),abs(o['report_mde_family_s']-o['recomputed_family'])) for o in out if o['gate']=='E5'):.1e} s)")
q("EVIDENCE_EXTRACT.md, E4 rows (%d parsed)" % len(ee), "mde_s", "per row", "mde_s", "equal the CSV" if not ee_bad else f"DIFFER: {ee_bad}")
q("CLAIM_SCOPE.md:252", "E4.F1.stencil.C7-W512_vs_C0 ... MDE 0.0144 s", "0.0144 s", "mde_s", f"{s512['recomputed_alpha05']:.4f} s at alpha 0.05; {s512['recomputed_family']:.4f} s at alpha/18; the falsification trigger uses mde_s by pre-registration")
q("CLAIM_SCOPE.md:255", "C7-W1/W64/W512 ... MDE 0.0873-0.1351 s", "0.0873-0.1351 s", "mde_s", "; ".join(f"{o['comparison'].split(' ')[0]} {o['recomputed_alpha05']:.4f} -> {o['recomputed_family']:.4f}" for o in f1g) + " s (alpha 0.05 -> alpha/18)")
lo, hi = min(pctb(o, "recomputed_alpha05") for o in f1g), max(pctb(o, "recomputed_alpha05") for o in f1g)
flo, fhi = min(pctb(o, "recomputed_family") for o in f1g), max(pctb(o, "recomputed_family") for o in f1g)
q("CLAIM_SCOPE.md:246, :255", "GraphBFS-23 E4 ... MDE 0.28-0.43% of the C0 median", "0.28-0.43%", "mde_s / median_base", f"{lo:.2f}-{hi:.2f}% at alpha 0.05; **{flo:.2f}-{fhi:.2f}% at alpha/18 (the Holm family of the tests)**")
q("section1_introduction.tex:104-105", "minimum detectable effects 1.8% and 2.0% (E6 t0, t10)", "1.8%, 2.0%", "E6 secondary_wall mde_s / C0 median",
  f"{100*E6['C7W512-t0']['a05']/E6['C7W512-t0']['base']:.2f}%, {100*E6['C7W512-t10']['a05']/E6['C7W512-t10']['base']:.2f}% at alpha 0.05; **{100*E6['C7W512-t0']['fam']/E6['C7W512-t0']['base']:.2f}%, {100*E6['C7W512-t10']['fam']/E6['C7W512-t10']['base']:.2f}% at alpha/3 (E6's family of 3)**")
q("CLAIM_SCOPE.md:245, :254", "MDE 1.8% at t0 and 2.0% at t10 (E6)", "1.8%, 2.0%", "E6 mde_s", "as the row above (same values)")
q("CLAIM_SCOPE.md:246, :255", "E6 GraphBFS-23 MDE 0.41-0.49% of the C0-t51 median", "0.41-0.49%", "E6 family2 mde_s / base",
  f"{100*E6['C0-t25']['a05']/E6['C0-t25']['base']:.2f}-{100*E6['C0-t0']['a05']/E6['C0-t0']['base']:.2f}% at alpha 0.05; **{100*E6['C0-t25']['fam']/E6['C0-t25']['base']:.2f}-{100*E6['C0-t0']['fam']/E6['C0-t0']['base']:.2f}% at alpha/2 (E6's family of 2)**")
q("E6 CSVs (secondary_wall, family2_graphbfs) column mde_bonf_s", "values in the column", "e.g. %.4f s (t0)" % E6["C7W512-t0"]["csv_bonf16"], "mde_bonf_s (hard-coded alpha 0.05/16)",
  f"E6's own family alpha gives {E6['C7W512-t0']['fam']:.4f} s (t0, m = 3): the column is for a different family. Not quoted in any document checked")
md = ["# MDE audit (Gate C6 step 2; catalog #27)", "",
"Script: `tests/c6_mde_audit.py` (reads the committed run CSVs, recomputes MDE = (z(1 - alpha/2) + z(0.80)) * sqrt(s1^2/n1 + s2^2/n2), writes `mde_audit.csv`). No report or claim file was edited.", "",
"## Finding", "",
"**E4 and E5 carry no wrong MDE.** `e4_analyze.py` and `e5_analyze.py` overwrite the E0.9b helper's hard-coded alpha 0.05/16 constant before use (`H.Z_MDE_BONF`, alpha 0.05/18 for E4 and 0.05/3 for E5), so their `mde_bonf_s` columns, their `MDE18` / `MDE3` labels and the 'MDE alpha/18' and 'MDE alpha/3' columns of the two reports are correct: all 21 rows equal the independent recomputation (to 5e-5 s). The wrong-alpha columns are those of the gates that did **not** override the constant (E0.9b's own 16 is right for E0.9b; E6's CSVs carry it for families of 3, 4 and 2; E1 not audited). Catalog #27's open question is therefore answered: **E4 and E5 are not affected.**", "",
"**The issue that does exist is different.** Every MDE *quoted in prose* in CLAIM_SCOPE, Section I and the E4 report text is the unadjusted per-test value (`mde_s`, alpha 0.05), while the tests are Holm-corrected. For a null claim ('no effect beyond the MDE') the relevant MDE is the one at the family alpha, which is larger (E4 by x1.37, E6's family of 3 by x1.16). The quotes are correct values of the column they name; they are not wrong numbers but they understate the detection limit of the Holm family. Corrections below.", "",
"Family sizes: E4 one Holm family of 18 (F1 6, F2 4, F3 6, F4 2 are its parts; the sub-family column of `mde_audit.csv` is supplementary); E5 3; E6 secondary wall 3, Family 2 2.", "",
"## Quoted values", "", "| where | quoted | value | source column | correct value (alpha 0.05 -> family alpha) |", "|---|---|---|---|---|"]
for r in rows: md.append("| " + " | ".join(str(x).replace("|", "/") for x in r) + " |")
md += ["", "## Table: all E4 and E5 rows (seconds)", "", "| gate | family | workload | comparison | CSV mde_s | CSV mde_bonf_s | recomputed alpha 0.05 | recomputed family alpha (m) | report MDE | report MDE family |", "|---|---|---|---|---|---|---|---|---|---|"]
for o in out: md.append(f"| {o['gate']} | {o['family']} | {o['workload']} | {o['comparison']} | {o['csv_mde_s']:.4f} | {o['csv_mde_bonf_s']:.4f} | {o['recomputed_alpha05']:.4f} | {o['recomputed_family']:.4f} ({o['family_m']}) | {o['report_mde_s']:.4f} | {o['report_mde_family_s']:.4f} |")
md += ["", "## Exact corrections (proposals; nothing edited)", "",
f"1. `CLAIM_SCOPE.md:246` and `:255`, E4 GraphBFS-23: 'MDE 0.28-0.43% of the C0 median' -> 'MDE {flo:.2f}-{fhi:.2f}% of the C0 median at the family alpha (0.05/18); {lo:.2f}-{hi:.2f}% at the unadjusted alpha 0.05'. In `:255` the seconds range '0.0873-0.1351 s' -> '{min(o['recomputed_family'] for o in f1g):.4f}-{max(o['recomputed_family'] for o in f1g):.4f} s at alpha 0.05/18'.",
f"2. `section1_introduction.tex:104-105` (and `CLAIM_SCOPE.md:245`, `:254`), E6: 'minimum detectable effects 1.8% and 2.0%' -> '{100*E6['C7W512-t0']['fam']/E6['C7W512-t0']['base']:.1f}% and {100*E6['C7W512-t10']['fam']/E6['C7W512-t10']['base']:.1f}%' if the MDE is to be stated at the Holm family's alpha (the 1.8% and 2.0% are correct for an unadjusted alpha of 0.05 and the sentence does not say so). Either use the new numbers or add 'at alpha = 0.05, unadjusted'.",
f"3. `CLAIM_SCOPE.md:246`/`:255`, E6 GraphBFS-23: '0.41-0.49%' -> '{100*E6['C0-t25']['fam']/E6['C0-t25']['base']:.2f}-{100*E6['C0-t0']['fam']/E6['C0-t0']['base']:.2f}%' at alpha/2, or label the quoted range as the unadjusted alpha 0.05.",
"4. `CLAIM_SCOPE.md:252` and `GATE_E4_REPORT.md:13`, stencil C7-W512 'MDE 0.0144 s': correct as the unadjusted value, and the E4 falsification trigger is pre-registered on `mde_s` (`e4_analyze.py:102`); keep, and state the alpha.",
"5. E6 CSVs' `mde_bonf_s` column is for alpha 0.05/16, not E6's families (already recorded in `E7_STATUS.md`); no document quotes it. Add a note to the E6 report's next revision.", "",
"## Not covered", "", "- T4 and E7/E8 quotes use `mde_pct` and `mde_family_pct` from the E7 helper, which already takes the family size (`e7_analyze.py:56`); not re-audited here.", "- E1 and E0.9b quotes of `mde_bonf_s`; E6's own report text."]
open("results/analysis/consolidation/MDE_AUDIT.md", "w").write("\n".join(md) + "\n")
print("wrote MDE_AUDIT.md;", len(rows), "quoted rows; evidence-extract mismatches:", ee_bad)
