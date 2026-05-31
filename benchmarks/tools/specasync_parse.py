#!/usr/bin/env python3
"""
specasync_parse.py — Parse SpecAsync-UVM debugfs binary log files.

Usage:
    python3 specasync_parse.py <batch_log> [--work-log <path>] [--out-dir <dir>]

Reads binary dumps of:
    /sys/kernel/debug/nvidia_uvm/specasync_log        (batch records)
    /sys/kernel/debug/nvidia_uvm/specasync_worker_log (work records)

Binary format (little-endian, no compiler-inserted padding — the kernel struct
uses explicit _pad fields to keep layout clean for userspace):

    specasync_batch_record  (72 bytes total,  struct fmt '<6Q6I')
    ─────────────────────────────────────────────────────────────────
    Offset  Sz   Type    Field
       0     8   u64     batch_id
       8     8   u64     t0_ns             batch entry
      16     8   u64     t1_ns             after VA-space lock acquired
      24     8   u64     t2_ns             after metadata discovery (all faults)
      32     8   u64     t3_ns             after residency decision / migration issued
      40     8   u64     t4_ns             batch exit
      48     4   u32     num_faults
      52     4   u32     spec_enqueues
      56     4   u32     spec_drops
      60     4   u32     spec_hits
      64     4   u32     enqueue_overhead_ns
      68     4   u32     _pad              explicit padding, always 0

    specasync_work_record   (48 bytes total,  struct fmt '<4Q4I')
    ─────────────────────────────────────────────────────────────────
    Offset  Sz   Type    Field
       0     8   u64     enqueue_ts_ns
       8     8   u64     dequeue_ts_ns
      16     8   u64     completion_ts_ns
      24     8   u64     va_addr
      32     4   u32     result     0=null 1=miss 2=hit 3=migration_done 4=throttled
      36     4   u32     policy_used
      40     4   u32     _pad[0]    ignored
      44     4   u32     _pad[1]    ignored
"""

import struct
import csv
import sys
import os
import math
import statistics
from pathlib import Path

# ── Struct format strings ────────────────────────────────────────────────────
# '<' = little-endian, no alignment padding (structs are hand-aligned in kernel)
BATCH_FMT  = '<6Q6I'
BATCH_SIZE = struct.calcsize(BATCH_FMT)

WORK_FMT   = '<4Q4I'
WORK_SIZE  = struct.calcsize(WORK_FMT)

assert BATCH_SIZE == 72, f"BATCH_FMT calcsize={BATCH_SIZE}, expected 72 — layout mismatch"
assert WORK_SIZE  == 48, f"WORK_FMT  calcsize={WORK_SIZE},  expected 48 — layout mismatch"

BATCH_FIELDS = (
    'batch_id', 't0_ns', 't1_ns', 't2_ns', 't3_ns', 't4_ns',
    'num_faults', 'spec_enqueues', 'spec_drops', 'spec_hits',
    'enqueue_overhead_ns', '_pad',
)

WORK_FIELDS = (
    'enqueue_ts_ns', 'dequeue_ts_ns', 'completion_ts_ns', 'va_addr',
    'result', 'policy_used', '_pad0', '_pad1',
)

RESULT_NAMES = {0: 'null', 1: 'miss', 2: 'hit', 3: 'migration_done', 4: 'throttled'}


# ── Parsers ──────────────────────────────────────────────────────────────────

def parse_batch_log(path):
    """Read binary batch log; return list of dicts (one per record)."""
    raw  = Path(path).read_bytes()
    n    = len(raw) // BATCH_SIZE
    tail = len(raw) % BATCH_SIZE
    if tail:
        print(f"Warning: {path}: {tail} trailing byte(s) ignored (incomplete record)",
              file=sys.stderr)
    recs = []
    for i in range(n):
        chunk = raw[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]
        vals  = struct.unpack(BATCH_FMT, chunk)
        recs.append(dict(zip(BATCH_FIELDS, vals)))
    return recs


def parse_work_log(path):
    """Read binary worker log; return list of dicts (one per record)."""
    raw  = Path(path).read_bytes()
    n    = len(raw) // WORK_SIZE
    tail = len(raw) % WORK_SIZE
    if tail:
        print(f"Warning: {path}: {tail} trailing byte(s) ignored", file=sys.stderr)
    recs = []
    for i in range(n):
        chunk = raw[i * WORK_SIZE : (i + 1) * WORK_SIZE]
        vals  = struct.unpack(WORK_FMT, chunk)
        recs.append(dict(zip(WORK_FIELDS, vals)))
    return recs


# ── Statistics ───────────────────────────────────────────────────────────────

def _percentile(values, p):
    """Linear-interpolation p-th percentile.  Returns NaN for empty input."""
    if not values:
        return float('nan')
    sv   = sorted(values)
    idx  = (len(sv) - 1) * p / 100.0
    lo   = int(idx)
    hi   = min(lo + 1, len(sv) - 1)
    frac = idx - lo
    return sv[lo] * (1.0 - frac) + sv[hi] * frac


def compute_batch_stats(recs):
    """Compute summary statistics over a list of batch records."""
    if not recs:
        return {}

    total   = [r['t4_ns'] - r['t0_ns'] for r in recs]
    ph01    = [r['t1_ns'] - r['t0_ns'] for r in recs]  # lock acquisition
    ph12    = [r['t2_ns'] - r['t1_ns'] for r in recs]  # metadata discovery
    ph23    = [r['t3_ns'] - r['t2_ns'] for r in recs]  # residency decision

    enqueues = sum(r['spec_enqueues'] for r in recs)
    hits     = sum(r['spec_hits']     for r in recs)
    drops    = sum(r['spec_drops']    for r in recs)

    def block(name, vals):
        return {
            f'{name}_mean_ns':   statistics.mean(vals),
            f'{name}_median_ns': statistics.median(vals),
            f'{name}_p50_ns':    _percentile(vals, 50),
            f'{name}_p95_ns':    _percentile(vals, 95),
            f'{name}_p99_ns':    _percentile(vals, 99),
        }

    out = {
        'num_batches':      len(recs),
        'total_enqueues':   enqueues,
        'total_hits':       hits,
        'total_drops':      drops,
        'hit_rate':         hits / enqueues if enqueues else 0.0,
        'wasted_spec_rate': (enqueues - hits) / enqueues if enqueues else 0.0,
    }
    out.update(block('total_service',   total))
    out.update(block('phase_lock_acq',  ph01))
    out.update(block('phase_metadata',  ph12))
    out.update(block('phase_residency', ph23))
    return out


# ── CSV writers ──────────────────────────────────────────────────────────────

def write_batch_csv(recs, out_path):
    cols = [f for f in BATCH_FIELDS if not f.startswith('_')]
    cols += ['total_latency_ns', 'phase01_ns', 'phase12_ns', 'phase23_ns']
    with open(out_path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in recs:
            row = {k: v for k, v in r.items() if not k.startswith('_')}
            row['total_latency_ns'] = r['t4_ns'] - r['t0_ns']
            row['phase01_ns']       = r['t1_ns'] - r['t0_ns']
            row['phase12_ns']       = r['t2_ns'] - r['t1_ns']
            row['phase23_ns']       = r['t3_ns'] - r['t2_ns']
            w.writerow(row)


def write_work_csv(recs, out_path):
    cols = [f for f in WORK_FIELDS if not f.startswith('_')]
    cols += ['queue_latency_ns', 'exec_latency_ns', 'result_name']
    with open(out_path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in recs:
            row = {k: v for k, v in r.items() if not k.startswith('_')}
            row['queue_latency_ns'] = r['dequeue_ts_ns']    - r['enqueue_ts_ns']
            row['exec_latency_ns']  = r['completion_ts_ns'] - r['dequeue_ts_ns']
            row['result_name']      = RESULT_NAMES.get(r['result'], 'unknown')
            w.writerow(row)


# ── Human-readable summary ───────────────────────────────────────────────────

def print_batch_summary(s):
    print(f"  Batches          : {s['num_batches']}")
    print(f"  Spec enqueues    : {s['total_enqueues']}")
    print(f"  Spec hits        : {s['total_hits']}")
    print(f"  Hit rate         : {s['hit_rate']:.4f}")
    print(f"  Wasted spec rate : {s['wasted_spec_rate']:.4f}")
    print("  Service latency T4-T0 (ns):")
    print(f"    mean={s['total_service_mean_ns']:.1f}  "
          f"median={s['total_service_median_ns']:.1f}  "
          f"p95={s['total_service_p95_ns']:.1f}  "
          f"p99={s['total_service_p99_ns']:.1f}")
    print("  Phase breakdown — mean (ns):")
    print(f"    lock_acq  = {s['phase_lock_acq_mean_ns']:.1f}")
    print(f"    metadata  = {s['phase_metadata_mean_ns']:.1f}")
    print(f"    residency = {s['phase_residency_mean_ns']:.1f}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(
        description='Parse SpecAsync-UVM debugfs binary logs → CSV + statistics.')
    ap.add_argument('batch_log',  help='Binary batch log  (dump of specasync_log)')
    ap.add_argument('--work-log', metavar='PATH',
                    help='Binary worker log (dump of specasync_worker_log)')
    ap.add_argument('--out-dir',  metavar='DIR', default='.',
                    help='Output directory for CSVs (default: .)')
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"[batch] Parsing: {args.batch_log}")
    batches = parse_batch_log(args.batch_log)
    print(f"        {len(batches)} records  ({BATCH_SIZE} B/record)")
    out_b = os.path.join(args.out_dir, 'batch_records.csv')
    write_batch_csv(batches, out_b)
    print(f"        Written: {out_b}")
    stats = compute_batch_stats(batches)
    if stats:
        print_batch_summary(stats)

    if args.work_log:
        print(f"\n[work]  Parsing: {args.work_log}")
        works = parse_work_log(args.work_log)
        print(f"        {len(works)} records  ({WORK_SIZE} B/record)")
        out_w = os.path.join(args.out_dir, 'work_records.csv')
        write_work_csv(works, out_w)
        print(f"        Written: {out_w}")


if __name__ == '__main__':
    main()
