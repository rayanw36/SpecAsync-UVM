# Gate T4-R1 session summary (final)

**Outcome: E7-T4 completed. Verdict REPLICATED; falsification trigger NOT fired; XA, XB, XC all HELD.** Report: `GATE_E7T4_REPORT.md` (figure `e7t4_threshold_by_workload.{png,pdf}`).

| result | |
|---|---|
| Family A (Stencil-24K) | stock-t0 vs t51 -5.07% (p 1.08e-05, Holm-significant); t10 -3.21% (significant). 5070 Ti: -9.57% / -7.13% (separate data) |
| Family B (7 workloads, 14 tests, one Holm family) | all deltas negative; 12 significant speedups, 2 n.s. (Stencil-8K t25, Sweep-4K t25); **no significant slowdown** |
| Data integrity | 240/240 rows, exit 0, threshold read-back matches on every row, srcversion 6284DA42F15EDC3AB92332B on every row, 0 new dmesg lines, no STOP |
| Cross-version (descriptive) | Stencil-24K t51 median 5.808 s vs old T4 595.71.05 C0 4.185 s (+38.8%); not tested |

## What happened, in order
1. T0-T4 (first session): instance verified; driver 595.91.07 installed from the archive pool after you approved (SHA256 matched Launchpad); CUDA 13.0.88 / gcc 13.3.0; benchmarks built; verified and E3a-2 modules compiled only (srcversions identical to the 5070 Ti's: 5997D238..., 33FD42E6...); E7-T4 pre-registered; positive control PASS.
2. Smoke ran 24/27 rows, then the instance was powered off at 17:59 UTC on 8 Oct (cause not checked); the session resumed after the cap. **Amendment 1** (new cap).
3. Smoke row 25, the oversubscribed Stencil (17.17 GiB managed), was OOM-killed on the 15.4 GiB / no-swap host. My pre-registration had checked VRAM but not host RAM. **Amendment 2:** oversub removed from Family B (7 workloads, 14 tests), memory stop condition added (managed allocation < MemAvailable - 4 GiB; never fired), new 4 h cap.
4. **My mistake:** I ran `loginctl terminate-session` on the xrdp session that contained my own Claude session, which ended that session. It was not repeated and is forbidden by the brief; the replacement session runs under tmux in the user manager.
5. Sweep ran as one detached `systemd-run --user --unit=e7t4-sweep` chain (own cgroup, parent `systemd --user`, linger on), 12:03-12:55 UTC, 240 rows, no skips, pushed after each workload.

## Caveats you should carry into the paper
* Oversubscription on the T4 is **not** covered (deferred to a separate gate on a larger-RAM host); Family B differs from the 5070 Ti E7 (7 vs 8 workloads, 14 vs 16 tests).
* GraphBFS-23 is Holm-significant but -0.14% (0.07 s of 54 s), below MDE: treat as no effect. SGEMM's MDE is inflated by a +20% t51 outlier; direction/significance agree with and without outliers.
* The stock srcversion on the T4 equals the 5070 Ti's; the E3a-2 and verified-module srcversions also match. srcversion is a source hash and does not imply identical binaries.
* The verified/E3a-2 modules were never loaded in this gate. `reconstruct_build_tree.sh` silently skips the glue patch without git-lfs.
* Smoke rows 1-24 were run before the power-cycle; they are excluded from analysis.
* `nvidia-drm` cannot load on this kernel (drm_ttm_helper not installed); display only. xrdp is restarted by `systemctl isolate multi-user.target`, so it had to be stopped again after the isolate.
* Unplanned installs (all named packages): git-lfs, python3-scipy/numpy/matplotlib, build-essential, rsync, patch, dkms; NVIDIA CUDA apt source + pin file `/etc/apt/preferences.d/cuda-limited`.

## End state
Stock module loaded, threshold 51, srcversion 6284DA42F15EDC3AB92332B verified; xrdp started again; default target graphical (currently multi-user.target until reboot or `isolate graphical.target`). Branch `t4-replication` pushed.

**STOP THE INSTANCE when you are done.**
HARD STOP.
