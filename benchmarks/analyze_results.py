import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# ================= CONFIGURATION =================
FILE_BASELINE = "robust_results_baseline.csv"
FILE_IMPROVED = "robust_results_specasync____3.csv"
OUTPUT_DIR = "analysis_output_____3"
# =================================================

def clean_dataframe(df, filename):
    """ Cleans column names and ensures numeric types """
    # 1. Strip whitespace from column names (Fixes ' Size_GB' error)
    df.columns = df.columns.str.strip()
    
    # 2. Check for required columns
    required = ['Benchmark', 'Size_Arg', 'Time_ms']
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"CRITICAL ERROR in {filename}: Missing columns {missing}")
        print(f"Found columns: {df.columns.tolist()}")
        return None

    # 3. Ensure Time_ms is numeric
    df['Time_ms'] = pd.to_numeric(df['Time_ms'], errors='coerce')
    
    # 4. Fix missing 'Size_GB' if it doesn't exist (Backwards compatibility)
    if 'Approx_Input_GB' not in df.columns:
        print(f"Warning: 'Size_GB' missing in {filename}. Calculating from Size_Arg...")
        # Approximate GB (assuming float array). Not perfect for SGEMM but good for sorting.
        df['Size_GB'] = (pd.to_numeric(df['Size_Arg'], errors='coerce') * 4) / 1e9
    
    return df

def load_and_aggregate(filename, label):
    if not os.path.exists(filename):
        print(f"Error: File {filename} not found.")
        return None

    try:
        df = pd.read_csv(filename)
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return None

    df = clean_dataframe(df, filename)
    if df is None: return None
    
    # Group by Benchmark and Size
    # We use Size_Arg for grouping to be precise, keep Size_GB for labels
    stats = df.groupby(['Benchmark', 'Size_Arg'])['Time_ms'].agg(
        Mean='mean',
        Std='std',
        Var='var',
        Count='count'
    ).reset_index()
    
    # Add Size_GB back for plotting (take the average or max of the group)
    # (Since Size_Arg is constant for a group, Size_GB should be too)
    if 'Size_GB' in df.columns:
        size_map = df[['Size_Arg', 'Size_GB']].drop_duplicates().set_index('Size_Arg')
        stats['Size_GB'] = stats['Size_Arg'].map(size_map['Size_GB'])
    else:
        stats['Size_GB'] = 0

    stats['Type'] = label
    return stats

def plot_benchmark(benchmark_name, df_base, df_imp, output_dir):
    # Filter data
    data_base = df_base[df_base['Benchmark'] == benchmark_name].sort_values('Size_Arg')
    data_imp = df_imp[df_imp['Benchmark'] == benchmark_name].sort_values('Size_Arg')
    
    if data_base.empty or data_imp.empty:
        return

    # Prepare Plot Data
    labels = [f"{s:.2f} GB" for s in data_base['Size_GB']]
    x = np.arange(len(labels))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot Bars with Error Bars
    ax.bar(x - width/2, data_base['Mean'], width, label='Baseline (Stock)', 
           yerr=data_base['Std'], capsize=5, color='#4c72b0', alpha=0.9)
    
    ax.bar(x + width/2, data_imp['Mean'], width, label='SpecAsync (Improved)', 
           yerr=data_imp['Std'], capsize=5, color='#55a868', alpha=0.9)

    ax.set_ylabel('Execution Time (ms)')
    ax.set_title(f'{benchmark_name}: Latency Comparison (Lower is Better)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    # Add Speedup Labels
    means_base = data_base['Mean'].values
    means_imp = data_imp['Mean'].values
    stds_base = data_base['Std'].values
    stds_imp = data_imp['Std'].values
    
    for i in range(len(x)):
        if i >= len(means_imp): break
        speedup = (1 - (means_imp[i] / means_base[i])) * 100
        color = 'green' if speedup > 0 else 'red'
        sign = '+' if speedup > 0 else ''
        
        # Height for text (bar height + error bar + padding)
        h_base = means_base[i] + (stds_base[i] if not np.isnan(stds_base[i]) else 0)
        h_imp = means_imp[i] + (stds_imp[i] if not np.isnan(stds_imp[i]) else 0)
        height = max(h_base, h_imp)
        
        ax.text(x[i], height * 1.05, f"{sign}{speedup:.1f}%", 
                ha='center', va='bottom', color=color, fontweight='bold', fontsize=9)

    plt.tight_layout()
    plot_path = os.path.join(output_dir, f"plot_{benchmark_name}.png")
    plt.savefig(plot_path, dpi=300)
    print(f"Saved plot: {plot_path}")
    plt.close()

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print("--- Loading and Cleaning Data ---")
    stats_base = load_and_aggregate(FILE_BASELINE, "Baseline")
    stats_imp = load_and_aggregate(FILE_IMPROVED, "SpecAsync")
    
    if stats_base is None or stats_imp is None:
        print("FAILED: Could not load one of the datasets. Check column names above.")
        return

    print("--- Generating Summary CSV ---")
    merged = pd.merge(stats_base, stats_imp, on=['Benchmark', 'Size_Arg'], suffixes=('_Base', '_Imp'))
    merged['Speedup_Pct'] = (1 - (merged['Mean_Imp'] / merged['Mean_Base'])) * 100
    
    summary_path = os.path.join(OUTPUT_DIR, "final_statistical_summary.csv")
    merged.to_csv(summary_path, index=False)
    print(f"Summary saved to {summary_path}")

    print("\n--- Generating Plots ---")
    for bench in stats_base['Benchmark'].unique():
        plot_benchmark(bench, stats_base, stats_imp, OUTPUT_DIR)

    print("\nAnalysis Complete!")

if __name__ == "__main__":
    main()
