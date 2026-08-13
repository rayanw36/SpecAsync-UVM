# Gate B6 Task 4 — cuFFT interleaved rerun on RTX 5070 Ti (driver 595.84)

**Same hardware, different driver than the original claim.** The "up to 4.4%" cuFFT
speedup figure this task revisits was measured on this exact RTX 5070 Ti under **driver
v580.95.05** (`CLAIM_SCOPE.md` row 12, `CUFFT_PROVENANCE.md`), months before any T4 work
existed in this repository. This rerun is on the **same GPU, same host, driver 595.84** —
a driver-version comparison on fixed hardware, not a cross-platform one. It is also, per
Gate T2, a *protocol* comparison: the legacy figure is non-interleaved, mean-of-n=50,
"Exp1"; this rerun (and T4's Gate T2) are interleaved, median-of-n=15, p0-vs-p2 at the
exact policy/depth the legacy hit rate was measured at.

Ran after a fresh headless reboot (`systemctl isolate multi-user.target`, per
`HOST_MEMORY_LEAK_5070TI.md`'s recommendation to free desktop memory and match B5's
protocol), from ~58GB `MemAvailable` at the start. `tests/t2_cufft_interleaved.sh 15`,
unmodified protocol — p0 vs p2 at **depth=0** (not depth=1 — the exact mismatch
`GATE_T2_REPORT.md` caught mid-task on the T4), 3 sizes, 2 warm-up + 15 kept, strictly
interleaved, reload before every run, plus C0/C1 continuity. Module srcversion
`9E98EF08CBA769C50A24937` throughout (the 595.84 SpecAsync build). 204/204 runs completed;
the harness's new abort guard (added this session, `check_memory_or_abort` in
`tests/t2_cufft_interleaved.sh`, threshold 6GiB `MemAvailable`) never triggered — minimum
`MemAvailable` seen was 9.59GiB, at the very last run. dmesg essentially clean (1 line
total across all 204 runs). Data: `results/phaseB2/cufft_interleaved_5070ti/
cufft_interleaved_times.csv`.

## 1. Does the legacy hit rate reproduce?

**No — but not by the same margin as on the T4, and the direction of the miss matters.**

| Size | This rerun, p2 hit rate (n=15, kept) | T4 (Gate T2, 595.71.05) | Legacy figure (580.95.05, non-interleaved) |
|---|--:|--:|--:|
| 67,108,864 (same size as the legacy row) | **13.80%** | 4.07% | 25.47% |
| 134,217,728 | 2.92% | 2.59% | -- |
| 268,435,456 | 1.77% | 1.70% | -- |

At the exact size/policy/depth/prefetch-state the legacy 25.47% was measured at, this
platform's own controlled rerun gets 13.80% — about half the legacy figure, but over 3x
higher than what the same protocol measured on the T4 (4.07%). The two larger sizes track
the T4's numbers closely (2.92% vs 2.59%, 1.77% vs 1.70%) — the divergence is concentrated
at the smallest size. This is reported as a genuine platform/driver-dependent difference in
how many speculative predictions land, not smoothed into agreement with either the T4 or
the legacy figure. No mechanism for the divergence is asserted here — architecture (Turing
vs Blackwell) and driver version (595.71.05 vs 595.84) both changed between this
measurement and the T4's, and disentangling them is outside this task's scope.

## 2. Does it correspond to any wall-clock effect?

**No — a cleaner null than either prior measurement.**

| Size | p0 (no speculation) median | p2 (stride) median | delta | MWU p |
|---|--:|--:|--:|
| 67,108,864 | 0.300s | 0.300s | +0.00% | 0.2213 (n.s.) |
| 134,217,728 | 0.380s | 0.380s | +0.00% | 0.1125 (n.s.) |
| 268,435,456 | 0.530s | 0.530s | +0.00% | 0.9465 (n.s.) |

All three sizes show identical p0/p2 medians and no significant difference (uncorrected —
consistent with Gate T2's convention of not running these through a multiple-comparison
family, since cuFFT was never part of T1's pre-registered 6-comparison set). Unlike the
T4's Gate T2 (one nominal p=0.019 at 134M, wrong direction, plausible false positive), this
rerun doesn't even produce that — all three p-values are unremarkable. **The higher hit
rate at 67,108,864 (13.80% vs the T4's 4.07%) makes this a stronger version of the null
result, not a weaker one**: even with substantially more speculative predictions landing,
there is still no measurable wall-clock benefit. Prediction accuracy and wall-clock
speedup remain dissociated on this platform too.

## 3. Secondary: C0/C1 continuity (stock prefetch ON vs OFF, no speculation either way)

| Size | C0 (prefetch ON) median | C1 (prefetch OFF) median | delta | MWU p |
|---|--:|--:|--:|
| 67,108,864 | 0.280s | 0.890s | +217.86% | 2.59e-06 |
| 134,217,728 | 0.360s | 1.630s | +352.78% | 2.31e-06 |
| 268,435,456 | 0.530s | 3.100s | +484.91% | 2.98e-06 |

Reproduces the T4's finding (+269.6% / +352.3% / +414.8%) at the same order of magnitude,
same direction, all Holm-irrelevant-strength significant (p~1e-6 range). The stock NVIDIA
prefetcher continues to do the real work for cuFFT's access pattern on this platform too —
this is not new information, it's the same sanity check Gate T2 ran before trusting its
primary null result, repeated here for the same reason.

## 4. Memory trajectory (per `HOST_MEMORY_LEAK_5070TI.md`'s abort protocol)

`MemAvailable` fell from 58.25GiB at run 1 to 9.59GiB at run 204 — 49.8GB consumed over 204
runs, **244.25MB/cycle average**, matching the characterization pass's median
(~230-250MB/cycle) closely. The abort threshold (6GiB) was never approached; the session
completed with real margin (9.59GiB, well above 6GiB) rather than clipping it — this run's
own trajectory is additional, independent confirmation of the leak-characterization
report's model, run on a genuinely fresh (headless, ~58GB free) boot rather than reasoned
about after the fact.

## 5. Verdict

**Both of Gate T2's original expectations hold again on this platform, with one platform-
specific wrinkle worth flagging**: the legacy hit-rate figure does not reproduce under a
controlled, interleaved, exact-configuration-matched rerun on this hardware either (13.80%
at best, vs the legacy 25.47%), and there is no wall-clock effect in either direction at
any size. The wrinkle is that this platform's own hit rate at the matching size (13.80%) is
meaningfully higher than what the identical protocol found on the T4 (4.07%) — a real,
unexplained (out of this task's scope to explain) driver/architecture-dependent difference
in raw prediction accuracy — but it does not change the paper's conclusion: more hits does
not buy measurable speed here either. Combined with Section 3's confirmation that the stock
prefetcher is still doing essentially all the real work, cuFFT gets no additional benefit
from SpecAsync speculation on this platform, exactly as found on the T4, under a different
driver version on the same physical GPU that originally produced the "up to 4.4%" claim
this whole investigation traces back to.
