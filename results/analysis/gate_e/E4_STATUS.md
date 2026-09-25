# Gate E4 — status

## Step 0 — Push and preflight
- Start 2026-09-26T00:20+03:00. Push while the desktop was up: `c6d9e81..4050287`, exit 0; level with origin.
- HEAD `4050287`; tracked clean (untracked `tests/group_probe`). tmux `%0` on `/dev/pts/0`, `DISPLAY` unset. Upgrade units inactive. Kernel 7.0.0-34-generic; driver 595.91.07. `git diff ea1a262 HEAD -- driver/src` empty. dmesg clean for the extended pattern. MemAvailable 57,754,152 kB; 39 GiB free.
- Module files:
  - verified `…-e0.9a2-fixed.ko`: srcversion `5997D238EF080B77DBD2AAF`, sha256 `ab91372bbbcd2faaa8654191ab85f68b9aae55af04229601e0763094e1d831be` (loaded, refcnt 0);
  - new `…-e3a2-width-ftfast.ko`: srcversion `33FD42E6E16B0A6658E2BEB`, sha256 `dc6b226ea329913e201b5cd4472cc42a504344783601fadc5921700b342345df`.
- Harness: `tests/e4_runner.py` is `e3b_runner.py` unchanged (timestamp dmesg diff, extended stop pattern, read-back, cas_giveup / region_invalid stops) plus the E4 stop `ft_fast_verified != 1` on fast = 1 loads.
- **Identity 1 with `trace_faults=0`:** its left side is `demand_faults`. That equalled `trace_pushes` exactly in **12/12** E3b runs where both exist (Step 2 and Step 3), and Identity 1's right side equalled `demand_faults` in every E3b Step 4 speculation run.
- Outcome: **PASS**.
