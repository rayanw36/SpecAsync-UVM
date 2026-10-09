# Gate T4-R1 session summary

**Outcome: setup, builds and pre-registration complete; E7-T4 sweep NOT run, no verdict.** Stopped at T5 (smoke 24/27) after an
unplanned instance power-cycle and the 5 h cap expiring while the session was away. T6 (analysis/report/figure) not produced: no timed data.

| phase | result |
|---|---|
| T0 | instance verified: 6.17.0-1017-aws, Ubuntu 24.04.4, 4 vCPU, 15 GiB, 96 GB EBS root (94 GB free), work dir on EBS, auto-updates off, holds and linger OK |
| T1 | 595.91.07 was missing from the apt index; user approved installing the exact debs from the archive pool. 18/18 files matched Launchpad SHA256 (both publications). Holds on all 18 nvidia packages. dkms built for 6.17.0-1017-aws. CUDA nvcc 13.0.88 (NVIDIA repo, with a pin blocking its driver packages), gcc 13.3.0. Stock srcversion **6284DA42F15EDC3AB92332B (same as the 5070 Ti, not different)**, threshold 51. No reboot needed. |
| T2 | one edit: `tests/e09b_runner.py:35` SPECASYNC_REPO env var (old default kept); benchmarks built for sm_75; smoke 5.91 s (Stencil-24K), 54.36 s (GraphBFS-23) vs old T4 4.185 / 54.265 |
| T3 | verified module 5997D238EF080B77DBD2AAF and E3a-2 module 33FD42E6E16B0A6658E2BEB: **both identical to the 5070 Ti srcversions**; vermagic 6.17.0-1017-aws (no `preempt`). Not inserted. Review packet: `E3A2_T4_BUILD_REVIEW.md`. Finding: patches are Git LFS pointers; without git-lfs the build script silently skips the glue patch and fails in the compiler. |
| T4 | `E7T4_PREREGISTRATION.md`, order (seed 202610072, 270 rows), runner wrapper, orchestrator, analyzer committed and pushed before any timed run; positive control reproduces -9.57%, p 1.08e-05 (PASS); oversub N=48000 kept (ratio 1.144 vs 1.078, 6.1% apart) |
| T5 | smoke 24/27 clean (graphs of walls in `e7t4_smoke.csv`; descriptive, excluded from analysis). Interrupted by the 17:59 power-off. Sweep not started. |
| T6 | not done |

## Why it stopped
The instance was powered off and rebooted at 17:59 UTC (clean systemd poweroff, not by this session). The orchestrator died at smoke row 24. When the session resumed at 07:27 UTC the next day, the cap (21:38 UTC) was long past. Resuming would depart from the pre-registration, and the gate says to stop without retries.

## To finish later (user's call)
Needs a new cap/T0 decision. The pre-registered skip rule and deadline are in the orchestrator and `phase0_start.txt`. Smoke rows 25-27 (oversub) and the timeouts file are still needed before the sweep.
(`e7t4_orchestrate.py smoke` is resumable by idx), then `sweep`. Pre-registration would have to be amended (new T0) and committed first.

## Unplanned installs / changes (all named packages)
git-lfs, python3-scipy/numpy/matplotlib, build-essential, rsync, patch, dkms (as dependency) and their dependencies, 4 non-NVIDIA libs upgraded as dependencies (libbz2-1.0, libdrm2, libdrm-common, libdrm-amdgpu1); NVIDIA CUDA apt source + pin file `/etc/apt/preferences.d/cuda-limited`.
Known leftovers: `nvidia-drm` cannot load on this kernel (missing drm_ttm_helper, linux-modules-extra not installed), display only.

## End state
Stock module loaded, threshold 51, srcversion 6284DA42F15EDC3AB92332B verified. xrdp active. System default target graphical. Branch `t4-replication` pushed.

**STOP THE INSTANCE when you are done. HARD STOP.**
