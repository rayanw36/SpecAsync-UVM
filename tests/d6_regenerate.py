#!/usr/bin/env python3
"""D6 regeneration (computation only; no runs, no driver interaction, no edits to any report).

For each PROSE-ONLY row of consolidation/D6_RAW_INVENTORY.md whose raw input exists on disk, recompute the number from
the raw (gitignored) files, write a small derived CSV under results/analysis/derived/, and record a derived-vs-prose
comparison row in results/analysis/derived/d6_comparison.csv. A mismatch is recorded with BOTH values; the prose is never
"corrected". Where a committed script exists it is imported and reused (tests/gate_e07_accuracy_analysis.py,
tests/gate_e08_index_drift_analysis.py, tests/gatec1_decomp_analysis.py's record layout); the others are the
commands recorded in the reports' own prose, turned into code here.

usage: d6_regenerate.py [row ...]     rows: 1 2 3 4 5 6 7 8 9 10 (default: all)
"""
import csv
import io
import os
import statistics as st
import struct
import sys
from contextlib import redirect_stdout

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.chdir(REPO)
OUT = "results/analysis/derived"
os.makedirs(OUT, exist_ok=True)
COMP = []                       # (row, quantity, derived, prose, prose_source, match, note)


def cmp(row, quantity, derived, prose, source, tol=None, note=""):
    """Record a comparison. Numbers are compared after rounding to the prose's own precision; text exactly."""
    if isinstance(prose, (int, float)) and isinstance(derived, (int, float)):
        if tol is None:
            ok = derived == prose
        else:
            ok = abs(derived - prose) <= tol
    else:
        ok = str(derived) == str(prose)
    COMP.append((row, quantity, derived, prose, source, "MATCH" if ok else "MISMATCH", note))
    return ok


def wcsv(name, header, rows):
    with open(f"{OUT}/{name}", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


# ------------------------------------------------------------------ rows 1 and 2: trace entry counts
def row1_2():
    # Row 1: E0 section 2/7. The committed headline traces are under phaseB2/gate3_interleaved (entries = size / 8).
    # The coalesced-faults-per-run figures are T4 measurements quoted from GATE_T4_REPORT.md (no raw file): used as constants.
    rows = []
    for wl, path, faults, prose_entries, prose_ratio in (
            ("Stencil-24K", "results/phaseB2/gate3_interleaved/c3_bench_stencil_trace.bin", 3237375, 276961, 11.7),
            ("GraphBFS-23", "results/phaseB2/gate3_interleaved/c3_bench_graph_bfs_trace.bin", 445721, 207564, 2.1)):
        n = os.path.getsize(path) // 8
        ratio = faults / n
        rows.append([1, wl, path, n, faults, f"{ratio:.4f}"])
        cmp(1, f"{wl} trace entries (size/8)", n, prose_entries, "GATE_E0_REPORT.md section 2")
        cmp(1, f"{wl} coalesced faults per run / trace entries", round(ratio, 1), prose_ratio, "GATE_E0_REPORT.md section 7",
            note=f"coalesced faults {faults:,} are quoted from GATE_T4_REPORT.md (T4; not regenerable from a raw file)")
    # Row 2: E0.5 Step 5 post-fix 1:1 alignment: trace entries of the fresh collections.
    for wl, path, prose in (("Stencil-24K", "results/phaseB1/gate_e05_realworkload/stencil24k_trace.bin", 2953867),
                            ("GraphBFS-23", "results/phaseB1/gate_e05_realworkload/graphbfs23_trace.bin", 483896)):
        n = os.path.getsize(path) // 8
        rows.append([2, wl, path, n, prose, f"{n / prose:.6f}"])
        cmp(2, f"{wl} trace entries == coalesced faults ({prose:,})", n, prose, "GATE_E0_5_REPORT.md Step 5",
            note="the counter value (demand_faults) is prose; the trace entry count is derived from the raw trace file")
    wcsv("d6_row01_02_trace_entries.csv", ["row", "workload", "raw_file", "trace_entries", "coalesced_faults_prose", "ratio_faults_per_entry"], rows)


# ------------------------------------------------------------------ rows 3 and 4: batch-ring parse (the scripts' own embedded block)
BFMT = "<6Q6I"
BSZ = struct.calcsize(BFMT)


def parse_batch(path):
    r = open(path, "rb").read()
    v = nf = enq = hits = drops = 0
    for i in range(len(r) // BSZ):
        x = struct.unpack(BFMT, r[i * BSZ:(i + 1) * BSZ])
        if x[1] == 0 or x[5] < x[1]:
            continue
        v += 1
        nf += x[6]
        enq += x[7]
        drops += x[8]
        hits += x[9]
    return v, nf, enq, hits, drops


def row3():
    d = "results/phaseB1/oracle_coalesce"
    out = []
    got = {}
    for tag in ("old", "new"):
        v, nf, enq, hits, _ = parse_batch(f"{d}/{tag}_batch.bin")
        tr = os.path.getsize(f"{d}/{tag}_trace.bin") // 8
        got[tag] = (v, nf, enq, hits, tr)
        out.append([tag, tr, v, nf, enq, hits, f"{hits / enq:.6f}", f"{nf / v:.3f}"])
    wcsv("d6_row03_oracle_coalesce.csv", ["module", "trace_entries", "valid_batches", "coalesced_faults", "spec_enqueued", "spec_hits", "hit_rate", "faults_per_batch"], out)
    S = "GATE_E0_5_REPORT.md Addition 2"
    n = got["new"]
    o = got["old"]
    cmp(3, "new: valid batches", n[0], 56, S)
    cmp(3, "new: total coalesced faults", n[1], 442, S)
    cmp(3, "new: spec_hits", n[3], 23, S)
    cmp(3, "new: trace entries", n[4], 450, S)
    cmp(3, "old: valid batches", o[0], 57, S)
    cmp(3, "old: total coalesced faults", o[1], 451, S)
    cmp(3, "old: spec_hits", o[3], 1, S)
    cmp(3, "old: trace entries", o[4], 445, S)
    cmp(3, "442/56 (faults per batch), 1 dp", round(n[1] / n[0], 1), 7.9, S)
    cmp(3, "23/56 = hit rate of enqueued, % 2 dp", round(100 * n[3] / n[2], 2), 41.07, S)
    cmp(3, "1/7.9 as a % of faults, 1 dp", round(100 / 7.9, 1), 12.7, S)
    cmp(3, "442/450 (new), 3 dp", round(n[1] / n[4], 3), 0.982, S)
    cmp(3, "451/445 (old), 3 dp", round(o[1] / o[4], 3), 1.013, S)
    cmp(3, "hits difference new - old", n[3] - o[3], 22, S, note="'1/57 -> 23/56 (22 events)'")


def row4():
    d = "results/phaseB1/oracle_probe"
    out = []
    for tag in ("old_buggy", "new_fix"):
        v, nf, enq, hits, _ = parse_batch(f"{d}/{tag}_batch.bin")
        out.append([tag, v, nf, enq, hits, f"{hits / enq:.4f}"])
        cmp(4, f"{tag}: spec_hits / spec_enqueued", f"{hits}/{enq}", "254/256", "GATE_A_report.md; PIPELINE_FIXES.md:57-63")
        cmp(4, f"{tag}: hit rate, 2 dp", round(hits / enq, 2), 0.99, "driver/PIPELINE_FIXES.md (serialized row)")
    wcsv("d6_row04_oracle_probe.csv", ["module", "valid_batches", "coalesced_faults", "spec_enqueued", "spec_hits", "hit_rate"], out)


# ------------------------------------------------------------------ rows 5 and 6: E0.7 / E0.8 / E0.9
def rows5_6():
    import gate_e07_accuracy_analysis as A7
    import gate_e08_index_drift_analysis as A8
    D1, D2 = "results/phaseB1/gate_e07_check1", "results/phaseB1/gate_e07_check2"
    S8, S9 = "GATE_E0_8_REPORT.md", "GATE_E0_9_REPORT.md"
    quiet = io.StringIO()
    out5, out6 = [], []
    prose_fwd = {("stencil24k", 1): 98.48, ("stencil24k", 0): 0.43, ("graphbfs23", 1): 36.51, ("graphbfs23", 0): 35.55}
    prose_bwd = {("stencil24k", 1): 0.0708, ("stencil24k", 0): 99.5854, ("graphbfs23", 1): 73.8671}
    prose_sp = {("stencil24k", 1): 0.9999999983, ("stencil24k", 0): 0.9999999984, ("graphbfs23", 1): 0.9976364, ("graphbfs23", 0): 0.9986221}
    prose_md = {("stencil24k", 1): 105, ("stencil24k", 0): 107, ("graphbfs23", 1): 38990, ("graphbfs23", 0): 36618}
    prose_ex = {("stencil24k", 1): 25134, ("stencil24k", 0): 25891, ("graphbfs23", 1): 7661, ("graphbfs23", 0): 7730}
    prose_sym = {("stencil24k", 10): 44.30, ("stencil24k", 100): 99.9997, ("stencil24k", 1000): 100.0,
                 ("graphbfs23", 10): 4.23, ("graphbfs23", 100): 11.30, ("graphbfs23", 1000): 46.49}
    for wl in ("stencil24k", "graphbfs23"):
        trace = A7.load_u64(f"{D1}/{wl}_trace.bin")
        for depth, fn in ((1, f"{wl}_replay_order.bin"), (0, f"{wl}_replay_order_depth0.bin")):
            rep = A7.load_u64(f"{D1}/{fn}")
            key = (wl, depth)
            # E0.7 forward-set: prediction k scored against actual k; "set" = predicted page appears anywhere in actual[k:]
            k_idx = np.arange(1, len(rep), dtype=np.int64)
            predicted, actual = trace[k_idx % len(trace)], rep[k_idx]
            fwd = 100 * float(A7.set_accuracy(predicted, actual).mean())
            cmp(6, f"{wl} depth={depth} forward-set (E0.7), % 2 dp", round(fwd, 2), prose_fwd[key], f"{S8} section 1")
            row = dict(workload=wl, depth=depth, trace_len=len(trace), replay_len=len(rep), forward_set_pct=fwd)
            if key in prose_bwd:
                with redirect_stdout(quiet):
                    b = A8.check1_backward_set(trace, rep, f"{wl} d{depth}")
                row["backward_set_pct"] = 100 * b["overall"]
                cmp(6, f"{wl} depth={depth} backward-set (Check 1), % 4 dp", round(100 * b["overall"], 4), prose_bwd[key], f"{S8} section 1")
            # Check 4: first-touch order
            ftA, ftB = A8.first_touch_sequence(trace), A8.first_touch_sequence(rep)
            import pandas as pd
            rA = pd.Series(np.arange(len(ftA)), index=ftA)
            rB = pd.Series(np.arange(len(ftB)), index=ftB)
            common = rA.index.intersection(rB.index)
            a, b = rA.loc[common].values, rB.loc[common].values
            from scipy.stats import spearmanr
            sp = float(spearmanr(a, b)[0])
            md = int(np.abs(a - b).max())
            n = min(len(ftA), len(ftB))
            exact = int((ftA[:n] == ftB[:n]).sum())
            row.update(common_pages=len(common), spearman=sp, max_rank_displacement=md, reduced_exact_match=exact)
            cmp(5, f"{wl} depth={depth} first-touch Spearman, 10 dp", round(sp, 10), prose_sp[key], f"{S8} section 4", tol=6e-8,
                note="prose gives 10 significant digits for Stencil and 7 for GraphBFS")
            cmp(5, f"{wl} depth={depth} max |rank diff|", md, prose_md[key], f"{S8} section 4",
                note="both values recorded; prose not corrected" if md != prose_md[key] else "")
            cmp(5, f"{wl} depth={depth} reduced exact-match count", exact, prose_ex[key], f"{S8} section 4")
            if depth == 1:
                d = np.abs(a - b)
                for W in (10, 100, 1000):
                    sym = 100 * float((d <= W).mean())
                    row[f"symmetric_le_{W}_pct"] = sym
                    dp = 4 if (wl == "stencil24k" and W >= 100) else 2          # the prose's own precision
                    cmp(6, f"{wl} depth=1 symmetric |rank diff| <= {W}, % {dp} dp", round(sym, dp), prose_sym[(wl, W)], f"{S9} section 1")
                if wl == "stencil24k":
                    a2, b2 = ftA[:n], ftB[:n]
                    w100 = 100 * float(A7.windowed_accuracy(a2, b2, 100).mean())
                    sset = 100 * float(A7.set_accuracy(a2, b2).mean())
                    row.update(reduced_window100_forward_pct=w100, reduced_set_forward_pct=sset)
                    cmp(6, "stencil24k depth=1 reduced window W=100 forward, % 2 dp", round(w100, 2), 51.19, f"{S8} section 4 (the ~51.19% ceiling)")
                    cmp(6, "stencil24k depth=1 reduced set forward, % 2 dp", round(sset, 2), 51.19, f"{S8} section 4")
            out5.append(row)
    # Check 6: pairs of plain-C1 traces
    prose_pairs = {("stencil24k", 1, 2): (4418, 1.94, 98.14), ("stencil24k", 1, 3): (3171, 2.95, 97.08), ("stencil24k", 2, 3): (1247, 21.21, 78.92),
                   ("graphbfs23", 1, 2): (1365, 70.89, 39.46), ("graphbfs23", 1, 3): (4351, 80.57, 28.85), ("graphbfs23", 2, 3): (2986, 78.61, 31.14)}
    prose_gap = {("graphbfs23", 1, 2): 31.43, ("graphbfs23", 2, 3): 47.47, ("graphbfs23", 1, 3): 51.72}
    for wl in ("stencil24k", "graphbfs23"):
        reps = {i: A7.load_u64(f"{D2}/{wl}_c1_rep{i}.bin") for i in (1, 2, 3)}
        for (i, j) in ((1, 2), (1, 3), (2, 3)):
            A, B = reps[i], reps[j]
            n = min(len(A), len(B))
            cnt = abs(len(A) - len(B))
            fwd = 100 * float(A7.set_accuracy(A[:n], B[:n]).mean())
            with redirect_stdout(quiet):
                bwd = 100 * A8.check1_backward_set(A, B, f"{wl} {i}v{j}")["overall"]
            p = prose_pairs[(wl, i, j)]
            out6.append([wl, f"rep{i} vs rep{j}", len(A), len(B), cnt, f"{fwd:.4f}", f"{bwd:.4f}", f"{abs(fwd - bwd):.4f}"])
            cmp(6, f"{wl} rep{i} vs rep{j} |count diff|", cnt, p[0], f"{S8} section 6")
            cmp(6, f"{wl} rep{i} vs rep{j} forward-set, % 2 dp", round(fwd, 2), p[1], f"{S8} section 6")
            cmp(6, f"{wl} rep{i} vs rep{j} backward-set, % 2 dp", round(bwd, 2), p[2], f"{S8} section 6")
            if (wl, i, j) in prose_gap:
                cmp(6, f"{wl} rep{i} vs rep{j} |forward - backward|, pts 2 dp", round(abs(fwd - bwd), 2), prose_gap[(wl, i, j)], f"{S9} section 1 (Correction 2)")
    keys = sorted({k for r in out5 for k in r})
    wcsv("d6_row05_06_e08_checks.csv", keys, [[r.get(k, "") for k in keys] for r in out5])
    wcsv("d6_row06_e08_pairs.csv", ["workload", "pair", "len_A", "len_B", "abs_count_diff", "forward_set_pct", "backward_set_pct", "abs_forward_minus_backward_pts"], out6)


# ------------------------------------------------------------------ row 7: E4 table check
def row7():
    def table(p):
        return np.fromfile(p, dtype="<u8")[2:]          # 16-byte header, then one u64 page address per first-touch rank

    def disp(a, b):
        pos = {int(v): i for i, v in enumerate(b.tolist())}
        return max(abs(i - pos[int(v)]) for i, v in enumerate(a.tolist())), set(a.tolist()) == set(b.tolist())
    base = "results/phaseB1/gate_e4"
    rows = []
    prose = {("stencil", "post"): 98, ("graphbfs", "post"): 35823, ("stencil", "smoke"): 96, ("graphbfs", "smoke"): 37992}
    for wl in ("stencil", "graphbfs"):
        sweep = table(f"{base}/tables/{wl}_ft_table.bin")
        for tag, d in (("post", "postreboot_check"), ("smoke", "smoke_tables")):
            other = table(f"{base}/{d}/{wl}_ft_table.bin")
            md, same = disp(other, sweep)
            rows.append([wl, d, len(other), same, md])
            cmp(7, f"{wl}: max first-touch rank displacement, {d} vs sweep tables", md, prose[(wl, tag)], "E4_STATUS.md Table-validity check")
            cmp(7, f"{wl}: same page set, {d} vs sweep tables", same, True, "E4_STATUS.md Table-validity check")
    wcsv("d6_row07_e4_table_check.csv", ["workload", "compared_dir", "entries", "same_page_set", "max_rank_displacement"], rows)


# ------------------------------------------------------------------ row 8: E0.9a-2 per-prediction usefulness / prevented
def row8():
    d = "results/phaseB1/gate_e09a2_validation"
    rows = []
    for wl in ("graphbfs23", "stencil24k"):
        table = np.fromfile(f"{d}/{wl}_ft_table.bin", dtype="<u8")[2:]
        for L, depth in ((1, 1), (16, 1), (256, 1), (4096, 1), (4096, 0)):
            fl, ro = f"{d}/{wl}_L{L}_depth{depth}_ftlog.bin", f"{d}/{wl}_L{L}_depth{depth}_replayorder.bin"
            if not (os.path.exists(fl) and os.path.exists(ro)):
                continue
            packed = np.fromfile(fl, dtype="<u8")
            seq, rank = (packed >> 32).astype(np.int64), (packed & 0xFFFFFFFF).astype(np.int64)
            replay = np.fromfile(ro, dtype="<u8")
            last = {}
            for i in range(len(replay) - 1, -1, -1):
                v = int(replay[i])
                if v not in last:
                    last[v] = i
            ok = rank < len(table)
            page = table[np.where(ok, rank, 0)]
            lp = np.array([last.get(int(p), -1) for p in page])
            useful = int(((lp > seq) & ok).sum())
            n = int(len(packed))
            rows.append([wl, L, depth, n, int(ok.sum()), useful, f"{100 * useful / n:.4f}", f"{100 * (n - useful) / n:.4f}"])
            if wl == "graphbfs23" and depth == 1:
                cmp(8, f"graphbfs23 L={L} usefulness, % 4 dp", round(100 * useful / n, 4), 100.0, "GATE_E0_9A2_REPORT.md section 7")
                cmp(8, f"graphbfs23 L={L} prevented, % 4 dp", round(100 * (n - useful) / n, 4), 0.0, "GATE_E0_9A2_REPORT.md section 7")
            if wl == "stencil24k" and L == 1 and depth == 1:
                cmp(8, "stencil24k L=1 depth=1 logged predictions", n, 140909, "GATE_E0_9_REPORT.md section 4 (E0.9a)",
                    note="the prose count is from E0.9a; these raw files are E0.9a-2's own (different) run, so the two need not agree. Both values recorded; prose not corrected")
                cmp(8, "stencil24k L=1 depth=1 usefulness, % 4 dp", round(100 * useful / n, 4), 100.0, "GATE_E0_9_REPORT.md section 4")
            if wl == "stencil24k" and depth == 1:
                cmp(8, f"stencil24k L={L} prevented, % 4 dp", round(100 * (n - useful) / n, 4), 0.0, "GATE_E0_9A2_REPORT.md section 7 ('on both workloads')")
    wcsv("d6_row08_prevented.csv", ["workload", "L", "depth", "logged_predictions", "rank_in_table", "touched_again_after", "usefulness_pct", "prevented_pct"], rows)


# ------------------------------------------------------------------ row 9: corrected pipelining ceilings (4 conventions)
def row9():
    DFMT = "<12Q4I"
    DSZ = struct.calcsize(DFMT)

    def trial(path):
        raw = open(path, "rb").read()
        d12 = tot = 0
        starts, ends = [], []
        for i in range(len(raw) // DSZ):
            f = struct.unpack_from(DFMT, raw, i * DSZ)
            d1 = f[2] - f[1] if f[2] > f[1] else 0
            d2 = f[4] - f[3] if f[4] > f[3] else 0
            end = max(f[6], f[8] if f[8] > 0 else 0)
            total = end - f[1] if end > f[1] else 0
            d12 += d1 + d2
            tot += total
            starts.append(f[1])
            ends.append(end)
        return d12, tot, (max(ends) - min(starts)) if starts else 0

    plat = {"5070 Ti": ("results/phaseC/paired_wallclock_5070ti", "t3_paired_times_5070ti.csv"),
            "T4": ("results/phaseC/paired_wallclock", "t3_paired_times.csv")}
    prose = {  # published, span/sum-agg, sum/median-agg, span/median-agg ceilings (CEILING_BASIS_VERIFICATION.md section 6), and D1+D2 share
        ("Stencil-8K", "5070 Ti"): (31.85, 16.92, 19.79, 3.34, 3.92), ("GraphBFS-23", "5070 Ti"): (13.71, 0.13, 0.38, 0.03, 0.08),
        ("Sweep-4K", "5070 Ti"): (32.54, 8.19, 9.30, 1.63, 1.86), ("Sweep-8K", "5070 Ti"): (31.94, 16.73, 19.67, 3.34, 3.94),
        ("Sweep-16K", "5070 Ti"): (32.20, 26.33, 32.61, 5.27, 6.53), ("Sweep-24K", "5070 Ti"): (31.74, 29.02, 36.55, 5.74, 7.25),
        ("Stencil-8K", "T4"): (33.34, 19.06, 35.90, 3.67, 7.09), ("GraphBFS-23", "T4"): (13.36, 0.20, 0.64, 0.04, 0.13),
        ("Sweep-4K", "T4"): (36.19, 12.18, 21.69, 2.44, 4.34), ("Sweep-8K", "T4"): (34.47, 18.33, 36.80, 3.67, 7.39),
        ("Sweep-16K", "T4"): (30.72, 16.39, 39.93, 3.26, 7.94), ("Sweep-24K", "T4"): (26.99, 15.31, 37.11, 3.05, 7.43)}
    rows = []
    for pname, (d, csvname) in plat.items():
        times = list(csv.DictReader(open(f"{d}/{csvname}")))
        for wl in ("Stencil-8K", "GraphBFS-23", "Sweep-4K", "Sweep-8K", "Sweep-16K", "Sweep-24K"):
            trials = [trial(f"{d}/decomp/{wl}_trial{k}.bin") for k in range(1, 6)]
            walls = [float(r["wall_s"]) * 1e6 for r in times if r["config"] == wl]        # microseconds
            med_wall = st.median(walls)
            sum12, sumtot = sum(t[0] for t in trials), sum(t[1] for t in trials)
            share = sum12 / sumtot
            sums = [t[1] / 1e3 for t in trials]                                           # us
            spans = [t[2] / 1e3 for t in trials]
            conv = {"sum_sumagg": sum(sums), "span_sumagg": sum(spans), "sum_medagg": st.median(sums), "span_medagg": st.median(spans)}
            ceil = {k: 100 * share * v / med_wall for k, v in conv.items()}
            rows.append([pname, wl, f"{100 * share:.2f}", med_wall] + [f"{ceil[k]:.2f}" for k in ("sum_sumagg", "span_sumagg", "sum_medagg", "span_medagg")])
            p = prose[(wl, pname)]
            S = "CEILING_BASIS_VERIFICATION.md section 6"
            cmp(9, f"{pname} {wl} D1+D2 share, % 2 dp", round(100 * share, 2), p[0], S)
            for k, pv in zip(("sum_sumagg", "span_sumagg", "sum_medagg", "span_medagg"), p[1:]):
                cmp(9, f"{pname} {wl} ceiling [{k}], % 2 dp", round(ceil[k], 2), pv, S)
    wcsv("d6_row09_ceilings.csv", ["platform", "workload", "d1d2_share_pct", "median_wall_us", "ceiling_published_sum_sumagg_pct",
                                   "ceiling_span_sumagg_pct", "ceiling_sum_medagg_pct", "ceiling_span_medagg_pct"], rows)
    span_med = [float(r[7]) for r in rows]
    cmp(9, "range of span/median-agg ceilings, min % 2 dp", round(min(span_med), 2), 0.08, "CEILING_BASIS_VERIFICATION.md section 7 (0.08-7.94%)")
    cmp(9, "range of span/median-agg ceilings, max % 2 dp", round(max(span_med), 2), 7.94, "CEILING_BASIS_VERIFICATION.md section 7 (0.08-7.94%)")


# ------------------------------------------------------------------ row 10: B10 "truncated + rotated"
def row10():
    CAP = 1048576
    rows = []
    for d in ("results/analysis/gate_b10_augmentation", "results/analysis/gate_b10_replication"):
        for f in sorted(os.listdir(d)):
            if f.endswith("_trace.bin"):
                n = os.path.getsize(f"{d}/{f}") // 8
                rows.append([f"{d}/{f}", n, CAP, n == CAP])
    wcsv("d6_row10_b10_trace_capacity.csv", ["trace_file", "entries", "ring_capacity", "entries_equal_capacity"], rows)
    cmp(10, "B10 C4 trace files with entries == ring capacity (1,048,576)", f"{sum(1 for r in rows if r[3])}/{len(rows)}", f"{len(rows)}/{len(rows)}",
        "GATE_E0_5_REPORT.md Addition 3 ('truncated + rotated')",
        note="a full ring is what truncation looks like from the file; whether it is also ROTATED needs the push count (head mod capacity), which is not in the file, so rotation is not regenerated here")


if __name__ == "__main__":
    want = {int(a) for a in sys.argv[1:]} or set(range(1, 11))
    for fn, rows in ((row1_2, {1, 2}), (row3, {3}), (row4, {4}), (rows5_6, {5, 6}), (row7, {7}), (row8, {8}), (row9, {9}), (row10, {10})):
        if want & rows:
            print(f"== rows {sorted(rows)}", flush=True)
            fn()
    path = f"{OUT}/d6_comparison.csv"
    old = []
    if os.path.exists(path) and len(sys.argv) > 1:
        old = [r for r in csv.reader(open(path))][1:]
        old = [r for r in old if int(r[0]) not in want]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["row", "quantity", "derived", "prose", "prose_source", "result", "note"])
        w.writerows(sorted(old + [list(map(str, r)) for r in COMP], key=lambda r: int(r[0])))
    mm = [r for r in COMP if r[5] == "MISMATCH"]
    print(f"{len(COMP)} comparisons this run: {len(COMP) - len(mm)} MATCH, {len(mm)} MISMATCH")
    for r in mm:
        print("  MISMATCH row", r[0], "|", r[1], "| derived", r[2], "| prose", r[3])
