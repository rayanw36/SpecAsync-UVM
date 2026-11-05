#!/usr/bin/env python3
"""Gate C9 phase 1a: apply the Crossref fixes of BIB_VERIFY_C8.md to paper/ref.bib (authors, year, volume, number, pages with --, doi), drop the resolved
UNVERIFIED sentences from notes, and add one provenance comment. bastemTilesTR -> the existing @inproceedings bastem2017tiles gets the registry fields.
Registry values are read from BIB_VERIFY_C8.md (they came from api.crossref.org); nothing is typed by hand. usage: c9_apply_bib.py"""
import re
BIB = "paper/ref.bib"
V = open("results/analysis/consolidation/BIB_VERIFY_C8.md").read()
reg = {}
for l in V.split("\n"):
    if l.startswith("| ") and not l.startswith("| key") and not l.startswith("|---"):
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        if len(c) >= 5 and c[1] in ("year", "volume", "number", "pages", "doi", "authors", "venue"):
            reg.setdefault(c[0], {})[c[1]] = c[3]
ACC = {"á": "{\\'a}", "é": "{\\'e}", "ó": "{\\'o}", "ü": "{\\\"u}", "ő": "{\\H{o}}"}
def tex(s): return "".join(ACC.get(ch, ch) for ch in s)
def norm_auth(s):
    out = []
    for a in re.split(r"\s+and\s+|;\s*", s):
        a = re.sub(r"[{}\\\"'^`~.]", "", a).strip()
        if "," in a: fam, giv = [x.strip() for x in a.split(",", 1)]
        else: parts = a.split(); fam, giv = parts[-1], " ".join(parts[:-1])
        out.append((fam.lower(), (giv.split() or [''])[0].lower()))
    return out
def span(text, name):
    m = re.search(rf"^(\s*){name}\s*=\s*", text, re.M | re.I)
    if not m: return None
    i = m.end()
    if text[i] == "{":
        d = 0
        for j in range(i, len(text)):
            d += text[j] == "{"; d -= text[j] == "}"
            if d == 0: return (m.start(), j + 1, m.group(1))
    return None
def setf(e, name, val):
    sp = span(e, name)
    if sp: return e[:sp[0]] + f"{sp[2]}{name:<9}= {{{val}}}" + e[sp[1]:]
    # insert before note or before closing brace
    sp = span(e, "note")
    ins = f"  {name:<9}= {{{val}}},\n"
    if sp: return e[:sp[0]] + ins + e[sp[0]:].lstrip("\n") if False else e[:sp[0]] + ins.rstrip("\n") + "\n" + e[sp[0]:]
    return e.rstrip()[:-1].rstrip().rstrip(",") + ",\n" + ins.rstrip(",\n") + "\n}"
def fix_note(e):
    sp = span(e, "note")
    if not sp: return e
    body = e[sp[0]:sp[1]]
    new = re.sub(r"UNVERIFIED:[^.]*\.\s*", "", body)
    new = re.sub(r"\{\s+", "{", new)
    if re.match(r"\s*note\s*=\s*\{\s*\}", new): return e[:sp[0]].rstrip().rstrip(",") + e[sp[1]:]
    return e[:sp[0]] + new + e[sp[1]:]
text = open(BIB).read()
parts = re.split(r"(?=^@\w+\{)", text, flags=re.M)
changed = []
for i, e in enumerate(parts):
    m = re.match(r"@\w+\{([^,]+),", e)
    if not m: continue
    key = m.group(1)
    if key == "bastemTilesTR": continue   # inside the legacy @comment block; left as is
    rk = "bastemTilesTR" if key == "bastem2017tiles" else key
    if rk not in reg: continue
    r = reg[rk]; o = e
    if "authors" in r:
        regauth = r["authors"].split("; ")
        bibauth = span(e, "author"); cur = e[bibauth[0]:bibauth[1]].split("=", 1)[1].strip()[1:-1] if bibauth else ""
        if "others" in cur or norm_auth(cur) != norm_auth(r["authors"]):
            e = setf(e, "author", " and ".join(tex(a) for a in regauth))
    for f in ("year", "volume", "number"):
        if f in r and f not in ("year",) or (f == "year" and "year" in r): e = setf(e, f, r[f])
    if "pages" in r: e = setf(e, "pages", r["pages"].replace("-", "--"))
    if "doi" in r and key != "bastem2017tiles": e = setf(e, "doi", r["doi"])
    if key == "bastem2017tiles":
        head, _, tail = e.partition("\n}\n")          # the entry ends at its own closing brace; the comment block after it is kept
        head = setf(head, "doi", r["doi"]); head = setf(head, "booktitle", r["venue"]); head = setf(head, "year", r["year"])
        head = re.sub(r",?\s*note\s*=\s*\{(?:[^{}]|\{[^{}]*\})*\}", "", head)
        e = head.rstrip().rstrip(",") + "\n}\n" + tail
    e = fix_note(e)
    if e != o: parts[i] = e; changed.append(key)
text = "".join(parts)
text = text.replace("% ========================================================\n", "% ========================================================\n% Entries below with registry-supplied fields (authors, volume, number, pages, doi) were verified against Crossref 2026-11-05 (results/analysis/consolidation/BIB_VERIFY_C8.md).\n", 1) if "verified against Crossref 2026-11-05" not in text else text
open(BIB, "w").write(text)
print("changed:", changed)
