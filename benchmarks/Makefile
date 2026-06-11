# Makefile — SpecAsync-UVM benchmark suite (core benchmarks)
#
# Targets:
#   bench_stream     STREAM Triad (3-array float, UVM)
#   bench_sgemm      cuBLAS SGEMM (NxN float, UVM)
#   bench_stencil    2D 5-point stencil (NxN float, 20 iters, UVM)
#   bench_cufft      1D C2C FFT (N complex floats, UVM)
#
# Architecture: sm_75 = Turing (Tesla T4, RTX 2000 series)

NVCC    := nvcc
NVCCFLAGS := -O3 -arch=sm_75

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
