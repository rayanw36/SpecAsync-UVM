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
# ONE colour map for the whole paper (defined once; every figure uses it). Workloads are distinguished by marker shape only.
THR = {0: "#2a78d6", 10: "#8fbce8", 25: "#12a39a", 51: "#8a8a85", 75: "#52514e", 100: "#000000"}  # blue, light blue, teal, grey (shipped), dark grey, black
C0_COL, SPEC_COL = THR[0], "#eb6834"   # C0 (no speculation) blue; speculation arms orange
BLUE, ORANGE = C0_COL, SPEC_COL
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#d8d8d4"
MK = {"stencil": "o", "graphbfs": "o"}   # shape = allocator: every managed-memory figure uses circles (FIGURES.md, marker convention)
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
    """state: sig -> filled, ns -> hollow, untested -> plus, sigmde -> filled with a white x (Holm-significant but |delta| below the achieved-n MDE)."""
    if state == "sigmde":
        ax.scatter([x], [y], s=size, marker=marker, facecolor=color, edgecolor=color, linewidths=1.0, zorder=5)
        ax.scatter([x], [y], s=size * 0.55, marker="x", color="white", linewidths=0.9, zorder=6)
    elif state == "untested":
        ax.scatter([x], [y], s=size * 1.2, marker="P", facecolor="white", edgecolor=color, linewidths=1.0, zorder=5)
    elif state == "sig":
        ax.scatter([x], [y], s=size, marker=marker, facecolor=color, edgecolor=color, linewidths=1.0, zorder=5)
    else:
        ax.scatter([x], [y], s=size, marker=marker, facecolor="white", edgecolor=color, linewidths=1.1, zorder=5)


def pct(v, base):
    return 100.0 * (v / base - 1.0)


def save(fig, name, sub=""):
    d = f"{OUT}/{sub}".rstrip("/")
    os.makedirs(d, exist_ok=True)
    fig.savefig(f"{d}/{name}.pdf", bbox_inches="tight")
    fig.savefig(f"{d}/{name}.png", bbox_inches="tight")
    plt.close(fig)


def panel(ax, letter, dx=-0.13):
    ax.text(dx, 1.03, f"({letter})", transform=ax.transAxes, fontsize=8.5, fontweight="bold", va="bottom", ha="left")


def legend_state(ax, loc="best", fig=None):
    from matplotlib.lines import Line2D
    h = [Line2D([], [], marker="o", ls="", mfc="k", mec="k", ms=4, label="Holm-significant"),
         Line2D([], [], marker="o", ls="", mfc="w", mec="k", ms=4, label="not significant"),
         Line2D([], [], marker="o", ls="", mfc="k", alpha=0.45, mec="none", ms=2.5, label="one run")]
    if fig is not None:   # outside the axes, below, so no data point is covered
        fig.legend(handles=h, frameon=False, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.07), handletextpad=0.3)
    else:
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
            pts(ax, i, [pct(v, base) for v in w], SPEC_COL, MK[wl], jitter=0.12)
            c = row("F1", wl, arm)
            med_marker(ax, i, fl(c["delta_pct"]), SPEC_COL, MK[wl], "sig" if c["holm_sig"] == "True" else "ns")
            n_cell[(wl, arm)] = len(w)
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_xticks(range(3)); ax.set_xticklabels(["W=1", "W=64", "W=512"])
        ax.set_xlabel(f"{ttl}: staging width (cheap oracle, prefetcher on)")
    axes[0].set_ylabel("wall-clock vs C0 median (%)")
    legend_state(axes[0], "upper right")
    ax = axes[2]
    for i, (wl, col, mk) in enumerate((("stencil", SPEC_COL, MK["stencil"]), ("graphbfs", SPEC_COL, MK["graphbfs"]))):
        base = st.median(wall(wl, "C0"))
        w = wall(wl, "C6-W512")
        pts(ax, i, [pct(v, base) for v in w], col, marker=mk, jitter=0.1)
        c = row("F4", wl, "C6-W512")
        med_marker(ax, i, fl(c["delta_pct"]), col, mk, "sig" if c["holm_sig"] == "True" else "ns")
        ax.annotate(f"{fl(c['delta_pct']):+.1f}%", (i, fl(c["delta_pct"])), xytext=(8, 7), textcoords="offset points", fontsize=7, ha="left", va="center")
    ax.set_xlim(-0.5, 1.9)
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
    fig, axes = plt.subplots(2, 1, figsize=(COL1, 4.3), sharex=True)
    for i, t in enumerate((51, 75, 100)):
        c0f = st.median(vals("C0", t, "demand_faults"))
        pts(axes[0], i, [1 - v / c0f for v in vals("C7W512", t, "demand_faults")], SPEC_COL, jitter=0.1)
        med_marker(axes[0], i, fl(fr[t]["D"]), SPEC_COL, "o", "sig" if fr[t]["holm_sig"] == "True" else "ns")
        c0w = st.median(vals("C0", t, "wall_s"))
        pts(axes[1], i, [pct(v, c0w) for v in vals("C7W512", t, "wall_s")], SPEC_COL, "o", jitter=0.1)
        med_marker(axes[1], i, fl(wc[t]["delta_pct"]), SPEC_COL, "o", "sig" if wc[t]["holm_sig"] == "True" else "ns")
    for ax in axes:
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_xticks(range(3)); ax.set_xticklabels(["51\n(shipped)", "75", "100\n(rule off)"])
    axes[1].set_xlabel("uvm_perf_prefetch_threshold")
    axes[0].set_ylabel("demand-fault reduction D(t)")
    axes[1].set_ylabel("wall-clock vs C0, same t (%)")
    panel(axes[0], "a", -0.19); panel(axes[1], "b", -0.19)
    fig.tight_layout(h_pad=1.0)
    legend_state(axes[0], fig=fig)
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
    fig, axes = plt.subplots(2, 1, figsize=(COL1, 4.4), sharex=True)
    c7t51_med = st.median(fl(r["wall_s"]) for r in runs if r["label"] == "stencil C7W512-t51")
    axes[0].axhline(c7t51_med, color=SPEC_COL, ls="--", lw=0.8, zorder=1)
    axes[0].text(0, c7t51_med + 0.003, "C7W512 at shipped threshold", color=SPEC_COL, fontsize=6, va="bottom", ha="left")
    for ax, key, ylab, secd in ((axes[0], "wall_s", "process wall-clock (s)", sw), (axes[1], "demand_faults", "demand faults per run", sd)):
        for arm, col, mk, dx in (("C0", C0_COL, "o", -0.9), ("C7W512", SPEC_COL, "o", 0.9)):
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
        ax.set_ylabel(ylab)
    axes[1].set_xlabel("uvm_perf_prefetch_threshold")
    panel(axes[0], "a", -0.19); panel(axes[1], "b", -0.19)
    from matplotlib.lines import Line2D
    fig.tight_layout(h_pad=1.0)
    fig.legend(handles=[Line2D([], [], marker="o", ls="-", color=C0_COL, ms=3.5, lw=0.8, label="C0 (speculation off)"),
                        Line2D([], [], marker="o", ls="-", color=SPEC_COL, ms=3.5, lw=0.8, label="C7W512 (oracle, W = 512)"),
                        Line2D([], [], marker="o", ls="", mfc="k", mec="k", ms=3.5, label="filled: Holm-significant"),
                        Line2D([], [], marker="o", ls="", mfc="w", mec="k", ms=3.5, label="hollow: not significant"),
                        Line2D([], [], marker="P", ls="", mfc="w", mec="k", ms=4.5, label="plus: not tested"),
                        Line2D([], [], marker="o", ls="", mfc="k", alpha=0.45, mec="none", ms=2.5, label="one run")],
               frameon=False, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.1), fontsize=6.5, handletextpad=0.3)
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
            for arm, col, mk, dx in (("stock-t0", THR[0], "o", -0.17), ("stock-t25", THR[25], "o", 0.17)):
                v = [fl(r["wall_s"]) for r in sub if r["label"].endswith(arm)]
                if not v:
                    continue
                pts(ax, i + dx, [pct(x, base) for x in v], col, mk, jitter=0.08)
                src = fa if fam == "A" else fb
                c = next(c for c in src if c["workload"] == wl and c["arm"] == arm)
                state = "ns" if c["holm_sig"] != "True" else ("sigmde" if (wl == "graphbfs" and abs(fl(c["delta_s"])) < fl(c["mde_s"])) else "sig")
                med_marker(ax, i + dx, fl(c["delta_pct"]), col, mk, state, size=18)
            n_t4 += 1
        counts[name] = n_t4
        ax.axhline(0, color=THR[51], lw=0.8)
        ax.set_xticks(range(len(WL7))); ax.set_xticklabels([w[1] for w in WL7], fontsize=5.6)
        ax.set_xlabel(name)
    axes[0].set_ylabel("wall-clock vs threshold 51 (%)")
    from matplotlib.lines import Line2D
    fig.tight_layout(w_pad=0.6)
    from matplotlib.lines import Line2D
    from matplotlib.legend_handler import HandlerTuple
    fig.legend(handles=[Line2D([], [], marker="o", ls="", color=THR[0], ms=3.5, label="threshold 0"), Line2D([], [], marker="o", ls="", color=THR[25], ms=3.5, label="threshold 25"),
                        Line2D([], [], ls="-", color=THR[51], lw=0.8, label="threshold 51 (shipped baseline)"),
                        Line2D([], [], marker="o", ls="", mfc="k", mec="k", ms=3.5, label="filled: Holm-significant"), Line2D([], [], marker="o", ls="", mfc="w", mec="k", ms=3.5, label="hollow: not significant"),
                        (Line2D([], [], marker="o", ls="", mfc="k", mec="k", ms=4.5), Line2D([], [], marker="x", ls="", color="white", ms=3.2, mew=0.9))],
               labels=["threshold 0", "threshold 25", "threshold 51 (shipped baseline)", "filled: Holm-significant", "hollow: not significant",
                       "filled with white x: GraphBFS-23, Holm-significant but |delta| below its MDE"],
               handler_map={tuple: HandlerTuple(ndivide=1, pad=0)},
               frameon=False, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.12), fontsize=6.5, handletextpad=0.3)
    save(fig, "fig_e7_threshold_by_workload_two_platforms")
    ra = {c["arm"]: c for c in rd(f"{GE}/e7/family_a.csv")}
    ta = {c["arm"]: c for c in rd("results/analysis/t4/family_a.csv")}
    tb = rd("results/analysis/t4/family_b.csv")
    nf = sum(1 for c in tb if c["holm_sig"] == "True" and fl(c["delta_s"]) < 0)
    gb = [c for c in tb if c["workload"] == "graphbfs"]
    gb_pct = max(abs(fl(c["delta_pct"])) for c in gb)
    gb_base = st.median(fl(c["median_base"]) for c in gb)
    assert all(c["holm_sig"] == "True" and abs(fl(c["delta_s"])) < fl(c["mde_s"]) for c in gb), "GraphBFS-23 rule no longer holds"
    META["e7"] = dict(csv=f"{GE}/e7/e7_runs.csv; {GE}/e7/family_a.csv; {GE}/e7/family_b.csv; results/analysis/t4/e7t4_runs.csv; results/analysis/t4/family_a.csv; results/analysis/t4/family_b.csv",
        fn="fig_e7", n="10 runs per cell on each platform (separate analyses, never pooled)",
        cap=(f"Stock driver 595.91.07, prefetcher on, no speculation: wall-clock change of threshold 0 and 25 against the shipped threshold 51 (each cell's own median), per workload, on the RTX 5070 Ti (left) and the Tesla T4 (right); the two platforms are analysed separately and not pooled. "
             f"Each run is a point; markers are medians, filled when Holm-significant (two-sided Mann-Whitney U, n = 10 per cell; Stencil-24K shows threshold 0 only, from family A). The oversubscribed Stencil cell was not run on the T4. "
             f"On Stencil-24K the change at threshold 0 is {fl(ra['stock-t0']['delta_pct']):+.2f}% on the RTX 5070 Ti and {fl(ta['stock-t0']['delta_pct']):+.2f}% on the T4, and {nf} of {len(tb)} T4 family-B tests are significantly faster; GraphBFS-23's changes ({gb_pct:.1f}% of a {gb_base:.0f} s run) are below its minimum detectable effect (white x)."))


# ------------------------------------------------------------------ F-E8
def fig_e8():
    runs = [r for r in rd(f"{GE}/e8/e8_runs.csv") if r["family"] in ("IN", "OV")]
    tests = rd(f"{GE}/e8/primary_tests.csv")
    fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.6))
    Ks = (1, 8, 64, 512)
    for ax, size, fam, lab in ((axes[0], "in", "IN", "in memory (8 GiB)"), (axes[1], "ov", "OV", "oversubscribed (24 GiB)")):
        for arm, col, mk, dx in (("stock-t0", THR[0], "o", -0.14), ("stock-t25", THR[25], "o", 0.14)):
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
        ax.axhline(0, color=THR[51], lw=0.8)
        ax.set_xticks(range(4)); ax.set_xticklabels([f"{K}" for K in Ks])
        ax.set_xlabel(f"pages touched per 2 MB block, {lab}")
    axes[0].set_ylabel("wall-clock vs threshold 51 (%)")
    from matplotlib.lines import Line2D
    axes[0].legend(handles=[Line2D([], [], marker="o", ls="-", color=THR[0], ms=3.5, lw=0.8, label="threshold 0"), Line2D([], [], marker="o", ls="-", color=THR[25], ms=3.5, lw=0.8, label="threshold 25"), Line2D([], [], ls="-", color=THR[51], lw=0.8, label="threshold 51 (shipped baseline)")], frameon=False, loc="upper right")
    panel(axes[0], "a", -0.1); panel(axes[1], "b", -0.1)
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
    wls = [("ov_k1", "oversub\nK=1"), ("ov_k8", "oversub\nK=8"), ("ov_k64", "oversub\nK=64"), ("ov_k512", "oversub\nK=512"), ("in_k1", "in-mem\nK=1"), ("in_k512", "in-mem\nK=512"), ("stencil", "Stencil-24K")]
    fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.6))
    for ax, key, lab in ((axes[0], "htod_bytes", "host to device migrated (GiB)"), (axes[1], "dtoh_bytes", "device to host migrated (GiB)")):
        for t, col, dx in ((0, THR[0], -0.2), (51, THR[51], 0.2)):
            xs, ys = [], []
            for i, (wl, _) in enumerate(wls):
                v = [fl(r[key]) / GIB for r in runs if r["workload"] == wl and int(r["threshold"]) == t]
                pts(ax, i + dx, v, col, jitter=0.05, size=6, alpha=0.7)
                xs.append(i + dx); ys.append(st.median(v))
            ax.bar(xs, ys, width=0.36, color=col, alpha=0.75, zorder=2, label=f"threshold {t}")
        ax.set_yscale("symlog", linthresh=0.01)
        ax.set_xticks(range(len(wls))); ax.set_xticklabels([w[1] for w in wls], fontsize=5.8)
        ax.set_ylabel(lab)
    axes[0].legend(frameon=False, loc="upper right")
    panel(axes[0], "a", -0.1); panel(axes[1], "b", -0.1)
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
    for arm, col, dx, lab in (("C1", C0_COL, -0.19, "C1 (no speculation, prefetcher off)"), ("C64096", SPEC_COL, 0.19, "C6, L = 4096 (oracle, prefetcher off)")):
        xs, ys = [], []
        for i, p in enumerate(ph):
            v = [fl(r[p]) / 1e9 for r in rows if r["arm"] == arm]
            n[arm] = len(v)
            pts(ax, i + dx, v, col, jitter=0.04, size=6, alpha=0.8)
            xs.append(i + dx); ys.append(st.median(v))
        ax.bar(xs, ys, width=0.34, color=col, alpha=0.75, zorder=2, label=lab)
        ax.annotate(f"{ys[ph.index('D5')]:.3f} s", (xs[ph.index("D5")], ys[ph.index("D5")]), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=6.5, color=col)
    ax.set_xticks(range(len(ph))); ax.set_xticklabels(ph)
    ax.set_xlabel("dispatch-window phase"); ax.set_ylabel("median time per run (s)")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.08)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=1, fontsize=6.5)
    fig.tight_layout()
    save(fig, "fig_ph_phase_medians")
    med = lambda arm, p: st.median(fl(r[p]) / 1e9 for r in rows if r["arm"] == arm)  # noqa: E731
    META["ph"] = dict(csv=f"{GE}/e1/partb_phase_totals.csv", fn="fig_ph", n=f"{n['C1']} runs (C1) and {n['C64096']} runs (C6-L4096)",
        cap=(f"RTX 5070 Ti, Stencil-24K, prefetcher off, E1 Part B: median time per run spent in each phase of the fault-dispatch window (D4 is the address-space lock hold and contains D5). "
             f"Bars are medians, points are the runs; no statistical test is applied (n = {n['C1']} and {n['C64096']}). "
             f"D5 is {med('C1', 'D5'):.3f} s with C1 and {med('C64096', 'D5'):.3f} s with the oracle (C6, L = 4096)."))


# ------------------------------------------------------------------ H2 (HMM vs managed): fig_h2_hmm and its supplementary single-panel versions
H2 = f"{GE}/h2"
H2KS = (1, 8, 64, 512)
H2_ROWS = []   # CSV fallback rows for fig_h2_hmm (panel, allocator, instrument, K, threshold, run, value)


def h2_panel_a(ax, rows_out):
    """Wall-clock change of t0 against t51 (%), against K (log-2 axis). symlog y with a linear region of +-20%. Managed circle, HMM triangle; filled = Holm-significant."""
    runs, tests = rd(f"{H2}/h2_runs.csv"), {(t["alloc"], int(t["K"])): t for t in rd(f"{H2}/h2_tests.csv")}
    col = THR[0]
    for alloc, mk, dx, ls, lab in (("managed", "o", -0.12, "-", "managed (UVM)"), ("malloc", "^", 0.12, "--", "HMM (malloc)")):
        xs, ys = [], []
        for K in H2KS:
            wl = f"{alloc}_k{K}"
            base = st.median(fl(r["wall_s"]) for r in runs if r["workload"] == wl and int(r["threshold"]) == 51)
            v = [pct(fl(r["wall_s"]), base) for r in runs if r["workload"] == wl and int(r["threshold"]) == 0]
            x = K * 2 ** dx
            n = len(v)
            ax.scatter([x * 2 ** (0.06 * ((i / max(n - 1, 1)) - 0.5) * 2) for i in range(n)], v, s=6, marker=mk, color=col, alpha=0.5, linewidths=0, zorder=3)
            t = tests[(alloc, K)]
            med_marker(ax, x, fl(t["delta_pct"]), col, mk, "sig" if t["holm_sig"] == "True" else "ns", size=26)
            xs.append(x); ys.append(fl(t["delta_pct"]))
            rows_out += [["a", alloc, "wall-clock", K, 0, i + 1, f"{y:.4f}"] for i, y in enumerate(v)] + [["a", alloc, "wall-clock", K, 0, "median", f"{fl(t['delta_pct']):.4f}"]]
        ax.plot(xs, ys, color=col, lw=0.8, ls=ls, zorder=4)
    ax.axhline(0, color=THR[51], lw=0.8)
    ax.set_xscale("log", base=2)
    ax.set_xticks(H2KS); ax.set_xticklabels([str(k) for k in H2KS]); ax.minorticks_off()
    ax.set_yscale("symlog", linthresh=20, linscale=1.0)
    ax.set_yticks([-20, -10, 0, 10, 20, 50, 100, 200]); ax.set_yticklabels(["-20", "-10", "0", "10", "20", "50", "100", "200"])
    ax.set_ylim(-35, 260)
    ax.set_xlabel("pages touched per 2 MB block (K)")
    ax.set_ylabel("threshold 0 vs 51, wall-clock change (%)")


def h2_panel_b(ax, rows_out):
    """Fraction of the 8 GiB array made resident. HMM: memory.used residency (triangles, valid for 4 KB chunks); managed: E9 traced HtoD (squares, K = 1 and 512 only). Descriptive (n = 3): filled."""
    res, e9 = rd(f"{H2}/residency_summary.csv"), rd(f"{GE}/e9/e9_runs.csv")
    for t, dx in ((0, -0.45), (51, -0.15)):
        xs, ys = [], []
        for K in H2KS:
            v = [fl(r["residency_frac_8gib"]) for r in res if r["workload"] == f"malloc_k{K}" and int(r["threshold"]) == t]
            x = K * 2 ** dx
            ax.scatter([x] * len(v), v, s=6, marker="^", color=THR[t], alpha=0.6, linewidths=0, zorder=3)
            med_marker(ax, x, st.median(v), THR[t], "^", "sig", size=26)
            xs.append(x); ys.append(st.median(v))
            rows_out += [["b", "malloc", "memory.used residency", K, t, i + 1, f"{y:.4f}"] for i, y in enumerate(v)]
        ax.plot(xs, ys, color=THR[t], lw=0.8, zorder=4)
    for t, dx in ((0, 0.15), (51, 0.45)):
        for K in (1, 512):
            v = [fl(r["htod_bytes"]) / 2 ** 33 for r in e9 if r["workload"] == f"in_k{K}" and int(r["threshold"]) == t]
            x = K * 2 ** dx
            ax.scatter([x] * len(v), v, s=6, marker="s", color=THR[t], alpha=0.6, linewidths=0, zorder=3)
            med_marker(ax, x, st.median(v), THR[t], "s", "sig", size=26)
            rows_out += [["b", "managed", "traced HtoD (E9)", K, t, i + 1, f"{y:.4f}"] for i, y in enumerate(v)]
    ax.axhline(1.0, color=MUTED, lw=0.5, ls=":")
    ax.set_xscale("log", base=2)
    ax.set_xticks(H2KS); ax.set_xticklabels([str(k) for k in H2KS]); ax.minorticks_off()
    ax.set_ylim(-0.03, 1.12)
    ax.set_xlabel("pages touched per 2 MB block (K)")
    ax.set_ylabel("fraction of the 8 GiB array made resident")


def h2_legend(fig, panels):
    from matplotlib.lines import Line2D
    h = []
    if "a" in panels:
        h += [Line2D([], [], marker="o", ls="-", color=THR[0], ms=4, lw=0.8, label="managed (UVM), solid"), Line2D([], [], marker="^", ls="--", color=THR[0], ms=4, lw=0.8, label="HMM (malloc), dashed"),
              Line2D([], [], marker="o", ls="", mfc="k", mec="k", ms=4, label="filled: Holm-significant"), Line2D([], [], marker="o", ls="", mfc="w", mec="k", ms=4, label="hollow: not significant")]
    if "b" in panels:
        h += [Line2D([], [], marker="o", ls="", color=THR[0], ms=4, label="threshold 0"), Line2D([], [], marker="o", ls="", color=THR[51], ms=4, label="threshold 51 (shipped)"),
              Line2D([], [], marker="^", ls="", mfc="k", mec="k", ms=4, label="HMM, memory.used residency"), Line2D([], [], marker="s", ls="", mfc="k", mec="k", ms=4, label="managed, traced HtoD (E9)")]
    h += [Line2D([], [], marker="o", ls="", mfc="k", alpha=0.5, mec="none", ms=2.5, label="one run")]
    fig.legend(handles=h, frameon=False, loc="lower center", ncol=4 if len(panels) == 2 else 2, bbox_to_anchor=(0.5, -0.12 if len(panels) == 2 else -0.2), fontsize=6.3, handletextpad=0.3)


def h2_caption_nums():
    T = {(t["alloc"], int(t["K"])): t for t in rd(f"{H2}/h2_tests.csv")}
    return {k: fl(v["delta_pct"]) for k, v in T.items()}


def fig_h2_hmm():
    rows = []
    fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.9))
    h2_panel_a(axes[0], rows); h2_panel_b(axes[1], rows)
    panel(axes[0], "a", -0.1); panel(axes[1], "b", -0.1)
    fig.tight_layout(w_pad=1.2)
    h2_legend(fig, "ab")
    save(fig, "fig_h2_hmm")
    with open(f"{OUT}/fig_h2_hmm.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["panel", "allocator", "instrument", "K", "threshold", "run", "value"]); w.writerows(rows)
    d = h2_caption_nums()
    META["h2"] = dict(csv=f"{H2}/h2_runs.csv; {H2}/h2_tests.csv; {H2}/residency_summary.csv; {GE}/e9/e9_runs.csv", fn="fig_h2_hmm", n="10 runs per timing cell; 3 runs per residency cell (descriptive)",
        cap=(f"RTX 5070 Ti, stock driver, 8 GiB array in memory. (a) Wall-clock change of threshold 0 against 51 on managed and on system-allocated (HMM, malloc) memory; symmetric-logarithmic y axis, linear within +-20%; each run is a point, markers are medians, filled when Holm-significant (two-sided Mann-Whitney U, one Holm family of 8, n = 10 per cell). "
             f"At K = 1 the change is {d[('malloc', 1)]:+.2f}% on HMM and {d[('managed', 1)]:+.2f}% on managed memory. (b) Fraction of the array made resident: HMM from nvidia-smi memory.used (valid for 4 KB chunks), managed from nsys traced host-to-device bytes of E9, a different session; "
             f"descriptive, n = 3, no test. Managed memory.used is not plotted because it measures allocated 2 MB chunks (catalog #31)."))


def fig_h2_time():
    rows = []
    fig, ax = plt.subplots(figsize=(COL1, 2.6))
    h2_panel_a(ax, rows)
    fig.tight_layout(); h2_legend(fig, "a")
    save(fig, "F-H2-time", "supplementary")
    with open(f"{OUT}/supplementary/F-H2-time.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["panel", "allocator", "instrument", "K", "threshold", "run", "value"]); w.writerows(rows)
    d = h2_caption_nums()
    META["h2t"] = dict(csv=f"{H2}/h2_runs.csv; {H2}/h2_tests.csv", fn="fig_h2_time", n="10 runs per cell",
        cap=(f"RTX 5070 Ti, stock driver, 8 GiB array in memory: wall-clock change of threshold 0 against 51 on managed and HMM memory (panel (a) of fig_h2_hmm alone). Symmetric-logarithmic y axis (linear within +-20%); each run is a point, markers are medians, filled when Holm-significant (n = 10 per cell). "
             f"At K = 512 the change is {d[('malloc', 512)]:+.2f}% on HMM and {d[('managed', 512)]:+.2f}% on managed memory."))


def fig_h2_res():
    rows = []
    fig, ax = plt.subplots(figsize=(COL1, 2.6))
    h2_panel_b(ax, rows)
    fig.tight_layout(); h2_legend(fig, "b")
    save(fig, "F-H2-res", "supplementary")
    with open(f"{OUT}/supplementary/F-H2-res.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["panel", "allocator", "instrument", "K", "threshold", "run", "value"]); w.writerows(rows)
    META["h2r"] = dict(csv=f"{H2}/residency_summary.csv; {GE}/e9/e9_runs.csv", fn="fig_h2_res", n="3 runs per cell (descriptive; no tests)",
        cap=("RTX 5070 Ti, stock driver, 8 GiB array in memory: fraction of the array made resident (panel (b) of fig_h2_hmm alone). Two instruments from different sessions: HMM nvidia-smi memory.used (valid for 4 KB chunks) and managed nsys traced host-to-device bytes (E9, K = 1 and 512 only). "
             "Descriptive, no test; managed memory.used is not plotted because it measures allocated 2 MB chunks (catalog #31)."))


def fig_h1():
    rows = [r for r in rd(f"{GE}/h1/h1_runs.csv") if r["exit_code"] == "0"]
    tests = {t["workload"]: t for t in rd(f"{GE}/h1/h1_tests.csv") if t["arm"] == "stock-t0"}
    names = [("stencil", "Stencil-24K"), ("in_k512", "sparse in memory\nK=512"), ("in_k1", "sparse in memory\nK=1")]
    wall = lambda w, t: [fl(r["wall_s"]) for r in rows if r["workload"] == w and r["label"].endswith(f"stock-t{t}")]  # noqa: E731
    fig, ax = plt.subplots(figsize=(COL1 * 1.25, 2.5))
    out = []
    for i, (w, lab) in enumerate(names):
        b = st.median(wall(w, 51))
        v0, v51 = [100 * (x / b - 1) for x in wall(w, 0)], [100 * (x / b - 1) for x in wall(w, 51)]
        pts(ax, i + 0.17, v0, THR[0], "^", jitter=0.06, size=6, alpha=0.5)
        med_marker(ax, i + 0.17, fl(tests[w]["delta_pct"]), THR[0], "^", "sig" if tests[w]["holm_sig"] == "True" else "ns", size=26)
        pts(ax, i - 0.17, v51, THR[51], "^", jitter=0.06, size=6, alpha=0.5)
        med_marker(ax, i - 0.17, 0.0, THR[51], "^", "untested", size=26)
        out += [[w, 0, j + 1, f"{x:.3f}"] for j, x in enumerate(wall(w, 0))] + [[w, 51, j + 1, f"{x:.3f}"] for j, x in enumerate(wall(w, 51))]
    ax.axhline(0, color=THR[51], lw=0.8)
    ax.set_xticks(range(len(names))); ax.set_xticklabels([n[1] for n in names], fontsize=6.3)
    ax.set_ylabel("wall-clock vs t51 median (%)")
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker="^", ls="", color=THR[0], ms=4, label="HMM, threshold 0"), Line2D([], [], marker="^", ls="", color=THR[51], ms=4, label="HMM, threshold 51 (shipped)"),
                       Line2D([], [], marker="^", ls="", mfc="k", mec="k", ms=4, label="filled: Holm-significant"), Line2D([], [], marker="^", ls="", mfc="w", mec="k", ms=4, label="hollow: not significant"),
                       Line2D([], [], marker="P", ls="", mfc="w", mec="k", ms=4.5, label="plus: reference, not tested")], frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, fontsize=6.3)
    fig.tight_layout()
    save(fig, "F-H1", "supplementary")
    with open(f"{OUT}/supplementary/F-H1.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["workload", "threshold", "run", "wall_s"]); w.writerows(out)
    META["h1"] = dict(csv=f"{GE}/h1/h1_runs.csv; {GE}/h1/h1_tests.csv", fn="fig_h1", n="10 runs per cell",
        cap=(f"RTX 5070 Ti, stock driver, system-allocated (HMM, malloc) memory, H1 Amendment 1: wall-clock of threshold 0 relative to the median at threshold 51, for Stencil-24K and the in-memory sparse benchmark at K = 512 and K = 1. Each run is a point; markers are medians, filled when Holm-significant (n = 10 per cell). "
             f"At K = 1 the change is {fl(tests['in_k1']['delta_pct']):+.2f}% and on Stencil-24K {fl(tests['stencil']['delta_pct']):+.2f}%."))


FUNCS = {"e4": fig_e4, "e5": fig_e5, "e6": fig_e6, "e7": fig_e7, "e8": fig_e8, "e9": fig_e9, "ph": fig_ph, "h2": fig_h2_hmm, "h2t": fig_h2_time, "h2r": fig_h2_res, "h1": fig_h1}
TITLES = {"e4": ("F-E4", "Wall-clock by arm vs C0 (E4 F1, F4)"), "e5": ("F-E5", "D(t) and wall-clock vs threshold (E5)"), "e6": ("F-E6", "C0 and C7W512 vs threshold 0-51 (E6)"),
          "e7": ("F-E7", "Threshold effect per workload, two platforms (E7, E7-T4)"), "e8": ("F-E8", "Threshold effect vs sparsity (E8)"), "e9": ("F-E9", "Migrated bytes (E9)"),
          "ph": ("F-PH", "Per-phase medians, Stencil-24K C1 vs C6-L4096 (E1 Part B)"), "h2": ("F-H2", "HMM vs managed: timing and residency (H1, H2, E9)"),
          "h2t": ("F-H2-time (supplementary)", "H2 timing, panel (a) alone"), "h2r": ("F-H2-res (supplementary)", "H2 residency, panel (b) alone"), "h1": ("F-H1 (supplementary)", "H1 Amendment 1 on HMM")}
FILES = {"e4": "fig_e4_wallclock_by_arm", "e5": "fig_e5_threshold_dose_response", "e6": "fig_e6_threshold_baseline", "e7": "fig_e7_threshold_by_workload_two_platforms",
         "e8": "fig_e8_sparse_access", "e9": "fig_e9_migrated_bytes", "ph": "fig_ph_phase_medians", "h2": "fig_h2_hmm", "h2t": "supplementary/F-H2-time", "h2r": "supplementary/F-H2-res", "h1": "supplementary/F-H1"}


def main():
    style()
    names = sys.argv[1:] or list(FUNCS)
    for n in names:
        FUNCS[n]()
        print("wrote", f"{OUT}/{FILES[n]}.pdf/.png", flush=True)
    from PIL import Image
    for n in names:
        im = Image.open(f"{OUT}/{FILES[n]}.png")
        META[n]["w"] = f"{im.size[0] / 300:.2f} x {im.size[1] / 300:.2f}"
        print(f"  width x height of {FILES[n]}: {META[n]['w']} in", flush=True)
    if not sys.argv[1:]:
        with open(f"{OUT}/FIGURES.md", "w") as f:
            f.write("# Paper figures (generated by `tests/make_paper_figures.py`; do not edit by hand)\n\n"
                    "One row per figure. Every number in a caption is read from the source CSV by the script.\n\n"
                    "## Marker convention (one for every figure in the paper)\n\n"
                    "Three channels, each carrying one thing:\n\n"
                    "- **Colour = threshold**: t0 blue, t10 light blue, t25 teal, t51 grey (the shipped default). Where a figure compares speculation arms at each threshold (F-E5, F-E6), colour is the arm (C0 blue, C7W512 orange) and the threshold is on the x axis; the legend says so.\n"
                    "- **Fill = significance**: filled = Holm-significant median, hollow = not significant, plus (P) = not tested (a reference or untested cell). A white x on a filled marker = Holm-significant but below the minimum detectable effect (F-E7, GraphBFS-23).\n"
                    "- **Shape = allocator or instrument**: circle = managed (UVM) memory, triangle = system-allocated (HMM, `malloc`) memory; in residency plots a square = the managed traced-bytes instrument (E9, nsys). Every non-H figure is managed memory, so it uses circles only.\n\n"
                    "Every run is a small point (alpha 0.5). **Descriptive panels** (n = 3, no test: F-E9, F-PH and the residency panel of F-H2) use filled markers or bars, and their captions say that they are descriptive. "
                    "Widths: 3.5 in (single column, `figure` with `\\columnwidth`) or 7.16 in (double column, `figure*` with `\\textwidth`); the table below gives the generated size of the saved PNG (tight bounding box, so within about 1% of the nominal width). Two-panel figures carry (a) and (b) labels.\n\n"
                    "**F-H2 (`fig_h2_hmm`) axis choice:** panel (a) uses a symmetric-logarithmic y axis (`symlog`, linear region +-20%, ticks -20 to 200) so that managed memory's -10% and HMM's +204% (K = 1) are both readable; the x axis is log-2 in K. "
                    "Panel (b): HMM `memory.used` residency (valid for 4 KB chunks) and managed nsys traced bytes from a different session; managed `memory.used` is not plotted because it measures allocated 2 MB chunks (catalog #31). "
                    "The CSV fallback `fig_h2_hmm.csv` has columns panel, allocator, instrument, K, threshold, run, value. The single-panel versions F-H2-time and F-H2-res, and F-H1, are in `supplementary/`; the C11 versions are in `retired/`.\n\n"
                    "| figure | file (PDF and PNG in `paper/figures/`) | script function | source CSV(s) | n per cell | size (in, w x h) | draft caption (at most 3 sentences) |\n|---|---|---|---|---|---|---|\n")
            for n in FUNCS:
                m = META[n]
                f.write(f"| {TITLES[n][0]}: {TITLES[n][1]} | `{FILES[n]}` | `{m['fn']}` | {m['csv'].replace('; ', '<br>')} | {m['n']} | {m['w']} | {m['cap']} |\n")
    print("done")


if __name__ == "__main__":
    main()
