# Gate E5 — status

## Step 0 — Push and preflight
- Start 2026-09-26T10:53+03:00. Push: already level with origin ("Everything up-to-date", `5717bfb`).
- Tracked clean (untracked `tests/group_probe`). tmux `%0` on `/dev/pts/0`, `DISPLAY` unset. Upgrade units inactive. Kernel 7.0.0-34-generic; driver 595.91.07. `git diff ea1a262 HEAD -- driver/src` empty. dmesg clean for the extended pattern. MemAvailable 57,700,596 kB; 38 GiB free.
- Module files: verified `5997D238EF080B77DBD2AAF` (sha256 `ab91372b…31be`, loaded, refcnt 0); new `33FD42E6E16B0A6658E2BEB` (sha256 `dc6b226e…45df`).
- Outcome: **PASS**.

## Step 1 — Source check (read-only)
- `E5_MECHANISM.md`:
  1. The density bitmap is `resident_mask | faulted_pages` (`uvm_perf_prefetch.c:227`), using the destination's resident mask (`:397`). **Speculatively resident pages count.**
  2. Already-resident prefetched pages are mapped in the same service step (`uvm_va_block.c:11532`, `:11961`, `:11981`).
  3. The comparison is a strict `counter*100 > pages*threshold` (`:118`); the range is 0–100 (above 100 falls back to 51 silently); settable at insmod with 0444 read-back. **T_off = 100** can never fire.
  4. At T_off, for Stencil, nothing else writes prefetch pages: big-page growth only feeds the count; first-touch population needs a preferred location, which Stencil doesn't set. PTE merging is named as the residual candidate.
- **H-feed is not refuted from source**, so the hypothesis test proceeds.
- Commit `48e7a78`; push exit 0.

## Step 2 — Pre-registration
- `E5_PREREGISTRATION.md` committed before any run. It fixes 6 arms × n = 10 = 60 runs (Stencil only); the order (seed 202609265, sha256 25450fae…); T_off = 100; the D(t) verdict rule including the D(51) ≤ 0 edge case; the 3-comparison wall-clock family; mechanism metrics; limitations; stop conditions.
- Code: `tests/e5_runner.py` (the E4 runner plus the threshold parameter and read-back), `tests/e5_make_order.py`, `tests/e5_analyze.py`. The analysis refuses fewer than 60 rows and was smoke-tested on synthetic data in the scratchpad only.
- Commit `9834517`; push exit 0.

## Step 3 — Runs
- Isolated to multi-user.target (exit 0). Table: stencil 1,125,000 (trace 2,948,110, 0 overwrites) — PASS (graphbfs table built by the collector, unused).
- Sweep launched 2026-09-26T10:58:02+0300.
- Sweep complete: 60/60 rows in sequence, no stop condition, 39c1dbe.

## Step 4 — Analysis and report
- `tests/e5_analyze.py` run unchanged from `9834517`. Integrity is clean: 60/60 in order, one srcversion, 0 dmesg lines, 100% ring coverage, identities 30/30, fast verified 30/30, threshold read back on every run.
- **H-feed: SUPPORTED.** D(51) = +0.401 (Holm-sig), D(75) = +0.534 (dose-response held), D(T_off) = −0.022; ratio −0.054 < 0.25.
- **The secondary wall-clock prediction failed:** C7W512 is faster at every threshold (−5.3 / −10.1 / −21.0%). At T_off the gain tracks D5 (copy offload), not fault prevention. Reported plainly.
- E4's trigger result replicates at t51 (−5.26%, Holm-sig).
- Report: `GATE_E5_REPORT.md`.
