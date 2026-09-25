# Gate E3b — Attended safety tests and the oracle-cost measurement

**The session completed with no stop condition.** This was the first load of
new kernel code since the E0.9a-2 crash. The module
`nvidia-uvm-specasync-NEW-e3a2-width-ftfast.ko` (srcversion
`33FD42E6E16B0A6658E2BEB`; renamed from `…-UNREVIEWED.ko` after Step 1)
ran **35 GPU workload runs**:
- 5 `group_probe` runs (Step 2 b–f);
- 6 Stencil smoke tests (Step 3), including W = 512 and the combined features;
- 24 Step 4 measurement runs.

The verified module separately ran the Step 2 reference run and 5 table-collection runs.

There were no stop-pattern dmesg lines, no timeouts, no memory drift, and
no non-zero `cas_giveup` or `spec_region_invalid`.

Platform: RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34-generic. Status
log: `E3B_STATUS.md`.

## Headline

1. **Safety.** Both features load, reject bad parameters, and run cleanly,
   including W = 512 (the worst case for mask fill and lock-hold) and the
   combined W = 64 + fast = 1 run. Both prediction-side identities hold
   **exactly** on every policy-6 run.
2. **The oracle's per-fault cost was its own lookup and lock** (Step 4).
   `specasync_ft_fast=1` removes **86.6% / 77.6% / 87.8%** of the per-fault
   prediction residual (Stencil C6 / Stencil C7 / GraphBFS C6):
   139.8 → 18.7, 162.9 → 35.0 and 167.0 → 20.1 ns per coalesced fault.
3. **A new bottleneck showed up.** With the cheap oracle, Stencil C6's
   queue-full drops rose by 51% (215k → 326k), and the under-lock (D5)
   saving shrank from 0.672 s to 0.515 s. A faster predictor overruns the
   worker queue.
4. **Caveat for E0.9b and E1.** Their conclusions were reached with an
   oracle that cost about 0.36 s (C6) and 0.041 s (C7) of servicing time
   per Stencil run, which a practical predictor would not. They must be
   re-tested at fast = 1 in the next pre-registered sweep.

## Step 0 — Push and preflight

- **Push:** level with origin (`42044a3`).
- **Preflight:** tree clean, tmux on a non-X pty, upgrade units inactive,
  kernel and driver as expected, `git diff ea1a262 HEAD -- driver/src`
  empty, dmesg clean for the extended pattern, MemAvailable 56.0 GB (desktop
  up), 40 GiB free.
- **Module files:**
  - verified: `5997D238EF080B77DBD2AAF`, sha256 `ab91372b…31be`;
  - new: `33FD42E6E16B0A6658E2BEB`, sha256 `dc6b226e…45df`.
- **Committed and pushed before any load** (`c6d9e81`): the scripts, the
  three order files, and the Step 4 expectation.
- Isolated to `multi-user.target`.

## Step 1 — insmod rejection: PASS

All 7 values were rejected: `specasync_spec_width` ∈ {0, 3, 1024, abc} and
`specasync_ft_fast` ∈ {2, −1, abc}.
- Each gave `insmod` rc 1 ("Invalid parameters"), the module's `pr_err`
  line, and the kernel's "invalid for parameter" line.
- No `nvidia_uvm` was left loaded.
- The verified module reloaded with srcversion `5997D238…` every time.

Table: `E3B_STATUS.md` Step 1 and `e3b/step1_reject.csv`.

**Harness defect found and fixed (recorded).** The first attempt stopped
after the first case, even though the module behaved correctly.
- The kernel log buffer had filled and begun rotating, so the line-count
  dmesg slice was empty.
- `tests/e3b_dmesg.py` now diffs by kernel timestamp, and all E3b scripts
  use it.
- The shared E0.9b `check_after` has the same weakness. When its prefix
  check fails it scans the last 200 lines, which is safe for stop detection
  but misreports new-line counts. Future harnesses should use the
  timestamp diff.
- Step 1 was rerun from its first case. That is a harness fix, not a
  result-driven rerun.

## Step 2 — `group_probe` (policy 6, depth 1, prefetch off, L = 4096)

| label | W | fast | ft_fast_verified | ft_fast_nranges | ft_fast_verify_ns | demand_faults | trace_pushes | ft_predictions | ft_held | ft_unknown_page | ft_exhausted | ft_skipped | ft_same_region | enqueued | drops | processed | spec_migrations | spec_pages_requested | spec_region_invalid | ft_fast_cas_giveup | fault_already_resident | dmesg_new_lines |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S2a verified |  |  |  |  |  | 8 | 8 | 7 | 0 | 0 | 1 | 1 |  | 7 | 0 | 7 | 0 |  |  |  | 0 | 0 |
| S2b new W1 f0 | 1 | 0 | 0 | 0 | 0 | 8 | 8 | 7 | 0 | 0 | 1 | 1 | 0 | 7 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| S2c new W1 f1 | 1 | 1 | 1 | 1 | 611 | 8 | 8 | 7 | 0 | 0 | 1 | 1 | 0 | 7 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| S2d new W16 f0 | 16 | 0 | 0 | 0 | 0 | 8 | 8 | 7 | 0 | 0 | 1 | 1 | 6 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| S2e new W64 f0 | 64 | 0 | 0 | 0 | 0 | 8 | 8 | 7 | 0 | 0 | 1 | 1 | 6 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| S2f new W512 f0 | 512 | 0 | 0 | 0 | 0 | 8 | 8 | 7 | 0 | 0 | 1 | 1 | 6 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |

| run | I1 left: trace_pushes | I1 right: pred+held+unk+exh+giveup | I1 diff | I2 left: ft_predictions | I2 right: same_region+enqueued+drops | I2 diff |
|---|---|---|---|---|---|---|
| S2a verified | 8 | 8 | 0 | 7 | 7 | 0 |
| S2b new W1 f0 | 8 | 8 | 0 | 7 | 7 | 0 |
| S2c new W1 f1 | 8 | 8 | 0 | 7 | 7 | 0 |
| S2d new W16 f0 | 8 | 8 | 0 | 7 | 7 | 0 |
| S2e new W64 f0 | 8 | 8 | 0 | 7 | 7 | 0 |
| S2f new W512 f0 | 8 | 8 | 0 | 7 | 7 | 0 |

- **(b) vs (a):** identical on every counter.
- **(c) vs (b):** identical on every policy-6 counter; verified 1, 1 range,
  611 ns.
- **Region history:** at W = 16/64/512 it skips 6 of 7 predictions (one
  region).
- **Both identities:** exact.

**Limitation:** `spec_migrations = spec_pages_requested = 0` in every run,
including the verified module. `group_probe` never reached
`make_resident`, so it **did not exercise the width path**, and the "≈ W ×
calls" checks held only trivially. The cause was not measured (the work
ring was not dumped).

## Step 3 — Stencil-24K smoke tests (L = 4096, trace_faults = 1)

| label | W | fast | ft_fast_verified | ft_fast_nranges | ft_fast_verify_ns | demand_faults | trace_pushes | ft_predictions | ft_held | ft_unknown_page | ft_exhausted | ft_skipped | ft_same_region | enqueued | drops | processed | spec_migrations | spec_pages_requested | spec_region_invalid | ft_fast_cas_giveup | fault_already_resident | dmesg_new_lines |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S3a C6 W1 f1 | 1 | 1 | 1 | 2 | 181689607 | 2978630 | 2978630 | 1124990 | 1842420 | 0 | 11220 | 10 | 0 | 819964 | 305026 | 819964 | 819184 | 819184 | 0 | 0 | 818858 | 0 |
| S3b C7 W1 f1 | 1 | 1 | 1 | 2 | 142791733 | 332195 | 332195 | 332195 | 0 | 0 | 0 | 792233 | 0 | 332195 | 0 | 332195 | 236393 | 236393 | 0 | 0 | 23080 | 0 |
| S3c C6 W16 f0 | 16 | 0 | 0 | 0 | 0 | 2986226 | 2986226 | 1124989 | 1850372 | 0 | 10865 | 11 | 103364 | 1021625 | 0 | 1021625 | 1021461 | 16343316 | 0 | 0 | 1124959 | 0 |
| S3d C6 W64 f0 | 64 | 0 | 0 | 0 | 0 | 2984251 | 2984251 | 1124988 | 1848390 | 0 | 10873 | 12 | 670632 | 454356 | 0 | 454356 | 454276 | 29073424 | 0 | 0 | 1124970 | 0 |
| S3e C6 W512 f0 | 512 | 0 | 0 | 0 | 0 | 2967734 | 2967734 | 1124988 | 1831352 | 0 | 11394 | 12 | 1122789 | 2199 | 0 | 2199 | 2199 | 1125512 | 0 | 0 | 1125000 | 0 |
| S3f C7 W64 f1 | 64 | 1 | 1 | 2 | 179608536 | 308886 | 308886 | 308886 | 0 | 0 | 0 | 815607 | 185398 | 123488 | 0 | 123488 | 91700 | 5868800 | 0 | 0 | 44232 | 0 |

| run | I1 left: trace_pushes | I1 right: pred+held+unk+exh+giveup | I1 diff | I2 left: ft_predictions | I2 right: same_region+enqueued+drops | I2 diff |
|---|---|---|---|---|---|---|
| S3a C6 W1 f1 | 2978630 | 2978630 | 0 | 1124990 | 1124990 | 0 |
| S3b C7 W1 f1 | 332195 | 332195 | 0 | 332195 | 332195 | 0 |
| S3c C6 W16 f0 | 2986226 | 2986226 | 0 | 1124989 | 1124989 | 0 |
| S3d C6 W64 f0 | 2984251 | 2984251 | 0 | 1124988 | 1124988 | 0 |
| S3e C6 W512 f0 | 2967734 | 2967734 | 0 | 1124988 | 1124988 | 0 |
| S3f C7 W64 f1 | 308886 | 308886 | 0 | 308886 | 308886 | 0 |

**Width checks** (`spec_pages_requested ÷ spec_migrations`):
- **1.00** at W = 1;
- **16.00** at W = 16, the **first multi-page `make_resident`** in this
  project (1,021,461 calls);
- **64.00** at W = 64;
- **511.83** at W = 512 (clipping at block ends);
- **64.00** in the combined run.

**W = 512 showed no stress:** 0 dmesg lines, wall-clock ≈ 17% of the
timeout, and the longest batch 0.31 ms against 0.27–0.29 ms in (a)–(d).

Both identities are exact on all 6 runs. Rings were 100% covered. fast = 1
loads were verified, with a check of 143–182 ms in-kernel.

## Step 4 — Did the oracle's cost come from the lookup and lock?

Expectation, design and full results: `E3B_ORACLE_COST.md`. The expectation
was committed verbatim before the first Step 4 run.

| arm | n | outside-lock svc−D3−D4 (s) | pre-lock segment t1−t0−D3 (s) | enqueue_overhead (s) | per prediction (ns) | D5 (s) | ft_predictions | enqueued | drops | coalesced faults (I1) | demand faults |
|---|---|---|---|---|---|---|---|---|---|---|---|
| graphbfs C1 | 2 | 0.0034 | 0.0018 | 0.0000 | nan | 0.7635 | 0 | 0 | 0 | 0 | 492910 |
| graphbfs C6f0 | 2 | 0.0932 | 0.0911 | 0.0096 | 116 | 0.6549 | 83258 | 83258 | 0 | 479548 | 479548 |
| graphbfs C6f1 | 2 | 0.0223 | 0.0202 | 0.0091 | 114 | 0.6657 | 79468 | 78998 | 470 | 485896 | 485896 |
| stencil C0 | 3 | 0.0014 | 0.0010 | 0.0000 | nan | 0.1061 | 0 | 0 | 0 | 0 | 346056 |
| stencil C1 | 3 | 0.0140 | 0.0090 | 0.0000 | nan | 1.6008 | 0 | 0 | 0 | 0 | 2926519 |
| stencil C6f0 | 3 | 0.4914 | 0.4854 | 0.0599 | 53 | 0.9289 | 1124999 | 909862 | 215117 | 2985620 | 2985620 |
| stencil C6f1 | 3 | 0.1231 | 0.1173 | 0.0532 | 47 | 1.0855 | 1124999 | 799072 | 325927 | 2981925 | 2981925 |
| stencil C7f0 | 3 | 0.0796 | 0.0790 | 0.0249 | 76 | 0.1406 | 327438 | 327438 | 0 | 327438 | 327438 |
| stencil C7f1 | 3 | 0.0379 | 0.0373 | 0.0245 | 72 | 0.1302 | 341659 | 341659 | 0 | 341659 | 341659 |

| workload | pair | increase outside-lock (s) | Δ enqueue (s) | **residual** (s) | residual per coalesced fault (ns) | residual per demand fault (ns) | D5 change vs baseline (s) |
|---|---|---|---|---|---|---|---|
| stencil | C6f0 − C1 | +0.4775 | +0.0599 | **+0.4175** | 139.8 | 139.8 | -0.6718 |
| stencil | C6f1 − C1 | +0.1091 | +0.0532 | **+0.0559** | 18.7 | 18.7 | -0.5153 |
| stencil | C7f0 − C0 | +0.0782 | +0.0249 | **+0.0534** | 162.9 | 162.9 | +0.0345 |
| stencil | C7f1 − C0 | +0.0365 | +0.0245 | **+0.0120** | 35.0 | 35.0 | +0.0241 |
| graphbfs | C6f0 − C1 | +0.0897 | +0.0096 | **+0.0801** | 167.0 | 167.0 | -0.1085 |
| graphbfs | C6f1 − C1 | +0.0188 | +0.0091 | **+0.0097** | 20.1 | 20.1 | -0.0978 |

| workload | pair | residual fast 0 (s) | residual fast 1 (s) | **fraction of residual removed** |
|---|---|---|---|---|
| stencil | C6 | +0.4175 | +0.0559 | **86.6%** |
| stencil | C7 | +0.0534 | +0.0120 | **77.6%** |
| graphbfs | C6 | +0.0801 | +0.0097 | **87.8%** |
**Verdict: lookup was the cost.** 77.6–87.8% of the per-fault residual is
removed at fast = 1. The remaining 12–22% (19–35 ns per fault) is **not
attributed**; the source candidates are listed in `E3B_ORACLE_COST.md`.

**D5 changed** on Stencil C6. The under-lock saving went from −0.672 to
−0.515 s, while queue-full drops went from 215,117 to 325,927 (§ D5 in
`E3B_ORACLE_COST.md`). This is reported as measured.

## Existing results and claims this bears on (flagged, not edited)

- **E0.9b and E1** (C6/C7 lose to C0; the Stencil C6-L4096 5.65% saving vs
  C1):
  - Obtained with an oracle whose lookup and lock cost 140–167 ns per
    fault on the servicing thread.
  - These conclusions **carry an expensive-oracle caveat** until re-tested
    at `specasync_ft_fast=1`.
  - The direction of the bias makes speculation look *worse*, so E1's
    "cannot beat C0" is not yet shown to survive a cheap oracle.
- **E1b** ("the per-fault prediction work dominates the handoff"):
  - Confirmed, and now attributed: that work was mostly the oracle's lookup
    and lock.
  - The paper's structural claim, that speculation's handoff is on the
    critical path, still holds.
  - With a cheap oracle, the remaining handoff cost at Stencil C6 is about
    +0.109 s pre-lock, of which +0.053 s is enqueue.
- **Claim 10** (rate mismatch): with a cheap oracle, queue-full drops rise.
  The worker's drain rate, not the predictor, becomes the limit on Stencil
  prefetch-off.
- **CLAIM_SCOPE.md is not edited.**

## Close

See `E3B_STATUS.md` for the push result and the restore.
