#!/usr/bin/env python3
"""Gate C21: replace four ref.bib entries by their Crossref records (fetched by DOI; cached JSON in /tmp/claude-1000/c21). Keys are kept. Reuses the author/title helpers of c20_bib_apply.py."""
import html, json, re, sys, unicodedata
sys.path.insert(0, "tests")
import c20_bibio as B
src = open("tests/c20_bib_apply.py").read()
exec(src[src.index("ACC = "):src.index("SRC = {}")])   # tex, initials, authors_cr, protect, tol
exec(src[src.index("REM_ORDER"):src.index("def split_notes")])   # fmt
CHECK = {"nihaal2024compression": (["Nihaal", "Mutyam"], "Parallel Processing", 2024)}
PLAN = {"li2019oversubframework": None, "diehl2018hpxcl": None, "nihaal2024compression": None, "nazaraliyev2024gpuvm": "Preprint: arXiv:2411.05309 (GPUVM)"}
s = open("paper/ref.bib").read()
for k, extra in PLAN.items():
    c = json.load(open(f"/tmp/claude-1000/c21/{k}.json"))
    if k in CHECK:
        fam, venue, yr = CHECK[k]
        ok = [a["family"] for a in c["authors"]] == fam and venue in c["container"] and c["year"] == yr
        print(k, "authors/venue check:", ok)
        if not ok: print("MISMATCH, entry left as is"); continue
    m = re.search(rf"@\w+\{{{k},.*?\n\}}\n", s, re.S)
    old = B.parse("paper/ref.bib")[k]["fields"]
    xn = old.get("x-note", "")
    if extra: xn = (extra + " | " if not xn else extra + " | " + xn)
    f = {"author": authors_cr(c["authors"]), "title": c["title"], "booktitle": tex(__import__("html").unescape(c["container"])), "pages": c["page"].replace("-", "--"), "year": str(c["year"]), "doi": c["doi"]}
    new = fmt(k, "inproceedings", f, xn)
    s = s[:m.start()] + new + "\n" + s[m.end():]
    print("replaced", k)
open("paper/ref.bib", "w").write(s)
