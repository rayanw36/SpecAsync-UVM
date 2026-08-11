#!/usr/bin/env python3
"""t_a2_analyze.py — Task A2: combined bimodality experiment analysis.

Implements the fixed decision rule from the task brief:
  alignment (base % 2MB) correlates with cluster -> H1
  clock/thermal correlates with cluster            -> H2
  neither, but processed-item count differs         -> H3
  none of the above                                  -> reproducible and unexplained

Cluster split is found programmatically (largest gap in sorted wall_s), not
hardcoded, since this session's module (Task A1's added atomics) may shift
the absolute threshold slightly from decisive_c0c3_interleaved.py's 16.0s.
"""
import csv
import statistics as st
import sys
from pathlib import Path

try:
    from scipy import stats as spstats
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False

REPO = Path(__file__).resolve().parent.parent
CSV_PATH = REPO / "results/analysis/t_a2_bimodality/bimodality.csv"


def load():
    with open(CSV_PATH) as f:
        rows = [r for r in csv.DictReader(f) if r["phase"] == "kept"]
    return rows


def find_split(vals):
    """Largest gap in sorted values; returns (threshold, low_idxs, high_idxs, gap, gap_ratio)."""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    sorted_vals = [vals[i] for i in order]
    gaps = [(sorted_vals[i + 1] - sorted_vals[i], i) for i in range(len(sorted_vals) - 1)]
    if not gaps:
        return None
    max_gap, split_i = max(gaps)
    other_gaps = [g for g, _ in gaps if g != max_gap]
    median_other = st.median(other_gaps) if other_gaps else 0.0
    ratio = max_gap / median_other if median_other > 0 else float("inf")
    threshold = (sorted_vals[split_i] + sorted_vals[split_i + 1]) / 2.0
    low_idxs = set(order[:split_i + 1])
    high_idxs = set(order[split_i + 1:])
    return threshold, low_idxs, high_idxs, max_gap, ratio


def mwu(a, b, label):
    if not HAVE_SCIPY or len(a) < 2 or len(b) < 2:
        return f"{label}: n_low={len(a)} n_high={len(b)} (insufficient for test)"
    stat, p = spstats.mannwhitneyu(a, b, alternative="two-sided")
    return (f"{label}: low(n={len(a)}) median={st.median(a):.4g}  "
            f"high(n={len(b)}) median={st.median(b):.4g}  "
            f"Mann-Whitney p={p:.4g}")


def analyze_arm(arm, rows):
    arm_rows = [r for r in rows if r["arm"] == arm]
    wall = [float(r["wall_s"]) for r in arm_rows]
    split = find_split(wall)
    print(f"\n{'='*90}\nArm: {arm}  (n={len(arm_rows)})\n{'='*90}")
    if split is None:
        print("  not enough data")
        return None
    threshold, low_idxs, high_idxs, gap, ratio = split
    print(f"  sorted wall_s: {sorted(round(w,3) for w in wall)}")
    print(f"  largest gap={gap:.3f}s at threshold={threshold:.3f}s "
          f"(gap/median_other_gap={ratio:.2f}x)")
    print(f"  split: {len(low_idxs)} low / {len(high_idxs)} high")
    is_bimodal = ratio >= 3.0 and len(low_idxs) >= 2 and len(high_idxs) >= 2
    print(f"  bimodal (gap >=3x median other gap, both clusters n>=2): {is_bimodal}")

    low_rows = [arm_rows[i] for i in low_idxs]
    high_rows = [arm_rows[i] for i in high_idxs]

    result = dict(arm=arm, is_bimodal=is_bimodal, threshold=threshold,
                  n_low=len(low_idxs), n_high=len(high_idxs))

    if not is_bimodal:
        return result

    print("\n  -- H1: base_mod_2mb (alignment) --")
    base_low = [int(r["base_mod_2mb"]) for r in low_rows]
    base_high = [int(r["base_mod_2mb"]) for r in high_rows]
    print(f"    low cluster base%2MB values:  {sorted(set(base_low))}")
    print(f"    high cluster base%2MB values: {sorted(set(base_high))}")
    if arm == "ASLR_OFF":
        print("    (ASLR_OFF: base is pinned by setarch -R -- expect a single "
              "constant value across ALL reps if setarch is fully effective; "
              "a single shared value here does not distinguish clusters by "
              "definition and is not evidence for/against H1 in this arm.)")
    else:
        print("   ", mwu(base_low, base_high, "base_mod_2mb"))
    result["h1_addrs_low"] = sorted(set(base_low))
    result["h1_addrs_high"] = sorted(set(base_high))

    print("\n  -- H2: clock / thermal / power --")
    for field, label in [("gpu_temp_after", "temp_after (C)"),
                          ("gpu_sm_after", "sm_clock_after (MHz)"),
                          ("gpu_mem_after", "mem_clock_after (MHz)"),
                          ("gpu_power_after", "power_after (W)"),
                          ("loadavg_before", "cpu_loadavg_before")]:
        lo = [float(r[field]) for r in low_rows]
        hi = [float(r[field]) for r in high_rows]
        print("   ", mwu(lo, hi, label))
    pstates_low = sorted(set(r["gpu_pstate_after"] for r in low_rows))
    pstates_high = sorted(set(r["gpu_pstate_after"] for r in high_rows))
    throttle_low = sorted(set(r["throttle_after"] for r in low_rows))
    throttle_high = sorted(set(r["throttle_after"] for r in high_rows))
    print(f"    pstate_after: low={pstates_low} high={pstates_high}")
    print(f"    throttle_after: low={throttle_low} high={throttle_high}")

    print("\n  -- H3: processed items (not just enqueued) --")
    proc_low = [int(r["processed"]) for r in low_rows]
    proc_high = [int(r["processed"]) for r in high_rows]
    enq_low = [int(r["enqueued"]) for r in low_rows]
    enq_high = [int(r["enqueued"]) for r in high_rows]
    print("   ", mwu(proc_low, proc_high, "processed"))
    print("   ", mwu(enq_low, enq_high, "enqueued"))
    all_match = all(int(r["processed"]) == int(r["enqueued"]) for r in arm_rows)
    print(f"    processed==enqueued in every rep (A1 finding holds here too): {all_match}")
    result["proc_low_median"] = st.median(proc_low)
    result["proc_high_median"] = st.median(proc_high)

    return result


def main():
    rows = load()
    print(f"Loaded {len(rows)} kept-phase rows from {CSV_PATH}")

    results = {}
    for arm in ("ASLR_ON", "ASLR_OFF"):
        r = analyze_arm(arm, rows)
        if r:
            results[arm] = r

    print(f"\n{'='*90}\nDECISION RULE VERDICT\n{'='*90}")
    off_bimodal = results.get("ASLR_OFF", {}).get("is_bimodal", False)
    on_bimodal = results.get("ASLR_ON", {}).get("is_bimodal", False)
    print(f"Bimodality persists under fixed ASLR (ASLR_OFF): {off_bimodal}")
    print(f"Bimodality also present under ASLR_ON: {on_bimodal}")
    print("\nApply the fixed decision rule from the task brief to the H1/H2/H3 "
          "sections above (printed per-arm). This script reports the raw "
          "correlations; the verdict sentence belongs in GATE_A2_REPORT.md, "
          "written from these numbers, not fabricated ahead of them.")


if __name__ == "__main__":
    main()
