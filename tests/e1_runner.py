#!/usr/bin/env python3
"""Gate E1 runner: tests/e09b_runner.py's execution and stop-condition logic,
unchanged, with the arm table replaced by E1's arms:

  C0   policy 0, depth 0, prefetch on
  C7-L policy 6, depth 1, prefetch on, specasync_ft_lookahead=L, fresh table

All arms specasync_log_enabled=1. Same CLI as e09b_runner.py. Commit
messages are prefixed "Gate E1" instead of "Gate E0.9b"."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import e09b_runner as R  # noqa: E402


def arm_params(arm, L, table):
    common = ["specasync_log_enabled=1", "uvm_perf_prefetch_enable=1"]
    if arm == "C0":
        return common + ["specasync_policy=0", "specasync_offload_depth=0"]
    if arm == "C7":
        return common + ["specasync_policy=6", "specasync_offload_depth=1",
                         f"specasync_ft_lookahead={L}", f"specasync_ft_table_path={table}"]
    raise ValueError(arm)


def expected_sysparams(arm, L):
    if arm == "C0":
        return {"specasync_policy": "0", "specasync_offload_depth": "0", "uvm_perf_prefetch_enable": "1"}
    if arm == "C7":
        return {"specasync_policy": "6", "specasync_offload_depth": "1", "uvm_perf_prefetch_enable": "1",
                "specasync_ft_lookahead": str(L)}
    raise ValueError(arm)


_git_commit = R.git_commit
R.arm_params = arm_params
R.expected_sysparams = expected_sysparams
R.git_commit = lambda paths, msg: _git_commit(paths, msg.replace("Gate E0.9b", "Gate E1", 1))

if __name__ == "__main__":
    sys.exit(R.main())
