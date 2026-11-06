#!/usr/bin/env python3
"""Gate C8 phase 3: booktabs LaTeX fragments for Sections VI-VIII, from COMMITTED CSVs only.

Every data row ends with a trailing `% <evidence ids>` comment (ids from results/analysis/consolidation/EVIDENCE_EXTRACT.md; where a row has no
extract id the comment names the CSV and the row key, `csv:<path>#<key>`). Nothing is typed by hand except column headings and the T-CAT
shortenings (flagged). The fragments contain only the tabular; captions are drafts in paper/tables/TABLES.md. MDE columns are at the family alpha:
E4 uses `mde_bonf_s` (alpha 0.05/18, set in e4_analyze.py); E5 `mde_bonf_s` (alpha/3); E6 rescales `mde_s` by the z-ratio (the CSV column is the 0.05/16 constant);
E7/E8/E7-T4 use `mde_family_pct` from the E7 helper.
usage: make_paper_tables.py   (writes paper/tables/*.tex and paper/tables/TABLES.md)
"""
import csv
import os
import re
import statistics as st

from scipy.stats import norm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
G = "results/analysis/gate_e"
OUT = "paper/tables"
EV = open("results/analysis/consolidation/EVIDENCE_EXTRACT.md").read()
EVIDS = set(re.findall(r"^\| `([^`]+)`", EV, re.M))
META = {}
Z80 = norm.ppf(0.80)


def rd(p):
    return list(csv.DictReader(open(p)))


def fl(x):
    return float(x)


def zr(m):
    return (norm.ppf(1 - 0.05 / (2 * m)) + Z80) / (norm.ppf(0.975) + Z80)


def eid(name, fallback):
    return name if name in EVIDS else f"csv:{fallback}"


def pv(p):
    p = fl(p)
    return f"{p:.2e}".replace("e-0", "e-").replace("e+0", "e+")


def tex(s):
    return str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def sig(b):
    return "yes" if str(b) == "True" else "no"


def sgn(x, nd=2):
    return f"{fl(x):+.{nd}f}".replace("-", "$-$")


def emit(name, head_cols, rows, colspec, note=None, groups=None):
    """rows: list of (cells, ids). groups: optional {row_index: heading} for midrules."""
    lines = [r"\begin{tabular}{" + colspec + "}", r"\toprule", " & ".join(head_cols) + r" \\", r"\midrule"]
    for i, (cells, ids) in enumerate(rows):
        if groups and i in groups:
            if i:
                lines.append(r"\midrule")
        lines.append(" & ".join(str(c) for c in cells) + r" \\ % " + ";".join(ids))
    lines += [r"\bottomrule", r"\end{tabular}"]
    path = f"{OUT}/{name}.tex"
    os.makedirs(OUT, exist_ok=True)
    open(path, "w").write("\n".join(lines) + "\n")
    return path


# ---------------------------------------------------------------- T-E4
def t_e4():
    comp = rd(f"{G}/e4/primary_comparisons.csv")
    rows = []
    for wl, wn in (("stencil", "Stencil-24K"), ("graphbfs", "GraphBFS-23")):
        for fam, arm in (("F1", "C7-W1"), ("F1", "C7-W64"), ("F1", "C7-W512"), ("F4", "C6-W512")):
            c = next(c for c in comp if c["family"] == fam and c["workload"] == wl and c["arm"] == arm and c["baseline"] == "C0")
            i = eid(f"E4.{fam}.{wl}.{arm}_vs_C0", f"{G}/e4/primary_comparisons.csv#{fam}.{wl}.{arm}")
            rows.append(([wn if arm == "C7-W1" else "", f"{arm} ({fam})", f"{fl(c['median_base']):.4f}", f"{fl(c['median_arm']):.4f}", sgn(c["delta_pct"]),
                          pv(c["p"]), f"{fl(c['holm_threshold']):.4f}", sig(c["holm_sig"]), f"{fl(c['mde_bonf_s']):.4f}"], [i]))
    p = emit("t_e4", ["Workload", "Arm vs C0", "Median C0 (s)", "Median arm (s)", r"$\Delta$ (\%)", "MWU $p$", "Holm thr.", "Sig.", r"MDE, $\alpha/18$ (s)"], rows,
             "@{}llrrrrrcr@{}", groups={4: ""})
    META["T-E4"] = dict(file=p, csv=f"{G}/e4/primary_comparisons.csv", cap="E4, RTX 5070 Ti, E3a-2 module: wall-clock of each speculation arm against C0 (the shipped driver) on Stencil-24K and GraphBFS-23, family F1 (prefetcher on) and the F4 row (perfect staging, prefetcher off). Two-sided Mann-Whitney U, one Holm family of 18, n = 10 per cell. The MDE is at the family alpha, alpha/18.")


# ---------------------------------------------------------------- T-E5
def t_e5():
    fr = {int(r["threshold"]): r for r in rd(f"{G}/e5/fault_reduction.csv")}
    wc = {int(r["threshold"]): r for r in rd(f"{G}/e5/wallclock_comparisons.csv")}
    rows = []
    for t, lab in ((51, "51 (shipped)"), (75, "75"), (100, "100 (rule off)")):
        f, w = fr[t], wc[t]
        rows.append(([lab, f"{fl(f['median_df_C0']):,.0f}".replace(",", r"{,}"), f"{fl(f['median_df_C7W512']):,.0f}".replace(",", r"{,}"), f"{fl(f['D']):+.4f}".replace("-", "$-$"), sig(f["holm_sig"]),
                      sgn(w["delta_pct"]), pv(w["p"]), sig(w["holm_sig"]), f"{fl(w['mde_bonf_s']):.4f}"],
                     [eid(f"E5.D({t})", f"{G}/e5/fault_reduction.csv#{t}"), eid(f"E5.wall.t{t}", f"{G}/e5/wallclock_comparisons.csv#{t}")]))
    p = emit("t_e5", ["Threshold", "Demand faults C0", "Demand faults C7W512", "$D(t)$", "Sig.", r"Wall-clock $\Delta$ (\%)", "MWU $p$", "Sig.", r"MDE, $\alpha/3$ (s)"], rows, "@{}lrrrcrrcr@{}")
    META["T-E5"] = dict(file=p, csv=f"{G}/e5/fault_reduction.csv; {G}/e5/wallclock_comparisons.csv", cap="E5, Stencil-24K, RTX 5070 Ti: demand-fault reduction D(t) of C7W512 against C0 at the same threshold, and the wall-clock change, at thresholds 51, 75 and 100 (100 disables the density rule). Two-sided Mann-Whitney U, Holm across 3, n = 10 per cell; MDE at alpha/3.")


# ---------------------------------------------------------------- T-E6
def t_e6():
    f1 = rd(f"{G}/e6/family1_primary.csv")
    sw = rd(f"{G}/e6/secondary_wall.csv")
    sd = rd(f"{G}/e6/secondary_demand.csv")
    rows = []
    for c in f1:
        t = c["base"].split("-")[1]
        rows.append((["Family 1 (wall-clock, $m{=}4$)", f"C7W512-t51 vs C0-{t}", f"{fl(c['median_base']):.4f}", f"{fl(c['median_c6']):.4f}", sgn(c["delta_pct"]), pv(c["p"]), sig(c["holm_sig"]),
                      f"{fl(c['mde_s']) * zr(4):.4f}"], [eid(f"E6.F1.C7W512-t51_vs_C0-{t}", f"{G}/e6/family1_primary.csv#{t}")]))
    for c in sw:
        t = c["arm"].split("-")[1]
        rows.append((["Within-threshold wall-clock ($m{=}3$)", f"C7W512-{t} vs C0-{t}", f"{fl(c['median_base']):.4f}", f"{fl(c['median_c6']):.4f}", sgn(c["delta_pct"]), pv(c["p"]), sig(c["holm_sig"]),
                      f"{fl(c['mde_s']) * zr(3):.4f}"], [eid(f"E6.wall.C7W512-{t}_vs_C0-{t}", f"{G}/e6/secondary_wall.csv#{t}")]))
    for c in sd:
        t = c["arm"].split("-")[1]
        rows.append((["Within-threshold demand faults ($m{=}3$)", f"C7W512-{t} vs C0-{t}", f"{fl(c['median_base']):,.0f}".replace(",", r"{,}"), f"{fl(c['median_c6']):,.0f}".replace(",", r"{,}"), sgn(c["delta_pct"]), pv(c["p"]),
                      sig(c["holm_sig"]), f"{fl(c['mde_s']) * zr(3):,.0f}".replace(",", r"{,}")], [eid(f"E6.demand.C7W512-{t}_vs_C0-{t}", f"{G}/e6/secondary_demand.csv#{t}")]))
    p = emit("t_e6", ["Family", "Comparison", "Median base", "Median arm", r"$\Delta$ (\%)", "MWU $p$", "Sig.", "MDE (family $\\alpha$)"], rows, "@{}llrrrrcr@{}", groups={4: "", 7: ""})
    META["T-E6"] = dict(file=p, csv=f"{G}/e6/family1_primary.csv; {G}/e6/secondary_wall.csv; {G}/e6/secondary_demand.csv", cap="E6, Stencil-24K, RTX 5070 Ti: C7W512 at the shipped threshold against C0 at thresholds 0, 10, 25 and 51 (Holm family of 4), and C7W512 against C0 at the same threshold on wall-clock and on demand faults (two Holm families of 3). n = 10 per cell. MDEs are at the family alpha, rescaled from the achieved-n value because the CSV column is the 0.05/16 constant.")


# ---------------------------------------------------------------- T-MECH
def t_mech():
    m4 = {(r["workload"], r["arm"]): r for r in rd(f"{G}/e4/mechanism.csv")}
    m5 = {(r["threshold"], r["arm"]): r for r in rd(f"{G}/e5/mechanism.csv")}
    rows = []

    def row(label, arm, r, ident):
        df, d5 = fl(r["demand_faults"]), fl(r["d5_s"])
        return ([label, arm, f"{df:,.0f}".replace(",", r"{,}"), f"{fl(r['fault_already_resident']):,.0f}".replace(",", r"{,}"), f"{fl(r['spec_pages_requested']):,.0f}".replace(",", r"{,}"),
                 f"{d5:.3f}", f"{d5 / df * 1e6:.2f}"], [ident])
    for wl, wn in (("stencil", "Stencil-24K"), ("graphbfs", "GraphBFS-23")):
        for arm in ("C0", "C1", "C6-W512", "C7-W512"):
            rows.append(row(wn if arm == "C0" else "", arm, m4[(wl, arm)], eid(f"E4.mech.{wl}.{arm}", f"{G}/e4/mechanism.csv#{wl}.{arm}")))
    for arm in ("C0", "C7W512"):
        rows.append(row("Stencil-24K, $t{=}100$" if arm == "C0" else "", f"{arm}-toff", m5[("100", arm)], eid(f"E5.mech.t100.{arm}", f"{G}/e5/mechanism.csv#100.{arm}")))
    p = emit("t_mech", ["Workload", "Arm", "Demand faults", "Fault already resident", "Pages requested", "D5 (s)", r"D5 per fault ($\mu$s)"], rows, "@{}llrrrrr@{}", groups={4: "", 8: ""})
    META["T-MECH"] = dict(file=p, csv=f"{G}/e4/mechanism.csv; {G}/e5/mechanism.csv", cap="Mechanism of speculation (E4, E5), RTX 5070 Ti: demand faults, faults on pages already resident on the GPU, pages requested by the worker, and D5 in total and per demand fault, for C0, C1, C6-W512 and C7-W512, and for the two cells with the density rule off (threshold 100). Medians of 10 runs; D5 per fault is the D5 median divided by the demand-fault median.")


# ---------------------------------------------------------------- T-HAND
def t_hand():
    e1b = rd(f"{G}/e1b/e1b_per_run.csv")
    rows = []
    names = {"C74096": "C7 (prefetcher on)", "C64096": "C6 (prefetcher off)"}
    for wl, arm in (("stencil", "C64096"), ("stencil", "C74096"), ("graphbfs", "C64096")):
        sel = [r for r in e1b if r["workload"] == wl and r["arm"] == arm]
        v = [st.median(fl(r["enq_ns"]) for r in sel) / st.median(fl(r["ft_predictions"]) for r in sel)]   # ratio of medians, as E1b.* in the evidence extract
        base = "C1" if arm == "C64096" else "C0"
        rows.append(([f"E1b {'Stencil-24K' if wl == 'stencil' else 'GraphBFS-23'}", names[arm], f"{st.median(v):.0f}", "", "", ""], [eid(f"E1b.{wl}.{arm.replace('C6', 'C6')}-{base}", f"{G}/e1b/e1b_per_run.csv#{wl}.{arm}")]))
    s4 = rd(f"{G}/e3b/step4_per_run.csv")

    def med(arm, k):
        return st.median(fl(r[k]) for r in s4 if r["arm"] == arm)
    res = {}
    for wl, pair, base, f0, f1 in (("stencil", "C6", "stencil C1", "stencil C6f0", "stencil C6f1"), ("stencil", "C7", "stencil C0", "stencil C7f0", "stencil C7f1"), ("graphbfs", "C6", "graphbfs C1", "graphbfs C6f0", "graphbfs C6f1")):
        out = []
        for a in (f0, f1):
            resid = (med(a, "outside_ns") - med(base, "outside_ns")) - med(a, "enq_ns")
            out.append((resid, resid / med(a, "demand_faults")))
        frac = 1 - out[1][0] / out[0][0]
        rows.append(([f"E3b {'Stencil-24K' if wl == 'stencil' else 'GraphBFS-23'}", f"{pair} (per-fault residual)", "", f"{out[0][1]:.0f}", f"{out[1][1]:.0f}", f"{100 * frac:.1f}"],
                     [eid(f"E3b.{wl}.{pair}.residual", f"{G}/e3b/step4_per_run.csv#{wl}.{pair}")]))
    p = emit("t_hand", ["Source", "Arm", "Enqueue per prediction (ns)", "Residual per fault, slow lookup (ns)", "Residual per fault, fast lookup (ns)", r"Residual removed (\%)"], rows, "@{}llrrrr@{}", groups={3: ""})
    META["T-HAND"] = dict(file=p, csv=f"{G}/e1b/e1b_per_run.csv; {G}/e3b/step4_per_run.csv", cap="Cost of the hook on the servicing thread (RTX 5070 Ti): the enqueue cost per prediction measured in E1b, and the per-fault residual (the increase of time outside the lock beyond the enqueue itself, per demand fault) with the original lookup and with the constant-time lookup, measured in E3b. Medians of 3 runs (2 for GraphBFS-23); no test is applied.")


# ---------------------------------------------------------------- T-E7
def t_e7():
    def load(p):
        return {(c["workload"], c["arm"]): c for c in rd(p)}
    plat = {"rtx": (load(f"{G}/e7/family_a.csv"), load(f"{G}/e7/family_b.csv"), "E7"), "t4": (load("results/analysis/t4/family_a.csv"), load("results/analysis/t4/family_b.csv"), "T4")}
    names = [("stencil8k", "Stencil-8K"), ("sweep4k", "Sweep-4K"), ("sweep16k", "Sweep-16K"), ("stream", "STREAM"), ("sgemm", "SGEMM"), ("cufft", "cuFFT"), ("graphbfs", "GraphBFS-23"), ("oversub", "Stencil, oversubscribed")]

    def cell(c, wl):
        if c is None:
            return "n/r"
        mark = ""
        if c["holm_sig"] == "True":
            mark = r"$^{\dagger}$" if (wl == "graphbfs" and abs(fl(c["delta_s"])) < fl(c["mde_s"])) else "$^{*}$"
        return sgn(c["delta_pct"]) + mark
    rows = []
    # Family A
    for arm in ("stock-t0", "stock-t10"):
        cells = ["Stencil-24K (Family A)", arm.replace("stock-", "")]
        ids = []
        for k in ("rtx", "t4"):
            fa, fb, pre = plat[k]
            c = fa[("stencil", arm)]
            cells += [cell(c, "stencil"), f"{fl(c['mde_family_pct']):.2f}"]
            ids.append(eid(f"{pre}.A.stencil.{arm}_vs_stock-t51", f"A.{k}.{arm}"))
        rows.append((cells, ids))
    for wl, wn in names:
        for arm in ("stock-t0", "stock-t25"):
            cells = [wn if arm == "stock-t0" else "", arm.replace("stock-", "")]
            ids = []
            for k in ("rtx", "t4"):
                fa, fb, pre = plat[k]
                c = fb.get((wl, arm))
                cells += [cell(c, wl), f"{fl(c['mde_family_pct']):.2f}" if c else "n/r"]
                if c:
                    ids.append(eid(f"{pre}.B.{wl}.{arm}_vs_stock-t51", f"B.{k}.{wl}.{arm}"))
            rows.append((cells, ids))
    p = emit("t_e7", ["Workload", "Threshold", r"RTX 5070 Ti $\Delta$ (\%)", r"MDE (\%)", r"Tesla T4 $\Delta$ (\%)", r"MDE (\%)"], rows, "@{}llrrrr@{}", groups={2: ""})
    META["T-E7"] = dict(file=p, csv=f"{G}/e7/family_a.csv; {G}/e7/family_b.csv; results/analysis/t4/family_a.csv; results/analysis/t4/family_b.csv",
                        cap="Threshold 0, 10 and 25 against the shipped 51 on the stock driver, RTX 5070 Ti (E7, Family B one Holm family of 16) and Tesla T4 (E7-T4, 14 tests), analysed separately and never pooled; delta is (arm - t51) / t51. A star marks Holm-significance; a dagger marks GraphBFS-23 on the T4, significant but below its minimum detectable effect; n/r: the oversubscribed cell was not run on the T4. MDE is at the family alpha.")


# ---------------------------------------------------------------- T-E8
def t_e8():
    tests = rd(f"{G}/e8/primary_tests.csv")
    rows = []
    for size, sn in (("in", "In memory (8 GiB)"), ("ov", "Oversubscribed (24 GiB)")):
        for K in (1, 8, 64, 512):
            for arm in ("stock-t0", "stock-t25"):
                c = next(t for t in tests if t["size"] == size and int(t["K"]) == K and t["arm"] == arm)
                rows.append(([sn if (K == 1 and arm == "stock-t0") else "", str(K), arm.replace("stock-", ""), f"{fl(c['median_base']):.3f}", f"{fl(c['median_c6']):.3f}", sgn(c["delta_pct"]), pv(c["p"]),
                              sig(c["holm_sig"]), f"{fl(c['mde_family_pct']):.2f}"], [eid(f"E8.{size}.K{K}.{arm}_vs_stock-t51", f"{G}/e8/primary_tests.csv#{size}.{K}.{arm}")]))
    p = emit("t_e8", ["Array", "$K$", "Thr.", "Median $t51$ (s)", "Median arm (s)", r"$\Delta$ (\%)", "MWU $p$", "Sig.", r"MDE (\%)"], rows, "@{}lrlrrrrcr@{}", groups={8: ""})
    META["T-E8"] = dict(file=p, csv=f"{G}/e8/primary_tests.csv", cap="E8, sparse access, RTX 5070 Ti, stock driver: wall-clock at threshold 0 and 25 against 51 for K pages touched per 2 MB block, with the array in memory and oversubscribed. Two-sided Mann-Whitney U, one Holm family of 16, n = 10 per cell; MDE at the family alpha.")


# ---------------------------------------------------------------- T-E9
def t_e9():
    cm = {(r["workload"], int(r["threshold"])): r for r in rd(f"{G}/e9/cell_medians.csv")}
    ps = rd("results/analysis/derived/c4_e9_phase_split.csv")
    GIB = 1073741824.0
    order = [("ov_k1", "Oversub. $K{=}1$"), ("ov_k8", "Oversub. $K{=}8$"), ("ov_k64", "Oversub. $K{=}64$"), ("ov_k512", "Oversub. $K{=}512$"), ("in_k1", "In-mem. $K{=}1$"), ("in_k512", "In-mem. $K{=}512$"), ("stencil", "Stencil-24K")]
    rows = []
    for wl, wn in order:
        for t in (0, 51):
            c = cm[(wl, t)]
            sub = [r for r in ps if r["workload"] == wl and int(r["threshold"]) == t]
            fill, kern = st.median(fl(r["fill_ms"]) for r in sub), st.median(fl(r["kernel_ms"]) for r in sub)
            rows.append(([wn if t == 0 else "", str(t), f"{fl(c['htod_bytes_median']) / GIB:.2f}", f"{fl(c['dtoh_bytes_median']) / GIB:.2f}", f"{fl(c['report_gpu_faults_median']):,.0f}".replace(",", r"{,}"),
                          f"{fl(c['report_cpu_faults_median']):,.0f}".replace(",", r"{,}"), f"{fill / 1000:.2f}", f"{kern / 1000:.2f}"],
                         [eid(f"E9.cell.{wl}.t{t}", f"{G}/e9/cell_medians.csv#{wl}.t{t}"), f"csv:results/analysis/derived/c4_e9_phase_split.csv#{wl}.t{t}"]))
    p = emit("t_e9", ["Cell", "Thr.", "HtoD (GiB)", "DtoH (GiB)", "GPU faults", "CPU faults", "Host fill (s)", "Kernels (s)"], rows, "@{}lrrrrrrr@{}", groups={})
    o = rd("results/analysis/derived/c4_e8_outside_kernels.csv")
    rows2 = []
    for r in o:
        if r["arm"] != "stock-t0":
            continue
        rows2.append(([("In memory" if r["size"] == "in" else "Oversubscribed") if r["K"] == "1" else "", r["K"], f"{fl(r['delta_wall_s']):+.3f}".replace("-", "$-$"), f"{fl(r['delta_outside_kernels_s']) * 1000:+.0f}".replace("-", "$-$"),
                       f"{fl(r['delta_kernel_s']):+.3f}".replace("-", "$-$"), f"{100 * fl(r['outside_share_of_delta']):+.0f}".replace("-", "$-$")],
                      [eid("E8.outside_kernels.t0", f"results/analysis/derived/c4_e8_outside_kernels.csv#{r['size']}.{r['K']}")]))
    p2 = emit("t_e9b", ["Array", "$K$", r"$\Delta$ wall (s)", r"$\Delta$ outside kernels (ms)", r"$\Delta$ kernels (s)", r"Outside share of $\Delta$ wall (\%)"], rows2, "@{}lrrrrr@{}", groups={4: ""})
    META["T-E9"] = dict(file=f"{p}; {p2}", csv=f"{G}/e9/cell_medians.csv; results/analysis/derived/c4_e9_phase_split.csv; results/analysis/derived/c4_e8_outside_kernels.csv",
                        cap="Unified-memory traffic of the stock driver at threshold 0 and 51 under nsys (E9, medians of 3 traced runs): bytes migrated each way, GPU and CPU page faults, and the host-initialisation and kernel phases (the CPU faults occur only in host initialisation). The second fragment gives, for the untraced E8 runs, the threshold-0 change in wall-clock, in time outside the kernels and in kernel time, and the share of the wall-clock change that lies outside the kernels (a negative share means the slowdown is entirely in the kernels).")


# ---------------------------------------------------------------- T-CAT (shortened; every row flagged where judgement was used)
CAT = {  # n: (short name, false conclusion, <= 15 words, how caught, family, judgement flag)
    1: ("Oracle cursor desync", "Even a perfect predictor yields no benefit, so speculation is useless.", "independent re-investigation (Gate B)", "Validation that could not fail", ""),
    2: ("ASLR address instability", "Oracle scores zero even after the cursor fix; speculation is useless.", "independent re-investigation (Gate B)", "Validation that could not fail", ""),
    3: ("STREAM host-ordering noise", "Prefetch speculation gives STREAM a real speedup (a false positive).", "interleaved re-run", "Operational hazards", ""),
    4: ("Timer collapse (T2 = T3)", "Metadata is nearly all of service time, so offload should target it.", "later independent pass", "Instrument cost and blindness", ""),
    5: ("Ring read byte-offset drift", "Garbled phase decompositions read as noisy but plausible data.", "same-session accounting-closure check", "Instrument cost and blindness", "J: the entry names no stated false conclusion"),
    6: ("cuFFT hit-rate outlier", "Stride prediction works on cuFFT, the one favourable real workload.", "reproduction (Task T2)", "Uncategorised", ""),
    7: ("Ring saturation without wraparound", "Capped ring counts were read as true per-repetition totals.", "later independent pass", "Aggregation-level mismatch", "J: the entry's naive reading is about independence of the dumps"),
    8: ("Rate-arithmetic aggregation error", "Overstated fault rates made the worker's race loss look decisive.", "verification pass", "Aggregation-level mismatch", "J: the number of repetitions dropped from the name"),
    9: ("Ceiling units mismatch", "A large wall-clock share could be recovered by hiding D1+D2.", "later independent pass", "Aggregation-level mismatch", "J: the cross-platform divergence part omitted"),
    10: ("setarch -R regime effect", "Fixed-address results were read as general platform noise.", "pre-registered test (A2b)", "Operational hazards", "J: the entry says it is not a false conclusion in the usual sense"),
    11: ("Host memory leak confound", "A live leak could be mistaken for a settled platform property.", "near-OOM forced a stop", "Operational hazards", "J: the entry says no false conclusion was yet produced"),
    12: ("Crippled-baseline comparison", "Speculation gives a large oversubscription speedup, reversing the central negative claim.", "independent verification pass", "Validation that could not fail", ""),
    13: ("Recording/consumption granularity mismatch", "Every oracle result read as a maximally favourable, aligned predictor.", "independent source audit (E0)", "Aggregation-level mismatch", ""),
    14: ("Positive control that could not fail", "The fix and hit accounting were sound; the width path was tested.", "later passes; one caught in-gate", "Validation that could not fail", "J: three instances merged into one sentence"),
    15: ("Improvement without an absolute ceiling", "The oracle fix was verified, licensing every later oracle result.", "independent pass (E0.5)", "Validation that could not fail", ""),
    16: ("Denominator mismatch", "One prediction per batch caps the hit rate at the reciprocal coalesce factor.", "independent pass (E0.5)", "Aggregation-level mismatch", ""),
    17: ("Index drift", "Stencil is closer to genuine divergence, so trace replay was abandoned.", "independent analysis-only pass (E0.8)", "Aggregation-level mismatch", ""),
    18: ("Forward-only metric asymmetry", "A real residual disagreement in first-touch order exists (withdrawn).", "next pass, then external review", "Aggregation-level mismatch", "J: two withdrawn conclusions reduced to one"),
    19: ("Circular ring read in slot order", "Residency-accumulation mechanism and oracle-arm wall-clock read as oracle behaviour.", "independent source audit (E0)", "Instrument cost and blindness", "J: two false conclusions merged"),
    20: ("spec_hits counts a window, not wins", "Hit rate read as prediction success; near-zero meant speculation never wins.", "a second counter disagreed", "Instrument cost and blindness", "J: two false conclusions merged"),
    21: ("Upper-bound instrument with its own cost", "Cannot beat C0 read as a property of speculation, not the oracle.", "reviewer challenge, then pre-registered test", "Instrument cost and blindness", ""),
    22: ("Helper returned NULL under a non-fatal assert", "None about data; a kernel oops changed the development protocol.", "a crash", "Operational hazards", "J: the entry says the hazard was physical"),
    23: ("Silent platform drift", "Older-driver and Gate-E results are one platform; the platform table is current.", "preflight (a module would not load)", "Record integrity", ""),
    24: ("Line-count dmesg diff", "Rejection printed nothing; a real oops line could scroll out unseen.", "loud harness failure", "Operational hazards", ""),
    25: ("Pilot ceiling failed its own test", "Servicing-window time maps onto wall-clock, so the ceiling bounds the saving.", "pre-registered prediction test", "Aggregation-level mismatch", ""),
    26: ("Status log vs primary record", "The status log is a primary record of platform state and timing.", "journal re-account; E8 review", "Record integrity", ""),
    27: ("Hard-coded multiplicity correction", "An MDE labelled at the family alpha is not at that alpha.", "author of a later gate", "Aggregation-level mismatch", ""),
    28: ("LFS pointer patch swallowed", "A driver-source problem was misdiagnosed; a wrong module could pass as verified.", "failed compile", "Operational hazards", "J: second clause is the entry's counterfactual"),
    29: ("Session killed by its own session kill", "None in data; lost time, and a half-run gate read as complete.", "the session ended", "Operational hazards", "J: the entry says no data conclusion"),
    30: ("VRAM-only sizing, no host-RAM check", "An out-of-memory thrashing run timed as an oversubscription measurement.", "pre-registered smoke pass (OOM kill)", "Operational hazards", "J: the entry says no result was reached"),
    31: ("memory.used read as migrated volume", "The volume moved is the same on both allocators (a measure valid on one only).", "inspection after the gate; E9 traced bytes", "Validation that could not fail", "J: the entry's false conclusion is a scored expectation (Z6) and its consequence for the managed t51 cell, merged into one sentence"),
}


def t_cat():
    s = open("results/analysis/ARTIFACT_CATALOG.md").read()
    nums = sorted(int(x) for x in re.findall(r"^### #(\d+) ", s, re.M)) + [int(m.group(1)) for m in re.finditer(r"^\| (\d+) \|", s, re.M)]
    assert sorted(set(nums)) == list(range(1, 32)), "catalog entries are not #1-#31"
    assert sorted(CAT) == list(range(1, 32))
    for n, v in CAT.items():
        assert len(v[1].split()) <= 15, (n, len(v[1].split()))
    fam_tab = s.split("| family | entries")[1].split("\n\n")[0]
    famof = {}
    for l in fam_tab.split("\n")[2:]:
        if l.startswith("|"):
            c = l.split("|")
            f = re.sub(r"[*_()]|\(new, C6\)|new, C6|uncategorised: a genuine outlier", "", c[1]).strip()
            for x in re.findall(r"#(\d+)", c[2]):
                famof[int(x)] = f
    rows = []
    flagged = []
    for n in range(1, 32):
        nm, fc, hc, fam, flag = CAT[n]
        if flag:
            flagged.append(f"#{n}: {flag}")
        rows.append(([f"\\#{n}", tex(nm), tex(fc), tex(hc), tex(fam)], [f"ARTIFACT_CATALOG.md#{n}"]))
    p = emit("t_cat", ["\\#", "Artifact", "False conclusion it would have produced", "How caught", "Family"], rows, "@{}rp{2.3cm}p{4.2cm}p{2.2cm}p{2.2cm}@{}")
    open(f"{OUT}/t_cat_judgement.txt", "w").write("\n".join(flagged) + "\n")
    META["T-CAT"] = dict(file=p, csv="results/analysis/ARTIFACT_CATALOG.md", cap="The 31 catalogued measurement artifacts, condensed: the false conclusion each would have produced (shortened to at most 15 words), how it was caught, and its family. Entries are listed in catalog order.")
    return len(flagged)


# ---------------------------------------------------------------- brace / booktabs check (no TeX toolchain on this host)
def check_file(path):
    t = open(path).read()
    code = "\n".join(re.sub(r"(?<!\\)%.*$", "", l) for l in t.split("\n"))
    errs = []
    if code.count("{") != code.count("}") - 0 and code.replace(r"\{", "").replace(r"\}", "").count("{") != code.replace(r"\{", "").replace(r"\}", "").count("}"):
        errs.append("unbalanced braces")
    for k in (r"\toprule", r"\midrule", r"\bottomrule", r"\begin{tabular}", r"\end{tabular}"):
        if k not in code:
            errs.append(f"missing {k}")
    ncol = None
    for l in code.split("\n"):
        if l.endswith(r"\\") and not l.startswith("\\"):
            n = len(re.findall(r"(?<!\\)&", l)) + 1
            if ncol is None:
                ncol = n
            elif n != ncol and not l.startswith(r"\midrule"):
                errs.append(f"row with {n} cells (expected {ncol}): {l[:60]}")
        elif l.startswith(r"\toprule") or l.strip() == "":
            pass
    m = re.search(r"\\begin\{tabular\}\{(.*)\}", code)
    if m:
        spec = re.sub(r"@\{[^}]*\}", "", m.group(1))
        spec = re.sub(r"p\{[^}]*\}", "p", spec)
        if ncol is not None and len(spec) != ncol:
            errs.append(f"column spec has {len(spec)} columns, rows have {ncol}")
    if len(re.findall(r"^[^%\n]*\\\\ % \S", t, re.M)) < 2:
        errs.append("data rows lack a trailing evidence-id comment")
    return errs


def main():
    t_e4(); t_e5(); t_e6(); t_mech(); t_hand(); t_e7(); t_e8(); t_e9()
    nflag = t_cat()
    order = ["T-E4", "T-E5", "T-E6", "T-MECH", "T-HAND", "T-E7", "T-E8", "T-E9", "T-CAT"]
    bad = 0
    lines = ["# Generated tables (`tests/make_paper_tables.py`; do not edit by hand)", "",
             "Every data row ends with a trailing `% evidence ids` comment. Ids of the form `csv:<path>#<key>` have no row in `EVIDENCE_EXTRACT.md` and point at the committed CSV row instead. Fragments are tabulars only; captions are drafts (at most 3 sentences, numbers only from the CSVs). No TeX toolchain exists on this host, so the fragments were checked by script (brace balance, booktabs commands, equal cell counts per row, column spec) and not compiled.", "",
             "| table | fragment(s) | source CSV(s) | draft caption |", "|---|---|---|---|"]
    for k in order:
        m = META[k]
        for f in m["file"].split("; "):
            errs = check_file(f)
            bad += len(errs)
            if errs:
                print("CHECK FAIL", f, errs)
        lines.append(f"| {k} | {m['file'].replace('; ', '<br>')} | {m['csv'].replace('; ', '<br>')} | {m['cap']} |")
    lines += ["", f"**T-CAT:** {nflag} of 30 shortenings needed judgement and are flagged in `t_cat_judgement.txt` (each lists what was merged or omitted); the rest are direct shortenings of the entry's own false-conclusion text. The family and 'how caught' columns follow the catalog's families table.", "", f"Script checks: {bad} problems."]
    open(f"{OUT}/TABLES.md", "w").write("\n".join(lines) + "\n")
    print("tables written; script-check problems:", bad, "; T-CAT judgement-flagged:", nflag)


if __name__ == "__main__":
    main()
