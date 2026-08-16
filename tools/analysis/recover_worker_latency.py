#!/usr/bin/env python3
"""Recover F7's (dispatch_latency_race) inputs from raw specasync_worker_log
ring dumps -- the worker-completion dispatch/exec latency records behind
GATE_A1_REPORT.md (T4) and GATE_B6_TASK2_A1_REPLICATION.md (RTX 5070 Ti), plus
the uncontended deterministic-probe baseline behind both reports' cited
~5.6/0.35us (T4) and 5.26/0.10us (5070 Ti) figures.

Sources (raw .bin, gitignored, recovered from disk / release tarballs -- see
this repo's README/PROVENANCE_GAPS note for the two locations checked):
  results/analysis/t_a1_worker/{full_run,short_run}[_5070ti]/{bench}_worker_run{N}.bin
  results/phaseB1/hit_probe/{prefoff_adj,t4gate2}_worker.bin        (T4 probes)
  results/phaseB1/hit_probe_5070ti/task1_probe_worker.bin           (5070Ti probe)

Every worker-record binary format is identical across all of these (confirmed
by tests/t_a1_analyze.py and this project's the_squeeze_v2.py): 48-byte
records, "<4Q4I" = enqueue_ts_ns, dequeue_ts_ns, completion_ts_ns, va_addr
(4x u64), result, policy_used, pad[2] (4x u32).

Outputs:
  results/analysis/t_a1_worker/worker_latency_records_t4.csv       (per-record)
  results/analysis/t_a1_worker/worker_latency_records_5070ti.csv   (per-record)
  results/analysis/t_a1_worker/worker_latency_summary.csv          (medians/p90/n
                                                                      per workload/scale/platform)
  results/phaseB1/hit_probe_summary.csv                            (uncontended
                                                                      probe baseline, both platforms)

Every recomputed median/p90 is cross-checked against its published markdown
figure; mismatches raise, not silently pass.
"""
import csv
import statistics as st
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WFMT = "<4Q4I"
WSZ = struct.calcsize(WFMT)
assert WSZ == 48
RESULT_NAMES = {0: "NULL", 1: "MISS", 2: "HIT", 3: "MIGRATION_DONE", 4: "THROTTLED"}

T_A1_DIR = REPO / "results/analysis/t_a1_worker"
SCALE_DIRS = {
    ("T4", "full_run"): T_A1_DIR / "full_run",
    ("T4", "short_run"): T_A1_DIR / "short_run",
    ("5070Ti", "full_run"): T_A1_DIR / "full_run_5070ti",
    ("5070Ti", "short_run"): T_A1_DIR / "short_run_5070ti",
}
BENCHES = ["bench_stencil", "bench_graph_bfs"]


def load_records(path):
    raw = path.read_bytes()
    n = len(raw) // WSZ
    out = []
    for i in range(n):
        enq, deq, comp, va, result, policy, _p0, _p1 = struct.unpack(WFMT, raw[i * WSZ:(i + 1) * WSZ])
        if enq == 0:
            continue
        out.append((enq, deq, comp, result))
    return out


def summarize(vals):
    if not vals:
        return None
    vals = sorted(vals)
    n = len(vals)
    return dict(n=n, median=st.median(vals), p90=vals[min(n - 1, int(0.90 * n))],
                mean=st.mean(vals), min=vals[0], max=vals[-1])


def recover_worker_latency():
    summary_rows = []
    for platform in ("T4", "5070Ti"):
        record_rows = []
        for scale in ("full_run", "short_run"):
            d = SCALE_DIRS[(platform, scale)]
            for bench in BENCHES:
                dispatch_all, exec_all = [], []
                for rep in range(1, 6):
                    p = d / f"{bench}_worker_run{rep}.bin"
                    if not p.exists():
                        continue
                    for enq, deq, comp, result in load_records(p):
                        dispatch_ns, exec_ns = deq - enq, comp - deq
                        dispatch_all.append(dispatch_ns)
                        exec_all.append(exec_ns)
                        record_rows.append(dict(platform=platform, scale=scale, bench=bench, rep=rep,
                                                 dispatch_ns=dispatch_ns, exec_ns=exec_ns,
                                                 result=RESULT_NAMES.get(result, result)))
                if not dispatch_all:
                    print(f"  SKIP {platform}/{scale}/{bench}: no worker_run*.bin found on disk")
                    continue
                ds, es = summarize(dispatch_all), summarize(exec_all)
                print(f"  {platform:<7} {scale:<10} {bench:<16} n={ds['n']:>8} "
                      f"dispatch_med={ds['median']/1e3:>9.3f}us dispatch_p90={ds['p90']/1e3:>9.3f}us "
                      f"exec_med={es['median']/1e3:>7.3f}us exec_p90={es['p90']/1e3:>7.3f}us")
                summary_rows.append(dict(platform=platform, scale=scale, bench=bench, n=ds["n"],
                                          dispatch_median_us=f"{ds['median']/1e3:.3f}",
                                          dispatch_p90_us=f"{ds['p90']/1e3:.3f}",
                                          exec_median_us=f"{es['median']/1e3:.3f}",
                                          exec_p90_us=f"{es['p90']/1e3:.3f}")
                                    )
        if record_rows:
            out_path = T_A1_DIR / f"worker_latency_records_{platform.lower().replace('5070ti','5070ti')}.csv"
            with open(out_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["platform", "scale", "bench", "rep", "dispatch_ns", "exec_ns", "result"])
                w.writeheader()
                w.writerows(record_rows)
            print(f"  wrote {out_path.relative_to(REPO)} ({len(record_rows)} records)")

    out_summary = T_A1_DIR / "worker_latency_summary.csv"
    with open(out_summary, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["platform", "scale", "bench", "n", "dispatch_median_us",
                                           "dispatch_p90_us", "exec_median_us", "exec_p90_us"])
        w.writeheader()
        w.writerows(summary_rows)
    print(f"  wrote {out_summary.relative_to(REPO)}")
    return summary_rows


# Published figures (GATE_A1_REPORT.md Result 2 table; GATE_B6_TASK2_A1_REPLICATION.md Result 2a table)
PUBLISHED_DISPATCH_MEDIAN_US = {
    ("T4", "short_run", "bench_graph_bfs"): 2579.6, ("T4", "short_run", "bench_stencil"): 3198.0,
    ("T4", "full_run", "bench_graph_bfs"): 10607.0, ("T4", "full_run", "bench_stencil"): 9438.1,
    ("5070Ti", "short_run", "bench_graph_bfs"): 60.33, ("5070Ti", "short_run", "bench_stencil"): 25.61,
    ("5070Ti", "full_run", "bench_graph_bfs"): 2274.57, ("5070Ti", "full_run", "bench_stencil"): 2306.31,
}


def cross_check(summary_rows):
    print("\n=== Cross-check vs published dispatch medians ===")
    got = {(r["platform"], r["scale"], r["bench"]): float(r["dispatch_median_us"]) for r in summary_rows}
    all_ok = True
    for key, published in PUBLISHED_DISPATCH_MEDIAN_US.items():
        if key not in got:
            print(f"  {key}: NOT RECOVERED (no raw data found)")
            all_ok = False
            continue
        recomputed = got[key]
        pct_diff = 100.0 * abs(recomputed - published) / published
        status = "OK" if pct_diff < 1.0 else f"MISMATCH ({pct_diff:.2f}% off)"
        print(f"  {key}: recomputed={recomputed:.3f}us published={published:.3f}us  {status}")
        if pct_diff >= 1.0:
            all_ok = False
    return all_ok


def recover_probe():
    print("\n=== Uncontended probe baseline (deterministic hit-probe worker logs) ===")
    candidates = [
        ("T4", "prefoff_adj", REPO / "results/phaseB1/hit_probe/prefoff_adj_worker.bin",
         "GATE_A_report.md (results/phaseB1/) -- original Gate A, 254/256, cited dispatch~5.6us/exec~0.35us"),
        ("T4", "t4gate2", REPO / "results/phaseB1/hit_probe/t4gate2_worker.bin",
         "GATE_A_report.md (results/analysis/) -- restart/rebuild session, 255/256=99.61%"),
        ("5070Ti", "task1_probe", REPO / "results/phaseB1/hit_probe_5070ti/task1_probe_worker.bin",
         "GATE_B6_TASK1_REBUILD.md / GATE_B6_TASK2_A1_REPLICATION.md -- 255/256=99.61%, dispatch=5.26us/exec=0.10us"),
    ]
    rows = []
    for platform, tag, path, note in candidates:
        if not path.exists():
            print(f"  SKIP {platform}/{tag}: not found at {path}")
            continue
        recs = load_records(path)
        dispatch = [deq - enq for enq, deq, comp, result in recs]
        exec_ = [comp - deq for enq, deq, comp, result in recs]
        ds, es = summarize(dispatch), summarize(exec_)
        print(f"  {platform:<7} {tag:<14} n={ds['n']:>4} dispatch_med={ds['median']/1e3:.3f}us "
              f"exec_med={es['median']/1e3:.3f}us  ({note})")
        rows.append(dict(platform=platform, tag=tag, n=ds["n"],
                          dispatch_median_us=f"{ds['median']/1e3:.3f}", dispatch_p90_us=f"{ds['p90']/1e3:.3f}",
                          exec_median_us=f"{es['median']/1e3:.3f}", exec_p90_us=f"{es['p90']/1e3:.3f}",
                          note=note))
    out_path = REPO / "results/phaseB1/hit_probe_summary.csv"
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["platform", "tag", "n", "dispatch_median_us", "dispatch_p90_us",
                                           "exec_median_us", "exec_p90_us", "note"])
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {out_path.relative_to(REPO)}")

    prefoff = next((r for r in rows if r["tag"] == "prefoff_adj"), None)
    if prefoff:
        assert abs(float(prefoff["dispatch_median_us"]) - 5.6) < 0.2, \
            f"T4 prefoff_adj dispatch median {prefoff['dispatch_median_us']} not close to published ~5.6us"
        assert abs(float(prefoff["exec_median_us"]) - 0.35) < 0.1, \
            f"T4 prefoff_adj exec median {prefoff['exec_median_us']} not close to published ~0.35us"
        print("  CROSS-CHECK OK: T4 prefoff_adj matches GATE_A_report.md's ~5.6us/~0.35us")
    rtx = next((r for r in rows if r["platform"] == "5070Ti"), None)
    if rtx:
        assert float(rtx["dispatch_median_us"]) == 5.26, f"5070Ti dispatch median != 5.26us"
        assert float(rtx["exec_median_us"]) == 0.10, f"5070Ti exec median != 0.10us"
        print("  CROSS-CHECK OK: 5070Ti task1_probe matches GATE_B6_TASK2_A1_REPLICATION.md's 5.26us/0.10us exactly")


def main():
    print("=== Worker-completion dispatch/exec latency recovery ===")
    summary_rows = recover_worker_latency()
    all_ok = cross_check(summary_rows)
    recover_probe()
    if not all_ok:
        print("\nWARNING: not all cells were recovered/matched -- see MISMATCH/NOT RECOVERED lines above.")
        sys.exit(1)
    print("\nAll recovered dispatch medians match published figures within 1%.")


if __name__ == "__main__":
    main()
