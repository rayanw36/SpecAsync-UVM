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
