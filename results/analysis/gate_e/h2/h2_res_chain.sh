#!/bin/bash
# Gate H2 residency chain (systemd-run --user --unit=h2res bash <this file>).
set -u
cd "$(dirname "$0")/../../../.." || exit 9
stamp() { echo "$(date +%FT%T) $*"; }
stamp "residency chain start pid $$"
python3 tests/h2_residency.py --order results/analysis/gate_e/h2/h2_residency_order.csv --csv results/analysis/gate_e/h2/residency_summary.csv --out-dir results/analysis/gate_e/h2/residency --order-sha256 results/analysis/gate_e/h2/h2_order.sha256
rc=$?; stamp "residency exit $rc"
if [ $rc -ne 0 ]; then echo "$(date +%FT%T) residency halted exit $rc" >> results/analysis/gate_e/h2/CHAIN_STOP; fi
exit $rc
