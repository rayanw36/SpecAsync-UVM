# Gate E8 status log

Phase 0 start: 2026-10-07 16:07:58 +03 (`e8/phase0_start.txt`). Session cap 3.5 h = 19:37:58.

## Open for review
(DOC-class items are appended here.)

## Log
- 16:08 Phase 0: HEAD 5be5965, clean tree (untracked tests/group_probe); 0 unpushed (the 37 E7 commits had already been pushed by the user); git credential.helper is now `store`, remote HTTPS. Kernel 7.0.0-34; driver 595.91.07; srcversions stock 6284DA42.., verified 5997D238.., e3a2 33FD42E6..; timers inactive; MemAvailable 57.5 GB; 38 GB free; driver/src identical to ea1a262; GPU memory 16303 MiB. **Lingering is enabled** (Linger=yes, set in E7). System currently in graphical.target (restored at user request); isolate happens in Phase 4.
- 16:25 Phase 1: `benchmarks/bench_sparse.cu` written, built with `/usr/local/cuda/bin/nvcc -O3 -arch=sm_120` (nvcc 13.0.88). Validation (`tests/e8_validate_bench.py`, 64 MiB and 1 GiB; timings dropped, not recorded) **OVERALL PASS**: (a) checksum equals host reference for K in {1,8,64,512}; (b) pages_touched = K x blocks; (c) same seed -> same hash, different seed -> different; (d) K=512 touches every page once (distinct = total = touched); (e) an off-by-one reference is detected (rc 1, MISMATCH). Log: `e8/bench_validation.log`. Fix during development: the two helper functions needed `__host__ __device__` (compile error, fixed before any validation run).

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
