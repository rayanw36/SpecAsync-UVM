# E7-T4 Amendment 1 (made before any timed run)

## Reason
During the smoke pass (idx 1-24 of 27 done, **no timed run had happened**, no sweep row exists) the instance was powered off and
started again at 17:59 UTC on 2026-10-08, killing the orchestrator; the session resumed after the original cap
(T0 + 5 h = 21:38:43 UTC) had passed. Cause of the poweroff as reported by the user (CloudTrail): **not supplied** (the field
in the resume brief was left as a placeholder); journal evidence only: clean `systemd-poweroff` at 17:59:51, not initiated by this session.
Preflight after the restart (2026-10-09 08:05 UTC): kernel 6.17.0-1017-aws, 18 nvidia-595 packages + 5 kernel-package holds, stock srcversion 6284DA42F15EDC3AB92332B,
threshold 51, `git diff ea1a262 HEAD -- driver/src` empty, MemAvailable 14.6 GiB, 83 GB free on the EBS root, dkms nvidia/595.91.07 built for 6.17.0-1017-aws.

## What changes
1. **New session start and cap.** New start 2026-10-09T08:05:10+00:00 (`phase0_start_2.txt`); cap = start + **4 h = 12:05:10 UTC**; reserve for T6/T7 25 min,
   so the latest sweep end is 11:40:10 UTC. The orchestrator computes and logs the deadlines at start and aborts if any is not later than now (unchanged logic).
   Skip rule unchanged in form (now + 30 x (max smoke wall + 4 s) <= latest sweep end), evaluated against the new deadlines.
2. **Orchestrator** (`e7t4_orchestrate.py`): two env/arg additions only, defaults unchanged: `--start-file F` and `T4_CAP_HOURS` (default 5; run with 4).
3. **Smoke rows 1-24 stand** (stock module, threshold read-back verified, 0 dmesg lines; they were run under the original registration). **Rows 25-27 (oversub t0 / t25 / t51) are run now**,
   by `e7t4_orchestrate.py smoke` (resumable by idx), after which the timeouts file is written (3 x median of each workload's 3 smoke walls, ceil s) and the sweep starts.
   Smoke rows remain excluded from analysis. The machine was rebooted between smoke rows 24 and 25; a fresh boot is recorded, not corrected for.

## What does not change
Families, tests, Holm structure, order file and seed (202610072, sha256 unchanged), timeouts rule, workload commands/sizes, expectations XA-XC,
verdict rule, falsification trigger, stop conditions (including "any departure from this pre-registration" and "active xrdp or desktop session during a timed run"), analysis code.
T6 additionally carries one descriptive line comparing this session's Stencil-24K stock-t51 median with the old T4 595.71.05 C0 value (4.185 s): not tested, cross-version observation only.
