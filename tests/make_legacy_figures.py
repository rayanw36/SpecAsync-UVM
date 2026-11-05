#!/usr/bin/env python3
"""Gate C8 phase 5: regenerate legacy figures F1, F2, F3 and F10 into paper/figures/legacy/ from COMMITTED CSVs, on the shared colour map of
tests/make_paper_figures.py (C0 blue, speculation arms orange, thresholds as there). Every run is a point and the median a larger marker where per-run data
exist. Every arm driven by the pre-E0.5 oracle (policy 4 / C3) is labelled "misaligned oracle (pre-E0.5)" (catalog #1, #13, AC-13); no caption says
"upper bound" or "oracle-perfect". Panels that rested on `spec_hits` hit rates (F1's hit-rate panel, F3's panel A) are not rebuilt (SUPERSEDED_VALUES.md;
EXISTING_FIGURES_ASSESSMENT.md). The legacy PDFs in results/figures/ are untouched.
usage: make_legacy_figures.py   -> paper/figures/legacy/f{1,2,3,10}_*.pdf|png and paper/figures/legacy/LEGACY.md
"""
import csv
import os
import statistics as st
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, "tests")
sys.path.insert(0, "tools/figures")
import make_paper_figures as M  # noqa: E402  (colour map, style, helpers)
from _fig_common import find_exclusion, load_exclusion_manifest  # noqa: E402

OUT = "paper/figures/legacy"
MIS = "misaligned oracle (pre-E0.5)"
GREY = M.THR[51]
DARK = M.THR[75]
META = {}


def rd(p):
    return list(csv.DictReader(open(p)))


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(f"{OUT}/{name}.pdf", bbox_inches="tight")
    fig.savefig(f"{OUT}/{name}.png", bbox_inches="tight")
    plt.close(fig)


def pct(v, b):
    return 100.0 * (v / b - 1.0)


# ------------------------------------------------------------------ F1: policy wall-time deltas
def f1():
    manifest = load_exclusion_manifest()
    tim = rd("results/phaseB/phaseB_timing.csv")
    gate_d = {("Stencil", "24000"): "stencil", ("GraphBFS", "23"): "graphbfs", ("Stencil_OvSub", "28300_20_11264"): "stencil_ovsub"}
    rows = {}
    for r in tim:
        rows[(r["benchmark"], r["size"], int(r["policy"]))] = float(r["median_ms"]) / 1000.0
    cells = []
    for bench in ("GraphBFS", "SGEMM", "STREAM", "Stencil", "Stencil_OvSub", "cuFFT"):
        for size in sorted({k[1] for k in rows if k[0] == bench}):
            cells.append((bench, size))
    fig, ax = plt.subplots(figsize=(M.COL2, 2.6))
    xs, labs, n_excl = [], [], 0
    style = {1: ("o", "adjacent (p1)"), 2: ("s", "stride (p2)"), 3: ("^", "Markov (p3)"), 4: ("D", MIS)}
    drawn = set()
    for ci, (bench, size) in enumerate(cells):
        labs.append(f"{bench}\n{size if len(size) < 9 else size.split('_')[0]}")
        gd = gate_d.get((bench, size))
        per_run = {}
        if gd:
            for r in rd(f"results/phaseB1/gate_d/{gd}/times.csv"):
                per_run.setdefault(int(r["policy"]), []).append(float(r["wall_s"]))
            base = st.median(per_run[0])
        elif (bench, size, 0) in rows:
            base = rows[(bench, size, 0)]
        else:
            continue
        for p in (1, 2, 3, 4):
            mk, lab = style[p]
            dx = (p - 2.5) * 0.15
            if gd and p in per_run:
                v = per_run[p]
                ax.scatter([ci + dx] * len(v), [pct(y, base) for y in v], s=5, color=M.SPEC_COL, alpha=0.4, marker=mk, linewidths=0, zorder=3)
                ax.scatter([ci + dx], [pct(st.median(v), base)], s=22, marker=mk, facecolor=M.SPEC_COL if p != 4 else "white", edgecolor=M.SPEC_COL, linewidths=1.0, zorder=5, label=None if lab in drawn else lab)
                drawn.add(lab)
            elif not gd:
                if p == 4:
                    continue  # pre-fix p4 is never plotted (the cursor-desync bug)
                excl = find_exclusion(manifest, "results/phaseB/phaseB_timing.csv", bench, size, f"p{p}", "wall_time")
                if excl or (bench, size, p) not in rows:
                    n_excl += 1
                    continue
                ax.scatter([ci + dx], [pct(rows[(bench, size, p)], base)], s=22, marker=mk, facecolor=M.SPEC_COL, edgecolor=M.SPEC_COL, linewidths=1.0, zorder=5, label=None if lab in drawn else lab)
                drawn.add(lab)
    ax.axhline(0, color=M.C0_COL, lw=1.0)
    ax.set_xticks(range(len(cells))); ax.set_xticklabels([l.replace("\n", " ") for l in labs], fontsize=5.6, rotation=70, ha="right")
    ax.set_ylabel("wall-clock vs p0 (%)")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.9), ncol=4, fontsize=6.5)
    ax.text(0.99, -1.12, "blue line = p0 (stock, speculation off); hollow = " + MIS + "; cells without per-run data show the median of 20",
            transform=ax.transAxes, ha="right", va="top", fontsize=5.8, color=M.MUTED)
    fig.tight_layout()
    save(fig, "f1_policy_matrix_walltime")
    META["F1"] = dict(file="f1_policy_matrix_walltime", csv="results/phaseB/phaseB_timing.csv; results/phaseB1/gate_d/{stencil,graphbfs,stencil_ovsub}/times.csv; results/figures/exclusion_manifest.csv",
                      note=f"wall-clock panel only (hit-rate panel not rebuilt: `spec_hits`); {n_excl} excluded cells (exclusion manifest) are omitted; pre-fix p4 never plotted; the p4 points are the post-fix Gate D reruns, which are still the {MIS}.",
                      cap=f"Phase B policy sweep, wall-clock relative to the stock driver (p0), for the adjacent, stride and Markov heuristics and, in the three cells where it was rerun, the {MIS}. Points are runs where per-run data exist, markers are medians; no test was applied and cells excluded by the exclusion manifest are omitted. The {MIS} did not align its trace with the faults it consumed, so its rows measure that misalignment and not any limit of prediction.")


# ------------------------------------------------------------------ F2: Gate 3 C0-C3 (original and interleaved)
CFG = {"C0": ("C0: stock prefetcher", M.C0_COL, "o"), "C1": ("C1: prefetcher off", GREY, "s"), "C2": ("C2: stride, depth 1", M.SPEC_COL, "^"), "C3": (f"C3: {MIS}", M.SPEC_COL, "D")}
BEN = [("bench_stencil", "Stencil-24K"), ("bench_graph_bfs", "GraphBFS-23")]


def gate3_original():
    d = {}
    for r in rd("results/phaseB2/gate3/gate3_times.csv"):
        d.setdefault((r["config"], r["bench"]), []).append(float(r["wall_s"]))
    return d


def gate3_interleaved():
    d = {}
    for r in rd("results/phaseB2/gate3_interleaved/gate3_interleaved_times.csv"):
        if r["rep_in_cell"].startswith("kept"):
            d.setdefault((r["config"], r["bench"]), []).append(float(r["wall_s"]))
    return d


def f2():
    fig, axes = plt.subplots(2, 2, figsize=(M.COL2, 4.0))
    ns = {}
    for ri, (title, data) in enumerate((("original order", gate3_original()), ("interleaved re-run", gate3_interleaved()))):
        for ci, (bk, bl) in enumerate(BEN):
            ax = axes[ri][ci]
            for i, cfg in enumerate(("C0", "C1", "C2", "C3")):
                lab, col, mk = CFG[cfg]
                v = data[(cfg, bk)]
                ns[(title, cfg, bk)] = len(v)
                M.pts(ax, i, v, col, mk, jitter=0.12, size=6, alpha=0.5)
                ax.scatter([i], [st.median(v)], s=26, marker=mk, facecolor=col if cfg != "C3" else "white", edgecolor=col, linewidths=1.1, zorder=5)
            ax.set_yscale("log")
            ax.set_xticks(range(4)); ax.set_xticklabels(["C0", "C1", "C2", "C3\n(misaligned\noracle)"], fontsize=6.3)
            ax.set_ylabel("wall-clock (s)" if ci == 0 else "")
            ax.set_xlabel(f"{bl}, {title}")
    fig.tight_layout()
    save(fig, "f2_gate3_c0_to_c3")
    META["F2"] = dict(file="f2_gate3_c0_to_c3", csv="results/phaseB2/gate3/gate3_times.csv; results/phaseB2/gate3_interleaved/gate3_interleaved_times.csv",
                      note=f"C3 relabelled '{MIS}'; the old title/caption wording 'decisive upper bound' is not used",
                      cap=f"Gate 3 wall-clock of C0 (stock prefetcher), C1 (prefetcher off), C2 (stride, depth 1) and C3 (the {MIS}), on Stencil-24K and GraphBFS-23, in the original order and in an interleaved re-run (kept phase). Points are runs, markers are medians; log scale; no test is applied. C3 consumed a trace that was not aligned with the faults, so it does not bound what speculation can do; the measurements of C3 stand only as measurements of that configuration.")


# ------------------------------------------------------------------ F3: the cost of turning the prefetcher off (panel B only)
def f3():
    fig, ax = plt.subplots(figsize=(M.COL1, 2.5))
    k = 0
    xt, xl = [], []
    for title, data in (("original", gate3_original()), ("interleaved", gate3_interleaved())):
        for bk, bl in BEN:
            base = st.median(data[("C0", bk)])
            v = data[("C1", bk)]
            M.pts(ax, k, [y / base for y in v], GREY, "s", jitter=0.1, size=6, alpha=0.5)
            ax.scatter([k], [st.median(v) / base], s=26, marker="s", facecolor=GREY, edgecolor=GREY, linewidths=1.1, zorder=5)
            xt.append(k); xl.append(f"{bl.split('-')[0]}\n{title}")
            k += 1
    ax.axhline(1.0, color=M.C0_COL, lw=1.0)
    ax.set_yscale("log")
    ax.set_xticks(xt); ax.set_xticklabels(xl, fontsize=6.3)
    ax.set_ylabel("C1 wall-clock / C0 median")
    ax.text(0.02, 0.96, "blue line = C0 (stock prefetcher)", transform=ax.transAxes, fontsize=6.3, color=M.C0_COL, va="top")
    fig.tight_layout()
    save(fig, "f3_cost_of_prefetch_off")
    META["F3"] = dict(file="f3_cost_of_prefetch_off", csv="results/phaseB2/gate3/gate3_times.csv; results/phaseB2/gate3_interleaved/gate3_interleaved_times.csv",
                      note="panel B of the old F3 only; panel A (probe vs benchmark hit rates, `spec_hits`, not like-for-like) is not rebuilt",
                      cap="Wall-clock cost of disabling the stock prefetcher (C1) relative to the stock driver (C0) on Stencil-24K and GraphBFS-23, in the original and in the interleaved Gate 3 runs. Points are runs normalised by the C0 median of the same series; log scale; no test is applied. C1 is a configuration built to isolate mechanisms and is not the shipped driver.")


# ------------------------------------------------------------------ F10: oversubscription, C0 / C1 / C3
def f10():
    rows = [r for r in rd("results/analysis/gate_b9_oversub_mechanism/task2c_c0_threeway_times_MERGED.csv") if r["phase"] == "kept"]
    iters = sorted({int(r["iters"]) for r in rows})
    fig, ax = plt.subplots(figsize=(M.COL1 * 1.3, 2.6))
    ns = set()
    for cfg, dx in (("C0", -0.12), ("C1", 0.0), ("C3", 0.12)):
        lab, col, mk = CFG[cfg]
        mx, my = [], []
        for i, it in enumerate(iters):
            v = [float(r["wall_s"]) for r in rows if r["config"] == cfg and int(r["iters"]) == it]
            ns.add(len(v))
            M.pts(ax, i + dx, v, col, mk, jitter=0.03, size=6, alpha=0.5)
            ax.scatter([i + dx], [st.median(v)], s=26, marker=mk, facecolor=col if cfg != "C3" else "white", edgecolor=col, linewidths=1.1, zorder=5)
            mx.append(i + dx); my.append(st.median(v))
        ax.plot(mx, my, color=col, lw=0.8, zorder=4, label=lab.replace("C3: " + MIS, "C3: " + MIS).replace("C0: stock prefetcher", "C0: stock prefetcher (baseline)"))
    ax.set_yscale("log")
    ax.set_xticks(range(len(iters))); ax.set_xticklabels([str(i) for i in iters])
    ax.set_xlabel("kernel iterations"); ax.set_ylabel("wall-clock (s)")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=1, fontsize=6.5)
    fig.tight_layout()
    save(fig, "f10_oversub_three_way")
    META["F10"] = dict(file="f10_oversub_three_way", csv="results/analysis/gate_b9_oversub_mechanism/task2c_c0_threeway_times_MERGED.csv", note=f"C3 relabelled '{MIS}'; n = {sorted(ns)} kept runs per cell",
                       cap=f"Oversubscribed Stencil (1.078 times GPU memory), wall-clock of C0 (stock), C1 (prefetcher off) and C3 (the {MIS}) against the number of kernel iterations, interleaved runs, kept phase. Points are runs and lines join medians; log scale; no test is applied. C1 is not the shipped driver, and C3 consumed a trace that was not aligned with the faults.")


# ------------------------------------------------------------------ F7: dispatch latency and fault inter-arrival interval (no "race")
def f7():
    wk = {}
    for r in rd("results/analysis/t_a1_worker/worker_latency_summary.csv"):
        wk[(r["platform"], r["scale"], r["bench"])] = r
    probes = {}
    for r in rd("results/phaseB1/hit_probe_summary.csv"):
        probes.setdefault(r["platform"], []).append(r)
    ints = {}
    for r in rd("results/gate3/telemetry/t4_prefetch_off_hitrate_recovered.csv"):
        if r["methodology"] == "corrected_marginal_clean" and r["fault_rate_per_s"]:
            ints.setdefault(r["bench"], []).append(1e6 / float(r["fault_rate_per_s"]))
    cats = [("full_run", "bench_stencil"), ("full_run", "bench_graph_bfs"), ("short_run", "bench_stencil"), ("short_run", "bench_graph_bfs")]
    mk = {"bench_stencil": "o", "bench_graph_bfs": "s"}
    bl = {"bench_stencil": "Stencil", "bench_graph_bfs": "GraphBFS"}
    sl = {"full_run": "full-size", "short_run": "short-run"}
    fig, axes = plt.subplots(1, 2, figsize=(M.COL2, 3.1), sharey=True)
    for ax, plat in zip(axes, ["T4", "5070Ti"]):
        for xi, (scale, bench) in enumerate(cats):
            r = wk[(plat, scale, bench)]
            med, p90 = float(r["dispatch_median_us"]), float(r["dispatch_p90_us"])
            ax.plot([xi, xi], [med, p90], color=M.SPEC_COL, lw=1.1, zorder=2)
            ax.scatter([xi], [med], s=24, marker=mk[bench], color=M.SPEC_COL, zorder=3)
            ax.scatter([xi], [p90], s=24, marker=mk[bench], facecolor="white", edgecolor=M.SPEC_COL, linewidths=1.0, zorder=3)
        tag = "prefoff_adj" if plat == "T4" else "task1_probe"
        pm = float(next(r for r in probes[plat] if r["tag"] == tag)["dispatch_median_us"])
        ax.axhline(pm, color=GREY, ls="--", lw=0.9)
        ax.text(-0.45, pm * 1.1, f"uncontended probe, {pm:.2f} \u00b5s", fontsize=5.8, color=M.MUTED)
        if plat == "T4":
            for b, v in ints.items():
                mid = (min(v) + max(v)) / 2
                ax.axhline(mid, color=DARK, lw=1.3, alpha=0.8)
                ax.text(-0.45, mid * (1.1 if b == "bench_graph_bfs" else 0.8), f"{bl[b]} demand-fault interval, {mid:.2f} \u00b5s", fontsize=5.8, color=DARK)
        ax.set_yscale("log"); ax.set_xlim(-0.55, 3.55)
        ax.set_xticks(range(4)); ax.set_xticklabels([f"{sl[s]}\n{bl[b]}" for s, b in cats], fontsize=6.3)
        ax.set_xlabel("Tesla T4" if plat == "T4" else "RTX 5070 Ti")
    axes[0].set_ylabel("latency or interval (\u00b5s, log)")
    from matplotlib.lines import Line2D
    fig.tight_layout()
    fig.legend(handles=[Line2D([], [], marker="o", ls="", color=M.SPEC_COL, ms=4, label="dispatch latency, median (enqueue to dequeue)"),
                        Line2D([], [], marker="o", ls="", mfc="w", mec=M.SPEC_COL, ms=4, label="dispatch latency, p90"),
                        Line2D([], [], color=DARK, lw=1.3, label="demand-fault inter-arrival interval (T4 only)"),
                        Line2D([], [], color=GREY, ls="--", lw=0.9, label="uncontended probe latency")], frameon=False, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.12), fontsize=6.3)
    save(fig, "f7_dispatch_latency_and_fault_interval")
    META["F7"] = dict(file="f7_dispatch_latency_and_fault_interval", csv="results/analysis/t_a1_worker/worker_latency_summary.csv; results/phaseB1/hit_probe_summary.csv; results/gate3/telemetry/t4_prefetch_off_hitrate_recovered.csv",
                      note="renamed and retitled: dispatch latency and fault inter-arrival interval (no 'race'); no 5070 Ti interval is drawn because no matching prefetch-off real-workload fault-rate sweep exists on that platform",
                      cap="Dispatch latency (enqueue to dequeue; median and p90) of the speculative worker on the Tesla T4 and the RTX 5070 Ti, for two workloads at two run sizes, beside the uncontended probe latency and, on the T4 only, the demand-fault inter-arrival interval. The figure compares the two time scales; it does not by itself explain the `spec_hits` coincidence rate, which is not a measure of prediction success. Points are summaries from the committed recovery CSVs; no test is applied.")


def main():
    M.style()
    for f in (f1, f2, f3, f7, f10):
        f()
        print("wrote", f.__name__)
    with open(f"{OUT}/LEGACY.md", "w") as f:
        f.write("# Regenerated legacy figures (`tests/make_legacy_figures.py`)\n\nShared colour map of `tests/make_paper_figures.py`. The files in `results/figures/` are unchanged. Captions: at most 3 sentences, no 'upper bound' or 'oracle-perfect' for pre-E0.5 data.\n\n"
                "| figure | file (PDF and PNG) | source CSV(s) | what changed / omitted | draft caption |\n|---|---|---|---|---|\n")
        for k in ("F1", "F2", "F3", "F7", "F10"):
            m = META[k]
            f.write(f"| {k} | `{m['file']}` | {m['csv'].replace('; ', '<br>')} | {m['note']} | {m['cap']} |\n")


if __name__ == "__main__":
    main()
