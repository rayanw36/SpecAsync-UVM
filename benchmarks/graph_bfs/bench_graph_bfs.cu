/*
 * bench_graph_bfs.cu — Frontier-based level-synchronous BFS in CSR format
 *
 * Graph generation via R-MAT (Kronecker-style):
 *   Parameters: a=0.57, b=0.19, c=0.19, d=0.05
 *
 * Usage: ./bench_graph_bfs <log2_vertices> [target_gb]
 *   log2_vertices = 24  ->  ~16M vertices
 *   log2_vertices = 25  ->  ~33M vertices
 *   target_gb is informational only (actual size set by log2_vertices)
 *
 * The CSR arrays (row_ptr, col_idx) and BFS arrays (visited, level,
 * frontier, next_frontier) are all allocated with cudaMallocManaged,
 * driving UVM page faults throughout the traversal.
 *
 * Output (parsed by run_robust.py):
 *   [RESULT] Time: X.XX ms
 *   Bandwidth: X.XX GB/s
 *
 * Bandwidth formula: edges_traversed * 8 bytes / time_s / 1e9
 *   (each traversed edge reads one col_idx entry [4 bytes] and one
 *    visited entry [4 bytes], approximate but consistent metric)
 *
 * Stderr info line:
 *   [INFO] Vertices=N Edges=M Visited=K
 *
 * Build: nvcc -O3 -arch=sm_89 -o bench_graph_bfs bench_graph_bfs.cu
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdint.h>
#include <algorithm>
#include <cuda_runtime.h>

/* ------------------------------------------------------------------ */
/* Error-checking macro                                                 */
/* ------------------------------------------------------------------ */
#define CUDA_CHECK(call)                                                       \
    do {                                                                       \
        cudaError_t _err = (call);                                             \
        if (_err != cudaSuccess) {                                             \
            fprintf(stderr, "CUDA error at %s:%d -- %s\n",                    \
                    __FILE__, __LINE__, cudaGetErrorString(_err));             \
            exit(EXIT_FAILURE);                                                \
        }                                                                     \
    } while (0)

/* ------------------------------------------------------------------ */
/* Wall-clock helper                                                    */
/* ------------------------------------------------------------------ */
static double now_sec(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

/* ------------------------------------------------------------------ */
/* R-MAT edge generation                                               */
/* ------------------------------------------------------------------ */
/*
 * Simple recursive R-MAT partitioning.
 * For each edge, repeatedly bisect the adjacency matrix using
 * a=0.57, b=0.19, c=0.19, d=0.05 until we reach a single cell.
 *
 * Uses a linear-congruential PRNG seeded per edge for reproducibility.
 */

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

/* ------------------------------------------------------------------ */
/* BFS kernels                                                          */
/* ------------------------------------------------------------------ */

/*
 * expand_frontier: for each vertex in current frontier, push unvisited
 * neighbours into next_frontier using atomicCAS on visited[].
 *
 * row_ptr[v]..row_ptr[v+1]-1 gives the range of neighbours in col_idx[].
 * visited[v] == -1 means unvisited; otherwise holds the BFS level.
 * next_frontier_size is incremented atomically.
 */
__global__ void expand_frontier(
    const long long  * __restrict__ row_ptr,
    const long long  * __restrict__ col_idx,
    int              * __restrict__ visited,      /* -1 = unvisited */
    const long long  * __restrict__ frontier,
    long long          frontier_size,
    long long        * __restrict__ next_frontier,
    int              * __restrict__ next_frontier_size,
    int                current_level)
{
    long long tid = (long long)blockIdx.x * blockDim.x + threadIdx.x;
    long long stride = (long long)gridDim.x * blockDim.x;

    for (long long fi = tid; fi < frontier_size; fi += stride) {
        long long v = frontier[fi];
        long long start = row_ptr[v];
        long long end   = row_ptr[v + 1];

        for (long long e = start; e < end; e++) {
            long long nb = col_idx[e];
            /* Try to mark nb as visited */
            int old = atomicCAS(&visited[(int)nb], -1, current_level + 1);
            if (old == -1) {
                /* We claimed nb; add to next frontier */
                int pos = atomicAdd(next_frontier_size, 1);
                next_frontier[pos] = nb;
            }
        }
    }
}

/* ------------------------------------------------------------------ */
/* main                                                                 */
/* ------------------------------------------------------------------ */
int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <log2_vertices> [target_gb]\n", argv[0]);
        return EXIT_FAILURE;
    }

    int log2_n = atoi(argv[1]);
    if (log2_n < 4 || log2_n > 28) {
        fprintf(stderr, "log2_vertices must be in [4, 28]\n");
        return EXIT_FAILURE;
    }

    /* Number of vertices and edges */
    long long num_vertices = (long long)1 << log2_n;
    /* Edge factor ~16 edges/vertex is a common Graph500 default */
    long long edge_factor  = 16;
    long long num_edges_target = num_vertices * edge_factor;

    /* ---------------------------------------------------------------- */
    /* Generate R-MAT edges on the host                                  */
    /* ---------------------------------------------------------------- */
    Edge *edges = (Edge *)malloc(num_edges_target * sizeof(Edge));
    if (!edges) {
        fprintf(stderr, "Failed to allocate edge buffer (%lld edges)\n",
                num_edges_target);
        return EXIT_FAILURE;
    }

    for (long long i = 0; i < num_edges_target; i++) {
        long long s, d;
        rmat_edge((uint64_t)i, log2_n, &s, &d);
        /* Remove self-loops */
        if (s == d) d = (d + 1) % num_vertices;
        edges[i].src = s;
        edges[i].dst = d;
    }

    /* Sort and deduplicate */
    std::sort(edges, edges + num_edges_target, edge_less);
    long long num_edges = 0;
    for (long long i = 0; i < num_edges_target; i++) {
        if (i == 0 || edges[i].src != edges[i-1].src ||
                      edges[i].dst != edges[i-1].dst) {
            edges[num_edges++] = edges[i];
        }
    }

    /* ---------------------------------------------------------------- */
    /* Build CSR in managed memory                                       */
    /* ---------------------------------------------------------------- */
    long long *row_ptr = NULL;
    long long *col_idx = NULL;

    CUDA_CHECK(cudaMallocManaged(&row_ptr,
                                 (num_vertices + 1) * sizeof(long long)));
    CUDA_CHECK(cudaMallocManaged(&col_idx,
                                 num_edges * sizeof(long long)));

    /* Count degree per vertex */
    memset(row_ptr, 0, (num_vertices + 1) * sizeof(long long));
    for (long long i = 0; i < num_edges; i++) {
        row_ptr[edges[i].src + 1]++;
    }
    /* Prefix sum */
    for (long long v = 1; v <= num_vertices; v++) {
        row_ptr[v] += row_ptr[v - 1];
    }
    /* Fill col_idx */
    long long *tmp_ptr = (long long *)malloc((num_vertices + 1) * sizeof(long long));
    memcpy(tmp_ptr, row_ptr, (num_vertices + 1) * sizeof(long long));
    for (long long i = 0; i < num_edges; i++) {
        long long v = edges[i].src;
        col_idx[tmp_ptr[v]++] = edges[i].dst;
    }
    free(tmp_ptr);
    free(edges);

    /* ---------------------------------------------------------------- */
    /* BFS arrays (managed memory)                                       */
    /* ---------------------------------------------------------------- */
    int      *visited            = NULL;
    long long *frontier          = NULL;
    long long *next_frontier     = NULL;
    int       *next_frontier_size_dev = NULL;

    CUDA_CHECK(cudaMallocManaged(&visited,
                                 num_vertices * sizeof(int)));
    /*
     * Worst-case frontier is all vertices. In practice frontiers are
     * much smaller, but we allocate conservatively.
     */
    CUDA_CHECK(cudaMallocManaged(&frontier,
                                 num_vertices * sizeof(long long)));
    CUDA_CHECK(cudaMallocManaged(&next_frontier,
                                 num_vertices * sizeof(long long)));
    CUDA_CHECK(cudaMallocManaged(&next_frontier_size_dev,
                                 sizeof(int)));

    /* Initialise visited to -1 (unvisited) */
    for (long long i = 0; i < num_vertices; i++) {
        visited[i] = -1;
    }

    /* Report managed-memory footprint to stderr */
    double csr_gb = ((double)(num_vertices + 1) * sizeof(long long) +
                     (double)num_edges           * sizeof(long long)) / 1e9;
    double bfs_gb = ((double)num_vertices * sizeof(int) +
                     2.0 * (double)num_vertices * sizeof(long long) +
                     sizeof(int)) / 1e9;
    fprintf(stderr,
            "[INFO] Vertices=%lld Edges=%lld CSR=%.2f GB BFS_arrays=%.2f GB\n",
            num_vertices, num_edges, csr_gb, bfs_gb);

    /* ---------------------------------------------------------------- */
    /* BFS from vertex 0                                                 */
    /* ---------------------------------------------------------------- */
    const int THREADS = 256;
    const int MAX_BLOCKS = 65535;

    /* Mark source vertex */
    visited[0] = 0;
    frontier[0] = 0;
    long long frontier_size = 1;

    long long edges_traversed = 0;
    long long visited_count   = 1;

    CUDA_CHECK(cudaDeviceSynchronize());
    double t0 = now_sec();

    int level = 0;
    while (frontier_size > 0) {
        *next_frontier_size_dev = 0;
        CUDA_CHECK(cudaDeviceSynchronize()); /* flush host write */

        int blocks = (int)((frontier_size + THREADS - 1) / THREADS);
        if (blocks > MAX_BLOCKS) blocks = MAX_BLOCKS;

        expand_frontier<<<blocks, THREADS>>>(
            row_ptr, col_idx,
            visited,
            frontier, frontier_size,
            next_frontier, next_frontier_size_dev,
            level);
        CUDA_CHECK(cudaGetLastError());
        CUDA_CHECK(cudaDeviceSynchronize());

        /* Count edges traversed this level (sum of degrees) */
        for (long long fi = 0; fi < frontier_size; fi++) {
            long long v = frontier[fi];
            edges_traversed += row_ptr[v + 1] - row_ptr[v];
        }

        long long next_size = (long long)*next_frontier_size_dev;
        visited_count += next_size;

        /* Swap frontier buffers */
        long long *tmp   = frontier;
        frontier          = next_frontier;
        next_frontier     = tmp;
        frontier_size     = next_size;
        level++;
    }

    CUDA_CHECK(cudaDeviceSynchronize());
    double t1 = now_sec();
    /* ---------------------------------------------------------------- */

    double time_ms = (t1 - t0) * 1e3;
    double time_s  = t1 - t0;
    /* Bandwidth: each traversed edge touches col_idx[4B] + visited[4B] */
    double bw_gbs  = ((double)edges_traversed * 8.0) / time_s / 1e9;

    printf("[RESULT] Time: %.2f ms\nBandwidth: %.2f GB/s\n", time_ms, bw_gbs);
    fprintf(stderr,
            "[INFO] Vertices=%lld Edges=%lld Visited=%lld\n",
            num_vertices, num_edges, visited_count);

    CUDA_CHECK(cudaFree(row_ptr));
    CUDA_CHECK(cudaFree(col_idx));
    CUDA_CHECK(cudaFree(visited));
    CUDA_CHECK(cudaFree(frontier));
    CUDA_CHECK(cudaFree(next_frontier));
    CUDA_CHECK(cudaFree(next_frontier_size_dev));

    return EXIT_SUCCESS;
}
