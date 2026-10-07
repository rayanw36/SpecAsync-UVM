#!/usr/bin/env python3
"""Gate E7 orchestrator (smoke and sweep). E6 lessons applied:
  * every deadline is computed HERE from the Phase 0 timestamp file (e7/phase0_start.txt), never from the shell;
  * the computed deadlines are printed and logged at start;
  * the script aborts if any deadline is not later than now.
Deadlines: session cap = Phase 0 + 3 h; reserve for Phases 6-7 = 25 min before the cap.
Family B skip rule (pre-registered): before each Family B workload w, run it only if
    now + 30 * (max smoke wall of w + 4 s) + EST_C2 + RESERVE <= cap,
EST_C2 = 20 * 6 s (Family C block 2, which always runs). The first workload that does not fit is skipped, with
every later Family B workload, whole; each is recorded in e7/family_b_skipped.txt. Nothing else is skipped.
A runner exit != 0 (a stop) ends everything immediately.
usage: e7_orchestrate.py smoke | sweep  [--start-file F]
"""
import csv
import datetime as dt
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E7 = f"{REPO}/results/analysis/gate_e/e7"
RAW = f"{REPO}/results/phaseB1/gate_e7"
WL = ["stencil8k", "sweep4k", "sweep16k", "stream", "sgemm", "cufft", "graphbfs", "oversub"]
CAP_S, RESERVE_S, OVERHEAD_S, EST_C2_S = 3 * 3600, 25 * 60, 4.0, 20 * 6.0
ORDER = f"{E7}/e7_order.csv"


def log(msg):
    line = f"- {time.strftime('%H:%M:%S')} {msg}\n"
    open(f"{E7}/E7_STATUS.md", "a").write(line)
    print(line, end="", flush=True)


def runner(order, csv_path, out, lo, hi, msg):
    cmd = [sys.executable, f"{REPO}/tests/e7_runner.py", "--order", order, "--csv", csv_path, "--out-dir", out,
           "--tables", f"{RAW}/tables", "--commit-msg", msg, "--from", str(lo), "--through", str(hi),
           "--commit-every", "10", "--order-sha256", f"{E7}/e7_order.sha256"]
    return subprocess.run(cmd, cwd=REPO).returncode


def main():
    mode = sys.argv[1]
    sf = sys.argv[sys.argv.index("--start-file") + 1] if "--start-file" in sys.argv else f"{E7}/phase0_start.txt"
    start = dt.datetime.fromisoformat(open(sf).read().strip())
    now = dt.datetime.now(start.tzinfo)
    cap = start + dt.timedelta(seconds=CAP_S)
    last_start = cap - dt.timedelta(seconds=RESERVE_S)
    log(f"orchestrator {mode}: phase0 {start:%H:%M:%S}, now {now:%H:%M:%S}, session cap {cap:%H:%M:%S}, "
        f"latest sweep end (cap - 25 min reserve) {last_start:%H:%M:%S}")
    for name, d in (("session cap", cap), ("sweep deadline", last_start)):
        if d <= now:
            log(f"ABORT: {name} {d:%H:%M:%S} is not later than now {now:%H:%M:%S}")
            return 5
    if mode == "smoke":
        rc = runner(f"{E7}/e7_smoke_order.csv", f"{E7}/e7_smoke.csv", f"{RAW}/smoke", 0, 0, "Gate E7 smoke")
        log(f"smoke runner exit {rc}")
        return rc
    csv_path = f"{E7}/e7_runs.csv"
    smoke = list(csv.DictReader(open(f"{E7}/e7_smoke.csv")))
    est = {w: 30 * (max(float(r["wall_s"]) for r in smoke if r["workload"] == w) + OVERHEAD_S) for w in WL}
    log("Family B estimates (s): " + ", ".join(f"{w} {est[w]:.0f}" for w in WL) + f"; EST_C2 {EST_C2_S:.0f}")
    steps = [("Family C block 1 + Family A", 1, 50)]
    skipped = []
    for k, w in enumerate(WL):
        steps.append((w, 51 + 30 * k, 80 + 30 * k))
    steps.append(("Family C block 2", 291, 310))
    for name, lo, hi in steps:
        if name in WL:
            n = dt.datetime.now(start.tzinfo)
            if skipped or n + dt.timedelta(seconds=est[name] + EST_C2_S) > last_start:
                skipped.append(name)
                open(f"{E7}/family_b_skipped.txt", "a").write(f"{name} skipped at {n:%H:%M:%S}: est {est[name]:.0f} s would pass "
                                                              f"{last_start:%H:%M:%S}\n")
                log(f"SKIP (pre-registered rule): Family B workload {name}")
                continue
        t0 = time.time()
        rc = runner(ORDER, csv_path, f"{RAW}/sweep", lo, hi, f"Gate E7 sweep ({name})")
        log(f"{name}: idx {lo}-{hi}: runner exit {rc} ({time.time() - t0:.0f} s)")
        if rc != 0:
            log(f"STOP (run-class): see {RAW}/sweep/STOP; no retry")
            return rc
    log(f"SWEEP COMPLETE; skipped Family B workloads: {skipped or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
