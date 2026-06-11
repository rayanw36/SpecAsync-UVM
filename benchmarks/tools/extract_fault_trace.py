#!/usr/bin/env python3
"""
extract_fault_trace.py — Build an oracle trace from SpecAsync worker log.

Usage:
  python3 extract_fault_trace.py work_records.csv --out oracle_trace.bin

The worker log records (va_addr, enqueue_ts_ns) for each speculative prefetch.
For HIT records, va_addr is a valid demand-fault address that was speculatively
pre-located correctly.  Sorting by enqueue_ts_ns gives the fault temporal order.

For the oracle policy (policy=4), the kernel reads a binary file of u64
addresses and serves them in round-robin order.  This tool produces that file.

Notes:
  - Only HIT records (result=2) are included; MISS/THROTTLED are excluded.
  - Deduplication removes consecutive duplicates.
  - Output is a packed binary of u64 little-endian values.

Alternative: if nsys is available, use --nsys mode to extract from a .nsys-rep.
"""

import struct, sys, csv, os, argparse
from pathlib import Path

RESULT_HIT = 2

def load_work_csv(path):
    """Load work_records.csv; return sorted list of (enqueue_ts_ns, va_addr, result)."""
    recs = []
    with open(path, newline='') as fh:
        for row in csv.DictReader(fh):
            try:
                result = int(float(row['result']))
                va     = int(float(row['va_addr']))
                ts     = int(float(row['enqueue_ts_ns']))
                if va == 0:
                    continue
                recs.append((ts, va, result))
            except (ValueError, KeyError):
                pass
    return sorted(recs)

def extract_oracle_trace(work_csv, hits_only=True, deduplicate=True):
    """Return list of u64 fault addresses in temporal order."""
    recs = load_work_csv(work_csv)
    addrs = []
    prev = None
    for ts, va, result in recs:
        if hits_only and result != RESULT_HIT:
            continue
        if deduplicate and va == prev:
            continue
        addrs.append(va)
        prev = va
    return addrs

def write_trace_bin(addrs, out_path):
    """Write list of u64 addresses as little-endian packed binary."""
    data = struct.pack(f'<{len(addrs)}Q', *addrs)
    Path(out_path).write_bytes(data)
    return len(data)

def main():
    ap = argparse.ArgumentParser(description='Build oracle trace from work_records.csv')
    ap.add_argument('work_csv', help='work_records.csv from specasync_parse.py')
    ap.add_argument('--out', default='oracle_trace.bin',
                    help='Output binary trace file (default: oracle_trace.bin)')
    ap.add_argument('--all-results', action='store_true',
                    help='Include all results (default: hits only)')
    ap.add_argument('--no-dedup', action='store_true',
                    help='Disable consecutive-duplicate removal')
    args = ap.parse_args()

    addrs = extract_oracle_trace(
        args.work_csv,
        hits_only=not args.all_results,
        deduplicate=not args.no_dedup
    )

    if not addrs:
        print("ERROR: no addresses extracted — is this a policy=0 (disabled) run?",
              file=sys.stderr)
        print("       Run with policy=1 (adjacent) to collect speculative hits.",
              file=sys.stderr)
        sys.exit(1)

    n_bytes = write_trace_bin(addrs, args.out)
    print(f"Extracted {len(addrs)} addresses → {args.out} ({n_bytes} bytes)")
    print(f"Unique addresses: {len(set(addrs))}")
    if addrs:
        print(f"Address range: 0x{min(addrs):016x} – 0x{max(addrs):016x}")

if __name__ == '__main__':
    main()
