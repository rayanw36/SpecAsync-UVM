import subprocess
import csv
import re
import time
import os

# Define sizes in Elements (floats = 4 bytes)
# 1 GB = 256 * 1024 * 1024 floats
GB_FLOATS = 1024 * 1024 * 256

# Test Cases: (Benchmark Name, Binary Path, List of Sizes in Elements)
TEST_SUITE = [
    ("STREAM", "./bench_stream", [
        int(0.5 * GB_FLOATS), # 2 GB (Small)
        int(2.0 * GB_FLOATS), # 8 GB (Medium)
        int(3.5 * GB_FLOATS), # 14 GB (Near Limit)
        int(4.5 * GB_FLOATS)  # 18 GB (Oversubscription!)
    ]),
    ("SGEMM", "./bench_sgemm", [
        4096,   # ~0.2 GB
        8192,   # ~0.8 GB
        16384,  # ~3.2 GB
        24000   # ~7.0 GB (Long run time)
    ]),
    ("Stencil", "./bench_stencil", [
        8192,   # ~0.5 GB
        16384,  # ~2.1 GB
        24000   # ~4.6 GB
    ]),
    ("cuFFT", "./bench_cufft", [
        1024*1024*64,   # 0.5 GB
        1024*1024*256,  # 2.0 GB
        1024*1024*512   # 4.0 GB
    ])
]

OUTPUT_FILE = "specasync_results.csv"

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
            if "Total GPU PageFaults" in line and "um_total_sum" not in line:
                header_index = i
                break
        
        if header_index == -1:
            return "Table Not Found"

        # 2. Identify the start and end position of the "Total GPU PageFaults" column
        # The header looks like: "...  Total CPU Page Faults  Total GPU PageFaults  ..."
        header_line = lines[header_index]
        col_name = "Total GPU PageFaults"
        start_pos = header_line.find(col_name)
        end_pos = start_pos + len(col_name)

        # 3. The data is usually 2 lines down (Line 1: Header, Line 2: dashes ----, Line 3: Data)
        data_line = lines[header_index + 2]
        
        # 4. Extract the text at that exact position
        if len(data_line) > start_pos:
            # Grab a bit more context in case the number is wider or shifted slightly
            # We take a slice from start_pos to end_pos, strip spaces, and remove commas
            raw_value = data_line[start_pos:end_pos+5].strip()
            
            # Sometimes the number aligns to the right, so we split just in case
            # But taking the slice is usually safest. Let's try to just clean the string.
            # If the column is empty, it might be blank.
            if not raw_value:
                return "0"
            
            # Filter for digits (e.g. "1,536" -> "1536")
            clean_value = ''.join(filter(str.isdigit, raw_value))
            return clean_value if clean_value else "0"

    except Exception as e:
        return f"Parse Error: {str(e)}"

    return "Not Found"

print(f"Starting Benchmark Suite. Results will be saved to {OUTPUT_FILE}...")

with open(OUTPUT_FILE, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Benchmark", "Size_Arg", "Size_GB", "Time_ms", "Bandwidth_GBs", "Faults_Detected"])

    for name, binary, sizes in TEST_SUITE:
        for size in sizes:
            # Calculate approx GB for logging
            if name == "SGEMM" or name == "Stencil":
                size_gb = (size * size * 4) / 1e9 
            else:
                size_gb = (size * 4) / 1e9 # Approximation for 1 array
            
            print(f"Running {name} with size {size} (~{size_gb:.2f} GB)...")
            
            # Command: Run nsys to get fault counts, but also capture stdout for time
            # Construct a meaningful filename for the report (e.g., STREAM_2GB)
            report_name = f"{name}_{size_gb:.1f}GB"
            
            # Full command with FLAGS and OUTPUT NAME
            cmd = (
                f"nsys profile --stats=true --trace=cuda "
                f"--cuda-memory-usage=true --cuda-um-gpu-page-faults=true "
                f"--cuda-um-cpu-page-faults=true "
                f"--output={report_name} --force-overwrite=true "
                f"{binary} {size}"
            )
            
            try:
                # Run command
                result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                output = result.stdout
                
                # 1. Parse Time (ms) from Benchmark Output (Standard Output)
                time_ms = "N/A"
                bw = "N/A"
                
                # Regex to find "[RESULT] Time: 123.45 ms"
                match_time = re.search(r"\[RESULT\] Time:\s+(\d+\.\d+)", output)
                if match_time:
                    time_ms = match_time.group(1)
                
                match_bw = re.search(r"Bandwidth:\s+(\d+\.\d+)", output)
                if match_bw:
                    bw = match_bw.group(1)

                # 2. Parse Faults from Nsight Summary (Stderr/Stdout mixed)
                # We look for the "um_total_sum" table row
                faults = parse_nsys_stats(output)
                if "Total GPU Page Faults" in output:
                    # Try to find the number. This is brittle but useful.
                    # It's often better to just look at the report manually for the key runs.
                    pass

                print(f"  -> Time: {time_ms} ms | Faults: {faults}")
                writer.writerow([name, size, f"{size_gb:.2f}", time_ms, bw, faults])
                csvfile.flush() # Save progress
                
            except Exception as e:
                print(f"  -> Error: {e}")

print("Suite Finished!")
