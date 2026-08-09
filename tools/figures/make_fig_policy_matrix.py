#!/usr/bin/env python3
"""F1 -- policy_matrix: corrected Phase B policy sweep (runtime delta + hit rate).

Sources:
  results/phaseB/phaseB_timing.csv       (p0-p4 wall time, mean/std/n, PRE Gate-B-fix)
  results/phaseB/phaseB_telemetry.csv    (p0-p4 hit rate, PRE Gate-B-fix)
  results/phaseB1/gate_d/{stencil,graphbfs,stencil_ovsub}/times.csv    (POST-fix wall time)
  results/phaseB1/gate_d/{stencil,graphbfs,stencil_ovsub}/summary.txt  (POST-fix hit rate)

FIX-1 (driver/PIPELINE_FIXES.md, results/phaseB1/GATE_B_diagnosis.md) only affects
policy=4 (oracle): the cursor-desync bug made every p4 row in phaseB_timing.csv /
phaseB_telemetry.csv artifactually near-zero-hit and, for the two benchmarks Phase B
happened to log, wildly slow. p0-p3 are not touched by that bug and are used as-is
from the Phase B sweep. p4 is used ONLY where Gate D reran it post-fix (Stencil@24000,
GraphBFS@23, Stencil_OvSub@28300_20_11264); everywhere else p4 is EXCLUDED and the gap
is annotated on the plot and printed to stdout -- the pre-fix number is never plotted.
"""
import csv
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fig_common import (PAGE_WIDTH_IN, POLICY_STYLE, GRID, INK_PRIMARY,
                          INK_SECONDARY, INK_MUTED, savefig, pct_formatter)
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

REPO = Path(__file__).resolve().parents[2]
TIMING_CSV = REPO / "results/phaseB/phaseB_timing.csv"
TELEM_CSV = REPO / "results/phaseB/phaseB_telemetry.csv"
GATE_D = {
    ("Stencil", "24000"): REPO / "results/phaseB1/gate_d/stencil",
    ("GraphBFS", "23"): REPO / "results/phaseB1/gate_d/graphbfs",
    ("Stencil_OvSub", "28300_20_11264"): REPO / "results/phaseB1/gate_d/stencil_ovsub",
}
BENCH_ORDER = ["GraphBFS", "SGEMM", "STREAM", "Stencil", "Stencil_OvSub", "cuFFT"]
POLICIES = ["p1", "p2", "p3", "p4"]

# results/phaseB1/GATE_C_report.md C2: the Phase B STREAM p1/p2/p3 numbers at these
# two sizes were measured all-baseline-then-all-treatment; re-run INTERLEAVED
# (40 cycles/policy/size) the -8.8% "speedup" disappears and reverses to a +1.5-2%
# slowdown, tracking p5 (null-worker, no prediction at all) almost exactly -- i.e.
# it is host-ordering noise on the shared EC2 instance, not a speculation effect,
# and it does not correlate with hit rate. Gate C only interleaved-reran p1 (and the
# p5 null control) at these two sizes, not p2/p3, so only p1 has a corrected number;
# all three are excluded from the bar chart and annotated, per the same
# exclude-and-annotate rule used for the pre-fix p4 rows.
STREAM_HOST_NOISE = {("STREAM", "134217728"), ("STREAM", "268435456")}
GATE_C_INTERLEAVED_P1 = {  # (delta_pct, ci_note) from GATE_C_report.md C2 table
    ("STREAM", "134217728"): 2.05,
    ("STREAM", "268435456"): 1.77,
}

Z95 = 1.959963985


def load_timing():
    rows = {}
    with open(TIMING_CSV) as f:
        for r in csv.DictReader(f):
            key = (r["benchmark"], r["size"], int(r["policy"]))
            rows[key] = dict(mean_ms=float(r["mean_ms"]), std_ms=float(r["std_ms"]),
                              n=int(r["n"]))
    return rows


def load_telem():
    rows = {}
    with open(TELEM_CSV) as f:
        for r in csv.DictReader(f):
            key = (r["benchmark"], r["size"], int(r["policy"]))
            rows[key] = float(r["hit_rate"])
    return rows


def load_gate_d(gdir):
    """Returns {policy_int: (median_s, sem_s, n)} from times.csv and
    {policy_int: hit_rate} parsed from summary.txt."""
    times = {}
    by_policy = {}
    with open(gdir / "times.csv") as f:
        for r in csv.DictReader(f):
            by_policy.setdefault(int(r["policy"]), []).append(float(r["wall_s"]))
    for p, vals in by_policy.items():
        med = st.median(vals)
        sem = st.stdev(vals) / len(vals) ** 0.5 if len(vals) > 1 else 0.0
        times[p] = (med, sem, len(vals))

    hit = {}
    txt = (gdir / "summary.txt").read_text()
    for m in re.finditer(r"p(\d)(?:\(oracle\))?\s*==\s*\n.*?hit_rate\(hits/enq\)=([\d.]+)",
                          txt, re.S):
        hit[int(m.group(1))] = float(m.group(2))
    return times, hit


def main():
    timing = load_timing()
    telem = load_telem()

    # cell key: (benchmark, size) -> {policy: dict(delta_pct, ci_pct, hit_pct,
    #                                               source, hit_source)}
    cells = {}
    benches = {}
    with open(TIMING_CSV) as f:
        for r in csv.DictReader(f):
            benches.setdefault(r["benchmark"], set()).add(r["size"])

    print(f"{'benchmark':<14} {'size':<20} {'pol':<4} {'delta%':>8} {'ci%':>7} "
          f"{'hit%':>9} {'wall_src':<10} {'hit_src':<10}")
    print("-" * 92)

    for bench in BENCH_ORDER:
        for size in sorted(benches.get(bench, [])):
            gate_key = (bench, size)
            has_gate_d = gate_key in GATE_D
            gd_times, gd_hit = ({}, {})
            if has_gate_d:
                gd_times, gd_hit = load_gate_d(GATE_D[gate_key])

            base_key = (bench, size, 0)
            if has_gate_d:
                base_med, _, base_n = gd_times[0]
            elif base_key in timing:
                base_med = timing[base_key]["mean_ms"]
            else:
                continue

            cell = {}
            for pname in POLICIES:
                p = int(pname[1])
                if p == 4 and not has_gate_d:
                    cell[pname] = dict(delta_pct=None, ci_pct=None, hit_pct=None,
                                        source="EXCLUDED (pre-fix only)",
                                        hit_source="EXCLUDED (pre-fix only)")
                    print(f"{bench:<14} {size:<20} {pname:<4} {'--':>8} {'--':>7} "
                          f"{'--':>9} {'no Gate D rerun':<10} {'no Gate D rerun':<10}")
                    continue

                if p in (1, 2, 3) and (bench, size) in STREAM_HOST_NOISE:
                    cell[pname] = dict(delta_pct=None, ci_pct=None, hit_pct=None,
                                        source="EXCLUDED (host-ordering artifact)",
                                        hit_source="EXCLUDED (host-ordering artifact)")
                    corrected = GATE_C_INTERLEAVED_P1.get((bench, size)) if p == 1 else None
                    note = f"Gate-C interleaved p1={corrected:+.2f}%" if corrected is not None else "no interleaved rerun for p2/p3"
                    print(f"{bench:<14} {size:<20} {pname:<4} {'--':>8} {'--':>7} "
                          f"{'--':>9} {'ARTIFACT, GATE_C':<10} {note}")
                    continue

                if has_gate_d:
                    med, sem, n = gd_times[p]
                    delta_pct = 100.0 * (med - base_med) / base_med
                    ci_pct = 100.0 * Z95 * sem / base_med
                    hit_pct = gd_hit.get(p, 0.0) * 100.0
                    wsrc, hsrc = "gate_d (post-fix)", "gate_d (post-fix)"
                else:
                    d = timing[(bench, size, p)]
                    delta_pct = 100.0 * (d["mean_ms"] - base_med) / base_med
                    sem = d["std_ms"] / d["n"] ** 0.5
                    ci_pct = 100.0 * Z95 * sem / base_med
                    hit_pct = telem.get((bench, size, p), 0.0) * 100.0
                    wsrc, hsrc = "phaseB (pre-fix, valid for p1-p3)", "phaseB (pre-fix, valid for p1-p3)"

                cell[pname] = dict(delta_pct=delta_pct, ci_pct=ci_pct, hit_pct=hit_pct,
                                    source=wsrc, hit_source=hsrc)
                print(f"{bench:<14} {size:<20} {pname:<4} {delta_pct:>8.2f} {ci_pct:>7.2f} "
                      f"{hit_pct:>9.4f} {wsrc:<10} {hsrc:<10}")
            cells[gate_key] = cell

    def short_size(bench, size):
        if bench in ("STREAM", "cuFFT"):
            n = int(size)
            return f"{n // (1 << 20)}M" if n >= (1 << 20) else f"{n // 1024}K"
        if bench == "Stencil_OvSub":
            return size.split("_")[0]
        return size

    # ---- Figure: 2 rows x 3 cols runtime-delta small multiples, + hit-rate strip ----
    fig = plt.figure(figsize=(PAGE_WIDTH_IN, 7.4))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.55], hspace=0.42)
    gs_top = gs[0].subgridspec(1, 6, wspace=0.55)

    for i, bench in enumerate(BENCH_ORDER):
        ax = fig.add_subplot(gs_top[i])
        sizes = sorted(benches.get(bench, []))
        x = np.arange(len(sizes))
        width = 0.8 / len(POLICIES)
        for j, pname in enumerate(POLICIES):
            style = POLICY_STYLE[pname]
            vals, errs, xs = [], [], []
            for k, size in enumerate(sizes):
                c = cells.get((bench, size), {}).get(pname)
                if c is None or c["delta_pct"] is None:
                    continue
                vals.append(c["delta_pct"])
                errs.append(c["ci_pct"])
                xs.append(x[k] + (j - 1.5) * width)
            ax.bar(xs, vals, width=width * 0.9, yerr=errs, color=style["color"],
                   hatch=style["hatch"], edgecolor=INK_PRIMARY, linewidth=0.4,
                   capsize=1.5, error_kw=dict(linewidth=0.5))
        # mark excluded cells (pre-fix p4, or STREAM host-ordering artifact)
        for k, size in enumerate(sizes):
            for j, pname in enumerate(POLICIES):
                c = cells.get((bench, size), {}).get(pname)
                if c is not None and c["delta_pct"] is None:
                    ax.annotate("×", (x[k] + (j - 1.5) * width, 0), ha="center",
                                va="center", fontsize=5, color=INK_MUTED)
        ax.axhline(0, color=INK_MUTED, linewidth=0.6)
        ax.set_xticks(x)
        ax.set_xticklabels([short_size(bench, s) for s in sizes],
                            rotation=30, ha="right", fontsize=5.2)
        ax.set_title(bench, fontsize=6.5, pad=2)
        ax.tick_params(axis="y", labelsize=5.5)
        ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=4))
        ax.grid(axis="y", linewidth=0.3, color=GRID)
        ax.set_xlim(-0.6, len(sizes) - 0.4)
        ax.margins(y=0.25)
        if i == 0:
            ax.set_ylabel("$\\Delta$ wall time\nvs p0 (%)", fontsize=6)

    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=POLICY_STYLE[p]["color"],
                              hatch=POLICY_STYLE[p]["hatch"], edgecolor=INK_PRIMARY,
                              linewidth=0.4, label=POLICY_STYLE[p]["label"])
               for p in POLICIES]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.985),
               ncol=4, frameon=False, fontsize=6.5)

    # ---- hit-rate strip panel, grouped by benchmark family with shaded bands ----
    ax2 = fig.add_subplot(gs[1])
    row_labels = []
    y = 0
    yticks = []
    band_on = False
    for bi, bench in enumerate(BENCH_ORDER):
        sizes_b = sorted(benches.get(bench, []))
        y0 = y
        for size in sizes_b:
            label = f"{bench} {short_size(bench, size)}"
            row_labels.append(label)
            yticks.append(y)
            ax2.axhline(y, color=GRID, linewidth=0.3, zorder=0)
            for pname in POLICIES:
                c = cells.get((bench, size), {}).get(pname)
                if c is None or c["hit_pct"] is None:
                    continue
                style = POLICY_STYLE[pname]
                xval = max(c["hit_pct"], 3e-4)
                ax2.scatter(xval, y, marker=style["marker"], color=style["color"],
                            edgecolor=INK_PRIMARY, linewidth=0.3, s=16, zorder=3)
            y += 1
        if band_on:
            ax2.axhspan(y0 - 0.5, y - 0.5, color="#f2f1ee", zorder=0)
        band_on = not band_on
    max_hit = max((c["hit_pct"] for cell in cells.values() for c in cell.values()
                   if c["hit_pct"] is not None), default=1.0)
    ax2.set_xscale("symlog", linthresh=1e-3, linscale=0.5)
    ax2.set_xlim(2e-4, max_hit * 1.6)
    ax2.set_ylim(y - 0.5, -0.5)
    ax2.set_yticks(yticks)
    ax2.set_yticklabels(row_labels, fontsize=5.2)
    ax2.set_xlabel("hit rate (%, symlog scale)")
    ax2.set_title("× excluded above = pre-fix oracle rows / STREAM p1-p3 host-ordering "
                   "artifact (GATE_B_diagnosis.md, GATE_C_report.md)",
                   fontsize=5, color=INK_MUTED, style="italic", pad=6)
    ax2.grid(axis="x", linewidth=0.3, color=GRID)
    ax2.grid(axis="y", visible=False)
    ax2.tick_params(axis="y", length=0)

    outstem = REPO / "results/figures/policy_matrix"
    savefig(fig, str(outstem))
    print(f"\nwrote {outstem}.pdf / .png")


if __name__ == "__main__":
    main()
