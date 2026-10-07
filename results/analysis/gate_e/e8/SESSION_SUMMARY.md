# Session summary: Gate E8 (adversarial sparse-access test)

Phase 0 start 2026-10-07 16:07:58 +03; session cap 19:37:58. Everything finished by about 16:50. Hard stop after Phase 7.

## Phases

| phase | status |
|---|---|
| 0 preflight | done; clean; lingering confirmed enabled; 0 unpushed (the user had pushed the E7 commits); git credential helper is now `store` |
| 1 `benchmarks/bench_sparse.cu` | done; validation (a)-(e) **PASS** at 64 MiB and 1 GiB (timings dropped); CUDA-call review table in `E8_STATUS.md`; pushed (`c7fb05c`) |
| 2 sizes | done: in-memory 8 GiB; oversubscribed **24 GiB** (1.5 x 15.92 GiB); 3 passes; seed 202610081; minimum MemAvailable 30.4 GiB (> 12 GiB), no reduction |
| 3 pre-registration + scripts | done; pushed before any timed run (`305202c`); positive control PASS (-9.57%, p 1.08e-05); self-tests PASS (scratch only) |
| 4 isolate + smoke | done: 28 smoke runs, no cell dropped, timeouts 8-50 s |
| 5 sweep | done: **260 of 260 rows** (IN 120, OV 120, M 20); no OV group or Family M skipped; no stop; pushed after every family/group |
| 6 analysis + report | done: `gate_e/GATE_E8_REPORT.md`, figure `e8_sparse_threshold.{png,pdf}`; pushed |
| 7 this file | done |

## E8 result

**GENERALITY FALSIFIED.** Six K < 512 cells show a Holm-significant slowdown at t0 or t25; the largest is **oversubscribed K = 1, t0: +84.96%**
(9.35 s vs 5.05 s); also oversubscribed K = 8 at t25 (+46.71%) and t0 (+41.15%). In memory the slowdowns are small (K = 1 t0 +3.95%). K = 64 and 512 are
5.6-9.7% *faster* at lower thresholds in both sizes, as in E6/E7. Benchmark **not suspect** (in-memory K = 512 t0: -7.54%).
Expectations: **XS1, XS2, XS3 held; XS4 and XS5 failed.** Mechanism (interpretation): on an oversubscribed array every pass re-pays migration at
t0 (about 1.8 s per pass at K = 1 vs 0.3 s at t51); Family M (n = 5, in-memory) shows fewer but 3.7x larger migrations per fault at K = 1.

## DOC-class items left open (all in `e8/E8_STATUS.md`)

1. `tests/e7_runner.py` could not be used unchanged (E8 needs benchmark stdout and ring dumps), so `tests/e8_runner.py` is a copy with the changes listed in its docstring.
2. Hand-typed times in the E8 status log were first estimates and were corrected to the real clock; some hand-typed times in `e7/E7_STATUS.md` are likewise estimates (the git commit times are authoritative). Not edited.
3. The crossover K on the oversubscribed array (between 8 and 64) was not located; only 1.5x oversubscription was tested.
4. Existing claims flagged for review, not edited: CS2-N10 (generality sentence), CS2-N1 item 4, the E7 "no workload slower" statement, the OPEN_DECISIONS D1 note ("tuned C0" needs a definition).
5. Carried over: X3 unscorable (E6), D6 option (a) regeneration, PATH_AUDIT fixes not applied, E0/E0.8 platform not recorded.

## Unresolved evidence ids

None added this gate (no CLAIM_SCOPE edits, no new evidence ids; the E8 results are not yet in `c1_evidence.py`; extend it before citing E8 in a claim).

## Push state

All commits pushed (the push after Phase 6 returned `5bf3f31..14e7598`); 0 unpushed at the time of writing before this file's own commit.

## End state

- Stock module loaded: srcversion `6284DA42F15EDC3AB92332B`, refcnt 0, `uvm_perf_prefetch_threshold` 51, no specasync parameters.
- Runtime target `multi-user.target` (as E6/E7); boot default still `graphical.target`.
- **Lingering is still enabled** (from E7). Undo with `sudo loginctl disable-linger rayenchikhaoui`, which stops the user manager and ends this tmux session.
- `tests/group_probe` (untracked) left as found; the benchmark binary `benchmarks/bench_sparse` is gitignored (build line in the `.cu` header).

## Stop

HARD STOP after Phase 7. No further runs.
