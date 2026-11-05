#!/bin/bash
# Gate H1 chain: smoke -> sweep as ONE unit, halting on the first failure. Started once with: systemd-run --user --unit=h1-chain bash <this file>  (never restarted, never run twice)
set -u
cd "$(dirname "$0")/../../../.." || exit 9
stamp() { echo "$(date +%FT%T) $*"; }
stamp "chain start pid $$ cgroup $(cat /proc/self/cgroup)"
for mode in smoke sweep; do
  stamp "orchestrate $mode"
  python3 tests/h1_orchestrate.py "$mode"
  rc=$?
  stamp "orchestrate $mode exit $rc"
  if [ $rc -ne 0 ]; then echo "$(date +%FT%T) chain halted: orchestrate $mode exit $rc" >> results/analysis/gate_e/h1/CHAIN_STOP; stamp "CHAIN HALTED"; exit $rc; fi
done
stamp "CHAIN COMPLETE"
