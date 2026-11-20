// C22 workloads: the R-MAT generator, self-loop fix and dedup of benchmarks/graph_bfs/bench_graph_bfs.cu (copied verbatim) to count the unique edges of the log2_vertices graph.
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <algorithm>
static const double RMAT_A = 0.57;
static const double RMAT_B = 0.19;
static const double RMAT_C = 0.19;
/* d = 1 - a - b - c = 0.05 */

/* Fast per-edge PRNG: simple 64-bit LCG */
static inline uint64_t lcg_next(uint64_t *state)
{
    *state = (*state) * 6364136223846793005ULL + 1442695040888963407ULL;
    return *state;
}

static inline double lcg_double(uint64_t *state)
{
    return (double)(lcg_next(state) >> 11) / (double)(1ULL << 53);
}

/*
 * Generate one R-MAT edge (src, dst) for a graph with 2^log2_n vertices.
 * seed is unique per edge.
 */
static void rmat_edge(uint64_t seed, int log2_n,
                      long long *src_out, long long *dst_out)
{
    uint64_t rng = seed ^ 0xdeadbeefcafe1234ULL;
    long long src = 0, dst = 0;
    long long half = (long long)1 << (log2_n - 1);

    for (int d = log2_n - 1; d >= 0; d--) {
        double r = lcg_double(&rng);
        long long bit = (long long)1 << d;
        if (r < RMAT_A) {
            /* top-left: src unchanged, dst unchanged */
        } else if (r < RMAT_A + RMAT_B) {
            /* top-right */
            dst |= bit;
        } else if (r < RMAT_A + RMAT_B + RMAT_C) {
            /* bottom-left */
            src |= bit;
        } else {
            /* bottom-right */
            src |= bit;
            dst |= bit;
        }
    }
    *src_out = src;
    *dst_out = dst;
    (void)half; /* suppress warning */
}

/* ------------------------------------------------------------------ */
/* Edge comparison for sorting                                          */
/* ------------------------------------------------------------------ */
struct Edge {
    long long src;
    long long dst;
};

static bool edge_less(const Edge &a, const Edge &b)
{
    if (a.src != b.src) return a.src < b.src;
    return a.dst < b.dst;
}

int main(int argc, char **argv) {
    int log2_n = atoi(argv[1]); long long V = 1LL << log2_n, T = V * 16;
    Edge *e = (Edge *)malloc(T * sizeof(Edge));
    for (long long i = 0; i < T; i++) { long long s, d; rmat_edge((uint64_t)i, log2_n, &s, &d); if (s == d) d = (d + 1) % V; e[i].src = s; e[i].dst = d; }
    std::sort(e, e + T, edge_less);
    long long n = 0; for (long long i = 0; i < T; i++) if (i == 0 || e[i].src != e[i-1].src || e[i].dst != e[i-1].dst) e[n++] = e[i];
    printf("log2_n=%d vertices=%lld edges_target=%lld edges_unique=%lld\n", log2_n, V, T, n);
}
