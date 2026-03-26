#include <cuda_runtime.h>
#include <stdio.h>
#include <sys/time.h>

#define SCALAR 3.0f

__global__ void stream_triad(float *a, float *b, float *c, size_t n) {
    size_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n) {
        a[idx] = b[idx] + SCALAR * c[idx];
    }
}

int main(int argc, char* argv[]) {
    size_t N = (argc > 1) ? atoll(argv[1]) : 1024*1024*256; // Default 1GB total
    size_t size = N * sizeof(float);
    float *a, *b, *c;

    printf("[STREAM] Size: %zu elements (~%.2f GB total)\n", N, (double)size*3/1e9);

    cudaMallocManaged(&a, size);
    cudaMallocManaged(&b, size);
    cudaMallocManaged(&c, size);

    // CPU Init (Force pages to Host)
    for (size_t i = 0; i < N; i++) {
        b[i] = 1.0f;
        c[i] = 2.0f;
    }

    // Timing
    cudaEvent_t start, stop;
    cudaEventCreate(&start); cudaEventCreate(&stop);

    printf("Launching Kernel...\n");
    cudaEventRecord(start);
    stream_triad<<<(N+255)/256, 256>>>(a, b, c, N);
    cudaEventRecord(stop);
    
    cudaDeviceSynchronize();
    
    float ms = 0;
    cudaEventElapsedTime(&ms, start, stop);
    printf("[RESULT] Time: %.2f ms | Bandwidth: %.2f GB/s\n", ms, (size*3/1e9)/(ms/1000));

    cudaFree(a); cudaFree(b); cudaFree(c);
    return 0;
}
