# Gate E3a-2 — status

## Part A — Push and preflight
- Start 2026-09-25T23:00+03:00
- Push first: `82b15b9..bb74711 manuscript-prep -> manuscript-prep`, exit 0; after fetch, level with origin.
- HEAD `bb74711`; tracked tree clean (untracked `tests/group_probe`, as always).
- tmux `%0` on `/dev/pts/0`, `DISPLAY` unset; upgrade units all inactive.
- Kernel 7.0.0-34-generic; driver 595.91.07. Verified module file and loaded module srcversion `5997D238EF080B77DBD2AAF`. `git diff ea1a262 HEAD -- driver/src` is empty.
- dmesg clean (no BUG/Oops/WARNING/GPF/NULL/irqs-disabled). MemAvailable 55,505,616 kB; `/` 40 GiB free.
- **No module load in this gate**, so the desktop is not isolated; graphical.target stays active throughout.
- Outcome: **PASS**.
- 23:05 B1 verified (no restructure). B2: K1/K8 = 0.667 at Stencil W=64 (< 0.8), so replaced with an 8-slot round-robin history. Part C fast oracle written. Building.

## Parts B–D
- **B1:** `continue` targets the `_fi` loop; nothing follows the enqueue. Correct, no restructure needed. The new B2 inner `_k` loop uses a `_seen` flag so that `continue` still targets `_fi`.
- **B2:** K1/K8 = 0.898 (Stencil W16), **0.667 (Stencil W64)**, 0.975 (GraphBFS W16/W64). The E1 tables give the same result. The rule fails, so the single region was **replaced with an 8-slot round-robin history** (masked index, guarded by W > 1).
- **B3:** double-count stated. The identities count each item once: lost = enqueued − spec_migrations; other_lost = lost − spec_region_invalid. Never add work-ring THROTTLED to spec_region_invalid.
- **C:** `specasync_ft_fast` (0444, 0|1, setter-validated). Range index: Stencil **2 ranges / 4.50 MB**, GraphBFS **19 ranges / 1.15 MB**. Lock-free cursor via a bounded `atomic_try_cmpxchg` on the existing `atomic_t`. Two deviations flagged: 32-bit rather than atomic64, and a 64-try bound with a give-up counter. Mandatory load-time equivalence check (every page plus boundary probes); on failure the fast path is disabled and `specasync_ft_fast_verified` = 0.
- **Self-check (no load):** the actual C functions, extracted from source and compiled in userspace, replayed the recorded traces (Stencil 2,944,267 faults; GraphBFS 480,974). Slow and fast are **identical** on every counter and the full prediction stream at L = 1/16/256/4096. 0 give-ups. The disable path works. Script: `tests/e3a2_userspace_check.sh`.
- **D:** no new UVM calls. The unchanged `driver/src` re-confirmed srcversion **5997D238EF080B77DBD2AAF**. E3a-2 build: 0 warnings/errors, srcversion **33FD42E6E16B0A6658E2BEB**, vermagic 7.0.0-34-generic, saved as `nvidia-uvm-specasync-NEW-e3a2-width-ftfast-UNREVIEWED.ko`. **Not loaded.** The verified module is still loaded.
- Patches: `driver/patches/e3a_spec_width.patch` (regenerated, cumulative, 793 lines) and the new `driver/patches/e3a2_region_history_ft_fast.delta.patch` (this session's delta, 580 lines).
- Review packet: `E3A2_REVIEW.md`.
