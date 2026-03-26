#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# ================= CONFIGURATION =================
FILE_BASELINE = "robust_results_baseline.csv"
FILE_EXP1 = "robust_results_specasync1.csv"   # Experiment 1 (old)
FILE_EXP2 = "robust_results_specasync3.csv"   # Experiment 2 (new)
OUTPUT_DIR = "analysis_output_3way"
# =================================================


def clean_dataframe(df: pd.DataFrame, filename: str) -> pd.DataFrame | None:
    """
    Cleans column names and ensures numeric types.
    Supports:
      - baseline/specasync2 format: Benchmark, Size_Arg, Time_ms, (maybe Size_GB)
      - specasync3 format: Benchmark, Size_Arg, Approx_Input_GB, Time_ms, ...
    Creates a unified numeric 'Size_GB' column for plotting.
    """
    df.columns = df.columns.str.strip()

    required = ['Benchmark', 'Size_Arg', 'Time_ms']
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"CRITICAL ERROR in {filename}: Missing columns {missing}")
        print(f"Found columns: {df.columns.tolist()}")
        return None

    # Ensure numeric
    df['Size_Arg'] = pd.to_numeric(df['Size_Arg'], errors='coerce')
    df['Time_ms'] = pd.to_numeric(df['Time_ms'], errors='coerce')

    # Unify Size_GB
    if 'Approx_Input_GB' in df.columns:
        df['Approx_Input_GB'] = pd.to_numeric(df['Approx_Input_GB'], errors='coerce')
        df['Size_GB'] = df['Approx_Input_GB']
    elif 'Size_GB' in df.columns:
        df['Size_GB'] = pd.to_numeric(df['Size_GB'], errors='coerce')
    else:
        # Fallback (rough): assumes 1D float arrays. Not exact for SGEMM/Stencil.
        print(f"Warning: No Approx_Input_GB/Size_GB in {filename}. Approximating from Size_Arg...")
        df['Size_GB'] = (df['Size_Arg'] * 4) / 1e9

    # Drop rows with missing essentials
    df = df.dropna(subset=['Benchmark', 'Size_Arg', 'Time_ms'])
    return df


def load_and_aggregate(filename: str, label: str) -> pd.DataFrame | None:
    if not os.path.exists(filename):
        print(f"Error: File {filename} not found.")
        return None

    try:
        df = pd.read_csv(filename)
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return None

    df = clean_dataframe(df, filename)
    if df is None:
        return None

    stats = df.groupby(['Benchmark', 'Size_Arg'])['Time_ms'].agg(
        Mean='mean',
        Std='std',
        Var='var',
        Count='count'
    ).reset_index()

    # Add Size_GB (use first value per Size_Arg if consistent)
    size_map = df[['Benchmark', 'Size_Arg', 'Size_GB']].drop_duplicates()
    # Map by (Benchmark, Size_Arg) to avoid SGEMM/Stencil ambiguity
    size_map = size_map.set_index(['Benchmark', 'Size_Arg'])['Size_GB']
    stats['Size_GB'] = stats.set_index(['Benchmark', 'Size_Arg']).index.map(size_map)

    stats['Type'] = label
    return stats


def plot_benchmark_3way(benchmark_name: str,
                        base: pd.DataFrame,
                        exp1: pd.DataFrame,
                        exp2: pd.DataFrame,
                        output_dir: str) -> None:
    b = base[base['Benchmark'] == benchmark_name].sort_values('Size_Arg')
    e1 = exp1[exp1['Benchmark'] == benchmark_name].sort_values('Size_Arg')
    e2 = exp2[exp2['Benchmark'] == benchmark_name].sort_values('Size_Arg')

    if b.empty:
        return

    # Align by Size_Arg intersection to avoid mismatched sizes
    common_sizes = set(b['Size_Arg'])
    common_sizes &= set(e1['Size_Arg'])
    common_sizes &= set(e2['Size_Arg'])

    if not common_sizes:
        print(f"Skipping {benchmark_name}: no common sizes across all three datasets.")
        return

    b = b[b['Size_Arg'].isin(common_sizes)].sort_values('Size_Arg')
    e1 = e1[e1['Size_Arg'].isin(common_sizes)].sort_values('Size_Arg')
    e2 = e2[e2['Size_Arg'].isin(common_sizes)].sort_values('Size_Arg')

    labels = [f"{s:.2f} GB" for s in b['Size_GB']]
    x = np.arange(len(labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(11, 6))

    ax.bar(x - width, b['Mean'], width, label='Baseline',
           yerr=b['Std'], capsize=5, alpha=0.9)

    ax.bar(x, e1['Mean'], width, label='SpecAsync Exp1',
           yerr=e1['Std'], capsize=5, alpha=0.9)

    ax.bar(x + width, e2['Mean'], width, label='SpecAsync Exp2',
           yerr=e2['Std'], capsize=5, alpha=0.9)

    ax.set_ylabel('Execution Time (ms)')
    ax.set_title(f'{benchmark_name}: Latency Comparison (Lower is Better)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    # Speedup labels (Exp1 and Exp2 vs Baseline)
    means_base = b['Mean'].values
    std_base = b['Std'].values

    means_e1 = e1['Mean'].values
    std_e1 = e1['Std'].values

    means_e2 = e2['Mean'].values
    std_e2 = e2['Std'].values

    for i in range(len(x)):
        # Compute heights for text placement
        h_base = means_base[i] + (std_base[i] if not np.isnan(std_base[i]) else 0.0)
        h_e1 = means_e1[i] + (std_e1[i] if not np.isnan(std_e1[i]) else 0.0)
        h_e2 = means_e2[i] + (std_e2[i] if not np.isnan(std_e2[i]) else 0.0)
        height = max(h_base, h_e1, h_e2)

        s1 = (1.0 - (means_e1[i] / means_base[i])) * 100.0
        s2 = (1.0 - (means_e2[i] / means_base[i])) * 100.0

        ax.text(x[i], height * 1.05,
                f"Exp1 {s1:+.1f}%\nExp2 {s2:+.1f}%",
                ha='center', va='bottom', fontsize=9, fontweight='bold')

    plt.tight_layout()
    plot_path = os.path.join(output_dir, f"plot_{benchmark_name}.png")
    plt.savefig(plot_path, dpi=300)
    print(f"Saved plot: {plot_path}")
    plt.close()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("--- Loading and Aggregating Data ---")
    stats_base = load_and_aggregate(FILE_BASELINE, "Baseline")
    stats_e1 = load_and_aggregate(FILE_EXP1, "SpecAsync_Exp1")
    stats_e2 = load_and_aggregate(FILE_EXP2, "SpecAsync_Exp2")

    if stats_base is None or stats_e1 is None or stats_e2 is None:
        print("FAILED: Could not load one of the datasets.")
        return

    print("--- Generating 3-way Summary CSV ---")
    merged = stats_base.merge(stats_e1, on=['Benchmark', 'Size_Arg'], suffixes=('_Base', '_E1'))
    merged = merged.merge(stats_e2, on=['Benchmark', 'Size_Arg'])

    # After second merge, exp2 columns are plain names (Mean, Std, etc). Rename them.
    merged = merged.rename(columns={
        'Mean': 'Mean_E2',
        'Std': 'Std_E2',
        'Var': 'Var_E2',
        'Count': 'Count_E2',
        'Size_GB': 'Size_GB_E2',
        'Type': 'Type_E2'
    })

    # Compute speedups vs baseline
    merged['Speedup_E1_Pct'] = (1 - (merged['Mean_E1'] / merged['Mean_Base'])) * 100
    merged['Speedup_E2_Pct'] = (1 - (merged['Mean_E2'] / merged['Mean_Base'])) * 100

    summary_path = os.path.join(OUTPUT_DIR, "final_statistical_summary_3way.csv")
    merged.to_csv(summary_path, index=False)
    print(f"Summary saved to {summary_path}")

    print("\n--- Generating Plots (3 bars per size) ---")
    for bench in sorted(stats_base['Benchmark'].unique()):
        plot_benchmark_3way(bench, stats_base, stats_e1, stats_e2, OUTPUT_DIR)

    print("\nAnalysis Complete!")


if __name__ == "__main__":
    main()
