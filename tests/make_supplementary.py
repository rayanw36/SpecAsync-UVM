#!/usr/bin/env python3
"""Gate C17: build paper/supplementary.tex (standalone IEEEtran, "Supplementary Material").
S1 full test tables (fragments of paper/tables/, captions from TABLES.md), S2 further figures (captions from paper/figures/FIGURES.md),
S3 the full ARTIFACT_CATALOG.md converted to LaTeX by this script, wording unchanged (only markup is converted).
Nothing from paper/figures/legacy or paper/figures/retired is used. No TeX toolchain is available on this host: the output is checked by script (brace and environment balance, paths)."""
import re, os
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
\noindent This document supplements the paper. Section~S1 holds the full test tables, S2 further figures, and S3 the full artifact catalog (the entries are reproduced from \texttt{ARTIFACT\_CATALOG.md} with markup converted by script and no change of wording).
"""
# ---------------- S1
TABS = [("t_e4", "T-E4", "Section VI (speculation against the shipped driver, E4)"), ("t_e5", "T-E5", "Section VI (the prefetcher's density rule, E5)"), ("t_e6", "T-E6", "Section VI (matched-threshold comparisons, E6)"),
        ("t_hand", "T-HAND", "Section VI (cost of the hook, E1b and E3b)"), ("t_e8", "T-E8", "Section VII (sparse access, E8; the paper shows these cells as a figure)"),
        ("t_e9", "T-E9", "Section VII (traced migration, E9)"), ("t_e9b", "T-E9", "Section VII (time outside the kernels, E8 untraced runs; second fragment of T-E9)")]
tmd = {}
for l in open("paper/tables/TABLES.md"):
    if l.startswith("| T-"):
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        tmd[c[0]] = c[3]
fmd = {}
for l in open("paper/figures/FIGURES.md"):
    if l.startswith("| F-"):
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        fmd[re.search(r"`([^`]+)`", c[1]).group(1)] = (c[0], c[-1], c[-2])
out = [PRE, r"\section{Full Test Tables}", r"\label{sec:s1}", ""]
for frag, tid, where in TABS:
    cap = tmd[tid]
    if tid == "T-E9":
        cap = cap.split(" The second fragment")[0] if frag == "t_e9" else "Second fragment of T-E9: " + (cap.split("The second fragment gives, ")[1] if "The second fragment gives, " in cap else cap)
    out += [r"\begin{table*}[t]", r"\centering\footnotesize", r"\caption{" + inline(cap) + " Supports " + inline(where) + ".}", r"\label{tab:s-" + frag + "}", r"\adjustbox{max width=\textwidth}{\input{tables/" + frag + "}}", r"\end{table*}", ""]
# ---------------- S2
FIGS = [("fig_e4_wallclock_by_arm", "figures/fig_e4_wallclock_by_arm", "figure*", "0.95\\textwidth"), ("fig_e7_threshold_by_workload_two_platforms", "figures/fig_e7_threshold_by_workload_two_platforms", "figure*", "0.95\\textwidth"),
        ("fig_ph_phase_medians", "figures/fig_ph_phase_medians", "figure", "\\columnwidth"), ("fig_h1", "figures/supplementary/F-H1", "figure", "\\columnwidth"),
        ("fig_h2_time", "figures/supplementary/F-H2-time", "figure", "\\columnwidth"), ("fig_h2_res", "figures/supplementary/F-H2-res", "figure", "\\columnwidth")]
out += [r"\section{Further Figures}", r"\label{sec:s2}", ""]
for key, path, env, width in FIGS:
    key_md = next(k for k in fmd if k == key or k.endswith(path.split("/")[-1]))
    title, cap, _n = fmd[key_md]
    out += [r"\begin{" + env + "}[t]", r"\centering", r"\includegraphics[width=" + width + "]{" + path + "}", r"\caption{" + inline(cap) + "}", r"\label{fig:s-" + os.path.basename(path) + "}", r"\end{" + env + "}", ""]
# ---------------- S3
out += [r"\section{Artifact Catalog}", r"\label{sec:s3}", ""]
lines = open("results/analysis/ARTIFACT_CATALOG.md").read().split("\n")
i, stack, para = 0, [], []
def flush_para():
    global para
    if para: out.append(inline(" ".join(para)) + "\n"); para = []
def close_lists(to=0):
    while len(stack) > to: out.append(r"\end{" + stack.pop()[0] + "}")
while i < len(lines):
    l = lines[i]
    h = re.match(r"^(#{1,4}) (.*)$", l)
    if h:
        flush_para(); close_lists()
        out.append({1: r"\subsection*{", 2: r"\subsection*{", 3: r"\subsubsection*{", 4: r"\paragraph{"}[len(h.group(1))] + inline(h.group(2)) + "}")
        i += 1; continue
    if l.strip() == "---":
        flush_para(); close_lists(); out.append(r"\medskip\hrule\medskip"); i += 1; continue
    if l.startswith("|"):
        flush_para(); close_lists()
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            rows.append([c.strip() for c in re.split(r"(?<!\\)\|", lines[i].strip().strip("|"))]); i += 1
        hdr, body = rows[0], [r for r in rows[2:]]
        ncol = max(len(r) for r in rows)   # rows #7-#11 of the first table have one more cell than the header: pad, do not change the text
        pad = lambda r: r + [""] * (ncol - len(r))   # noqa: E731
        hdr, body = pad(hdr), [pad(r) for r in body]
        colspec = "".join(r"p{\dimexpr(\textwidth-" + str(2 * ncol) + r"\tabcolsep)/" + str(ncol) + r"\relax}" for _ in range(ncol))
        out += [r"\onecolumn", r"{\footnotesize\emergencystretch=3em", r"\begin{longtable}{" + colspec + "}", r"\toprule", " & ".join(inline(c) for c in hdr) + r" \\", r"\midrule", r"\endhead"]
        out += [" & ".join(inline(c) for c in r) + r" \\" for r in body] + [r"\bottomrule", r"\end{longtable}", "}", r"\twocolumn", ""]
        continue
    b = re.match(r"^(\s*)([-*]|\d+\.) (.*)$", l)
    if b:
        flush_para()
        depth = len(b.group(1)) // 2 + 1
        kind = "enumerate" if b.group(2)[0].isdigit() else "itemize"
        close_lists(depth) if len(stack) > depth else None
        while len(stack) < depth: stack.append((kind,)); out.append(r"\begin{" + kind + "}")
        text = b.group(3); i += 1
        while i < len(lines) and re.match(r"^\s{2,}\S", lines[i]) and not re.match(r"^\s*([-*]|\d+\.) ", lines[i]): text += " " + lines[i].strip(); i += 1
        out.append(r"\item " + inline(text)); continue
    if not l.strip():
        flush_para(); 
        # a blank line ends a list unless the next non-blank line is a list item or an indented continuation
        j = i + 1
        while j < len(lines) and not lines[j].strip(): j += 1
        if stack and not (j < len(lines) and re.match(r"^\s*([-*]|\d+\.) |^\s{2,}\S", lines[j])): close_lists()
        i += 1; continue
    if stack and re.match(r"^\s{2,}\S", l):   # continuation of the last list item
        out.append(inline(l.strip())); i += 1; continue
    close_lists(); para.append(l.strip()); i += 1
flush_para(); close_lists()
out += [r"\end{document}", ""]
tex = "\n".join(out)
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
