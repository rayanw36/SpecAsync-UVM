#!/usr/bin/env python3
import subprocess
import csv
import re
import os

# =========================
# Configuration
# =========================
NUM_RUNS = 50        # Statistical runs
WARMUP_RUNS = 1      # Discarded warmup runs per (benchmark,size)
OUTPUT_FILE = "robust_results_specasync____3.csv"

MEGA_ELEM = 1024 * 1024

TEST_SUITE = [
    ("STREAM", "./bench_stream", [
        int(128 * MEGA_ELEM),
        int(256 * MEGA_ELEM),
        int(512 * MEGA_ELEM),
    ]),
    ("SGEMM", "./bench_sgemm", [
        8192,
        16384,
        24000,
    ]),
    ("Stencil", "./bench_stencil", [
        8192,
        16384,
        24000,
    ]),
    ("cuFFT", "./bench_cufft", [
        int(64 * MEGA_ELEM),
        int(128 * MEGA_ELEM),
        int(256 * MEGA_ELEM),
    ]),
]

# =========================
# Helpers
# =========================
TIME_REGEX = re.compile(r"\[RESULT\] Time:\s+(\d+\.\d+)")
BW_REGEX = re.compile(r"Bandwidth:\s+(\d+\.\d+)")

def get_time_from_output(output: str) -> str:
    m = TIME_REGEX.search(output)
    return m.group(1) if m else "N/A"

def get_bw_from_output(output: str) -> str:
    m = BW_REGEX.search(output)
    return m.group(1) if m else "N/A"

def parse_nsys_stats(output: str) -> str:
    """
    Parses the nsys text output to find 'Total GPU PageFaults'.
    Finds the header line containing 'Total GPU PageFaults' (not the um_total_sum label line),
    locates the column, and extracts the numeric value from the data row (2 lines below).
    """
    try:
        lines = output.splitlines()
        header_index = -1

        for i, line in enumerate(lines):
            if "Total GPU PageFaults" in line and "um_total_sum" not in line:
                header_index = i
                break

        if header_index == -1 or header_index + 2 >= len(lines):
            return "Table Not Found"

        header_line = lines[header_index]
        col_name = "Total GPU PageFaults"
        start_pos = header_line.find(col_name)
        if start_pos == -1:
            return "Column Not Found"

        data_line = lines[header_index + 2]
        if len(data_line) <= start_pos:
            return "0"

        raw_chunk = data_line[start_pos:start_pos + 20]
        number_str = re.search(r"[0-9,]+", raw_chunk)
        if number_str:
            return number_str.group(0).replace(",", "") or "0"
        return "0"

    except Exception as e:
        return f"Parse Error: {str(e)}"

def get_uvm_srcversion() -> str:
    try:
        return subprocess.check_output(
            "cat /sys/module/nvidia_uvm/srcversion",
            shell=True,
            text=True
        ).strip()
    except Exception:
        return "UNKNOWN"

def approx_input_gb(bench_name: str, size: int) -> float:
    # For SGEMM/Stencil, size is N and input is ~N*N floats.
    # For STREAM/cuFFT, size is total elements.
    if bench_name in ["SGEMM", "Stencil"]:
        return (size * size * 4) / 1e9
    return (size * 4) / 1e9

# =========================
# Main
# =========================
def main():
    uvm_src = get_uvm_srcversion()
    print(f"Loaded nvidia_uvm srcversion: {uvm_src}")
    print(f"Starting Robust Benchmark Suite. Warmup: {WARMUP_RUNS}, Stats Runs: {NUM_RUNS}.")
    print(f"Saving to {OUTPUT_FILE}...")

    total_benchmarks = sum(len(sizes) for _, _, sizes in TEST_SUITE)
    current_benchmark = 0

    with open(OUTPUT_FILE, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "UVM_Srcversion",
            "Benchmark",
            "Size_Arg",
            "Approx_Input_GB",
            "Run_ID",
            "Time_ms",
            "Bandwidth_GBs",
            "Faults_Detected_Nsys",
            "ExitCode",
        ])

        for name, binary, sizes in TEST_SUITE:
            for size in sizes:
                current_benchmark += 1
                size_gb = approx_input_gb(name, size)

                print(f"\n--- [{current_benchmark}/{total_benchmarks}] "
                      f"Benchmarking {name} Size {size} (~{size_gb:.2f} GB Input) ---")

                # =========================================
                # STEP 1: Fault Validation (nsys run)
                # =========================================
                print("  > Step 1: Validating Fault Counts (nsys run)...")
                safe_name = name.lower().replace(" ", "_")
                cmd_nsys = (
                    f"nsys profile --stats=true --trace=cuda "
                    f"--cuda-um-gpu-page-faults=true "
                    f"--output=temp_nsys_{safe_name}_{size} --force-overwrite=true "
                    f"{binary} {size}"
                )
                res_nsys = subprocess.run(
                    cmd_nsys,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                faults = parse_nsys_stats(res_nsys.stdout)
                print(f"    Detected {faults} faults.")

                # =========================================
                # STEP 2: Warm-up
                # =========================================
                if WARMUP_RUNS > 0:
                    print(f"  > Step 2: Warming up GPU ({WARMUP_RUNS} runs, discarded)...")
                    for _ in range(WARMUP_RUNS):
                        subprocess.run(
                            f"{binary} {size}",
                            shell=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )

                # =========================================
                # STEP 3: Statistical Data Collection
                # =========================================
                print(f"  > Step 3: Collecting Statistics ({NUM_RUNS} runs fast)...")
                for i in range(NUM_RUNS):
                    cmd_run = f"{binary} {size}"
                    res_run = subprocess.run(
                        cmd_run,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True
                    )

                    time_ms = get_time_from_output(res_run.stdout)
                    bw = get_bw_from_output(res_run.stdout)

                    if res_run.returncode != 0:
                        print(f"    ERROR: Run {i+1} exited with code {res_run.returncode}")

                    if time_ms == "N/A":
                        print(f"    Warning: Run {i+1} did not produce a time output.")

                    writer.writerow([
                        uvm_src,
                        name,
                        size,
                        f"{size_gb:.2f}",
                        i + 1,
                        time_ms,
                        bw,
                        faults,
                        res_run.returncode
                    ])
                    csvfile.flush()

                    if (i + 1) % 10 == 0 or (i + 1) == NUM_RUNS:
                        print(f"    Finished run {i+1}/{NUM_RUNS}")

        # Cleanup
        print("\nCleaning up temporary nsys files...")
        subprocess.run("rm -f temp_nsys_*", shell=True, stderr=subprocess.DEVNULL)

    print(f"\nSuite Finished! Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
