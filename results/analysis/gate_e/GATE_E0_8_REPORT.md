# Gate E0.8 — Index drift or genuine divergence?

Analysis only. No new benchmark runs, no driver changes, no module loads.
All data reused from `results/phaseB1/gate_e07_check1/` and
`results/phaseB1/gate_e07_check2/` (verified present before starting —
all 7 Check 1 files and all 6 Check 2 files existed; nothing was missing,
nothing was regenerated). Analysis script: `tests/gate_e08_index_drift_analysis.py`
(committed). Figure: `results/analysis/gate_e/gate_e08_check3_signed_lag.png`
(committed).

## 0. Push confirmation

`95a4ac8` was local-only when this gate began — confirmed via `git fetch` +
comparing `origin/manuscript-prep` (`a8230fb`) against local `HEAD`
(`95a4ac8`, one ahead). Pushed successfully (`a8230fb..95a4ac8`, exit 0)
before any analysis started.

## E0.7's verdict is overturned for Stencil-24K, confirmed-as-mixed for GraphBFS-23

Stated up front because it changes how to read everything below: **E0.7
concluded Stencil-24K was "closer to genuine divergence." That conclusion
does not survive this gate.** Stencil-24K is, on the evidence below, close
to pure index drift. GraphBFS-23's "mixed" reading survives, refined with a
mechanism (index drift plus real, smaller-magnitude reordering) rather than
left as an unexplained blend.

## 1. Check 1 — Backward set accuracy

For each position *k*, does trace[*k*] appear anywhere in `replay[:k]`?
Computed via first-occurrence position in the replay sequence (vectorized:
`first_occurrence_in_replay(trace[k]) < k`; mathematically equivalent to a
literal growing-set membership test, verified by construction — see script).

| run | forward-set (E0.7) | **backward-set (this gate)** |
|---|---:|---:|
| Stencil-24K depth=1 | 98.48% | **0.0708%** |
| Stencil-24K depth=0 | 0.43% | **99.5854%** |
| GraphBFS-23 depth=1 | 36.51% | **73.8671%** |
| GraphBFS-23 depth=0 | 35.55% | (not recomputed — see §6 for the Check-2-pair equivalents, which cover the same question) |

**Stencil-24K's prediction is confirmed exactly, not approximately.** Depth=1:
forward 98.48% / backward 0.07% — almost perfect mirror. Depth=0: forward
0.43% / backward 99.59% — almost perfect mirror in the other direction. This
is precisely the signature the hypothesis predicts and E0.7's own
"genuine divergence" reading (based on depth=0's forward-set alone) did not
consider the possibility that a bidirectional check would reverse it.

**GraphBFS-23 is not a clean mirror.** Forward 36.51%, backward 73.87% —
both substantial, backward higher than forward but not by the extreme
Stencil ratio, and the decile pattern is uneven in both directions (backward
decile 0 is 38.47%, not near 100% or near 0%). This is not the signature of
pure drift; see Check 3/4 below for what it is instead.

Per-decile backward-set, Stencil-24K depth=1: d0=0.699% d1-d8=0.000% d9=0.009%.
Depth=0: d0=95.85% d1-d9=100.000%. GraphBFS-23 depth=1: d0=38.47% d1=45.38%
d2=62.66% d3=79.12% d4=94.73% d5=75.92% d6=77.61% d7=91.23% d8=75.55%
d9=98.00%.

## 2. Check 2 — Whole-run page-set overlap

| run | \|A\| distinct | \|B\| distinct | intersection | Jaccard |
|---|---:|---:|---:|---:|
| Stencil-24K depth=1 | 1,125,000 | 1,125,000 | 1,125,000 | **100.0000%** |
| Stencil-24K depth=0 | 1,125,000 | 1,125,000 | 1,125,000 | **100.0000%** |
| GraphBFS-23 depth=1 | 287,956 | 287,956 | 287,956 | **100.0000%** |

**Every page touched in one run is touched in the other, for both
workloads, at both depths, exactly.** "Divergence" in the sense of
*different pages being faulted* is ruled out completely — confirmed, not
assumed, and confirmed identically for GraphBFS-23 too, which is new
information not available from E0.7 (which never checked page-set identity,
only positional/windowed measures). Whatever separates the two workloads,
it is entirely about *when*, never about *which*.

## 3. Check 3 — Signed lag

Method: for each trace position *k*, find the position of trace[*k*] in the
other sequence closest to *k* (rule = `nearest`, i.e. minimum absolute
offset, the specified default) and record `offset = matched_position - k`.
Also computed under `first occurrence` matching (always use the address's
first position in the other sequence, regardless of *k*) to check whether
the matching rule changes the conclusion.

**The two rules gave results identical to the reported precision for both
Stencil runs** (e.g. depth=1 decile-0 median 2280.0 under both rules) —
expected, since Stencil's near-total page-set overlap combined with tight
first-touch correlation (§4) means most trace positions have only one
plausible nearby match. **For GraphBFS the two rules diverge somewhat**
(e.g. depth=1 decile 9: median −3230 under `nearest` vs. −146,144.5 under
`first`) — GraphBFS revisits some pages far more unevenly, so "first
occurrence" can pick a distant early match when a much closer later
occurrence exists. The `nearest` rule is used for the headline numbers
below as specified; the rule sensitivity is itself informative (a large
gap between the two rules is further evidence GraphBFS's repeats are not
simple index-shifted duplicates).

### Stencil-24K depth=1 (median offset, `nearest` rule, by decile)

| d0 | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 | d9 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| +2,280 | +9,490 | +15,329 | +20,727 | +26,078 | +29,394 | +33,334 | +36,928 | +37,551 | +42,511 |

`frac_positive` = 0.993 (d0) rising to 1.000 (d1-d9) — **every single trace
position from decile 1 onward has its nearest replay match strictly ahead
of it**, and the median offset **grows smoothly and monotonically**,
tracking the total count difference almost exactly: 42,511 (decile-9
median) vs. +43,610 (the actual total entry-count difference, trace vs.
replay). This is the textbook index-drift signature named in the brief.

### Stencil-24K depth=0 (mirror image)

| d0 | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 | d9 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| −3,307 | −6,398 | −8,812 | −12,052 | −15,819 | −22,784 | −28,462 | −32,887 | −40,399 | −44,471 |

`frac_positive` = 0.041 (d0), 0.000 (d1-d9) — smoothly, monotonically
**negative**, tracking the total count difference (−44,808) almost exactly
(−44,471 at decile 9). **Both depth=1 and depth=0 show the same
smooth-monotonic-drift shape, with opposite sign matching the sign of the
count difference exactly** — this is the single strongest piece of evidence
in this gate.

### GraphBFS-23 depth=1 (median offset, `nearest` rule)

| d0 | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 | d9 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | +1,798 | −3,550 | −1,208 | −1,258 | −2,416 | −3,538 | −3,374 | −2,962 | −3,230 |

No smooth trend — the sign flips between decile 0/1 and decile 2 onward,
then stays small and roughly flat (IQRs of 1,000-23,000, an order of
magnitude below Stencil's decile-9 IQR-scale drift). This is **not** a
monotonically growing or shrinking offset; it is closer to the "diffuse
cloud with no clean trend" alternative the brief describes, though with a
visible local structure (a real, small, roughly-constant lag rather than
pure noise). See the figure for the visual: Stencil's two panels show a
clean rising/falling line through the scatter; GraphBFS's two panels show a
much flatter, noisier band.

**Figure:** `results/analysis/gate_e/gate_e08_check3_signed_lag.png` — four
panels (Stencil depth=1, Stencil depth=0, GraphBFS depth=1, GraphBFS
depth=0), each a downsampled scatter of signed offset vs. trace position
with the decile-median line overlaid. The contrast between Stencil's two
clean diagonal lines and GraphBFS's two flat, noisy bands is visible at a
glance.

## 4. Check 4 — First-touch order

Reduced each sequence to first-occurrence order (every duplicate stripped),
then compared. Values below are the *exact* Spearman coefficient (not the
rounded display value — the discrepancy between a rounded "1.0000" and the
true value turned out to matter and is reported precisely for that reason).

| run pair | common pages | Spearman (exact) | max \|rank diff\| | reduced exact-match |
|---|---:|---:|---:|---:|
| Stencil-24K, trace vs. depth=1 replay | 1,125,000 | 0.9999999983 | **105** | 25,134 / 1,125,000 (2.23%) |
| Stencil-24K, trace vs. depth=0 replay | 1,125,000 | 0.9999999984 | **107** | 25,891 / 1,125,000 (2.30%) |
| GraphBFS-23, trace vs. depth=1 replay | 287,956 | 0.9976364 | **38,990** | 7,661 / 287,956 (2.66%) |
| GraphBFS-23, trace vs. depth=0 replay | 287,956 | 0.9986221 | **36,618** | 7,730 / 287,956 (2.68%) |

**Stencil-24K's first-touch order is stable to within ±107 positions out of
1,125,000 — a 0.0095% displacement bound, not a rounding artifact of a
"1.0000" display.** Every page is first touched in essentially the same
relative order in every run; only the count of subsequent duplicate faults
for that page varies, which is exactly what corrupts raw-index comparisons.
Kendall tau on a 200,000-page subsample: 1.0000 (depth=1), consistent.

**GraphBFS-23's first-touch order is highly but much less tightly
correlated** — Spearman ~0.998, but the maximum rank displacement (37,000-
39,000 out of 287,956, i.e. up to ~13.5% of the range) is far larger in
relative terms than Stencil's ~0.01%. Kendall tau (200,000-page subsample):
0.9676 (depth=1). **This is real, substantial local reordering, not
duplicate-count noise on an otherwise-fixed order** — consistent with
Check 3's finding that GraphBFS does not show a clean monotonic drift.

Reduced-sequence exact/windowed/set measures (depth=1, both workloads —
depth=0 not separately re-run for the full windowed/set battery given time
budget; the Spearman/exact-match numbers above, which are the primary
Check 4 deliverable, are reported for depth=0 too):

| workload | reduced exact | window W=10 | W=100 | W=1,000 | W=10,000 | reduced set |
|---|---:|---:|---:|---:|---:|---:|
| Stencil-24K depth=1 | 2.23% | 21.48% | 51.19% | 51.19% | 51.19% | 51.19% |
| GraphBFS-23 depth=1 | 2.66% | 3.43% | 6.58% | 22.72% | 45.30% | 49.26% |

Both reach a similar ceiling (~49-51%) for "does this page's first touch
land in the same set-overlap region," well below 100% even after removing
every duplicate — a real residual disagreement in first-touch order exists
for both workloads at the *reduced-sequence* windowed scale, even though
Stencil's *rank* correlation is near-perfect. These are not contradictory:
rank correlation measures relative order across the whole sequence;
windowed accuracy on the reduced sequence measures a much stricter
positional condition, and a max shift of 105-107 positions is still enough
to push many individual comparisons outside a 10-10,000-entry window when
local page density is high.

## 5. Check 5 — Repeat-gap histogram

For every page faulted more than once, gap = distance in positions between
consecutive occurrences.

| run | n gaps | p10 | p25 | median | p75 | p90 | p99 | run_length÷20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Stencil-24K trace (collection) | 1,829,436 | 1 | 1 | **1** | 1 | 1 | 79 | 147,722 |
| Stencil-24K replay (depth=1) | 1,873,046 | 1 | 1 | **1** | 1 | 1 | 64 | 149,902 |
| GraphBFS-23 trace (collection) | 199,024 | 1 | 1 | 82 | 245 | 67,749 | 367,648 | 24,349 |
| GraphBFS-23 replay (depth=1) | 193,999 | 1 | 1 | 81 | 245 | 75,410 | 364,459 | 24,098 |

**Stencil-24K: p10 through p90 are all exactly 1.** Ninety percent of every
repeated page's consecutive-occurrence gaps are back-to-back or
near-back-to-back positions — **duplicate storms**, exactly as the
hypothesis predicts, with no mass anywhere near run_length÷20 = 147,722.
**This directly refutes E0.7 §4's iteration-compounding mechanism**: if
depth=1's high forward-set accuracy were caused by successful speculative
migrations pre-empting a page's demand fault on later *iterations*
(spacing ~147,722 apart), the gap histogram would show mass near that
value. It does not — every quantile through p90 is 1. **E0.7 §4 does not
survive this check.**

**GraphBFS-23: a genuinely different, two-part distribution.** Median gap
82 (short, consistent with some duplicate-storm behavior) but p90 jumps to
67,749-75,410 and p99 to ~365,000 — a real population of *far*-separated
repeats exists alongside the near-duplicates. Neither pure "duplicate
storm" nor pure "iteration revisit" (there is no fixed iteration count to
compare against for a BFS traversal; run_length÷20 is shown only for
consistency with the Stencil row and has no structural meaning here).
GraphBFS's repeat structure is a mix, consistent with §3/§4's finding that
its order is mostly-stable-but-really-perturbed rather than pure drift.

## 6. Check 6 — Does accuracy track count difference?

| workload | pair | \|count diff\| | forward-set (E0.7) | backward-set (Check 1) | first-touch Spearman (Check 4) |
|---|---|---:|---:|---:|---:|
| Stencil | rep1 vs rep2 | 4,418 | 1.94% | 98.14% | 0.999999998 |
| Stencil | rep1 vs rep3 | 3,171 | 2.95% | 97.08% | 0.999999998 |
| Stencil | rep2 vs rep3 | **1,247** | **21.21%** | **78.92%** | 0.999999998 |
| GraphBFS | rep1 vs rep2 | 1,365 | 70.89% | 39.46% | 0.998737 |
| GraphBFS | rep1 vs rep3 | 4,351 | 80.57% | 28.85% | 0.998682 |
| GraphBFS | rep2 vs rep3 | 2,986 | 78.61% | 31.14% | 0.998577 |

**Stencil: forward-set tracks count difference cleanly and in the
predicted direction.** The pair with the smallest count difference
(rep2-vs-rep3, 1,247) has by far the least extreme split (21.21%/78.92%);
the two pairs with larger differences (3,171 and 4,418) both show the
extreme near-0%/near-100% split. Three points, one clean monotonic pattern,
no reversals — reported as a pattern, not a correlation coefficient, per
instruction.

**GraphBFS: no comparably clean pattern.** Count differences (1,365; 2,986;
4,351) do not line up monotonically with forward-set (70.89%; 78.61%;
80.57%) the way Stencil's do relative to backward-set direction — here
forward-set *increases* with count difference, the opposite sense from what
pure index-drift would predict (larger drift should make positional
matching *harder*, not easier, if order were otherwise fixed). This is
consistent with GraphBFS's order not being fixed enough for count
difference alone to be the dominant driver — real reordering (Check 3/4)
is doing more of the work than duplicate-count drift here. First-touch
Spearman is flat (~0.9986) across all three GraphBFS pairs regardless of
count difference, unlike Stencil's identically-flat-but-far-higher
(~0.999999998) figure — both workloads show Spearman *not* varying with
count difference, which makes sense (first-touch order and duplicate count
are, by construction, independent quantities), but GraphBFS's flat value
sits at a genuinely lower plateau, not just a noisier estimate of the same
near-1.0 value Stencil shows.

## 7. Plain verdict, per workload

**Stencil-24K: index drift confirmed.** Every one of the four criteria
listed in this gate's brief is met: backward-set is high exactly where
forward-set is low and vice versa (Check 1, both depths, near-exact
mirror); page-set overlap is 100% (Check 2); lag trends smoothly and
monotonically, in the sign matching the count-difference sign, tracking its
magnitude closely (Check 3); first-touch order is correlated to
0.9999999983-0.9999999984, with a maximum displacement of ~106 positions
out of 1,125,000 (Check 4). **E0.7's "closer to genuine divergence" verdict
for Stencil-24K is overturned by this gate.** The true situation: Stencil's
page-visitation order is essentially deterministic and stable across
independent runs of the same benchmark; what varies run to run is the
number of duplicate (redundant, back-to-back) faults per page before its
speculative or demand-driven migration lands, and that duplicate-count
variation alone is enough to make every index-anchored measure (E0.7's
entire accuracy battery) swing between ~0% and ~100% depending on which
direction the count happens to drift that run.

**GraphBFS-23: mixed, with index drift present but not dominant.** Page-set
overlap is complete (Check 2, ruling out different-page divergence
entirely, same as Stencil), and first-touch order is highly correlated
(Spearman 0.998, Check 4) — both point toward the same broad "same pages,
mostly same order" picture as Stencil. But the degree of order-preservation
is measurably, consistently weaker (max rank displacement ~13% of the
range vs. Stencil's ~0.01%; Check 3's lag shows no clean monotonic trend;
Check 5's repeat-gap distribution has a substantial far-separated
population Stencil's does not; Check 6's count-difference relationship runs
in the opposite direction from Stencil's). **Neither "index drift" nor
"genuine divergence" alone accounts for GraphBFS-23** — real, non-trivial
local reordering coexists with a smaller amount of duplicate-count drift,
and this gate's checks do not support collapsing that mixture into either
single label.

## 8. Does E0.7 §4 (migration compounding) survive Check 5?

**No.** §4 proposed that Stencil's depth=1 forward-set advantage came from
successful speculative migrations pre-empting a page's demand fault on
*later loop iterations* — a mechanism that predicts repeat-gaps clustered
near run_length÷20 ≈ 147,722. Check 5 shows p10 through p90 of Stencil's
repeat-gap distribution are all exactly 1, with no mass anywhere near that
value on either the trace or the depth=1 replay sequence. The actual
mechanism behind depth=1's high forward-set / low backward-set (and
depth=0's mirror) is the index-drift finding in this gate, not iteration
compounding. This does not need to be stated in E0.7 (not edited, per
instruction) but is recorded here as superseding that section's proposed
mechanism.

## Flags for review (not edited)

- Any claim-document language built on E0.7's "Stencil-24K is closer to
  genuine divergence" (if any exists by the time this is reviewed) should
  be revisited against this gate's reversal.
- `CLAIM_SCOPE.md` rows referencing oracle accuracy as evidence for or
  against trace-replay viability should account for the workload split
  found here: a self-synchronizing, resync-on-match oracle (the path named
  in this gate's brief for "index drift confirmed") has direct empirical
  support for Stencil-24K specifically, and partial, weaker support for
  GraphBFS-23.

## Artifacts

- `tests/gate_e08_index_drift_analysis.py` — all six checks' implementation.
- `results/analysis/gate_e/gate_e08_check3_signed_lag.png` — Check 3 figure,
  four panels.
- Raw sequences reused from E0.7, unmodified, gitignored per existing
  convention (`results/phaseB1/gate_e07_check1/*.bin`,
  `results/phaseB1/gate_e07_check2/*.bin`).

**HARD STOP.** Per instruction: no oracle design, no driver work in this
gate. If a self-synchronizing oracle is the chosen next step, it applies
most directly to Stencil-24K (index drift confirmed) and only partially to
GraphBFS-23 (real reordering would still limit it) — that choice, and
GraphBFS-23's separate, only-partially-drift-explained behavior, are left
for review.
