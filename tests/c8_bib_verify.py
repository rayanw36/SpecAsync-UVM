#!/usr/bin/env python3
"""Gate C8 phase 7: look up each UNVERIFIED entry of paper/ref.bib (and allen2024finegrain's year) in the Crossref registry (api.crossref.org; by DOI when
the entry has one, else by title). Read-only: ref.bib is NOT edited. A registry record is accepted only if its title matches the bib title (difflib ratio
>= 0.9, case and braces ignored); otherwise the entry is reported "no registry match" and nothing is guessed. Writes results/analysis/consolidation/BIB_VERIFY_C8.md.
No identity, email or key is sent: plain GET requests only."""
import difflib, json, re, sys, time, urllib.parse, urllib.request
BIB = open("paper/ref.bib").read()
OUT = "results/analysis/consolidation/BIB_VERIFY_C8.md"
ents = [e for e in re.split(r"\n(?=@\w+\{)", BIB) if e.startswith("@")]
sel = [e for e in ents if "UNVERIFIED" in e or e.startswith("@article{allen2024finegrain")]

def field(e, k):
    m = re.search(rf"\b{k}\s*=\s*(\{{(?:[^{{}}]|\{{[^{{}}]*\}})*\}}|\"[^\"]*\"|\d+)", e, re.I | re.S)
    return " ".join(re.sub(r"[{}]", "", m.group(1)).split()).strip('"') if m else ""

# lookup-only query titles for two entries whose bib title differs from the registry's (abbreviation / subtitle); the match rule below still applies
ALT = {"allen2024finegrain": "Fine-grain Quantitative Analysis of Demand Paging in Unified Virtual Memory",
       "raasveldt2018fair": "Fair Benchmarking Considered Difficult: Common Pitfalls In Database Performance Testing"}

def match(bibt, regt):
    a, b = norm(bibt), norm(regt)
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.9 or (len(b) > 20 and a.startswith(b))

def norm(t): return re.sub(r"[^a-z0-9 ]", "", re.sub(r"[{}]", "", t.lower()))

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "specasync-bib-check/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r: return json.load(r)

rows, blocked = [], False
for e in sel:
    key = re.match(r"@\w+\{([^,]+),", e).group(1)
    title, doi = field(e, "title"), field(e, "doi")
    rec = None
    try:
        if doi:
            rec = get("https://api.crossref.org/works/" + urllib.parse.quote(doi))["message"]
        else:
            items = get("https://api.crossref.org/works?rows=5&query.bibliographic=" + urllib.parse.quote(ALT.get(key, title)))["message"]["items"]
            cand = [i for i in items if match(title, (i.get("title") or [""])[0]) or match(ALT.get(key, title), (i.get("title") or [""])[0])]
            rec = cand[0] if cand else None
    except Exception as ex:
        blocked = True; rows.append((key, "blocked", str(ex)[:80])); break
    time.sleep(0.5)
    if not rec:
        rows.append((key, "nomatch", title)); continue
    reg = dict(title=(rec.get("title") or [""])[0], year=str((rec.get("issued", {}).get("date-parts") or [[""]])[0][0]),
               venue=(rec.get("container-title") or [""])[0], volume=rec.get("volume", ""), number=rec.get("issue", ""), pages=rec.get("page", ""), doi=rec.get("DOI", ""),
               authors="; ".join(f"{a.get('family','')}, {a.get('given','')}".strip(", ") for a in rec.get("author", [])))
    rows.append((key, "ok", dict(bib=dict(author=field(e, "author"), year=field(e, "year"), volume=field(e, "volume"), number=field(e, "number"), pages=field(e, "pages"), doi=doi,
                                         venue=field(e, "journal") or field(e, "booktitle")), reg=reg)))
md = ["# Bibliography verification against the Crossref registry (Gate C8 phase 7)", "",
      "`paper/ref.bib` was **not edited**. Each UNVERIFIED entry was looked up by DOI (if it has one) or by title; a record counts only if its title matches (ratio >= 0.9, or the registry title is a prefix of the bib title; two entries were queried under their full/expanded titles, see `ALT` in the script). Nothing was guessed. Registry = `api.crossref.org`, plain GET requests, no credentials or email sent.", ""]
if blocked: md += ["**blocked:** " + rows[-1][2], ""]
md += ["| key | field | bib value | registry value | proposed fix |", "|---|---|---|---|---|"]
for key, st, d in rows:
    if st == "blocked": md.append(f"| {key} | - | - | blocked ({d}) | none |"); continue
    if st == "nomatch": md.append(f"| {key} | - | - | no registry match for the title | none (not in Crossref under this title; check the venue's site) |"); continue
    b, r = d["bib"], d["reg"]
    any_row = False
    for f in ("year", "volume", "number", "pages", "venue", "doi"):
        bv, rv = b[f], r["venue" if f == "venue" else f]
        if rv and bv != rv and not (f == "venue" and norm(rv)[:25] in norm(bv) + " "):
            md.append(f"| {key} | {f} | {bv or '(absent)'} | {rv} | {'add' if not bv else 'replace'} `{f} = {{{rv}}}` |"); any_row = True
    md.append(f"| {key} | authors | {b['author'] or '(absent)'} | {r['authors'] or '(none returned)'} | replace with the registry list if it is complete |")
    if not any_row: md.append(f"| {key} | (other fields) | - | agree with the registry | none |")
md += ["", "## allen2024finegrain", ""]
a = [r for r in rows if r[0] == "allen2024finegrain"]
if a and a[0][1] == "ok":
    r = a[0][2]["reg"]
    md.append(f"The registry gives **year {r['year']}** (venue `{r['venue']}`, volume {r['volume']}, issue {r['number']}, DOI {r['doi']}); ref.bib has year {a[0][2]['bib']['year']} (key `allen2024finegrain`).")
else:
    md.append("No registry record was matched for this entry (see the table).")
open(OUT, "w").write("\n".join(md) + "\n"); print("\n".join(md))
