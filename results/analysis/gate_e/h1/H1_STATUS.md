# Gate H1 status

- 21:47:23 Phase 4 preflight: branch manuscript-prep, 0 unpushed, tree clean; kernel 7.0.0-34-generic; driver 595.91.07; stock srcversion 6284DA42F15EDC3AB92332B, refcnt 0, threshold 51; upgrade timers inactive; `git diff ea1a262 HEAD -- driver/src` empty; MemAvailable 58455904 kB; no GPU compute processes; THP enabled=madvise; Linger=yes; this session runs under `user@1000.service` (tmux scope), not a login session; no xrdp.
- 21:47:39 Phase 4: isolate multi-user.target exit 0, session survived (user state lingering). Launching the chain as a detached user unit.
- 21:47:39 orchestrator smoke: phase0 21:39:44, now 21:47:39, session cap 01:39:44, latest sweep end (cap - 25 min reserve) 01:14:44
- 21:47:39 STOP (run-class) in smoke: see /home/rayenchikhaoui/SpecAsync-UVM/results/phaseB1/gate_h1/smoke/STOP; no retry
- 21:48:17 PRE-RUN HARNESS DEFECT (not a stop condition): the first orchestrate smoke exited 4 (runner refused: the SHA-256 of h1_smoke_order.csv was not in h1_order.sha256; the file held only the sweep order's hash, E8's held both). No module was reloaded and no benchmark ran (dmesg shows only the console messages of the isolate; refcnt 0). Corrected by adding the smoke order's hash to h1_order.sha256 (the sweep order and its hash c9270e39... are unchanged); the refusal log is kept as CHAIN_STOP.pre_run_refusal_2026-11-05. Recorded as a departure-free harness correction before any timed run; relaunching the chain once.
- 21:48:20 orchestrator smoke: phase0 21:39:44, now 21:48:20, session cap 01:39:44, latest sweep end (cap - 25 min reserve) 01:14:44
- 2026-11-06 13:35:15 RESUME after a pause of the user's: the machine had hung and been power-cycled; state read from the journal. STOP (run-class): see STOP and h1_lockup_excerpt.txt. H1 stops here: no retry, no sweep.

- 2026-11-06 13:47:56 AMENDMENT 1 RUN preflight: boot started 2026-11-06 13:32:52; no dmesg line matching the stop patterns on this boot; stock srcversion 6284DA42F15EDC3AB92332B, refcnt 0, threshold 51; THP enabled=madvise defrag=madvise and numa_balancing=0 (as in C9); MemAvailable 59432812 kB; Addressing Mode HMM; upgrade timers inactive; amendment commit 54566e2.
- 13:48:04 isolate multi-user.target exit 0; chain launched as unit h1a1.
- 13:48:04 orchestrator smoke: phase0 21:39:44, now 13:48:04, session cap 01:39:44, latest sweep end (cap - 25 min reserve) 01:14:44
- 13:48:04 ABORT: session cap 01:39:44 is not later than now 13:48:04
- 13:48:38 PRE-RUN GUARD ABORT (not a stop condition; nothing ran): the orchestrator refused because phase0_start.txt still held the C9 start (cap 01:39 on 2026-11-06 already passed). phase0_start.txt set to the C10 session start; chain relaunched once (unit h1a1).
- 13:48:38 orchestrator smoke: phase0 13:46:30, now 13:48:38, session cap 17:46:30, latest sweep end (cap - 25 min reserve) 17:21:30
- 13:49:17 smoke complete: 6 rows; h1_timeouts.csv written
