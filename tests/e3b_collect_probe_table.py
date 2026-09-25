#!/usr/bin/env python3
"""Gate E3b: first-touch table for tests/group_probe, collected exactly as the
workload tables are (verified module, policy 0, log off, prefetch off,
trace_faults=1, setarch -R), with the distinct-page assertion = 8
(group_probe touches N = 8 pages inside one 2 MB block)."""
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import e09b_runner as R  # noqa: E402
VER_KO = f"{R.REPO}/driver/build/595.91.07/nvidia-uvm-specasync-NEW-e0.9a2-fixed.ko"
tables = sys.argv[1]; os.makedirs(tables, exist_ok=True)
before = R.dmesg_lines()
if R.read_sys("/sys/module/nvidia_uvm/refcnt") not in (None, "0"): sys.exit("STOP: refcnt != 0")
if R.read_sys("/sys/module/nvidia_uvm/refcnt") is not None and R.sh(["sudo", "-n", "rmmod", "nvidia_uvm"]).returncode:
    sys.exit("STOP: rmmod failed")
r = R.sh(["sudo", "-n", "insmod", VER_KO, "specasync_policy=0", "specasync_log_enabled=0",
          "uvm_perf_prefetch_enable=0", "specasync_trace_faults=1"])
if r.returncode or R.read_sys("/sys/module/nvidia_uvm/srcversion") != "5997D238EF080B77DBD2AAF":
    sys.exit(f"STOP: insmod/srcversion problem: {r.stderr}")
R.check_after(before, tables, "probe table insmod")
subprocess.run(["sudo", "-n", "tee", f"{R.DBG}/specasync_clear"], input="1", capture_output=True, text=True, check=True)
before = R.dmesg_lines()
b = subprocess.run(["timeout", "30", "setarch", "-R", f"{R.REPO}/tests/group_probe"], capture_output=True, text=True)
if b.returncode: sys.exit(f"STOP: group_probe exited {b.returncode}")
trace = os.path.join(tables, "group_probe_trace.bin")
with open(trace, "wb") as f:
    subprocess.run(["sudo", "-n", "cat", f"{R.DBG}/specasync_fault_trace"], stdout=f)
R.check_after(before, tables, "probe table run")
print(b.stdout.strip()); print("trace entries", os.path.getsize(trace) // 8, "overwrites", R.dbg("trace_overwrites"))
p = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "prepare_first_touch_table.py"),
                    trace, os.path.join(tables, "group_probe_ft_table.bin"), "8"], capture_output=True, text=True)
print(p.stdout.strip(), p.stderr.strip()); sys.exit(p.returncode)
