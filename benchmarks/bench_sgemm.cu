/*
 * bench_sgemm.cu — Matrix-multiply benchmark using cuBLAS
 * C = A * B  (NxN single-precision, no transpose)
 *
 * Usage: ./bench_sgemm <N>
 *   e.g. ./bench_sgemm 8192   (8192x8192 float matrices)
 *
 * Output (parsed by run_robust.py):
 *   [RESULT] Time: X.XX ms
 *   Bandwidth: X.XX GB/s
 *
 * Bandwidth formula: 3 * N * N * sizeof(float) / time_s / 1e9
 *   (read A, read B, write C)
 *
 * Build: nvcc -O3 -arch=sm_89 -o bench_sgemm bench_sgemm.cu -lcublas
 */

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <cuda_runtime.h>
#include <cublas_v2.h>

/* ------------------------------------------------------------------ */
/* Error-checking macros                                                */
/* ------------------------------------------------------------------ */
#define CUDA_CHECK(call)                                                       \
    do {                                                                       \
        cudaError_t _err = (call);                                             \
        if (_err != cudaSuccess) {                                             \
            fprintf(stderr, "CUDA error at %s:%d — %s\n",                     \
                    __FILE__, __LINE__, cudaGetErrorString(_err));             \
            exit(EXIT_FAILURE);                                                \
        }                                                                     \
    } while (0)

#define CUBLAS_CHECK(call)                                                     \
    do {                                                                       \
        cublasStatus_t _st = (call);                                           \
        if (_st != CUBLAS_STATUS_SUCCESS) {                                    \
            fprintf(stderr, "cuBLAS error at %s:%d — status %d\n",            \
                    __FILE__, __LINE__, (int)_st);                             \
            exit(EXIT_FAILURE);                                                \
        }                                                                     \
    } while (0)

/* ------------------------------------------------------------------ */
/* Helper: wall-clock time in seconds                                   */
/* ------------------------------------------------------------------ */
static double now_sec(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

/* ------------------------------------------------------------------ */
/* main                                                                 */
/* ------------------------------------------------------------------ */
int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <N>\n", argv[0]);
        return EXIT_FAILURE;
    }

    int N = atoi(argv[1]);
    if (N <= 0) {
        fprintf(stderr, "N must be positive\n");
        return EXIT_FAILURE;
    }

    long long elems = (long long)N * N;

    float *A, *B, *C;
    CUDA_CHECK(cudaMallocManaged(&A, elems * sizeof(float)));
    CUDA_CHECK(cudaMallocManaged(&B, elems * sizeof(float)));
    CUDA_CHECK(cudaMallocManaged(&C, elems * sizeof(float)));

    /* Initialise on the host — pages start CPU-side to drive UVM faults */
    for (long long i = 0; i < elems; i++) {
        A[i] = 1.0f / (float)(i % N + 1);
        B[i] = 1.0f / (float)(i / N + 1);
        C[i] = 0.0f;
    }

    cublasHandle_t handle;
    CUBLAS_CHECK(cublasCreate(&handle));

    const float alpha = 1.0f;
    const float beta  = 0.0f;

    /* --- Timed region ------------------------------------------------ */
    CUDA_CHECK(cudaDeviceSynchronize());
    double t0 = now_sec();

    /*
     * cuBLAS uses column-major storage.  To compute C = A*B in row-major
     * we call C^T = B^T * A^T which is equivalent to:
     *   cublasSgemm(handle, CUBLAS_OP_N, CUBLAS_OP_N, N, N, N,
     *               &alpha, B, N, A, N, &beta, C, N)
     */
    CUBLAS_CHECK(cublasSgemm(handle,
                             CUBLAS_OP_N, CUBLAS_OP_N,
                             N, N, N,
                             &alpha,
                             B, N,
                             A, N,
                             &beta,
                             C, N));

    CUDA_CHECK(cudaDeviceSynchronize());
    double t1 = now_sec();
    /* ----------------------------------------------------------------- */

    double time_ms = (t1 - t0) * 1e3;
    double time_s  = t1 - t0;
    double bw_gbs  = (3.0 * (double)elems * sizeof(float)) / time_s / 1e9;

    printf("[RESULT] Time: %.2f ms\nBandwidth: %.2f GB/s\n", time_ms, bw_gbs);

    CUBLAS_CHECK(cublasDestroy(handle));
    CUDA_CHECK(cudaFree(A));
    CUDA_CHECK(cudaFree(B));
    CUDA_CHECK(cudaFree(C));

    return EXIT_SUCCESS;
}
