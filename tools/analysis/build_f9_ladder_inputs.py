#!/usr/bin/env python3
"""Assemble F9's (bandwidth_scaling_ladder) four rungs into one committed CSV,
each value traced to a committed source -- no rung transcribed from a markdown
table without a machine-checkable source behind it.

Rung 1 -- PCIe raw bandwidth: computed from the negotiated-capability PCIe
generation/width fields in the two already-committed platform provenance files
(results/analysis/platform/{T4,5070TI}_PLATFORM_PROVENANCE.txt's "=== PCIe ==="
nvidia-smi --query-gpu block), via the standard PCI-SIG per-lane throughput
table (not looked up externally -- gen1/gen2 use 8b/10b coding, 80% efficiency;
gen3+ use 128b/130b coding, ~98.46% efficiency). MAX negotiated gen/width is
used for both platforms (5070 Ti's *current* link state was captured at GPU
idle and downclocks to gen1 for power saving -- documented in that file's own
"note: PCIe link current state" section -- so current != this platform's
compute-time capability; max is the comparable quantity, which is also what
GATE_B7_5070TI_PHASEC.md's "~8x" figure used).

Rung 2 -- kernel-loop time: 5070 Ti recovered from the already-committed
results/phaseC/decomp_overhead_5070ti/overhead_times_interleaved.csv (n=10,
DECOMP1 build, the corrected/interleaved pass GATE_B7_5070TI_PHASEC.md Section 2
cites). T4 side has NO committed or recoverable raw-trial source (see
PROVENANCE_GAPS_F7_F9_F11.md and this script's own tarball check below) --
left OUT per policy, not transcribed from PHASEC_REPORT.md's 1645.6ms table entry.

Rung 3 -- process wall-clock: both platforms recovered from the already-
committed results/phaseC/paired_wallclock{,_5070ti}/t3_paired_times*.csv
(Sweep-24K config, kept reps).

Rung 4 -- dispatch-window sum: both platforms recovered from per-batch decomp
CSVs -- T4 from the already-committed decomp_stencil_sweep_24000_t3.csv;
5070 Ti from decomp_sweep_24000_5070ti_t3.csv, built by
build_t3_sweep_csv_5070ti.py from raw .bin snapshots that were on disk but
never previously in any committed derived form.
"""
import csv
import re
import statistics as st
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLATFORM_DIR = REPO / "results/analysis/platform"
OUT_CSV = REPO / "results/figures/f9_ladder_inputs.csv"

# PCI-SIG per-lane effective throughput, GB/s (line-rate GT/s x coding efficiency / 8 bits/byte)
PCIE_GBPS_PER_LANE = {
    1: 2.5 * 0.80 / 8,
    2: 5.0 * 0.80 / 8,
    3: 8.0 * (128 / 130) / 8,
    4: 16.0 * (128 / 130) / 8,
    5: 32.0 * (128 / 130) / 8,
}


def parse_pcie(path):
    txt = path.read_text()
    m = re.search(r"pcie\.link\.gen\.current, pcie\.link\.gen\.max, "
                  r"pcie\.link\.width\.current, pcie\.link\.width\.max\n"
                  r"(\d+), (\d+), (\d+), (\d+)", txt)
    assert m, f"could not find PCIe csv block in {path}"
    gen_cur, gen_max, width_cur, width_max = (int(x) for x in m.groups())
    return dict(gen_cur=gen_cur, gen_max=gen_max, width_cur=width_cur, width_max=width_max)


def load_wall_clock_median(csv_path, config="Sweep-24K"):
    vals = []
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            if r["config"] != config:
                continue
            vals.append(float(r["wall_s"]))
    assert vals, f"no {config} rows in {csv_path}"
    return st.median(vals), len(vals)


def load_dispatch_window_sum(csv_path):
    tot = 0
    n = 0
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            tot += int(r["total_ns"])
            n += 1
    return tot, n


def load_kernel_loop_median_5070ti():
    path = REPO / "results/phaseC/decomp_overhead_5070ti/overhead_times_interleaved.csv"
    vals = []
    with open(path) as f:
        for r in csv.DictReader(f):
            if r["build"] == "DECOMP1":
                vals.append(float(r["time_ms"]))
    assert vals, f"no DECOMP1 rows in {path}"
    return st.median(vals), len(vals)


def main():
    rows = []

    # ---- Rung 1: PCIe ----
    print("=== Rung 1: PCIe raw bandwidth (from committed platform provenance files) ===")
    # gen = MAX negotiated (immune to idle power-state downclock, per 5070 Ti's own
    # provenance file note); width = CURRENT (reflects actual physical slot wiring --
    # T4's g4dn.xlarge instance is physically wired x8 despite the GPU chip supporting
    # x16 max, per its own "Link Width: Max=16x, Current=8x" reading; the 5070 Ti's
    # current width is already 16x, no slot limitation there). This combination is what
    # reproduces "gen3 x8" / "gen5 x16" exactly, not gen-max+width-max.
    t4_pcie = parse_pcie(PLATFORM_DIR / "T4_PLATFORM_PROVENANCE.txt")
    rtx_pcie = parse_pcie(PLATFORM_DIR / "5070TI_PLATFORM_PROVENANCE.txt")
    t4_gbps = PCIE_GBPS_PER_LANE[t4_pcie["gen_max"]] * t4_pcie["width_cur"]
    rtx_gbps = PCIE_GBPS_PER_LANE[rtx_pcie["gen_max"]] * rtx_pcie["width_cur"]
    pcie_ratio = rtx_gbps / t4_gbps
    print(f"  T4:      gen{t4_pcie['gen_max']} x{t4_pcie['width_cur']} (max gen, physically-wired width) = {t4_gbps:.3f} GB/s")
    print(f"  5070 Ti: gen{rtx_pcie['gen_max']} x{rtx_pcie['width_cur']} (max gen, physically-wired width) = {rtx_gbps:.3f} GB/s")
    print(f"  ratio: {pcie_ratio:.3f}x (report cites '~8x')")
    rows.append(dict(rung="pcie_raw_bandwidth", t4_value=f"{t4_gbps:.3f}", t4_unit="GB/s",
                      rtx5070ti_value=f"{rtx_gbps:.3f}", rtx5070ti_unit="GB/s",
                      ratio=f"{pcie_ratio:.3f}",
                      source="results/analysis/platform/{T4,5070TI}_PLATFORM_PROVENANCE.txt"))

    # ---- Rung 2: kernel-loop ----
    print("\n=== Rung 2: kernel-loop time ===")
    rtx_kl, rtx_kl_n = load_kernel_loop_median_5070ti()
    print(f"  5070 Ti: median={rtx_kl:.3f}ms (n={rtx_kl_n}, DECOMP1, interleaved) -- "
          f"cross-check vs GATE_B7_5070TI_PHASEC.md's cited 369.735ms")
    assert abs(rtx_kl - 369.735) < 0.001, f"5070Ti kernel-loop median {rtx_kl} != 369.735"
    print("  T4: NO recoverable raw-trial source (no committed CSV, not in the T4 tarball's "
          "Phase C paired-wallclock decomp dumps -- G3's original 5-trial overhead run predates "
          "any harness that saved raw trial times to disk). LEFT OUT of this rung -- "
          "PHASEC_REPORT.md's 1645.6ms is not transcribed here.")
    rows.append(dict(rung="kernel_loop_time", t4_value="", t4_unit="ms",
                      rtx5070ti_value=f"{rtx_kl:.3f}", rtx5070ti_unit="ms", ratio="",
                      source="T4: UNRECOVERABLE (see note); "
                             "5070Ti: results/phaseC/decomp_overhead_5070ti/overhead_times_interleaved.csv"))

    # ---- Rung 3: process wall-clock ----
    print("\n=== Rung 3: process wall-clock (Sweep-24K) ===")
    t4_wc, t4_wc_n = load_wall_clock_median(REPO / "results/phaseC/paired_wallclock/t3_paired_times.csv")
    rtx_wc, rtx_wc_n = load_wall_clock_median(REPO / "results/phaseC/paired_wallclock_5070ti/t3_paired_times_5070ti.csv")
    wc_ratio = t4_wc / rtx_wc
    print(f"  T4:      median={t4_wc:.3f}s (n={t4_wc_n})")
    print(f"  5070 Ti: median={rtx_wc:.3f}s (n={rtx_wc_n})")
    print(f"  ratio: {wc_ratio:.3f}x (report cites '3.79x')")
    rows.append(dict(rung="process_wallclock", t4_value=f"{t4_wc:.3f}", t4_unit="s",
                      rtx5070ti_value=f"{rtx_wc:.3f}", rtx5070ti_unit="s", ratio=f"{wc_ratio:.3f}",
                      source="results/phaseC/paired_wallclock{,_5070ti}/t3_paired_times*.csv"))

    # ---- Rung 4: dispatch-window sum ----
    print("\n=== Rung 4: dispatch-window sum (Sweep-24K) ===")
    t4_dw, t4_dw_n = load_dispatch_window_sum(REPO / "results/phaseC/paired_wallclock/decomp_stencil_sweep_24000_t3.csv")
    rtx_dw, rtx_dw_n = load_dispatch_window_sum(REPO / "results/phaseC/paired_wallclock_5070ti/decomp_sweep_24000_5070ti_t3.csv")
    dw_ratio = t4_dw / rtx_dw
    print(f"  T4:      sum(total_ns)={t4_dw} ({t4_dw/1e3:.1f}us, n={t4_dw_n} batches)")
    print(f"  5070 Ti: sum(total_ns)={rtx_dw} ({rtx_dw/1e3:.1f}us, n={rtx_dw_n} batches)")
    print(f"  ratio: {dw_ratio:.3f}x (report cites '2.35x')")
    rows.append(dict(rung="dispatch_window_sum", t4_value=f"{t4_dw/1e3:.1f}", t4_unit="us",
                      rtx5070ti_value=f"{rtx_dw/1e3:.1f}", rtx5070ti_unit="us", ratio=f"{dw_ratio:.3f}",
                      source="T4: results/phaseC/paired_wallclock/decomp_stencil_sweep_24000_t3.csv; "
                             "5070Ti: results/phaseC/paired_wallclock_5070ti/decomp_sweep_24000_5070ti_t3.csv"))

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["rung", "t4_value", "t4_unit", "rtx5070ti_value",
                                           "rtx5070ti_unit", "ratio", "source"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {OUT_CSV.relative_to(REPO)}")
    print("\n3 of 4 rungs are now fully both-sides-verifiable (PCIe, wall-clock, dispatch-window). "
          "Kernel-loop's T4 side remains unrecoverable -- rung left incomplete, not fabricated.")


if __name__ == "__main__":
    main()
