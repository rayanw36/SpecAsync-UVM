import subprocess
import csv
import re
import time
import os

# Configuration
NUM_RUNS = 50   # Total repetitions for statistics
WARMUP_RUNS = 1 # Runs to discard at the start to stabilize GPU state
OUTPUT_FILE = "robust_results_specasync3.csv"

# Define constant for readable sizes (assuming 4-byte floats)
# NOTE: This constant is used to define input sizes, not necessarily total memory footprint.
MEGA_ELEM = 1024 * 1024

# Test Cases: (Benchmark Name, Binary Path, List of Sizes)
# Sizes are elements for 1D, or side length (N) for 2D.
TEST_SUITE = [
    ("STREAM", "./bench_stream", [
        int(128 * MEGA_ELEM), 
        int(256 * MEGA_ELEM), 
        int(512 * MEGA_ELEM)
    ]),
    ("SGEMM", "./bench_sgemm", [
        8192,   
        16384,  
        24000   
    ]),
    ("Stencil", "./bench_stencil", [
        8192,   
        16384,  
        24000   
    ]),
    ("cuFFT", "./bench_cufft", [
        int(64 * MEGA_ELEM),   
        int(128 * MEGA_ELEM),  
        int(256 * MEGA_ELEM)   
    ])
]

def parse_nsys_stats(output):
    """
    Parses the nsys text output to find 'Total GPU PageFaults'.
    It finds the 'um_total_sum' table, locates the column position, 
    and grabs the number from the data row.
    """
    try:
        lines = output.splitlines()
        header_index = -1
        
        # 1. Find the header line for the summary table
        for i, line in enumerate(lines):
            # Look for the specific header that contains both key phrases
            if "Total GPU PageFaults" in line and "um_total_sum" not in line:
                header_index = i
                break
        
        if header_index == -1 or header_index + 2 >= len(lines):
            return "Table Not Found"

        # 2. Identify the start position of the "Total GPU PageFaults" column
        # The header looks like: "...  Total CPU Page Faults  Total GPU PageFaults  ..."
        header_line = lines[header_index]
        col_name = "Total GPU PageFaults"
        start_pos = header_line.find(col_name)
        
        if start_pos == -1:
             return "Column Not Found"

        # 3. The data is usually 2 lines down (Line 1: Header, Line 2: dashes ----, Line 3: Data)
        data_line = lines[header_index + 2]
        
        # 4. Extract the text at that exact position. 
        # Grab enough characters to cover a large number (e.g., 15 chars wide)
        if len(data_line) > start_pos:
            # Extract a chunk of text starting from the column position
            # We grab 20 characters to be safe for large numbers like "123,456,789"
            raw_chunk = data_line[start_pos:start_pos+20]
            
            # Extract only digits and commas from this chunk
            # This handles numbers aligned left or right within the column space
            number_str = re.search(r"[0-9,]+", raw_chunk)
            
            if number_str:
                # Remove commas and return the pure digit string
                clean_value = number_str.group(0).replace(',', '')
                return clean_value if clean_value else "0"
            else:
                # If no digits found in that chunk, it's 0
                return "0"

    except Exception as e:
        return f"Parse Error: {str(e)}"

    return "Not Found"
# Pre-compile regex for performance during repeated runs
TIME_REGEX = re.compile(r"\[RESULT\] Time:\s+(\d+\.\d+)")
BW_REGEX = re.compile(r"Bandwidth:\s+(\d+\.\d+)")

def get_time_from_output(output):
    match = TIME_REGEX.search(output)
    return match.group(1) if match else "N/A"

def get_bw_from_output(output):
    match = BW_REGEX.search(output)
    return match.group(1) if match else "N/A"

print(f"Starting Robust Benchmark Suite. Warmup: {WARMUP_RUNS}, Stats Runs: {NUM_RUNS}.")
print(f"Saving to {OUTPUT_FILE}...")

# Open csv file once
with open(OUTPUT_FILE, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    # Added "Iteration_Type" to distinguish warmup runs if you choose to log them later
    writer.writerow(["Benchmark", "Size_Arg", "Approx_Input_GB", "Run_ID", "Time_ms", "Bandwidth_GBs", "Faults_Detected_Nsys"])

    total_benchmarks = sum(len(sizes) for _, _, sizes in TEST_SUITE)
    current_benchmark = 0

    for name, binary, sizes in TEST_SUITE:
        for size in sizes:
            current_benchmark += 1
            # Calculate approx Input GB for reference
            if name in ["SGEMM", "Stencil"]:
                # Size is N, input is usually N*N floats
                size_gb = (size * size * 4) / 1e9 
            else:
                 # Size is total elements
                size_gb = (size * 4) / 1e9

            print(f"\n--- [{current_benchmark}/{total_benchmarks}] Benchmarking {name} Size {size} (~{size_gb:.2f} GB Input) ---")

            # =========================================
            # STEP 1: Fault Validation (nsys run)
            # =========================================
            print(f"  > Step 1: Validating Fault Counts (nsys run)...")
            # Added -f to force overwrite, changed output name to be unique per run to avoid conflicts
            cmd_nsys = (
                f"nsys profile --stats=true --trace=cuda "
                f"--cuda-um-gpu-page-faults=true "
                f"--output=temp_nsys_{name}_{size} --force-overwrite=true "
                f"{binary} {size}"
            )
            # Capture stderr too, sometimes nsys outputs crucial info there
            res_nsys = subprocess.run(cmd_nsys, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            faults = parse_nsys_stats(res_nsys.stdout)
            print(f"    Detected {faults} faults.")

            # =========================================
            # STEP 2: Warm-up (Crucial for variance)
            # =========================================
            if WARMUP_RUNS > 0:
                 print(f"  > Step 2: Warming up GPU ({WARMUP_RUNS} runs, discarded)...")
                 for w in range(WARMUP_RUNS):
                     subprocess.run(f"{binary} {size}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # =========================================
            # STEP 3: Statistical Data Collection
            # =========================================
            print(f"  > Step 3: Collecting Statistics ({NUM_RUNS} runs fast)...")
            for i in range(NUM_RUNS):
                cmd_run = f"{binary} {size}"
                res_run = subprocess.run(cmd_run, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                
                time_ms = get_time_from_output(res_run.stdout)
                bw = get_bw_from_output(res_run.stdout)

                if time_ms == "N/A":
                     print(f"    Warning: Run {i+1} failed to produce a time output.")

                # Write immediately
                writer.writerow([name, size, f"{size_gb:.2f}", i+1, time_ms, bw, faults])
                csvfile.flush()
                
                # Simple progress indicator per benchmark
                if (i+1) % 10 == 0 or (i+1) == NUM_RUNS:
                    print(f"    Finished run {i+1}/{NUM_RUNS}")

    # Clean up temp nsys files at the end
    print("\nCleaning up temporary nsys files...")
    subprocess.run("rm temp_nsys_*.nsys-rep temp_nsys_*.sqlite", shell=True, stderr=subprocess.DEVNULL)

print(f"\nSuite Finished! Results saved to {OUTPUT_FILE}")
