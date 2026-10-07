# Gate E8 status log

Phase 0 start: 2026-10-07 16:07:58 +03 (`e8/phase0_start.txt`). Session cap 3.5 h = 19:37:58.

## Open for review
(DOC-class items are appended here.)

- Timestamps: log lines whose time I typed by hand (not printed by `date` or a script) were estimates; I corrected the E8 ones to the real clock. Some hand-typed times in `e7/E7_STATUS.md` (for example "14:20 Phase 3" and "14:05 Phase 2 DONE") are likewise estimates and run later than the real times (Phase 2 finished about 14:00 and the Phase 3 push was at 14:04:37 by `date`). Not edited; the git commit times are authoritative. From here on, times in this log come from `date` or the orchestrator.

## Log
- 16:08 Phase 0: HEAD 5be5965, clean tree (untracked tests/group_probe); 0 unpushed (the 37 E7 commits had already been pushed by the user); git credential.helper is now `store`, remote HTTPS. Kernel 7.0.0-34; driver 595.91.07; srcversions stock 6284DA42.., verified 5997D238.., e3a2 33FD42E6..; timers inactive; MemAvailable 57.5 GB; 38 GB free; driver/src identical to ea1a262; GPU memory 16303 MiB. **Lingering is enabled** (Linger=yes, set in E7). System currently in graphical.target (restored at user request); isolate happens in Phase 4.
- 16:10 Phase 1: `benchmarks/bench_sparse.cu` written, built with `/usr/local/cuda/bin/nvcc -O3 -arch=sm_120` (nvcc 13.0.88). Validation (`tests/e8_validate_bench.py`, 64 MiB and 1 GiB; timings dropped, not recorded) **OVERALL PASS**: (a) checksum equals host reference for K in {1,8,64,512}; (b) pages_touched = K x blocks; (c) same seed -> same hash, different seed -> different; (d) K=512 touches every page once (distinct = total = touched); (e) an off-by-one reference is detected (rc 1, MISMATCH). Log: `e8/bench_validation.log`. Fix during development: the two helper functions needed `__host__ __device__` (compile error, fixed before any validation run).

### Code review: every CUDA call in bench_sparse.cu

| call | allocates / migrates | error check |
|---|---|---|
| `cudaMallocManaged(&arr, bytes)` | the ONE managed array (8 GiB or the oversubscribed size); pages start unpopulated, then CPU-resident when the host writes every word | `CUDA_CHECK` (exit 2) |
| `cudaMalloc(&d_idx, n*8)` | page-list index array in device memory, NOT managed: never faults | `CUDA_CHECK` |
| `cudaMalloc(&d_acc, 8)` | 64-bit checksum accumulator, device memory, not managed | `CUDA_CHECK` |
| `cudaMemcpy(d_idx <- host list, H2D)` | explicit copy of the index list to device memory (no managed memory involved) | `CUDA_CHECK` |
| `cudaMemset(d_acc, 0, 8)` | zeroes the accumulator | `CUDA_CHECK` |
| host loop `arr[i] = init_word(i)` | not a CUDA call: host stores to every word, so every page is CPU-resident before the first kernel | n/a (plain stores) |
| `cudaEventCreate` x2 | timing events | `CUDA_CHECK` |
| `cudaEventRecord(e0)`, `sparse_pass<<<>>>`, `cudaGetLastError()`, `cudaEventRecord(e1)`, `cudaEventSynchronize(e1)`, `cudaEventElapsedTime` | the kernel faults on managed pages (migrations are done by UVM, not requested); one launch per pass, synchronised per pass | each wrapped in `CUDA_CHECK`; launch checked by `cudaGetLastError` |
| `cudaMemcpy(&got <- d_acc, D2H)` | 8-byte checksum read-back from device memory; does NOT touch the managed array | `CUDA_CHECK` |
| `cudaEventDestroy` x2, `cudaFree(d_acc)`, `cudaFree(d_idx)`, `cudaFree(arr)` | releases | `CUDA_CHECK` |

Not called anywhere: `cudaMemAdvise`, `cudaMemPrefetchAsync`, `cudaDeviceSynchronize` (events synchronise instead), any host read of `arr` after the kernels.
- 16:09 Phase 1 committed and pushed.
- 16:11 Phase 2: GPU total memory 16303 MiB = 15.92 GiB; 1.5x = 23.88 GiB -> oversubscribed size **24 GiB**. In-memory size 8 GiB, passes 3, seed 202610081. Empirical memory check (one oversubscribed run, K=1, 1 pass, timing not recorded, checksum OK): minimum MemAvailable during the run 30.4 GiB (> 12 GiB). No reduction needed.
- DOC-CLASS decision (Phase 3 runner): e7_runner.py cannot be used unchanged: E8 needs the benchmark's stdout (per-pass kernel time, checksum line) and ring dumps for Family M, and e7_runner discards stdout. Per the brief's fallback, `tests/e8_runner.py` is a copy of e7_runner.py; changes listed in its docstring (cell table/paths, stdout capture, ring dumps for dump_rings=1 rows, dropped-cell filter, per-label timeouts).
- 16:13:49 Phase 3: tests/e8_cells.py, e8_make_order.py (seed 202610082: 260 order rows, 28 smoke rows), e8_runner.py (copy of e7_runner, changes listed in its docstring), e8_orchestrate.py (stale-deadline abort test: ABORT, exit 5), e8_analyze.py. Positive control PASS (-9.57%, p 1.08e-05); selftest PASS (scratch only). E8_PREREGISTRATION.md written.
- 16:14:05 Phase 4: pushed (305202c). Lingering still enabled (Linger=yes). isolate multi-user.target exit 0, session survived. Platform: 7.0.0-34, 595.91.07, stock 6284DA42 loaded refcnt 0, timers inactive, driver/src identical to ea1a262.
- 16:14:07 orchestrator smoke: phase0 16:07:58, now 16:14:07, session cap 19:37:58, latest sweep end (cap - 25 min reserve) 19:12:58
- 16:16:40 smoke complete: 28 rows, dropped cells: 0; e8_timeouts.csv written
- 16:16:45 push after smoke: ok
- 16:16:57 Phase 4 DONE: 28 smoke runs (24 stock + 4 mechanism), all exit 0, thresholds read back, dmesg clean, no cell dropped (smoke max 10 s); timeouts 8-50 s (e8_timeouts.csv); smoke excluded from analysis; pushed. Phase 5 starts.
- 16:16:57 orchestrator sweep: phase0 16:07:58, now 16:16:57, session cap 19:37:58, latest sweep end (cap - 25 min reserve) 19:12:58
- 16:22:51 Family IN: idx 1-120: runner exit 0 (354 s)
- 16:22:57 push after Family IN: ok
- 16:22:57 Family OV group ov_k1: est 316 s, starting
- 16:26:50 Family OV ov_k1: idx 121-150: runner exit 0 (232 s)
- 16:26:56 push after Family OV ov_k1: ok
- 16:26:56 Family OV group ov_k512: est 347 s, starting
- 16:31:20 Family OV ov_k512: idx 151-180: runner exit 0 (264 s)
- 16:31:26 push after Family OV ov_k512: ok
- 16:31:26 Family OV group ov_k8: est 380 s, starting
- 16:36:25 Family OV ov_k8: idx 181-210: runner exit 0 (300 s)
- 16:36:32 push after Family OV ov_k8: ok
- 16:36:32 Family OV group ov_k64: est 337 s, starting
- 16:40:46 Family OV ov_k64: idx 211-240: runner exit 0 (254 s)
- 16:40:51 push after Family OV ov_k64: ok
- 16:41:53 Family M: idx 241-260: runner exit 0 (61 s)
- 16:41:58 push after Family M: ok
- 16:41:58 SWEEP COMPLETE; skipped OV groups: none
- 16:42:13 Phase 5 DONE: 260 rows (IN 120, OV 120, M 20), no OV group or Family M skipped, no stop, pushed after every family/group. Phase 6 starts.
- 16:43:29 Phase 6: analysis run; verdict GENERALITY FALSIFIED (largest slowdown ov K=1 t0 +84.96%); benchmark not suspect; XS1-3 held, XS4-5 failed. Two runs (idx 102, 223) counted one new kernel line each (drm_fb_helper / hrtimer notices; not in the stop pattern).
