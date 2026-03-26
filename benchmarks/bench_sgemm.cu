#include <cublas_v2.h>
#include <cuda_runtime.h>
#include <stdio.h>

int main(int argc, char* argv[]) {
    int N = (argc > 1) ? atoi(argv[1]) : 8192; // Default 8k matrix
    size_t size = (size_t)N * N * sizeof(float);
    float *A, *B, *C;
    float alpha = 1.0f, beta = 0.0f;

    printf("[SGEMM] Matrix %dx%d (~%.2f GB total)\n", N, N, (double)size*3/1e9);

    cudaMallocManaged(&A, size);
    cudaMallocManaged(&B, size);
    cudaMallocManaged(&C, size);

    // CPU Init
    for (size_t i = 0; i < N*N; i++) {
        A[i] = 1.0f; B[i] = 1.0f;
    }

    cublasHandle_t handle;
    cublasCreate(&handle);

    cudaEvent_t start, stop;
    cudaEventCreate(&start); cudaEventCreate(&stop);

    printf("Launching cuBLAS SGEMM...\n");
    cudaEventRecord(start);
    // A, B, C are on Host -> GPU Faults happen here
    cublasSgemm(handle, CUBLAS_OP_N, CUBLAS_OP_N, N, N, N, &alpha, A, N, B, N, &beta, C, N);
    cudaEventRecord(stop);
    
    cudaDeviceSynchronize();
    
    float ms = 0;
    cudaEventElapsedTime(&ms, start, stop);
    printf("[RESULT] Time: %.2f ms\n", ms);

    cublasDestroy(handle);
    cudaFree(A); cudaFree(B); cudaFree(C);
    return 0;
}
