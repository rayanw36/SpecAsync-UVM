# Gate E7 / C2-APPLY status log

Phase 0 start: 2026-10-07 13:51:00 +03 (file `e7/phase0_start.txt`). Session cap 3 h = 16:51:00.

## Open for review
- Remote is HTTPS, not SSH; no SSH private key on this host. Push works through `gh` used as a one-off
  credential helper (`git -c credential.helper='!gh auth git-credential' push`); git config unchanged.
- **CS2-N1 item 5 MDE:** the brief's text said "MDE about 2.3%". The E6 within-threshold MDEs are 0.0181 s (t0) and 0.0205 s (t10), i.e. 1.8% and 2.0% of the C0 medians; 2.3% is the cross-threshold Family 1 MDE. Wrote 1.8% / 2.0% (evidence over wording).
- **CS2-N1 item 6:** E6 GraphBFS MDE is 0.41-0.49% of the C0-t51 median, added next to E4's 0.28-0.43%.
- **E6_REVIEW_NOTES:** the brief's "C7W512-t51 1.0738 -> E5 -> 1.0918" skips E5's actual median 1.0673; the table gives all three (1.0738, 1.0673, 1.0918).
- **CS2-5** ("only whole-block speculation saves time" relative to the shipped C0) was not in the brief's edit list and is still literally true at threshold 51; left unedited, flagged here for review.

## Log
- 13:51 Phase 0 start. 16 unpushed commits pushed (8123093). PLATFORM_5070TI.md committed and pushed (cfdf7a1).
- 13:58 Preflight: HEAD cfdf7a1; tree clean (untracked tests/group_probe, e7/); kernel 7.0.0-34; driver 595.91.07; srcversions stock 6284DA42.., verified 5997D238.., e3a2 33FD42E6..; timers inactive; MemAvailable 56 GB; 37 GB free; driver/src identical to ea1a262. System is in graphical.target (restored at user request); isolate happens in Phase 4.
- 14:20 Phase 1 DONE (commit): c1_evidence.py extended (+27 E6 rows, 191 total; 194 cited ids resolved, 0 unresolved); CLAIM_SCOPE edits 1-5 applied (N1 replaced, N3/N4 additions, new CS2-N10, limitation replaced); OPEN_DECISIONS D1 note; E6_REVIEW_NOTES.md.
