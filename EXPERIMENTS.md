# Phase B Experiment Execution Guide

Step-by-step instructions for running Phase 2 experiments on the GPU box.
This file assumes the phase2 branch is already cloned and you are on a machine
with Linux 6.14, NVIDIA Open Kernel Modules v580.95.05, and CUDA toolkit.

---

## 0. Repository and build workflow

The repository uses the **patch-only** pattern:
- The modified driver source is **not** stored as an extracted tree.
- The full diff is in `driver/patches/specasync_uvm_v580.95.05.patch`, stored
  via Git LFS (~190 MB).
- The upstream source tree (nvidia-open-580.95.05) must be obtained separately
  and the patch applied to it.

**Upstream source:** NVIDIA Open Kernel Modules v580.95.05
Obtain from: https://github.com/NVIDIA/open-gpu-kernel-modules/releases/tag/580.95.05
(tag `580.95.05`, tarball `nvidia-open-gpu-kernel-modules-580.95.05.tar.gz`)

The patch applies at the top of the extracted tree with `-p1`.

---

## 1. Clone and pull LFS

```bash
git clone https://github.com/rayanw36/specasync-uvm.git SpecAsync-UVM
cd SpecAsync-UVM
git checkout claude/specasync-phase2-instrumentation-3r7Jc
git lfs pull        # fetches the 190 MB patch file
```

Verify:
```bash
file driver/patches/specasync_uvm_v580.95.05.patch
# Should say: unified diff output, ...
# NOT: ASCII text (that would mean LFS pointer still present)
```

---

## 2. Apply Phase 2 driver additions

The Phase 2 code in `driver/src/` contains:
- `specasync_telemetry.h` — struct definitions and ring-buffer inline functions
- `specasync_debugfs.c` — debugfs interface, module params, ring-buffer alloc
- `specasync_faults_instrumentation.c` — reference implementation for T0–T4
  instrumentation, prediction policies, residency offload

These files are NOT yet applied to the upstream source tree. Before building,
complete the integration steps in `driver/PHASE_B_INTEGRATION.md` (§1–§9).
Each section has grep commands to find the exact integration points.

**Quick summary of integration work:**
1. Copy `driver/src/specasync_debugfs.c` into `kernel-open/nvidia-uvm/`
2. Add `nvidia-uvm-objs += specasync_debugfs.o` to the Kbuild
3. Copy `driver/src/specasync_telemetry.h` into `kernel-open/nvidia-uvm/`
4. In `uvm_gpu_replayable_faults.c`: add T0–T4 timestamps, spec_hits check,
   enqueue call, policy dispatch — following Section 2–5 of the .c reference file
5. In `uvm_va_space.h`: add `specasync_pred` field
6. In `uvm_va_space.c`: alloc/free the per-VA-space prediction state

Expected integration time: 2–4 hours for a developer familiar with the UVM source.

---

## 3. Build the modified nvidia_uvm module

```bash
# Obtain upstream source (adjust URL/path as needed)
wget https://github.com/NVIDIA/open-gpu-kernel-modules/archive/refs/tags/580.95.05.tar.gz
tar xf 580.95.05.tar.gz
cd open-gpu-kernel-modules-580.95.05

# Apply Phase 1 patch
patch -p1 < ~/SpecAsync-UVM/driver/patches/specasync_uvm_v580.95.05.patch

# Apply Phase 2 additions (after completing PHASE_B_INTEGRATION.md steps)
# ... (copy files, edit sources as described above) ...

# Build
make modules -j$(nproc) 2>&1 | tee ~/SpecAsync-UVM/results/build.log
```

---

## 4. Install and verify the module

```bash
KVER=$(uname -r)
MODDIR="/lib/modules/$KVER/kernel/nvidia-580-open"
sudo cp nvidia-uvm.ko "$MODDIR/nvidia-uvm.ko"
sudo depmod -a
sudo modprobe -r nvidia_uvm
sudo modprobe nvidia_uvm \
    specasync_log_enabled=1 \
    specasync_policy=1 \
    specasync_offload_depth=0

# Verify it's YOUR build (not the stock module)
cat /sys/module/nvidia_uvm/srcversion
# Save this hash — you'll need it for SPECASYNC_SRCVERSION in the run harness
```

Verify debugfs entries exist:
```bash
ls /sys/kernel/debug/nvidia_uvm/specasync*
# Expected: specasync_clear  specasync_log  specasync_worker_log
```

---

## 5. Build benchmarks

```bash
cd ~/SpecAsync-UVM/benchmarks
make -j$(nproc)
make -C stencil_oversub
make -C graph_bfs
```

Validate timing ballpark (single trial each):
```bash
./bench_stream  134217728  # expect ~88 ms
./bench_sgemm   8192       # expect ~152 ms
./bench_stencil 8192       # expect ~28.7 ms
./bench_cufft   67108864   # expect ~23.4 ms
```

Acceptable range: ±20% vs `results/baseline/robust_results_baseline.csv` means.
See `benchmarks/RECONSTRUCTION_NOTES.md` for per-benchmark targets.

---

## 6. Run the full experiment sweep

```bash
cd ~/SpecAsync-UVM/benchmarks

# Set the srcversion hash from step 4:
export SPECASYNC_SRCVERSION="<hash from step 4>"

# Dry run first to check everything is wired:
sudo bash run_all_experiments.sh --dry-run

# Full run (will take several hours):
sudo bash run_all_experiments.sh 2>&1 | tee /tmp/specasync_run.log

# With --force to rerun if needed:
sudo bash run_all_experiments.sh --force --policy 1,2,3
```

Results land in:
```
results/
  p0_d0/   (speculation disabled — baseline)
  p1_d0/   (adjacent-page, metadata-only)
  p1_d1/   (adjacent-page, residency offload)
  p2_d0/   (stride, metadata-only)
  p2_d1/   (stride, residency offload)
  p3_d0/   (markov, metadata-only)
  p3_d1/   (markov, residency offload)
  summary/ (generated by cost_benefit.py)
  run_<timestamp>.log
```

---

## 7. Oracle policy run (optional)

To measure the upper bound of speculation benefit:
```bash
# Collect a fault trace for one benchmark (using existing nsys tooling):
nsys profile --trace=cuda --cuda-um-gpu-page-faults=true \
  --output=/tmp/oracle_trace ./bench_cufft 67108864
# Extract fault addresses as u64 binary:
python3 benchmarks/tools/extract_fault_trace.py /tmp/oracle_trace.nsys-rep \
  > /tmp/oracle_cufft_64m.bin

# Load oracle at module init:
sudo modprobe -r nvidia_uvm
sudo modprobe nvidia_uvm \
  specasync_policy=4 \
  specasync_oracle_trace_path=/tmp/oracle_cufft_64m.bin

# Run one benchmark with oracle:
sudo bash run_all_experiments.sh --policy 4 --force
```

Note: `extract_fault_trace.py` is not yet implemented (deferred to Phase B).
The oracle policy requires a binary file of u64 fault addresses. You can
generate this from nsys SQLite output or by adding a kernel-side trace dump.

---

## 8. Analyze results

```bash
cd ~/SpecAsync-UVM
python3 benchmarks/tools/cost_benefit.py
# Outputs: results/summary/cost_benefit.md + results/summary/phase_breakdown.pdf

# For per-benchmark plots using Phase 1 analysis scripts:
cd benchmarks
python3 analyze_results_3way.py
```

---

## 9. Push results to branch

```bash
cd ~/SpecAsync-UVM
git add results/
git commit -m "Phase 2 results: $(date +%Y%m%d)"
git push origin claude/specasync-phase2-instrumentation-3r7Jc
```

---

## Troubleshooting

**debugfs files missing:** Module loaded but `specasync_*` files absent —
`specasync_debugfs_init()` may not have been called. Check
`dmesg | grep specasync` for init log line.

**All batches show spec_hits=0:** Hit table may not be wired. Check that
`specasync_hit_table_consume()` is actually called in service_fault_batch()
(§3 of PHASE_B_INTEGRATION.md).

**enqueue_overhead_ns always 0:** Enqueue overhead accumulation is in the
`specasync_enqueue()` function body. Verify it is called with the `sa_rec`
pointer (not a copy).

**WARN: srcversion mismatch:** You are running the stock NVIDIA driver.
Reload with `sudo modprobe -r nvidia_uvm && sudo modprobe nvidia_uvm` after
installing the SpecAsync build.

**Parser assertion failure:** Struct sizes changed during integration. Run
`python3 benchmarks/tools/synthetic_test.py` — it will immediately show any
size mismatch. Fix by checking BUILD_BUG_ON assertions from §8 of
PHASE_B_INTEGRATION.md.
