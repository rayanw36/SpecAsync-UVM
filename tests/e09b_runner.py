#!/usr/bin/env python3
"""Gate E0.9b unattended runner.

Executes a committed run-order file one run at a time, enforcing every
automatic stop condition from the gate brief after every run:

  1. new dmesg lines matching BUG|Oops|WARNING|general protection|NULL pointer|
     exited with irqs disabled  (checked on ALL new lines, not only nvidia_uvm
     lines: an oops's first line does not name the module)
  2. rmmod fails, or nvidia_uvm refcnt != 0 before a reload
  3. benchmark hits its timeout (never killed-and-continued)
  4. MemAvailable < 6 GiB
  5. free disk on the results filesystem < 10 GiB
  6. loaded srcversion != expected
  (7, pre-registration departure, is enforced by only ever following the
   order file and the fixed arm definitions below.)

On any stop condition: writes <out_dir>/STOP with the evidence, commits the
CSV, and exits 3 WITHOUT touching the module or the desktop.

Resumable: rows already in the CSV are skipped (by run index), so an
interruption that is not a stop condition resumes at the next run in order.

Order file: CSV with header idx,workload,arm,L  (L empty for C0/C1).
"""
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import time

REPO = "/home/rayenchikhaoui/SpecAsync-UVM"
DBG = "/sys/kernel/debug/specasync"
EXPECTED_SRCVERSION = "5997D238EF080B77DBD2AAF"
KO = f"{REPO}/driver/build/595.91.07/nvidia-uvm-specasync-NEW-e0.9a2-fixed.ko"
MEM_FLOOR_KB = 6 * 1024 * 1024
DISK_FLOOR_BYTES = 10 * 1024 ** 3
BAD = re.compile(r"BUG|Oops|WARNING|general protection|NULL pointer|exited with irqs disabled")

BENCH = {
    "stencil": ([f"{REPO}/benchmarks/bench_stencil", "24000"]),
    "graphbfs": ([f"{REPO}/benchmarks/graph_bfs/bench_graph_bfs", "23"]),
}

COUNTERS = [
    "demand_faults", "enqueued", "processed", "drops", "spec_hits", "spec_migrations",
    "ft_predictions", "ft_skipped", "ft_held", "ft_unknown_page", "ft_exhausted",
    "fault_already_resident",
]


def sh(cmd, check=False, capture=True):
    r = subprocess.run(cmd, capture_output=capture, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{cmd} -> {r.returncode}: {r.stderr}")
    return r


def dmesg_lines():
    return sh(["sudo", "-n", "dmesg"]).stdout.splitlines()


def mem_available_kb():
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1])
    return -1


def read_sys(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def dbg(name):
    return sh(["sudo", "-n", "cat", f"{DBG}/specasync_{name}"]).stdout.strip()


def arm_params(arm, L, table):
    common = ["specasync_log_enabled=1"]
    if arm == "C0":
        return common + ["specasync_policy=0", "specasync_offload_depth=0", "uvm_perf_prefetch_enable=1"]
    if arm == "C1":
        return common + ["specasync_policy=0", "specasync_offload_depth=0", "uvm_perf_prefetch_enable=0"]
    if arm == "C6":
        return common + ["specasync_policy=6", "specasync_offload_depth=1", "uvm_perf_prefetch_enable=0",
                         f"specasync_ft_lookahead={L}", f"specasync_ft_table_path={table}"]
    raise ValueError(arm)


def expected_sysparams(arm, L):
    exp = {"specasync_policy": "0", "specasync_offload_depth": "0", "uvm_perf_prefetch_enable": "1" if arm == "C0" else "0"}
    if arm == "C6":
        exp.update({"specasync_policy": "6", "specasync_offload_depth": "1", "specasync_ft_lookahead": str(L)})
    return exp


class Stop(Exception):
    pass


def reload_module(arm, L, table):
    if read_sys("/sys/module/nvidia_uvm/refcnt") is not None:
        rc = read_sys("/sys/module/nvidia_uvm/refcnt")
        if rc != "0":
            raise Stop(f"condition 2: nvidia_uvm refcnt={rc} (not 0) before reload")
        r = sh(["sudo", "-n", "rmmod", "nvidia_uvm"])
        if r.returncode != 0:
            raise Stop(f"condition 2: rmmod failed rc={r.returncode}: {r.stderr.strip()}")
    r = sh(["sudo", "-n", "insmod", KO] + arm_params(arm, L, table))
    if r.returncode != 0:
        raise Stop(f"insmod failed rc={r.returncode}: {r.stderr.strip()} (cannot continue with a known module)")
    srcv = read_sys("/sys/module/nvidia_uvm/srcversion")
    if srcv != EXPECTED_SRCVERSION:
        raise Stop(f"condition 6: loaded srcversion {srcv} != expected {EXPECTED_SRCVERSION}")
    for k, v in expected_sysparams(arm, L).items():
        got = read_sys(f"/sys/module/nvidia_uvm/parameters/{k}")
        if got != v:
            raise Stop(f"condition 7: module param {k}={got}, expected {v} for arm {arm} L={L}")
    return srcv


def check_after(before_lines, out_dir, label):
    after = dmesg_lines()
    new = after[len(before_lines):] if after[:len(before_lines)] == before_lines else after[-200:]
    bad = [l for l in new if BAD.search(l)]
    if bad:
        raise Stop(f"condition 1 ({label}): new dmesg lines matched: " + " | ".join(bad[:10]))
    mem = mem_available_kb()
    if mem < MEM_FLOOR_KB:
        raise Stop(f"condition 4 ({label}): MemAvailable {mem} kB < 6 GiB")
    free = shutil.disk_usage(out_dir).free
    if free < DISK_FLOOR_BYTES:
        raise Stop(f"condition 5 ({label}): free disk {free} B < 10 GiB")
    return len(new), mem, free


def git_commit(paths, msg):
    sh(["git", "-C", REPO, "add"] + paths)
    r = sh(["git", "-C", REPO, "diff", "--cached", "--quiet"])
    if r.returncode == 0:
        return None
    sh(["git", "-C", REPO, "commit", "-q", "-m", msg + "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
        "Claude-Session: https://claude.ai/code/session_013R7hqocoYREgYBhLTAjkLy"])
    return sh(["git", "-C", REPO, "log", "--oneline", "-1"]).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--order", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-dir", required=True, help="raw dump dir (gitignored)")
    ap.add_argument("--tables", required=True, help="dir holding <workload>_ft_table.bin")
    ap.add_argument("--timeout-stencil", type=int, required=True)
    ap.add_argument("--timeout-graphbfs", type=int, required=True)
    ap.add_argument("--dump-decomp", action="store_true")
    ap.add_argument("--commit-every", type=int, default=0)
    ap.add_argument("--label", default="run")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    stop_file = os.path.join(args.out_dir, "STOP")
    if os.path.exists(stop_file):
        print("STOP file exists; refusing to run:", open(stop_file).read())
        return 3

    with open(args.order) as f:
        order = list(csv.DictReader(f))

    done = set()
    fields = ["idx", "ts_utc", "workload", "arm", "L", "wall_s", "bench_result_ms", "exit_code", "srcversion",
              "mem_before_kb", "mem_after_kb", "disk_free_gb", "dmesg_new_lines", "decomp_records"] + COUNTERS
    if os.path.exists(args.csv):
        with open(args.csv) as f:
            done = {r["idx"] for r in csv.DictReader(f)}
    else:
        os.makedirs(os.path.dirname(args.csv), exist_ok=True)
        with open(args.csv, "w", newline="") as f:
            csv.writer(f).writerow(fields)

    since_commit = 0
    for row in order:
        idx, wl, arm, L = row["idx"], row["workload"], row["arm"], (row["L"] or "")
        if idx in done:
            continue
        table = os.path.join(args.tables, f"{wl}_ft_table.bin")
        tmo = args.timeout_stencil if wl == "stencil" else args.timeout_graphbfs
        label = f"{args.label} idx={idx} {wl} {arm}{('-L' + L) if L else ''}"
        try:
            before = dmesg_lines()
            srcv = reload_module(arm, L, table)
            check_after(before, args.out_dir, label + " after insmod")
            clr = subprocess.run(["sudo", "-n", "tee", f"{DBG}/specasync_clear"], input="1",
                                 capture_output=True, text=True)
            if clr.returncode != 0:
                raise Stop(f"({label}): specasync_clear write failed: {clr.stderr.strip()}")
            mem_before = mem_available_kb()
            before = dmesg_lines()
            binargs = BENCH[wl]
            t0 = time.monotonic_ns()
            r = subprocess.run(["timeout", str(tmo), "setarch", "-R"] + binargs, capture_output=True, text=True)
            t1 = time.monotonic_ns()
            if r.returncode == 124:
                raise Stop(f"condition 3 ({label}): benchmark hit its {tmo}s timeout")
            if r.returncode != 0:
                raise Stop(f"({label}): benchmark exited {r.returncode} (not a timeout); stderr tail: {r.stderr[-300:]}")
            time.sleep(1.0)  # let in-flight worker items drain before snapshotting counters (outside timed region)
            m = re.search(r"\[RESULT\] Time: ([0-9.]+) ms", r.stdout)
            res_ms = m.group(1) if m else ""
            ctr = {c: dbg(c) for c in COUNTERS}
            ndec = ""
            if args.dump_decomp:
                dpath = os.path.join(args.out_dir, f"{args.label}_{idx}_{wl}_{arm}{L}_decomp.bin")
                with open(dpath, "wb") as f:
                    subprocess.run(["sudo", "-n", "cat", f"{DBG}/specasync_decomp_log"], stdout=f)
                ndec = str(os.path.getsize(dpath) // 112)
            nnew, mem_after, free = check_after(before, args.out_dir, label + " after run")
        except Stop as e:
            with open(stop_file, "w") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} STOPPED at {label}: {e}\n")
            h = git_commit([args.csv], f"Gate E0.9b {args.label}: STOPPED at idx {idx} -- {str(e)[:120]}")
            print(f"STOP: {e}\ncommit: {h}", flush=True)
            return 3

        out = {"idx": idx, "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "workload": wl, "arm": arm,
               "L": L, "wall_s": f"{(t1 - t0) / 1e9:.6f}", "bench_result_ms": res_ms, "exit_code": r.returncode,
               "srcversion": srcv, "mem_before_kb": mem_before, "mem_after_kb": mem_after,
               "disk_free_gb": f"{free / 1024 ** 3:.1f}", "dmesg_new_lines": nnew, "decomp_records": ndec}
        out.update(ctr)
        with open(args.csv, "a", newline="") as f:
            csv.writer(f).writerow([out[k] for k in fields])
        # wall-clock goes only to the CSV, never to stdout (E0.9b "no interim peeking")
        print(f"done {label} mem_after={mem_after} dmesg_new={nnew}", flush=True)
        since_commit += 1
        if args.commit_every and since_commit >= args.commit_every:
            h = git_commit([args.csv], f"Gate E0.9b {args.label}: rows through idx {idx}")
            print(f"commit {h}", flush=True)
            since_commit = 0

    h = git_commit([args.csv], f"Gate E0.9b {args.label}: all {len(order)} runs complete")
    print(f"COMPLETE commit {h}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
