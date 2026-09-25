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
