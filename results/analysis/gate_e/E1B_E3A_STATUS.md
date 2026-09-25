# Gate E1b + E3a — status

**COMPLETE — HARD STOP (2026-09-25): no stop condition.**
- **E1b:** the handoff location is confirmed by measurement (the pre-lock segment is 99.9–100% of the outside-lock increase), but the enqueue itself is only 10–31% of it. Most of the cost is per-fault prediction work.
- **E3a:** compiled cleanly (srcversion 91F634807244D31148A8597) and **NOT loaded**, awaiting review of `E3A_WIDTH_REVIEW.md`.
- The last 4 commits are unpushed (headless); run `git push`.

## Part A — Push and preflight
- Start 2026-09-25T22:33+03:00
- Push before isolating: `9ac42ab..22638b0 manuscript-prep -> manuscript-prep`, exit 0. After fetch, `git status -sb` is level with origin.
- HEAD `22638b0`; tracked tree clean. Untracked: `tests/group_probe` (probe binary, never tracked).
- tmux pane `%0` on `/dev/pts/0`, `DISPLAY` unset. Upgrade units: all inactive.
- Kernel `7.0.0-34-generic`; driver 595.91.07. Module file and loaded module srcversion **`5997D238EF080B77DBD2AAF`** (loaded in C0 config from E1's restore; refcnt 0). `git diff ea1a262 HEAD -- driver/` empty.
- dmesg since boot: no BUG/Oops/WARNING/GPF/NULL/irqs-disabled line.
- MemAvailable 56,096,504 kB (desktop up); `/` 40 GiB free.
- Outcome: **PASS**.
- Commit `f2e4591`; push exit 0.

## Part B — E1b
- Source check done (see `E1B_HANDOFF_COST.md` §1). `enqueue_overhead_ns` covers kzalloc, INIT_WORK, uvm_gpu_retain and queue_work, but **not** `specasync_ft_predict` (bsearch + global irqsave spinlock, run for every coalesced fault). Batch-ring `t1 − t0` brackets the whole pre-lock segment and is used as the complete measure.
- Order: 16 runs, seed 202609262, committed before the first run. Runner: `tests/e1b_runner.py`.
- Commit `82b15b9`; push exit 0.
- 2026-09-25T22:36:28+0300 isolated to multi-user.target.
- Tables (prefetch off): stencil 1,125,000 (trace 2,944,267, 0 overwrites); graphbfs 287,956 (trace 480,974, 0 overwrites). Assertions PASS. (Same informational daemon-reload warning at isolate.)
- Runs launched 2026-09-25T22:37:11+0300
- 16/16 runs, **no stop condition**, 0 new dmesg lines. Both rings at 100% coverage (≤ 74,896 records); every batch↔decomp pair aligned; ring sums equal the global counters.
- Result: the pre-lock segment = 99.9–100% of the outside-lock increase, so the location is **confirmed**. Enqueue overhead = only 12.7% (Stencil prefetch off) / 31.0% (on) / 9.8% (GraphBFS) of it, at 54–75 ns per prediction. The rest is prediction-side per-fault work (≈139–167 ns per demand fault), not attributed further. Flag: the E3a enqueue-skip premise is weakened.
- Doc: `E1B_HANDOFF_COST.md`; data `e1b/e1b_runs.csv`, `e1b/e1b_per_run.csv`, `e1b/e1b_summary.md`; script `tests/e1b_analyze.py`.
- Commit `d00c0a9` (local; headless, so the push is deferred to the close).
- 22:46 Part C: sources in driver/src-e3a/ (driver/src untouched). Building in a new work tree ~/specasync-work/nvidia-595.91.07-specasync-e3a.

## Part C — E3a (compile only)
- Sources are in `driver/src-e3a/`; the patch is `driver/patches/e3a_spec_width.patch` (342 lines). `driver/src/` is untouched.
- Built in a new tree with the verified build script. It first reproduced srcversion 5997D238EF080B77DBD2AAF from the unmodified sources, confirming the tree, before the overlay was applied.
- Final build: 0 warnings, 0 errors. `nvidia-uvm-specasync-NEW-e3a-width-UNREVIEWED.ko`, srcversion **91F634807244D31148A8597**, vermagic 7.0.0-34-generic. **Not loaded.** The verified module (5997D238…) remains loaded and unchanged.
- One safety tightening came from self-review: at W > 1, block liveness (`uvm_va_block_is_dead`) is re-checked under the block lock.
- Review packet: `E3A_WIDTH_REVIEW.md`. It contains the full diff, the function/precondition table, the pointer list, the W=1 identity argument, the risk assessment, the test plan, and the E1b flag (the enqueue skip can save at most the enqueue share).
- Commit `031aaae`; push **failed** (exit 128, headless; recorded, not worked around).
- Preflight note for the next session: `git diff ea1a262 HEAD -- driver/` is no longer empty, because `driver/src-e3a/` and `driver/patches/e3a_spec_width.patch` were added. The verified module's inputs (`driver/src`, `driver/scripts`, `driver/stock_backup`) are still identical to ea1a262. Use `-- driver/src` or the srcversion check.

## Close
- No stop condition occurred. The **verified** module was reloaded with speculation off and prefetch on (policy 0, depth 0, prefetch 1, log 0; srcversion 5997D238EF080B77DBD2AAF; no `specasync_spec_width` parameter present, so it is confirmed not to be the new module). graphical.target and gdm are active (same informational daemon-reload warning); `nvidia-smi` works; dmesg is clean.
- **HARD STOP.** The E3a module (91F634807244D31148A8597) has never been loaded and must not be until `E3A_WIDTH_REVIEW.md` is reviewed.
