# SpecAsync-UVM (README draft; replaces the outdated `README.md` after review)

`README.md` is not a stub: it describes the original v580.95.05 / kernel 6.14 prototype and is out of date, so this is written beside it as `README_DRAFT.md`. Nothing here states a result beyond what `results/analysis/CLAIM_SCOPE.md` states.

## Project

When a GPU touches a managed page that is not resident, the NVIDIA UVM driver services the fault on the CPU: it batches faults from a hardware buffer, decides where each page should live, copies, maps, and replays. SpecAsync-UVM is a modification of the open UVM driver in which a background worker stages pages that a predictor nominates while the fault-servicing thread continues, so that part of the cost is paid off the fault path. To ask what off-path staging can achieve at all, we drive it with a first-touch oracle (a table of the run's own page order recorded in an earlier run) and measure it against the driver as shipped.

The measurements are organised as pre-registered gates, each with its families of comparisons, statistic, test, minimum detectable effect and falsification trigger fixed in a committed `*_PREREGISTRATION.md` before any timed run. The driver's own density prefetcher (`uvm_perf_prefetch_threshold`) turns out to be central, and several earlier conclusions were retired when the oracle and some counters were found to be misaligned; `results/analysis/ARTIFACT_CATALOG.md` records those. The manuscript is in `paper/`; its claims and their evidence are in `results/analysis/CLAIM_SCOPE.md`.

## Repository map

| path | contents |
|---|---|
| `driver/src/` | the verified specasync sources (the source of truth); `driver/src-e3a/` the E3a/E3a-2 overlay (staging width, region history, cheap oracle) |
| `driver/patches/` | glue and full patches, **stored in Git LFS** (`*.patch`) |
| `driver/scripts/` | `reconstruct_build_tree.sh` (builds the work tree), build/install helpers |
| `benchmarks/`, `oracles/` | CUDA benchmarks (`bench_stencil`, `bench_stream`, `bench_sgemm`, `bench_cufft`, `bench_sparse`, `graph_bfs`, `stencil_oversub`) and recorded oracle inputs |
| `tests/` | gate runners, order generators, orchestrators and analyzers (`e4_*` ... `e9_*`), evidence-id tooling (`c1_*`, `c4_*`, `c5_*`), `make_paper_figures.py` |
| `results/analysis/` | reports, pre-registrations (`gate_e/`), derived CSVs (`derived/`), `consolidation/` (claim and paper consolidation), `t4/` (Tesla T4 replication) |
| `results/analysis/REPRODUCE.md` | the command sequence per gate and each analyzer's positive control |
| `results/figures/`, `tools/figures/` | the earlier figures F1-F11 and their scripts; `paper/figures/` the post-E0.5 figures |
| `paper/` | manuscript sections, bibliography, figures (`paper/figures/FIGURES.md`) |
| `MANIFEST.sha256`, `MIGRATION_NOTES.md` | transfer manifest and migration notes |

## Platforms (from `results/analysis/PLATFORM_5070TI.md` and `results/analysis/t4/GATE_E7T4_REPORT.md`, `E3A2_T4_BUILD_REVIEW.md`)

| | RTX 5070 Ti host | Tesla T4 (AWS g4dn.xlarge) |
|---|---|---|
| NVIDIA driver | 595.91.07, open kernel module, Ubuntu apt `nvidia-dkms-595-open` | 595.91.07, open, apt `nvidia-kernel-source-595-open` 595.91.07-0ubuntu0.24.04.1 |
| kernel | 7.0.0-34-generic | 6.17.0-1017-aws |
| CUDA toolkit | 13.0 (V13.0.88; `nvcc` not on `PATH`) | see the T4 reports |
| gcc | 13.3.0 | 13.3.0 |
| stock `nvidia_uvm` srcversion | `6284DA42F15EDC3AB92332B` | `6284DA42F15EDC3AB92332B` |
| verified specasync module | `5997D238EF080B77DBD2AAF` | `5997D238EF080B77DBD2AAF` |
| E3a-2 module | `33FD42E6E16B0A6658E2BEB` | `33FD42E6E16B0A6658E2BEB` |

Earlier results (B5 to B10) were taken on driver 595.84 and, on the T4, 595.71.05; the 595.84 port no longer exists (`ARTIFACT_CATALOG.md` #23). The 5070 Ti runs for E4 onward use 595.91.07. A srcversion depends on the source files, not the kernel, so equal srcversions on the two hosts do not mean equal binaries.

## Building the modules

1. **Install git-lfs first** and fetch the patches; without it `driver/patches/*.patch` are pointer files and the build tree is assembled without the glue changes. `reconstruct_build_tree.sh` now stops with exit 2 and a message if the glue patch is a pointer:
   ```
   sudo apt install git-lfs && git lfs install && git lfs pull --include='driver/patches/*'
   ```
2. **Verified module** (needs `rsync`, `patch`, `make`, kernel headers; no sudo):
   ```
   SRC=/usr/src/nvidia-595.91.07 WORK=$HOME/specasync-work/nvidia-595.91.07-specasync-e3a \
   NV_KERNEL_MODULES="nvidia nvidia-uvm nvidia-modeset nvidia-drm nvidia-peermem" \
     driver/scripts/reconstruct_build_tree.sh
   modinfo $WORK/nvidia-uvm.ko | grep -E '^srcversion|^vermagic'   # expect 5997D238EF080B77DBD2AAF
   ```
   The full five-module set is needed because `nvidia-uvm` alone fails conftest.
3. **E3a-2 module**, overlaid on the same tree and rebuilt incrementally (from `PLATFORM_5070TI.md`):
   ```
   cp driver/src-e3a/{specasync_debugfs.c,specasync_internal.h,specasync_telemetry.h,uvm_gpu_replayable_faults.c} "$WORK/nvidia-uvm/"
   rm -f "$WORK"/nvidia-uvm/{uvm_gpu_replayable_faults.o,specasync_debugfs.o} "$WORK"/nvidia-uvm.ko
   make -C "$WORK" NV_KERNEL_MODULES="nvidia nvidia-uvm nvidia-modeset nvidia-drm nvidia-peermem" modules -j"$(nproc)"
   modinfo "$WORK/nvidia-uvm.ko" | grep -E '^srcversion|^vermagic'   # expect 33FD42E6E16B0A6658E2BEB
   ```
   The stock module is loaded by default; gate runners `rmmod` and `insmod` per run and read the srcversion back. Do not load either module on a machine you care about without reading the gate's pre-registration.

## Running one gate end to end

Every gate follows the same shape (details and exact commands in `results/analysis/REPRODUCE.md`):

1. Read the gate's `results/analysis/gate_e/<Gate>_PREREGISTRATION.md`; it fixes the cells, n, the seed, the order file's SHA-256 and the stop conditions.
2. Preflight: record kernel, driver and srcversion; the upgrade timers must be inactive; free host RAM must exceed the largest managed allocation (`ARTIFACT_CATALOG.md` #23, #11; the T4 OOM in `CATALOG_CANDIDATES_C5.md`); run from a session that will survive the isolate (`loginctl enable-linger`, detached `systemd-run --user`), never from inside a login session you will end.
3. Regenerate the order file with the gate's `*_make_order.py` and check its hash against the committed `*_order.sha256` (the runner refuses to run otherwise).
4. Smoke, then sweep, with the gate's orchestrator or runner; any stop condition ends the session and nothing is retried.
5. Run the analyzer's positive control, then the analyzer; it refuses to run unless the rows present equal the order rows minus the recorded skips.

## Environment variables (from `results/analysis/PATH_FIXES.md`)

`SPECASYNC_ROOT` (repository root), `SPECASYNC_HOME` (the `/home/ubuntu` home), `SPECASYNC_WORK` (DKMS work tree), `NV_SRC` (NVIDIA DKMS source), `SPECASYNC_USER` (owner for `chown`). Defaults are the old literal paths, so scripts behave as before unless set. `reconstruct_build_tree.sh` and `resume.sh` still default to the T4's **595.71.05** tree: set `NV_SRC` for another version. The T4 orchestrator reads `SPECASYNC_REPO` and `T4_CAP_HOURS`.

## Data policy

Raw outputs are not committed: profiler files (`*.nsys-rep`, `*.sqlite`, `*.qdrep`, `*.qdstrm`), compiled benchmark binaries, and bulk per-run ring dumps and raw run directories (`results/phaseB1/gate_e4/` to `gate_e9/` and the earlier `gate_e*` directories, see `.gitignore`). Derived data are committed: every gate's runs CSV (`e*_runs.csv`), order file and hash, analysis CSVs and reports under `results/analysis/`, and `derived/`. Every number in a claim, a figure caption or a paper section must come from a committed CSV or an evidence id (`results/analysis/consolidation/EVIDENCE_EXTRACT.md`, checked by `tests/c1_check_ids.py`); nothing is transcribed by hand.

## Status

The claims, their evidence and their scope are in **`results/analysis/CLAIM_SCOPE.md`**. Read that, not this README, for what is and is not established. Open items for the manuscript are in `results/analysis/consolidation/C5_STATUS.md`.
