#!/usr/bin/env python3
"""Gate E3b runner (Steps 2-4): one row = one run, fully specified by the
order file, on either the verified module or the new E3a-2 module.

Order CSV columns:
  idx, label, workload, module (verified|new), policy, depth, prefetch, L, W,
  fast, trace_faults, dump_rings
Per run: refcnt 0 -> rmmod -> insmod (params from the row; the verified
module never receives the new parameters) -> srcversion and parameter
read-back -> (new module) read ft_fast_verified / nranges / verify_ns ->
dmesg diff -> specasync_clear -> `timeout T setarch -R <bench>` -> 1 s drain
-> all counters -> optional batch+decomp ring dumps -> stop checks.

Stop conditions (E3b brief): the E0.9b set via e09b_runner.check_after with
the dmesg pattern extended to soft lockup / hung_task / RCU stall; insmod
failure; srcversion mismatch; timeout; nonzero exit; ft_fast_cas_giveup > 0;
spec_region_invalid > 0 (every run here is managed and non-oversubscribed).
On a stop: writes <out>/STOP, commits the CSV, prints the dmesg tail and
counters, exits 3, touches nothing else. Wall-clock goes to the CSV only.
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import e09b_runner as R  # noqa: E402
import e3b_dmesg  # noqa: E402

R.check_after = e3b_dmesg.check_after   # timestamp-based diff (log buffer rotates)
R.BAD = re.compile(r"BUG|Oops|WARNING|general protection|NULL pointer|exited with irqs disabled|"
                   r"soft lockup|hung_task|RCU stall")
MOD = {
    "verified": (f"{R.REPO}/driver/build/595.91.07/nvidia-uvm-specasync-NEW-e0.9a2-fixed.ko", "5997D238EF080B77DBD2AAF"),
    "new": (f"{R.REPO}/driver/build/595.91.07/nvidia-uvm-specasync-NEW-e3a2-width-ftfast.ko", "33FD42E6E16B0A6658E2BEB"),
}
BENCH = dict(R.BENCH)
BENCH["group_probe"] = [f"{R.REPO}/tests/group_probe"]
TMO = {"stencil": 22, "graphbfs": 168, "group_probe": 30}
BASE_CTRS = R.COUNTERS + ["trace_pushes", "trace_overwrites"]
NEW_CTRS = ["ft_same_region", "spec_region_invalid", "spec_pages_requested", "ft_fast_cas_giveup"]
LOAD_INFO = ["ft_fast_verified", "ft_fast_nranges", "ft_fast_verify_ns"]


def params(row, table):
    p = ["specasync_log_enabled=1", f"specasync_policy={row['policy']}", f"specasync_offload_depth={row['depth']}",
         f"uvm_perf_prefetch_enable={row['prefetch']}", f"specasync_trace_faults={row['trace_faults']}"]
    if row["policy"] == "6":
        p += [f"specasync_ft_lookahead={row['L']}", f"specasync_ft_table_path={table}"]
    if row["module"] == "new":
        p += [f"specasync_spec_width={row['W']}", f"specasync_ft_fast={row['fast']}"]
    return p


def expected(row):
    e = {"specasync_policy": row["policy"], "specasync_offload_depth": row["depth"],
         "uvm_perf_prefetch_enable": row["prefetch"], "specasync_trace_faults": row["trace_faults"]}
    if row["policy"] == "6":
        e["specasync_ft_lookahead"] = row["L"]
    if row["module"] == "new":
        e["specasync_spec_width"] = row["W"]
        e["specasync_ft_fast"] = row["fast"]
    return e


def load(row, table, out_dir, label):
    ko, srcv = MOD[row["module"]]
    before = R.dmesg_lines()
    if R.read_sys("/sys/module/nvidia_uvm/refcnt") is not None:
        rc = R.read_sys("/sys/module/nvidia_uvm/refcnt")
        if rc != "0":
            raise R.Stop(f"refcnt={rc} before reload")
        r = R.sh(["sudo", "-n", "rmmod", "nvidia_uvm"])
        if r.returncode != 0:
            raise R.Stop(f"rmmod failed rc={r.returncode}: {r.stderr.strip()}")
    r = R.sh(["sudo", "-n", "insmod", ko] + params(row, table))
    if r.returncode != 0:
        raise R.Stop(f"insmod failed where success was expected: rc={r.returncode}: {r.stderr.strip()}")
    got = R.read_sys("/sys/module/nvidia_uvm/srcversion")
    if got != srcv:
        raise R.Stop(f"srcversion {got} != expected {srcv}")
    for k, v in expected(row).items():
        g = R.read_sys(f"/sys/module/nvidia_uvm/parameters/{k}")
        if g != v:
            raise R.Stop(f"parameter {k}={g}, expected {v}")
    R.check_after(before, out_dir, label + " after insmod")
    info = {k: (R.dbg(k) if row["module"] == "new" else "") for k in LOAD_INFO}
    return got, info


def dmesg_tail(n=40):
    return "\n".join(R.dmesg_lines()[-n:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--order", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--tables", required=True)
    ap.add_argument("--commit-msg", default="Gate E3b")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    stop_file = os.path.join(args.out_dir, "STOP")
    if os.path.exists(stop_file):
        print("STOP file exists; refusing:", open(stop_file).read())
        return 3
    order = list(csv.DictReader(open(args.order)))
    fields = (["idx", "label", "ts_utc", "workload", "module", "policy", "depth", "prefetch", "L", "W", "fast",
               "trace_faults", "wall_s", "exit_code", "srcversion", "mem_before_kb", "mem_after_kb", "disk_free_gb",
               "dmesg_new_lines", "batch_records", "decomp_records"] + LOAD_INFO + BASE_CTRS + NEW_CTRS)
    done = set()
    if os.path.exists(args.csv):
        done = {r["idx"] for r in csv.DictReader(open(args.csv))}
    else:
        with open(args.csv, "w", newline="") as f:
            csv.writer(f).writerow(fields)
    for row in order:
        if row["idx"] in done:
            continue
        wl = row["workload"]
        table = os.path.join(args.tables, f"{wl}_ft_table.bin")
        label = f"idx={row['idx']} {row['label']}"
        ctr = {}
        try:
            srcv, info = load(row, table, args.out_dir, label)
            clr = subprocess.run(["sudo", "-n", "tee", f"{R.DBG}/specasync_clear"], input="1",
                                 capture_output=True, text=True)
            if clr.returncode != 0:
                raise R.Stop(f"specasync_clear failed: {clr.stderr.strip()}")
            mem_before = R.mem_available_kb()
            before = R.dmesg_lines()
            t0 = time.monotonic_ns()
            r = subprocess.run(["timeout", str(TMO[wl]), "setarch", "-R"] + BENCH[wl], capture_output=True, text=True)
            t1 = time.monotonic_ns()
            if r.returncode == 124:
                raise R.Stop(f"benchmark timeout ({TMO[wl]} s)")
            if r.returncode != 0:
                raise R.Stop(f"benchmark exited {r.returncode}; stderr tail: {r.stderr[-300:]}")
            time.sleep(1.0)
            ctr = {c: R.dbg(c) for c in BASE_CTRS}
            ctr.update({c: (R.dbg(c) if row["module"] == "new" else "") for c in NEW_CTRS})
            nb = nd = ""
            if row["dump_rings"] == "1":
                stem = os.path.join(args.out_dir, f"e3b_{row['idx']}")
                for name, ext in (("specasync_log", "_batch.bin"), ("specasync_decomp_log", "_decomp.bin")):
                    with open(stem + ext, "wb") as f:
                        subprocess.run(["sudo", "-n", "cat", f"{R.DBG}/{name}"], stdout=f)
                nb = os.path.getsize(stem + "_batch.bin") // 72
                nd = os.path.getsize(stem + "_decomp.bin") // 112
            nnew, mem_after, free = R.check_after(before, args.out_dir, label + " after run")
            if row["module"] == "new":
                if int(ctr["ft_fast_cas_giveup"]) > 0:
                    raise R.Stop(f"specasync_ft_fast_cas_giveup = {ctr['ft_fast_cas_giveup']} > 0")
                if int(ctr["spec_region_invalid"]) > 0:
                    raise R.Stop(f"specasync_spec_region_invalid = {ctr['spec_region_invalid']} > 0 on a managed, non-oversubscribed run")
        except R.Stop as e:
            with open(stop_file, "w") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} STOPPED at {label}: {e}\n"
                        f"counters: {ctr}\n--- dmesg tail ---\n{dmesg_tail()}\n")
            h = R.git_commit([args.csv], f"{args.commit_msg}: STOPPED at {label} -- {str(e)[:100]}")
            print(f"STOP: {e}\ncounters: {ctr}\ncommit: {h}\n--- dmesg tail ---\n{dmesg_tail()}", flush=True)
            return 3
        out = {k: row[k] for k in ("idx", "label", "workload", "module", "policy", "depth", "prefetch", "L", "W",
                                   "fast", "trace_faults")}
        out.update({"ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "wall_s": f"{(t1 - t0) / 1e9:.6f}",
                    "exit_code": r.returncode, "srcversion": srcv, "mem_before_kb": mem_before,
                    "mem_after_kb": mem_after, "disk_free_gb": f"{free / 1024 ** 3:.1f}", "dmesg_new_lines": nnew,
                    "batch_records": nb, "decomp_records": nd})
        out.update(info)
        out.update(ctr)
        with open(args.csv, "a", newline="") as f:
            csv.writer(f).writerow([out[k] for k in fields])
        print(f"done {label} dmesg_new={nnew} mem_after={mem_after} verified={info.get('ft_fast_verified')} "
              f"nranges={info.get('ft_fast_nranges')} rings={nb}/{nd}", flush=True)
    print("COMPLETE", R.git_commit([args.csv], f"{args.commit_msg}: rows complete"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
