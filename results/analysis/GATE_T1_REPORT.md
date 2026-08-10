# Gate T1 — Interleaved Gate 3 C0-C3 rerun

Executed exactly per `results/analysis/PREREGISTRATION.md`: rotation `C0,C1,C2,C3,...`
repeating, module reloaded before every single run (uniform across all four configs, per
the pre-registration's corrected mechanism), 2 warm-up rotations discarded, 20 kept
rotations/cell (target met exactly, minimum of 15 exceeded). Data:
`results/phaseB2/gate3_interleaved/gate3_interleaved_times.csv` (176 rows: 88/benchmark,
22/config/benchmark including warm-up). Original `results/phaseB2/gate3/gate3_times.csv`
untouched. Per-run telemetry rings (555 MB, `results/phaseB2/gate3_interleaved/telemetry/`)
retained on disk, not committed to git (matches this project's existing convention for raw
ring dumps -- see `MIGRATION_NOTES.md`). Module srcversion `8A2651D1CB32C7B239FB511`
throughout; dmesg clean (only expected `specasync: oracle trace loaded: 207564 entries`
lines on every C3 reload, no warnings/errors).

## 1. Descriptive table (kept phase, n=20/cell)

| Config | Benchmark | n | median | mean | stdev |
|---|---|---|---|---|---|
| C0 | Stencil-24K | 20 | 4.1850s | 4.1875s | 0.0284 |
| C1 | Stencil-24K | 20 | 14.8500s | 14.9455s | 0.2997 |
| C2 | Stencil-24K | 20 | 16.0700s | 16.4800s | 0.7463 |
| C3 | Stencil-24K | 20 | 15.8400s | 15.9585s | 0.7625 |
| C0 | GraphBFS-23 | 20 | 54.2650s | 54.2645s | 0.0190 |
| C1 | GraphBFS-23 | 20 | 58.2400s | 58.2360s | 0.0280 |
| C2 | GraphBFS-23 | 20 | 58.1000s | 58.1715s | 0.2891 |
| C3 | GraphBFS-23 | 20 | 58.2500s | 58.2465s | 0.1421 |

## 2. Six pre-registered comparisons (Holm-Bonferroni, family size=6)

| Comparison | kind | med_A | med_B | delta% | p (MWU) | Holm threshold | Holm significant |
|---|---|---|---|---|---|---|---|
| C3 vs C0, GraphBFS-23 | secondary | 58.2500 | 54.2650 | +7.34% | 6.11e-08 | 0.00833 | **YES** |
| C3 vs C0, Stencil-24K | secondary | 15.8400 | 4.1850 | +278.49% | 6.50e-08 | 0.01 | **YES** |
| C2 vs C1, Stencil-24K | secondary | 16.0700 | 14.8500 | +8.22% | 3.37e-07 | 0.0125 | **YES** |
| **C3 vs C1, Stencil-24K** | **primary** | 15.8400 | 14.8500 | **+6.67%** | **9.69e-07** | 0.01667 | **YES** |
| C2 vs C1, GraphBFS-23 | secondary | 58.1000 | 58.2400 | -0.24% | 1.04e-03 | 0.025 | **YES** |
| **C3 vs C1, GraphBFS-23** | **primary** | 58.2500 | 58.2400 | **+0.02%** | **0.7758** | 0.05 | **no** |

## 3. Does the Stencil C3-vs-C1 significance survive?

**Yes -- and more decisively than before.** Under Gate 3's original blocked protocol
(`MULTIPLE_COMPARISONS.md`), Stencil-24K C3-vs-C1 was `p=0.0361` uncorrected, flipping to
**not significant** under Holm. Under this interleaved rerun, the same comparison is
`p=9.69e-07`, **significant even after Holm correction** (threshold 0.01667) -- roughly
five orders of magnitude smaller p-value, and Cohen's d=1.749 (large effect, up from 1.084
in the original blocked data). **This is the opposite of what contamination pushing the
result toward significance would predict** -- B1's hypothesis was that blocked-protocol
contamination inflated C3 upward, making the old (marginal, Holm-nonsignificant) result an
artifact. Instead, the clean interleaved data makes the C3-vs-C1 Stencil gap *more* certain,
not less. **The abstract's blanket "C3 is statistically indistinguishable from C1" claim is
therefore not supported for Stencil-24K** -- C3 is reliably ~6.7% slower than C1 on this
workload, under a protocol with no blocking confound.

**GraphBFS-23 tells the opposite story and supports the original claim cleanly:** p=0.7758,
Cohen's d=0.103 (negligible), delta=+0.02% -- indistinguishable, and now with a much tighter
MDE than before (Section 5).

## 4. Do the five high C3-Stencil runs reproduce?

**Yes, as a genuine bimodal pattern -- and it is no longer explainable by block position.**
20 kept runs, in run order:

```
16.93  15.09  15.92  15.95  15.74  15.76  15.20  16.66  16.42  15.12
15.42  17.18  16.32  15.23  16.81  17.17  15.16  15.02  15.29  16.78
```

8/20 (40%) sit in a high cluster (16.32-17.18s), 12/20 (60%) in a low cluster
(15.02-15.95s), with a **clean 0.37s gap** between the two clusters (no intermediate
values) -- a genuinely bimodal, not continuous, distribution. This closely matches the
original blocked-protocol finding (`OUTLIER_FORENSICS.md`: 5/15 = 33% high vs 8/20 = 40%
high here -- same rough proportion).

**What's changed: the high-cluster runs are no longer clustered by position.** Under the
original blocked protocol, the high runs sat at positions [3,4,5,7,10] of 15 -- clustered
early-to-mid-block, the signature of a warm-up/contention transient.  Under this session's
strict interleaving, the high-cluster run-order positions (numbered 1-20 within C3's own
20 kept reps) are **[1, 8, 9, 12, 13, 15, 16, 20]** -- spread across the entire session,
start to end, with no positional clustering. A Spearman rank correlation of wall-time
against run-order gives **rho=-0.011, p=0.965** -- no monotonic drift whatsoever.

Per `PREREGISTRATION.md` Section 9's explicit secondary trigger: this reproduction, with
the position-correlation explanation now ruled out, **upgrades the "warm-up/contention
artifact" reading to "two genuine, reproducible operating regimes."** Something about the
Stencil-24K + C3 (oracle, depth=1, prefetch-off) configuration itself is bimodal --
plausibly a scheduling/cache/TLB regime that gets selected pseudo-randomly per run,
independent of when in the session the run happens. **This does not change the significance
verdict** (C3 vs C1 Stencil was already significant either way, Section 3) but it is a real
addition to the mechanism story the manuscript's discussion section should address, per the
pre-registration's own stated criterion for this trigger.

## 5. New minimum detectable effect (MDE)

Two-sample MDE at 80% power, alpha=0.05 two-sided, n=20/arm, using each primary
comparison's own pooled standard deviation:

| Primary comparison | pooled SD | MDE (absolute) | **MDE (% of C1 median)** |
|---|---|---|---|
| Stencil-24K, C3 vs C1 | 0.5793s | 0.5133s | **3.46%** |
| GraphBFS-23, C3 vs C1 | 0.1024s | 0.0907s | **0.16%** |

**Neither matches the original headline 1.02% MDE figure, and the two benchmarks now
diverge sharply from each other.** GraphBFS's MDE tightened to 0.16% (better-powered null
than before) -- this benchmark's interleaved data is very low-noise (stdev 0.019-0.142s on
a ~58s runtime). Stencil's MDE loosened to 3.46% (worse-powered than the original 1.02%) --
**this benchmark is moot on power anyway, since C3-vs-C1 Stencil is already significant at
p=9.69e-07, far below any MDE consideration.** The MDE matters only for interpreting a null
result, and Stencil's comparison isn't null.

**Why Stencil's variance is higher under this protocol, reported honestly:** every kept run
in this session is preceded by a full module reload (per `PREREGISTRATION.md`'s corrected
mechanism -- necessary because `uvm_perf_prefetch_enable` and `specasync_oracle_trace_path`
are read-only after load). Reload-transient variance (settle time, first-touch cache/TLB
state) is a roughly fixed absolute cost per run; on Stencil-24K's short ~15s runtime that
fixed cost is a much larger relative share of variance than on GraphBFS-23's ~58s runtime
(C1 stdev/median: Stencil 2.0%, GraphBFS 0.05%). This is a real trade-off of the
reload-based interleaving mechanism against the original (partially) live-switched
protocol -- it buys a clean, unconfounded comparison at the cost of some added per-run
noise on short benchmarks. Flagged here rather than left implicit.

## 6. Outlier scan (Tukey fence, per the pre-registered rule; headline unaffected either way)

| Config/Bench | fence | flagged |
|---|---|---|
| C0/Stencil | [4.122, 4.263] | none |
| C1/Stencil | [14.570, 15.210] | 16.11 |
| C2/Stencil | [14.155, 18.935] | none |
| **C3/Stencil** | **[13.021, 18.891]** | **none** |
| C0/GraphBFS | [54.205, 54.325] | none |
| C1/GraphBFS | [58.184, 58.294] | 58.16 |
| C2/GraphBFS | [57.825, 58.385] | 58.54, 59.24 |
| C3/GraphBFS | [57.740, 58.720] | none |

**C3/Stencil again flags zero points**, exactly reproducing the "masking" phenomenon
`OUTLIER_FORENSICS.md` first identified: a genuinely bimodal sample widens its own Tukey
fence (via inflated Q3/IQR) enough to swallow its own high cluster, so a naive fence-based
outlier removal would silently miss the real story here (Section 4). Consistent with the
pre-registered policy (Section 7): **removing none from the headline number** -- the
descriptive/test tables above use the full, un-trimmed 20-sample cells throughout.

## 7. Plain statement on the abstract's blanket claim

**Not fully supported, in a specific and now well-characterized way.** The interleaved
rerun **confirms** the claim for GraphBFS-23 (C3 statistically indistinguishable from C1,
now with an MDE of 0.16% -- a materially better-powered null than the original 1.02%
figure) and **contradicts** it for Stencil-24K (C3 significantly slower than C1, p=9.69e-07,
d=1.749, ~6.7% -- more decisive than the original marginal/Holm-nonsignificant result, not
less). This is the opposite of B1's contamination hypothesis, which predicted the clean data
would *weaken* the Stencil significance (since blocked-protocol contamination was thought to
inflate C3). Instead, cleaning up the protocol made the Stencil gap more certain. The
paper's central claim needs to be stated per-workload, not as a single blanket sentence:
speculative prefetching provides no measurable benefit on either workload (neither shows
C3 beating C1, addressing the pre-registration's actual falsification trigger in Section
9, which is about improvement, not any significant difference) but on Stencil it measurably
*costs* wall-clock time relative to the simpler C1 baseline, while on GraphBFS it is
genuinely indistinguishable. The five-high-C3-Stencil-runs pattern (Section 4) is a real,
reproducible bimodal mechanism worth a sentence in the discussion, not an artifact to wave
away.

**Falsification check against `PREREGISTRATION.md` Section 9:** the primary trigger
("C3 shows a statistically significant *and* practically meaningful *improvement* over C1")
did **not** fire in either benchmark -- C3 never beats C1. The secondary trigger (bimodal
pattern reproducing as position-independent) **did** fire (Section 4). Per the
pre-registration's own terms, this does not overturn the paper's negative/null conclusion
about speculative prefetching's benefit, but it does require the abstract's claim to be
split by workload rather than stated as one blanket sentence, and the discussion section
to address the Stencil bimodality as a real mechanism finding.
