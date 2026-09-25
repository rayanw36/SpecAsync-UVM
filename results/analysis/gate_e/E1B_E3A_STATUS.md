# Gate E1b + E3a — status

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
