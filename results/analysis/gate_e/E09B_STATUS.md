# Gate E0.9b — unattended session status

## Step 0 — Preflight
- Start: 2026-09-25T17:38:11+03:00
- HEAD: `5bda4d2` (`manuscript-prep...origin/manuscript-prep [ahead 1]` — 5bda4d2 not yet pushed from the previous session)
- Tracked tree clean (`git diff` empty). One untracked file: `tests/group_probe` (compiled probe binary, never tracked — not a modification).
- Session under tmux: `TMUX=/tmp/tmux-1000/default,4571,0`, `DISPLAY` unset, pty `pts/0 (tmux(4571).%0)`.
- `unattended-upgrades`, `apt-daily.timer`, `apt-daily-upgrade.timer`: all **inactive**.
- Kernel `7.0.0-34-generic`; driver `595.91.07`.
- Module under test: `driver/build/595.91.07/nvidia-uvm-specasync-NEW-e0.9a2-fixed.ko`, srcversion **`5997D238EF080B77DBD2AAF`**, vermagic `7.0.0-34-generic`. Built from `ea1a262` source; `git diff ea1a262 HEAD -- driver/` is empty, so HEAD's driver source is identical to the verified build.
- Currently loaded: stock DKMS `nvidia_uvm` (srcversion `6284DA42F15EDC3AB92332B`).
- `dmesg` since boot: no `nvidia_uvm` BUG/Oops/WARNING/GPF/NULL/irqs-disabled lines.
- `MemAvailable` 56,695,104 kB; `/` free 41 GiB (98 G total).
- Outcome: **PASS**.
- End: 2026-09-25T17:39 — commit `0919c58`; push **succeeded** (`ea1a262..0919c58`, which also carried the previously-unpushed `5bda4d2`).

## Step 1 — Source checks
- Start 2026-09-25T17:40; end 2026-09-25T17:40:38+03:00
- Q1: `ft_predictions = enqueued + drops` exactly (drop counter `specasync_drops`: queue-full at 1,024 or kzalloc failure). Already-resident items ARE counted in `spec_migrations` (no-op `make_resident` returns NV_OK) — so pre-staged coverage is an upper bound.
- Q2: prefetched pages are migrated AND mapped in the same `service_finish` call — the prefetcher can prevent faults; speculation cannot.
- Q3: no aggregate servicing-time timer exists. Only drop-on-full rings (131,072 slots). Decomp ring coverage is 100% iff a run records < 131,071 entries — Step 2 measures it.
- Outcome: answered from source, no code changes.
