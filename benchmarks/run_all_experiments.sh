#!/usr/bin/env bash
# run_all_experiments.sh — Phase 2 full experiment sweep for SpecAsync-UVM
#
# Assumed environment (GPU box after git lfs pull + build + module load):
#   - Modified nvidia_uvm module loaded (verify via SRCVERSION check below)
#   - Benchmarks compiled in this directory: bench_stream bench_sgemm
#     bench_stencil bench_cufft stencil_oversub/bench_stencil_oversub
#     graph_bfs/bench_graph_bfs
#   - Python 3 with specasync_parse.py and cost_benefit.py in tools/
#   - debugfs mounted at /sys/kernel/debug
#   - Script run as root (or with CAP_DAC_READ_SEARCH for debugfs)
#
# Usage:
#   sudo bash run_all_experiments.sh [--force] [--dry-run] [--policy LIST]
#
# Options:
#   --force       Re-run and overwrite existing result directories
#   --dry-run     Print what would be run without executing benchmarks
#   --policy LIST Comma-separated subset of policies, e.g. --policy 0,1,2
#
# Result layout:
#   results/p{policy}_d{depth}/{benchmark}/{size}/
#     raw_batch.bin          (binary dump of specasync_log)
#     raw_worker.bin         (binary dump of specasync_worker_log)
#     batch_records.csv      (parsed by specasync_parse.py)
#     work_records.csv       (parsed by specasync_parse.py)
#     timing_raw.csv         (wall-time measurements, 50 trials)
#   results/run_<timestamp>.log   (full run log via tee)

set -euo pipefail

# ── Configurable paths ────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RESULTS_DIR="$REPO_ROOT/results"
TOOLS_DIR="$SCRIPT_DIR/tools"
DEBUGFS_BASE="/sys/kernel/debug"
BATCH_LOG="$DEBUGFS_BASE/specasync_log"
WORKER_LOG="$DEBUGFS_BASE/specasync_worker_log"
CLEAR_LOG="$DEBUGFS_BASE/specasync_clear"
MODULE_PARAM_BASE="/sys/module/nvidia_uvm/parameters"

# Expected srcversion of the SpecAsync-UVM module (Phase B: fill in after build)
# Run: cat /sys/module/nvidia_uvm/srcversion
# and paste the hash here so the pre-flight check works.
EXPECTED_SRCVERSION="${SPECASYNC_SRCVERSION:-}"   # override via env var

NUM_STAT_RUNS=20
WARMUP_RUNS=1

# ── Policy × depth matrix ─────────────────────────────────────────────────────
# policy: 0=disabled 1=adjacent 2=stride 3=markov   (4=oracle needs trace file)
# depth:  0=metadata-only 1=residency-prep
# Skip: (policy=0, depth=1) — nonsensical (disabled + residency offload)
# Phase B: depth=0 only for initial sweep; depth=1 after validation
declare -a POLICY_LIST=(0 1 2 3)
declare -a DEPTH_LIST=(0)

# ── Benchmark definitions ─────────────────────────────────────────────────────
# Format: "NAME:BINARY:SIZE1,SIZE2,SIZE3"
# T4-calibrated sizes (sm_75, 15 GiB VRAM, 14 GiB host RAM):
#   BFS log2=26 requires 8 GB host malloc — OOM; capped at 24.
#   Oversub uses balloon_mib=11264 to pin ~11 GiB VRAM leaving ~4 GiB usable;
#     25000→5 GB (1.25x), 28300→6.4 GB (1.6x), 32000→8.2 GB (2.05x) oversubscription.
declare -a BENCHMARKS=(
    "STREAM:./bench_stream:134217728,268435456,536870912"
    "SGEMM:./bench_sgemm:8192,16384,24000"
    "Stencil:./bench_stencil:8192,16384,24000"
    "cuFFT:./bench_cufft:67108864,134217728,268435456"
    "Stencil_OvSub:./stencil_oversub/bench_stencil_oversub:25000 20 11264,28300 20 11264,32000 20 11264"
    "GraphBFS:./graph_bfs/bench_graph_bfs:22,23,24"
)

# ── Argument parsing ──────────────────────────────────────────────────────────
FORCE=0
DRY_RUN=0
CUSTOM_POLICIES=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)     FORCE=1 ;;
        --dry-run)   DRY_RUN=1 ;;
        --policy)    CUSTOM_POLICIES="$2"; shift ;;
        *)           echo "Unknown option: $1" >&2; exit 1 ;;
    esac
    shift
done

if [[ -n "$CUSTOM_POLICIES" ]]; then
    IFS=',' read -ra POLICY_LIST <<< "$CUSTOM_POLICIES"
fi

# ── Logging setup ─────────────────────────────────────────────────────────────
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
LOG_FILE="$RESULTS_DIR/run_${TIMESTAMP}.log"
mkdir -p "$RESULTS_DIR"

# Tee all output to log file from here on
exec > >(tee -a "$LOG_FILE") 2>&1

echo "============================================================"
echo " SpecAsync-UVM Phase 2 Experiment Run"
echo " Started: $(date)"
echo " Force: $FORCE  DryRun: $DRY_RUN"
echo " Log: $LOG_FILE"
echo "============================================================"

# ── Pre-flight checks ─────────────────────────────────────────────────────────
echo ""
echo "[preflight] Checking environment..."

# 1. Module must be loaded
if ! lsmod | grep -q nvidia_uvm; then
    echo "[FATAL] nvidia_uvm module is not loaded." >&2
    echo "        Run: sudo modprobe nvidia_uvm" >&2
    exit 1
fi
echo "[preflight] nvidia_uvm loaded: OK"

# 2. srcversion check (if EXPECTED_SRCVERSION is set)
ACTUAL_SRCVERSION="$(cat /sys/module/nvidia_uvm/srcversion 2>/dev/null || echo 'unknown')"
if [[ -n "$EXPECTED_SRCVERSION" ]]; then
    if [[ "$ACTUAL_SRCVERSION" != "$EXPECTED_SRCVERSION" ]]; then
        echo "[FATAL] srcversion mismatch!" >&2
        echo "  Expected: $EXPECTED_SRCVERSION" >&2
        echo "  Actual:   $ACTUAL_SRCVERSION" >&2
        echo "  You may be running the stock driver, not SpecAsync-UVM." >&2
        exit 1
    fi
    echo "[preflight] srcversion match: OK ($ACTUAL_SRCVERSION)"
else
    echo "[preflight] srcversion: $ACTUAL_SRCVERSION (set SPECASYNC_SRCVERSION to enforce)"
fi

# 3. debugfs paths
for F in "$BATCH_LOG" "$WORKER_LOG" "$CLEAR_LOG"; do
    if [[ ! -e "$F" ]]; then
        echo "[FATAL] debugfs path not found: $F" >&2
        echo "        Is debugfs mounted? Is the SpecAsync module loaded?" >&2
        exit 1
    fi
done
echo "[preflight] debugfs paths: OK"

# 4. Benchmark binaries
for entry in "${BENCHMARKS[@]}"; do
    IFS=':' read -r bname binary _ <<< "$entry"
    bin_path="$SCRIPT_DIR/$binary"
    if [[ ! -x "$bin_path" ]]; then
        echo "[WARN] Binary not found or not executable: $bin_path" >&2
        echo "       Run 'make' in benchmarks/ first." >&2
    fi
done
echo "[preflight] Binary check done (warnings above if any missing)"

# 5. Python tools
if ! python3 "$TOOLS_DIR/specasync_parse.py" --help &>/dev/null; then
    echo "[FATAL] specasync_parse.py not working." >&2
    exit 1
fi
echo "[preflight] Python tools: OK"

echo ""
echo "[preflight] All checks passed. Beginning sweep."

# ── Helper: set module parameters ─────────────────────────────────────────────
set_module_param() {
    local param="$1"
    local value="$2"
    local path="$MODULE_PARAM_BASE/$param"
    if [[ -w "$path" ]]; then
        echo "$value" > "$path"
    else
        echo "[WARN] Cannot write $path (run as root?)" >&2
    fi
}

# ── Helper: clear debugfs ring buffers ────────────────────────────────────────
clear_logs() {
    echo "1" > "$CLEAR_LOG" 2>/dev/null || true
}

# ── Helper: run one benchmark × size trial ────────────────────────────────────
# Returns nothing; writes timing_raw.csv row to $OUTCSV
OUTCSV=""
run_trial() {
    local binary="$1"
    local size="$2"
    local run_id="$3"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "  [dryrun] $binary $size (run $run_id)"
        return
    fi

    local output
    output="$(${binary} ${size} 2>/dev/null)" || output="ERROR"

    local time_ms
    time_ms="$(echo "$output" | grep -oP '(?<=\[RESULT\] Time: )\d+\.\d+' || echo 'N/A')"
    local bw
    bw="$(echo "$output" | grep -oP '(?<=Bandwidth: )\d+\.\d+' || echo 'N/A')"

    echo "$run_id,$time_ms,$bw" >> "$OUTCSV"
}

# ── Main sweep ────────────────────────────────────────────────────────────────
for policy in "${POLICY_LIST[@]}"; do
    for depth in "${DEPTH_LIST[@]}"; do
        # Skip: policy=0 + depth>0 is nonsensical
        if [[ "$policy" -eq 0 && "$depth" -gt 0 ]]; then
            continue
        fi

        CONFIG="p${policy}_d${depth}"
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo " Config: $CONFIG  (policy=$policy depth=$depth)"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        # Apply module parameters
        if [[ "$DRY_RUN" -eq 0 ]]; then
            set_module_param "specasync_policy"        "$policy"
            set_module_param "specasync_offload_depth" "$depth"
            set_module_param "specasync_log_enabled"   "1"
            echo "  Module params set: policy=$policy depth=$depth"
        fi

        for entry in "${BENCHMARKS[@]}"; do
            IFS=':' read -r bname binary sizes_str <<< "$entry"
            IFS=',' read -ra sizes <<< "$sizes_str"

            for size in "${sizes[@]}"; do
                # Sanitise size string for use as directory name (spaces → _)
                size_label="${size// /_}"
                OUTDIR="$RESULTS_DIR/$CONFIG/$bname/$size_label"

                # Idempotency: skip if done unless --force
                if [[ -d "$OUTDIR" && "$FORCE" -eq 0 ]]; then
                    if [[ -f "$OUTDIR/batch_records.csv" ]]; then
                        echo "  [skip] $bname/$size (exists; use --force to rerun)"
                        continue
                    fi
                fi

                mkdir -p "$OUTDIR"
                echo ""
                echo "  [$CONFIG] $bname size=$size"

                # Warmup runs (output discarded)
                if [[ "$DRY_RUN" -eq 0 ]]; then
                    echo "    Warmup ($WARMUP_RUNS run(s))..."
                    for _ in $(seq 1 "$WARMUP_RUNS"); do
                        "${SCRIPT_DIR}/$binary" "$size" &>/dev/null || true
                    done

                    # Clear logs right before timed runs
                    clear_logs
                fi

                # Timed runs
                OUTCSV="$OUTDIR/timing_raw.csv"
                echo "Run_ID,Time_ms,Bandwidth_GBs" > "$OUTCSV"

                echo "    Timing ($NUM_STAT_RUNS runs)..."
                for run_id in $(seq 1 "$NUM_STAT_RUNS"); do
                    run_trial "$SCRIPT_DIR/$binary" "$size" "$run_id"
                    if (( run_id % 10 == 0 )); then
                        echo "      ... run $run_id/$NUM_STAT_RUNS"
                    fi
                done

                # Dump debugfs logs
                if [[ "$DRY_RUN" -eq 0 ]]; then
                    cat "$BATCH_LOG"  > "$OUTDIR/raw_batch.bin"  2>/dev/null || \
                        echo "[WARN] Could not dump batch log" >&2
                    cat "$WORKER_LOG" > "$OUTDIR/raw_worker.bin" 2>/dev/null || \
                        echo "[WARN] Could not dump worker log" >&2

                    # Parse logs
                    python3 "$TOOLS_DIR/specasync_parse.py" \
                        "$OUTDIR/raw_batch.bin" \
                        --work-log "$OUTDIR/raw_worker.bin" \
                        --out-dir  "$OUTDIR" || \
                        echo "[WARN] Parser failed for $CONFIG/$bname/$size" >&2
                fi

                echo "    Done → $OUTDIR"
            done
        done
    done
done

# ── Post-processing ───────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Post-processing: cost-benefit analysis"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ "$DRY_RUN" -eq 0 ]]; then
    python3 "$TOOLS_DIR/cost_benefit.py" \
        --results-dir "$RESULTS_DIR" \
        --summary-dir "$RESULTS_DIR/summary" || \
        echo "[WARN] cost_benefit.py failed (non-fatal)" >&2
fi

echo ""
echo "============================================================"
echo " Run complete: $(date)"
echo " Results: $RESULTS_DIR"
echo " Log:     $LOG_FILE"
echo "============================================================"
