/*
 * bench_sparse.cu — adversarial sparse-access benchmark (Gate E8). Userspace only.
 *
 * Usage: ./bench_sparse <GiB> <K> <passes> <seed>
 *   GiB     size of the one cudaMallocManaged array (fractions allowed, e.g. 0.0625 = 64 MiB)
 *   K       distinct 4 KB pages touched in EACH 2 MB block (1..512)
 *   passes  number of kernel launches; every pass uses the SAME page list
 *   seed    seeds the block permutation, the page choice and the word offsets
 *
 * Design (E8_PREREGISTRATION.md):
 *   - one cudaMallocManaged array; no cudaMemAdvise, no cudaMemPrefetchAsync. The host writes EVERY
 *     word before the first kernel, so every page starts CPU-resident, preferred location unset.
 *   - the 2 MB blocks are visited in a seeded random permutation; within a block, K distinct
 *     seeded-random 4 KB pages are chosen (partial Fisher-Yates); each listed page gets one seeded word.
 *   - the page list is built on the host and copied into a cudaMalloc (NOT managed) index array, so
 *     the index array never faults.
 *   - each pass = one kernel launch, one thread per listed page, read-modify-write of one 4-byte word:
 *       a[i] = a[i] * 1664525 + 1013904223 (mod 2^32).
 *     In the LAST pass the kernel also adds the new value into a 64-bit device accumulator (a cudaMalloc'd
 *     word), so the checksum comes from the GPU-updated array without any extra pass over managed memory.
 *   - expected_checksum is computed independently on the host from the initial-value formula and the page
 *     list (it never reads the array back).
 *   - exit status 1 if checksum != expected_checksum.
 *
 * Test hook (validation only): environment variable SPARSE_TEST_REF_OFFSET=<n> adds n to the host reference
 * so the mismatch path can be exercised (validation (e)).
 *
 * Output (stdout):
 *   [RESULT] pages_touched=<n> blocks=<b> K=<k> passes=<p> seed=<s>
 *   distinct_pages=<n> total_pages=<n>
 *   checksum=<hex> expected_checksum=<hex>
 *   page_list_hash=<hex>
 *   pass <i> kernel_ms=<x>
 *   CHECKSUM OK | CHECKSUM MISMATCH
 *
 * Build: /usr/local/cuda/bin/nvcc -O3 -arch=sm_120 -o bench_sparse bench_sparse.cu
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <algorithm>
#include <random>
#include <vector>
#include <cuda_runtime.h>

#define CUDA_CHECK(call)                                                       \
    do {                                                                       \
        cudaError_t err__ = (call);                                            \
        if (err__ != cudaSuccess) {                                            \
            fprintf(stderr, "CUDA error %s at %s:%d: %s\n", #call, __FILE__,   \
                    __LINE__, cudaGetErrorString(err__));                      \
            exit(2);                                                           \
        }                                                                      \
    } while (0)

static const uint64_t BLOCK_BYTES = 2ull << 20;      /* 2 MB UVM block */
static const uint32_t PAGES_PER_BLOCK = 512;         /* 4 KB pages per block */
static const uint32_t WORDS_PER_PAGE = 1024;         /* 4-byte words per 4 KB page */

__host__ __device__ static inline uint32_t init_word(uint64_t i) { return (uint32_t)(i * 2654435761u) ^ (uint32_t)(i >> 32); }
__host__ __device__ static inline uint32_t step_word(uint32_t v) { return v * 1664525u + 1013904223u; }

__global__ void sparse_pass(uint32_t *arr, const uint64_t *idx, uint64_t n, unsigned long long *acc, int last)
{
    uint64_t t = (uint64_t)blockIdx.x * blockDim.x + threadIdx.x;
    if (t >= n) return;
    uint64_t i = idx[t];
    uint32_t v = step_word(arr[i]);
    arr[i] = v;
    if (last) atomicAdd(acc, (unsigned long long)v);
}

int main(int argc, char **argv)
{
    if (argc != 5) {
        fprintf(stderr, "Usage: %s <GiB> <K> <passes> <seed>\n", argv[0]);
        return 2;
    }
    double gib = atof(argv[1]);
    int K = atoi(argv[2]);
    int passes = atoi(argv[3]);
    uint64_t seed = strtoull(argv[4], NULL, 10);
    if (!(gib > 0) || K < 1 || K > (int)PAGES_PER_BLOCK || passes < 1) {
        fprintf(stderr, "bad arguments\n");
        return 2;
    }
    uint64_t bytes = (uint64_t)(gib * (double)(1ull << 30));
    uint64_t blocks = bytes / BLOCK_BYTES;
    if (blocks < 1) { fprintf(stderr, "size < one 2 MB block\n"); return 2; }
    bytes = blocks * BLOCK_BYTES;
    uint64_t words = bytes / 4, total_pages = blocks * PAGES_PER_BLOCK;

    /* ---- host page list (seeded) ---- */
    std::mt19937_64 rng(seed);
    std::vector<uint64_t> block_order(blocks);
    for (uint64_t b = 0; b < blocks; b++) block_order[b] = b;
    std::shuffle(block_order.begin(), block_order.end(), rng);
    uint64_t n = blocks * (uint64_t)K;
    std::vector<uint64_t> list(n);
    std::vector<uint32_t> pg(PAGES_PER_BLOCK);
    uint64_t t = 0;
    for (uint64_t bi = 0; bi < blocks; bi++) {
        for (uint32_t p = 0; p < PAGES_PER_BLOCK; p++) pg[p] = p;
        for (int k = 0; k < K; k++) {                         /* partial Fisher-Yates: K distinct pages */
            uint32_t j = k + (uint32_t)(rng() % (PAGES_PER_BLOCK - k));
            std::swap(pg[k], pg[j]);
            uint64_t page = block_order[bi] * PAGES_PER_BLOCK + pg[k];
            uint32_t off = (uint32_t)(rng() % WORDS_PER_PAGE);
            list[t++] = page * WORDS_PER_PAGE + off;
        }
    }
    uint64_t h = 1469598103934665603ull;                      /* FNV-1a 64 over the index bytes */
    for (uint64_t i = 0; i < n; i++) {
        uint64_t v = list[i];
        for (int b = 0; b < 8; b++) { h ^= (v >> (8 * b)) & 0xff; h *= 1099511628211ull; }
    }
    std::vector<uint64_t> sorted(list);
    std::sort(sorted.begin(), sorted.end());
    uint64_t distinct_words = std::unique(sorted.begin(), sorted.end()) - sorted.begin();
    for (uint64_t i = 0; i < n; i++) sorted[i] = list[i] / WORDS_PER_PAGE;
    std::sort(sorted.begin(), sorted.begin() + n);
    uint64_t distinct_pages = std::unique(sorted.begin(), sorted.begin() + n) - sorted.begin();
    if (distinct_words != n || distinct_pages != n) { fprintf(stderr, "internal: page list not distinct\n"); return 2; }

    /* ---- independent host reference (never reads the array back) ---- */
    unsigned long long expected = 0;
    for (uint64_t i = 0; i < n; i++) {
        uint32_t v = init_word(list[i]);
        for (int p = 0; p < passes; p++) v = step_word(v);
        expected += v;
    }
    const char *off = getenv("SPARSE_TEST_REF_OFFSET");
    if (off) expected += strtoull(off, NULL, 10);

    /* ---- device memory ---- */
    uint32_t *arr = NULL;
    CUDA_CHECK(cudaMallocManaged(&arr, bytes));               /* the only managed allocation */
    uint64_t *d_idx = NULL;
    CUDA_CHECK(cudaMalloc(&d_idx, n * sizeof(uint64_t)));     /* NOT managed: never faults */
    unsigned long long *d_acc = NULL;
    CUDA_CHECK(cudaMalloc(&d_acc, sizeof(unsigned long long)));
    CUDA_CHECK(cudaMemcpy(d_idx, list.data(), n * sizeof(uint64_t), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemset(d_acc, 0, sizeof(unsigned long long)));

    /* host writes EVERY word: every page starts CPU-resident */
    for (uint64_t i = 0; i < words; i++) arr[i] = init_word(i);

    /* ---- passes ---- */
    cudaEvent_t e0, e1;
    CUDA_CHECK(cudaEventCreate(&e0));
    CUDA_CHECK(cudaEventCreate(&e1));
    std::vector<float> ms(passes);
    int threads = 256;
    uint64_t grid = (n + threads - 1) / threads;
    for (int p = 0; p < passes; p++) {
        CUDA_CHECK(cudaEventRecord(e0));
        sparse_pass<<<(unsigned)grid, threads>>>(arr, d_idx, n, d_acc, p == passes - 1);
        CUDA_CHECK(cudaGetLastError());
        CUDA_CHECK(cudaEventRecord(e1));
        CUDA_CHECK(cudaEventSynchronize(e1));
        CUDA_CHECK(cudaEventElapsedTime(&ms[p], e0, e1));
    }
    unsigned long long got = 0;
    CUDA_CHECK(cudaMemcpy(&got, d_acc, sizeof(got), cudaMemcpyDeviceToHost));

    printf("[RESULT] pages_touched=%llu blocks=%llu K=%d passes=%d seed=%llu\n", (unsigned long long)n,
           (unsigned long long)blocks, K, passes, (unsigned long long)seed);
    printf("distinct_pages=%llu total_pages=%llu\n", (unsigned long long)distinct_pages, (unsigned long long)total_pages);
    printf("checksum=%016llx expected_checksum=%016llx\n", got, expected);
    printf("page_list_hash=%016llx\n", (unsigned long long)h);
    for (int p = 0; p < passes; p++) printf("pass %d kernel_ms=%.3f\n", p + 1, ms[p]);

    CUDA_CHECK(cudaEventDestroy(e0));
    CUDA_CHECK(cudaEventDestroy(e1));
    CUDA_CHECK(cudaFree(d_acc));
    CUDA_CHECK(cudaFree(d_idx));
    CUDA_CHECK(cudaFree(arr));
    if (got != expected) { printf("CHECKSUM MISMATCH\n"); return 1; }
    printf("CHECKSUM OK\n");
    return 0;
}
