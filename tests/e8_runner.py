#!/usr/bin/env python3
"""Gate E8 runner: a COPY of tests/e7_runner.py (E7's runner could not be used unchanged: it discards the benchmark's
stdout and does not dump rings). Same per-run protocol and stop conditions as E7 (reload; srcversion and parameter
read-back incl. uvm_perf_prefetch_threshold; timestamp dmesg diff; `timeout T setarch -R <bench>`; 1 s drain; stop checks;
one CSV row; E7's stock-module mode and e3b_runner.load for module = new rows). The ONLY changes from e7_runner.py:
  1. cell table: the workload table is E8's bench_sparse cells (tests/e8_cells.py); the per-row timeout comes from
     e8/e8_timeouts.csv (label,timeout_s; = 5 x smoke wall, <= 300 s) or is 300 s with --smoke;
  2. the benchmark's stdout is saved to <out>/e8_<idx>_stdout.txt; the per-pass kernel times (descriptive only) are
     parsed into pass1_ms..pass3_ms; a nonzero exit (including a checksum mismatch, rc 1) is already a stop;
  3. rows with dump_rings = 1 (Family M only) dump the batch and decomp rings, outside the timed region, as e3b_runner does;
  4. rows whose label is in e8/dropped_cells.txt (smoke run > 300 s) are skipped (pre-registered, not a departure);
  5. paths / names (e8, results/phaseB1/gate_e8); no stencil table is used.
usage: e8_runner.py --order ORDER --csv CSV --out-dir DIR --commit-msg MSG [--smoke] [--from N] [--through N]
                    [--commit-every N] [--order-sha256 FILE]
"""
import argparse
import csv
import hashlib
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import re  # noqa: E402
import e5_runner  # noqa: E402  (applies the threshold-aware params/expected to e3b_runner)
import e8_cells as C  # noqa: E402
E = e5_runner.E
R = E.R

STOCK_SRCV = "6284DA42F15EDC3AB92332B"
REPO = R.REPO
B = f"{REPO}/benchmarks"
E8 = f"{REPO}/results/analysis/gate_e/e8"


def timeouts(smoke):
    t = {}
    p = f"{E8}/e8_timeouts.csv"
    if not smoke and os.path.exists(p):
        t = {r["label"]: int(r["timeout_s"]) for r in csv.DictReader(open(p))}
    return t


def dropped():
    p = f"{E8}/dropped_cells.txt"
    return {l.split(" | ")[0] for l in open(p) if l.strip() and not l.startswith("#")} if os.path.exists(p) else set()


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
           "srcversion", "mem_before_kb", "mem_after_kb", "disk_free_gb", "dmesg_new_lines", "pass1_ms", "pass2_ms", "pass3_ms", "batch_records", "decomp_records"]
          + E.LOAD_INFO + E.BASE_CTRS + E.NEW_CTRS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--order", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--smoke", action="store_true")
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
    drop = dropped()
    order = [r for r in csv.DictReader(open(args.order)) if r["label"] not in drop]
    tmo_map = timeouts(args.smoke)
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
        cmd, tmo = C.command(REPO, wl), tmo_map.get(row["label"], C.MAX_TMO)
        table = ""
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
                raise R.Stop(f"benchmark exited {r.returncode}; stdout tail: {r.stdout[-200:]} stderr tail: {r.stderr[-300:]}")
            with open(os.path.join(args.out_dir, f"e8_{row['idx']}_stdout.txt"), "w") as f:
                f.write(r.stdout)
            passes = [m for m in re.findall(r"pass \d+ kernel_ms=([0-9.]+)", r.stdout)]
            if len(passes) != C.PASSES or "CHECKSUM OK" not in r.stdout:
                raise R.Stop(f"benchmark output incomplete or checksum not confirmed: {r.stdout[-200:]}")
            time.sleep(1.0)
            if row["module"] == "new":
                ctr = {c: R.dbg(c) for c in E.BASE_CTRS + E.NEW_CTRS}
            nb = nd = ""
            if row["dump_rings"] == "1":
                stem = os.path.join(args.out_dir, f"e8_{row['idx']}")
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
                        f"counters: {ctr}\n--- dmesg tail ---\n{E.dmesg_tail()}\n")
            h = commit([args.csv], f"{args.commit_msg}: STOPPED at {label} -- {str(e)[:100]}")
            print(f"STOP: {e}\ncounters: {ctr}\ncommit: {h}\n--- dmesg tail ---\n{E.dmesg_tail()}", flush=True)
            return 3
        out = {k: row[k] for k in ("idx", "label", "workload", "family", "block", "module", "policy", "depth",
                                   "prefetch", "L", "W", "fast", "trace_faults", "threshold")}
        out.update({"ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "threshold_readback": thr_rb,
                    "prefetch_readback": pf_rb, "wall_s": f"{(t1 - t0) / 1e9:.6f}", "exit_code": r.returncode,
                    "srcversion": srcv, "mem_before_kb": mem_before, "mem_after_kb": mem_after,
                    "disk_free_gb": f"{free / 1024 ** 3:.1f}", "dmesg_new_lines": nnew, "batch_records": nb,
                    "decomp_records": nd, **{f"pass{i + 1}_ms": p for i, p in enumerate(passes)}})
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
