# Gate E8 — Report: adversarial sparse-access test of the prefetch threshold

Pre-registration: `E8_PREREGISTRATION.md` (committed and pushed before any timed run, `305202c`). Log: `e8/E8_STATUS.md`.
Data: `e8/e8_runs.csv` (260 rows). Analysis: `tests/e8_analyze.py` (outputs in `e8/`). Figure: `e8_sparse_threshold.png` / `.pdf`.
Platform: RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34, `multi-user.target`, stock `nvidia_uvm`. delta = (arm − t51) ÷ t51,
so **negative = the lower threshold is faster**; n = 10 per cell; one Holm family of 16.

## Verdict (mechanical): GENERALITY FALSIFIED

The E6/E7 result that a lower prefetch threshold is faster **does not generalise to sparse access.** Six cells with K < 512 show
a Holm-significant **slowdown** at t0 or t25. The **largest slowdown is oversubscribed K = 1 at threshold 0: +84.96%**
(9.347 s vs 5.054 s, p = 1.08e-05).

| cell (K < 512) | arm | delta | p |
|---|---|---:|---:|
| oversubscribed, K = 1 | t0 | **+84.96%** | 1.08e-05 |
| oversubscribed, K = 8 | t25 | **+46.71%** | 1.08e-05 |
| oversubscribed, K = 8 | t0 | **+41.15%** | 1.08e-05 |
| in-memory, K = 1 | t0 | +3.95% | 1.08e-05 |
| oversubscribed, K = 1 | t25 | +1.88% | 4.33e-05 |
| in-memory, K = 8 | t25 | +0.78% | 6.84e-03 |

The benchmark is **not suspect**: the in-memory K = 512 cell is 7.54% *faster* at t0 than at t51 (p = 1.08e-05), the direction the
pre-registration requires.

**What the data shows.** The sign of the effect depends on how sparse the access is and on whether memory is oversubscribed:

- **K = 64 and K = 512 (dense enough): lower thresholds are faster in both sizes**, by 5.6–9.7%, which matches E6/E7.
- **K = 1 and K = 8, in memory: small effects** (t0: +3.95% at K = 1, −2.32% at K = 8; t25: −0.60% and +0.78%).
- **K = 1 and K = 8, oversubscribed: large slowdowns, +41% to +85% at t0** (and +47% at t25 for K = 8), with MDEs of 0.6–1.3%.
  The crossover from slowdown to speedup lies between K = 8 and K = 64 on the oversubscribed array; it was not located more finely.

## Expectations (reviewer, directional; operational definitions in the pre-registration)

| id | expectation | outcome | basis |
|---|---|---|---|
| XS1 | in-memory K = 1: t0 significantly slower than t51 | **held** | +3.95%, p 1.08e-05, Holm-significant (small: about 0.06 s) |
| XS2 | oversubscribed K = 1 or 8: t0 significantly slower | **held** | +84.96% and +41.15%, both Holm-significant |
| XS3 | K = 512, both sizes: t0 faster than t51 | **held** | in-memory −7.54%, oversubscribed −7.66% |
| XS4 | within each size, t0's delta rises monotonically as K falls | **FAILED** | not monotonic in either size: K = 64 is faster than K = 512 (in-memory −9.69 vs −7.54; oversubscribed −9.67 vs −7.66), so the delta falls from K = 512 to K = 64 before it rises |
| XS5 | t25 deltas lie between the t0 and t51 deltas, cell by cell | **FAILED** | three cells: in-memory K = 1 (t25 −0.60%, t0 +3.95%), in-memory K = 8 (t25 +0.78%, t0 −2.32%) and oversubscribed K = 8 (t25 +46.71% is worse than t0 +41.15%) |

## Primary tests (one Holm family of 16)

| size | K | arm vs t51 | median arm (s) | median t51 (s) | delta | p | Holm thr | result | Cohen's d | MDE (%) | MDE at family α (%) | without outliers: delta s / p |
|---|---:|---|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---|
| in-memory 8 GiB | 512 | stock-t0 | 1.8189 | 1.9671 | -7.54% | 1.08e-05 | 0.0042 | **faster** | -9.25 | 1.04 | 1.41 | -0.1474 / 4.1e-05 |
| in-memory 8 GiB | 512 | stock-t25 | 1.8439 | 1.9671 | -6.26% | 1.08e-05 | 0.0045 | **faster** | -4.63 | 1.57 | 2.13 | -0.1255 / 4.1e-05 |
| in-memory 8 GiB | 64 | stock-t0 | 1.6682 | 1.8471 | -9.69% | 1.08e-05 | 0.0036 | **faster** | -23.66 | 0.51 | 0.69 | -0.1790 / 4.6e-05 |
| in-memory 8 GiB | 64 | stock-t25 | 1.7103 | 1.8471 | -7.41% | 1.08e-05 | 0.0038 | **faster** | -17.41 | 0.53 | 0.71 | -0.1368 / 2.2e-05 |
| in-memory 8 GiB | 8 | stock-t0 | 1.6535 | 1.6928 | -2.32% | 1.08e-05 | 0.0033 | **faster** | -3.98 | 0.64 | 0.87 | -0.0398 / 4.6e-05 |
| in-memory 8 GiB | 8 | stock-t25 | 1.7060 | 1.6928 | +0.78% | 6.84e-03 | 0.0250 | **SLOWER** | +1.42 | 0.83 | 1.13 | +0.0132 / 6.8e-03 |
| in-memory 8 GiB | 1 | stock-t0 | 1.6413 | 1.5789 | +3.95% | 1.08e-05 | 0.0031 | **SLOWER** | +6.92 | 0.70 | 0.95 | +0.0622 / 1.0e-04 |
| in-memory 8 GiB | 1 | stock-t25 | 1.5694 | 1.5789 | -0.60% | 4.33e-02 | 0.0500 | **faster** | -1.20 | 0.78 | 1.06 | -0.0095 / 4.3e-02 |
| oversubscribed 24 GiB | 512 | stock-t0 | 7.3262 | 7.9336 | -7.66% | 1.08e-05 | 0.0100 | **faster** | -17.22 | 0.56 | 0.76 | -0.6039 / 2.2e-05 |
| oversubscribed 24 GiB | 512 | stock-t25 | 7.4917 | 7.9336 | -5.57% | 1.08e-05 | 0.0125 | **faster** | -12.77 | 0.55 | 0.75 | -0.4384 / 2.2e-05 |
| oversubscribed 24 GiB | 64 | stock-t0 | 6.9274 | 7.6688 | -9.67% | 1.08e-05 | 0.0071 | **faster** | -32.00 | 0.38 | 0.52 | -0.7381 / 2.2e-05 |
| oversubscribed 24 GiB | 64 | stock-t25 | 7.1353 | 7.6688 | -6.96% | 1.08e-05 | 0.0083 | **faster** | -23.28 | 0.38 | 0.52 | -0.5301 / 2.2e-05 |
| oversubscribed 24 GiB | 8 | stock-t0 | 9.5652 | 6.7765 | +41.15% | 1.08e-05 | 0.0056 | **SLOWER** | +46.77 | 1.10 | 1.49 | +2.7943 / 2.2e-05 |
| oversubscribed 24 GiB | 8 | stock-t25 | 9.9418 | 6.7765 | +46.71% | 1.08e-05 | 0.0063 | **SLOWER** | +99.10 | 0.59 | 0.80 | +3.1653 / 1.1e-05 |
| oversubscribed 24 GiB | 1 | stock-t0 | 9.3473 | 5.0537 | +84.96% | 1.08e-05 | 0.0050 | **SLOWER** | +84.37 | 1.26 | 1.71 | +4.2977 / 2.2e-05 |
| oversubscribed 24 GiB | 1 | stock-t25 | 5.1485 | 5.0537 | +1.88% | 4.33e-05 | 0.0167 | **SLOWER** | +3.23 | 0.77 | 1.04 | +0.0989 / 2.2e-05 |

## Descriptive: per-pass kernel time (median of 10 runs; not tested)

| size | K | threshold | pass 1 (ms) | pass 2 (ms) | pass 3 (ms) |
|---|---:|---|---:|---:|---:|
| in-memory 8 GiB | 1 | t0 | 158.0 | 0.0 | 0.0 |
| in-memory 8 GiB | 1 | t25 | 40.2 | 0.0 | 0.0 |
| in-memory 8 GiB | 1 | t51 | 34.2 | 0.0 | 0.0 |
| in-memory 8 GiB | 8 | t0 | 161.1 | 0.0 | 0.0 |
| in-memory 8 GiB | 8 | t25 | 186.3 | 0.0 | 0.0 |
| in-memory 8 GiB | 8 | t51 | 140.0 | 0.1 | 0.0 |
| in-memory 8 GiB | 64 | t0 | 168.3 | 0.0 | 0.1 |
| in-memory 8 GiB | 64 | t25 | 185.8 | 0.0 | 0.1 |
| in-memory 8 GiB | 64 | t51 | 311.7 | 0.0 | 0.1 |
| in-memory 8 GiB | 512 | t0 | 173.5 | 0.7 | 1.1 |
| in-memory 8 GiB | 512 | t25 | 186.5 | 0.7 | 1.1 |
| in-memory 8 GiB | 512 | t51 | 287.5 | 0.7 | 1.1 |
| oversubscribed 24 GiB | 1 | t0 | 1762.4 | 1830.7 | 1804.9 |
| oversubscribed 24 GiB | 1 | t25 | 357.3 | 370.7 | 323.2 |
| oversubscribed 24 GiB | 1 | t51 | 294.5 | 305.7 | 290.9 |
| oversubscribed 24 GiB | 8 | t0 | 1772.3 | 1800.4 | 1998.6 |
| oversubscribed 24 GiB | 8 | t25 | 1863.6 | 1856.8 | 2175.3 |
| oversubscribed 24 GiB | 8 | t51 | 902.3 | 790.2 | 921.3 |
| oversubscribed 24 GiB | 64 | t0 | 719.6 | 1091.2 | 1095.4 |
| oversubscribed 24 GiB | 64 | t25 | 767.7 | 1136.0 | 1133.1 |
| oversubscribed 24 GiB | 64 | t51 | 1059.7 | 1234.3 | 1229.2 |
| oversubscribed 24 GiB | 512 | t0 | 734.9 | 1101.9 | 1106.7 |
| oversubscribed 24 GiB | 512 | t25 | 772.1 | 1134.3 | 1136.4 |
| oversubscribed 24 GiB | 512 | t51 | 997.7 | 1213.2 | 1199.0 |

- **In memory,** passes 2 and 3 cost almost nothing at every threshold (the touched pages are resident after pass 1); the threshold only
  changes pass 1: at K = 1, t0 spends 158 ms against 34 ms at t51 to touch 4,096 pages, and at K = 512 it spends 174 ms against 288 ms.
- **Oversubscribed, K = 1 and 8 at t0 (and K = 8 at t25): every pass costs about the same** (about 1.8 s per pass at K = 1, t0, against about 0.3 s
  at t51). The data is not kept resident between passes, so each pass pays the migration cost again. This is consistent with the lower
  threshold causing whole regions to be migrated for one or a few touched pages, but the stock module has no fault counters, so that
  reading is an **interpretation**, not a measurement. At K = 64 and 512 the passes cost 0.7–1.2 s at every threshold.

## Descriptive, untested: mechanism (Family M, E3a-2 module with speculation off, in-memory, n = 5)

| cell (E3a-2 module, policy 0, in-memory) | n | wall median (s) | demand faults (median) | D5 per demand fault (ns) |
|---|---:|---:|---:|---:|
| in_k1 spec-C0-t0 | 5 | 1.6458 | 5,180 | 17,368 |
| in_k1 spec-C0-t51 | 5 | 1.5692 | 6,744 | 4,681 |
| in_k512 spec-C0-t0 | 5 | 1.8181 | 73,006 | 1,317 |
| in_k512 spec-C0-t51 | 5 | 1.9753 | 141,701 | 1,854 |

- Wall-clock agrees in direction with the stock-module cells (K = 1: +4.9% at t0; K = 512: −8.0%).
- At K = 512, t0 roughly **halves the demand faults** (73,006 vs 141,701) at a **lower** D5 per fault; at K = 1 t0 has **fewer** faults
  (5,180 vs 6,744) but a **3.7×** larger D5 per fault (17.4 µs vs 4.7 µs): fewer, much larger migrations per fault, which is what a
  sparse workload pays for. n = 5, no test applied.

## Run integrity

- 260 rows (IN 120, OV 120, M 20); all `exit_code` 0 (so every checksum was confirmed); the read-back threshold equals the order's in
  every row; srcversions only `6284DA42…` (stock) and `33FD42E6…` (Family M); `ft_fast_cas_giveup` 0. No stop file. No cell was dropped
  and no OV group or Family M was skipped. 28 smoke runs are excluded. Pushed after every family and group (all `ok`).
- Two runs each logged one new kernel line (idx 102 and 223): a `workqueue: drm_fb_helper_damage_work hogged CPU` notice and an
  `hrtimer: interrupt took 3897 ns` notice appear in the log in this window. Neither is in the stop pattern. No run was removed.
- The benchmark was validated for correctness (a)–(e) before use (`e8/bench_validation.log`); the analyzer's positive control reproduces
  E7 Family A (−9.57%, p 1.08e-05).

## Limitations

- `stock-t0/t25` are not the shipped driver. One platform; one synthetic benchmark; one page list per size (seed 202610081); K ∈ {1, 8, 64, 512}.
- Process wall-clock includes the host's initial write of the whole array and CUDA start-up; this is identical across thresholds and dilutes
  relative effects, especially in memory at K = 1 (a 124 ms pass-1 difference inside a 1.6 s process).
- The crossover K on the oversubscribed array lies between 8 and 64 and was not located; no K between 8 and 64 was run.
- The mechanism for the oversubscribed slowdown is inferred from per-pass times; the stock module cannot report fault or migration counts, and Family M
  (n = 5) is in-memory only, so it does not cover the oversubscribed case.
- Oversubscription here is 1.5× the GPU's memory; other ratios were not tested.

## Existing claims flagged (not edited)

- **CS2-N10 (Prefetch threshold tuning):** its generality sentence ("Generality: E7 Family B, and the T4 replication") now has a counter-example
  class: sparse access on an oversubscribed array, where t0 and t25 are far slower than the shipped 51. The claim should state that the
  gain depends on access density and on oversubscription, and that the shipped default is not dominated by t0.
- **CS2-N1 item 4** ("the same gain is available without speculation"): qualified. The tuning gain is not free: it is workload-dependent and
  reverses for sparse oversubscribed access. Items 3–5 are unchanged.
- **E7 / the "no workload slower at t0" statement** (GATE_E7_REPORT): it is true of the workloads E7 tested, and E8 shows it is not a general property.
- **OPEN_DECISIONS D1 note** ("any follow-on predictor is compared against a tuned C0"): the tuned C0 is workload-dependent, so "tuned" needs a definition.

The user decides these edits.
