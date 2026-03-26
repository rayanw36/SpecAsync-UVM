import subprocess
import os

# === Debug Configuration ===
binary = "./bench_stencil"
size = 24000
debug_file = "raw_nsys_output.txt"
# ===========================

print(f"--- Starting Nsight Systems Debug Run ---")
print(f"Target: Stencil Size {size}")
print(f"Goal: Capture raw text output to analyze output format.")

# Command: Run nsys and force it to print the summary stats to stdout.
# We do NOT define an --output file, which forces nsys to dump text to the terminal.
cmd_nsys = (
                f"nsys profile --stats=true --trace=cuda "
                f"--cuda-um-gpu-page-faults=true "
                f"--output=temp_fault_check --force-overwrite=true "
                f"{binary} {size}"
            )

print(f"\nExecuting command:\n{cmd_nsys}\n")
print("Running benchmark... (this might take a moment)")

try:
    # Run command and capture combined stdout/stderr
    # We use shell=True to handle the sudo command correctly
    result = subprocess.run(cmd_nsys, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output = result.stdout

    # Save the exact raw output to a text file
    with open(debug_file, "w") as f:
        f.write(output)

    print(f"\n--- Debug Run Complete ---")
    print(f"SUCCESS: Raw output saved to '{debug_file}'")
    print("========================================================")
    print("PLEASE UPLOAD OR PASTE THE CONTENTS OF THIS FILE.")
    print("========================================================")

except Exception as e:
    print(f"\nERROR during debug run: {e}")
