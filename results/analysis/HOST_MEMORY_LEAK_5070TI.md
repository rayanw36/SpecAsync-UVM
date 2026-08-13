# Host memory leak characterization — RTX 5070 Ti, driver 595.84

Scope note: this is a characterization pass, not a debugging project. Timeboxed to the five
questions below; no ftrace, no kmemleak build, no bisection of the driver source. Ran on a
freshly rebooted host (today, 2026-08-13, boot starting 14:20 local) so all measurements
start from a clean baseline, not from the accumulated state of the Task 4 crisis.

Tooling: `tests/leak_probe.sh` (new, ad hoc, not a standing gate harness) — reload/run
cycles instrumented with `/proc/meminfo` snapshots before and after each cycle. Raw data:
`results/analysis/leak_probe/leak_probe.csv`.

## 1. Quantify precisely

Four conditions, n=5 cycles minimum per condition (reload_cufft got 15 across three batches
because it doubled as the input to Part 2's slabinfo diff and Part 3's stock comparison —
folded in here rather than discarded). Leak size per cycle = `MemFree` before minus
`MemFree` after (kB), converted to MB.

| Condition | n | median MB/cycle | range MB/cycle |
|---|--:|--:|--:|
| reload-only (rmmod/insmod, no CUDA run) | 5 | **-0.1** | -0.7 to +92.8 |
| reload + `bench_cufft` (134217728 elements) | 15 | **250.6** | 221.6 to 323.0 |
| reload + `bench_stencil` (N=24000) | 5 | **231.9** | 228.9 to 297.5 |
| CUDA run with **no** reload between runs (1 reload, then 5x `bench_cufft`) | 5 | **-1.9** | -25.9 to +225.4 |

Reload-only and no-reload-CUDA are both indistinguishable from zero (one outlier each,
+92.8MB and +225.4MB respectively, both first-in-batch — plausibly page-cache warm-up
noise, not leak; neither condition shows a consistent per-cycle climb the way the two
reload+workload conditions do). **The leak requires both a reload and a CUDA run in the
same cycle** — reload alone doesn't do it, and repeated CUDA execution against one
already-loaded module doesn't do it either. This isolates the leak to whatever happens when
a fresh module instance sets up its UVM state for a CUDA context (fault handling, GPU MMU
page tables, VA-space registration) and then tears down — the combination, not either half
alone.

Confirms the original ~250MB/cycle estimate from the Task 4 crisis: median 250.6MB/cycle on
cuFFT (n=15), 231.9MB/cycle on Stencil (n=5) — same order of magnitude, workload-independent
within noise.

## 2. Locate it, cheaply

Full `/proc/meminfo` diffed before/after a 5-cycle `reload_cufft` batch (~1.36GB total
consumed, ~273MB/cycle for that particular batch):

| Field | before (kB) | after (kB) | delta |
|---|--:|--:|--:|
| MemFree | 52,335,720 | 50,969,976 | **-1,365,744** |
| Slab | 465,988 | 465,972 | -16 |
| SUnreclaim | 275,832 | 275,816 | -16 |
| SReclaimable | — | — | 0 (noise-level) |
| KernelStack | 21,120 | 21,232 | +112 |
| VmallocUsed | 176,124 | 176,220 | +96 |
| PageTables | 41,004 | 41,368 | +364 |
| AnonPages | 2,588,828 | 2,639,164 | +50,336 |
| Mapped | 952,204 | 952,320 | +116 |
| Cached | 2,991,100 | 2,991,436 | +336 |

None of the named, tracked pools move by more than ~50MB combined — two orders of magnitude
short of the 1.37GB `MemFree` drop. Computing `unaccounted = MemTotal - (MemFree + Buffers +
Cached + SwapCached + Slab + KernelStack + PageTables + VmallocUsed + SecPageTables +
Percpu)`: **7,104,856 kB before → 8,469,568 kB after, delta +1,364,712 kB — 99.98% of the
missing memory lands in "unaccounted."**

`echo 3 | sudo tee /proc/sys/vm/drop_caches` was run after this accumulation: `buff/cache`
dropped from 3.2GiB to 934MiB (the reclaimable page cache emptied as expected), but `used`
memory did not move (8.9GiB → 8.8GiB, within rounding). **The leaked memory is not
reclaimable page cache and is not attributed to Slab/SUnreclaim/KernelStack/VmallocUsed/
PageTables.** It is raw, unaccounted, non-reclaimable growth — the signature of memory
allocated directly via the page allocator (e.g. `alloc_pages`/DMA-mapped buffers such as GPU
fault-handling scratch space or page-table storage for the GPU MMU) that bypasses the
slab/vmalloc accounting paths `/proc/meminfo` tracks by name, and is never freed on
`rmmod`.

(`DirectMap1G` dropped by exactly 1GB with a matching rise in `DirectMap2M`/`DirectMap4k` —
this is the kernel's own physmap being re-split to smaller page granularities, unrelated to
the leak's magnitude; it reflects `set_memory_*`-style attribute changes on some region of
physical memory, not additional memory consumption. Noted for completeness, not pursued
further per the timebox.)

## 3. Is it ours?

Stock `nvidia-uvm.ko` (the DKMS-installed 595.84 module currently active on this host after
every reboot, `/lib/modules/.../updates/dkms/nvidia-uvm.ko.zst`, srcversion
`F1940EC6EED67E9D19C5F00` — confirmed distinct from the SpecAsync build's srcversion
`9E98EF08CBA769C50A24937`), 5 reload+`bench_cufft` cycles, same size, `uvm_perf_prefetch_
enable=1` (the only parameter it accepts that's relevant here — no `specasync_*` params
exist on this build):

| Module | n | median MB/cycle | range MB/cycle |
|---|--:|--:|--:|
| SpecAsync build (`nvidia-595.84-specasync/nvidia-uvm.ko`) | 15 | 250.6 | 221.6 – 323.0 |
| **Stock DKMS build** | 5 | **241.2** | 238.9 – 326.2 |

**Not ours.** The stock, unmodified 595.84 driver leaks at statistically the same rate as
the SpecAsync-patched build — medians 8% apart, well inside the SpecAsync build's own
cycle-to-cycle spread (221.6–323.0MB). This rules out `specasync_log_enabled`'s ring buffer,
the custom telemetry structs, or any other SpecAsync-specific allocation as the cause (the
stock module has none of that code and leaks anyway). **This is an upstream NVIDIA
595.84-driver behavior, not a defect introduced by this project's kernel patches** — it
should be documented in the manuscript as a driver-version limitation affecting the
measurement protocol, not as a limitation of the SpecAsync prototype itself.

Module was reloaded back to the SpecAsync build immediately after this test (srcversion
verified `9E98EF08CBA769C50A24937`) to leave the host in its working state.

## 4. Threat-to-validity analysis

Using the combined reload+CUDA-run median (247.35MB/cycle, n=20, pooling the cuFFT and
Stencil samples from Part 1) for mixed-workload sessions, and the workload-specific medians
for single-workload sessions. Starting free memory: this host has shown **~55GB free
immediately after a fresh reboot** twice independently (today's boot, and the boot before
Task 3 — Task 3's own report already recorded "post-reboot, `free -h` showed a clean 55GB").

| Session | Runs | Workload | Boot | Assumed start free | Rate used | Predicted cumulative leak | Predicted end free |
|---|--:|---|---|--:|--:|--:|--:|
| B5 | 176 | Stencil + GraphBFS | fresh (boot -2) | 55GB | 247.35MB (combined) | 42.5GB | **~12.5GB** |
| Task 3 | 44 | Stencil only | fresh (boot -1) | 55GB | 231.9MB (stencil) | 10.2GB | **~44.8GB** |
| Task 4 | 108 (of 204 target) | cuFFT only | same boot -1, right after Task 3 | ~45GB (Task 3's predicted end) | 250.6MB (cufft) | 24.5GB | **~20.5GB** |

Cross-check against what was actually observed: Task 4's own session notes recorded ~14GB
used (≈46GB free) at Task 4's start, right after Task 3 finished — matches the model's
~44.8GB prediction closely. By the time Task 4 was manually stopped at run 108, used memory
had climbed to 36–41GB (≈19–24GB free) during live monitoring, and further diagnostic reload
cycles run immediately afterward pushed it to ~44.5GB used (≈15.5GB free) before the
investigation stopped — bracketing the model's ~20.5GB prediction at run 108 well. The model
is not exact (it doesn't account for the extra diagnostic cycles run after the 108th
production run, or baseline idle overhead), but it reproduces the observed trajectory
closely enough to trust for run-index projections.

**Extrapolating Task 4's own rate forward to the full 204-run target from its actual ~45GB
start**: predicted crossing of a 10GB-free "tight" threshold at run **#143**, and a 2GB-free
"critical" threshold at run **#176** — both *inside* the 204-run target. This is why Task 4
could not complete under Task 3's leftover memory budget: the math says it was never going
to reach run 204 without hitting a wall, independent of the exact stopping point chosen.
**From a fresh 55GB reboot**, the same 204-run extrapolation predicts ending at ~5GB free
(55GB − 204×250.6MB ≈ 5.0GB) — tight, but the "critical" 2GB threshold isn't predicted to be
crossed until run ~219, past the 204-run target. A fresh-boot resume is therefore
projected to complete, with a real but small margin.

### Does this explain B5's run-order drift (rho=0.548, p=0.0123)?

Reported as a candidate explanation, not a proven cause — per the addendum already appended
to `GATE_B6_TASK3_A2_REPLICATION.md`, Task 3's non-reproduction of this drift was originally
framed as plain session-to-session noise. This leak gives a second, mechanistic candidate
that doesn't require invoking unexplained noise.

**Supporting evidence:**
- Direction matches: B5's drift is upward (later runs slower), consistent with degrading
  free memory increasing allocation/migration cost over the course of a session.
- B5's predicted cumulative consumption (42.5GB of a 55GB budget, ~77%) means memory
  pressure plausibly built up meaningfully over its 176 runs — unlike Task 3, whose 44 runs
  predicted only ~19% of budget consumed, staying comfortably clear of any pressure zone
  throughout. A mechanism that needs meaningful pressure to manifest is consistent with
  "shows up in B5, doesn't show up in Task 3."
- The leak mechanism is confirmed real and active throughout the boot B5 ran on: `journalctl`
  for that boot (boot -2, 2026-08-12 10:52–23:57) shows genuine kernel OOM-killer events at
  23:25 and 23:26 that same boot, killing `bench_stencil` processes directly — hours after
  B5 itself completed and was committed (15:03), during later work on the same
  never-rebooted session. The crisis this investigation was launched to explain is the same
  boot B5 ran on, just later in it.

**Non-supporting evidence:**
- B5's drift was only significant for Stencil-24K's position-independence check; the same
  check on GraphBFS-23 in that report was not significant (rho=0.229, p=0.332). A session-
  wide, monotonically-building memory-pressure effect would be expected to leave *some*
  trace in both workloads' run-order correlation, not appear cleanly in one and not the
  other — though GraphBFS's own noise floor could simply be masking a smaller effect there,
  so this doesn't rule the mechanism out.
- This characterization only measured the leak rate at low-to-moderate memory pressure
  (starting from ~55GB free, ending each condition batch well above any critical threshold).
  Whether the per-cycle rate stays constant as free memory shrinks toward exhaustion, or
  accelerates (reclaim/compaction overhead rising near the watermark), was not tested here
  (out of scope per the timebox). A smoothly constant rate predicts a smooth monotonic
  drift across the *whole* run sequence, matching B5's clean Spearman correlation; an
  accelerating/cliff-like rate would predict drift concentrated in the tail instead — the
  data as measured can't distinguish these, so the "clean linear correlation across all 176
  runs" observation is only weak support for the smooth-rate version of this story.
- Task 3's non-reproduction is equally consistent with the original "single-session,
  unreplicated noise" explanation already on record. Nothing here uniquely favors the
  memory-pressure account over that simpler one — both predict the same observation (no
  drift in a low-pressure, freshly-booted 44-run session).

**Verdict: plausible, mechanistically grounded, but not established.** Worth carrying in the
manuscript as a candidate explanation for B5's drift, explicitly flagged as unconfirmed —
not as a resolution of it.

## 5. T4 exposure

No new T4 runs — the instance is down. This section uses only what's already committed:
`results/analysis/T4_REPORT.md`, `results/phaseB/gate_reports/gate0_env.md`, the four
`GATE_T{1,2,3,4}_REPORT.md` files, and the raw harness logs in
`results/analysis/t4_run_logs/`.

**Platform:** `g4dn.xlarge`, Tesla T4, driver **595.71.05** (same 595.x release family as
this host's 595.84, different minor version), kernel `6.17.0-1019-aws`, **15 GiB host RAM**
(`T4_REPORT.md`, `gate0_env.md`).

**What the logs show about memory:** nothing directly. No T4 report or raw log captures
`/proc/meminfo`, `free`, or any host-RAM figure at any point — every memory-related line
found (`GATE_T4_REPORT.md`: "0 MiB GPU memory leaked at completion") refers to **GPU VRAM**
via `nvidia-smi`-style accounting, not host RAM. The T4 harnesses never instrumented host
memory the way `leak_probe.sh` does now. **Direct confirmation is impossible from existing
data — this question is open, not answered, by design of what was originally collected.**

**What can be inferred indirectly:** the four raw run logs (`t1_run.log` through
`t4_run.log`) carry continuous timestamps from 13:01:03 to 19:32:21 on 2026-08-10, with no
gap consistent with a reboot — a single ~6.5-hour session covering all of T1 (176 runs), T2
(204 runs, run twice — the depth=1 version was discarded but its reload cycles still
happened — so ~408 reload cycles from T2 alone), T3 (30 runs), and T4 (60 runs): **well over
650 reload+CUDA-run cycles in one continuous boot.** At this host's measured ~247MB/cycle
rate, 650 cycles would consume ~157GB — over 10x the T4 instance's entire 15GiB of RAM.
Every one of those four gates completed and was published with no report of a crash, OOM, or
mid-session restart, and dmesg was explicitly checked clean in multiple reports. **This is
strong indirect evidence that this leak, at anything close to the rate measured on this
host, was not present on the T4/Turing/595.71.05 platform** — consistent with the leak being
specific to driver 595.84 and/or this host's Blackwell (sm_120) architecture, rather than a
595.x-family-wide behavior. This is inference from absence of failure, not a measurement —
stated as the best available answer given the instance is gone, not as settled fact.

## Verdict

1. **Confirmed and quantified**: ~230-250MB leaked per (reload + CUDA-run) cycle, needs both
   halves together, workload-independent (cuFFT and Stencil agree within noise).
2. **Located to "unaccounted"**: not Slab, not SUnreclaim, not KernelStack, not Vmalloc, not
   PageTables, not reclaimable page cache — raw non-reclaimable growth outside meminfo's
   named pools, consistent with driver-side page-allocator allocations (e.g. GPU MMU page
   tables / fault-handling scratch) never freed on unload.
3. **Not a SpecAsync defect**: the stock, unpatched 595.84 driver leaks at the same rate.
   Upstream NVIDIA issue; belongs in the manuscript as a measurement-protocol limitation on
   this driver version, not as a prototype limitation.
4. **Plausible but unconfirmed contributor to B5's run-order drift** — real mechanism,
   right direction, right order of magnitude, but the evidence is mixed (doesn't explain
   GraphBFS's null) and doesn't rule out the simpler single-session-noise account already on
   record.
5. **T4 exposure is an open question** — no direct evidence either way, but indirect
   evidence (650+ reload cycles surviving a 15GiB host in one session) weighs against the
   same leak, at the same rate, having been present there.

Task 4 resumes from rep 1 next, unmodified reload-every-run protocol, from a fresh reboot —
per Part 4's projection this has a small but real margin to complete all 204 runs.
