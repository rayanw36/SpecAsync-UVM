#include <cufft.h>
#include <cuda_runtime.h>
#include <stdio.h>

int main(int argc, char* argv[]) {
    int N = (argc > 1) ? atoi(argv[1]) : 1024*1024*64; // 64M elements
    size_t size = N * sizeof(cufftComplex);
    cufftComplex *data;

    printf("[cuFFT] 1D FFT Size: %d (~%.2f GB)\n", N, (double)size/1e9);

    cudaMallocManaged(&data, size);

    // CPU Init
    for (int i = 0; i < N; i++) {
        data[i].x = 1.0f; data[i].y = 0.0f;
    }

    cufftHandle plan;
    cufftPlan1d(&plan, N, CUFFT_C2C, 1);

    cudaEvent_t start, stop;
    cudaEventCreate(&start); cudaEventCreate(&stop);

    printf("Launching FFT...\n");
    cudaEventRecord(start);
    cufftExecC2C(plan, data, data, CUFFT_FORWARD);
    cudaEventRecord(stop);

    cudaDeviceSynchronize();
    float ms = 0;
    cudaEventElapsedTime(&ms, start, stop);
    printf("[RESULT] Time: %.2f ms\n", ms);

    cufftDestroy(plan);
    cudaFree(data);
    return 0;
}
