#!/usr/bin/env bash
# finish_p4.sh — re-parse all p4 raw bins with the CORRECT parser CLI, then run analysis.
# Safe to run only AFTER the oracle sweep has finished (SWEEP_DONE).
set -uo pipefail
HOME_DIR=/home/ubuntu/SpecAsync-UVM
PARSE="$HOME_DIR/benchmarks/tools/specasync_parse.py"
P4="$HOME_DIR/results/p4_d0"

echo "[finish_p4] Re-parsing all p4 raw bins ..."
for batch in "$P4"/*/*/raw_batch.bin; do
    [[ -s "$batch" ]] || continue
    dir="$(dirname "$batch")"
    work="$dir/raw_worker.bin"
    if sudo python3 "$PARSE" "$batch" --work-log "$work" --out-dir "$dir" >/dev/null 2>&1; then
        echo "  PARSED $(basename "$(dirname "$dir")")/$(basename "$dir") -> $(wc -l < "$dir/batch_records.csv") batch rows"
    else
        echo "  FAIL   $dir"
    fi
done

echo "[finish_p4] Running analysis ..."
python3 "$HOME_DIR/benchmarks/tools/analyze_phaseB.py"
python3 "$HOME_DIR/benchmarks/tools/cost_benefit.py"
echo "[finish_p4] DONE"
