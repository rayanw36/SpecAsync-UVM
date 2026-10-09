#!/usr/bin/env python3
"""Gate E9 runner: a COPY of tests/e8_runner.py (stock module only) that runs every benchmark under nsys and extracts
unified-memory counts. Same per-run protocol and stop conditions as E8 (reload; srcversion and parameter read-back incl.
uvm_perf_prefetch_threshold; timestamp dmesg diff; 1 s drain; MemAvailable / disk floors; one CSV row). Changes from e8_runner.py:
  1. the command is `timeout T nsys profile --trace=cuda --cuda-um-gpu-page-faults=true --cuda-um-cpu-page-faults=true
     --force-overwrite=true -o <out>/e9_<idx> setarch -R <bench>`; T = 3 x E8's timeout for the cell (e9/e9_timeouts.csv), or 300 s with --smoke;
  2. after the (timed) run, outside the timed region: tests/e9_extract.py reads the report; ANY nsys failure (nonzero exit, missing report,
     extraction error) is a STOP (pre-registered E9 stop condition);
  3. the workload table: bench_sparse cells (tests/e8_cells.py) and Stencil-24K (bench_stencil 24000); the checksum check applies to bench_sparse;
  4. wall-clock is recorded but NEVER compared (tracing perturbs timing).
usage: e9_runner.py --order ORDER --csv CSV --out-dir DIR --commit-msg MSG [--smoke] [--from N] [--through N] [--order-sha256 FILE]
"""
import argparse
import csv
import hashlib
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import e8_runner as B  # noqa: E402  (stock-module load, commit helper, paths; e8_runner itself is imported unchanged)
import e9_extract as X  # noqa: E402
import e8_cells as C  # noqa: E402

R, E, REPO = B.R, B.E, B.REPO
E9 = f"{REPO}/results/analysis/gate_e/e9"
EXTRA = ["report_htod_mb", "report_dtoh_mb", "report_cpu_faults", "report_gpu_faults", "htod_bytes", "dtoh_bytes", "dtod_bytes", "uvm_migrations",
         "htod_fault_bytes", "htod_prefetch_bytes", "htod_evict_bytes", "htod_other_bytes", "dtoh_fault_bytes", "dtoh_prefetch_bytes",
         "dtoh_evict_bytes", "dtoh_other_bytes", "gpu_fault_events", "gpu_faults_sum"] + \
        [f"pass{i}_{d}_bytes" for i in (1, 2, 3) for d in ("htod", "dtoh")]
FIELDS = ["idx", "label", "ts_utc", "workload", "family", "block", "module", "prefetch", "threshold", "threshold_readback", "prefetch_readback",
          "wall_s_NOT_COMPARED", "exit_code", "srcversion", "mem_before_kb", "mem_after_kb", "disk_free_gb", "dmesg_new_lines", "rep_bytes"] + \
         ["pass1_ms", "pass2_ms", "pass3_ms"] + EXTRA
NSYS = ["nsys", "profile", "--trace=cuda", "--cuda-um-gpu-page-faults=true", "--cuda-um-cpu-page-faults=true", "--force-overwrite=true"]


def command(wl):
    if wl == "stencil":
        return [f"{REPO}/benchmarks/bench_stencil", "24000"]
    return C.command(REPO, wl)


def timeouts(smoke):
    p = f"{E9}/e9_timeouts.csv"
    return {} if smoke or not os.path.exists(p) else {r["label"]: int(r["timeout_s"]) for r in csv.DictReader(open(p))}


def main():
    ap = argparse.ArgumentParser()
    for a in ("--order", "--csv", "--out-dir", "--commit-msg"):
        ap.add_argument(a, required=(a != "--commit-msg"), default="Gate E9")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--from", dest="lo", type=int, default=0)
    ap.add_argument("--through", type=int, default=0)
    ap.add_argument("--order-sha256", default="")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    stop_file = os.path.join(args.out_dir, "STOP")
    if os.path.exists(stop_file):
        print("STOP file exists; refusing:", open(stop_file).read())
        return 3
    if args.order_sha256:
        h = hashlib.sha256(open(args.order, "rb").read()).hexdigest()
        if h not in open(args.order_sha256).read():
            print(f"REFUSING: sha256 of {args.order} ({h[:16]}...) is not in {args.order_sha256}")
            return 4
    order = list(csv.DictReader(open(args.order)))
    tmo_map = timeouts(args.smoke)
    done = {r["idx"] for r in csv.DictReader(open(args.csv))} if os.path.exists(args.csv) else set()
    if not os.path.exists(args.csv):
        with open(args.csv, "w", newline="") as f:
            csv.writer(f).writerow(FIELDS)
    for row in order:
        idx = int(row["idx"])
        if row["idx"] in done or (args.lo and idx < args.lo):
            continue
        if args.through and idx > args.through:
            break
        wl, label = row["workload"], f"idx={row['idx']} {row['label']}"
        tmo = tmo_map.get(row["label"], 300)
        rep = os.path.join(args.out_dir, f"e9_{row['idx']}")
        ex = {}
        try:
            if row["module"] != "stock":
                raise R.Stop("E9 runs the stock module only")
            srcv = B.load_stock(row, args.out_dir, label)
            thr_rb = R.read_sys("/sys/module/nvidia_uvm/parameters/uvm_perf_prefetch_threshold")
            pf_rb = R.read_sys("/sys/module/nvidia_uvm/parameters/uvm_perf_prefetch_enable")
            mem_before = R.mem_available_kb()
            before = R.dmesg_lines()
            t0 = time.monotonic_ns()
            r = subprocess.run(["timeout", str(tmo)] + NSYS + ["-o", rep, "setarch", "-R"] + command(wl), capture_output=True, text=True)
            t1 = time.monotonic_ns()
            if r.returncode == 124:
                raise R.Stop(f"benchmark timeout ({tmo} s)")
            if r.returncode != 0:
                raise R.Stop(f"nsys/benchmark exited {r.returncode}; stdout tail: {r.stdout[-200:]} stderr tail: {r.stderr[-300:]}")
            open(f"{rep}_stdout.txt", "w").write(r.stdout)
            passes = re.findall(r"pass \d+ kernel_ms=([0-9.]+)", r.stdout)
            if wl != "stencil" and (len(passes) != C.PASSES or "CHECKSUM OK" not in r.stdout):
                raise R.Stop(f"benchmark output incomplete or checksum not confirmed: {r.stdout[-200:]}")
            if not os.path.exists(rep + ".nsys-rep"):
                raise R.Stop("nsys report missing after a zero exit (nsys failure)")
            time.sleep(1.0)
            try:
                ex = X.extract(rep + ".nsys-rep")
            except Exception as e:  # any extraction failure is an nsys failure
                raise R.Stop(f"nsys extraction failed: {e}")
            nnew, mem_after, free = R.check_after(before, args.out_dir, label + " after run")
        except R.Stop as e:
            with open(stop_file, "w") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} STOPPED at {label}: {e}\n--- dmesg tail ---\n{E.dmesg_tail()}\n")
            h = B.commit([args.csv], f"{args.commit_msg}: STOPPED at {label} -- {str(e)[:100]}")
            print(f"STOP: {e}\ncommit: {h}\n--- dmesg tail ---\n{E.dmesg_tail()}", flush=True)
            return 3
        out = {k: row[k] for k in ("idx", "label", "workload", "family", "block", "module", "prefetch", "threshold")}
        out.update({"ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "threshold_readback": thr_rb, "prefetch_readback": pf_rb,
                    "wall_s_NOT_COMPARED": f"{(t1 - t0) / 1e9:.6f}", "exit_code": r.returncode, "srcversion": srcv, "mem_before_kb": mem_before,
                    "mem_after_kb": mem_after, "disk_free_gb": f"{free / 1024 ** 3:.1f}", "dmesg_new_lines": nnew,
                    "rep_bytes": os.path.getsize(rep + ".nsys-rep"), **{f"pass{i + 1}_ms": p for i, p in enumerate(passes)}, **ex})
        with open(args.csv, "a", newline="") as f:
            csv.writer(f).writerow([out.get(k, "") for k in FIELDS])
        print(f"done {label} dmesg_new={nnew} mem_after={mem_after} thr={thr_rb} htod={ex.get('htod_bytes')} dtoh={ex.get('dtoh_bytes')} gpu_faults={ex.get('gpu_faults_sum')}", flush=True)
    print("COMPLETE", B.commit([args.csv], f"{args.commit_msg}: rows complete"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
