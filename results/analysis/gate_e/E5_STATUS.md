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
