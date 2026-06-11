# Makefile — bench_stencil_oversub
#
# 2D 5-point stencil sized for VRAM-oversubscription experiments.
# Typical N values and working-set sizes (two float grids = 2 * N^2 * 4 bytes):
#   N = 51200  ->  ~20.97 GB  (~1.31x oversubscription of 16 GB VRAM)
#   N = 55000  ->  ~24.20 GB  (~1.51x oversubscription)
#   N = 63000  ->  ~31.75 GB  (~1.98x oversubscription)
#
# Usage after build:
#   ./bench_stencil_oversub 51200
#   ./bench_stencil_oversub 55000
#   ./bench_stencil_oversub 63000 20

NVCC      := nvcc
NVCCFLAGS := -O3 -arch=sm_75

TARGET := bench_stencil_oversub

.PHONY: all clean

all: $(TARGET)

$(TARGET): bench_stencil_oversub.cu
	$(NVCC) $(NVCCFLAGS) -o $@ $<

clean:
	rm -f $(TARGET)
