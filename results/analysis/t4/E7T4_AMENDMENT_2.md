# E7-T4 Amendment 2 (made before any timed run)

## Reason
The pre-registered oversubscribed Stencil (`bench_stencil_oversub 48000 1`, 2 x N^2 x 4 B = **17.17 GiB** managed) cannot run on this g4dn.xlarge
(15.4 GiB RAM, no swap): the UVM CPU-side page population exhausts host RAM and the kernel OOM-killed it at smoke row 25
(2026-10-09 08:05:52 UTC; `block_populate_pages_cpu`, file-rss 15.1 GB). The pre-registration checked the VRAM ratio (1.144 vs 1.078) but not host RAM.
**No timed data exists**: the smoke CSV has the 24 rows of the other workloads, the sweep CSV does not exist, no timeouts file was written.
Cause of the 2026-10-08 17:59 UTC poweroff: **not checked** (the field in the brief was left as a placeholder; journal shows a clean systemd-poweroff, not initiated by this session).
Preflight at 2026-10-09T11:41:11+00:00: kernel 6.17.0-1017-aws, 18 nvidia-595 holds + 5 kernel holds, stock srcversion 6284DA42F15EDC3AB92332B, threshold 51,
`git diff ea1a262 HEAD -- driver/src` empty, MemAvailable 13.6 GiB, 82 GB free on EBS.

## Changes
1. **Oversubscribed Stencil is removed from Family B.** Family B = 7 workloads (Stencil-8K, Sweep-4K, Sweep-16K, STREAM, SGEMM, cuFFT, GraphBFS-23), tests t0 and t25 vs t51 each,
   **one Holm family of 14**. The oversub rows (order idx 241-270, the last 30; smoke idx 25-27) are simply not run: the order file, its sha256, seed 202610072 and the order of all remaining rows are unchanged
   (the sweep covers idx 1-240; the analyzer expects 240 rows). Smoke is therefore complete at 24 rows (the 24 already run under Amendment 1 stand); the timeouts file is computed from them.
2. **XB without the oversubscribed workload:** "Sweep-16K, STREAM and SGEMM are faster at t0 than at t51, direction only" (held iff all three medians are lower at t0).
3. **New stop condition:** before each run (after the module insmod, before the benchmark), the benchmark's managed allocation must be below MemAvailable - 4 GiB; otherwise stop.
   Managed bytes from the benchmark sources: Stencil-24K 4.29 GiB, Stencil-8K 0.48, Sweep-4K 0.12, Sweep-16K 1.91, STREAM 3.00, SGEMM 6.44, cuFFT 1.00, GraphBFS-23 1.22 GiB (upper bound V x 156 B)
   (`MANAGED_BYTES` in `e7t4_runner.py`; tested: passes at 13 GiB available, stops at 9 GiB for SGEMM).
4. **Cap:** session start 2026-10-09T11:41:11+00:00, cap = start + 4 h = **15:41:11 UTC**, latest sweep end (cap - 25 min reserve) **15:16:11 UTC** (`phase0_start_3.txt`, `T4_CAP_HOURS=4`); the orchestrator logs the computed deadlines and aborts if any is not later than now.
5. **Orchestration:** the whole remainder (smoke, timeouts file, sweep) runs as ONE detached chain under `systemd-run --user --unit=e7t4-sweep`, logging to `e7t4_chain.log`, halting on the first failure.

## Not changed
Family A, tests, Holm structure, the remaining order, seed, timeouts rule, workload commands/sizes, XA, XC, verdict and falsification trigger, stop conditions (including "any departure from this pre-registration"
and "active xrdp or desktop session during a timed run"), statistical code.

## Deferred
Oversubscription on the T4 (VRAM ratio ~1.1) is deferred to a separate gate on a host with enough RAM.
