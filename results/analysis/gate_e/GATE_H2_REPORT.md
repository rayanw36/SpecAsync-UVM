# Gate H2 - Report: the sparse-access cost of threshold 0 on HMM vs managed memory (in memory only)

## Verdict (mechanical, `H2_PREREGISTRATION.md`): MECHANISM SUPPORTED

Pre-registration committed before any timed run (`11c0c95`); stock `nvidia_uvm` 6284DA42; 8 GiB array on the 16 GB GPU, no oversubscribed cell; 160 timed runs (16 cells x 10) and a 48-run residency pass (16 cells x 3).

**Falsification note:** "H2 tests a hypothesis formed after seeing H1's K = 1 result. Its K = 1 malloc timing cells repeat a condition already observed; only the new K values, the residency measures and the allocator contrast are tests of a prediction made before the data."

## Timing (one Holm family of 8; delta = (t0 - t51) / t51)

| allocator | K | median t51 (s) | median t0 (s) | difference (s) | delta | MWU p | Holm-adjusted p | Holm-sig | MDE, family alpha (m = 8) | Cohen's d | without outliers (delta s / p) | evidence id |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| managed | 1 | 1.5812 | 1.6432 | +0.0620 | +3.92% | 1.08e-05 | 8.66e-05 | True | 0.0118 s = 0.75% | +8.5 | +0.0620 / 2.17e-05 (0 and 1 flagged) | `H2.managed_k1.t0_vs_t51` |
| managed | 8 | 1.6784 | 1.6535 | -0.0249 | -1.49% | 2.09e-03 | 2.09e-03 | True | 0.0231 s = 1.38% | -1.6 | -0.0248 / 4.14e-03 (1 and 0 flagged) | `H2.managed_k8.t0_vs_t51` |
| managed | 64 | 1.8544 | 1.6692 | -0.1853 | -9.99% | 1.08e-05 | 8.66e-05 | True | 0.0158 s = 0.85% | -18.9 | -0.1811 / 4.11e-05 (1 and 1 flagged) | `H2.managed_k64.t0_vs_t51` |
| managed | 512 | 1.9617 | 1.8207 | -0.1411 | -7.19% | 1.08e-05 | 8.66e-05 | True | 0.0302 s = 1.54% | -7.4 | -0.1411 / 1.08e-05 (0 and 0 flagged) | `H2.managed_k512.t0_vs_t51` |
| malloc | 1 | 2.1600 | 6.5589 | +4.3988 | +203.65% | 1.08e-05 | 8.66e-05 | True | 0.0403 s = 1.87% | +174.9 | +4.4003 / 4.11e-05 (1 and 1 flagged) | `H2.malloc_k1.t0_vs_t51` |
| malloc | 8 | 4.3655 | 6.5652 | +2.1997 | +50.39% | 1.08e-05 | 8.66e-05 | True | 0.0744 s = 1.70% | +47.5 | +2.1974 / 4.11e-05 (1 and 1 flagged) | `H2.malloc_k8.t0_vs_t51` |
| malloc | 64 | 8.7784 | 6.6133 | -2.1651 | -24.66% | 1.08e-05 | 8.66e-05 | True | 0.0679 s = 0.77% | -51.1 | -2.1651 / 1.08e-05 (0 and 0 flagged) | `H2.malloc_k64.t0_vs_t51` |
| malloc | 512 | 8.3860 | 6.7454 | -1.6406 | -19.56% | 1.08e-05 | 8.66e-05 | True | 0.0605 s = 0.72% | -43.3 | -1.6413 / 2.17e-05 (0 and 1 flagged) | `H2.malloc_k512.t0_vs_t51` |

## GPU memory residency (peak minus pre-launch baseline of `memory.used`; n = 3 runs per cell; 8 GiB = 8192 MiB)

| allocator | K | threshold | median (GiB) | range (GiB) | median fraction of 8 GiB | evidence id |
|---|---|---|---|---|---|---|
| managed | 1 | 0 | 7.60 | 7.23 to 7.60 | 0.950 | `H2.res.managed.k1.t0` |
| managed | 1 | 51 | 6.85 | 5.85 to 7.44 | 0.856 | `H2.res.managed.k1.t51` |
| managed | 8 | 0 | 7.60 | 7.48 to 7.60 | 0.950 | `H2.res.managed.k8.t0` |
| managed | 8 | 51 | 7.35 | 7.23 to 7.90 | 0.919 | `H2.res.managed.k8.t51` |
| managed | 64 | 0 | 8.10 | 6.73 to 8.10 | 1.013 | `H2.res.managed.k64.t0` |
| managed | 64 | 51 | 7.66 | 7.27 to 7.85 | 0.957 | `H2.res.managed.k64.t51` |
| managed | 512 | 0 | 7.37 | 6.74 to 7.99 | 0.921 | `H2.res.managed.k512.t0` |
| managed | 512 | 51 | 7.87 | 7.87 to 8.24 | 0.983 | `H2.res.managed.k512.t51` |
| malloc | 1 | 0 | 8.24 | 8.24 to 8.24 | 1.030 | `H2.res.malloc.k1.t0` |
| malloc | 1 | 51 | 0.49 | 0.49 to 0.49 | 0.061 | `H2.res.malloc.k1.t51` |
| malloc | 8 | 0 | 8.24 | 8.24 to 8.24 | 1.030 | `H2.res.malloc.k8.t0` |
| malloc | 8 | 51 | 2.24 | 2.13 to 2.24 | 0.280 | `H2.res.malloc.k8.t51` |
| malloc | 64 | 0 | 8.24 | 8.24 to 8.24 | 1.031 | `H2.res.malloc.k64.t0` |
| malloc | 64 | 51 | 8.24 | 8.24 to 8.24 | 1.031 | `H2.res.malloc.k64.t51` |
| malloc | 512 | 0 | 8.26 | 8.26 to 8.26 | 1.032 | `H2.res.malloc.k512.t0` |
| malloc | 512 | 51 | 8.26 | 8.26 to 8.26 | 1.032 | `H2.res.malloc.k512.t51` |

## Expectations

- **Z1** t0 flat in K on malloc: max/min of t0 medians <= 1.10: **HELD** (max/min = 1.028) `H2.Z1`
- **Z2** t51 strictly increasing in K on malloc: **FAILED** (t51 medians 2.160, 4.365, 8.778, 8.386) `H2.Z2`
- **Z3** malloc delta strictly decreasing in K; K=1 Holm-sig and positive; K=512 Holm-sig and negative: **FAILED** (deltas +203.65%, +50.39%, -24.66%, -19.56%) `H2.Z3`
- **Z4** malloc K=1 t0 residency >= 0.8 x 8 GiB: **HELD** (8440 MiB = 1.030 of 8 GiB) `H2.Z4`
- **Z5** malloc K=1 t51 residency <= 0.1 x 8 GiB: **HELD** (502 MiB = 0.061 of 8 GiB) `H2.Z5`
- **Z6** managed K=1 t0 residency >= 0.8 x 8 GiB: **HELD** (7784 MiB = 0.950 of 8 GiB) `H2.Z6`
- **Z7** K=1 delta larger on malloc than managed; 95% bootstrap CI of the difference has lower bound > 0: **HELD** (difference +199.73 points, 95% CI [+198.06, +201.66] (10000 resamples within cells, seed 20261106)) `H2.Z7`

## Observations outside the pre-registered criteria

- On **managed** memory the K = 1 residency at threshold 51 is already 0.856 of the array (`H2.res.managed.k1.t51`), against 0.061 on malloc (`H2.res.malloc.k1.t51`): the t0-vs-t51 residency contrast that Z5 expects exists only on HMM. On managed memory the whole array is resident after a K = 1 pass at both thresholds, so its small t0 cost is not a difference in volume moved.
- Z2 and Z3 failed because the malloc t51 medians are not monotonic in K (K = 512 is faster than K = 64, as in E8/H1); they do not enter the verdict.

## Limitations
One platform, one benchmark and page list, four K values, in memory only (HMM oversubscription is not run, see `GATE_H1_REPORT.md`). `memory.used` is a device-level measure; baseline subtraction assumes nothing else changes GPU memory during the run (headless host). Absolute times are not comparable across allocators; only within-allocator contrasts and the difference of deltas are. CS2-N10 and CLAIM_SCOPE are not edited; the proposed claim text is `consolidation/CS2_N12_PROPOSED.md`.

## Figures
`paper/figures/F-H2-time.pdf` (median time against K; t0 blue, t51 grey; managed filled, malloc open markers; every run a point) and `paper/figures/F-H2-res.pdf` (residency against K); CSV fallbacks `F-H2-time.csv`, `F-H2-res.csv`.
