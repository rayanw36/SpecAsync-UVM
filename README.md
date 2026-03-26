# SpecAsync-UVM

This repository contains the experimental artifacts for **SpecAsync-UVM**, a prototype modification to NVIDIA Unified Virtual Memory (UVM) replayable-fault handling.
The idea is to decouple speculative preparation work from the GPU fault critical path by offloading it to a background kernel worker thread.

## Repository Layout
- `driver/patches/` : patch against NVIDIA Open Kernel Modules v580.95.05 (UVM component).
- `driver/scripts/` : helper scripts (Linux) to build/install/verify the modified `nvidia_uvm` module.
- `benchmarks/` : CUDA microbenchmarks (STREAM, SGEMM, Stencil, cuFFT) + automation scripts.
- `results/` : CSVs and plots used in the paper.
- `paper/` : manuscript + figures (not included now).

## Requirements (Linux testbed)
- NVIDIA Open Kernel Modules **v580.95.05**
- Linux kernel **6.14.x**
- CUDA toolkit + Nsight Systems (`nsys`)
- GPU supporting UVM (tested on RTX 5070 Ti-class)

## Reproducing Driver Build (Linux)
1. Obtain NVIDIA Open Kernel Modules v580.95.05 source.
2. Apply patch:
   ```bash
   cd nvidia-580.95.05
   patch -p1 < ../SpecAsync-UVM/driver/patches/specasync_uvm_v580.95.05.patch
   ```

3. Build:
    ```bash
    make modules -j"$(nproc)"
    ```


4. Install the rebuilt UVM module (example path; adjust for your distro):
```bash
KVER=$(uname -r)
MODDIR="/lib/modules/$KVER/kernel/nvidia-580-open"
sudo cp ./nvidia-uvm.ko "$MODDIR/nvidia-uvm.ko"
sudo depmod -a
sudo modprobe -r nvidia_uvm
sudo modprobe nvidia_uvm
```

Verify the loaded module is YOUR build
```bash
cat /sys/module/nvidia_uvm/srcversion
modinfo nvidia_uvm | grep srcversion
```

Running Benchmarks

See benchmarks/README_benchmarks.md.

Notes

This is a research prototype for evaluation only.