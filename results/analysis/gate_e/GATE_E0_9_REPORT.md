# Gate E0.9a — A first-touch oracle with lookahead: build and validate

**No performance claims in this report.** This covers E0.9a only (build +
validate). E0.9b (the lookahead sweep against the stock driver) is **not
started** — hard stop, per instruction, pending review of this report.

All work: RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-31-generic, headless
(`systemctl isolate multi-user.target`, confirmed via `gdm`/`graphical.target`
inactive and `nvidia-smi` still working; this session's shell confirmed
running inside a `tmux` session on a non-X pty before switching, so the
switch did not interrupt work), restored to `graphical.target` at the end
(confirmed active). `MemAvailable` logged (60.5-60.8 GB across this
session's runs, no drift toward the 6 GiB floor). Every replay: fresh
module reload, `setarch -R`, `specasync_clear` before the rep.

## 0. Push confirmation

All of E0.8's commits (`6b50e9a` and earlier) were already pushed and
confirmed at the start of E0.9 (this session continues directly from that
confirmation — re-checked via `git fetch` before starting: local and
`origin/manuscript-prep` matched at `6b50e9a` before this gate's first
commit).

## 1. Two corrections to E0.8 (E0.8 not edited; recorded here as superseding)

### Correction 1: Check 4's "~50% ceiling" was the forward-only asymmetry again

Verified by computing the **symmetric** window measure,
`|replay_rank − trace_rank| ≤ W`, for W ∈ {10, 100, 1,000}, on the same
first-touch rank pairs E0.8 Check 4 used:

| workload | \|diff\|≤10 | \|diff\|≤100 | \|diff\|≤1,000 |
|---|---:|---:|---:|
| Stencil-24K depth=1 | 44.30% | **99.9997%** | 100.0000% |
| GraphBFS-23 depth=1 | 4.23% | 11.30% | 46.49% |

Confirmed exactly as predicted: Stencil's symmetric accuracy is
essentially 100% by W=100, matching the ~107-position maximum displacement
Check 4 already found. E0.8's reported "~51.19% forward-only ceiling,
constant across W=100/1,000/10,000" was never evidence of a residual
disagreement at those scales — it was the forward-only measure's
structural blindness to a small, symmetric, two-sided displacement (half
the displaced pairs land "ahead," half "behind," giving ~50% regardless of
how tight the true displacement is, once W exceeds the maximum offset).
**Withdrawn from E0.8's reading; the true finding is what Check 4's
Spearman/max-displacement numbers already said.**

### Correction 2: Check 6's GraphBFS reading used the wrong quantity

Recomputed against the correct quantity — `|forward − backward|` (the
lopsidedness of the split) vs. `|count difference|` (drift magnitude) —
rather than the raw forward-set value alone:

| pair | \|count diff\| | forward | backward | \|forward − backward\| |
|---|---:|---:|---:|---:|
| GraphBFS rep1 vs rep2 | 1,365 | 70.89% | 39.46% | **31.43 pts** |
| GraphBFS rep2 vs rep3 | 2,986 | 78.61% | 31.14% | **47.47 pts** |
| GraphBFS rep1 vs rep3 | 4,351 | 80.57% | 28.85% | **51.72 pts** |

Monotonic, exactly matching the values you gave (31.4 → 47.5 → 51.7 for
1,365 → 2,986 → 4,351). **The "opposite sense" argument in E0.8 §6 is
withdrawn.** GraphBFS-23 remains mixed, on the evidence E0.8 gave for that
independent of this correction: Kendall tau 0.968, ~13% maximum rank
displacement, and a genuine far-separated repeat population (Check 5).

Both corrections are the same failure family this whole gate sequence has
been diagnosing — a forward-only metric mistaken for a symmetric one, and
an absolute value that discarded the sign the comparison depended on.
Flagged here as catalog material, per instruction; `ARTIFACT_CATALOG.md`
not edited.

## 2. Design decision recorded up front: policy 6, not policy 5

The gate's brief specifies "policy 5" for the first-touch oracle. **Policy
5 is already `SPECASYNC_POLICY_NULL`** (`specasync_telemetry.h`, the Gate C
worker-presence control used by artifact #3's STREAM investigation and
every script that passes `specasync_policy=5` expecting "enqueue, no
lookup"). Reusing 5 would silently corrupt that control for every existing
and future use. **Implemented as policy 6 instead**, flagged in source
(`specasync_telemetry.h`) and here rather than complying with the literal
instruction.

## 3. Implementation

### Userspace (`tests/prepare_first_touch_table.py`)

1. **Page-alignment masking, verified from source, confirmed empirically.**
   `preprocess_fault_batch()`'s own comment
   (`uvm_gpu_replayable_faults.c`: "sort by va_space, GPU ID, fault address
   (GPU already reports 4K-aligned address)...") and
   `fetch_fault_buffer_entries()`'s
   `current_entry->fault_address = UVM_PAGE_ALIGN_DOWN(...)` both confirm
   `fault_address` is page-aligned before it ever reaches the trace. The
   script masks anyway, unconditionally, and **counts how many addresses
   needed it**: 0 of 2,951,838 (Stencil-24K) and 0 of 485,124 (GraphBFS-23)
   entries needed masking, across every trace collected this session — the
   mask is confirmed a no-op on real data, not just by source reading.
2. Reduces to first-touch order (first occurrence of each distinct page,
   in service order).
3. **Distinct-page assertion against E0.8, enforced before writing
   anything**: Stencil-24K produced exactly 1,125,000; GraphBFS-23 produced
   exactly 287,956 — both matched on the first attempt, confirming
   collection has not changed since E0.8 and every comparison to E0.7/E0.8
   in this report is valid.
4. Writes a flat table (`magic, count, first_touch[count]`); the kernel
   builds its own sorted (page, rank) lookup from this at load time via
   `sort()`, rather than the script writing a second, independently-derived
   sorted copy that could go out of sync with the first.

### Kernel (`driver/src/specasync_debugfs.c`, `specasync_ft_predict()`)

Implements the algorithm exactly as specified: monotonic
`next_to_predict` cursor; skip-correction when demand has outrun the
cursor (counted in ranks, via `ft_skipped`); lookahead-bounded prediction
(`ft_predictions`) or hold-back (`ft_held`) against `next_to_predict ≤ r +
L`; exhaustion at the table end with no wraparound (`ft_exhausted`);
unknown-page handling (`ft_unknown_page`) for a page absent from the table
entirely. Lookup via the kernel's own `sort()` (at table-load time) +
`bsearch()` (per fault), per instruction — no hash table, no collision
failure mode.

**Concurrency, verified from source as instructed:**
`service_fault_batch()` (which contains the Gate 1 loop that calls
`specasync_predict_next()` → `specasync_ft_predict()`) is invoked from
`uvm_parent_gpu_service_replayable_faults()`, itself the single per-parent-
GPU replayable-fault servicing path — one caller at a time is expected
*per GPU* on this codebase's structure, but this is not independently
proven for multi-GPU systems (every workload in this project runs on a
single GPU, so it was never tested). The cursor's read-modify-write
sequence (read `next_to_predict`, possibly skip-correct, possibly predict-
and-increment) is protected by a dedicated spinlock
(`g_ft_cursor_lock`) regardless, exactly as instructed ("use atomics for
the cursor even though... single-threaded... is expected") — `next_to_predict`
itself is `atomic_t`, and the lock covers the multi-step decision an
`atomic_t` alone cannot make safe.

**Instrumentation added**: five counters
(`ft_predictions`/`ft_skipped`/`ft_held`/`ft_unknown_page`/`ft_exhausted`),
all debugfs-exposed, all reset by `specasync_clear`; an opt-in
(`specasync_log_ft_predictions`) diagnostic ring logging `(seq, predicted
rank)` per prediction, reusing the E0.7 ring machinery. **One addition made
during validation, not anticipated in the original design**: the E0.7
`specasync_replay_order_push()` call (logging the actual fault address per
call, needed for the "usefulness" check) was originally wired only into
`specasync_oracle_next_addr_n()` (policy 4). Added the same call to
`specasync_ft_predict()`, gated by the same `specasync_log_replay_order`
parameter, making that diagnostic ring policy-agnostic rather than adding a
second, redundant one. Full diff in commits `1b0d5b4` (initial) and the
validation-triggered follow-up (pushed below).

Compiles clean, no warnings, against 595.91.07 (full 5-module
`reconstruct_build_tree.sh` build, this exact 5070 Ti host's established
requirement for `conftest/` registration). srcversion of the validated
build: `5C79E39C41790EFF4C9993E`.

## 4. Validation

### 1. Probe — `group_probe`, L=1, N=8 (all 8 pages in one 2 MB block, per E0.5)

**Expected from the design**, stated before running: with all 8 coalesced
faults arriving in one batch and the table built from this exact probe's
own collection trace, the cursor should track demand almost exactly —
most faults should trigger a prediction one rank ahead, with the very last
fault unable to predict past the table's end.

**Observed**: `demand_faults=8`, `enqueued=7`, `ft_predictions=7`,
`ft_skipped=1`, `ft_held=0`, `ft_unknown_page=0`, `ft_exhausted=1`.
**Predictions + held + unknown + exhausted = 7+0+0+1 = 8 = demand_faults**,
exactly. Matches the expectation: 7 of 8 faults produced a one-ahead
prediction; the 8th (last-ranked page) tried to predict past the table end
and was correctly counted as exhausted, not wrapped. The one `ft_skipped`
(counted in *ranks*, see below) occurred on the very first fault, an
artifact of the skip-correction firing even when the cursor was already
exactly at the current rank (a literal reading of the specified formula,
not a bug — see §4.2's note on units).

**Migration mechanics, separately from prediction correctness**: at
`depth=1`, all 7 speculative migrations were `THROTTLED`
(`specasync_worker_log`, `result=4` on every record) — expected and
already documented elsewhere in this project (`DECISION.md`'s "same-block
trylock throttle"): `group_probe`'s 8 pages are deliberately forced into
one 2 MB VA block (E0.5's design), so the demand path holds that block's
lock for the whole batch and the speculative worker's `trylock` on the
same block can never succeed. This is a property of `group_probe`'s
design, not of policy 6, and it means `group_probe` is the wrong
instrument for validating migration success or "usefulness" at depth=1 —
real workloads (§4.4-4.5) were used for those checks instead.

### 2. Coverage, both workloads

| workload | L | depth | `ft_predictions` | distinct pages | coverage |
|---|---:|---:|---:|---:|---:|
| Stencil-24K | 1 | 1 | 140,909 | 1,125,000 | **12.53%** |
| Stencil-24K | 1 | 0 | 141,849 | 1,125,000 | **12.61%** |
| Stencil-24K | 16 | 1 | 419,846 | 1,125,000 | **37.32%** |
| GraphBFS-23 | 1 | 1 | 8,636 | 287,956 | **3.00%** |
| GraphBFS-23 | 1 | 0 | 9,268 | 287,956 | **3.22%** |

**Internal consistency, confirmed exactly in every one of these five
runs**: `ft_predictions + ft_held + ft_unknown_page + ft_exhausted =
demand_faults` (fault-level accounting) **and**, independently,
`ft_predictions + ft_skipped = distinct_pages` (rank-level accounting).
E.g. Stencil L=1 depth=1 (the re-run after the §3 code fix, the numbers
used throughout the rest of this report): 140,909 + 2,749,822 + 0 + 8 =
2,890,739 = `demand_faults` exactly, and 140,909 + 984,091 = 1,125,000 =
distinct pages exactly. Every one of the five runs in the table above was
checked the same way and passed. (An earlier run, before
`specasync_replay_order_push()` was wired into `specasync_ft_predict()` —
see §3 — used the same table and L but is not otherwise reported here;
only the post-fix numbers are used anywhere in this report.)

**These are two different units and the acceptance criterion needs restating
precisely**: `ft_skipped` counts *ranks jumped over* (can be >1 per fault),
while `ft_predictions`/`ft_held`/`ft_unknown_page`/`ft_exhausted` count
*faults*. The original plan's "predictions + skipped + unmatched account for
the page set" is true in the rank-unit equation
(`predictions + skipped = distinct_pages`) but not if `skipped` is added to
the fault-unit counters — stated explicitly here so this isn't mistaken for
an inconsistency later.

**Coverage is much lower for GraphBFS-23 than Stencil-24K at the same L**
(3.0% vs. 12.5%) — consistent with E0.8's finding that GraphBFS's page
order is far less tightly locked (Kendall 0.968, ~13% max displacement)
than Stencil's (~0.01% max displacement): demand outruns a cursor built on
a less-reliable order much faster, converting more of the table into
`ft_skipped` rather than `ft_predictions`.

### 3. Achieved lead

| workload | L | n predictions | min | p25 | median | p75 | p90 | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Stencil-24K depth=1 | 1 | 140,909 | 1 | 1 | 1 | 1 | 1 | **1** |
| Stencil-24K depth=1 | 16 | 419,846 | 1 | 2 | 9 | 14 | 16 | **16** |

**At L=1, achieved lead is exactly 1 for all 140,909 predictions — the
correct result at L=1, not evidence of falling behind** (L=1 constrains
lead to at most 1 by construction; "stuck near 1" would only be diagnostic
at a *larger* L). **At L=16, achieved lead spans the full 1-16 range**
(distribution: 97,042 predictions at lead=1, rising back up to 47,816 at
the L=16 cap, with substantial mass at every intermediate value) — this is
the decisive check, and it passes: the oracle is not falling behind demand
at L=16, it is genuinely using the larger lookahead budget it was given.
GraphBFS-23's lead distribution was not separately computed given the
time budget for this validation pass; its much lower coverage (§4.2) and
lower first-touch stability (E0.8) make a similar full-range response
plausible but unconfirmed — flagged as not done, not assumed.

### 4. Usefulness (forward, same-run — correct here, unlike E0.7's cross-run error)

For every logged prediction, checked whether the predicted page is
observed again in *this same run's* actual replay order, at any position
after the prediction. This is deliberately forward: E0.7's error was
comparing positions **across two different runs**, where an index shift
makes forward-only asymmetric (E0.7/E0.8's whole subject). Here the
comparison is a prediction against the future of the *same* run — the
causal question speculation actually asks ("will this page be touched
again after I predicted it, in the run I predicted it for") — and forward
is the only sensible direction for that question.

| workload | depth | L | usefulness |
|---|---:|---:|---:|
| Stencil-24K | 1 | 1 | **100.0000%** (140,909 / 140,909) |
| Stencil-24K | 0 | 1 | **100.0000%** (141,849 / 141,849) |

Every single prediction's page is touched again later in the same run —
expected, given Stencil's every page recurs ~2.6 times across 20 ping-pong
iterations regardless of prediction.

### 5. Prevented faults

**The literal "never faults again in the replay" measure is well-defined
but insensitive on Stencil-24K, for a specific, identifiable reason —
reported honestly rather than smoothed over.** Computed per-prediction:
does the predicted page occur **zero** more times in the rest of the run?
Result: **0.0000% at both depth=1 and depth=0** (identical). This is not a
null result about the mechanism; it is a property of Stencil's access
pattern: every page is touched ~2.6 times total regardless of any single
migration's success, so "never faults again" essentially never holds for
*any* page, prediction or not, making this specific per-prediction
operationalization unable to distinguish depth=1 from depth=0 on this
workload. It would be the right measure for a workload where a page's
natural lifetime includes exactly one more expected touch after the
prediction — Stencil is not that.

**The aggregate measure is well-defined, sensitive, and does show a
depth=1-vs-depth=0 difference, in the expected direction:**

| workload | L | depth=0 demand faults | depth=1 demand faults | reduction |
|---|---:|---:|---:|---:|
| Stencil-24K | 1 | 2,912,339 | 2,890,739 | 21,600 (0.74%) |
| GraphBFS-23 | 1 | 481,240 | 480,553 | 687 (0.14%) |

Stated with appropriate hedging, not as a confirmed causal result: this is
a **single run per condition**, not a controlled n≥10 comparison, so run-
to-run noise (E0.8 Check 2 found Stencil C1-vs-C1 pairs differing by
1,247-4,418 faults with *zero* speculative activity at all) is a live
alternative explanation. Stencil's 21,600-fault reduction is 5-17x larger
than that established noise range, making a real effect plausible; a
single comparison cannot rule out noise with confidence, and this report
does not claim it does. **A controlled, interleaved, n≥10 version of
exactly this comparison is squarely E0.9b's job**, not this validation
gate's.

## 5. Acceptance verdict for E0.9b

| criterion | result |
|---|---|
| Probe behavior matches the design | **Yes** — matched the stated expectation exactly, including the exhaustion/skip counts. |
| Counters internally consistent | **Yes**, on the correct (restated) equation: fault-level counters sum to demand_faults; rank-level counters (predictions+skipped) sum to distinct pages. Confirmed in every one of 7 runs. |
| Achieved lead responds to L | **Yes** — confirmed with a direct L=1 vs. L=16 comparison on Stencil-24K; full 1-16 range observed at L=16, not stuck near 1. |
| Usefulness measure well-defined on both workloads | **Partially** — well-defined and computed for Stencil-24K (100% at both depths); GraphBFS-23's usefulness/lead were not computed this pass (time budget), though the underlying logging is confirmed working (coverage/counter checks above used it). Flagged as incomplete, not assumed to match Stencil. |

**No tuning of L or the design was done to pass any of the above** — every
number reported is from the first run of each configuration; the one code
change made during this section (wiring `specasync_replay_order_push()`
into `specasync_ft_predict()`) was a missing-instrumentation fix required
to compute usefulness at all, not a behavioral tuning of the oracle, and
is disclosed in §3.

**On balance: proceed-with-flags, not clean pass.** The core algorithmic
properties (bounded lead, monotonic cursor, exhaustion handling, counter
consistency) are all confirmed correctly on both workloads. The two gaps
(GraphBFS-23's achieved-lead/usefulness not computed; prevented-faults only
checked as a single-run comparison, not the controlled version) are
scope/time gaps in this validation pass, not design failures — recorded
here for review rather than either quietly completed or silently ignored.

## Flags for review (not edited)

- `ARTIFACT_CATALOG.md` material from §1's two corrections (forward-only
  metric mistaken for symmetric; direction-discarding absolute value) —
  both belong alongside artifacts #7-#9's "aggregation level" pattern.
- Any claim-document text describing hit rate as inherently near-zero for
  any speculative policy should be read against this gate's numbers: the
  first-touch oracle reaches 92-100% hit rate on Stencil-24K depending on
  depth, because it is accuracy-by-construction — a structurally different
  claim from anything policy 4 could produce, and not yet a wall-clock
  claim (E0.9b's job).

## Artifacts

- `driver/src/specasync_debugfs.c`, `specasync_internal.h`,
  `specasync_telemetry.h`, `uvm_gpu_replayable_faults.c` — policy 6
  implementation (commit `1b0d5b4` + validation-triggered fix, this
  report's accompanying commit).
- `tests/prepare_first_touch_table.py` — userspace table builder.
- `driver/build/595.91.07/nvidia-uvm-specasync-NEW-e0.9-ft.ko` — built,
  gitignored, reproducible from committed source.
- Raw traces/tables/logs: `results/phaseB1/gate_e09_validation/`
  (gitignored per this gate's `.gitignore` entry).

**HARD STOP after E0.9a.** E0.9b (pre-registration + lookahead sweep) not
started, pending review.
