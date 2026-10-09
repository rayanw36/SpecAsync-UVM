#!/usr/bin/env python3
"""Gate E7 runner. Same per-run protocol as E6 (tests/e6_runner.py -> e5_runner -> e4_runner -> e3b_runner,
all unchanged and imported): reload, srcversion and parameter read-back (including
uvm_perf_prefetch_threshold), ft_fast_verified on every fast = 1 load, timestamp dmesg diff,
`timeout T setarch -R <bench>`, a 1 s drain, the stop checks, one CSV row.

E7 adds ONE thing: a "stock" module mode. For rows with module = stock the runner inserts
/lib/modules/$(uname -r)/updates/dkms/nvidia-uvm.ko.zst with
uvm_perf_prefetch_enable=<prefetch> uvm_perf_prefetch_threshold=<threshold>, verifies
srcversion 6284DA42F15EDC3AB92332B and reads both parameters back (a mismatch is a stop).
The stock module has no specasync debugfs, so no counters / ring dumps are read for stock rows
(those columns stay blank). Module = new rows go through e3b_runner.load unchanged.

Other E7 differences, all bookkeeping: 8 benchmark workloads (the E6 stencil / graphbfs entries are
taken from e3b_runner unchanged); the read-back threshold is written to the CSV; --from/--through select
an idx range; --commit-every commits the CSV every N completed rows; --order-sha256 refuses to run if the
order file does not match the committed hash; commits carry this session's attribution trailer.

On any stop: writes <out>/STOP, commits the CSV, prints the dmesg tail, exits 3, touches nothing else.
Wall-clock goes to the CSV only.

usage: e7_runner.py --order ORDER --csv CSV --out-dir DIR --tables DIR --commit-msg MSG
                    [--from N] [--through N] [--commit-every N] [--order-sha256 FILE]
"""
import argparse
import csv
import hashlib
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import e5_runner  # noqa: E402  (applies the threshold-aware params/expected to e3b_runner)
E = e5_runner.E
R = E.R

STOCK_SRCV = "6284DA42F15EDC3AB92332B"
REPO = R.REPO
B = f"{REPO}/benchmarks"
# workload -> (command line, timeout s). stencil / graphbfs are e3b_runner's entries, unchanged.
WL = {
    "stencil": (E.BENCH["stencil"], E.TMO["stencil"]),
    "graphbfs": (E.BENCH["graphbfs"], E.TMO["graphbfs"]),
    "stencil8k": ([f"{B}/bench_stencil", "8000"], 22),
    "sweep4k": ([f"{B}/bench_stencil", "4000"], 22),
    "sweep16k": ([f"{B}/bench_stencil", "16000"], 22),
    "stream": ([f"{B}/bench_stream", "268435456"], 22),
    "sgemm": ([f"{B}/bench_sgemm", "24000"], 60),
    "cufft": ([f"{B}/bench_cufft", "134217728"], 22),
    "oversub": ([f"{B}/stencil_oversub/bench_stencil_oversub", "48000", "1"], 10),
}
assert WL["stencil"][1] == 22 and WL["graphbfs"][1] == 168


def stock_ko():
    return f"/lib/modules/{os.uname().release}/updates/dkms/nvidia-uvm.ko.zst"


def load_stock(row, out_dir, label):
    before = R.dmesg_lines()
    rc = R.read_sys("/sys/module/nvidia_uvm/refcnt")
    if rc is not None:
        if rc != "0":
            raise R.Stop(f"refcnt={rc} before reload")
        r = R.sh(["sudo", "-n", "rmmod", "nvidia_uvm"])
        if r.returncode != 0:
            raise R.Stop(f"rmmod failed rc={r.returncode}: {r.stderr.strip()}")
    r = R.sh(["sudo", "-n", "insmod", stock_ko(), f"uvm_perf_prefetch_enable={row['prefetch']}",
              f"uvm_perf_prefetch_threshold={row['threshold']}"])
    if r.returncode != 0:
        raise R.Stop(f"stock insmod failed: rc={r.returncode}: {r.stderr.strip()}")
    got = R.read_sys("/sys/module/nvidia_uvm/srcversion")
    if got != STOCK_SRCV:
        raise R.Stop(f"srcversion {got} != expected stock {STOCK_SRCV}")
    for k, v in (("uvm_perf_prefetch_enable", row["prefetch"]), ("uvm_perf_prefetch_threshold", row["threshold"])):
        g = R.read_sys(f"/sys/module/nvidia_uvm/parameters/{k}")
        if g != v:
            raise R.Stop(f"parameter {k}={g}, expected {v}")
    R.check_after(before, out_dir, label + " after insmod")
    return got


def commit(paths, msg):
    R.sh(["git", "-C", REPO, "add"] + paths)
    if R.sh(["git", "-C", REPO, "diff", "--cached", "--quiet"]).returncode == 0:
        return None
    R.sh(["git", "-C", REPO, "commit", "-q", "-m", msg + "\n\n"
          "Claude-Session: https://claude.ai/code/session_013R7hqocoYREgYBhLTAjkLy"])
    return R.sh(["git", "-C", REPO, "log", "--oneline", "-1"]).stdout.strip()


FIELDS = (["idx", "label", "ts_utc", "workload", "family", "block", "module", "policy", "depth", "prefetch", "L", "W",
           "fast", "trace_faults", "threshold", "threshold_readback", "prefetch_readback", "wall_s", "exit_code",
           "srcversion", "mem_before_kb", "mem_after_kb", "disk_free_gb", "dmesg_new_lines"]
          + E.LOAD_INFO + E.BASE_CTRS + E.NEW_CTRS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--order", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--tables", required=True)
    ap.add_argument("--commit-msg", default="Gate E7")
    ap.add_argument("--from", dest="lo", type=int, default=0)
    ap.add_argument("--through", type=int, default=0)
    ap.add_argument("--commit-every", type=int, default=10)
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
    done = set()
    if os.path.exists(args.csv):
        done = {r["idx"] for r in csv.DictReader(open(args.csv))}
    else:
        with open(args.csv, "w", newline="") as f:
            csv.writer(f).writerow(FIELDS)
    n_new = 0
    for row in order:
        idx = int(row["idx"])
        if row["idx"] in done or (args.lo and idx < args.lo):
            continue
        if args.through and idx > args.through:
            break
        wl = row["workload"]
        cmd, tmo = WL[wl]
        table = os.path.join(args.tables, "stencil_ft_table.bin")
        label = f"idx={row['idx']} {row['label']}"
        ctr, info = {}, {}
        try:
            if row["module"] == "stock":
                srcv = load_stock(row, args.out_dir, label)
            else:
                srcv, info = E.load(row, table, args.out_dir, label)
                clr = subprocess.run(["sudo", "-n", "tee", f"{R.DBG}/specasync_clear"], input="1",
                                     capture_output=True, text=True)
                if clr.returncode != 0:
                    raise R.Stop(f"specasync_clear failed: {clr.stderr.strip()}")
            thr_rb = R.read_sys("/sys/module/nvidia_uvm/parameters/uvm_perf_prefetch_threshold")
            pf_rb = R.read_sys("/sys/module/nvidia_uvm/parameters/uvm_perf_prefetch_enable")
            mem_before = R.mem_available_kb()
            before = R.dmesg_lines()
            t0 = time.monotonic_ns()
            r = subprocess.run(["timeout", str(tmo), "setarch", "-R"] + cmd, capture_output=True, text=True)
            t1 = time.monotonic_ns()
            if r.returncode == 124:
                raise R.Stop(f"benchmark timeout ({tmo} s)")
            if r.returncode != 0:
                raise R.Stop(f"benchmark exited {r.returncode}; stderr tail: {r.stderr[-300:]}")
            time.sleep(1.0)
            if row["module"] == "new":
                ctr = {c: R.dbg(c) for c in E.BASE_CTRS + E.NEW_CTRS}
            nnew, mem_after, free = R.check_after(before, args.out_dir, label + " after run")
            if row["module"] == "new":
                if int(ctr["ft_fast_cas_giveup"]) > 0:
                    raise R.Stop(f"specasync_ft_fast_cas_giveup = {ctr['ft_fast_cas_giveup']} > 0")
                if int(ctr["spec_region_invalid"]) > 0:
                    raise R.Stop(f"specasync_spec_region_invalid = {ctr['spec_region_invalid']} > 0 on a managed, non-oversubscribed run")
        except R.Stop as e:
            with open(stop_file, "w") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} STOPPED at {label}: {e}\n"
                        f"counters: {ctr}\n--- dmesg tail ---\n{E.dmesg_tail()}\n")
            h = commit([args.csv], f"{args.commit_msg}: STOPPED at {label} -- {str(e)[:100]}")
            print(f"STOP: {e}\ncounters: {ctr}\ncommit: {h}\n--- dmesg tail ---\n{E.dmesg_tail()}", flush=True)
            return 3
        out = {k: row[k] for k in ("idx", "label", "workload", "family", "block", "module", "policy", "depth",
                                   "prefetch", "L", "W", "fast", "trace_faults", "threshold")}
        out.update({"ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "threshold_readback": thr_rb,
                    "prefetch_readback": pf_rb, "wall_s": f"{(t1 - t0) / 1e9:.6f}", "exit_code": r.returncode,
                    "srcversion": srcv, "mem_before_kb": mem_before, "mem_after_kb": mem_after,
                    "disk_free_gb": f"{free / 1024 ** 3:.1f}", "dmesg_new_lines": nnew})
        out.update(info)
        out.update(ctr)
        with open(args.csv, "a", newline="") as f:
            csv.writer(f).writerow([out.get(k, "") for k in FIELDS])
        n_new += 1
        print(f"done {label} dmesg_new={nnew} mem_after={mem_after} thr={thr_rb}", flush=True)
        if args.commit_every and n_new % args.commit_every == 0:
            commit([args.csv], f"{args.commit_msg}: {n_new} rows this invocation")
    print("COMPLETE", commit([args.csv], f"{args.commit_msg}: rows complete"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
