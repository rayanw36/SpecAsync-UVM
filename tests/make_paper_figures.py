#!/usr/bin/env python3
"""Gate C5 step 4: paper figures from COMMITTED CSVs only. One function per figure, one shared style.

Style: serif font (STIX), IEEE widths (single column 3.5 in, double column 7.16 in), colourblind-safe palette (the validated categorical slots 1-3 of the
dataviz reference palette: blue, orange, aqua) with a second encoding (marker shape), no titles inside the figure, recessive grid. Every run is a point and
the median is a larger marker (or bar). A median marker is FILLED when the comparison is Holm-significant in the source analysis, HOLLOW when it is not
significant, and a PLUS when the cell was not tested (n = 3 descriptive figures use bars). Output: paper/figures/<name>.pdf and .png, plus paper/figures/FIGURES.md
(source CSVs, function, n per cell, a draft caption of at most three sentences). Captions are f-strings over values read from the CSVs; nothing is typed by hand.

usage: make_paper_figures.py [name ...]   names: e4 e5 e6 e7 e8 e9 ph (default: all)
"""
import csv
import math
import os
import statistics as st
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
OUT = "paper/figures"
GE = "results/analysis/gate_e"
BLUE, ORANGE, AQUA, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#0b0b0b", "#52514e", "#d8d8d4"
COL1, COL2 = 3.5, 7.16
GIB = 1073741824.0
META = {}


def style():
    plt.rcParams.update({
        "font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix",
        "font.size": 7.5, "axes.labelsize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
        "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 2.5, "ytick.major.size": 2.5,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.4, "axes.axisbelow": True,
        "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.dpi": 300, "figure.dpi": 100,
    })


def rd(path):
    return list(csv.DictReader(open(path)))


def fl(x):
    return float(x)


def pts(ax, x, ys, color, marker="o", jitter=0.0, size=5, alpha=0.45):
    n = len(ys)
    xs = [x + (jitter * ((i / max(n - 1, 1)) - 0.5) * 2 if n > 1 else 0) for i in range(n)]
    ax.scatter(xs, ys, s=size, color=color, alpha=alpha, linewidths=0, zorder=3, marker=marker)


def med_marker(ax, x, y, color, marker="o", state="sig", size=22):
    """state: sig -> filled, ns -> hollow, untested -> plus."""
    if state == "untested":
        ax.scatter([x], [y], s=size * 1.2, marker="P", facecolor="white", edgecolor=color, linewidths=1.0, zorder=5)
    elif state == "sig":
        ax.scatter([x], [y], s=size, marker=marker, facecolor=color, edgecolor=color, linewidths=1.0, zorder=5)
    else:
        ax.scatter([x], [y], s=size, marker=marker, facecolor="white", edgecolor=color, linewidths=1.1, zorder=5)


def pct(v, base):
    return 100.0 * (v / base - 1.0)


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(f"{OUT}/{name}.pdf", bbox_inches="tight")
    fig.savefig(f"{OUT}/{name}.png", bbox_inches="tight")
    plt.close(fig)


def legend_state(ax, loc="best"):
    from matplotlib.lines import Line2D
    h = [Line2D([], [], marker="o", ls="", mfc="k", mec="k", ms=4, label="Holm-significant"),
         Line2D([], [], marker="o", ls="", mfc="w", mec="k", ms=4, label="not significant"),
         Line2D([], [], marker="o", ls="", mfc="k", alpha=0.45, mec="none", ms=2.5, label="one run")]
    ax.legend(handles=h, frameon=False, loc=loc, handletextpad=0.3, borderaxespad=0.2)


# ------------------------------------------------------------------ F-E4
def fig_e4():
    runs = rd(f"{GE}/e4/e4_runs.csv")
    comp = rd(f"{GE}/e4/primary_comparisons.csv")

    def wall(wl, arm):
        return [fl(r["wall_s"]) for r in runs if r["workload"] == wl and r["label"] == f"{wl} {arm}"]

    def row(fam, wl, arm):
        return next(c for c in comp if c["family"] == fam and c["workload"] == wl and c["arm"] == arm and c["baseline"] == "C0")
    fig, axes = plt.subplots(1, 3, figsize=(COL2, 2.35), gridspec_kw={"width_ratios": [3, 3, 2.2]})
    n_cell = {}
    for ax, wl, ttl in ((axes[0], "stencil", "Stencil-24K"), (axes[1], "graphbfs", "GraphBFS-23")):
        base = st.median(wall(wl, "C0"))
        for i, arm in enumerate(("C7-W1", "C7-W64", "C7-W512")):
            w = wall(wl, arm)
            pts(ax, i, [pct(v, base) for v in w], BLUE, jitter=0.12)
            c = row("F1", wl, arm)
            med_marker(ax, i, fl(c["delta_pct"]), BLUE, "o", "sig" if c["holm_sig"] == "True" else "ns")
            n_cell[(wl, arm)] = len(w)
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_xticks(range(3)); ax.set_xticklabels(["W=1", "W=64", "W=512"])
        ax.set_xlabel(f"{ttl}: staging width (cheap oracle, prefetcher on)")
    axes[0].set_ylabel("wall-clock vs C0 median (%)")
    legend_state(axes[0], "upper right")
    ax = axes[2]
    for i, (wl, col, mk) in enumerate((("stencil", BLUE, "o"), ("graphbfs", ORANGE, "s"))):
        base = st.median(wall(wl, "C0"))
        w = wall(wl, "C6-W512")
        pts(ax, i, [pct(v, base) for v in w], col, marker=mk, jitter=0.1)
        c = row("F4", wl, "C6-W512")
        med_marker(ax, i, fl(c["delta_pct"]), col, mk, "sig" if c["holm_sig"] == "True" else "ns")
    ax.axhline(0, color=MUTED, lw=0.6)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["Stencil\n24K", "GraphBFS\n23"])
    ax.set_xlabel("perfect staging, prefetcher off\n(C6-W512, family F4)")
    fig.tight_layout(w_pad=0.8)
    save(fig, "fig_e4_wallclock_by_arm")
    s, g = row("F1", "stencil", "C7-W512"), row("F4", "stencil", "C6-W512")
    META["e4"] = dict(csv=f"{GE}/e4/e4_runs.csv; {GE}/e4/primary_comparisons.csv", fn="fig_e4", n="10 runs per arm, including C0",
        cap=(f"RTX 5070 Ti, driver 595.91.07, stock prefetcher on: wall-clock change of the staging arms relative to the median of C0 (the shipped driver) on Stencil-24K and GraphBFS-23 (E4 family F1), and of perfect off-path staging with the in-path prefetcher off, C6-W512 (family F4, right). "
             f"Each run is a point; markers are medians, filled when Holm-significant (two-sided Mann-Whitney U, n = 10 per arm). "
             f"At W = 512 the Stencil-24K arm is {fl(s['delta_pct']):+.2f}% against C0, while C6-W512 is {fl(g['delta_pct']):+.2f}%."))


# ------------------------------------------------------------------ F-E5
def fig_e5():
    runs = rd(f"{GE}/e5/e5_runs.csv")
    wc = {int(r["threshold"]): r for r in rd(f"{GE}/e5/wallclock_comparisons.csv")}
    fr = {int(r["threshold"]): r for r in rd(f"{GE}/e5/fault_reduction.csv")}
    tl = {51: "t51", 75: "t75", 100: "toff"}

    def vals(arm, t, key):
        return [fl(r[key]) for r in runs if r["label"] == f"stencil {arm}-{tl[t]}"]
    fig, axes = plt.subplots(1, 2, figsize=(COL2 * 0.62, 2.35))
    for i, t in enumerate((51, 75, 100)):
        c0f = st.median(vals("C0", t, "demand_faults"))
        pts(axes[0], i, [1 - v / c0f for v in vals("C7W512", t, "demand_faults")], BLUE, jitter=0.1)
        med_marker(axes[0], i, fl(fr[t]["D"]), BLUE, "o", "sig" if fr[t]["holm_sig"] == "True" else "ns")
        c0w = st.median(vals("C0", t, "wall_s"))
        pts(axes[1], i, [pct(v, c0w) for v in vals("C7W512", t, "wall_s")], ORANGE, "s", jitter=0.1)
        med_marker(axes[1], i, fl(wc[t]["delta_pct"]), ORANGE, "s", "sig" if wc[t]["holm_sig"] == "True" else "ns")
    for ax in axes:
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_xticks(range(3)); ax.set_xticklabels(["51\n(shipped)", "75", "100\n(rule off)"])
        ax.set_xlabel("uvm_perf_prefetch_threshold")
    axes[0].set_ylabel("demand-fault reduction D(t)")
    axes[1].set_ylabel("C7W512 wall-clock vs C0 at the same t (%)")
    legend_state(axes[0], "upper right")
    fig.tight_layout(w_pad=0.8)
    save(fig, "fig_e5_threshold_dose_response")
    META["e5"] = dict(csv=f"{GE}/e5/e5_runs.csv; {GE}/e5/fault_reduction.csv; {GE}/e5/wallclock_comparisons.csv", fn="fig_e5", n="10 runs per cell",
        cap=(f"RTX 5070 Ti, stock prefetcher, Stencil-24K: D(t) = 1 - (median demand faults of C7W512) / (median of C0 at the same threshold) and the wall-clock change of C7W512 against C0 at the same threshold. "
             f"Each run is a point; markers are medians, filled when Holm-significant (two-sided Mann-Whitney U, n = 10 per cell). "
             f"D is {fl(fr[51]['D']):+.4f} at the shipped threshold 51, {fl(fr[75]['D']):+.4f} at 75 and {fl(fr[100]['D']):+.4f} with the rule disabled (100)."))


# ------------------------------------------------------------------ F-E6
def fig_e6():
    runs = rd(f"{GE}/e6/e6_runs.csv")
    runs = [r for r in runs if r["workload"] == "stencil"]
    sw = {r["arm"]: r for r in rd(f"{GE}/e6/secondary_wall.csv")}
    sd = {r["arm"]: r for r in rd(f"{GE}/e6/secondary_demand.csv")}
    f1 = {r["base"]: r for r in rd(f"{GE}/e6/family1_primary.csv")}
    ts = (0, 10, 25, 51)
    fig, axes = plt.subplots(1, 2, figsize=(COL2 * 0.68, 2.35))
    for ax, key, ylab, secd in ((axes[0], "wall_s", "process wall-clock (s)", sw), (axes[1], "demand_faults", "demand faults per run", sd)):
        for arm, col, mk, dx in (("C0", BLUE, "o", -0.9), ("C7W512", ORANGE, "s", 0.9)):
            med_x, med_y = [], []
            for t in ts:
                v = [fl(r[key]) for r in runs if r["label"] == f"stencil {arm}-t{t}"]
                x = t + dx
                pts(ax, x, v, col, mk, jitter=0.6)
                m = st.median(v)
                med_x.append(x); med_y.append(m)
                a = f"C7W512-t{t}"
                if a in secd:
                    state = "sig" if secd[a]["holm_sig"] == "True" else "ns"
                elif key == "wall_s" and t == 51:
                    state = "sig" if f1["C0-t51"]["holm_sig"] == "True" else "ns"
                else:
                    state = "untested"
                med_marker(ax, x, m, col, mk, state)
            ax.plot(med_x, med_y, color=col, lw=0.8, zorder=4)
        ax.set_xticks(ts); ax.set_xticklabels(["0", "10", "25", "51"])
        ax.set_xlabel("uvm_perf_prefetch_threshold"); ax.set_ylabel(ylab)
    from matplotlib.lines import Line2D
    axes[0].legend(handles=[Line2D([], [], marker="o", ls="-", color=BLUE, ms=3.5, lw=0.8, label="C0 (speculation off)"),
                            Line2D([], [], marker="s", ls="-", color=ORANGE, ms=3.5, lw=0.8, label="C7W512 (oracle, W = 512)"),
                            Line2D([], [], marker="P", ls="", mfc="w", mec=MUTED, ms=4.5, label="not tested")], frameon=False, loc="upper left", fontsize=6.3)
    fig.tight_layout(w_pad=0.8)
    save(fig, "fig_e6_threshold_baseline")
    c0t0 = st.median(fl(r["wall_s"]) for r in runs if r["label"] == "stencil C0-t0")
    c0t51 = st.median(fl(r["wall_s"]) for r in runs if r["label"] == "stencil C0-t51")
    c7t51 = st.median(fl(r["wall_s"]) for r in runs if r["label"] == "stencil C7W512-t51")
    META["e6"] = dict(csv=f"{GE}/e6/e6_runs.csv; {GE}/e6/secondary_wall.csv; {GE}/e6/secondary_demand.csv; {GE}/e6/family1_primary.csv", fn="fig_e6", n="10 runs per cell",
        cap=(f"RTX 5070 Ti, E3a-2 module, Stencil-24K, prefetcher on: process wall-clock and demand faults of C0 (speculation off) and C7W512 (oracle, W = 512) at each prefetch threshold. "
             f"Each run is a point; markers are medians, filled when the within-threshold comparison is Holm-significant (two-sided Mann-Whitney U, n = 10 per cell), hollow when not, a plus when the cell was not tested. "
             f"The C0 median is {c0t0:.4f} s at threshold 0 against {c0t51:.4f} s at the shipped 51, and C7W512 at 51 is {c7t51:.4f} s."))


# ------------------------------------------------------------------ F-E7
WL7 = [("stencil", "Stencil\n24K", "A"), ("stencil8k", "Stencil\n8K", "B"), ("sweep4k", "Sweep\n4K", "B"), ("sweep16k", "Sweep\n16K", "B"), ("stream", "STREAM", "B"),
       ("sgemm", "SGEMM", "B"), ("cufft", "cuFFT", "B"), ("graphbfs", "GraphBFS\n23", "B"), ("oversub", "Stencil\noversub", "B")]


def fig_e7():
    fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.5), sharey=True)
    sets = (("RTX 5070 Ti (E7)", f"{GE}/e7/e7_runs.csv", f"{GE}/e7/family_a.csv", f"{GE}/e7/family_b.csv"),
            ("Tesla T4 (E7-T4)", "results/analysis/t4/e7t4_runs.csv", "results/analysis/t4/family_a.csv", "results/analysis/t4/family_b.csv"))
    counts = {}
    for ax, (name, runs_p, fa_p, fb_p) in zip(axes, sets):
        runs = [r for r in rd(runs_p)]
        fa, fb = rd(fa_p), rd(fb_p)
        n_t4 = 0
        for i, (wl, lab, fam) in enumerate(WL7):
            sub = [r for r in runs if r["workload"] == wl and r.get("family", "") == fam] if "family" in runs[0] else [r for r in runs if r["workload"] == wl]
            if not sub:
                ax.text(i, -12, "not run", rotation=90, ha="center", va="center", fontsize=6.5, color=MUTED)
                continue
            base = st.median(fl(r["wall_s"]) for r in sub if r["label"].endswith("stock-t51"))
            for arm, col, mk, dx in (("stock-t0", BLUE, "o", -0.17), ("stock-t25", ORANGE, "s", 0.17)):
                v = [fl(r["wall_s"]) for r in sub if r["label"].endswith(arm)]
                if not v:
                    continue
                pts(ax, i + dx, [pct(x, base) for x in v], col, mk, jitter=0.08)
                src = fa if fam == "A" else fb
                c = next(c for c in src if c["workload"] == wl and c["arm"] == arm)
                med_marker(ax, i + dx, fl(c["delta_pct"]), col, mk, "sig" if c["holm_sig"] == "True" else "ns", size=18)
            n_t4 += 1
        counts[name] = n_t4
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_xticks(range(len(WL7))); ax.set_xticklabels([w[1] for w in WL7], fontsize=5.6)
        ax.set_xlabel(name)
    axes[0].set_ylabel("wall-clock vs threshold 51 (%)")
    from matplotlib.lines import Line2D
    axes[0].legend(handles=[Line2D([], [], marker="o", ls="", color=BLUE, ms=3.5, label="threshold 0"), Line2D([], [], marker="s", ls="", color=ORANGE, ms=3.5, label="threshold 25"),
                            Line2D([], [], marker="o", ls="", mfc="k", mec="k", ms=3.5, label="filled: Holm-significant"), Line2D([], [], marker="o", ls="", mfc="w", mec="k", ms=3.5, label="hollow: not significant")],
                   frameon=False, loc="lower left", ncol=2, columnspacing=0.8)
    fig.tight_layout(w_pad=0.6)
    save(fig, "fig_e7_threshold_by_workload_two_platforms")
    ra = {c["arm"]: c for c in rd(f"{GE}/e7/family_a.csv")}
    ta = {c["arm"]: c for c in rd("results/analysis/t4/family_a.csv")}
    tb = rd("results/analysis/t4/family_b.csv")
    nf = sum(1 for c in tb if c["holm_sig"] == "True" and fl(c["delta_s"]) < 0)
    META["e7"] = dict(csv=f"{GE}/e7/e7_runs.csv; {GE}/e7/family_a.csv; {GE}/e7/family_b.csv; results/analysis/t4/e7t4_runs.csv; results/analysis/t4/family_a.csv; results/analysis/t4/family_b.csv",
        fn="fig_e7", n="10 runs per cell on each platform (separate analyses, never pooled)",
        cap=(f"Stock driver 595.91.07, prefetcher on, no speculation: wall-clock change of threshold 0 and 25 against the shipped threshold 51 (each cell's own median), per workload, on the RTX 5070 Ti (left) and the Tesla T4 (right); the two platforms are analysed separately and not pooled. "
             f"Each run is a point; markers are medians, filled when Holm-significant (two-sided Mann-Whitney U, n = 10 per cell; Stencil-24K shows threshold 0 only, from family A). The oversubscribed Stencil cell was not run on the T4. "
             f"On Stencil-24K the change at threshold 0 is {fl(ra['stock-t0']['delta_pct']):+.2f}% on the RTX 5070 Ti and {fl(ta['stock-t0']['delta_pct']):+.2f}% on the T4, and {nf} of {len(tb)} T4 family-B tests are significantly faster."))


# ------------------------------------------------------------------ F-E8
def fig_e8():
    runs = [r for r in rd(f"{GE}/e8/e8_runs.csv") if r["family"] in ("IN", "OV")]
    tests = rd(f"{GE}/e8/primary_tests.csv")
    fig, axes = plt.subplots(1, 2, figsize=(COL2 * 0.78, 2.45))
    Ks = (1, 8, 64, 512)
    for ax, size, fam, lab in ((axes[0], "in", "IN", "in memory (8 GiB)"), (axes[1], "ov", "OV", "oversubscribed (24 GiB)")):
        for arm, col, mk, dx in (("stock-t0", BLUE, "o", -0.14), ("stock-t25", ORANGE, "s", 0.14)):
            mx, my = [], []
            for i, K in enumerate(Ks):
                wl = f"{size}_k{K}"
                base = st.median(fl(r["wall_s"]) for r in runs if r["workload"] == wl and r["label"].endswith("stock-t51"))
                v = [fl(r["wall_s"]) for r in runs if r["workload"] == wl and r["label"].endswith(arm)]
                pts(ax, i + dx, [pct(x, base) for x in v], col, mk, jitter=0.07)
                c = next(t for t in tests if t["size"] == size and int(t["K"]) == K and t["arm"] == arm)
                med_marker(ax, i + dx, fl(c["delta_pct"]), col, mk, "sig" if c["holm_sig"] == "True" else "ns", size=18)
                mx.append(i + dx); my.append(fl(c["delta_pct"]))
            ax.plot(mx, my, color=col, lw=0.8, zorder=4)
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_xticks(range(4)); ax.set_xticklabels([f"{K}" for K in Ks])
        ax.set_xlabel(f"pages touched per 2 MB block, {lab}")
    axes[0].set_ylabel("wall-clock vs threshold 51 (%)")
    from matplotlib.lines import Line2D
    axes[0].legend(handles=[Line2D([], [], marker="o", ls="-", color=BLUE, ms=3.5, lw=0.8, label="threshold 0"), Line2D([], [], marker="s", ls="-", color=ORANGE, ms=3.5, lw=0.8, label="threshold 25")], frameon=False, loc="upper right")
    fig.tight_layout(w_pad=0.8)
    save(fig, "fig_e8_sparse_access")
    g = {(t["size"], int(t["K"]), t["arm"]): fl(t["delta_pct"]) for t in tests}
    META["e8"] = dict(csv=f"{GE}/e8/e8_runs.csv; {GE}/e8/primary_tests.csv", fn="fig_e8", n="10 runs per cell",
        cap=(f"RTX 5070 Ti, stock driver, synthetic sparse-access benchmark: wall-clock change of threshold 0 and 25 against threshold 51 as the number of pages touched per 2 MB block grows, with the array in memory (left) and 1.5x oversubscribed (right). "
             f"Each run is a point; markers are medians, filled when Holm-significant (two-sided Mann-Whitney U, one Holm family of {len(tests)} tests, n = 10 per cell). "
             f"With one page per block the change at threshold 0 is {g[('in', 1, 'stock-t0')]:+.2f}% in memory and {g[('ov', 1, 'stock-t0')]:+.2f}% oversubscribed."))


# ------------------------------------------------------------------ F-E9
def fig_e9():
    runs = rd(f"{GE}/e9/e9_runs.csv")
    wls = [("ov_k1", "oversub\nK=1"), ("ov_k8", "oversub\nK=8"), ("ov_k64", "oversub\nK=64"), ("ov_k512", "oversub\nK=512"), ("in_k1", "in-mem\nK=1"), ("in_k512", "in-mem\nK=512"), ("stencil", "Stencil\n24K")]
    fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.45))
    for ax, key, lab in ((axes[0], "htod_bytes", "host to device migrated (GiB)"), (axes[1], "dtoh_bytes", "device to host migrated (GiB)")):
        for t, col, dx in ((0, BLUE, -0.2), (51, ORANGE, 0.2)):
            xs, ys = [], []
            for i, (wl, _) in enumerate(wls):
                v = [fl(r[key]) / GIB for r in runs if r["workload"] == wl and int(r["threshold"]) == t]
                pts(ax, i + dx, v, col, jitter=0.05, size=6, alpha=0.7)
                xs.append(i + dx); ys.append(st.median(v))
            ax.bar(xs, ys, width=0.36, color=col, alpha=0.75, zorder=2, label=f"threshold {t}")
        ax.set_yscale("symlog", linthresh=0.01)
        ax.set_xticks(range(len(wls))); ax.set_xticklabels([w[1] for w in wls], fontsize=6.3)
        ax.set_ylabel(lab)
    axes[0].legend(frameon=False, loc="upper right")
    fig.tight_layout(w_pad=0.8)
    save(fig, "fig_e9_migrated_bytes")
    cm = {(r["workload"], int(r["threshold"])): r for r in rd(f"{GE}/e9/cell_medians.csv")}
    META["e9"] = dict(csv=f"{GE}/e9/e9_runs.csv; {GE}/e9/cell_medians.csv", fn="fig_e9", n="3 runs per cell (descriptive; no tests)",
        cap=(f"RTX 5070 Ti, stock driver, nsys-traced runs: unified-memory bytes migrated host to device and device to host per run at threshold 0 and at the shipped 51, for the sparse-access benchmark (oversubscribed and in memory) and Stencil-24K. "
             f"Bars are medians of 3 traced runs, points are the runs, and the axis is symmetric-logarithmic; no statistical test is applied (counts are under tracing). "
             f"With one page per block on the oversubscribed array, threshold 0 migrates {fl(cm[('ov_k1', 0)]['htod_bytes_median']) / GIB:.1f} GiB in and {fl(cm[('ov_k1', 0)]['dtoh_bytes_median']) / GIB:.1f} GiB out, against {fl(cm[('ov_k1', 51)]['htod_bytes_median']) / GIB:.1f} and {fl(cm[('ov_k1', 51)]['dtoh_bytes_median']) / GIB:.1f} GiB at 51."))


# ------------------------------------------------------------------ F-PH
def fig_ph():
    rows = [r for r in rd(f"{GE}/e1/partb_phase_totals.csv") if r["workload"] == "stencil"]
    ph = ["D1", "D2", "D3", "D4", "D5", "D6", "D7"]
    fig, ax = plt.subplots(figsize=(COL1, 2.35))
    n = {}
    for arm, col, dx, lab in (("C1", BLUE, -0.19, "C1 (no speculation, prefetcher off)"), ("C64096", ORANGE, 0.19, "C6, L = 4096 (oracle, prefetcher off)")):
        xs, ys = [], []
        for i, p in enumerate(ph):
            v = [fl(r[p]) / 1e9 for r in rows if r["arm"] == arm]
            n[arm] = len(v)
            pts(ax, i + dx, v, col, jitter=0.04, size=6, alpha=0.8)
            xs.append(i + dx); ys.append(st.median(v))
        ax.bar(xs, ys, width=0.34, color=col, alpha=0.75, zorder=2, label=lab)
    ax.set_yscale("log")
    ax.set_xticks(range(len(ph))); ax.set_xticklabels(ph)
    ax.set_xlabel("dispatch-window phase"); ax.set_ylabel("median time per run (s)")
    ax.legend(frameon=False, loc="upper right", fontsize=6.3)
    fig.tight_layout()
    save(fig, "fig_ph_phase_medians")
    med = lambda arm, p: st.median(fl(r[p]) / 1e9 for r in rows if r["arm"] == arm)  # noqa: E731
    META["ph"] = dict(csv=f"{GE}/e1/partb_phase_totals.csv", fn="fig_ph", n=f"{n['C1']} runs (C1) and {n['C64096']} runs (C6-L4096)",
        cap=(f"RTX 5070 Ti, Stencil-24K, prefetcher off, E1 Part B: median time per run spent in each phase of the fault-dispatch window (D4 is the address-space lock hold and contains D5). "
             f"Bars are medians, points are the runs; no statistical test is applied (n = {n['C1']} and {n['C64096']}). "
             f"D5 is {med('C1', 'D5'):.3f} s with C1 and {med('C64096', 'D5'):.3f} s with the oracle (C6, L = 4096)."))


FUNCS = {"e4": fig_e4, "e5": fig_e5, "e6": fig_e6, "e7": fig_e7, "e8": fig_e8, "e9": fig_e9, "ph": fig_ph}
TITLES = {"e4": ("F-E4", "Wall-clock by arm vs C0 (E4 F1, F4)"), "e5": ("F-E5", "D(t) and wall-clock vs threshold (E5)"), "e6": ("F-E6", "C0 and C7W512 vs threshold 0-51 (E6)"),
          "e7": ("F-E7", "Threshold effect per workload, two platforms (E7, E7-T4)"), "e8": ("F-E8", "Threshold effect vs sparsity (E8)"), "e9": ("F-E9", "Migrated bytes (E9)"),
          "ph": ("F-PH", "Per-phase medians, Stencil-24K C1 vs C6-L4096 (E1 Part B)")}
FILES = {"e4": "fig_e4_wallclock_by_arm", "e5": "fig_e5_threshold_dose_response", "e6": "fig_e6_threshold_baseline", "e7": "fig_e7_threshold_by_workload_two_platforms",
         "e8": "fig_e8_sparse_access", "e9": "fig_e9_migrated_bytes", "ph": "fig_ph_phase_medians"}


def main():
    style()
    names = sys.argv[1:] or list(FUNCS)
    for n in names:
        FUNCS[n]()
        print("wrote", f"{OUT}/{FILES[n]}.pdf/.png", flush=True)
    if not sys.argv[1:]:
        with open(f"{OUT}/FIGURES.md", "w") as f:
            f.write("# Paper figures (generated by `tests/make_paper_figures.py`; do not edit by hand)\n\n"
                    "One row per figure. Every number in a caption is read from the source CSV by the script. Markers: **filled** = Holm-significant median, **hollow** = not significant, "
                    "**plus** = not tested; every run is a point. Figures with n = 3 are descriptive (bars, no test). Widths: 3.5 in (single column) or 7.16 in (double column).\n\n"
                    "| figure | file (PDF and PNG in `paper/figures/`) | script function | source CSV(s) | n per cell | draft caption (at most 3 sentences) |\n|---|---|---|---|---|---|\n")
            for n in FUNCS:
                m = META[n]
                f.write(f"| {TITLES[n][0]}: {TITLES[n][1]} | `{FILES[n]}` | `{m['fn']}` | {m['csv'].replace('; ', '<br>')} | {m['n']} | {m['cap']} |\n")
    print("done")


if __name__ == "__main__":
    main()
