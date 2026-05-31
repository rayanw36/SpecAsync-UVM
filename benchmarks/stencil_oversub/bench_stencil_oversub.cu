/*
 * bench_stencil_oversub.cu — 2D 5-point stencil with VRAM-oversubscription
 *
 * Identical algorithm to bench_stencil.cu, but sized for working sets that
 * exceed a 16 GB GPU:
 *
 *   Two float grids, total bytes = 2 * N^2 * 4
 *   N ≈ 51200  →  2 × 51200²  × 4 ≈ 20.97 GB  (~1.31× oversubscription)
 *   N ≈ 55000  →  2 × 55000²  × 4 ≈ 24.20 GB  (~1.51× oversubscription)
 *   N ≈ 63000  →  2 × 63000²  × 4 ≈ 31.75 GB  (~1.98× oversubscription)
 *
 * Usage: ./bench_stencil_oversub <N> [iters]
 *   N      — grid side length (e.g. 51200)
 *   iters  — number of ping-pong iterations (default: 20)
 *
 * Prints to stderr at startup:
 *   [INFO] Grid NxN = X.XX GB managed memory
 *
 * Output (parsed by run_robust.py):
 *   [RESULT] Time: X.XX ms
 *   Bandwidth: X.XX GB/s
 *
 * Bandwidth formula: iters * N * N * 2 * sizeof(float) / time_s / 1e9
 *
 * Build: nvcc -O3 -arch=sm_89 -o bench_stencil_oversub bench_stencil_oversub.cu
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
/* Kernel: 2D 5-point stencil, 16×16 thread blocks                     */
/* ------------------------------------------------------------------ */
__global__ void stencil_2d(const float * __restrict__ src,
                            float       * __restrict__ dst,
                            long long N)
{
    long long col = (long long)blockIdx.x * blockDim.x + threadIdx.x;
    long long row = (long long)blockIdx.y * blockDim.y + threadIdx.y;

    /* Skip boundary cells */
    if (row < 1 || row >= N - 1 || col < 1 || col >= N - 1)
        return;

    long long idx = row * N + col;
    dst[idx] = 0.25f * (src[idx - N] + src[idx + N] +
                        src[idx - 1] + src[idx + 1]);
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
        fprintf(stderr, "Usage: %s <N> [iters]\n", argv[0]);
        return EXIT_FAILURE;
    }

    long long N    = atoll(argv[1]);
    int       iters = (argc >= 3) ? atoi(argv[2]) : 20;

    if (N <= 2) {
        fprintf(stderr, "N must be > 2\n");
        return EXIT_FAILURE;
    }
    if (iters <= 0) {
        fprintf(stderr, "iters must be positive\n");
        return EXIT_FAILURE;
    }

    long long elems     = N * N;
    double    grid_gb   = 2.0 * (double)elems * sizeof(float) / 1e9;

    fprintf(stderr, "[INFO] Grid %lldx%lld = %.2f GB managed memory\n",
            N, N, grid_gb);

    float *grid0, *grid1;
    CUDA_CHECK(cudaMallocManaged(&grid0, elems * sizeof(float)));
    CUDA_CHECK(cudaMallocManaged(&grid1, elems * sizeof(float)));

    /*
     * Initialise on the host in batches to avoid long single-threaded loops
     * at very large N. Pages start CPU-side, triggering UVM page faults when
     * the GPU kernel first accesses them.
     */
    for (long long i = 0; i < elems; i++) {
        grid0[i] = (float)(i % 1024) / 1024.0f;
        grid1[i] = 0.0f;
    }

    dim3 threads(16, 16);
    dim3 blocks((unsigned int)((N + threads.x - 1) / threads.x),
                (unsigned int)((N + threads.y - 1) / threads.y));

    float *src = grid0;
    float *dst = grid1;

    /* --- Timed region ------------------------------------------------ */
    CUDA_CHECK(cudaDeviceSynchronize());
    double t0 = now_sec();

    for (int iter = 0; iter < iters; iter++) {
        stencil_2d<<<blocks, threads>>>(src, dst, N);
        CUDA_CHECK(cudaGetLastError());
        float *tmp = src;
        src = dst;
        dst = tmp;
    }

    CUDA_CHECK(cudaDeviceSynchronize());
    double t1 = now_sec();
    /* ----------------------------------------------------------------- */

    double time_ms = (t1 - t0) * 1e3;
    double time_s  = t1 - t0;
    double bw_gbs  = ((double)iters * (double)elems * 2.0 * sizeof(float))
                     / time_s / 1e9;

    printf("[RESULT] Time: %.2f ms\nBandwidth: %.2f GB/s\n", time_ms, bw_gbs);

    CUDA_CHECK(cudaFree(grid0));
    CUDA_CHECK(cudaFree(grid1));

    return EXIT_SUCCESS;
}
