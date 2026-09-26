#!/usr/bin/env python3
"""Gate E5 runner: tests/e4_runner.py (itself tests/e3b_runner.py plus the
ft_fast_verified stop) with one addition: the order file's `threshold`
column is passed as uvm_perf_prefetch_threshold at insmod and verified by
read-back from /sys/module/nvidia_uvm/parameters/ (a mismatch is a stop).
Same CLI as e4_runner.py, including --commit-every."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import e4_runner as E4  # noqa: E402
E = E4.E

_params, _expected = E.params, E.expected


def params(row, table):
    return _params(row, table) + [f"uvm_perf_prefetch_threshold={row['threshold']}"]


def expected(row):
    e = _expected(row)
    e["uvm_perf_prefetch_threshold"] = row["threshold"]
    return e


E.params, E.expected = params, expected

if __name__ == "__main__":
    sys.exit(E4.main())
