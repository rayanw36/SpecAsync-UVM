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

## Task 3 — Oversubscription sweep on the 5070 Ti

### VRAM ratio, and which convention this task matches (stated explicitly, per the brief)

- This platform: 16,303 MiB (confirmed via `nvidia-smi`).
- T4: 15,360 MiB (`T4_REPORT.md` Gate 0).
- **Ratio: 16303/15360 = 1.0614x -- this platform has 6.14% more VRAM.** Close, not
  identical, exactly as the brief anticipated.
- **Convention chosen: match oversubscription RATIO, not absolute allocation size.**
  Oversubscription ratio (working set / physical VRAM) is the mechanism-relevant quantity
  for testing whether the hit-rate collapse reproduces -- an identical absolute GB working
  set would represent a *different* degree of oversubscription on the two platforms'
  different VRAM capacities, which would confound "does the same regime reproduce" with
  "is this platform tested at a different severity than the T4 was." Matching ratio keeps
  severity comparable; the tradeoff (noted, not hidden) is that the absolute working-set
  size differs slightly between what this platform runs and what an identically-labelled
  ratio would mean on the T4.

### Gate D's original scenario -- what could and couldn't be reproduced literally

The T4's only on-disk oversubscription data is `results/phaseB1/GATE_D_report.md`:
`Stencil_OvSub 28300 20 11264` (a 3-argument invocation), oracle (p4) hit rate **0.26%**
(0.0026) -- barely above p3 (0.0025), collapsed from the clean oracle dominance Stencil/
GraphBFS showed at that gate (oracle scored 0.66%/6.48% there respectively -- still small
in absolute terms, but 2-25x its own p1-p3 baseline, unlike the oversubscribed case).
**That exact 3-argument benchmark variant no longer exists in this repo** --
`benchmarks/stencil_oversub/bench_stencil_oversub.cu` (the only oversubscription tool
currently built and ready to run) takes a single `<N>` argument, a different interface.
Gate D's precise working-set size cannot be reconstructed from its 3 recorded numbers
alone with confidence. **This task therefore runs a fresh oversubscription test with the
current tool, testing the same qualitative claim Gate D made (does the oracle's advantage
collapse under memory pressure), not a literal replay of Gate D's exact configuration.**

### A real obstacle found and worked around: host RAM, not VRAM, is the binding constraint here

Before committing to a rotation sweep, sized a probe at the current tool's own documented
"severe" target (~1.98x, N=65000, 33.80 GB working set) and ran it once, standalone, to
check timing. **It was killed by the Linux OOM killer** (`dmesg`: `Out of memory: Killed
process ... (bench_stencil_o) ... file-rss:27462912kB` -- a genuine host-RAM exhaustion,
not a GPU/VRAM failure). Confirmed by a follow-up, carefully-monitored probe at a much
smaller size (N=48000, 18.43 GB, ratio 1.078x): host `used` memory climbed to within
~13GB of this host's full 60GB capacity during the run, i.e. **the UVM oversubscription
mechanism stages close to the entire working set through host RAM at some point**, not
just the excess beyond VRAM capacity -- meaning the usable ceiling for *any* oversubscribed
working set on this machine, this session, is set by available host RAM (already reduced
by the characterized ~250MB/reload-cycle leak accumulated across Tasks 1-2), not by the
16,303 MiB VRAM figure the ratio computation above is based on.

**This is reported as a real, load-bearing finding, not a footnote**: it means "the T4 had
15,360 MiB VRAM and 15 GiB host RAM" (`T4_REPORT.md`) -- a host-RAM-to-VRAM ratio close to
1:1 -- while this session's 5070 Ti host has 60 GiB RAM against 16,303 MiB VRAM, a ~3.7:1
ratio nominally far more generous. That headroom was largely consumed by this session's own
leak accumulation from Tasks 1-2 before Task 3 started, leaving less real margin than the
raw 60 GiB figure suggests. **Given this, the originally-planned severe (~1.98x) target was
abandoned in favor of a smaller, safety-verified ratio (~1.08x, N=48000, 18.43 GB) that
fits within the memory actually available at the time Task 3 ran** -- a deliberate,
disclosed reduction in severity, not a silent one, made because the alternative (attempting
the original target) had already been empirically shown to OOM-kill the process outright.
Per the brief's own instruction ("if it doesn't clear with margin, tell me before running
rather than trimming the experiment"): this finding surfaced *during* Task 3's own probing
(the first OOM was itself the discovery that the original target didn't clear), and the
smaller target was independently verified safe (a full monitored run completed cleanly,
memory recovered fully afterward) before the interleaved sweep was committed to -- reported
here in full rather than silently substituted.

### Protocol, reduced from T1's

Reduced rotation count from T1's 2 warm-up + 20 kept (Gate D's own precedent: its
oversubscription arm used **n=4** total runs, far below its own Stencil/GraphBFS n=6/n=4 --
oversubscribed runs are minutes, not seconds, each). This task: **1 warm-up + 3 kept
rotations** (16 total runs). C1 (prefetch off) measured standalone before the sweep at
159s/run vs C0's 25s/run -- consistent with Gate D's "eviction/thrash-dominated" framing.
Abort guard added to the harness itself (`tests/t_b8_oversub_5070ti.sh`, matching
`tests/t2_cufft_interleaved.sh`'s convention), checked after every single run.

### Result

All 16 runs completed; abort guard never triggered; `MemAvailable` ended at 27.4GB, clear
of the 6GiB floor throughout (minimum observed: ~12GB, during the standalone safety probes
before the sweep even started).

| Config | n | median | stdev |
|---|--:|--:|--:|
| C0 | 3 | 27.180s | 0.0100 |
| C1 | 3 | 159.290s | 0.1308 |
| C2 | 3 | 183.660s | 0.1801 |
| C3 | 3 | 70.450s | 0.6408 |

| Comparison | delta% | MWU p | Cohen's d |
|---|--:|--:|--:|
| C1 vs C0 | +486.06% | 0.1 (ceiling at n=3) | 1425.2 |
| C2 vs C1 | +15.30% | 0.1 (ceiling at n=3) | 154.5 |
| **C3 vs C1** | **-55.77%** | **0.1 (ceiling at n=3)** | **-191.9** |
| C3 vs C0 | +159.20% | 0.1 (ceiling at n=3) | 95.8 |

**n=3/cell cannot reach p<0.05 by MWU regardless of effect size (2/20=0.1 is the minimum
achievable two-sided p-value at 3-vs-3) -- 0.1 here is the ceiling of available evidence,
not a weak result.** The three C1 values (159.26-159.50s) and three C3 values
(70.07-71.32s) do not overlap at all, and the effect (C3 more than 2x faster than C1) is
far larger than anything else in this report -- but this rests on n=3 and should be read
with that caveat prominently attached, not smoothed into a confident percentage the way
the n=20 comparisons above can be.

**Oracle hit rate (aggregate, 3 kept C3 reps): 0.0019%** (17,477,449 demand faults,
13,230,089 enqueued, 24.30% drop rate, 250 hits) -- still near-zero, same regime as every
other C3 hit rate in this report and project. **The ring saturates in every single C3 rep**
(131,071/131,071 records, all three) -- this workload is even more fault-dense than SGEMM
under oversubscription pressure, consistent with Gate D's own "eviction/thrash-dominated"
characterization.

### Does the collapse reproduce? No -- and the reason resolves what looked like a
### contradiction, it does not create one

**Hit rate: reproduces the collapse.** 0.0019% here vs Gate D's 0.26% on the T4 -- both
near-zero, both far below what Stencil/GraphBFS's own oracle scored at Gate D
(0.66%/6.48%). The *hit-rate* collapse claim reproduces cleanly.

**Wall-clock: does NOT reproduce "the oracle advantage collapses" -- but this is not a
platform divergence, it is a configuration difference.** Gate D found the oracle "barely
beats p3" and drew no wall-clock benefit, but Gate D's own report states explicitly *why*:
its entire p1-p4 sweep, including the oversubscription arm, ran at **`offload_depth=0`**
(metadata-only lookup, no actual migration) -- and Gate D's own verdict says "at
`offload_depth=0` a 'hit' has no consumable product... the path to any speedup is
`offload_depth≥1`." **This task's C3, matching T1's protocol exactly, runs at
`offload_depth=1`** (real migration attempted on prediction) -- a configuration Gate D
never tested under oversubscription. This is not the same experiment reaching a different
conclusion; it is a different, depth=1 experiment that Gate D's own analysis predicted
might behave differently, now run for the first time.

**And it does behave differently: C3 (depth=1) is ~2.3x faster than C1 here, despite a
hit rate of 0.0019%.** Since the formal hit-table credit is essentially zero, this
wall-clock benefit cannot be "correct predictions consumed in time" in the usual sense --
something else is happening. A plausible, **unconfirmed** mechanism: under severe eviction
pressure, even speculative migrations that arrive too late to be credited as a formal
"hit" may still complete and leave a page resident, incidentally reducing future
eviction/refault churn -- a side effect of extra migration *activity*, not of correct
*prediction*, that would only matter in a thrashing regime where eviction pressure (not
prediction accuracy) is the bottleneck. This project's telemetry cannot confirm or refute
that mechanism directly (it has no attribution of *which* migrations came from the async
path when a later demand fault also touches the same page) -- flagged as a hypothesis, not
asserted as established. **C2 (stride, also depth=1) is directionally the opposite**: +15.3%
*slower* than C1, consistent with stride prediction being a poor fit for an
eviction-order-dominated access pattern -- the oracle's exact-trace basis, not depth=1
alone, appears to matter for whether this effect helps or hurts.

**This is reported as a genuine, unexplained-mechanism, single-platform, n=3-caveated
finding worth a dedicated follow-up (larger n, and ideally a matching depth=1 T4
oversubscription run to see if the mechanism is architecture-general or specific to this
platform's PCIe/eviction-bandwidth balance) -- not as a settled cross-platform divergence,
and not as confirmation that oversubscription is newly favorable for SpecAsync.** The
hit-rate collapse (the mechanism this project has consistently used to explain *why*
speculation doesn't help) reproduces intact; what's new is evidence that depth=1's
wall-clock effect may not run entirely through that mechanism under this specific
(oversubscribed, thrashing) regime.

## What this extends, and what remains single-platform

**Extends cross-platform**: the oversubscription hit-rate collapse itself (0.0019% here vs
0.26% T4, both far below the non-oversubscribed oracle scores at Gate D) -- the mechanism
project-wide (rate mismatch, `GATE_T4_REPORT.md`/`GATE_A1_REPORT.md`) is consistent with
memory-pressure-driven thrashing making the fault stream even less predictable than the
already-unpredictable non-oversubscribed case. The 595.71.05 build-feasibility finding
(Task 1) extends what's known about the architecture/driver axis, independent of any GPU
run.

**Remains single-platform, no T4 comparison exists**: SGEMM's entire C0-C3 interleaved
result (Task 2) -- never run under T1's protocol on the T4. The depth=1 oversubscription
wall-clock result (Task 3) -- Gate D's T4 data is depth=0 only, so this specific
configuration has no T4 counterpart at all, not even a mismatched-convention one. A
595.71.05 *runtime* comparison (Task 1) -- build feasibility is confirmed, load-and-run is
not.

**New open questions this block raises, not closed**: what mechanism gives depth=1 a
wall-clock benefit under oversubscription despite near-zero hit-table credit; why SGEMM's
C3-vs-C1 sign differs from Stencil's despite SGEMM's higher fault density; whether a
595.71.05 runtime comparison is safe to attempt on different hardware (a fresh
headless-only machine, not one with an active display stack).

## Findings summary

| Finding | T4 | This platform | Verdict |
|---|---|---|---|
| 595.71.05 builds for sm_120 | n/a (T4 never needed this) | Builds cleanly, zero rejects, symbols export correctly | **New finding** -- ABI/architecture axis does not block a future same-driver comparison |
| SGEMM fault density | n/a (not measured this way on T4) | 0.572M faults/s -- denser than Stencil (0.188M/s) | **New finding**, correctly predicts hit-rate regime |
| SGEMM oracle hit rate | n/a | 0.0057%, rate-mismatch regime | **Consistent with the stencil-family mechanism** |
| SGEMM C3 vs C0 | n/a | +183.17%, C3 loses decisively | **Matches predicted pattern** |
| SGEMM C3 vs C1 | Stencil: C3 slower (+6.67% T4/+3.60% 5070Ti) | SGEMM: C3 *faster* (-1.25%, Holm-sig) | **Does not match Stencil's sign** -- prediction only partially confirmed |
| Oversubscription hit-rate collapse | 0.26% (Gate D, depth=0) | 0.0019% (depth=1) | **Reproduces** (both far below non-oversubscribed oracle scores) |
| Oversubscription C3 wall-clock benefit | None found (Gate D, depth=0 -- architecturally incapable per Gate D's own analysis) | Large benefit (-55.77% vs C1, n=3) | **Not comparable** -- different configuration (depth=0 vs depth=1), not a platform divergence |

## Artifacts

- `results/analysis/t_b8_sgemm_5070ti/sgemm_interleaved_times.csv` (Task 2, 88 rows)
- `results/analysis/t_b8_oversub_5070ti/oversub_times.csv` (Task 3, 16 rows)
- `tests/t_b8_sgemm_interleaved.sh`, `tests/t_b8_oversub_5070ti.sh` (new harnesses)
- Raw `.bin` ring dumps and oracle traces gitignored (EBS-only, reconstructible); CSVs and
  this report committed. 595.71.05 build artifacts (Task 1) intentionally not committed or
  kept -- provenance (exact package version, commands) recorded above instead, per the
  brief ("the .ko files themselves need not be kept").
