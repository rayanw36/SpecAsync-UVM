#!/usr/bin/env python3
"""C22 VII-5 / M4: share of the threshold-0 wall-clock gain of Stencil-24K that falls outside the GPU kernels, from E9's traced Stencil-24K runs (n = 3 per threshold) using the phase split of
tests/c4_cpu_fault_phases.py (results/analysis/derived/c4_e9_phase_split.csv: alloc, fill, setup, kernel, post) and the traced wall (e9_runs.csv wall_s_NOT_COMPARED).
Method as c4_e8_outside_kernels.csv: share = (delta_wall - delta_kernel) / delta_wall. Output consolidation/C22_VII5_STENCIL_CPU.md."""
import csv, statistics as st
ph = [r for r in csv.DictReader(open("results/analysis/derived/c4_e9_phase_split.csv")) if r["workload"] == "stencil"]
wall = {r["idx"]: float(r["wall_s_NOT_COMPARED"]) for r in csv.DictReader(open("results/analysis/gate_e/e9/e9_runs.csv")) if r["workload"] == "stencil"}
e7 = [r for r in csv.DictReader(open("results/analysis/gate_e/e7/e7_runs.csv")) if r["workload"] == "stencil" and r["label"] in ("stencil stock-t0", "stencil stock-t51")]
def med(t, f): return st.median(f(r) for r in ph if int(r["threshold"]) == t)
W = {t: st.median(wall[r["idx"]] for r in ph if int(r["threshold"]) == t) for t in (0, 51)}
P = {t: {k: med(t, lambda r, k=k: float(r[k + "_ms"]) / 1e3) for k in ("alloc", "fill", "setup", "kernel", "post")} for t in (0, 51)}
CF = {t: med(t, lambda r: float(r["cpu_faults"])) for t in (0, 51)}
dW = W[0] - W[51]; dK = P[0]["kernel"] - P[51]["kernel"]; dF = P[0]["fill"] - P[51]["fill"]
W7 = {t: st.median(float(r["wall_s"]) for r in e7 if r["label"].endswith(f"t{t}")) for t in (0, 51)}
dW7 = W7[0] - W7[51]
SUM = {t: sum(P[t].values()) for t in (0, 51)}
RES = {t: W[t] - SUM[t] for t in (0, 51)}
o = ["# C22 VII-5 / M4: CPU-side share of the threshold-0 gain on Stencil-24K", "",
     "Script `tests/c22_vii5_stencil_cpu.py`. Sources: `results/analysis/derived/c4_e9_phase_split.csv` (nsys phase split of the 3 + 3 traced E9 Stencil-24K runs; produced by `tests/c4_cpu_fault_phases.py`), `gate_e/e9/e9_runs.csv` (traced wall, column `wall_s_NOT_COMPARED`), `gate_e/e7/e7_runs.csv` (untraced wall, 10 + 10 runs). **E9 has a kernel-time split for Stencil-24K** (phase `kernel` = first kernel start to last kernel end of the 20 iterations, host sync between them included).", "",
     "## Phase medians (s), traced, n = 3 per threshold", "", "| phase | t0 | t51 | t0 - t51 |", "|---|---|---|---|"]
for k in ("alloc", "fill", "setup", "kernel", "post"):
    o.append(f"| {k} | {P[0][k]:.3f} | {P[51][k]:.3f} | {P[0][k]-P[51][k]:+.3f} |")
o += [f"| **traced wall** | {W[0]:.3f} | {W[51]:.3f} | {dW:+.3f} |", f"| CPU page faults (all in the host fill phase, `E9.cpu_phase.fill_only`) | {CF[0]:.0f} | {CF[51]:.0f} | {CF[0]-CF[51]:+.0f} ({CF[51]/CF[0]:.2f}x fewer at t0) |", "",
      "## Share of the gain outside the kernels", "",
      f"- Traced gain (t0 - t51 wall): {dW:+.3f} s, of which kernels {dK:+.3f} s and everything else {dW-dK:+.3f} s. **Outside-kernel share of the traced gain = {100*(dW-dK)/dW:.1f}% (an upper estimate: the tracing residual is included)** (host fill phase alone {dF:+.3f} s = {100*dF/dW:.1f}%).",
      f"- Where the traced wall is not in a phase: wall minus the five phases = {RES[0]:.3f} s at t0 and {RES[51]:.3f} s at t51 (CUDA initialisation, nsys start-up and trace flush), a difference of {RES[0]-RES[51]:+.3f} s, i.e. {100*(RES[0]-RES[51])/dW:.1f}% of the traced gain. The traced `post` and `alloc` phases differ by {P[0]['post']-P[51]['post']+P[0]['alloc']-P[51]['alloc']:+.3f} s. The traced gain is therefore {100*dK/dW:.1f}% kernels, {100*dF/dW:.1f}% host fill, and {100*(dW-dK-dF)/dW:.1f}% other (mostly the tracing residual, which grows with the GPU fault count: 27,876 faults at t0 against 91,935 at t51, `E9.ratio.stencil`).",
      f"- Untraced Stencil-24K gain (E7 Family A, medians of 10): {dW7:+.4f} s ({100*dW7/W7[51]:+.2f}%). The traced kernel difference ({dK:+.3f} s) is **larger than the whole untraced gain**, so the traced kernel/untraced wall mixture is not valid and no untraced share is given: the traced runs cannot be used to split the untraced gain.",
      "- Compare E8 dense cells (K >= 64, t0): 17-23% outside the kernels (`E8.outside_kernels.share_dense`), computed from untraced wall and benchmark-reported kernel time; E9 traced runs are inflated by nsys, so the traced share is an estimate with n = 3.", "",
      "Per-run values: " + "; ".join(f"idx {r['idx']} t{r['threshold']}: wall {wall[r['idx']]:.3f}, fill {float(r['fill_ms'])/1e3:.3f}, kernel {float(r['kernel_ms'])/1e3:.3f}" for r in ph) + ".", "",
      "Evidence ids (new): `C22.M4.stencil.outside_share_traced`, `C22.M4.stencil.fill_delta`, `C22.M4.stencil.cpu_faults`.", ""]
open("results/analysis/consolidation/C22_VII5_STENCIL_CPU.md", "w").write("\n".join(o))
print("\n".join(o[7:22]))
