/*
 * bench_stream.cu — STREAM Triad benchmark
 * C[i] = A[i] + scalar * B[i]
 *
 * Usage: ./bench_stream <N_elements>
 *   e.g. ./bench_stream 134217728   (128M floats = 512 MB per array)
 *
 * Output (parsed by run_robust.py):
 *   [RESULT] Time: X.XX ms
 *   Bandwidth: X.XX GB/s
 *
 * Bandwidth formula: 3 * N * sizeof(float) / time_s / 1e9
 *   (one read of A, one read of B, one write of C)
 *
 * Build: nvcc -O3 -arch=sm_89 -o bench_stream bench_stream.cu
 */

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <cuda_runtime.h>

/* ------------------------------------------------------------------ */
/* Error-checking macro                                                 */
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

/* ------------------------------------------------------------------ */
/* Kernel                                                               */
/* ------------------------------------------------------------------ */
__global__ void stream_triad(const float * __restrict__ A,
                              const float * __restrict__ B,
                              float       * __restrict__ C,
                              float scalar, long long N)
{
    long long idx = (long long)blockIdx.x * blockDim.x + threadIdx.x;
    long long stride = (long long)gridDim.x * blockDim.x;
    for (long long i = idx; i < N; i += stride) {
        C[i] = A[i] + scalar * B[i];
    }
}

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
        fprintf(stderr, "Usage: %s <N_elements>\n", argv[0]);
        return EXIT_FAILURE;
    }

    long long N = atoll(argv[1]);
    if (N <= 0) {
        fprintf(stderr, "N must be positive\n");
        return EXIT_FAILURE;
    }

    float *A, *B, *C;
    CUDA_CHECK(cudaMallocManaged(&A, N * sizeof(float)));
    CUDA_CHECK(cudaMallocManaged(&B, N * sizeof(float)));
    CUDA_CHECK(cudaMallocManaged(&C, N * sizeof(float)));

    /* Initialise on the host so pages start on CPU side (triggers UVM faults) */
    for (long long i = 0; i < N; i++) {
        A[i] = 1.0f;
        B[i] = 2.0f;
        C[i] = 0.0f;
    }

    const float scalar = 3.0f;
    const int THREADS = 256;
    const int BLOCKS  = (int)((N + THREADS - 1) / THREADS);
    /* cap blocks to avoid launching too many for very large N */
    const int MAX_BLOCKS = 65535;
    const int launch_blocks = (BLOCKS < MAX_BLOCKS) ? BLOCKS : MAX_BLOCKS;

    /* --- Timed region ------------------------------------------------ */
    CUDA_CHECK(cudaDeviceSynchronize());
    double t0 = now_sec();

    stream_triad<<<launch_blocks, THREADS>>>(A, B, C, scalar, N);
    CUDA_CHECK(cudaGetLastError());

    CUDA_CHECK(cudaDeviceSynchronize());
    double t1 = now_sec();
    /* ----------------------------------------------------------------- */

    double time_ms = (t1 - t0) * 1e3;
    double time_s  = t1 - t0;
    double bw_gbs  = (3.0 * (double)N * sizeof(float)) / time_s / 1e9;

    printf("[RESULT] Time: %.2f ms\nBandwidth: %.2f GB/s\n", time_ms, bw_gbs);

    CUDA_CHECK(cudaFree(A));
    CUDA_CHECK(cudaFree(B));
    CUDA_CHECK(cudaFree(C));

    return EXIT_SUCCESS;
}
