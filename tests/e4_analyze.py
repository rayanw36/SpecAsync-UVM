#!/usr/bin/env python3
"""Gate E4 Step 4: pre-registered analysis (E4_PREREGISTRATION.md).

Statistical helpers (MWU exact/asymptotic, Holm step-down, MDE, Cohen's d,
Tukey fences) are imported unchanged from tests/e09b_analyze.py; the
Bonferroni-level MDE is set for this gate's family of 18.
Refuses to run unless all rows of the committed order exist (no peeking).

Usage: e4_analyze.py [DATA_DIR [RAW_DIR [FIG_PREFIX]]]
"""
import csv
import os
import statistics as st
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
_argv, sys.argv = sys.argv, sys.argv[:1]
import e09b_analyze as H  # noqa: E402
sys.argv = _argv
H.Z_MDE_BONF = 2.991316 + 0.841621   # two-sided alpha = 0.05/18, power 0.80

D = sys.argv[1] if len(sys.argv) > 1 else "results/analysis/gate_e/e4"
RAW = sys.argv[2] if len(sys.argv) > 2 else "results/phaseB1/gate_e4/sweep"
FIG = sys.argv[3] if len(sys.argv) > 3 else "results/analysis/gate_e/e4_wallclock_by_arm"
WLS = ["stencil", "graphbfs"]
DISTINCT = {"stencil": 1125000, "graphbfs": 287956}
CAP = 131071
ON = ["C7-slow-W1", "C7-W1", "C7-W64", "C7-W512"]
OFF = ["C6-slow-W1", "C6-W1", "C6-W64", "C6-W512"]
FAMILY = ([("F1", a, "C0") for a in ("C7-W1", "C7-W64", "C7-W512")] +
          [("F2", "C7-W1", "C7-slow-W1"), ("F2", "C6-W1", "C6-slow-W1")] +
          [("F3", a, "C1") for a in ("C6-W1", "C6-W64", "C6-W512")] +
          [("F4", "C6-W512", "C0")])
E3B_SERVICING = {"C6": 0.3616, "C7": 0.0414}   # E3b Step 4, Stencil-24K residual removed (s), cross-session only


def g(r, k):
    return int(r[k]) if r.get(k, "") not in ("", None) else 0


def rings(idx):
    b = list(struct.iter_unpack("<6Q6I", open(f"{RAW}/e3b_{idx}_batch.bin", "rb").read()))
    d = list(struct.iter_unpack("<12Q4I", open(f"{RAW}/e3b_{idx}_decomp.bin", "rb").read()))
    return dict(batch_records=len(b), decomp_records=len(d), full_coverage=int(len(b) < CAP and len(d) < CAP),
                enq_ns=sum(x[10] for x in b), outside_ns=sum((x[6] - x[5]) - x[9] - x[10] for x in d),
                d5_ns=sum(x[11] for x in d))


def main():
    order = list(csv.DictReader(open(f"{D}/e4_order.csv")))
    rows = list(csv.DictReader(open(f"{D}/e4_runs.csv")))
    if len(rows) != len(order):
        sys.exit(f"REFUSING: {len(rows)} of {len(order)} rows present -- no interim analysis")
    for r in rows:
        r["arm"] = r["label"].split(" ", 1)[1]
        r.update(rings(r["idx"]))

    # ---- integrity
    integ = [f"rows {len(rows)} / {len(order)}"]
    mism = [o["idx"] for o, r in zip(order, rows) if (o["idx"], o["label"]) != (r["idx"], r["label"])]
    integ.append(f"order adherence: {len(order) - len(mism)} / {len(order)} in sequence; mismatches {mism}")
    integ.append(f"srcversions {sorted({r['srcversion'] for r in rows})}; exit codes {sorted({r['exit_code'] for r in rows})}")
    integ.append(f"dmesg new lines: total {sum(g(r, 'dmesg_new_lines') for r in rows)}; runs with any: "
                 f"{[(r['idx'], r['dmesg_new_lines']) for r in rows if r['dmesg_new_lines'] != '0']}")
    mb = [g(r, "mem_before_kb") for r in rows]; ma = [g(r, "mem_after_kb") for r in rows]
    integ.append(f"MemAvailable kB before {min(mb)}-{max(mb)} after {min(ma)}-{max(ma)}; first {mb[0]} last {ma[-1]}")
    integ.append(f"disk free GB min {min(float(r['disk_free_gb']) for r in rows)}")
    integ.append(f"ring coverage 100% on {sum(r['full_coverage'] for r in rows)} / {len(rows)} runs; max records "
                 f"{max(max(r['batch_records'], r['decomp_records']) for r in rows)}")
    p6 = [r for r in rows if r["policy"] == "6"]
    i1 = [r["idx"] for r in p6 if g(r, "demand_faults") != sum(g(r, k) for k in ("ft_predictions", "ft_held", "ft_unknown_page", "ft_exhausted", "ft_fast_cas_giveup"))]
    i2 = [r["idx"] for r in p6 if g(r, "ft_predictions") != g(r, "ft_same_region") + g(r, "enqueued") + g(r, "drops")]
    integ.append(f"Identity 1 (demand_faults = pred+held+unk+exh+giveup) holds on {len(p6) - len(i1)} / {len(p6)}; fails {i1}")
    integ.append(f"Identity 2 (pred = same_region+enqueued+drops) holds on {len(p6) - len(i2)} / {len(p6)}; fails {i2}")
    fast = [r for r in rows if r["fast"] == "1"]
    integ.append(f"ft_fast_verified = 1 on {sum(r['ft_fast_verified'] == '1' for r in fast)} / {len(fast)} fast loads; "
                 f"cas_giveup max {max(g(r, 'ft_fast_cas_giveup') for r in rows)}; region_invalid max {max(g(r, 'spec_region_invalid') for r in rows)}")
    open(f"{D}/integrity.txt", "w").write("\n".join(integ) + "\n")
    print("\n".join(integ))

    wall = {}
    for r in rows:
        wall.setdefault((r["workload"], r["arm"]), []).append(float(r["wall_s"]))

    # ---- 18 comparisons
    comps = []
    for wl in WLS:
        for fam, arm, base in FAMILY:
            b, c = wall[(wl, base)], wall[(wl, arm)]
            d = dict(family=fam, workload=wl, comparison=f"{arm} vs {base}", arm=arm, baseline=base)
            d.update({k.replace("_c6", "_arm"): v for k, v in H.compare(b, c).items()})
            bk, ck = H.tukey_keep(b), H.tukey_keep(c)
            d2 = H.compare(bk, ck)
            d.update(noout_n_base=len(bk), noout_n_arm=len(ck), noout_delta_s=d2["delta_s"], noout_p=d2["p"])
            comps.append(d)
    thr, sig = H.holm([c["p"] for c in comps])
    thr2, sig2 = H.holm([c["noout_p"] for c in comps])
    for c, t, s, t2, s2 in zip(comps, thr, sig, thr2, sig2):
        c.update(holm_threshold=t, holm_sig=s, noout_holm_threshold=t2, noout_holm_sig=s2)
        c["verdict"] = (f"{c['arm']} faster" if c["delta_s"] < 0 else f"{c['arm']} slower") if s else "no significant difference"
        c["falsification_trigger"] = (c["family"] == "F1" and s and (c["median_base"] - c["median_arm"]) > c["mde_s"])
    with open(f"{D}/primary_comparisons.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(comps[0])); w.writeheader(); w.writerows(comps)
    for c in comps:
        print(f"{c['family']} {c['workload']:8s} {c['comparison']:24s} base {c['median_base']:.4f} arm {c['median_arm']:.4f} "
              f"d {c['delta_s']:+.4f}s ({c['delta_pct']:+.2f}%) p={c['p']:.2e}[{c['mwu_method'][0]}] thr={c['holm_threshold']:.5f} "
              f"{c['verdict']:32s} d={c['cohen_d']:+.2f} MDE={c['mde_s']:.4f} MDE18={c['mde_bonf_s']:.4f} | noout "
              f"{c['noout_delta_s']:+.4f} p={c['noout_p']:.2e} sig={c['noout_holm_sig']} n={c['noout_n_base']}/{c['noout_n_arm']}"
              + ("  ***FALSIFICATION TRIGGER***" if c["falsification_trigger"] else ""))
    print("FALSIFICATION TRIGGER FIRED:", any(c["falsification_trigger"] for c in comps))

    # ---- mechanism per cell
    mech = []
    for wl in WLS:
        for arm in ["C0"] + ON + ["C1"] + OFF:
            rs = [r for r in rows if r["workload"] == wl and r["arm"] == arm]
            m = lambda k: st.median(g(r, k) for r in rs)  # noqa: E731
            mr = lambda k: st.median(r[k] for r in rs)  # noqa: E731
            mech.append(dict(workload=wl, arm=arm, n=len(rs), demand_faults=m("demand_faults"),
                             fault_already_resident=m("fault_already_resident"),
                             far_frac_distinct=m("fault_already_resident") / DISTINCT[wl],
                             ft_predictions=m("ft_predictions"), ft_same_region=m("ft_same_region"),
                             enqueued=m("enqueued"), drops=m("drops"), spec_migrations=m("spec_migrations"),
                             lost_after_enqueue=st.median(g(r, "enqueued") - g(r, "spec_migrations") for r in rs),
                             spec_region_invalid=m("spec_region_invalid"),
                             spec_pages_requested=m("spec_pages_requested"),
                             spec_hits_10ms_staleness_counter=m("spec_hits"),
                             outside_lock_s=mr("outside_ns") / 1e9, enqueue_overhead_s=mr("enq_ns") / 1e9,
                             d5_s=mr("d5_ns") / 1e9))
    with open(f"{D}/mechanism.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(mech[0])); w.writeheader(); w.writerows(mech)
    for x in mech:
        print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in x.items()})

    # ---- F4 and F2 statements
    lines = []
    for wl in WLS:
        mx = [x for x in mech if x["workload"] == wl and x["arm"] == "C6-W512"][0]
        c0 = st.median(wall[(wl, "C0")]); c6 = st.median(wall[(wl, "C6-W512")])
        lines.append(f"F4 {wl}: C6-W512 staged {mx['far_frac_distinct']:.4f} of distinct pages ahead of their fault "
                     f"(fault_already_resident {mx['fault_already_resident']:.0f} / {DISTINCT[wl]}); demand faults "
                     f"{mx['demand_faults']:.0f} (C0 {[x for x in mech if x['workload']==wl and x['arm']=='C0'][0]['demand_faults']:.0f}); "
                     f"wall-clock ratio C6-W512 / C0 = {c6 / c0:.3f}")
    for wl in WLS:
        for p, slow, fastarm in (("C7", "C7-slow-W1", "C7-W1"), ("C6", "C6-slow-W1", "C6-W1")):
            cost = st.median(wall[(wl, slow)]) - st.median(wall[(wl, fastarm)])
            extra = (f"; E3b Stencil servicing-time estimate of the removed residual {E3B_SERVICING[p]:.3f} s "
                     f"(cross-session comparison, not a test)") if wl == "stencil" else ""
            lines.append(f"F2 {wl} {p}: wall-clock cost of the slow oracle's overhead = median({slow}) - median({fastarm}) = {cost:+.4f} s{extra}")
    open(f"{D}/f2_f4_statements.txt", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))

    # ---- central figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    for ax, wl, title in zip(axes, WLS, ["Stencil-24K", "GraphBFS-23"]):
        for ref, col in (("C0", "tab:blue"), ("C1", "tab:gray")):
            v = wall[(wl, ref)]; q = st.quantiles(v, n=4, method="inclusive")
            ax.axhline(st.median(v), color=col, lw=1.5, label=f"{ref} median (IQR shaded)")
            ax.axhspan(q[0], q[2], color=col, alpha=0.13)
        xs = list(range(len(ON))) + [len(ON) + 1 + i for i in range(len(OFF))]
        for x, arm, col in zip(xs, ON + OFF, ["tab:green"] * len(ON) + ["tab:red"] * len(OFF)):
            v = wall[(wl, arm)]
            ax.scatter([x] * len(v), v, s=12, color=col, alpha=0.45, zorder=3)
            ax.plot([x - 0.3, x + 0.3], [st.median(v)] * 2, color=col, lw=2.5, zorder=4)
        ax.axvspan(-0.5, len(ON) - 0.5, color="tab:green", alpha=0.05)
        ax.axvspan(len(ON) + 0.5, xs[-1] + 0.5, color="tab:red", alpha=0.05)
        ax.set_xticks(xs); ax.set_xticklabels(ON + OFF, rotation=35, ha="right", fontsize=8)
        ax.set_ylabel("process wall-clock (s)"); ax.set_title(f"{title} (n=10 per cell)\nprefetch ON (green) | prefetch OFF (red)", fontsize=10)
        ax.grid(alpha=0.3, axis="y")
    axes[0].legend(fontsize=8, loc="best")
    fig.suptitle("Gate E4: wall-clock per arm (RTX 5070 Ti, 595.91.07, kernel 7.0.0-34; L = 4096)", fontsize=10)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(f"{FIG}.{ext}", dpi=150)


if __name__ == "__main__":
    main()
