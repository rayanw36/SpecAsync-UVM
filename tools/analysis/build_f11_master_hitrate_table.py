#!/usr/bin/env python3
"""Assemble F11's (hitrate_vs_speedup) master table: every (configuration,
platform, hit_rate, wall_clock_delta, baseline) tuple in the project that has
BOTH a hit rate and a wall-clock comparison, with baseline as an explicit
column per OVERSUB_C3_VERIFICATION.md's methodology note ("no comparison in
this project may leave its baseline implicit").

Row groups and their committed sources:
  1. Deterministic hit-probe -- results/phaseB1/hit_probe_summary.csv (latency)
     + the probes' own *_batch.bin (hit rate, recomputed here). No wall-clock
     comparison exists for this synthetic microbenchmark (baseline="n/a").
  2. cuFFT (policy=2/stride, size=67108864) -- results/phaseB2/cufft_interleaved{,_5070ti}/
     cufft_interleaved_times.csv. baseline=p0 (same-session, same CSV).
  3. Oracle real workloads, non-oversubscribed (Stencil-24K, GraphBFS-23), T4 --
     results/gate3/telemetry/t4_prefetch_off_hitrate_recovered.csv (hit rate,
     corrected/clean reps) + t4_prefetch_off_times.csv (wall-clock).
     baseline=C1 explicitly (same-session prefetch-OFF baseline; C0 was not run
     in this session -- see notes column, not silently assumed).
  4. Oversubscribed oracle (C3, N=48000, iters=20) --
     results/analysis/gate_b9_oversub_mechanism/task2c_c0_threeway_times_MERGED.csv.
     TWO rows, baseline=C0 (real/practical) and baseline=C1 (crippled,
     same-mechanism-family) -- both included explicitly rather than picking one,
     per the methodology note this project adopted after the C1-baseline alarm.
"""
import csv
import statistics as st
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_CSV = REPO / "results/figures/f11_hitrate_vs_speedup_master.csv"

BFMT = "<6Q6I"
BSZ = struct.calcsize(BFMT)


def parse_probe_batch(path):
    raw = path.read_bytes()
    n = len(raw) // BSZ
    enq = hits = 0
    for i in range(n):
        v = struct.unpack(BFMT, raw[i * BSZ:(i + 1) * BSZ])
        t0, t4 = v[1], v[5]
        if t0 == 0 or t4 < t0:
            continue
        enq += v[7]
        hits += v[9]
    return hits, enq


rows = []


def add(config, platform, hit_rate_pct, wall_clock_delta_pct, baseline, n_hit, n_wall, notes, source):
    rows.append(dict(config=config, platform=platform, hit_rate_pct=hit_rate_pct,
                      wall_clock_delta_pct=wall_clock_delta_pct, baseline=baseline,
                      n_hit=n_hit, n_wall=n_wall, notes=notes, source=source))


def group1_probe():
    print("=== Group 1: deterministic hit-probe ===")
    probes = [
        ("T4", "prefoff_adj", REPO / "results/phaseB1/hit_probe/prefoff_adj_batch.bin",
         "original Gate A probe (GATE_A_report.md, results/phaseB1/)"),
        ("T4", "t4gate2", REPO / "results/phaseB1/hit_probe/t4gate2_batch.bin",
         "restart/rebuild session probe (GATE_A_report.md, results/analysis/)"),
        ("5070Ti", "task1_probe", REPO / "results/phaseB1/hit_probe_5070ti/task1_probe_batch.bin",
         "GATE_B6_TASK1_REBUILD.md"),
    ]
    for platform, tag, path, note in probes:
        hits, enq = parse_probe_batch(path)
        rate = 100.0 * hits / enq
        print(f"  {platform} {tag}: {hits}/{enq} = {rate:.4f}%")
        add(f"probe_{tag}", platform, f"{rate:.4f}", "", "n/a (deterministic positive-control "
            "microbenchmark -- no comparable wall-clock baseline exists)", enq, "", note,
            str(path.relative_to(REPO)))


def group2_cufft():
    print("\n=== Group 2: cuFFT (policy=2/stride, size=67108864) ===")
    for platform, path in [("T4", REPO / "results/phaseB2/cufft_interleaved/cufft_interleaved_times.csv"),
                            ("5070Ti", REPO / "results/phaseB2/cufft_interleaved_5070ti/cufft_interleaved_times.csv")]:
        rows_ = list(csv.DictReader(open(path)))
        p0 = [r for r in rows_ if r["config"] == "p0_prefetchON" and r["size"] == "67108864"
              and r["rep_in_cell"].startswith("kept")]
        p2 = [r for r in rows_ if r["config"] == "p2_prefetchON" and r["size"] == "67108864"
              and r["rep_in_cell"].startswith("kept")]
        med_wall_p0 = st.median(float(r["wall_s"]) for r in p0)
        med_wall_p2 = st.median(float(r["wall_s"]) for r in p2)
        med_hit_p2 = st.median(float(r["hit_rate"]) for r in p2) * 100.0
        delta = 100.0 * (med_wall_p2 - med_wall_p0) / med_wall_p0
        print(f"  {platform}: hit_rate={med_hit_p2:.4f}% wall_delta={delta:+.4f}% (n={len(p2)})")
        add("cuFFT_p2_stride", platform, f"{med_hit_p2:.4f}", f"{delta:.4f}", "p0 (same-session, same CSV)",
            len(p2), len(p2), "size=67108864, matches the legacy 25.47% cell being re-examined",
            str(path.relative_to(REPO)))


def group3_oracle_real():
    print("\n=== Group 3: oracle real workloads (non-oversub, T4) ===")
    hitrate_rows = list(csv.DictReader(open(REPO / "results/gate3/telemetry/t4_prefetch_off_hitrate_recovered.csv")))
    times_rows = list(csv.DictReader(open(REPO / "results/gate3/telemetry/t4_prefetch_off_times.csv")))

    def wall_median(bench, cfg):
        vals = [float(r["wall_s"]) for r in times_rows if r["bench"] == bench and r["config"] == cfg]
        return st.median(vals), len(vals)

    # Stencil-24K: only rep1 is clean (ring saturates mid-rep2)
    stencil_hit = next(r for r in hitrate_rows if r["bench"] == "bench_stencil" and r["rep"] == "1"
                        and r["methodology"] == "corrected_marginal_clean")
    stencil_c1_wall, n1 = wall_median("bench_stencil", "C1")
    stencil_c3_wall, n3 = wall_median("bench_stencil", "C3")
    delta = 100.0 * (stencil_c3_wall - stencil_c1_wall) / stencil_c1_wall
    print(f"  Stencil-24K: hit_rate={stencil_hit['hit_rate_pct']}% (rep1 only, clean) "
          f"wall_delta={delta:+.4f}% (C1 n={n1}, C3 n={n3}, full 15-rep medians)")
    add("oracle_C3", "T4_Stencil-24K", stencil_hit["hit_rate_pct"], f"{delta:.4f}", "C1 (same-session; "
        "C0 not run in this prefetch-OFF sweep session -- see notes)", 1, n3,
        "hit_rate from rep1 only (ring-clean); wall-clock delta from full 15-rep C1/C3 medians "
        "(timing is unaffected by ring saturation, unlike the ring-derived hit count) -- "
        "not the same literal reps, each statistic uses its own most representative sample",
        "results/gate3/telemetry/t4_prefetch_off_hitrate_recovered.csv + t4_prefetch_off_times.csv")

    # GraphBFS-23: reps1-4 clean, pooled
    gbfs_hit_rows = [r for r in hitrate_rows if r["bench"] == "bench_graph_bfs"
                      and r["methodology"] == "corrected_marginal_clean"]
    tot_hits = sum(int(r["hits"]) for r in gbfs_hit_rows)
    tot_enq = sum(int(r["enqueued"]) for r in gbfs_hit_rows)
    gbfs_rate = 100.0 * tot_hits / tot_enq
    gbfs_c1_wall, n1 = wall_median("bench_graph_bfs", "C1")
    gbfs_c3_wall, n3 = wall_median("bench_graph_bfs", "C3")
    delta = 100.0 * (gbfs_c3_wall - gbfs_c1_wall) / gbfs_c1_wall
    print(f"  GraphBFS-23: hit_rate={gbfs_rate:.4f}% (reps1-4 pooled, clean) "
          f"wall_delta={delta:+.4f}% (C1 n={n1}, C3 n={n3}, full 15-rep medians)")
    add("oracle_C3", "T4_GraphBFS-23", f"{gbfs_rate:.4f}", f"{delta:.4f}", "C1 (same-session; "
        "C0 not run in this prefetch-OFF sweep session -- see notes)", 4, n3,
        "hit_rate from reps1-4 pooled (ring-clean, marginal-diff reconstruction); wall-clock delta "
        "from full 15-rep C1/C3 medians, same caveat as Stencil-24K row above",
        "results/gate3/telemetry/t4_prefetch_off_hitrate_recovered.csv + t4_prefetch_off_times.csv")


def group4_oversub():
    print("\n=== Group 4: oversubscribed oracle (C3, N=48000, iters=20) ===")
    path = REPO / "results/analysis/gate_b9_oversub_mechanism/task2c_c0_threeway_times_MERGED.csv"
    rows_ = list(csv.DictReader(open(path)))
    c3 = [r for r in rows_ if r["config"] == "C3" and r["phase"] == "kept" and r["iters"] == "20"]
    c0 = [r for r in rows_ if r["config"] == "C0" and r["phase"] == "kept" and r["iters"] == "20"]
    c1 = [r for r in rows_ if r["config"] == "C1" and r["phase"] == "kept" and r["iters"] == "20"]
    enq = sum(int(r["atomic_enqueued"]) for r in c3)
    hits = sum(int(r["atomic_spec_hits"]) for r in c3)
    hit_rate = 100.0 * hits / enq
    med_c3 = st.median(float(r["wall_s"]) for r in c3)
    med_c0 = st.median(float(r["wall_s"]) for r in c0)
    med_c1 = st.median(float(r["wall_s"]) for r in c1)
    delta_c0 = 100.0 * (med_c3 - med_c0) / med_c0
    delta_c1 = 100.0 * (med_c3 - med_c1) / med_c1
    print(f"  hit_rate={hit_rate:.4f}% (n={len(c3)}) vs C0 delta={delta_c0:+.2f}% vs C1 delta={delta_c1:+.2f}%")
    add("oversub_C3_iters20", "5070Ti_N48000", f"{hit_rate:.4f}", f"{delta_c0:.4f}",
        "C0 (real/practical baseline)", len(c3), len(c0),
        "OVERSUB_C3_VERIFICATION.md's primary comparison", str(path.relative_to(REPO)))
    add("oversub_C3_iters20", "5070Ti_N48000", f"{hit_rate:.4f}", f"{delta_c1:.4f}",
        "C1 (crippled, same-mechanism-family baseline)", len(c3), len(c1),
        "included per this project's post-alarm policy: never leave baseline implicit, "
        "and C1-only comparisons were the source of the original false alarm -- both shown",
        str(path.relative_to(REPO)))


def main():
    group1_probe()
    group2_cufft()
    group3_oracle_real()
    group4_oversub()

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["config", "platform", "hit_rate_pct", "wall_clock_delta_pct",
                                           "baseline", "n_hit", "n_wall", "notes", "source"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {OUT_CSV.relative_to(REPO)} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
