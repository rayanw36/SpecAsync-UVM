# Gate C1 — Consolidate the claims before writing — status

**COMPLETE — HARD STOP (2026-09-26).** Seven proposal files are written; nothing is applied. See `C1_REVIEW.md`.

Documentation only: no module loads, no runs, no desktop isolation. **No canonical file is edited.** Everything here is a proposal for review.

## Step 0 — Push and preflight
- 2026-09-26T11:31+03:00. Push `9834517..c266e74 manuscript-prep -> manuscript-prep`, exit 0; after fetch, level with origin.
- **HEAD at start: `c266e740942099e6c4ec2ced443f467738dee62b`.**
- Tracked tree clean (untracked `tests/group_probe`, as always).

## Step 1 — Flag ledger (in progress)
- Read all Gate E reports and status files: E0, E0.5, E0.7, E0.8, E0.9, E0.9a-2, E0.9b, E1, E1 Part B, E1b, E3a/E3a-2 reviews, E3b, E3b oracle cost, E4, E5, E5 mechanism. Also read `CLAIM_SCOPE.md`, `ARTIFACT_CATALOG.md`, `OVERSUB_C3_VERIFICATION.md`, `driver/PIPELINE_FIXES.md`, `GATE_A_report.md`, and the three hit-rate reports.
- Evidence rule implemented as a script. `tests/c1_evidence.py` extracts every cited number from **committed derived files only** into `EVIDENCE_EXTRACT.md`: 148 values, each with its file and field. Every value checked against its report's prose matched (for example T1 C3 vs C0 +278.49% against the prose +278.5%; B5 +302.25% against +302.3%; claim 16 +0.331%).
- Numbers from E0.5–E0.9a-2 have **no committed derived file**: their raw data is gitignored and only the scripts are committed. They are marked PROSE-ONLY wherever cited.
- FLAG_LEDGER.md: 74 rows: 69 flags from Gate E and earlier reports, 3 surfaced by C1's source checks (70–72), 2 unflagged Gate E metric statements (73–74); 8 flags marked 'do not apply as written'.
- ARTIFACT_CATALOG_ADDITIONS_PROPOSED.md: entries #12–#25 (14 new), 2 amendments (#1 root cause; rejected-hypothesis row), 4 families + synthesis. Existing entries' 'how caught' cells were re-read and classified from source (#5 original / closure check, #10 pre-registered, #11 loud failure).
- CLAIM_SCOPE_v2_PROPOSED.md: 27 blocks (17 existing, 8 new, 2 retired). stands 9, narrowed 5, superseded 2, retired 3, new 8. Every number has an evidence id, or is marked PROSE-ONLY or UNCHECKED.

## Step 4 — HITRATE_REREAD.md
- 10 mechanistic claims re-read (GATE_T4 ×4, GATE_A1 ×4, B6 Task 2 ×2). The dispatch-race explanation is retired; the backlog exclusion and the latency measurements stand. None of the three reports has an arm-versus-arm wall-clock result; T1's C3 wall-clock stands as a configuration measurement.

## Step 5 — SUPERSEDED_VALUES.md
- 41 file:line entries across `paper/`, `CLAIM_SCOPE.md`, `ARTIFACT_CATALOG.md` and the earlier reports; each marked as a superseded value (v) or interpretation (i).
- "any such scheme" was not found in the repository; it exists only in the chat-session Section I draft, for which a 7-item change list is given.

## Step 6 — OPEN_DECISIONS.md
- D1 (practical block predictor), D2 (T4 scope), D3 (GraphBFS oracle), D4 (5 unresolved claims), D5 (averted hazards), D6 (evidence gaps for PROSE-ONLY numbers).

## Step 7 — Review packet
- `C1_REVIEW.md`: a one-page summary, counts, every PROSE-ONLY and UNCHECKED number, and file pointers.
- Commit `db708d4`; push exit 0; level with origin.
- Confirmed unedited: `CLAIM_SCOPE.md`, `ARTIFACT_CATALOG.md`, `PREREGISTRATION.md`, `COMPLETENESS_LEDGER.md`, `paper/`, and all reports (`git diff c266e74 HEAD --stat` touches only `results/analysis/consolidation/` and `tests/c1_evidence.py`).
- **HARD STOP.** Proposals are applied only after review.
