#!/usr/bin/env python3
"""Gate E6 runner. tests/e5_runner.py is used unchanged: it already passes the order
file's `threshold` column to insmod and verifies it by read-back, and wraps
e4_runner (chunked --commit-every) over e3b_runner (reload, srcversion and parameter
read-back, ft_fast_verified, timestamp dmesg diff, stop checks, ring dumps). The only
E6 inputs are the order file (tests/e6_make_order.py), the output paths and the
--commit-msg. Bench timeouts (stencil 22 s, graphbfs 168 s) are e3b_runner's TMO, unchanged.
Usage: e6_runner.py --order ... --csv ... --out-dir ... --tables ... --commit-msg "Gate E6 ..." --commit-every 10
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import e5_runner  # noqa: E402  (applies the threshold-aware params/expected on import)

if __name__ == "__main__":
    sys.exit(e5_runner.E4.main())
