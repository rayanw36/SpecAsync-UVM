#!/usr/bin/env python3
"""E7-T4 runner wrapper. Imports tests/e7_runner.py UNCHANGED (stock mode) and adds only two things, both
pre-registered in E7T4_PREREGISTRATION.md:
  1. per-workload timeouts = 3 x this machine's smoke median (e7t4_timeouts.json; before it exists, the
     provisional smoke timeouts below, used only for the smoke pass);
  2. the stop condition "an active xrdp or desktop session during a timed run", checked at every
     R.check_after (i.e. after every insmod and every run).
Needs SPECASYNC_REPO=<repo root>. All other arguments pass through to e7_runner.main().
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("SPECASYNC_REPO") or os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
os.environ["SPECASYNC_REPO"] = REPO
sys.path.insert(0, f"{REPO}/tests")
import e7_runner as X  # noqa: E402
R = X.R

PROVISIONAL_SMOKE_TMO = {"graphbfs": 600}          # everything else 300 s: a smoke timeout is a hang, not a measurement
TMO_FILE = f"{HERE}/e7t4_timeouts.json"
tmo = json.load(open(TMO_FILE)) if os.path.exists(TMO_FILE) else {}
for wl, (cmd, old) in list(X.WL.items()):
    X.WL[wl] = (cmd, tmo.get(wl, PROVISIONAL_SMOKE_TMO.get(wl, 300)))


def guard():
    bad = []
    for u in ("xrdp", "xrdp-sesman"):
        if subprocess.run(["systemctl", "is-active", "--quiet", u]).returncode == 0:
            bad.append(f"{u} active")
    for line in subprocess.run(["loginctl", "list-sessions", "--no-legend"], capture_output=True, text=True).stdout.splitlines():
        sid = line.split()[0]
        t = subprocess.run(["loginctl", "show-session", sid, "-p", "Type", "--value"], capture_output=True, text=True).stdout.strip()
        if t in ("x11", "wayland", "mir"):
            bad.append(f"graphical session {sid} ({t})")
    if bad:
        raise R.Stop("pre-registered stop: active xrdp / desktop session during a timed run: " + "; ".join(bad))


# Amendment 2 stop condition: before each run, the benchmark's managed allocation must be below MemAvailable - 4 GiB.
# Managed bytes per workload, from the benchmark sources (cudaMallocManaged calls): stencil 2*N^2*4; stream 3*N*4;
# sgemm 3*N^2*4; cufft N*8; graph_bfs scale 23: V*(8+16*8+4+2*8) = V*156 (upper bound, edges deduplicated).
MANAGED_BYTES = {
    "stencil": 2 * 24000 ** 2 * 4, "stencil8k": 2 * 8000 ** 2 * 4, "sweep4k": 2 * 4000 ** 2 * 4, "sweep16k": 2 * 16000 ** 2 * 4,
    "stream": 3 * 268435456 * 4, "sgemm": 3 * 24000 ** 2 * 4, "cufft": 134217728 * 8, "graphbfs": (1 << 23) * 156 + 8,
}
HEADROOM = 4 * 1024 ** 3


def mem_guard(label):
    wl = label.split()[1]
    need = MANAGED_BYTES.get(wl)
    if need is None:
        raise R.Stop(f"pre-registered stop: no managed-allocation estimate for workload {wl!r}")
    avail = R.mem_available_kb() * 1024
    if not need < avail - HEADROOM:
        raise R.Stop(f"pre-registered stop (Amendment 2): managed allocation {need} B (>= MemAvailable {avail} B - 4 GiB) for {label}")


_orig = R.check_after


def check_after(before, out_dir, label):
    guard()
    if label.endswith("after insmod"):
        mem_guard(label)
    return _orig(before, out_dir, label)


R.check_after = check_after

if __name__ == "__main__":
    sys.exit(X.main())
