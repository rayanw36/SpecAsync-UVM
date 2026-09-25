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
- Commit `b655a62`; push exit 0

## Step 2 — Pilot ceiling
- Start 2026-09-25T17:41 (pilot table collection); pilot runs 17:43–17:46; end 2026-09-25T17:49
- Tables: stencil 1,125,000 / graphbfs 287,956 asserted, trace overwrites 0.
- 10/10 pilot runs, no stop condition, 0 new dmesg lines, MemAvailable ≥ 60.9 GB. `ft_predictions = enqueued + drops` exact on all 5 C6 runs.
- Decomp ring: 23,534–75,199 records per run (< 131,071) → 100% coverage → ceiling computed (branch 2, prefix-based, scale 1.0).
- Ceiling (servicing window, C1 − C6-L4096): Stencil 0.198 s [0.170, 0.217], 216 ns per pre-staged fault; GraphBFS ≈ 0 [−0.0165, +0.0165].
- Disclosure: the pilot runner printed per-run wall-clock to stdout; no arm comparison was made. The runner now writes wall-clock to the CSV only.
- Addendum: `E09B_PREREG_ADDENDUM_PILOT.md`.
- Commit `46761ec`; push **failed** (exit 128, `could not read Username for 'https://github.com'` — no credential helper with the desktop isolated). Recorded, not worked around; later steps commit locally.

## Step 3 — Pre-registration
- Start 2026-09-25T17:52; end 2026-09-25T17:51:55+0300
- `E09B_PREREGISTRATION.md` written before any sweep run. Arms, 120-run order (seed 20260925, sha256 45241ae6…), statistics, falsification trigger, mechanism metrics, limitations, stop rules verbatim.
- Analysis code `tests/e09b_analyze.py` committed with it. It refuses to run until all 120 rows exist, and was smoke-tested on synthetic data only (scratchpad, not committed).
- Sweep timeouts: Stencil 22 s, GraphBFS 168 s (5× the pooled pilot maximum).
- Commit `a3942b9`; push exit 128 (failed, keyring/credentials unavailable headless; recorded, not worked around).
