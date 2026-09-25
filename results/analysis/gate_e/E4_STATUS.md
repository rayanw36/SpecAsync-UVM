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
- 00:21 isolated to multi-user.target (exit 0; gdm and graphical.target inactive).

## Step 1 — Smoke tests (never-run combinations; policy 6, depth 1, L = 4096, fast = 1, trace_faults = 0)
- Fresh prefetch-off tables (smoke_tables): stencil 1,125,000 (trace 2,948,284, 0 overwrites); graphbfs 287,956 (trace 483,367, 0 overwrites). PASS.
- 7/7 runs, **no stop condition**: 0 new dmesg lines; every fast load had verified = 1 (2 / 19 ranges); MemAvailable ≥ 59.7 GB; rings 100% covered (305–73,230 records).

| run | W | I1 left (demand_faults) | I1 right | I1 diff | I2 left | I2 right | I2 diff | pages/migration | spec_region_invalid | cas_giveup | verified | nranges | fault_already_resident |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SMOKE stencil pf0 W64 f1 | 64 | 3012311 | 3012311 | 0 | 1124999 | 1124999 | 0 | 64.00 | 0 | 0 | 1 | 2 | 1124974 |
| SMOKE stencil pf0 W512 f1 | 512 | 2980210 | 2980210 | 0 | 1124977 | 1124977 | 0 | 511.83 | 0 | 0 | 1 | 2 | 1124488 |
| SMOKE stencil pf1 W512 f1 | 512 | 200918 | 200918 | 0 | 200918 | 200918 | 0 | 511.76 | 0 | 0 | 1 | 2 | 21278 |
| SMOKE graphbfs pf0 W64 f1 | 64 | 479724 | 479724 | 0 | 84405 | 84405 | 0 | 64.00 | 0 | 0 | 1 | 19 | 181371 |
| SMOKE graphbfs pf0 W512 f1 | 512 | 475959 | 475959 | 0 | 79256 | 79256 | 0 | 511.86 | 0 | 0 | 1 | 19 | 226123 |
| SMOKE graphbfs pf1 W64 f1 | 64 | 38129 | 38129 | 0 | 5424 | 5424 | 0 | 64.00 | 0 | 0 | 1 | 19 | 1952 |
| SMOKE graphbfs pf1 W512 f1 | 512 | 28303 | 28303 | 0 | 4168 | 4168 | 0 | 511.62 | 0 | 0 | 1 | 19 | 2751 |

nonzero identity differences: 0
- Every combination runs clean. Both identities are exact, and pages per migration match W (64.00; 511.6–511.9 at W = 512, clipped at block ends).
- Disclosure: my check script printed the smoke wall-clock values to confirm the timeout margin (every run is far below 22 s / 168 s). They stay in `e4/smoke_runs.csv`, are **excluded from all analysis**, and no arm comparison was made.
- **Step 1 PASS.**
