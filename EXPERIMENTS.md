# Phase B Experiment Reproduction Guide

Full step-by-step instructions to reproduce SpecAsync-UVM Phase B results on
an AWS g4dn.xlarge (Tesla T4, sm_75) running NVIDIA driver 595.71.05.

---

## Environment

| Item | Value |
|------|-------|
| Instance | AWS g4dn.xlarge |
| GPU | Tesla T4 (sm_75, 16 GiB VRAM) |
| Kernel | 6.17.0-1017-aws |
| Driver | NVIDIA 595.71.05 (nvidia-uvm) |
| CUDA | 12.0 (nvcc at `/usr/bin/nvcc`) |
| DLAMI | Deep Learning AMI (Ubuntu) |
| EBS | `~/SpecAsync-UVM/` — persistent across stop/start |
| NVMe | `/opt/dlami/nvme/work/` — **wiped on instance stop** |

---

## Step 0: Clone and prepare

```bash
git clone https://github.com/rayanw36/specasync-uvm.git ~/SpecAsync-UVM
cd ~/SpecAsync-UVM
git checkout phaseB-v595-port
```

The patch file is at `driver/patches/specasync_uvm_v595.71.05.patch` (real
unified diff, not LFS pointer).

---

## Step 1: Copy source and apply patch

The patch uses absolute-path headers (`--- /usr/src/nvidia-595.71.05/...`)
and must be applied with `-p4`:

```bash
# Stock source is pre-installed at:
ls /usr/src/nvidia-595.71.05/nvidia-uvm/

# Create work directory on NVMe:
sudo mkdir -p /opt/dlami/nvme/work
sudo cp -r /usr/src/nvidia-595.71.05 /opt/dlami/nvme/work/nvidia-595.71.05-specasync

# Apply patch:
cd /opt/dlami/nvme/work/nvidia-595.71.05-specasync
patch -p4 < ~/SpecAsync-UVM/driver/patches/specasync_uvm_v595.71.05.patch
```

---

## Step 2: Build the modified module

```bash
KVER=$(uname -r)
WORK_SRC="/opt/dlami/nvme/work/nvidia-595.71.05-specasync/nvidia-uvm"
cd "${WORK_SRC}"
make -C /lib/modules/${KVER}/build M="${WORK_SRC}" \
    -f "${WORK_SRC}/nvidia-uvm-sources.Kbuild" modules 2>&1 | tee build.log
```

Or use the convenience script:
```bash
sudo bash ~/SpecAsync-UVM/scripts/rebuild_and_reload.sh
```

---

## Step 3: Safe module hot-swap

**IMPORTANT:** Never touch `nvidia.ko`, `nvidia-modeset`, or `nvidia-drm`.

```bash
# Verify stock backup exists:
ls ~/SpecAsync-UVM/driver/stock_backup/nvidia-uvm.ko.stock
# Stock srcversion: 85A79790636BBD99BA3E43B

# Stop persistenced and hot-swap:
sudo systemctl stop nvidia-persistenced
sudo rmmod nvidia_uvm
sudo insmod /opt/dlami/nvme/work/nvidia-595.71.05-specasync/nvidia-uvm/nvidia-uvm.ko

# Verify our build is loaded:
cat /sys/module/nvidia_uvm/srcversion
# Must NOT be: 85A79790636BBD99BA3E43B (that is the stock module)

# Save the srcversion for the run harness:
export SPECASYNC_SRCVERSION="$(cat /sys/module/nvidia_uvm/srcversion)"

sudo systemctl start nvidia-persistenced
```

Restore stock module if anything goes wrong:
```bash
sudo rmmod nvidia_uvm
sudo insmod ~/SpecAsync-UVM/driver/stock_backup/nvidia-uvm.ko.stock
```

---

## Step 4: Verify debugfs

```bash
ls /sys/kernel/debug/specasync_log          # batch telemetry
ls /sys/kernel/debug/specasync_worker_log   # per-work-item telemetry
ls /sys/kernel/debug/specasync_clear        # write any byte to reset
ls /sys/kernel/debug/specasync_fault_trace  # demand-fault VA trace (oracle)
dmesg | grep specasync | tail -5
# Expect: specasync: init OK  log_enabled=1 policy=1 offload_depth=0
```

---

## Step 5: Build benchmarks

```bash
cd ~/SpecAsync-UVM/benchmarks
make -j$(nproc)
make -C stencil_oversub
make -C graph_bfs
```

Smoke-test (should print `[RESULT] Time: ... ms`):
```bash
./bench_sgemm   8192
./bench_stencil 8192
./bench_stream  67108864
./bench_cufft   67108864
./graph_bfs/bench_graph_bfs 20
./stencil_oversub/bench_stencil_oversub 1000 5 0
```

---

## Step 6: Policy sweep (p0–p3)

```bash
cd ~/SpecAsync-UVM/benchmarks
export SPECASYNC_SRCVERSION="<hash from step 3>"

# Dry run first:
sudo bash run_all_experiments.sh --dry-run

# Full sweep (4 policies × 6 benchmarks × 3 sizes × 20 runs ≈ 7–8 hours):
sudo bash run_all_experiments.sh 2>&1 | tee ~/SpecAsync-UVM/results/phaseB/logs/sweep_run1.log &
echo "Sweep PID: $!"
```

Results go to `results/p{0,1,2,3}_d0/`.

**Benchmark configuration:**
| Benchmark | Sizes | Notes |
|-----------|-------|-------|
| SGEMM | 8192, 16384, 24000 | N×N FP32 gemm |
| Stencil | 8192, 16384, 24000 | 2D 5-pt stencil |
| STREAM | 67M, 134M, 268M, 537M | triad bandwidth |
| cuFFT | 64M, 128M, 256M floats | cufftExecC2C |
| GraphBFS | log₂=22,23,24 | BFS on random graph |
| Stencil_OvSub | 25000 20 11264, 28300 20 11264, 32000 20 11264 | 1.25×/1.6×/2.05× oversub (11 GiB balloon) |

---

## Step 7: Oracle trace collection (after step 6 + rebuild)

After the policy sweep completes, rebuild the module (step 2–3) to get the
clean `clear_write` fix and the `specasync_fault_trace` debugfs file.

```bash
# Collect demand-fault VA traces:
sudo bash ~/SpecAsync-UVM/scripts/collect_oracle_traces.sh

# Run oracle (p4) experiments:
sudo bash ~/SpecAsync-UVM/scripts/oracle_sweep.sh
```

Oracle traces go to `~/SpecAsync-UVM/oracles/{bench}/{size}/oracle_trace.bin`.
Oracle results go to `results/p4_d0/`.

---

## Step 8: Analyze results

```bash
cd ~/SpecAsync-UVM

# Aggregate timing + telemetry, produce plots and SUMMARY.md:
python3 benchmarks/tools/analyze_phaseB.py

# Cost-benefit table and phase-breakdown chart:
python3 benchmarks/tools/cost_benefit.py

# Outputs:
#   results/phaseB/SUMMARY.md
#   results/phaseB/phaseB_timing.csv
#   results/phaseB/phaseB_telemetry.csv
#   results/phaseB/plots/
#   results/summary/cost_benefit.md
#   results/summary/phase_breakdown.pdf
```

---

## Step 9: Commit and push

```bash
cd ~/SpecAsync-UVM
git add benchmarks/tools/ scripts/ EXPERIMENTS.md results/phaseB/
git commit -m "Phase B: v595 port, T4 sweep results, oracle infrastructure"
git push origin phaseB-v595-port
```

---

## Module parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `specasync_log_enabled` | 1 | Enable telemetry ring buffers |
| `specasync_policy` | 1 | 0=disabled, 1=adjacent, 2=stride, 3=markov, 4=oracle |
| `specasync_offload_depth` | 0 | Async prefetch depth (0=sync only) |
| `specasync_trace_faults` | 0 | Enable demand-fault VA trace ring |
| `specasync_oracle_trace_path` | NULL | Path to oracle trace binary |

Change at runtime (no reload needed):
```bash
echo 2 | sudo tee /sys/module/nvidia_uvm/parameters/specasync_policy
```

---

## Troubleshooting

**`rmmod nvidia_uvm` fails:** GPU is in use. Stop all CUDA processes first
(`fuser /dev/nvidia*`), then retry.

**debugfs files missing:** `specasync_debugfs_init()` not called, or
`/sys/kernel/debug` not mounted. Check `dmesg | grep specasync`.

**Hit rate = 0 for p1/p2/p3:** Worker thread not running or enqueue not wired.
Check `dmesg` for specasync worker-related messages.

**Telemetry shows cross-session garbage (lat >> 1 s):** Ring buffer not cleared
between sessions. Write `echo 1 > /sys/kernel/debug/specasync_clear`. Fixed in
the v595 rebuild (clear_write now zeroes the entire ring buffer).

**OOM in GraphBFS:** log₂ ≥ 25 requires > 4 GB host memory for edge buffer.
Use log₂ ≤ 24.

**Stencil_OvSub too slow:** Each run takes ~38 s for N=25000. This is expected;
the benchmark stresses the full UVM demand-paging path.
