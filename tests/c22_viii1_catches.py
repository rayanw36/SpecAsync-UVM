#!/usr/bin/env python3
"""C22 VIII-1 / I-4: catching mechanism, in-own-gate and pre-registered status for all 31 catalog entries. The classification below is read from ARTIFACT_CATALOG.md ('How caught' fields and the families table);
the script checks it against the catalog's families table columns and writes consolidation/C22_VIII1_CATCHES.md with the counts."""
import re
cat = open("results/analysis/ARTIFACT_CATALOG.md").read()
titles = {}
for l in cat.split("\n"):
    m = re.match(r"^\| (\d+) \| \*\*(.*?)\*\* \|", l)
    if m: titles[int(m.group(1))] = m.group(2)
    m = re.match(r"^### #(\d+) · (.*?)( \*\(.*)?$", l)
    if m: titles[int(m.group(1))] = m.group(2)
# n: (mechanism, in own gate, pre-registered check, note)   in-gate: Y / N / "Y (instance 3 only)" ; prereg: Y / N / "pre-defined, not pre-registered"
C = {
 1: ("later independent re-investigation (Gate B, serialized-vs-coalesced probe)", "N", "N", ""),
 2: ("the same Gate B investigation", "N", "N", ""),
 3: ("later interleaved re-run with a null-worker control (Gate C)", "N", "N", ""),
 4: ("later source inspection (Gate C)", "N", "N", ""),
 5: ("same-session accounting-closure gate G1 of Phase C (D1+D2+svc+D6+D7 within 2% of total)", "Y", "pre-defined in the Phase C plan, not a committed pre-registration", "caught before any number reached a report (catalog: 'the one artifact caught within the same session'); catalog column: original analysis"),
 6: ("later reproduction (Task T2, interleaved rerun)", "N", "N", ""),
 7: ("later passes (A1 open item, T4 correction note, 2026-08-13 correction pass)", "N", "N", ""),
 8: ("dedicated verification pass (Part 2)", "N", "N", ""),
 9: ("verification pass that tested a different hypothesis", "N", "N", ""),
 10: ("pre-registered test A2b (a follow-on gate to A2, before any dependent claim was published)", "Y", "Y", "A2 flagged the observation; A2b was pre-registered to test it; counted in-gate by the catalog (Section VIII)"),
 11: ("the failure itself: a near-OOM forced a stop and a characterization pass", "Y", "N", "caught in the session that suffered it"),
 12: ("independent verification pass mandated by the trigger policy", "N", "N", "the policy required a pass; no pre-registered check of this error existed"),
 13: ("independent source audit (Gate E0), 103 days later", "N", "N", ""),
 14: ("instances 1-2: independent later pass (E0.5); instance 3: the original analysis, in the same step (counters read with the question 'was the path exercised at all?')", "Y (instance 3 only)", "N", "instance 3 was a question asked of the data, not a committed check"),
 15: ("independent pass (E0.5)", "N", "N", ""),
 16: ("independent pass (E0.5), recomputing from the raw ring", "N", "N", ""),
 17: ("independent analysis-only pass (E0.8)", "N", "N", ""),
 18: ("next independent pass (E0.8), then external review", "N", "N", ""),
 19: ("independent source audit (E0)", "N", "N", ""),
 20: ("the original analysis: a second, redundant counter (`fault_already_resident`) kept rising while `spec_hits` fell, in the same table (E0.9a-2)", "Y", "N", "redundant measurement, not a pre-written check"),
 21: ("first E1b (forced by a reviewer's challenge to E1), then E3b (pre-registered test, expectation committed before the run)", "N", "Y (the E3b catch; a later gate than the one that made the error)", "the first catch (E1b) was not pre-registered and not in-gate"),
 22: ("a kernel oops (crash), user present", "Y", "N", ""),
 23: ("operational preflight at the next session (a module refused to load)", "N", "N", "platform drift between sessions, caught by the failure itself"),
 24: ("the original harness run: the rejection test failed loudly", "Y", "N", ""),
 25: ("pre-registered prediction test (E0.9b addendum, committed before the sweep)", "Y", "Y", "the only aggregation-level entry caught in-gate"),
 26: ("read-only journal re-account (E6) and the E8 review", "N", "N", ""),
 27: ("the author of a later gate (E7) reading the helper", "N", "N", ""),
 28: ("the failing compile, then reading the script output", "Y", "N", ""),
 29: ("the failure itself; recorded as amendments before any timed run", "Y", "N", ""),
 30: ("pre-registered smoke pass (an OOM kill) of the same gate", "Y", "Y", ""),
 31: ("inspection of the managed t51 cell against the density rule after the gate, confirmed against E9", "N", "N", "the gate's own scoring did not catch it"),
}
# checks against the catalog's families table columns
tab = cat.split("| family | entries")[1].split("\n\n")[0].split("\n")[2:]
col = {k: set() for k in ("orig", "later", "prereg", "fail")}
for l in tab:
    if l.startswith("|"):
        c = l.split("|")
        for k, i in (("orig", 3), ("later", 4), ("prereg", 5), ("fail", 6)):
            col[k] |= {int(x) for x in re.findall(r"#(\d+)", c[i])}
assert {n for n, v in C.items() if v[2].startswith("Y")} == col["prereg"] == {10, 21, 25, 30}, (col["prereg"])
assert {n for n, v in C.items() if v[1].startswith("Y")} >= col["orig"] | {10, 25, 30}, "in-gate set misses an 'original analysis' entry"
ing = [n for n, v in C.items() if v[1] == "Y"]; part = [n for n, v in C.items() if v[1].startswith("Y (")]
pre = [n for n, v in C.items() if v[2].startswith("Y")]
both = [n for n in pre if C[n][1] == "Y"]
o = ["# C22 VIII-1 / I-4: where each catalog entry was caught (all 31)", "",
     "Script `tests/c22_viii1_catches.py`; source `ARTIFACT_CATALOG.md` ('How caught' of each entry; the families table columns), checked by assertion: the entries the table lists under 'caught by a pre-registered test' are exactly #10, #21, #25, #30; every 'original analysis' entry (#5, #14, #20) is classified in-gate. The supplement S3 reproduces the same entries unchanged.", "",
     "Definitions used. **Inside its own gate:** the catch happened in the gate or session that produced the error, by that gate's own analysis, checks, pre-registered test, harness or by the failure itself; later independent passes, reviews and later gates are outside. **Pre-registered check:** a test or smoke pass whose expectation or rule was committed before the measurement it judged.", "",
     "| # | entry | catching mechanism | inside its own gate? | check written before the measurement? | note |", "|---|---|---|---|---|---|"]
for n in range(1, 32):
    m, g, p, note = C[n]
    o.append(f"| {n} | {titles.get(n, '?')} | {m} | {g} | {p} | {note} |")
o += ["", "## Counts", "",
      f"- **Caught inside its own gate (any mechanism): {len(ing) + len(part)} of 31** - {', '.join('#' + str(n) for n in sorted(ing))} outright, and #14 for instance 3 only (instances 1-2 were caught by a later pass). By mechanism: original analysis {sorted(col['orig'])} (#5, #14 instance 3, #20); pre-registered tests or smoke passes #10, #25, #30; the failure itself (crash, loud harness, forced stop, failed compile, session end) #11, #22, #24, #28, #29.",
      f"- **Caught by a pre-registered check: {len(pre)} of 31** - {', '.join('#' + str(n) for n in pre)} (the catalog table column). Of these, **inside the gate that made the error: {len(both)}** ({', '.join('#' + str(n) for n in both)}); #21's pre-registered catch (E3b) came in a later gate, after a first, review-forced catch (E1b), so it is not an in-gate catch under the definition above.",
      "- Caught only by a later independent pass, review or later gate: " + ", ".join('#' + str(n) for n in range(1, 32) if C[n][1] == "N") + f" ({sum(1 for n in C if C[n][1] == 'N')} entries; #23 is caught by the next session's preflight).",
      "- Aggregation-level family (9 entries): 8 caught by a later pass or review, 1 (#25) in its own gate by a pre-registered test (unchanged from C14).", "",
      "## What this means for the two statements", "",
      "1. **\"caught inside its own gate\"** (Section VIII: \"four errors were caught inside their own gate, and all four by a check written before the measurement\"; Section I similar). By the definition above 11 entries (10 plus #14's third instance) were caught inside their own gate, of which only 3 (#10, #25, #30) by a pre-registered check; the four-entry set {#10, #21, #25, #30} is the set caught by a pre-registered check, and #21's catch came in a later gate. The sentence is accurate if read as \"four were caught by a check written before the measurement\" (with #21's caught in the following gate E3b) and understates the in-gate catches if read literally.",
      "2. **\"caught by a pre-registered check\"**: 4 of 31 (#10, #21, #25, #30), matching the catalog's families table. #5 (Phase C's accounting-closure gate G1) was a check defined in the phase plan before the run but not a committed pre-registration (the pre-registration regime starts with E0.9b), #14 instance 3 and #20 were caught by the original analysis without a pre-written check.",
      "", "Suggested wording for the author (not applied): \"Eleven of the 31 errors were caught inside the gate that made them (by its own analysis, by a crash or loud harness failure, or by a pre-registered test); four were caught by a check written before the measurement.\"", ""]
open("results/analysis/consolidation/C22_VIII1_CATCHES.md", "w").write("\n".join(o))
print(len(ing), len(part), len(pre), both)
