// hit_probe.cu — SpecAsync-UVM Gate A deterministic positive control (sm_75).
//
// Purpose: make the speculation hit counter fire ON PURPOSE so we can tell
// whether near-zero hit rates on real benchmarks are a real prediction finding
// or an instrumentation artifact.
//
// Method: allocate one managed buffer, then touch a fixed sequence of 4 KB
// pages with a full device sync between every touch, so faults are SERIALIZED
// (one demand fault per service batch). Under specasync_policy=adjacent, the
// service batch for page N predicts page N+1 and the async worker tags it; the
// next touch of page N+1 should be credited as a hit.
//
// The ascending stride-1 (4 KB) pattern is exactly what the adjacent predictor
// expects, so a correctly-accounted pipeline should show a HIGH hit rate.
// To make the control independent of the UVM prefetcher, run with the module
// reloaded with uvm_perf_prefetch_enable=0 (see run_hit_probe.sh --no-prefetch
// note); with prefetch on, expect hits to taper once the prefetcher engages.
//
// Build: nvcc -arch=sm_75 -o hit_probe hit_probe.cu
// Usage: ./hit_probe [num_pages] [stride_pages]
//          num_pages    : how many distinct pages to touch   (default 256)
//          stride_pages : gap between touched pages, in 4 KB  (default 1 = adjacent)

#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cuda_runtime.h>

#define PAGE 4096ULL

__global__ void touch_one(volatile char *p, unsigned long long off) {
    p[off] = (char)(off & 0xff);   // write fault, dirties the page
}

static void ck(cudaError_t e, const char *what) {
    if (e != cudaSuccess) {
        fprintf(stderr, "CUDA error at %s: %s\n", what, cudaGetErrorString(e));
        exit(1);
    }
}

int main(int argc, char **argv) {
    unsigned long long num_pages = (argc > 1) ? strtoull(argv[1], 0, 0) : 256ULL;
    unsigned long long stride    = (argc > 2) ? strtoull(argv[2], 0, 0) : 1ULL;

    size_t bytes = (size_t)(num_pages * stride + 1) * PAGE;

    char *buf = nullptr;
    ck(cudaMallocManaged(&buf, bytes), "cudaMallocManaged");

    // Establish a clean baseline: force the whole buffer resident on the CPU
    // first (host writes), so every subsequent GPU touch is a genuine
    // host->device demand fault in ascending page order.
    for (size_t i = 0; i < bytes; i += PAGE) buf[i] = 0;
    ck(cudaMemPrefetchAsync(buf, bytes, cudaCpuDeviceId, 0), "prefetch->cpu");
    ck(cudaDeviceSynchronize(), "sync prefetch");

    printf("hit_probe: num_pages=%llu stride_pages=%llu buffer=%.1f MiB\n",
           num_pages, stride, bytes / (1024.0 * 1024.0));

    // Serialized ascending touches, full sync between each so each page is its
    // own service batch.
    for (unsigned long long n = 0; n < num_pages; ++n) {
        unsigned long long off = n * stride * PAGE;
        touch_one<<<1, 1>>>(buf, off);
        ck(cudaGetLastError(), "launch");
        ck(cudaDeviceSynchronize(), "sync touch");
    }

    printf("hit_probe: done, touched %llu pages\n", num_pages);
    cudaFree(buf);
    return 0;
}
