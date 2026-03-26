import subprocess
import os

# === Debug Configuration ===
# We target Stencil because it is the hardest for the driver to pre-migrate.
# If this shows 0 faults, then the driver is definitely pre-migrating everything.
binary = "./bench_stencil"
size = 24000
debug_file = "raw_nsys_root_output.txt"
# ===========================

print(f"--- Starting Root Nsight Systems Debug Run ---")
print(f"Target: Stencil Size {size}")
print(f"Goal: Capture raw text output running as ROOT.")

# Command: Run nsys directly (we will run this python script with sudo)
# We force output to stdout so we can capture it.
cmd_nsys = (
    f"nsys profile --stats=true "
    f"--trace=cuda "
    f"--cuda-um-gpu-page-faults=true "
    f"{binary} {size}"
)

print(f"\nExecuting command:\n{cmd_nsys}\n")
print("Running benchmark as root... (this might take a moment)")

try:
    # Run command and capture combined stdout/stderr
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
