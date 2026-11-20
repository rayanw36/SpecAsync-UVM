// C22 VII-4: reproduces bench_sparse.cu's page list (same std::mt19937_64, std::shuffle, partial Fisher-Yates) and writes, per K,
// the touched page indices (4 KB pages, global) in list order as uint32 to argv[4]; prints page_list_hash (FNV-1a over the word indices) to validate against the run logs.
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <random>
#include <algorithm>
#include <vector>
int main(int argc, char **argv) {
    double gib = atof(argv[1]); int K = atoi(argv[2]); uint64_t seed = strtoull(argv[3], 0, 10);
    const uint64_t BLOCK = 2ull << 20, PPB = 512, WPP = 1024;
    uint64_t blocks = (uint64_t)(gib * (double)(1ull << 30)) / BLOCK;
    std::mt19937_64 rng(seed);
    std::vector<uint64_t> bo(blocks); for (uint64_t b = 0; b < blocks; b++) bo[b] = b;
    std::shuffle(bo.begin(), bo.end(), rng);
    uint64_t n = blocks * (uint64_t)K; std::vector<uint64_t> list(n); std::vector<uint32_t> pg(PPB); uint64_t t = 0;
    for (uint64_t bi = 0; bi < blocks; bi++) {
        for (uint32_t p = 0; p < PPB; p++) pg[p] = p;
        for (int k = 0; k < K; k++) { uint32_t j = k + (uint32_t)(rng() % (PPB - k)); std::swap(pg[k], pg[j]); uint64_t page = bo[bi] * PPB + pg[k]; uint32_t off = (uint32_t)(rng() % WPP); list[t++] = page * WPP + off; }
    }
    uint64_t h = 1469598103934665603ull;
    for (uint64_t i = 0; i < n; i++) { uint64_t v = list[i]; for (int b = 0; b < 8; b++) { h ^= (v >> (8 * b)) & 0xff; h *= 1099511628211ull; } }
    printf("blocks=%llu K=%d page_list_hash=%016llx\n", (unsigned long long)blocks, K, (unsigned long long)h);
    if (argc > 4) { FILE *f = fopen(argv[4], "wb"); for (uint64_t i = 0; i < n; i++) { uint32_t pgi = (uint32_t)(list[i] / WPP); fwrite(&pgi, 4, 1, f); } fclose(f); }
}
