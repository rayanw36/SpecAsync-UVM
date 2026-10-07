#!/usr/bin/env python3
"""Gate E8 orchestrator (smoke and sweep). E7 lessons: every deadline is computed HERE from e8/phase0_start.txt,
printed and logged at start, and the script aborts if any deadline is not later than now.
Deadlines: session cap = Phase 0 + 3.5 h; reserve for Phases 6-7 = 25 min before the cap.

smoke: runs e8_smoke_order.csv with every timeout 300 s. A smoke run that times out (> 300 s) drops that cell
  (recorded in e8/dropped_cells.txt; pre-registered, not a departure) and the smoke continues; any other stop ends
  everything. Afterwards writes e8/e8_timeouts.csv (timeout = ceil(5 x smoke wall), at most 300 s).
sweep: Family IN (idx 1-120, always), Family OV by K group in the order K = 1, 512, 8, 64, then Family M.
  Pre-registered skip rule: before each OV K-group, run it only if now + sum over its cells of 10 x (smoke wall + 4 s) +
  reserve <= cap; the first group that does not fit is skipped with all later OV groups, whole, and recorded in
  e8/ov_skipped.txt. Family M runs last only if now + 5 x sum(M cell smoke wall + 5 s) + reserve <= cap, else it is
  recorded in e8/m_skipped.txt. A runner exit != 0 (a stop) ends everything immediately. After every family / group the
  CSV is committed (by the runner) and pushed here; a failed push is logged, not a stop.
usage: e8_orchestrate.py smoke | sweep [--start-file F]
"""
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
import e8_cells as C  # noqa: E402
E8 = f"{REPO}/results/analysis/gate_e/e8"
RAW = f"{REPO}/results/phaseB1/gate_e8"
CAP_S, RESERVE_S, OVERHEAD_S, OVERHEAD_M_S = int(3.5 * 3600), 25 * 60, 4.0, 5.0
ORDER = f"{E8}/e8_order.csv"


def log(msg):
    line = f"- {time.strftime('%H:%M:%S')} {msg}\n"
    open(f"{E8}/E8_STATUS.md", "a").write(line)
    print(line, end="", flush=True)


def runner(order, csv_path, out, lo, hi, msg, smoke=False):
    cmd = [sys.executable, f"{REPO}/tests/e8_runner.py", "--order", order, "--csv", csv_path, "--out-dir", out,
           "--commit-msg", msg, "--from", str(lo), "--through", str(hi), "--commit-every", "10",
           "--order-sha256", f"{E8}/e8_order.sha256"] + (["--smoke"] if smoke else [])
    return subprocess.run(cmd, cwd=REPO).returncode


def push(what):
    r = subprocess.run(["git", "-C", REPO, "push"], capture_output=True, text=True, timeout=120)
    log(f"push after {what}: {'ok' if r.returncode == 0 else 'FAILED (' + r.stderr.strip()[-120:] + ')'}")


def smoke():
    out, csv_path = f"{RAW}/smoke", f"{E8}/e8_smoke.csv"
    lo = 0
    while True:
        rc = runner(f"{E8}/e8_smoke_order.csv", csv_path, out, lo, 0, "Gate E8 smoke", smoke=True)
        if rc == 0:
            break
        stop = open(f"{out}/STOP").read() if os.path.exists(f"{out}/STOP") else ""
        m = re.search(r"STOPPED at idx=(\d+) (.*?): benchmark timeout \(300 s\)", stop)
        if rc == 3 and m:
            open(f"{E8}/dropped_cells.txt", "a").write(f"{m.group(2)} | smoke run exceeded 300 s (idx {m.group(1)})\n")
            log(f"smoke: cell '{m.group(2)}' exceeded 300 s -> DROPPED (pre-registered rule)")
            os.remove(f"{out}/STOP")
            lo = int(m.group(1)) + 1
            continue
        log(f"STOP (run-class) in smoke: see {out}/STOP; no retry")
        return rc
    rows = list(csv.DictReader(open(csv_path)))
    with open(f"{E8}/e8_timeouts.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["label", "timeout_s"])
        for r in rows:
            w.writerow([r["label"], min(C.MAX_TMO, math.ceil(5 * float(r["wall_s"])))])
    log(f"smoke complete: {len(rows)} rows, dropped cells: "
        f"{open(f'{E8}/dropped_cells.txt').read().count(chr(10)) if os.path.exists(f'{E8}/dropped_cells.txt') else 0}; e8_timeouts.csv written")
    subprocess.run(["git", "-C", REPO, "add", f"{E8}"], check=False)
    subprocess.run(["git", "-C", REPO, "commit", "-q", "-m", "Gate E8 smoke: timeouts and dropped cells\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_013R7hqocoYREgYBhLTAjkLy"], check=False)
    push("smoke")
    return 0


def sweep(start, cap, last_start):
    sm = list(csv.DictReader(open(f"{E8}/e8_smoke.csv")))
    wall = {r["label"]: float(r["wall_s"]) for r in sm}
    order = list(csv.DictReader(open(ORDER)))
    csv_path, out = f"{E8}/e8_runs.csv", f"{RAW}/sweep"

    def run_range(name, lo, hi):
        t0 = time.time()
        rc = runner(ORDER, csv_path, out, lo, hi, f"Gate E8 sweep ({name})")
        log(f"{name}: idx {lo}-{hi}: runner exit {rc} ({time.time() - t0:.0f} s)")
        if rc != 0:
            log(f"STOP (run-class): see {out}/STOP; no retry")
            return rc
        push(name)
        return 0

    rc = run_range("Family IN", 1, 120)
    if rc:
        return rc
    skipped = []
    for g, K in enumerate(C.OV_K_ORDER):
        lo, hi = 121 + 30 * g, 150 + 30 * g
        key = f"ov_k{K}"
        est = sum(10 * (wall[r["label"]] + OVERHEAD_S) for r in order if r["workload"] == key and r["label"] in wall and r["family"] == "OV" and int(r["block"]) == 1)
        now = dt.datetime.now(start.tzinfo)
        if skipped or now + dt.timedelta(seconds=est) > last_start:
            skipped.append(key)
            open(f"{E8}/ov_skipped.txt", "a").write(f"{key} skipped at {now:%H:%M:%S}: est {est:.0f} s would pass {last_start:%H:%M:%S}\n")
            log(f"SKIP (pre-registered rule): Family OV group {key} (est {est:.0f} s)")
            continue
        log(f"Family OV group {key}: est {est:.0f} s, starting")
        rc = run_range(f"Family OV {key}", lo, hi)
        if rc:
            return rc
    mcells = {r["label"] for r in order if r["family"] == "M"}
    est_m = 5 * sum(wall.get(l, 0) + OVERHEAD_M_S for l in mcells)
    now = dt.datetime.now(start.tzinfo)
    if now + dt.timedelta(seconds=est_m) > last_start:
        open(f"{E8}/m_skipped.txt", "w").write(f"Family M skipped at {now:%H:%M:%S}: est {est_m:.0f} s would pass {last_start:%H:%M:%S}\n")
        log("SKIP (pre-registered rule): Family M")
    else:
        rc = run_range("Family M", 241, 260)
        if rc:
            return rc
    log(f"SWEEP COMPLETE; skipped OV groups: {skipped or 'none'}")
    return 0


def main():
    mode = sys.argv[1]
    sf = sys.argv[sys.argv.index("--start-file") + 1] if "--start-file" in sys.argv else f"{E8}/phase0_start.txt"
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
    return smoke() if mode == "smoke" else sweep(start, cap, last_start)


if __name__ == "__main__":
    sys.exit(main())
