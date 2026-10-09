# T4 gate status (GATE T4-R1)

T0 start: 2026-10-08 16:38 UTC (5 h cap -> 21:38 UTC)

## T0 - instance state (verified, not redone)
- Kernel: 6.17.0-1017-aws (expected 6.17.0-1017-aws: OK)
- OS: Ubuntu 24.04.4 LTS; vCPUs: 4; RAM: 15Gi
- GPU: NVIDIA Corporation TU104GL [Tesla T4] (rev a1)
- EBS root: /dev/root 96G, 94G free (nvme1n1p1). Instance store nvme0n1 (116G) unmounted. Work dir /home/ubuntu is on the EBS root: OK
- unattended-upgrades, apt-daily.timer, apt-daily-upgrade.timer: disabled + inactive: OK
- apt-mark showhold: linux-aws, linux-headers-aws, linux-image-aws, linux-headers-6.17.0-1017-aws, linux-image-6.17.0-1017-aws: OK
- Linger=yes for ubuntu: OK

## T1 - BLOCKED (awaiting user)
- Repo cloned over SSH (deploy key t4aws), branch t4-replication created from manuscript-prep @ 23307df.
- `apt-get update` run (index refresh only). apt offers nvidia-*-595-open only at 595.99.02 and 595.84. **595.91.07-0ubuntu0.24.04.1 is NOT in the apt index.**
- The exact .debs still exist in the Ubuntu archive pool (pool/multiverse/n/nvidia-graphics-drivers-595/), but are not covered by the current signed index.
- Per T1 ("not available -> stop and ask; do not substitute") nothing was installed. No packages changed.

## T1 - driver provenance (user-approved Option 1, conditions 1-5)
Source: http://us-west-2.ec2.archive.ubuntu.com/ubuntu/pool/multiverse/n/nvidia-graphics-drivers-595/ (files not in current apt index). Independent check: Launchpad API binaryFileUrls(include_meta) for both the Superseded and Deleted publications of 595.91.07-0ubuntu0.24.04.1 (amd64); 18/18 files x 2 publications MATCH, 0 mismatch (raw: results/analysis/t4/driver_deb_sha256.txt).

| file | SHA256 |
|---|---|
| libnvidia-cfg1-595_595.91.07-0ubuntu0.24.04.1_amd64.deb | 4ad6a640ccc9612d8db11a60b0b432be79a6506dac05b7c8ad6d8a205beb5db7 |
| libnvidia-common-595_595.91.07-0ubuntu0.24.04.1_amd64.deb | deee8e79ea0eb3517dc6da386cd0dfa79af41f19d3a4121da51c7d95fc2e8859 |
| libnvidia-compute-595_595.91.07-0ubuntu0.24.04.1_amd64.deb | 285e9a350f7294c37b530801bcce4fc0f02ee5b3ecae1a0e397bef1d97c5653d |
| libnvidia-decode-595_595.91.07-0ubuntu0.24.04.1_amd64.deb | b74222c2ffdb2d0f48f778044c1c52ffba993ec071980359ea70a3b5045c15dc |
| libnvidia-encode-595_595.91.07-0ubuntu0.24.04.1_amd64.deb | 83ca5fe94f1b6a4ced9e16e83cb97198ee8e37b6dadac8bd5f3a23c57618dd76 |
| libnvidia-extra-595_595.91.07-0ubuntu0.24.04.1_amd64.deb | 4b7b7192cbc1caf21bce696c100b8562f12075b4a69b27f6c12449b86362e5de |
| libnvidia-fbc1-595_595.91.07-0ubuntu0.24.04.1_amd64.deb | 4e3d0f19d6367eded50654d95d49bf330c8d0b362e4f2f40db1d5af9a0ad9f44 |
| libnvidia-gl-595_595.91.07-0ubuntu0.24.04.1_amd64.deb | 14283e1ca43f5ad453812a7d06ba3b438d616cdbb3e4ed01785b36f202101189 |
| nvidia-compute-utils-595_595.91.07-0ubuntu0.24.04.1_amd64.deb | cdce96ee8a6b39c17621d90d83098e0f3b433d04e1657a8ba60c275e5d499d5b |
| nvidia-dkms-595-open_595.91.07-0ubuntu0.24.04.1_amd64.deb | 70264a7964b7d5eb8dd24f16585323104966a272a181a26198a7ed14ce47881c |
| nvidia-driver-595-open_595.91.07-0ubuntu0.24.04.1_amd64.deb | 4e8d54b3bedf0fbde487f2df7fbb2cd72cfa0e42cc9031e482d1544058aed268 |
| nvidia-firmware-595-595.91.07_595.91.07-0ubuntu0.24.04.1_amd64.deb | 360d93469608748a46d063058357553bfb0975df1eb6a60d8dc8d8032d949952 |
| nvidia-headless-595-open_595.91.07-0ubuntu0.24.04.1_amd64.deb | 7b0ed3be281b48cefc08116ac5dd018df3dc2c4892c456d3b2c1a5033868c9d8 |
| nvidia-headless-no-dkms-595-open_595.91.07-0ubuntu0.24.04.1_amd64.deb | 437288901ea43614c5eb391b82670f87fe30b233f1eb765592db0c346bf9a376 |
| nvidia-kernel-common-595_595.91.07-0ubuntu0.24.04.1_amd64.deb | dd9cca39b9235622c40682290f73d27e49111021b0c22346bb7f8374a611f15d |
| nvidia-kernel-source-595-open_595.91.07-0ubuntu0.24.04.1_amd64.deb | 56d65487016ec399cccfa30be1f693e988bc37dd9875141ba8092707bb5ed44a |
| nvidia-utils-595_595.91.07-0ubuntu0.24.04.1_amd64.deb | 7e090f2776b54795987f842554655011804d3b085115e9236821905f7a8a4744 |
| xserver-xorg-video-nvidia-595_595.91.07-0ubuntu0.24.04.1_amd64.deb | 22ff09fdaba41b10972c34877b5320274fc58116dd0f8ea9d9069aaad146ae9f |

Simulation (apt-get install --simulate --no-install-recommends): no other nvidia version, no kernel pkgs. Non-NVIDIA dependency changes pulled in by apt (not an upgrade command): libbz2-1.0, libdrm2, libdrm-common, libdrm-amdgpu1 upgraded; dkms, gcc-13, make, binutils, xserver-xorg-core, mesa etc. newly installed; libnvidia-egl-wayland1 1:1.1.13-1ubuntu0.1 from noble-updates.

## T1 - result (DONE; user approved pool install, all 5 conditions met)
- Installed the 18 debs above (open flavour, no recommends). Condition 1: simulate showed no 595.99/595.84. Condition 2: 36/36 Launchpad SHA256 matches. Condition 4: all 18 installed nvidia/libnvidia 595 pkgs on apt-mark hold (23 holds total incl. kernel).
- No reboot needed: `modprobe nvidia nvidia_uvm` loaded cleanly; kernel still 6.17.0-1017-aws.
- /proc/driver/nvidia/version: NVRM version: NVIDIA UNIX Open Kernel Module for x86_64  595.91.07  Release Build  (dvs-builder@U22-I3-B08-02-2)  Wed Jul 29 03:01:16 UTC 2026
- dkms status: nvidia/595.91.07, 6.17.0-1017-aws, x86_64: installed
- GPU: Tesla T4, compute_cap 7.5, 15360 MiB. Turing: driver recognises it; nvcc 13.0 lists compute_75.
- Stock nvidia_uvm srcversion: **6284DA42F15EDC3AB92332B** (/sys/module + modinfo of /lib/modules/6.17.0-1017-aws/updates/dkms/nvidia-uvm.ko.zst; vermagic '6.17.0-1017-aws SMP mod_unload modversions'). NOTE: identical to the 5070 Ti stock srcversion (expected to differ); recorded, not an error. nvidia.ko srcversion A970FABA258551DAB05BE12.
- uvm_perf_prefetch_threshold read-back (stock default): 51
- CUDA toolkit: NVIDIA apt repo (signed-by cuda-archive-keyring from cuda-keyring_1.1-1 sha256 d2a6b11c...), cuda-compiler-13-0/libraries-13-0/libraries-dev-13-0 = 13.0.1-1; **nvcc release 13.0, V13.0.88** (cuda-nvcc-13-0 13.0.88-1); libcublas 13.1.1.3, libcufft 12.0.0.61. /usr/local/cuda -> cuda-13.0. Own pin file /etc/apt/preferences.d/cuda-limited blocks nvidia-*/libnvidia-* from that repo. Not installed: nsight/visual tools (not needed). cuda-toolkit-config-common 13.4.92 came in as a config-only dep.
- gcc: gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
- Plus build-essential, rsync, patch, dkms installed (named, for builds).

## T2 - scripts run here (DONE)
- Env-var path fixes were NOT on origin (PATH_AUDIT.md was audit-only), so one minimal edit: `tests/e09b_runner.py:35` `REPO = os.environ.get("SPECASYNC_REPO", "/home/rayenchikhaoui/SpecAsync-UVM")` (default unchanged; every E-runner imports it). Run with SPECASYNC_REPO=/home/ubuntu/SpecAsync-UVM. No other file edited. e7_runner.py/e5/e4/e3b unchanged.
- Benchmarks built for sm_75 with nvcc 13.0.88 (benchmarks/Makefile, graph_bfs/Makefile, stencil_oversub/Makefile; binaries are gitignored). One warning: bench_graph_bfs.cu(98) unused variable `half`.
- Smoke (stock module, threshold 51, setarch -R, single run, xrdp active, DESCRIPTIVE ONLY; old T4 C0 = GATE_T1_REPORT.md, driver 595.71.05):

| workload | this run (595.91.07 stock t51) | old T4 C0 (595.71.05, n=20 median) |
|---|---:|---:|
| Stencil-24K | 5.91 s | 4.185 s |
| GraphBFS-23 | 54.36 s | 54.265 s |
- 17:02:22 orchestrator smoke: T0 16:38:43, now 17:02:22, session cap 21:38:43, latest sweep end (cap - 25 min reserve) 21:13:43

## T5 - STOPPED before the sweep (2026-10-09 07:27 UTC, session resumed)
- 17:02 UTC: xrdp/xrdp-sesman stopped (isolate to multi-user.target restarted xrdp, stopped again), no graphical session; smoke pass launched.
- Smoke ran 24 of 27 rows (idx 1-24; oversub idx 25-27 not run) with zero stop conditions: exit 0, srcversion 6284DA42..., read-back ok, 0 new dmesg lines.
- **17:59 UTC: the instance was powered off and started again (journal: clean systemd-poweroff, `last -x`: shutdown 17:59, boot 17:59). Not initiated by this session; cause unknown.** It killed the orchestrator. Same kernel 6.17.0-1017-aws, stock module/threshold 51 present after boot, xrdp active again (default graphical.target).
- Session resumed 07:27 UTC on Oct 9: T0 + 5 h cap (21:38:43 UTC Oct 8) is ~10 h past. The orchestrator would abort, and re-running from a changed machine state is a departure from the pre-registration (a stop condition), so per the RUN-class rule: **no retry, no sweep, no timeouts file written (needs all 27 smoke rows), stop.** No timed data exist; no verdict.
- 08:05:43 orchestrator smoke: T0 08:05:10, now 08:05:43, session cap 12:05:10, latest sweep end (cap - 25 min reserve) 11:40:10

## Resume (Amendment 1) - STOPPED at smoke row 25, 2026-10-09 08:05 UTC
- R0 preflight and Amendment 1 committed/pushed (8e33b2b) before any run. CloudTrail cause: not supplied by the user (placeholder left in the brief).
- 08:05:43 the orchestrator started (deadlines: cap 12:05:10, sweep end 11:40:10) and loaded row 25 (oversub, stock-t0).
- **08:05:52 kernel global OOM killed `bench_stencil_oversub` (anon 13 MB, file-rss 15.1 GB, total-vm 22.9 GB), trace in `block_populate_pages_cpu` (UVM CPU-side page population).** No row was written (smoke CSV still 24 rows); the orchestrator was also gone when the session was next looked at, so no STOP file exists. By the runner's rules this is a stop (benchmark killed / MemAvailable floor).
- Cause: the oversubscribed Stencil (N=48000: 2 x N^2 x 4 B = **17.17 GiB** managed memory) is populated in host RAM; this g4dn.xlarge has 15.4 GiB RAM and **no swap**. The 5070 Ti host had far more RAM. The pre-registered sizing check compared only VRAM ratios (1.144 vs 1.078) and did not consider host RAM: **a pre-registration gap, mine.** The workload as registered cannot run here at any threshold.
- Per RUN-class rule: no retry, no workaround, no sweep. Changing N, dropping oversub, or adding swap are departures from the pre-registration and need a user decision / Amendment 2.
- End state restored: `rmmod nvidia_uvm; modprobe nvidia_uvm` -> stock srcversion 6284DA42F15EDC3AB92332B, threshold 51; xrdp active; machine otherwise left as is (multi-user.target). Sweep and timeouts file: not produced. T6: not produced.
- 12:03:31 orchestrator smoke: T0 12:02:31, now 12:03:31, session cap 16:02:31, latest sweep end (cap - 25 min reserve) 15:37:31
- 12:03:31 smoke runner exit 0
- 12:03:31 timeouts (3 x smoke median, ceil s): {"cufft": 9, "graphbfs": 163, "sgemm": 51, "stencil": 18, "stencil8k": 8, "stream": 12, "sweep16k": 11, "sweep4k": 7}
- 12:03:34 orchestrator sweep: T0 12:02:31, now 12:03:34, session cap 16:02:31, latest sweep end (cap - 25 min reserve) 15:37:31
- 12:03:34 Family B estimates (s): stencil8k 192, sweep4k 183, sweep16k 232, stream 241, sgemm 646, cufft 202, graphbfs 1747

## Amendment 2 run (2026-10-09, start 12:02:31 UTC, cap 16:02:31, sweep end 15:37:31)
- Preflight clean (kernel, holds 18+5, stock srcversion 6284DA42..., t51, empty driver diff, no processes, no STOP files). Cause of the 8 Oct 17:59 UTC poweroff: **not checked**.
- Previous session ended because I ran `loginctl terminate-session` on the xrdp session containing it (my error); that action is forbidden from now on and was not repeated. At this preflight no graphical session remained.
- xrdp + xrdp-sesman stopped; `systemctl isolate multi-user.target` **restarted xrdp/xrdp-sesman**; stopped again (xrdp inactive, sesman 'failed' = not running), 10 s later still stopped, 0 xrdp/Xorg processes, only a tty login session.
- Launched ONE chain: `systemd-run --user --unit=e7t4-sweep` -> `e7t4_chain.sh` (smoke -> timeouts -> sweep), log `e7t4_chain.log`, halts on first failure. Smoke was already complete (24 rows), timeouts file written: {"cufft": 9, "graphbfs": 163, "sgemm": 51, "stencil": 18, "stencil8k": 8, "stream": 12, "sweep16k": 11, "sweep4k": 7}.
- **Detachment verified:** chain main PID 11982 has PPID 741 = `systemd --user`; its cgroup is `.../user@1000.service/app.slice/e7t4-sweep.service`, whereas this Claude process is in `.../app.slice/tmux-spawn-*.scope`; `systemctl --user show`: Restart=no, KillMode=control-group; `Linger=yes`. So it has no process-tree or cgroup relation to the Claude session.
