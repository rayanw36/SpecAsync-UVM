# Gate H1 - Report: threshold trade-off on HMM-managed (malloc'd) memory

## Verdict: NOT RUN. The gate stopped in its smoke pass on a kernel oops in the stock driver's HMM path

No timed H1 run exists and the analysis was not run (the sweep never started; there is no `h1_runs.csv`). The pre-registered stop condition (E8's list: new `dmesg` lines matching `BUG`, `Oops`, `exited with irqs disabled`, `soft lockup`; any of the four) fired on the **first oversubscribed malloc-mode cell**.

## What happened (evidence: `h1/STOP`, `h1/h1_lockup_excerpt.txt`, `h1/H1_STATUS.md`)
- Smoke idx 1-6 (the three in-memory cells, both thresholds) completed with exit code 0 and no stop (smoke rows are excluded from analysis by the pre-registration; no number from them is reported).
- Smoke idx 7, **`ov_k1 stock-t0`** (bench_sparse 24 GiB, K = 1, `--alloc malloc`, stock `nvidia_uvm` 6284DA42, threshold 0): 21:49:23 `BUG: kernel NULL pointer dereference` in `free_chunk+0x4d/0xd0 [nvidia_uvm]`, from the kernel thread "vidmem lazy free" (`process_lazy_free`), which then "exited with irqs disabled". From 21:49:48 the UVM GPU fault bottom half spun on a spin lock for 1527 s (soft lockup, CPU 2; trace `uvm_pmm_gpu_unpin_allocated` <- `sync_page_and_chunk_state` <- `uvm_hmm_va_block_service_locked` <- `uvm_va_block_service_locked` <- `service_fault_batch_block_locked`, the HMM GPU-fault path). The machine did not recover and was power-cycled; the chain died with the boot.
- No retry and no further run, per the pre-registered stop rule. End state: stock module, threshold 51, `graphical.target`.

## Interpretation (stated as far as the evidence goes)
- This is a defect in the **stock 595.91.07 driver's HMM eviction/free path under oversubscription** (device-private page chunks freed while another path holds or has dropped the pinned state). It was triggered by an unmodified module, an unmodified kernel and a plain `malloc` array: no specasync code was loaded. The oops precedes the lock-up, so the lock-up is probably the consequence (the lazy-free thread died holding a lock the fault handler needs); that causal order is read from the timestamps, not proven.
- It means the sparse **oversubscribed HMM** cells of H1 cannot be run on this platform without risking a host hang. The in-memory cells ran without incident in the smoke pass, so a reduced gate (in-memory cells only) may be possible, but that is a change of the pre-registration and was not made.
- Consequently **CS2-N10 is not tested on HMM** and nothing in it is flagged as contradicted; the claim stays scoped to managed (`cudaMallocManaged`) memory, which Section III and CS2-N10 already state.

## Limitations
One occurrence. Not reproduced (retrying is forbidden by the stop rule). The trigger cell is the oversubscribed K = 1 at threshold 0; whether other oversubscribed HMM cells (or threshold 51) trigger it is unknown.
