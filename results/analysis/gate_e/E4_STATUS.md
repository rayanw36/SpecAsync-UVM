# Gate E4 — status

**COMPLETE (2026-09-26) — ⚠️ FALSIFICATION TRIGGER FIRED:** on Stencil-24K, C7-W512 (cheap oracle, whole-block width, prefetch on) beats C0 by 4.93% (p = 1.08e-5, Holm-sig, 3.9× MDE). GraphBFS shows no F1 difference. Nothing further was run.
- 200/200 runs, no stop condition. There was one user-initiated shutdown during run 63, and the sweep resumed per the rule after table validation.
- Commits after `8fdf3ba`'s push are unpushed (headless); run `git push`.

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

## Step 2 — Pre-registration
- `E4_PREREGISTRATION.md` committed before any sweep run. It fixes 10 arms × 2 workloads × n = 10 = 200 runs; the order (seed 202609264, sha256 6f42b480…); 18 comparisons in one Holm family (F1 6, F2 4, F3 6, F4 2); the F1 falsification trigger; mechanism metrics; identities; limitations; and the stop conditions verbatim.
- `tests/e4_analyze.py` was committed with it. It refuses fewer than 200 rows, and was smoke-tested on synthetic data in the scratchpad only.
- Commit `aed1f7f` (local; headless).

## Step 3 — Sweep
- Tables: stencil 1,125,000 (trace 2,947,275, 0 overwrites); graphbfs 287,956 (trace 482,045, 0 overwrites). Assertions PASS.
- Sweep launched 2026-09-26T00:28:01+0300.
- Before the first sweep run: `tests/e4_runner.py` gained `--commit-every N` (it runs the unchanged E3b loop in N-row chunks using the existing `--through`; E3b commits the CSV at each chunk end). This implements the pre-registered "commit every 10 runs"; run behaviour is unchanged.
- Sweep launched 2026-09-26T00:3x+03:00. Runs 1–62 completed, with no stop condition and chunk commits at 10…60 (`6c0b652` covers through run 60). Rows 61–62 are in the CSV and committed below.

### Interruption (not a stop condition) — evidence
- Run 62 completed at 00:47:53. **Run 63** (`graphbfs C7-W512`) loaded, verified and started at 00:47:53. The journal shows the module load (`ft_fast: range index verified: 287956 pages, 19 ranges … check 56089293 ns`; `init OK … spec_width=512 ft_fast=1(active=1)`) and the `specasync_clear` write at 00:47:53.
- At 00:48:26 the user logged in on **tty1**. At 00:48:38 they ran `sudo shutdown not` (typo), and at 00:48:41 `sudo /usr/sbin/shutdown now`. logind: "The system will power off now!" The shutdown was orderly (`systemd-poweroff.service`), and the machine was powered back on at 09:35:50.
- **No crash.** In the previous boot's kernel log from 00:00 to the power-off there is no BUG / Oops / WARNING / GPF / NULL pointer / irqs-disabled / soft lockup / hung_task / RCU stall line, and no NVRM or Xid line.
- Run 63 read no counters before the shutdown, 48 s after it started (timeout 168 s; the same configuration took 31.6 s in the Step 1 smoke test). The journal cannot tell whether the benchmark was still executing or the runner had already been terminated when the previous Claude Code session ended. **Not determined.**
- Run 63 has **no CSV row**. Per the pre-registration ("after any interruption that is not a stop condition, the run resumes at the next index not in the CSV; … never restarted, no cell ever re-run"), the sweep resumes at idx 63. That run produced no result, so this is not a re-run of a completed cell.

### Resume after reboot (2026-09-26 09:40)
- Post-reboot preflight **PASS**:
  - kernel 7.0.0-34-generic, driver 595.91.07, tmux `%0` on `/dev/pts/0` (`DISPLAY` unset), upgrade units inactive;
  - both module files unchanged (srcversion and sha256);
  - `git diff ea1a262 HEAD -- driver/src` empty, dmesg clean for the extended pattern;
  - MemAvailable 60.5 GB, 39 GiB free;
  - the stock DKMS `nvidia_uvm` (`6284DA42…`) was loaded after boot, refcnt 0.
- The push before isolating succeeded (`ca19a68`, level with origin). Isolated to multi-user.target again.
- **Table-validity check.** The tables hold absolute VAs, and no earlier gate used tables across a reboot. A check trace was collected into a *separate* directory (`postreboot_check/`, verified module, the same procedure) and compared with the committed sweep tables:

| workload | same page set | max first-touch rank displacement, post-reboot vs sweep tables | the same, two **pre-reboot** collections (smoke_tables vs sweep tables) |
|---|---|---|---|
| Stencil-24K | **yes** (1,125,000; same first page 0x7ffd3e017000) | 98 | 96 |
| GraphBFS-23 | **yes** (287,956; same first page 0x7ffff0000000) | 35,823 | 37,992 |

  The address layout under `setarch -R` is identical across the reboot, and the order drift is within the same-session run-to-run range. **The sweep continues with the committed tables, unchanged.** The check trace is not sweep data and is not used.
- Resumed at idx 63 per the pre-registered resume rule.
- Sweep complete: 200/200 rows, idx 1–200 in sequence, last run 2026-09-26T07:25:11Z, no stop condition, final commit `be9778e`.

## Step 4 — Analysis (as pre-registered)
- `tests/e4_analyze.py` run unchanged from `aed1f7f`. Integrity is clean: 200/200 runs in order, one srcversion, 0 dmesg lines, 100% ring coverage, both identities 160/160, fast verified 120/120, giveup/invalid 0.
- **FALSIFICATION TRIGGER FIRED:** Stencil C7-W512 vs C0 is −0.0557 s (−4.93%), p = 1.08e-5 (complete separation), Holm-sig, 3.9× MDE. GraphBFS F1 shows no difference. **Per the pre-registration, nothing further is run.**
- F2: the slow oracle costs 0.222 s of wall-clock (Stencil C6, Holm-sig); C7 0.025 s n.s.
- F3: width with prefetch off gives −9.7 / −21.6 / −23.3% (Stencil).
- F4: C6-W512 staged 99.95% of pages, yet demand faults stay 2.96M; wall-clock ratio to C0 is 2.92 (Stencil) and 1.04 (GraphBFS).
- Exploratory: the result is not a boot artifact (it holds within each boot).

## Step 5 — Report and close
- `GATE_E4_REPORT.md` has the trigger at the top, unsoftened.
- Report commit `af6255f`. The single push attempt **failed** (exit 128, headless). Recorded, not worked around.
- No stop condition occurred (the trigger is a result, not a stop condition), so the system was restored. The **verified** module was reloaded with speculation off and prefetch on (policy 0, depth 0, prefetch 1, log 0; srcversion 5997D238EF080B77DBD2AAF; no E3a-2 parameters present). graphical.target and gdm active; `nvidia-smi` works; dmesg clean.
- **STOP. This was the last experimental gate before the paper.**
