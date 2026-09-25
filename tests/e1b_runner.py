#!/usr/bin/env python3
"""Gate E1b runner: measure the handoff cost directly.

Reuses tests/e09b_runner.py's helpers unchanged (reload_module with srcversion
and parameter read-back, check_after with every stop condition, dmesg diff,
counter reads, git_commit). Differences from the E0.9b/E1 main loop:
  - arms C0, C1, C6 (policy 6, prefetch off), C7 (policy 6, prefetch on);
  - after every run, dumps BOTH the batch ring (specasync_log, 72 B records)
    and the decomp ring (specasync_decomp_log, 112 B records) and records
    their record counts in the CSV;
  - a nonzero benchmark exit code is a stop (as in E1).
Wall-clock goes to the CSV only, never stdout. Resumable by idx.
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

ARMS = {
    "C0": {"specasync_policy": "0", "specasync_offload_depth": "0", "uvm_perf_prefetch_enable": "1"},
    "C1": {"specasync_policy": "0", "specasync_offload_depth": "0", "uvm_perf_prefetch_enable": "0"},
    "C6": {"specasync_policy": "6", "specasync_offload_depth": "1", "uvm_perf_prefetch_enable": "0"},
    "C7": {"specasync_policy": "6", "specasync_offload_depth": "1", "uvm_perf_prefetch_enable": "1"},
}


def arm_params(arm, L, table):
    p = ["specasync_log_enabled=1"] + [f"{k}={v}" for k, v in ARMS[arm].items()]
    if ARMS[arm]["specasync_policy"] == "6":
        p += [f"specasync_ft_lookahead={L}", f"specasync_ft_table_path={table}"]
    return p


def expected_sysparams(arm, L):
    e = dict(ARMS[arm])
    if e["specasync_policy"] == "6":
        e["specasync_ft_lookahead"] = str(L)
    return e


R.arm_params = arm_params
R.expected_sysparams = expected_sysparams


def dump(name, path):
    with open(path, "wb") as f:
        subprocess.run(["sudo", "-n", "cat", f"{R.DBG}/{name}"], stdout=f)
    return os.path.getsize(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--order", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--tables", required=True)
    ap.add_argument("--timeout-stencil", type=int, required=True)
    ap.add_argument("--timeout-graphbfs", type=int, required=True)
    ap.add_argument("--commit-every", type=int, default=0)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    stop_file = os.path.join(args.out_dir, "STOP")
    if os.path.exists(stop_file):
        print("STOP file exists; refusing to run:", open(stop_file).read())
        return 3
    order = list(csv.DictReader(open(args.order)))
    fields = ["idx", "ts_utc", "workload", "arm", "L", "wall_s", "bench_result_ms", "exit_code", "srcversion",
              "mem_before_kb", "mem_after_kb", "disk_free_gb", "dmesg_new_lines",
              "batch_records", "decomp_records", "batch_bytes_mod", "decomp_bytes_mod"] + R.COUNTERS
    done = set()
    if os.path.exists(args.csv):
        done = {r["idx"] for r in csv.DictReader(open(args.csv))}
    else:
        with open(args.csv, "w", newline="") as f:
            csv.writer(f).writerow(fields)

    since = 0
    for row in order:
        idx, wl, arm, L = row["idx"], row["workload"], row["arm"], (row["L"] or "")
        if idx in done:
            continue
        table = os.path.join(args.tables, f"{wl}_ft_table.bin")
        tmo = args.timeout_stencil if wl == "stencil" else args.timeout_graphbfs
        label = f"e1b idx={idx} {wl} {arm}{('-L' + L) if L else ''}"
        try:
            before = R.dmesg_lines()
            srcv = R.reload_module(arm, L, table)
            R.check_after(before, args.out_dir, label + " after insmod")
            clr = subprocess.run(["sudo", "-n", "tee", f"{R.DBG}/specasync_clear"], input="1",
                                 capture_output=True, text=True)
            if clr.returncode != 0:
                raise R.Stop(f"({label}): specasync_clear failed: {clr.stderr.strip()}")
            mem_before = R.mem_available_kb()
            before = R.dmesg_lines()
            t0 = time.monotonic_ns()
            r = subprocess.run(["timeout", str(tmo), "setarch", "-R"] + R.BENCH[wl], capture_output=True, text=True)
            t1 = time.monotonic_ns()
            if r.returncode == 124:
                raise R.Stop(f"benchmark timeout ({label}): {tmo}s")
            if r.returncode != 0:
                raise R.Stop(f"({label}): benchmark exited {r.returncode}; stderr tail: {r.stderr[-300:]}")
            time.sleep(1.0)
            m = re.search(r"\[RESULT\] Time: ([0-9.]+) ms", r.stdout)
            ctr = {c: R.dbg(c) for c in R.COUNTERS}
            stem = os.path.join(args.out_dir, f"e1b_{idx}_{wl}_{arm}{L}")
            bb = dump("specasync_log", stem + "_batch.bin")
            db = dump("specasync_decomp_log", stem + "_decomp.bin")
            nnew, mem_after, free = R.check_after(before, args.out_dir, label + " after run")
        except R.Stop as e:
            with open(stop_file, "w") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} STOPPED at {label}: {e}\n")
            h = R.git_commit([args.csv], f"Gate E1b: STOPPED at idx {idx} -- {str(e)[:120]}")
            print(f"STOP: {e}\ncommit: {h}", flush=True)
            return 3
        out = {"idx": idx, "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "workload": wl, "arm": arm,
               "L": L, "wall_s": f"{(t1 - t0) / 1e9:.6f}", "bench_result_ms": m.group(1) if m else "",
               "exit_code": r.returncode, "srcversion": srcv, "mem_before_kb": mem_before, "mem_after_kb": mem_after,
               "disk_free_gb": f"{free / 1024 ** 3:.1f}", "dmesg_new_lines": nnew,
               "batch_records": bb // 72, "decomp_records": db // 112,
               "batch_bytes_mod": bb % 72, "decomp_bytes_mod": db % 112}
        out.update(ctr)
        with open(args.csv, "a", newline="") as f:
            csv.writer(f).writerow([out[k] for k in fields])
        print(f"done {label} batch={out['batch_records']} decomp={out['decomp_records']} "
              f"mem_after={mem_after} dmesg_new={nnew}", flush=True)
        since += 1
        if args.commit_every and since >= args.commit_every:
            print("commit", R.git_commit([args.csv], f"Gate E1b: rows through idx {idx}"), flush=True)
            since = 0
    print("COMPLETE commit", R.git_commit([args.csv], f"Gate E1b: all {len(order)} runs complete"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
