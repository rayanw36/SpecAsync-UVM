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



# Intended evidence ids (added in Gate C4 follow-up): the generic matcher above can match a number to an unrelated id, so the numbers that matter are
# mapped by hand to the id they are meant to cite and CHECKED numerically against that id's own value text. Key: (token, context substring).
INTENDED = {
    ("99.95", "staging 99.95"): ["E5.mech.t100.C7W512"], ("2.92", "configuration remained"): ["E4.F4.stencil.C6-W512_vs_C0"],
    ("21", "worth 21"): ["E5.wall.t100"], ("23", "21--23"): ["E4.F3.stencil.C6-W512_vs_C1"],
    ("3.4", "3.4--5.3"): ["E6.F1.C7W512-t51_vs_C0-t51"], ("5.3", "3.4--5.3"): ["E5.wall.t51"],
    ("40", "about 40"): ["E5.D(51)"], ("40", "grows from 40"): ["E5.D(51)"], ("53", "to 53"): ["E5.D(75)"],
    ("9.57", "9.57"): ["E7.A.stencil.stock-t0_vs_stock-t51"], ("6.4", "6.4"): ["E6.F1.C7W512-t51_vs_C0-t0"], ("2.8", "at most 2.8"): ["E6.wall.C7W512-t25_vs_C0-t25"],
    ("1.8", "effects 1.8"): ["E6.wall.C7W512-t0_vs_C0-t0"], ("2.0", "and 2.0"): ["E6.wall.C7W512-t10_vs_C0-t10"],
    ("2.5", "2.5--17"): ["E7.B.sgemm.stock-t0_vs_stock-t51"], ("17", "2.5--17"): ["E7.B.oversub.stock-t0_vs_stock-t51"],
    ("41", "41--85"): ["E8.range.ov_sparse_t0"], ("85", "41--85"): ["E8.range.ov_sparse_t0"],
    ("130", "130"): ["E9.cell.ov_k1.t0"], ("4", "against 4"): ["E9.cell.ov_k1.t51"],
    ("5.1", "-5.1"): ["T4.A.stencil.stock-t0_vs_stock-t51"], ("12", "12 of 14"): ["T4.B.count"], ("14", "12 of 14"): ["T4.B.count"],
}


def ev_text():
    return {l.split("`")[1]: l.split("|")[2] for l in open(EV) if l.startswith("| `")}


def intended_check(tok, ctx, ids, text):
    """OK if some number in an intended id's value text equals the token at the token's own precision (also x100 for fractions, and 1 + pct/100 for a ratio;
    1.8 / 2.0 are the MDE as a percentage of the baseline median: mde_s / median_base)."""
    dec = len(tok.split(".")[1]) if "." in tok else 0
    t = float(tok)
    for i in ids:
        v = text.get(i)
        if v is None:
            return f"FAIL: id {i} not in the extract"
        nums = [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*(?:\.\d+)?", v)]
        cand = [abs(n) for n in nums] + [abs(n) * 100 for n in nums if abs(n) <= 1.5] + [1 + n / 100 for n in nums]
        m = re.search(r"median_base=([0-9.]+)", v)
        e = re.search(r"mde_s=([0-9.]+)", v)
        if m and e:
            cand.append(100 * float(e.group(1)) / float(m.group(1)))
        for c in cand:
            if round(c, dec) == t:
                return f"OK ({i}: {round(c, max(dec, 2))})"
    return "FAIL: no number in the intended id rounds to the token"


def main():
    ev = ev_numbers()
    evt = ev_text()
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
            ic = next(((k, v) for k, v in INTENDED.items() if k[0] == tok and k[1] in line), None)
            if ic is None and tok == "9.57":
                ic = (("9.57", ""), INTENDED[("9.57", "9.57")])
            iid = ";".join(ic[1]) if ic else ""
            ichk = intended_check(tok, ctx, ic[1], evt) if ic else ""
            rows.append([ln, tok, cat, status, ";".join(ids[:3]), len(ids), ctx, iid, ichk])
        for m in WORDS.finditer(line):
            words.append([ln, m.group(0), re.sub(r"\s+", " ", line[max(0, m.start() - 40):m.end() + 40]).strip()])
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["line", "token", "category", "status", "evidence_ids_first3", "n_matching_ids", "context", "intended_id", "intended_check"])
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
    ok = sum(1 for r in rows if r[8].startswith("OK")); bad = [r for r in rows if r[8].startswith("FAIL")]
    print(f"intended-id check: {ok} OK, {len(bad)} FAIL" + "".join(f"\n  FAIL line {r[0]} {r[1]}: {r[8]}" for r in bad))
    nf = [r for r in rows if r[3] == "not found" and r[2] == "quantity"]
    print(f"quantities NOT found in {EV}: {len(nf)}")
    for r in nf:
        print(f"  line {r[0]}: {r[1]}   ...{r[6]}...")


if __name__ == "__main__":
    main()
