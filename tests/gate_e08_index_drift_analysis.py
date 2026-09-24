#!/usr/bin/env python3
"""Gate E0.8: index-drift vs genuine-divergence analysis.

Analysis only. Operates on raw u64 address sequences already collected by
Gate E0.7 (results/phaseB1/gate_e07_check1/, gate_e07_check2/). No new
benchmark runs, no driver interaction.

Checks 1-5 operate on a pair of sequences (A, B). For Check 1's runs,
A = trace (collection order), B = replay_order (actual replay fault order).
For Check 6's runs, A/B are two independent plain-C1 traces.
"""
import sys
import json
import bisect
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, kendalltau


def load_u64(path):
    return np.fromfile(path, dtype="<u8")


def decile_report(mask, n):
    out = {"overall": float(mask.sum()) / n if n else float("nan")}
    for d in range(10):
        lo = (d * n) // 10
        hi = ((d + 1) * n) // 10
        sub = mask[lo:hi]
        tot = len(sub)
        out[f"d{d}"] = float(sub.sum()) / tot if tot else float("nan")
    return out


def first_occurrence_positions(seq):
    """Return a pandas Series: index=address, value=first index in seq."""
    s = pd.Series(np.arange(len(seq)), index=seq)
    return s.groupby(level=0).min()


def all_occurrence_positions(seq):
    """Return dict: address -> sorted numpy array of positions in seq."""
    df = pd.DataFrame({"addr": seq, "pos": np.arange(len(seq))})
    grouped = df.groupby("addr")["pos"].apply(lambda s: np.sort(s.values))
    return grouped.to_dict()


# ---------------------------------------------------------------- Check 1 --
def check1_backward_set(A, B, label):
    """For each k, does A[k] appear anywhere in B[:k]? (A=trace, B=replay)"""
    n = min(len(A), len(B))
    A = A[:n]
    first_pos_B = first_occurrence_positions(B)
    mapped = first_pos_B.reindex(A).values.astype("float64")  # NaN if absent
    k = np.arange(n)
    with np.errstate(invalid="ignore"):
        mask = mapped < k
    mask = np.nan_to_num(mask, nan=0.0).astype(bool)
    rep = decile_report(mask, n)
    print(f"  [Check1 backward-set] {label}: overall={100*rep['overall']:.4f}%  "
          + " ".join(f"d{d}={100*rep[f'd{d}']:.4f}%" for d in range(10)))
    return rep


# ---------------------------------------------------------------- Check 2 --
def check2_page_set_overlap(A, B, label):
    setA, setB = set(np.unique(A).tolist()), set(np.unique(B).tolist())
    inter = setA & setB
    union = setA | setB
    a_in_b = len(inter) / len(setA) if setA else float("nan")
    b_in_a = len(inter) / len(setB) if setB else float("nan")
    jaccard = len(inter) / len(union) if union else float("nan")
    print(f"  [Check2 page-set] {label}: |A|={len(setA)} |B|={len(setB)} |A∩B|={len(inter)} "
          f"A-in-B={100*a_in_b:.4f}% B-in-A={100*b_in_a:.4f}% Jaccard={100*jaccard:.4f}%")
    return {"A_in_B": a_in_b, "B_in_A": b_in_a, "jaccard": jaccard,
            "distinctA": len(setA), "distinctB": len(setB), "intersection": len(inter)}


# ---------------------------------------------------------------- Check 3 --
def check3_signed_lag(A, B, label, rule="nearest"):
    """For each trace position k, signed offset = (matched position in B) - k."""
    n = len(A)
    if rule == "first":
        first_pos_B = first_occurrence_positions(B)
        matched = first_pos_B.reindex(A).values.astype("float64")
        offsets = matched - np.arange(n)
    else:
        pos_map = all_occurrence_positions(B)
        offsets = np.full(n, np.nan)
        for k in range(n):
            arr = pos_map.get(A[k])
            if arr is None:
                continue
            idx = bisect.bisect_left(arr, k)
            candidates = []
            if idx < len(arr):
                candidates.append(arr[idx])
            if idx > 0:
                candidates.append(arr[idx - 1])
            best = min(candidates, key=lambda p: abs(p - k))
            offsets[k] = best - k

    valid = ~np.isnan(offsets)
    stats = {"rule": rule, "n_valid": int(valid.sum()), "n_total": n}
    per_decile = {}
    for d in range(10):
        lo = (d * n) // 10
        hi = ((d + 1) * n) // 10
        sub = offsets[lo:hi]
        sub = sub[~np.isnan(sub)]
        if len(sub) == 0:
            per_decile[f"d{d}"] = None
            continue
        med = float(np.median(sub))
        q1, q3 = np.percentile(sub, [25, 75])
        frac_pos = float((sub > 0).mean())
        per_decile[f"d{d}"] = {"median": med, "iqr": float(q3 - q1), "frac_positive": frac_pos, "n": len(sub)}
    stats["per_decile"] = per_decile
    print(f"  [Check3 signed-lag, rule={rule}] {label}: valid={stats['n_valid']}/{n}")
    for d in range(10):
        pd_ = per_decile[f"d{d}"]
        if pd_ is None:
            print(f"    d{d}: no valid matches")
        else:
            print(f"    d{d}: median={pd_['median']:.1f} IQR={pd_['iqr']:.1f} frac_pos={pd_['frac_positive']:.3f} n={pd_['n']}")
    return offsets, stats


# ---------------------------------------------------------------- Check 4 --
def first_touch_sequence(seq):
    """Order in which each distinct address is FIRST faulted."""
    _, idx = np.unique(seq, return_index=True)
    order = np.sort(idx)
    return seq[order]


def check4_first_touch(A, B, label):
    ftA, ftB = first_touch_sequence(A), first_touch_sequence(B)
    rankA = pd.Series(np.arange(len(ftA)), index=ftA)
    rankB = pd.Series(np.arange(len(ftB)), index=ftB)
    common = rankA.index.intersection(rankB.index)
    rA = rankA.loc[common].values
    rB = rankB.loc[common].values
    if len(common) < 2:
        print(f"  [Check4] {label}: fewer than 2 common pages, skipping correlation")
        return None
    sp, sp_p = spearmanr(rA, rB)
    # Kendall tau on the full common set can be slow (O(n log n) with scipy's
    # default, but can still be heavy for n ~ 1e6); use scipy's method='auto'.
    if len(common) > 200000:
        rng = np.random.default_rng(0)
        sample_idx = rng.choice(len(common), size=200000, replace=False)
        kt, kt_p = kendalltau(rA[sample_idx], rB[sample_idx])
        kt_note = " (subsampled 200,000 of %d common pages)" % len(common)
    else:
        kt, kt_p = kendalltau(rA, rB)
        kt_note = ""
    print(f"  [Check4 first-touch] {label}: common_pages={len(common)} "
          f"Spearman={sp:.4f} (p={sp_p:.2e}) Kendall={kt:.4f}{kt_note} (p={kt_p:.2e})")

    # Apply E0.7-style exact/windowed/set measures to the REDUCED sequences.
    n = min(len(ftA), len(ftB))
    a, b = ftA[:n], ftB[:n]
    exact = a == b
    rep_exact = decile_report(exact, n)
    print(f"    reduced exact-position: overall={100*rep_exact['overall']:.4f}%")

    first_pos_b = first_occurrence_positions(b)
    n_full = n
    results = {"spearman": sp, "spearman_p": sp_p, "kendall": kt, "kendall_p": kt_p,
               "n_common": len(common), "reduced_exact": rep_exact}
    for W in (10, 100, 1000, 10000):
        mask = np.zeros(n_full, dtype=bool)
        window = {}
        right = min(W, n_full)
        for i in range(right):
            window[b[i]] = window.get(b[i], 0) + 1
        for k in range(n_full):
            mask[k] = window.get(a[k], 0) > 0
            window[b[k]] -= 1
            if window[b[k]] == 0:
                del window[b[k]]
            new_right = k + W
            if right == new_right and right < n_full:
                window[b[right]] = window.get(b[right], 0) + 1
                right += 1
        rep_w = decile_report(mask, n_full)
        results[f"reduced_window{W}"] = rep_w
        print(f"    reduced window W={W}: overall={100*rep_w['overall']:.4f}%")

    last_pos = {}
    for i in range(n_full - 1, -1, -1):
        if b[i] not in last_pos:
            last_pos[b[i]] = i
    set_mask = np.zeros(n_full, dtype=bool)
    for k in range(n_full):
        lp = last_pos.get(a[k])
        set_mask[k] = lp is not None and lp >= k
    rep_set = decile_report(set_mask, n_full)
    results["reduced_set"] = rep_set
    print(f"    reduced set: overall={100*rep_set['overall']:.4f}%")
    return results


# ---------------------------------------------------------------- Check 5 --
def check5_repeat_gaps(seq, label):
    df = pd.DataFrame({"addr": seq, "pos": np.arange(len(seq))})
    gaps = df.groupby("addr")["pos"].apply(lambda s: np.diff(np.sort(s.values)))
    all_gaps = np.concatenate([g for g in gaps if len(g) > 0]) if len(gaps) else np.array([])
    if len(all_gaps) == 0:
        print(f"  [Check5] {label}: no repeated pages")
        return None
    qs = np.percentile(all_gaps, [10, 25, 50, 75, 90, 99])
    print(f"  [Check5 repeat-gaps] {label}: n_gaps={len(all_gaps)} "
          f"p10={qs[0]:.0f} p25={qs[1]:.0f} median={qs[2]:.0f} p75={qs[3]:.0f} p90={qs[4]:.0f} p99={qs[5]:.0f} "
          f"run_length={len(seq)} run_len/20={len(seq)/20:.0f}")
    return {"n_gaps": len(all_gaps), "p10": qs[0], "p25": qs[1], "median": qs[2],
            "p75": qs[3], "p90": qs[4], "p99": qs[5], "run_length": len(seq)}


if __name__ == "__main__":
    mode = sys.argv[1]
    A = load_u64(sys.argv[2])
    B = load_u64(sys.argv[3])
    label = sys.argv[4] if len(sys.argv) > 4 else ""
    if mode == "check1":
        check1_backward_set(A, B, label)
    elif mode == "check2":
        check2_page_set_overlap(A, B, label)
    elif mode == "check3":
        check3_signed_lag(A, B, label, rule="nearest")
        check3_signed_lag(A, B, label, rule="first")
    elif mode == "check4":
        check4_first_touch(A, B, label)
    elif mode == "check5":
        check5_repeat_gaps(A, label + " (A)")
        check5_repeat_gaps(B, label + " (B)")
    elif mode == "all":
        check1_backward_set(A, B, label)
        check2_page_set_overlap(A, B, label)
        check4_first_touch(A, B, label)
        check5_repeat_gaps(A, label + " (A)")
        check5_repeat_gaps(B, label + " (B)")
