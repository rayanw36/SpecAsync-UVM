/*
 * gate2_depth1_probe.cu — Gate 2 depth-1 validation probe.
 *
 * Allocates a 4 MB managed buffer (2 × 2MB VA blocks).  Touches all 1024
 * pages sequentially so the demand path crosses the block boundary at page 512.
 *
 * With adjacent policy (predict page + 4KB):
 *  - Pages 0–510: predicted page is in the SAME block → trylock contends
 *  - Page 511: predicted page 512 is in block 1 ← block 0 held by demand path
 *    but block 1 is FREE → worker should trylock block 1, migrate page 512,
 *    insert hit-table entry before the demand fault on page 512 arrives.
 *
 * Expected depth=1, adjacent, prefetch off:
 *   - page 511 worker: MIGRATION_DONE (block-crossing hit)
 *   - Page 512 demand fault: spec_hit = 1 (if worker finished before demand)
 *   - hit-batch (page 512) should be faster than same-block miss batches
 *
 * Build: nvcc -arch=sm_75 -o gate2_depth1_probe gate2_depth1_probe.cu
 */
#include <stdio.h>
#include <stdlib.h>
#include <cuda_runtime.h>

#define BLOCK_BYTES  (2ULL * 1024 * 1024)  /* 2 MB = one UVM VA block */
#define PAGE_BYTES   4096
#define NUM_BLOCKS_M 2
#define TOTAL_PAGES  ((int)(NUM_BLOCKS_M * BLOCK_BYTES / PAGE_BYTES))  /* 1024 */

__global__ void touch_page(volatile unsigned char *buf, size_t byte_off)
{
    volatile unsigned char s = buf[byte_off];
    (void)s;
}

int main(void)
{
    size_t total = NUM_BLOCKS_M * BLOCK_BYTES;
    unsigned char *buf;
    cudaError_t err;

    err = cudaMallocManaged(&buf, total);
    if (err != cudaSuccess) {
        fprintf(stderr, "cudaMallocManaged failed: %s\n", cudaGetErrorString(err));
        return 1;
    }
    cudaMemAdvise(buf, total, cudaMemAdviseSetPreferredLocation, cudaCpuDeviceId);
    cudaMemPrefetchAsync(buf, total, cudaCpuDeviceId, 0);
    cudaDeviceSynchronize();

    printf("gate2_depth1_probe: %d pages, %d UVM blocks, seq access\n",
           TOTAL_PAGES, NUM_BLOCKS_M);
    printf("  VA=%p  block boundary at page %d (offset %zu B)\n",
           buf, (int)(BLOCK_BYTES / PAGE_BYTES), BLOCK_BYTES);

    for (int p = 0; p < TOTAL_PAGES; p++) {
        size_t off = (size_t)p * PAGE_BYTES;
        touch_page<<<1, 1>>>(buf, off);
        cudaDeviceSynchronize();
        if (p == 510 || p == 511 || p == 512 || p == 513)
            printf("  page %d done (offset %zu KB, block %d)\n",
                   p, off >> 10, (int)(off / BLOCK_BYTES));
    }

    printf("gate2_depth1_probe: done (%d faults total)\n", TOTAL_PAGES);
    cudaFree(buf);
    return 0;
}
