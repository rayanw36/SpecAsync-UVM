#!/usr/bin/env python3
"""Gate C1-APPLY (prefix list extended in Gate C4 to E6-E9, T4, D6; files that do not exist yet are skipped): every evidence id cited (in backticks) in the applied files must
resolve to a row of results/analysis/consolidation/EVIDENCE_EXTRACT.md. Prints the
resolved count and every unresolved id with its file:line. Prefix list = the id
families the extractor emits."""
import re, sys
EXTRACT = "results/analysis/consolidation/EVIDENCE_EXTRACT.md"
FILES = ["results/analysis/CLAIM_SCOPE.md", "results/analysis/ARTIFACT_CATALOG.md"] + [
    f"results/analysis/consolidation/{f}" for f in (
        "CLAIM_SCOPE_v2_PROPOSED.md", "ARTIFACT_CATALOG_ADDITIONS_PROPOSED.md", "HITRATE_REREAD.md",
        "SUPERSEDED_VALUES.md", "OPEN_DECISIONS.md", "FLAG_LEDGER.md", "C1_REVIEW.md",
        "REVIEW_NOTES_E7_E9.md", "CPU_FAULT_CHECK.md")]
PREFIX = r"(?:E09b|E1PartB|E1b|E1|E3b|E4|E5|E6|E7|E8|E9|T4|D6|claim\d+|T1B5|T4hit|A1|B9|B10)"
ids = set(re.findall(r"^\| `([^`]+)` \|", open(EXTRACT).read(), re.M))
tok = re.compile(r"`(" + PREFIX + r"\.[A-Za-z0-9_.()\-+]+)`")
ok = bad = 0
for f in FILES:
    if not __import__('os').path.exists(f):
        continue
    for n, line in enumerate(open(f), 1):
        for m in tok.finditer(line):
            cid = m.group(1).rstrip(".")
            if cid in ids: ok += 1
            else:
                bad += 1; print(f"UNRESOLVED {f}:{n}: `{cid}`")
print(f"resolved {ok}; unresolved {bad}; extract rows {len(ids)}")
