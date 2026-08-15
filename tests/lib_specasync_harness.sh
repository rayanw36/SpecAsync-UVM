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

# ---- per-run free-memory logging -----------------------------------------
# Added after HOST_MEMORY_LEAK_5070TI.md characterized a ~230-250MB/reload-
# cycle host memory leak (unaccounted pool, reproduces on the stock 595.84
# driver -- not a SpecAsync defect, but a run-order-correlated confound for
# every interleaved gate on this platform). Standing addition: every harness
# that sources this library now logs MemAvailable before/after each run, for
# free, the same way dmesg_delta already is.
mem_available_kb() {
    if [ "$DRY_RUN" = "1" ]; then
        echo 0
        return
    fi
    awk '/^MemAvailable:/ {print $2}' /proc/meminfo
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
    local header="run_order_idx,timestamp_iso8601,config,bench,size,rep_in_cell,wall_s,srcversion,dmesg_delta,mem_avail_before_kb,mem_avail_after_kb"
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
    local ts wall srcv ddelta mem_before mem_after
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    srcv=$(current_srcversion)
    mem_before=$(mem_available_kb)

    if [ "$DRY_RUN" = "1" ]; then
        wall="0.000000"
        ddelta=0
        mem_after=0
        harness_log "[dry-run] run_order=$RUN_ORDER_IDX cfg=$cfg bench=$bench size=$size rep=$rep bin=$bin args=$args"
    else
        dmesg_mark
        [ -x "$bin" ] || harness_die "benchmark binary not found or not executable: $bin"
        wall=$({ /usr/bin/time -f "%e" setarch -R "$bin" $args >/dev/null; } 2>&1 | tail -1)
        ddelta=$(dmesg_delta_count)
        mem_after=$(mem_available_kb)
        harness_log "run_order=$RUN_ORDER_IDX cfg=$cfg bench=$bench size=$size rep=$rep wall=${wall}s dmesg_delta=$ddelta mem_avail=${mem_after}kB"
    fi

    local row="$RUN_ORDER_IDX,$ts,$cfg,$bench,$size,$rep,$wall,$srcv,$ddelta,$mem_before,$mem_after"
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

# ---- in-run memory watchdog ----------------------------------------------
# Added after Gate B9 Task 1(c): the between-runs check_memory_or_abort
# pattern above cannot catch a memory spike that happens *during* a run --
# an nsys UM-fault-tracing pass on the 5070 Ti OOM-killed the benchmark
# process mid-run (host anon-rss 17.1GB + nsys's own multi-GB sqlite/trace
# buffer, invisible to a guard that only samples between runs). This is a
# standing fix: any harness that launches a memory-hungry foreground command
# under oversubscription should route it through run_with_memory_watchdog
# instead of a bare invocation.
#
# SECOND INCIDENT, same gate, right after the first: the watchdog fired
# correctly (killed the runaway process, marker file proves it, no kernel
# OOM-killer entry) -- but the CALLING script's own incident-reporting code
# went silent immediately after and the whole script exited without ever
# writing its planned log lines or CSV row. Root cause, reconstructed:
# MemAvailable kept falling for ~16s *after* the kill signal (the killed
# process's ~18GB UM allocation takes real wall-clock time for the driver to
# tear down and reclaim), and the original abort-path code -- both inside
# this function (`harness_log "$(cat "$marker_file")"`) and in the caller
# (`$(cat ...)`, `$(basename ...)` inside harness_log, `$(mem_available_kb)`
# which itself forks awk) -- forked a subprocess for every one of those
# calls, right in that post-kill window when a fork can itself fail. A
# failed command substitution under `set -e` (inherited from this file)
# terminates the script immediately, silently, before anything flushes.
#
# Fix, applied here as a standing library change so every future caller
# inherits it for free: NOTHING in the poll loop or the fire branch below
# forks. MemAvailable is read with a plain `read` loop over /proc/meminfo
# (no awk); the marker is written with `printf` to a fd opened ONCE before
# the run starts (no `> file` reopen at fire time, no command substitution);
# `kill` and `wait` are bash builtins. Pair with harness_log_nofork() and
# mem_watchdog_read_marker() below for the same guarantee in caller code.
#
# run_with_memory_watchdog <floor_kb> <marker_file> -- <command...>
#   Launches <command...> in its own process group (setsid), polls
#   MemAvailable every 1s while it runs, and if MemAvailable drops below
#   <floor_kb>, kills the whole process group immediately and writes a
#   fixed-format line ("WATCHDOG floor_kb=<N> avail_kb=<N> pgid=<pid>") to
#   <marker_file>. Returns the command's exit code, or 137 (matching a
#   SIGKILL exit convention) if the watchdog fired.
#
#   IMPORTANT: <marker_file> is now pre-created (truncated to empty) at the
#   start of EVERY call, whether or not the watchdog fires -- so it always
#   exists afterward. Do NOT test `[ -f "$marker_file" ]` to detect a fire
#   (always true); check this function's RETURN CODE (137) instead, or test
#   `[ -s "$marker_file" ]` (non-empty) if you need the file check too.
#
# Floor guidance: 6 GiB (this project's standing abort floor) for ordinary
# benchmark runs; use a higher floor (e.g. 10 GiB) for nsys or other tools
# that must flush a large buffer to disk at teardown, since the flush itself
# needs headroom the bare workload wouldn't.
run_with_memory_watchdog() {
    local floor_kb="$1" marker_file="$2"
    shift 2
    if [ "$1" = "--" ]; then shift; fi

    rm -f "$marker_file"

    if [ "$DRY_RUN" = "1" ]; then
        harness_log "[dry-run] run_with_memory_watchdog floor_kb=$floor_kb marker=$marker_file cmd=$*"
        return 0
    fi

    # Pre-open the marker fd now, before the run starts -- see incident note
    # above. Never reopen or otherwise touch marker_file by path again.
    exec {__wd_fd}>"$marker_file"

    setsid "$@" &
    local cmd_pid=$!

    (
        local avail_kb key val unit
        while kill -0 "$cmd_pid" 2>/dev/null; do
            avail_kb=""
            while IFS=': ' read -r key val unit; do
                if [ "$key" = "MemAvailable" ]; then
                    avail_kb="$val"
                    break
                fi
            done < /proc/meminfo
            if [ -n "$avail_kb" ] && [ "$avail_kb" -lt "$floor_kb" ]; then
                printf 'WATCHDOG floor_kb=%s avail_kb=%s pgid=%s\n' \
                    "$floor_kb" "$avail_kb" "$cmd_pid" >&"$__wd_fd"
                kill -9 -- "-$cmd_pid" 2>/dev/null
                break
            fi
            sleep 1
        done
    ) &
    local watchdog_pid=$!

    # Save/restore errexit around `wait` by its PRIOR state, not
    # unconditionally -- an unconditional `set -e` here previously clobbered
    # a caller's own `set +e ... set -e` wrapper the instant this function
    # returned a non-zero (137) status, killing the caller's script before
    # it could even capture $? (reproduced with an artificially high floor
    # and zero real memory pressure -- this was a set -e scoping bug, not
    # the fork-under-pressure failure it first looked like).
    local __wd_errexit_was_set=0
    case $- in *e*) __wd_errexit_was_set=1 ;; esac

    local exit_code
    set +e
    wait "$cmd_pid"
    exit_code=$?
    [ "$__wd_errexit_was_set" = 1 ] && set -e

    kill "$watchdog_pid" 2>/dev/null || true
    wait "$watchdog_pid" 2>/dev/null || true

    exec {__wd_fd}>&-

    if [ -s "$marker_file" ]; then
        return 137
    fi
    return "$exit_code"
}

# ---- fork-free helpers for abort-path code in CALLING scripts -----------
# Use these instead of harness_log / $(...) / mem_available_kb inside any
# code that runs after run_with_memory_watchdog reports a fire (return code
# 137). See that function's header for why: a fork right after a watchdog
# kill can itself fail while the killed process's memory is still being
# reclaimed, silently aborting the very code meant to report the incident.

# harness_log_nofork <message> -- same shape as harness_log, but the
# timestamp comes from printf's builtin %(...)T strftime (bash >= 4.2), not
# `date`, and there is no $(basename ...) lookup -- so it never forks.
harness_log_nofork() {
    printf '[abort %(%H:%M:%S)T] %s\n' -1 "$*" >&2
}

# mem_watchdog_read_marker <marker_file> <floor_var> <avail_var> <pgid_var>
# Fork-free parse of a marker file written by run_with_memory_watchdog into
# the three named variables (via `read`/`printf -v`, no command
# substitution, no subshell -- a here-string does not fork in bash).
mem_watchdog_read_marker() {
    local marker="$1" _floor_var="$2" _avail_var="$3" _pgid_var="$4"
    local line
    read -r line < "$marker"
    local -a parts
    read -r -a parts <<< "$line"
    local part
    for part in "${parts[@]}"; do
        case "$part" in
            floor_kb=*) printf -v "$_floor_var" '%s' "${part#floor_kb=}" ;;
            avail_kb=*) printf -v "$_avail_var" '%s' "${part#avail_kb=}" ;;
            pgid=*)     printf -v "$_pgid_var" '%s' "${part#pgid=}" ;;
        esac
    done
}
