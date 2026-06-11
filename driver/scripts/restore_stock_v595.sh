#!/usr/bin/env bash
# Restore the stock nvidia-uvm module from backup
set -euo pipefail

BACKUP="$HOME/SpecAsync-UVM/driver/stock_backup/nvidia-uvm.ko.stock"
STOCK_PATH="/lib/modules/$(uname -r)/updates/dkms/nvidia-uvm.ko"
STOCK_SRCVER="85A79790636BBD99BA3E43B"

if [ ! -f "$BACKUP" ]; then
    echo "ERROR: backup not found at $BACKUP" >&2
    exit 1
fi

echo "[restore_stock] Stopping nvidia-persistenced..."
systemctl stop nvidia-persistenced 2>/dev/null || true

echo "[restore_stock] Unloading current nvidia_uvm..."
modprobe -r nvidia_uvm

echo "[restore_stock] Loading stock module..."
insmod "$BACKUP"

LOADED=$(cat /sys/module/nvidia_uvm/srcversion)
echo "[restore_stock] Loaded srcversion: $LOADED"
if [ "$LOADED" = "$STOCK_SRCVER" ]; then
    echo "[restore_stock] OK — stock module verified."
else
    echo "[restore_stock] WARNING: srcversion $LOADED != expected $STOCK_SRCVER" >&2
fi

systemctl start nvidia-persistenced 2>/dev/null || true
