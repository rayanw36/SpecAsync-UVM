#include <cuda_runtime.h>
#include <stdio.h>

#define RADIUS 1

__global__ void stencil_2d(float *in, float *out, int N) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    int idx = y * N + x;

    if (x >= RADIUS && x < N - RADIUS && y >= RADIUS && y < N - RADIUS) {
        float val = in[idx];
        val += in[idx - 1]; // Left
        val += in[idx + 1]; // Right
        val += in[idx - N]; // Top
        val += in[idx + N]; // Bottom
        out[idx] = val * 0.2f;
    }
}

int main(int argc, char* argv[]) {
    int N = (argc > 1) ? atoi(argv[1]) : 16384; // ~16k x 16k grid
    size_t size = (size_t)N * N * sizeof(float);
    float *in, *out;

    printf("[STENCIL] Grid %dx%d (~%.2f GB total)\n", N, N, (double)size*2/1e9);

    cudaMallocManaged(&in, size);
    cudaMallocManaged(&out, size);

    // CPU Init
    for (size_t i = 0; i < (size_t)N*N; i++) in[i] = 1.0f;

    dim3 threads(16, 16);
    dim3 blocks((N + 15) / 16, (N + 15) / 16);

    cudaEvent_t start, stop;
    cudaEventCreate(&start); cudaEventCreate(&stop);

    printf("Launching Stencil...\n");
    cudaEventRecord(start);
    stencil_2d<<<blocks, threads>>>(in, out, N);
    cudaEventRecord(stop);
    
    cudaDeviceSynchronize();

    float ms = 0;
    cudaEventElapsedTime(&ms, start, stop);
    printf("[RESULT] Time: %.2f ms\n", ms);

    cudaFree(in); cudaFree(out);
    return 0;
}
