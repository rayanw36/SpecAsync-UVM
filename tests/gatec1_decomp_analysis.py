#!/usr/bin/env python3
"""
gatec1_decomp_analysis.py — Phase C Gate-1 decomp record parser and validator.

Reads /sys/kernel/debug/specasync/specasync_decomp_log (binary, 112 B records)
and validates Gates G1 (accounting closure) and G2 (monotonicity), then prints
the D1-D7 breakdown table for the paper.

Record layout (112 bytes, struct '<12Q4I'):
  batch_id, d1_start, d1_end, d2_start, d2_end,
  svc_start, svc_end, d6_start, d6_end,
  d3_wait_ns, d4_hold_ns, d5_serv_ns,
  num_faults, num_va_spaces, num_blocks, _pad
"""

import struct
import sys
import numpy as np
from pathlib import Path

DECOMP_FMT  = '<12Q4I'
DECOMP_SIZE = struct.calcsize(DECOMP_FMT)   # must be 112
assert DECOMP_SIZE == 112, f"DECOMP_SIZE={DECOMP_SIZE}, expected 112"

DECOMP_LOG  = Path('/sys/kernel/debug/specasync/specasync_decomp_log')
CLOSURE_TOL = 0.02   # Gate G1: D1+D2+svc+D6 must be within 2% of total window


def load_decomp(path=DECOMP_LOG):
    raw = path.read_bytes()
    n = len(raw) // DECOMP_SIZE
    recs = []
    for i in range(n):
        fields = struct.unpack_from(DECOMP_FMT, raw, i * DECOMP_SIZE)
        recs.append({
            'batch_id':    fields[0],
            'd1_start':    fields[1],
            'd1_end':      fields[2],
            'd2_start':    fields[3],
            'd2_end':      fields[4],
            'svc_start':   fields[5],
            'svc_end':     fields[6],
            'd6_start':    fields[7],
            'd6_end':      fields[8],
            'd3_wait_ns':  fields[9],
            'd4_hold_ns':  fields[10],
            'd5_serv_ns':  fields[11],
            'num_faults':  fields[12],
            'num_va_sp':   fields[13],
            'num_blocks':  fields[14],
        })
    return recs


def compute_phases(r):
    """Return phase durations (ns) for one record."""
    d1  = r['d1_end']  - r['d1_start']   if r['d1_end']  > r['d1_start']  else 0
    d2  = r['d2_end']  - r['d2_start']   if r['d2_end']  > r['d2_start']  else 0
    svc = r['svc_end'] - r['svc_start']  if r['svc_end'] > r['svc_start'] else 0
    d3  = r['d3_wait_ns']
    d4  = r['d4_hold_ns']
    d5  = r['d5_serv_ns']
    d6  = (r['d6_end'] - r['d6_start']
           if r['d6_end'] > r['d6_start'] > 0 else 0)
    # total window from d1_start to max of (svc_end, d6_end)
    end  = max(r['svc_end'], r['d6_end'] if r['d6_end'] > 0 else 0)
    total = end - r['d1_start'] if end > r['d1_start'] else 0
    # D7: residual — gaps between phases
    accounted = d1 + d2 + svc + d6
    d7 = max(0, total - accounted)
    return dict(d1=d1, d2=d2, svc=svc, d3=d3, d4=d4, d5=d5, d6=d6,
                total=total, accounted=accounted, d7=d7)


def validate_g1_g2(recs, verbose=False):
    """Gate G1 (closure) and G2 (monotonicity) validation."""
    g1_violations = []
    g2_violations = []
    g1_pass = g2_pass = 0

    for i, r in enumerate(recs):
        p = compute_phases(r)

        # G2: monotonicity checks
        mono_ok = True
        checks = [
            ('d1_start<=d1_end',   r['d1_start'], r['d1_end']),
            ('d2_start<=d2_end',   r['d2_start'], r['d2_end']),
            ('svc_start<=svc_end', r['svc_start'], r['svc_end']),
            ('D5<=D4',             r['d5_serv_ns'], r['d4_hold_ns']),
            ('D3+D4<=svc',         r['d3_wait_ns'] + r['d4_hold_ns'], p['svc']),
        ]
        for label, a, b in checks:
            if a > b:
                g2_violations.append(f"batch {r['batch_id']}: {label} FAIL ({a} > {b})")
                mono_ok = False

        # G1: accounting closure
        if p['total'] > 0:
            frac_unaccounted = p['d7'] / p['total']
            if frac_unaccounted > CLOSURE_TOL:
                g1_violations.append(
                    f"batch {r['batch_id']}: unaccounted {frac_unaccounted*100:.1f}% "
                    f"(d1+d2+svc+d6={p['accounted']:.0f} total={p['total']:.0f})")
            else:
                g1_pass += 1
        if mono_ok:
            g2_pass += 1

    return g1_violations, g1_pass, g2_violations, g2_pass


def print_breakdown(recs, label=''):
    """Print D1-D7 median table."""
    phases = [compute_phases(r) for r in recs if compute_phases(r)['total'] > 0]
    if not phases:
        print("No valid records.")
        return

    keys = ['d1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'total', 'svc']
    arr = {k: np.array([p[k] for p in phases]) for k in keys}

    total_med = np.median(arr['total'])
    svc_med   = np.median(arr['svc'])

    print(f"\n{'='*70}")
    print(f"Phase C dispatch-window decomposition  {label}")
    print(f"  n = {len(phases)} batches")
    print(f"{'='*70}")
    print(f"{'Sub-phase':<30} {'Median µs':>10} {'p95 µs':>10} {'% of total':>12}")
    print(f"{'-'*70}")

    phase_labels = {
        'd1':  'D1 fault-buffer drain',
        'd2':  'D2 preprocess/sort/dedup',
        'd3':  'D3 va_space lock WAIT',
        'd4':  'D4 va_space lock HOLD (incl D5)',
        'd5':  '  D5 dispatch (inside D4)',
        'd6':  'D6 replay push',
        'd7':  'D7 residual (gaps)',
        'svc': 'svc_total (D3+D4+overhead)',
    }

    for k in ['d1', 'd2', 'svc', 'd3', 'd4', 'd5', 'd6', 'd7']:
        med_us = np.median(arr[k]) / 1e3
        p95_us = np.percentile(arr[k], 95) / 1e3
        pct    = np.median(arr[k]) / total_med * 100 if total_med > 0 else 0
        print(f"{phase_labels.get(k, k):<30} {med_us:>10.2f} {p95_us:>10.2f} {pct:>11.1f}%")

    print(f"{'-'*70}")
    total_us = total_med / 1e3
    print(f"{'TOTAL window':<30} {total_us:>10.2f}")
    print(f"\n  Fault count distribution (faults/batch):")
    faults = np.array([r['num_faults'] for r in recs if r['num_faults'] > 0])
    if len(faults):
        print(f"    median={np.median(faults):.0f}  p95={np.percentile(faults,95):.0f}  "
              f"min={faults.min()}  max={faults.max()}")
    va_spaces = np.array([r['num_va_sp'] for r in recs if r['num_va_sp'] > 0])
    if len(va_spaces):
        print(f"  VA-space acquisitions/batch: median={np.median(va_spaces):.0f}  "
              f"p95={np.percentile(va_spaces,95):.0f}")
    blocks = np.array([r['num_blocks'] for r in recs if r['num_blocks'] > 0])
    if len(blocks):
        print(f"  dispatch calls/batch: median={np.median(blocks):.0f}  "
              f"p95={np.percentile(blocks,95):.0f}")


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DECOMP_LOG
    label = sys.argv[2] if len(sys.argv) > 2 else path.name

    if not path.exists():
        print(f"ERROR: {path} not found. Is the phaseC module loaded?", file=sys.stderr)
        sys.exit(1)

    recs = load_decomp(path)
    print(f"Loaded {len(recs)} decomp records from {path}")

    if not recs:
        print("No records. Did you run a workload?")
        sys.exit(1)

    # G2 / G1 validation
    g1_v, g1_p, g2_v, g2_p = validate_g1_g2(recs)

    print(f"\n=== Gate G2 (monotonicity): {g2_p}/{len(recs)} pass ===")
    for v in g2_v[:10]:
        print(f"  FAIL: {v}")
    if len(g2_v) > 10:
        print(f"  ... ({len(g2_v)-10} more)")

    print(f"\n=== Gate G1 (accounting closure ±{CLOSURE_TOL*100:.0f}%): "
          f"{g1_p}/{len(recs)} pass ===")
    for v in g1_v[:10]:
        print(f"  FAIL: {v}")
    if len(g1_v) > 10:
        print(f"  ... ({len(g1_v)-10} more)")

    print_breakdown(recs, label=label)

    # CSV output for further analysis
    csv_path = Path('results/phaseC/decomp_' + label.replace(' ', '_') + '.csv')
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, 'w') as f:
        f.write('batch_id,d1_ns,d2_ns,d3_ns,d4_ns,d5_ns,d6_ns,svc_ns,total_ns,'
                'num_faults,num_va_spaces,num_blocks\n')
        for r in recs:
            p = compute_phases(r)
            f.write(f"{r['batch_id']},{p['d1']},{p['d2']},{p['d3']},{p['d4']},"
                    f"{p['d5']},{p['d6']},{p['svc']},{p['total']},"
                    f"{r['num_faults']},{r['num_va_sp']},{r['num_blocks']}\n")
    print(f"\nCSV written to {csv_path}")


if __name__ == '__main__':
    main()
