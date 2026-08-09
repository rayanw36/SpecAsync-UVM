# cuFFT provenance audit (Task 1, read-only)

Working hypothesis: **CONFIRMED.** cuFFT ran on the T4 only during the Phase B sweep
(non-interleaved, pre-oracle-fix), producing timing and hit-rate telemetry that sit in
the untrusted tier for p4 and were never revisited by any later gate. The legacy 4.3-4.4%
figure is RTX 5070 Ti / driver 580.95.05 / Linux 6.14 and has no T4 counterpart under any
protocol, interleaved or otherwise.

---

## Q1 -- cuFFT in `results/phaseB/phaseB_timing.csv`?

Yes. 3 sizes (67108864, 134217728, 268435456) x policies p0-p3, n=20 runs/cell; p4 only
at one size (268435456), n=20.

```
0,0,cuFFT,134217728,229.4455,1.5984,20,229.0900
0,0,cuFFT,268435456,462.2015,3.9241,20,461.1750
0,0,cuFFT,67108864,116.8820,2.5108,20,116.3500
1,0,cuFFT,134217728,230.7025,2.3000,20,229.8300
1,0,cuFFT,268435456,460.7055,2.7634,20,460.2100
1,0,cuFFT,67108864,116.6370,2.8970,20,115.2950
2,0,cuFFT,134217728,230.7380,2.8730,20,229.2100
2,0,cuFFT,268435456,465.3590,6.9668,20,463.2500
2,0,cuFFT,67108864,118.1150,3.5664,20,115.5050
3,0,cuFFT,134217728,229.0980,2.0066,20,228.6600
3,0,cuFFT,268435456,461.1145,4.0321,20,458.9750
3,0,cuFFT,67108864,115.0170,0.3234,20,114.9450
4,0,cuFFT,268435456,1751.9000,4.9726,20,1752.0000
```
(columns: `policy,depth,benchmark,size,mean_ms,std_ms,n,median_ms`)

## Q2 -- cuFFT in `phaseB_telemetry.csv`; is the 25.47% hit rate a T4/595.71.05 row?

Yes, present at the same 3 sizes x p0-p3 + p4@268435456. **Correction to the working
hypothesis's framing: the 25.47% outlier is policy=2 (stride), not the oracle (p4)**:

```
2,0,cuFFT,67108864,1700,0.25471,1700.0,433.0,420976,602865,2216429,2778,416934
```
(columns: `policy,depth,benchmark,size,n_batches,hit_rate,enqueues,hits,lat_median_ns,lat_mean_ns,lat_p95_ns,ph01_median_ns,ph12_median_ns`)

Run metadata: `phaseB_timing.csv`/`phaseB_telemetry.csv` carry no per-row timestamp or
module srcversion column. The enclosing session's metadata comes from
`results/phaseB/gate_reports/gate5_analysis.md` ("all output files regenerated
2026-06-13") and `results/phaseB/SUMMARY.md` ("Platform: AWS g4dn.xlarge, Tesla T4
(sm_75), Driver 595.71.05"). No finer-grained (per-row) timestamp or srcversion exists
on disk for this file -- reported as such rather than inferred to a specific hour/build.

## Q3 -- cuFFT in Gate C / Gate D / Gate 3 / Phase C?

All four: **no.**

- Gate C interleaved reruns (`results/phaseB1/GATE_C_report.md`): STREAM only (C1/C2
  interleaved vs p0/p5). No mention of cuFFT anywhere in the file.
- Gate D oracle reruns (`results/phaseB1/GATE_D_report.md`, `results/phaseB1/gate_d/`):
  only 3 directories exist -- `stencil/`, `graphbfs/`, `stencil_ovsub/`. No `cufft/`
  directory, no mention in the report.
- Gate 3 favorable C0-C3 (`results/phaseB2/GATE3_report.md`, `tests/gate3_favorable_run.sh`):
  hardcodes `bench_stencil` and `bench_graph_bfs` only (`BENCH_STENCIL`, `BENCH_BFS`
  variables in the script); no cuFFT path exists in the script at all.
- Phase C dispatch decomposition (`results/phaseC/PHASEC_REPORT.md`): workloads are
  Stencil-8K/24K, GraphBFS-23, and the Stencil sweep. No cuFFT.

## Q4 -- does cuFFT still build for sm_75? What's actually there?

Source exists: `benchmarks/bench_cufft.cu` (38 lines, 1D C2C FFT via `cufftPlan1d` /
`cufftExecC2C`, `cudaMallocManaged` buffer). `benchmarks/Makefile`:

```make
NVCCFLAGS := -O3 -arch=sm_75
TARGETS := bench_stream bench_sgemm bench_stencil bench_cufft
bench_cufft: bench_cufft.cu
	$(NVCC) $(NVCCFLAGS) -o $@ $< -lcufft
```

The Makefile's *current* architecture flag is `sm_75` (Turing/T4) for all four
benchmarks -- this is the flag that would apply on a rebuild today, not necessarily what
any specific historical binary was built with. A pre-built `benchmarks/bench_cufft`
binary is also present in the tree (`ELF 64-bit ... not stripped`, no embedded arch
string readable without objdump/cuobjdump, which this task does not run). Per the task's
read-only constraint, **not rebuilt or executed** -- source presence and current build
flags reported, nothing more.

## Q5 -- the legacy 4.3-4.4% claim: which commit, platform, driver, raw file?

**Commit `ded7672` ("Add files via upload"), 2026-03-26, author Rayen Chikhaoui** --
the very first substantive commit in the repo's history (root of `main`), which added
`benchmarks/robust_results_baseline.csv` and `benchmarks/robust_results_specasync{1,2,3,____3}.csv`
alongside the four `bench_*.cu` sources and the compiled binaries. This predates the T4
port (`phaseB-v595-port`, first commit 2026-06-13) by over two months.

Recomputing per-size deltas directly from the raw CSVs (mean of n=50 runs/cell each):

```
robust_results_specasync1.csv vs robust_results_baseline.csv, cuFFT:
  size=67108864   base=23.352ms  spec=22.335ms  delta=-4.35%
  size=134217728  base=44.026ms  spec=42.126ms  delta=-4.32%
  size=268435456  base=86.377ms  spec=85.798ms  delta=-0.67%
robust_results_specasync2.csv: -1.73%, -1.34%, -1.88%
robust_results_specasync3.csv: +0.11%, -1.33%, -1.25%
```

The -4.35%/-4.32% pair (specasync1, the two smaller sizes) is the source of "up to 4.4%"
in the paper text. Platform is stated explicitly and consistently in four independent
places, none of which mention the T4:

- `README.md:14-17`: "NVIDIA Open Kernel Modules v580.95.05 ... Linux kernel 6.14.x ...
  tested on RTX 5070 Ti-class"
- `paper/abstract_v2.md:32-34`: "Microbenchmark evaluation on an RTX 5070 Ti (50-trial
  protocol ...) ... cuFFT gains up to 4.4% (mean, n=50, Exp1)"
- `paper/intro_revisions.md:38-39`: "On an RTX 5070 Ti, cuFFT workloads show up to 4.4%
  wall-time improvement"
- `benchmarks/RECONSTRUCTION_NOTES.md:93-95` and `:104-106`: "cuFFT is the benchmark most
  responsive to SpecAsync-UVM (Exp1 shows up to 4.4% speedup)"; stencil_oversub sizing
  table explicitly keyed to "RTX 5070 Ti (16 GB)"

**Confirmed, not refuted:** the 4.3-4.4% claim is RTX 5070 Ti / driver v580.95.05 / Linux
6.14.x, from `robust_results_specasync1.csv` vs `robust_results_baseline.csv`, n=50/cell,
non-interleaved ("Exp1"), committed before any T4 work existed in this repository.

## Q6 -- any cuFFT wall-clock number on the T4 under the interleaved protocol?

**Confirmed: no.** Per Q3, cuFFT never appears in Gate C (the only gate that established
and used the interleaved protocol on this repo's T4 runs). The only T4 cuFFT numbers
that exist anywhere are the Phase B `phaseB_timing.csv`/`phaseB_telemetry.csv` rows
(Q1/Q2), all-baseline-then-all-treatment by construction (same sweep script family as the
STREAM rows Gate C found to be host-noise-contaminated at this exact ordering).

---

## Manuscript implication

The paper cannot describe cuFFT as "confirmed on the T4" or imply the 4.3-4.4% figure
carries over to the current platform: it is a different GPU, different driver major
version, different kernel, and a different (non-interleaved, pre-Gate-C) measurement
protocol from every other number in this figure set. The T4 cuFFT data that does exist
(Phase B p0-p3) shows deltas within noise (-1.6% to +1.3%, comparable in magnitude to the
now-debunked STREAM -8.8%) and one hit-rate outlier (p2@67108864 = 25.47%, Task 0 manifest
does not currently exclude this row -- it is p2, not the demonstrated-artifact p4, and no
report anywhere calls it invalid; it is flagged here as unexplained rather than excluded,
since exclusion requires a report basis per Task 0's rules, not just an unusual value).
