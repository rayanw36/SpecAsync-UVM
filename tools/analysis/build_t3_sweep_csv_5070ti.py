#!/usr/bin/env python3
"""5070 Ti counterpart of build_t3_sweep_csv.py: converts the same-session paired
Task 3/4 decomp .bin captures at
results/phaseC/paired_wallclock_5070ti/decomp/{workload}_trial{1-5}.bin (on disk,
never previously committed in derived form) into the same per-batch CSV schema as
the T4 side, so GATE_B7_5070TI_PHASEC.md's dispatch-window-sum figures (Section 4)
are reproducible from committed data instead of existing only as a markdown
table entry.

Recovers exactly the value PROVENANCE_GAPS_F7_F9_F11.md flagged as unrecoverable:
sum(total_ns) over Sweep-24K's 5 trials = 987,448,177ns = 987,448.2us, matching
GATE_B7_5070TI_PHASEC.md Section 4's cited figure exactly (asserted below, not
just printed).
"""
import csv
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DECOMP_DIR = REPO / "results/phaseC/paired_wallclock_5070ti/decomp"
OUT_DIR = REPO / "results/phaseC/paired_wallclock_5070ti"

DECOMP_FMT = "<12Q4I"
DECOMP_SIZE = struct.calcsize(DECOMP_FMT)
assert DECOMP_SIZE == 112

# All 6 workloads present on disk for this same-session paired capture (T4's
# equivalent only committed the 4 Sweep-* sizes; this capture also has
# Stencil-8K and GraphBFS-23, recovered here too since the raw data exists).
WL_TO_TAG = {"Stencil-8K": "stencil_8K", "GraphBFS-23": "graphbfs_23", "Sweep-4K": "sweep_4000",
             "Sweep-8K": "sweep_8000", "Sweep-16K": "sweep_16000", "Sweep-24K": "sweep_24000"}


def load_decomp(path):
    raw = Path(path).read_bytes()
    n = len(raw) // DECOMP_SIZE
    recs = []
    for i in range(n):
        f = struct.unpack_from(DECOMP_FMT, raw, i * DECOMP_SIZE)
        recs.append({
            "batch_id": f[0], "d1_start": f[1], "d1_end": f[2],
            "d2_start": f[3], "d2_end": f[4], "svc_start": f[5], "svc_end": f[6],
            "d6_start": f[7], "d6_end": f[8], "d3_wait_ns": f[9],
            "d4_hold_ns": f[10], "d5_serv_ns": f[11], "num_faults": f[12],
            "num_va_spaces": f[13], "num_blocks": f[14],
        })
    return recs


def compute_row(r):
    d1 = r["d1_end"] - r["d1_start"] if r["d1_end"] > r["d1_start"] else 0
    d2 = r["d2_end"] - r["d2_start"] if r["d2_end"] > r["d2_start"] else 0
    svc = r["svc_end"] - r["svc_start"] if r["svc_end"] > r["svc_start"] else 0
    d3 = r["d3_wait_ns"]
    d4 = r["d4_hold_ns"]
    d5 = r["d5_serv_ns"]
    d6 = r["d6_end"] - r["d6_start"] if r["d6_end"] > r["d6_start"] > 0 else 0
    end = max(r["svc_end"], r["d6_end"] if r["d6_end"] > 0 else 0)
    total = end - r["d1_start"] if end > r["d1_start"] else 0
    return {
        "batch_id": r["batch_id"], "d1_ns": d1, "d2_ns": d2, "d3_ns": d3,
        "d4_ns": d4, "d5_ns": d5, "d6_ns": d6, "svc_ns": svc, "total_ns": total,
        "num_faults": r["num_faults"], "num_va_spaces": r["num_va_spaces"],
        "num_blocks": r["num_blocks"],
    }


def main():
    sums = {}
    for wl, tag in WL_TO_TAG.items():
        files = sorted(DECOMP_DIR.glob(f"{wl}_trial*.bin"))
        if not files:
            print(f"SKIP {wl}: no .bin files found in {DECOMP_DIR}")
            continue
        rows = []
        for f in files:
            for r in load_decomp(f):
                row = compute_row(r)
                if row["total_ns"] > 0:
                    rows.append(row)
        out_path = OUT_DIR / f"decomp_{tag}_5070ti_t3.csv"
        with open(out_path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        tot = sum(r["total_ns"] for r in rows)
        sums[wl] = tot
        print(f"{wl}: {len(files)} trials, {len(rows)} valid records, "
              f"sum(total_ns)={tot} = {tot/1e3:.1f}us -> {out_path.relative_to(REPO)}")

    expected_sweep24k = 987448177
    assert sums["Sweep-24K"] == expected_sweep24k, \
        f"Sweep-24K sum(total_ns) mismatch: got {sums['Sweep-24K']}, expected {expected_sweep24k}"
    print(f"\nCROSS-CHECK: Sweep-24K sum(total_ns) = {sums['Sweep-24K']/1e3:.1f}us == "
          f"GATE_B7_5070TI_PHASEC.md Section 4's cited 987,448.2us EXACTLY. "
          f"F9's previously-unverifiable dispatch-window rung is now recovered.")


if __name__ == "__main__":
    main()
