#!/usr/bin/env python3
"""Gate C8 phase 4: follow \\input from paper/main_v2.tex and report unresolved \\ref/\\eqref/\\autoref, duplicate \\label, and \\cite keys missing from paper/ref.bib.
Comments (unescaped %) are ignored. Read-only. usage: c8_ref_check.py [MAIN_TEX] [OUT_MD]"""
import os, re, sys
MAIN = sys.argv[1] if len(sys.argv) > 1 else "paper/main_v2.tex"
OUT = sys.argv[2] if len(sys.argv) > 2 else "results/analysis/consolidation/MAIN_V2_CHECK.md"
base = os.path.dirname(MAIN)
files, queue = [], [MAIN]
while queue:
    f = queue.pop(0)
    if f in files or not os.path.exists(f): continue
    files.append(f)
    for l in open(f):
        l = re.sub(r"(?<!\\)%.*$", "", l)
        for m in re.finditer(r"\\input\{([^}]*)\}", l):
            n = m.group(1); n = n if n.endswith(".tex") else n + ".tex"
            queue.append(os.path.join(base, n))
labels, refs, cites = {}, [], []
for f in files:
    for n, l in enumerate(open(f), 1):
        l = re.sub(r"(?<!\\)%.*$", "", l)
        for m in re.finditer(r"\\label\{([^}]*)\}", l): labels.setdefault(m.group(1), []).append(f"{os.path.basename(f)}:{n}")
        for m in re.finditer(r"\\(?:ref|eqref|autoref|Cref|cref|pageref)\*?\{([^}]*)\}", l):
            for k in m.group(1).split(","): refs.append((os.path.basename(f), n, k.strip()))
        for m in re.finditer(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}", l):
            for k in m.group(1).split(","): cites.append((os.path.basename(f), n, k.strip()))
bib = set(re.findall(r"^@\w+\{([^,\s]+),", open(os.path.join(base, "ref.bib")).read(), re.M))
bad_refs = [r for r in refs if r[2] not in labels]
dups = {k: v for k, v in labels.items() if len(v) > 1}
bad_cites = sorted({(r[2]) for r in cites if r[2] not in bib})
md = ["# main_v2.tex reference check (Gate C8 phase 4)", "", f"Files followed: {', '.join(os.path.basename(f) for f in files)}", "",
      f"- labels: {len(labels)}; \\ref uses: {len(refs)}; unresolved refs: **{len(bad_refs)}**", f"- duplicate labels: **{len(dups)}**", f"- distinct cite keys: {len({c[2] for c in cites})}; missing from ref.bib: **{len(bad_cites)}**", ""]
if bad_refs: md += ["## Unresolved \\ref", ""] + [f"- `{k}` at {f}:{n}" for f, n, k in bad_refs] + [""]
if dups: md += ["## Duplicate labels", ""] + [f"- `{k}`: {', '.join(v)}" for k, v in dups.items()] + [""]
if bad_cites: md += ["## Cite keys missing from ref.bib", ""] + [f"- `{k}`" for k in bad_cites] + [""]
open(OUT, "w").write("\n".join(md) + "\n"); print("\n".join(md))
