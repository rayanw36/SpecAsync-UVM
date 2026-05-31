#!/usr/bin/env python3
"""
cost_benefit.py — SpecAsync-UVM speculation cost-benefit analysis.

Reads Phase 2 telemetry from:
    results/p{policy}_d{depth}/{benchmark}/{size}/batch_records.csv
    (produced by specasync_parse.py after each experimental run)

Baseline comparison uses p0_d0 (speculation disabled) if present; otherwise
falls back to results/baseline/robust_results_baseline.csv (Phase 1 format).

Outputs:
    results/summary/cost_benefit.md       markdown table for paper
    results/summary/phase_breakdown.pdf   stacked bar chart (requires matplotlib)

Metrics computed per (benchmark, size, config):
    enqueue_overhead_ns      mean enqueue_overhead_ns field from batch records
    service_latency_delta_ns baseline_mean - config_mean  (positive = faster)
    hit_rate                 sum(spec_hits) / sum(spec_enqueues)
    wasted_spec_rate         1 - hit_rate
    net_benefit_per_fault_ns (service_latency_delta * hit_rate) - enqueue_overhead
    phase_{lock,meta,res}_mean_ns  mean of T1-T0, T2-T1, T3-T2
"""

import csv
import os
import sys
import glob
import statistics
from pathlib import Path

_HERE        = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR  = os.path.normpath(os.path.join(_HERE, '..', '..', 'results'))
SUMMARY_DIR  = os.path.join(RESULTS_DIR, 'summary')

PHASE1_BASELINE = os.path.join(RESULTS_DIR, 'baseline', 'robust_results_baseline.csv')


# ── Data loaders ─────────────────────────────────────────────────────────────

def find_phase2_configs(results_dir):
    """Return sorted list of (policy, depth, config_dir) for p*_d* directories."""
    configs = []
    for d in sorted(glob.glob(os.path.join(results_dir, 'p*_d*'))):
        name = os.path.basename(d)
        try:
            p_str, d_str = name.split('_')
            configs.append((int(p_str[1:]), int(d_str[1:]), d))
        except (ValueError, IndexError):
            continue
    return configs


def load_batch_csv(csv_path):
    """Load a batch_records.csv produced by specasync_parse.py."""
    recs = []
    with open(csv_path, newline='') as fh:
        for row in csv.DictReader(fh):
            parsed = {}
            for k, v in row.items():
                try:
                    parsed[k] = float(v)
                except (ValueError, TypeError):
                    parsed[k] = v
            recs.append(parsed)
    return recs


def load_phase1_timing(csv_path):
    """
    Load Phase 1 robust_results CSV; return dict
    (Benchmark, Size_Arg) -> list[float] of Time_ms values.
    """
    data = {}
    with open(csv_path, newline='') as fh:
        for row in csv.DictReader(fh):
            key = (row['Benchmark'], row['Size_Arg'])
            try:
                data.setdefault(key, []).append(float(row['Time_ms']))
            except (ValueError, KeyError):
                pass
    return data


# ── Metric computation ────────────────────────────────────────────────────────

def compute_metrics(batch_recs, baseline_latency_ns=None):
    """
    Compute cost-benefit metrics from a list of batch_records dicts.

    baseline_latency_ns: mean total service latency of the disabled-speculation
                         run for the same (benchmark, size), in ns.
                         If None, service_latency_delta is reported as 0.
    """
    if not batch_recs:
        return None

    enqueues = sum(r['spec_enqueues'] for r in batch_recs)
    hits     = sum(r['spec_hits']     for r in batch_recs)

    overhead_vals = [r['enqueue_overhead_ns'] for r in batch_recs]
    latency_vals  = [r['total_latency_ns']    for r in batch_recs]
    ph01_vals     = [r['phase01_ns']          for r in batch_recs]
    ph12_vals     = [r['phase12_ns']          for r in batch_recs]
    ph23_vals     = [r['phase23_ns']          for r in batch_recs]

    hit_rate     = hits / enqueues if enqueues else 0.0
    overhead     = statistics.mean(overhead_vals) if overhead_vals else 0.0
    mean_latency = statistics.mean(latency_vals)  if latency_vals  else 0.0

    delta = (baseline_latency_ns - mean_latency) if baseline_latency_ns is not None else 0.0
    net   = (delta * hit_rate) - overhead

    return {
        'num_batches':               len(batch_recs),
        'enqueue_overhead_ns':       overhead,
        'mean_service_latency_ns':   mean_latency,
        'service_latency_delta_ns':  delta,
        'hit_rate':                  hit_rate,
        'wasted_spec_rate':          1.0 - hit_rate,
        'net_benefit_per_fault_ns':  net,
        'phase_lock_mean_ns':        statistics.mean(ph01_vals) if ph01_vals else 0.0,
        'phase_meta_mean_ns':        statistics.mean(ph12_vals) if ph12_vals else 0.0,
        'phase_res_mean_ns':         statistics.mean(ph23_vals) if ph23_vals else 0.0,
    }


# ── Markdown output ───────────────────────────────────────────────────────────

def build_markdown_table(rows):
    cols = ('Benchmark', 'Size', 'Config',
            'Hit Rate', 'Wasted Spec',
            'Enq OH (ns)', 'Svc Δ (ns)', 'Net Benefit/F (ns)')
    sep = '|' + '|'.join(['---'] * len(cols)) + '|'
    lines = ['| ' + ' | '.join(cols) + ' |', sep]
    for r in rows:
        lines.append(
            f"| {r['benchmark']} | {r['size']} | {r['config']}"
            f" | {r['hit_rate']:.3f}"
            f" | {r['wasted_spec_rate']:.3f}"
            f" | {r['enqueue_overhead_ns']:.0f}"
            f" | {r['service_latency_delta_ns']:.0f}"
            f" | {r['net_benefit_per_fault_ns']:.0f} |"
        )
    return '\n'.join(lines)


# ── Phase breakdown chart ─────────────────────────────────────────────────────

def try_plot_phase_breakdown(rows, out_pdf):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("[cost_benefit] matplotlib not available — skipping phase_breakdown.pdf",
              file=sys.stderr)
        return

    labels = [f"{r['benchmark']}\n{r['size']}\n{r['config']}" for r in rows]
    lock_v = [r['phase_lock_mean_ns'] for r in rows]
    meta_v = [r['phase_meta_mean_ns'] for r in rows]
    res_v  = [r['phase_res_mean_ns']  for r in rows]

    x      = np.arange(len(labels))
    width  = 0.55
    bot_lm = [a + b for a, b in zip(lock_v, meta_v)]

    fig, ax = plt.subplots(figsize=(max(8, len(rows) * 0.8), 6))
    ax.bar(x, lock_v, width, label='Lock Acq  T0→T1', color='#4878d0')
    ax.bar(x, meta_v, width, bottom=lock_v, label='Metadata  T1→T2', color='#ee854a')
    ax.bar(x, res_v,  width, bottom=bot_lm, label='Residency T2→T3', color='#6acc65')

    ax.set_ylabel('Mean time (ns)')
    ax.set_title('Fault-Service Phase Breakdown per Config')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    plt.tight_layout()
    plt.savefig(out_pdf)
    print(f"[cost_benefit] Saved: {out_pdf}")
    plt.close()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(description='SpecAsync cost-benefit analysis.')
    ap.add_argument('--results-dir', default=RESULTS_DIR,
                    help='Root results directory')
    ap.add_argument('--summary-dir', default=SUMMARY_DIR,
                    help='Output directory for markdown + PDF')
    args = ap.parse_args()

    os.makedirs(args.summary_dir, exist_ok=True)

    configs = find_phase2_configs(args.results_dir)
    if not configs:
        print("[cost_benefit] No p*_d* config directories found in:")
        print(f"               {args.results_dir}")
        print("               Run run_all_experiments.sh first (Phase B).")
        sys.exit(0)

    # Build baseline latency map from p0_d0 (or Phase 1 CSV as fallback)
    baseline_map = {}
    for policy, depth, config_dir in configs:
        if policy == 0 and depth == 0:
            for csv_f in glob.glob(
                    os.path.join(config_dir, '*', '*', 'batch_records.csv')):
                parts = Path(csv_f).parts
                bench = parts[-3]
                size  = parts[-2]
                recs  = load_batch_csv(csv_f)
                if recs:
                    baseline_map[(bench, size)] = statistics.mean(
                        r['total_latency_ns'] for r in recs)
            break

    if not baseline_map and os.path.exists(PHASE1_BASELINE):
        print("[cost_benefit] p0_d0 not found; using Phase 1 baseline for delta computation.")
        p1 = load_phase1_timing(PHASE1_BASELINE)
        # Phase 1 times are in ms; convert to ns for comparison with telemetry
        for (bench, size), times in p1.items():
            baseline_map[(bench, size)] = statistics.mean(times) * 1e6

    table_rows = []
    for policy, depth, config_dir in configs:
        config_name = f"p{policy}_d{depth}"
        for csv_f in sorted(glob.glob(
                os.path.join(config_dir, '*', '*', 'batch_records.csv'))):
            parts = Path(csv_f).parts
            bench = parts[-3]
            size  = parts[-2]
            recs  = load_batch_csv(csv_f)
            if not recs:
                continue
            base_lat = baseline_map.get((bench, size))
            m = compute_metrics(recs, base_lat)
            if m is None:
                continue
            row = {'benchmark': bench, 'size': size, 'config': config_name}
            row.update(m)
            table_rows.append(row)

    if not table_rows:
        print("[cost_benefit] No batch_records.csv found under any config directory.")
        sys.exit(0)

    md_body = (
        "# SpecAsync-UVM Cost-Benefit Analysis\n\n"
        "Generated by `benchmarks/tools/cost_benefit.py`.\n\n"
        "**Column definitions:**\n"
        "- **Hit Rate** = sum(spec_hits) / sum(spec_enqueues)\n"
        "- **Wasted Spec** = 1 − Hit Rate\n"
        "- **Enq OH** = mean enqueue_overhead_ns per batch\n"
        "- **Svc Δ** = baseline_mean_latency − config_mean_latency (positive = faster)\n"
        "- **Net Benefit/F** = (Svc Δ × Hit Rate) − Enq OH\n\n"
    ) + build_markdown_table(table_rows) + '\n'

    md_path  = os.path.join(args.summary_dir, 'cost_benefit.md')
    pdf_path = os.path.join(args.summary_dir, 'phase_breakdown.pdf')
    Path(md_path).write_text(md_body)
    print(f"[cost_benefit] Written: {md_path}")

    try_plot_phase_breakdown(table_rows, pdf_path)


if __name__ == '__main__':
    main()
