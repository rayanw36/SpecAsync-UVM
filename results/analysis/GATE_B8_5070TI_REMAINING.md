# Gate B8 — remaining 5070 Ti experiments (595.71.05 build check, SGEMM, oversubscription)

**Platform: RTX 5070 Ti, sm_120 Blackwell, driver 595.84, srcversion
`9E98EF08CBA769C50A24937`. Not the T4.** Ran headless (`systemctl isolate
multi-user.target`) throughout. Every T4 figure below is quoted from the cited report,
never presented as measured here.

## Task 1 — 595.71.05 build feasibility (build only, not loaded)

**Result: builds cleanly. Not loaded, per the brief — the running driver stack stays
595.84 throughout.**

### Provenance (recorded before the scratchpad build tree is cleaned up)

- Package: `nvidia-kernel-source-595-server-open`, version **595.71.05-0ubuntu0.24.04.1**
  (Ubuntu `noble-updates`/`noble-security`, multiverse) -- the same driver version number
  the T4 ran.
- Download (no root, no install, no dkms interaction):
  ```
  apt-get download nvidia-kernel-source-595-server-open
  dpkg-deb -x nvidia-kernel-source-595-server-open_595.71.05-0ubuntu0.24.04.1_amd64.deb extracted/
  ```
- Source tree used for the build: `extracted/usr/src/nvidia-595.71.05/`, rsynced into a
  scratch `WORK` directory.
- Patch applied cleanly, zero rejects, all 8 files:
  ```
  patch -p4 -d "$WORK" < driver/patches/specasync_uvm_v595.71.05.patch
  ```
  (`-p4` strips `/opt/dlami/nvme/work/nvidia-595.71.05-specasync/` down to the tree-relative
  path; verified first with `--dry-run` at `-p4`/`-p5`/`-p6`, only `-p4` matched cleanly.)
- Build invocation (same pattern as the working 595.84 build this project already uses):
  ```
  cd "$WORK"
  make NV_KERNEL_MODULES="nvidia nvidia-uvm" modules -j24
  ```
  Exit code 0. `nvidia.ko` (36,431,504 bytes) and `nvidia-uvm.ko` (57,759,376 bytes)
  produced. `modinfo`: `version: 595.71.05`, `vermagic: 7.0.0-28-generic SMP preempt
  mod_unload modversions`.

### Findings

- **595.71.05 already ships Blackwell HAL files** (`uvm_blackwell.c`,
  `uvm_blackwell_host.c`, `uvm_blackwell_ce.c`, `uvm_blackwell_fault_buffer.c`, GB20x
  references in `uvm_hal.h`) -- this driver version is not a pre-Blackwell release being
  force-ported; it already has source-level Blackwell/sm_120 awareness.
- **The patch applies with zero rejects** against the pristine 595.71.05 tree.
- **The specasync symbols export correctly**: `nm nvidia-uvm.ko` shows
  `specasync_debugfs_init` with proper `__ksymtab`/CRC entries -- the patched module built
  as a coherent whole, not just "the stock driver happened to compile."
- All build-log "error"-matching lines individually checked: every one is a function name
  (`gpuHandleSanityCheckRegReadError`, etc.) inside benign `objtool`/MITIGATION_RETHUNK
  "naked return" warnings, the same class already seen and accepted on the working 595.84
  build. No real compile errors. Remaining warnings are cosmetic
  (`-Wmissing-prototypes`, `-Wexpansion-to-defined`) in both stock files and the specasync
  additions.

### Conclusion, stated precisely

**The architecture/ABI axis is not what blocks a same-driver T4-vs-5070-Ti comparison.**
Nothing structural (missing sm_120 support, ABI mismatch, conftest failure) prevents
595.71.05 from building for this platform. What blocks it is (a) the risk to this
machine's *active* 595.84 display stack from loading a different UVM module against a
595.84 `nvidia.ko` (per the brief, not attempted), and (b) the kernel version this build
targeted (`7.0.0-28-generic`, this machine's running kernel) vs whatever the T4 actually
ran, which was not independently re-verified here. **A same-driver comparison is
structurally feasible but untested at runtime -- this is not a claim that it would work,
only that nothing found here rules it out.** Confirming it would require an actual
load-and-run session on a machine where the risk to a live display stack doesn't apply
(e.g. a fresh headless boot, or a disposable instance), which this session did not attempt.

## Task 2 — SGEMM on the 5070 Ti

New script `tests/t_b8_sgemm_interleaved.sh`, deliberately separate from
`tests/t1_gate3_interleaved.sh` rather than parameterizing it over a third benchmark
(matches this project's existing convention of one harness per gate). Same protocol as T1
exactly: rotation C0,C1,C2,C3 never blocked, 2 warm-up + 20 kept rotations, module reload
before every run, `setarch -R` throughout, fresh oracle trace collected on this machine
(799,062 entries -- not reused from anywhere). `bench_sgemm 24000` (matches the largest
SGEMM size used elsewhere in this project). Module srcversion
`9E98EF08CBA769C50A24937` throughout. **Memory budget, projected before running**: 88
runs, 1 reload each, ~250MB/cycle characterized leak -> ~22GB against ~48GB available at
the start; ran to completion at `MemAvailable` 32.15GB, comfortably clear.

### Fault density, measured before the interleaved run -- the prediction

Single reload+run, policy=0 depth=0 prefetch=0 (matching the convention already used to
derive the Task 3/corrected Stencil-24K and GraphBFS-23 rates), `bench_sgemm 24000`:
ring saturated **within this single run** (131,071/131,071 records, batch_id 0-131070
contiguous, non-wrapped) -- itself informative before any rate arithmetic: Stencil-24K's
own ring didn't saturate until partway through its *second* rep. Rate computed from the
captured (pre-saturation) window only, same span-based method as the fault-rate
correction: 1,656,038 faults over a 2.893s span = **572,431 faults/s (0.572 M/s)**.

**This is denser than Stencil-24K's corrected 0.188 M/s and far denser than GraphBFS-23's
0.00765 M/s -- SGEMM sits nearer the stencil family, in fact past it, not nearer
GraphBFS.** Stated prediction, before running the interleaved protocol: SGEMM should show
the stencil-family failure pattern -- near-zero oracle hit rate (rate-mismatch dominated,
per `GATE_T4_REPORT.md`/`GATE_A1_REPORT.md`'s corrected mechanism), C3 losing decisively
to C0 (stock prefetcher dominance), and no wall-clock benefit from speculation anywhere in
the C0-C3 comparison set.

### Result

| Config | n | median | stdev | min | max |
|---|--:|--:|--:|--:|--:|
| C0 | 20 | 4.605s | 0.0117 | 4.590s | 4.640s |
| C1 | 20 | 13.205s | 0.0332 | 13.140s | 13.270s |
| C2 | 20 | 13.520s | 0.0391 | 13.450s | 13.620s |
| C3 | 20 | 13.040s | 0.0659 | 12.950s | 13.170s |

| Comparison | delta% | MWU p | Holm-sig (family=3) | Cohen's d |
|---|--:|--:|:--:|--:|
| C3 vs C0 | +183.17% | 5.66e-08 | YES | 178.30 |
| C2 vs C1 | +2.39% | 6.38e-08 | YES | 8.62 |
| **C3 vs C1** | **-1.25%** | **1.28e-07** | **YES** | **-3.04** |

**Oracle hit rate (aggregate, 20 kept C3 reps): 0.0057%** (31,863,883 demand faults,
19,828,009 enqueued, 37.77% drop rate, 1,125 hits) -- near-zero, in the same regime as
Stencil-24K (0.0002-0.02% across various reports), nowhere near GraphBFS-23's 0.0025-0.25%.

**Does C3 ever beat C1 or C0? Beats C1 (barely); does not beat C0.** C3 loses decisively to
C0 (+183.17%, stock prefetcher dominance -- matches the stencil-family pattern predicted).
But unlike Stencil-24K (T1: C3 significantly *slower* than C1, +6.67% T4 / +3.60% 5070 Ti,
per `CLAIM_SCOPE.md` claim 7), SGEMM's C3 is **significantly *faster* than C1** here
(-1.25%, Holm-significant, n=20/cell) -- a real, reproducible effect at this sample size,
not noise (MWU p=1.28e-07), but a practically tiny one (0.165s on a 13s runtime) whose
significance comes from exceptionally tight variance (stdev 0.03-0.07s), the same pattern
already characterized elsewhere in this project as "statistically significant, practically
negligible."

### Verdict: prediction partially confirmed

**Confirmed**: near-zero hit rate (0.0057%, rate-mismatch regime as predicted), C3 loses
decisively to C0 (stock prefetcher still dominates, as predicted). **Not confirmed**: the
prediction that SGEMM's C3-vs-C1 comparison would follow Stencil's pattern (C3 significantly
*slower*) -- instead it shows a small but real *faster* result, a genuinely different
outcome from Stencil despite SGEMM's higher fault density. The density measurement correctly
predicted the *hit-rate regime* (both near-zero, rate-mismatch dominated) but not the
*sign* of the C3-vs-C1 wall-clock comparison -- fault density alone is not sufficient to
predict that sign; something else (SGEMM's compute/access pattern, matrix-multiply's
different cache/coalescing behavior vs. stencil's ping-pong pattern) evidently matters too,
and this data cannot isolate what. Reported as a genuine, only-partial confirmation, not
smoothed into "prediction held."

**Not comparable to a T4 figure** -- SGEMM was never run under T1's interleaved protocol on
the T4 (`run_robust.py`'s Phase B sweep covered SGEMM at N=8192/16384/24000 under a
different, non-interleaved, mean-of-many-runs convention -- not on the same basis as this
table). This is a first-time C0-C3 interleaved SGEMM measurement, single-platform.
