#!/usr/bin/env bash
# watch_progress.sh — show per-benchmark p4 parse + analysis progress.
# Usage: bash watch_progress.sh        (one snapshot)
#        watch -n2 bash watch_progress.sh   (live)
H=/home/ubuntu/SpecAsync-UVM
P4="$H/results/p4_d0"
PH="$H/results/phaseB"

printf "%-34s %8s %8s %8s\n" "BENCHMARK/SIZE" "TIMING" "BATCH" "WORKER"
printf '%.0s-' {1..62}; echo
for dir in "$P4"/*/*/; do
    [[ -d "$dir" ]] || continue
    label="$(basename "$(dirname "$dir")")/$(basename "$dir")"
    t=$([[ -s "$dir/timing_raw.csv" ]] && echo "$(($(wc -l < "$dir/timing_raw.csv")-1))" || echo "-")
    b=$([[ -s "$dir/batch_records.csv" ]] && echo "$(($(wc -l < "$dir/batch_records.csv")-1))" || echo "-")
    w=$([[ -s "$dir/work_records.csv" ]] && echo "$(($(wc -l < "$dir/work_records.csv")-1))" || echo "-")
    printf "%-34s %8s %8s %8s\n" "$label" "$t" "$b" "$w"
done

echo
echo "Analysis artifacts:"
for f in "$PH/SUMMARY.md" "$PH/phaseB_timing.csv" "$PH/phaseB_telemetry.csv" "$H/results/summary/cost_benefit.md"; do
    if [[ -f "$f" ]]; then
        printf "  [x] %-46s (%s)\n" "${f#$H/}" "$(stat -c '%y' "$f" | cut -d. -f1)"
    else
        printf "  [ ] %-46s (missing)\n" "${f#$H/}"
    fi
done
