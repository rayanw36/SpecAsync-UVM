#!/usr/bin/env python3
"""Gate E1b: descriptive handoff-cost analysis. No wall-clock is read.

Per run, from the batch ring ('<6Q6I', 72 B) and decomp ring ('<12Q4I', 112 B):
  enq_ns        sum of enqueue_overhead_ns (kzalloc..queue_work; source-checked)
  prelock_ns    sum over records with t1 != 0 of (t1 - t0) - d3_wait of the
                paired decomp record = Gate 1 predict+enqueue loop + trace loop
                (no-op) + ats flag, i.e. everything before the first lock
                request (valid when num_va_spaces == 1; counted otherwise)
  outside_ns    decomp sum of (svc - D3 - D4) = E1 Part B's quantity
  postlock_ns   outside_ns - prelock_ns (svc time after the last lock release)
Batch record k is paired with decomp record k; alignment is verified by
requiring svc_start <= t0 <= t4 <= svc_end for each pair.
"""
import csv
import statistics as st
import struct
import sys

RAW = "results/phaseB1/gate_e1b/raw"
D = "results/analysis/gate_e/e1b"
CAP = 131071
BF, DF = "<6Q6I", "<12Q4I"


def per_run(r):
    stem = f"{RAW}/e1b_{r['idx']}_{r['workload']}_{r['arm']}{r['L']}"
    b = list(struct.iter_unpack(BF, open(stem + "_batch.bin", "rb").read()))
    d = list(struct.iter_unpack(DF, open(stem + "_decomp.bin", "rb").read()))
    o = dict(idx=r["idx"], workload=r["workload"], arm=r["arm"] + r["L"], batch_records=len(b), decomp_records=len(d),
             full_coverage=int(len(b) < CAP and len(d) < CAP), ft_predictions=int(r["ft_predictions"]),
             enqueued=int(r["enqueued"]), drops=int(r["drops"]), demand_faults=int(r["demand_faults"]))
    o["enq_ns"] = sum(x[10] for x in b)
    o["ring_spec_enqueues"] = sum(x[7] for x in b)
    o["ring_spec_drops"] = sum(x[8] for x in b)
    o["outside_ns"] = sum((x[6] - x[5]) - x[9] - x[10] for x in d)
    o["d3_ns"] = sum(x[9] for x in d)
    misaligned = t1zero = multi_vs = 0
    pre = 0
    for bb, dd in zip(b, d):
        t0, t1, t4 = bb[1], bb[2], bb[5]
        if not (dd[5] <= t0 <= t4 <= dd[6]):
            misaligned += 1
            continue
        if t1 == 0:
            t1zero += 1
            continue
        if dd[13] != 1:
            multi_vs += 1
        pre += (t1 - t0) - dd[9]
    o.update(prelock_ns=pre, pairs_misaligned=misaligned, t1_zero=t1zero, multi_va_space=multi_vs,
             len_mismatch=int(len(b) != len(d)))
    o["postlock_ns"] = o["outside_ns"] - pre
    return o


def main():
    rows = list(csv.DictReader(open(f"{D}/e1b_runs.csv")))
    order = list(csv.DictReader(open(f"{D}/e1b_order.csv")))
    if len(rows) != len(order):
        sys.exit("REFUSING: incomplete run set")
    per = [per_run(r) for r in rows]
    with open(f"{D}/e1b_per_run.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per[0])); w.writeheader(); w.writerows(per)
    for p in per:
        print({k: p[k] for k in ("idx", "workload", "arm", "batch_records", "decomp_records", "full_coverage",
                                 "pairs_misaligned", "t1_zero", "multi_va_space", "len_mismatch")})
    med = {}
    keys = ["enq_ns", "prelock_ns", "outside_ns", "postlock_ns", "d3_ns", "ft_predictions", "enqueued", "drops",
            "ring_spec_enqueues", "demand_faults"]
    for wl, arm in [("stencil", "C1"), ("stencil", "C64096"), ("stencil", "C0"), ("stencil", "C74096"),
                    ("graphbfs", "C1"), ("graphbfs", "C64096")]:
        ps = [p for p in per if p["workload"] == wl and p["arm"] == arm]
        med[(wl, arm)] = {k: st.median(p[k] for p in ps) for k in keys}
        med[(wl, arm)]["n"] = len(ps)
    lines = ["| workload | arm | n | enqueue_overhead total (s) | per prediction (ns) | per enqueued (ns) | pre-lock segment (s) | outside-lock svc − D3 − D4 (s) | post-lock remainder (s) | ft_predictions | enqueued | demand faults |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for (wl, arm), m in med.items():
        pp = m["enq_ns"] / m["ft_predictions"] if m["ft_predictions"] else float("nan")
        pe = m["enq_ns"] / m["enqueued"] if m["enqueued"] else float("nan")
        lines.append(f"| {wl} | {arm} | {m['n']} | {m['enq_ns']/1e9:.4f} | {pp:.0f} | {pe:.0f} | {m['prelock_ns']/1e9:.4f} | "
                     f"{m['outside_ns']/1e9:.4f} | {m['postlock_ns']/1e9:.4f} | {m['ft_predictions']:.0f} | {m['enqueued']:.0f} | {m['demand_faults']:.0f} |")
    lines.append("")
    lines.append("| pair | Δ outside-lock (s) | Δ enqueue_overhead (s) | enqueue ÷ Δ outside | Δ pre-lock (s) | pre-lock ÷ Δ outside | Δ pre-lock − Δ enqueue = predict/lookup (s) | per demand fault in speculative arm (ns) | Δ post-lock (s) |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for wl, base, spec in [("stencil", "C1", "C64096"), ("stencil", "C0", "C74096"), ("graphbfs", "C1", "C64096")]:
        a, b = med[(wl, base)], med[(wl, spec)]
        do = b["outside_ns"] - a["outside_ns"]; de = b["enq_ns"] - a["enq_ns"]; dp = b["prelock_ns"] - a["prelock_ns"]
        dq = b["postlock_ns"] - a["postlock_ns"]
        lines.append(f"| {wl} {spec} − {base} | {do/1e9:+.4f} | {de/1e9:+.4f} | {de/do:.1%} | {dp/1e9:+.4f} | {dp/do:.1%} | "
                     f"{(dp-de)/1e9:+.4f} | {(dp-de)/b['demand_faults']:.0f} | {dq/1e9:+.4f} |")
    open(f"{D}/e1b_summary.md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
