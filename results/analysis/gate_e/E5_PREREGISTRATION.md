# Gate E5 — Pre-registration: does speculation help by feeding the prefetcher?

**Written and committed 2026-09-26, before the first run.** No E5 data exists
at commit time. The source check (`E5_MECHANISM.md`, commit `48e7a78`) is
part of this pre-registration.

Code fixed with this commit (not to be changed after the first run):

| file | role |
|---|---|
| `tests/e5_runner.py` | the E4 runner plus the threshold parameter and its read-back |
| `tests/e4_runner.py`, `tests/e3b_runner.py`, `tests/e3b_dmesg.py` | the runners it builds on, and the timestamp dmesg diff |
| `tests/e3b_collect_tables.py` | the table collector |
| `tests/e5_make_order.py` | order |
| `tests/e5_analyze.py` | analysis; it imports E0.9b's statistical helpers unchanged, and its Bonferroni MDE is set for a family of 3 |

## Hypothesis (H-feed)

The prefetcher's density rule fetches a whole region when more than a
threshold share of its pages are *already resident, or faulting now*. Pages
that speculation made resident count toward that share. Staging a whole
block pushes regions over the threshold early, so the demand path's service
step maps them in one go and prevents the faults that would have followed.

**Source status (Step 1):** the premise holds, and H-feed is not refuted
from source.
- The density bitmap is `resident_mask | faulted_pages`, using the
  destination's resident mask (`uvm_perf_prefetch.c:227`, `:397`).
- Already-resident prefetched pages are mapped in the same service step
  (`uvm_va_block.c:11532`, `:11961`, `:11981`).

## Platform, module, parameters

- RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34-generic, headless.
- **Every arm uses the new module**
  `nvidia-uvm-specasync-NEW-e3a2-width-ftfast.ko` (srcversion
  **`33FD42E6E16B0A6658E2BEB`**). No new kernel code, no rebuilds.
- `specasync_log_enabled=1` and `specasync_trace_faults=0` on every arm.
- `uvm_perf_prefetch_threshold` is set at `insmod` and verified by read-back
  from `/sys/module/nvidia_uvm/parameters/`. A mismatch is a stop.
- **T_off = 100.** The density test is `counter·100 > pages·threshold`
  (strict), and `counter ≤ pages`, so it can never fire at 100. The accepted
  range is 0–100; values above 100 silently fall back to 51, so they are
  **not** used.

## Arms (Stencil-24K only)

| arm | policy | depth | prefetch | threshold | W | fast | L |
|---|---|---|---|---|---|---|---|
| C0-t51 | 0 | 0 | on | 51 (default) | 1 | 0 | — |
| C7W512-t51 | 6 | 1 | on | 51 | 512 | 1 | 4096 |
| C0-t75 | 0 | 0 | on | 75 | 1 | 0 | — |
| C7W512-t75 | 6 | 1 | on | 75 | 512 | 1 | 4096 |
| C0-toff | 0 | 0 | on | 100 | 1 | 0 | — |
| C7W512-toff | 6 | 1 | on | 100 | 512 | 1 | 4096 |

GraphBFS is excluded: E4 found no F1 effect there, so there is nothing to
explain.

**Table.** A fresh prefetch-off first-touch table is collected at the start
of Step 3 by `tests/e3b_collect_tables.py` (the verified module, the
unchanged E0.9b procedure). The distinct-page assertion is **1,125,000**,
and the session stops if it fails. The collector also builds a GraphBFS
table, which is not used.

## Design

- **n = 10 per cell, 60 runs.**
- **Order:** `e5/e5_order.csv`, from `tests/e5_make_order.py` with seed
  **202609265**. It has 10 blocks, each a seeded permutation of all 6 cells.
  **SHA-256 `25450faec8589d17ec771f295832e79579f9b1db87cb830eab3f09b159c3c4ca`.**
  The order is followed exactly.
- **Per run:** as in E4. Reload, srcversion and **parameter read-back
  (including the threshold)**, `ft_fast_verified`, the timestamp dmesg
  diff, `specasync_clear`, `timeout 22 setarch -R <bench>`, a 1 s drain,
  counters, then **batch- and decomp-ring dumps outside the timed region**,
  then stop checks and one CSV row (`e5/e5_runs.csv`).
- **Timeout: 22 s**, confirmed as adequate. At T_off the prefetcher
  produces no prefetch pages for Stencil (`E5_MECHANISM.md` §4), so C0-toff
  should run near prefetch-off speed. E4's C1 median was 4.30 s and its
  C6-W512 median 3.30 s, both about 5× inside the timeout.
- **Commits:** every 10 runs (`--commit-every 10`). After any interruption
  that is not a stop condition, the run resumes at the next index not in the
  CSV. The sweep is never restarted and no cell is ever re-run.
- Wall-clock goes to the CSV only. `e5_analyze.py` refuses to run on fewer
  than 60 rows.

## Primary mechanism test: demand faults

For each threshold *t* ∈ {51, 75, 100}:

    D(t) = 1 − median(demand faults, C7W512-t) ÷ median(demand faults, C0-t)

E4 measured D(51) ≈ 0.40.

**Test.** A two-sided Mann–Whitney U on per-run demand faults, C7W512-t vs
C0-t, one per threshold. Holm across the 3, α = 0.05.

**H-feed verdict, applied mechanically:**
- **Supported:** D(51) > 0 **and** its demand-fault MWU is Holm-significant,
  **and** D(T_off) < **0.25 × D(51)**.
- **Refuted:** D(T_off) ≥ **0.75 × D(51)**. The fault reduction does not
  depend on the density rule. The alternatives in `E5_MECHANISM.md` §4 then
  become the leading candidates: PTE merging first, since the other two are
  inert for Stencil from source.
- **Partial:** anything between. Both values and the ratio are reported.
- **Edge case, fixed in advance:** if D(51) ≤ 0, the ratio is undefined. The
  result is then reported as **not classifiable**, with all three D values.

**Dose-response (secondary, not decisive):** H-feed predicts
D(75) ≥ D(51). D(75) is reported, with whether that held.

## Secondary: wall-clock

- C7W512-t vs C0-t at each threshold: **3 comparisons, one Holm family**,
  two-sided MWU, median of record.
- Reported for each: MDE at achieved n and at α/3, Cohen's d, and results
  with and without Tukey-flagged outliers. No run is ever removed from the
  primary analysis.
- Process wall-clock (`time.monotonic_ns()` around
  `timeout 22 setarch -R <bench>`) is the outcome of record.
- H-feed predicts the wall-clock gain shrinks or vanishes at T_off along
  with the fault reduction. This is descriptive and not part of the verdict.

## Mechanism metrics (per cell; diagnostic)

Demand faults, `fault_already_resident`, predictions, same-region skips,
enqueued, drops, `spec_pages_requested`, D5, pre-lock servicing
(Σ svc − D3 − D4), and `enqueue_overhead_ns`.

Integrity checks on every policy-6 run:
- Identity 1: `demand_faults = pred + held + unk + exh + giveup`;
- Identity 2: `pred = same_region + enqueued + drops`;
- ring coverage 100% (fewer than 131,071 records), or the covered fraction
  is reported and nothing is scaled.

## Outputs

`e5/e5_runs.csv`, `e5/fault_reduction.{csv,md}`,
`e5/wallclock_comparisons.csv`, `e5/mechanism.csv`, `e5/integrity.txt`, and
the figure `e5_threshold.{png,pdf}`. The figure shows demand faults and
wall-clock against threshold, with C0 and C7W512 as two series.

Anything not pre-registered goes under **Exploratory — not confirmatory**.

## Stated limitations

- Single workload and single platform: RTX 5070 Ti, driver 595.91.07,
  kernel 7.0.0-34.
- `uvm_perf_prefetch_threshold` also changes the prefetcher for C0, so
  **C0-toff and C0-t75 are not the shipped driver**. Every comparison is
  within a threshold.
- The oracle is still a **perfect first-touch table**. This gate explains
  the mechanism, not what a practical predictor achieves.
- At T_off the prefetch hint is still computed (`uvm_perf_prefetch_enable=1`)
  and costs time, but yields nothing. That makes C0-toff slightly slower
  than a true prefetch-off run.

## Stop conditions (as E4, verbatim scope)

> Any new `dmesg` line (any source) matching `BUG`, `Oops`, `WARNING`,
> `general protection`, `NULL pointer`, `exited with irqs disabled`,
> `soft lockup`, `hung_task`, or `RCU stall` (timestamp-based diff); `rmmod`
> failure or nonzero `refcnt`; benchmark timeout; `MemAvailable` below 6 GiB;
> free disk below 10 GiB; srcversion mismatch; nonzero benchmark exit;
> parameter read-back mismatch (including `uvm_perf_prefetch_threshold`);
> `specasync_ft_fast_verified ≠ 1` on any fast = 1 load;
> `specasync_ft_fast_cas_giveup > 0`; `specasync_spec_region_invalid > 0`;
> or anything requiring a departure from this pre-registration.
>
> On any: stop immediately, no retries, leave the system as it is, record
> the evidence, commit locally.
