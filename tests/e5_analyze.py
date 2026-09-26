#!/usr/bin/env python3
"""Gate E5 Step 4: pre-registered analysis (E5_PREREGISTRATION.md).

Statistical helpers imported unchanged from tests/e09b_analyze.py. Refuses to
run unless all 60 rows of the committed order exist (no peeking).

Primary mechanism test: D(t) = 1 - median(demand_faults, C7W512-t) /
median(demand_faults, C0-t) for t in {51, 75, T_off=100}; two-sided MWU on
demand faults per t, Holm across the 3. H-feed verdict, mechanical:
  Supported : D(51) > 0 and Holm-significant, and D(T_off) < 0.25 * D(51)
  Refuted   : D(51) > 0 and D(T_off) >= 0.75 * D(51)
  Partial   : D(51) > 0 and anything between
  Not classifiable : D(51) <= 0 (the ratio is undefined; reported as such)
Dose-response (secondary): D(75) >= D(51)?
Secondary: wall-clock C7W512-t vs C0-t, 3 comparisons, one Holm family.
Usage: e5_analyze.py [DATA_DIR [RAW_DIR [FIG_PREFIX]]]
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
H.Z_MDE_BONF = 2.393980 + 0.841621   # two-sided alpha = 0.05/3, power 0.80

D = sys.argv[1] if len(sys.argv) > 1 else "results/analysis/gate_e/e5"
RAW = sys.argv[2] if len(sys.argv) > 2 else "results/phaseB1/gate_e5/sweep"
FIG = sys.argv[3] if len(sys.argv) > 3 else "results/analysis/gate_e/e5_threshold"
TS = [("t51", 51), ("t75", 75), ("toff", 100)]
CAP = 131071
DISTINCT = 1125000


def g(r, k):
    return int(r[k]) if r.get(k, "") not in ("", None) else 0


def rings(idx):
    b = list(struct.iter_unpack("<6Q6I", open(f"{RAW}/e3b_{idx}_batch.bin", "rb").read()))
    d = list(struct.iter_unpack("<12Q4I", open(f"{RAW}/e3b_{idx}_decomp.bin", "rb").read()))
    return dict(batch_records=len(b), decomp_records=len(d), full_coverage=int(len(b) < CAP and len(d) < CAP),
                enq_ns=sum(x[10] for x in b), outside_ns=sum((x[6] - x[5]) - x[9] - x[10] for x in d),
                d5_ns=sum(x[11] for x in d))


def main():
    order = list(csv.DictReader(open(f"{D}/e5_order.csv")))
    rows = list(csv.DictReader(open(f"{D}/e5_runs.csv")))
    if len(rows) != len(order):
        sys.exit(f"REFUSING: {len(rows)} of {len(order)} rows present -- no interim analysis")
    for r in rows:
        name = r["label"].split(" ", 1)[1]
        r["arm"], r["tn"] = name.rsplit("-", 1)
        r.update(rings(r["idx"]))

    integ = [f"rows {len(rows)} / {len(order)}"]
    mism = [o["idx"] for o, r in zip(order, rows) if (o["idx"], o["label"]) != (r["idx"], r["label"])]
    integ.append(f"order adherence: {len(order) - len(mism)} / {len(order)} in sequence; mismatches {mism}")
    integ.append(f"srcversions {sorted({r['srcversion'] for r in rows})}; exit codes {sorted({r['exit_code'] for r in rows})}")
    integ.append(f"dmesg new lines total {sum(g(r, 'dmesg_new_lines') for r in rows)}; runs with any "
                 f"{[(r['idx'], r['dmesg_new_lines']) for r in rows if r['dmesg_new_lines'] != '0']}")
    mb = [g(r, "mem_before_kb") for r in rows]; ma = [g(r, "mem_after_kb") for r in rows]
    integ.append(f"MemAvailable kB before {min(mb)}-{max(mb)} after {min(ma)}-{max(ma)}")
    integ.append(f"ring coverage 100% on {sum(r['full_coverage'] for r in rows)} / {len(rows)}; max records "
                 f"{max(max(r['batch_records'], r['decomp_records']) for r in rows)}")
    p6 = [r for r in rows if r["policy"] == "6"]
    i1 = [r["idx"] for r in p6 if g(r, "demand_faults") != sum(g(r, k) for k in ("ft_predictions", "ft_held", "ft_unknown_page", "ft_exhausted", "ft_fast_cas_giveup"))]
    i2 = [r["idx"] for r in p6 if g(r, "ft_predictions") != g(r, "ft_same_region") + g(r, "enqueued") + g(r, "drops")]
    integ.append(f"Identity 1 holds {len(p6) - len(i1)} / {len(p6)} (fails {i1}); Identity 2 holds {len(p6) - len(i2)} / {len(p6)} (fails {i2})")
    integ.append(f"ft_fast_verified = 1 on {sum(r['ft_fast_verified'] == '1' for r in p6)} / {len(p6)}; "
                 f"cas_giveup max {max(g(r, 'ft_fast_cas_giveup') for r in rows)}; region_invalid max {max(g(r, 'spec_region_invalid') for r in rows)}")
    open(f"{D}/integrity.txt", "w").write("\n".join(integ) + "\n")
    print("\n".join(integ))

    cell = lambda arm, tn: [r for r in rows if r["arm"] == arm and r["tn"] == tn]  # noqa: E731

    # ---- primary: demand-fault reduction D(t)
    dres = []
    for tn, t in TS:
        c0 = [g(r, "demand_faults") for r in cell("C0", tn)]
        c7 = [g(r, "demand_faults") for r in cell("C7W512", tn)]
        U, p, meth = H.mwu(c7, c0)
        dres.append(dict(threshold=t, median_df_C0=st.median(c0), median_df_C7W512=st.median(c7),
                         D=1 - st.median(c7) / st.median(c0), U=U, p=p, mwu_method=meth))
    thr, sig = H.holm([x["p"] for x in dres])
    for x, t_, s in zip(dres, thr, sig):
        x["holm_threshold"], x["holm_sig"] = t_, s
    D51, D75, Doff = (x["D"] for x in dres)
    sig51 = dres[0]["holm_sig"]
    if D51 <= 0:
        verdict, ratio = "NOT CLASSIFIABLE (D(51) <= 0)", float("nan")
    else:
        ratio = Doff / D51
        if sig51 and ratio < 0.25:
            verdict = "SUPPORTED"
        elif ratio >= 0.75:
            verdict = "REFUTED"
        else:
            verdict = "PARTIAL"
    with open(f"{D}/fault_reduction.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dres[0])); w.writeheader(); w.writerows(dres)
    lines = ["| threshold | median demand faults C0 | median demand faults C7W512 | D(t) | MWU p (demand faults) | Holm thr | Holm-sig |",
             "|---|---|---|---|---|---|---|"]
    for x in dres:
        lines.append(f"| {x['threshold']}{' (T_off)' if x['threshold'] == 100 else ''} | {x['median_df_C0']:,.0f} | "
                     f"{x['median_df_C7W512']:,.0f} | **{x['D']:+.4f}** | {x['p']:.2e} | {x['holm_threshold']:.4f} | {x['holm_sig']} |")
    lines.append("")
    lines.append(f"D(T_off) / D(51) = {ratio:.4f}  ->  H-feed verdict (pre-registered, mechanical): **{verdict}**")
    lines.append(f"Dose-response (secondary): D(75) = {D75:+.4f} vs D(51) = {D51:+.4f} -> D(75) >= D(51): {D75 >= D51}")
    open(f"{D}/fault_reduction.md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))

    # ---- secondary: wall-clock
    wall = {(r["arm"], r["tn"]): [] for r in rows}
    for r in rows:
        wall[(r["arm"], r["tn"])].append(float(r["wall_s"]))
    comps = []
    for tn, t in TS:
        b, c = wall[("C0", tn)], wall[("C7W512", tn)]
        d = dict(threshold=t, comparison=f"C7W512-{tn} vs C0-{tn}")
        d.update({k.replace("_c6", "_arm"): v for k, v in H.compare(b, c).items()})
        bk, ck = H.tukey_keep(b), H.tukey_keep(c)
        d2 = H.compare(bk, ck)
        d.update(noout_n_base=len(bk), noout_n_arm=len(ck), noout_delta_s=d2["delta_s"], noout_p=d2["p"])
        comps.append(d)
    thr, sig = H.holm([c["p"] for c in comps])
    thr2, sig2 = H.holm([c["noout_p"] for c in comps])
    for c, t_, s, t2, s2 in zip(comps, thr, sig, thr2, sig2):
        c.update(holm_threshold=t_, holm_sig=s, noout_holm_sig=s2,
                 verdict=("C7W512 faster" if c["delta_s"] < 0 else "C7W512 slower") if s else "no significant difference")
    with open(f"{D}/wallclock_comparisons.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(comps[0])); w.writeheader(); w.writerows(comps)
    for c in comps:
        print(f"{c['comparison']:24s} C0 {c['median_base']:.4f} C7W512 {c['median_arm']:.4f} d {c['delta_s']:+.4f}s "
              f"({c['delta_pct']:+.2f}%) p={c['p']:.2e} thr={c['holm_threshold']:.4f} {c['verdict']:26s} "
              f"d={c['cohen_d']:+.2f} MDE={c['mde_s']:.4f} MDE3={c['mde_bonf_s']:.4f} | noout {c['noout_delta_s']:+.4f} "
              f"p={c['noout_p']:.2e} sig={c['noout_holm_sig']} n={c['noout_n_base']}/{c['noout_n_arm']}")

    # ---- mechanism per cell
    mech = []
    for tn, t in TS:
        for arm in ("C0", "C7W512"):
            rs = cell(arm, tn)
            m = lambda k: st.median(g(r, k) for r in rs)  # noqa: E731
            mr = lambda k: st.median(r[k] for r in rs)  # noqa: E731
            mech.append(dict(threshold=t, arm=arm, n=len(rs), demand_faults=m("demand_faults"),
                             fault_already_resident=m("fault_already_resident"),
                             far_frac_distinct=m("fault_already_resident") / DISTINCT,
                             ft_predictions=m("ft_predictions"), ft_same_region=m("ft_same_region"),
                             enqueued=m("enqueued"), drops=m("drops"), spec_migrations=m("spec_migrations"),
                             spec_pages_requested=m("spec_pages_requested"),
                             prelock_outside_s=mr("outside_ns") / 1e9, enqueue_overhead_s=mr("enq_ns") / 1e9,
                             d5_s=mr("d5_ns") / 1e9, wall_median_s=st.median(wall[(arm, tn)])))
    with open(f"{D}/mechanism.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(mech[0])); w.writeheader(); w.writerows(mech)
    for x in mech:
        print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in x.items()})

    # ---- figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    xs = [51, 75, 100]
    for ax, key, ylab in ((axes[0], "demand_faults", "demand faults per run"), (axes[1], "wall", "process wall-clock (s)")):
        for arm, col, dx in (("C0", "tab:blue", -1.2), ("C7W512", "tab:green", 1.2)):
            meds = []
            for tn, t in TS:
                v = wall[(arm, tn)] if key == "wall" else [g(r, key) for r in cell(arm, tn)]
                ax.scatter([t + dx] * len(v), v, s=12, color=col, alpha=0.45, zorder=3)
                meds.append(st.median(v))
            ax.plot([t + dx for t in xs], meds, "o-", color=col, lw=1.8, zorder=4,
                    label=f"{arm} median (points: runs)")
        ax.set_xticks(xs); ax.set_xticklabels(["51 (default)", "75", "100 (T_off)"])
        ax.set_xlabel("uvm_perf_prefetch_threshold"); ax.set_ylabel(ylab); ax.grid(alpha=0.3)
    axes[0].set_title("Demand faults vs prefetch density threshold", fontsize=10)
    axes[1].set_title("Wall-clock vs prefetch density threshold", fontsize=10)
    axes[0].legend(fontsize=8)
    fig.suptitle("Gate E5: Stencil-24K, prefetcher on; C7W512 = cheap oracle + W=512 (n=10 per cell)", fontsize=10)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(f"{FIG}.{ext}", dpi=150)


if __name__ == "__main__":
    main()
