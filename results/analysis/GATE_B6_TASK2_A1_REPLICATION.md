# Gate B6, Task 2 — A1 replication on RTX 5070 Ti (worker completion / dispatch latency)

Platform: RTX 5070 Ti, sm_120, driver 595.84, srcversion `9E98EF08CBA769C50A24937`
(Task 1 build). T4 baseline throughout: `GATE_A1_REPORT.md`.

## Platform-difference axes carried over from Task 0 (apply to interpretation below)

- **PCIe: T4 gen3 x8 (~8 GB/s) vs this machine gen5 x16 (~63 GB/s), roughly 8x more migration
  bandwidth.** This is migration-relevant and first-order for this project's results —
  flagging it prominently here because Task 2's exec-latency figures (the migration step)
  are exactly where it would show up. Note on already-collected B5 data: the prefetch-on
  benefit was **3.55x on the T4 vs 3.88x here** (`GATE_B5_5070TI_REPLICATION.md`,
  `CLAIM_SCOPE.md` row 8) despite the 8x bandwidth gap — i.e. **the prefetcher's value is not
  bandwidth-explained**; something other than raw transfer bandwidth (batching, fault-service
  hot-path overhead) dominates that ratio.
- **CPU: T4 2 cores/4 threads vs this machine 12 cores/24 threads (6x).** Task 2 is
  therefore a **partial substitute for the never-run A3 core-count control** (T5 in the
  T4 numbering was gated on an AWS instance resize that never happened). This is a
  pre-declared question, answered directly in Result 2b below, regardless of which way it
  comes out.

## Protocol

`tests/t_a1_worker_completion.sh`, host-portability changes only (`KO`/`OUT` env overrides
added, same pattern as `t1_gate3_interleaved.sh` — no logic changed). C3 (oracle, depth=1,
prefetch OFF) only. `specasync_clear` before every rep.

- **Full-size**: Stencil@24000, GraphBFS@23, n=5 each — the published sizes, unmodified.
- **Short-run non-wrapping cross-check**: the T4 used Stencil@2000, GraphBFS@18. Calibrated
  (single-rep dry check first) rather than assumed: on this platform these enqueue 26,088
  and 15,767 items respectively — both well under the 131,072-slot ring cap, same as the T4.
  No size adjustment was needed. Confirmed `worker_ring_wrapped=no` and
  `window_records == processed` for every one of the 10 short-run reps.

Output: `results/analysis/t_a1_worker/{short_run,full_run}_5070ti/` (kept separate from the
T4's `short_run`/`full_run` dirs to avoid collision, same convention as B5's
`gate3_interleaved_5070ti`). Analyzed with `tests/t_a1_analyze.py`, given a directory-override
argument pair (its only change — the T4-default paths and behavior are untouched when called
with no arguments) so it could read the 5070 Ti's directories and this platform's own
uncontended-probe reference instead of the T4's hardcoded one.

## Uncontended probe baseline (this platform's own — not the T4's)

Computed from Task 1's deterministic hit-probe worker-log dump (256 items, no ring wrap):

| | dispatch (enqueue→dequeue) | exec (dequeue→completion) |
|---|--:|--:|
| median | **5.26 µs** | **0.10 µs** |
| p90 | 5.36 µs | 0.17 µs |

T4's equivalent (`GATE_A1_REPORT.md`): dispatch ≈5.6 µs median, exec ≈0.35 µs median — close,
same regime. This platform's own baseline (not the T4's) is what the ratios below are
computed against, since absolute µs are not comparable across CPU/PCIe-different platforms
but the ratio to each platform's own idle-dispatch cost is.

## Result 1 — processed/enqueued ratio: exactly 1.000000, every rep, both scales

| run set | bench | reps | sum(processed) | sum(enqueued) | ratio | sum(drops) |
|---|---|---|--:|--:|---|--:|
| short | GraphBFS-18 | 5 | 74,246 | 74,246 | **1.000000** | 11,964 |
| short | Stencil-2000 | 5 | 130,878 | 130,878 | **1.000000** | 5,915 |
| full | GraphBFS-23 | 5 | 2,036,401 | 2,036,401 | **1.000000** | 330,811 |
| full | Stencil-24000 | 5 | 13,503,518 | 13,503,518 | **1.000000** | 1,612,685 |

Every individual rep asserted programmatically (`t_a1_analyze.py`'s `assert p == e`) — no
exceptions raised, all 20 reps pass. **(b) Backlog is ruled out here exactly as on the T4.**
Nothing queued is ever abandoned; every item that clears the queue-depth cap runs to
completion. **Reproduces.**

## Result 2a — dispatch/exec latency: absolute terms

| run set | bench | dispatch median | dispatch p90 | exec median | exec p90 |
|---|---|--:|--:|--:|--:|
| short | GraphBFS-18 | 60.33 µs | 1,702.37 µs | 0.45 µs | 2.88 µs |
| short | Stencil-2000 | 25.61 µs | 334.66 µs | 0.40 µs | 0.51 µs |
| full | GraphBFS-23 | 2,274.57 µs | 3,113.01 µs | 2.23 µs | 3.58 µs |
| full | Stencil-24000 | 2,306.31 µs | 3,605.79 µs | 2.24 µs | 3.32 µs |

T4 (`GATE_A1_REPORT.md`, absolute):

| run set | bench | dispatch median | dispatch p90 | exec median | exec p90 |
|---|---|--:|--:|--:|--:|
| short | GraphBFS-18 | 2,579.6 µs | 6,577.9 µs | 2.96 µs | 10.19 µs |
| short | Stencil-2000 | 3,198.0 µs | 3,804.2 µs | 2.82 µs | 3.09 µs |
| full | GraphBFS-23 | 10,607.0 µs | 12,068.9 µs | 10.09 µs | 12.73 µs |
| full | Stencil-24000 | 9,438.1 µs | 11,535.9 µs | 9.33 µs | 11.88 µs |

Absolute dispatch latency is 4-40x lower here than on the T4 at every cell — expected given
both the CPU (6x cores, presumably higher per-core clock/IPC too) and PCIe differences, and
**exactly why absolute µs are not the comparable quantity** across these two platforms (per
Task 0's addendum). Exec latency (the migration step) is also lower here (2.2-2.4 µs
full-run vs 9.3-10.1 µs on the T4, roughly 4x) — directionally consistent with the 8x PCIe
bandwidth gap mattering for the actual transfer, though a 4x latency drop from an 8x
bandwidth increase is unsurprising for small, fixed-overhead-dominated single-page transfers
and should not be read as a clean bandwidth-scaling result on its own.

## Result 2b — dispatch/exec latency: ratio to this platform's own uncontended baseline (the comparable quantity)

| run set | bench | dispatch ratio (5070 Ti) | dispatch ratio (T4) |
|---|---|--:|--:|
| short | GraphBFS-18 | **11.5x** | 460.6x |
| short | Stencil-2000 | **4.9x** | 571.1x |
| full | GraphBFS-23 | **432.4x** | 1,894.1x |
| full | Stencil-24000 | **438.5x** | 1,685.4x |

(5070 Ti ratios: dispatch median / 5.26 µs. T4 ratios: dispatch median / 5.6 µs, recomputed
here from `GATE_A1_REPORT.md`'s reported medians for direct comparison — T4's own report
states the blowup qualitatively as "500-2,000x" without laying out this exact per-cell table.)

**This is the pre-declared A3-substitute answer, stated directly, both directions:**

- **At full-run (sustained, high-enqueue-rate) load, the blowup reproduces but is
  substantially smaller: ~432-438x here vs ~1,685-1,894x on the T4 — roughly a 4x
  reduction, not enough to fall out of the "500-2,000x" regime's order of magnitude but
  landing just below its stated low end.** Dispatch latency under sustained load is still
  three orders of magnitude above the idle baseline on 6x the cores — CPU contention has not
  been eliminated as a factor at this load level, but it has been reduced.
- **At short-run (low-enqueue-rate, uncontended-adjacent) load, the blowup does NOT
  reproduce in the same regime: ~4.9-11.5x here vs ~460.6-571.1x on the T4 — roughly a
  50-100x reduction.** This is not a weak positive to be smoothed into "still shows a
  blowup" — at this load level the 5070 Ti's dispatch latency is close to its own
  uncontended baseline, a qualitatively different regime from the T4's short-run figures.

**Read together: core count is a first-order contributor to the dispatch-latency blowup at
low-to-moderate contention, but the mechanism does not disappear at high sustained enqueue
rates even with 6x the physical cores.** This does not overturn Gate A1's race-loss
explanation for the near-zero real-workload hit rate (full-run — the load regime the
published benchmark sizes actually run at — still shows a ~430x blowup, comfortably enough
to lose the race against demand-fault inter-arrival rates in the ~0.008-0.19M faults/sec
range this project established (corrected 2026-08-13, `GATE_T4_REPORT.md`/`GATE_A1_REPORT.md`
-- supersedes the 0.03-0.3M figure originally cited here from
`RATE_MISMATCH_VERIFICATION.md`, which was itself later found to carry a second,
independent ring-saturation error). But it reframes *why*: the
mechanism is not purely architectural/algorithmic (workqueue dispatch overhead independent of
host resources) — it has a real, load-dependent CPU-contention component that this
platform's extra cores partially, not fully, absorb. A true A3 (controlled core-count sweep
on identical hardware) remains unrun; this is a cross-platform observation at fixed (if very
different) core counts, not a controlled sweep, and should be scoped as such.

## Result 3 — verdict

**Reproduces (Result 1, processed==enqueued exactly, backlog ruled out) — reproduces with a
smaller but still present magnitude, load-dependent (Result 2b, dispatch-latency blowup:
full-run ~430x here vs ~1,685-1,894x on T4; short-run ~5-12x here vs ~460-571x on T4).**
Gate A1's core finding — that the near-zero real-workload hit rate is explained by dispatch
scheduling delay, not un-executed backlog — holds on this platform. Its magnitude is not
platform-invariant, and the direction of the difference (fewer cores → bigger blowup) is
exactly what a CPU-contention component of the mechanism would predict, making Task 2 modest
positive evidence (not proof, absent a controlled sweep) that CPU-side contention is a real
part of the mechanism rather than a T4 artifact.
