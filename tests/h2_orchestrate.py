#!/usr/bin/env python3
"""Gate H2 orchestrator (smoke and sweep), after tests/e8_orchestrate.py. Deadlines are computed HERE from h1/phase0_start.txt, printed and logged at start;
the script aborts if any deadline is not later than now. Session cap = Phase 0 + 4 h; reserve for the summary = 25 min before the cap.
smoke: runs h2_smoke_order.csv (one run per cell, timeout 300 s, every stop condition applied); a smoke run that times out (> 300 s) drops that cell
  (recorded in h1/dropped_cells.txt; pre-registered, not a departure) and the smoke continues; any other stop ends everything. Afterwards writes
  h1/h2_timeouts.csv (timeout = ceil(5 x smoke wall), at most 300 s).
sweep: in-memory cells (idx 1-160); there are no oversubscribed cells in H2. (inherited text: only if now + sum over those cells of 10 x (smoke wall + 4 s) <= cap - reserve,
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
import h2_cells as C  # noqa: E402
H1 = f"{REPO}/results/analysis/gate_e/h2"
RAW = f"{REPO}/results/phaseB1/gate_h2"
CAP_S, RESERVE_S, OVERHEAD_S = 4 * 3600, 25 * 60, 4.0
ORDER = f"{H1}/h2_order.csv"
TRAILER = "Claude-Session: https://claude.ai/code/session_013R7hqocoYREgYBhLTAjkLy"


def log(msg):
    line = f"- {time.strftime('%H:%M:%S')} {msg}\n"
    open(f"{H1}/H2_STATUS.md", "a").write(line)
    print(line, end="", flush=True)


def runner(order, csv_path, out, lo, hi, msg, smoke=False):
    cmd = [sys.executable, f"{REPO}/tests/h2_runner.py", "--order", order, "--csv", csv_path, "--out-dir", out, "--commit-msg", msg, "--from", str(lo), "--through", str(hi),
           "--commit-every", "10", "--order-sha256", f"{H1}/h2_order.sha256"] + (["--smoke"] if smoke else [])
    return subprocess.run(cmd, cwd=REPO).returncode


def push(what):
    r = subprocess.run(["git", "-C", REPO, "push"], capture_output=True, text=True, timeout=120)
    log(f"push after {what}: {'ok' if r.returncode == 0 else 'FAILED (' + r.stderr.strip()[-120:] + ')'}")


def smoke():
    out, csv_path = f"{RAW}/smoke", f"{H1}/h2_smoke.csv"
    lo = 0
    while True:
        rc = runner(f"{H1}/h2_smoke_order.csv", csv_path, out, lo, 0, "Gate H2 smoke", smoke=True)
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
    with open(f"{H1}/h2_timeouts.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["label", "timeout_s"])
        for r in rows:
            w.writerow([r["label"], min(C.MAX_TMO, math.ceil(5 * float(r["wall_s"])))])
    log(f"smoke complete: {len(rows)} rows; h2_timeouts.csv written")
    subprocess.run(["git", "-C", REPO, "add", H1], check=False)
    subprocess.run(["git", "-C", REPO, "commit", "-q", "-m", f"Gate H2 smoke: timeouts and dropped cells\n\n{TRAILER}"], check=False)
    push("smoke")
    return 0


def sweep(start, cap, last_start):
    wall = {r["label"]: float(r["wall_s"]) for r in csv.DictReader(open(f"{H1}/h2_smoke.csv"))}
    order = list(csv.DictReader(open(ORDER)))
    csv_path, out = f"{H1}/h1_runs.csv", f"{RAW}/sweep"

    def run_range(name, lo, hi):
        t0 = time.time()
        rc = runner(ORDER, csv_path, out, lo, hi, f"Gate H2 sweep ({name})")
        log(f"{name}: idx {lo}-{hi}: runner exit {rc} ({time.time() - t0:.0f} s)")
        if rc != 0:
            log(f"STOP (run-class): see {out}/STOP; no retry")
            return rc
        push(name)
        return 0
    rc = run_range("timed cells", 1, 160)
    if rc:
        return rc
    # Amendment 1: no oversubscribed stage (removed cells)
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
