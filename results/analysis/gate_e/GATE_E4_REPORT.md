# Gate E4 — Final sweep: cheap oracle, width, and off-path vs in-path

## ⚠️ FALSIFICATION TRIGGER FIRED

**On Stencil-24K, C7-W512 beats the driver as it ships (C0) by 0.0557 s
(−4.93%).**

| | |
|---|---|
| medians | C0 1.1295 s; C7-W512 1.0738 s |
| test | two-sided MWU p = 1.08 × 10⁻⁵, the smallest attainable at 10 vs 10 (complete separation: the slowest C7-W512 run, 1.0937 s, is faster than the fastest C0 run, 1.1077 s) |
| Holm | significant (threshold 0.00294) |
| MDE | 0.0144 s; 0.0197 s at α/18. The effect is 3.9× the MDE. |
| Cohen's d | −4.61 |
| without outliers | −0.0559 s, p = 2.2 × 10⁻⁵, Holm-significant |

C7-W512 is:
- the first-touch oracle (policy 6, depth 1, L = 4096);
- with the cheap constant-time lookup (`specasync_ft_fast=1`);
- migrating the whole 2 MB VA block per speculative call (`specasync_spec_width=512`);
- **with the stock prefetcher left on.**

**The paper's central claim, that speculation cannot improve the driver as
it ships, no longer holds in that form.** It is falsified on Stencil-24K on
this platform.

It is **not** falsified on GraphBFS-23: no F1 arm differs significantly from
C0 there. C7-W512 vs C0 is −0.06% (p = 0.53), against an MDE of 0.087 s
(≈0.28%).

**Per the pre-registration, nothing further is run.** No extra cells, no
follow-up configurations, no confirmation run.

The pre-registered F1 results are:

| workload | C7-W1 vs C0 | C7-W64 vs C0 | C7-W512 vs C0 |
|---|---|---|---|
| Stencil-24K | **+5.87%, slower** (Holm-sig) | −1.83%, n.s. (p = 0.089) | **−4.93%, faster** (Holm-sig; trigger) |
| GraphBFS-23 | −0.28%, n.s. | −0.10%, n.s. | −0.06%, n.s. |

Speculation with the cheap oracle at single-page width is still slower than
the shipped driver on Stencil. Only whole-block width crosses over.

Platform for every number: RTX 5070 Ti, driver 595.91.07, kernel
7.0.0-34-generic. Module `nvidia-uvm-specasync-NEW-e3a2-width-ftfast.ko`
(srcversion `33FD42E6E16B0A6658E2BEB`) in every arm. Pre-registration:
`E4_PREREGISTRATION.md` (commit `aed1f7f`, before the first sweep run).
Status log: `E4_STATUS.md`.

## Step 0–1 — Preflight and smoke tests

- **Step 0:** push level with origin; preflight passed, with both module
  srcversions and sha256s recorded (`E4_STATUS.md`).
- **Step 1:** all 7 never-run combinations ran once each with no stop
  condition. Both identities are exact, and pages per migration are 64.00 /
  511.6–511.9. Smoke wall-clock is in `e4/smoke_runs.csv` and is excluded
  from all analysis.

## Step 3 — Run integrity

```
rows 200 / 200
order adherence: 200 / 200 in sequence; mismatches []
srcversions ['33FD42E6E16B0A6658E2BEB']; exit codes ['0']
dmesg new lines: total 0; runs with any: []
MemAvailable kB before 59984124-61574028 after 59755476-61315340; first 60256940 last 61130168
disk free GB min 37.8
ring coverage 100% on 200 / 200 runs; max records 75194
Identity 1 (demand_faults = pred+held+unk+exh+giveup) holds on 160 / 160; fails []
Identity 2 (pred = same_region+enqueued+drops) holds on 160 / 160; fails []
ft_fast_verified = 1 on 120 / 120 fast loads; cas_giveup max 0; region_invalid max 0
```

- Every fast = 1 load verified the range index (Stencil 2 ranges, GraphBFS
  19).
- `ft_fast_cas_giveup` and `spec_region_invalid` are 0 on all 200 runs.
- Identity 1 uses `demand_faults` as its left side because
  `trace_faults=0`, as pre-registered and validated in E3b.

**Interruption (not a stop condition), full evidence in `E4_STATUS.md`:**
- After run 62, the user shut the machine down from tty1 (`sudo shutdown
  now`, 00:48:41) while run 63 was in progress. The shutdown was orderly
  (`systemd-poweroff`).
- The previous boot has no stop-pattern, NVRM or Xid kernel line.
- Run 63 produced no row. Whether its benchmark was still executing or the
  runner had already been terminated with the previous Claude Code session
  **could not be determined**.
- After the reboot:
  - the post-reboot preflight passed;
  - a **table-validity check** showed the `setarch -R` address layout
    identical across the reboot (same page sets, first-touch order drift
    98 / 35,823 ranks against 96 / 37,992 between two pre-reboot
    collections);
  - the sweep **resumed at run 63** per the pre-registered resume rule;
  - run 63 then completed normally.
- Runs 1–62 are pre-reboot and 63–200 post-reboot. Exploratory item 1
  checks that the trigger result is not a boot artifact.

## Step 4 — Results (pre-registered)

### The 18 primary comparisons (one Holm family)

| family | workload | comparison | median baseline (s) | median arm (s) | Δ (s) | Δ % | MWU p | Holm thr | verdict | Cohen's d | MDE (s) | MDE α/18 (s) | without outliers: Δ / p / Holm-sig (n) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 | stencil | C7-W1 vs C0 | 1.1295 | 1.1958 | +0.0663 | +5.87% | 1.08e-05 | 0.00278 | **C7-W1 slower** | +4.54 | 0.0194 | 0.0266 | +0.0661 / 2.2e-05 / yes (9/10) |
| F1 | stencil | C7-W64 vs C0 | 1.1295 | 1.1089 | -0.0206 | -1.83% | 8.92e-02 | 0.00714 | no significant difference | -1.04 | 0.0201 | 0.0274 | -0.0209 / 6.5e-02 / no (9/10) |
| F1 | stencil | C7-W512 vs C0 | 1.1295 | 1.0738 | -0.0557 | -4.93% | 1.08e-05 | 0.00294 | **C7-W512 faster** ⚠️ **TRIGGER** | -4.61 | 0.0144 | 0.0197 | -0.0559 / 2.2e-05 / yes (9/10) |
| F2 | stencil | C7-W1 vs C7-slow-W1 | 1.2205 | 1.1958 | -0.0247 | -2.03% | 2.32e-02 | 0.00625 | no significant difference | -1.23 | 0.0221 | 0.0302 | -0.0200 / 8.3e-02 / no (8/10) |
| F2 | stencil | C6-W1 vs C6-slow-W1 | 4.1038 | 3.8822 | -0.2216 | -5.40% | 1.08e-05 | 0.00313 | **C6-W1 faster** | -9.80 | 0.0280 | 0.0383 | -0.2183 / 2.2e-05 / yes (9/10) |
| F3 | stencil | C6-W1 vs C1 | 4.2986 | 3.8822 | -0.4164 | -9.69% | 1.08e-05 | 0.00333 | **C6-W1 faster** | -19.85 | 0.0261 | 0.0358 | -0.4162 / 2.2e-05 / yes (9/10) |
| F3 | stencil | C6-W64 vs C1 | 4.2986 | 3.3693 | -0.9294 | -21.62% | 1.08e-05 | 0.00357 | **C6-W64 faster** | -64.46 | 0.0182 | 0.0249 | -0.9292 / 2.2e-05 / yes (9/10) |
| F3 | stencil | C6-W512 vs C1 | 4.2986 | 3.2975 | -1.0011 | -23.29% | 1.08e-05 | 0.00385 | **C6-W512 faster** | -62.71 | 0.0199 | 0.0273 | -1.0009 / 2.2e-05 / yes (9/10) |
| F4 | stencil | C6-W512 vs C0 | 1.1295 | 3.2975 | +2.1680 | +191.95% | 1.08e-05 | 0.00417 | **C6-W512 slower** | +147.67 | 0.0184 | 0.0252 | +2.1678 / 2.2e-05 / yes (9/10) |
| F1 | graphbfs | C7-W1 vs C0 | 31.5513 | 31.4619 | -0.0894 | -0.28% | 3.53e-01 | 0.01250 | no significant difference | -0.39 | 0.1351 | 0.1848 | -0.0894 / 3.5e-01 / no (10/10) |
| F1 | graphbfs | C7-W64 vs C0 | 31.5513 | 31.5199 | -0.0313 | -0.10% | 4.81e-01 | 0.02500 | no significant difference | -0.30 | 0.1323 | 0.1810 | -0.0313 / 4.8e-01 / no (10/10) |
| F1 | graphbfs | C7-W512 vs C0 | 31.5513 | 31.5322 | -0.0190 | -0.06% | 5.29e-01 | 0.05000 | no significant difference | -0.29 | 0.0873 | 0.1194 | -0.0190 / 5.3e-01 / no (10/10) |
| F2 | graphbfs | C7-W1 vs C7-slow-W1 | 31.5011 | 31.4619 | -0.0392 | -0.12% | 3.93e-01 | 0.01667 | no significant difference | -0.15 | 0.1465 | 0.2004 | -0.0384 / 6.0e-01 / no (9/10) |
| F2 | graphbfs | C6-W1 vs C6-slow-W1 | 33.1379 | 33.0734 | -0.0645 | -0.19% | 1.65e-01 | 0.00833 | no significant difference | -0.60 | 0.1888 | 0.2583 | -0.0645 / 1.7e-01 / no (10/10) |
| F3 | graphbfs | C6-W1 vs C1 | 33.0890 | 33.0734 | -0.0156 | -0.05% | 3.15e-01 | 0.01000 | no significant difference | -0.42 | 0.1629 | 0.2229 | -0.0150 / 4.5e-01 / no (9/10) |
| F3 | graphbfs | C6-W64 vs C1 | 33.0890 | 32.8775 | -0.2115 | -0.64% | 4.33e-05 | 0.00556 | **C6-W64 faster** | -2.44 | 0.1296 | 0.1773 | -0.2109 / 8.7e-05 / yes (9/10) |
| F3 | graphbfs | C6-W512 vs C1 | 33.0890 | 32.7692 | -0.3198 | -0.97% | 1.08e-05 | 0.00455 | **C6-W512 faster** | -3.07 | 0.1337 | 0.1830 | -0.3192 / 2.2e-05 / yes (9/10) |
| F4 | graphbfs | C6-W512 vs C0 | 31.5513 | 32.7692 | +1.2179 | +3.86% | 1.08e-05 | 0.00500 | **C6-W512 slower** | +12.95 | 0.1199 | 0.1641 | +1.2179 / 1.1e-05 / yes (10/10) |

1.08e-5 is the smallest two-sided exact p at 10 vs 10. MWU was exact
throughout (no ties). Excluding Tukey-flagged runs changes **no verdict**.

### Central figure

`e4_wallclock_by_arm.png` / `.pdf`: wall-clock per arm, one panel per
workload, C0 and C1 as horizontal lines (IQR shaded), prefetch-on arms green
and prefetch-off arms red.

### Mechanism metrics (per-cell medians; diagnostic only)

`e4/mechanism.csv`. `spec_hits` is a 10 ms staleness-window counter, **not a
win counter**. Lost-after-enqueue = `enqueued − spec_migrations`; it
includes `spec_region_invalid`, which is 0 everywhere, so nothing is
double-counted.

| workload | arm | demand faults | fault_already_resident | as fraction of distinct pages | ft_predictions | same-region skips | enqueued | drops | lost after enqueue | spec_pages_requested | outside-lock svc−D3−D4 (s) | enqueue_overhead (s) | D5 (s) | spec_hits (10 ms staleness counter) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stencil | C0 | 339,251 | 0 | 0.0000 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0014 | 0.0000 | 0.1051 | 0 |
| stencil | C7-slow-W1 | 331,944 | 29,124 | 0.0259 | 331,944 | 0 | 331,944 | 0 | 88,908 | 242,219 | 0.0796 | 0.0249 | 0.1363 | 22,222 |
| stencil | C7-W1 | 340,817 | 23,248 | 0.0207 | 340,817 | 0 | 340,817 | 0 | 99,107 | 241,286 | 0.0373 | 0.0242 | 0.1325 | 18,451 |
| stencil | C7-W64 | 318,730 | 42,896 | 0.0381 | 318,730 | 191,682 | 127,002 | 0 | 33,727 | 5,977,888 | 0.0206 | 0.0104 | 0.0776 | 8,328 |
| stencil | C7-W512 | 204,641 | 22,960 | 0.0204 | 204,641 | 202,443 | 2,198 | 0 | 572 | 832,392 | 0.0058 | 0.0008 | 0.0565 | 1,322 |
| stencil | C1 | 2,921,620 | 0 | 0.0000 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0140 | 0.0000 | 1.6011 | 0 |
| stencil | C6-slow-W1 | 2,986,499 | 918,392 | 0.8163 | 1,124,999 | 0 | 918,990 | 206,008 | 598 | 918,392 | 0.4934 | 0.0607 | 0.9199 | 918 |
| stencil | C6-W1 | 2,984,186 | 805,291 | 0.7158 | 1,124,999 | 0 | 806,179 | 318,820 | 691 | 805,474 | 0.1217 | 0.0519 | 1.0791 | 1,164 |
| stencil | C6-W64 | 3,016,782 | 1,124,960 | 1.0000 | 1,124,999 | 669,686 | 455,313 | 0 | 112 | 29,132,592 | 0.1248 | 0.0510 | 0.4929 | 399 |
| stencil | C6-W512 | 2,960,758 | 1,124,488 | 0.9995 | 1,124,999 | 1,122,800 | 2,199 | 0 | 1 | 1,125,000 | 0.0568 | 0.0011 | 0.4925 | 2,197 |
| graphbfs | C0 | 44,290 | 0 | 0.0000 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0002 | 0.0000 | 0.0488 | 0 |
| graphbfs | C7-slow-W1 | 43,494 | 692 | 0.0024 | 6,523 | 0 | 6,523 | 0 | 441 | 6,052 | 0.0088 | 0.0006 | 0.0497 | 459 |
| graphbfs | C7-W1 | 43,500 | 628 | 0.0022 | 6,264 | 0 | 6,264 | 0 | 498 | 5,760 | 0.0018 | 0.0006 | 0.0467 | 430 |
| graphbfs | C7-W64 | 37,215 | 1,896 | 0.0066 | 5,566 | 2,476 | 3,025 | 0 | 175 | 182,292 | 0.0014 | 0.0003 | 0.0396 | 131 |
| graphbfs | C7-W512 | 30,358 | 2,448 | 0.0085 | 3,601 | 1,966 | 1,650 | 0 | 82 | 804,568 | 0.0010 | 0.0002 | 0.0333 | 54 |
| graphbfs | C1 | 483,503 | 0 | 0.0000 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0034 | 0.0000 | 0.7308 | 0 |
| graphbfs | C6-slow-W1 | 481,942 | 65,474 | 0.2274 | 74,430 | 0 | 74,430 | 0 | 8,948 | 65,483 | 0.0923 | 0.0090 | 0.6610 | 1,516 |
| graphbfs | C6-W1 | 483,274 | 64,189 | 0.2229 | 73,424 | 0 | 72,832 | 387 | 8,717 | 64,236 | 0.0214 | 0.0083 | 0.6654 | 1,648 |
| graphbfs | C6-W64 | 486,385 | 180,036 | 0.6252 | 75,845 | 17,492 | 57,954 | 818 | 1,703 | 3,599,324 | 0.0199 | 0.0066 | 0.4733 | 851 |
| graphbfs | C6-W512 | 485,603 | 231,996 | 0.8057 | 73,496 | 21,502 | 51,511 | 0 | 1,579 | 25,553,498 | 0.0194 | 0.0061 | 0.4116 | 714 |

### Required statement — F4 (perfect off-path staging vs the in-path prefetcher)

```
F4 stencil: C6-W512 staged 0.9995 of distinct pages ahead of their fault (fault_already_resident 1124488 / 1125000); demand faults 2960758 (C0 339251); wall-clock ratio C6-W512 / C0 = 2.919
F4 graphbfs: C6-W512 staged 0.8057 of distinct pages ahead of their fault (fault_already_resident 231996 / 287956); demand faults 485603 (C0 44290); wall-clock ratio C6-W512 / C0 = 1.039
```

- **Stencil-24K:** C6-W512 staged **99.95%** of distinct pages (1,124,488
  of 1,125,000) ahead of their fault. Demand faults were still **2,960,758**,
  against C0's 339,251: 8.7× as many, and essentially C1's 2.92M. **The
  wall-clock ratio to C0 is 2.919.**
- **GraphBFS-23:** 80.6% staged; 485,603 demand faults against 44,290;
  wall-clock ratio **1.039**.
- **These ratios are the measured cost of staging off-path without
  mappings, relative to staging in-path with them.** Speculation never
  installs mappings, so perfect staging leaves the prefetch-off fault count
  essentially unchanged.
- Both F4 comparisons: **C6-W512 is slower than C0**, Holm-significant.

### Required statement — F2 (oracle instrument cost)

```
F2 stencil C7: wall-clock cost of the slow oracle's overhead = median(C7-slow-W1) - median(C7-W1) = +0.0247 s; E3b Stencil servicing-time estimate of the removed residual 0.041 s (cross-session comparison, not a test)
F2 stencil C6: wall-clock cost of the slow oracle's overhead = median(C6-slow-W1) - median(C6-W1) = +0.2216 s; E3b Stencil servicing-time estimate of the removed residual 0.362 s (cross-session comparison, not a test)
F2 graphbfs C7: wall-clock cost of the slow oracle's overhead = median(C7-slow-W1) - median(C7-W1) = +0.0392 s
F2 graphbfs C6: wall-clock cost of the slow oracle's overhead = median(C6-slow-W1) - median(C6-W1) = +0.0645 s
```

**Stencil C6** (prefetch off):
- The slow oracle costs **0.222 s of wall-clock** per run: C6-W1 is 5.40%
  faster than C6-slow-W1, Holm-significant.
- E3b's servicing-time estimate of the removed residual was 0.362 s, so the
  wall-clock cost is about **61%** of it. This is a cross-session
  comparison, not a test.

**Stencil C7** (prefetch on):
- 0.025 s, not significant (p = 0.023 against a Holm threshold of 0.00625).
- That is about **60%** of E3b's 0.041 s estimate (cross-session, not a
  test).

**GraphBFS:** 0.039 s (C7) and 0.065 s (C6), both not significant, against
MDEs of 0.15 and 0.19 s.

## Exploratory — not confirmatory

None of the following was pre-registered.

1. **The trigger result is not a boot artifact.** Stencil medians by boot:
   - C0: 1.1341 s (pre, n = 3) and 1.1288 s (post, n = 7);
   - C7-W512: 1.0880 s (pre, n = 3) and 1.0692 s (post, n = 7).

   C7-W512 is faster in both boots, and the two cells are completely
   separated overall.
2. **E1 replicates.** C7-slow-W1 against C0 on Stencil is **+8.06%**
   (1.2205 vs 1.1295 s). E1 measured +8.13% for the same configuration
   (C7-L4096, expensive oracle, W = 1) in a different session. This is a
   cross-session comparison, not a test.
3. **E0.9b's direction replicates.** C6-slow-W1 against C1 on Stencil is
   **−4.53%** (E0.9b: −5.65%). With the cheap oracle it becomes −9.69%
   (F3, C6-W1), and with width −21.6% (W64) and −23.3% (W512).
4. **How C7-W512 beats C0: the fault count drops.**
   - C7-W512's median demand faults are **204,641 against C0's 339,251
     (−39.7%)**, and D5 falls from 0.105 to 0.057 s.
   - Its handoff is nearly free: 2,198 enqueues (about one per 2 MB block),
     outside-lock 0.0058 s.
   - Prefetch-off C6-W512 does **not** reduce demand faults (2.96M, against
     C1's 2.92M), even with 99.95% of pages staged.
   - A hypothesis, **untested**: once the worker has made a whole block
     resident, the demand path's own service step, with the stock
     prefetcher on, maps the already-resident region around a faulting page
     and so prevents later faults in that block. Speculation still never
     maps. The prefetcher does, over residency that speculation created.
     Testing it would need instrumentation and runs that this gate forbids.
5. **Width alone is monotone on Stencil with prefetch on:** +5.87% (W1),
   −1.83% (W64, n.s.), −4.93% (W512).

## Existing results and claims these bear on (flagged, not edited)

`CLAIM_SCOPE.md`, the manuscript and every earlier report are unedited.

**The paper's central claim**, "speculation cannot improve the driver as it
ships":
- **Falsified in that form on Stencil-24K** (C7-W512, −4.93%, Holm-sig,
  3.9× MDE).
- Not falsified on GraphBFS-23 (no F1 difference; MDE ≈0.28%, weakened
  oracle).
- Any restatement must name:
  - the configuration: cheap perfect first-touch oracle, whole-block width,
    prefetcher on;
  - the workload dependence;
  - that the gain coincides with the in-path prefetcher operating on
    speculatively created residency (exploratory item 4, untested
    mechanism);
  - single platform.

**E1's "cannot beat C0":**
- Holds for the configurations E1 tested: the W = 1 slowdown replicates
  (+8.06% vs +8.13%), and the cheap oracle at W = 1 is still +5.87% slower.
- **Does not hold for C7-W512.** It must be scoped to single-page
  speculation.

**E0.9b's 5.65%** (C6-L4096 vs C1, expensive oracle):
- The direction replicates (−4.53%).
- The expensive oracle **understated** speculation's gain with the
  prefetcher off: −9.69% with the cheap oracle, and −21.6 to −23.3% with
  width.
- It remains far from C0: best prefetch-off arm / C0 = 2.92 on Stencil.

**The E3b expensive-oracle caveat can now be retired for these questions.**
- F2 measures the slow oracle's wall-clock cost directly: 0.222 s (Stencil
  C6, Holm-sig) and 0.025 s (Stencil C7, n.s.).
- E4 re-tests E0.9b's and E1's questions with the cheap oracle.
- The E0.9b and E1 numbers stand as measurements of the expensive-oracle
  configuration only. For "what can a first-touch oracle achieve", E4
  supersedes them.

**CLAIM_SCOPE claim 5** ("no per-hit wall-time saving"): contradicted
relative to C0 on Stencil at W = 512. It was already qualified relative to
C1 by E0.9b.

**Claim 7** (C3 loses to C0):
- As a statement about C3 it stands.
- The generalisation flagged in E1, "no tested oracle configuration beats
  C0", **no longer holds**.

**Claim 8** (turning off the prefetcher costs more than the oracle can
recover): **supported, strongly.** Even perfect off-path staging with
whole-block width and the prefetcher off (C6-W512) is 2.92× C0 on Stencil
and 1.039× on GraphBFS (F4, Holm-sig).

**Claim 10** (rate mismatch):
- With whole-block width the worker needs about one enqueue per 2 MB block
  (2,198 per Stencil run), and queue drops vanish (0 at W64/W512 on
  Stencil).
- The rate mismatch is sidestepped by width, not by a faster worker.

**Claim 15** (pipelining ceiling, D1+D2 overlap):
- The E1 Part B scope flag stands.
- C7-W512's gain coincides with fewer demand faults and a halved D5, not
  with any D1+D2 overlap. The ceiling does not bound it.

**Structural claim** (the handoff is on the critical path): still true. It
is **amortised** by width: outside-lock servicing is 0.0058 s at W512 on
Stencil C7, against 0.080 s at W1 with the slow oracle.

## Stated limitations (from the pre-registration)

- GraphBFS runs the weakened-cursor oracle.
- `fault_already_resident` means the worker beat the servicing thread, not
  the GPU.
- The cheap oracle keeps a residual of about 19–35 ns per fault.
- Speculation never installs mappings; F4 measures exactly that.
- Single platform: RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34.
- The first-touch table is a **perfect oracle** built from the same
  workload's recorded order. The trigger result is therefore an upper-bound
  demonstration, not a practical predictor's result.
