#!/usr/bin/env python3
"""Gate C4 step 2: list every number in paper/section1_introduction.tex and whether it appears in EVIDENCE_EXTRACT.md. Does NOT edit the prose.
Tokenisation: LaTeX comments, \\cite{}/\\ref{}/\\label{} arguments and math-mode delimiters are dropped; every remaining numeral is a token.
Match tiers (a token is looked up against every number in the evidence value strings, also x100 for fractions below 1.5):
  exact          the same digits (thousands commas ignored, sign ignored)
  rounded        the evidence number rounded to the token's own number of decimals equals the token (e.g. 3.4 vs 3.36)
  not found      neither
Word numbers (four, nine, Twenty-five ...) are listed separately for manual checking.
usage: c4_section1_numbers.py [TEX] [OUT_CSV]"""
import csv
import re
import sys

TEX = sys.argv[1] if len(sys.argv) > 1 else "paper/section1_introduction.tex"
OUT = sys.argv[2] if len(sys.argv) > 2 else "results/analysis/consolidation/SECTION1_NUMBER_CHECK.csv"
EV = "results/analysis/consolidation/EVIDENCE_EXTRACT.md"
NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)*(?![\w])|(?<![\w.])\d[\d,]*(?:\.\d+)*")
WORDS = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|hundred|"
                   r"(?:twenty|thirty|forty)-(?:one|two|three|four|five|six|seven|eight|nine)|first|second|third|fourth|half)\b", re.I)


def strip_tex(line):
    line = re.sub(r"(?<!\\)%.*$", "", line)
    line = re.sub(r"\\(cite|ref|label|input|includegraphics)\*?(\[[^\]]*\])?\{[^}]*\}", " ", line)
    return line


def ev_numbers():
    rows = [l for l in open(EV) if l.startswith("| `")]
    out = []
    for l in rows:
        eid = l.split("`")[1]
        cells = l.split("|")
        text = cells[2] if len(cells) > 2 else ""
        for m in re.finditer(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?![\w.]*e[-+]?\d)", text):
            s = m.group(0).replace(",", "")
            try:
                out.append((float(s), s, eid))
            except ValueError:
                pass
    return out


def main():
    ev = ev_numbers()
    exact, vals = {}, []
    for v, s, eid in ev:
        exact.setdefault(s.lstrip("0") if s.startswith("0.") is False else s, []).append(eid)
        exact.setdefault(s, []).append(eid)
        vals.append((v, eid))
        if abs(v) <= 1.5:
            vals.append((v * 100, eid))
    rows, words = [], []
    for ln, raw in enumerate(open(TEX), 1):
        line = strip_tex(raw)
        for m in NUM.finditer(line):
            tok = m.group(0)
            tnum = tok.replace(",", "")
            if tnum.count(".") > 1:                       # version-like identifiers, e.g. 595.91.07
                cat, status, ids = "identifier", "n/a (version)", []
            else:
                after = line[m.end():m.end() + 12]
                cat = "quantity" if re.match(r"\s*(\\%|\\times|\\,\s*(ns|MB)|\\,|x)", after) or "." in tnum or len(tnum) > 3 else "small/other"
                ids = exact.get(tnum, [])
                status = "exact" if ids else None
                if not ids:
                    dec = len(tnum.split(".")[1]) if "." in tnum else 0
                    t = float(tnum)
                    hit = sorted({eid for v, eid in vals if abs(round(abs(v), dec) - t) < 1e-9})
                    ids, status = (hit, "rounded") if hit else ([], "not found")
            ctx = re.sub(r"\s+", " ", line[max(0, m.start() - 40):m.end() + 30]).strip()
            rows.append([ln, tok, cat, status, ";".join(ids[:3]), len(ids), ctx])
        for m in WORDS.finditer(line):
            words.append([ln, m.group(0), re.sub(r"\s+", " ", line[max(0, m.start() - 40):m.end() + 40]).strip()])
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["line", "token", "category", "status", "evidence_ids_first3", "n_matching_ids", "context"])
        w.writerows(rows)
    with open(OUT.replace(".csv", "_WORDS.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["line", "word", "context"])
        w.writerows(words)
    from collections import Counter
    c = Counter((r[2], r[3]) for r in rows)
    print(f"{len(rows)} numeric tokens ({len(words)} word numbers listed separately)")
    for k in sorted(c):
        print(f"  {k[0]:12s} {k[1]:14s} {c[k]}")
    nf = [r for r in rows if r[3] == "not found" and r[2] == "quantity"]
    print(f"quantities NOT found in {EV}: {len(nf)}")
    for r in nf:
        print(f"  line {r[0]}: {r[1]}   ...{r[6]}...")


if __name__ == "__main__":
    main()
