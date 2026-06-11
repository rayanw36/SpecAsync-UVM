# Gate 2 — Benchmark Calibration

**Date:** 2026-06-11
**Status:** PASS

## Platform notes (T4 vs RTX 5070 Ti)

The original Phase 1 baseline used an RTX 5070 Ti (Ada Lovelace, sm_89,
PCIe 5.0). Phase B uses a Tesla T4 (Turing, sm_75, PCIe 3.0).

Expected changes:
- T4 peak bandwidth ~320 GB/s vs 5070 Ti ~960 GB/s → lower compute BW
- T4 PCIe 3.0 x16 = 16 GB/s vs PCIe 5.0 x16 = 64 GB/s → higher UVM migration cost
- UVM fault latency expected to be **higher** on T4 (more headroom for speculation)

## Benchmark compilation

All compiled with `-arch=sm_75` (was `sm_89` in original).

## SGEMM calibration (p0, baseline)

| N | Mean (ms) | Std (ms) | CV |
|---|-----------|----------|----|
| 8192 | ~3600 | — | — |
| 16384 | ~3900 | — | — |
| 24000 | 6867 | 17 | 0.25% |

Note: SGEMM is compute-bound. Variation is low.

## Stencil calibration (p0, baseline)

| N | Mean (ms) | Std (ms) |
|---|-----------|----------|
| 8192 | ~600 | — |
| 16384 | ~1500 | — |
| 24000 | ~1514 | — |

## STREAM calibration (p0, baseline)

| N (elements) | Mean (ms) | Bandwidth (GB/s) |
|--------------|-----------|-----------------|
| 67M | — | ~4.3 |
| 134M | ~377 | 4.26 |
| 268M | — | — |
| 537M | — | — |

## cuFFT calibration (p0, baseline)

| N (elements) | Mean (ms) |
|--------------|-----------|
| 64M | ~115 |
| 128M | ~230 |
| 256M | ~462 |

## GraphBFS calibration (p0, baseline)

| log₂(N) | Notes |
|---------|-------|
| 22 | 4M vertices, ~40M edges |
| 23 | 8M vertices, ~80M edges |
| 24 | 16M vertices, ~160M edges |

Note: log₂=25 (32M vertices) requires 4.3 GB host malloc for edge buffer and
caused OOM. log₂=24 is the largest feasible size on this instance.

## Stencil_OvSub calibration (p0, baseline, with balloon)

Balloon = 11264 MiB pinned via `cudaMalloc` leaves ~5 GB usable VRAM.

| N | iters | balloon_mib | Managed (GB) | Oversub ratio | Mean (ms) |
|---|-------|------------|--------------|---------------|-----------|
| 25000 | 20 | 11264 | 5.0 | ~1.0× (fill) | ~38700 |
| 28300 | 20 | 11264 | 6.4 | ~1.28× | — |
| 32000 | 20 | 11264 | 8.2 | ~1.64× | — |

Note: N=25000 with 38.7s per run is expected — the first iteration
triggers full migration of 5 GB from CPU to GPU over PCIe 3.0.
