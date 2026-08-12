#!/usr/bin/env python3
"""Convert T3's fresh paired-wallclock sweep decomp .bin captures into the same
per-batch CSV schema as results/phaseC/decomp_stencil_sweep_*.csv, so F5 can be
regenerated against T3's larger, corroborating capture (see GATE_T3_REPORT.md
Section 2: D1+D2 share matches the original within 0.5-1.9pp across all four
sweep sizes). Source .bin files are the raw ring dumps from
results/phaseC/paired_wallclock/decomp/{workload}_trial{1-5}.bin (not committed,
per this project's raw-telemetry convention) -- this script regenerates the
derived CSVs (committed) from them.
"""
import csv
import struct
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DECOMP_DIR = REPO / "results/phaseC/paired_wallclock/decomp"
OUT_DIR = REPO / "results/phaseC/paired_wallclock"

DECOMP_FMT = "<12Q4I"
DECOMP_SIZE = struct.calcsize(DECOMP_FMT)
assert DECOMP_SIZE == 112

WL_TO_SIZE = {"Sweep-4K": "4000", "Sweep-8K": "8000", "Sweep-16K": "16000", "Sweep-24K": "24000"}


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
    for wl, size in WL_TO_SIZE.items():
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
        out_path = OUT_DIR / f"decomp_stencil_sweep_{size}_t3.csv"
        with open(out_path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"{wl} (N={size}): {len(files)} trials, {len(rows)} valid records -> {out_path}")


if __name__ == "__main__":
    main()
