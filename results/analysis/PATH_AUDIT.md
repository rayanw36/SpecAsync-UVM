# Hardcoded-path audit (Gate C1-APPLY Phase 2b, handoff task 8)

Read-only; nothing was edited. Scope: `tests/`, `benchmarks/`, `scripts/`,
`driver/scripts/`, the driver patch files, and `driver/build/` (text files only; no hits).
Patterns: `/home/<user>`, the user name, the hostname `LinuxPC`, `/opt/dlami`,
`/usr/src/<kernel- or driver-specific>`, `/root`, `/mnt`, `/data`, `/tmp/claude`, and
kernel-headers paths for a specific kernel version.

**Counts.** 22 hits in 10 script files (1 in `tests/`, 15 in `scripts/` across 6 files, 6 in
`driver/scripts/`), plus embedded paths in 2 patch files. **Excluded as portable:** 326
references to kernel interfaces (`/sys/`, `/proc/`, `/dev/`). Those are part of the
platform API, not machine-specific paths.

## A. Scripts (file:line → suggested replacement)

| file:line | hardcoded value | suggested replacement |
|---|---|---|
| `tests/e09b_runner.py:35` | `REPO = "/home/rayenchikhaoui/SpecAsync-UVM"` | `REPO = os.environ.get("SPECASYNC_REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`. **Highest priority**: every E-gate runner (E0.9b through E6) imports this constant through `e09b_runner`, so one edit fixes them all. The `KO` path and every benchmark path are built from it. |
| `scripts/collect_oracle_traces.sh:16` | `UBUNTU_HOME="/home/ubuntu"` | `UBUNTU_HOME="${SPECASYNC_HOME:-$(cd "$(dirname "$0")/.." && pwd)}"` |
| `scripts/finish_p4.sh:5` | `HOME_DIR=/home/ubuntu/SpecAsync-UVM` | `HOME_DIR="$(cd "$(dirname "$0")/.." && pwd)"` |
| `scripts/watch_progress.sh:5` | `H=/home/ubuntu/SpecAsync-UVM` | `H="$(cd "$(dirname "$0")/.." && pwd)"` |
| `scripts/oracle_sweep.sh:12` | `UBUNTU_HOME="/home/ubuntu"` | as `collect_oracle_traces.sh:16` |
| `scripts/oracle_sweep.sh:41` | `UBUNTU_HOME="/home/ubuntu"` (second definition) | remove the duplicate; use the variable from line 12 |
| `scripts/oracle_sweep.sh:43` | `NVME_KO="/opt/dlami/nvme/work/nvidia-595.71.05-specasync/nvidia-uvm.ko"` | `NVME_KO="${SPECASYNC_WORK:?set SPECASYNC_WORK}/nvidia-uvm.ko"` |
| `scripts/rebuild_and_reload.sh:13` | `WORK_SRC="/opt/dlami/nvme/work/nvidia-595.71.05-specasync/nvidia-uvm"` | `WORK_SRC="${SPECASYNC_WORK:?}/nvidia-uvm"` |
| `scripts/rebuild_and_reload.sh:14` | `TOP_DIR="/opt/dlami/nvme/work/nvidia-595.71.05-specasync"` | `TOP_DIR="${SPECASYNC_WORK:?}"` |
| `scripts/rebuild_and_reload.sh:16` | `STOCK_BACKUP="/home/ubuntu/SpecAsync-UVM/driver/stock_backup/nvidia-uvm.ko.stock"` | `STOCK_BACKUP="$REPO_ROOT/driver/stock_backup/nvidia-uvm.ko.stock"` with `REPO_ROOT` derived from `$0` |
| `scripts/rebuild_and_reload.sh:72` | `rsync -av /opt/dlami/nvme/…` (printed instruction) | print `${SPECASYNC_WORK}` instead of the literal path |
| `scripts/resume.sh:12` | `EBS_HOME="/home/ubuntu/SpecAsync-UVM"` | script-relative root, as above |
| `scripts/resume.sh:14` | `SRC_STOCK="/usr/src/nvidia-595.71.05"` | `SRC_STOCK="${SRC_STOCK:-/usr/src/nvidia-$(cat driver/VERSION 2>/dev/null)}"`, or an explicit parameter. The version is the **T4** driver (595.71.05), so this is also a platform hazard |
| `scripts/resume.sh:15` | `WORK_TOP="/opt/dlami/nvme/work/nvidia-595.71.05-specasync"` | `WORK_TOP="${SPECASYNC_WORK:?}"` |
| `scripts/resume.sh:49` | `mkdir -p /opt/dlami/nvme/work` | `mkdir -p "$SPECASYNC_WORK"` |
| `scripts/resume.sh:50` | `chown ubuntu:ubuntu /opt/dlami/nvme/work` | `chown "$(id -un):$(id -gn)" "$SPECASYNC_WORK"`; the hard-coded owner is a user name |
| `driver/scripts/install_uvm_v595.sh:6` | `WORK=/opt/dlami/nvme/work/nvidia-595.71.05-specasync` | `WORK="${SPECASYNC_WORK:?}"` |
| `driver/scripts/build_uvm_v595.sh:5` | `WORK=/opt/dlami/nvme/work/nvidia-595.71.05-specasync` | `WORK="${SPECASYNC_WORK:?}"` |
| `driver/scripts/reconstruct_build_tree.sh:16` | `: "${SRC:=/usr/src/nvidia-595.71.05}"` | already overridable (`${SRC:=…}`). Change the default to a version-independent lookup, or document the override. The 595.91.07 run used `SRC=/usr/src/nvidia-595.91.07` explicitly (E0.5 onward) |
| `driver/scripts/reconstruct_build_tree.sh:17` | `: "${WORK:=/opt/dlami/nvme/work/nvidia-595.71.05-specasync}"` | already overridable. Default to `${SPECASYNC_WORK:-$HOME/work/…}` |
| `driver/scripts/reconstruct_build_tree.sh:4–6` | comments naming `/opt/dlami/nvme` and `/usr/src/nvidia-595.71.05` | comment-only; update when the defaults change |

**Notes on `scripts/`.** These are the AWS T4 instance scripts (`/home/ubuntu`,
`/opt/dlami`). That instance no longer exists (`reconstruct_build_tree.sh` states the
instance store is wiped on stop), so these scripts cannot run as written on the current
host. Two options for review: fix the paths as above, or move the directory under
`legacy/` with a README. The audit does not choose.

## B. Patch files (embedded paths)

| file | hits | what it is | suggested replacement |
|---|---|---|---|
| `driver/patches/specasync_uvm_v580.95.05.patch` | **159,028 lines**, from 23 embedded `.cmd` build artifacts | the diff includes Kbuild `.cmd` files, whose contents embed the absolute path `/usr/src/linux-headers-6.14.0-37-generic` (and `/usr/src/nvidia`, `/usr/src/ofa_kernel`) | regenerate the patch with `--exclude='*.cmd'` (as the v595 patch's own `diff` line already does), so no build artifacts are included. The `.cmd` files are not source |
| `driver/patches/specasync_uvm_v595.71.05.patch` | 16 `/usr/src/nvidia-595.71.05` and 16 `/opt/dlami/nvme/work/…` | the `diff -ruN` header lines name both trees absolutely | regenerate with relative paths (`cd` into the parent, then `diff -ruN a/ b/`), so headers are `a/…` and `b/…` |

## C. Not hits, checked and cleared

- `driver/build/` contains binaries (`.ko`) and no text references: 0 hits.
- `benchmarks/`: 0 hits.
- `LinuxPC` (the hostname) appears in none of the audited trees; it appears only in the
  systemd journal (see `consolidation/D6_RAW_INVENTORY.md`).
- My own runner scripts from E0.9b onward use the `REPO` constant (A, first row) and
  nothing else. Apart from that constant they contain no hardcoded user or host paths.

## Count summary

| category | count |
|---|---:|
| script files with hits | 10 (1 in `tests/`, 6 in `scripts/`, 3 in `driver/scripts/`; each counted once) |
| script hit lines | 22 (`tests` 1 · `scripts` 15 · `driver/scripts` 6) |
| patch files with embedded paths | 2 (159,028 and 32 lines) |
| portable kernel-interface references, excluded | 326 |
| distinct user names in hardcoded paths | 2 (`rayenchikhaoui`, `ubuntu`) |
| distinct hosts | 0 hostname hard-codes (the EC2 `ubuntu` home and `/opt/dlami` are instance layouts, counted under paths) |
