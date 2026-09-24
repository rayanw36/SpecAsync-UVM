#!/usr/bin/env python3
"""Gate E0.7 Check 1/2 accuracy analysis.

Check 1: given a collected trace (collection-run fault order) and a
replay-order dump (replay-run actual fault order, logged by the new
specasync_replay_order ring), compute exact-next / windowed / set accuracy,
overall and by decile.

Check 2: given two plain-C1 traces of the same workload (no oracle, no
replay machinery at all), compute the same measures treating trace A as
"predictions" and trace B as "actual", to characterize hardware fault-order
nondeterminism independent of anything SpecAsync does.

The "predicted" sequence for Check 1 is NOT logged directly -- it is
derived from the collection trace via the proven, deterministic cursor
formula (see specasync_oracle_next_addr_n): call k's actual fault is
replay_order[k]; the prediction scored against it is trace[k % len(trace)],
for k = 1 .. N-1 (k=0 has no prior prediction). This script verifies that
derivation against the kernel's own oracle_correct/oracle_predictions
counters before reporting anything else.
"""
import sys
import numpy as np
from collections import Counter


def load_u64(path):
    return np.fromfile(path, dtype="<u8")


def decile_of(k, n):
    d = (k * 10) // n
    return min(d, 9)


def exact_next_accuracy(predicted, actual):
    """predicted, actual: same-length arrays; predicted[k] scored against actual[k]."""
    correct = predicted == actual
    return correct


def windowed_accuracy(predicted, actual, W):
    """For each k, does predicted[k] appear in actual[k : k+W]?"""
    n = len(actual)
    result = np.zeros(n, dtype=bool)
    window = Counter()
    # seed window with actual[0:W]
    right = min(W, n)
    for i in range(right):
        window[actual[i]] += 1
    for k in range(n):
        result[k] = window[predicted[k]] > 0
        # slide: remove actual[k] (leaving the window), add actual[k+W] if in range
        window[actual[k]] -= 1
        if window[actual[k]] == 0:
            del window[actual[k]]
        new_right = k + W
        if right == new_right and right < n:
            window[actual[right]] += 1
            right += 1
    return result


def set_accuracy(predicted, actual):
    """For each k, does predicted[k] appear anywhere in actual[k:]?"""
    n = len(actual)
    last_pos = {}
    for i in range(n - 1, -1, -1):
        if actual[i] not in last_pos:
            last_pos[actual[i]] = i
    result = np.zeros(n, dtype=bool)
    for k in range(n):
        lp = last_pos.get(predicted[k])
        result[k] = lp is not None and lp >= k
    return result


def report_by_decile(mask, n, label):
    print(f"  {label}: overall {mask.sum()}/{n} = {100*mask.sum()/n:.4f}%")
    for d in range(10):
        lo = (d * n) // 10
        hi = ((d + 1) * n) // 10
        sub = mask[lo:hi]
        tot = len(sub)
        print(f"    decile {d}: {sub.sum()}/{tot} = {100*sub.sum()/tot if tot else float('nan'):.4f}%")


def check1(trace_path, replay_order_path, expected_correct, expected_predictions, label):
    print(f"=== Check 1: {label} ===")
    trace = load_u64(trace_path)
    actual_full = load_u64(replay_order_path)
    len_trace = len(trace)
    n_full = len(actual_full)
    print(f"trace entries={len_trace} replay_order entries={n_full}")

    # predicted[k] for k=1..n_full-1 = trace[k % len_trace]; actual[k] = actual_full[k]
    k_idx = np.arange(1, n_full, dtype=np.int64)
    predicted = trace[k_idx % len_trace]
    actual = actual_full[k_idx]
    n = len(actual)

    exact = exact_next_accuracy(predicted, actual)
    n_correct = int(exact.sum())
    print(f"Sanity check vs. kernel counters: derived exact-next correct={n_correct} "
          f"predictions={n} | kernel reported correct={expected_correct} predictions={expected_predictions}")
    if n_correct != expected_correct or n != expected_predictions:
        print("!!! MISMATCH -- derivation does not reproduce the kernel's own counters. STOPPING for this workload.")
        return None
    print("Reproduced exactly. Proceeding.")

    report_by_decile(exact, n, "exact-next")

    results = {"exact": exact}
    for W in (10, 100, 1000, 10000):
        wacc = windowed_accuracy(predicted, actual, W)
        report_by_decile(wacc, n, f"windowed W={W}")
        results[f"window{W}"] = wacc

    sacc = set_accuracy(predicted, actual)
    report_by_decile(sacc, n, "set (anywhere in remainder)")
    results["set"] = sacc
    return results


def check2_pair(path_a, path_b, label):
    print(f"=== Check 2 pair: {label} ===")
    a = load_u64(path_a)
    b = load_u64(path_b)
    n = min(len(a), len(b))
    a = a[:n]
    b = b[:n]
    print(f"lengths: A={len(load_u64(path_a))} B={len(load_u64(path_b))}, compared over n={n}")

    exact = a == b
    report_by_decile(exact, n, "exact-position")

    for W in (10, 100, 1000, 10000):
        wacc = windowed_accuracy(a, b, W)
        report_by_decile(wacc, n, f"windowed W={W}")

    sacc = set_accuracy(a, b)
    report_by_decile(sacc, n, "set (anywhere in remainder)")


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "check1":
        check1(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), sys.argv[6])
    elif mode == "check2":
        check2_pair(sys.argv[2], sys.argv[3], sys.argv[4])
