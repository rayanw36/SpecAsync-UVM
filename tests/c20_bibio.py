"""BibTeX parse/write helpers and Crossref/arXiv record normalisers for Gate C20."""
import re, json
def parse(path):
    s = open(path).read(); out = {}; i = 0
    comment_spans = []
    m0 = re.search(r"@Comment\s*\{", s)
    if m0:
        d, j = 1, m0.end()
        while j < len(s) and d: d += (s[j] == "{") - (s[j] == "}"); j += 1
        comment_spans.append((m0.start(), j))
    for m in re.finditer(r"^@(\w+)\s*\{\s*([^,\s@{]+)\s*,", s, re.M):
        typ, key = m.group(1), m.group(2)
        if typ.lower() in ("comment", "string", "preamble"): continue
        d, j = 1, m.start() + s[m.start():].index("{") + 1
        while j < len(s) and d: d += (s[j] == "{") - (s[j] == "}"); j += 1
        body = s[m.end():j - 1]
        fields = {}
        for fm in re.finditer(r"(\w[\w-]*)\s*=\s*", body):
            if fm.start() and body[:fm.start()].count("{") != body[:fm.start()].count("}"): continue
            k0 = fm.group(1).lower(); p = fm.end()
            if body[p] == "{":
                d, q = 1, p + 1
                while q < len(body) and d: d += (body[q] == "{") - (body[q] == "}"); q += 1
                v = body[p + 1:q - 1]
            elif body[p] == '"':
                q = body.index('"', p + 1); v = body[p + 1:q]
            else:
                q = re.compile(r"[,\s}]").search(body, p).start(); v = body[p:q]
            fields[k0] = re.sub(r"\s+", " ", v).strip()
        out[key] = {"type": typ.lower(), "fields": fields, "in_comment": any(a <= m.start() < b for a, b in comment_spans)}
    return out
def plain(t):
    t = re.sub(r"\\[`'^\"~=.]\{?(\w)\}?", r"\1", t); t = re.sub(r"\{\\[a-z]+\{?(\w)\}?\}", r"\1", t)
    return re.sub(r"[{}]", "", t).replace("--", "-").strip()
def norm(t): return re.sub(r"[^a-z0-9]+", " ", plain(t).lower()).strip()
def cr_item(m):
    au = [{"family": a.get("family", ""), "given": a.get("given", "")} for a in m.get("author", [])]
    iss = m.get("issued", {}).get("date-parts", [[None]])[0][0]
    return {"doi": m.get("DOI"), "title": (m.get("title") or [""])[0], "container": (m.get("container-title") or [""])[0], "type": m.get("type"), "volume": m.get("volume"), "issue": m.get("issue"),
            "page": m.get("page"), "year": iss, "authors": au, "publisher": m.get("publisher"), "score": m.get("score"), "subtitle": (m.get("subtitle") or [""])[0], "article": m.get("article-number")}
def arxiv_item(x):
    if x.strip().startswith("{"): return None
    t = re.search(r"<entry>.*?<title>(.*?)</title>", x, re.S)
    if not t: return None
    au = re.findall(r"<author>\s*<name>(.*?)</name>", x)
    pub = re.search(r"<published>(\d{4})", x)
    doi = re.search(r"<arxiv:doi[^>]*>(.*?)</arxiv:doi>", x)
    jr = re.search(r"<arxiv:journal_ref[^>]*>(.*?)</arxiv:journal_ref>", x, re.S)
    return {"title": re.sub(r"\s+", " ", t.group(1)).strip(), "authors": au, "year": pub.group(1) if pub else None, "doi": doi.group(1) if doi else None, "journal_ref": re.sub(r"\s+", " ", jr.group(1)) if jr else None}
