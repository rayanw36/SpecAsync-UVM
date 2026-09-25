#!/usr/bin/env python3
"""Gate E4 runner: tests/e3b_runner.py unchanged (timestamp dmesg diff, the
extended stop pattern, parameter read-back, cas_giveup / region_invalid
stops, batch+decomp ring dumps), plus one E4 stop condition:
specasync_ft_fast_verified != 1 on any fast = 1 load. Same CLI."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import e3b_runner as E  # noqa: E402
R = E.R

_load = E.load


def load(row, table, out_dir, label):
    srcv, info = _load(row, table, out_dir, label)
    if row["module"] == "new" and row["fast"] == "1" and info.get("ft_fast_verified") != "1":
        raise R.Stop(f"specasync_ft_fast_verified = {info.get('ft_fast_verified')} (!= 1) on a fast = 1 load")
    return srcv, info


E.load = load

if __name__ == "__main__":
    sys.exit(E.main())
