#!/usr/bin/env python3
"""E7-T4 orchestrator (smoke and sweep); same design as tests/e7_orchestrate.py with T4 paths.
  * every deadline is computed HERE from phase0_start.txt (T0 = 2026-10-08T16:38:43Z), cap = T0 + 5 h, reserve
    for T6/T7 = 25 min before the cap; logged at start; abort if not later than now;
  * smoke: one run per never-run cell (27), provisional 300 s timeouts (graphbfs 600 s); afterwards the
    timeouts file is written: 3 x the median of that workload's 3 smoke walls, rounded up to whole seconds;
  * sweep: Family A, then Family B workload by workload. Skip rule (pre-registered): before each Family B workload
    w run it only if now + 30 * (max smoke wall of w + 4 s) + RESERVE <= cap; the first workload that does not
    fit is skipped, with every later one, whole, recorded in family_b_skipped.txt;
  * after every step: git push (failure of the push is logged, not a stop);
  * a runner exit != 0 (a stop) ends everything immediately, no retry.
usage: SPECASYNC_REPO=... e7t4_orchestrate.py smoke | sweep
"""
import csv
import datetime as dt
import json
import math
import os
import statistics as st
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("SPECASYNC_REPO") or os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
os.environ["SPECASYNC_REPO"] = REPO
RAW = f"{HERE}/raw"
# Amendment 2: oversubscribed Stencil removed (cannot run on 15.4 GiB host); Family B = 7 workloads, idx 31-240.
WL = ["stencil8k", "sweep4k", "sweep16k", "stream", "sgemm", "cufft", "graphbfs"]
CAP_S, RESERVE_S, OVERHEAD_S = float(os.environ.get("T4_CAP_HOURS", 5)) * 3600, 25 * 60, 4.0
ORDER = f"{HERE}/e7t4_order.csv"
STATUS = f"{HERE}/T4_STATUS.md"


def log(msg):
    line = f"- {time.strftime('%H:%M:%S')} {msg}\n"
    open(STATUS, "a").write(line)
    print(line, end="", flush=True)


def push():
    r = subprocess.run(["git", "-C", REPO, "push", "-q"], capture_output=True, text=True)
    if r.returncode != 0:
        log(f"git push failed (not a stop): {r.stderr.strip()[:200]}")


def runner(order, csv_path, out, lo, hi, msg):
    cmd = [sys.executable, f"{HERE}/e7t4_runner.py", "--order", order, "--csv", csv_path, "--out-dir", out,
           "--tables", f"{RAW}/tables", "--commit-msg", msg, "--from", str(lo), "--through", str(hi),
           "--commit-every", "10", "--order-sha256", f"{HERE}/e7t4_order.sha256"]
    return subprocess.run(cmd, cwd=REPO).returncode


def main():
    mode = sys.argv[1]
    sf = sys.argv[sys.argv.index("--start-file") + 1] if "--start-file" in sys.argv else f"{HERE}/phase0_start.txt"
    start = dt.datetime.fromisoformat(open(sf).read().strip())
    now = dt.datetime.now(start.tzinfo)
    cap = start + dt.timedelta(seconds=CAP_S)
    last_start = cap - dt.timedelta(seconds=RESERVE_S)
    log(f"orchestrator {mode}: T0 {start:%H:%M:%S}, now {now:%H:%M:%S}, session cap {cap:%H:%M:%S}, "
        f"latest sweep end (cap - 25 min reserve) {last_start:%H:%M:%S}")
    for name, d in (("session cap", cap), ("sweep deadline", last_start)):
        if d <= now:
            log(f"ABORT: {name} {d:%H:%M:%S} is not later than now {now:%H:%M:%S}")
            return 5
    if mode == "smoke":
        rc = runner(f"{HERE}/e7t4_smoke_order.csv", f"{HERE}/e7t4_smoke.csv", f"{RAW}/smoke", 0, 24, "E7-T4 smoke")  # Amendment 2: rows 25-27 (oversub) removed
        log(f"smoke runner exit {rc}")
        if rc == 0:
            smoke = list(csv.DictReader(open(f"{HERE}/e7t4_smoke.csv")))
            tmo = {}
            for w in sorted({r["workload"] for r in smoke}):
                walls = [float(r["wall_s"]) for r in smoke if r["workload"] == w]
                tmo[w] = math.ceil(3 * st.median(walls))
            json.dump(tmo, open(f"{HERE}/e7t4_timeouts.json", "w"), indent=1, sort_keys=True)
            log("timeouts (3 x smoke median, ceil s): " + json.dumps(tmo, sort_keys=True))
        push()
        return rc
    csv_path = f"{HERE}/e7t4_runs.csv"
    smoke = list(csv.DictReader(open(f"{HERE}/e7t4_smoke.csv")))
    est = {w: 30 * (max(float(r["wall_s"]) for r in smoke if r["workload"] == w) + OVERHEAD_S) for w in WL}
    log("Family B estimates (s): " + ", ".join(f"{w} {est[w]:.0f}" for w in WL))
    steps = [("Family A", 1, 30)] + [(w, 31 + 30 * k, 60 + 30 * k) for k, w in enumerate(WL)]
    skipped = []
    for name, lo, hi in steps:
        if name in WL:
            n = dt.datetime.now(start.tzinfo)
            if skipped or n + dt.timedelta(seconds=est[name]) > last_start:
                skipped.append(name)
                open(f"{HERE}/family_b_skipped.txt", "a").write(f"{name} skipped at {n:%H:%M:%S}: est {est[name]:.0f} s would pass "
                                                                f"{last_start:%H:%M:%S}\n")
                log(f"SKIP (pre-registered rule): Family B workload {name}")
                continue
        t0 = time.time()
        rc = runner(ORDER, csv_path, f"{RAW}/sweep", lo, hi, f"E7-T4 sweep ({name})")
        log(f"{name}: idx {lo}-{hi}: runner exit {rc} ({time.time() - t0:.0f} s)")
        push()
        if rc != 0:
            log(f"STOP (run-class): see {RAW}/sweep/STOP; no retry")
            return rc
    log(f"SWEEP COMPLETE; skipped Family B workloads: {skipped or 'none'}")
    push()
    return 0


if __name__ == "__main__":
    sys.exit(main())
