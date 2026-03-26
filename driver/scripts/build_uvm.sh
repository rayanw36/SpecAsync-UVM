#!/usr/bin/env bash
set -euo pipefail
make modules -j"$(nproc)"
echo "[OK] build complete"
