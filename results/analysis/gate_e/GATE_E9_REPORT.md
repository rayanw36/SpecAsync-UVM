# Gate E9 — Report: unified-memory tracing of the threshold effect

Pre-registration: `E9_PREREGISTRATION.md` (committed and pushed before any traced run, `5ad9e19`). Log: `e9/SESSION_STATUS.md`. Data: `e9/e9_runs.csv` (42 rows, n = 3 per cell);
medians and ranges: `e9/cell_medians.csv`. Analysis: `tests/e9_analyze.py` (descriptive only; no tests). Figure: `e9_um_bytes.png` / `.pdf`.
Platform: RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34, `multi-user.target`, stock `nvidia_uvm`, nsys 2025.3.2. Wall-clock was recorded and is **not** compared.
All counts are **under nsys tracing** (see Limitations). Sizes: GiB = 2^30 bytes.

## Expectations (reviewer, directional; operational definitions in the pre-registration)

| id | expectation | outcome | basis (medians of 3) |
|---|---|---|---|
| Y1 | oversubscribed K = 1: HtoD at t0 at least 10× t51 | **held** | 129.80 GiB vs 3.96 GiB: **32.8×** |
| Y2 | oversubscribed K = 1 and 8 at t0: DtoH at least 1 GiB per pass, much smaller at t51 | **held** | K=1: t0 DtoH 32.8 / 41.0 / 40.8 GiB per pass, total 114.6 vs 3.5 GiB at t51; K=8: 32.8 / 44.8 / 45.1 GiB per pass, total 122.7 vs 29.2 GiB at t51 (0.24 × t0, just inside the 0.25 criterion) |
| Y3 | Stencil-24K: HtoD within 5%; GPU fault count at t0 below t51 | **held** | HtoD 4.26 vs 4.29 GiB (**0.74%** apart); GPU page faults 27,876 vs 91,935 (**−70%**) |
| Y4 | oversubscribed K = 1 at t51: the repeat-pass cost comes with DtoH eviction (or remote-map/thrashing), not zero migration | **held** (DtoH arm only) | passes 2 and 3 migrate **1.31 / 1.15 GiB in and 1.31 / 1.15 GiB out**; thrashing and remote-map events are not observable in this nsys |

Y2's K = 8 criterion is met narrowly (t51 total is 24% of t0's against a 25% limit), so it is a weaker pass than Y1, Y3 and Y4.

## What the counts show

1. **Sparse access at threshold 0 migrates whole regions, and on an oversubscribed array does so every pass.** At oversubscribed K = 1 the program touches 12,288 pages
   (48 MiB) per pass, yet at t0 the traced run moves **130 GiB in and 115 GiB out** (about 41–48 GiB in per pass, more than the 24 GiB array); at t51 it moves **4.0 GiB in and 3.5 GiB out**.
   Dividing the 3-pass totals by 3 × 12,288 touched pages (arithmetic, not a measurement): about **3.6 MiB migrated in per touched page per pass at t0** (more than one 2 MB block) against about **113 KiB at t51**.
   This is the migration-volume counterpart of E8's +85% slowdown at the same cell (and +41% at K = 8, where HtoD is 138 vs 33 GiB).
2. **The previously unexplained E8 observation is explained.** At t51, oversubscribed K = 1 still costs about 0.3 s per pass (E8 per-pass kernel time). The trace shows why: **every repeat pass
   still migrates about 1.2 GiB in and about 1.2 GiB out** (DtoH eviction accompanies it; the GPU is full of earlier data), so the cost is not zero migration. (Y4.)
3. **Where a lower threshold is faster, the same bytes move in fewer, larger migrations.** Oversubscribed K = 64 and 512 move about **72 GiB in at both thresholds** (24 GiB per pass); in-memory K = 512 moves 7.6 vs 7.9 GiB; Stencil-24K 4.26 vs 4.29 GiB.
   What falls is the **GPU fault count**: 2,027 vs 7,661 (K=64), 2,780 vs 6,642 (K=512), 271 vs 776 (in-memory K=512), 27,876 vs 91,935 (Stencil). This is the mechanism behind E6/E7's gains on dense access: fewer faults, not fewer bytes.
4. **In memory the cost of over-migration is small because the array fits.** In-memory K = 1 moves **8.0 GiB at t0 against 0.25 GiB at t51** (32×), but in a single pass (passes 2 and 3 move nothing), which matches E8's small in-memory effect (+3.95% wall-clock, and a 158 vs 34 ms first pass).
5. **A finding that was not asked for: the CPU page-fault count depends on the threshold.** nsys counts **6× more CPU page faults at t51 than at t0 in every cell**, and the t0 count equals the number of 2 MB blocks
   (oversubscribed 12,288 vs 73,728; in-memory 4,096 vs 24,576; Stencil-24K 2,198 vs 13,188). The host writes the whole array before the first kernel, so this is the host-side first-touch path, and it
   suggests the prefetcher also acts on CPU faults: at t0 one CPU fault populates a whole block, at t51 about six are needed. **That is an inference from the counts; the source path was not read here.**
   If it holds, part of the E6–E8 wall-clock difference between thresholds arises on the host before any kernel runs, in every workload, including the cells where the GPU side is unchanged.

## Per-cell counts (medians; min–max of the 3 runs in parentheses)

| cell | thr | n | HtoD GiB: median (min–max) | DtoH GiB | GPU page faults | CPU page faults | HtoD by page fault GiB | HtoD by speculative prefetch GiB |
|---|---|---:|---|---|---|---|---:|---:|
| oversubscribed K=1 | t0 | 3 | 129.80 (127.41–130.44) | 114.61 (112.21–115.25) | 626 (607–638) | 12,288 | 0.254 | 129.547 |
| oversubscribed K=1 | t51 | 3 | 3.96 (3.72–4.03) | 3.49 (3.24–3.55) | 526 (511–529) | 73,728 | 0.248 | 3.713 |
| oversubscribed K=8 | t0 | 3 | 138.31 (137.93–139.33) | 122.74 (120.03–124.13) | 1,634 (1,632–1,636) | 12,288 | 0.913 | 137.399 |
| oversubscribed K=8 | t51 | 3 | 33.22 (33.22–33.24) | 29.17 (29.09–29.31) | 4,857 (4,856–4,872) | 73,728 | 2.024 | 31.199 |
| oversubscribed K=64 | t0 | 3 | 71.78 (71.76–72.00) | 53.76 (53.53–54.54) | 2,027 (2,021–2,049) | 12,288 | 1.097 | 70.706 |
| oversubscribed K=64 | t51 | 3 | 72.00 (71.91–72.00) | 56.81 (56.69–56.81) | 7,661 (7,574–7,676) | 73,728 | 2.441 | 69.556 |
| oversubscribed K=512 | t0 | 3 | 71.68 (71.68–71.84) | 52.87 (52.87–52.87) | 2,780 (2,771–2,811) | 12,288 | 1.314 | 70.364 |
| oversubscribed K=512 | t51 | 3 | 71.83 (71.81–71.88) | 54.85 (54.54–54.88) | 6,642 (6,629–6,691) | 73,728 | 2.730 | 69.104 |
| in-memory K=1 | t0 | 3 | 8.00 (8.00–8.00) | 0.00 (0.00–0.00) | 74 (71–77) | 4,096 | 0.016 | 7.984 |
| in-memory K=1 | t51 | 3 | 0.25 (0.25–0.25) | 0.00 (0.00–0.00) | 72 (37–105) | 24,576 | 0.016 | 0.234 |
| in-memory K=512 | t0 | 3 | 7.64 (7.45–7.64) | 0.00 (0.00–0.00) | 271 (264–274) | 4,096 | 0.136 | 7.499 |
| in-memory K=512 | t51 | 3 | 7.94 (7.85–8.00) | 0.00 (0.00–0.00) | 776 (753–776) | 24,576 | 0.288 | 7.653 |
| Stencil-24K | t0 | 3 | 4.26 (4.22–4.29) | 0.00 (0.00–0.00) | 27,876 (27,146–28,808) | 2,198 | 0.107 | 4.151 |
| Stencil-24K | t51 | 3 | 4.29 (4.29–4.29) | 0.00 (0.00–0.00) | 91,935 (91,057–92,309) | 13,188 | 0.270 | 4.022 |

## Per-pass migrated bytes, `bench_sparse` cells (medians)

| cell | thr | HtoD pass 1 / 2 / 3 (GiB) | DtoH pass 1 / 2 / 3 (GiB) |
|---|---|---|---|
| oversubscribed K=1 | t0 | 48.00 / 41.04 / 40.82 | 32.80 / 41.04 / 40.82 |
| oversubscribed K=1 | t51 | 1.50 / 1.31 / 1.15 | 1.03 / 1.31 / 1.15 |
| oversubscribed K=8 | t0 | 47.98 / 44.85 / 45.71 | 32.79 / 44.85 / 45.11 |
| oversubscribed K=8 | t51 | 11.34 / 10.68 / 11.22 | 7.75 / 10.68 / 10.90 |
| oversubscribed K=64 | t0 | 24.00 / 24.00 / 23.78 | 6.82 / 24.00 / 22.95 |
| oversubscribed K=64 | t51 | 24.00 / 24.00 / 24.00 | 8.81 / 24.00 / 24.00 |
| oversubscribed K=512 | t0 | 23.92 / 24.00 / 23.92 | 6.86 / 24.00 / 22.01 |
| oversubscribed K=512 | t51 | 24.00 / 24.00 / 23.83 | 8.85 / 24.00 / 22.00 |
| in-memory K=1 | t0 | 8.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| in-memory K=1 | t51 | 0.25 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| in-memory K=512 | t0 | 7.64 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| in-memory K=512 | t51 | 7.94 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |

In pass 1 the DtoH column is smaller than the HtoD column because the GPU is still filling; passes 2 and 3 are the steady state. At the dense oversubscribed cells (K = 64, 512) every pass moves the whole 24 GiB array at both thresholds.

## Run integrity

- 42 rows; all `exit_code` 0 (every checksum confirmed); the read-back threshold equals the order's in every row; srcversion only `6284DA42…`; no stop file; no block skipped; pushed after every block (`ok`). 14 smoke runs are excluded.
- The extraction control passed (`e9/extraction_control.txt`: SQLite totals equal nsys's own `um_total_sum` for HtoD, DtoH and GPU faults; causes and passes sum to the totals).
- Every traced run logged one new kernel line, `NVRM: GPU0 refcntRequestReference_IMPL: Failed to enter state 1 (current state: 0, status: 0x00000056)`, which appeared only while traced runs were active.
  It is not in the stop pattern, no run failed, and its source (probably nsys's GPU-control path, by timing) is **not established**. E8's untraced runs did not produce it.
- The cap: the session was paused after Phase 3 and resumed; the 3.5 h cap counted working time (`e9/cap_anchor.txt`).

## Limitations

- **All counts are under tracing.** nsys may perturb the fault and migration pattern, not just the timing. E9 shows what migrates when traced, which is evidence about the mechanism and not a re-measurement of E6–E8's conditions.
- nsys groups GPU faults (a 1 GiB probe shows 77–82 GPU faults for 4,096 touched pages), so "GPU page faults" is nsys's number, not the driver's demand-fault count. Only relative comparisons within this table are meaningful.
- n = 3 per cell, descriptive only; ranges are narrow but three runs cannot bound variability. One page list per size. Stock module, one platform.
- Thrashing, throttling and remote-map events are **not observable** with this nsys version, so Y4's second arm and any claim about thrashing cannot be tested here; "migration without eviction" is excluded, "no thrashing" is not.
- Migration volumes above the array size (41–48 GiB per pass at oversubscribed K = 1, t0) mean some data migrates more than once per pass; the counts do not say why.
- The CPU-fault finding is an inference from counts (above) and has not been checked against the driver source.

## Existing claims flagged (not edited)

- **CS2-N10** (Prefetch threshold tuning): the current text in `CLAIM_SCOPE.md` carries **no "interpretation" or "unexplained" sentence**, because the C3-APPLY edits that would add them have not been applied (the brief was not available; see `e9/SESSION_STATUS.md`). When they are applied, E9 changes them as follows: the **interpretation** (E8's "consistent with whole regions being migrated for one or a few touched pages") is now **measured** (items 1 and 3), and the **unexplained** sentence (K = 1 at t51 still costing about 0.3 s per pass) is **explained** (item 2: about 1.2 GiB in and out per repeat pass).
- **`GATE_E8_REPORT.md`, Limitations:** the statement that the host's initial write of the array is "identical across thresholds" is contradicted by the CPU-fault counts (item 5). Not edited.
- **E6/E7 readings** that attribute the threshold effect to the GPU fault path alone: item 5 says part of it may arise on the host. Not edited.
- **CS2-N1 item 4** ("the same gain is available without speculation") is unaffected in sign, but the **mechanism** it rests on (CS2-N3, fewer demand faults) is now also seen directly as fewer GPU page faults at unchanged bytes (item 3).

The user decides these edits.
