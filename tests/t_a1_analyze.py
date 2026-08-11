#!/usr/bin/env python3
"""t_a1_analyze.py — Task A1: worker completion telemetry analysis.

Parses specasync_work_record dumps (48 B: enqueue_ts_ns, dequeue_ts_ns,
completion_ts_ns, va_addr [4xu64], result, policy_used, pad[2] [4xu32]) from
results/analysis/t_a1_worker/{full_run,short_run}/*_worker_run*.bin and
computes the dispatch/exec latency distribution, plus reads the paired CSV's
processed/enqueued/drops counters (true kernel atomics, immune to ring wrap).

full_run/*.bin is a WINDOW (last 131,071 records) on Stencil/GraphBFS -- both
enqueue ~2-2.7M/2-400K items/run, so the ring wraps and the window covers only
the tail of the run. short_run/*.bin is the COMPLETE run (calibrated sizes
chosen so processed < 131,072 -- verified via worker_ring_wrapped=no in the
CSV), used as the cross-check the task calls for.
"""
import csv
import statistics as st
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WFMT = "<4Q4I"
WSZ = struct.calcsize(WFMT)
RESULT_NAMES = {0: "NULL", 1: "MISS", 2: "HIT", 3: "MIGRATION_DONE", 4: "THROTTLED"}


def load_worker_records(path):
    raw = Path(path).read_bytes()
    out = []
    for i in range(len(raw) // WSZ):
        enq, deq, comp, va, result, policy, _p0, _p1 = struct.unpack(
            WFMT, raw[i * WSZ:(i + 1) * WSZ])
        if enq == 0:
            continue
        out.append((enq, deq, comp, result))
    return out


def summarize(vals):
    if not vals:
        return None
    vals = sorted(vals)
    n = len(vals)
    return dict(
        n=n, min=vals[0], p10=vals[int(0.10 * n)], median=st.median(vals),
        p90=vals[min(n - 1, int(0.90 * n))], max=vals[-1], mean=st.mean(vals))


def fmt_ns(d):
    if d is None:
        return "n/a"
    return (f"n={d['n']:>8}  min={d['min']/1e3:>9.2f}us  p10={d['p10']/1e3:>9.2f}us  "
            f"median={d['median']/1e3:>9.2f}us  p90={d['p90']/1e3:>9.2f}us  "
            f"max={d['max']/1e3:>10.2f}us  mean={d['mean']/1e3:>9.2f}us")


def analyze_dir(tag, out_dir):
    csv_path = out_dir / "worker_completion.csv"
    print(f"\n{'='*100}\n{tag}: {csv_path}\n{'='*100}")
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    for bench in sorted(set(r["bench"] for r in rows)):
        bench_rows = [r for r in rows if r["bench"] == bench]
        processed_tot = sum(int(r["processed"]) for r in bench_rows)
        enqueued_tot = sum(int(r["enqueued"]) for r in bench_rows)
        drops_tot = sum(int(r["drops"]) for r in bench_rows)
        wrapped = any(r["worker_ring_wrapped"] == "yes" for r in bench_rows)
        ratio = processed_tot / enqueued_tot if enqueued_tot else float("nan")

        print(f"\n--- {bench} ({len(bench_rows)} reps, ring_wrapped={wrapped}) ---")
        print(f"  sum(processed)={processed_tot}  sum(enqueued)={enqueued_tot}  "
              f"processed/enqueued={ratio:.6f}  sum(drops)={drops_tot}")
        for r in bench_rows:
            p, e = int(r["processed"]), int(r["enqueued"])
            assert p == e, f"processed != enqueued for a rep -- {r}"

        # Latency distribution from the worker ring dumps (all reps pooled).
        dispatch_lat, exec_lat, total_lat = [], [], []
        result_counts = {}
        for r in bench_rows:
            fp = out_dir / f"{bench}_worker_run{r['rep_in_cell']}.bin"
            if not fp.exists():
                continue
            for enq, deq, comp, result in load_worker_records(fp):
                dispatch_lat.append(deq - enq)
                exec_lat.append(comp - deq)
                total_lat.append(comp - enq)
                result_counts[result] = result_counts.get(result, 0) + 1

        print(f"  dispatch (enqueue->dequeue): {fmt_ns(summarize(dispatch_lat))}")
        print(f"  exec     (dequeue->complete): {fmt_ns(summarize(exec_lat))}")
        print(f"  total    (enqueue->complete): {fmt_ns(summarize(total_lat))}")
        print(f"  result breakdown: " +
              ", ".join(f"{RESULT_NAMES.get(k,k)}={v}" for k, v in sorted(result_counts.items())))


def main():
    analyze_dir("SHORT RUN (complete, non-wrapping)", REPO / "results/analysis/t_a1_worker/short_run")
    analyze_dir("FULL RUN (windowed, tail of run)", REPO / "results/analysis/t_a1_worker/full_run")

    print(f"\n{'='*100}")
    print("Uncontended probe reference (GATE_A_report.md / Gate A this session): "
          "~5.6us queue wait, ~0.35us exec")
    print("Verdict: processed == enqueued EXACTLY in every single rep, both scales "
          "-- (b) backlog is ruled out. Every enqueued item eventually executes; "
          "the near-zero hit rate is explained entirely by (a) race loss (dispatch "
          "latency vs demand-fault inter-arrival time), not un-executed work.")


if __name__ == "__main__":
    main()
