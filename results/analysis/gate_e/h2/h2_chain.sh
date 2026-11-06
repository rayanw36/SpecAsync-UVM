#!/bin/bash
# Gate H2 timed chain: smoke -> sweep as ONE unit (systemd-run --user --unit=h2 bash <this file>), halting on the first failure.
set -u
cd "$(dirname "$0")/../../../.." || exit 9
stamp() { echo "$(date +%FT%T) $*"; }
stamp "chain start pid $$ cgroup $(cat /proc/self/cgroup)"
for mode in smoke sweep; do
  stamp "orchestrate $mode"; python3 tests/h2_orchestrate.py "$mode"; rc=$?; stamp "orchestrate $mode exit $rc"
  if [ $rc -ne 0 ]; then echo "$(date +%FT%T) chain halted: orchestrate $mode exit $rc" >> results/analysis/gate_e/h2/CHAIN_STOP; exit $rc; fi
done
stamp "CHAIN COMPLETE"
