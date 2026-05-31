/*
 * bench_cufft.cu — 1D complex-to-complex FFT benchmark using cuFFT
 *
 * Usage: ./bench_cufft <N_elements>
 *   e.g. ./bench_cufft 67108864   (64M complex floats)
 *
 * Output (parsed by run_robust.py):
 *   [RESULT] Time: X.XX ms
 *   Bandwidth: X.XX GB/s
 *
 * Bandwidth formula: 2 * N * sizeof(cufftComplex) / time_s / 1e9
 *   (one read pass + one write pass over the complex array)
 *
 * Build: nvcc -O3 -arch=sm_89 -o bench_cufft bench_cufft.cu -lcufft
 */

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <cuda_runtime.h>
#include <cufft.h>

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

#define CUFFT_CHECK(call)                                                      \
    do {                                                                       \
        cufftResult _r = (call);                                               \
        if (_r != CUFFT_SUCCESS) {                                             \
            fprintf(stderr, "cuFFT error at %s:%d — result %d\n",             \
                    __FILE__, __LINE__, (int)_r);                              \
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
        fprintf(stderr, "Usage: %s <N_elements>\n", argv[0]);
        return EXIT_FAILURE;
    }

    long long N = atoll(argv[1]);
    if (N <= 0) {
        fprintf(stderr, "N must be positive\n");
        return EXIT_FAILURE;
    }

    /* cuFFT plan size is int — guard against overflow */
    if (N > (long long)INT_MAX) {
        fprintf(stderr, "N too large for a single cuFFT 1D plan\n");
        return EXIT_FAILURE;
    }

    cufftComplex *data;
    CUDA_CHECK(cudaMallocManaged(&data, N * sizeof(cufftComplex)));

    /* Initialise on host — drives UVM page faults on first GPU access */
    for (long long i = 0; i < N; i++) {
        data[i].x = (float)(i % 1024) / 1024.0f;
        data[i].y = 0.0f;
    }

    /* Create plan */
    cufftHandle plan;
    CUFFT_CHECK(cufftPlan1d(&plan, (int)N, CUFFT_C2C, 1));

    /* --- Timed region ------------------------------------------------ */
    CUDA_CHECK(cudaDeviceSynchronize());
    double t0 = now_sec();

    CUFFT_CHECK(cufftExecC2C(plan, data, data, CUFFT_FORWARD));

    CUDA_CHECK(cudaDeviceSynchronize());
    double t1 = now_sec();
    /* ----------------------------------------------------------------- */

    double time_ms = (t1 - t0) * 1e3;
    double time_s  = t1 - t0;
    double bw_gbs  = (2.0 * (double)N * sizeof(cufftComplex)) / time_s / 1e9;

    printf("[RESULT] Time: %.2f ms\nBandwidth: %.2f GB/s\n", time_ms, bw_gbs);

    CUFFT_CHECK(cufftDestroy(plan));
    CUDA_CHECK(cudaFree(data));

    return EXIT_SUCCESS;
}
