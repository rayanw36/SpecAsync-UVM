# Gate B6, Task 3 — A2 replication on RTX 5070 Ti (ASLR regime and bimodality)

Platform: RTX 5070 Ti, sm_120, driver 595.84, srcversion `9E98EF08CBA769C50A24937`
(Task 1 build, loaded via `KO=~/build/nvidia-595.84-specasync/nvidia-uvm.ko` — the
repo-relative default path in `tests/t_a2_bimodality.sh` does not exist on this host).
T4 baseline: `GATE_A2_REPORT.md`, `GATE_A2B_SETARCH_REGIME.md`. This platform's own prior
(earlier, ASLR_OFF-only) result: `GATE_B5_5070TI_REPLICATION.md`.

## Session provenance note

Before this run, the host hit a severe, pre-existing memory exhaustion (~51GB unaccounted
for, unrelated to and predating this task) that blocked even the pinning pre-check. The
NVIDIA driver stack was fully unloaded and ruled out as the cause without recovering the
memory; the user then rebooted the machine. Post-reboot, `free -h` showed a clean 55GB
free/60GB total before any run in this report started, and memory stayed stable throughout
the 44-run session (2.7GB → 14GB used, no OOM, no dmesg anomalies — checked, zero rows with
`dmesg_delta>3`). **This note is procedural only; it does not affect any number below.**

## Protocol

`tests/t_a2_bimodality.sh`, `KO`/`OUT` env overrides pointed at this platform's build and a
fresh `results/analysis/t_a2_bimodality_5070ti/` output directory (the prior false-start
directory under this path was discarded per instruction before this run). C3 (oracle,
depth=1, prefetch OFF), Stencil-24K only. ASLR_ON/ASLR_OFF strictly interleaved
(ON,OFF,ON,OFF,...), 2 warm-up + 20 kept rotations = 44 runs, 20 kept reps/arm. Module
reloaded before every run, `specasync_clear` before every rep. GPU
clocks.current.sm/memory, temperature, power.draw, pstate, throttle reasons, and CPU
loadavg logged before+after every run; allocation base address logged from
`[SPECASYNC_ALLOC]` stderr. Analyzed with `tests/t_a2_analyze.py` (its new `CSV_PATH`
override and `spearman_report` addition, both committed this session).

## Pre-check — does `setarch -R` pin the base VA on this platform?

Required before the full run; the oracle methodology depends on it (per instruction, a
failure here would have been a STOP condition).

| arm | run 1 | run 2 | run 3 |
|---|---|---|---|
| ASLR_ON (bare) | `0x760a4e000000` | `0x736872000000` | `0x7e8252000000` |
| ASLR_OFF (`setarch -R`) | `0x7ffd3e000000` | `0x7ffd3e000000` | `0x7ffd3e000000` |

**Confirmed: pins.** ASLR_OFF held one constant address 3/3, ASLR_ON varied every run —
same qualitative pattern as the T4/B5 reference (`0x7ffdce000000` held 3/3 there; the
absolute address differing here is expected — different platform/binary/session, not a
discrepancy). Held for the full 44-run set too: all 22 ASLR_OFF runs (warmup+kept) share
the single value `0x7ffd3e000000`; all 22 ASLR_ON runs have distinct addresses.

## Result 1 — wall-time distribution per arm

| arm | n | sorted wall_s range | median | variance | split | largest gap | gap/median-other-gap | bimodal (rule: ratio≥3x, both clusters n≥2) |
|---|---:|---|--:|--:|---|--:|--:|---|
| ASLR_ON | 20 | 4.65 – 4.81 s | 4.7100 | 0.001278 | 19 low / 1 high | 0.040 s | 8.00x | **False** (fails n≥2 both sides) |
| ASLR_OFF | 20 | 4.45 – 4.53 s | 4.4900 | 0.000462 | 18 low / 2 high | 0.010 s | ∞ (tied gaps elsewhere) | **True** by the raw rule |

**The ASLR_OFF "bimodal=True" flag is an artifact, not a real cluster split, and is
reported as such rather than absorbed as a positive.** The gap is 0.01s — the measurement
resolution floor of `/usr/bin/time -f "%e"` (matches B5's own characterization of this
exact granularity) — on a distribution that spans only 0.08s total, i.e. genuinely
unimodal. The `ratio=∞` reading is a division-by-zero artifact of tied gaps elsewhere in
the sorted sample, not a large real gap. Both arms are, in substance, unimodal and tightly
packed (0.08–0.16s total spread) — nothing resembling T4's clean 10-low/10-high,
17.25x-gap-ratio split (`GATE_A2_REPORT.md` Result 1, 15.07–17.31s range) appears in
either arm here.

## Result 2 — H1/H2/H3 correlate tables

ASLR_ON's split (19/1) fails the script's own minimum n≥2-per-cluster gate, so no
correlate table is computed for it — correctly, a 1-point cluster gives no meaningful
comparison (weaker than T4's own ASLR_ON split, which was 2/18 and did clear this gate).

ASLR_OFF (18/2 split, flagged bimodal by the raw rule above but treated as non-substantive
per Result 1 — table reported anyway for completeness/transparency):

| check | low (n=18) | high (n=2) | Mann-Whitney p |
|---|---|---|--:|
| H1: base_mod_2mb | {0} | {0} | uninformative — ASLR_OFF is pinned, so base is constant across **all** 22 runs (warmup+kept) in this arm, not just within the split; zero variance by construction, same as T4 |
| H2: temp_after (°C) | 51.5 | 51.5 | 0.8992 |
| H2: sm_clock_after (MHz) | 2850 | 2842 | 0.6610 |
| H2: mem_clock_after (MHz) | 13,800 | 13,800 | 1.000 |
| H2: power_after (W) | 82.94 | 83.13 | 0.8526 |
| H2: cpu_loadavg_before | 1.72 | 1.60 | 1.000 |
| H3: processed | 2.633e6 | 2.644e6 | 0.3789 |
| H3: enqueued | 2.633e6 | 2.644e6 | 0.3789 |

GPU stayed at pstate P1 throughout (T4 stayed at P0 — different but stable in both cases),
throttle bitmask `0x0` in every run, no throttling. All p≥0.36 — no H1, H2, or H3 signal,
consistent with the split being non-substantive rather than a real regime that merely
lacks a cause. `processed == enqueued` in every one of the 44 runs (Task 1/2's finding
holds here again).

## Result 3 — arm-to-arm comparison (question a)

| | ASLR_ON | ASLR_OFF | this platform | T4 (`GATE_A2B_SETARCH_REGIME.md`, C3) |
|---|--:|--:|---|---|
| median wall_s | 4.7100 | 4.4900 | — | ON 16.160 / OFF 15.605 |
| variance | 0.001278 | 0.000462 | ratio (ON/OFF) = **2.765x** | **522.7x** |
| Levene (spread) | | | stat=2.5066, **p=0.1217** | stat=10.659, **p=0.0043** |
| Mann-Whitney (location) | | | stat=400.0, **p=6.197e-08** | stat=60.0, **p=0.472** |

**(a) Does NOT reproduce as a spread difference — reproduces instead as a location shift,
the opposite pattern from the T4.** T4's headline finding was a huge variance ratio
(523x) with a significant Levene's test and no significant median shift (MWU p=0.472) —
a pure spread effect. Here, the variance ratio is a modest 2.8x and Levene's test is not
significant (p=0.12) — **the spread-difference finding does not reproduce**. Instead, the
Mann-Whitney location test is overwhelmingly significant (p=6.2e-8): ASLR_ON is
consistently ~4.9% slower (median 4.71s vs 4.49s) than ASLR_OFF, a real, reproducible
location shift T4 did not show. **Platforms agree that ASLR regime measurably affects
Stencil-24K/C3 wall-clock time, but disagree on which statistic carries the effect** —
spread on the T4, location here — and this is reported in those terms, not folded into a
generic "reproduces."

**Holm-Bonferroni across this task's six pre-declared hypothesis tests** (Levene and MWU
above, plus the four Spearman tests in Results 4/5 below), α=0.05, step-down:

| rank | test | raw p | Holm threshold (0.05/(6−rank+1)) | survives? |
|---|---|--:|--:|---|
| 1 | MWU arm location shift | 6.197e-08 | 0.00833 | **yes** |
| 2 | Levene arm spread | 0.1217 | 0.01 | no — and correction halts here |
| 3 | Spearman wall-vs-processed, ASLR_OFF | 0.1454 | 0.0125 | no |
| 4 | Spearman wall-vs-processed, ASLR_ON | 0.6095 | 0.0167 | no |
| 5 | Spearman rep-vs-wall, ASLR_OFF | 0.7959 | 0.025 | no |
| 6 | Spearman rep-vs-wall, ASLR_ON | 0.8761 | 0.05 | no |

**Only the arm-location shift survives Holm-Bonferroni correction.** Every other
pre-declared test in this task — including the spread difference itself — is null, even
before considering the correction. This is reported as a null, not as a weak positive.

## Result 4 — wall_s vs processed (question b)

| arm | this platform rho | this platform p | T4 rho | T4 p |
|---|--:|--:|--:|--:|
| ASLR_ON | 0.1216 | 0.6095 | -0.2410 | 0.31 (n.s.) |
| ASLR_OFF | 0.3377 | 0.1454 | **0.9747** | **3.6e-13** |

**(b) Does NOT reproduce, in either arm.** T4's ASLR_OFF showed a near-deterministic
monotonic relationship (rho=0.97) between wall-clock time and speculative items
processed — essentially, slower runs did more speculative work. Here neither arm shows a
significant correlation (both p>0.14, both survive nowhere near Holm-Bonferroni). The
brief's fallback question — "if it holds without bimodal split here, note that as an
important distinction" — does not apply, because it does not hold at all: this is a full
non-reproduction, not a partial one. Consistent with this, the `processed` volumes
themselves are tight in both arms here (ASLR_ON median 2,905,234, range
[2,883,622–2,963,941]; ASLR_OFF median 2,632,591, range [2,614,054–2,659,241]) — neither
arm shows T4's own secondary "tight-ON/wide-OFF" processed-volume pattern
(`GATE_A2_REPORT.md` cross-reference: ON ~3.2–3.25M tight, OFF 1.9–2.8M wide). ASLR_ON is
consistently ~10% higher than ASLR_OFF here, a modest, stable offset, not the T4's
volume-variance asymmetry.

## Result 5 — bimodality and run-order drift vs B5 (questions c, d)

| | this platform, ASLR_ON | this platform, ASLR_OFF | B5 (`GATE_B5_5070TI_REPLICATION.md`, ASLR_OFF only) |
|---|--:|--:|--:|
| spread | 0.16 s | 0.08 s | 0.07 s |
| bimodal? | No (fails cluster gate) | No (0.01s tie-artifact, not a real gap) | No — explicitly called unimodal |
| rep_in_cell vs wall_s rho | -0.0373 | -0.0617 | 0.5483 |
| rep_in_cell vs wall_s p | 0.8761 | 0.7959 | **0.0123** |

**(c) Confirms B5 under both arms.** B5 sampled only ASLR_OFF and found a smooth,
unimodal 0.07s-spread distribution with no clean cluster gap. This session confirms that
under **both** arms: ASLR_OFF here is 0.08s spread (near-identical to B5's 0.07s),
ASLR_ON is 0.16s (about double, still unimodal by the same criteria — fails the n≥2/gap
test). Neither arm shows anything resembling T4's genuine bimodality. B5's "does not
reproduce" verdict for bimodality is confirmed under both ASLR regimes, not just the one
B5 happened to sample.

**(d) Does NOT reproduce.** B5 found a small but statistically significant upward
run-order drift under ASLR_OFF (rho=0.548, p=0.0123 — later runs slightly slower). This
session finds no drift in either arm (ASLR_ON rho=-0.037, p=0.876; ASLR_OFF rho=-0.062,
p=0.796) — both near zero, both non-significant, and if anything the point estimate flips
sign (slightly negative vs B5's positive), though neither is distinguishable from zero.
This is a genuine non-replication of B5's own earlier finding, not just of the T4's — flagged
rather than smoothed over. It does not differ meaningfully by ASLR arm here (both null,
same order of magnitude).

## Verdict

Four pre-declared questions, answered directly:

- **(a) Spread-vs-location:** does not reproduce as a spread effect (Levene p=0.12 vs T4's
  p=0.0043); reproduces instead as a strong location shift T4 did not show
  (MWU p=6.2e-8) — platforms agree ASLR regime affects wall-clock time, disagree on which
  statistic carries it.
- **(b) wall_s-vs-processed correlation:** does not reproduce (T4 rho=0.97, p=3.6e-13;
  here both arms rho<0.34, p>0.14, neither significant).
- **(c) Bimodal split:** confirms B5's non-bimodality finding, now under both ASLR arms
  (previously only checked under ASLR_OFF) — neither arm shows a real cluster split; the
  raw split-detection rule flags ASLR_OFF as "bimodal" but that flag is a measurement-
  resolution tie artifact on a 0.08s-total-spread unimodal distribution, not a
  reproduction of T4's genuine 0.69s-gap split.
- **(d) Run-order drift:** does not reproduce B5's own earlier finding (B5 rho=0.548,
  p=0.0123 under ASLR_OFF; here both arms null, rho≈-0.04 to -0.06, p>0.79).

**Net: this platform shows a real, Holm-Bonferroni-surviving ASLR_ON-vs-ASLR_OFF effect on
Stencil-24K/C3 wall-clock time (question a), but it is a different statistical signature
(location, not spread) than the T4's, and none of the finer-grained bimodality/drift/
processed-correlation structure T4 or this platform's own earlier B5 session found
reproduces here.** H1/H2/H3 correlate checks (Result 2) find no clock/thermal/alignment/
volume explanation for even the non-substantive ASLR_OFF split — consistent with there
being no real secondary structure to explain, not with an unexplained-but-real effect
being missed. This is a genuinely different regime from the T4's, not the T4's phenomenon
at reduced magnitude — reported as such rather than assimilated into "reproduces, smaller
effect," the smoothing this task's standing policy explicitly disallows.

## Addendum — three follow-up checks (requested after initial report)

### A1. Relative-magnitude check: is the non-reproduction a resolution artifact?

Computed directly from the T4's own raw data (`results/analysis/t_a2_bimodality/bimodality.csv`,
20 kept ASLR_OFF reps), not assumed:

```
T4 ASLR_OFF sorted wall_s: [15.07, 15.11, 15.13, 15.21, 15.21, 15.21, 15.33, 15.45, 15.52,
  15.64, 16.33, 16.84, 17.16, 17.20, 17.20, 17.22, 17.29, 17.29, 17.31, 17.31]
median = 15.985 s   largest gap = 0.690 s (between 15.64 and 16.33)
gap / median = 4.32%
```

(The `~4.4%` figure in the follow-up request was a fair ballpark; 4.32% is the exact value
from the raw file, used below in place of the estimate.)

Scaling that proportional gap to this platform's own ASLR_OFF median (4.49 s, this report's
Result 3):

```
predicted-equivalent gap = 0.0432 x 4.49 s = 0.194 s
observed TOTAL spread here, ASLR_OFF, all 20 kept reps = 0.08 s (4.45-4.53 s)
0.194 / 0.08 = 2.42x
```

**A gap of T4's proportional size would be 2.42x larger than this platform's entire observed
range, not just larger than one gap within it.** Even measured against `ASLR_ON`'s wider
0.16 s total spread (the more generous comparison), the predicted-equivalent gap (0.194 s)
still exceeds it, 1.21x. `/usr/bin/time -f "%e"`'s resolution (0.01 s) is 19x finer than the
predicted 0.194 s gap — comfortably enough to resolve a gap of that size had one existed.
**The non-reproduction is not a measurement-resolution ceiling effect: a T4-proportional
bimodal split would have been clearly visible in this data, and it is absent.**

### A2. Session-level instability: B5 vs. this report is same-platform, not cross-platform

`GATE_B5_5070TI_REPLICATION.md` and this report ran the **identical** platform (this
machine), identical config (Stencil-24K, C3), identical n=20 kept ASLR_OFF reps, and
reached opposite run-order-drift conclusions: B5 rho=0.548 (p=0.0123, significant); this
report rho=-0.062 (p=0.796, null). Reframing Result 5's (d) verdict: **this is not "B5's
finding fails to reproduce on this platform" in the cross-platform sense used elsewhere in
this report — it is one machine disagreeing with its own earlier session.** Neither
session's drift figure should be read as a stable property of this platform; B5's rho=0.548
must be treated as a single-session result, unreplicated by the next same-config session on
the same hardware, not as established platform behavior. This is recorded here as a threat
to validity for any future claim built on B5's drift figure specifically (the wall-time
spread/bimodality findings in Results 1 and 3 above are not affected — those compare this
report against the T4, a genuine cross-platform comparison, not against B5).

### A3. Speculative-volume variance: consistency with (not proof of) the H3 mechanism

`processed` range as a percentage of median, computed directly from each dataset's raw kept
rows (not the cluster-median figures in Result 2, which describe only the ASLR_OFF
low/high split):

| dataset | n | min | max | median | range as % of median |
|---|--:|--:|--:|--:|--:|
| this platform, ASLR_OFF | 20 | 2,614,054 | 2,659,241 | 2,632,591 | **1.72%** |
| this platform, ASLR_ON | 20 | 2,883,622 | 2,963,941 | 2,905,234 | **2.77%** |
| T4, ASLR_OFF (`t_a2_bimodality/bimodality.csv`) | 20 | 1,853,690 | 2,914,085 | 2,226,272 | **47.63%** |

This platform's `ASLR_OFF` speculative-volume variance is **~28x tighter** than the T4's
(1.72% vs 47.63% of median). `GATE_A2_REPORT.md`'s H3 finding was that wall-clock variance
and `processed`-volume variance move together on the T4 (rho=0.97, Result 4 above) — under
that mechanism, a platform whose speculative-volume variance is this much smaller would be
*predicted* to also show little-to-no wall-clock bimodality, which is exactly what Results 1
and 2 above find. **This is consistency with the H3 mechanism, not proof of its causal
direction** — `GATE_A2_REPORT.md` itself left open whether more processing causes slower
runs or slower runs allow more processing, and this report's data cannot distinguish those
two directions either (Result 4 already found no wall_s-vs-processed correlation here to
even test the relationship on). What this addendum adds is narrower: a mechanism whose
predicted precondition (large volume variance) is absent exactly where its predicted effect
(wall-time bimodality) is also absent is better-corroborated than a bare non-reproduction
with no such link — one data point toward H3 being the right general shape of explanation,
not a demonstration that it is.
