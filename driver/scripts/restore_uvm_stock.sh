#!/usr/bin/env bash
set -euo pipefail
KVER=$(uname -r)
MODDIR="/lib/modules/$KVER/kernel/nvidia-580-open"
if [ -f "$MODDIR/nvidia-uvm.ko.ORIG" ]; then
  echo "[restore] restoring ORIG nvidia-uvm.ko"
  sudo cp "$MODDIR/nvidia-uvm.ko.ORIG" "$MODDIR/nvidia-uvm.ko"
  sudo depmod -a
  sudo modprobe -r nvidia_uvm || true
  sudo modprobe nvidia_uvm
  echo "[OK] restored"
else
  echo "[ERROR] $MODDIR/nvidia-uvm.ko.ORIG not found"
  exit 1
fi
