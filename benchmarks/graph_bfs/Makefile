# Makefile — bench_graph_bfs
#
# Frontier-based level-synchronous BFS on R-MAT graphs in CSR format.
# All arrays (row_ptr, col_idx, visited, frontier, next_frontier) use
# cudaMallocManaged to drive UVM page faults.
#
# Typical invocations:
#   ./bench_graph_bfs 24          # 2^24 = ~16M vertices, edge_factor=16 -> ~268M edges
#   ./bench_graph_bfs 25          # 2^25 = ~33M vertices
#
# Working-set sizes (CSR only, row_ptr + col_idx, both long long):
#   log2=24:  (16M+1)*8 + 268M*8 ~= 2.3 GB CSR  + BFS arrays ~0.5 GB
#   log2=25:  (33M+1)*8 + 536M*8 ~= 4.6 GB CSR  + BFS arrays ~1.0 GB
# For 20-32 GB targets, combine with multiple concurrent streams or
# increase edge_factor in the source (EDGE_FACTOR constant).

NVCC      := nvcc
# std=c++14 needed for std::sort with a lambda-comparable struct
NVCCFLAGS := -O3 -arch=sm_75 -std=c++14

TARGET := bench_graph_bfs

.PHONY: all clean

all: $(TARGET)

$(TARGET): bench_graph_bfs.cu
	$(NVCC) $(NVCCFLAGS) -o $@ $<

clean:
	rm -f $(TARGET)
