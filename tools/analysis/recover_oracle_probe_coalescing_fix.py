#!/usr/bin/env python3
"""Recover the positive-control verification for FIX-1 (ARTIFACT_CATALOG.md #1,
the oracle cursor-desync bug) from raw specasync_log batch-ring dumps still on
disk at results/phaseB1/{oracle_probe,oracle_coalesce}/ (gitignored, recovered
during the T4 tarball extraction for the F7/F9/F11 recovery pass; never
previously converted to a committed derived CSV -- see
results/analysis/RECOVERY_F7_F9_F11.md Task 5, exposure #1).

GATE_B_diagnosis.md's headline table:

    | probe                       | OLD ko B83C15DA | NEW ko 090C90A |
    |------------------------------|-----------------:|----------------:|
    | serialized (1 fault/batch)   | 0.99 (self-hit)  | 0.99            |
    | coalesced (7.9 faults/batch) | 0.0175           | 0.4107          |

Two probes x two module builds (before/after FIX-1) = 4 files. The naming on
disk does NOT match the intuitive guess (oracle_probe/ turns out to hold the
SERIALIZED probe, oracle_coalesce/ the COALESCED probe) -- this script
verifies which file is which by recomputing avg faults/batch, not by trusting
the directory name.

Batch-record format: "<6Q6I" (72 bytes), same as every other specasync_log
ring dump this project parses (t_a1_analyze.py, the_squeeze_v2.py, and this
session's recover_t4_prefetch_off_hitrate.py) -- v[1]/v[5] are validity
timestamps, v[6]=num_faults, v[7]=spec_enqueues, v[8]=spec_drops, v[9]=spec_hits.
"""
import csv
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BFMT = "<6Q6I"
BSZ = struct.calcsize(BFMT)
assert BSZ == 72

CANDIDATES = [
    ("oracle_probe", "old_buggy", REPO / "results/phaseB1/oracle_probe/old_buggy_batch.bin"),
    ("oracle_probe", "new_fix", REPO / "results/phaseB1/oracle_probe/new_fix_batch.bin"),
    ("oracle_coalesce", "old", REPO / "results/phaseB1/oracle_coalesce/old_batch.bin"),
    ("oracle_coalesce", "new", REPO / "results/phaseB1/oracle_coalesce/new_batch.bin"),
]

OUT_CSV = REPO / "results/phaseB1/oracle_probe_coalescing_fix_recovered.csv"


def parse(path):
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


def main():
    print("=== Raw batch-ring recovery: oracle_probe/ + oracle_coalesce/ ===")
    rows = []
    parsed = {}
    for dirname, tag, path in CANDIDATES:
        if not path.exists():
            print(f"  SKIP {dirname}/{tag}: {path} not found")
            continue
        d = parse(path)
        avg_faults_per_batch = d["faults"] / d["n_valid"] if d["n_valid"] else float("nan")
        hit_rate = d["hits"] / d["enqueued"] if d["enqueued"] else float("nan")
        print(f"  {dirname}/{tag}: n_valid_batches={d['n_valid']:>4} faults={d['faults']:>4} "
              f"enqueued={d['enqueued']:>4} hits={d['hits']:>4} "
              f"avg_faults/batch={avg_faults_per_batch:.3f} hit_rate={hit_rate:.4f}")
        parsed[(dirname, tag)] = dict(d, avg_faults_per_batch=avg_faults_per_batch, hit_rate=hit_rate)
        rows.append(dict(directory=dirname, tag=tag, **d,
                          avg_faults_per_batch=f"{avg_faults_per_batch:.4f}",
                          hit_rate=f"{hit_rate:.4f}"))

    # Identify probe type empirically (avg faults/batch), not by directory name.
    print("\n=== Probe-type identification (by avg faults/batch, not directory name) ===")
    for key, d in parsed.items():
        kind = "SERIALIZED (~1 fault/batch)" if d["avg_faults_per_batch"] < 2 else "COALESCED (~7.9 faults/batch)"
        print(f"  {key[0]}/{key[1]}: avg_faults/batch={d['avg_faults_per_batch']:.3f} -> {kind}")

    # ---- Cross-check against GATE_B_diagnosis.md's published table ----
    print("\n=== Cross-check vs GATE_B_diagnosis.md's published table ===")

    serialized_old = parsed[("oracle_probe", "old_buggy")]
    serialized_new = parsed[("oracle_probe", "new_fix")]
    assert abs(serialized_old["avg_faults_per_batch"] - 1.0) < 0.01, "oracle_probe/old_buggy is not the serialized probe"
    assert abs(serialized_new["avg_faults_per_batch"] - 1.0) < 0.01, "oracle_probe/new_fix is not the serialized probe"
    assert abs(serialized_old["hit_rate"] - 0.99) < 0.005, f"serialized OLD hit_rate {serialized_old['hit_rate']} != published 0.99"
    assert abs(serialized_new["hit_rate"] - 0.99) < 0.005, f"serialized NEW hit_rate {serialized_new['hit_rate']} != published 0.99"
    print(f"  serialized (oracle_probe/): OLD={serialized_old['hit_rate']:.4f} NEW={serialized_new['hit_rate']:.4f} "
          f"-- both match published '0.99 (degenerate self-hit)' / '0.99' OK")

    coalesced_old = parsed[("oracle_coalesce", "old")]
    coalesced_new = parsed[("oracle_coalesce", "new")]
    assert abs(coalesced_old["avg_faults_per_batch"] - 7.9) < 0.1, "oracle_coalesce/old is not the coalesced probe"
    assert abs(coalesced_new["avg_faults_per_batch"] - 7.9) < 0.1, "oracle_coalesce/new is not the coalesced probe"
    assert round(coalesced_old["hit_rate"], 4) == 0.0175, \
        f"coalesced OLD hit_rate {coalesced_old['hit_rate']:.4f} != published 0.0175"
    assert round(coalesced_new["hit_rate"], 4) == 0.4107, \
        f"coalesced NEW hit_rate {coalesced_new['hit_rate']:.4f} != published 0.4107"
    print(f"  coalesced (oracle_coalesce/): OLD={coalesced_old['hit_rate']:.4f} NEW={coalesced_new['hit_rate']:.4f} "
          f"-- EXACT match to published 0.0175 / 0.4107 OK")

    improvement = coalesced_new["hit_rate"] / coalesced_old["hit_rate"]
    print(f"  improvement: {improvement:.2f}x (published '(23x)', PIPELINE_VALIDATION.md)")
    assert 22.5 < improvement < 23.5, f"improvement {improvement:.2f}x not close to published ~23x"
    print(f"  CROSS-CHECK OK: {improvement:.2f}x reproduces the published ~23x coalescing-fix improvement")

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["directory", "tag", "n_slots", "n_valid", "faults",
                                           "enqueued", "drops", "hits", "avg_faults_per_batch", "hit_rate"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {OUT_CSV.relative_to(REPO)}")
    print("\nFIX-1's positive-control verification (0.0175 -> 0.4107, 23x) is now backed "
          "by a committed, cross-checked derived CSV -- ARTIFACT_CATALOG.md #1's evidence "
          "is reproducible from git, not markdown-only.")


if __name__ == "__main__":
    main()
