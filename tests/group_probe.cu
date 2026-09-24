// group_probe.cu — Gate E0.5: forces real va-block dispatch-group collapsing,
// unlike coalesce_probe.cu (which does not — see GATE_E0_5_REPORT.md, the
// "coalesce_probe.cu allocation pattern" section, for the measured proof:
// its faults cycle round-robin through 8 distinct 2MB-aligned VA blocks
// rather than clustering inside one, so every fault gets its own dispatch
// group and the recording/consumption mismatch this probe exists to expose
// never gets exercised).
//
// Design: over-allocate 2 blocks (4 MB) and compute the first 2MB-aligned
// address inside that allocation. Touch N distinct 4 KB pages starting at
// that aligned base, all guaranteed to fall inside the SAME UVM va_block
// (va_blocks are always 2MB-aligned regardless of allocation boundaries).
// One kernel launch, one burst of faults, all addressed within one block ->
// service_fault_batch_ats_sub (uvm_gpu_replayable_faults.c) should merge
// them into one dispatch group per top-level batch, so k (coalesced faults
// / dispatch groups) -> N by construction, not by luck.
//
// Run with the stock UVM prefetcher OFF (uvm_perf_prefetch_enable=0 at
// insmod) -- otherwise the prefetcher may migrate multiple pages per batch
// ahead of the threads that would otherwise fault them individually, which
// would suppress the very fault stream this probe needs to produce. This
// probe does not set that parameter itself; the wrapper script must.
//
// Keep N small (8 or 16 to start) -- this probe isolates *alignment*, not
// dispatch latency. Confirm k from telemetry (trace-entry count vs.
// specasync_demand_faults / specasync_batch_record's num_faults sum) rather
// than assuming N == k; report both.
//
// Build: nvcc -arch=sm_75 -o group_probe group_probe.cu
// Usage: ./group_probe [N]   (default 8)

#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cuda_runtime.h>
#define PAGE      4096ULL
#define BLOCK_2MB (2ULL * 1024 * 1024)

__global__ void touch_pages_in_block(volatile char *base, unsigned long long n) {
    unsigned long long i = (unsigned long long)blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) base[i * PAGE] = (char)(i & 0xff);   // each thread faults one page, same block
}

static void ck(cudaError_t e, const char *w) {
    if (e != cudaSuccess) { fprintf(stderr, "CUDA %s: %s\n", w, cudaGetErrorString(e)); exit(1); }
}

int main(int argc, char **argv) {
    unsigned long long n = (argc > 1) ? strtoull(argv[1], 0, 0) : 8ULL;
    if (n * PAGE > BLOCK_2MB) {
        fprintf(stderr, "N too large: %llu pages (%llu B) exceeds one 2MB block\n",
                n, n * PAGE);
        return 1;
    }

    // Over-allocate 2 blocks so a 2MB-aligned window is guaranteed to exist
    // inside the allocation regardless of the allocator's own base address.
    size_t bytes = 2 * BLOCK_2MB;
    char *raw = nullptr;
    ck(cudaMallocManaged(&raw, bytes), "malloc");

    uintptr_t raw_addr    = (uintptr_t)raw;
    uintptr_t aligned_addr = (raw_addr + (BLOCK_2MB - 1)) & ~(BLOCK_2MB - 1);
    char *base = (char *)aligned_addr;

    printf("group_probe: raw=%p aligned_base=%p offset_into_alloc=%lu\n",
           (void *)raw, (void *)base, (unsigned long)(aligned_addr - raw_addr));
    printf("group_probe: touching %llu pages, all inside [%p, %p) — one 2MB block\n",
           n, (void *)base, (void *)(base + n * PAGE));

    // Make the whole allocation CPU-resident first, then explicitly hand it
    // back to the CPU, so the GPU kernel below must fault every page in.
    for (size_t i = 0; i < bytes; i += PAGE) raw[i] = 0;
    struct cudaMemLocation cpu_loc;
    cpu_loc.type = cudaMemLocationTypeHost;
    cpu_loc.id   = 0;
    ck(cudaMemPrefetchAsync(raw, bytes, cpu_loc, 0, 0), "prefetch");
    ck(cudaDeviceSynchronize(), "sync0");

    int threads = 256, blocks = (int)((n + threads - 1) / threads);
    touch_pages_in_block<<<blocks, threads>>>((volatile char *)base, n);
    ck(cudaGetLastError(), "launch");
    ck(cudaDeviceSynchronize(), "sync1");
    printf("group_probe: done\n");

    cudaFree(raw);
    return 0;
}
