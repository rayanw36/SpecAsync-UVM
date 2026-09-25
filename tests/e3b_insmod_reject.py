#!/usr/bin/env python3
"""Gate E3b Step 1: insmod rejection of bad parameter values (no GPU work).

For each (parameter, value): rmmod the verified module (refcnt 0) ->
insmod the NEW module with that value -> insmod must FAIL, the module's
pr_err line must appear in the new dmesg lines, and no nvidia_uvm may be
loaded -> reload the verified module (speculation off, prefetch on) and
confirm its srcversion. Any unexpected outcome is a stop (exit 3): nothing
further is attempted. Writes one CSV row per value.
"""
import csv
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import e09b_runner as R  # noqa: E402

BAD = re.compile(r"BUG|Oops|WARNING|general protection|NULL pointer|exited with irqs disabled|"
                 r"soft lockup|hung_task|RCU stall")
NEW_KO = f"{R.REPO}/driver/build/595.91.07/nvidia-uvm-specasync-NEW-e3a2-width-ftfast-UNREVIEWED.ko"
VER_KO = f"{R.REPO}/driver/build/595.91.07/nvidia-uvm-specasync-NEW-e0.9a2-fixed.ko"
VER_SRCV = "5997D238EF080B77DBD2AAF"
CASES = [("specasync_spec_width", v) for v in ("0", "3", "1024", "abc")] + \
        [("specasync_ft_fast", v) for v in ("2", "-1", "abc")]


def main():
    out = sys.argv[1]
    rows = []
    for param, val in CASES:
        row = {"param": param, "value": val}
        before = R.dmesg_lines()
        rc = R.read_sys("/sys/module/nvidia_uvm/refcnt")
        if rc != "0":
            print(f"STOP: refcnt={rc} before rmmod ({param}={val})"); return 3
        r = R.sh(["sudo", "-n", "rmmod", "nvidia_uvm"])
        if r.returncode != 0:
            print(f"STOP: rmmod failed: {r.stderr.strip()}"); return 3
        r = R.sh(["sudo", "-n", "insmod", NEW_KO, "specasync_policy=0", "specasync_log_enabled=0",
                  f"{param}={val}"])
        row["insmod_rc"] = r.returncode
        row["insmod_stderr"] = r.stderr.strip().replace("\n", " ")
        row["left_loaded"] = int(os.path.exists("/sys/module/nvidia_uvm"))
        new = R.dmesg_lines()[len(before):]
        errline = [l for l in new if "specasync" in l and "rejected" in l]
        row["pr_err_line"] = errline[0].split("] ", 1)[-1] if errline else ""
        row["kernel_line"] = next((l.split("] ", 1)[-1] for l in new if "invalid for parameter" in l), "")
        bad = [l for l in new if BAD.search(l)]
        if r.returncode == 0 or row["left_loaded"] or not errline or bad:
            print(f"STOP: unexpected outcome for {param}={val}: {row}; bad dmesg: {bad}")
            rows.append(row)
            break
        before = R.dmesg_lines()
        r2 = R.sh(["sudo", "-n", "insmod", VER_KO, "specasync_policy=0", "specasync_offload_depth=0",
                   "specasync_log_enabled=0", "uvm_perf_prefetch_enable=1"])
        row["verified_reload_rc"] = r2.returncode
        row["verified_srcversion"] = R.read_sys("/sys/module/nvidia_uvm/srcversion")
        bad = [l for l in R.dmesg_lines()[len(before):] if BAD.search(l)]
        rows.append(row)
        print(row, flush=True)
        if r2.returncode != 0 or row["verified_srcversion"] != VER_SRCV or bad:
            print(f"STOP: verified reload problem: {row}; bad dmesg: {bad}")
            break
    keys = ["param", "value", "insmod_rc", "insmod_stderr", "left_loaded", "pr_err_line", "kernel_line",
            "verified_reload_rc", "verified_srcversion"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for rr in rows:
            w.writerow({k: rr.get(k, "") for k in keys})
    ok = len(rows) == len(CASES) and all(rr.get("verified_srcversion") == VER_SRCV for rr in rows)
    print("RESULT:", "ALL REJECTED AS EXPECTED" if ok else "NOT ALL PASSED")
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
