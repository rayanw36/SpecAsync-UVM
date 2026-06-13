#!/usr/bin/env bash
# gate_d_run.sh — Gate D re-baseline for one fault-heavy benchmark with the
# corrected pipeline. p0-p3 via runtime policy switch; p4 (oracle) via trace
# collect + reload. All runs under setarch -R (stable layout; required for the
# oracle's absolute-VA trace to match between collect and replay).
#
# Usage: sudo ./gate_d_run.sh <name> <binary> "<size_args>" <runs> <ko_path>
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
NAME="${1:?}"; BIN="${2:?}"; ARGS="${3:?}"; RUNS="${4:-8}"; KO="${5:?ko}"
DBG=/sys/kernel/debug/specasync; POL=/sys/module/nvidia_uvm/parameters/specasync_policy
OUT="$REPO/results/phaseB1/gate_d/$NAME"; mkdir -p "$OUT"
TIMES="$OUT/times.csv"; echo "policy,run,wall_s" > "$TIMES"
ANALYZE="$REPO/tests/gate_d_analyze.py"

time_run(){ /usr/bin/time -f "%e" setarch -R "$BIN" $ARGS >/dev/null 2>>/tmp/gd_t; tail -1 /tmp/gd_t; }

echo "############ Gate D: $NAME ($ARGS), $RUNS runs/policy ############"

# --- p0..p3 : runtime policy switch, no reload ---
for pol in 0 1 2 3; do
  echo "$pol" | sudo tee "$POL" >/dev/null
  echo 1 | sudo tee "$DBG/specasync_clear" >/dev/null
  setarch -R "$BIN" $ARGS >/dev/null 2>&1 || true   # warmup
  echo 1 | sudo tee "$DBG/specasync_clear" >/dev/null
  : > /tmp/gd_t
  for r in $(seq 1 "$RUNS"); do
    t=$(time_run); echo "$pol,$r,$t" >> "$TIMES"
  done
  sleep 0.5
  sudo cat "$DBG/specasync_log" > "$OUT/p${pol}_batch.bin"
  python3 "$ANALYZE" "$OUT/p${pol}_batch.bin" "$NAME p$pol"
done

# --- p4 : oracle (collect trace under policy 0, replay under policy 4) ---
TRACE="$OUT/oracle_trace.bin"
echo "[oracle] collect trace (policy=0, trace_faults=1)"
sudo rmmod nvidia_uvm
sudo insmod "$KO" specasync_policy=0 specasync_log_enabled=1 specasync_trace_faults=1
setarch -R "$BIN" $ARGS >/dev/null 2>&1 || true
sleep 0.5
sudo cat "$DBG/specasync_fault_trace" > "$TRACE"
echo "[oracle] trace entries: $(( $(stat -c%s "$TRACE")/8 ))"
echo "[oracle] reload policy=4 with trace"
sudo rmmod nvidia_uvm
sudo insmod "$KO" specasync_policy=4 specasync_log_enabled=1 specasync_oracle_trace_path="$TRACE"
echo 1 | sudo tee "$DBG/specasync_clear" >/dev/null
: > /tmp/gd_t
for r in $(seq 1 "$RUNS"); do
  t=$(time_run); echo "4,$r,$t" >> "$TIMES"
done
sleep 0.5
sudo cat "$DBG/specasync_log" > "$OUT/p4_batch.bin"
python3 "$ANALYZE" "$OUT/p4_batch.bin" "$NAME p4(oracle)"

# restore inactive specasync module, no trace
sudo rmmod nvidia_uvm
sudo insmod "$KO" specasync_policy=0 specasync_log_enabled=1
echo "[gate_d] wall-time medians (s):"
python3 - "$TIMES" <<'PY'
import csv,sys,statistics as st
rows=list(csv.DictReader(open(sys.argv[1])))
by={}
for r in rows: by.setdefault(int(r['policy']),[]).append(float(r['wall_s']))
b=st.median(by[0]) if by.get(0) else float('nan')
for p in sorted(by):
    m=st.median(by[p]); d=100*(m-b)/b if b else 0
    print(f"  p{p}: median={m:.3f}s  Δvs p0={d:+.1f}%  (n={len(by[p])})")
PY
