#!/usr/bin/env python3
"""Gate C17: build paper/supplementary.tex (standalone IEEEtran, "Supplementary Material").
S1 full test tables (fragments of paper/tables/, captions from TABLES.md), S2 further figures (captions from paper/figures/FIGURES.md),
S3 the full ARTIFACT_CATALOG.md converted to LaTeX by this script, wording unchanged (only markup is converted).
Nothing from paper/figures/legacy or paper/figures/retired is used. No TeX toolchain is available on this host: the output is checked by script (brace and environment balance, paths)."""
import re, os, sys
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
def esc_raw(t): return "".join(SPECIAL.get(c, c) for c in t)
def esc(t):
    t = esc_raw(t)
    t = t.replace("=", "=\\allowbreak{}").replace("-", "-\\allowbreak{}").replace("/", "/\\allowbreak{}").replace("\\_", "\\_\\allowbreak{}")   # plain-text slash-joined tokens may break
    return re.sub(r'"([^"\n]*)"', r"``\1''", t)   # straight double quotes -> TeX quotes (markup only)
def code(t):
    """File names, paths and identifiers may break anywhere (the effect of \\path/\\url with xurl, without the argument restrictions of \\url)."""
    e = esc_raw(t)
    if len(t) > 8:
        e = re.sub(r"(\\[\\{}%&$#_^~]|\\textasciitilde\{\}|\\textasciicircum\{\}|\\textbackslash\{\}|.)", lambda m: m.group(1) + r"\allowbreak{}", e)
    else:
        for ch in ("/", r"\_", ".", "-", "=", ","): e = e.replace(ch, ch + r"\allowbreak{}")
    return r"\texttt{" + e + "}"
TOK = re.compile(r"(`[^`]+`|\*\*.+?\*\*|(?<![*\w])\*[^*\n]+?\*(?![*\w]))")
def inline(t):
    out, pos = [], 0
    for m in TOK.finditer(t):
        out.append(esc(t[pos:m.start()])); g = m.group(0)
        if g.startswith("`"): out.append(code(g[1:-1]))
        elif g.startswith("**"): out.append(r"\textbf{" + inline(g[2:-2]) + "}")
        else: out.append(r"\emph{" + inline(g[1:-1]) + "}")
        pos = m.end()
    out.append(esc(t[pos:]))
    return "".join(out)
PRE = r"""\documentclass[journal]{IEEEtran}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{longtable}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{url}
\usepackage{adjustbox}
\usepackage{xcolor}
\DeclareUnicodeCharacter{2192}{\ensuremath{\rightarrow}}
\DeclareUnicodeCharacter{2248}{\ensuremath{\approx}}
\DeclareUnicodeCharacter{2212}{\ensuremath{-}}
\DeclareUnicodeCharacter{2265}{\ensuremath{\geq}}
\DeclareUnicodeCharacter{2264}{\ensuremath{\leq}}
\DeclareUnicodeCharacter{00B1}{\ensuremath{\pm}}
\DeclareUnicodeCharacter{00F7}{\ensuremath{\div}}
\DeclareUnicodeCharacter{00D7}{\ensuremath{\times}}
\DeclareUnicodeCharacter{00B2}{\ensuremath{^{2}}}
\graphicspath{{figures/}}
\setcounter{secnumdepth}{1}
\begin{document}
\title{Supplementary Material}
\author{Author~Name,~Second~Author}
\markboth{Supplementary Material}{Supplementary Material}
\maketitle
\noindent This document supplements the paper. Section~S1 holds the full test tables, S2 further figures, and S3 the catalog of measurement artifacts.
"""
# ---------------- S1
TABS = [("t_e4", "T-E4", "Section VI (speculation against the shipped driver, E4)"), ("t_e5", "T-E5", "Section VI (the prefetcher's density rule, E5)"), ("t_e6", "T-E6", "Section VI (matched-threshold comparisons, E6)"),
        ("t_hand", "T-HAND", "Section VI (cost of the hook, E1b and E3b)"), ("t_e8", "T-E8", "Section VII (sparse access, E8; the paper shows these cells as a figure)"),
        ("t_e9", "T-E9", "Section VII (traced migration, E9)"), ("t_e9b", "T-E9", "Section VII (time outside the kernels, E8 untraced runs; second fragment of T-E9)"),
        ("t_e7_full", "T-E7-FULL", "Section VII-A (threshold on dense workloads, both GPUs, with p-values)"), ("t_h1", "T-H1", "Section VII-C (system-allocated memory, H1)"), ("t_h2", "T-H2", "Section VII-C (managed against system-allocated memory, H2)")]
tmd = {}
for l in list(open("paper/tables/TABLES.md")) + list(open("paper/tables/TABLES_C22.md")):
    if l.startswith("| T-"):
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        tmd[c[0]] = c[3]
fmd = {}
for l in open("paper/figures/FIGURES.md"):
    if l.startswith("| F-"):
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        fmd[re.search(r"`([^`]+)`", c[1]).group(1)] = (c[0], c[-1], c[-2])

CAPLOG = []
def clean_cap(cap, where):
    o = cap
    for a, b in ((" Second fragment of T-E9: ", " "), ("Second fragment of T-E9: ", "Companion to the preceding table: "), ("E3a-2 module", "our modified module"),
                 ("MDEs are at the family alpha, rescaled from the achieved-n value because the CSV column is the 0.05/16 constant.", "MDEs are computed at each family's own corrected level."),
                 (" (panel (a) of fig_h2_hmm alone)", ""), (" (panel (b) of fig_h2_hmm alone)", "")):
        cap = cap.replace(a, b)
    cap = re.sub(r"\bfig_[a-z0-9_]+", "", cap); cap = re.sub(r"\bT-[A-Z0-9][A-Z0-9-]*", "", cap)
    cap = re.sub(r"\s+", " ", cap).replace(" ,", ",").replace("( ", "(").replace(" )", ")").strip()
    if cap != o: CAPLOG.append((where, o, cap))
    return cap
out = [PRE, r"\clearpage", r"\section{Full Test Tables}", r"\label{sec:s1}", ""]
SUBS = {"t_e7_full": "Threshold comparisons on both GPUs (E7, E7-T4)", "t_h1": "System-allocated memory, H1", "t_h2": "Managed against system-allocated memory, H2"}
for frag, tid, where in TABS:
    cap = tmd[tid]
    if frag in SUBS: out += [r"\subsection{" + SUBS[frag] + "}", ""]
    if tid == "T-E9":
        cap = cap.split(" The second fragment")[0] if frag == "t_e9" else "Second fragment of T-E9: " + (cap.split("The second fragment gives, ")[1] if "The second fragment gives, " in cap else cap)
    cap = clean_cap(cap, "S1 " + frag)
    out += [r"\begin{table*}[t]", r"\centering\footnotesize", r"\caption{" + inline(cap) + " Supports " + inline(where) + ".}", r"\label{tab:s-" + frag + "}", r"\adjustbox{max width=\textwidth}{\input{tables/" + frag + "}}", r"\end{table*}", ""]
# ---------------- S2
FIGS = [("fig_e4_wallclock_by_arm", "figures/fig_e4_wallclock_by_arm", "figure*", "0.95\\textwidth"), ("fig_e7_threshold_by_workload_two_platforms", "figures/fig_e7_threshold_by_workload_two_platforms", "figure*", "0.95\\textwidth"),
        ("fig_ph_phase_medians", "figures/fig_ph_phase_medians", "figure", "\\columnwidth"), ("fig_h1", "figures/supplementary/F-H1", "figure", "\\columnwidth")]
out += [r"\clearpage", r"\section{Further Figures}", r"\label{sec:s2}", ""]
for key, path, env, width in FIGS:
    key_md = next(k for k in fmd if k == key or k.endswith(path.split("/")[-1]))
    title, cap, _n = fmd[key_md]
    cap = clean_cap(cap, "S2 " + key)
    out += [r"\begin{" + env + "}[t]", r"\centering", r"\includegraphics[width=" + width + "]{" + path + "}", r"\caption{" + inline(cap) + "}", r"\label{fig:s-" + os.path.basename(path) + "}", r"\end{" + env + "}", ""]
# ---------------- S3 (rewritten in C25: one table built from the same source as t_cat)
sys.path.insert(0, "tests")
_av = sys.argv; sys.argv = sys.argv[:1]
import make_paper_tables as MT
sys.argv = _av
WH = {1: "The oracle's trace cursor advanced at a different rate from the fault stream it was meant to track.",
 2: "Address-space randomisation moved the managed array between recording and replay, so recorded addresses did not match.",
 3: "A STREAM speedup came from the order in which a host script ran its configurations, not from prefetching.",
 4: "Two driver timestamps were taken at the same point, so the metadata phase absorbed the whole service time.",
 5: "A parser lost its byte offset in long runs and produced garbled phase records.",
 6: "One cuFFT hit rate came from a blocked run order and did not reproduce under interleaving.",
 7: "A fixed-size trace ring filled up and stopped recording without wrapping, so its counts were capped.",
 8: "A fault rate was computed at the wrong aggregation level, inflating it about fifteen-fold.",
 9: "A ceiling on achievable savings mixed time quantities of different units and levels.",
 10: "Runs with a fixed address-space layout behaved differently from runs without one.",
 11: "A host memory leak made later runs of a sequence differ from earlier ones.",
 12: "An oversubscription speedup was measured against a baseline with speculation and the prefetcher both off.",
 13: "The oracle trace was recorded at one granularity (per dispatch group) and consumed at another (per fault).",
 14: "A control meant to validate the oracle fix passed by construction: its granularities coincided or its accesses never exercised the bug.",
 15: "An improvement was accepted on single-digit counts without comparing it with an absolute ceiling.",
 16: "A hit rate per enqueued prediction was compared with a ceiling per fault.",
 17: "Duplicate-fault counts vary between runs, so positions in a recorded trace do not line up across runs.",
 18: "A forward-only agreement metric was asymmetric under a shift of the trace.",
 19: "The trace ring was read in physical-slot order, so the record came out truncated and rotated.",
 20: "A counter named for successful speculation in fact counted faults on pages predicted within the previous 10 ms.",
 21: "The oracle's own lookup cost was charged to the speculation arm it was meant to bound.",
 22: "A kernel helper guarded only by a non-fatal assertion returned NULL and crashed the kernel.",
 23: "Unattended upgrades silently changed the driver release between measurement campaigns.",
 24: "A line-count diff of the kernel log failed when the log buffer rotated.",
 25: "A pilot's ceiling prediction failed its own pre-registered test.",
 26: "A status log recorded a platform state that the system journal contradicted, and its times were estimates entered by hand.",
 27: "A statistics helper hard-coded the multiplicity correction for one family size and was reused for others.",
 28: "A build script swallowed a failure when a patch file was only a Git-LFS pointer.",
 29: "A script ended its own run by killing the login that contained it.",
 30: "A pre-registration sized an array against GPU memory but not host memory.",
 31: "GPU memory in use was read as migrated volume after being validated on one allocator only."}
REPL = []   # (entry, field, old, new) for review
FIX = {(16, 'false conclusion'): [('One prediction per batch caps the hit rate at the reciprocal coalesce factor.', 'One prediction per batch caps the hit rate at one over the number of faults coalesced per batch.')],
       (26, 'how caught'): [('journal re-account; E8 review', 'comparison with the system journal')],
       (29, 'how caught'): [('the run ended', 'observed when the run stopped')]}
def plain(n, field, t):
    o = t
    t = re.sub(r"\s*\((?:Gate [A-Z]\d?|E0(?:\.\d+)?)\)", " (an earlier gate)", t)
    t = re.sub(r"\s*\((?:A2b|Task T2)\)", "", t)
    t = t.replace("Older-driver and Gate-E results are one platform; the platform table is current.", "Results from an earlier driver release and from the later gates were read as one platform; the platform table was assumed current.")
    t = t.replace("same-session", "same-run").replace("the session ended", "the run ended")
    t = t.replace("reproduction ", "later reproduction ") if t.startswith("reproduction") else t
    for a, b in FIX.get((n, field), []):
        assert a in t, (n, field, a, t)
        t = t.replace(a, b)
    if t != o: REPL.append((n, field, o, t))
    return t
OPEN = r"""We recorded 31 artifacts in the course of this study: errors in measurement,
analysis or procedure, each with the false conclusion it produced or would have
produced. Most are errors of our own; we list them because the same errors can
arise in any measurement of a GPU driver, and because several of them shaped
the results reported in the paper. Each row gives what happened, the conclusion
it led or would have led to, how it was caught, and its family
(Section VIII-A of the paper). The full working record of each entry is in the
artifact's repository."""
CLOSE = r"""Three observations summarise the catalog. First, errors of aggregation level
were the most consequential and the hardest to see: every step of the analysis
was arithmetically correct, and eight of the nine were caught only by a later,
independent pass. Second, eleven of the 31 errors were caught inside the gate
that made them, three of them by a check written before the measurement, while
six checks that could not have failed let errors through; this is why every
analysis script now has a positive control that must also reject a perturbed
copy of the data. Third,
several instruments measured something other than what their names suggested.
Two of them, a hit counter that counted proximity in time rather than success
and a memory counter that reads allocation rather than migration on managed
memory, were caught only when a second, independent instrument disagreed with
them."""
FAMN = {"Instrument cost and blindness": "Instrument cost and blindness"}
out += [r"\onecolumn", r"\section{Artifact Catalog}", r"\label{sec:s3}", "", OPEN, "",
        r"{\footnotesize", r"\begin{longtable}{@{}r >{\raggedright\arraybackslash}p{0.27\textwidth} >{\raggedright\arraybackslash}p{0.27\textwidth} >{\raggedright\arraybackslash}p{0.17\textwidth} >{\raggedright\arraybackslash}p{0.12\textwidth}@{}}", r"\toprule", r"\# & What happened & False conclusion & How caught & Family \\", r"\midrule", r"\endhead"]
for n in range(1, 32):
    nm, fc, hc, fam, flag = MT.CAT[n]
    out.append(f"{n} & {inline(WH[n])} & {inline(plain(n, 'false conclusion', fc))} & {inline(plain(n, 'how caught', hc))} & {inline(fam)} \\\\")
out += [r"\bottomrule", r"\end{longtable}", "}", "", CLOSE, "", r"\twocolumn", ""]
out += [r"\end{document}", ""]
tex = "\n".join(out)
open("results/analysis/consolidation/C25_SUPP_REVIEW.md", "w").write("# C25: replacements and caption changes in the supplement (for review)\n\n## S3 table replacements (entry, field, old -> new)\n\n" + "\n".join(f"- #{n} {f}: `{o}` -> `{t}`" for n, f, o, t in REPL) + "\n\n## S1/S2 caption changes\n\n" + "\n\n".join(f"### {w}\n- before: {o}\n- after: {t}" for w, o, t in CAPLOG) + "\n")
open("paper/supplementary.tex", "w").write(tex)
# ---- script checks (no TeX toolchain)
import collections
c = collections.Counter(re.findall(r"\\begin\{(\w+\*?)\}", tex)); e = collections.Counter(re.findall(r"\\end\{(\w+\*?)\}", tex))
assert c == e, (c, e)
body = re.sub(r"\\[\\{}%&$#_^~]", "", tex)
assert body.count("{") == body.count("}"), (body.count("{"), body.count("}"))
paths = re.findall(r"\\(?:includegraphics(?:\[[^\]]*\])?|input)\{([^}]*)\}", tex)
bad = [p for p in paths if not (os.path.exists("paper/" + p + ".tex") or os.path.exists("paper/" + p + ".pdf"))]
print(f"supplementary.tex: {len(tex.splitlines())} lines; environments balanced ({sum(c.values())}); braces balanced; paths {len(paths)}, missing {bad}")
