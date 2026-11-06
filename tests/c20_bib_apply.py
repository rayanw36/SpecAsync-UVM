#!/usr/bin/env python3
"""Gate C20 steps 1, 3, 4: rewrite paper/ref.bib from the Crossref/arXiv lookup (tests/c20_bib_lookup.py output) and write consolidation/BIB_VERIFY_C20.md.
 - note/annote/addendum/comment -> x-note (ignored by BibTeX). No field is invented: every new value is copied from a Crossref or arXiv record.
 - Match rule: a DOI lookup is authoritative; a title lookup is accepted only if exactly one non-preprint candidate has the same title (case, punctuation, spaces and parenthesised acronyms ignored);
   otherwise the entry stays as it was and is marked OPEN with the candidates. arXiv-only entries get the author list from arXiv when the arXiv title matches.
 - Titles are protected with braces (acronyms and proper nouns). The original file is kept as paper/archive/ref_c19.bib; entries removed (arXiv duplicates of upgraded keys, entries inside @Comment that are not cited) are listed in the report."""
import html, json, re, sys, unicodedata
sys.path.insert(0, "tests")
import c20_bibio as B
SCR = "/tmp/claude-1000/c20"
old = B.parse("paper/archive/ref_c19.bib")
L = json.load(open(f"{SCR}/lookup.json"))
cited = open("/tmp/claude-1000/cited.txt").read().split()
ACC = {"́": "'", "̀": "`", "̂": "^", "̈": '"', "̃": "~", "̄": "=", "̇": ".", "̋": "H ", "̌": "v ", "̧": "c ", "̨": "k "}
def tex(s):
    out = []
    for ch in unicodedata.normalize("NFD", s):
        if ch in ACC and out:
            a = ACC[ch]; base = out.pop()
            out.append("{\\" + a + ("" if len(a) == 1 else "") + base + "}")
        else: out.append({"\u00f8": r"{\o}", "\u0142": r"{\l}", "\u00df": r"{\ss}", "\u00e6": r"{\ae}", "\u2019": "'", "\u2013": "--", "\u2014": "---"}.get(ch, ch))
    return "".join(out).replace("&amp;", "&").replace("&", r"\&")
def initials(given):
    ws = given.replace(".", ". ").split(); ini = []; part = []
    for w in ws:
        if w[0].islower(): part.append(w); continue
        ini.append("-".join(x[0] + "." for x in w.split("-") if x))
    return " ".join(ini), " ".join(part)
def authors_cr(au):
    r = []
    for a in au:
        ini, part = initials(a["given"]) if a["given"] else ("", "")
        fam = (part + " " + a["family"]).strip()
        r.append(tex(fam) + (", " + tex(ini) if ini else ""))
    return " and ".join(r)
def authors_arxiv(names):
    r = []
    for n in names:
        w = n.split(); fam = w[-1]; given = " ".join(w[:-1])
        ini, part = initials(given); r.append(tex((part + " " + fam).strip()) + (", " + tex(ini) if ini else ""))
    return " and ".join(r)
PROT = {"Markov", "Forest", "Boulder", "R-Max", "Early-Adaptor", "I/O", "SoK"}
def protect(title):
    out, depth, tok = [], 0, ""
    parts = re.split(r"(\s+)", title)
    res = []
    for p in parts:
        if not p.strip() or "{" in p or "}" in p: res.append(p); continue
        m = re.match(r"^([\(\"']*)(.*?)([\):,.?!\"']*)$", p)
        pre, core, post = m.groups()
        if core and (re.search(r"[A-Z]{2}", core) or core in PROT or re.search(r"[A-Z]\d|\d[A-Z]|[a-z][A-Z]", core)):
            core = "{" + core + "}"
        res.append(pre + core + post)
    return "".join(res)
def tol(t): return re.sub(r"[^a-z0-9]", "", re.sub(r"\([^)]*\)", "", B.plain(html.unescape(t)).lower()))
SRC = {}
def newfields(k, e):
    """returns (fields dict, status, detail, source) for a cited key."""
    f = dict(e["fields"]); r = L[k]; cands = r["cands"]
    bt = tol(f.get("title", ""))
    sel, why = None, ""
    if r.get("doi") and cands and cands[0]["via"] == "doi": sel = cands[0]
    elif not r.get("doi") or r.get("doi_error"):
        ex = [c for c in cands if c["type"] in ("proceedings-article", "journal-article") and tol(c["title"] + (": " + c["subtitle"] if c.get("subtitle") else "")) == bt or (c["type"] in ("proceedings-article", "journal-article") and tol(c["title"]) == bt)]
        if len(ex) == 1: sel = ex[0]
        elif len(ex) > 1: why = "two or more candidates"
        else: why = "no exact title match"
    ax = r.get("arxiv")
    new = dict(f); status = "UNCHANGED"; source = ""
    if sel:
        source = "https://api.crossref.org/works/" + sel["doi"]
        titl = f.get("title", "")
        full = sel["title"] + (": " + sel["subtitle"] if sel.get("subtitle") else "")
        if tol(titl) != tol(full) and tol(titl) != tol(sel["title"]) and k not in ("go2023earlyadaptor",):
            titl = full
        new["title"] = titl
        new["author"] = authors_cr(sel["authors"])
        new["year"] = str(sel["year"])
        new["doi"] = sel["doi"]
        cont = html.unescape(sel["container"])
        if sel["type"] == "journal-article":
            new["journal"] = tex(cont); new.pop("booktitle", None)
            for kk in ("volume", "issue"):
                if sel.get(kk): new["volume" if kk == "volume" else "number"] = sel[kk]
            if sel.get("article"): new["note"] = "Art. no. " + sel["article"]
            new["_type"] = "article"
        else:
            new["booktitle"] = tex(cont); new.pop("journal", None); new["_type"] = "inproceedings"
            new.pop("volume", None); new.pop("number", None)
        if sel.get("page"): new["pages"] = sel["page"].replace("-", "--")
        for kk in ("howpublished", "archiveprefix"): new.pop(kk, None)
        status = "FIXED"
    elif ax and tol(ax["title"]) == bt:
        source = "http://export.arxiv.org/api/query?id_list=" + r["eprint"]
        new["author"] = authors_arxiv(ax["authors"]); status = "FIXED"; why = "authors from arXiv; venue not changed (no peer-reviewed version found on Crossref)"
        new["howpublished"] = "arXiv preprint arXiv:" + r["eprint"]
    else:
        status = "OPEN"
    return new, status, why, source
REM_ORDER = ["author", "title", "journal", "booktitle", "volume", "number", "pages", "year", "address", "publisher", "howpublished", "doi", "note", "eprint", "archiveprefix"]
def fmt(k, typ, f, xnote):
    ls = [f"@{typ}{{{k},"]
    seen = set()
    for n in REM_ORDER + sorted(set(f) - set(REM_ORDER) - {"_type", "x-note", "annote", "addendum", "comment", "institution"}):
        if n in f and n not in seen and n != "_type":
            v = f[n]
            if n == "title": v = protect(v)
            ls.append(f"  {n} = {{{v}}},"); seen.add(n)
    if xnote: ls.append(f"  x-note = {{{xnote}}},")
    ls[-1] = ls[-1].rstrip(",")
    return "\n".join(ls + ["}"])
def split_notes(f):
    x = []; keep = dict(f)
    for n in ("note", "annote", "addendum", "comment"):
        if n in keep: x.append(f"{n}: " + keep.pop(n))
    return keep, " | ".join(x)
out_entries, report, renamed, keptnotes, removed = [], [], [], [], []
# decide upgrades: cited originals take the _published keys' place
UPG = {"long2022dlprefetch_published", "choi2022gpuaware_published", "parravicini2021dagpolyglot_published"}
CHANGED = {}
for k in sorted(old):
    e = old[k]
    if k in UPG or (e["in_comment"] and k not in cited):
        removed.append((k, "arXiv duplicate of an upgraded cited key" if k in UPG else "inside @Comment and not cited")); continue
    keep, xnote = split_notes(e["fields"])
    if xnote: renamed.append((k, xnote))
    base = {"fields": keep, "type": e["type"]}
    if k in cited:
        nf, status, why, src = newfields(k, {"fields": keep, "type": e["type"]})
        typ = nf.pop("_type", e["type"])
        if "Art. no." in nf.get("note", ""): keptnotes.append((k, nf["note"]))
        # arXiv-only entries: the howpublished field carries the identifier, no note kept
        if status == "FIXED" and typ in ("article", "inproceedings"): nf.pop("eprint", None) if False else None
        CHANGED[k] = (keep, nf, status, why, src)
        if k == "gu2020uvmbench" or k == "nazaraliyev2024gpuvm": pass
        out_entries.append(fmt(k, typ, nf, xnote))
    else:
        out_entries.append(fmt(k, e["type"], keep, xnote))
hdr = "% ref.bib, cleaned for print (Gate C20). Internal notes are in x-note fields (ignored by BibTeX). Fields filled from Crossref/arXiv; see results/analysis/consolidation/BIB_VERIFY_C20.md.\n% The previous file (with audit history, @Comment block and all notes) is paper/archive/ref_c19.bib.\n\n"
open("paper/ref.bib", "w").write(hdr + "\n\n".join(out_entries) + "\n")
json.dump({"renamed": renamed, "kept": keptnotes, "removed": removed, "changed": {k: [v[0], v[1], v[2], v[3], v[4]] for k, v in CHANGED.items()}}, open(f"{SCR}/apply.json", "w"), indent=1)
print(len(out_entries), "entries written;", len(renamed), "x-note renames;", len(removed), "removed")
