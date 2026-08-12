#!/usr/bin/env bash
# lib_specasync_harness.sh — shared functions for the T1-T4 GPU harnesses
# (Task 1.3). Sourced, not executed directly.
#
# Every harness that sources this library gets, for free:
#   - a DRY_RUN=1 mode that exercises argument parsing, output paths, CSV
#     headers, and telemetry dump logic without touching insmod/rmmod or
#     running any GPU binary (Task 1.3's explicit requirement)
#   - the full per-run telemetry columns the original gate3_favorable_run.sh
#     omitted: run-order index, wall-clock timestamp, config, benchmark,
#     size, module srcversion, and a dmesg delta count
#   - a uniform reload-based config switch (see PREREGISTRATION.md's
#     correction: uvm_perf_prefetch_enable and specasync_oracle_trace_path
#     are read-only after module load, so every config switch reloads,
#     not just the ones that "need" to)
#
# DRY_RUN=1 is honored by every function below; real GPU/module operations
# are skipped and replaced with clearly-labelled placeholder values so the
# harness's plumbing can be verified end-to-end before the module exists.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DBGFS="/sys/kernel/debug/specasync"
POL_PARAM=/sys/module/nvidia_uvm/parameters/specasync_policy
DEPTH_PARAM=/sys/module/nvidia_uvm/parameters/specasync_offload_depth

DRY_RUN="${DRY_RUN:-0}"
RUN_ORDER_IDX=0
DMESG_MARK_FILE="$(mktemp -u)"

# Logging goes to stderr, deliberately -- several functions below (e.g.
# collect_oracle_trace) return their result via stdout command substitution,
# and a log line on stdout would silently corrupt the captured value.
harness_log() { echo "[$(basename "${BASH_SOURCE[1]:-harness}") $(date '+%H:%M:%S')] $*" >&2; }
harness_die() { echo "[ERROR] $*" >&2; exit 1; }

# ---- srcversion -------------------------------------------------------
current_srcversion() {
    if [ "$DRY_RUN" = "1" ]; then
        echo "DRYRUN0000000000000000"
        return
    fi
    if [ -f /sys/module/nvidia_uvm/srcversion ]; then
        cat /sys/module/nvidia_uvm/srcversion
    else
        echo "UNKNOWN"
    fi
}

# ---- dmesg delta tracking ----------------------------------------------
# Call dmesg_mark before a run, dmesg_delta_count after, to get the number
# of new kernel-log lines emitted during that run (warnings/errors or not --
# counted here; classified by the caller if it cares).
dmesg_mark() {
    if [ "$DRY_RUN" = "1" ]; then
        echo 0 > "$DMESG_MARK_FILE.count"
        return
    fi
    sudo -n dmesg | wc -l > "$DMESG_MARK_FILE.count"
}

dmesg_delta_count() {
    if [ "$DRY_RUN" = "1" ]; then
        echo 0
        return
    fi
    local before after
    before=$(cat "$DMESG_MARK_FILE.count" 2>/dev/null || echo 0)
    after=$(sudo -n dmesg | wc -l)
    echo $(( after - before ))
}

dmesg_delta_text() {
    if [ "$DRY_RUN" = "1" ]; then
        echo ""
        return
    fi
    local n
    n=$(dmesg_delta_count)
    if [ "$n" -gt 0 ]; then
        sudo -n dmesg | tail -n "$n"
    fi
}

# ---- module reload ------------------------------------------------------
# reload_module <ko_path> <policy> <depth> <prefetch> [oracle_trace_path]
#
# Every config switch reloads (see file header note) -- this is uniform
# across C0-C3 / p0-p2, not special-cased per config, per
# PREREGISTRATION.md's corrected mechanism.
reload_module() {
    local ko="$1" policy="$2" depth="$3" prefetch="$4" trace="${5:-}"
    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] reload_module ko=$ko policy=$policy depth=$depth prefetch=$prefetch trace=${trace:-none}"
        return
    fi
    [ -f "$ko" ] || harness_die "module not found: $ko (Phase 2 must build it first)"
    dmesg_mark
    sudo rmmod nvidia_uvm 2>/dev/null || true
    local extra="specasync_policy=$policy specasync_offload_depth=$depth uvm_perf_prefetch_enable=$prefetch specasync_log_enabled=1"
    if [ -n "$trace" ]; then
        extra="$extra specasync_oracle_trace_path=$trace"
    fi
    sudo insmod "$ko" $extra
    sleep 0.3
    local d
    d=$(dmesg_delta_count)
    if [ "$d" -gt 0 ]; then
        harness_log "reload: $d new dmesg line(s) -- logged, not necessarily an error"
    fi
}

# ---- live param switch (only valid for specasync_policy/offload_depth) --
# Retained for harnesses that don't need prefetch/oracle switching (T4) and
# can therefore avoid a reload's settle cost. Do NOT use this for
# prefetch_enable or oracle_trace_path -- see PREREGISTRATION.md.
live_switch_policy_depth() {
    local policy="$1" depth="$2"
    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] live_switch policy=$policy depth=$depth"
        return
    fi
    echo "$policy" | sudo tee "$POL_PARAM" >/dev/null
    echo "$depth"  | sudo tee "$DEPTH_PARAM" >/dev/null
}

# ---- CSV init with the full required column set -------------------------
# csv_init <path> <extra_columns_csv_or_empty>
csv_init() {
    local path="$1" extra="${2:-}"
    mkdir -p "$(dirname "$path")"
    local header="run_order_idx,timestamp_iso8601,config,bench,size,rep_in_cell,wall_s,srcversion,dmesg_delta"
    if [ -n "$extra" ]; then
        header="$header,$extra"
    fi
    echo "$header" > "$path"
}

# ---- timed run with full telemetry columns -------------------------------
# time_run <csv_path> <bin> <args> <config> <bench> <size> <rep_in_cell> [extra_value]
time_run() {
    local csv="$1" bin="$2" args="$3" cfg="$4" bench="$5" size="$6" rep="$7" extra="${8:-}"
    RUN_ORDER_IDX=$((RUN_ORDER_IDX + 1))
    local ts wall srcv ddelta
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    srcv=$(current_srcversion)

    if [ "$DRY_RUN" = "1" ]; then
        wall="0.000000"
        ddelta=0
        harness_log "[dry-run] run_order=$RUN_ORDER_IDX cfg=$cfg bench=$bench size=$size rep=$rep bin=$bin args=$args"
    else
        dmesg_mark
        [ -x "$bin" ] || harness_die "benchmark binary not found or not executable: $bin"
        wall=$({ /usr/bin/time -f "%e" setarch -R "$bin" $args >/dev/null; } 2>&1 | tail -1)
        ddelta=$(dmesg_delta_count)
        harness_log "run_order=$RUN_ORDER_IDX cfg=$cfg bench=$bench size=$size rep=$rep wall=${wall}s dmesg_delta=$ddelta"
    fi

    local row="$RUN_ORDER_IDX,$ts,$cfg,$bench,$size,$rep,$wall,$srcv,$ddelta"
    if [ -n "$extra" ]; then
        row="$row,$extra"
    fi
    echo "$row" >> "$csv"
}

# ---- telemetry ring dump --------------------------------------------------
# dump_ring <debugfs_file> <out_path>
dump_ring() {
    local dbg_file="$1" out="$2"
    mkdir -p "$(dirname "$out")"
    if [ "$DRY_RUN" = "1" ]; then
        printf '' > "$out"
        harness_log "[dry-run] dump_ring $dbg_file -> $out (0 bytes, placeholder)"
        return
    fi
    sudo cat "$dbg_file" > "$out" 2>/dev/null || harness_log "WARNING: could not read $dbg_file (module loaded? debugfs mounted?)"
}

clear_ring() {
    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] clear_ring"
        return
    fi
    echo 1 | sudo tee "$DBGFS/specasync_clear" >/dev/null 2>&1 || true
}
