#!/usr/bin/env python3
"""Gate E3b Step 4: descriptive oracle-cost analysis (E1b definitions). No wall-clock read.

Per run (batch ring '<6Q6I' 72 B + decomp ring '<12Q4I' 112 B, paired k<->k and
alignment-checked svc_start <= t0 <= t4 <= svc_end):
  outside_ns  = sum(svc - D3 - D4)       the brief's "pre-lock servicing time" (E1b's outside-lock)
  prelock_ns  = sum(t1 - t0 - D3)        the batch-ring pre-lock segment (check: ~= outside)
  enq_ns      = sum(enqueue_overhead_ns)
  d5_ns       = sum(D5)
  coalesced   = ft_predictions + ft_held + ft_unknown_page + ft_exhausted + ft_fast_cas_giveup
                (Identity 1's right side; held exactly on every Step 2-3 run where
                 trace_pushes was available; Step 4 runs with trace_faults=0)
Per arm: medians. Per speculative arm vs its baseline (C1 or C0):
  increase    = outside(arm) - outside(base)
  residual    = increase - (enq(arm) - enq(base))     per-fault prediction cost
  residual per coalesced fault; fraction of fast-0 residual removed at fast 1.
"""
import csv
import statistics as st
import struct
import sys

RAW = "results/phaseB1/gate_e3b/step4"
D = "results/analysis/gate_e/e3b"
CAP = 131071


def i(r, k):
    return int(r[k]) if r.get(k, "") not in ("", None) else 0


def per_run(r):
    b = list(struct.iter_unpack("<6Q6I", open(f"{RAW}/e3b_{r['idx']}_batch.bin", "rb").read()))
    d = list(struct.iter_unpack("<12Q4I", open(f"{RAW}/e3b_{r['idx']}_decomp.bin", "rb").read()))
    o = dict(idx=r["idx"], arm=r["label"].replace("S4 ", ""), batch_records=len(b), decomp_records=len(d),
             full_coverage=int(len(b) < CAP and len(d) < CAP), len_mismatch=int(len(b) != len(d)))
    o["enq_ns"] = sum(x[10] for x in b)
    o["outside_ns"] = sum((x[6] - x[5]) - x[9] - x[10] for x in d)
    o["d5_ns"] = sum(x[11] for x in d)
    mis = t1z = 0
    pre = 0
    for bb, dd in zip(b, d):
        if not (dd[5] <= bb[1] <= bb[5] <= dd[6]):
            mis += 1
            continue
        if bb[2] == 0:
            t1z += 1
            continue
        pre += (bb[2] - bb[1]) - dd[9]
    o.update(prelock_ns=pre, misaligned=mis, t1_zero=t1z)
    o["coalesced_I1"] = sum(i(r, k) for k in ("ft_predictions", "ft_held", "ft_unknown_page", "ft_exhausted",
                                              "ft_fast_cas_giveup"))
    for k in ("ft_predictions", "enqueued", "drops", "demand_faults", "ft_same_region", "ft_fast_cas_giveup",
              "spec_region_invalid", "ft_fast_verified"):
        o[k] = i(r, k)
    o["I2_diff"] = o["ft_predictions"] - (o["ft_same_region"] + o["enqueued"] + o["drops"])
    return o


def main():
    rows = list(csv.DictReader(open(f"{D}/step4_runs.csv")))
    if len(rows) != len(list(csv.DictReader(open(f"{D}/step4_order.csv")))):
        sys.exit("REFUSING: incomplete")
    per = [per_run(r) for r in rows]
    with open(f"{D}/step4_per_run.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per[0])); w.writeheader(); w.writerows(per)
    print("coverage/alignment:", sorted({(p["full_coverage"], p["len_mismatch"], p["misaligned"], p["t1_zero"]) for p in per}),
          "max records", max(p["batch_records"] for p in per), "| I2 diffs", sorted({p["I2_diff"] for p in per}),
          "| giveup", sorted({p["ft_fast_cas_giveup"] for p in per}), "| region_invalid", sorted({p["spec_region_invalid"] for p in per}))
    arms = {}
    for p in per:
        arms.setdefault(p["arm"], []).append(p)
    M = {a: {k: st.median(p[k] for p in ps) for k in ("enq_ns", "outside_ns", "prelock_ns", "d5_ns", "coalesced_I1",
                                                       "ft_predictions", "enqueued", "drops", "demand_faults")}
         for a, ps in arms.items()}
    for a in M:
        M[a]["n"] = len(arms[a])
    lines = ["| arm | n | outside-lock svc−D3−D4 (s) | pre-lock segment t1−t0−D3 (s) | enqueue_overhead (s) | per prediction (ns) | D5 (s) | ft_predictions | enqueued | drops | coalesced faults (I1) | demand faults |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in sorted(M):
        m = M[a]
        pp = m["enq_ns"] / m["ft_predictions"] if m["ft_predictions"] else float("nan")
        lines.append(f"| {a} | {m['n']} | {m['outside_ns']/1e9:.4f} | {m['prelock_ns']/1e9:.4f} | {m['enq_ns']/1e9:.4f} | "
                     f"{pp:.0f} | {m['d5_ns']/1e9:.4f} | {m['ft_predictions']:.0f} | {m['enqueued']:.0f} | {m['drops']:.0f} | "
                     f"{m['coalesced_I1']:.0f} | {m['demand_faults']:.0f} |")
    lines += ["", "| workload | pair | increase outside-lock (s) | Δ enqueue (s) | **residual** (s) | residual per coalesced fault (ns) | residual per demand fault (ns) | D5 change vs baseline (s) |",
              "|---|---|---|---|---|---|---|---|"]
    res = {}
    for wl, base, specs in (("stencil", "C1", ("C6f0", "C6f1")), ("stencil", "C0", ("C7f0", "C7f1")),
                            ("graphbfs", "C1", ("C6f0", "C6f1"))):
        B = M[f"{wl} {base}"]
        for s in specs:
            S = M[f"{wl} {s}"]
            inc = S["outside_ns"] - B["outside_ns"]
            de = S["enq_ns"] - B["enq_ns"]
            resid = inc - de
            res[(wl, s)] = resid
            lines.append(f"| {wl} | {s} − {base} | {inc/1e9:+.4f} | {de/1e9:+.4f} | **{resid/1e9:+.4f}** | "
                         f"{resid/S['coalesced_I1']:.1f} | {resid/S['demand_faults']:.1f} | {(S['d5_ns']-B['d5_ns'])/1e9:+.4f} |")
    lines += ["", "| workload | pair | residual fast 0 (s) | residual fast 1 (s) | **fraction of residual removed** |", "|---|---|---|---|---|"]
    for wl, a0, a1 in (("stencil", "C6f0", "C6f1"), ("stencil", "C7f0", "C7f1"), ("graphbfs", "C6f0", "C6f1")):
        r0, r1 = res[(wl, a0)], res[(wl, a1)]
        lines.append(f"| {wl} | {a0[:2]} | {r0/1e9:+.4f} | {r1/1e9:+.4f} | **{1 - r1/r0:.1%}** |")
    open(f"{D}/step4_summary.md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
