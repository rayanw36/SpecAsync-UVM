/*
 * bench_stencil.cu — 2D 5-point stencil benchmark
 * new[i,j] = 0.25 * (old[i-1,j] + old[i+1,j] + old[i,j-1] + old[i,j+1])
 *
 * Usage: ./bench_stencil <N> [--alloc managed|malloc]   (default managed; malloc: aligned_alloc, 2 MiB aligned, MADV_NOHUGEPAGE; Gate H1)
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
#include <string.h>
#include <stdint.h>
#include <sys/mman.h>
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


/* ---- H1 (Gate C9): --alloc {managed,malloc}. Default managed = the behaviour of every earlier gate, unchanged. malloc mode allocates the
 * same bytes with aligned_alloc (2 MiB alignment, size rounded up to 2 MiB) and madvise(MADV_NOHUGEPAGE); everything else (host
 * initialisation, kernels, checksum) is identical. The option is removed from argv before the positional arguments are parsed. ---- */
static int g_alloc_malloc = 0;
static void strip_alloc_flag(int *argc, char **argv)
{
    int w = 1;
    for (int r = 1; r < *argc; r++) {
        if (strcmp(argv[r], "--alloc") == 0 && r + 1 < *argc) {
            const char *m = argv[++r];
            if (strcmp(m, "malloc") == 0) g_alloc_malloc = 1;
            else if (strcmp(m, "managed") == 0) g_alloc_malloc = 0;
            else { fprintf(stderr, "--alloc must be managed or malloc\n"); exit(2); }
        } else {
            argv[w++] = argv[r];
        }
    }
    *argc = w;
}
static void *alloc_array(size_t bytes)
{
    void *p = NULL;
    if (!g_alloc_malloc) { CUDA_CHECK(cudaMallocManaged(&p, bytes)); return p; }
    const size_t A = (size_t)2 << 20;
    size_t b = (bytes + A - 1) & ~(A - 1);
    p = aligned_alloc(A, b);
    if (!p) { fprintf(stderr, "aligned_alloc failed\n"); exit(2); }
    if (madvise(p, b, MADV_NOHUGEPAGE) != 0) { fprintf(stderr, "madvise(MADV_NOHUGEPAGE) failed\n"); exit(2); }
    return p;
}
static void free_array(void *p)
{
    if (g_alloc_malloc) free(p); else CUDA_CHECK(cudaFree(p));
}

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
    strip_alloc_flag(&argc, argv);
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
    grid0 = (float *)alloc_array(elems * sizeof(float));
    grid1 = (float *)alloc_array(elems * sizeof(float));
    /* Task A2 (AWS final work block): allocation base address, for H1
     * (page-alignment vs bimodal cluster) correlation. Printed to stderr so
     * it never interferes with [RESULT]-line stdout parsers. */
    fprintf(stderr, "[SPECASYNC_ALLOC] grid0=%p grid1=%p size=%lld\n",
            (void *)grid0, (void *)grid1, elems * (long long)sizeof(float));

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


    /* Validation only (Gate H1): STENCIL_CHECKSUM=1 prints a 64-bit sum of the bit patterns of the final grid (after the timed region), and for
     * N <= 4096 a CPU reference of the same ping-pong computation. Unset = no extra work and no extra output. */
    if (getenv("STENCIL_CHECKSUM")) {
        auto bits = [](float f) { uint32_t u; memcpy(&u, &f, 4); return (uint64_t)u; };
        uint64_t sum = 0;
        for (long long i = 0; i < elems; i++) sum += bits(src[i]);
        printf("[CHECKSUM] %016llx\n", (unsigned long long)sum);
        if (N <= 4096) {
            float *a = (float *)malloc(elems * sizeof(float)), *b = (float *)malloc(elems * sizeof(float));
            for (long long i = 0; i < elems; i++) { a[i] = (float)(i % 1024) / 1024.0f; b[i] = 0.0f; }
            float *s0 = a, *d0 = b;
            for (int it = 0; it < ITERS; it++) {
                for (int r = 1; r < N - 1; r++)
                    for (int c = 1; c < N - 1; c++) {
                        long long k = (long long)r * N + c;
                        d0[k] = 0.25f * (s0[k - N] + s0[k + N] + s0[k - 1] + s0[k + 1]);
                    }
                float *t = s0; s0 = d0; d0 = t;
            }
            uint64_t ref = 0;
            for (long long i = 0; i < elems; i++) ref += bits(s0[i]);
            printf("[CHECKSUM_REF] %016llx\n", (unsigned long long)ref);
            free(a); free(b);
        }
    }

    free_array(grid0);
    free_array(grid1);

    return EXIT_SUCCESS;
}
