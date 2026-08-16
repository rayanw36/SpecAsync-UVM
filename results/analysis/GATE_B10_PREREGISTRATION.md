# Gate B10 Pre-Registration: Does Speculation Help ON TOP of the Prefetcher?

Written and committed **before** any B10 run executes, per standing protocol
(`PREREGISTRATION.md` Section 9's convention: state the falsification trigger
and the MDE in advance, not after seeing results).

## 1. The gap this closes

Every configuration tested through `OVERSUB_C3_VERIFICATION.md` treats
speculation as a **replacement** for the stock prefetcher (C3 = prefetch OFF +
speculation ON) or tests the prefetcher **alone** (C0 = prefetch ON,
speculation OFF). C0 beats C3 by 1.76-4.47x under oversubscription. That
result answers "is speculation a good replacement for the prefetcher" (no).
It does not answer "does speculation help **on top of** the prefetcher" --
no configuration with both prefetch ON and speculation ON has been measured.

This matters specifically under oversubscription because Task B (per-run
atomic counters, `OVERSUB_C3_VERIFICATION.md`) showed C3 eliminates roughly
146M demand faults relative to C1 -- a real, non-zero mechanism effect. C0's
win over C3 could be entirely explained by C0's cheaper per-fault path (the
granularity/cost asymmetry documented in that report), in which case adding
speculation to C0 might still shave faults C0's own prefetcher misses. Or C0's
prefetcher could already be capturing everything speculation would catch,
in which case C4 adds pure overhead with no offsetting benefit. Both are live
possibilities before this runs; that is what makes this worth measuring
rather than inferring from C3-vs-C0.

## 2. New configuration

**C4**: `specasync_policy=4` (oracle), `specasync_offload_depth=1` (real
migration), `uvm_perf_prefetch_enable=1` (stock prefetcher ON). This is C3
with the prefetcher turned back on -- the only cell added by this gate.
C0/C1/C2/C3 definitions are unchanged from `PREREGISTRATION.md`/B9; C4 is
additive, nothing is redefined.

## 3. Protocol

- Benchmark: `bench_stencil_oversub`, N=48000 (~1.078x VRAM, same target as B9).
- `iters` in {1, 5, 20} -- three values (not B9's five): the dose-response
  shape (monotonic growth with iteration count) is already established by
  Task 2b/2c; this question needs the endpoints plus one midpoint, not the
  full curve.
- Arms: **C0 and C4 only**, strictly interleaved within each `iters` value.
- n = 10 kept reps/arm/iters (double B9's n=5): the expected effect here, if
  real, is smaller than the C3-vs-C1/C0 effects already measured (those were
  gross mechanism-replacement differences of 176-447%; this is asking whether
  a prefetcher-saturated baseline has headroom left), so higher power is
  needed for a null to mean anything.
- 1 warm-up rotation + 10 kept rotations = 11 rotations x 2 arms x 3 iters
  values = 66 runs, plus 3 fresh oracle-trace collection passes (one per
  `iters` value, C4-only, same as B9's per-iters trace convention).
- `setarch -R` for both arms. Module reload before every run, verified via
  `verify_module_reload` (not just attempted). `specasync_clear` before every
  rep (explicit call, on top of the reload-per-rep design that already zeroes
  the atomics/rings as a side effect -- both are applied, so there is no
  ambiguity about residual state).
- Oracle trace for C4 collected fresh on this machine, per `iters` value,
  same procedure as B9 (policy=0/depth=0/prefetch=0 trace-collection pass,
  not reused across `iters` values).
- srcversion: `4488C9F6F75570BB2FB34F8` (the atomics build) -- confirmed via
  `modinfo` before launch.

## 4. Statistic of record: median

Unchanged from `PREREGISTRATION.md` Section 4. Median is the statistic of
record for every headline wall-clock number this task produces.

## 5. Test of record: Mann-Whitney U, two-sided

Unchanged from `PREREGISTRATION.md` Section 5.

## 6. Comparison family and correction

**Family, enumerated in advance (3 comparisons):**

1. C4 vs C0, iters=1
2. C4 vs C0, iters=5
3. C4 vs C0, iters=20

**Family size = 3.** Holm-Bonferroni step-down applied exactly as in
`PREREGISTRATION.md`/`MULTIPLE_COMPARISONS.md`: sort the three MWU p-values
ascending, compare the k-th smallest to alpha/(3-k+1) (i.e. alpha/3, alpha/2,
alpha in order); once one comparison fails its threshold, every larger
p-value in sorted order is also rejected-from-significance regardless of its
own threshold. All three comparisons are primary -- there is no secondary
comparison in this family, unlike B9's C1/C3 designs, because the entire
point of B10 is the C4-vs-C0 question at each dose point.

## 7. Minimum detectable effect (MDE) at n=10

Computed from B9's observed C0 variance (`task2c_c0_threeway_times_MERGED.csv`,
n=5/iters value, the same benchmark/N/protocol this gate reuses), via a
two-sample-t power calculation (noncentral-t, df=18, power=0.80) at the most
conservative Holm step for a 3-comparison family (alpha/3 = 0.0167 two-sided).
This is an approximation to MWU (asymptotic relative efficiency of
Wilcoxon-Mann-Whitney vs. the t-test is ~0.955 under near-normal data, i.e.
true MWU MDE is up to ~2-3% larger, relatively, than the t-test figure below)
and it is stated explicitly rather than silently assumed:

**Required Cohen's d for 80% power, n=10/arm, alpha=0.0167 (two-sided): d = 1.57.**

| iters | B9 C0 n=5 mean (s) | B9 C0 n=5 SD (s) | CV | **MDE at n=10 (%, this MWU-vs-t-test-approx caveat applies)** |
|---|---|---|---|---|
| 1  | 3.338  | 0.0817 | 2.45% | **~3.9%** |
| 5  | 8.768  | 0.3103 | 3.54% | **~5.6%** |
| 20 | 27.186 | 0.0207 | 0.08% | **~0.13%** (see caveat below) |

**Caveat on the iters=20 figure:** that SD is estimated from only 5 points
and happens to be extremely tight (CV=0.08%); a single small sample can
understate true variance. The 0.13% MDE should be read as an optimistic
lower bound, not a reliable guarantee that a sub-1% effect will actually be
detectable at n=10 -- treat the iters=1 and iters=5 figures (3.9%, 5.6%) as
the more trustworthy planning numbers for this gate.

**Stated before running, as required:** at n=10/arm, this study is
well-powered to detect a 5% improvement at iters=1 and iters=5. If the
observed C4-vs-C0 effect at those two points is smaller than the MDE and
non-significant, that is a genuine, adequately-powered null, not an
underpowered non-result -- it will be reported as such.

## 8. Falsification trigger

Mirrors `PREREGISTRATION.md` Section 9's construction, restated for this
question:

**This gate's result would identify a real augmentation benefit if, under
strict interleaving, C4 shows a statistically significant (Holm-corrected,
alpha=0.05) *and* practically meaningful improvement over C0 in at least one
of the three comparisons** -- i.e. faster than C0 by more than that
comparison's pre-registered MDE (Section 7), in the direction of C4 being
faster. A statistically-significant-but-sub-MDE improvement would not, by
itself, be reported as a positive finding, consistent with the project's
standing convention that statistical significance below the MDE is noise,
not signal.

**Any other outcome -- C4 statistically indistinguishable from C0, or C4
significantly slower than C0 -- is a null result for the augmentation
question** and will be reported as a null with its MDE stated alongside, not
framed as a weak positive or hedged.

## 9. Scope

5070-Ti-only, oversubscription-only (N=48000, ~1.078x VRAM). This gate makes
no claim about non-oversubscribed regimes or other hardware, consistent with
every other B9/B10 result on this platform.

## 10. Diagnostic (not part of the falsification trigger)

Per-run atomic counters (`processed`, `enqueued`, `drops`, `demand_faults`,
`spec_hits`, `spec_migrations`) are logged for both arms. The key diagnostic
question: does C4's `spec_hits` rise materially above C3's observed
~0.0025% hit rate (`OVERSUB_C3_VERIFICATION.md`), or does the prefetcher
suppress demand faults so effectively that speculation has little left to
hit even when both are active? This is reported for mechanism color
regardless of which way the wall-clock verdict in Section 8 lands -- a null
wall-clock result with elevated `spec_hits` and a null wall-clock result with
flat `spec_hits` are different stories, both informative, neither privileged
as "the real" outcome in advance.
