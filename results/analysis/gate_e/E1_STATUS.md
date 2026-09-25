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
- Commit `53f147e`; push exit 0.

## Part B — Ceiling reconciliation (analysis only)
- Start 2026-09-25T21:17; end 2026-09-25T21:18+0300
- **Verdict: Scope mismatch.**
  - Pre-staging cut D5 (dispatch under the VA-space lock) by 0.681 s on Stencil. D1+D2 changed by +0.003 s.
  - The net 0.198 s window reduction is D5's saving minus +0.477 s of speculation enqueue work, which runs in `service_fault_batch()` outside the lock.
  - The pipelining ceiling bounds D1+D2 hiding only. It is measured prefetch-on, with no Stencil-24K point on the 5070 Ti (Sweep-24K 7.25% at 595.84 is the nearest).
  - Not compared with 5.65%: different baseline, different phases, different instrument.
  - The "any such scheme" wording was not found in the manuscript files. The overreach is CLAIM_SCOPE claim 15's "structural upper limit on what's even offloadable" (flagged, not edited).
- Doc: `E1_PARTB_CEILING_RECONCILIATION.md`.
- Commit `61980f1`; push exit 0.

## Part C — Pre-registration
- `E1_PREREGISTRATION.md` written before any E1 run. It fixes arms C0/C7-L, prefetch-off tables, the 100-run order (seed 202609261, sha256 d17cd7de…), 8 comparisons, the trigger, metrics, limitations and verbatim stop conditions.
- Code: `tests/e1_runner.py` (a wrapper over the E0.9b runner, logic unchanged), `tests/e1_make_order.py`, `tests/e1_analyze.py` (smoke-tested on synthetic data in the scratchpad only).
- Timeouts: Stencil 22 s, GraphBFS 168 s (the floors; 5× the E0.9b C0 median is lower).
- Risk noted: this is the first-ever run of policy 6 with prefetch on. It is a new parameter combination, not new code.
- Commit `9ac42ab`; push exit 0.

## Part C — Tables and sweep
- 2026-09-25T21:20:38+0300 isolated to multi-user.target.
- systemctl printed "The unit file ... of multi-user.target changed on disk. Run 'systemctl daemon-reload'". Informational, not a stop condition. daemon-reload was not run (outside the allowed commands). Isolate exit 0; gdm and graphical.target inactive; MemAvailable 61,336,648 kB.
- Tables (prefetch off): stencil 1,125,000 (trace 2,948,005, overwrites 0); graphbfs 287,956 (trace 481,067, overwrites 0). Assertions **PASS**.
- Sweep launched 2026-09-25T21:21:24+0300
- Sweep end 2026-09-25T18:51:02Z. **100/100 runs, no stop condition**, no interruption, no re-run. Commits every 10 runs: `635c463` … `9813a9f`.
- srcversion constant; exit codes all 0; MemAvailable ≥ 60.8 GB; disk ≥ 39.8 GB. dmesg: 1 line on run 92 (`drm_fb_helper_damage_work hogged CPU`, framebuffer console, not nvidia); nothing else. Identity held on 80/80.

## Part C — Analysis
- `tests/e1_analyze.py` run unchanged from `9ac42ab`.
- Falsification trigger **not fired**. Stencil: every C7-L is Holm-significantly slower than C0 (+3.9% to +8.4%). GraphBFS: no significant difference at any L (MDE ≈ 0.5%).
- C0 `fault_already_resident` = 0 in all 20 C0 runs, so the counter is attributable to speculation.

## Close
- `GATE_E1_REPORT.md` written.
