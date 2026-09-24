# Gate E0.5 — Step 1 (accepted) + three pre-Step-2 additions

Step 1 (git archaeology, contradiction resolution) was reported inline in the
prior turn and accepted. This file records the three follow-up checks
requested before Step 2, and their outcome: **addition 2 falsifies the
mechanism model Step 2's fix is designed around. Step 2 is not started.**
No driver source was touched in this pass — read-only investigation and
direct parsing of already-existing raw telemetry files only.

---

## Addition 1 — Re-checking the cc90fc1 → fc384fb attribution

**Corrected finding: the prior report's framing was imprecise. `cc90fc1`
(FIX-1) introduced the full magnitude of the over-consumption; `fc384fb`
redistributed it without changing the total.**

Verified directly from `git show cc90fc1`'s diff (reproduced in the prior
report): the only call site in State 1 is

```c
if (specasync_log_enabled && batch_context->num_coalesced_faults > 0) {
    uvm_fault_buffer_entry_t *_fe = batch_context->ordered_fault_cache[0];
    if (_fe && _fe->va_space) {
        u64 _spec_addr = specasync_predict_next(_fe->va_space,
                                                _fe->fault_address,
                                                batch_context->num_coalesced_faults);
        ...
    }
}
```

There is exactly one call, inside one `if`, with one value passed:
`batch_context->num_coalesced_faults`. No branch inside this block passes a
different value; the only alternative outcome is the whole block being
skipped (zero calls, `num_coalesced_faults == 0` or a null `va_space`), never
a partial or substitute value. So **on every path where a prediction happens
in State 1, the cursor advances by exactly the batch's full coalesced-fault
count, in one call.**

Comparing totals over a run:
- **State 1:** one call per top-level HW batch, cursor advance =
  `num_coalesced_faults` for that batch. Summed over the run: total advance =
  run's total coalesced-fault count.
- **State 2 (`fc384fb`):** `num_coalesced_faults` calls per batch, cursor
  advance = 1 each. Summed over the run: total advance = run's total
  coalesced-fault count.

**Identical total.** `fc384fb`'s per-fault loop changes which fault each
prediction is attributed to (every fault gets its own speculative work item
and its own cursor position, instead of only `ordered_fault_cache[0]` of each
batch getting one), and it changes the *within-batch distribution* of cursor
advances (one lump of size N vs. N steps of size 1) — but the **rate of
cursor advance relative to trace-entries-recorded is set by
`num_coalesced_faults` vs. dispatch-group count, and neither commit touches
dispatch-group recording.** The ~11.7x (Stencil-24K) / ~2.1x (GraphBFS-23)
over-consumption ratio reported in Gate E0 §7 was fully present the moment
`cc90fc1` landed (2026-06-13); `fc384fb` (2026-06-14) is not where that
magnitude came from. Withdrawing "fc384fb regressed the consumption
granularity" from the prior report — the correct statement is: **FIX-1
introduced the over-consumption; `fc384fb` changed its internal distribution
and (usefully, for a different reason — per-fault speculative coverage) its
attribution, but left its magnitude untouched.**

## Addition 2 — Arithmetic check against `coalesce_probe.cu`: model falsified for this probe

Parsed the raw telemetry directly (`results/phaseB1/oracle_coalesce/*.bin`,
still present on disk, gitignored, never re-derived from any report's
aggregate — first time these specific files have been read since they were
produced):

| file | parsed from | value |
|---|---|---:|
| `new_trace.bin` | file size / 8 | 450 entries (dispatch groups recorded, collection run) |
| `new_batch.bin` | `specasync_batch_record` ring, valid records | 56 valid batches, **442 total coalesced faults**, 56 spec_enqueued, 23 spec_hits, hit_rate = 0.410714... (reproduces 0.4107 exactly) |
| `old_trace.bin` | file size / 8 | 445 entries |
| `old_batch.bin` | same ring | 57 valid batches, 451 total coalesced faults, 57 enqueued, 1 hit, hit_rate = 0.017544 (reproduces 0.0175 exactly) |

`spec_enqueued == valid_batches` in both files (56==56, 57==57) — this
independently confirms both binaries were produced by **State 1** code (one
enqueue per batch, for `ordered_fault_cache[0]` only), not State 2, which
would show `spec_enqueued ≈ total coalesced faults`. This matters below.

**The ratio the model predicts (`k` = total coalesced faults / trace
entries):**

- New (fixed): 442 / 450 ≈ **0.982**
- Old (buggy): 451 / 445 ≈ **1.013**

**This is the "≈ 1" outcome you flagged as falsifying.** For this specific
probe, recording (dispatch groups) and the demand-fault count are already
matched almost 1:1 — i.e. `coalesce_probe.cu`'s access pattern does not
produce meaningful dispatch-group collapsing (unlike Stencil-24K/GraphBFS-23,
where E0 measured genuine ~11.7x/~2.1x grouping from real per-block fault
density). `1/k` here would predict a hit rate near 100% (old) or 98% (new);
measured is 1.75% and 41.07%. **The over-consumption-ratio model does not
explain this probe's result, in either direction, and by a wide margin.**

**What actually explains the 41% (and the 1.75%), from the same data:**

1. **Coverage ceiling, not alignment.** State 1 issues exactly one
   speculative prediction per batch (56 predictions for 442 faults) —
   `spec_enqueued=56` confirms it. Only the batch-boundary fault in each of
   the 56 batches is ever a candidate for a hit; the other ~386 faults
   (everything but `ordered_fault_cache[0]` in each batch) have no
   speculative work item targeting them at all, for reasons unrelated to
   trace alignment. `hit_rate`'s denominator is `enqueued` (56), not total
   faults (442) — so 41% describes success among the 56 attempts made, not
   coverage of the run's faults.
2. **Cross-launch nondeterminism.** Collection and replay are two *separate*
   kernel launches of the same deterministic-address burst kernel (the
   script does `rmmod`/`insmod` and a fresh `run()` between them). Their
   total coalesced-fault counts already differ (450 vs. 442, new; 445 vs.
   451, old) — a ~1-2% discrepancy that can only come from the GPU's fault
   buffer draining/batching boundaries falling slightly differently between
   two runs of "the same" kernel, not from anything in the driver's
   bookkeeping. Since the oracle's prediction targets a specific *position*
   in the recorded trace, any such per-run boundary shift misaligns some
   fraction of the 56 predictions even with `k≈1`.

Neither of these is the recording/consumption rate-mismatch mechanism E0 §7
found on Stencil-24K/GraphBFS-23. **`coalesce_probe.cu` is not a good
instrument for validating that specific mechanism** — its access pattern
happens not to exercise dispatch-group collapsing, so it cannot distinguish
"cursor desync fixed" from "still broken for an unrelated reason." This was
true in 2026-06-13 when it was used as the sole positive-control evidence for
FIX-1, and it is still true now.

**One sentence on the real-workload comparison, not to be investigated
further here, per instruction:** Stencil-24K's measured ratio (11.7) would
predict a hit rate near 8.5% under the simple `1/k` model; the measured
figure is 0.0132%, a further ~640x shortfall beyond what the ratio alone
explains — consistent with your point that a misaligned prediction on a
real workload is very unlikely to coincide with a page that later actually
faults (an unrelated address, not a nearby plausible one), whereas on this
specific probe's monotonic single-block-scoped page range a misaligned
prediction has a much better chance of still landing on some other page in
the same short run.

### Consequence: `CLAIM_SCOPE.md` row 6 rests on the same unverified arithmetic

Flagged, not edited. `CLAIM_SCOPE.md:37` states: *"Oracle mechanism ceiling:
one-prediction-per-batch design caps achievable hit rate at ~1/coalesce_factor
... Follows directly from the fixed (post-FIX-1) design,"* citing
`driver/PIPELINE_FIXES.md` (FIX-1) and `GATE_B_diagnosis.md` — the same two
documents Step 1 showed already contained the un-checked arithmetic. Using
this session's own numbers: `coalesce_factor` (mean faults/batch) for the
probe is 442/56 ≈ 7.9 (matches the commit message's own "7.9 f/b" label), so
the "~1/coalesce_factor" formula predicts a ceiling near 1/7.9 ≈ 12.7% —
**the measured 41.07% hit rate exceeds this predicted ceiling by more than
3x.** The claim's own cited evidence does not support the formula it states.
This is the same failure pattern as the 0.4107 reading: a plausible-sounding
mechanistic story, stated as following "directly" from the fix, that nobody
checked arithmetically against the numbers already sitting in the evidence
file it cites.

## Addition 3 — Every result depending on the oracle path, by state

State boundaries, from Step 1: **State 0** = before 2026-06-13 16:14
(`cc90fc1`); **State 1** = `cc90fc1` through 2026-06-14 18:53
(`fc384fb`⁻¹); **State 2** = `fc384fb` (2026-06-14 18:54) onward, current.
All three states are now known to be misaligned between recording and
consumption (State 0: consumption under-advances relative to a per-fault-ish
recording rate; States 1 and 2: consumption over-advances relative to
dispatch-group recording, by ~11.7x/2.1x on the two headline real workloads —
Addition 2 shows this ratio is workload-dependent, not universal). Oracle
policy is `specasync_policy=4`, i.e. **C3** in this project's benchmark
config naming, and **C4** where C3 is combined with the prefetcher
(`prefetch=1`).

| result | file | figure(s) | state |
|---|---|---|---|
| Oracle scores 0.0000 on all 6 cells | `results/phaseB/gate_reports/gate4_oracle.md`, `results/summary/cost_benefit.md` | hit_rate=0.0000, all benchmarks | 0 |
| FIX-1 validation probe | `results/phaseB1/GATE_B_diagnosis.md`, `driver/PIPELINE_FIXES.md` | coalesced probe 0.0175→0.4107; "FIXED and verified" | 0→1 (before/after pair) |
| Gate D real-workload oracle re-baseline | `results/phaseB1/GATE_D_report.md` (module `81CDE275`) | Stencil 0.66%, GraphBFS 6.48%, Stencil_OvSub 0.26% hit rate; "oracle now genuinely predicts... yet still yields no speedup"; cost-benefit table; "100x slower" claim ruled out | **1** |
| Gate 1/2/3/4 "decisive experiment," Path B closed | `results/phaseB2/GATE1_report.md`, `GATE2_report.md`, `GATE3_report.md`, `GATE4_report.md`, `DECISION.md`, `results/phaseB2/gate3/gate3_times.csv` | C3: Stencil 15.68s (+269% vs C0), GraphBFS 58.64s (+5.7%); "Path B is closed" | **2** (produced by `fc384fb` itself) |
| T1 headline (platform of record) | `results/analysis/GATE_T1_REPORT.md`, `results/analysis/GATE_A_report.md` (trace provenance) | Stencil-24K C3=15.84s, hit rate 0.0132%; GraphBFS-23 C3=58.25s, hit rate 0.2357%; traces `c3_bench_stencil_trace.bin` (276,961 entries), `c3_bench_graph_bfs_trace.bin` (207,564 entries) | **2** |
| T4 prefetch-off telemetry / rate-mismatch chain | `results/analysis/GATE_T4_REPORT.md`, `RATE_MISMATCH_VERIFICATION.md`, `GATE_A1_REPORT.md` | C3 demand-fault/hit/drop counts (Stencil 70,655,453/9,933 hits; GraphBFS 24,918,253/51,569 hits, both pre-ring-saturation-correction); the "dispatch loses the race" mechanism argument, built on these C3 counts | **2** |
| Cross-platform replication | `results/analysis/GATE_B5_5070TI_REPLICATION.md`, `GATE_B6_TASK2_A1_REPLICATION.md`, `GATE_B6_TASK3_A2_REPLICATION.md`, `GATE_B7_5070TI_PHASEC.md` | C3 wall-clock/hit-rate figures on RTX 5070 Ti reproducing T1's qualitative result | **2** |
| ASLR/setarch regime finding | `results/analysis/GATE_A2_REPORT.md`, `GATE_A2B_SETARCH_REGIME.md` | C3-specific variance under `setarch -R`, a property that exists *because* oracle replay is used at all | **2** (property of the mechanism, not a hit-rate number, but oracle-dependent) |
| Bimodality mining | `results/analysis/BIMODALITY_TELEMETRY_MINING.md` | C3/Stencil-24K bimodal wall-clock clusters, spec-queue counters | **2** |
| Oversubscription oracle (C3), all iters | `results/analysis/OVERSUB_C3_VERIFICATION.md`, `OVERSUB_SPEEDUP_VERIFICATION.md` | C3 wall-clock and demand-fault/hit/migration counts at N=48000, iters∈{1,3,5,10,20} | **2**, and additionally truncated + rotated (Gate E0 §3/§7 — ring capacity exceeded on top of the rate mismatch) |
| Oracle-on-prefetcher (C4), oversubscription | `results/analysis/GATE_B10_PREREGISTRATION.md`, `GATE_B10_AUGMENTATION.md`, `GATE_B10_REPLICATION.md`, `GATE_B9_TASK2_REBUILD.md` | C4 wall-clock crossover/oscillation across iters∈{1,5,8,12,16,20}; the "residency accumulation" mechanism narrative built on these `demand_faults` counts | **2**, additionally truncated + rotated |
| Claim-scope entries citing oracle mechanism | `results/analysis/CLAIM_SCOPE.md` rows 6, 7, 8, 10 | "~1/coalesce_factor" ceiling (row 6, see above); C3-vs-C0 magnitude (row 7); prefetch-cost claim (row 8, not oracle-dependent itself but stated alongside); rate-mismatch mechanism (row 10, uses C3 counts) | rows reference **1 and 2** |
| Manuscript draft | `paper/main.tex` (lines ~89, 128, 150-165), `paper/intro_revisions.md`, `paper/abstract_v2.md` | oracle-policy description, hit-rate figure placeholders (Panel A/B, oversub collapse figure), "excluding pre-Gate-B.1-fix oracle rows" note at `main.tex:128` — this note itself assumes only *pre*-FIX-1 rows needed excluding, which is now known to be incomplete | references **0 (explicitly excluded), 1, 2** |

**Flag only, per instruction — none of the files above were edited.**

The honest summary, stated plainly: **no oracle measurement in this
project's history has been produced by a driver where recording and
consumption operated at matched, aligned rates.** State 0 under-consumed;
States 1 and 2 over-consume by a workload-dependent ratio that is large on
real workloads (~11.7x/~2.1x) and apparently near 1 on at least one synthetic
probe (`coalesce_probe.cu`) for unrelated reasons. Every hit-rate number in
the table above, and every wall-clock comparison that was framed as "against
a maximally favorable, oracle-perfect predictor," was measured against a
predictor that was never actually shown to be aligned with the fault stream
it was replaying.

---

## Addendum (this pass) — §1 restated with the arithmetic shown, coalesce_probe.cu's cause confirmed, denominator mismatch confirmed, Step 2 implemented

### What is established vs. not (per instruction, kept separate)

**Established, source- and telemetry-derived, does not depend on any probe:**
recording fires once per va-block dispatch group
(`uvm_gpu_replayable_faults.c:2645/2652` pre-fix), consumption once per
coalesced fault (`:2628-2641`, `specasync_oracle_next_addr_n`), measured
ratios 11.7 (Stencil-24K) and 2.1 (GraphBFS-23).

**Not established, and not settled here:**

| Workload | k | 1/k predicts | Measured hit rate | Gap |
|---|---:|---:|---:|---:|
| Stencil-24K | 11.7 | ~8.5% | 0.0132% | ~648x unaccounted |
| GraphBFS-23 | 2.1 | ~48% | 0.2357% | ~202x unaccounted |

Two to three orders of magnitude beyond what the simple `1/k` story predicts.
The plain, tentative reading — misalignment caps how often an aligned
prediction is even offered, and the independently-measured dispatch-latency
race (`RATE_MISMATCH_VERIFICATION.md`, `GATE_A1_REPORT.md`) destroys nearly
all of what remains — is recorded here as an open question with the
arithmetic shown, not asserted. **No investigation opened into it in this
gate**, per instruction.

### `coalesce_probe.cu`'s k≈1 cause, verified directly (not just inferred)

Parsed `new_trace.bin`'s raw addresses directly (450 `u64` entries, still on
disk, never previously read as raw addresses — only its byte count had been
used before). Result: the addresses step through **exactly 8 distinct
2 MB-aligned VA blocks in round-robin order** — consecutive trace entries
differ by ≈ ±2,097,152 B (one 2 MB block) with a wrap back to block 0 every
8th entry (block indices 67108464-67108471, i.e. exactly 8 consecutive
2 MB-aligned blocks spanning the probe's ~16.8 MB allocation for its default
N). This confirms the hypothesis precisely: within any given top-level HW
batch, the ~7.9 coalesced faults present are typically one page from each of
several *different* blocks, not several pages inside the *same* block — so
`service_fault_batch_ats_sub`'s same-block merge condition
(`uvm_gpu_replayable_faults.c` ~2260-2303) almost never fires, and nearly
every coalesced fault becomes its own dispatch group. The cause is
structural (this probe's threads/warps happen to get serviced in an order
that scatters across the whole buffer rather than clustering within one
block), not a fluke of one run — both `old_trace.bin` (445 entries) and
`new_trace.bin` show the same pattern. **`group_probe.cu` (below) exists
specifically to remove this degree of freedom** by construction rather than
by hoping for favorable scheduling.

One incidental observation, noted but not chased: `run_oracle_coalesce.sh`
never sets `uvm_perf_prefetch_enable=0` for either module load, unlike every
later collection script. Whether this affected the ~450-of-however-many-were-
launched event count is unclear and irrelevant to the k≈1 finding (confirmed
directly from addresses above, independent of the total count); flagged only
so `group_probe.cu`'s wrapper explicitly disables it.

### §3 verified: the 41% vs. 12.7% comparison was a denominator mismatch

Confirmed from the parser convention used everywhere in this project
(`run_hit_probe.sh`'s inline Python, `run_oracle_coalesce.sh`'s inline
Python, both compute `hit_rate = hits / enq` where `enq` sums
`specasync_batch_record.spec_enqueues`) and cross-checked against a
published figure: GraphBFS-23 C3's hits/enqueued = 51,569 / 20,505,109 =
**0.0025147**, matching `GATE_T4_REPORT.md`'s published "0.0025" to 4
significant figures. hits/demand_faults for the same run = 51,569 /
24,918,253 = 0.0020695 — close but distinguishably different, confirming the
convention is **hits ÷ enqueued (= processed), not hits ÷ total faults**,
project-wide.

For the coalesce probe: `enqueued = 56` (confirmed — `spec_enqueued ==
valid_batches` in the raw telemetry, State 1's one-enqueue-per-batch design),
`hits = 23`, so 0.4107 = 23/56 exactly. `CLAIM_SCOPE.md:37`'s "~1/coalesce_
factor" ceiling, evaluated against `coalesce_factor` = mean faults/batch =
442/56 ≈ 7.9 (the commit's own "7.9 f/b" label), predicts a ceiling against
the **fault** denominator (442): 1/7.9 ≈ 12.7% of 442 faults, i.e. ≈56
faults expected to be predictable at all — which is, not coincidentally,
almost exactly `enqueued` itself (56). **The two quantities were never
comparable: the ceiling formula bounds how many of the 442 faults could ever
receive a prediction (≈56, and indeed exactly 56 were enqueued — the formula
is roughly right about *that*), while the reported 41.07% figure measures
success *among those 56 attempts*, a different question the formula says
nothing about.** Confirmed: this is a fourth instance of the project's most
recurrent failure mode — a quantity computed at one aggregation level
(per-fault ceiling) compared against one at another (per-enqueued success
rate) — alongside artifacts #7, #8, #9. Belongs in the catalog synthesis
alongside them. `CLAIM_SCOPE.md` not edited.

### FIX-1's validation rested on single-digit counts

Confirmed directly: old = 1 hit / 57 enqueued; new = 23 hits / 56 enqueued.
"23x more hits" (the commit message's own framing) is arithmetically exact
and rests on an absolute difference of 22 events. Combined with the ceiling
lesson above (a relative improvement accepted without checking the
achievable absolute ceiling), this is recorded as the sharpest pitfalls-
section material this gate has produced: two independent, compounding
reasons a plausible-looking validation number should have been distrusted,
both visible in the evidence file at the time it was written, neither
checked.

### Step 2 — implemented

`driver/src/uvm_gpu_replayable_faults.c`: removed the
`specasync_trace_push()` call from inside the per-dispatch-group loop
(old line 2652) and added a new, separate loop immediately after the
existing Gate 1 prediction loop, iterating `ordered_fault_cache[0..
num_coalesced_faults-1]` — the same index range and order as Gate 1 — and
calling `specasync_trace_push(_te->fault_address)` for every entry. Diff is
additive-only plus one deleted line; nothing else touched (`git diff
--stat`: 44 insertions, 1 deletion, one file).

**Requirement 1 (guard parity) — resolved, with a correction to the naive
approach.** The new loop is deliberately **not** merged into the Gate 1
loop and does **not** share its `specasync_log_enabled` guard. Grepped every
insmod invocation in `scripts/` and `tests/` (40+ call sites): essentially
every real trace-collection script in this project — `t1_gate3_
interleaved.sh`, `gate3_favorable_run.sh`, `t_a2_bimodality.sh`, `t_a2b_
setarch_regime.sh`, `t_b8_oversub_5070ti.sh`, `t_b9_task1_checksum.sh`, `t_
b9_task2b_iter_sweep.sh`, `t_b10_c0_vs_c4.sh`, `t_b10c_replication_
crossover.sh`, `t4_prefetch_off_telemetry.sh`, and more — loads the module
for collection with **`specasync_log_enabled=0 specasync_trace_faults=1`**.
Had the new recording site been placed inside the Gate 1 loop's `if
(specasync_log_enabled ...)` block (the reading that most directly matches
"identical guards"), it would have silently stopped recording in every one
of those scripts — exactly the failure mode this step exists to remove, with
different numbers. The new site is instead gated only by
`specasync_trace_faults` (checked inside `specasync_trace_push()` itself,
unchanged), matching the *original* call site's independence from
`specasync_log_enabled`. What **is** now identical between recording and
consumption is the thing that actually matters: the iteration set and order
(`ordered_fault_cache[0..num_coalesced_faults-1]`, same array, same indices)
— recording and consumption never run in the same module load anyway
(collection writes a file; a later, separate replay load reads it), so a
literally shared boolean was never the right notion of parity here. Stated
explicitly per instruction: recording's guard is `specasync_trace_faults`
(unchanged); the Gate 1 prediction/enqueue call's guard is
`specasync_log_enabled && num_coalesced_faults > 0` plus per-entry `_fe &&
_fe->va_space` (unchanged); these are deliberately different flags, and the
new code preserves that difference rather than eliminating it.

**Requirement 2 (offset) — verified, no consumption-side change needed.**
`specasync_oracle_next_addr_n(consumed=1)` (called once per coalesced fault
from the unchanged Gate 1 loop) does `old = atomic_fetch_add(1,
&g_oracle_idx); return trace[(old+1) % len]`. Starting from `g_oracle_idx
== 0`: servicing coalesced fault 0 (`old=0`) returns `trace[1]`; servicing
fault 1 (`old=1`) returns `trace[2]`; in general, while servicing fault *k*
the call returns `trace[k+1]` — correct "next fault" semantics, and this
arithmetic is **untouched by Step 2**. It was already correct; it just had
nothing meaningful to index into, because `trace[k+1]` was, before this fix,
almost never actually the address of coalesced fault *k+1* (dispatch-group
recording meant `trace` advanced far slower than the fault count). With
recording now at matching granularity, `trace[i]` is populated in the same
order Gate 1 will later consume it, for as long as the collection and replay
runs' fault orders agree (a separate, already-known concern — FIX-2's
ASLR-pinning requirement, `setarch -R`, unaffected by this change).

**Requirement 3 (nothing else in this step) — confirmed by the diff itself**:
one deleted line, one new self-contained loop, no ring, no read-path, no new
counters.

### `tests/group_probe.cu` — built, compiles, functionally sane

Single 4 MB `cudaMallocManaged` over-allocation, computes the first
2 MB-aligned address inside it, touches N (default 8) distinct 4 KB pages
starting there — all provably inside one va_block by construction, not by
favorable scheduling. Compiles clean (`nvcc -arch=sm_120`, matching this
host's RTX 5070 Ti/Blackwell) after two portability fixes forced by this
host's CUDA 13.2 toolkit (older than what `coalesce_probe.cu` was written
against): added `#include <cstdint>` for `uintptr_t`, and replaced the
removed `cudaMemPrefetchAsync(ptr, count, int device, stream)` overload with
the current `cudaMemLocation`-struct form. Ran once against the stock
driver (no SpecAsync telemetry involved, no root needed) to confirm it
executes without crashing and reports the expected aligned window:

```
group_probe: raw=0x75c302000000 aligned_base=0x75c302000000 offset_into_alloc=0
group_probe: touching 8 pages, all inside [0x75c302000000, 0x75c302008000) — one 2MB block
group_probe: done
```

Not yet run under the SpecAsync module (blocked — see below).

---

## Blocked: no buildable/loadable SpecAsync module exists on this host

This was not anticipated by the gate plan and needs your direction before
any old-module or new-module baseline can be taken.

- Every `.ko` in `driver/build/` (`nvidia-uvm-specasync.ko`, `-phaseB1.ko`,
  `-phaseB2.ko`, `-phaseC.ko`, `-t4*.ko`) has `vermagic: 6.17.0-101[7-9]-aws`
  — built for the old AWS T4 instances. This machine runs `7.0.0-31-generic`.
  None of these load here (`insmod` would refuse on vermagic mismatch).
- `results/analysis/DRIVER_595_84_PORT_INVESTIGATION.md` records that this
  exact 5070 Ti host was ported to driver **595.84** at some point after
  this project's last memory checkpoint (2026-08-11) — `GATE_B10_
  REPLICATION.md` etc. cite srcversion `4488C9F6F75570BB2FB34F8` on
  "driver 595.84." **That port no longer exists.** `nvidia-smi` on this host
  now reports **595.91.07**, and `/usr/src/nvidia-595.84` is gone (DKMS only
  keeps the currently-installed version's source; only `/usr/src/nvidia-
  595.91.07` is present, plus `dkms status` confirming 595.91.07 across three
  kernel versions). The driver was upgraded at the OS level since that port
  was built, most likely by a routine update, and nothing in this project's
  history has ported to 595.91.07.
- This machine is the user's active graphical desktop — `nvidia-smi` shows
  `Xorg` and `gnome-shell` running on this same GPU right now. `rmmod`/
  `insmod nvidia_uvm` while X holds the device is the kind of action this
  project's own sudoers configuration appears to anticipate needing to avoid:
  passwordless `sudo systemctl isolate multi-user.target` / `graphical.
  target` is provisioned alongside `insmod`/`rmmod`/`tee`/`cat`/`dmesg` (and
  nothing else) — strongly suggesting the intended procedure is to drop to a
  non-graphical target before touching the module and switch back after,
  which will close the user's current graphical session.

I have passwordless `sudo` for exactly `insmod`, `rmmod`, `tee`, `cat`,
`dmesg`, and the two `systemctl isolate` targets — enough to execute this
once a loadable module exists, but porting SpecAsync's `driver/src/` onto
pristine `/usr/src/nvidia-595.91.07` from scratch (confirming the two
patches still apply, resolving any new conftest/API differences between
595.84 and 595.91.07, building, and validating) is unplanned, real work with
its own failure modes, on top of the display-session disruption. I'm not
attempting either without your go-ahead. Options as I see them: (a) port to
595.91.07 now and accept the graphical-session interruption, (b) you handle
the module rebuild/reload yourself (via `!`-prefixed commands) and hand me a
loadable `.ko` to test against, or (c) something else you'd prefer. Your
call.

---

## Continuation — port to 595.91.07, Step 3, enumeration check

Proceeding on the 5070 Ti per instruction (T4 access unavailable for now).
This session's commits: `e7de063` (Step 2 + Gate E0/E0.5 reports),
`dcc301e` (fixed a `*/`-in-comment build break Step 2's own comment
introduced — see below), and the commit at the end of this section (Step 3 +
enumeration-parity fix). §1's instruction (commit and push before dropping
to a console session, because the `gh` credential lives in the keyring and a
headless session can't push) was followed at every stopping point in this
section — each push is confirmed by its own `git push` output, not assumed.

### §2 — Port to 595.91.07: mechanical, confirmed before applying anything

Fetched the public `NVIDIA/open-gpu-kernel-modules` repo at both the `595.84`
and `595.91.07` tags for every file SpecAsync's patches touch or that Gate
E0.5's fix depends on: `uvm_gpu_replayable_faults.c`, `uvm_va_block.c`,
`uvm_perf_prefetch.c`, `uvm_va_space.c`, `uvm_va_space.h`, `uvm.c`,
`nvidia-uvm-sources.Kbuild`. **All seven are byte-identical between the two
tags** (`diff -q`, confirmed for every file, not sampled). Also confirmed
this host's installed `/usr/src/nvidia-595.91.07` matches the public
`595.91.07` tag exactly for the same seven files (same method
`DRIVER_595_84_PORT_INVESTIGATION.md` used for the 595.84/local comparison).

Direct answers to the three questions asked before applying anything:

- **`service_fault_batch()`'s structure, including the old-2645 dispatch
  loop and the Gate 1 loop region: unchanged.** The whole file is
  byte-identical, so there is nothing to re-verify from scratch — Step 2's
  offset and enumeration reasoning (both derived by reading this exact file)
  carries over without modification.
- **Prefetcher threshold/defaults/params (`uvm_perf_prefetch.c`): unchanged.**
  Byte-identical file. No revision needed to any C0-vs-C1 reasoning on this
  account.
- **Fault batching/coalescing (`uvm_va_block.c`): unchanged.** Byte-identical
  file. *k* (coalesced-faults-per-dispatch-group) should not differ from
  this cause between 595.84 and 595.91.07.

**The port is mechanical**, confirmed before building, not assumed. Applied
`driver/scripts/reconstruct_build_tree.sh` with `SRC=/usr/src/nvidia-595.91.07`,
a new local `WORK` directory (no `/opt/dlami/nvme`, which was AWS-only), and
`NV_KERNEL_MODULES="nvidia nvidia-uvm nvidia-modeset nvidia-drm nvidia-peermem"`
(the full 5-module build `GATE_B9_TASK2_REBUILD.md` already established this
exact 5070 Ti host's kernel needs, for `conftest/` registration — the
`nvidia-uvm`-alone default fails here with `NV_IS_EXPORT_SYMBOL_GPL_*`
undefined errors, reproduced once before switching). Glue patch applied
clean (`patching file nvidia-uvm-sources.Kbuild` / `specasync_internal.h` /
`uvm.c` / `uvm_va_space.c` / `uvm_va_space.h`, no rejects). Only
`nvidia-uvm.ko` is ever unloaded/reloaded; `nvidia`/`nvidia-modeset`/
`nvidia-drm`/`nvidia-peermem` stay whatever the desktop is already running,
matching the prior session's established procedure.

**One real bug found and fixed during this build, not upstream's fault:**
Step 2's own new comment contained the literal text `t_b8_*/t_b9_*` — the
glob wildcard immediately followed by a path separator forms `*/`, which
closes a C block comment early. The compiler then parsed the rest of the
comment as code, failing on the apostrophe in
"`specasync_oracle_next_addr_n()'s existing`" two sentences later
("missing terminating ' character") and spuriously flagging `family` as an
unused variable from the same now-uncommented text. Fixed by rewording to
"the t_b8 and t_b9 script families" (commit `dcc301e`, pushed before this
paragraph was written).

Both modules built clean, no warnings, against 595.91.07, kernel
`7.0.0-31-generic` (this host's actual running kernel — vermagic confirms
it):

| module | source state | srcversion |
|---|---|---|
| OLD | git HEAD before Step 2 (`ca4a143`) | `A25B8956A04371E44ED230B` |
| NEW (post Step 2 + Step 3) | current `driver/src/` | `ACB91A66456F53C974C9DED` |

Saved at `driver/build/595.91.07/nvidia-uvm-specasync-{OLD-preE05,NEW-e0.5fix}.ko`
(gitignored, per this project's `*.ko` pattern — not committed; reproducible
from committed source + `reconstruct_build_tree.sh` on any 595.91.07 host).
**Both are 5070 Ti / driver 595.91.07 only** — noted explicitly per §7's
instruction, so nothing here gets compared against 595.84-era B5-B10 data
without that distinction being visible.

### §4 — Enumeration check, finished properly this time

**Static.** Enumerated every skip/early-exit in both loops in
`service_fault_batch()`:

- Gate 1 (prediction) loop: no `continue`/`break`, one per-iteration skip
  condition, `if (_fe && _fe->va_space)`.
- The recording loop Step 2 added: no `continue`/`break`; **originally
  checked only `if (_te)`, one condition short of Gate 1's.** This is
  exactly the smaller, harder-to-spot mismatch you warned about: any
  coalesced-fault entry with a non-NULL pointer but NULL `va_space` would
  have been recorded but never predicted-on, a real (if probably rare)
  divergence between the two enumerated sets. `UVM_ASSERT(current_entry->
  va_space)` at the old trace-push site (and the dispatch loop, unchanged)
  establishes `va_space` is expected non-NULL for every entry
  `preprocess_fault_batch()` hands to `service_fault_batch()` by the time
  either loop runs, which is presumably why Gate 1's own author added the
  defensive check and why nothing has visibly broken from its absence in
  30-some fault-handler revisions — but "presumably safe because of an
  assert elsewhere" is not the same as "provably enumerates the same set,"
  so the check was added to match Gate 1 exactly: `if (_te && _te-
  >va_space)`. Now both loops have literally the same skip condition,
  verifiable by inspection, not by trusting an assert holds. Included in
  the srcversion `ACB91A66456F53C974C9DED` build above.

**Dynamic** (the stronger check): requires an actual replay run —
`g_specasync_trace_pushes` (new, `specasync_telemetry.h`) vs.
`g_specasync_oracle_consumes` (new, `specasync_internal.h`/
`specasync_debugfs.c`), asserted equal in the same process. Implemented as
part of Step 3 below; **not yet run** — needs the headless session next.

### Step 3 — implemented (ring capacity, read-path fix, full counter suite)

All required by Step 5's validation (`measured oracle accuracy... by
decile, zero overwrites`) and by this section's own dynamic check, so
brought forward from the original plan rather than deferred:

- **`specasync_trace_ring_slots`**, new module param (int, `0444`), default
  unchanged (`SPECASYNC_TRACE_RING_SLOTS_DEFAULT = 1<<20`, same value as the
  old compile-time constant). `alloc_trace_ring()` rounds up to a power of
  two (`roundup_pow_of_two`) since the `head & mask` push path requires it.
  Every existing non-oversubscribed collection stays under the default, so
  behavior is unchanged unless a larger value is explicitly requested.
- **`trace_ring_read()` fixed for chronological order on wrap.** Previously
  read linearly from physical slot 0 regardless of wrap state (Gate E0 §3's
  "rotated, not just repeated" finding). Now: below capacity, identical to
  before (start slot 0); once wrapped, starts at `head % capacity` (the
  oldest surviving entry) and rotates the two-segment copy accordingly,
  matching the pattern the other three rings already use for their
  head/tail bookkeeping.
- **Counters, all exposed read-only via debugfs, all reset by
  `specasync_clear`** (matching the existing demand_faults/spec_hits/
  spec_migrations convention — a clean per-run total, no delta arithmetic):
  `specasync_trace_pushes`, `specasync_trace_overwrites`,
  `specasync_oracle_consumes`, `specasync_oracle_wraps`,
  `specasync_oracle_correct`, `specasync_oracle_predictions`, and
  `specasync_oracle_{correct,total}_decile{0..9}`.
- **Accuracy scoring**, in `specasync_oracle_next_addr_n()` (now takes
  `current_fault_addr` too): each call scores the *previous* call's
  prediction against the fault being serviced now (one call in arrears,
  since a prediction can only be checked once the fault it targeted either
  does or doesn't occur), before computing and storing the new prediction.
  Decile = predicted position's location within the loaded trace
  (`predicted_index * 10 / trace_len`), a real-time proxy for "how far into
  the run" since Step 2 made recording and consumption advance at matching
  rates (near one full pass per run, not many). Protected by a dedicated
  spinlock (`g_oracle_score_lock`) separate from `g_oracle_idx`'s atomic,
  since the three-field last-prediction state is a read-modify-write group,
  not a single atomic op. `g_oracle_last_pred_valid` is cleared on
  `specasync_clear` (so a new rep's first fault is never scored against a
  stale prediction left over from the previous rep); `g_oracle_idx` itself
  is deliberately left untouched by `specasync_clear`, unchanged from
  existing behavior.
- **Wraps counted exactly**, not inferred: `specasync_oracle_next_addr_n()`
  compares `old/len` before and after each advance (using the raw,
  un-modulo'd cumulative cursor) and adds the lap difference.

Compiles clean, no warnings (checked by isolating `nvidia-uvm.o`'s rebuild
and grepping for `warning|error` — none). Not yet run against real telemetry
— that's the rest of Step 5, next.

---

## Step 5 — empirical validation, headless, both modules

Dropped to `multi-user.target` (`sudo systemctl isolate multi-user.target`,
confirmed via `systemctl is-active gdm` -> `inactive` and `nvidia-smi` still
working with no display attached) after confirming §1's push was in
(`ea72f33`, confirmed pushed before dropping). Restored `graphical.target`
at the end of this section (confirmed `gdm`/`graphical.target` both `active`
again). All module work used the passwordless `insmod`/`rmmod`/`tee`/`cat`
sudo grants; only `nvidia_uvm.ko` was ever unloaded/reloaded, matching
`GATE_B9_TASK2_REBUILD.md`'s established procedure — `nvidia`/`nvidia-drm`/
`nvidia-modeset` were never touched, and my freshly-built `nvidia-uvm.ko`
(built together with fresh copies of those three in the same `WORK` tree,
for `conftest/` registration — see §2 above) loaded and worked against the
*already-running*, unmodified `nvidia.ko`/`nvidia-modeset.ko` without any
symbol-version conflict.

`MemAvailable` logged at start (61,140,216 kB) and after the largest run
(61,158,892 kB) — no meaningful drift across this session's ~10 reloads, no
approach to the 6 GiB abort floor. `specasync_clear` written before every
rep; single srcversion per module confirmed via `dmesg`'s `init OK` line on
every reload.

### `group_probe.cu` (N=8, `k` measured, not assumed)

Collected fresh under **both** modules, `setarch -R` wrapping every
collection and replay invocation (an initial pass without `setarch -R` was
run first and correctly produced 0 hits/0 correct on both modules — the
recorded trace's absolute VA never matched the replay process's freshly-
randomized allocation base, exactly FIX-2's failure mode; re-run with
`setarch -R` before drawing any conclusion from it).

| module | trace entries (= measured *k*) | replay hit_rate | oracle_correct / predictions |
|---|---:|---:|---:|
| OLD (pre-Step-2, srcversion `A25B8956...`) | 1 | 1 / 8 = **12.5%** | n/a (no counter in this build) |
| NEW (post-Step-2/3, srcversion `ACB91A66...`) | 8 | 8 / 8 = **100%** | 7 / 7 = **100%** |

*k* = 8 exactly (not assumed — every one of the 8 coalesced faults collapsed
into the single 2 MB block by construction, confirmed directly from the
trace file's entry count on both modules' collection runs). **Old ≈ 1/k
(12.5%, exact), new ≈ the serialized probe's ceiling (100%) — both
predictions confirmed exactly, not approximately.** `oracle_predictions=7`
(not 8) is expected and correct: the first of 8 calls has no prior
prediction to score against (see the "one call in arrears" design in
Step 3 above), so only 7 of 8 calls produce a scoreable comparison.

**Dynamic enumeration-parity check** (same process, NEW module, `policy=4`
+ `specasync_trace_faults=1` together so both loops fire in one run):
`trace_pushes = 8`, `oracle_consumes = 8` — **exact match.** Confirms the
Gate 1 loop and the new recording loop enumerate identically, empirically,
not just by the static code-inspection argument in §4.

**Zero overwrites:** `specasync_trace_overwrites = 0` on every collection
this session (group_probe and both real workloads, below) — the ring was
never asked to hold more than it was sized for.

**Replay-twice reproducibility** (NEW module, same trace, two independent
module reloads): hit_rate 1.0 and 1.0 (8/8 both times), `oracle_correct/
predictions` 7/7 both times. Exact agreement.

### Real workloads — alignment and accuracy, NEW module only

(Comparing OLD vs. NEW *on real workloads* is §6's job, using hit rate as
the falsification-relevant statistic across a proper interleaved sweep;
this section validates the fix itself using the counters Step 3 added,
which only exist in the NEW build.)

**Collection (fresh per workload, `specasync_log_enabled=0
specasync_trace_faults=1 uvm_perf_prefetch_enable=0`, matching this
project's standing collection protocol exactly):**

| workload | coalesced faults (`specasync_demand_faults`) | trace entries | ratio | overwrites |
|---|---:|---:|---:|---:|
| Stencil-24K (size 24000) | 2,953,867 | 2,953,867 | **1.000000** | 0 |
| GraphBFS-23 (size 23) | 483,896 | 483,896 | **1.000000** | 0 |

**Exact 1:1 alignment on both real workloads** — recording and consumption
now enumerate the same faults at the same rate, not just on the synthetic
probe. (These absolute fault counts are this platform/GPU's own — RTX
5070 Ti, 595.91.07 — not directly comparable to the T4's 3,237,375 /
445,721 figures cited in `GATE_E0_REPORT.md` §2; different platform, not a
discrepancy.)

**Replay** (`setarch -R`, fresh module load per configuration, `specasync_
clear` before the run):

| workload | depth | demand faults | enqueued | spec_hits | hit_rate | spec_migrations | oracle_correct / predictions | overall accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Stencil-24K | 0 | 2,899,860 | 2,899,860 | 5,323 | 0.1836% | 0 | 221 / 2,899,859 | 0.0076% |
| Stencil-24K | 1 (= C3) | 2,910,050 | 2,910,011 | 17,278 | 0.5937% | 2,821,745 (96.97% of enqueued) | 162 / 2,910,049 | 0.0056% |
| GraphBFS-23 | 1 (= C3) | 480,176 | 471,103 | 5,764 | 1.2235% | 459,280 (97.49% of enqueued) | 7,261 / 480,175 | 1.5122% |

`hit_rate` is `spec_hits ÷ enqueued` throughout, stated explicitly per your
instruction, next to every figure, so it is never read against a per-fault
denominator again. **All three hit rates are higher than the corresponding
published T1 figures** (Stencil-24K 0.0132%, GraphBFS-23 0.2357%) — roughly
14-45x higher, though still small in absolute terms and not a claim about
what the *wall-clock* comparison will show (that's §6). No wraps occurred on
either replay (`oracle_wraps = 0` both times) — each replay's demand-fault
count stayed under its trace's length, consistent with §1's finding that
Step 2 removed the workload-scale wraparound Gate E0 §7 found.

**The decile breakdown is the most informative single result this gate has
produced, and it was not anticipated in this specific form:**

| workload (depth) | decile 0 accuracy | deciles 1-9 combined |
|---|---:|---:|
| Stencil-24K (depth=0, no migration at all) | 221/295,386 = **0.0748%** | 0 / 2,604,473 = **0%**, exactly |
| Stencil-24K (depth=1, real migration) | 162/295,386 = **0.0548%** | 0 / 2,614,663 = **0%**, exactly |
| GraphBFS-23 (depth=1, real migration) | 7,243/48,389 = **14.97%** | 18 / 431,786 = **0.0042%** |

**Prediction accuracy is concentrated almost entirely in the first tenth of
each run and collapses to (Stencil: exactly, GraphBFS: nearly) zero for the
remaining nine tenths — on both workloads, and, critically, *at
`offload_depth=0` as well as `depth=1`*.** The `depth=0` Stencil row has
**zero real speculative migrations** (`spec_migrations` is not shown for it
above but was confirmed 0 in the raw run) — nothing in that run could have
disturbed page residency relative to the collection run. Its decile decay
is therefore not explained by the mechanism the original gate plan's Step 5
brief anticipated ("once speculation changes residency the real fault
stream diverges from the recorded one") — it happens with **zero**
speculative interference. The two runs that separate collection from
replay by nothing but a second, independent process launch of the identical
benchmark already diverge almost completely after the first ~10% of the
run. The most plausible explanation, stated as a hypothesis and not chased
further in this gate: ordinary run-to-run non-determinism in real GPU
execution (warp/thread scheduling, fault-buffer drain timing, page-table
walk ordering) is enough on its own to decorrelate a recorded fault order
from a fresh run's actual fault order well before speculation ever gets a
chance to compound it. GraphBFS-23's much higher decile-0 figure (14.97%
vs. Stencil's 0.07%) and its small but non-zero tail (unlike Stencil's exact
zero) are consistent with GraphBFS's more repetitive, revisit-heavy access
pattern giving isolated addresses a nonzero chance of recurring by chance
later in the trace, not with the underlying mechanism differing between the
two workloads.

**This is exactly the kind of finding the original gate plan asked Step 4 to
produce** ("Accuracy decaying across the run is the direct measurement of
[the oracle's residency-divergence] limitation, and it belongs in the
paper's limitations section whatever the headline result turns out to be")
— except the cause found here is broader than residency divergence alone:
it reproduces without any speculative migration at all. Recorded as a
finding with the numbers shown; not investigated further past this point,
per this gate's discipline against opening new investigations mid-gate.

### System restored

Stock `nvidia_uvm` reloaded (`insmod /lib/modules/7.0.0-31-generic/updates/
dkms/nvidia-uvm.ko.zst` — `modprobe` is not in the passwordless sudo grant,
and bare `insmod nvidia_uvm` doesn't resolve a module name to a path the way
`modprobe` does, so the full path was needed) before returning to
`graphical.target`. Both confirmed: `lsmod` shows the stock module loaded
with 0 dependents-of-concern, `systemctl is-active gdm`/`graphical.target`
both `active`.

---

## Summary before §6

- **Step 2's fix works, confirmed three independent ways**: a probe built
  specifically to force dispatch-group collapsing (old 12.5% = exactly 1/k,
  new 100% = ceiling), a same-process dynamic enumeration check
  (trace_pushes = oracle_consumes = 8, exact), and two real workloads
  (trace entries = demand faults, 1.000000, on both).
- **Hit rate rises substantially post-fix on both real workloads** (14-45x
  the published T1 figures) but remains small in absolute terms (<1.3%
  even at its highest, GraphBFS-23 depth=1) — this by itself does not yet
  say anything about wall-clock; that is §6's question, not this one's.
- **New, load-bearing finding for the paper's limitations section**: oracle
  prediction accuracy collapses after the first ~10% of a real run,
  independent of whether real speculative migration occurs at all. A
  trace-replay oracle validated only on a short, fully-deterministic
  synthetic probe (as `coalesce_probe.cu` was, and as `group_probe.cu` also
  is) cannot be assumed to generalize its accuracy to a full real-workload
  run — the two are shown here to behave completely differently past the
  first tenth of the run.
- Every number in this section is 5070 Ti / driver 595.91.07 / kernel
  7.0.0-31-generic. No 595.84 data is compared against it above.

**Acceptance-gate reading, per the original gate's own criterion** ("if
measured accuracy is materially low — say below roughly 90% — then the
oracle is still not an oracle... report the number and stop"): overall
measured accuracy on real workloads is 0.0056%-1.51%, far below 90%. On the
strict reading of that criterion, E0.6 (or this session's replacement for
it, the old-vs-new comparison) should not proceed. But the criterion was
written before this session found *why* — the collapse is not a residual
alignment defect (group_probe's 100%/8-of-8 dynamic check rules that out
directly) but appears to be real-workload non-determinism swamping a
single fixed reference trace within the first tenth of a run. Whether that
distinction is enough to justify proceeding to §6 anyway is a judgment call
stated here, not made unilaterally: **not proceeding to §6 without your
read on this**, per the hard stop already in place.

**HARD STOP. Report above; §6 not started.**

