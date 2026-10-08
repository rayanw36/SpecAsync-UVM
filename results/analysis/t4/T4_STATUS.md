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
