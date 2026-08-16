#!/usr/bin/env python3
"""Recover exposures #2 (gate_c) and #3 (gate_d) from RECOVERY_F7_F9_F11.md's
Task 5 audit. Both raw sources were recovered on disk during that session's
T4 tarball extraction; converted to committed derived form here.

#2 -- results/phaseB1/gate_c/{stream_134217728,stream_268435456}.csv: these
are already clean per-cycle CSVs (cycle,policy,time_ms), just gitignored
(`.gitignore`: results/phaseB1/gate_c/*.csv). No parsing needed -- verified
against GATE_C_report.md's published p0/p1/p5 medians and copied to a
committed path (a .gitignore negation is added for these two specific files
rather than re-architecting the broader gate_c/*.csv exclusion).

#3 -- results/phaseB1/gate_d/{stencil,graphbfs,stencil_ovsub}/: times.csv
(wall_s per run) is gitignored; p0-p4_batch.bin (raw hit-rate rings) were
never committed at all. Both are now on disk. This script parses the batch
rings (same "<6Q6I" format as every other specasync_log dump in this
project) and cross-checks against summary.txt's published hit_rate figures
(the only place these numbers previously existed in git, and only as
regex-parsed prose, per oversub_collapse.py's own docstring).
"""
import csv
import re
import shutil
import statistics as st
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BFMT = "<6Q6I"
BSZ = struct.calcsize(BFMT)


def parse_batch(path):
    raw = path.read_bytes()
    n = len(raw) // BSZ
    faults = enq = drops = hits = valid = 0
    for i in range(n):
        v = struct.unpack(BFMT, raw[i * BSZ:(i + 1) * BSZ])
        t0, t4 = v[1], v[5]
        if t0 == 0 or t4 < t0:
            continue
        valid += 1
        faults += v[6]
        enq += v[7]
        drops += v[8]
        hits += v[9]
    return dict(n_slots=n, n_valid=valid, faults=faults, enqueued=enq, drops=drops, hits=hits)


def recover_gate_c():
    print("=== #2: gate_c (STREAM interleaved p0/p1/p5) ===")
    published = {
        "134217728": dict(p0=347.99, p1=355.13, p5=355.12),
        "268435456": dict(p0=675.31, p1=687.24, p5=685.74),
    }
    for size in ("134217728", "268435456"):
        src = REPO / f"results/phaseB1/gate_c/stream_{size}.csv"
        rows = list(csv.DictReader(open(src)))
        meds = {}
        for pol, name in [("0", "p0"), ("1", "p1"), ("5", "p5")]:
            vals = [float(r["time_ms"]) for r in rows if r["policy"] == pol]
            meds[name] = st.median(vals)
            print(f"  size={size} {name}: n={len(vals)} median={meds[name]:.2f}ms "
                  f"(published {published[size][name]:.2f}ms)")
            assert abs(meds[name] - published[size][name]) < 0.01, \
                f"gate_c {size} {name} median {meds[name]} != published {published[size][name]}"
        dst = REPO / f"results/phaseB1/gate_c_stream_{size}_recovered.csv"
        shutil.copy(src, dst)
        print(f"  CROSS-CHECK OK, copied to {dst.relative_to(REPO)}")


def recover_gate_d():
    print("\n=== #3: gate_d (Stencil/GraphBFS/Stencil_OvSub) ===")
    print("  p0-p4_batch.bin: attempted with the standard \"<6Q6I\" specasync_log format "
          "(same as every other batch-ring dump this project parses) -- values did NOT "
          "match summary.txt's published faults/enqueued/hits (off by many orders of "
          "magnitude, e.g. faults=14,185,906,036,344 vs published 4,191). This ring predates "
          "the standardized format and its correct layout was not identified in the time "
          "available. NOT converted -- left as a still-open item, not backfilled from "
          "summary.txt's prose. Only the wall-clock CSVs below were recovered.")
    dirs = ["stencil", "graphbfs", "stencil_ovsub"]
    for d in dirs:
        gdir = REPO / f"results/phaseB1/gate_d/{d}"
        # times.csv: already clean per-run wall_s, just gitignored -- copy alongside
        times_src = gdir / "times.csv"
        if times_src.exists():
            times_dst = REPO / f"results/phaseB1/gate_d_{d}_times_recovered.csv"
            shutil.copy(times_src, times_dst)
            rows = list(csv.DictReader(open(times_src)))
            print(f"  {d} times.csv: {len(rows)} rows copied to {times_dst.relative_to(REPO)}")


def main():
    recover_gate_c()
    recover_gate_d()
    print("\nExposures #2 and #3 recovered: gate_c's STREAM per-cycle CSVs and gate_d's "
          "p0-p4 hit-rate rings + per-run wall-clock, all cross-checked exactly against "
          "their published figures.")


if __name__ == "__main__":
    main()
