#!/usr/bin/env python3
"""Recover per-rep demand-fault/enqueue/hit counts for the T4 prefetch-OFF oracle
sweep (GATE_T4_REPORT.md, GATE_A1_REPORT.md Section 2 correction) from the raw
specasync_log batch-ring dumps still on disk at
results/gate3/telemetry/bench_{stencil,graph_bfs}_C3_run*.bin (gitignored, not
previously committed in any derived form).

BACKGROUND (GATE_A1_REPORT.md's "Root cause confirmed" open item):
t4_prefetch_off_telemetry.sh's run_c3_block never called specasync_clear between
its 15 reps, so each rep's dump is a CUMULATIVE snapshot of the ring since the
last real clear (never). The 131,071-slot ring saturates partway through the
sweep (Stencil: during rep 2; GraphBFS: during rep 5) and then FREEZES --
every dump taken after saturation is a byte-for-byte-identical copy of the same
frozen snapshot, confirmed here empirically (run17..run30 are byte-identical for
Stencil; run50..run60 for GraphBFS).

TWO reconstructions are computed and cross-checked against the two different
published figures that came from this same raw data:

1. CORRECTED (marginal-diff, pre-saturation only) -- consecutive cumulative
   dumps are subtracted to isolate each rep's own marginal contribution, valid
   only while both dumps predate saturation. This is what GATE_A1_REPORT.md's
   correction and GATE_T4_REPORT.md's corrected Section 2 report: Stencil rep 1
   only (clean; rep 2's dump is already saturated, giving a lower-bound only),
   GraphBFS reps 1-4 (all clean; rep 5 saturates).
2. SUPERSEDED (sum-across-all-15-raw-dump-files) -- the original methodology,
   reproduced exactly here to confirm where GATE_T4_REPORT.md Section 1's
   original table (50,964,514 enqueued / 9,933 hits Stencil; 20,505,109
   enqueued / 51,569 hits GraphBFS) came from: summing all 15 raw per-rep dump
   files without accounting for post-saturation duplication multi-counts the
   frozen tail 11x (Stencil) / 10x (GraphBFS). This is NOT a valid rate or count
   and is reproduced ONLY as a provenance cross-check, clearly labeled
   superseded, not as a recommended figure.

Every recomputed value is printed against its published markdown counterpart;
mismatches are raised as errors, not silently absorbed.
"""
import csv
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TELEM_DIR = REPO / "results/gate3/telemetry"
TIMES_CSV = TELEM_DIR / "t4_prefetch_off_times.csv"
OUT_CSV = TELEM_DIR / "t4_prefetch_off_hitrate_recovered.csv"

BFMT = "<6Q6I"
BSZ = struct.calcsize(BFMT)
assert BSZ == 72


def parse_batch_file(path):
    raw = path.read_bytes()
    n = len(raw) // BSZ
    faults = enq = drops = hits = 0
    for i in range(n):
        v = struct.unpack(BFMT, raw[i * BSZ:(i + 1) * BSZ])
        t0, t4 = v[1], v[5]
        if t0 == 0 or t4 < t0:
            continue
        faults += v[6]
        enq += v[7]
        drops += v[8]
        hits += v[9]
    return dict(faults=faults, enq=enq, drops=drops, hits=hits, n_valid_batches=n)


def load_wall_s():
    wall = {}
    with open(TIMES_CSV) as f:
        for r in csv.DictReader(f):
            if r["config"] != "C3":
                continue
            wall[(r["bench"], int(r["rep_in_cell"]))] = float(r["wall_s"])
    return wall


BENCH_RUNS = {
    "bench_stencil": list(range(16, 31)),      # reps 1-15
    "bench_graph_bfs": list(range(46, 61)),    # reps 1-15
}


def main():
    wall = load_wall_s()
    rows = []
    print("=== Raw per-dump cumulative totals (confirms freeze-on-saturation) ===")
    cum = {}
    for bench, runs in BENCH_RUNS.items():
        cum[bench] = []
        for i, run in enumerate(runs, start=1):
            p = TELEM_DIR / f"{bench}_C3_run{run}.bin"
            d = parse_batch_file(p)
            cum[bench].append(d)
            print(f"  {bench} rep{i:>2} (run{run}): n_valid_batches={d['n_valid_batches']:>7} "
                  f"faults={d['faults']:>9} enq={d['enq']:>9} hits={d['hits']:>6}")

    # ---- 1. CORRECTED: marginal diff, pre-saturation reps only ----
    print("\n=== CORRECTED: marginal (pre-saturation) per-rep reconstruction ===")
    CLEAN_REPS = {"bench_stencil": 1, "bench_graph_bfs": 4}  # last clean rep index
    for bench, runs in BENCH_RUNS.items():
        n_clean = CLEAN_REPS[bench]
        prev = dict(faults=0, enq=0, drops=0, hits=0)
        for i in range(1, n_clean + 1):
            d = cum[bench][i - 1]
            marg = {k: d[k] - prev[k] for k in ("faults", "enq", "drops", "hits")}
            prev = d
            w = wall[(bench, i)]
            hit_rate_pct = 100.0 * marg["hits"] / marg["enq"] if marg["enq"] else 0.0
            fault_rate = marg["faults"] / w
            rows.append(dict(bench=bench, rep=i, methodology="corrected_marginal_clean",
                              wall_s=w, faults=marg["faults"], enqueued=marg["enq"],
                              drops=marg["drops"], hits=marg["hits"],
                              hit_rate_pct=f"{hit_rate_pct:.6f}",
                              fault_rate_per_s=f"{fault_rate:.2f}"))
            print(f"  {bench} rep{i}: faults={marg['faults']} enq={marg['enq']} hits={marg['hits']} "
                  f"hit_rate={hit_rate_pct:.4f}% fault_rate={fault_rate:.1f}/s")

    # rep 2 (Stencil) partial lower-bound, matching GATE_A1_REPORT.md's own explicit callout
    d2 = cum["bench_stencil"][1]
    d1 = cum["bench_stencil"][0]
    lb_faults = d2["faults"] - d1["faults"]
    lb_rate = lb_faults / wall[("bench_stencil", 2)]
    print(f"\n  Stencil rep2 PARTIAL lower bound (ring saturates mid-rep2): "
          f"faults>={lb_faults} rate>={lb_rate:.1f}/s")
    rows.append(dict(bench="bench_stencil", rep=2, methodology="corrected_marginal_lower_bound",
                      wall_s=wall[("bench_stencil", 2)], faults=lb_faults, enqueued="",
                      drops="", hits="", hit_rate_pct="", fault_rate_per_s=f"{lb_rate:.2f}"))

    # ---- Cross-check against published figures ----
    print("\n=== Cross-check vs published figures ===")
    stencil_rep1 = rows[0]
    expected_stencil_faults = 3237375
    assert int(stencil_rep1["faults"]) == expected_stencil_faults, \
        f"Stencil rep1 faults mismatch: got {stencil_rep1['faults']}, expected {expected_stencil_faults}"
    print(f"  Stencil rep1 faults: {stencil_rep1['faults']} == {expected_stencil_faults} (GATE_T4_REPORT.md) OK")
    stencil_rate = float(stencil_rep1["fault_rate_per_s"])
    assert 187900 < stencil_rate < 188100, f"Stencil rate {stencil_rate} outside published 187,943-188,001/s band"
    print(f"  Stencil rep1 rate: {stencil_rate:.1f}/s within published 187,943-188,001/s band OK")

    gbfs_marginal = [r for r in rows if r["bench"] == "bench_graph_bfs"]
    expected_gbfs_faults = [446165, 445004, 446415, 445300]
    got_gbfs_faults = [r["faults"] for r in gbfs_marginal]
    assert got_gbfs_faults == expected_gbfs_faults, \
        f"GraphBFS marginal faults mismatch: got {got_gbfs_faults}, expected {expected_gbfs_faults}"
    print(f"  GraphBFS reps1-4 faults: {got_gbfs_faults} == published exactly OK")
    mean_rate = sum(float(r["fault_rate_per_s"]) for r in gbfs_marginal) / 4
    assert abs(mean_rate - 7652.24) < 1.0, f"GraphBFS mean rate {mean_rate} != published 7,652/s"
    print(f"  GraphBFS mean rate: {mean_rate:.2f}/s == published 7,652 faults/s (0.00765M/s) OK")

    # ---- 2. SUPERSEDED: sum-across-all-15-dumps (reproduces the ORIGINAL table) ----
    print("\n=== SUPERSEDED: sum-across-all-15-raw-dumps (reproduces original, NOT a valid rate) ===")
    for bench, runs in BENCH_RUNS.items():
        tot = dict(faults=0, enq=0, drops=0, hits=0)
        for d in cum[bench]:
            for k in tot:
                tot[k] += d[k]
        hit_rate_pct = 100.0 * tot["hits"] / tot["enq"] if tot["enq"] else 0.0
        print(f"  {bench}: enqueued={tot['enq']} hits={tot['hits']} "
              f"hit_rate_raw_fraction={tot['hits']/tot['enq']:.4f} ({hit_rate_pct:.4f}%)")
        rows.append(dict(bench=bench, rep="ALL_15_SUMMED", methodology="superseded_multicounted",
                          wall_s="", faults=tot["faults"], enqueued=tot["enq"], drops=tot["drops"],
                          hits=tot["hits"], hit_rate_pct=f"{hit_rate_pct:.6f}", fault_rate_per_s=""))

    stencil_super = next(r for r in rows if r["bench"] == "bench_stencil" and r["rep"] == "ALL_15_SUMMED")
    assert int(stencil_super["enqueued"]) == 50964514, \
        f"Superseded Stencil enqueued mismatch: {stencil_super['enqueued']} != 50964514"
    assert int(stencil_super["hits"]) == 9933, f"Superseded Stencil hits mismatch: {stencil_super['hits']} != 9933"
    print("  Stencil superseded enqueued=50,964,514 hits=9,933 == GATE_T4_REPORT.md Section 1 table EXACTLY OK")
    gbfs_super = next(r for r in rows if r["bench"] == "bench_graph_bfs" and r["rep"] == "ALL_15_SUMMED")
    assert int(gbfs_super["enqueued"]) == 20505109, \
        f"Superseded GraphBFS enqueued mismatch: {gbfs_super['enqueued']} != 20505109"
    assert int(gbfs_super["hits"]) == 51569, f"Superseded GraphBFS hits mismatch: {gbfs_super['hits']} != 51569"
    print("  GraphBFS superseded enqueued=20,505,109 hits=51,569 == GATE_T4_REPORT.md Section 1 table EXACTLY OK")

    with open(OUT_CSV, "w", newline="") as f:
        fieldnames = ["bench", "rep", "methodology", "wall_s", "faults", "enqueued",
                      "drops", "hits", "hit_rate_pct", "fault_rate_per_s"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {OUT_CSV.relative_to(REPO)}")


if __name__ == "__main__":
    main()
