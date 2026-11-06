#!/usr/bin/env python3
"""Gate H2 residency pass (mechanism; NOT a timed outcome and never in the timing family). For each row of the residency order: reload the stock module
with the row's threshold (h2_runner.load_stock: srcversion and parameter read-back), start `nvidia-smi --query-gpu=timestamp,memory.used --format=csv,noheader,nounits -lms 50`
(the `timestamp` column is added to the pre-registered query so that the 1 s before launch can be identified), wait 1.5 s, launch the benchmark under `setarch -R`,
stop the sampler 0.3 s after exit. baseline = median of the samples in the 1 s before launch; residency = peak sample - baseline (MiB).
Stops (as the timed runner, plus): zero samples, no sample in the pre-launch second, MemAvailable < 4 GiB. Writes <out>/res_<idx>.csv (raw samples) and the summary CSV.
usage: h2_residency.py --order ORDER --csv SUMMARY_CSV --out-dir DIR [--order-sha256 FILE] [--dry-run]"""
import argparse, csv, datetime as dt, hashlib, os, statistics as st, subprocess, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import h2_runner as RN  # noqa: E402
import h2_cells as C  # noqa: E402
R = RN.R
MIB8 = 8 * 1024


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--order", required=True); ap.add_argument("--csv", required=True); ap.add_argument("--out-dir", required=True)
    ap.add_argument("--order-sha256", default=""); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.order_sha256 and hashlib.sha256(open(a.order, "rb").read()).hexdigest() not in open(a.order_sha256).read():
        print("REFUSING: order hash not in", a.order_sha256); return 4
    order = list(csv.DictReader(open(a.order)))
    if a.dry_run:
        print(f"DRY RUN ok: {a.order} accepted, {len(order)} rows; nothing executed"); return 0
    os.makedirs(a.out_dir, exist_ok=True)
    stop_file = os.path.join(a.out_dir, "STOP")
    tmo = RN.timeouts(False)
    done = {r["idx"] for r in csv.DictReader(open(a.csv))} if os.path.exists(a.csv) else set()
    if not os.path.exists(a.csv):
        csv.writer(open(a.csv, "w", newline="")).writerow(["idx", "label", "workload", "threshold", "baseline_mib", "peak_mib", "residency_mib", "residency_frac_8gib", "n_samples", "n_pre_launch", "wall_s", "exit_code"])
    for row in order:
        if row["idx"] in done:
            continue
        label = f"idx={row['idx']} {row['label']}"
        sampler = None
        try:
            srcv = RN.load_stock(row, a.out_dir, label)
            if R.mem_available_kb() < 4 * 1024 * 1024:
                raise R.Stop("host MemAvailable below 4 GiB")
            before = R.dmesg_lines()
            raw = os.path.join(a.out_dir, f"res_{row['idx']}.csv")
            f = open(raw, "w")
            sampler = subprocess.Popen(["nvidia-smi", "--query-gpu=timestamp,memory.used", "--format=csv,noheader,nounits", "-lms", "50"], stdout=f, stderr=subprocess.DEVNULL)
            time.sleep(1.5)
            t_launch = dt.datetime.now()
            t0 = time.monotonic_ns()
            r = subprocess.run(["timeout", str(tmo.get(row["label"], C.MAX_TMO)), "setarch", "-R"] + C.command(RN.REPO, row["workload"]), capture_output=True, text=True)
            t1 = time.monotonic_ns()
            time.sleep(0.3); sampler.terminate(); sampler.wait(); f.close()
            if r.returncode == 124: raise R.Stop("benchmark timeout")
            if r.returncode != 0: raise R.Stop(f"benchmark exited {r.returncode}; {r.stdout[-200:]} {r.stderr[-200:]}")
            if "CHECKSUM OK" not in r.stdout: raise R.Stop("checksum not confirmed")
            S = []
            for l in open(raw):
                p = l.strip().split(", ")
                if len(p) == 2:
                    S.append((dt.datetime.strptime(p[0], "%Y/%m/%d %H:%M:%S.%f"), int(p[1])))
            if not S: raise R.Stop("the GPU memory sampler produced no samples")
            pre = [m for t, m in S if t_launch - dt.timedelta(seconds=1) <= t < t_launch]
            if not pre: raise R.Stop("no sampler sample in the 1 s before launch")
            base, peak = st.median(pre), max(m for t, m in S)
            time.sleep(1.0)
            nnew, mem_after, free = R.check_after(before, a.out_dir, label + " after run")
        except R.Stop as e:
            if sampler and sampler.poll() is None: sampler.terminate()
            open(stop_file, "w").write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} STOPPED at {label}: {e}\n--- dmesg tail ---\n{RN.E.dmesg_tail()}\n")
            print("STOP:", e); return 3
        with open(a.csv, "a", newline="") as g:
            csv.writer(g).writerow([row["idx"], row["label"], row["workload"], row["threshold"], base, peak, peak - base, f"{(peak - base) / MIB8:.4f}", len(S), len(pre), f"{(t1 - t0) / 1e9:.3f}", r.returncode])
        print(f"done {label} residency={peak - base} MiB", flush=True)
    print("COMPLETE"); return 0


if __name__ == "__main__":
    sys.exit(main())
