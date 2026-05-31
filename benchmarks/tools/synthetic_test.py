#!/usr/bin/env python3
"""
synthetic_test.py — Validate specasync_parse.py against synthetic binary data.

Generates known batch and work records packed with the same struct layout as
the kernel, parses them via specasync_parse, and asserts every field and every
computed statistic matches ground truth.

This is the iPad-runnable correctness gate. If it passes, the parser is sound
and can be trusted on real hardware data.

Output is printed to stdout AND saved to synthetic_test_results.txt (same dir).
Exit code: 0 = all pass, 1 = any failure.
"""

import struct
import os
import sys
import math
import random
import tempfile
import statistics
import csv as csv_mod

# ── Import parser from the same directory ────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import specasync_parse as sp

# ── Test harness ──────────────────────────────────────────────────────────────

SEED        = 42
NUM_BATCHES = 1000
NUM_WORKS   = 5000

_lines    = []
_failures = 0


def emit(line):
    _lines.append(line)
    print(line)


def check(name, got, expected, tol=0.0):
    global _failures
    # NaN: both NaN counts as equal
    if isinstance(expected, float) and math.isnan(expected):
        ok = isinstance(got, float) and math.isnan(got)
    elif isinstance(expected, float) or isinstance(tol, float) and tol > 0:
        ok = abs(got - expected) <= max(abs(tol), 1e-9)
    else:
        ok = (got == expected)
    tag = "PASS" if ok else "FAIL"
    if not ok:
        _failures += 1
    emit(f"  [{tag}] {name}")
    if not ok:
        emit(f"         got={got!r}  expected={expected!r}")
    return ok


# ── Test 1: struct size constants ─────────────────────────────────────────────

emit("\n=== Test 1: Struct size constants ===")
check("BATCH_FMT calcsize == 72",  sp.BATCH_SIZE, 72)
check("WORK_FMT  calcsize == 48",  sp.WORK_SIZE,  48)

# ── Test 2: Batch record round-trip ───────────────────────────────────────────

emit("\n=== Test 2: Batch record binary round-trip ===")

rng = random.Random(SEED)

def _rand_ts(base, lo, hi):
    return base + rng.randint(lo, hi)

gt_batches = []
T_BASE = 1_000_000_000  # 1 s base, so timestamps fit in u64 easily

for i in range(NUM_BATCHES):
    t0 = T_BASE + i * 50_000
    t1 = t0 + rng.randint(100,    5_000)
    t2 = t1 + rng.randint(500,   20_000)
    t3 = t2 + rng.randint(1_000, 50_000)
    t4 = t3 + rng.randint(100,    2_000)
    enq  = rng.randint(0, 8)
    hits = rng.randint(0, enq) if enq > 0 and rng.random() < 0.4 else 0
    drops = rng.randint(0, enq - hits) if enq > hits else 0
    gt_batches.append({
        'batch_id':            i,
        't0_ns':               t0,
        't1_ns':               t1,
        't2_ns':               t2,
        't3_ns':               t3,
        't4_ns':               t4,
        'num_faults':          rng.randint(1, 64),
        'spec_enqueues':       enq,
        'spec_drops':          drops,
        'spec_hits':           hits,
        'enqueue_overhead_ns': rng.randint(0, 5_000),
        '_pad':                0,
    })

def pack_batch(r):
    return struct.pack(
        sp.BATCH_FMT,
        r['batch_id'], r['t0_ns'], r['t1_ns'], r['t2_ns'], r['t3_ns'], r['t4_ns'],
        r['num_faults'], r['spec_enqueues'], r['spec_drops'], r['spec_hits'],
        r['enqueue_overhead_ns'], r['_pad'],
    )

batch_bin = b''.join(pack_batch(r) for r in gt_batches)
check("packed size == NUM_BATCHES × BATCH_SIZE",
      len(batch_bin), NUM_BATCHES * sp.BATCH_SIZE)

with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as tf:
    batch_path = tf.name
    tf.write(batch_bin)

try:
    parsed = sp.parse_batch_log(batch_path)
    check("parsed record count", len(parsed), NUM_BATCHES)

    # Spot-check first, middle, last
    for idx in (0, NUM_BATCHES // 2, NUM_BATCHES - 1):
        gt = gt_batches[idx]
        pr = parsed[idx]
        for f in ('batch_id', 't0_ns', 't1_ns', 't2_ns', 't3_ns', 't4_ns',
                  'num_faults', 'spec_enqueues', 'spec_drops', 'spec_hits',
                  'enqueue_overhead_ns'):
            check(f"batch[{idx}].{f}", pr[f], gt[f])

    # Full sweep: count any mismatch across sentinel fields
    mismatches = sum(
        1 for gt, pr in zip(gt_batches, parsed)
        if any(pr[f] != gt[f] for f in
               ('batch_id', 't0_ns', 't4_ns', 'spec_enqueues', 'spec_hits'))
    )
    check("full sweep mismatch count", mismatches, 0)
finally:
    os.unlink(batch_path)

# ── Test 3: Work record round-trip ────────────────────────────────────────────

emit("\n=== Test 3: Work record binary round-trip ===")

gt_works = []
for i in range(NUM_WORKS):
    enq_ts  = T_BASE + i * 10_000
    deq_ts  = enq_ts + rng.randint(1_000,  100_000)
    comp_ts = deq_ts + rng.randint(5_000,  500_000)
    gt_works.append({
        'enqueue_ts_ns':     enq_ts,
        'dequeue_ts_ns':     deq_ts,
        'completion_ts_ns':  comp_ts,
        'va_addr':           (rng.randint(0, (1 << 47) - 1) >> 12) << 12,
        'result':            rng.randint(0, 4),
        'policy_used':       rng.randint(0, 3),
        '_pad0':             0,
        '_pad1':             0,
    })

def pack_work(r):
    return struct.pack(
        sp.WORK_FMT,
        r['enqueue_ts_ns'], r['dequeue_ts_ns'], r['completion_ts_ns'], r['va_addr'],
        r['result'], r['policy_used'], r['_pad0'], r['_pad1'],
    )

work_bin = b''.join(pack_work(r) for r in gt_works)
check("packed size == NUM_WORKS × WORK_SIZE",
      len(work_bin), NUM_WORKS * sp.WORK_SIZE)

with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as tf:
    work_path = tf.name
    tf.write(work_bin)

try:
    parsed_works = sp.parse_work_log(work_path)
    check("parsed work record count", len(parsed_works), NUM_WORKS)

    for idx in (0, NUM_WORKS // 2, NUM_WORKS - 1):
        gt = gt_works[idx]
        pr = parsed_works[idx]
        for f in ('enqueue_ts_ns', 'dequeue_ts_ns', 'completion_ts_ns',
                  'va_addr', 'result', 'policy_used'):
            check(f"work[{idx}].{f}", pr[f], gt[f])

    work_mismatches = sum(
        1 for gt, pr in zip(gt_works, parsed_works)
        if any(pr[f] != gt[f] for f in
               ('enqueue_ts_ns', 'va_addr', 'result', 'policy_used'))
    )
    check("full work sweep mismatch count", work_mismatches, 0)
finally:
    os.unlink(work_path)

# ── Test 4: Statistics on controlled dataset ──────────────────────────────────

emit("\n=== Test 4: Statistics correctness (controlled dataset) ===")

# 100 records, all with identical phase durations — every statistic is deterministic
controlled = []
for i in range(100):
    t0 = T_BASE + i * 100_000
    controlled.append({
        'batch_id':            i,
        't0_ns':               t0,
        't1_ns':               t0 + 1_000,   # lock_acq  = 1000 ns
        't2_ns':               t0 + 3_000,   # metadata  = 2000 ns
        't3_ns':               t0 + 6_000,   # residency = 3000 ns
        't4_ns':               t0 + 7_000,   # total     = 7000 ns
        'num_faults':          4,
        'spec_enqueues':       10,            # 100 × 10 = 1000 total
        'spec_drops':          2,
        'spec_hits':           4,             # 100 × 4  = 400 hits  → rate 0.40
        'enqueue_overhead_ns': 500,
        '_pad':                0,
    })

s = sp.compute_batch_stats(controlled)

check("total_service mean  = 7000 ns",     s['total_service_mean_ns'],    7000.0, tol=1e-6)
check("total_service median = 7000 ns",    s['total_service_median_ns'],  7000.0, tol=1e-6)
check("total_service p50   = 7000 ns",     s['total_service_p50_ns'],     7000.0, tol=1e-6)
check("total_service p95   = 7000 ns",     s['total_service_p95_ns'],     7000.0, tol=1e-6)
check("total_service p99   = 7000 ns",     s['total_service_p99_ns'],     7000.0, tol=1e-6)
check("phase_lock_acq mean  = 1000 ns",    s['phase_lock_acq_mean_ns'],   1000.0, tol=1e-6)
check("phase_metadata mean  = 2000 ns",    s['phase_metadata_mean_ns'],   2000.0, tol=1e-6)
check("phase_residency mean = 3000 ns",    s['phase_residency_mean_ns'],  3000.0, tol=1e-6)
check("hit_rate = 0.40",                   s['hit_rate'],                 0.40,   tol=1e-9)
check("wasted_spec_rate = 0.60",           s['wasted_spec_rate'],         0.60,   tol=1e-9)
check("total_enqueues = 1000",             s['total_enqueues'],           1000)
check("total_hits     = 400",              s['total_hits'],               400)
check("num_batches    = 100",              s['num_batches'],              100)

# ── Test 5: _percentile helper ────────────────────────────────────────────────

emit("\n=== Test 5: _percentile() function ===")

vals = list(range(1, 101))   # [1, 2, ..., 100]
# Manual verification:
#   p50: idx = 99 × 0.50 = 49.5 → sv[49]=50, sv[50]=51 → 50 + 0.5×1 = 50.5
#   p95: idx = 99 × 0.95 = 94.05 → sv[94]=95, sv[95]=96 → 95 + 0.05×1 = 95.05
#   p99: idx = 99 × 0.99 = 98.01 → sv[98]=99, sv[99]=100 → 99 + 0.01×1 = 99.01
check("p50  of 1..100 = 50.5",  sp._percentile(vals, 50),  50.5,  tol=1e-9)
check("p95  of 1..100 = 95.05", sp._percentile(vals, 95),  95.05, tol=1e-6)
check("p99  of 1..100 = 99.01", sp._percentile(vals, 99),  99.01, tol=1e-6)
check("p0   of 1..100 = 1.0",   sp._percentile(vals, 0),   1.0,   tol=1e-9)
check("p100 of 1..100 = 100.0", sp._percentile(vals, 100), 100.0, tol=1e-9)
check("empty list → NaN",       sp._percentile([], 50),    float('nan'))

# Single-element list
check("p50 of [42] = 42.0", sp._percentile([42], 50), 42.0, tol=1e-9)

# ── Test 6: CSV round-trip ────────────────────────────────────────────────────

emit("\n=== Test 6: write_batch_csv / write_work_csv round-trip ===")

with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w',
                                 newline='') as tf:
    batch_csv_path = tf.name

try:
    sp.write_batch_csv(controlled, batch_csv_path)
    with open(batch_csv_path, newline='') as fh:
        rows = list(csv_mod.DictReader(fh))

    check("batch CSV row count = 100",           len(rows),                       100)
    check("batch CSV has total_latency_ns col",  'total_latency_ns' in rows[0],   True)
    check("batch CSV has phase01_ns col",        'phase01_ns'       in rows[0],   True)
    check("batch CSV has phase12_ns col",        'phase12_ns'       in rows[0],   True)
    check("batch CSV has phase23_ns col",        'phase23_ns'       in rows[0],   True)
    check("batch CSV _pad col absent",           '_pad'         not in rows[0],   True)

    first = rows[0]
    check("CSV[0] total_latency_ns = 7000", int(float(first['total_latency_ns'])), 7000)
    check("CSV[0] phase01_ns       = 1000", int(float(first['phase01_ns'])),       1000)
    check("CSV[0] phase12_ns       = 2000", int(float(first['phase12_ns'])),       2000)
    check("CSV[0] phase23_ns       = 3000", int(float(first['phase23_ns'])),       3000)
finally:
    os.unlink(batch_csv_path)

# Work CSV
work_sample = [
    {
        'enqueue_ts_ns': 1_000_000_000,
        'dequeue_ts_ns': 1_000_010_000,
        'completion_ts_ns': 1_000_060_000,
        'va_addr': 0x7f0000000000,
        'result': 2,
        'policy_used': 1,
        '_pad0': 0, '_pad1': 0,
    }
]
with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w',
                                 newline='') as tf:
    work_csv_path = tf.name

try:
    sp.write_work_csv(work_sample, work_csv_path)
    with open(work_csv_path, newline='') as fh:
        wrows = list(csv_mod.DictReader(fh))
    check("work CSV row count = 1",              len(wrows), 1)
    check("work CSV queue_latency_ns = 10000",
          int(float(wrows[0]['queue_latency_ns'])), 10_000)
    check("work CSV exec_latency_ns  = 50000",
          int(float(wrows[0]['exec_latency_ns'])),  50_000)
    check("work CSV result_name = 'hit'",        wrows[0]['result_name'], 'hit')
    check("work CSV _pad0 col absent",           '_pad0' not in wrows[0], True)
finally:
    os.unlink(work_csv_path)

# ── Test 7: Trailing-byte warning (does not crash) ────────────────────────────

emit("\n=== Test 7: Trailing bytes handled gracefully ===")

with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as tf:
    trunc_path = tf.name
    # Write 1 full batch record + 13 orphan bytes
    tf.write(pack_batch(gt_batches[0]))
    tf.write(b'\xDE\xAD\xBE\xEF\xCA\xFE\xBA\xBE\x00\x01\x02\x03\x04')

try:
    import io
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    truncated = sp.parse_batch_log(trunc_path)
    warn_output = sys.stderr.getvalue()
    sys.stderr = old_stderr
    check("only 1 complete record parsed",    len(truncated), 1)
    check("first record batch_id correct",   truncated[0]['batch_id'], gt_batches[0]['batch_id'])
    check("warning emitted to stderr",       'trailing' in warn_output.lower(), True)
finally:
    sys.stderr = old_stderr  # safety restore
    os.unlink(trunc_path)

# ── Summary ───────────────────────────────────────────────────────────────────

total_checks = sum(1 for l in _lines if '[PASS]' in l or '[FAIL]' in l)
pass_count   = sum(1 for l in _lines if '[PASS]' in l)
fail_count   = sum(1 for l in _lines if '[FAIL]' in l)

emit("\n" + "=" * 65)
result_str = "ALL TESTS PASSED" if _failures == 0 else f"{_failures} TEST(S) FAILED"
emit(f"{result_str}  ({pass_count}/{total_checks} checks passed)")
emit("Python: " + sys.version.split()[0])
emit("BATCH_SIZE=" + str(sp.BATCH_SIZE) + "  WORK_SIZE=" + str(sp.WORK_SIZE))
emit("Synthetic data: " + str(NUM_BATCHES) + " batches, " + str(NUM_WORKS) + " work records")
emit("=" * 65)

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'synthetic_test_results.txt')
with open(out_path, 'w') as fh:
    fh.write('\n'.join(_lines) + '\n')
print(f"\nResults saved → {out_path}")

sys.exit(0 if _failures == 0 else 1)
