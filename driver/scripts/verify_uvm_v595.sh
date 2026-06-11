#!/usr/bin/env bash
# Verify the SpecAsync nvidia-uvm module is loaded correctly
set -euo pipefail

SPECASYNC_SRCVER="EF55E64556352EDABEBE583"
STOCK_SRCVER="85A79790636BBD99BA3E43B"

LOADED=$(cat /sys/module/nvidia_uvm/srcversion 2>/dev/null || echo "NOT_LOADED")
echo "Loaded srcversion : $LOADED"
echo "SpecAsync expected: $SPECASYNC_SRCVER"
echo "Stock srcversion  : $STOCK_SRCVER"

if [ "$LOADED" = "$SPECASYNC_SRCVER" ]; then
    echo "STATUS: SpecAsync module loaded OK"
elif [ "$LOADED" = "$STOCK_SRCVER" ]; then
    echo "STATUS: STOCK module is loaded (not SpecAsync)"
    exit 1
else
    echo "STATUS: Unknown srcversion"
    exit 1
fi

echo "---"
echo "debugfs files:"
ls /sys/kernel/debug/specasync* /sys/kernel/debug/specasync/ 2>/dev/null || echo "  MISSING"

echo "---"
echo "Recent dmesg:"
dmesg | tail -20 | grep -iE "specasync|uvm" | head -10 || true
