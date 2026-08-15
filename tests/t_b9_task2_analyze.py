#!/usr/bin/env python3
"""
t_b9_task2_analyze.py -- Gate B9 Task 2 mechanism analysis.

Reads results/analysis/gate_b9_oversub_mechanism/task2_mechanism_times.csv
(run metadata) plus the per-run binary telemetry dumps in
telemetry_task2_mechanism/ (written by tests/t_b9_task2_mechanism.sh), and
produces:

  - task2_run_summary.csv        one row per KEPT run, with every parsed
                                  metric (demand faults, spec enqueue/hit/
                                  drop, migration_done count, thrash
                                  median/p90/max, D1-D7 sums, ring-drop/wrap
                                  warnings)
  - task2_aggregate_comparison.csv   C1-vs-C3 median, MWU p, Cohen's d, Holm
                                      threshold/verdict across the declared
                                      metric family

Reuses benchmarks/tools/specasync_parse.py's batch/work record parsers so
the byte layout is defined in exactly one place in this repo.

Decomp D7 is computed from the recorded fields per the accounting-closure
formula in driver/src/specasync_telemetry.h:
    D7 = (svc_start - d2_end) + (d6_start - svc_end) + other residual
Since "other residual" isn't separately recorded, this script reports the
two measurable components of D7 (post-metadata gap, post-service gap) and
their sum, and flags this explicitly as an approximation, not exact D7.

Thrash proxy: specasync_fault_trace is a TRUE circular-overwrite ring
(1,048,576 u64 slots, no drop-on-full -- confirmed by reading
specasync_trace_push() in driver/src/uvm_gpu_replayable_faults.c). If a
run's total demand-fault count (from batch records) exceeds 1,048,576, the
trace only contains the trailing ~1,048,576 fault events, not the whole
run -- this script computes total_demand_faults from batch records
independently and flags wrapped=True whenever it exceeds the ring capacity,
so the repeat-count distribution is never silently presented as full-run.

batch_ring/work_ring/decomp_ring are DROP-ON-FULL (131,072 slots each,
confirmed by reading specasync_batch_ring_push() et al.) -- if the parsed
record count for a run lands at or near 131,072, this script flags a
possible-drop warning (the opposite bias from the trace ring: late-run data
would be missing, not early-run data).
"""
import csv
import struct
import statistics as st
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "benchmarks" / "tools"))
from specasync_parse import (  # noqa: E402
    parse_batch_log, parse_work_log, BATCH_SIZE, WORK_SIZE, RESULT_NAMES,
)

from scipy import stats as scipy_stats  # noqa: E402

OUT_DIR = REPO / "results/analysis/gate_b9_oversub_mechanism"
CSV_IN = OUT_DIR / "task2_mechanism_times.csv"
TELEM_DIR = OUT_DIR / "telemetry_task2_mechanism"
RUN_SUMMARY_CSV = OUT_DIR / "task2_run_summary.csv"
AGG_CSV = OUT_DIR / "task2_aggregate_comparison.csv"

PAGE_SHIFT = 12
BATCH_RING_SLOTS = 131072
WORK_RING_SLOTS = 131072
TRACE_RING_SLOTS = 1048576

DECOMP_FMT = "<12Q4I"
DECOMP_SIZE = struct.calcsize(DECOMP_FMT)
assert DECOMP_SIZE == 112, f"DECOMP_FMT calcsize={DECOMP_SIZE}, expected 112"
DECOMP_FIELDS = (
    "batch_id", "d1_start", "d1_end", "d2_start", "d2_end",
    "svc_start", "svc_end", "d6_start", "d6_end",
    "d3_wait_ns", "d4_hold_ns", "d5_serv_ns",
    "num_faults", "num_va_spaces", "num_blocks", "_pad",
)


def parse_decomp_log(path):
    raw = Path(path).read_bytes()
    n = len(raw) // DECOMP_SIZE
    recs = []
    for i in range(n):
        chunk = raw[i * DECOMP_SIZE:(i + 1) * DECOMP_SIZE]
        vals = struct.unpack(DECOMP_FMT, chunk)
        d = dict(zip(DECOMP_FIELDS, vals))
        if d["batch_id"] == 0 and d["d1_start"] == 0:
            continue  # stale/zero slot
        recs.append(d)
    return recs


def parse_trace_bin(path):
    raw = Path(path).read_bytes()
    n = len(raw) // 8
    if n == 0:
        return []
    return list(struct.unpack(f"<{n}Q", raw))


def thrash_stats(addrs):
    """Per-page repeat-fault-count distribution from a raw VA trace."""
    if not addrs:
        return dict(n_entries=0, n_unique_pages=0, repeat_median=float("nan"),
                     repeat_p90=float("nan"), repeat_max=0)
    pages = [a >> PAGE_SHIFT for a in addrs]
    counts = {}
    for p in pages:
        counts[p] = counts.get(p, 0) + 1
    vals = sorted(counts.values())
    p90_idx = min(len(vals) - 1, int(round(0.90 * (len(vals) - 1))))
    return dict(
        n_entries=len(addrs),
        n_unique_pages=len(counts),
        repeat_median=st.median(vals),
        repeat_p90=vals[p90_idx],
        repeat_max=max(vals),
    )


def decomp_stats(recs):
    if not recs:
        return dict(n_decomp_batches=0)
    d1 = [r["d1_end"] - r["d1_start"] for r in recs]
    d2 = [r["d2_end"] - r["d2_start"] for r in recs]
    d6 = [(r["d6_end"] - r["d6_start"]) if r["d6_end"] > 0 else 0 for r in recs]
    svc = [r["svc_end"] - r["svc_start"] for r in recs]
    d3 = [r["d3_wait_ns"] for r in recs]
    d4 = [r["d4_hold_ns"] for r in recs]
    d5 = [r["d5_serv_ns"] for r in recs]
    # D7 components per the accounting-closure formula (header comment):
    #   D7 = (svc_start - d2_end) + (d6_start - svc_end) + other residual
    # "other residual" is not separately recorded -- report the two
    # measurable gaps and their sum, flagged as an approximation.
    gap_post_metadata = [r["svc_start"] - r["d2_end"] for r in recs]
    gap_post_service = [(r["d6_start"] - r["svc_end"]) if r["d6_end"] > 0 else 0
                         for r in recs]
    d7_approx = [a + b for a, b in zip(gap_post_metadata, gap_post_service)]
    return dict(
        n_decomp_batches=len(recs),
        d1_sum_ns=sum(d1), d1_median_ns=st.median(d1),
        d2_sum_ns=sum(d2), d2_median_ns=st.median(d2),
        d3_wait_sum_ns=sum(d3),
        d4_hold_sum_ns=sum(d4),
        d5_serv_sum_ns=sum(d5),
        d6_sum_ns=sum(d6),
        svc_sum_ns=sum(svc),
        d7_approx_sum_ns=sum(d7_approx),
        num_va_spaces_total=sum(r["num_va_spaces"] for r in recs),
        num_blocks_total=sum(r["num_blocks"] for r in recs),
    )


def main():
    rows = list(csv.DictReader(open(CSV_IN)))
    kept = [r for r in rows if r["phase"] == "kept" and r["exit_code"] == "0"]
    if not kept:
        print("No kept, successful rows found in", CSV_IN, file=sys.stderr)
        sys.exit(1)

    summary_rows = []
    for r in kept:
        prefix = r["telemetry_prefix"]
        batch_bin = TELEM_DIR / f"{prefix}_batch.bin"
        work_bin = TELEM_DIR / f"{prefix}_work.bin"
        decomp_bin = TELEM_DIR / f"{prefix}_decomp.bin"
        trace_bin = TELEM_DIR / f"{prefix}_trace.bin"

        batches = parse_batch_log(batch_bin) if batch_bin.exists() else []
        works = parse_work_log(work_bin) if work_bin.exists() else []
        decomps = parse_decomp_log(decomp_bin) if decomp_bin.exists() else []
        trace = parse_trace_bin(trace_bin) if trace_bin.exists() else []

        total_faults = sum(b["num_faults"] for b in batches)
        total_enq = sum(b["spec_enqueues"] for b in batches)
        total_drop = sum(b["spec_drops"] for b in batches)
        total_hits = sum(b["spec_hits"] for b in batches)
        hit_rate = (total_hits / total_enq) if total_enq else 0.0

        work_result_counts = {name: 0 for name in RESULT_NAMES.values()}
        for w in works:
            work_result_counts[RESULT_NAMES.get(w["result"], "unknown")] = \
                work_result_counts.get(RESULT_NAMES.get(w["result"], "unknown"), 0) + 1

        batch_ring_near_full = len(batches) >= int(0.95 * BATCH_RING_SLOTS)
        work_ring_near_full = len(works) >= int(0.95 * WORK_RING_SLOTS)

        tstats = thrash_stats(trace)
        trace_wrapped = total_faults > TRACE_RING_SLOTS

        dstats = decomp_stats(decomps)

        row = dict(
            run_order_idx=r["run_order_idx"],
            config=r["config"],
            rep=r["rep_in_cell"],
            wall_s=float(r["wall_s"]) if r["wall_s"] else float("nan"),
            total_demand_faults=total_faults,
            total_spec_enqueues=total_enq,
            total_spec_drops=total_drop,
            total_spec_hits=total_hits,
            hit_rate=hit_rate,
            atomic_processed=r["atomic_processed"],
            atomic_enqueued=r["atomic_enqueued"],
            atomic_drops=r["atomic_drops"],
            n_batch_records=len(batches),
            n_work_records=len(works),
            batch_ring_near_full=batch_ring_near_full,
            work_ring_near_full=work_ring_near_full,
            work_migration_done=work_result_counts.get("migration_done", 0),
            work_hit=work_result_counts.get("hit", 0),
            work_miss=work_result_counts.get("miss", 0),
            work_throttled=work_result_counts.get("throttled", 0),
            work_null=work_result_counts.get("null", 0),
            trace_n_entries=tstats["n_entries"],
            trace_n_unique_pages=tstats["n_unique_pages"],
            trace_repeat_median=tstats["repeat_median"],
            trace_repeat_p90=tstats["repeat_p90"],
            trace_repeat_max=tstats["repeat_max"],
            trace_wrapped=trace_wrapped,
        )
        row.update({f"decomp_{k}": v for k, v in dstats.items()})
        summary_rows.append(row)

    fieldnames = list(summary_rows[0].keys())
    with open(RUN_SUMMARY_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(summary_rows)
    print(f"wrote {RUN_SUMMARY_CSV} ({len(summary_rows)} rows)")

    c1 = [x for x in summary_rows if x["config"] == "C1"]
    c3 = [x for x in summary_rows if x["config"] == "C3"]
    print(f"\nC1 kept runs: {len(c1)}   C3 kept runs: {len(c3)}")

    def cohens_d(a, b):
        na, nb = len(a), len(b)
        sa, sb = st.stdev(a), st.stdev(b)
        pooled_sd = (((na - 1) * sa**2 + (nb - 1) * sb**2) / (na + nb - 2)) ** 0.5
        return (st.mean(a) - st.mean(b)) / pooled_sd if pooled_sd else float("nan")

    def holm_bonferroni(pvals, alpha=0.05):
        m = len(pvals)
        order = sorted(range(m), key=lambda i: pvals[i])
        reject = [False] * m
        thresholds = [None] * m
        still = True
        for rank, i in enumerate(order):
            thr = alpha / (m - rank)
            thresholds[i] = thr
            if still and pvals[i] <= thr:
                reject[i] = True
            else:
                still = False
        return thresholds, reject

    metrics = [
        ("wall_s", "wall-clock (s)"),
        ("total_demand_faults", "total demand faults"),
        ("hit_rate", "hit rate"),
        ("trace_repeat_median", "thrash: per-page repeat median"),
        ("trace_repeat_p90", "thrash: per-page repeat p90"),
    ]

    comparisons = []
    for key, label in metrics:
        a = [x[key] for x in c1]
        b = [x[key] for x in c3]
        u_stat, u_p = scipy_stats.mannwhitneyu(a, b, alternative="two-sided")
        d = cohens_d(a, b)
        comparisons.append(dict(
            metric=key, label=label,
            c1_median=st.median(a), c3_median=st.median(b),
            pct_delta=(st.median(b) - st.median(a)) / st.median(a) * 100 if st.median(a) else float("nan"),
            mwu_p=u_p, cohens_d=d,
        ))

    pvals = [c["mwu_p"] for c in comparisons]
    thr, reject = holm_bonferroni(pvals)

    print("\n=== C1 vs C3 mechanism metrics (Holm family, m={}) ===".format(len(comparisons)))
    with open(AGG_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["metric", "label", "c1_median", "c3_median", "pct_delta",
                    "mwu_p", "holm_threshold", "holm_significant", "cohens_d"])
        for i, c in enumerate(comparisons):
            sig = "YES" if reject[i] else "no"
            w.writerow([c["metric"], c["label"], c["c1_median"], c["c3_median"],
                        c["pct_delta"], c["mwu_p"], thr[i], sig, c["cohens_d"]])
            print(f"  {c['label']:32s} C1={c['c1_median']:.6g}  C3={c['c3_median']:.6g}  "
                  f"delta={c['pct_delta']:+.2f}%  MWU p={c['mwu_p']:.4g}  "
                  f"Holm sig={sig}  d={c['cohens_d']:.3f}")
    print(f"\nwrote {AGG_CSV}")

    n_wrapped_c1 = sum(1 for x in c1 if x["trace_wrapped"])
    n_wrapped_c3 = sum(1 for x in c3 if x["trace_wrapped"])
    print(f"\nTrace-ring wrap: C1 {n_wrapped_c1}/{len(c1)} runs wrapped, "
          f"C3 {n_wrapped_c3}/{len(c3)} runs wrapped "
          f"(ring capacity {TRACE_RING_SLOTS} entries; wrapped => "
          f"trailing-window-only, not full-run).")
    n_batch_full_c1 = sum(1 for x in c1 if x["batch_ring_near_full"])
    n_batch_full_c3 = sum(1 for x in c3 if x["batch_ring_near_full"])
    if n_batch_full_c1 or n_batch_full_c3:
        print(f"WARNING: batch ring near-full (possible record drops, late-run "
              f"data missing): C1 {n_batch_full_c1}/{len(c1)}, C3 {n_batch_full_c3}/{len(c3)}")


if __name__ == "__main__":
    main()
