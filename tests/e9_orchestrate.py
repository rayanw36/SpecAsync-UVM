#!/usr/bin/env python3
"""Gate E9 orchestrator (smoke and sweep). E7/E8 lessons: every deadline is computed HERE from e9/cap_anchor.txt (the effective Phase 0
start after the recorded pause; falls back to phase0_start.txt), printed and logged at start, and the script aborts if any deadline is not
later than now. Deadlines: session cap = anchor + 3.5 h; reserve for the report and summary = 25 min before the cap.
smoke: the 14 cells once each (timeout 300 s); any stop ends everything.
sweep: 3 blocks of 14 runs (idx 1-14, 15-28, 29-42). Pre-registered skip rule: before each block, run it only if
  now + sum over the smoke rows of (smoke wall + 8 s) + reserve <= cap; the first block that does not fit is skipped with every later block,
  whole, and recorded in e9/blocks_skipped.txt (n per cell then falls below 3; that is not a departure). A runner exit != 0 ends everything.
The CSV is committed and pushed after every block; a failed push is logged, not a stop.
usage: e9_orchestrate.py smoke | sweep
"""
import csv
import datetime as dt
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E9 = f"{REPO}/results/analysis/gate_e/e9"
RAW = f"{REPO}/results/phaseB1/gate_e9"
CAP_S, RESERVE_S, OVERHEAD_S = int(3.5 * 3600), 25 * 60, 8.0
ORDER = f"{E9}/e9_order.csv"


def log(msg):
    line = f"- {time.strftime('%H:%M:%S')} {msg}\n"
    open(f"{E9}/SESSION_STATUS.md", "a").write(line)
    print(line, end="", flush=True)


def runner(order, csv_path, out, lo, hi, msg, smoke=False):
    cmd = [sys.executable, f"{REPO}/tests/e9_runner.py", "--order", order, "--csv", csv_path, "--out-dir", out, "--commit-msg", msg,
           "--from", str(lo), "--through", str(hi), "--order-sha256", f"{E9}/e9_order.sha256"] + (["--smoke"] if smoke else [])
    return subprocess.run(cmd, cwd=REPO).returncode


def push(what):
    r = subprocess.run(["git", "-C", REPO, "push"], capture_output=True, text=True, timeout=120)
    log(f"push after {what}: {'ok' if r.returncode == 0 else 'FAILED (' + r.stderr.strip()[-120:] + ')'}")


def main():
    mode = sys.argv[1]
    anchor = f"{E9}/cap_anchor.txt" if os.path.exists(f"{E9}/cap_anchor.txt") else f"{E9}/phase0_start.txt"
    start = dt.datetime.fromisoformat(open(anchor).read().strip())
    now = dt.datetime.now(start.tzinfo)
    cap = start + dt.timedelta(seconds=CAP_S)
    last = cap - dt.timedelta(seconds=RESERVE_S)
    log(f"orchestrator {mode}: anchor {start:%F %H:%M:%S} ({os.path.basename(anchor)}), now {now:%H:%M:%S}, session cap {cap:%F %H:%M:%S}, "
        f"latest sweep end (cap - 25 min reserve) {last:%F %H:%M:%S}")
    for name, d in (("session cap", cap), ("sweep deadline", last)):
        if d <= now:
            log(f"ABORT: {name} {d:%F %H:%M:%S} is not later than now {now:%F %H:%M:%S}")
            return 5
    if mode == "smoke":
        rc = runner(f"{E9}/e9_smoke_order.csv", f"{E9}/e9_smoke.csv", f"{RAW}/smoke", 0, 0, "Gate E9 smoke", smoke=True)
        log(f"smoke runner exit {rc}")
        if rc == 0:
            push("smoke")
        return rc
    sm = list(csv.DictReader(open(f"{E9}/e9_smoke.csv")))
    est = sum(float(r["wall_s_NOT_COMPARED"]) + OVERHEAD_S for r in sm)
    log(f"block estimate {est:.0f} s")
    skipped = []
    for b in range(3):
        lo, hi = 1 + 14 * b, 14 * (b + 1)
        n = dt.datetime.now(start.tzinfo)
        if skipped or n + dt.timedelta(seconds=est) > last:
            skipped.append(b + 1)
            open(f"{E9}/blocks_skipped.txt", "a").write(f"block {b + 1} skipped at {n:%H:%M:%S}: est {est:.0f} s would pass {last:%H:%M:%S}\n")
            log(f"SKIP (pre-registered rule): block {b + 1}")
            continue
        t0 = time.time()
        rc = runner(ORDER, f"{E9}/e9_runs.csv", f"{RAW}/sweep", lo, hi, f"Gate E9 sweep (block {b + 1})")
        log(f"block {b + 1}: idx {lo}-{hi}: runner exit {rc} ({time.time() - t0:.0f} s)")
        if rc != 0:
            log(f"STOP (run-class): see {RAW}/sweep/STOP; no retry")
            return rc
        push(f"block {b + 1}")
    log(f"SWEEP COMPLETE; skipped blocks: {skipped or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
