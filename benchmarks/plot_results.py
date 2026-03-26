import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 1. Load Data Directly from the CSV File
csv_file = "baseline_results.csv"

try:
    df = pd.read_csv(csv_file)
    print(f"Successfully loaded {len(df)} rows from {csv_file}")
except FileNotFoundError:
    print(f"Error: Could not find '{csv_file}'. Make sure you run 'run_suite.py' first.")
    exit(1)

# 2. Correct "Size_GB" to "Total_GB" based on array counts
# STREAM: 3 arrays (a,b,c). SGEMM: 3 (A,B,C). Stencil: 2 (in,out). cuFFT: 1 (complex=8bytes, code used 4)
def get_real_mem(row):
    if row['Benchmark'] == 'STREAM': return row['Size_GB'] * 3
    if row['Benchmark'] == 'SGEMM': return row['Size_GB'] * 3
    if row['Benchmark'] == 'Stencil': return row['Size_GB'] * 2
    if row['Benchmark'] == 'cuFFT': return row['Size_GB'] * 2 # Complex is 2x float
    return row['Size_GB']

# Ensure 'Faults_Detected' is numeric (coerces errors to NaN if "Table Not Found" persists)
df['Faults_Detected'] = pd.to_numeric(df['Faults_Detected'], errors='coerce')

# Calculate metrics
df['Total_Memory_GB'] = df.apply(get_real_mem, axis=1)
df['Fault_Density'] = df['Faults_Detected'] / df['Total_Memory_GB'] # Faults per GB

# Drop rows where Faults could not be parsed (avoid plotting errors)
df = df.dropna(subset=['Faults_Detected'])

# Set style
sns.set_style("whitegrid")
plt.rcParams.update({'font.size': 12})

# --- Graph 1: Fault Density (The "Why We Need SpecAsync" Graph) ---
plt.figure(figsize=(10, 6))
# Filter for > 1.0 GB to get stable readings
plot_data = df[df['Size_GB'] > 0.5].copy()

if not plot_data.empty:
    barplot = sns.barplot(x='Benchmark', y='Fault_Density', data=plot_data, errorbar=None, palette="viridis")
    plt.title('OS Overhead Intensity: Faults per GB of Data', fontsize=16, fontweight='bold')
    plt.ylabel('Faults / GB', fontsize=14)
    plt.xlabel('Workload', fontsize=14)
    plt.bar_label(barplot.containers[0], fmt='%.0f')
    plt.tight_layout()
    plt.savefig('graph_fault_density.png')
    print("Generated graph_fault_density.png")
else:
    print("Not enough data > 0.5GB to plot Fault Density.")

# --- Graph 2: Scaling Behavior (Time vs Size) ---
plt.figure(figsize=(10, 6))
sns.lineplot(x='Total_Memory_GB', y='Time_ms', hue='Benchmark', style='Benchmark', 
             markers=True, dashes=False, data=df, linewidth=2.5, markersize=9)
plt.title('Baseline Performance Scaling (UVM)', fontsize=16, fontweight='bold')
plt.ylabel('Execution Time (ms)', fontsize=14)
plt.xlabel('Total Memory Footprint (GB)', fontsize=14)
plt.legend(title='Benchmark', fontsize=12)
plt.grid(True, which="both", ls="--")
plt.tight_layout()
plt.savefig('graph_scaling.png')
print("Generated graph_scaling.png")
