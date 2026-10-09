#!/bin/bash
# E7-T4 chain (Amendment 2): remaining smoke rows -> timeouts file -> sweep, as ONE unit; halts on the first failure.
# Started once by: systemd-run --user --unit=e7t4-sweep ... bash e7t4_chain.sh   (never restarted, never run twice)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE" || exit 9
export SPECASYNC_REPO="$(cd ../../.. && pwd)" T4_CAP_HOURS=4
stamp() { echo "$(date -u +%FT%TZ) $*"; }
stamp "chain start pid $$ ppid $PPID cgroup $(cat /proc/self/cgroup)"
for mode in smoke sweep; do
  stamp "orchestrate $mode"
  python3 e7t4_orchestrate.py "$mode" --start-file phase0_start_4.txt
  rc=$?
  stamp "orchestrate $mode exit $rc"
  if [ $rc -ne 0 ]; then
    mkdir -p raw; echo "$(date -u +%FT%TZ) chain halted: orchestrate $mode exit $rc" >> raw/CHAIN_STOP
    stamp "CHAIN HALTED (see raw/CHAIN_STOP, raw/*/STOP)"
    exit $rc
  fi
done
stamp "CHAIN COMPLETE"
