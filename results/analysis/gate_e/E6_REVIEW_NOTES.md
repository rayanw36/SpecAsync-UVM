# Gate E6 — Review notes (Gate C2-APPLY, 2026-10-07)

Notes added after review. `GATE_E6_REPORT.md` is **not** edited; this file sits beside it.

## 1. X3 was badly specified and is unscorable

X3 ("V-A versus V-B is genuinely uncertain, about even") was committed by the reviewer without a
direction. Neither verdict contradicts "about even", so any held/failed mark would need a criterion
invented after the fact. The report left it **not scored**; that was correct, and the defect is in the
expectation, not in the analysis. Future expectations carry a direction and a threshold (E7 does).

## 2. Why C7W512-t51 differs across sessions while C0-t51 does not

Per-arm Stencil-24K medians, prefetch on, threshold 51, E3a-2 module (srcversion `33FD42E6…`), computed
from the committed run CSVs (n = 10 per cell; wall-clock in seconds):

| gate | C0-t51 median (min–max) | C7W512-t51 median (min–max) | C7 − C0 | session window (UTC) |
|---|---|---|---:|---|
| E4 (`e4_runs.csv`; arms `stencil C0`, `stencil C7-W512`) | 1.1295 (1.1077–1.1443) | 1.0738 (1.0604–1.0937) | −4.93% | 2026-09-25 21:29 → 09-26 07:22 (spans a reboot) |
| E5 (`e5_runs.csv`) | 1.1265 (1.1192–1.2357) | 1.0673 (1.0364–1.0978) | −5.26% | 2026-09-26 07:58–08:01 |
| E6 (`e6_runs.csv`) | 1.1298 (1.1200–1.1490) | 1.0918 (1.0528–1.1238) | −3.36% | 2026-10-05 16:39–16:42 |

- **C0-t51 is stable:** 1.1295, 1.1265, 1.1298 s (range 0.3%).
- **C7W512-t51 moves:** 1.0738 → 1.0673 → 1.0918 s (range 2.3%), and its interquartile range is
  consistently wider than C0's (0.026 / 0.025 / 0.039 s vs 0.010 / 0.019 / 0.016 s).
- Descriptive only, from one E6 split: first five C7W512-t51 runs median 1.0925 s, last five 1.0680 s
  (C0-t51: 1.1276, 1.1329). n = 5 per half; not a test.
- **So the −3.36% versus −5.26% gap comes from the speculation arm, not from the baseline.** This is
  not explained by E6. E7 Family C (block 1 vs block 2 of both arms, same module, same session) tests
  session drift directly. The magnitude should be reported as a range across sessions (CS2-N1 item 3).
- Limit of this table: the run CSVs hold `policy, depth, prefetch, L, W, fast, trace_faults, srcversion`
  per run but **no stored threshold or `log_enabled` column**; the runner's read-back was a stop check
  and was not saved (see `e7/E7_PARAM_CHECK.md`).

## 3. The four `drm_fb_helper` notices

Runs idx 20 (C0-t51), 22 (C7W512-t10), 79 (C7W512-t51) and 97 (GraphBFS C0-t0) each logged one new
kernel line, matched by uptime offset to `workqueue: drm_fb_helper_damage_work hogged CPU for >10000us N
times, consider switching to WQ_UNBOUND` (counts 4, 5, 7 and 11; the first two appear at uptime 7936 s
and 7941 s, the others later in the same boot). It is a notice about another kernel thread (the DRM framebuffer damage worker), not about the benchmark
or the UVM module. It is not in the stop pattern and nothing stopped. Whether it affected timing is **not
established**: all four runs lie inside their own cell's Tukey fences (wall-clock ranks 8, 7, 7 and 4 of 10;
fences computed from the cell's 10 runs), so there is no sign of an effect, and no run was removed.
