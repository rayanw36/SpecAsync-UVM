# Path fixes (Gate C3 session, Phase 3; from `PATH_AUDIT.md`)

One commit. Every hardcoded path in the audited scripts is now an environment variable **whose default is today's literal value**, so
each script behaves identically unless the variable is set. Variables: `SPECASYNC_ROOT` (repository root), `SPECASYNC_HOME`
(the `/home/ubuntu` home), `SPECASYNC_WORK` (the DKMS work tree), `NV_SRC` (the NVIDIA DKMS source), `SPECASYNC_USER` (the owner for `chown`).
Each variable is used with `:-` in shell (an empty value counts as unset) and `... or default` in Python, so both treat empty as unset.

| file:line | old | new | variable |
|---|---|---|---|
| `tests/e09b_runner.py:35` | `REPO = "/home/rayenchikhaoui/SpecAsync-UVM"` | `REPO = os.environ.get("SPECASYNC_ROOT") or "/home/rayenchikhaoui/SpecAsync-UVM"` | SPECASYNC_ROOT |
| `scripts/collect_oracle_traces.sh:16` | `UBUNTU_HOME="/home/ubuntu"` | `UBUNTU_HOME="${SPECASYNC_HOME:-/home/ubuntu}"` | SPECASYNC_HOME |
| `scripts/finish_p4.sh:5` | `HOME_DIR=/home/ubuntu/SpecAsync-UVM` | `HOME_DIR="${SPECASYNC_ROOT:-/home/ubuntu/SpecAsync-UVM}"` | SPECASYNC_ROOT |
| `scripts/watch_progress.sh:5` | `H=/home/ubuntu/SpecAsync-UVM` | `H="${SPECASYNC_ROOT:-/home/ubuntu/SpecAsync-UVM}"` | SPECASYNC_ROOT |
| `scripts/oracle_sweep.sh:12,41` | `UBUNTU_HOME="/home/ubuntu"` | `UBUNTU_HOME="${SPECASYNC_HOME:-/home/ubuntu}"` | SPECASYNC_HOME |
| `scripts/oracle_sweep.sh:43` | `NVME_KO="/opt/dlami/nvme/work/nvidia-595.71.05-specasync/nvidia-uvm.ko"` | `NVME_KO="${SPECASYNC_WORK:-/opt/dlami/nvme/work/nvidia-595.71.05-specasync}/nvidia-uvm.ko"` | SPECASYNC_WORK |
| `scripts/rebuild_and_reload.sh:13` | `WORK_SRC="/opt/dlami/nvme/work/nvidia-595.71.05-specasync/nvidia-uvm"` | `WORK_SRC="${SPECASYNC_WORK:-/opt/dlami/nvme/work/nvidia-595.71.05-specasync}/nvidia-uvm"` | SPECASYNC_WORK |
| `scripts/rebuild_and_reload.sh:14` | `TOP_DIR="/opt/dlami/nvme/work/nvidia-595.71.05-specasync"` | `TOP_DIR="${SPECASYNC_WORK:-/opt/dlami/nvme/work/nvidia-595.71.05-specasync}"` | SPECASYNC_WORK |
| `scripts/rebuild_and_reload.sh:16` | `STOCK_BACKUP="/home/ubuntu/SpecAsync-UVM/driver/stock_backup/nvidia-uvm.ko.stock"` | `STOCK_BACKUP="${SPECASYNC_ROOT:-/home/ubuntu/SpecAsync-UVM}/driver/stock_backup/nvidia-uvm.ko.stock"` | SPECASYNC_ROOT |
| `scripts/rebuild_and_reload.sh:72` | `echo "  rsync -av /opt/dlami/nvme/work/nvidia-595.71.05-specasync/nvidia-uvm/nvidia-uvm.ko \\"` | `echo "  rsync -av ${TOP_DIR}/nvidia-uvm/nvidia-uvm.ko \\"` | SPECASYNC_WORK (via TOP_DIR) |
| `scripts/resume.sh:12` | `EBS_HOME="/home/ubuntu/SpecAsync-UVM"` | `EBS_HOME="${SPECASYNC_ROOT:-/home/ubuntu/SpecAsync-UVM}"` | SPECASYNC_ROOT |
| `scripts/resume.sh:14` | `SRC_STOCK="/usr/src/nvidia-595.71.05"` | `SRC_STOCK="${NV_SRC:-/usr/src/nvidia-595.71.05}"` | NV_SRC |
| `scripts/resume.sh:15` | `WORK_TOP="/opt/dlami/nvme/work/nvidia-595.71.05-specasync"` | `WORK_TOP="${SPECASYNC_WORK:-/opt/dlami/nvme/work/nvidia-595.71.05-specasync}"` | SPECASYNC_WORK |
| `scripts/resume.sh:49` | `mkdir -p /opt/dlami/nvme/work` | `mkdir -p "$(dirname "$WORK_TOP")"` | SPECASYNC_WORK (via WORK_TOP) |
| `scripts/resume.sh:50` | `chown ubuntu:ubuntu /opt/dlami/nvme/work` | `chown "${SPECASYNC_USER:-ubuntu}:${SPECASYNC_USER:-ubuntu}" "$(dirname "$WORK_TOP")"` | SPECASYNC_USER, SPECASYNC_WORK |
| `driver/scripts/install_uvm_v595.sh:6` | `WORK=/opt/dlami/nvme/work/nvidia-595.71.05-specasync` | `WORK="${SPECASYNC_WORK:-/opt/dlami/nvme/work/nvidia-595.71.05-specasync}"` | SPECASYNC_WORK |
| `driver/scripts/build_uvm_v595.sh:5` | `WORK=/opt/dlami/nvme/work/nvidia-595.71.05-specasync` | `WORK="${SPECASYNC_WORK:-/opt/dlami/nvme/work/nvidia-595.71.05-specasync}"` | SPECASYNC_WORK |
| `driver/scripts/reconstruct_build_tree.sh:16` | `: "${SRC:=/usr/src/nvidia-595.71.05}"` | `: "${SRC:=${NV_SRC:-/usr/src/nvidia-595.71.05}}"` | NV_SRC |
| `driver/scripts/reconstruct_build_tree.sh:17` | `: "${WORK:=/opt/dlami/nvme/work/nvidia-595.71.05-specasync}"` | `: "${WORK:=${SPECASYNC_WORK:-/opt/dlami/nvme/work/nvidia-595.71.05-specasync}}"` | SPECASYNC_WORK |

**19 edits, 20 line replacements, 10 files** (`oracle_sweep.sh` has two identical `UBUNTU_HOME` lines; both changed).

## Verification (any failure would have reverted that file; none failed)

- `bash -n` on all 9 edited shell scripts: OK. `python3 -m py_compile tests/e09b_runner.py`: OK.
- Each edited assignment line evaluated in a clean environment (all five variables unset) and compared with the old line's result: **identical**
  for all 15 assignment edits; the four non-assignment edits (`rebuild_and_reload.sh` echo, `resume.sh` mkdir and chown) were checked by hand
  (`$(dirname "$WORK_TOP")` = `/opt/dlami/nvme/work`; owner `ubuntu:ubuntu`; the echo prints `$TOP_DIR`, which has the old value).
- `tests/e09b_runner.py`: `REPO` is unchanged by default, `/x` with `SPECASYNC_ROOT=/x`, and unchanged with `SPECASYNC_ROOT=` (empty). The E7 and E8 runners import it.
- E8 analyzer positive control: **PASS** (reproduces E7 Family A, -9.57%, p 1.08e-05).
- E8 benchmark validation at 64 MiB: **PASS** (checksum equals the host reference for K = 1, 8, 64, 512; K = 8 page-list hash `cadb089e31a7ed3e`
  and checksum `000000868205d9da` equal the Phase 1 validation log).
- Not run: the scripts under `scripts/` and `driver/scripts/` (they target the AWS T4 instance, which no longer exists; syntax and default-equivalence only).

## Not edited (DOC-class; recorded)

- **Patch files** (`driver/patches/specasync_uvm_v580.95.05.patch`, `specasync_uvm_v595.71.05.patch`): the paths are inside diff headers and embedded build
  artifacts, where an environment variable has no meaning; fixing them means regenerating the patches (`--exclude='*.cmd'`, relative paths), which changes
  their content and is not a path substitution. Left as is.
- **Comments** naming `/opt/dlami/nvme` and `/usr/src/nvidia-595.71.05` in `driver/scripts/reconstruct_build_tree.sh` (lines 4 and 6): comment-only; update when the defaults change.
- The T4 hazard noted in the audit remains: `resume.sh` and `reconstruct_build_tree.sh` default to the **595.71.05** (T4) source tree; set `NV_SRC` for another driver version.
