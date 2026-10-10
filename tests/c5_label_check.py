#!/usr/bin/env python3
"""Gate C5 step 1d: list every \\ref-style reference and every \\label in the manuscript files and report references that do not resolve (read-only; nothing is fixed).
Files: paper/main.tex, paper/section1_introduction.tex, paper/section3_background.tex, and (read-only, outside the repo) ~/Downloads/section2_related_work.tex.
Comment text (after an unescaped %) is ignored. usage: c5_label_check.py [OUT_CSV]"""
import csv, os, re, sys
FILES = ["paper/main.tex", "paper/section1_introduction.tex", "paper/section3_background.tex", os.path.expanduser("~/Downloads/section2_related_work.tex")]
OUT = sys.argv[1] if len(sys.argv) > 1 else "results/analysis/consolidation/LABEL_CHECK.csv"
REF = re.compile(r"\\(ref|Cref|cref|autoref|eqref|pageref|nameref|vref)\*?\{([^}]*)\}")
LAB = re.compile(r"\\label\{([^}]*)\}")
labels, refs = {}, []
for f in FILES:
    if not os.path.exists(f):
        print("MISSING FILE", f); continue
    for n, line in enumerate(open(f), 1):
        line = re.sub(r"(?<!\\)%.*$", "", line)
        for m in LAB.finditer(line):
            labels.setdefault(m.group(1), []).append(f"{os.path.basename(f)}:{n}")
        for m in REF.finditer(line):
            for k in m.group(2).split(","):
                refs.append((os.path.basename(f), n, m.group(1), k.strip()))
bad = [r for r in refs if r[3] not in labels]
dup = {k: v for k, v in labels.items() if len(v) > 1}
with open(OUT, "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["file", "line", "command", "key", "resolves", "defined_at"])
    for f, n, c, k in refs:
        w.writerow([f, n, c, k, "yes" if k in labels else "NO", ";".join(labels.get(k, []))])
print(f"{len(refs)} references, {len(labels)} distinct labels defined, {len(bad)} unresolved references, {len(dup)} labels defined more than once")
for f, n, c, k in bad: print(f"  UNRESOLVED {f}:{n} \\{c}{{{k}}}")
for k, v in dup.items(): print(f"  DUPLICATE label {k}: {v}")
print("labels defined:", {os.path.basename(f): sorted(k for k, v in labels.items() if any(x.startswith(os.path.basename(f) + ":") for x in v)) for f in FILES if os.path.exists(f)})
