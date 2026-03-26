#!/usr/bin/env bash
set -euo pipefail
KVER=$(uname -r)
MODDIR="/lib/modules/$KVER/kernel/nvidia-580-open"
echo "[install] installing nvidia-uvm.ko to: $MODDIR"
sudo cp ./nvidia-uvm.ko "$MODDIR/nvidia-uvm.ko"
sudo depmod -a
sudo modprobe -r nvidia_uvm || true
sudo modprobe nvidia_uvm
echo "[OK] installed + reloaded"
