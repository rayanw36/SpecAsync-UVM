#!/usr/bin/env python3
"""Gate H1 orchestrator (smoke and sweep), after tests/e8_orchestrate.py. Deadlines are computed HERE from h1/phase0_start.txt, printed and logged at start;
the script aborts if any deadline is not later than now. Session cap = Phase 0 + 4 h; reserve for the summary = 25 min before the cap.
smoke: runs h1_smoke_order.csv (one run per cell, timeout 300 s, every stop condition applied); a smoke run that times out (> 300 s) drops that cell
  (recorded in h1/dropped_cells.txt; pre-registered, not a departure) and the smoke continues; any other stop ends everything. Afterwards writes
  h1/h1_timeouts.csv (timeout = ceil(5 x smoke wall), at most 300 s).
sweep: in-memory cells (idx 1-60) always; the oversubscribed cells (idx 61-100) only if now + sum over those cells of 10 x (smoke wall + 4 s) <= cap - reserve,
  else skipped WHOLE and recorded in h1/ov_skipped.txt (pre-registered, not a departure). A runner exit != 0 (a stop) ends everything immediately.
usage: h1_orchestrate.py smoke | sweep [--start-file F]"""
import csv
import datetime as dt
import math
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f"{REPO}/tests")
import h1_cells as C  # noqa: E402
H1 = f"{REPO}/results/analysis/gate_e/h1"
RAW = f"{REPO}/results/phaseB1/gate_h1"
CAP_S, RESERVE_S, OVERHEAD_S = 4 * 3600, 25 * 60, 4.0
ORDER = f"{H1}/h1_order.csv"
TRAILER = "Claude-Session: https://claude.ai/code/session_013R7hqocoYREgYBhLTAjkLy"


def log(msg):
    line = f"- {time.strftime('%H:%M:%S')} {msg}\n"
    open(f"{H1}/H1_STATUS.md", "a").write(line)
    print(line, end="", flush=True)


def runner(order, csv_path, out, lo, hi, msg, smoke=False):
    cmd = [sys.executable, f"{REPO}/tests/h1_runner.py", "--order", order, "--csv", csv_path, "--out-dir", out, "--commit-msg", msg, "--from", str(lo), "--through", str(hi),
           "--commit-every", "10", "--order-sha256", f"{H1}/h1_order.sha256"] + (["--smoke"] if smoke else [])
    return subprocess.run(cmd, cwd=REPO).returncode


def push(what):
    r = subprocess.run(["git", "-C", REPO, "push"], capture_output=True, text=True, timeout=120)
    log(f"push after {what}: {'ok' if r.returncode == 0 else 'FAILED (' + r.stderr.strip()[-120:] + ')'}")


def smoke():
    out, csv_path = f"{RAW}/smoke", f"{H1}/h1_smoke.csv"
    lo = 0
    while True:
        rc = runner(f"{H1}/h1_smoke_order.csv", csv_path, out, lo, 0, "Gate H1 smoke", smoke=True)
        if rc == 0:
            break
        stop = open(f"{out}/STOP").read() if os.path.exists(f"{out}/STOP") else ""
        m = re.search(r"STOPPED at idx=(\d+) (.*?): benchmark timeout \(300 s\)", stop)
        if rc == 3 and m:
            open(f"{H1}/dropped_cells.txt", "a").write(f"{m.group(2)} | smoke run exceeded 300 s (idx {m.group(1)})\n")
            log(f"smoke: cell '{m.group(2)}' exceeded 300 s -> DROPPED (pre-registered rule)")
            os.remove(f"{out}/STOP")
            lo = int(m.group(1)) + 1
            continue
        log(f"STOP (run-class) in smoke: see {out}/STOP; no retry")
        return rc
    rows = list(csv.DictReader(open(csv_path)))
    with open(f"{H1}/h1_timeouts.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["label", "timeout_s"])
        for r in rows:
            w.writerow([r["label"], min(C.MAX_TMO, math.ceil(5 * float(r["wall_s"])))])
    log(f"smoke complete: {len(rows)} rows; h1_timeouts.csv written")
    subprocess.run(["git", "-C", REPO, "add", H1], check=False)
    subprocess.run(["git", "-C", REPO, "commit", "-q", "-m", f"Gate H1 smoke: timeouts and dropped cells\n\n{TRAILER}"], check=False)
    push("smoke")
    return 0


def sweep(start, cap, last_start):
    wall = {r["label"]: float(r["wall_s"]) for r in csv.DictReader(open(f"{H1}/h1_smoke.csv"))}
    order = list(csv.DictReader(open(ORDER)))
    csv_path, out = f"{H1}/h1_runs.csv", f"{RAW}/sweep"

    def run_range(name, lo, hi):
        t0 = time.time()
        rc = runner(ORDER, csv_path, out, lo, hi, f"Gate H1 sweep ({name})")
        log(f"{name}: idx {lo}-{hi}: runner exit {rc} ({time.time() - t0:.0f} s)")
        if rc != 0:
            log(f"STOP (run-class): see {out}/STOP; no retry")
            return rc
        push(name)
        return 0
    rc = run_range("in-memory cells", 1, 60)
    if rc:
        return rc
    est = sum(10 * (wall[r["label"]] + OVERHEAD_S) for r in order if r["family"] == "OV" and int(r["block"]) == 1 and r["label"] in wall)
    now = dt.datetime.now(start.tzinfo)
    if now + dt.timedelta(seconds=est) > last_start:
        open(f"{H1}/ov_skipped.txt", "w").write(f"oversubscribed cells skipped at {now:%H:%M:%S}: est {est:.0f} s would pass {last_start:%H:%M:%S}\n")
        log(f"SKIP (pre-registered rule): oversubscribed cells (est {est:.0f} s)")
    else:
        log(f"oversubscribed cells: est {est:.0f} s, starting")
        rc = run_range("oversubscribed cells", 61, 100)
        if rc:
            return rc
    log("SWEEP COMPLETE")
    return 0


def main():
    mode = sys.argv[1]
    sf = sys.argv[sys.argv.index("--start-file") + 1] if "--start-file" in sys.argv else f"{H1}/phase0_start.txt"
    start = dt.datetime.fromisoformat(open(sf).read().strip())
    now = dt.datetime.now(start.tzinfo)
    cap = start + dt.timedelta(seconds=CAP_S)
    last_start = cap - dt.timedelta(seconds=RESERVE_S)
    log(f"orchestrator {mode}: phase0 {start:%H:%M:%S}, now {now:%H:%M:%S}, session cap {cap:%H:%M:%S}, latest sweep end (cap - 25 min reserve) {last_start:%H:%M:%S}")
    for name, d in (("session cap", cap), ("sweep deadline", last_start)):
        if d <= now:
            log(f"ABORT: {name} {d:%H:%M:%S} is not later than now {now:%H:%M:%S}")
            return 5
    return smoke() if mode == "smoke" else sweep(start, cap, last_start)


if __name__ == "__main__":
    sys.exit(main())
