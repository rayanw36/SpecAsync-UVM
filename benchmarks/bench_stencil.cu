/*
 * bench_stencil.cu — 2D 5-point stencil benchmark
 * new[i,j] = 0.25 * (old[i-1,j] + old[i+1,j] + old[i,j-1] + old[i,j+1])
 *
 * Usage: ./bench_stencil <N>
 *   e.g. ./bench_stencil 8192   (8192x8192 float grid)
 *
 * Runs 20 ping-pong stencil iterations between two managed grids.
 *
 * Output (parsed by run_robust.py):
 *   [RESULT] Time: X.XX ms
 *   Bandwidth: X.XX GB/s
 *
 * Bandwidth formula: 20 * N * N * 2 * sizeof(float) / time_s / 1e9
 *   (one read + one write per element per iteration, 20 iterations)
 *
 * Build: nvcc -O3 -arch=sm_89 -o bench_stencil bench_stencil.cu
 */

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <cuda_runtime.h>

#define ITERS 20

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
/* Kernel: 16×16 thread blocks                                          */
/* ------------------------------------------------------------------ */
__global__ void stencil_2d(const float * __restrict__ src,
                            float       * __restrict__ dst,
                            int N)
{
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    int row = blockIdx.y * blockDim.y + threadIdx.y;

    /* Skip boundary cells */
    if (row < 1 || row >= N - 1 || col < 1 || col >= N - 1)
        return;

    long long idx = (long long)row * N + col;
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
        fprintf(stderr, "Usage: %s <N>\n", argv[0]);
        return EXIT_FAILURE;
    }

    int N = atoi(argv[1]);
    if (N <= 2) {
        fprintf(stderr, "N must be > 2\n");
        return EXIT_FAILURE;
    }

    long long elems = (long long)N * N;

    float *grid0, *grid1;
    CUDA_CHECK(cudaMallocManaged(&grid0, elems * sizeof(float)));
    CUDA_CHECK(cudaMallocManaged(&grid1, elems * sizeof(float)));

    /* Initialise on host — drives UVM page faults on first GPU access */
    for (long long i = 0; i < elems; i++) {
        grid0[i] = (float)(i % 1024) / 1024.0f;
        grid1[i] = 0.0f;
    }

    dim3 threads(16, 16);
    dim3 blocks((N + threads.x - 1) / threads.x,
                (N + threads.y - 1) / threads.y);

    float *src = grid0;
    float *dst = grid1;

    /* --- Timed region ------------------------------------------------ */
    CUDA_CHECK(cudaDeviceSynchronize());
    double t0 = now_sec();

    for (int iter = 0; iter < ITERS; iter++) {
        stencil_2d<<<blocks, threads>>>(src, dst, N);
        CUDA_CHECK(cudaGetLastError());
        /* Swap ping-pong buffers */
        float *tmp = src;
        src = dst;
        dst = tmp;
    }

    CUDA_CHECK(cudaDeviceSynchronize());
    double t1 = now_sec();
    /* ----------------------------------------------------------------- */

    double time_ms = (t1 - t0) * 1e3;
    double time_s  = t1 - t0;
    /* read + write per element per iteration, 20 iterations */
    double bw_gbs  = ((double)ITERS * (double)elems * 2.0 * sizeof(float))
                     / time_s / 1e9;

    printf("[RESULT] Time: %.2f ms\nBandwidth: %.2f GB/s\n", time_ms, bw_gbs);

    CUDA_CHECK(cudaFree(grid0));
    CUDA_CHECK(cudaFree(grid1));

    return EXIT_SUCCESS;
}
