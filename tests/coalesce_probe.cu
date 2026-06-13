// coalesce_probe.cu — Gate B oracle test under COALESCED faults (sm_75).
//
// Unlike hit_probe.cu (one synced fault per batch), this launches a single
// kernel whose threads each touch a distinct 4 KB page, so the GPU emits a
// burst of faults that UVM coalesces into multi-fault service batches — exactly
// the regime where the old per-batch oracle cursor desynchronises from the
// per-fault demand stream. This is the probe that separates the buggy oracle
// (cursor advances 1/batch -> predictions fall behind -> ~0 hits) from the
// fixed one (cursor advances by faults-consumed/batch -> stays in sync).
//
// Build: nvcc -arch=sm_75 -o coalesce_probe coalesce_probe.cu
// Usage: ./coalesce_probe [num_pages]   (default 4096)

#include <cstdio>
#include <cstdlib>
#include <cuda_runtime.h>
#define PAGE 4096ULL

__global__ void touch_pages(volatile char *p, unsigned long long n) {
    unsigned long long i = (unsigned long long)blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) p[i * PAGE] = (char)(i & 0xff);   // each thread faults a distinct page
}

static void ck(cudaError_t e, const char *w) {
    if (e != cudaSuccess) { fprintf(stderr, "CUDA %s: %s\n", w, cudaGetErrorString(e)); exit(1); }
}

int main(int argc, char **argv) {
    unsigned long long n = (argc > 1) ? strtoull(argv[1], 0, 0) : 4096ULL;
    size_t bytes = (size_t)(n + 1) * PAGE;
    char *buf = nullptr;
    ck(cudaMallocManaged(&buf, bytes), "malloc");
    for (size_t i = 0; i < bytes; i += PAGE) buf[i] = 0;     // resident on CPU
    ck(cudaMemPrefetchAsync(buf, bytes, cudaCpuDeviceId, 0), "prefetch");
    ck(cudaDeviceSynchronize(), "sync0");

    printf("coalesce_probe: %llu pages in one burst kernel\n", n);
    int threads = 256, blocks = (int)((n + threads - 1) / threads);
    touch_pages<<<blocks, threads>>>(buf, n);                // burst -> coalesced batches
    ck(cudaGetLastError(), "launch");
    ck(cudaDeviceSynchronize(), "sync1");
    printf("coalesce_probe: done\n");
    cudaFree(buf);
    return 0;
}
