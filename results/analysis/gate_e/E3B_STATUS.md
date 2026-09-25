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
