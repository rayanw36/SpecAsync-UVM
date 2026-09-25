#!/usr/bin/env python3
"""Gate E0.9b: collect fresh first-touch tables for both workloads, with the
same stop-condition checks as e09b_runner.py and the E0.8 distinct-page
assertion (1,125,000 / 287,956). Exit 3 on any stop condition, 2 on a
failed assertion, 0 on success."""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import e09b_runner as R  # noqa: E402

EXPECT = {"stencil": 1125000, "graphbfs": 287956}
TMO = {"stencil": 30, "graphbfs": 180}


def main():
    tables = sys.argv[1]
    os.makedirs(tables, exist_ok=True)
    stop_file = os.path.join(tables, "STOP")
    for wl in ("stencil", "graphbfs"):
        label = f"table-collect {wl}"
        try:
            before = R.dmesg_lines()
            if R.read_sys("/sys/module/nvidia_uvm/refcnt") is not None:
                rc = R.read_sys("/sys/module/nvidia_uvm/refcnt")
                if rc != "0":
                    raise R.Stop(f"condition 2: refcnt={rc} before reload")
                r = R.sh(["sudo", "-n", "rmmod", "nvidia_uvm"])
                if r.returncode != 0:
                    raise R.Stop(f"condition 2: rmmod failed: {r.stderr.strip()}")
            r = R.sh(["sudo", "-n", "insmod", R.KO, "specasync_policy=0", "specasync_log_enabled=0",
                      "uvm_perf_prefetch_enable=0", "specasync_trace_faults=1",
                      "specasync_trace_ring_slots=4194304"])
            if r.returncode != 0:
                raise R.Stop(f"insmod failed: {r.stderr.strip()}")
            srcv = R.read_sys("/sys/module/nvidia_uvm/srcversion")
            if srcv != R.EXPECTED_SRCVERSION:
                raise R.Stop(f"condition 6: srcversion {srcv}")
            R.check_after(before, tables, label + " after insmod")
            before = R.dmesg_lines()
            b = subprocess.run(["timeout", str(TMO[wl]), "setarch", "-R"] + R.BENCH[wl], capture_output=True, text=True)
            if b.returncode == 124:
                raise R.Stop(f"condition 3 ({label}): timeout {TMO[wl]}s")
            if b.returncode != 0:
                raise R.Stop(f"({label}): benchmark exited {b.returncode}")
            trace = os.path.join(tables, f"{wl}_trace.bin")
            with open(trace, "wb") as f:
                subprocess.run(["sudo", "-n", "cat", f"{R.DBG}/specasync_fault_trace"], stdout=f)
            ow = R.dbg("trace_overwrites")
            R.check_after(before, tables, label + " after run")
            if ow != "0":
                raise R.Stop(f"({label}): trace ring overwrote {ow} entries -- table would be incomplete")
        except R.Stop as e:
            with open(stop_file, "w") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} STOPPED at {label}: {e}\n")
            print("STOP:", e)
            return 3
        p = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "prepare_first_touch_table.py"),
                            trace, os.path.join(tables, f"{wl}_ft_table.bin"), str(EXPECT[wl])],
                           capture_output=True, text=True)
        print(p.stdout.strip())
        if p.returncode != 0:
            print("ASSERTION FAILED:", p.stderr.strip())
            with open(stop_file, "w") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} STOPPED: distinct-page assertion failed for {wl}: {p.stderr.strip()}\n")
            return 2
        print(f"{wl}: trace entries={os.path.getsize(trace)//8} overwrites={ow}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
