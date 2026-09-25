# Gate E3b — status (attended)

## Step 0 — Push and preflight
- Start 2026-09-25T23:57+03:00.
- Push while the desktop was up: "Everything up-to-date", exit 0. Level with origin (`42044a3`).
- Tracked tree clean (untracked `tests/group_probe`). tmux `%0` on `/dev/pts/0`, `DISPLAY` unset. Upgrade units inactive. Kernel 7.0.0-34-generic, driver 595.91.07. `git diff ea1a262 HEAD -- driver/src` empty. dmesg clean for the extended pattern (including soft lockup, hung_task and RCU stall). MemAvailable 56,041,652 kB; 40 GiB free.
- Module files:
  - verified `nvidia-uvm-specasync-NEW-e0.9a2-fixed.ko`: srcversion `5997D238EF080B77DBD2AAF`, sha256 `ab91372bbbcd2faaa8654191ab85f68b9aae55af04229601e0763094e1d831be` (loaded, refcnt 0);
  - new `nvidia-uvm-specasync-NEW-e3a2-width-ftfast-UNREVIEWED.ko`: srcversion `33FD42E6E16B0A6658E2BEB`, sha256 `dc6b226ea329913e201b5cd4472cc42a504344783601fadc5921700b342345df`.
- Scripts and orders, committed before any load: `tests/e3b_insmod_reject.py`, `tests/e3b_collect_probe_table.py`, `tests/e3b_runner.py`, `e3b/step{2,3,4}_order.csv` (Step 4 seed 202609263). The Step 4 expectation is committed verbatim in `E3B_ORACLE_COST.md`.
- Identity measurement: "coalesced faults on the policy-6 path" = `specasync_trace_pushes`. It increments once per coalesced fault with a va_space, in the same enumeration as the Gate 1 loop, and only when `specasync_trace_faults=1`. So Steps 2–3 run with trace_faults=1; Step 4, which measures timing, runs with 0.
- Outcome: **PASS**.
- Isolated to multi-user.target at 2026-09-26 00:0x (exit 0; the same informational daemon-reload warning). gdm and graphical.target inactive. MemAvailable 60,283,532 kB.

## Step 1 — insmod rejection
- **First attempt: harness defect, not a module failure.** Case `specasync_spec_width=0`: `insmod` failed ("Invalid parameters", rc 1) and no `nvidia_uvm` was left loaded, both as expected. My script then reported "pr_err line not found" and stopped conservatively. dmesg shows both lines were emitted:
  `[40147.834325] specasync: specasync_spec_width=0 rejected: must be a power of two in [1, 512]`
  `` [40147.834341] nvidia_uvm: `0' invalid for parameter `specasync_spec_width' ``
- Cause: the kernel log buffer is **full and rotating** (the oldest line is now at 0.27 s), so the line-count slice `after[len(before):]` was empty. The shared E0.9b `check_after` has the same weakness: when its prefix check fails it scans the last 200 lines. That is still safe for stop-pattern detection but misreports `dmesg_new_lines`.
- Fix: `tests/e3b_dmesg.py`, a **timestamp-based** diff (lines with a timestamp later than the last pre-snapshot line), used by the reject script and patched into the E3b runner as `check_after`. No listed stop condition had fired.
- The verified module was reloaded (C0 config; srcversion `5997D238EF080B77DBD2AAF`, refcnt 0). Step 1 was rerun from its first case with the fixed harness. This is a harness fix, not a result-driven rerun: the first case's module outcome already matched the expectation.
- **Rerun: all 7 rejected as expected** (`e3b/step1_reject.csv`):

| parameter | value | insmod | module's pr_err | kernel line | left loaded | verified reload |
|---|---|---|---|---|---|---|
| specasync_spec_width | 0 | rc 1, "Invalid parameters" | `specasync_spec_width=0 rejected: must be a power of two in [1, 512]` | `` `0' invalid for parameter `` | no | 5997D238… ✓ |
| specasync_spec_width | 3 | rc 1 | `=3 rejected: must be a power of two in [1, 512]` | ✓ | no | ✓ |
| specasync_spec_width | 1024 | rc 1 | `=1024 rejected: must be a power of two in [1, 512]` | ✓ | no | ✓ |
| specasync_spec_width | abc | rc 1 | `='abc' rejected: not an integer` | ✓ | no | ✓ |
| specasync_ft_fast | 2 | rc 1 | `=2 rejected: must be 0 or 1` | ✓ | no | ✓ |
| specasync_ft_fast | -1 | rc 1 | `=-1 rejected: must be 0 or 1` | ✓ | no | ✓ |
| specasync_ft_fast | abc | rc 1 | `='abc' rejected: not an integer` | ✓ | no | ✓ |

- No stop-pattern dmesg line. **Step 1 PASS.**
- **Rename (recorded):** `driver/build/595.91.07/nvidia-uvm-specasync-NEW-e3a2-width-ftfast-UNREVIEWED.ko` → `nvidia-uvm-specasync-NEW-e3a2-width-ftfast.ko` (mv; the file is unchanged: srcversion 33FD42E6E16B0A6658E2BEB, sha256 dc6b226e…).

## Step 2 — group_probe (policy 6, depth 1, prefetch off, L=4096, trace_faults=1; 8 coalesced faults, one 2 MB block)
- Table: 8 distinct pages (trace 8 entries, 0 overwrites). 6/6 runs, **no stop condition**, 0 new dmesg lines, MemAvailable ≈ 60.0 GB throughout.

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
- **(c) vs (b):** identical on every policy-6 counter. At fast = 1, `ft_fast_verified = 1`, `nranges = 1` (8 contiguous pages), verify 611 ns, `cas_giveup = 0`.
- **fast = 0 loads:** `verified = 0` and `nranges = 0`, as designed.
- **Both identities hold exactly** (difference 0) on all 6 runs.
- **W > 1:** `ft_same_region = 6` and `enqueued = 1` at W = 16/64/512. All 7 predictions fall in one region, so the history skips 6. `spec_region_invalid = 0`.
- **Limitation, stated plainly:** `spec_migrations = 0` in **every** run, including the verified module (a), and `spec_pages_requested = 0`, which counts every `make_resident` call.
  - So the worker **never called `make_resident`** in `group_probe`.
  - The (b) check "spec_pages_requested = number of make_resident calls" and the (d)–(f) checks "≈ W × calls" hold only **trivially** (0 = W × 0).
  - **`group_probe` did not exercise the widened migration path at all.**
  - Why is not measured: the work ring was not dumped in Step 2. Source suggests the worker's block `trylock` fails while the demand path services the same 8 faults in one batch, giving THROTTLED; no counter separates that.
  - **Step 3 is therefore the first run in which a multi-page region reaches `make_resident`.**

## Step 3 — Stencil-24K smoke tests (policy 6, depth 1, L=4096, trace_faults=1, rings dumped)
- Fresh prefetch-off tables: stencil 1,125,000 (trace 2,942,674, 0 overwrites); graphbfs 287,956 (trace 485,300, 0 overwrites). Assertions PASS.
- 6/6 runs in order a→f, with (e) run alone and inspected before (f). **No stop condition**, 0 new dmesg lines in every run, MemAvailable 59.9–60.3 GB, rings 100% covered (4,417–73,299 records).

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

| run | pages requested ÷ spec_migrations | wall (s; timeout 22) | stress indicators (servicing window / D5 / longest batch) |
|---|---|---|---|
| a C6 W1 f1 | 1.00 | 4.01 | 1.869 s / 1.075 s / 0.27 ms |
| b C7 W1 f1 | 1.00 | 1.23 | 0.254 s / 0.130 s / 0.29 ms |
| c C6 W16 f0 | **16.00** | 3.80 | 1.754 s / 0.501 s / 0.28 ms |
| d C6 W64 f0 | **64.00** | 3.77 | 1.697 s / 0.497 s / 0.28 ms |
| e C6 W512 f0 | **511.83** (clipping at block ends) | 3.78 | 1.589 s / 0.495 s / 0.31 ms (p99 0.05 ms) |
| f C7 W64 f1 (both features) | **64.00** | 1.17 | — |

(Wall-clock and servicing times were read only as stress indicators, as the brief requires for (e). No arm comparisons are made in this step.)

- **(c) is the first multi-page `make_resident`** in this project: 1,021,461 calls at 16 pages each. (d) makes 454,276 calls at 64 pages; (e) makes 2,199 calls at 512 pages.
- **W = 512 showed no stress:** no dmesg output, wall-clock ≈ 17% of the timeout, and the longest batch 0.31 ms against 0.27–0.29 ms in (a)–(d).
- **Both identities hold exactly** (difference 0) on all 6 runs.
- `spec_region_invalid = 0` and `cas_giveup = 0` on all runs. `ft_same_region > 0` on every W > 1 run (103,364 / 670,632 / 1,122,789 / 185,398).
- **fast = 1 loads:** `verified = 1`, `nranges = 2`, and a load-time check of **143–182 ms** in-kernel (54 ms in userspace).
- **Step 3 PASS.**
