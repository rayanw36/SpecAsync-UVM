# Gate E1 — status

## Part A — Push and preflight
- Start 2026-09-25T21:14+03:00
- Push **before** isolating the desktop: `b655a62..a6d3f93 manuscript-prep -> manuscript-prep`, exit 0. After `git fetch`, `git status -sb` shows `## manuscript-prep...origin/manuscript-prep` (level).
- HEAD `a6d3f93`; tracked tree clean. Untracked: `tests/group_probe` (probe binary, never tracked, as in E0.9b).
- tmux: `TMUX=/tmp/tmux-1000/default,4571,0`, `DISPLAY` unset; claude runs in pane `%0` on `/dev/pts/0` (non-X pty).
- `unattended-upgrades`, `apt-daily.timer`, `apt-daily-upgrade.timer`: all **inactive**.
- Kernel `7.0.0-34-generic`; driver `595.91.07`.
- Module file `nvidia-uvm-specasync-NEW-e0.9a2-fixed.ko` srcversion **`5997D238EF080B77DBD2AAF`**; the loaded module has the same srcversion (left in C0 config by E0.9b: policy 0, prefetch 1, refcnt 0). `git diff ea1a262 HEAD -- driver/` is empty.
- dmesg since boot: no BUG/Oops/WARNING/general protection/NULL pointer/irqs-disabled line from any source.
- MemAvailable 57,636,188 kB (desktop still up); `/` 40 GiB free of 98 G.
- Outcome: **PASS**.
