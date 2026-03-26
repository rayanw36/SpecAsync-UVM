import subprocess
import csv
import re
import os

# ================= CONFIGURATION =================
OUTPUT_FILE = "sync1_fault_analysis.csv"
# Define constant for readable sizes (assuming 4-byte floats)
MEGA_ELEM = 1024 * 1024

# Test Cases: (Benchmark Name, Binary Path, List of Sizes in Elements)
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
# =================================================

def parse_nsys_faults(output):
    """
    Parses the nsys text output to find 'Total GPU PageFaults'.
    It locates the header line, finds the start index of the column,
    and then grabs the number from the corresponding data line two rows down.
    """
    try:
        lines = output.splitlines()
        header_index = -1
        
        # 1. Find the header line for the summary table
        # We look for the line containing the specific column name
        for i, line in enumerate(lines):
            if "Total GPU PageFaults" in line:
                header_index = i
                break
        
        # Check if header found and if there are enough lines following it for data
        if header_index == -1 or header_index + 2 >= len(lines):
            return "0" # Table or data row not found

        # 2. Identify the start position of the column
        header_line = lines[header_index]
        col_name = "Total GPU PageFaults"
        start_pos = header_line.find(col_name)
        
        if start_pos == -1:
             return "0" # Should not happen if it was in the line, but safety first

        # 3. The data is 2 lines down (Line 1: Header, Line 2: ---, Line 3: Data)
        data_line = lines[header_index + 2]
        
        # 4. Extract the number. We extract a chunk starting at the column index.
        # We grab enough characters to cover a large number (e.g., 20 chars)
        if len(data_line) > start_pos:
            # Extract a chunk of text starting from the column position
            raw_chunk = data_line[start_pos:start_pos+20]
            
            # Use regex to find the first sequence of digits and commas in that chunk
            # This handles numbers aligned left or right within the column space
            match = re.search(r"([0-9,]+)", raw_chunk)
            if match:
                # Remove commas and return
                clean_value = match.group(1).replace(',', '')
                return clean_value if clean_value else "0"
                
    except Exception as e:
        print(f"Warning: Parsing failed: {e}")
        pass
    return "0"

print(f"Starting Fault Analysis Suite. Results will be saved to {OUTPUT_FILE}...")

with open(OUTPUT_FILE, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    # We only care about the benchmark config and the fault count
    writer.writerow(["Benchmark", "Size_Arg", "Approx_Input_GB", "Faults_Detected_Nsys"])

    total_benchmarks = sum(len(sizes) for _, _, sizes in TEST_SUITE)
    current_benchmark = 0

    for name, binary, sizes in TEST_SUITE:
        for size in sizes:
            current_benchmark += 1
            # Calculate approx Input GB for reference
            if name in ["SGEMM", "Stencil"]:
                size_gb = (size * size * 4) / 1e9 
            else:
                size_gb = (size * 4) / 1e9

            print(f"[{current_benchmark}/{total_benchmarks}] Running {name} Size {size} (~{size_gb:.2f} GB)...")

            # Command: Run nsys specifically to get fault stats
            # We use --force-overwrite and a temp output name to avoid clutter
            cmd_nsys = (
                f"nsys profile --stats=true --trace=cuda "
                f"--cuda-um-gpu-page-faults=true "
                f"--output=temp_fault_check --force-overwrite=true "
                f"{binary} {size}"
            )
            
            try:
                # Run command and capture both stdout and stderr (nsys stats often print to stderr)
                result = subprocess.run(cmd_nsys, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                output = result.stdout
                
                # Parse the fault count using the robust regex function
                faults = parse_nsys_faults(output)
                
                print(f"  -> Detected Faults: {faults}")
                
                # Write row to CSV
                writer.writerow([name, size, f"{size_gb:.2f}", faults])
                csvfile.flush() # Save progress immediately

            except Exception as e:
                print(f"  -> Error running nsys: {e}")
                writer.writerow([name, size, f"{size_gb:.2f}", "Error"])

    # Clean up the temporary nsys output files
    print("\nCleaning up temporary nsys files...")
    subprocess.run("rm temp_fault_check.nsys-rep temp_fault_check.sqlite", shell=True, stderr=subprocess.DEVNULL)

print(f"\nFault Analysis Complete! Results saved to {OUTPUT_FILE}")
