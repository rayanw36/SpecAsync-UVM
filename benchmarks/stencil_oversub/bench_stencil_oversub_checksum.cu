/*
 * bench_stencil_oversub_checksum.cu — Gate B9 Task 1 output-equivalence variant
 *
 * BENCHMARK MODIFICATION, disclosed per GATE_B9_OVERSUB_MECHANISM.md Task 1a:
 * bench_stencil_oversub.cu emits no verifiable result beyond [RESULT] Time/
 * Bandwidth. This variant is a byte-for-byte copy of bench_stencil_oversub.cu
 * with one addition: after the timed region (so the primary Time/Bandwidth
 * metric is unaffected), it computes and prints a checksum of the final
 * output buffer (`src` after the last ping-pong swap) --
 *
 *   [CHECKSUM] elems=<N> sum=<double, Kahan-summed> fnv1a64=<hex 64-bit hash>
 *   [COUNTERS] iters=<N> kernel_launches=<N>
 *
 * The FNV-1a hash runs over the raw IEEE-754 bit pattern of every element
 * (not the float value), so it is sensitive to bit-identical equality, not
 * just numerically-close equality. The Kahan sum is a second, independent
 * check that is robust to hash collisions and reports a numeric magnitude
 * a human can sanity-check.
 *
 * This binary is used ONLY for Task 1's output-equivalence check. Tasks 2-4
 * use the original, unmodified bench_stencil_oversub binary throughout, so
 * none of this project's existing timing data or the new mechanism/sweep
 * data in this gate depends on the modified code path.
 *
 * Build: nvcc -O3 -arch=sm_75 -o bench_stencil_oversub_checksum bench_stencil_oversub_checksum.cu
 *   (same NVCCFLAGS as the Makefile's original target -- same embedded PTX,
 *   same JIT path on sm_120, so kernel codegen is unchanged from the binary
 *   used everywhere else in this project.)
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <cuda_runtime.h>

#define CUDA_CHECK(call)                                                       \
    do {                                                                       \
        cudaError_t _err = (call);                                             \
        if (_err != cudaSuccess) {                                             \
            fprintf(stderr, "CUDA error at %s:%d — %s\n",                     \
                    __FILE__, __LINE__, cudaGetErrorString(_err));             \
            exit(EXIT_FAILURE);                                                \
        }                                                                     \
    } while (0)

__global__ void stencil_2d(const float * __restrict__ src,
                            float       * __restrict__ dst,
                            long long N)
{
    long long col = (long long)blockIdx.x * blockDim.x + threadIdx.x;
    long long row = (long long)blockIdx.y * blockDim.y + threadIdx.y;

    if (row < 1 || row >= N - 1 || col < 1 || col >= N - 1)
        return;

    long long idx = row * N + col;
    dst[idx] = 0.25f * (src[idx - N] + src[idx + N] +
                        src[idx - 1] + src[idx + 1]);
}

static double now_sec(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <N> [iters] [balloon_mib]\n", argv[0]);
        return EXIT_FAILURE;
    }

    long long N         = atoll(argv[1]);
    int       iters     = (argc >= 3) ? atoi(argv[2]) : 20;
    long long balloon_mib = (argc >= 4) ? atoll(argv[3]) : 0;

    if (N <= 2) {
        fprintf(stderr, "N must be > 2\n");
        return EXIT_FAILURE;
    }
    if (iters <= 0) {
        fprintf(stderr, "iters must be positive\n");
        return EXIT_FAILURE;
    }

    void *balloon = NULL;
    if (balloon_mib > 0) {
        size_t balloon_bytes = (size_t)balloon_mib * 1024ULL * 1024ULL;
        cudaError_t berr = cudaMalloc(&balloon, balloon_bytes);
        if (berr != cudaSuccess) {
            fprintf(stderr, "[WARN] Balloon alloc failed (%lld MiB): %s — continuing without\n",
                    balloon_mib, cudaGetErrorString(berr));
            balloon = NULL;
            balloon_mib = 0;
        } else {
            fprintf(stderr, "[INFO] Balloon: %lld MiB VRAM pinned\n", balloon_mib);
        }
    }

    long long elems     = N * N;
    double    grid_gb   = 2.0 * (double)elems * sizeof(float) / 1e9;

    fprintf(stderr, "[INFO] Grid %lldx%lld = %.2f GB managed memory balloon=%lld MiB\n",
            N, N, grid_gb, balloon_mib);

    float *grid0, *grid1;
    CUDA_CHECK(cudaMallocManaged(&grid0, elems * sizeof(float)));
    CUDA_CHECK(cudaMallocManaged(&grid1, elems * sizeof(float)));

    for (long long i = 0; i < elems; i++) {
        grid0[i] = (float)(i % 1024) / 1024.0f;
        grid1[i] = 0.0f;
    }

    dim3 threads(16, 16);
    dim3 blocks((unsigned int)((N + threads.x - 1) / threads.x),
                (unsigned int)((N + threads.y - 1) / threads.y));

    float *src = grid0;
    float *dst = grid1;

    /* --- Timed region (identical to bench_stencil_oversub.cu) -------- */
    CUDA_CHECK(cudaDeviceSynchronize());
    double t0 = now_sec();

    int kernel_launches = 0;
    for (int iter = 0; iter < iters; iter++) {
        stencil_2d<<<blocks, threads>>>(src, dst, N);
        CUDA_CHECK(cudaGetLastError());
        kernel_launches++;
        float *tmp = src;
        src = dst;
        dst = tmp;
    }

    CUDA_CHECK(cudaDeviceSynchronize());
    double t1 = now_sec();
    /* ------------------------------------------------------------------ */

    double time_ms = (t1 - t0) * 1e3;
    double time_s  = t1 - t0;
    double bw_gbs  = ((double)iters * (double)elems * 2.0 * sizeof(float))
                     / time_s / 1e9;

    printf("[RESULT] Time: %.2f ms\nBandwidth: %.2f GB/s\n", time_ms, bw_gbs);

    /* --- Checksum region: AFTER the timed region, does not affect
     *     [RESULT] Time. `src` holds the final result post-swap. --------- */
    double  kahan_sum = 0.0, kahan_c = 0.0;
    uint64_t fnv = 14695981039346656037ULL;   /* FNV-1a 64 offset basis */
    const uint64_t fnv_prime = 1099511628211ULL;

    for (long long i = 0; i < elems; i++) {
        float v = src[i];
        double y = (double)v - kahan_c;
        double t = kahan_sum + y;
        kahan_c = (t - kahan_sum) - y;
        kahan_sum = t;

        uint32_t bits;
        memcpy(&bits, &v, sizeof(bits));
        fnv ^= (uint64_t)bits;
        fnv *= fnv_prime;
    }

    printf("[CHECKSUM] elems=%lld sum=%.17g fnv1a64=%016llx\n",
           elems, kahan_sum, (unsigned long long)fnv);
    printf("[COUNTERS] iters=%d kernel_launches=%d\n", iters, kernel_launches);

    CUDA_CHECK(cudaFree(grid0));
    CUDA_CHECK(cudaFree(grid1));
    if (balloon) cudaFree(balloon);

    return EXIT_SUCCESS;
}
