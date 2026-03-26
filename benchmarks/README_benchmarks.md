# Benchmarks

This folder contains CUDA benchmarks using managed memory (`cudaMallocManaged`) to trigger UVM replayable faults.

## Build (Linux)
Example:
```bash
nvcc -O3 -lcublas -lcufft bench_sgemm.cu -o bench_sgemm
nvcc -O3 bench_stream.cu -o bench_stream
nvcc -O3 bench_stencil.cu -o bench_stencil
nvcc -O3 -lcufft bench_cufft.cu -o bench_cufft
```

# Run robust suite

```
Run robust suite
```

# Analyze results

Two-way comparison:
```
python3 analyze_results.py
```

Three-way comparison:
```bash
python3 analyze_results_3way.py
```

