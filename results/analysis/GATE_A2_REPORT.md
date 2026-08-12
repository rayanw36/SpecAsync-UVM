# Gate A2 — combined bimodality experiment (H1/H2/H3)

## Provenance note

The task brief for this session cites `BIMODALITY_TELEMETRY_MINING.md` as an existing document
establishing the ~30%/~46%/18-38% cluster-difference figures and the H1/H2/H3 framing. **No
file by that name (or any "bimodal"-named file besides this report and figures) exists in the
repository** — confirmed by an exhaustive filename and content search. The closest prior record
is `results/analysis/OUTLIER_FORENSICS.md` (Gate 3 non-interleaved, 5/15-high split, Tukey-fence
masking analysis) and `GATE_T1_REPORT.md` (interleaved rerun, 8/20-high, Spearman
rho=-0.011 position-independence). Per this project's standing policy against treating an
unverified prior as settled fact, this report does not cite the missing document's specific
figures and instead re-establishes the bimodal split and its correlates from scratch, in this
session's own data. This does not affect the experiment design or validity below — Task A2 is
self-contained and does not depend on the missing document.

## Design

Single session, C3 (oracle, depth=1, prefetch OFF), Stencil-24K only. Module
`driver/build/nvidia-uvm-specasync-t4-a1.ko` (Task A1's build — includes the
`g_specasync_processed/enqueued/drops` atomics, needed here for the H3 check).

- Arms: `ASLR_ON` (plain invocation, system default `randomize_va_space=2`) vs `ASLR_OFF`
  (`setarch $(uname -m) -R`), strictly interleaved ON,OFF,ON,OFF,... 22 rotations (2 warm-up +
  20 kept), 44 runs total, 20 kept reps/arm. Module reloaded before every single run.
- **`setarch -R` confirmed effective before the run**: four back-to-back invocations showed
  `setarch -R` pins `cudaMallocManaged`'s base to the same address every time
  (`0x7fffce000000`), while plain invocation returns a different base each time
  (`0x7b85fe000000`, `0x7ac67a000000`, ...). No fallback to system-wide
  `randomize_va_space` was needed.
- `bench_stencil.cu` modified to print `[SPECASYNC_ALLOC] grid0=... grid1=... size=...` to
  stderr (does not touch the `[RESULT]` stdout line any existing parser reads). Binary
  rebuilt (`nvcc -O3 -arch=sm_75`); original binary preserved as
  `benchmarks/bench_stencil.orig_backup`.
- Per run: `specasync_clear` before, GPU state (`clocks.current.sm/memory`,
  `temperature.gpu`, `power.draw`, `pstate`, `clocks_throttle_reasons.active`,
  `persistence_mode`) and CPU load average before+after, allocation base address, then
  `g_specasync_processed/enqueued/drops` and full `specasync_log` +
  `specasync_worker_log` dumps after.
- Data: `results/analysis/t_a2_bimodality/bimodality.csv` (44 rows, 40 kept), harness
  `tests/t_a2_bimodality.sh`, analysis `tests/t_a2_analyze.py`.

One bug found and fixed before the real run: the first attempt mixed `/usr/bin/time`'s own
`-f` report and the benchmark's `[SPECASYNC_ALLOC]` stderr into a single redirect, leaving
`wall_s` empty for every row. Fixed by pointing `/usr/bin/time -o` at its own file, separate
from the benchmark's stderr capture. Caught immediately (first row inspected before letting
the full 44-run session proceed) and re-run clean — the aborted first attempt's partial data
was discarded, not used in any of the numbers below.

## Result 1 — bimodality persists under fixed ASLR, and is much weaker under ASLR-on

| arm | n | sorted wall_s range | split | largest gap | gap/median-other-gap |
|---|---|---|---|---|---|
| `ASLR_OFF` | 20 | 15.07 - 17.31 s | **10 low / 10 high** | 0.690 s | **17.25x** |
| `ASLR_ON` | 20 | 16.01 - 16.23 s | 2 low / 18 high | 0.040 s | 4.00x |

`ASLR_OFF` reproduces a clean, large bimodal split (low cluster 15.07-15.64s, high cluster
16.33-17.31s, a ~0.69s gap 17x larger than any other gap in the sorted sample) — consistent
with `GATE_T1_REPORT.md`'s interleaved finding. `ASLR_ON`'s "split" is a much weaker artifact
(2 points marginally below an otherwise tight, continuous 16.07-16.23s band) — the
gap-detection heuristic technically flags it, but it is not the same phenomenon: an order of
magnitude smaller gap, on a distribution that is otherwise essentially unimodal. **The real
bimodal effect is specific to `ASLR_OFF` (fixed address) in this data, not present in any
comparable strength under `ASLR_ON` (randomized address).**

This is already a first, cheap signal against H1: if page-address instability were the cause,
the arm with a *varying* address (`ASLR_ON`) should show the effect, and the arm with a fixed
address (`ASLR_OFF`) should not. The data shows the opposite.

## Result 2 — H1 (alignment): structurally dead in both arms

`base % 2MB` is **exactly 0 in every single run, in both arms** — not just similar, identical.
`ASLR_ON`'s absolute addresses do vary run-to-run (confirming ASLR is genuinely active for
this arm — e.g. `0x7298ce000000`, `0x704346000000`, `0x74aeea000000`, ...), but every one of
them lands on a 2 MB boundary; `ASLR_OFF`'s address is pinned to a single constant value
(`0x7fff46000000`) as designed. Since alignment-within-2MB has zero variance in both arms,
**H1's specific mechanism (page-offset misalignment) has no variance to correlate with
anything, full stop** — this is the "if base addresses are identical, H1 is dead" cheap check
the task asked for, confirmed at the alignment level rather than the absolute-address level
(absolute address does vary under `ASLR_ON`, but that variation is orthogonal to the
`ASLR_OFF` bimodal split, which occurs at a *literally constant* address).

`ASLR_OFF`'s Mann-Whitney comparison of `base_mod_2mb` between its own low/high clusters is
undefined (both clusters share the single constant value by construction) — not weak
evidence, no evidence, by definition. **H1 rejected.**

## Result 3 — H2 (clock/thermal/power): no correlation in either arm

| arm | field | low median | high median | Mann-Whitney p |
|---|---|---|---|---|
| ASLR_OFF | temp_after (C) | 41 | 41 | 1.000 |
| ASLR_OFF | sm_clock_after (MHz) | 1590 | 1590 | 1.000 |
| ASLR_OFF | mem_clock_after (MHz) | 5000 | 5000 | 1.000 |
| ASLR_OFF | power_after (W) | 38.0 | 37.8 | 0.520 |
| ASLR_OFF | cpu_loadavg_before | 1.73 | 1.79 | 0.450 |
| ASLR_ON | temp_after (C) | 42 | 41 | 0.0049 |
| ASLR_ON | sm_clock_after (MHz) | 1590 | 1590 | 1.000 |
| ASLR_ON | power_after (W) | 36.6 | 37.8 | 0.528 |

GPU clocks never left `P0`/1590 MHz SM/5000 MHz mem in any run in either arm; throttle-reason
bitmask was `0x0` throughout (no thermal or power throttling at any point). `pstate` was `P0`
for every run. `ASLR_OFF` — where the real, strong bimodal split lives — shows **no**
significant clock/thermal/power/CPU-load difference between clusters (all p≥0.45, most
p=1.0 exactly, identical medians). The one nominally significant p-value (temp_after,
`ASLR_ON`, p=0.0049) sits in the arm whose "split" is the weak 2-vs-18 artifact from Result 1
(a 1°C median difference, on n=2 vs n=18, is not a meaningful clock/thermal effect on a GPU
that never moved off P0/1590 MHz) and does not survive scrutiny as a real H2 signal. **H2
rejected** for the arm that actually shows the phenomenon.

## Result 4 — H3 (processed items): the decisive positive result

| arm | processed low median | processed high median | Mann-Whitney p |
|---|---|---|---|
| **ASLR_OFF** | 1,919,000 | 2,682,000 | **0.0001827** |
| ASLR_ON | 3,248,000 | 3,246,000 | 0.263 (n.s.) |

In `ASLR_OFF`, the high (slow) wall-time cluster processes **~40% more speculative items**
than the low (fast) cluster — highly significant (p=0.0002), and (per Task A1's finding)
`processed == enqueued` exactly in every one of these 40 runs too, so this is unambiguously
"processed more," not "queued more but throttled the same" — exactly the condition the task's
decision rule maps to H3, not H1/H2.

**This is not just a two-cluster effect — it is a strong continuous, monotonic relationship
across the full sample.** Spearman correlation between `wall_s` and `processed`, all 20 kept
`ASLR_OFF` reps:

```
ASLR_OFF: wall_s vs processed   Spearman rho = 0.9747   p = 3.6e-13
ASLR_OFF: rep_in_cell vs wall_s  Spearman rho = 0.1176   p = 0.62   (no run-order drift)
ASLR_ON:  wall_s vs processed   Spearman rho = -0.2410  p = 0.31   (n.s.)
ASLR_ON:  rep_in_cell vs wall_s  Spearman rho = -0.3441  p = 0.14   (n.s.)
```

`rho=0.97` is close to a deterministic monotonic relationship — essentially every extra
speculative item processed corresponds to more wall time, continuously, not just in a
two-state jump. This is not explained by warm-up or session drift (`rep_in_cell` vs `wall_s`
is uncorrelated, p=0.62, matching `GATE_T1_REPORT.md`'s own position-independence check).
`ASLR_ON` shows neither the wall-time spread nor the processed-items correlation. **H3
accepted for `ASLR_OFF`.**

## Verdict (per the task's fixed decision rule)

- Alignment correlation (H1): **none** — `base % 2MB` has zero variance in both arms; the
  effect appears at a *literally fixed* address. H1 rejected.
- Clock/thermal correlation (H2): **none** — GPU never leaves P0/1590MHz/5000MHz, no
  throttling, no significant power/temp/load difference in the arm that shows the effect. H2
  rejected.
- Processed-item difference (not just enqueued): **yes, strongly** (p=0.0002 cluster test,
  rho=0.97 continuous test). **→ H3: speculation volume is real work being done, and scales
  with wall time.**

**Cause vs. symptom remains genuinely open, exactly as the task anticipated by routing an H3
finding to "discussion section" rather than declaring it fully resolved.** Two directions are
both consistent with `rho=0.97`:
1. Doing more speculative migration work (more `MIGRATION_DONE` results, each holding the
   VA-block lock and performing an actual page migration at `offload_depth=1`) directly costs
   wall time — extra real work slows the run.
2. A run that is slower for some *other* reason gives the demand-fault stream more wall-clock
   time to run before finishing, and — since the async worker races the same demand stream —
   a slower run structurally allows more items to reach dispatch before the corresponding
   address is already resident, so more get queued and processed as a **consequence** of the
   slowdown rather than its cause.

This session's data cannot distinguish these two directions (both predict the same
correlation), and per the task's own instructions this ambiguity is reported honestly rather
than resolved by assertion. What the data **does** rule out is any process/thermal/alignment
explanation external to the speculation mechanism itself — whichever direction is true, the
bimodal split is intrinsic to the speculative pipeline's own load, not an artifact of ASLR,
ambient GPU throttling, or CPU contention.

## Cross-reference to Task A1

`ASLR_OFF`'s `processed` totals here (1.9-2.8M/run) sit squarely inside Task A1's full-run
range (2.05-2.7M/run, same Stencil-24K/C3 config, different session) — consistent, not a new
anomaly. `ASLR_ON`'s totals cluster tightly around 3.2-3.25M — noticeably higher and far less
variable than `ASLR_OFF`'s. This is a secondary, unplanned observation (ASLR state
apparently affects *typical* speculative volume, not just its variance) worth flagging for a
future pass but outside this task's scope to chase further.

**Gate A2: bimodality reproduces under fixed ASLR, is much weaker under randomized ASLR
(opposite of an H1 prediction), correlates with neither alignment nor GPU/CPU
clock-thermal-load state, and correlates strongly and continuously (rho=0.97) with
speculative items processed. Verdict: H3, with cause-vs-symptom direction left open for
discussion. Proceeding to Task A3.**

## Addendum (2026-08-12) — provenance note update

The Provenance note above states that no file named `BIMODALITY_TELEMETRY_MINING.md` exists in
the repository. That was accurate at the time A2 ran. The document has since arrived via the
merge from the desktop session (`git log` commit `81a0db9`, merged into `manuscript-prep` at
`64dfc56`), and now lives at `results/analysis/BIMODALITY_TELEMETRY_MINING.md`. This addendum
does not edit the note above — it stands as an accurate record of what was known when A2 ran —
and instead cross-checks its now-available figures against this report's independently
re-derived numbers.

**Same underlying figures the provenance note flagged as uncited:** `BIMODALITY_TELEMETRY_MINING.md`
Task 1.1 reports, from T1's original interleaved C3/Stencil-24K telemetry (8 high / 12 low
split, no ASLR arm), `spec_enqueued` +29.69%, `spec_drops` -46.22%, and four timing-phase sums
in the +17.42%–+38.42% range between high/low clusters — precisely the "~30%/~46%/18-38%"
figures the task brief originally cited and this report's provenance note could not verify.
Confirmed: those figures are real and are in the document, sourced from `results/phaseB2/gate3_interleaved/telemetry/`.

**Agreement with A2's independent numbers:** A2's own `ASLR_OFF` cluster split (10 low / 10 high,
this session's own `t_a2_bimodality.sh` run) gives a `processed` (== `enqueued`, per A1) delta of
(2,682,000 − 1,919,000) / 1,919,000 ≈ **+39.7%** — same direction and comparable order of
magnitude to the mining document's +29.69% `spec_enqueued` delta, not an exact match, which is
expected: different sessions, different cluster boundaries (A2's 10/10 vs the mining document's
8/12), and A2 additionally interleaves an ASLR arm the mining document's source data does not
control for. No discrepancy in direction, mechanism, or order of magnitude.

**Same H1/H2/H3 verdict, arrived at independently:** the mining document's "Preliminary
hypothesis read" section calls H1 "disfavored, not dead" pending the allocation-base logging
check it flags as not yet run, and calls H2 "plausible, not confirmed" pending GPU clock/thermal
logging it also flags as not yet run. A2's Result 2 and Result 3 are exactly those two
follow-up checks, run for the first time in this report: H1 is now **rejected outright**
(`base % 2MB` has zero variance in both ASLR arms) and H2 is now **rejected** for the arm that
shows the effect (no significant clock/thermal/power/load difference, GPU never leaves P0). Both
outcomes are consistent with the mining document's framing — it correctly identified these as
the decisive open checks and did not prejudge their outcome. A2's H3 verdict (accepted, with
cause-vs-symptom direction left explicitly open) matches the mining document's own H3 read
word-for-word: "the data is consistent with this, but cannot be distinguished from a queue-race
symptom of H1/H2" and "[t]hese are observationally identical in this counter set. Nothing here
adjudicates between them." No discrepancy.

**One scope caveat, not a contradiction:** the mining document's residual H1/H2 concern is
raised specifically in its **C1** discussion — "C1 has no speculative queue at all, yet its core
batch-service loop... still varies enough to correlate with total wall time... points at
something in the baseline UVM fault-servicing loop itself" — whereas A2's H2 rejection (Result 3)
tested only **C3**. A2 did not re-test C1's clock/thermal state, so the mining document's C1
observation is neither confirmed nor refuted by this report; it remains open. This is exactly the
question Task 2 of this work block (`GATE_A2B_SETARCH_REGIME.md`) is designed to resolve — whether
the ASLR-driven wall-time effect this report documents (Result 1) is present in C1 (general
allocation/paging effect, matching the mining document's residual C1 concern) or specific to C3
(speculation-pipeline effect, matching this report's H3 verdict).

**Net: no numeric or interpretive discrepancy found.** The two documents were produced by
independent sessions on different data slices and reach the same H1-rejected/H2-rejected(-for-C3)/
H3-accepted-with-open-causality verdict, with comparable effect sizes on the metrics they share.
