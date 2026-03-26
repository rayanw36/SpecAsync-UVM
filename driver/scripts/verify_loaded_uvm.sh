#!/usr/bin/env bash
set -euo pipefail
echo "[verify] uname -r: $(uname -r)"
echo "[verify] loaded module filename:"
modinfo nvidia_uvm | egrep "filename|vermagic|srcversion" || true
echo "[verify] /sys/module srcversion:"
if [ -f /sys/module/nvidia_uvm/srcversion ]; then
  cat /sys/module/nvidia_uvm/srcversion
else
  echo "nvidia_uvm not loaded"
fi
