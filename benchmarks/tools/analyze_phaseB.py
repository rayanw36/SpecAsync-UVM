#!/usr/bin/env python3
"""
analyze_phaseB.py — Phase B results aggregation and plotting.

Reads timing_raw.csv and batch_records.csv from results/p*_d*/ and produces:
  results/phaseB/SUMMARY.md          — key findings, reviewer-comment order
  results/phaseB/plots/              — all figures
  results/phaseB/phaseB_timing.csv   — aggregated timing table
  results/phaseB/phaseB_telemetry.csv — aggregated telemetry table

Usage:
  python3 analyze_phaseB.py [--results-dir DIR] [--out-dir DIR]
"""

import os, glob, csv, statistics, sys, math
from pathlib import Path
from collections import defaultdict

_HERE       = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.normpath(os.path.join(_HERE, '..', '..', 'results'))
OUT_DIR     = os.path.normpath(os.path.join(_HERE, '..', '..', 'results', 'phaseB'))

POLICY_NAMES = {0: 'Disabled', 1: 'Adjacent', 2: 'Stride', 3: 'Markov', 4: 'Oracle'}

# ── Loaders ───────────────────────────────────────────────────────────────────

def load_timing(csv_path):
    """Return list of time_ms floats from timing_raw.csv (handles Run_ID,Time_ms or run,time_ms)."""
    rows = []
    with open(csv_path, newline='') as fh:
        for r in csv.DictReader(fh):
            # Normalise header case
            row_lc = {k.lower(): v for k, v in r.items()}
            try:
                rows.append(float(row_lc['time_ms']))
            except (ValueError, KeyError):
                pass
    return rows

MAX_BATCH_LATENCY_NS = 30e9   # 30 s — cross-session records show billions of µs

def load_batch(csv_path):
    """Load batch_records.csv, filtering stale records (t0_ns==0 or implausible latency)."""
    recs = []
    with open(csv_path, newline='') as fh:
        for row in csv.DictReader(fh):
            try:
                t0 = float(row['t0_ns'])
                tl = float(row['total_latency_ns'])
                if t0 == 0 or tl <= 0 or tl > MAX_BATCH_LATENCY_NS:
                    continue
                recs.append({k: float(v) for k, v in row.items()
                             if k not in ('_pad',)})
            except (ValueError, KeyError):
                pass
    return recs

def find_configs(results_dir):
    """Return sorted list of (policy, depth, config_dir)."""
    out = []
    for d in sorted(glob.glob(os.path.join(results_dir, 'p*_d*'))):
        name = os.path.basename(d)
        try:
            p, dd = name.split('_')
            out.append((int(p[1:]), int(dd[1:]), d))
        except (ValueError, IndexError):
            pass
    return out

# ── Aggregation ───────────────────────────────────────────────────────────────

def aggregate_timing(results_dir):
    """
    Returns dict: (policy, depth, bench, size) -> {mean, std, n, ...}
    """
    data = {}
    for policy, depth, cdir in find_configs(results_dir):
        for f in sorted(glob.glob(os.path.join(cdir, '*', '*', 'timing_raw.csv'))):
            parts = Path(f).parts
            bench, size = parts[-3], parts[-2]
            times = load_timing(f)
            if len(times) < 2:
                continue
            data[(policy, depth, bench, size)] = {
                'mean': statistics.mean(times),
                'std':  statistics.stdev(times),
                'n':    len(times),
                'median': statistics.median(times),
            }
    return data

def aggregate_telemetry(results_dir):
    """
    Returns dict: (policy, depth, bench, size) -> telemetry stats dict
    """
    data = {}
    for policy, depth, cdir in find_configs(results_dir):
        for f in sorted(glob.glob(os.path.join(cdir, '*', '*', 'batch_records.csv'))):
            parts = Path(f).parts
            bench, size = parts[-3], parts[-2]
            recs = load_batch(f)
            if not recs:
                continue
            enqueues = sum(r['spec_enqueues'] for r in recs)
            hits     = sum(r['spec_hits']     for r in recs)
            latencies = [r['total_latency_ns'] for r in recs]
            ph01      = [r['phase01_ns']       for r in recs]
            ph12      = [r['phase12_ns']       for r in recs]
            data[(policy, depth, bench, size)] = {
                'n_batches':     len(recs),
                'hit_rate':      hits / enqueues if enqueues else 0.0,
                'enqueues':      enqueues,
                'hits':          hits,
                'lat_median_ns': statistics.median(latencies),
                'lat_mean_ns':   statistics.mean(latencies),
                'lat_p95_ns':    sorted(latencies)[int(len(latencies)*0.95)],
                'ph01_median_ns': statistics.median(ph01),
                'ph12_median_ns': statistics.median(ph12),
            }
    return data

# ── Formatting ────────────────────────────────────────────────────────────────

def pct_delta(a, b):
    """% change from a to b."""
    if a == 0:
        return 0.0
    return (b - a) / a * 100.0

def fmt_pct(v):
    sign = '+' if v >= 0 else ''
    return f"{sign}{v:.1f}%"

# ── Timing comparison table ───────────────────────────────────────────────────

def build_timing_table(timing, baseline_policy=0, baseline_depth=0):
    """
    Produce per-benchmark rows comparing p0 (baseline) vs p1,p2,p3.
    Returns list of dicts for CSV output, and markdown string.
    """
    rows = []
    base = {(b, s): v for (p, d, b, s), v in timing.items()
            if p == baseline_policy and d == baseline_depth}

    for (policy, depth, bench, size), v in sorted(timing.items()):
        if policy == baseline_policy and depth == baseline_depth:
            continue
        bk = (bench, size)
        if bk not in base:
            continue
        delta_pct = pct_delta(base[bk]['mean'], v['mean'])
        rows.append({
            'Benchmark': bench, 'Size': size,
            'Config': f"p{policy}_d{depth}",
            'Policy': POLICY_NAMES.get(policy, str(policy)),
            'Baseline_mean_ms': f"{base[bk]['mean']:.2f}",
            'Baseline_std_ms':  f"{base[bk]['std']:.2f}",
            'Config_mean_ms':   f"{v['mean']:.2f}",
            'Config_std_ms':    f"{v['std']:.2f}",
            'Delta_pct':        f"{delta_pct:.1f}",
            'N': v['n'],
        })
    return rows

# ── Plots ─────────────────────────────────────────────────────────────────────

def try_plots(timing, telemetry, out_dir):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("[analyze_phaseB] matplotlib unavailable — skipping plots", file=sys.stderr)
        return

    plots_dir = os.path.join(out_dir, 'plots')
    os.makedirs(plots_dir, exist_ok=True)

    # 1. End-to-end comparison: baseline vs each policy, per benchmark
    bench_names = sorted({b for (_, _, b, _) in timing})
    for bench in bench_names:
        sizes = sorted({s for (_, _, b, s) in timing if b == bench})
        policies = sorted({p for (p, d, b, s) in timing
                           if b == bench and d == 0})
        if 0 not in policies:
            continue

        fig, axes = plt.subplots(1, len(sizes), figsize=(4*len(sizes), 4), sharey=False)
        if len(sizes) == 1:
            axes = [axes]

        for ax, size in zip(axes, sizes):
            means  = []
            errs   = []
            labels = []
            for p in policies:
                key = (p, 0, bench, size)
                if key not in timing:
                    continue
                means.append(timing[key]['mean'])
                errs.append(timing[key]['std'])
                labels.append(POLICY_NAMES.get(p, str(p)))

            x = np.arange(len(means))
            bars = ax.bar(x, means, yerr=errs, capsize=4,
                          color=['#4878d0','#ee854a','#6acc65','#d65f5f','#956cb4'],
                          edgecolor='black', linewidth=0.5)
            base_mean = means[0] if means else 1.0
            for i, (bar, mean) in enumerate(zip(bars, means)):
                if i > 0 and base_mean > 0:
                    pct = (mean - base_mean) / base_mean * 100
                    sign = '+' if pct >= 0 else ''
                    ax.text(bar.get_x() + bar.get_width()/2, mean + errs[i]*1.1,
                            f'{sign}{pct:.1f}%', ha='center', va='bottom', fontsize=7)
            ax.set_title(f'{bench}\nsize={size}', fontsize=9)
            ax.set_xticks(x)
            ax.set_xticklabels(labels, fontsize=8, rotation=30)
            ax.set_ylabel('Time (ms)' if ax is axes[0] else '')
            ax.grid(axis='y', linestyle='--', alpha=0.4)

        fig.suptitle(f'SpecAsync-UVM: {bench} — Stock vs Speculation Policies', fontsize=11)
        plt.tight_layout()
        out_p = os.path.join(plots_dir, f'timing_{bench}.png')
        plt.savefig(out_p, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"[plot] {out_p}")

    # 2. Fault-latency CDF for fault-heavy workloads (policy 0 vs 1)
    cdf_benches = ['Stencil', 'GraphBFS', 'Stencil_OvSub']
    for bench in cdf_benches:
        sizes = sorted({s for (_, _, b, s) in telemetry if b == bench})
        if not sizes:
            continue
        size = sizes[-1]  # largest size
        fig, ax = plt.subplots(figsize=(6, 4))
        for policy in [0, 1]:
            key = (policy, 0, bench, size)
            if key not in telemetry:
                continue
            # We don't have per-record latencies here — approximate from median
            # A future improvement would pass raw latencies through
            label = f"p{policy} ({POLICY_NAMES.get(policy)})"
            ax.axvline(telemetry[key]['lat_median_ns'] / 1000,
                       label=f'{label} median', linestyle='--')
        ax.set_xlabel('Service latency (µs)')
        ax.set_ylabel('Approx. fraction')
        ax.set_title(f'Fault Service Latency — {bench} size={size}')
        ax.legend()
        ax.grid(linestyle='--', alpha=0.4)
        plt.tight_layout()
        out_p = os.path.join(plots_dir, f'latency_cdf_{bench}.png')
        plt.savefig(out_p, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"[plot] {out_p}")

    # 3. Policy sweep: hit rate and timing delta
    fault_heavy = ['Stencil', 'GraphBFS', 'Stencil_OvSub']
    for bench in fault_heavy:
        sizes = sorted({s for (_, _, b, s) in timing if b == bench})
        if not sizes:
            continue
        size = sizes[-1]
        policies = sorted({p for (p, d, b, s) in timing
                           if b == bench and d == 0 and p != 0})
        if not policies:
            continue
        base_key = (0, 0, bench, size)
        if base_key not in timing:
            continue
        base_mean = timing[base_key]['mean']

        pct_deltas = []
        hit_rates  = []
        labels     = []
        for p in policies:
            key = (p, 0, bench, size)
            if key not in timing:
                continue
            pct_deltas.append(pct_delta(base_mean, timing[key]['mean']))
            tel_key = (p, 0, bench, size)
            hit_rates.append(telemetry[tel_key]['hit_rate'] * 100
                             if tel_key in telemetry else 0)
            labels.append(POLICY_NAMES.get(p, str(p)))

        if not labels:
            continue
        x = np.arange(len(labels))
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3))
        ax1.bar(x, pct_deltas, color='#4878d0', edgecolor='black', linewidth=0.5)
        ax1.axhline(0, color='black', linewidth=0.7)
        ax1.set_xticks(x); ax1.set_xticklabels(labels)
        ax1.set_ylabel('Runtime Δ (%)\n(negative = faster)')
        ax1.set_title(f'{bench} {size} — Timing Delta')
        ax1.grid(axis='y', linestyle='--', alpha=0.4)

        ax2.bar(x, hit_rates, color='#6acc65', edgecolor='black', linewidth=0.5)
        ax2.set_xticks(x); ax2.set_xticklabels(labels)
        ax2.set_ylabel('Hit Rate (%)')
        ax2.set_title(f'{bench} {size} — Speculation Hit Rate')
        ax2.set_ylim(0, 105)
        ax2.grid(axis='y', linestyle='--', alpha=0.4)
        plt.tight_layout()
        out_p = os.path.join(plots_dir, f'policy_sweep_{bench}.png')
        plt.savefig(out_p, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"[plot] {out_p}")

    print(f"[analyze_phaseB] Plots written to {plots_dir}")


# ── Summary markdown ──────────────────────────────────────────────────────────

def build_summary(timing, telemetry):
    lines = ["# SpecAsync-UVM Phase B — Results Summary\n"]

    # --- C4: Expanded evaluation
    lines.append("## Reviewer Comment C4: Expanded Evaluation (T4, 5 benchmarks)\n")
    lines.append("**Platform:** AWS g4dn.xlarge · Tesla T4 (sm_75) · 15 GiB VRAM · "
                 "14 GiB host RAM · Driver 595.71.05\n")
    lines.append("**Methodology:** 20 runs per config (N reduced from 50 for "
                 "slow benchmarks), 1 warm-up, mean ± std.\n")

    # Timing table
    base = {(b, s): v for (p, d, b, s), v in timing.items() if p == 0 and d == 0}
    for (policy, depth, bench, size), v in sorted(timing.items()):
        if policy == 0:
            continue
        bk = (bench, size)
        if bk not in base:
            continue
        delta_pct = pct_delta(base[bk]['mean'], v['mean'])
        lines.append(f"- **{bench}** size={size}  p{policy} vs p0: "
                     f"{base[bk]['mean']:.1f}ms → {v['mean']:.1f}ms  "
                     f"({fmt_pct(delta_pct)})")

    # --- C3: Critical-path evidence
    lines.append("\n## Reviewer Comment C3: Critical-Path Evidence (Fault Latency)\n")
    for (policy, depth, bench, size), t in sorted(telemetry.items()):
        lines.append(
            f"- **{bench}** size={size} p{policy}: "
            f"hit_rate={t['hit_rate']:.3f} "
            f"lat_median={t['lat_median_ns']/1000:.1f}µs "
            f"lock_acq_median={t['ph01_median_ns']/1000:.1f}µs "
            f"metadata_median={t['ph12_median_ns']/1000:.1f}µs")

    # --- C1: Platform notes
    lines.append("\n## Platform Notes: T4 vs RTX 5070 Ti\n")
    lines.append(
        "- T4 (Turing sm_75): PCIe 3.0, 15.36 GiB VRAM, ~320 GB/s memory BW.\n"
        "- Original experiments used RTX 5070 Ti (Ada Lovelace sm_89): PCIe 5.0, "
        "higher peak BW.\n"
        "- T4 shows higher fault latency (µs range) due to slower PCIe bandwidth "
        "and older fault-service pipeline.\n"
        "- Speculation benefit expected to be *more pronounced* on T4 due to "
        "higher latency baseline (more headroom to save).\n"
        "- Oversubscription experiments use balloon trick: 11 GiB VRAM pinned "
        "leaving ~4 GiB usable; sizes 25000/28300/32000 give 1.25×/1.6×/2.05× "
        "oversubscription.\n"
        "- BFS sizes capped at log₂=24 (log₂=25/26 OOM: 4.3/8 GB host malloc "
        "for edge buffer).\n"
    )
    return '\n'.join(lines) + '\n'


# ── CSV export ────────────────────────────────────────────────────────────────

def write_timing_csv(timing, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['policy', 'depth', 'benchmark', 'size',
                    'mean_ms', 'std_ms', 'n', 'median_ms'])
        for (p, d, b, s), v in sorted(timing.items()):
            w.writerow([p, d, b, s,
                        f"{v['mean']:.4f}", f"{v['std']:.4f}",
                        v['n'], f"{v['median']:.4f}"])

def write_telemetry_csv(telemetry, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['policy', 'depth', 'benchmark', 'size',
                    'n_batches', 'hit_rate', 'enqueues', 'hits',
                    'lat_median_ns', 'lat_mean_ns', 'lat_p95_ns',
                    'ph01_median_ns', 'ph12_median_ns'])
        for (p, d, b, s), v in sorted(telemetry.items()):
            w.writerow([p, d, b, s,
                        v['n_batches'],
                        f"{v['hit_rate']:.5f}",
                        v['enqueues'], v['hits'],
                        f"{v['lat_median_ns']:.0f}",
                        f"{v['lat_mean_ns']:.0f}",
                        f"{v['lat_p95_ns']:.0f}",
                        f"{v['ph01_median_ns']:.0f}",
                        f"{v['ph12_median_ns']:.0f}"])


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(description='Phase B results aggregation.')
    ap.add_argument('--results-dir', default=RESULTS_DIR)
    ap.add_argument('--out-dir',     default=OUT_DIR)
    args = ap.parse_args()

    print(f"[analyze_phaseB] Results: {args.results_dir}")
    print(f"[analyze_phaseB] Output:  {args.out_dir}")

    timing    = aggregate_timing(args.results_dir)
    telemetry = aggregate_telemetry(args.results_dir)

    print(f"[analyze_phaseB] Loaded {len(timing)} timing configs, "
          f"{len(telemetry)} telemetry configs")

    os.makedirs(args.out_dir, exist_ok=True)

    write_timing_csv(timing,    os.path.join(args.out_dir, 'phaseB_timing.csv'))
    write_telemetry_csv(telemetry, os.path.join(args.out_dir, 'phaseB_telemetry.csv'))
    print("[analyze_phaseB] Wrote timing and telemetry CSVs")

    summary = build_summary(timing, telemetry)
    summary_path = os.path.join(args.out_dir, 'SUMMARY.md')
    Path(summary_path).write_text(summary)
    print(f"[analyze_phaseB] Wrote {summary_path}")

    try_plots(timing, telemetry, args.out_dir)


if __name__ == '__main__':
    main()
