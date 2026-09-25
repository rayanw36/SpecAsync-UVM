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

def main():
    """--commit-every N: run the unchanged E3b main loop in chunks of N rows
    (its --through option); it commits the CSV at the end of every chunk, so
    rows are committed every N runs. Returns E3b's exit code (3 = stop)."""
    argv = sys.argv[1:]
    every = 0
    if "--commit-every" in argv:
        k = argv.index("--commit-every")
        every = int(argv[k + 1])
        del argv[k:k + 2]
    if not every:
        sys.argv = [sys.argv[0]] + argv
        return E.main()
    import csv
    order = argv[argv.index("--order") + 1]
    n = len(list(csv.DictReader(open(order))))
    for through in range(every, n + every, every):
        sys.argv = [sys.argv[0]] + argv + ["--through", str(min(through, n))]
        rc = E.main()
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
