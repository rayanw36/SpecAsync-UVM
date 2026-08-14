# Verification: Gate B8 Task 3's -55.77% C3-vs-C1 oversubscription result

Checks the artifact hypotheses raised against `GATE_B8_5070TI_REMAINING.md`'s oversubscription
finding (C3 more than 2x faster than C1 at n=3, hit rate still 0.0019%) before it is trusted
or carried into any manuscript-facing document. Items 1-4 use only the already-committed CSV
(`results/analysis/t_b8_oversub_5070ti/oversub_times.csv`) -- no new runs for this part.

## 1. Was C1-vs-C3 interleaved or blocked?

**Interleaved. Not the artifact #3 (phantom STREAM speedup) failure mode.** Run order from
the CSV, full session:

```
run_order:  1    2    3    4    5    6    7    8    9    10   11   12   13   14   15   16
config:     C0   C1   C2   C3   C0   C1   C2   C3   C0   C1   C2   C3   C0   C1   C2   C3
phase:      wu   wu   wu   wu   k2   k2   k2   k2   k3   k3   k3   k3   k4   k4   k4   k4
```

Strict `C0,C1,C2,C3` rotation, repeated 4 times (1 warm-up + 3 kept), the same rotation
structure `t1_gate3_interleaved.sh` and every other interleaved harness in this project uses
-- never blocked (all of C1's runs together, then all of C3's). **This rules out artifact #3's
specific mechanism directly**: that artifact required a blocked all-baseline-then-all-
treatment order so a slow host-noise drift landed asymmetrically on one arm; this run alternates
through all four configs every ~7-8 minutes, so no such drift could land on only one arm.

One caveat, disclosed rather than smoothed over: within each rotation, C1 always occupies
position 2 and C3 always occupies position 4 (with C2's own ~180s run always sitting between
them) -- this is the same fixed-rotation-order design every prior interleaved comparison in
this project uses (T1, B5, SGEMM all fix the C0,C1,C2,C3 order per rotation too), not a new
weakness specific to this run, but it does mean C1 and C3 are never *adjacent* in run order,
only alternating across rotations.

## 2. MemAvailable trajectory, before and after every run

| run | config | phase | wall_s | mem_before (GB) | mem_after (GB) | delta (GB) |
|--:|---|---|--:|--:|--:|--:|
| 1 | C0 | warmup | 27.19 | 30.156 | 29.912 | 0.244 |
| 2 | C1 | warmup | 159.29 | 29.896 | 29.662 | 0.234 |
| 3 | C2 | warmup | 183.95 | 29.658 | 29.422 | 0.236 |
| 4 | C3 | warmup | 70.70 | 29.407 | 29.166 | 0.241 |
| 5 | C0 | kept | 27.17 | 29.159 | 28.922 | 0.236 |
| **6** | **C1** | **kept** | **159.29** | **28.913** | 28.684 | 0.230 |
| 7 | C2 | kept | 183.85 | 28.667 | 28.427 | 0.240 |
| **8** | **C3** | **kept** | **71.32** | **28.419** | 28.179 | 0.240 |
| 9 | C0 | kept | 27.19 | 28.180 | 27.937 | 0.243 |
| **10** | **C1** | **kept** | **159.50** | **27.927** | 27.693 | 0.234 |
| 11 | C2 | kept | 183.49 | 27.687 | 27.448 | 0.239 |
| **12** | **C3** | **kept** | **70.45** | **27.432** | 27.194 | 0.237 |
| 13 | C0 | kept | 27.18 | 27.193 | 26.954 | 0.240 |
| **14** | **C1** | **kept** | **159.26** | **26.945** | 26.667 | 0.278 |
| 15 | C2 | kept | 183.66 | 26.658 | 26.420 | 0.238 |
| **16** | **C3** | **kept** | **70.07** | **26.403** | 26.153 | 0.250 |

**Per-cycle leak (the `delta` column) is uniform across configs**, 0.230-0.278GB regardless
of whether the run itself is C0/C1/C2/C3 -- no config-specific leak-rate anomaly, matching
`HOST_MEMORY_LEAK_5070TI.md`'s characterization.

**The two arms do sit at systematically different memory levels -- but in the direction that
argues against, not for, an artifact explanation.** Within each rotation, C3 always runs with
*less* `MemAvailable` than the C1 that preceded it two positions earlier (C2's own cycle sits
between them):

| Rotation | C1 mem_before | C3 mem_before | gap | gap as % of C1's level |
|---|--:|--:|--:|--:|
| kept_2 | 28.913 GB | 28.419 GB | 0.495 GB | 1.71% |
| kept_3 | 27.927 GB | 27.432 GB | 0.496 GB | 1.77% |
| kept_4 | 26.945 GB | 26.403 GB | 0.542 GB | 2.01% |

A ~1.7-2.0% reduction in available host memory is the environment C3 runs in, not C1. If
reduced memory availability were driving the wall-clock difference, the naive expectation for
a host-RAM-bound, already-thrashing workload is that *less* headroom makes a run *slower*
(more reclaim pressure, less caching headroom) -- the opposite of what's observed (C3, with
less memory, is more than 2x *faster*). **This does not rule out every conceivable memory-
related confound** (a subtler, non-monotonic effect is not excluded by this alone), but the
simple, most obvious version of "the arms sat at different memory levels and that explains it"
points the wrong direction to account for the effect on its own.

## 3. Individual wall-clock values, all six runs (n=3/arm)

| Config | Runs | Values | Range |
|---|---|---|---|
| C1 | 6, 10, 14 | 159.29, 159.50, 159.26 | 0.24s (0.15%) |
| C3 | 8, 12, 16 | 71.32, 70.45, 70.07 | 1.25s (1.77%) |

**Zero overlap.** The highest C3 value (71.32s) is still 55.3% below the lowest C1 value
(159.26s). Both arms are internally tight (C1 within 0.24s of itself across the whole
session; C3 within 1.25s), which is why n=3 already reaches the maximum-available MWU
significance ceiling (p=0.1, the floor achievable at 3-vs-3) despite the tiny n -- the
separation is total, not marginal.

## 4. Was C0 run? Does C3 beat it?

**Yes, C0 was run (every rotation, position 1). No, C3 does not beat C0.** C0 median 27.18s
vs C3 median 70.45s (+159.20%, already reported in `GATE_B8_5070TI_REMAINING.md`). **The
framing is unchanged from every other workload in this project**: the stock prefetcher (C0)
still dominates outright; C3's advantage is specifically over C1 (no speculation, prefetch
also off), not a general "speculation beats everything" result. This is not a first for the
project -- it is the same "C0 wins overall, comparisons among the non-prefetch configs are
the interesting ones" pattern already established everywhere else.

## Verdict on items 1-4: proceed to re-run

Both preconditions the brief set for proceeding are met: **the comparison was interleaved
(item 1), and the memory gap between arms, while real, is small (~2%) and points in the
wrong direction to explain the effect as an artifact (item 2).** The individual values (item
3) show total separation at n=3, and C0's inclusion (item 4) confirms the result sits inside
the project's existing framework rather than contradicting it elsewhere. No artifact
hypothesis from items 1-2 explains the effect. Proceeding to the n=10 re-run per the brief's
conditional instruction.

---

## 5. Pre-registered n=10 re-run

**Registered before running** (this section written and committed before any of the re-run's
data exists):

- **Design**: C0, C1, C3 only (per the brief -- C2 excluded from this verification), strict
  `C0,C1,C3,C0,C1,C3,...` rotation, module reload before every run, `setarch -R`, fresh
  oracle trace collected in-session for C3. 2 warm-up + 10 kept rotations (36 total runs).
  Same target as Task 3: N=48000, 18.43GB working set, ~1.08x this platform's VRAM.
  `MemAvailable` logged before/after every run; abort guard active at 6GiB.
- **Statistics**: median (statistic of record), Mann-Whitney U (test of record), Cohen's d.
- **Family for Holm-Bonferroni**: size 2. **Primary: C3 vs C1. Secondary: C3 vs C0.**
- **Falsification criterion, stated before running**: if C3's median does not beat C1's median
  at n=10, or the comparison is not Holm-significant, **the n=3 result is noise and is
  retracted**, not reinterpreted. If C3 beats C1 but the effect size shrinks substantially
  from n=3's Cohen's d, that is reported as a revised (smaller) estimate, not a failure to
  replicate, provided the direction and significance both hold.
- **What this does NOT re-test**: the mechanism question (whether the benefit runs through
  prediction credit or something else) -- Section 6 below, conditional on this section's
  result.

### 5.1 Result

Ran to completion: 36/36 runs (2 warm-up + 10 kept rotations x 3 configs), no aborts, no
errors. `tests/t_b8_oversub_verify_n10.sh`, srcversion `9E98EF08CBA769C50A24937` on every
row (confirmed correct module throughout), `dmesg_delta` 0-3 across the board (routine),
`MemAvailable` declined monotonically from 61.1GB to 52.0GB over the session (~244MB/cycle,
matching `HOST_MEMORY_LEAK_5070TI.md`) and never approached the 6GiB abort floor. Raw data:
`results/analysis/t_b8_oversub_5070ti/oversub_n10_verify_times.csv`.

**Kept-phase wall-clock (n=10/arm, seconds):**

| Config | Values | Median | Mean | SD |
|---|---|--:|--:|--:|
| C0 | 27.10, 27.09, 27.08, 27.12, 27.13, 27.09, 27.10, 27.08, 27.07, 27.09 | 27.090 | 27.095 | 0.0184 |
| C1 | 159.19, 159.07, 159.44, 159.51, 159.43, 159.29, 158.97, 159.10, 158.89, 159.09 | 159.145 | 159.198 | 0.2116 |
| C3 | 69.38, 68.97, 69.33, 69.08, 69.10, 70.31, 67.92, 70.33, 68.29, 69.27 | 69.185 | 69.198 | 0.7533 |

**Primary: C3 vs C1.** Complete separation -- every C3 value (67.92-70.33) sits below every
C1 value (158.89-159.51); zero overlap across 20 observations. Median improvement: (69.185 -
159.145) / 159.145 = **-56.52%**, essentially identical to the n=3 estimate (-55.77%), not
just same-direction but same-magnitude. Mann-Whitney U: complete separation at n1=n2=10 is
the most extreme rank configuration possible; exact two-sided p = 2/C(20,10) = **1.08e-5**.
Cohen's d = 162.7 (driven by C1's very low variance).

**Secondary: C3 vs C0.** Also complete separation, in the other direction -- every C3 value
sits above every C0 value. C3 is slower than C0 by (69.198 - 27.095) / 27.095 = **+155.4%**,
consistent with items 1-4 and every other workload in this project: the stock prefetcher
still wins outright. Exact two-sided p = **1.08e-5**.

**Holm-Bonferroni, family of 2:** both raw p-values are 1.08e-5. Step-up adjustment: adjusted
p(1) = 1.08e-5 x 2 = 2.17e-5; adjusted p(2) = max(2.17e-5, 1.08e-5 x 1) = 2.17e-5. Both
comparisons remain significant at any conventional alpha after correction.

**Verdict against the pre-registered falsification criterion:** C3's median (69.185s) beats
C1's median (159.145s), and the comparison is Holm-significant (adjusted p = 2.17e-5). Per
the criterion stated in Section 5 before this data existed, **the n=3 result is CONFIRMED,
not retracted** -- and the magnitude did not shrink (-56.52% at n=10 vs -55.77% at n=3); per
the pre-registration's second clause this is reported as a same-magnitude replication, not a
revised-down estimate. The finding now clears this project's standard bar: interleaved,
memory-comparable, n=10, Holm-significant, magnitude-stable. It may be cited as a **verified**
finding (C3 beats C1 in this specific oversubscribed, depth=1, oracle-policy configuration),
still bounded by the existing framing that C3 does not beat C0.

This unlocks Section 6, the mechanism question, which was conditional on this result.

## 6. Mechanism check: does the benefit require depth=1 (real migration), or does it persist at depth=0 (metadata-only)?

**Pre-registered before running** (written before any Section 6 data exists):

- **Question**: Gate D's claim is that depth=0 is "architecturally incapable" of the
  migration-side benefit -- depth=0 only marks pages via metadata/prefetch hints without
  triggering the actual asynchronous migration path that depth=1 enables. If that's right,
  an oracle-policy (policy=4) arm run at depth=0 should behave like C1 (no benefit, since no
  real migration occurs), not like C3. If the depth=0 oracle arm is *also* fast, the benefit
  isn't migration-side at all -- it would have to come from something depth-independent (e.g.
  a driver/scheduling side effect of `specasync_policy=4` itself), which would contradict
  Gate D's mechanism claim and require new framing.
- **Design**: add one new arm, **C3d0** (`specasync_policy=4`, `specasync_offload_depth=0`,
  `uvm_perf_prefetch_enable=0`, same oracle trace mechanism as C3), alongside C1 and C3 as a
  reference pair (C0 dropped -- it's not informative for this specific migration-vs-no-migration
  question, already answered in Section 5). Strict `C1,C3,C3d0` rotation, module reload before
  every run, fresh oracle trace collected in-session, same N=48000/18.43GB target, same 6GiB
  abort guard, `MemAvailable` logged before/after every run. 2 warm-up + 10 kept rotations
  (36 total runs).
- **Statistics**: median, Mann-Whitney U, Cohen's d. Family for Holm-Bonferroni: size 2
  (C3d0 vs C1, C3d0 vs C3).
- **Interpretation registered before running**: if C3d0's median is close to C1's (no
  Holm-significant improvement over C1), the benefit is depth=1-specific / migration-side,
  consistent with Gate D. If C3d0's median is close to C3's (Holm-significant improvement
  over C1, not Holm-significant difference from C3, or a much smaller gap to C3 than to C1),
  the benefit is not migration-gated and Gate D's "architecturally incapable" framing needs
  re-examination. An intermediate result (C3d0 significantly different from *both* C1 and C3)
  is reported as exactly that -- a partial/mixed effect -- not forced into either bucket.

### 6.1 Result

Ran to completion: 36/36 runs (2 warm-up + 10 kept rotations x 3 configs), no aborts. One
non-finding worth disclosing rather than omitting: `dmesg_delta` jumped from the usual 0-2 to
10 on the last two C3d0 kept reps (kept_11, kept_12). Checked directly against `dmesg -T`:
this was `wlp8s0` WiFi AP roaming (disconnect/reassociate to a different AP, `NVRM: Going
over RM unhandled interrupt threshold for irq 112` lines present throughout the *entire*
session on both C3 and C3d0 reloads, not specific to these two runs) -- environmental noise
from running headless on a laptop, unrelated to the driver or the experiment. srcversion
`9E98EF08CBA769C50A24937` on every row (correct module throughout). `MemAvailable` declined
monotonically from 51.7GB to 42.6GB, consistent with the known leak rate, never near the 6GiB
floor. Raw data: `results/analysis/t_b8_oversub_5070ti/oversub_depth0_verify_times.csv`.

**Kept-phase wall-clock (n=10/arm, seconds):**

| Config | Median | Mean | SD |
|---|--:|--:|--:|
| C1 | 159.020 | 159.076 | 0.3994 |
| C3 | 68.480 | 68.585 | 0.7098 |
| C3d0 | 192.420 | 192.888 | 1.3457 |

**Primary: C3d0 vs C1.** Complete separation -- every C3d0 value (191.69-195.51) sits above
every C1 value (158.54-160.04); zero overlap. C3d0 is not merely "no benefit" relative to C1
-- it is **21.0% slower** than C1 by median ((192.42-159.02)/159.02), a regression, not a
null result. Exact two-sided Mann-Whitney p (complete separation, n1=n2=10) = 1.08e-5.
Cohen's d = 34.1.

**Secondary: C3d0 vs C3.** Also complete separation -- C3d0 uniformly far slower than C3.
C3d0 is **181.0% slower** than C3 by median ((192.42-68.48)/68.48). Exact two-sided p =
1.08e-5. Cohen's d = 115.6.

**Holm-Bonferroni, family of 2:** both raw p = 1.08e-5; adjusted p(1) = 2.17e-5, adjusted
p(2) = 2.17e-5. Both significant at any conventional alpha.

**Verdict against the pre-registered interpretation buckets:** C3d0 is not "close to C1" in
the neutral sense anticipated -- it lands in a third position, significantly slower than
*both* reference arms, and further from C3 (181% gap) than from C1 (21% gap). Per the
registered interpretation, this is unambiguously **the depth=1-specific / migration-side
bucket, not the intermediate/mixed bucket**: C3d0 shows no trace of C3's benefit (the 21%
gap to C1 runs in the wrong direction to be read as a partial benefit -- it's a cost, not a
discount), so the finding does not need to be forced into a partial-effect interpretation.
**The oversubscription benefit requires depth=1 (real migration); it does not persist, even
partially, when only the oracle-policy prediction machinery runs without the migration path
depth=0 provides.** This is consistent with, and now has direct measurement behind, Gate D's
"architecturally incapable" claim for depth=0. A secondary, unregistered observation: paying
for oracle-policy bookkeeping (trace lookup, prediction logic) without capturing the
migration benefit costs roughly 21% versus running no speculation at all (C1) -- plausibly
the predictor's own overhead with nothing to offset it, though this run was not designed to
isolate that mechanism and the report does not claim more than the measurement supports.

## Overall verdict

The n=3 finding in `GATE_B8_5070TI_REMAINING.md` (C3 beats C1 by -55.77% at the oversubscribed
N=48000 target) is **verified, not retracted**. Items 1-4 ruled out the interleaving and
memory-confound artifact hypotheses from the committed n=3 data. The pre-registered n=10
re-run (Section 5) reproduced the effect at essentially the same magnitude (-56.52% at n=10
vs -55.77% at n=3) with Holm-significant separation on both the primary (C3 vs C1) and
secondary (C3 vs C0) comparisons. The mechanism check (Section 6) shows the benefit is
strictly depth=1-specific: an oracle-policy arm at depth=0 does not partially capture the
benefit -- it regresses 21% below C1, and sits 181% behind C3. **This finding may now be
cited as verified** within the scope actually measured: C3 (oracle, depth=1) beats C1 (no
speculation) by roughly -56% wall-clock at this specific oversubscribed working-set target
(N=48000, 18.43GB, ~1.08x this platform's VRAM) on the 5070 Ti; C3 does not beat C0 (stock
prefetch); and the benefit does not manifest at depth=0. Carrying this into
`CLAIM_SCOPE.md` or any other manuscript-facing document is a separate, deliberate step not
taken here per the standing instruction that gated this verification.
