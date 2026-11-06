#!/usr/bin/env python3
"""Gate C20 step 2 (lookup): for each cited key of paper/ref.bib, query Crossref (by DOI when present, otherwise by title + first author) and arXiv (arXiv-only entries);
cache every response under SCRATCH and write SCRATCH/lookup.json. No email or identifier of the user is sent (generic user agent). Nothing is changed in ref.bib here."""
import json, os, re, sys, time, urllib.parse, urllib.request
sys.path.insert(0, "tests")
import c20_bibio as B
SCR = sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-1000/c20"
os.makedirs(SCR, exist_ok=True)
UA = {"User-Agent": "SpecAsync-bib-check/1.0"}
def get(url, tag):
    f = f"{SCR}/{re.sub(r'[^A-Za-z0-9._-]', '_', tag)}.json"
    if os.path.exists(f): return open(f).read()
    for k in range(3):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read().decode()
            open(f, "w").write(r); time.sleep(0.4); return r
        except Exception as e:
            err = str(e); time.sleep(2)
    open(f, "w").write(json.dumps({"error": err})); return open(f).read()
entries = B.parse("paper/ref.bib")
cited = open("/tmp/claude-1000/cited.txt").read().split()
out = {}
for k in cited:
    e = entries[k]; f = e["fields"]
    rec = {"bib_title": B.plain(f.get("title", "")), "doi": f.get("doi"), "eprint": f.get("eprint"), "cands": []}
    if f.get("doi"):
        r = json.loads(get(f"https://api.crossref.org/works/{urllib.parse.quote(f['doi'])}", f"doi_{f['doi']}"))
        if "message" in r: rec["cands"].append({"via": "doi", **B.cr_item(r["message"])})
        else: rec["doi_error"] = r.get("error", "not found")
    if not f.get("doi") or rec.get("doi_error"):
        fa = ""
        au = f.get("author", "")
        m = re.match(r"\s*([^,]+?)(?:,| and | others)", au)
        if m and "others" not in au.split(" and ")[0]: fa = m.group(1).split()[-1]
        q = urllib.parse.urlencode({"query.bibliographic": B.plain(f.get("title", "")) + " " + fa, "rows": 6})
        r = json.loads(get(f"https://api.crossref.org/works?{q}", f"q_{k}"))
        for it in r.get("message", {}).get("items", []): rec["cands"].append({"via": "title", **B.cr_item(it)})
    if f.get("eprint"):
        x = get(f"http://export.arxiv.org/api/query?id_list={f['eprint']}", f"arxiv_{f['eprint']}")
        rec["arxiv"] = B.arxiv_item(x)
    out[k] = rec
json.dump(out, open(f"{SCR}/lookup.json", "w"), indent=1)
print("done", len(out))
