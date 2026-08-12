# Gate B5 — T1 cross-platform replication on RTX 5070 Ti (Blackwell, driver 595.84)

Platform: local machine, RTX 5070 Ti, driver 595.84, kernel 7.0.0-28-generic, headless
(`multi-user.target`) for the entire B.2-B.4 session. Module: freshly built from
`/usr/src/nvidia-595.84` via `driver/scripts/reconstruct_build_tree.sh` (made SRC/WORK
overridable; built all 5 modules together to satisfy `nvidia.Kbuild`'s conftest
registrations, only `nvidia-uvm.ko` loaded — see build log for the two build-system fixes
required). srcversion `FADA940587C8B92B63A0FFF`, constant across all 176 reloads (verified).
Zero dmesg warnings/errors across the session (`dmesg_delta` never exceeded routine
init-banner line counts).

T4 baseline throughout this report: `results/analysis/GATE_T1_REPORT.md` (the interleaved,
pre-registered rerun — not the original blocked `GATE3_report.md`, since T1 is what this
replication is of).

## 1. Deterministic hit-probe (B.2)

255/256 hits = **99.61%** hit rate, `policy=1` (adjacent), prefetch off. T4's deterministic
probe: **~99.6%** (`GATE_T4_REPORT.md`). **Reproduces closely.**

## 2. Fresh oracle traces (B.3)

Collected on this machine, not reused from T4: Stencil-24K 231,374 fault addresses (T4:
277,239), GraphBFS-23 218,794 (T4: 207,609) — different counts confirm these are genuinely
platform-specific traces, not accidentally-copied T4 data. `setarch -R` (bare and with
explicit `$(uname -m)` — verified equivalent) pins `cudaMallocManaged`'s base VA to a fixed
`0x7ffdce000000` across independent process launches (3/3 identical; without `setarch -R`,
3 launches gave 3 different bases), replicating T4's FIX-2 mechanism
(`driver/PIPELINE_FIXES.md`) on this architecture. Replaying the same trace twice gave
consistent hit rates both times (Stencil: 0.0001 vs 0.0001; GraphBFS: 0.0032 vs 0.0031) —
replay-reproducibility confirmed.

**Incidental finding:** these B.3 oracle-replay hit rates (0.01%-0.32% on real workloads,
policy=4 depth=1) are in the same order of magnitude as T4 Task T4's real-workload finding
(0.02%-0.25%, `GATE_T4_REPORT.md`) — the "near-zero real-workload hit rate despite ~99.6%
synthetic-probe hit rate" phenomenon is not Turing/T4-specific; it reproduces on Blackwell.

## 3. T1 interleaved C0-C3 rerun (B.4)

Ran `tests/t1_gate3_interleaved.sh` unmodified (only made `KO`/`OUT` overridable, same
pattern as the build script) against the freshly-built module and freshly-collected traces.
176 runs, 22 rotations (2 warm-up + 20 kept), matching T1's exact protocol
(`PREREGISTRATION.md`). Output: `results/phaseB2/gate3_interleaved_5070ti/` (kept separate
from T4's `results/phaseB2/gate3_interleaved/` to avoid collision).

### Descriptive (kept phase, n=20/cell)

| Config | Benchmark | 5070 Ti median | 5070 Ti stdev | T4 median | T4 stdev |
|---|---|--:|--:|--:|--:|
| C0 | Stencil-24K | 1.1100s | 0.0103 | 4.1850s | 0.0284 |
| C1 | Stencil-24K | 4.3100s | 0.0169 | 14.8500s | 0.2997 |
| C2 | Stencil-24K | 4.4700s | 0.0222 | 16.0700s | 0.7463 |
| C3 | Stencil-24K | 4.4650s | 0.0218 | 15.8400s | 0.7625 |
| C0 | GraphBFS-23 | 31.3800s | 0.1471 | 54.2650s | 0.0190 |
| C1 | GraphBFS-23 | 33.0250s | 0.0989 | 58.2400s | 0.0280 |
| C2 | GraphBFS-23 | 32.8700s | 0.0998 | 58.1000s | 0.2891 |
| C3 | GraphBFS-23 | 32.8950s | 0.1631 | 58.2500s | 0.1421 |

Absolute wall-clock is not comparable across platforms (faster GPU/host here). Ratios and
significance verdicts are the comparable quantities, below. Note the 5070 Ti's variance is
1-2 orders of magnitude tighter on Stencil-24K (bare-metal desktop vs. EC2 virtualized
instance is the likely explanation, not investigated further here).

### Prefetch-on benefit (C0 vs C1, Stencil-24K) — architectural claim

5070 Ti: C1/C0 = 4.3100/1.1100 = **3.88×**. T4: 14.8500/4.1850 = **3.55×**. **Reproduces**
(same order of magnitude, both platforms show the stock prefetcher is ~3.5-3.9× faster than
no speculation on this workload) — supports claim 8's now-corrected Tesla-T4-specific cost
ratio also holding, at a similar magnitude, on Blackwell.

### Six pre-registered comparisons (Holm-Bonferroni, family size=6)

| Comparison | kind | 5070Ti delta% | 5070Ti p (MWU) | 5070Ti Holm-sig | T4 delta% | T4 p (MWU) | T4 Holm-sig |
|---|---|--:|--:|:--:|--:|--:|:--:|
| C3 vs C0, Stencil-24K | secondary | +302.25% | 5.59e-08 | YES | +278.49% | 6.50e-08 | YES |
| C2 vs C1, Stencil-24K | secondary | +3.71% | 5.61e-08 | YES | +8.22% | 3.37e-07 | YES |
| **C3 vs C1, Stencil-24K** | **primary** | **+3.60%** | **5.91e-08** | **YES** | **+6.67%** | **9.69e-07** | **YES** |
| C3 vs C0, GraphBFS-23 | secondary | +4.83% | 6.71e-08 | YES | +7.34% | 6.11e-08 | YES |
| C2 vs C1, GraphBFS-23 | secondary | -0.47% | 3.14e-04 | YES | -0.24% | 1.04e-03 | YES |
| **C3 vs C1, GraphBFS-23** | **primary** | **-0.39%** | **0.0246** | **YES** | **+0.02%** | **0.7758** | **no** |

### Question: does "C3 statistically indistinguishable from C1" hold?

**Stencil-24K: reproduces T4's contradiction of the claim.** C3 is significantly *slower*
than C1 on both platforms (+3.60% here, +6.67% on T4; both Holm-significant). Effect size is
far larger here (Cohen's d=8.275 vs T4's d=1.749) purely because this machine's variance is
so much tighter — the underlying effect direction and significance verdict agree.

**GraphBFS-23: does NOT cleanly reproduce.** T4 found a true null (p=0.7758, d=0.103,
delta=+0.02%, MDE 0.16%) — the difference was far below what T4's own power could detect.
Here, the same comparison reaches Holm significance (p=0.0246, Holm threshold 0.05) with
d=-0.534 (small-to-medium effect) and delta=-0.39% — the **opposite sign** from Stencil's
pattern (C3 fractionally *faster* than C1 here, not slower) and a magnitude close to this
platform's own MDE (0.36%), i.e. a real but marginal, borderline-detectable effect rather
than a clear signal. **Reported as a genuine platform divergence, not smoothed into
agreement**: T4's GraphBFS null does not hold on the 5070 Ti under this platform's tighter
measurement noise floor.

### Bimodality (Stencil-24K, C3) — does NOT reproduce

T4 (`GATE_T1_REPORT.md` \S4): clean two-cluster split, 8/20 high (16.32-17.18s) vs 12/20 low
(15.02-15.95s), a 0.37s gap with no intermediate values, position-independent
(Spearman rho=-0.011, p=0.965).

5070 Ti: sorted kept-phase values span only 4.44s-4.51s (0.07s total range); the largest
gap between adjacent sorted values is 0.01s (measurement-resolution granularity of
`/usr/bin/time -f "%e"`, not a real cluster boundary) — a smooth, unimodal-looking
distribution, not two clusters. Spearman rho=0.5483, p=0.0123 — **unlike T4, this platform
shows a small but statistically significant upward drift of wall-time with run order**
(later runs slightly slower), the opposite of T4's "no drift whatsoever" finding.

GraphBFS-23 C3 was checked too (not part of T4's bimodality claim, checked here for
completeness): no clean gap (largest 0.13s in a ~0.8s range), rho=0.229, p=0.332 — no
significant drift, no bimodality.

**The bimodal Stencil-24K/C3 pattern that GATE_T1_REPORT.md characterized as "two genuine,
reproducible operating regimes" does not reproduce on this platform.** Combined with the
mild but real run-order drift found here instead, this platform shows a different secondary
behavior (slow monotonic drift) rather than T4's discrete bimodal switching. Both are real,
measured phenomena; they are not the same phenomenon, and the manuscript should not claim
one implies the other.

## 4. Answers to the replication questions

1. **Deterministic hit-probe (~99.6%)?** Reproduces: 99.61%.
2. **Path B closed (C3 loses to C0 on both benchmarks)?** Reproduces on both: Stencil
   +302.25% (T4: +278.49%), GraphBFS +4.83% (T4: +7.34%) — C3 loses decisively on Stencil,
   modestly on GraphBFS, same as T4.
3. **Prefetch-on benefit magnitude (~3.6× on Stencil)?** Reproduces: 3.88× here vs 3.55× on
   T4, same order of magnitude.
4. **"C3 indistinguishable from C1" — Stencil-24K?** Reproduces T4's *contradiction*: C3 is
   significantly slower than C1 on both platforms (+3.60% here, +6.67% on T4).
5. **"C3 indistinguishable from C1" — GraphBFS-23?** Does **not** reproduce: T4 found a true
   null (p=0.78); this platform finds a marginal, small-effect, Holm-significant difference
   (p=0.025, opposite sign, near this platform's own MDE) — flagged as a genuine divergence.
6. **Stencil-24K/C3 bimodality?** Does **not** reproduce: no cluster gap on this platform
   (0.07s total spread with 0.01s-resolution granularity only); instead a small but real
   run-order drift appears (rho=0.548, p=0.012) that T4 did not show.

## 5. What changes in `CLAIM_SCOPE.md`

Claims whose "Tesla-T4-specific" qualifier should gain a "reproduces on RTX 5070 Ti
(Blackwell)" note, per this report: the prefetch-on benefit magnitude (~3.5-3.9×, item 3
above) and the Path-B-closed/C3-loses-to-C0 verdict (item 2). The Stencil-24K
"C3 significantly slower than C1" finding (item 4) also reproduces and should be flagged as
cross-platform, not T4-only. The GraphBFS-23 null result and the Stencil bimodality finding
should explicitly gain a "does not reproduce on RTX 5070 Ti" note rather than being left as
if T4's finding is platform-general — see the two divergences in Section 3 and Section 3
(bimodality) above for the exact language.
