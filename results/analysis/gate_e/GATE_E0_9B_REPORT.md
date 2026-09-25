# Gate E0.9b — First-touch oracle lookahead sweep (unattended session)

*Status log: `E09B_STATUS.md`. The session completed with no stop condition.*

## Headline

- **Falsification trigger: did not fire.** No C6-L beats C0 at any L on
  either workload. All 8 C6-vs-C0 comparisons are Holm-significant, and all
  in the direction of **C6 slower**: +258% to +308% on Stencil-24K and +5.0%
  to +5.4% on GraphBFS-23. Perfect first-touch knowledge, at any lookahead
  tested, does not come close to the driver as it ships.
- **Marginal effect of speculation with prefetch off (vs C1):** the effect
  depends on L.
  - **Stencil-24K, C6-L4096: 0.244 s faster (−5.65%)**, Holm-significant,
    and larger than its MDE (0.020 s).
  - **Stencil-24K, C6-L1 and C6-L16: about 0.32 s slower (+7.5%)**,
    Holm-significant.
  - **Stencil-24K, C6-L256:** not significant.
  - **GraphBFS-23:** no L is faster. L256 is Holm-significantly slower
    (+0.54%), and the rest are not significant.
- **The prediction test failed upward on Stencil.** The measured C6-L4096
  saving (0.244 s) is **above** the pre-registered pilot ceiling interval
  [0.170, 0.217] s. **The ceiling was wrong:** the decomp-ring servicing
  window does not capture all of the wall-clock channel through which
  pre-staging acts. On GraphBFS the measurement is **below** the interval:
  C6-L4096 was 0.092 s slower than C1, which is not significant.

Platform for every number in this report: RTX 5070 Ti, driver 595.91.07,
kernel 7.0.0-34-generic, SpecAsync module srcversion
`5997D238EF080B77DBD2AAF` (built from `ea1a262`, verified in E0.9a-2).

## Step 0 — Preflight

See `E09B_STATUS.md` Step 0. All checks passed.

## Step 1 — Source checks (read-only)

### Q1. Where are speculative predictions lost?

**`ft_predictions − enqueued` counts items dropped at enqueue, and the drop
counter is `specasync_drops`** (`g_specasync_drops`). Every nonzero policy-6
prediction reaches `specasync_enqueue()`
(`driver/src/uvm_gpu_replayable_faults.c:382-420`). Its three early returns
are: (a) `!g_specasync_wq || specasync_policy == 0 || spec_addr == 0`
(line 390) — never taken for a policy-6 prediction, which is nonzero by
construction; (b) queue full, `g_specasync_queue_depth >=
SPECASYNC_MAX_QUEUE_DEPTH` (1,024, line 101) — increments
`g_specasync_drops` (lines 392-394); (c) `kzalloc(GFP_ATOMIC)` failure —
also increments `g_specasync_drops` (line 402). Every other path
increments `g_specasync_enqueued` (line 419). So, by construction:

    ft_predictions = enqueued + drops        (exact identity)

This identity is checked on every sweep run (Step 4) rather than assumed.

**An enqueued item whose page is already resident on the GPU when the
worker reaches it *is* counted in `spec_migrations`.** The worker
(`specasync_worker_fn`, lines 279-378) counts `spec_migrations` whenever
`uvm_va_block_make_resident()` returns `NV_OK` (lines 341-344). That
function's copy step (`uvm_va_block_make_resident_copy`,
`uvm_va_block.c:4740-4845`) masks already-resident pages out of both the
unmap set (`uvm_page_mask_andnot(unmap_page_mask, page_mask,
resident_mask)`, line 4783) and the copy, and has no error path for "nothing
to do" — it returns `NV_OK`. **So `spec_migrations` counts successful
`make_resident` calls, including no-op calls on pages already resident.**
It is not a count of pages actually moved. No existing counter separates the
two (stock UVM's `num_pages_in` lives in a debug-only procfs file, disabled
in this release build — `uvm_procfs.c:36-42`, `uvm_gpu.c:1044-1045`).

Items lost *after* enqueue are `enqueued − spec_migrations`: `THROTTLED`
results (block-lock `trylock` failure, context-alloc failure, address outside
the block, or `make_resident` error — lines 309-347), plus items whose block
lookup fails and fall through to the depth-0 path (lines 356-366).

Bearing on the pre-registered metric *pre-staged coverage =
`spec_migrations` ÷ distinct pages*: it is an **upper bound** on pages
actually moved ahead of demand, not an exact count. E0.9a-2's data
(`fault_already_resident` within 0.05% of `spec_migrations` at every L)
indicates the no-op share is small, but that is an inference from a second
counter, not a measurement of it — stated as such in the pre-registration.

### Q2. Does the stock prefetcher's region get mapped in the same service step?

**Yes.** On the demand path, `uvm_va_block_service_locked()`
(`uvm_va_block.c:12021`) calls `uvm_va_block_get_prefetch_hint()` (line 12046)
(`uvm_va_block.c:11487-11539`) before servicing. That function ORs the
prefetcher's pages into the same `new_residency` mask as the faulting pages
(`uvm_page_mask_or(new_residency_mask, new_residency_mask,
prefetch_pages_mask)`, line 11532), gives them access type
`UVM_FAULT_ACCESS_TYPE_PREFETCH` (line 11520), and widens the service region
to cover them (line 11533). `uvm_va_block_service_finish()` then computes a
mapping protection for **every page in `new_residency_mask`**
(`uvm_va_block.c:11961`) and `block_service_finish_map()`
(`uvm_va_block.c:11770`, step "3.2 — Add new mappings") maps each
protection group via `uvm_va_block_map()`.

**So prefetched pages are migrated and mapped in the same call as the fault
that triggered them.** A later access to a prefetched page finds a valid GPU
mapping and does not fault. The prefetcher can therefore *prevent* faults;
the off-path speculative worker, which only calls
`uvm_va_block_make_resident()` and never reaches `service_finish()`
(E0.9a-2 §3), can only make them cheaper. This asymmetry is structural and
the paper can state it from source.

### Q3. What servicing-time instrumentation exists without new code?

**No per-run aggregate timer exists.** The full set of debugfs aggregate
counters is: `processed, enqueued, drops, demand_faults, spec_hits,
spec_migrations, trace_pushes, trace_overwrites, oracle_consumes,
oracle_wraps, oracle_correct, oracle_predictions, ft_predictions,
ft_skipped, ft_held, ft_unknown_page, ft_exhausted, fault_already_resident`
(`specasync_debugfs.c`) — all counts, no time sums. Stock UVM's
`fault_stats` procfs file is counts only (`uvm_gpu.c:711-757`) and is
debug-build-only.

Time exists only in three **drop-on-full** rings, each 131,072 slots
(`specasync_telemetry.h:161,183,184`), all gated on `specasync_log_enabled`:

| ring | record | granularity | time fields |
|---|---|---|---|
| `specasync_decomp_log` | 112 B | one per serviced top-level batch in `uvm_parent_gpu_service_replayable_faults()` (pushed at `uvm_gpu_replayable_faults.c:~3577` cancel path, `~3626` normal path) | `d1_start … d6_end`, `svc_start/svc_end`, `num_faults`, `num_blocks` |
| `specasync_log` (batch) | 72 B | one per `service_fault_batch()` call | `t0 … t4` |
| `specasync_worker_log` | 48 B | one per worker item | enqueue/dequeue/completion |

The decomp ring is the natural servicing-time source: per top-level batch,
servicing window = (`d6_end` if nonzero, else `svc_end`) − `d1_start`, and
`num_blocks` counts dispatch groups. **Whether it saturates on a full
Stencil-24K run is not known from source** — it depends on the number of
top-level batches per run (the T4 recorded 88,171 batch records for a
3.24M-fault Stencil-24K rep, under the 131,071 cap, but that is a different
platform). Because the ring is drop-on-full with no reader-side draining,
**a run whose record count is below 131,071 dropped nothing and covers 100%
of batches and dispatch groups exactly**; a run at exactly 131,071 saturated
and covers an unknown-to-the-ring fraction. Step 2 measures this directly.

## Step 2 — Pilot and ceiling

Full method and numbers: `E09B_PREREG_ADDENDUM_PILOT.md` (commit `46761ec`,
before any Step 3 run).

- 10/10 pilot runs completed (`e09b/pilot_runs.csv`, `710ec7f`), with no stop
  condition and 0 new dmesg lines.
- `ft_predictions = enqueued + drops` held exactly on all 5 C6 runs.
- Decomp ring: 23,534–75,199 records per run, all below 131,071, so
  **100% coverage**. The ceiling was estimated by decision-rule branch 2,
  labelled prefix-based, scale factor 1.0.

| workload | C1 − C6-L4096 total servicing window | pilot pairwise interval | per pre-staged fault |
|---|---|---|---|
| Stencil-24K | **0.198 s** | [0.170, 0.217] s | 216 ns |
| GraphBFS-23 | **≈ 0** | [−0.0165, +0.0165] s | ≈ 0 |

**Disclosure:** the pilot runner printed per-run wall-clock to stdout, so the
pilot values were displayed. No arm comparison was computed from them. They
were used only pooled per workload, to set the sweep timeouts. The runner was
changed before the sweep to keep wall-clock off stdout.

## Step 3 — Pre-registration

`E09B_PREREGISTRATION.md` (commit `a3942b9`), together with the addendum. The
analysis code `tests/e09b_analyze.py` was committed with it and refuses to run
on a partial sweep.

## Step 4 — Run integrity

| check | result |
|---|---|
| Fresh tables | Stencil 1,125,000 distinct (trace 2,940,203, overwrites 0); GraphBFS 287,956 (trace 490,948, overwrites 0). Assertions **passed**. |
| Rows | **120 / 120** (`e09b/sweep_runs.csv`) |
| Order adherence | 120 / 120 rows match `sweep_order.csv` in sequence (sha256 `45241ae6…`) |
| Interruptions / resumes / re-runs | none / none / **none** |
| Commits | every 10 runs: `a7c997e` … `f459f05` (12 commits) |
| srcversion | `5997D238EF080B77DBD2AAF` on all 120 runs |
| Benchmark exit codes | all 0; no timeouts (22 s / 168 s) |
| MemAvailable | before-run 61,095,576–61,433,776 kB; after-run 60,835,652–61,174,916 kB; no drift (first 61,299,740, last 61,046,540) |
| Free disk | ≥ 39.9 GB |
| dmesg | 0 new lines on 119 runs. Run 13 (Stencil C6-L16, 14:56:46Z) had 8 new lines, all a Wi-Fi reassociation (`wlp8s0: deauthenticated … 4WAY_HANDSHAKE_TIMEOUT`, then re-auth/associate, uptime 18316.6–18317.1 s). Not `nvidia_uvm`, no stop pattern. The run is **kept** and was not re-run. The Tukey fences did not flag it: its cell kept 10 of 10 runs in the no-outlier analysis. No BUG/Oops/WARNING/GPF/NULL/irqs-disabled line from any source during the session. |
| `ft_predictions = enqueued + drops` | holds exactly on **80 / 80** C6 runs |
| Sweep window | 2026-09-25 14:52:45Z – 15:32:14Z |

## Step 5 — Results (pre-registered)

All values are process wall-clock medians, n = 10 per cell. Delta = C6-L − baseline.
Holm step-down runs across the 16 comparisons, family α = 0.05. MWU is exact:
no ties occurred. Full table: `e09b/primary_comparisons.csv`.

### Stencil-24K (C0 1.1374 s, C1 4.3166 s)

| comparison | median C6-L (s) | Δ (s) | Δ % | MWU p | Holm thr | verdict | Cohen's d | MDE (s) | without outliers: Δ / p / Holm-sig (n) |
|---|---|---|---|---|---|---|---|---|---|
| C6-L1 vs C0 | 4.6441 | +3.5067 | +308.3% | 1.08e-5 | 0.0031 | C6 slower | +149.0 | 0.030 | +3.5087 / 4.1e-5 / yes (9/9) |
| C6-L16 vs C0 | 4.6390 | +3.5016 | +307.9% | 1.08e-5 | 0.0033 | C6 slower | +137.7 | 0.032 | +3.5045 / 2.2e-5 / yes (9/10) |
| C6-L256 vs C0 | 4.2892 | +3.1517 | +277.1% | 1.08e-5 | 0.0036 | C6 slower | +118.9 | 0.033 | +3.1521 / 4.1e-5 / yes (9/9) |
| C6-L4096 vs C0 | 4.0729 | +2.9354 | +258.1% | 1.08e-5 | 0.0038 | C6 slower | +123.9 | 0.030 | +2.9383 / 2.2e-5 / yes (9/10) |
| C6-L1 vs C1 | 4.6441 | +0.3275 | +7.59% | 1.08e-5 | 0.0042 | C6 slower | +20.8 | 0.020 | +0.3268 / 2.2e-5 / yes (10/9) |
| C6-L16 vs C1 | 4.6390 | +0.3225 | +7.47% | 1.08e-5 | 0.0045 | C6 slower | +17.4 | 0.023 | +0.3225 / 1.1e-5 / yes (10/10) |
| C6-L256 vs C1 | 4.2892 | −0.0274 | −0.63% | 0.075 | 0.0167 | no significant difference | −0.68 | 0.025 | −0.0299 / 0.017 / no (10/9) |
| **C6-L4096 vs C1** | 4.0729 | **−0.2437** | **−5.65%** | 1.08e-5 | 0.0050 | **C6 faster** | −14.5 | 0.020 | −0.2437 / 1.1e-5 / yes (10/10) |

### GraphBFS-23 (C0 31.5931 s, C1 33.1139 s)

| comparison | median C6-L (s) | Δ (s) | Δ % | MWU p | Holm thr | verdict | Cohen's d | MDE (s) | without outliers: Δ / p / Holm-sig (n) |
|---|---|---|---|---|---|---|---|---|---|
| C6-L1 vs C0 | 33.2259 | +1.6328 | +5.17% | 1.08e-5 | 0.0056 | C6 slower | +15.3 | 0.135 | same / 1.1e-5 / yes (10/10) |
| C6-L16 vs C0 | 33.1821 | +1.5889 | +5.03% | 1.08e-5 | 0.0063 | C6 slower | +15.2 | 0.134 | same / 1.1e-5 / yes (10/10) |
| C6-L256 vs C0 | 33.2929 | +1.6998 | +5.38% | 1.08e-5 | 0.0071 | C6 slower | +17.0 | 0.123 | same / 1.1e-5 / yes (10/10) |
| C6-L4096 vs C0 | 33.2056 | +1.6125 | +5.10% | 1.08e-5 | 0.0083 | C6 slower | +12.7 | 0.160 | +1.6125 / 4.6e-5 / yes (10/8) |
| C6-L1 vs C1 | 33.2259 | +0.1120 | +0.34% | 0.043 | 0.0125 | no significant difference | +1.10 | 0.123 | same / 0.043 / no |
| C6-L16 vs C1 | 33.1821 | +0.0682 | +0.21% | 0.190 | 0.0250 | no significant difference | +0.78 | 0.121 | same / 0.190 / no |
| C6-L256 vs C1 | 33.2929 | +0.1790 | +0.54% | 0.0052 | 0.0100 | C6 slower | +1.43 | 0.109 | same / 0.0052 / yes |
| C6-L4096 vs C1 | 33.2056 | +0.0917 | +0.28% | 0.218 | 0.0500 | no significant difference | +0.55 | 0.149 | +0.0917 / 0.146 / no (10/8) |

1.08e-5 is the smallest two-sided exact p attainable at 10 vs 10 (complete
separation). Excluding Tukey-flagged runs changes **no verdict**. The MDE at
the Bonferroni level α/16 is in the CSV: 0.027–0.045 s for Stencil and
0.148–0.216 s for GraphBFS.

**Falsification trigger:** not fired. No C6-L vs C0 comparison has
median(C0) − median(C6-L) > 0, let alone more than the MDE.

### Central figure

`e09b_wallclock_vs_L.png` / `.pdf`: wall-clock against L, with C0 and C1 medians
as horizontal lines (IQR shaded), individual runs as points, and one panel per
workload.

### Mechanism metrics (per-cell medians; diagnostic only)

`e09b/mechanism_by_L.csv`. Coverage is an **upper bound** (Step 1 Q1).
`spec_hits` is a **10 ms staleness-window counter, not a win counter**.

| workload | arm | demand faults | predictions | enqueued | not enqueued (drops) | migrated (`spec_migrations`) | lost after enqueue | pre-staged coverage | `fault_already_resident` | `spec_hits` (10 ms window) |
|---|---|---|---|---|---|---|---|---|---|---|
| Stencil | C0 | 346,440 | — | — | — | — | — | — | 0 | 0 |
| Stencil | C1 | 2,930,091 | — | — | — | — | — | — | 0 | 0 |
| Stencil | C6-L1 | 2,891,994 | 141,045 | 141,045 | 0 | 129,527 | 11,502 | ≤ 11.5% | 129,526 | 129,474 |
| Stencil | C6-L16 | 2,893,016 | 418,791 | 418,791 | 0 | 328,038 | 91,062 | ≤ 29.2% | 327,838 | 326,515 |
| Stencil | C6-L256 | 2,996,749 | 1,124,999 | 1,124,999 | 0 | 846,140 | 278,859 | ≤ 75.2% | 846,140 | 441,673 |
| Stencil | C6-L4096 | 2,992,458 | 1,124,999 | 919,828 | 205,171 | 919,262 | 560 | ≤ 81.7% | 919,262 | 859 |
| GraphBFS | C0 | 43,900 | — | — | — | — | — | — | 0 | 0 |
| GraphBFS | C1 | 487,831 | — | — | — | — | — | — | 0 | 0 |
| GraphBFS | C6-L1 | 486,261 | 9,166 | 9,166 | 0 | 2,773 | 6,389 | ≤ 0.96% | 2,773 | 2,520 |
| GraphBFS | C6-L16 | 486,110 | 10,425 | 10,425 | 0 | 3,915 | 6,491 | ≤ 1.36% | 3,915 | 3,436 |
| GraphBFS | C6-L256 | 485,833 | 16,506 | 16,506 | 0 | 9,743 | 6,785 | ≤ 3.38% | 9,743 | 7,649 |
| GraphBFS | C6-L4096 | 484,795 | 80,962 | 80,962 | 0 | 71,938 | 9,101 | ≤ 24.98% | 71,912 | 1,563 |

Every column is a separate per-run median, so the columns need not sum
exactly across a row.

### Prediction test (pre-registered, addendum `46761ec`)

| workload | measured C6-L4096 saving vs C1 | pre-registered interval | result |
|---|---|---|---|
| Stencil-24K | **+0.2437 s** | [0.170, 0.217] s (point 0.198) | **ABOVE: the ceiling was wrong** |
| GraphBFS-23 | −0.0917 s (C6 slower, n.s.) | [−0.0165, +0.0165] s | BELOW |

The Stencil measurement exceeds the upper end of the interval by 0.027 s. By
the rule registered in advance, this means **the ceiling was wrong**.
Specifically, the premise that wall-clock saving can come only through the
servicing thread's per-batch window is false for this workload. The wall-clock
saving is 23% larger than the servicing-window reduction measured in the
pilot. This report does not offer an explanation in place of that finding.
Candidate channels, untested, are listed under Exploratory.

On GraphBFS, "below" is consistent with an upper-bound ceiling. The pilot
predicted about 0, and the sweep measured a small, non-significant slowdown.

## Exploratory — not confirmatory

None of the following was pre-registered. Each is a lead, not a result.

1. **The prefetcher's advantage (C0 vs C1), not in the primary family.**
   - Stencil: C1/C0 = 3.80× (4.3166 / 1.1374 s). This compares with 3.88×
     on the same GPU under driver 595.84 (`GATE_B5_5070TI_REPLICATION.md`).
   - GraphBFS: 1.048×.
   - Demand faults fall 88.2% (Stencil) and 91.0% (GraphBFS) with the
     prefetcher on. This is consistent with Step 1 Q2: the prefetcher
     prevents faults.
   - The best C6 cell recovers 0.244 s of Stencil's 3.179 s prefetch-off
     gap, which is **7.7%**.
2. **Non-monotone L effect on Stencil.** L1 and L16 are *slower* than C1
   by about 0.32 s, even though they pre-stage 11–29% of pages. L256 is
   neutral and L4096 is faster.
   - Hypothesis (untested): worker overhead and va_block lock contention
     dominate when predictions land just ahead of demand.
   - In line with that, `spec_hits` ≈ `fault_already_resident` at L1 and
     L16, so nearly every pre-staged page was hit within 10 ms. That means
     the worker ran almost concurrently with the servicing thread for the
     same blocks.
3. **`spec_hits` collapses at L4096** (859 vs 919,262
   `fault_already_resident` on Stencil; 1,563 vs 71,912 on GraphBFS).
   Pre-staged pages land more than 10 ms before use. This shows directly
   that `spec_hits` is not a win counter: the fastest arm has almost none.
4. **Losses move from after enqueue to at enqueue as L grows (Stencil).**
   - L256: 0 drops, but 278,859 lost after enqueue (25%; `THROTTLED` or
     fall-through).
   - L4096: 205,171 dropped at enqueue (queue full, 18%), with only 560
     lost after enqueue.
   - Coverage still rises from ≤ 75.2% to ≤ 81.7%.
5. **Why the ceiling might be exceeded (untested candidates).**
   - C6-L4096 had about 9% fewer top-level batches in the pilot (68k vs
     75k), so fewer fault-buffer replays and GPU-side stall and replay
     cycles, which the servicing window does not time.
   - The 1 s post-run wait is outside the timed region, so it is not the
     cause.
   - Distinguishing these candidates would need instrumentation that this
     gate forbids.
6. **C6 demand faults slightly exceed C1's at L256/L4096 on Stencil**
   (+2.2%, 2.99M vs 2.93M, also seen in the pilot). Pre-staging does not
   reduce the fault count, as expected from H-map, and slightly raises it.
   The cause is not investigated.

## Stated limitations (from the pre-registration)

- GraphBFS-23 runs a weakened oracle: the cursor jumps past out-of-order
  late-ranked faults. Measured coverage is ≤ 0.96–24.98%, and GraphBFS
  results understate what a first-touch oracle could achieve there.
- `fault_already_resident` means the worker beat the servicing thread, not
  that the page was ready before the GPU accessed it.
- Pre-staged coverage is an upper bound, because `spec_migrations` counts
  no-op `make_resident` calls.
- Mechanism asymmetry: speculation never maps, and the prefetcher does.
- Platform: RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34 only. The
  manuscript's platform table is stale (ledger).

## Existing claims this bears on (flagged, not edited)

`CLAIM_SCOPE.md` is not edited. For the user to decide:

- **Claim 7** ("C3 … the absolute upper bound of SpecAsync … loses to C0"):
  - The first-touch oracle with lookahead (C6) is a *stronger* oracle than C3.
    It pre-stages up to about 82% of Stencil pages, where C3 was near zero.
  - C6 still loses to C0 at every L on both workloads (+258% to +308%
    Stencil, +5.0% to +5.4% GraphBFS; driver 595.91.07).
  - This **strengthens** the qualitative claim. It also means the phrase
    "absolute upper bound" should no longer attach to C3.
- **Claim 8** (turning off the prefetcher costs more than the oracle can
  recover):
  - **Supported** with the stronger oracle. The best C6 cell recovers 7.7%
    of the Stencil prefetch-off gap and none of the GraphBFS gap.
  - C1/C0 = 3.80× on 595.91.07, compared with 3.88× on 595.84.
- **Claim 5** (no per-hit wall-time saving):
  - With prefetch off, C6-L4096 gives a Holm-significant **5.65%**
    wall-clock saving over C1 on Stencil.
  - The claim's direction does not hold for a first-touch oracle with large
    lookahead, relative to the prefetch-off baseline. It still holds
    relative to C0.
- **Claim 10** (rate mismatch explains the near-zero hit rate):
  - With lookahead, the worker wins the race for up to 919k pages per run on
    Stencil.
  - The rate mismatch applies to *reactive* prediction (L ≈ 1 behaves like
    it). Lookahead largely overcomes it. The claim's scope should say
    "without lookahead".
- **Claim 6** (one-prediction-per-batch ceiling): not directly tested.
  Policy 6 predicts per coalesced fault with lookahead, so it sits outside
  the design that claim describes.
- **The Step 2 ceiling itself:** the decomp-ring servicing window
  underestimated the wall-clock channel, as the prediction test shows. Any
  existing or future use of servicing-window differences as a *ceiling* on
  wall-clock saving should be treated as unreliable on this evidence.
  `PIPELINING_CEILING.md` and claim 15 use a different construction (the
  D1+D2 window share) and are not directly contradicted, but they rest on a
  similar premise.
