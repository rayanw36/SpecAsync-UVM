# Makefile — SpecAsync-UVM benchmark suite (core benchmarks)
#
# Targets:
#   bench_stream     STREAM Triad (3-array float, UVM)
#   bench_sgemm      cuBLAS SGEMM (NxN float, UVM)
#   bench_stencil    2D 5-point stencil (NxN float, 20 iters, UVM)
#   bench_cufft      1D C2C FFT (N complex floats, UVM)
#
# Architecture: sm_89 = Ada Lovelace (RTX 4000/5000 series)
# Adjust -arch= for other hardware (sm_80 = A100, sm_86 = RTX 3000 series)

NVCC    := nvcc
NVCCFLAGS := -O3 -arch=sm_89

TARGETS := bench_stream bench_sgemm bench_stencil bench_cufft

.PHONY: all clean

all: $(TARGETS)

bench_stream: bench_stream.cu
	$(NVCC) $(NVCCFLAGS) -o $@ $<

bench_sgemm: bench_sgemm.cu
	$(NVCC) $(NVCCFLAGS) -o $@ $< -lcublas

bench_stencil: bench_stencil.cu
	$(NVCC) $(NVCCFLAGS) -o $@ $<

bench_cufft: bench_cufft.cu
	$(NVCC) $(NVCCFLAGS) -o $@ $< -lcufft

clean:
	rm -f $(TARGETS)
